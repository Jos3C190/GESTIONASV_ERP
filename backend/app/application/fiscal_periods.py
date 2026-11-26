"""Cierre de período fiscal (V8b2) y la guardia que usan los demás módulos."""

from __future__ import annotations

import uuid
from datetime import date

from app.application.fiscal_books.use_cases import FiscalBookUseCases
from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.entities.fiscal_books import Period
from app.domain.entities.fiscal_period import (
    PeriodStatus,
    require_closable,
    require_reopen_reason,
)
from app.domain.ports.fiscal_period_repository import FiscalPeriodRepository


def _parse(value: str) -> Period:
    try:
        return Period.parse(value)
    except ValueError as error:
        raise BusinessRuleError(
            "El período debe tener la forma AAAA-MM.", code="fiscal_book_period_invalid"
        ) from error


class FiscalPeriodUseCases:
    def __init__(self, repository: FiscalPeriodRepository, books: FiscalBookUseCases) -> None:
        self._repository = repository
        self._books = books

    async def status(self, company_id: uuid.UUID, period_key: str, today: date) -> PeriodStatus:
        period = _parse(period_key)
        history = await self._repository.history(company_id, period)
        closed = next((item for item in history if item.status == "closed"), None)
        blockers: list[str] = []
        if closed is None:
            try:
                require_closable(period, today)
            except BusinessRuleError as error:
                blockers.append(error.message)
            unsealed = await self._repository.unsealed(company_id, period)
            if unsealed:
                blockers.append(
                    f"{unsealed} documento(s) del mes siguen sin sello de Hacienda (pendientes o en "
                    "contingencia)."
                )
        return PeriodStatus(period=period, closed=closed, history=history, blockers=blockers)

    async def close(
        self, company_id: uuid.UUID, period_key: str, actor_id: uuid.UUID, today: date
    ) -> PeriodStatus:
        period = _parse(period_key)
        await self._repository.lock(company_id, period)
        current = await self.status(company_id, period_key, today)
        if current.closed is not None:
            raise ConflictError(
                f"{period.label} ya está cerrado.", code="fiscal_period_already_closed"
            )
        require_closable(period, today)
        if current.blockers:
            raise BusinessRuleError(
                "No se puede cerrar el período: " + " ".join(current.blockers),
                code="fiscal_period_unsealed_documents",
            )
        view = await self._books.month(company_id, period_key)
        summary = {
            "mode": view.month.mode,
            **{key: str(value) for key, value in view.summary.__dict__.items()},
        }
        await self._repository.close(company_id, period, summary, actor_id)
        return await self.status(company_id, period_key, today)

    async def reopen(
        self,
        company_id: uuid.UUID,
        period_key: str,
        reason: str,
        actor_id: uuid.UUID,
        today: date,
    ) -> PeriodStatus:
        period = _parse(period_key)
        text = require_reopen_reason(reason)
        await self._repository.lock(company_id, period)
        current = await self.status(company_id, period_key, today)
        if current.closed is None:
            raise BusinessRuleError(
                f"{period.label} no está cerrado.", code="fiscal_period_not_closed"
            )
        await self._repository.reopen(company_id, current.closed.id, text, actor_id)
        return await self.status(company_id, period_key, today)

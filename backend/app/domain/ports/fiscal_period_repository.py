"""Puertos del cierre de período fiscal (V8b2)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Protocol

from app.domain.entities.fiscal_books import Period
from app.domain.entities.fiscal_period import PeriodClose


class ClosedPeriods(Protocol):
    async def closed_period(self, company_id: uuid.UUID, day: date) -> Period | None:
        """El mes de ``day`` si está cerrado; ``None`` si está abierto."""
        ...


class FiscalPeriodRepository(ClosedPeriods, Protocol):
    async def lock(self, company_id: uuid.UUID, period: Period) -> None: ...

    async def history(self, company_id: uuid.UUID, period: Period) -> list[PeriodClose]:
        """Cierres del mes, del más reciente al más antiguo."""
        ...

    async def unsealed(self, company_id: uuid.UUID, period: Period) -> int:
        """Documentos y eventos de retorno del mes que siguen sin sello."""
        ...

    async def close(
        self,
        company_id: uuid.UUID,
        period: Period,
        summary: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> uuid.UUID: ...

    async def reopen(
        self, company_id: uuid.UUID, close_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> None: ...

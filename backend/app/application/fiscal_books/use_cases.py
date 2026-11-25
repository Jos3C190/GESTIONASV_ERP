"""Libros de IVA y anexos del F-07 de una empresa, y datos fiscales de sus compras."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.fiscal_books import (
    FiscalMonth,
    MonthSummary,
    Period,
    PurchaseFiscalData,
    RentaPurchase,
    build_month,
    validate_purchase_fiscal,
)
from app.domain.ports.fiscal_book_repository import (
    FiscalBookRepository,
    Issuer,
    PendingPurchase,
    PurchaseFiscalView,
)

MODES = ("production", "test", "simulated")
# Una compra entra al libro cuando ya se recibió; en borrador o cancelada no.
RECORDABLE_STATUSES = ("received", "verified", "closed")


@dataclass(frozen=True)
class MonthView:
    issuer: Issuer
    month: FiscalMonth
    summary: MonthSummary
    modes: list[str]
    pending_purchases: list[PendingPurchase]
    contingency: int


def _period(value: str) -> Period:
    try:
        return Period.parse(value)
    except ValueError as error:
        raise BusinessRuleError(
            "El período debe tener la forma AAAA-MM.", code="fiscal_book_period_invalid"
        ) from error


class FiscalBookUseCases:
    def __init__(self, repository: FiscalBookRepository) -> None:
        self._repository = repository

    async def month(
        self, company_id: uuid.UUID, period_key: str, mode: str | None = None
    ) -> MonthView:
        period = _period(period_key)
        if mode is not None and mode not in MODES:
            raise BusinessRuleError(
                "El modo debe ser producción, pruebas o simulado.", code="fiscal_book_mode_invalid"
            )
        modes = await self._repository.modes(company_id, period)
        chosen = mode or ("production" if "production" in modes or not modes else modes[0])
        sales = await self._repository.sales(company_id, period, chosen)
        returns = await self._repository.returns(company_id, period, chosen)
        purchases = await self._repository.purchases(company_id, period)
        month = build_month(period, chosen, sales, returns, purchases)
        pending = await self._repository.pending_purchases(company_id, period)
        contingency = await self._repository.contingency_count(company_id, period, chosen)
        if contingency:
            month.warnings.append(
                f"{contingency} documento(s) del mes siguen en contingencia, sin sello: van al libro "
                "(art. 141 CT) pero no a los anexos hasta que Hacienda los selle. Aquí todavía no "
                "aparecen."
            )
        if pending:
            month.warnings.append(
                f"{len(pending)} compra(s) recibidas en el mes no tienen registrado el documento del "
                "proveedor y no entran al libro ni al anexo de compras."
            )
        return MonthView(
            issuer=await self._repository.issuer(company_id),
            month=month,
            summary=month.summary(),
            modes=modes,
            pending_purchases=pending,
            contingency=contingency,
        )

    async def purchase(self, company_id: uuid.UUID, purchase_id: uuid.UUID) -> PurchaseFiscalView:
        view = await self._repository.purchase(company_id, purchase_id)
        if view is None:
            raise NotFoundError("Compra no encontrada.", code="purchase_not_found")
        return view

    async def renta_defaults(self, company_id: uuid.UUID) -> RentaPurchase:
        return await self._repository.renta_defaults(company_id)

    async def save_renta_defaults(
        self, company_id: uuid.UUID, renta: RentaPurchase, actor_id: uuid.UUID
    ) -> RentaPurchase:
        renta = renta.validate()
        await self._repository.save_renta_defaults(company_id, renta, actor_id)
        return renta

    async def record_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        data: PurchaseFiscalData,
        actor_id: uuid.UUID,
        today: date,
    ) -> PurchaseFiscalView:
        view = await self.purchase(company_id, purchase_id)
        if view.status not in RECORDABLE_STATUSES:
            raise BusinessRuleError(
                "Registra el documento del proveedor cuando la compra ya se recibió.",
                code="fiscal_purchase_not_received",
            )
        clean = validate_purchase_fiscal(data, today)
        await self._repository.save_purchase_fiscal(company_id, purchase_id, clean, actor_id)
        return await self.purchase(company_id, purchase_id)

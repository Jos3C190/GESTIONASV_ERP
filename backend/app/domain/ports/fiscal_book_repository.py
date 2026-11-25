"""Lectura de un mes para los libros de IVA y el F-07, y datos fiscales de las compras."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.fiscal_books import (
    Period,
    PurchaseDocument,
    PurchaseFiscalData,
    RentaPurchase,
    ReturnEvent,
    SaleDocument,
)


@dataclass(frozen=True)
class Issuer:
    name: str
    nit: str | None
    nrc: str | None


@dataclass(frozen=True)
class PendingPurchase:
    """Compra recibida en el mes sin el documento del proveedor registrado."""

    id: uuid.UUID
    code: str
    supplier: str
    invoice_number: str | None
    invoice_date: date | None
    total: Decimal


@dataclass(frozen=True)
class PurchaseFiscalView:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID | None
    code: str
    status: str
    supplier_name: str
    supplier_ids: dict[str, str]
    invoice_number: str | None
    invoice_date: date | None
    exempt: Decimal
    taxed: Decimal
    vat: Decimal
    fiscal: PurchaseFiscalData | None
    recorded_at: datetime | None


class FiscalBookRepository(Protocol):
    async def issuer(self, company_id: uuid.UUID) -> Issuer: ...

    async def modes(self, company_id: uuid.UUID, period: Period) -> list[str]: ...

    async def sales(
        self, company_id: uuid.UUID, period: Period, mode: str
    ) -> list[SaleDocument]: ...

    async def returns(
        self, company_id: uuid.UUID, period: Period, mode: str
    ) -> list[ReturnEvent]: ...

    async def purchases(self, company_id: uuid.UUID, period: Period) -> list[PurchaseDocument]: ...

    async def pending_purchases(
        self, company_id: uuid.UUID, period: Period
    ) -> list[PendingPurchase]: ...

    async def contingency_count(self, company_id: uuid.UUID, period: Period, mode: str) -> int: ...

    async def purchase(
        self, company_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> PurchaseFiscalView | None: ...

    async def save_purchase_fiscal(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        data: PurchaseFiscalData,
        actor_id: uuid.UUID,
    ) -> None: ...

    async def renta_defaults(self, company_id: uuid.UUID) -> RentaPurchase: ...

    async def save_renta_defaults(
        self, company_id: uuid.UUID, renta: RentaPurchase, actor_id: uuid.UUID
    ) -> None: ...

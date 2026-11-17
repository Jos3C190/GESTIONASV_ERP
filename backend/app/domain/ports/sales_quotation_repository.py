"""Puerto de persistencia de la cotización de venta (bloque V2d)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.sales_quotation import QuotationStatus
from app.domain.ports.sales_document import DocumentLine, DocumentTotals, LineIdentity

# La cotización usa las piezas comunes de los documentos de venta.
QuotationLine = DocumentLine
QuotationTotals = DocumentTotals
__all__ = ["LineIdentity", "QuotationLine", "QuotationTotals"]


@dataclass(slots=True)
class Quotation:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    code: str
    quotation_date: date
    valid_until: date
    document_type: str
    price_list_id: uuid.UUID | None
    prices_include_vat: bool
    global_discount_percent: Decimal
    status: QuotationStatus
    version: int
    notes: str | None
    totals: DocumentTotals
    requires_authorization: bool
    authorization_reasons: tuple[str, ...]
    created_by_id: uuid.UUID
    lines: list[DocumentLine] = field(default_factory=list)
    issued_by_id: uuid.UUID | None = None
    issued_at: datetime | None = None
    authorized_by_id: uuid.UUID | None = None
    authorized_at: datetime | None = None
    authorization_note: str | None = None
    customer_response_by_id: uuid.UUID | None = None
    customer_response_at: datetime | None = None
    rejection_reason: str | None = None
    cancelled_by_id: uuid.UUID | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class QuotationFilters:
    branch_ids: tuple[uuid.UUID, ...] | None
    """``None``: todas las sucursales; tupla vacía: ninguna."""
    branch_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    status: str | None = None
    """Un ``QuotationStatus`` o ``expired`` (emitida con la vigencia vencida)."""
    from_date: date | None = None
    to_date: date | None = None
    today: date | None = None


@dataclass(frozen=True, slots=True)
class LinkedSale:
    id: uuid.UUID
    code: str


@dataclass(frozen=True, slots=True)
class PeopleNames:
    names: dict[uuid.UUID, str]

    def of(self, user_id: uuid.UUID | None) -> str | None:
        return self.names.get(user_id) if user_id else None


class SalesQuotationRepository(Protocol):
    async def line_identity(
        self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID | None, unit_id: int
    ) -> LineIdentity: ...

    async def branch_is_active(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool: ...

    async def get(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID, *, lock: bool = False
    ) -> Quotation | None: ...

    async def page(
        self, company_id: uuid.UUID, filters: QuotationFilters, page: int, size: int
    ) -> tuple[list[Quotation], int]: ...

    async def add(self, quotation: Quotation) -> None: ...

    async def save(self, quotation: Quotation, *, replace_lines: bool) -> None: ...

    async def linked_sale(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> LinkedSale | None: ...

    async def user_names(self, user_ids: set[uuid.UUID]) -> PeopleNames: ...

    async def validity_days(self, company_id: uuid.UUID) -> int: ...

    async def save_validity_days(
        self, company_id: uuid.UUID, days: int, actor_id: uuid.UUID
    ) -> None: ...

    async def lock_key(self, company_id: uuid.UUID, action: str, key: str) -> None: ...

    async def remembered(
        self, company_id: uuid.UUID, action: str, key: str
    ) -> tuple[str, uuid.UUID] | None:
        """Huella y recurso de una clave de idempotencia ya usada."""
        ...

    async def remember(
        self,
        company_id: uuid.UUID,
        action: str,
        key: str,
        fingerprint: str,
        resource_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None: ...

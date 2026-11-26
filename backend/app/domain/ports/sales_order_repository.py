"""Puerto de persistencia del pedido de venta (bloque V2e)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.sales_order import DeliveryMode, ExchangeSource, OrderStatus, PaymentTerms
from app.domain.ports.sales_document import DocumentLine, DocumentTotals, LineIdentity
from app.domain.ports.sales_quotation_repository import PeopleNames


@dataclass(slots=True)
class OrderLine:
    line: DocumentLine
    source_quotation_line_id: uuid.UUID | None = None
    delivered_base: Decimal = Decimal("0")
    """Unidad base ya entregada en entregas confirmadas (solo lectura)."""


@dataclass(slots=True)
class Order:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    code: str
    document_type: str
    price_list_id: uuid.UUID | None
    prices_include_vat: bool
    global_discount_percent: Decimal
    status: OrderStatus
    version: int
    notes: str | None
    totals: DocumentTotals
    requires_authorization: bool
    authorization_reasons: tuple[str, ...]
    promised_date: date
    delivery_mode: DeliveryMode
    delivery_address_id: uuid.UUID | None
    delivery_address_text: str | None
    payment_terms: PaymentTerms
    credit_days: int
    created_by_id: uuid.UUID
    quotation_id: uuid.UUID | None = None
    exchange_return_id: uuid.UUID | None = None
    lines: list[OrderLine] = field(default_factory=list)
    confirmed_by_id: uuid.UUID | None = None
    confirmed_at: datetime | None = None
    authorized_by_id: uuid.UUID | None = None
    authorized_at: datetime | None = None
    authorization_note: str | None = None
    cancelled_by_id: uuid.UUID | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def delivered_any(self) -> bool:
        return any(item.delivered_base > 0 for item in self.lines)


@dataclass(frozen=True, slots=True)
class OrderFilters:
    branch_ids: tuple[uuid.UUID, ...] | None
    """``None``: todas las sucursales; tupla vacía: ninguna."""
    branch_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    status: str | None = None
    from_date: date | None = None
    to_date: date | None = None


@dataclass(frozen=True, slots=True)
class DeliveryAddress:
    id: uuid.UUID
    text: str


class SalesOrderRepository(Protocol):
    async def line_identity(
        self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID | None, unit_id: int
    ) -> LineIdentity: ...

    async def branch_is_active(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool: ...

    async def get(
        self, company_id: uuid.UUID, order_id: uuid.UUID, *, lock: bool = False
    ) -> Order | None: ...

    async def page(
        self, company_id: uuid.UUID, filters: OrderFilters, page: int, size: int
    ) -> tuple[list[Order], int]: ...

    async def add(self, order: Order) -> None: ...

    async def save(self, order: Order, *, replace_lines: bool) -> None: ...

    async def for_quotation(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> Order | None: ...

    async def exchange_source(
        self, company_id: uuid.UUID, return_id: uuid.UUID, *, exclude_order: uuid.UUID | None
    ) -> ExchangeSource | None:
        """La devolución que se cambia, con lo aceptado y el otro pedido de cambio vigente."""
        ...

    async def delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> DeliveryAddress | None:
        """Una dirección activa del cliente, con su texto para copiarlo al pedido."""
        ...

    async def lock_reservations(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, items: set[uuid.UUID]
    ) -> None:
        """Serializa confirmaciones que apartan los mismos artículos en la sucursal."""
        ...

    async def on_hand(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, items: set[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]:
        """Unidad base disponible en las bodegas activas (no de tránsito) de la sucursal."""
        ...

    async def reserved(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        items: set[uuid.UUID],
        exclude_order: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        """Lo pendiente de entregar de los pedidos confirmados de la sucursal."""
        ...

    async def user_names(self, user_ids: set[uuid.UUID]) -> PeopleNames: ...

    async def invoiced(self, company_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        """Si el pedido tiene un documento fiscal vigente (no fallido)."""
        ...

    async def lock_key(self, company_id: uuid.UUID, action: str, key: str) -> None: ...

    async def remembered(
        self, company_id: uuid.UUID, action: str, key: str
    ) -> tuple[str, uuid.UUID] | None: ...

    async def remember(
        self,
        company_id: uuid.UUID,
        action: str,
        key: str,
        fingerprint: str,
        resource_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None: ...

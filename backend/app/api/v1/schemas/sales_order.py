"""DTO del pedido de venta (bloque V2e)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.sales_quotation import (
    AuthorizationReasonOut,
    QuotationLineIn,
    QuotationLineOut,
    QuotationPageMeta,
)

OrderStatusOut = Literal["draft", "pending_authorization", "confirmed", "cancelled"]


class DeliveryIn(BaseModel):
    promised_date: date
    delivery_mode: Literal["pickup", "delivery"]
    delivery_address_id: UUID | None = None

    @model_validator(mode="after")
    def _address_matches_mode(self) -> DeliveryIn:
        if self.delivery_mode == "delivery" and self.delivery_address_id is None:
            raise ValueError("Elige la dirección de entrega del cliente.")
        if self.delivery_mode == "pickup" and self.delivery_address_id is not None:
            raise ValueError("Un pedido con retiro en sucursal no lleva dirección de entrega.")
        return self


class OrderDraftIn(DeliveryIn):
    branch_id: UUID
    customer_id: UUID
    document_type: Literal["01", "03"] | None = None
    global_discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[QuotationLineIn] = Field(min_length=1, max_length=200)
    exchange_return_id: UUID | None = None
    """V8b1: devolución aceptada que este pedido cambia por otro producto."""


class OrderUpdateIn(OrderDraftIn):
    expected_version: int = Field(ge=1)


class OrderFromQuotationIn(DeliveryIn):
    notes: str | None = Field(default=None, max_length=4000)


class OrderActionIn(BaseModel):
    expected_version: int = Field(ge=1)


class OrderNoteIn(OrderActionIn):
    note: str | None = Field(default=None, max_length=1000)


class OrderReasonIn(OrderActionIn):
    reason: str = Field(min_length=1, max_length=1000)


class OrderLineOut(QuotationLineOut):
    source_quotation_line_id: UUID | None
    quantity_delivered_base: Decimal
    quantity_pending_base: Decimal
    available_base: Decimal | None
    """Disponible para vender en la sucursal sin contar este pedido (solo en borrador o por
    autorizar)."""


class OrderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_deliver_on_confirm: bool
    """Al confirmar el pedido se descuenta la existencia y la salida queda en el kardex."""


class AutoDeliveryOut(BaseModel):
    """Salida automática al confirmar el pedido (pedido del ingeniero, 24/11/2026)."""

    delivery_id: UUID | None = None
    delivery_code: str | None = None
    pending_products: list[str] = Field(default_factory=list)
    """Productos que no se cubrieron con unidades completas: quedan apartados."""
    message: str | None = None


class OrderOut(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    customer_id: UUID
    customer_code: str
    customer_name: str
    quotation_id: UUID | None
    quotation_code: str | None
    exchange_return_id: UUID | None = None
    exchange_return_code: str | None = None
    code: str
    document_type: Literal["01", "03"]
    price_list_id: UUID | None
    price_list_name: str | None
    prices_include_vat: bool
    global_discount_percent: Decimal
    status: OrderStatusOut
    delivery_progress: Literal["pending", "partial", "complete"]
    version: int
    notes: str | None
    total_not_subject: Decimal
    total_exempt: Decimal
    total_taxed: Decimal
    subtotal_sales: Decimal
    total_discount: Decimal
    subtotal: Decimal
    vat: Decimal
    vat_perceived: Decimal
    vat_withheld: Decimal
    total: Decimal
    total_in_words: str
    requires_authorization: bool
    authorization_reasons: list[AuthorizationReasonOut]
    costs_visible: bool
    promised_date: date
    delivery_mode: Literal["pickup", "delivery"]
    delivery_address_id: UUID | None
    delivery_address_text: str | None
    payment_terms: Literal["cash", "credit"]
    credit_days: int
    created_by_id: UUID
    created_by_name: str | None
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    authorized_by_name: str | None
    authorized_at: datetime | None
    authorization_note: str | None
    cancelled_by_name: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    lines: list[OrderLineOut]
    auto_delivery: AutoDeliveryOut | None = None
    created_at: datetime | None
    updated_at: datetime | None


class OrderPage(BaseModel):
    items: list[OrderOut]
    meta: QuotationPageMeta

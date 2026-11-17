"""DTO de la cotización de venta rediseñada (bloque V2d)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

QuotationStatusOut = Literal[
    "draft", "pending_authorization", "issued", "accepted", "rejected", "cancelled"
]


class QuotationLineIn(BaseModel):
    product_id: int = Field(gt=0)
    variant_id: UUID | None = None
    unit_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    """Si falta, se aplica el descuento sugerido."""
    manual_price: Decimal | None = Field(default=None, ge=0, max_digits=19, decimal_places=8)
    """Precio escrito a mano en la forma de la lista. Exige ``sales_prices:override``."""


class QuotationDraftIn(BaseModel):
    branch_id: UUID
    customer_id: UUID
    document_type: Literal["01", "03"] | None = None
    valid_until: date | None = None
    global_discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[QuotationLineIn] = Field(min_length=1, max_length=200)


class QuotationUpdateIn(QuotationDraftIn):
    expected_version: int = Field(ge=1)


class QuotationActionIn(BaseModel):
    expected_version: int = Field(ge=1)


class QuotationNoteIn(QuotationActionIn):
    note: str | None = Field(default=None, max_length=1000)


class QuotationReasonIn(QuotationActionIn):
    reason: str = Field(min_length=1, max_length=1000)


class AuthorizationReasonOut(BaseModel):
    code: str
    message: str


class QuotationLineOut(BaseModel):
    id: UUID | None
    line_number: int
    product_id: int
    variant_id: UUID | None
    inventory_item_id: UUID
    product_sku: str
    product_name: str
    unit_id: int
    unit_name: str
    base_unit_id: int
    base_unit_name: str
    unit_factor: Decimal
    quantity: Decimal
    quantity_base: Decimal
    price_list_id: UUID | None
    list_price: Decimal | None
    price_overridden: bool
    unit_price: Decimal
    discount_percent: Decimal
    suggested_discount_percent: Decimal
    suggested_discount_source: Literal["none", "customer", "volume"]
    tax_treatment: Literal["taxed", "exempt", "not_subject"]
    item_type: Literal["1", "2", "3"]
    document_unit_price: Decimal
    discount_amount: Decimal
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat_item: Decimal | None
    line_total: Decimal
    cost: Decimal | None
    """Solo para quien puede ver costos o autorizar descuentos."""
    margin_percent: Decimal | None
    authorization_reasons: list[AuthorizationReasonOut]


class QuotationOut(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    customer_id: UUID
    customer_code: str
    customer_name: str
    code: str
    quotation_date: date
    valid_until: date
    document_type: Literal["01", "03"]
    price_list_id: UUID | None
    price_list_name: str | None
    prices_include_vat: bool
    global_discount_percent: Decimal
    status: QuotationStatusOut
    expired: bool
    """Emitida con la vigencia vencida: ya no se puede aceptar."""
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
    created_by_id: UUID
    created_by_name: str | None
    issued_by_name: str | None
    issued_at: datetime | None
    authorized_by_name: str | None
    authorized_at: datetime | None
    authorization_note: str | None
    customer_response_by_name: str | None
    customer_response_at: datetime | None
    rejection_reason: str | None
    cancelled_by_name: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    sale_id: UUID | None
    sale_code: str | None
    lines: list[QuotationLineOut]
    created_at: datetime | None
    updated_at: datetime | None


class QuotationPageMeta(BaseModel):
    page: int
    size: int
    total: int
    pages: int


class QuotationPage(BaseModel):
    items: list[QuotationOut]
    meta: QuotationPageMeta


class QuotationSettingsIn(BaseModel):
    quotation_validity_days: int = Field(ge=1, le=365)


class QuotationSettingsOut(BaseModel):
    quotation_validity_days: int

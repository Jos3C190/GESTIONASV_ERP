"""Public DTOs for clients, sales quotations and sales without delivery."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SalesCustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None


class SalesCustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    is_active: bool | None = None


class SalesCustomerOut(BaseModel):
    id: UUID
    company_id: UUID
    code: str
    name: str
    phone: str | None
    email: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SalesLineInput(BaseModel):
    product_id: int = Field(gt=0)
    variant_id: UUID | None = None
    unit_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)


class SalesQuotationCreate(BaseModel):
    branch_id: UUID
    customer_id: UUID
    valid_until: date
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[SalesLineInput] = Field(min_length=1, max_length=200)


class SalesQuotationUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    valid_until: date
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[SalesLineInput] = Field(min_length=1, max_length=200)


class SalesDocumentAction(BaseModel):
    expected_version: int = Field(ge=1)


class SalesCancellation(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class SalesDraftLineUpdate(BaseModel):
    source_quotation_line_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)


class SalesDraftUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[SalesDraftLineUpdate] = Field(min_length=1, max_length=200)


class SalesLineOut(BaseModel):
    id: UUID
    source_quotation_line_id: UUID
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
    unit_price: Decimal
    line_total: Decimal
    quantity_delivered_base: Decimal
    quantity_pending_base: Decimal


class SalesQuotationOut(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    customer_id: UUID
    customer_code: str
    customer_name: str
    code: str
    quotation_date: date
    valid_until: date
    currency: Literal["USD"]
    subtotal: Decimal
    total: Decimal
    status: Literal["draft", "confirmed", "cancelled", "expired"]
    stored_status: Literal["draft", "confirmed", "cancelled"]
    version: int
    notes: str | None
    converted: bool
    sale_id: UUID | None
    sale_code: str | None
    lines: list[SalesLineOut]
    created_at: datetime
    updated_at: datetime


class SaleOut(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    customer_id: UUID
    customer_code: str
    customer_name: str
    quotation_id: UUID
    quotation_code: str
    code: str
    currency: Literal["USD"]
    subtotal: Decimal
    total: Decimal
    status: Literal["draft", "confirmed", "cancelled"]
    version: int
    notes: str | None
    delivery_progress: Literal["pending", "partial", "complete"]
    lines: list[SalesLineOut]
    created_at: datetime
    updated_at: datetime


class SalesDeliveryAssignmentIn(BaseModel):
    sale_line_id: UUID
    handling_unit_id: UUID


class SalesDeliveryCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    assignments: list[SalesDeliveryAssignmentIn] = Field(min_length=1, max_length=200)


class SalesDeliveryDraftUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=4000)
    assignments: list[SalesDeliveryAssignmentIn] = Field(min_length=1, max_length=200)


class SalesDeliveryCancellation(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class SalesDeliveryStockUnitOut(BaseModel):
    handling_unit_id: UUID
    code: str
    inventory_item_id: UUID
    quantity_base: Decimal
    base_unit_name: str
    lot_code: str | None
    expiry_date: date | None
    warehouse_id: UUID
    warehouse_name: str
    location_id: UUID
    location_code: str
    packaging_snapshot: dict[str, Any] | None


class SalesDeliveryStockLineOut(BaseModel):
    sale_line_id: UUID
    product_sku: str
    product_name: str
    unit_name: str
    base_unit_name: str
    quantity_pending_base: Decimal
    units: list[SalesDeliveryStockUnitOut]


class SalesDeliveryAllocationOut(BaseModel):
    id: UUID
    handling_unit_id: UUID
    handling_unit_code: str | None
    warehouse_id: UUID
    location_id: UUID
    inventory_lot_detail_id: UUID | None
    lot_code: str | None
    expiry_date: date | None
    quantity_base: Decimal
    movement_id: UUID | None
    movement_line_id: UUID | None
    valuation_entry_id: UUID | None


class SalesDeliveryLineOut(BaseModel):
    id: UUID
    sale_line_id: UUID
    product_sku: str
    product_name: str
    unit_name: str
    base_unit_name: str
    quantity_base: Decimal
    quantity_in_sale_unit: Decimal
    unit_factor: Decimal
    allocations: list[SalesDeliveryAllocationOut]


class SalesDeliveryOut(BaseModel):
    id: UUID
    company_id: UUID
    branch_id: UUID
    sale_id: UUID
    code: str
    status: Literal["draft", "confirmed", "cancelled"]
    version: int
    notes: str | None
    created_by_id: UUID
    confirmed_by_id: UUID | None
    confirmed_at: datetime | None
    cancelled_by_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[SalesDeliveryLineOut]


class SalesUnitOut(BaseModel):
    unit_id: int
    name: str
    factor: Decimal
    packaging_definition_id: UUID | None
    packaging_version: int | None


class SalesCatalogItemOut(BaseModel):
    product_id: int
    variant_id: UUID | None
    inventory_item_id: UUID
    sku: str
    name: str
    base_unit_id: int
    base_unit_name: str
    units: list[SalesUnitOut]


class SalesPageMeta(BaseModel):
    page: int
    size: int
    total: int
    pages: int


class SalesCustomerPage(BaseModel):
    items: list[SalesCustomerOut]
    meta: SalesPageMeta


class SalesQuotationPage(BaseModel):
    items: list[SalesQuotationOut]
    meta: SalesPageMeta


class SalesPage(BaseModel):
    items: list[SaleOut]
    meta: SalesPageMeta

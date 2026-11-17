"""Public DTOs for clients, sales quotations and sales without delivery."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SalesDocumentAction(BaseModel):
    expected_version: int = Field(ge=1)


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

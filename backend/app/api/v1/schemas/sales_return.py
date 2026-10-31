"""HTTP contracts for customer returns."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ReturnReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)
]


class SalesReturnLineCreate(BaseModel):
    delivery_allocation_id: uuid.UUID
    quantity_base: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    reason: ReturnReason
    declared_condition: Literal["resalable", "damaged", "wrong_item", "other"]


class SalesReturnCreate(BaseModel):
    notes: str | None = Field(None, max_length=4000)
    lines: list[SalesReturnLineCreate] = Field(..., min_length=1, max_length=100)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class SalesReturnResolveLine(BaseModel):
    return_line_id: uuid.UUID
    decision: Literal["accepted", "rejected"]
    quantity_base: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    condition: Literal["resalable", "damaged", "wrong_item", "other"]
    reason: ReturnReason
    destination_location_id: uuid.UUID | None = None


class SalesReturnResolve(BaseModel):
    lines: list[SalesReturnResolveLine] = Field(..., min_length=1, max_length=100)


class SalesReturnEventOut(BaseModel):
    id: uuid.UUID
    decision: str
    quantity_base: Decimal
    condition: str
    reason: str
    destination_location_id: uuid.UUID | None
    movement_id: uuid.UUID | None
    movement_line_id: uuid.UUID | None
    valuation_entry_id: uuid.UUID | None
    actor_id: uuid.UUID
    created_at: datetime


class SalesReturnEvidenceOut(BaseModel):
    document_id: uuid.UUID
    title: str
    file_name: str


class SalesReturnLineOut(BaseModel):
    id: uuid.UUID
    delivery_id: uuid.UUID
    delivery_code: str
    delivery_allocation_id: uuid.UUID
    source_handling_unit_id: uuid.UUID
    inventory_item_id: uuid.UUID
    product_sku: str
    product_name: str
    unit_name: str
    base_unit_name: str
    lot_code: str | None
    quantity_received_base: Decimal
    quantity_accepted_base: Decimal
    quantity_rejected_base: Decimal
    quantity_pending_base: Decimal
    quantity_returnable_base: Decimal
    reason: str
    declared_condition: str
    events: list[SalesReturnEventOut]


class SalesReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    sale_id: uuid.UUID
    code: str
    status: str
    notes: str | None
    created_by_id: uuid.UUID
    received_by_id: uuid.UUID | None
    received_at: datetime | None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    evidence: list[SalesReturnEvidenceOut] = Field(default_factory=list)
    lines: list[SalesReturnLineOut]


class SalesReturnableAllocationOut(BaseModel):
    delivery_id: uuid.UUID
    delivery_code: str
    delivery_line_id: uuid.UUID
    delivery_allocation_id: uuid.UUID
    delivery_date: datetime
    handling_unit_code: str | None
    inventory_item_id: uuid.UUID
    product_sku: str
    product_name: str
    unit_name: str
    base_unit_name: str
    lot_code: str | None
    quantity_delivered_base: Decimal
    quantity_returned_base: Decimal
    quantity_reserved_base: Decimal
    quantity_returnable_base: Decimal


class SalesReturnCancellation(BaseModel):
    reason: ReturnReason


__all__ = [
    "SalesReturnCancellation",
    "SalesReturnCreate",
    "SalesReturnEvidenceOut",
    "SalesReturnOut",
    "SalesReturnResolve",
    "SalesReturnableAllocationOut",
]

"""HTTP contracts for company-scoped inventory transfer documents."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.api.v1.schemas.common import ORMOut
from app.api.v1.schemas.inventory import StrictModel


class TransferDemandAllocationIn(StrictModel):
    purchase_request_detail_id: uuid.UUID
    allocated_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class TransferLineIn(StrictModel):
    handling_unit_id: uuid.UUID
    quantity_base: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    inventory_lot_detail_id: uuid.UUID | None = None
    demand_allocations: list[TransferDemandAllocationIn] = Field(default_factory=list, max_length=100)
    excess_reason: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)


class TransferCreateIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    origin_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=4000)
    lines: list[TransferLineIn] = Field(min_length=1, max_length=500)


class TransferUpdateIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    origin_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID | None
    notes: str | None = Field(max_length=4000)
    lines: list[TransferLineIn] = Field(min_length=1, max_length=500)


class TransferCommandIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)


class TransferDispatchIn(TransferCommandIn):
    vehicle_id: uuid.UUID


class TransferReceiptLineIn(StrictModel):
    transfer_detail_id: uuid.UUID
    destination_location_id: uuid.UUID
    quantity_base: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class TransferReceiveIn(TransferCommandIn):
    lines: list[TransferReceiptLineIn] = Field(min_length=1, max_length=500)


class TransferIncidentIn(TransferCommandIn):
    reason: str = Field(min_length=5, max_length=4000)
    evidence_reference: str | None = Field(None, max_length=500)


class TransferIncidentResolveIn(TransferCommandIn):
    resolution: Literal["resume_transit", "close_received"]
    resolution_notes: str = Field(min_length=5, max_length=4000)


class InventoryVehicleCreateIn(StrictModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2, max_length=120)


class InventoryVehicleStatusIn(StrictModel):
    status: Literal["active", "inactive"]


class InventoryVehicleOut(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    status: Literal["active", "inactive"]
    transit_warehouse_id: uuid.UUID
    transit_warehouse_name: str
    transit_location_id: uuid.UUID
    created_at: datetime


class TransferVehicleReferenceOut(StrictModel):
    id: uuid.UUID
    code: str
    name: str
    status: str


class TransferDemandAllocationOut(StrictModel):
    purchase_request_detail_id: uuid.UUID
    request_id: uuid.UUID
    request_code: str
    branch_id: uuid.UUID
    branch_name: str
    quantity_requested: Decimal
    allocated_quantity: Decimal
    quantity_dispatched: Decimal
    quantity_received: Decimal
    quantity_adjusted_out: Decimal


class TransferReceiptOut(StrictModel):
    id: uuid.UUID
    movement_id: uuid.UUID
    handling_unit_id: uuid.UUID
    handling_unit_code: str | None
    quantity_received: Decimal
    received_by_id: uuid.UUID
    received_at: datetime


class TransferLineOut(StrictModel):
    id: uuid.UUID
    line_number: int
    inventory_item_id: uuid.UUID
    product_id: int | None
    variant_id: uuid.UUID | None
    sku: str | None
    product_name: str
    base_unit_id: int | None
    base_unit_name: str | None
    base_unit_symbol: str | None
    presentation_name: str | None
    inventory_lot_detail_id: uuid.UUID | None
    inventory_lot_detail_code: str | None
    source_handling_unit_id: uuid.UUID
    source_handling_unit_code: str | None
    transit_handling_unit_id: uuid.UUID | None
    transit_handling_unit_code: str | None
    quantity_planned: Decimal
    quantity_dispatched: Decimal
    quantity_received: Decimal
    quantity_in_transit: Decimal
    quantity_returned: Decimal
    quantity_adjusted_out: Decimal
    excess_reason: str | None
    notes: str | None
    demand_allocations: list[TransferDemandAllocationOut]
    receipts: list[TransferReceiptOut]


class TransferIncidentOut(StrictModel):
    id: uuid.UUID
    status: Literal["open", "resolved"]
    reason: str
    evidence_reference: str | None
    opened_by_id: uuid.UUID
    opened_at: datetime
    resolution: str | None
    resolution_notes: str | None
    resolved_by_id: uuid.UUID | None
    resolved_at: datetime | None


class InventoryTransferOut(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    origin_warehouse_id: uuid.UUID
    origin_warehouse_name: str
    origin_branch_id: uuid.UUID | None
    destination_warehouse_id: uuid.UUID
    destination_warehouse_name: str
    destination_branch_id: uuid.UUID | None
    vehicle: TransferVehicleReferenceOut | None
    status: Literal["preparation", "in_transit", "received", "closed_with_adjustment", "incident", "cancelled"]
    notes: str | None
    created_by_id: uuid.UUID
    created_at: datetime
    dispatched_by_id: uuid.UUID | None
    dispatched_at: datetime | None
    received_by_id: uuid.UUID | None
    received_at: datetime | None
    dispatch_movement_id: uuid.UUID | None
    lines: list[TransferLineOut]
    incidents: list[TransferIncidentOut]


class TransferDemandOut(StrictModel):
    purchase_request_detail_id: uuid.UUID
    purchase_request_id: uuid.UUID
    request_code: str
    request_status: str
    branch_id: uuid.UUID
    branch_name: str
    request_date: datetime
    required_date: datetime | None
    product_id: int
    inventory_item_id: uuid.UUID | None
    product_name: str
    sku: str | None
    unit_id: int
    unit_name: str
    unit_symbol: str | None
    quantity_requested: Decimal
    quantity_assigned: Decimal
    quantity_dispatched: Decimal
    quantity_in_transit: Decimal
    quantity_received: Decimal
    quantity_adjusted_out: Decimal
    quantity_pending: Decimal

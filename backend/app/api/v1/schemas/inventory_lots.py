"""Read contracts for receipt lots and grouped placement progress."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InventoryLotHandlingUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    quantity_base: Decimal
    stock_status: str
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    location_code: str
    expiry_date: date | None
    lot_code: str | None
    measurement_status: str
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    pending_placement_quantity_base: Decimal
    placed_quantity_base: Decimal


class InventoryLotLineOut(BaseModel):
    inventory_lot_detail_ids: list[uuid.UUID]
    inventory_lot_detail_id: uuid.UUID
    receipt_lot_detail_code: str
    purchase_detail_id: uuid.UUID
    inventory_item_id: uuid.UUID
    product_sku: str | None
    product_name: str | None
    base_unit_id: int
    base_unit_name: str | None
    base_unit_symbol: str | None
    accepted_quantity_base: Decimal
    placed_quantity_base: Decimal
    pending_placement_quantity_base: Decimal
    handling_units: list[InventoryLotHandlingUnitOut]


class LegacyInventoryStockOut(BaseModel):
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    location_code: str | None
    inventory_item_id: uuid.UUID
    product_sku: str | None
    product_name: str
    base_unit_symbol: str
    stock_status: str
    total_quantity_base: Decimal
    attributable_quantity_base: Decimal
    legacy_quantity_base: Decimal
    legacy_handling_unit_count: int
    legacy_handling_unit_quantity_base: Decimal
    reconciliation_difference: Decimal
    reconciled: bool


class InventoryLotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_code: str
    warehouse_id: uuid.UUID
    code: str
    received_at: datetime
    placement_status: Literal["pending_placement", "partially_placed", "placed"]
    costing_status: str
    lines: list[InventoryLotLineOut]


class InventoryLotPageOut(BaseModel):
    items: list[InventoryLotOut]
    page: int
    size: int
    total: int
    legacy_stock: list[LegacyInventoryStockOut] = Field(default_factory=list)

"""Cost-free stock projections and explicit administrator opening input."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Positive = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=60)]


class WarehouseStockRow(BaseModel):
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str | None
    base_unit_symbol: str
    location_id: uuid.UUID
    location_code: str
    stock_status: str
    lot_code: str | None
    expiry_date: date | None
    quantity_base: Decimal


class WarehouseStockPage(BaseModel):
    items: list[WarehouseStockRow]
    total: int
    page: int
    size: int


class ProductOpeningIn(BaseModel):
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity_base: Positive
    gross_weight_kg: Positive
    volume_m3: Positive
    unit_cost: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6)]
    operational_date: date
    document_reference: Text
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
    idempotency_key: Annotated[str, StringConstraints(min_length=16, max_length=100)]
    lot_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    expiry_date: date | None = None

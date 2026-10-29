"""Contracts for authenticated QR-link management and public unit trace pages."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.api.v1.schemas.inventory import StockStatus, StrictModel


class TraceCapabilityCreateIn(StrictModel):
    handling_unit_id: uuid.UUID


class TraceCapabilityOut(StrictModel):
    token: str
    created_at: datetime


class TraceCapabilityRevokeOut(StrictModel):
    revoked_count: int = Field(ge=0)


class PublicTraceResolveIn(StrictModel):
    token: str = Field(min_length=40, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class PublicTraceMovementOut(StrictModel):
    movement_type: str
    posted_at: datetime
    from_warehouse_code: str | None
    from_warehouse_name: str | None
    from_location_code: str | None
    from_stock_status: StockStatus | None
    to_warehouse_code: str | None
    to_warehouse_name: str | None
    to_location_code: str | None
    to_stock_status: StockStatus | None
    quantity_base: Decimal


class PublicTraceOriginOut(StrictModel):
    supplier_name: str | None
    purchase_code: str | None
    purchase_order_code: str | None
    received_at: datetime | None
    consolidation_code: str | None


class PublicHandlingUnitTraceOut(StrictModel):
    handling_unit_code: str
    product_sku: str | None
    product_name: str | None
    quantity_base: Decimal
    base_unit_symbol: str | None
    lot_code: str | None
    receipt_lot_code: str | None
    receipt_lot_header_code: str | None
    expiry_date: date | None
    stock_status: StockStatus
    warehouse_code: str | None
    warehouse_name: str | None
    location_code: str | None
    origin: PublicTraceOriginOut
    movements: list[PublicTraceMovementOut]


__all__ = [
    "PublicHandlingUnitTraceOut",
    "PublicTraceMovementOut",
    "PublicTraceOriginOut",
    "PublicTraceResolveIn",
    "TraceCapabilityCreateIn",
    "TraceCapabilityOut",
    "TraceCapabilityRevokeOut",
]

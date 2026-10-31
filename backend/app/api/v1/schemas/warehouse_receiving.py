"""Warehouse receipt DTOs expose quantities and locations, without prices."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from app.api.v1.schemas.common import ORMOut


class WarehouseReceiptLineOut(ORMOut):
    id: uuid.UUID
    product_name: str
    product_sku: str
    unit_symbol: str
    quantity_received: Decimal
    quantity_accepted: Decimal | None


class WarehouseReceiptOut(ORMOut):
    id: uuid.UUID
    code: str
    warehouse_id: uuid.UUID
    purchase_date: datetime
    status: str
    ready: bool
    retaceo_code: str | None
    lines: tuple[WarehouseReceiptLineOut, ...]

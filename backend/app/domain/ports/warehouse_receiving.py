"""Operational receipt read model, deliberately without commercial amounts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WarehouseReceiptLine:
    id: uuid.UUID
    product_name: str
    product_sku: str
    unit_symbol: str
    quantity_received: Decimal
    quantity_accepted: Decimal | None


@dataclass(frozen=True, slots=True)
class WarehouseReceipt:
    id: uuid.UUID
    code: str
    warehouse_id: uuid.UUID
    purchase_date: datetime
    status: str
    ready: bool
    retaceo_code: str | None
    lines: tuple[WarehouseReceiptLine, ...]


class WarehouseReceivingRepository(Protocol):
    async def list_pending(
        self, company_id: uuid.UUID, warehouse_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[WarehouseReceipt], int]: ...
    async def get_receipt(
        self, company_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> WarehouseReceipt | None: ...

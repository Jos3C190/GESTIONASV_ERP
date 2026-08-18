"""Product master-data entities used by the catalog API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProductIdentifier:
    id: uuid.UUID
    product_id: int | None
    company_id: uuid.UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    variant_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ProductSupplier:
    id: uuid.UUID
    product_id: int
    supplier_id: int
    company_id: uuid.UUID
    supplier_product_code: str | None = None
    unit_cost: Decimal | None = None
    currency_code: str | None = None
    minimum_order_qty: Decimal | None = None
    order_multiple: Decimal | None = None
    lead_time_days: int | None = None
    is_preferred: bool = False
    status: str = "active"
    valid_from: date | None = None
    valid_until: date | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

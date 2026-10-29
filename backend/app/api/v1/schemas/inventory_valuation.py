"""Company-wide valuation contracts. All money uses decimal strings."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.api.v1.schemas.common import ORMOut
from app.api.v1.schemas.inventory import StrictModel


class OpeningLineIn(StrictModel):
    inventory_item_id: uuid.UUID
    quantity_base: Decimal = Field(gt=0, max_digits=24, decimal_places=6)
    total_cost: Decimal = Field(ge=0, max_digits=24, decimal_places=6)
    cost_reference: str = Field(min_length=3, max_length=240)


class ValuationOpeningIn(StrictModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reference: str = Field(min_length=3, max_length=240)
    snapshot_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved: Literal[True]
    lines: list[OpeningLineIn] = Field(max_length=10000)


class ValuationSettingOut(ORMOut):
    company_id: uuid.UUID
    currency: str
    opened_at: datetime
    opened_by: uuid.UUID
    opening_reference: str


class PhysicalValuationRow(StrictModel):
    inventory_item_id: uuid.UUID
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    stock_status: str
    lot_code: str | None
    expiry_date: date | None
    quantity_base: Decimal


class ValuationItemOut(StrictModel):
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str | None
    base_unit: str


class ValuationBalanceOut(ORMOut):
    inventory_item_id: uuid.UUID
    quantity_base: Decimal
    inventory_value: Decimal
    average_unit_cost: Decimal
    updated_at: datetime


class ValuationOverviewOut(StrictModel):
    setting: ValuationSettingOut | None
    snapshot_fingerprint: str
    physical_stock: list[PhysicalValuationRow]
    items: list[ValuationItemOut]
    balances: list[ValuationBalanceOut]


class ValuationEntryOut(ORMOut):
    id: uuid.UUID
    inventory_item_id: uuid.UUID
    sequence: int
    kind: str
    quantity_base: Decimal
    source_value: Decimal
    original_entry_id: uuid.UUID | None
    movement_line_id: uuid.UUID | None
    purchase_detail_id: uuid.UUID | None
    retaceo_id: uuid.UUID | None
    source_reference: str
    operational_date: date
    accounting_date: date
    posted_at: datetime
    posted_by: uuid.UUID
    inventory_delta: Decimal
    balance_quantity: Decimal
    balance_value: Decimal
    average_unit_cost: Decimal
    cost_breakdown: list[dict[str, str]]


class SupplierCreditIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    supplier_return_entry_id: uuid.UUID
    credit_net: Decimal = Field(ge=0, max_digits=24, decimal_places=6)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reference: str = Field(min_length=3, max_length=500)

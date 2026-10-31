"""Read-only physical and valued Kardex contracts."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from app.api.v1.schemas.inventory import StrictModel
from app.api.v1.schemas.inventory_valuation import ValuationEntryOut, ValuationSettingOut


class KardexItemOptionOut(StrictModel):
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str | None
    base_unit_symbol: str
    last_movement_at: datetime | None = None


class KardexContextOut(StrictModel):
    company_name: str
    nit: str | None
    nrc: str | None
    product_name: str | None = None
    sku: str | None = None
    base_unit_symbol: str | None = None
    warehouse_name: str | None = None
    warehouse_code: str | None = None
    branch_name: str | None = None


class PhysicalKardexRowOut(StrictModel):
    id: uuid.UUID
    movement_id: uuid.UUID
    movement_type: str
    source_reference: str | None
    document_reference: str | None = None
    operator: str | None = None
    posted_at: datetime
    product_name: str
    product_sku: str | None
    base_unit_symbol: str
    lot_code: str | None
    inventory_lot_detail_id: uuid.UUID | None
    receipt_lot_code: str | None
    receipt_lot_header_code: str | None
    handling_unit_id: uuid.UUID | None
    handling_unit_code: str | None
    from_warehouse_id: uuid.UUID | None
    from_warehouse_external: bool
    from_warehouse_code: str | None
    from_warehouse_name: str | None
    from_location_id: uuid.UUID | None
    from_location_code: str | None
    from_stock_status: str | None
    to_warehouse_id: uuid.UUID | None
    to_warehouse_external: bool
    to_warehouse_code: str | None
    to_warehouse_name: str | None
    to_location_id: uuid.UUID | None
    to_location_code: str | None
    to_stock_status: str | None
    quantity_base: Decimal
    incoming_quantity: Decimal
    outgoing_quantity: Decimal
    net_quantity: Decimal
    balance_after: Decimal | None
    is_internal: bool


class PhysicalKardexOut(StrictModel):
    context: KardexContextOut | None = None
    warehouse_id: uuid.UUID
    inventory_item_id: uuid.UUID
    period_from: date
    period_to: date
    balance_basis: str
    opening_known: bool
    opening_quantity: Decimal | None
    incoming_quantity: Decimal
    outgoing_quantity: Decimal
    closing_known: bool
    closing_quantity: Decimal | None
    items: list[PhysicalKardexRowOut]
    page: int
    page_size: int
    total: int


class KardexReconciliationRowOut(StrictModel):
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str | None
    base_unit_symbol: str
    physical_quantity: Decimal | None
    valued_quantity: Decimal | None
    quantity_difference: Decimal | None
    inventory_value: Decimal | None
    average_unit_cost: Decimal | None


class KardexReconciliationOut(StrictModel):
    context: KardexContextOut | None = None
    as_of: date | None = None
    generated_at: datetime | None = None
    balance_known: bool = True
    inventory_value: Decimal | None = None
    reconciled_items: int = 0
    discrepant_items: int = 0
    unvalued_items: int = 0
    valuation_enabled: bool
    currency: str | None
    items: list[KardexReconciliationRowOut]
    page: int
    page_size: int
    total: int


class ValuedKardexOut(StrictModel):
    context: KardexContextOut | None = None
    inventory_item_id: uuid.UUID
    setting: ValuationSettingOut | None
    period_from: date
    period_to: date
    opening_known: bool
    opening_quantity: Decimal | None
    opening_value: Decimal | None
    closing_known: bool
    closing_quantity: Decimal | None
    closing_value: Decimal | None
    period_value_change: Decimal | None
    entries: list[ValuationEntryOut]
    page: int
    page_size: int
    total: int

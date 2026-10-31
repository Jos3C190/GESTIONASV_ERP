"""Read contracts for the receipt-lot putaway queue."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.api.v1.routers.inventory_lots import (
    _hu_placement_quantities,
    _matches_placement_filter,
)
from app.api.v1.schemas.inventory import HandlingUnitOut
from app.api.v1.schemas.inventory_lots import (
    InventoryLotHandlingUnitOut,
    InventoryLotLineOut,
    InventoryLotOut,
    InventoryLotPageOut,
)

pytestmark = pytest.mark.unit


def test_lot_queue_contract_groups_product_progress_and_handling_units() -> None:
    company_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    lot_id = uuid.uuid4()
    item_id = uuid.uuid4()
    detail_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    location_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    received_at = datetime.now(UTC)
    hu = InventoryLotHandlingUnitOut(
        id=unit_id,
        code="HU-RECEIPT-001",
        quantity_base=Decimal("12"),
        stock_status="quarantine",
        warehouse_id=warehouse_id,
        location_id=location_id,
        location_code="A02-R01-N01-P01",
        expiry_date=date(2026, 12, 31),
        lot_code="FACTORY-LOT-9",
        measurement_status="incomplete",
        occupied_weight_kg=None,
        occupied_volume_m3=None,
        pending_placement_quantity_base=Decimal("0"),
        placed_quantity_base=Decimal("12"),
    )
    line = InventoryLotLineOut(
        inventory_lot_detail_ids=[detail_id],
        inventory_lot_detail_id=detail_id,
        receipt_lot_detail_code="LOT-COM-0001-D00000000000000000000000000000000",
        purchase_detail_id=uuid.uuid4(),
        inventory_item_id=item_id,
        product_sku="PRD-0001",
        product_name="Producto de prueba",
        base_unit_id=1,
        base_unit_name="Caja",
        base_unit_symbol="cj",
        accepted_quantity_base=Decimal("20"),
        placed_quantity_base=Decimal("12"),
        pending_placement_quantity_base=Decimal("8"),
        handling_units=[hu],
    )
    lot = InventoryLotOut(
        id=lot_id,
        company_id=company_id,
        purchase_id=purchase_id,
        purchase_code="COM-0001",
        warehouse_id=warehouse_id,
        code="LOT-COM-0001",
        received_at=received_at,
        placement_status="partially_placed",
        costing_status="applied",
        lines=[line],
    )
    page = InventoryLotPageOut(items=[lot], page=1, size=20, total=1)

    payload = page.model_dump(mode="json")
    assert payload["items"][0]["lines"][0]["inventory_lot_detail_ids"] == [str(detail_id)]
    assert payload["items"][0]["lines"][0]["handling_units"][0]["placed_quantity_base"] == "12"
    assert payload["items"][0]["placement_status"] == "partially_placed"


def test_hu_out_remains_compatible_with_historical_units_without_receipt_lot() -> None:
    unit = HandlingUnitOut(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        inventory_item_id=uuid.uuid4(),
        packaging_definition_id=None,
        code="HU-OLD-001",
        lot_code="MAKER-LOT",
        expiry_date=None,
        quantity_base=Decimal("1"),
        actual_gross_weight_kg=None,
        actual_length_m=None,
        actual_width_m=None,
        actual_height_m=None,
        actual_volume_m3=None,
        occupied_weight_kg=None,
        occupied_volume_m3=None,
        stock_status="quarantine",
        measurement_status="incomplete",
        measurement_source="master",
        closed_at=None,
        created_at=None,
        updated_at=None,
    )

    assert unit.receipt_lot_id is None
    assert unit.receipt_lot_code is None
    assert unit.product_sku is None


def test_partial_putaway_keeps_receipt_remainder_pending_then_completes() -> None:
    # HU 20 -> place 12 in storage and retain 8 at receiving, then place 8.
    pending_12, placed_12 = _hu_placement_quantities(
        quantity=Decimal("12"),
        location_type="rack",
        storage_eligible=True,
        location_active=True,
    )
    pending_8, placed_8 = _hu_placement_quantities(
        quantity=Decimal("8"),
        location_type="receiving",
        storage_eligible=False,
        location_active=True,
    )
    assert pending_12 + pending_8 == Decimal("8")
    assert placed_12 + placed_8 == Decimal("12")

    pending_final, placed_final = _hu_placement_quantities(
        quantity=Decimal("8"),
        location_type="rack",
        storage_eligible=True,
        location_active=True,
    )
    assert pending_12 + pending_final == Decimal("0")
    assert placed_12 + placed_final == Decimal("20")


def test_pending_filter_includes_partially_placed_lot_with_remaining_quantity() -> None:
    assert _matches_placement_filter("pending_placement", "partially_placed")
    assert _matches_placement_filter("pending_placement", "pending_placement")
    assert not _matches_placement_filter("pending_placement", "placed")
    assert _matches_placement_filter("partially_placed", "partially_placed")
    assert not _matches_placement_filter("partially_placed", "pending_placement")
    assert _matches_placement_filter("all", "placed")

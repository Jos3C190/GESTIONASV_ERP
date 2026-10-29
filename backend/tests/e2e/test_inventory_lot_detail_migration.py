"""Migration checks for canonical receipt-detail lot identity."""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from sqlalchemy import create_engine, select, text

from tests.e2e.test_inventory_block4_closure import _measured_receipt

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_separate_partial_receipts_have_distinct_detail_codes(e2e_client):
    first = await _measured_receipt(
        e2e_client, quantity="2.000000", username="b02-partial-receipt-one"
    )
    second = await _measured_receipt(
        e2e_client, quantity="1.000000", username="b02-partial-receipt-two"
    )
    _, first_warehouse_id, _, first_item_id, first_lot_id, _ = first
    _, second_warehouse_id, _, second_item_id, second_lot_id, _ = second
    assert first_warehouse_id == second_warehouse_id
    assert first_item_id == second_item_id
    assert first_lot_id != second_lot_id

    async with async_session_factory() as session:
        lots = [
            await session.get(InventoryLotModel, first_lot_id),
            await session.get(InventoryLotModel, second_lot_id),
        ]
        details = list(
            await session.scalars(
                select(InventoryLotDetailModel)
                .where(InventoryLotDetailModel.inventory_lot_id.in_([first_lot_id, second_lot_id]))
                .order_by(InventoryLotDetailModel.inventory_lot_id)
            )
        )
        assert all(lot is not None for lot in lots)
        assert len(details) == 2
        assert len({detail.purchase_detail_id for detail in details}) == 2
        assert len({detail.code for detail in details}) == 2
        assert {detail.accepted_quantity_base for detail in details} == {
            Decimal("1.000000"),
            Decimal("2.000000"),
        }
        lot_by_id = {lot.id: lot for lot in lots if lot is not None}
        assert all(
            detail.code
            == f"{lot_by_id[detail.inventory_lot_id].code}-D{detail.id.hex.upper()}"
            for detail in details
        )


@pytest.mark.asyncio
async def test_0084_to_0085_keeps_immutable_movements_and_resolves_legacy_detail_lot(e2e_client):
    headers, warehouse_id, handling_unit_id, item_id, lot_id, _ = await _measured_receipt(
        e2e_client, username="b02-detail-migration"
    )
    async with async_session_factory() as session:
        lot = await session.get(InventoryLotModel, lot_id)
        unit = await session.get(InventoryHandlingUnitModel, handling_unit_id)
        assert lot is not None
        assert unit is not None
        detail = await session.scalar(
            select(InventoryLotDetailModel).where(
                InventoryLotDetailModel.inventory_lot_id == lot_id,
                InventoryLotDetailModel.inventory_item_id == item_id,
            )
        )
        line = await session.scalar(
            select(InventoryMovementLineModel)
            .where(InventoryMovementLineModel.handling_unit_id == handling_unit_id)
            .order_by(InventoryMovementLineModel.line_number)
            .limit(1)
        )
        assert detail is not None
        assert line is not None
        detail_id = detail.id
        expected_detail_code = f"{lot.code}-D{detail.id.hex.upper()}"
        original_line = (
            line.id,
            line.movement_id,
            line.line_number,
            line.inventory_item_id,
            line.handling_unit_id,
            line.quantity_base,
            line.lot_code,
            line.expiry_date,
        )

    database_url = os.environ["DATABASE_URL_SYNC"]
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_section_option("alembic", "sqlalchemy.url", database_url.replace("%", "%%"))
    await dispose_engine()
    try:
        command.downgrade(config, "0084")
        command.upgrade(config, "0085")
    finally:
        # Keep the disposable E2E schema usable even if an assertion fails.
        command.upgrade(config, "head")
        await dispose_engine()

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            migrated_line = connection.execute(
                text(
                    "SELECT id, movement_id, line_number, inventory_item_id, handling_unit_id, "
                    "quantity_base, lot_code, expiry_date, inventory_lot_detail_id "
                    "FROM inventory_movement_lines WHERE id = :line_id"
                ),
                {"line_id": original_line[0]},
            ).one()
            immutable_trigger = connection.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgrelid = 'inventory_movement_lines'::regclass "
                    "AND tgname = 'trg_inventory_movement_lines_immutable' AND NOT tgisinternal"
                )
            ).scalar_one()
    finally:
        engine.dispose()

    # The test exercises the 0084 -> 0085 transition, then restores the
    # disposable database to the current project head in its finally.
    assert revision == ScriptDirectory.from_config(config).get_current_head()
    assert tuple(migrated_line[:8]) == original_line
    assert migrated_line.inventory_lot_detail_id is None
    assert immutable_trigger == 1

    async with async_session_factory() as session:
        detail = await session.get(InventoryLotDetailModel, detail_id)
        unit = await session.get(InventoryHandlingUnitModel, handling_unit_id)
        assert detail is not None
        assert unit is not None
        assert detail.code == expected_detail_code
        assert unit.inventory_lot_detail_id == detail_id

    today = datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat()
    kardex = await e2e_client.get(
        "/api/v1/inventory/kardex/physical",
        headers=headers,
        params={
            "warehouse_id": str(warehouse_id),
            "inventory_item_id": str(item_id),
            "period_from": today,
            "period_to": today,
            "lot_code": expected_detail_code,
        },
    )
    assert kardex.status_code == 200, kardex.text
    assert kardex.json()["total"] == 1
    assert kardex.json()["items"][0]["receipt_lot_code"] == expected_detail_code

    label = await e2e_client.get(
        f"/api/v1/inventory/labels/preview?handling_unit_id={handling_unit_id}",
        headers=headers,
    )
    assert label.status_code == 200, label.text
    assert label.json()["receipt_lot_code"] == expected_detail_code

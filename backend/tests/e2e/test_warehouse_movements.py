"""Warehouse operator history: server filters, local dates, paging and access scope."""

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import (
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.organization import Location, Warehouse
from sqlalchemy import select

from tests.e2e.test_inventory_preparation import _operator_headers
from tests.e2e.test_purchase_orders import _reference_ids

pytestmark = pytest.mark.e2e


async def test_operator_history_filters_full_ledger_and_denies_other_warehouses(e2e_client):
    client = e2e_client
    company, _, warehouse, product, *_ = await _reference_ids()
    headers = await _operator_headers(client, company, warehouse)
    actor = (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]
    local = ZoneInfo("America/El_Salvador")
    async with async_session_factory() as session:
        item = await session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company, InventoryItemModel.product_id == product
            )
        )
        catalog = await session.get(ProductModel, product)
        sku = catalog.sku
        location = await session.scalar(select(Location).where(Location.warehouse_id == warehouse))
        source_warehouse = await session.get(Warehouse, warehouse)
        other = Warehouse(
            company_id=company,
            branch_id=source_warehouse.branch_id,
            warehouse_category_id=source_warehouse.warehouse_category_id,
            code="HISTORY-OTHER",
            name="Other assigned scope",
            is_central=False,
        )
        session.add(other)
        await session.flush()
        other_id = other.id
        cases = [
            (
                datetime(2026, 10, 27, 23, 59, 59, tzinfo=local),
                "receipt",
                "before",
                None,
                warehouse,
            ),
            (datetime(2026, 10, 28, 0, 0, tzinfo=local), "receipt", "first", None, warehouse),
            (
                datetime(2026, 10, 28, 12, 0, tzinfo=local),
                "putaway",
                "internal",
                warehouse,
                warehouse,
            ),
            (
                datetime(2026, 10, 28, 23, 59, 59, 999999, tzinfo=local),
                "shipment",
                "last",
                warehouse,
                None,
            ),
            (datetime(2026, 10, 29, 0, 0, tzinfo=local), "receipt", "after", None, warehouse),
        ]
        for index, (posted, kind, ref, origin, destination) in enumerate(cases):
            movement = InventoryMovementModel(
                company_id=company,
                movement_type=kind,
                idempotency_key=f"history-{index}",
                request_fingerprint="0" * 64,
                source_reference=f"HISTORY-{ref}",
                posted_at=posted,
                created_at=posted,
                posted_by=uuid.UUID(actor),
            )
            session.add(movement)
            await session.flush()
            session.add(
                InventoryMovementLineModel(
                    company_id=company,
                    movement_id=movement.id,
                    line_number=1,
                    inventory_item_id=item.id,
                    lot_code="FAB-28" if ref != "internal" else "FAB-other",
                    from_warehouse_id=origin,
                    from_location_id=location.id if origin else None,
                    to_warehouse_id=destination,
                    to_location_id=location.id if destination else None,
                    from_stock_status="available" if origin else None,
                    to_stock_status="available" if destination else None,
                    quantity_base=Decimal("2"),
                    occupied_weight_kg=Decimal("1"),
                    occupied_volume_m3=Decimal("0.01"),
                    measurement_status="complete",
                )
            )
        await session.commit()
    endpoint = f"/api/v1/inventory/warehouses/{warehouse}/movements"

    async def query(**params):
        response = await client.get(endpoint, headers=headers, params=params)
        assert response.status_code == 200, response.text
        assert not any(
            key in response.text for key in ("unit_cost", "average_unit_cost", "inventory_value")
        )
        return response.json()

    # The default, unfiltered contract stays backward-compatible.
    assert len(await query()) == 5
    day = {"period_from": "2026-10-28", "period_to": "2026-10-28"}
    assert [r["source_reference"] for r in await query(**day)] == [
        "HISTORY-last",
        "HISTORY-internal",
        "HISTORY-first",
    ]
    assert len(await query(**day, q=sku.lower())) == 3
    assert await query(**day, q="%") == []  # Literal search, not a SQL wildcard.
    assert len(await query(**day, lot_code="fab-28")) == 2
    assert len(await query(**day, movement_type="receipt")) == 1
    for direction, ref in (("incoming", "first"), ("outgoing", "last"), ("internal", "internal")):
        rows = await query(**day, direction=direction)
        assert [r["source_reference"] for r in rows] == [f"HISTORY-{ref}"]
    assert (await query(**day, source_reference="-first"))[0]["source_reference"] == "HISTORY-first"
    assert (await query(**day, limit=1, offset=2))[0]["source_reference"] == "HISTORY-first"
    invalid = await client.get(
        endpoint, headers=headers, params={"period_from": "2026-11-01", "period_to": "2026-10-01"}
    )
    assert invalid.status_code == 422
    assert (
        await client.get(endpoint, headers=headers, params={"direction": "invented"})
    ).status_code == 422
    assert (
        await client.get(f"/api/v1/inventory/warehouses/{other_id}/movements", headers=headers)
    ).status_code == 403
    assert (
        await client.get(endpoint, headers={**headers, "X-Company-ID": str(uuid.uuid4())})
    ).status_code in (403, 404)
    assert (
        await client.get("/api/v1/inventory/kardex/valuation", headers=headers)
    ).status_code == 403

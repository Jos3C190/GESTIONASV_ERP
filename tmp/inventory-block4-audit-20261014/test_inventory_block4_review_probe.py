"""Temporary review probes; run only with the dedicated erp_db_test fixture."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.inventory_lot import InventoryLotModel
from app.infrastructure.models.organization import Location
from tests.e2e.test_purchase_orders import (
    _headers,
    _receiving_location_id,
    _reference_ids,
    _sent_order,
)

pytestmark = pytest.mark.e2e


async def _measured_receipt(client):
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        client, company_id=company_id, username="block4-review", is_superuser=True
    )
    order = await _sent_order(
        client, headers=headers, branch_id=branch_id, warehouse_id=warehouse_id,
        product_id=product_id, supplier_id=supplier_id, currency=currency,
    )
    created = await client.post(
        "/api/v1/purchases", headers=headers,
        json={"purchase_order_id": order["id"], "lines": [{
            "purchase_order_detail_id": order["details"][0]["id"],
            "quantity_received": "4.000000",
        }]},
    )
    assert created.status_code == 201, created.text
    purchase = created.json()
    received = await client.post(f"/api/v1/purchases/{purchase['id']}/receive", headers=headers)
    assert received.status_code == 200, received.text
    verified = await client.post(
        f"/api/v1/purchases/{purchase['id']}/verify", headers=headers,
        json={"lines": [{
            "purchase_detail_id": purchase["details"][0]["id"],
            "quantity_accepted": "4.000000",
            "inventory_location_id": str(await _receiving_location_id(warehouse_id)),
        }]},
    )
    assert verified.status_code == 200, verified.text
    async with async_session_factory() as session:
        lot = await session.scalar(select(InventoryLotModel).where(
            InventoryLotModel.company_id == company_id,
            InventoryLotModel.purchase_id == uuid.UUID(purchase["id"]),
        ))
        unit = await session.scalar(select(InventoryHandlingUnitModel).where(
            InventoryHandlingUnitModel.inventory_lot_id == lot.id,
        ))
        unit_id, item_id, lot_id = unit.id, unit.inventory_item_id, lot.id
    measured = await client.patch(
        f"/api/v1/inventory/handling-units/{unit_id}/measurements", headers=headers,
        json={"source": "manual", "measures": {
            "gross_weight_kg": "1", "length_m": "0.1", "width_m": "0.1", "height_m": "0.1",
        }},
    )
    assert measured.status_code == 200, measured.text
    return headers, warehouse_id, unit_id, item_id, lot_id, measured.json()


async def test_measurement_response_retains_current_release_requirements(e2e_client):
    headers, warehouse_id, unit_id, _, _, measured = await _measured_receipt(e2e_client)
    listed = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=headers
    )
    assert listed.status_code == 200, listed.text
    actual = next(row for row in listed.json() if row["id"] == str(unit_id))
    assert actual["release_requirements"], "An unconfirmed new receipt must still require its label"
    assert measured["release_requirements"] == actual["release_requirements"]


async def test_ready_hu_can_be_distributed_to_two_destinations_in_one_group(e2e_client):
    headers, warehouse_id, unit_id, item_id, lot_id, _ = await _measured_receipt(e2e_client)
    async with async_session_factory() as session:
        # Reproduce the explicitly supported historical receipt exception.
        # This fixture changes only erp_db_test; no validators/services are mocked.
        lot = await session.get(InventoryLotModel, lot_id)
        lot.label_confirmation_required = False
        destinations = [Location(
            warehouse_id=warehouse_id, code=f"AUDIT-B4-{number}",
            aisle="B4", rack="01", level="01", position=str(number),
            storage_eligible=True, capacity_enforcement_mode="disabled",
        ) for number in (1, 2)]
        session.add_all(destinations)
        await session.flush()
        destination_ids = [destination.id for destination in destinations]
        await session.commit()
    listed = await e2e_client.get(
        f"/api/v1/inventory/warehouses/{warehouse_id}/handling-units", headers=headers
    )
    assert listed.status_code == 200, listed.text
    source = next(row for row in listed.json() if row["id"] == str(unit_id))
    assert source["release_requirements"] == [], source
    response = await e2e_client.post(
        "/api/v1/inventory/putaway-groups/confirm", headers=headers,
        json={
            "idempotency_key": "review-block4-two-destinations",
            "receipt_lot_id": str(lot_id), "inventory_item_id": str(item_id),
            "allocations": [{
                "handling_unit_id": str(unit_id), "quantity_base": quantity,
                "destination_location_id": str(destination_id),
            } for quantity, destination_id in zip(("1", "3"), destination_ids, strict=True)],
        },
    )
    if response.status_code != 201:
        async with async_session_factory() as session:
            units = list(await session.scalars(select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.inventory_lot_id == lot_id,
            )))
            assert len(units) == 1, "A rejected group must not leave its partial split committed"
            assert units[0].quantity_base == Decimal("4")
            assert str(units[0].location_id) == source["location_id"]
    assert response.status_code == 201, response.text
    assert [part["stock_status"] for part in response.json()["allocations"]] == [
        "quarantine", "quarantine"
    ]

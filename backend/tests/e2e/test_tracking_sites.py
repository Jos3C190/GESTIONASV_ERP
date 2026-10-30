"""Branch and warehouse sites for tracking: locations, map layer and automatic geofences."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.e2e.test_fleet_vehicles import _admin, _branches

pytestmark = pytest.mark.e2e


async def _category(e2e_client: Any, headers: dict[str, str]) -> str:
    response = await e2e_client.get(
        f"/api/v1/warehouse-categories?company_id={headers['X-Company-ID']}&size=1", headers=headers
    )
    assert response.status_code == 200, response.text
    return str(response.json()["items"][0]["id"])


def _warehouse(branch_id: str, category_id: str, **extra: Any) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:6].upper()
    return {
        "branch_id": branch_id,
        "warehouse_category_id": category_id,
        "code": f"WS-{suffix}",
        "name": f"Bodega externa {suffix}",
        **extra,
    }


async def test_warehouse_in_another_building_keeps_its_own_location(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = next(
        item for item in await _branches(e2e_client, admin) if not item["is_headquarters"]
    )
    category = await _category(e2e_client, admin)

    missing = await e2e_client.post(
        "/api/v1/warehouses",
        headers=admin,
        json=_warehouse(branch["id"], category, location_mode="own", physical_location="Km 12"),
    )
    assert missing.status_code == 422

    body = _warehouse(
        branch["id"],
        category,
        location_mode="own",
        physical_location="Carretera Panamericana km 12",
        latitude=13.7,
        longitude=-89.1,
    )
    created = await e2e_client.post("/api/v1/warehouses", headers=admin, json=body)
    assert created.status_code == 201, created.text
    warehouse = created.json()
    assert warehouse["location_mode"] == "own"
    assert float(warehouse["latitude"]) == pytest.approx(13.7)
    assert warehouse["geofence_radius_m"] == 150

    # Una edición que no envía la ubicación no borra la del edificio propio.
    partial = {key: body[key] for key in ("branch_id", "warehouse_category_id", "code", "name")}
    kept = await e2e_client.patch(
        f"/api/v1/warehouses/{warehouse['id']}",
        headers=admin,
        json={**partial, "physical_location": body["physical_location"]},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["location_mode"] == "own"
    assert float(kept.json()["longitude"]) == pytest.approx(-89.1)

    moved = await e2e_client.patch(
        f"/api/v1/warehouses/{warehouse['id']}",
        headers=admin,
        json={**partial, "location_mode": "branch", "latitude": 1, "longitude": 1},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["location_mode"] == "branch"
    assert moved.json()["latitude"] is None
    assert moved.json()["geofence_radius_m"] is None

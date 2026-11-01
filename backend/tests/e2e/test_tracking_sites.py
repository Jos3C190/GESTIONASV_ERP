"""Branch and warehouse sites for tracking: locations, map layer and automatic geofences."""

from __future__ import annotations

import uuid
from typing import Any

import app.api.v1.traccar_access as traccar_module
import pytest
from app.api.v1.site_sync import wait_for_pending_syncs
from app.application.tracking import TraccarUnavailableError
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.organization import Warehouse

from tests.e2e import test_fleet_tracking
from tests.e2e.test_fleet_tracking import FakeTraccar
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches
from tests.e2e.test_inventory_transfers import _committed_transfer_context, _create_preparation

pytestmark = pytest.mark.e2e

#: Fake Traccar server shared with the fleet tracking tests.
traccar = test_fleet_tracking.traccar


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
    await wait_for_pending_syncs()
    assert moved.json()["location_mode"] == "branch"
    assert moved.json()["latitude"] is None
    assert moved.json()["geofence_radius_m"] is None


def _site_geofences(fake: FakeTraccar) -> dict[str, dict[str, Any]]:
    return {
        geofence["attributes"]["erpSiteId"]: geofence
        for geofence in fake.geofences.values()
        if "erpSiteId" in (geofence.get("attributes") or {})
    }


async def test_sites_layer_and_automatic_geofences(e2e_client: Any, traccar: FakeTraccar) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    operating = [item for item in branches if not item["is_headquarters"]]
    category = await _category(e2e_client, admin)

    # Abrir Seguimiento reconcilia: cada sucursal con coordenadas tiene su geocerca.
    first = await e2e_client.get("/api/v1/tracking/sites", headers=admin)
    assert first.status_code == 200, first.text
    layer = first.json()
    assert layer["sync"]["error"] is None
    assert layer["sync"]["synced_at"] is not None
    branch_sites = {site["id"] for site in layer["sites"] if site["kind"] == "branch"}
    assert {item["id"] for item in operating} <= branch_sites
    assert branch_sites <= set(_site_geofences(traccar))

    body = _warehouse(
        operating[0]["id"],
        category,
        location_mode="own",
        physical_location="Bodega del aeropuerto",
        latitude=13.44,
        longitude=-89.05,
        geofence_radius_m=400,
    )
    created = (await e2e_client.post("/api/v1/warehouses", headers=admin, json=body)).json()
    await wait_for_pending_syncs()
    geofence = _site_geofences(traccar)[created["id"]]
    assert geofence["name"] == f"Almacén {body['name']}"
    assert "400.0" in geofence["area"]

    # Las geocercas de sistema no se borran desde Seguimiento.
    listed = (await e2e_client.get("/api/v1/tracking/geofences", headers=admin)).json()
    system = next(item for item in listed if item["id"] == geofence["id"])
    assert system["system"] is True
    assert system["can_manage"] is False
    blocked = await e2e_client.delete(f"/api/v1/tracking/geofences/{geofence['id']}", headers=admin)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "system_geofence"

    # Un gerente de otra sucursal ve todos los lugares de su empresa.
    manager = await _branch_manager(e2e_client, admin, operating[1]["id"])
    seen = (await e2e_client.get("/api/v1/tracking/sites", headers=manager)).json()
    assert created["id"] in {site["id"] for site in seen["sites"]}
    assert operating[0]["id"] in {site["id"] for site in seen["sites"]}

    # Con Traccar caído la edición funciona; el estado lo informa y la sincronización lo corrige.
    partial = {key: body[key] for key in ("branch_id", "warehouse_category_id", "code", "name")}
    working_call = traccar.call

    async def down(*args: Any, **kwargs: Any) -> Any:
        raise TraccarUnavailableError("sin conexión")

    traccar_module.traccar_call = down
    moved = await e2e_client.patch(
        f"/api/v1/warehouses/{created['id']}",
        headers=admin,
        json={**partial, "location_mode": "branch"},
    )
    assert moved.status_code == 200, moved.text
    stale = (await e2e_client.get("/api/v1/tracking/sites", headers=admin)).json()
    assert stale["sync"]["error"]
    assert created["id"] in _site_geofences(traccar)

    traccar_module.traccar_call = working_call
    synced = await e2e_client.post("/api/v1/tracking/sites/sync", headers=admin)
    assert synced.status_code == 200, synced.text
    assert synced.json()["sync"]["error"] is None
    assert created["id"] not in _site_geofences(traccar)
    assert created["id"] not in {site["id"] for site in synced.json()["sites"]}


async def test_transfer_route_uses_the_warehouse_building(e2e_client: Any) -> None:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    transfer = await _create_preparation(e2e_client, values, headers, f"site-{suffix[:12]}")
    async with async_session_factory() as session:
        warehouse = await session.get(Warehouse, values.destination_id)
        assert warehouse is not None
        warehouse.location_mode = "own"
        warehouse.latitude = 13.31
        warehouse.longitude = -87.85
        warehouse.geofence_radius_m = 500
        await session.commit()
    track = await e2e_client.get(f"/api/v1/tracking/transfers/{transfer['id']}", headers=headers)
    assert track.status_code == 200, track.text
    destination = track.json()["destination"]
    assert destination["latitude"] == pytest.approx(13.31)
    assert destination["longitude"] == pytest.approx(-87.85)

"""Tracking simulator end to end: virtual GPS, source swap, alerts, joystick, scope."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.core.config import settings
from app.infrastructure import tracking_monitor, tracking_simulator
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.tracking import TrackingAlertModel, TrackingSimulationModel
from sqlalchemy import select

from tests.e2e import test_fleet_tracking
from tests.e2e.test_fleet_tracking import FakeTraccar
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle
from tests.e2e.test_inventory_transfers import (
    DISPATCH_OVERRIDE,
    _committed_transfer_context,
    _create_preparation,
)
from tests.e2e.test_tracking_alerts import _position

pytestmark = pytest.mark.e2e

traccar = test_fleet_tracking.traccar
SIMULATOR = "/api/v1/tracking/simulator"


@pytest.fixture
def reports(traccar: FakeTraccar, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Enable the simulator and record what the virtual GPS sends over OsmAnd."""
    sent: list[dict[str, str]] = []
    monkeypatch.setattr(settings, "TRACKING_SIMULATOR_ENABLED", True)
    monkeypatch.setattr(settings, "OSRM_URL", None)

    def fake_send(url: str) -> None:
        query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
        sent.append(query)
        device = next(d for d in traccar.devices.values() if d["uniqueId"] == query["id"])
        at = datetime.fromtimestamp(int(query["timestamp"]) / 1000, UTC)
        traccar.positions.setdefault(device["id"], []).append(
            {
                "longitude": float(query["lon"]),
                "latitude": float(query["lat"]),
                "speed": float(query["speed"]),
                "course": float(query["bearing"]),
                "fixTime": at.isoformat().replace("+00:00", "Z"),
            }
        )

    monkeypatch.setattr("app.api.v1.simulator._send", fake_send)
    return sent


async def _dispatched_transfer(e2e_client: Any) -> tuple[Any, dict[str, str], dict[str, Any]]:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    transfer = await _create_preparation(e2e_client, values, headers, f"sim-{suffix[:12]}")
    dispatched = await e2e_client.post(
        f"/api/v1/inventory/transfers/{transfer['id']}/dispatch",
        headers=headers,
        json={
            "vehicle_id": str(values.vehicle_id),
            "idempotency_key": f"sim-dispatch-{suffix}",
            "override_reason": DISPATCH_OVERRIDE,
        },
    )
    assert dispatched.status_code == 200, dispatched.text
    return values, headers, transfer


async def test_route_session_stands_in_for_the_real_gps(
    e2e_client: Any, traccar: FakeTraccar, reports: list[dict[str, str]]
) -> None:
    values, headers, transfer = await _dispatched_transfer(e2e_client)
    now = datetime.now(UTC)
    real_device = traccar.add_device(f"REAL{uuid.uuid4().hex[:10]}")
    async with async_session_factory() as session:
        fleet = await session.scalar(
            select(FleetVehicleModel).where(
                FleetVehicleModel.inventory_vehicle_id == values.vehicle_id
            )
        )
        assert fleet is not None
        fleet.gps_device_unique_id = traccar.devices[real_device]["uniqueId"]
        fleet.traccar_device_id = real_device
        record = await session.get(InventoryTransferModel, uuid.UUID(transfer["id"]))
        assert record is not None
        record.dispatched_at = now - timedelta(minutes=50)
        # Origen y destino en el mapa (San Miguel → Usulután).
        for warehouse_id, point in (
            (record.origin_warehouse_id, (Decimal("-88.1857"), Decimal("13.4837"))),
            (record.destination_warehouse_id, (Decimal("-88.4360"), Decimal("13.3431"))),
        ):
            warehouse = await session.get(Warehouse, warehouse_id)
            assert warehouse is not None
            assert warehouse.branch_id is not None
            branch = await session.get(Branch, warehouse.branch_id)
            assert branch is not None
            branch.longitude, branch.latitude = point
        fleet_id = str(fleet.id)
        await session.commit()

    state = await e2e_client.get(SIMULATOR, headers=headers)
    assert state.status_code == 200, state.text
    assert state.json()["enabled"] is True
    assert state.json()["can_simulate"] is True
    listed = next(item for item in state.json()["vehicles"] if item["id"] == fleet_id)
    assert listed["transfer_id"] == transfer["id"]
    assert listed["has_gps"] is True

    started = await e2e_client.post(
        f"{SIMULATOR}/sessions",
        headers=headers,
        json={
            "vehicle_id": fleet_id,
            "mode": "route",
            "transfer_id": transfer["id"],
            "speed_kmh": 120,
        },
    )
    assert started.status_code == 201, started.text
    simulation = started.json()
    virtual = traccar.devices[simulation["traccar_device_id"]]
    assert virtual["uniqueId"].startswith("erp-sim-")
    assert virtual["attributes"]["erpSimulated"] is True
    assert len(reports) == 1
    assert simulation["route_length_m"] > 0

    again = await e2e_client.post(
        f"{SIMULATOR}/sessions",
        headers=headers,
        json={"vehicle_id": fleet_id, "mode": "joystick", "start": [-88.18, 13.48]},
    )
    assert again.status_code == 409

    # Seguimiento lee la unidad desde el GPS virtual y no muestra el real mientras tanto.
    positions = (await e2e_client.get("/api/v1/tracking/positions", headers=headers)).json()
    mine = [item for item in positions["devices"] if item["vehicle"]["id"] == fleet_id]
    assert [item["id"] for item in mine] == [simulation["traccar_device_id"]]
    assert mine[0]["simulated"] is True

    for second in (10, 20, 30):
        await tracking_simulator.tick(now=datetime.now(UTC) + timedelta(seconds=second), dt=10)
    async with async_session_factory() as session:
        row = await session.get(TrackingSimulationModel, uuid.UUID(simulation["id"]))
        assert row is not None
        assert row.progress_m > 0
        assert row.current_speed_kmh > 0
    assert len(reports) >= 2

    trip = await e2e_client.get(f"/api/v1/tracking/transfers/{transfer['id']}", headers=headers)
    assert trip.status_code == 200, trip.text
    assert trip.json()["simulated"] is True
    assert trip.json()["position"] is not None

    # Una parada larga simulada abre una alerta marcada como simulada.
    traccar.positions[simulation["traccar_device_id"]] = [
        _position(now - timedelta(minutes=48), 25.0, (-88.75, 13.60)),
        _position(now - timedelta(minutes=35), 0.5),
        _position(now - timedelta(minutes=1), 0.0),
    ]
    await tracking_monitor.run_once()
    alerts = (await e2e_client.get("/api/v1/tracking/alerts", headers=headers)).json()
    stop = next(item for item in alerts["items"] if item["kind"] == "long_stop")
    assert stop["simulated"] is True

    for action, extra in (
        ("pause", {}),
        ("resume", {}),
        ("stop", {"minutes": 5}),
        ("signal_loss", {"minutes": 3}),
        ("signal_restore", {}),
        ("speed", {"speed_kmh": 80}),
        ("detour", {}),
    ):
        controlled = await e2e_client.post(
            f"{SIMULATOR}/sessions/{simulation['id']}/control",
            headers=headers,
            json={"action": action, **extra},
        )
        assert controlled.status_code == 200, (action, controlled.text)
    assert controlled.json()["progress_m"] == 0
    assert controlled.json()["speed_kmh"] == 80
    assert controlled.json()["route_length_m"] != simulation["route_length_m"]

    ended = await e2e_client.delete(f"{SIMULATOR}/sessions/{simulation['id']}", headers=headers)
    assert ended.status_code == 204
    async with async_session_factory() as session:
        alert = await session.get(TrackingAlertModel, uuid.UUID(stop["id"]))
        assert alert is not None
        assert alert.resolved_at is not None
    positions = (await e2e_client.get("/api/v1/tracking/positions", headers=headers)).json()
    mine = [item for item in positions["devices"] if item["vehicle"]["id"] == fleet_id]
    assert [item["id"] for item in mine] == [real_device]
    assert mine[0]["simulated"] is False


async def test_joystick_permissions_and_shutdown(
    e2e_client: Any,
    traccar: FakeTraccar,
    reports: list[dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    suffix = uuid.uuid4().hex[:5].upper()
    created = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=admin,
        json=_vehicle(branch, f"SIM-{suffix}", f"S {suffix}"),
    )
    assert created.status_code == 201, created.text
    vehicle_id = created.json()["id"]

    manager = await _branch_manager(e2e_client, admin, branch)
    view = (await e2e_client.get(SIMULATOR, headers=manager)).json()
    assert view["enabled"] is True
    assert view["can_simulate"] is False
    forbidden = await e2e_client.post(
        f"{SIMULATOR}/sessions",
        headers=manager,
        json={"vehicle_id": vehicle_id, "mode": "joystick", "start": [-88.18, 13.48]},
    )
    assert forbidden.status_code == 403

    started = await e2e_client.post(
        f"{SIMULATOR}/sessions",
        headers=admin,
        json={"vehicle_id": vehicle_id, "mode": "joystick", "start": [-88.18, 13.48]},
    )
    assert started.status_code == 201, started.text
    simulation = started.json()
    assert simulation["route"] == []

    # Un vehículo sin GPS real aparece en el mapa gracias al GPS virtual.
    positions = (await e2e_client.get("/api/v1/tracking/positions", headers=admin)).json()
    assert any(
        item["vehicle"]["id"] == vehicle_id and item["simulated"] for item in positions["devices"]
    )

    drive = f"{SIMULATOR}/sessions/{simulation['id']}/drive"
    moved = await e2e_client.post(
        drive,
        headers=admin,
        json={"latitude": 13.48, "longitude": -88.1795, "course": 90, "speed_kmh": 30},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["longitude"] == pytest.approx(-88.1795)
    teleport = await e2e_client.post(
        drive,
        headers=admin,
        json={"latitude": 13.48, "longitude": -87.5, "course": 90, "speed_kmh": 30},
    )
    assert teleport.status_code == 409
    assert teleport.json()["code"] == "simulation_teleport"
    paused = await e2e_client.post(
        f"{SIMULATOR}/sessions/{simulation['id']}/control", headers=admin, json={"action": "pause"}
    )
    assert paused.status_code == 409

    seen = (await e2e_client.get(SIMULATOR, headers=manager)).json()["sessions"]
    assert [item["id"] for item in seen] == [simulation["id"]]
    assert seen[0]["can_control"] is False

    # El identificador del GPS virtual no se puede vincular como GPS real.
    reserved = await e2e_client.put(
        f"/api/v1/fleet/vehicles/{vehicle_id}/gps-device",
        headers=admin,
        json={"unique_id": "erp-sim-0123456789"},
    )
    assert reserved.status_code == 409

    # Al desactivar el simulador desaparece la función y el motor cierra las sesiones.
    monkeypatch.setattr(settings, "TRACKING_SIMULATOR_ENABLED", False)
    assert (await e2e_client.get(SIMULATOR, headers=admin)).json()["enabled"] is False
    refused = await e2e_client.post(
        f"{SIMULATOR}/sessions",
        headers=admin,
        json={"vehicle_id": vehicle_id, "mode": "joystick", "start": [-88.18, 13.48]},
    )
    assert refused.status_code == 404
    await tracking_simulator.tick(dt=2)
    async with async_session_factory() as session:
        row = await session.get(TrackingSimulationModel, uuid.UUID(simulation["id"]))
        assert row is not None
        assert row.state == "ended"
        assert row.end_reason == "El simulador se desactivó."

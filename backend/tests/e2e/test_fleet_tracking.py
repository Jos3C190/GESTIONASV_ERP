"""Tracking: GPS devices linked from Fleet and branch-scoped visibility."""

from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from sqlalchemy import text

from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle

pytestmark = pytest.mark.e2e


class FakeTraccar:
    """In-memory stand-in for the Traccar REST API used by the ERP."""

    def __init__(self) -> None:
        self.devices: dict[int, dict[str, Any]] = {}
        self.geofences: dict[int, dict[str, Any]] = {}
        self.links: set[tuple[int, int]] = set()
        self._next = 100

    def _id(self) -> int:
        self._next += 1
        return self._next

    def add_device(self, unique_id: str, attributes: dict[str, Any] | None = None) -> int:
        device_id = self._id()
        self.devices[device_id] = {
            "id": device_id,
            "uniqueId": unique_id,
            "name": unique_id,
            "status": "online",
            "attributes": attributes or {},
        }
        return device_id

    async def call(  # noqa: PLR0911
        self,
        base: str,
        user: str,
        password: str,
        path: str,
        *,
        method: str = "GET",
        body: Any = None,
    ) -> Any:  # noqa: C901, PLR0911, PLR0912
        del base, user, password
        parts = urlsplit(path)
        query = parse_qs(parts.query)
        segments = parts.path.strip("/").split("/")[1:]
        body = json.loads(json.dumps(body)) if body is not None else None
        if segments == ["devices"]:
            if method == "POST":
                device_id = self._id()
                self.devices[device_id] = {**body, "id": device_id, "status": "online"}
                return self.devices[device_id]
            unique = query.get("uniqueId", [None])[0]
            return [d for d in self.devices.values() if unique in (None, d["uniqueId"])]
        if segments[0] == "devices":
            device_id = int(segments[1])
            if method == "PUT":
                self.devices[device_id] = {**body, "id": device_id}
            return self.devices[device_id]
        if segments == ["geofences"]:
            if method == "POST":
                geofence_id = self._id()
                self.geofences[geofence_id] = {**body, "id": geofence_id}
                return self.geofences[geofence_id]
            if "deviceId" in query:
                device_id = int(query["deviceId"][0])
                return [g for g in self.geofences.values() if (device_id, g["id"]) in self.links]
            return list(self.geofences.values())
        if segments[0] == "geofences" and method == "DELETE":
            self.geofences.pop(int(segments[1]))
            return None
        if segments == ["permissions"]:
            link = (body["deviceId"], body["geofenceId"])
            if method == "POST":
                self.links.add(link)
            else:
                self.links.discard(link)
            return None
        if segments == ["positions"] or segments[:2] == ["reports", "events"]:
            return []
        raise AssertionError(f"unexpected Traccar call {method} {path}")

    async def snapshot(self, base: str, user: str, password: str) -> tuple[list[Any], list[Any]]:
        del base, user, password
        positions = [
            {
                "deviceId": device_id,
                "latitude": 13.48,
                "longitude": -88.18,
                "speed": 10,
                "course": 90,
                "attributes": {},
            }
            for device_id in self.devices
        ]
        return list(self.devices.values()), positions


@pytest.fixture
def traccar(monkeypatch: pytest.MonkeyPatch) -> FakeTraccar:
    fake = FakeTraccar()
    monkeypatch.setattr(settings, "TRACCAR_URL", "http://traccar.test")
    monkeypatch.setattr(settings, "TRACCAR_USER", "erp")
    monkeypatch.setattr(settings, "TRACCAR_PASSWORD", "fake")
    monkeypatch.setattr("app.api.v1.traccar_access.traccar_call", fake.call)
    monkeypatch.setattr("app.api.v1.routers.tracking.fetch_traccar_snapshot", fake.snapshot)
    return fake


async def _linked_vehicle(
    e2e_client: Any, headers: dict[str, str], branch: str, imei: str
) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:5].upper()
    created = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=headers,
        json=_vehicle(branch, f"GPS-{suffix}", f"G {suffix}"),
    )
    assert created.status_code == 201, created.text
    linked = await e2e_client.put(
        f"/api/v1/fleet/vehicles/{created.json()['id']}/gps-device",
        headers=headers,
        json={"unique_id": imei},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["gps_linked"] is True
    return linked.json()


async def _grant_branch_managers(code: str) -> None:
    """Let branch managers manage the given permission (seed roles only read geofences)."""
    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO role_permissions (role_id, permission_id, created_at) "
                "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
                "WHERE r.name = 'GERENTE DE SUCURSAL' AND p.code = :code "
                "ON CONFLICT DO NOTHING"
            ),
            {"code": code},
        )
        await session.commit()


def _square(lng: float, lat: float) -> dict[str, Any]:
    return {
        "type": "polygon",
        "coordinates": [[lng, lat], [lng + 0.01, lat], [lng + 0.01, lat + 0.01]],
    }


async def test_tracking_is_scoped_to_the_users_branches(
    e2e_client: Any, traccar: FakeTraccar
) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    branch_a, branch_b = branches[0]["id"], branches[1]["id"]
    imei = uuid.uuid4().hex[:15]
    vehicle_a = await _linked_vehicle(e2e_client, admin, branch_a, f"A{imei}")
    vehicle_b = await _linked_vehicle(e2e_client, admin, branch_b, f"B{imei}")
    device_a = next(d for d in traccar.devices.values() if d["uniqueId"] == f"A{imei}")
    assert device_a["name"] == vehicle_a["code"]
    assert device_a["attributes"]["erpBranchId"] == branch_a

    # Un dispositivo registrado por otra empresa no puede tomarse.
    traccar.add_device(f"X{imei}", {"erpCompanyId": str(uuid.uuid4())})
    other = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=admin,
        json=_vehicle(branch_a, f"GX-{imei[:5]}", f"X {imei[:5]}"),
    )
    foreign = await e2e_client.put(
        f"/api/v1/fleet/vehicles/{other.json()['id']}/gps-device",
        headers=admin,
        json={"unique_id": f"X{imei}"},
    )
    assert foreign.status_code == 409

    await _grant_branch_managers("tracking:geofences")
    manager = await _branch_manager(e2e_client, admin, branch_a)
    snapshot = await e2e_client.get("/api/v1/tracking/positions", headers=manager)
    assert snapshot.status_code == 200, snapshot.text
    seen = {device["vehicle"]["id"] for device in snapshot.json()["devices"]}
    assert vehicle_a["id"] in seen
    assert vehicle_b["id"] not in seen
    assert (
        await e2e_client.get(f"/api/v1/tracking/positions?branch_id={branch_b}", headers=manager)
    ).status_code == 403

    company_wide = await e2e_client.post(
        "/api/v1/tracking/geofences",
        headers=manager,
        json={"name": "Toda la empresa", "shape": _square(-88.2, 13.4)},
    )
    assert company_wide.status_code == 403
    own = await e2e_client.post(
        "/api/v1/tracking/geofences",
        headers=manager,
        json={"name": "Patio A", "branch_id": branch_a, "shape": _square(-88.2, 13.4)},
    )
    assert own.status_code == 201, own.text
    assert own.json()["can_manage"] is True
    assert (device_a["id"], own.json()["id"]) in traccar.links
    device_b = next(d for d in traccar.devices.values() if d["uniqueId"] == f"B{imei}")
    assert (device_b["id"], own.json()["id"]) not in traccar.links

    shared = await e2e_client.post(
        "/api/v1/tracking/geofences",
        headers=admin,
        json={"name": "Zona metropolitana", "shape": _square(-89.2, 13.7)},
    )
    assert shared.status_code == 201, shared.text
    foreign_branch = await e2e_client.post(
        "/api/v1/tracking/geofences",
        headers=admin,
        json={"name": "Patio B", "branch_id": branch_b, "shape": _square(-88.0, 13.3)},
    )
    assert foreign_branch.status_code == 201, foreign_branch.text

    visible = (await e2e_client.get("/api/v1/tracking/geofences", headers=manager)).json()
    by_name = {item["name"]: item for item in visible}
    assert set(by_name) == {"Patio A", "Zona metropolitana"}
    assert by_name["Zona metropolitana"]["can_manage"] is False
    assert (
        await e2e_client.delete(
            f"/api/v1/tracking/geofences/{shared.json()['id']}", headers=manager
        )
    ).status_code == 403
    assert (
        await e2e_client.delete(
            f"/api/v1/tracking/geofences/{foreign_branch.json()['id']}", headers=manager
        )
    ).status_code == 404

    # Al desvincular, el ERP deja de mostrarlo y Traccar pierde las etiquetas de la empresa.
    unlinked = await e2e_client.delete(
        f"/api/v1/fleet/vehicles/{vehicle_a['id']}/gps-device", headers=admin
    )
    assert unlinked.status_code == 200, unlinked.text
    assert "erpCompanyId" not in traccar.devices[device_a["id"]]["attributes"]
    after = (await e2e_client.get("/api/v1/tracking/positions", headers=manager)).json()
    assert after["devices"] == []

"""Guided GPS setup: what a device needs to connect and whether it is reporting."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.application.tracking import TraccarUnavailableError
from app.core.config import settings

from tests.e2e.test_fleet_tracking import FakeTraccar, _linked_vehicle, traccar  # noqa: F401
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle

pytestmark = pytest.mark.e2e

PUBLIC_URL = "http://192.168.1.50:5055"


@pytest.fixture
def public_url(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "TRACCAR_PUBLIC_URL", PUBLIC_URL)
    return PUBLIC_URL


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


async def _vehicle_id(e2e_client: Any, headers: dict[str, str], branch: str) -> str:
    suffix = uuid.uuid4().hex[:5].upper()
    created = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=headers,
        json=_vehicle(branch, f"GPS-{suffix}", f"G {suffix}"),
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_phone_link_generates_an_identifier_and_keeps_it(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
    public_url: str,
) -> None:
    admin = await _admin(e2e_client)
    vehicle_id = await _vehicle_id(e2e_client, admin, (await _branches(e2e_client, admin))[0]["id"])
    url = f"/api/v1/fleet/vehicles/{vehicle_id}"

    before = await e2e_client.get(f"{url}/gps-setup", headers=admin)
    assert before.status_code == 200, before.text
    assert before.json()["phone_config_uri"] is None
    assert before.json()["private_network"] is True

    first = await e2e_client.put(f"{url}/gps-device", headers=admin, json={"kind": "phone"})
    assert first.status_code == 200, first.text
    unique_id = first.json()["gps_device_unique_id"]
    assert unique_id.startswith("GS-")

    again = await e2e_client.put(f"{url}/gps-device", headers=admin, json={"kind": "phone"})
    assert again.json()["gps_device_unique_id"] == unique_id

    setup = (await e2e_client.get(f"{url}/gps-setup", headers=admin)).json()
    assert setup["configured"] is True
    assert setup["phone_config_uri"].startswith(f"{public_url}?id={unique_id}&")


async def test_manual_identifier_cannot_take_the_phone_prefix(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
) -> None:
    admin = await _admin(e2e_client)
    vehicle_id = await _vehicle_id(e2e_client, admin, (await _branches(e2e_client, admin))[0]["id"])

    response = await e2e_client.put(
        f"/api/v1/fleet/vehicles/{vehicle_id}/gps-device",
        headers=admin,
        json={"unique_id": "GS-ABC123"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize("body", [{"kind": "tracker"}, {"kind": "phone", "unique_id": "ABC123"}])
async def test_identifier_must_match_the_kind(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
    body: dict[str, str],
) -> None:
    admin = await _admin(e2e_client)
    vehicle_id = await _vehicle_id(e2e_client, admin, (await _branches(e2e_client, admin))[0]["id"])

    response = await e2e_client.put(
        f"/api/v1/fleet/vehicles/{vehicle_id}/gps-device", headers=admin, json=body
    )

    assert response.status_code == 422


async def test_status_follows_the_real_signal(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
    public_url: str,
) -> None:
    del public_url
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    vehicle = await _linked_vehicle(e2e_client, admin, branch, uuid.uuid4().hex[:15])
    url = f"/api/v1/fleet/vehicles/{vehicle['id']}/gps-status"
    device_id = next(iter(traccar.devices))

    waiting = (await e2e_client.get(url, headers=admin)).json()
    assert waiting["state"] == "waiting"
    assert waiting["kind"] == "tracker"
    assert waiting["last_update"] is None

    now = datetime.now(UTC)
    traccar.devices[device_id]["lastUpdate"] = _iso(now - timedelta(minutes=2))
    traccar.positions[device_id] = [
        {
            "deviceId": device_id,
            "latitude": 13.48,
            "longitude": -88.18,
            "fixTime": _iso(now),
            "attributes": {"batteryLevel": 80},
        }
    ]
    reporting = (await e2e_client.get(url, headers=admin)).json()
    assert reporting["state"] == "reporting"
    assert reporting["battery_level"] == 80

    traccar.devices[device_id]["lastUpdate"] = _iso(now - timedelta(hours=3))
    assert (await e2e_client.get(url, headers=admin)).json()["state"] == "silent"


async def test_status_does_not_invent_a_state_when_the_server_is_down(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    vehicle = await _linked_vehicle(e2e_client, admin, branch, uuid.uuid4().hex[:15])

    async def down(*_: Any, **__: Any) -> Any:
        raise TraccarUnavailableError

    monkeypatch.setattr("app.api.v1.traccar_access.traccar_call", down)

    response = await e2e_client.get(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/gps-status", headers=admin
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "unavailable"


async def test_unlinked_vehicle_says_whether_it_can_connect(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await _admin(e2e_client)
    vehicle_id = await _vehicle_id(e2e_client, admin, (await _branches(e2e_client, admin))[0]["id"])
    url = f"/api/v1/fleet/vehicles/{vehicle_id}"

    monkeypatch.setattr(settings, "TRACCAR_PUBLIC_URL", None)
    missing = (await e2e_client.get(f"{url}/gps-status", headers=admin)).json()
    assert missing["state"] == "unlinked"
    assert missing["server_configured"] is False
    assert (await e2e_client.get(f"{url}/gps-setup", headers=admin)).json()["configured"] is False

    monkeypatch.setattr(settings, "TRACCAR_PUBLIC_URL", PUBLIC_URL)
    assert (await e2e_client.get(f"{url}/gps-status", headers=admin)).json()["server_configured"]


async def test_setup_and_status_are_scoped_to_the_users_branches(
    e2e_client: Any,
    traccar: FakeTraccar,  # noqa: F811
    public_url: str,
) -> None:
    del public_url
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    other = await _vehicle_id(e2e_client, admin, branches[1]["id"])
    manager = await _branch_manager(e2e_client, admin, branches[0]["id"])

    status_response = await e2e_client.get(
        f"/api/v1/fleet/vehicles/{other}/gps-status", headers=manager
    )
    setup_response = await e2e_client.get(
        f"/api/v1/fleet/vehicles/{other}/gps-setup", headers=manager
    )

    assert status_response.status_code == 404
    assert setup_response.status_code in {403, 404}

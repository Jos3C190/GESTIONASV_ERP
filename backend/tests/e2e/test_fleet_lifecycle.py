"""Trash for fleet vehicles and drivers: blockers, listing and restore."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.e2e.test_fleet_drivers import _employee
from tests.e2e.test_fleet_vehicles import _admin, _branches, _vehicle

pytestmark = pytest.mark.e2e

REASON = {"reason": "Registro duplicado por error de captura"}


async def _delete(client: Any, headers: dict[str, str], resource: str, record_id: str) -> Any:
    return await client.request(
        "DELETE", f"/api/v1/lifecycle/{resource}/{record_id}", headers=headers, json=REASON
    )


async def test_vehicle_and_driver_go_to_trash_only_when_released(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    employee = await _employee(e2e_client, admin, branch)
    suffix = uuid.uuid4().hex[:5].upper()
    vehicle = (
        await e2e_client.post(
            "/api/v1/fleet/vehicles",
            headers=admin,
            json=_vehicle(branch, f"LC-{suffix}", f"L {suffix}", kind="pickup"),
        )
    ).json()
    driver = (
        await e2e_client.post(
            "/api/v1/drivers",
            headers=admin,
            json={"employee_id": employee["id"], "branch_id": branch, "license_class": "liviana"},
        )
    ).json()
    assigned = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/assignment",
        headers=admin,
        json={"driver_id": driver["id"], "override_reason": "Licencia en trámite de renovación"},
    )
    assert assigned.status_code in (200, 201), assigned.text

    for resource, record in (("fleet_vehicles", vehicle), ("drivers", driver)):
        blocked = await _delete(e2e_client, admin, resource, record["id"])
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["code"] == "record_has_dependencies"
    employee_blocked = await _delete(e2e_client, admin, "employees", employee["id"])
    assert employee_blocked.status_code == 409
    assert "perfil de conductor" in employee_blocked.json()["message"]

    ended = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/assignment/end",
        headers=admin,
        json={"reason": "Cambio de unidad"},
    )
    assert ended.status_code in (200, 204), ended.text

    deleted = await _delete(e2e_client, admin, "fleet_vehicles", vehicle["id"])
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["label"] == f"LC-{suffix} L {suffix}"
    assert (
        await e2e_client.get(f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=admin)
    ).status_code == 404
    driver_deleted = await _delete(e2e_client, admin, "drivers", driver["id"])
    assert driver_deleted.status_code == 200, driver_deleted.text
    assert driver_deleted.json()["label"] == f"{employee['first_name']} {employee['last_name']}"

    trash = await e2e_client.get("/api/v1/lifecycle/trash?resource=drivers", headers=admin)
    assert trash.status_code == 200, trash.text
    assert driver["id"] in {item["record_id"] for item in trash.json()["items"]}

    restored = await e2e_client.post(
        f"/api/v1/lifecycle/fleet_vehicles/{vehicle['id']}/restore", headers=admin
    )
    assert restored.status_code == 200, restored.text
    back = await e2e_client.get(f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=admin)
    assert back.status_code == 200
    assert back.json()["driver"] is None

"""Drivers: employees with a driving profile, fitness rules and assignments."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle

pytestmark = pytest.mark.e2e


async def _employee(e2e_client: Any, headers: dict[str, str], branch_id: str) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:6].upper()
    response = await e2e_client.post(
        "/api/v1/employees",
        headers={**headers, "X-Branch-ID": branch_id},
        json={
            "company_id": headers["X-Company-ID"],
            "employee_code": f"DRV-{suffix}",
            "first_name": "Carlos",
            "last_name": f"Martínez {suffix}",
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_driver_profile_assignment_and_invariants(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    branch = branches[0]["id"]
    employee = await _employee(e2e_client, admin, branch)
    suffix = uuid.uuid4().hex[:5].upper()
    vehicle = (
        await e2e_client.post(
            "/api/v1/fleet/vehicles",
            headers=admin,
            json=_vehicle(branch, f"DV-{suffix}", f"V {suffix}", kind="pickup"),
        )
    ).json()

    candidates = await e2e_client.get(
        f"/api/v1/drivers/candidates?branch_id={branch}", headers=admin
    )
    assert candidates.status_code == 200, candidates.text
    assert employee["id"] in {item["employee_id"] for item in candidates.json()}

    wrong_branch = await e2e_client.post(
        "/api/v1/drivers",
        headers=admin,
        json={
            "employee_id": employee["id"],
            "branch_id": branches[1]["id"],
            "license_class": "liviana",
        },
    )
    assert wrong_branch.status_code == 409
    assert wrong_branch.json()["code"] == "employee_branch_unassigned"

    created = await e2e_client.post(
        "/api/v1/drivers",
        headers=admin,
        json={"employee_id": employee["id"], "branch_id": branch, "license_class": "liviana"},
    )
    assert created.status_code == 201, created.text
    driver = created.json()
    assert driver["employee"]["code"] == employee["employee_code"]
    assert driver["compliance"]["state"] == "blocked"  # sin licencia cargada
    duplicate = await e2e_client.post(
        "/api/v1/drivers",
        headers=admin,
        json={"employee_id": employee["id"], "branch_id": branch, "license_class": "liviana"},
    )
    assert duplicate.status_code == 409

    # Sin licencia vigente: bloqueado salvo excepción autorizada con motivo.
    refused = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/assignment",
        headers=admin,
        json={"driver_id": driver["id"]},
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "driver_not_fit"
    assigned = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/assignment",
        headers=admin,
        json={"driver_id": driver["id"], "override_reason": "Licencia en trámite, viaje urgente"},
    )
    assert assigned.status_code == 201, assigned.text
    detail = (await e2e_client.get(f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=admin)).json()
    assert detail["driver"]["driver_id"] == driver["id"]

    # La clase de licencia debe permitir el tipo de vehículo asignado.
    heavy = await e2e_client.patch(
        f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=admin, json={"kind": "tanker"}
    )
    assert heavy.status_code == 409
    assert heavy.json()["code"] == "license_class_incompatible"

    # Un conductor no puede perder su sucursal base ni el empleado inactivarse mientras sea conductor.
    assignments = await e2e_client.get(
        f"/api/v1/employees/{employee['id']}/branch-assignments", headers=admin
    )
    home = next(item for item in assignments.json() if item["branch_id"] == branch)
    end_home = await e2e_client.post(
        f"/api/v1/employee-branch-assignments/{home['id']}/end", headers=admin
    )
    assert end_home.status_code == 409
    deactivate = await e2e_client.patch(
        f"/api/v1/employees/{employee['id']}",
        headers={**admin, "X-Branch-ID": branch},
        json={"status": "inactivo"},
    )
    assert deactivate.status_code == 409

    # Suspender al conductor libera el vehículo.
    suspended = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/status",
        headers=admin,
        json={"status": "suspended", "reason": "Investigación de incidente"},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["vehicle"] is None
    history = await e2e_client.get(f"/api/v1/drivers/{driver['id']}/assignments", headers=admin)
    assert history.json()[0]["ends_at"] is not None
    assert "suspendido" in history.json()[0]["end_reason"]

    blocked_again = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/assignment",
        headers=admin,
        json={"driver_id": driver["id"], "override_reason": "Intento con conductor suspendido"},
    )
    assert blocked_again.status_code == 409

    license_categories = await e2e_client.get(
        f"/api/v1/drivers/{driver['id']}/documents/categories", headers=admin
    )
    assert license_categories.status_code == 200, license_categories.text
    assert [item["code"] for item in license_categories.json()] == ["driver_license"]


async def test_branch_manager_cannot_override_or_reach_other_branches(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    own, other = branches[0]["id"], branches[1]["id"]
    foreign_employee = await _employee(e2e_client, admin, other)
    foreign_driver = (
        await e2e_client.post(
            "/api/v1/drivers",
            headers=admin,
            json={
                "employee_id": foreign_employee["id"],
                "branch_id": other,
                "license_class": "pesada",
            },
        )
    ).json()
    own_employee = await _employee(e2e_client, admin, own)
    own_driver = (
        await e2e_client.post(
            "/api/v1/drivers",
            headers=admin,
            json={"employee_id": own_employee["id"], "branch_id": own, "license_class": "pesada"},
        )
    ).json()
    suffix = uuid.uuid4().hex[:5].upper()
    own_vehicle = (
        await e2e_client.post(
            "/api/v1/fleet/vehicles",
            headers=admin,
            json=_vehicle(own, f"BM-{suffix}", f"B {suffix}"),
        )
    ).json()

    manager = await _branch_manager(e2e_client, admin, own)
    listed = await e2e_client.get("/api/v1/drivers", headers=manager)
    assert listed.status_code == 200, listed.text
    ids = {item["id"] for item in listed.json()["items"]}
    assert own_driver["id"] in ids
    assert foreign_driver["id"] not in ids
    assert (
        await e2e_client.get(f"/api/v1/drivers/{foreign_driver['id']}", headers=manager)
    ).status_code == 404

    cross = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{own_vehicle['id']}/assignment",
        headers=manager,
        json={"driver_id": foreign_driver["id"]},
    )
    assert cross.status_code == 404

    no_override = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{own_vehicle['id']}/assignment",
        headers=manager,
        json={"driver_id": own_driver["id"], "override_reason": "Lo autorizo yo mismo"},
    )
    assert no_override.status_code == 409
    assert "autorización de excepciones" in no_override.json()["message"]

"""Fleet vehicles: company isolation, branch isolation and business rules."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Flota!Segura2026"


async def _login(e2e_client: Any, username: str, password: str = PASSWORD) -> str:
    response = await e2e_client.post(
        "/api/v1/auth/login", json={"login": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return f"Bearer {response.json()['access_token']}"


async def _admin(e2e_client: Any) -> dict[str, str]:
    username = f"fleet-admin-{uuid.uuid4().hex[:8]}"
    await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=True,
    )
    company_id = await get_test_company_id()
    return {"Authorization": await _login(e2e_client, username), "X-Company-ID": str(company_id)}


async def _branches(e2e_client: Any, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = await e2e_client.get(
        f"/api/v1/branches?company_id={headers['X-Company-ID']}", headers=headers
    )
    assert response.status_code == 200, response.text
    branches = [branch for branch in response.json() if branch.get("is_active", True)]
    assert len(branches) >= 2
    return branches


async def _branch_manager(e2e_client: Any, admin: dict[str, str], branch_id: str) -> dict[str, str]:
    roles = (await e2e_client.get("/api/v1/roles/catalogue", headers=admin)).json()
    manager = next(role for role in roles if role["name"] == "GERENTE DE SUCURSAL")
    suffix = uuid.uuid4().hex[:8]
    created = await e2e_client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "company_id": admin["X-Company-ID"],
            "username": f"fleet-mgr-{suffix}",
            "email": f"fleet-mgr-{suffix}@example.com",
            "password": PASSWORD,
            "role_ids": [manager["id"]],
        },
    )
    assert created.status_code == 201, created.text
    access = await e2e_client.put(
        f"/api/v1/users/{created.json()['id']}/companies/{admin['X-Company-ID']}/branch-access",
        headers=admin,
        json={
            "access_all_branches": False,
            "branch_ids": [branch_id],
            "default_branch_id": branch_id,
        },
    )
    assert access.status_code == 200, access.text
    return {
        "Authorization": await _login(e2e_client, f"fleet-mgr-{suffix}"),
        "X-Company-ID": admin["X-Company-ID"],
    }


def _vehicle(branch_id: str, code: str, plate: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "branch_id": branch_id,
        "code": code,
        "plate": plate,
        "kind": "refrigerated",
        "brand": "Isuzu",
        "model": "ELF 400",
        "year": 2024,
        "capacity_kg": "4000",
        "fuel_type": "diesel",
        "odometer_km": "1250.5",
    }
    payload.update(overrides)
    return payload


async def test_vehicle_lifecycle_and_rules(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    suffix = uuid.uuid4().hex[:5].upper()

    created = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=admin,
        json=_vehicle(branch, f"fl {suffix}", f"c {suffix}"),
    )
    assert created.status_code == 201, created.text
    vehicle = created.json()
    assert vehicle["code"] == f"FL-{suffix}"
    assert vehicle["plate"] == f"C {suffix}"
    assert vehicle["operational_status"] == "available"
    assert vehicle["odometer_km"] == "1250.5"
    # Sin tarjeta de circulación, seguro ni revisión técnica el vehículo no es apto.
    assert vehicle["compliance"]["state"] == "blocked"
    assert {issue["code"] for issue in vehicle["compliance"]["issues"]} >= {"document_missing"}

    duplicate = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=admin,
        json=_vehicle(branch, f"OTRO-{suffix}", f"C {suffix}"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "vehicle_plate_taken"

    no_reason = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/status",
        headers=admin,
        json={"status": "out_of_service"},
    )
    assert no_reason.status_code == 422

    retired = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/status",
        headers=admin,
        json={"status": "retired", "reason": "Venta del vehículo"},
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["status"] == "retired"

    edit_retired = await e2e_client.patch(
        f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=admin, json={"color": "Blanco"}
    )
    assert edit_retired.status_code == 409

    listed = await e2e_client.get("/api/v1/fleet/vehicles", headers=admin)
    assert vehicle["id"] not in {item["id"] for item in listed.json()["items"]}
    with_retired = await e2e_client.get(
        "/api/v1/fleet/vehicles?include_retired=true", headers=admin
    )
    assert vehicle["id"] in {item["id"] for item in with_retired.json()["items"]}


async def test_branch_users_only_see_and_manage_their_branch(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    own, other = branches[0]["id"], branches[1]["id"]
    suffix = uuid.uuid4().hex[:5].upper()
    foreign = await e2e_client.post(
        "/api/v1/fleet/vehicles", headers=admin, json=_vehicle(other, f"OT-{suffix}", f"P {suffix}")
    )
    assert foreign.status_code == 201, foreign.text
    manager = await _branch_manager(e2e_client, admin, own)

    listed = await e2e_client.get("/api/v1/fleet/vehicles", headers=manager)
    assert listed.status_code == 200, listed.text
    assert all(item["branch_id"] == own for item in listed.json()["items"])
    assert foreign.json()["id"] not in {item["id"] for item in listed.json()["items"]}

    hidden = await e2e_client.get(f"/api/v1/fleet/vehicles/{foreign.json()['id']}", headers=manager)
    assert hidden.status_code == 404

    other_filter = await e2e_client.get(
        f"/api/v1/fleet/vehicles?branch_id={other}", headers=manager
    )
    assert other_filter.status_code == 403

    create_elsewhere = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=manager,
        json=_vehicle(other, f"X-{suffix}", f"X {suffix}"),
    )
    assert create_elsewhere.status_code == 403

    own_vehicle = await e2e_client.post(
        "/api/v1/fleet/vehicles", headers=manager, json=_vehicle(own, f"OW-{suffix}", f"O {suffix}")
    )
    assert own_vehicle.status_code == 201, own_vehicle.text

    move_out = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{own_vehicle.json()['id']}/branch",
        headers=manager,
        json={"branch_id": other, "reason": "Reubicación"},
    )
    assert move_out.status_code == 403

    docs = await e2e_client.get(
        f"/api/v1/fleet/vehicles/{foreign.json()['id']}/documents", headers=manager
    )
    assert docs.status_code == 404


async def test_vehicle_documents_follow_category_rules(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    suffix = uuid.uuid4().hex[:5].upper()
    vehicle = (
        await e2e_client.post(
            "/api/v1/fleet/vehicles",
            headers=admin,
            json=_vehicle(branch, f"DC-{suffix}", f"D {suffix}"),
        )
    ).json()
    categories = await e2e_client.get(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/documents/categories", headers=admin
    )
    assert categories.status_code == 200, categories.text
    by_code = {item["code"]: item for item in categories.json()}
    assert by_code["circulation_card"]["compliance_required"] is True
    assert by_code["circulation_card"]["requires_expiry"] is True
    assert by_code["purchase_invoice"]["compliance_required"] is False

    missing_expiry = await e2e_client.post(
        f"/api/v1/fleet/vehicles/{vehicle['id']}/documents/uploads",
        headers=admin,
        json={
            "file_name": "revision.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "checksum_sha256": "a" * 64,
            "category_id": by_code["technical_inspection"]["id"],
        },
    )
    assert missing_expiry.status_code == 422
    assert missing_expiry.json()["code"] == "document_expiry_required"

    library = await e2e_client.get("/api/v1/documents/library?module=fleet", headers=admin)
    assert library.status_code in {200, 422}
    if library.status_code == 200:
        assert library.json()["items"] == []


async def test_other_company_cannot_reach_vehicle(e2e_client: Any) -> None:
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.organization import Company

    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    suffix = uuid.uuid4().hex[:5].upper()
    vehicle = (
        await e2e_client.post(
            "/api/v1/fleet/vehicles",
            headers=admin,
            json=_vehicle(branch, f"CO-{suffix}", f"Q {suffix}"),
        )
    ).json()
    async with async_session_factory() as session:
        template = await session.get(Company, uuid.UUID(admin["X-Company-ID"]))
        assert template is not None
        other = Company(
            name=f"Empresa ajena {suffix}",
            commercial_name=f"Ajena {suffix}",
            nit=f"0614-{suffix}",
            nrc=f"N{suffix}",
            address="San Salvador",
            department_id=template.department_id,
            municipality_id=template.municipality_id,
            district_id=template.district_id,
        )
        session.add(other)
        await session.commit()
        other_company = other.id
    other_headers = {**admin, "X-Company-ID": str(other_company)}
    response = await e2e_client.get(
        f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=other_headers
    )
    assert response.status_code == 404
    listing = await e2e_client.get("/api/v1/fleet/vehicles", headers=other_headers)
    assert vehicle["id"] not in {item["id"] for item in listing.json()["items"]}

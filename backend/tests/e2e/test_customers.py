"""API de clientes con identidad fiscal: flujo, auditoría, permisos y aislamiento."""

from __future__ import annotations

import uuid

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Municipality,
    UserCompany,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"
BASE = "/api/v1/customers"


async def _login(client: AsyncClient, *, superuser: bool) -> tuple[str, dict[str, str]]:
    username = f"clientes-{uuid.uuid4().hex[:8]}"
    user_id = await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=superuser,
    )
    login = await client.post("/api/v1/auth/login", json={"login": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return user_id, {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Company-ID": str(await get_test_company_id()),
    }


async def _geography() -> dict[str, str]:
    async with async_session_factory() as session:
        row = (
            await session.execute(
                select(GeographicDepartment.id, Municipality.id, District.id)
                .join(Municipality, Municipality.department_id == GeographicDepartment.id)
                .join(District, District.municipality_id == Municipality.id)
                .where(
                    GeographicDepartment.name == "San Miguel",
                    Municipality.name == "San Miguel Centro",
                    District.name == "San Miguel",
                )
            )
        ).one()
    return {
        "department_id": str(row[0]),
        "municipality_id": str(row[1]),
        "district_id": str(row[2]),
    }


def _taxpayer(geography: dict[str, str]) -> dict[str, object]:
    return {
        "customer_type": "taxpayer",
        "name": "Cafetería El Trigal, S.A. de C.V.",
        "person_type": "2",
        "taxpayer_category": "other",
        "document_type": "36",
        "document_number": "0614-010101-101-1",
        "nrc": "123456-7",
        "activity_code": "56101",
        "geography": geography,
        "address_line": "Avenida Roosevelt 12",
        "email": "compras@trigal.example",
        "credit_days": 15,
        "credit_limit": "500.00",
    }


async def test_taxpayer_flow_with_delivery_addresses_is_audited(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    geography = await _geography()
    created = await e2e_client.post(BASE, json=_taxpayer(geography), headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"].startswith("CLI-")
    assert body["document_number"] == "06140101011011"
    assert body["receivable_documents"] == ["01", "03"]
    assert body["tax_credit_missing"] == []
    assert body["address"]["district_code"] == "17"
    customer_id = body["id"]

    incomplete = {**_taxpayer(geography), "nrc": None}
    updated = await e2e_client.put(f"{BASE}/{customer_id}", json=incomplete, headers=headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["receivable_documents"] == ["01"]
    assert updated.json()["tax_credit_missing"] == ["NRC."]

    address = await e2e_client.post(
        f"{BASE}/{customer_id}/delivery-addresses",
        json={"label": "Cafetería centro", "address_line": "2.ª Calle Oriente 5",
              "latitude": "13.481000", "longitude": "-88.177000"},
        headers=headers,
    )  # fmt: skip
    assert address.status_code == 201, address.text
    assert address.json()["is_default"] is True
    detail = await e2e_client.get(f"{BASE}/{customer_id}", headers=headers)
    assert len(detail.json()["delivery_addresses"]) == 1

    deactivated = await e2e_client.patch(
        f"{BASE}/{customer_id}/status", json={"is_active": False}, headers=headers
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    company_id = uuid.UUID(headers["X-Company-ID"])
    async with async_session_factory() as session:
        audited = dict(
            (
                await session.execute(
                    select(AuditLog.resource_type, func.count())
                    .where(
                        AuditLog.company_id == company_id,
                        AuditLog.resource_id.in_([customer_id, address.json()["id"]]),
                    )
                    .group_by(AuditLog.resource_type)
                )
            )
            .tuples()
            .all()
        )
    assert audited == {"sales_customer": 3, "sales_customer_delivery_address": 1}


async def test_validation_errors_are_in_spanish(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    geography = await _geography()
    bad_nit = await e2e_client.post(
        BASE, json={**_taxpayer(geography), "document_number": "0614-1"}, headers=headers
    )
    assert bad_nit.status_code == 422
    assert bad_nit.json()["code"] == "customer_nit_invalid"
    await e2e_client.post(BASE, json=_taxpayer(geography), headers=headers)
    duplicate = await e2e_client.post(BASE, json=_taxpayer(geography), headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "customer_document_duplicate"
    foreign = await e2e_client.post(
        BASE, json={"customer_type": "foreign", "name": "Panadería Centroamericana"},
        headers=headers,
    )  # fmt: skip
    assert foreign.status_code == 422
    assert foreign.json()["code"] == "customer_country_required"


async def test_generic_customer_per_branch(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    async with async_session_factory() as session:
        branch_id = await session.scalar(
            select(Branch.id).where(Branch.company_id == uuid.UUID(headers["X-Company-ID"]))
        )
    first = await e2e_client.get(
        f"{BASE}/generic", params={"branch_id": str(branch_id)}, headers=headers
    )
    assert first.status_code == 200, first.text
    assert first.json()["name"] == "Consumidor final"
    assert first.json()["is_generic"] is True
    again = await e2e_client.get(
        f"{BASE}/generic", params={"branch_id": str(branch_id)}, headers=headers
    )
    assert again.json()["id"] == first.json()["id"]
    locked = await e2e_client.patch(
        f"{BASE}/{first.json()['id']}/status", json={"is_active": False}, headers=headers
    )
    assert locked.status_code == 422
    assert locked.json()["code"] == "customer_generic_locked"
    listed = await e2e_client.get(BASE, headers=headers)
    assert first.json()["id"] not in {item["id"] for item in listed.json()["items"]}


async def test_another_company_never_sees_the_customer(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    geography = await _geography()
    created = await e2e_client.post(BASE, json=_taxpayer(geography), headers=headers)
    customer_id = created.json()["id"]
    async with async_session_factory() as session:
        original = await session.get(Company, uuid.UUID(headers["X-Company-ID"]))
        assert original is not None
        suffix = uuid.uuid4().hex[:8]
        other = Company(
            name=f"Otra {suffix}, S.A. de C.V.",
            commercial_name=f"Otra {suffix}",
            nit=f"{uuid.uuid4().int % 10**14:014d}",
            nrc=f"{uuid.uuid4().int % 10**6:06d}",
            address="Aislada",
            department_id=original.department_id,
            municipality_id=original.municipality_id,
            district_id=original.district_id,
        )
        session.add(other)
        await session.flush()
        session.add(UserCompany(user_id=uuid.UUID(user_id), company_id=other.id))
        await session.commit()
        other_id = other.id
    other_headers = {**headers, "X-Company-ID": str(other_id)}
    assert (await e2e_client.get(f"{BASE}/{customer_id}", headers=other_headers)).status_code == 404
    assert (await e2e_client.get(BASE, headers=other_headers)).json()["meta"]["total"] == 0
    # El mismo NIT puede registrarse como cliente de otra empresa.
    again = await e2e_client.post(BASE, json=_taxpayer(geography), headers=other_headers)
    assert again.status_code == 201, again.text


async def test_customers_require_permissions(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=False)
    assert (await e2e_client.get(BASE, headers=headers)).status_code == 403
    denied = await e2e_client.post(BASE, json={"name": "Ana López"}, headers=headers)
    assert denied.status_code == 403

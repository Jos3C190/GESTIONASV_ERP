"""API de configuración fiscal del emisor: flujo completo, auditoría, permisos y aislamiento."""

from __future__ import annotations

import uuid

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import Branch, Company, UserCompany
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"
BASE = "/api/v1/fiscal"


async def _login(client: AsyncClient, *, superuser: bool) -> tuple[str, dict[str, str]]:
    username = f"fiscal-{uuid.uuid4().hex[:8]}"
    user_id = await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=superuser,
    )
    login = await client.post("/api/v1/auth/login", json={"login": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    company_id = await get_test_company_id()
    return user_id, {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def _second_company(user_id: str) -> tuple[uuid.UUID, uuid.UUID]:
    async with async_session_factory() as session:
        original = await session.get(Company, await get_test_company_id(session=session))
        assert original is not None
        suffix = uuid.uuid4().hex[:8]
        other = Company(
            name=f"Otra emisora {suffix}, S.A. de C.V.",
            commercial_name=f"Otra emisora {suffix}",
            nit=f"{uuid.uuid4().int % 10**14:014d}",
            nrc=f"{uuid.uuid4().int % 10**6:06d}",
            address="Emisor aislado",
            department_id=original.department_id,
            municipality_id=original.municipality_id,
            district_id=original.district_id,
        )
        session.add(other)
        await session.flush()
        branch = Branch(
            company_id=other.id,
            name=f"Casa matriz {suffix}",
            code=f"CM{suffix[:4]}",
            address="Emisor aislado",
            department_id=original.department_id,
            municipality_id=original.municipality_id,
            district_id=original.district_id,
        )
        session.add(branch)
        session.add(
            UserCompany(user_id=uuid.UUID(user_id), company_id=other.id, access_all_branches=True)
        )
        await session.commit()
        return other.id, branch.id


async def _configure(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    activity = await client.post(
        f"{BASE}/activities", json={"code": "10712", "is_primary": True}, headers=headers
    )
    assert activity.status_code == 201, activity.text
    options = (await client.get(f"{BASE}/branch-options", headers=headers)).json()
    free = [o for o in options if o["establishment_id"] is None]
    assert free, options
    establishment = await client.post(
        f"{BASE}/establishments",
        json={
            "branch_id": free[0]["id"],
            "establishment_type": "02",
            "code": "M001",
            "activity_id": activity.json()["id"],
        },
        headers=headers,
    )
    assert establishment.status_code == 201, establishment.text
    point = await client.post(
        f"{BASE}/establishments/{establishment.json()['id']}/points-of-sale",
        json={"code": "P001", "name": "Caja 1"},
        headers=headers,
    )
    assert point.status_code == 201, point.text
    return {"establishment": establishment.json(), "point": point.json()}


async def test_catalogs_are_served_from_hacienda_version(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    catalogs = await e2e_client.get(f"{BASE}/catalogs", headers=headers)
    assert catalogs.status_code == 200, catalogs.text
    assert len(catalogs.json()) == 33
    districts = await e2e_client.get(
        f"{BASE}/catalogs/cat-008", params={"group": "06"}, headers=headers
    )
    assert districts.status_code == 200, districts.text
    assert {"group_code": "06", "code": "14", "name": "SAN SALVADOR"} in districts.json()
    missing = await e2e_client.get(f"{BASE}/catalogs/CAT-099", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "fiscal_catalog_unknown"


async def test_issuer_configuration_flow_is_audited(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    # La semilla deja el NRC «Pendiente de verificación»: no sirve para emitir.
    async with async_session_factory() as session:
        company = await session.get(Company, uuid.UUID(headers["X-Company-ID"]))
        assert company is not None
        company.nrc = "123456-7"
        await session.commit()
    profile = await e2e_client.get(f"{BASE}/profile", headers=headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["configured"] is False
    assert profile.json()["operating_mode"] == "simulated"
    assert profile.json()["production_blockers"]

    configured = await _configure(e2e_client, headers)
    establishment = configured["establishment"]
    assert isinstance(establishment, dict)
    assert establishment["address"]["complete"] is True
    assert establishment["activity_code"] == "10712"

    enable = await e2e_client.put(
        f"{BASE}/document-types/01",
        json={"is_enabled": True, "certification_status": "pending"},
        headers=headers,
    )
    assert enable.status_code == 200, enable.text
    production = {
        "taxpayer_category": "medium",
        "person_type": "2",
        "operating_mode": "production",
        "dte_email": "facturacion@example.com",
        "dte_phone": "2222-0000",
    }
    blocked = await e2e_client.put(f"{BASE}/profile", json=production, headers=headers)
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "fiscal_production_not_ready"
    assert "Factura" in blocked.json()["message"]

    approve = await e2e_client.put(
        f"{BASE}/document-types/01",
        json={"is_enabled": True, "certification_status": "approved", "notes": "Aprobadas"},
        headers=headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["certified_at"] is not None
    saved = await e2e_client.put(f"{BASE}/profile", json=production, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["operating_mode"] == "production"
    assert saved.json()["production_blockers"] == []

    company_id = uuid.UUID(headers["X-Company-ID"])
    async with async_session_factory() as session:
        audited = dict(
            (
                await session.execute(
                    select(AuditLog.resource_type, func.count())
                    .where(
                        AuditLog.company_id == company_id,
                        AuditLog.resource_type.like("fiscal_%"),
                    )
                    .group_by(AuditLog.resource_type)
                )
            ).all()
        )
    assert audited == {
        "fiscal_activity": 1,
        "fiscal_establishment": 1,
        "fiscal_point_of_sale": 1,
        "fiscal_document_type": 2,
        "fiscal_profile": 1,
    }


async def test_invalid_codes_return_spanish_errors(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    options = (await e2e_client.get(f"{BASE}/branch-options", headers=headers)).json()
    response = await e2e_client.post(
        f"{BASE}/establishments",
        json={"branch_id": options[0]["id"], "establishment_type": "01", "code": "M001"},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "fiscal_establishment_code_type_mismatch"
    unknown = await e2e_client.put(
        f"{BASE}/document-types/02",
        json={"is_enabled": True, "certification_status": "pending"},
        headers=headers,
    )
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "fiscal_document_type_invalid"


async def test_another_company_never_sees_this_issuer(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    configured = await _configure(e2e_client, headers)
    establishment = configured["establishment"]
    point = configured["point"]
    assert isinstance(establishment, dict)
    assert isinstance(point, dict)
    other_company, other_branch = await _second_company(user_id)
    other = {**headers, "X-Company-ID": str(other_company)}

    assert (await e2e_client.get(f"{BASE}/establishments", headers=other)).json() == []
    assert (await e2e_client.get(f"{BASE}/activities", headers=other)).json() == []
    foreign = await e2e_client.get(f"{BASE}/establishments/{establishment['id']}", headers=other)
    assert foreign.status_code == 404
    foreign_point = await e2e_client.patch(
        f"{BASE}/points-of-sale/{point['id']}",
        json={"code": "P009", "name": "Ajena", "is_active": False},
        headers=other,
    )
    assert foreign_point.status_code == 404
    # Cada emisor numera por su cuenta: la otra empresa puede usar M001 y P001.
    activity = await e2e_client.post(f"{BASE}/activities", json={"code": "47215"}, headers=other)
    assert activity.status_code == 201, activity.text
    created = await e2e_client.post(
        f"{BASE}/establishments",
        json={"branch_id": str(other_branch), "establishment_type": "02", "code": "M001"},
        headers=other,
    )
    assert created.status_code == 201, created.text
    assert (await e2e_client.get(f"{BASE}/profile", headers=other)).json()["configured"] is False


async def test_settings_require_fiscal_permissions(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=False)
    for method, path in (
        ("GET", "/profile"),
        ("GET", "/establishments"),
        ("PUT", "/document-types/01"),
        ("GET", "/catalogs"),
    ):
        response = await e2e_client.request(
            method,
            f"{BASE}{path}",
            json={"is_enabled": True, "certification_status": "pending"}
            if method == "PUT"
            else None,
            headers=headers,
        )
        assert response.status_code == 403, (path, response.text)

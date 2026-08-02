"""E2E security checks for operational branch isolation."""

from __future__ import annotations

import uuid

import pytest

from tests.e2e.conftest import seed_user

pytestmark = pytest.mark.e2e


async def _company_with_multiple_branches() -> uuid.UUID:
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.organization import Branch, Company
    from sqlalchemy import func, select

    async with async_session_factory() as session:
        return (
            await session.execute(
                select(Company.id)
                .join(Branch, Branch.company_id == Company.id)
                .where(Company.is_active.is_(True), Branch.is_active.is_(True))
                .group_by(Company.id)
                .having(func.count(Branch.id) >= 2)
                .limit(1)
            )
        ).scalar_one()


async def _login_superadmin(e2e_client) -> dict[str, str]:
    await seed_user(
        username="superadmin",
        email="superadmin@erp-system.dev",
        password="Cambio!Seguro2026",
        is_superuser=True,
    )
    response = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": "superadmin", "password": "Cambio!Seguro2026"},
    )
    company_id = await _company_with_multiple_branches()
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def test_restricted_user_cannot_cross_branch_boundary(e2e_client) -> None:
    admin_headers = await _login_superadmin(e2e_client)
    company_id = admin_headers["X-Company-ID"]
    branches_response = await e2e_client.get(
        f"/api/v1/branches?company_id={company_id}", headers=admin_headers
    )
    assert branches_response.status_code == 200
    branches = branches_response.json()
    assert len(branches) >= 2
    allowed_branch_id = branches[0]["id"]
    forbidden_branch_id = branches[1]["id"]

    roles_response = await e2e_client.get("/api/v1/roles/catalogue", headers=admin_headers)
    administrator = next(
        role for role in roles_response.json() if role["name"] == "ADMINISTRADOR"
    )
    suffix = uuid.uuid4().hex[:8]
    created_user = await e2e_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "company_id": company_id,
            "username": f"branch-{suffix}",
            "email": f"branch-{suffix}@example.com",
            "password": "Branch!Scope2026",
            "role_ids": [administrator["id"]],
        },
    )
    assert created_user.status_code == 201, created_user.text

    access_response = await e2e_client.put(
        f"/api/v1/users/{created_user.json()['id']}/companies/{company_id}/branch-access",
        headers=admin_headers,
        json={
            "access_all_branches": False,
            "branch_ids": [allowed_branch_id],
            "default_branch_id": allowed_branch_id,
        },
    )
    assert access_response.status_code == 200, access_response.text

    login_response = await e2e_client.post(
        "/api/v1/auth/login",
        json={"login": f"branch-{suffix}", "password": "Branch!Scope2026"},
    )
    restricted_headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}",
        "X-Company-ID": company_id,
        "X-Branch-ID": allowed_branch_id,
    }
    allowed = await e2e_client.get(
        f"/api/v1/dashboard/summary?company_id={company_id}&branch_id={allowed_branch_id}",
        headers=restricted_headers,
    )
    assert allowed.status_code == 200
    assert len(allowed.json()["activity_series"]) == 90
    assert 0 <= allowed.json()["onboarding_progress"] <= 100
    assert isinstance(allowed.json()["team"], list)
    assert isinstance(allowed.json()["recent_users"], list)

    forbidden_headers = {**restricted_headers, "X-Branch-ID": forbidden_branch_id}
    forbidden_read = await e2e_client.get(
        f"/api/v1/employees?company_id={company_id}&branch_id={forbidden_branch_id}",
        headers=forbidden_headers,
    )
    assert forbidden_read.status_code == 403

    forbidden_write = await e2e_client.post(
        "/api/v1/employees",
        headers=forbidden_headers,
        json={
            "company_id": company_id,
            "employee_code": f"DENY-{suffix}",
            "first_name": "Acceso",
            "last_name": "Denegado",
        },
    )
    assert forbidden_write.status_code == 403

    forbidden_global_scope = await e2e_client.get(
        f"/api/v1/dashboard/summary?company_id={company_id}",
        headers={
            "Authorization": restricted_headers["Authorization"],
            "X-Company-ID": company_id,
        },
    )
    assert forbidden_global_scope.status_code == 403

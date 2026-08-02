"""E2E checks for company-scoped warehouse categories."""

from __future__ import annotations

import uuid

import pytest

from tests.e2e.conftest import seed_user

pytestmark = pytest.mark.e2e


async def _login(e2e_client, username: str, password: str) -> str:
    response = await e2e_client.post(
        "/api/v1/auth/login", json={"login": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_categories_are_isolated_by_company_and_reject_cross_assignment(
    e2e_client,
) -> None:
    password = "Category!Scope2026"
    await seed_user(
        username="category-admin",
        email="category-admin@example.com",
        password=password,
        is_superuser=True,
    )
    token = await _login(e2e_client, "category-admin", password)
    auth = {"Authorization": f"Bearer {token}"}
    companies_response = await e2e_client.get("/api/v1/companies", headers=auth)
    assert companies_response.status_code == 200, companies_response.text
    companies = companies_response.json()
    assert len(companies) >= 2
    first_company_id = companies[0]["id"]
    second_company_id = companies[1]["id"]
    category_name = f"Aislamiento {uuid.uuid4().hex[:10]}"
    created_ids: list[str] = []

    try:
        for company_id in (first_company_id, second_company_id):
            response = await e2e_client.post(
                "/api/v1/warehouse-categories",
                headers={**auth, "X-Company-ID": company_id},
                json={"company_id": company_id, "name": category_name},
            )
            assert response.status_code == 201, response.text
            created_ids.append(response.json()["id"])

        first_list = await e2e_client.get(
            f"/api/v1/warehouse-categories?company_id={first_company_id}&size=1&search=Aislamiento",
            headers={**auth, "X-Company-ID": first_company_id},
        )
        second_list = await e2e_client.get(
            f"/api/v1/warehouse-categories?company_id={second_company_id}&size=1&search=Aislamiento",
            headers={**auth, "X-Company-ID": second_company_id},
        )
        first_body = first_list.json()
        second_body = second_list.json()
        assert first_body["meta"]["size"] == 1
        assert second_body["meta"]["size"] == 1
        assert [item["id"] for item in first_body["items"] if item["name"] == category_name] == [created_ids[0]]
        assert [item["id"] for item in second_body["items"] if item["name"] == category_name] == [created_ids[1]]

        branches = await e2e_client.get(
            f"/api/v1/branches?company_id={first_company_id}",
            headers={**auth, "X-Company-ID": first_company_id},
        )
        assert branches.status_code == 200, branches.text
        assert branches.json()
        warehouse_page = await e2e_client.get(
            f"/api/v1/warehouses?company_id={first_company_id}&page=1&size=1",
            headers={**auth, "X-Company-ID": first_company_id},
        )
        assert warehouse_page.status_code == 200, warehouse_page.text
        warehouse_body = warehouse_page.json()
        assert warehouse_body["meta"]["page"] == 1
        assert warehouse_body["meta"]["size"] == 1
        assert "summary" in warehouse_body
        assert "status_counts" in warehouse_body["summary"]
        rejected = await e2e_client.post(
            "/api/v1/warehouses",
            headers={**auth, "X-Company-ID": first_company_id},
            json={
                "branch_id": branches.json()[0]["id"],
                "warehouse_category_id": created_ids[1],
                "code": f"X-{uuid.uuid4().hex[:8]}",
                "name": "Almacén inválido entre empresas",
            },
        )
        assert rejected.status_code == 409
        assert "otra empresa" in rejected.json()["detail"]
    finally:
        from app.infrastructure.db.session import async_session_factory
        from app.infrastructure.models.organization import WarehouseCategory
        from sqlalchemy import delete

        async with async_session_factory() as session:
            await session.execute(
                delete(WarehouseCategory).where(WarehouseCategory.id.in_(created_ids))
            )
            await session.commit()


async def test_user_cannot_list_categories_from_an_unassigned_company(e2e_client) -> None:
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.organization import Company, UserCompany
    from sqlalchemy import select

    password = "Category!Denied2026"
    user_id = await seed_user(
        username="category-limited",
        email="category-limited@example.com",
        password=password,
    )
    token = await _login(e2e_client, "category-limited", password)
    async with async_session_factory() as session:
        assigned_id = (
            await session.execute(
                select(UserCompany.company_id).where(UserCompany.user_id == uuid.UUID(user_id))
            )
        ).scalar_one()
        forbidden_id = (
            await session.execute(
                select(Company.id).where(Company.id != assigned_id).limit(1)
            )
        ).scalar_one()

    response = await e2e_client.get(
        f"/api/v1/warehouse-categories?company_id={forbidden_id}",
        headers={"Authorization": f"Bearer {token}", "X-Company-ID": str(forbidden_id)},
    )
    assert response.status_code == 403

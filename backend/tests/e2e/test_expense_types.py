from __future__ import annotations

import uuid

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.purchase_quotation import ExpenseTypeModel
from httpx import AsyncClient
from sqlalchemy import delete

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


async def _headers(
    client: AsyncClient,
    *,
    company_id: uuid.UUID,
    username: str,
    is_superuser: bool,
) -> dict[str, str]:
    await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=is_superuser,
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"login": username, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    return {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def test_expense_types_lists_only_active_company_options(
    e2e_client: AsyncClient,
) -> None:
    async with async_session_factory() as session:
        company_id = await get_test_company_id(session=session)
        suffix = uuid.uuid4().hex[:8]
        active = ExpenseTypeModel(
            id=uuid.uuid4(),
            company_id=company_id,
            name=f"E2E Active Expense {suffix}",
            description="Visible para órdenes de compra.",
            is_active=True,
        )
        inactive = ExpenseTypeModel(
            id=uuid.uuid4(),
            company_id=company_id,
            name=f"E2E Inactive Expense {suffix}",
            description="No debe aparecer.",
            is_active=False,
        )
        session.add_all([active, inactive])
        await session.commit()
        active_id = active.id
        inactive_id = inactive.id

    headers = await _headers(
        e2e_client,
        company_id=company_id,
        username=f"expense-types-admin-{suffix}",
        is_superuser=True,
    )
    try:
        response = await e2e_client.get("/api/v1/expense-types", headers=headers)
        assert response.status_code == 200, response.text
        items = response.json()
        by_id = {item["id"]: item for item in items}
        assert by_id[str(active_id)] == {
            "id": str(active_id),
            "name": f"E2E Active Expense {suffix}",
            "description": "Visible para órdenes de compra.",
        }
        assert str(inactive_id) not in by_id
        assert all("company_id" not in item and "is_active" not in item for item in items)
    finally:
        async with async_session_factory() as session:
            await session.execute(
                delete(ExpenseTypeModel).where(
                    ExpenseTypeModel.id.in_([active_id, inactive_id])
                )
            )
            await session.commit()


async def test_expense_types_requires_purchase_order_read_permission(
    e2e_client: AsyncClient,
) -> None:
    async with async_session_factory() as session:
        company_id = await get_test_company_id(session=session)

    headers = await _headers(
        e2e_client,
        company_id=company_id,
        username=f"expense-types-no-role-{uuid.uuid4().hex[:8]}",
        is_superuser=False,
    )
    response = await e2e_client.get("/api/v1/expense-types", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"

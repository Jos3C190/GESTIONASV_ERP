from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.purchase_request import PurchaseRequestModel
from httpx import AsyncClient
from sqlalchemy import and_, delete, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


@pytest.fixture
async def purchase_client(e2e_client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Clean purchase rows before the shared E2E fixture deletes their users."""
    try:
        yield e2e_client
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(PurchaseRequestModel))
            await session.commit()


async def _reference_ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, int]:
    async with async_session_factory() as session:
        company_id = await get_test_company_id(session=session)
        branch_id, warehouse_id = (
            await session.execute(
                select(Branch.id, Warehouse.id)
                .join(Warehouse, Warehouse.branch_id == Branch.id)
                .where(
                    Branch.company_id == company_id,
                    Branch.deleted_at.is_(None),
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Warehouse.deleted_at.is_(None),
                    Warehouse.is_active.is_(True),
                    Warehouse.operational_status == "active",
                )
                .limit(1)
            )
        ).one()
        product_id = (
            await session.execute(
                select(ProductModel.id_product)
                .join(
                    CompanyUnitModel,
                    and_(
                        CompanyUnitModel.company_id == ProductModel.company_id,
                        CompanyUnitModel.unit_id == ProductModel.purchase_unit,
                    ),
                )
                .where(
                    ProductModel.company_id == company_id,
                    ProductModel.deleted_at.is_(None),
                    ProductModel.is_active.is_(True),
                    ProductModel.lifecycle_status == "active",
                    ProductModel.can_purchase.is_(True),
                    CompanyUnitModel.is_enabled.is_(True),
                )
                .limit(1)
            )
        ).scalar_one()
    return company_id, branch_id, warehouse_id, product_id


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


def _create_payload(
    *,
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: int,
    quantity: str = "2.000000",
) -> dict[str, object]:
    return {
        "branch_id": str(branch_id),
        "warehouse_id": str(warehouse_id),
        "justification": "Reposición para prueba E2E de compras",
        "notes": "Flujo de validación",
        "details": [
            {
                "product_id": product_id,
                "quantity": quantity,
                "description": "Materia prima",
            }
        ],
    }


async def test_purchase_request_crud_workflow_and_audit(purchase_client: AsyncClient) -> None:
    company_id, branch_id, warehouse_id, product_id = await _reference_ids()
    headers = await _headers(
        purchase_client,
        company_id=company_id,
        username="purchase-admin",
        is_superuser=True,
    )

    created_response = await purchase_client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json=_create_payload(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
        ),
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    request_id = created["id"]
    assert created["status"] == "draft"
    assert created["code"].startswith("SCR-")
    assert created["details"][0]["product_id"] == product_id
    assert created["details"][0]["unit_id"] > 0

    listed = await purchase_client.get(
        "/api/v1/purchase-requests",
        headers=headers,
        params={"branch_id": str(branch_id)},
    )
    assert listed.status_code == 200, listed.text
    assert request_id in {item["id"] for item in listed.json()["items"]}

    fetched = await purchase_client.get(
        f"/api/v1/purchase-requests/{request_id}",
        headers=headers,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == request_id

    update_payload = _create_payload(
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity="3.500000",
    )
    update_payload["justification"] = "Cantidad corregida para reposición"
    updated_response = await purchase_client.put(
        f"/api/v1/purchase-requests/{request_id}",
        headers=headers,
        json=update_payload,
    )
    assert updated_response.status_code == 200, updated_response.text
    updated = updated_response.json()
    assert updated["justification"] == "Cantidad corregida para reposición"
    assert Decimal(updated["details"][0]["quantity"]) == Decimal("3.500000")

    submitted = await purchase_client.post(
        f"/api/v1/purchase-requests/{request_id}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    approved = await purchase_client.post(
        f"/api/v1/purchase-requests/{request_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    audit = await purchase_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "company_id": str(company_id),
            "resource_type": "purchase_requests",
            "resource_id": request_id,
            "size": 50,
        },
    )
    assert audit.status_code == 200, audit.text
    actions = {item["action"] for item in audit.json()["items"]}
    assert {"CREATE", "UPDATE", "SUBMIT", "APPROVE"}.issubset(actions)


async def test_purchase_request_requires_rbac_permission(purchase_client: AsyncClient) -> None:
    company_id, _branch_id, _warehouse_id, _product_id = await _reference_ids()
    headers = await _headers(
        purchase_client,
        company_id=company_id,
        username="purchase-no-role",
        is_superuser=False,
    )

    response = await purchase_client.get("/api/v1/purchase-requests", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_purchase_request_invalid_transition_returns_422(
    purchase_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id = await _reference_ids()
    headers = await _headers(
        purchase_client,
        company_id=company_id,
        username="purchase-transition",
        is_superuser=True,
    )
    created = await purchase_client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json=_create_payload(
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
        ),
    )
    assert created.status_code == 201, created.text

    response = await purchase_client.post(
        f"/api/v1/purchase-requests/{created.json()['id']}/approve",
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "purchase_request_invalid_transition"


async def test_purchase_request_duplicate_product_returns_422(
    purchase_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id = await _reference_ids()
    headers = await _headers(
        purchase_client,
        company_id=company_id,
        username="purchase-duplicate",
        is_superuser=True,
    )
    payload = _create_payload(
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    payload["details"] = [
        {"product_id": product_id, "quantity": "1"},
        {"product_id": product_id, "quantity": "2"},
    ]

    response = await purchase_client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "purchase_request_duplicate_product"

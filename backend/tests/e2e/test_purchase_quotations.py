from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.purchase_quotation import PurchaseQuotationModel
from app.infrastructure.models.purchase_request import PurchaseRequestModel
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.supplier_master_data import CurrencyModel
from httpx import AsyncClient
from sqlalchemy import and_, delete, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


@pytest.fixture
async def quotation_client(e2e_client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Clean procurement rows before the shared E2E fixture deletes users."""
    try:
        yield e2e_client
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(PurchaseQuotationModel))
            await session.execute(delete(PurchaseRequestModel))
            await session.commit()


async def _reference_ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, int, int, str]:
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
        supplier_id = await session.scalar(
            select(SupplierModel.id_supplier)
            .where(
                SupplierModel.company_id == company_id,
                SupplierModel.deleted_at.is_(None),
                SupplierModel.is_active.is_(True),
                SupplierModel.supplier_status == "approved",
            )
            .limit(1)
        )
        currency = await session.scalar(
            select(CurrencyModel.code)
            .where(CurrencyModel.is_active.is_(True))
            .order_by(CurrencyModel.code)
            .limit(1)
        )
        assert supplier_id is not None
        assert currency is not None
    return company_id, branch_id, warehouse_id, product_id, supplier_id, currency


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


async def _approved_purchase_request(
    client: AsyncClient,
    *,
    headers: dict[str, str],
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: int,
) -> dict[str, object]:
    created = await client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json={
            "branch_id": str(branch_id),
            "warehouse_id": str(warehouse_id),
            "justification": "Compra para comparar proveedores",
            "details": [{"product_id": product_id, "quantity": "4.000000"}],
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    submitted = await client.post(
        f"/api/v1/purchase-requests/{request_id}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    approved = await client.post(
        f"/api/v1/purchase-requests/{request_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def _quotation_payload(
    *,
    supplier_id: int,
    currency: str,
    purchase_request: dict[str, object],
) -> dict[str, object]:
    details = purchase_request["details"]
    assert isinstance(details, list)
    detail = details[0]
    assert isinstance(detail, dict)
    return {
        "supplier_id": supplier_id,
        "currency": currency,
        "requests": [
            {
                "purchase_request_id": purchase_request["id"],
                "lines": [
                    {
                        "purchase_request_detail_id": detail["id"],
                        "quantity": detail["quantity"],
                    }
                ],
            }
        ],
    }


async def test_purchase_quotation_workflow_comparison_and_audit(
    quotation_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        quotation_client,
        company_id=company_id,
        username="quotation-admin",
        is_superuser=True,
    )
    purchase_request = await _approved_purchase_request(
        quotation_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )

    created_response = await quotation_client.post(
        "/api/v1/purchase-quotations",
        headers=headers,
        json=_quotation_payload(
            supplier_id=supplier_id,
            currency=currency,
            purchase_request=purchase_request,
        ),
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    quotation_id = created["id"]
    assert created["status"] == "draft"
    assert created["code"].startswith("COT-")
    assert len(created["details"]) == 1
    trace = created["request_links"][0]["details"][0]
    assert trace["purchase_quotation_detail_id"] == created["details"][0]["id"]
    draft_detail_id = created["details"][0]["id"]

    listed = await quotation_client.get("/api/v1/purchase-quotations", headers=headers)
    assert listed.status_code == 200, listed.text
    assert quotation_id in {item["id"] for item in listed.json()["items"]}

    sent = await quotation_client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/send",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "requested"

    request_detail = purchase_request["details"][0]
    response = await quotation_client.put(
        f"/api/v1/purchase-quotations/{quotation_id}/response",
        headers=headers,
        json={
            "quotation_date": datetime.now(UTC).isoformat(),
            "payment_terms": "30 días crédito",
            "delivery_days": 3,
            "lines": [
                {
                    "product_id": request_detail["product_id"],
                    "unit_id": request_detail["unit_id"],
                    "quantity": request_detail["quantity"],
                    "unit_price": "12.500000",
                    "tax_rate": "13",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    received = response.json()
    assert received["status"] == "received"
    assert Decimal(received["total"]) > Decimal("0")
    assert received["details"][0]["id"] == draft_detail_id

    request_after_quote = await quotation_client.get(
        f"/api/v1/purchase-requests/{purchase_request['id']}",
        headers=headers,
    )
    assert request_after_quote.status_code == 200, request_after_quote.text
    assert request_after_quote.json()["status"] == "quoted"

    comparison = await quotation_client.get(
        f"/api/v1/purchase-quotations/comparison/{purchase_request['id']}",
        headers=headers,
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()[0]["quotation_id"] == quotation_id

    evaluated = await quotation_client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/evaluate",
        headers=headers,
    )
    assert evaluated.status_code == 200, evaluated.text
    assert evaluated.json()["status"] == "under_evaluation"

    selected = await quotation_client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/select",
        headers=headers,
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["status"] == "selected"

    audit = await quotation_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "company_id": str(company_id),
            "resource_type": "purchase_quotations",
            "resource_id": quotation_id,
            "size": 50,
        },
    )
    assert audit.status_code == 200, audit.text
    actions = {item["action"] for item in audit.json()["items"]}
    assert {"CREATE", "SEND", "RECEIVE", "EVALUATE", "SELECT"}.issubset(actions)


async def test_purchase_quotation_requires_rbac_permission(
    quotation_client: AsyncClient,
) -> None:
    (
        company_id,
        _branch_id,
        _warehouse_id,
        _product_id,
        _supplier_id,
        _currency,
    ) = await _reference_ids()
    headers = await _headers(
        quotation_client,
        company_id=company_id,
        username="quotation-no-role",
        is_superuser=False,
    )

    response = await quotation_client.get("/api/v1/purchase-quotations", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_purchase_quotation_invalid_transition_returns_422(
    quotation_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        quotation_client,
        company_id=company_id,
        username="quotation-transition",
        is_superuser=True,
    )
    purchase_request = await _approved_purchase_request(
        quotation_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    created = await quotation_client.post(
        "/api/v1/purchase-quotations",
        headers=headers,
        json=_quotation_payload(
            supplier_id=supplier_id,
            currency=currency,
            purchase_request=purchase_request,
        ),
    )
    assert created.status_code == 201, created.text

    response = await quotation_client.post(
        f"/api/v1/purchase-quotations/{created.json()['id']}/select",
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "purchase_quotation_invalid_transition"


async def test_purchase_quotation_rejects_response_quantity_above_scope(
    quotation_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        quotation_client,
        company_id=company_id,
        username="quotation-scope",
        is_superuser=True,
    )
    purchase_request = await _approved_purchase_request(
        quotation_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    created = await quotation_client.post(
        "/api/v1/purchase-quotations",
        headers=headers,
        json=_quotation_payload(
            supplier_id=supplier_id,
            currency=currency,
            purchase_request=purchase_request,
        ),
    )
    assert created.status_code == 201, created.text
    quotation_id = created.json()["id"]
    sent = await quotation_client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/send",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text

    request_detail = purchase_request["details"][0]
    response = await quotation_client.put(
        f"/api/v1/purchase-quotations/{quotation_id}/response",
        headers=headers,
        json={
            "quotation_date": datetime.now(UTC).isoformat(),
            "lines": [
                {
                    "product_id": request_detail["product_id"],
                    "unit_id": request_detail["unit_id"],
                    "quantity": "99.000000",
                    "unit_price": "1.000000",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "purchase_quotation_response_quantity_exceeded"

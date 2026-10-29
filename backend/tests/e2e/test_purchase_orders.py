from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.api.v1.deps import get_malware_scanner, get_object_storage
from app.core.config import settings
from app.domain.ports.malware_scanner import ScanResult
from app.domain.ports.object_storage import PresignedUpload, StoredObjectInfo
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import InventoryItemModel, InventoryMovementModel
from app.infrastructure.models.organization import Branch, Location, Warehouse, WarehouseCategory
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.purchase_quotation import (
    ExpenseTypeModel,
)
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.supplier_master_data import CurrencyModel
from httpx import AsyncClient
from sqlalchemy import and_, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


@pytest.fixture
async def purchase_order_client(e2e_client: AsyncClient) -> AsyncClient:
    """Alias for the API client; the disposable database resets per test."""
    return e2e_client


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
                    Warehouse.storage_eligible.is_(True),
                )
                .limit(1)
            )
        ).one()
        products = (
            await session.execute(
                select(ProductModel.id_product, ProductModel.purchase_unit)
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
                .order_by(ProductModel.id_product)
            )
        ).all()
        product_id = None
        for candidate_id, purchase_unit_id in products:
            item = await session.scalar(
                select(InventoryItemModel).where(
                    InventoryItemModel.company_id == company_id,
                    InventoryItemModel.product_id == candidate_id,
                )
            )
            if item is None:
                # The catalog seed intentionally has no operational stock.
                # Create only the inventory identity needed by receipt E2E
                # tests, using the product's purchase unit as its base unit.
                session.add(
                    InventoryItemModel(
                        company_id=company_id,
                        product_id=candidate_id,
                        variant_id=None,
                        base_unit_id=purchase_unit_id,
                        is_active=True,
                    )
                )
                await session.commit()
                product_id = candidate_id
                break
            if item.base_unit_id == purchase_unit_id and item.is_active:
                product_id = candidate_id
                break
        assert product_id is not None, "El seed E2E necesita un producto con unidad base compatible."
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


async def _receiving_location_id(warehouse_id: uuid.UUID) -> uuid.UUID:
    """Return an active receiving point in the exact warehouse under test."""
    async with async_session_factory() as session:
        location_id = await session.scalar(
            select(Location.id)
            .where(
                Location.warehouse_id == warehouse_id,
                Location.location_type == "receiving",
                Location.is_active.is_(True),
                Location.lifecycle_status == "active",
                Location.deleted_at.is_(None),
            )
            .order_by(Location.created_at, Location.id)
            .limit(1)
        )
    assert location_id is not None, "El almacén de prueba necesita un punto de recepción activo."
    return location_id


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
    quantity: str = "4.000000",
) -> dict[str, object]:
    created = await client.post(
        "/api/v1/purchase-requests",
        headers=headers,
        json={
            "branch_id": str(branch_id),
            "warehouse_id": str(warehouse_id),
            "justification": "Compra para validar órdenes",
            "details": [{"product_id": product_id, "quantity": quantity}],
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


async def _selected_quotation(
    client: AsyncClient,
    *,
    headers: dict[str, str],
    purchase_request: dict[str, object],
    supplier_id: int,
    currency: str,
) -> dict[str, object]:
    request_details = purchase_request["details"]
    assert isinstance(request_details, list)
    request_detail = request_details[0]
    assert isinstance(request_detail, dict)

    created = await client.post(
        "/api/v1/purchase-quotations",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "currency": currency,
            "requests": [
                {
                    "purchase_request_id": purchase_request["id"],
                    "lines": [
                        {
                            "purchase_request_detail_id": request_detail["id"],
                            "quantity": request_detail["quantity"],
                        }
                    ],
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    quotation_id = created.json()["id"]

    sent = await client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/send",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text

    responded = await client.put(
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
                    "available_quantity": request_detail["quantity"],
                    "unit_price": "12.500000",
                    "tax_rate": "13",
                }
            ],
        },
    )
    assert responded.status_code == 200, responded.text

    selected = await client.post(
        f"/api/v1/purchase-quotations/{quotation_id}/select",
        headers=headers,
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["status"] == "selected"
    return selected.json()


def _order_payload(
    *,
    quotation: dict[str, object],
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    quantity: str,
    notes: str,
) -> dict[str, object]:
    details = quotation["details"]
    assert isinstance(details, list)
    detail = details[0]
    assert isinstance(detail, dict)
    return {
        "purchase_quotation_id": quotation["id"],
        "branch_id": str(branch_id),
        "warehouse_id": str(warehouse_id),
        "expected_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        "lines": [
            {
                "purchase_quotation_detail_id": detail["id"],
                "quantity": quantity,
            }
        ],
        "notes": notes,
    }


async def test_purchase_order_workflow_request_status_and_audit(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-admin",
        is_superuser=True,
    )
    purchase_request = await _approved_purchase_request(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    quotation = await _selected_quotation(
        purchase_order_client,
        headers=headers,
        purchase_request=purchase_request,
        supplier_id=supplier_id,
        currency=currency,
    )

    created_response = await purchase_order_client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json=_order_payload(
            quotation=quotation,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            quantity="2.000000",
            notes="Primer borrador",
        ),
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    order_id = created["id"]
    assert created["status"] == "draft"
    assert created["code"].startswith("OC-")
    assert created["supplier_id"] == supplier_id
    assert created["currency"] == currency
    assert created["payment_terms"] == "30 días crédito"
    assert Decimal(created["additional_expenses"]) == Decimal("0")

    listed = await purchase_order_client.get("/api/v1/purchase-orders", headers=headers)
    assert listed.status_code == 200, listed.text
    assert order_id in {item["id"] for item in listed.json()["items"]}

    fetched = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}",
        headers=headers,
    )
    assert fetched.status_code == 200, fetched.text
    fetched_order = fetched.json()
    assert fetched_order["purchase_quotation_id"] == quotation["id"]
    fetched_details = fetched_order["details"]
    assert isinstance(fetched_details, list)
    fetched_detail = fetched_details[0]
    assert isinstance(fetched_detail, dict)
    source_detail_id = fetched_detail["purchase_quotation_detail_id"]
    assert source_detail_id == quotation["details"][0]["id"]

    update_payload = {
        "branch_id": fetched_order["branch_id"],
        "warehouse_id": fetched_order["warehouse_id"],
        "expected_date": fetched_order["expected_date"],
        "lines": [
            {
                "purchase_quotation_detail_id": source_detail_id,
                "quantity": "4.000000",
            }
        ],
        "notes": "Cantidad final",
    }
    updated = await purchase_order_client.put(
        f"/api/v1/purchase-orders/{order_id}",
        headers=headers,
        json=update_payload,
    )
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["details"][0]["quantity"]) == Decimal("4")
    assert updated.json()["notes"] == "Cantidad final"

    submitted = await purchase_order_client.post(
        f"/api/v1/purchase-orders/{order_id}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "pending_approval"

    approved = await purchase_order_client.post(
        f"/api/v1/purchase-orders/{order_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    sent = await purchase_order_client.post(
        f"/api/v1/purchase-orders/{order_id}/send",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"

    request_after_order = await purchase_order_client.get(
        f"/api/v1/purchase-requests/{purchase_request['id']}",
        headers=headers,
    )
    assert request_after_order.status_code == 200, request_after_order.text
    assert request_after_order.json()["status"] == "completed"

    audit = await purchase_order_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "company_id": str(company_id),
            "resource_type": "purchase_orders",
            "resource_id": order_id,
            "size": 50,
        },
    )
    assert audit.status_code == 200, audit.text
    audit_items = audit.json()["items"]
    actions = {item["action"] for item in audit_items}
    assert {"CREATE", "UPDATE", "SUBMIT", "APPROVE", "SEND"}.issubset(actions)
    update_audit = next(item for item in audit_items if item["action"] == "UPDATE")
    assert (
        update_audit["after_state"]["details"][0]["purchase_quotation_detail_id"]
        == source_detail_id
    )


async def test_purchase_order_requires_rbac_permission(
    purchase_order_client: AsyncClient,
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
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-no-role",
        is_superuser=False,
    )

    response = await purchase_order_client.get("/api/v1/purchase-orders", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_purchase_order_invalid_transition_returns_422(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-transition",
        is_superuser=True,
    )
    purchase_request = await _approved_purchase_request(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    quotation = await _selected_quotation(
        purchase_order_client,
        headers=headers,
        purchase_request=purchase_request,
        supplier_id=supplier_id,
        currency=currency,
    )
    created = await purchase_order_client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json=_order_payload(
            quotation=quotation,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            quantity="1.000000",
            notes="Transición inválida",
        ),
    )
    assert created.status_code == 201, created.text

    response = await purchase_order_client.post(
        f"/api/v1/purchase-orders/{created.json()['id']}/approve",
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "purchase_order_invalid_transition"


async def test_purchase_order_cancel_before_send_is_audited(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-cancel",
        is_superuser=True,
    )
    purchase_request = await _approved_purchase_request(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    quotation = await _selected_quotation(
        purchase_order_client,
        headers=headers,
        purchase_request=purchase_request,
        supplier_id=supplier_id,
        currency=currency,
    )
    created = await purchase_order_client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json=_order_payload(
            quotation=quotation,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            quantity="1.000000",
            notes="Cancelar antes de envío",
        ),
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]

    cancelled = await purchase_order_client.post(
        f"/api/v1/purchase-orders/{order_id}/cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    audit = await purchase_order_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "company_id": str(company_id),
            "resource_type": "purchase_orders",
            "resource_id": order_id,
            "size": 50,
        },
    )
    assert audit.status_code == 200, audit.text
    actions = {item["action"] for item in audit.json()["items"]}
    assert {"CREATE", "CANCEL"}.issubset(actions)


async def _sent_order(
    client: AsyncClient,
    *,
    headers: dict[str, str],
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: int,
    supplier_id: int,
    currency: str,
    quantity: str = "4.000000",
) -> dict[str, object]:
    purchase_request = await _approved_purchase_request(
        client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=quantity,
    )
    quotation = await _selected_quotation(
        client,
        headers=headers,
        purchase_request=purchase_request,
        supplier_id=supplier_id,
        currency=currency,
    )
    created = await client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json=_order_payload(
            quotation=quotation,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            notes="Orden para validar recepciones",
        ),
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]

    submitted = await client.post(
        f"/api/v1/purchase-orders/{order_id}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    approved = await client.post(
        f"/api/v1/purchase-orders/{order_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    sent = await client.post(
        f"/api/v1/purchase-orders/{order_id}/send",
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"
    return sent.json()


async def test_headquarters_user_can_read_new_central_receipt_without_global_scope(
    purchase_order_client: AsyncClient,
) -> None:
    from app.infrastructure.models.rbac import Permission, Role, RolePermission

    company_id, regular_branch_id, _, product_id, supplier_id, currency = await _reference_ids()
    admin_headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-headquarters-admin",
        is_superuser=True,
    )

    branches_response = await purchase_order_client.get(
        f"/api/v1/branches?company_id={company_id}", headers=admin_headers
    )
    assert branches_response.status_code == 200, branches_response.text
    headquarters = next(
        (item for item in branches_response.json() if item["is_headquarters"]), None
    )
    regular_branch_id = uuid.UUID(
        next(item["id"] for item in branches_response.json() if not item["is_headquarters"])
    )
    if headquarters is None:
        created_headquarters = await purchase_order_client.post(
            "/api/v1/branches",
            headers=admin_headers,
            json={
                "company_id": str(company_id),
                "is_headquarters": True,
                "name": "Matriz recepción prueba B01",
            },
        )
        assert created_headquarters.status_code == 201, created_headquarters.text
        headquarters = created_headquarters.json()
    headquarters_id = uuid.UUID(headquarters["id"])

    async with async_session_factory() as session:
        central_warehouse_id = await session.scalar(
            select(Warehouse.id)
            .where(
                Warehouse.company_id == company_id,
                Warehouse.branch_id == headquarters_id,
                Warehouse.is_central.is_(True),
                Warehouse.is_active.is_(True),
                Warehouse.operational_status == "active",
                Warehouse.deleted_at.is_(None),
            )
            .order_by(Warehouse.created_at, Warehouse.id)
            .limit(1)
        )
        category_id = await session.scalar(
            select(WarehouseCategory.id)
            .where(
                WarehouseCategory.company_id == company_id,
                WarehouseCategory.is_active.is_(True),
                WarehouseCategory.deleted_at.is_(None),
            )
            .order_by(WarehouseCategory.name)
            .limit(1)
        )
    if central_warehouse_id is None:
        assert category_id is not None
        created_central = await purchase_order_client.post(
            "/api/v1/warehouses",
            headers=admin_headers,
            json={
                "company_id": str(company_id),
                "branch_id": str(headquarters_id),
                "warehouse_category_id": str(category_id),
                "code": f"BM-B01-{uuid.uuid4().hex[:8]}",
                "name": f"Bodega central B01 {uuid.uuid4().hex[:6]}",
                "is_central": True,
            },
        )
        assert created_central.status_code == 201, created_central.text
        central_warehouse_id = uuid.UUID(created_central.json()["id"])

    async with async_session_factory() as session:
        receiving_location_id = await session.scalar(
            select(Location.id)
            .where(
                Location.warehouse_id == central_warehouse_id,
                Location.location_type == "receiving",
                Location.is_active.is_(True),
                Location.lifecycle_status == "active",
                Location.deleted_at.is_(None),
            )
            .order_by(Location.created_at, Location.id)
            .limit(1)
        )
        if receiving_location_id is None:
            receiving_location = Location(
                warehouse_id=central_warehouse_id,
                code=f"B01-REC-{uuid.uuid4().hex[:8]}",
                aisle="A",
                rack="R01",
                level="N01",
                position="P01",
                location_type="receiving",
                lifecycle_status="active",
            )
            session.add(receiving_location)
            await session.commit()
            receiving_location_id = receiving_location.id

    order = await _sent_order(
        purchase_order_client,
        headers=admin_headers,
        branch_id=headquarters_id,
        warehouse_id=central_warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
        quantity="2.000000",
    )
    order_detail = order["details"][0]
    purchase_response = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=admin_headers,
        json={
            "purchase_order_id": order["id"],
            "supplier_invoice_number": "FAC-B01-CENTRAL-001",
            "lines": [
                {
                    "purchase_order_detail_id": order_detail["id"],
                    "quantity_received": "2.000000",
                }
            ],
        },
    )
    assert purchase_response.status_code == 201, purchase_response.text
    purchase = purchase_response.json()
    assert purchase["branch_id"] == str(headquarters_id)
    assert purchase["warehouse_id"] == str(central_warehouse_id)

    username = f"hq-receipt-reader-{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as session:
        permission_ids = set(
            (
                await session.scalars(
                    select(Permission.id).where(
                        Permission.code.in_(
                            {
                                "purchases:read",
                                "purchases:receive",
                                "purchases:verify",
                                "inventory:receive",
                                "locations.view",
                            }
                        ),
                        Permission.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        assert len(permission_ids) == 5
        reader_role = Role(
            company_id=company_id,
            name=f"B01 Receipt Reader {uuid.uuid4().hex[:8]}",
            description="Receive, verify, and read receipts within headquarters scope E2E.",
        )
        session.add(reader_role)
        await session.flush()
        role_id = reader_role.id
        session.add_all(
            RolePermission(role_id=role_id, permission_id=permission_id)
            for permission_id in permission_ids
        )
        await session.commit()
    reader_created = await purchase_order_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "company_id": str(company_id),
            "username": username,
            "email": f"{username}@example.com",
            "password": "Headquarters!2026",
            "role_ids": [str(role_id)],
        },
    )
    assert reader_created.status_code == 201, reader_created.text
    access_updated = await purchase_order_client.put(
        f"/api/v1/users/{reader_created.json()['id']}/companies/{company_id}/branch-access",
        headers=admin_headers,
        json={
            "access_all_branches": False,
            "branch_ids": [str(headquarters_id)],
            "default_branch_id": str(headquarters_id),
        },
    )
    assert access_updated.status_code == 200, access_updated.text
    reader_login = await purchase_order_client.post(
        "/api/v1/auth/login",
        json={"login": username, "password": "Headquarters!2026"},
    )
    assert reader_login.status_code == 200, reader_login.text
    reader_headers = {
        "Authorization": f"Bearer {reader_login.json()['access_token']}",
        "X-Company-ID": str(company_id),
        "X-Branch-ID": str(headquarters_id),
    }

    received = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase['id']}/receive", headers=reader_headers
    )
    assert received.status_code == 200, received.text
    verified = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase['id']}/verify",
        headers=reader_headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": purchase["details"][0]["id"],
                    "quantity_accepted": "2.000000",
                    "inventory_location_id": str(receiving_location_id),
                }
            ]
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"

    read_receipt = await purchase_order_client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=reader_headers
    )
    assert read_receipt.status_code == 200, read_receipt.text
    assert read_receipt.json()["warehouse_id"] == str(central_warehouse_id)
    headquarters_receipts = await purchase_order_client.get(
        "/api/v1/purchases",
        params={"branch_id": str(headquarters_id)},
        headers=reader_headers,
    )
    assert headquarters_receipts.status_code == 200, headquarters_receipts.text
    assert purchase["id"] in {item["id"] for item in headquarters_receipts.json()["items"]}
    global_receipts = await purchase_order_client.get(
        "/api/v1/purchases", headers=reader_headers
    )
    assert global_receipts.status_code == 403, global_receipts.text
    other_branch_receipts = await purchase_order_client.get(
        "/api/v1/purchases",
        params={"branch_id": str(regular_branch_id)},
        headers=reader_headers,
    )
    assert other_branch_receipts.status_code == 403, other_branch_receipts.text

    # Reproduce a legacy central receipt without changing its historical branch field.
    async with async_session_factory() as session:
        historical_purchase = await session.get(PurchaseModel, uuid.UUID(purchase["id"]))
        assert historical_purchase is not None
        historical_purchase.branch_id = None
        await session.commit()

    headquarters_legacy_receipt = await purchase_order_client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=reader_headers
    )
    assert headquarters_legacy_receipt.status_code == 200, headquarters_legacy_receipt.text
    assert headquarters_legacy_receipt.json()["branch_id"] is None
    headquarters_legacy_list = await purchase_order_client.get(
        "/api/v1/purchases",
        params={"branch_id": str(headquarters_id)},
        headers=reader_headers,
    )
    assert headquarters_legacy_list.status_code == 200, headquarters_legacy_list.text
    assert purchase["id"] in {
        item["id"] for item in headquarters_legacy_list.json()["items"]
    }
    global_legacy_receipt = await purchase_order_client.get(
        f"/api/v1/purchases/{purchase['id']}", headers=admin_headers
    )
    assert global_legacy_receipt.status_code == 200, global_legacy_receipt.text
    global_legacy_list = await purchase_order_client.get(
        "/api/v1/purchases", headers=admin_headers
    )
    assert global_legacy_list.status_code == 200, global_legacy_list.text
    assert purchase["id"] in {item["id"] for item in global_legacy_list.json()["items"]}
    other_branch_legacy_list = await purchase_order_client.get(
        "/api/v1/purchases",
        params={"branch_id": str(regular_branch_id)},
        headers=reader_headers,
    )
    assert other_branch_legacy_list.status_code == 403, other_branch_legacy_list.text


async def test_purchase_draft_can_be_edited_and_saved_without_duplicate_detail(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-draft-edit-save",
        is_superuser=True,
    )
    order = await _sent_order(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    order_detail_id = order["details"][0]["id"]

    created = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "supplier_invoice_number": "FAC-DRAFT-001",
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
            "notes": "Borrador original",
        },
    )
    assert created.status_code == 201, created.text
    purchase = created.json()
    purchase_id = purchase["id"]
    detail_id = purchase["details"][0]["id"]

    updated = await purchase_order_client.put(
        f"/api/v1/purchases/{purchase_id}",
        headers=headers,
        json={
            "supplier_invoice_number": "FAC-DRAFT-001-EDITADA",
            "supplier_invoice_date": datetime.now(UTC).date().isoformat(),
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
            "notes": "Borrador editado y guardado",
        },
    )
    assert updated.status_code == 200, updated.text
    edited = updated.json()
    assert edited["supplier_invoice_number"] == "FAC-DRAFT-001-EDITADA"
    assert edited["notes"] == "Borrador editado y guardado"
    assert len(edited["details"]) == 1
    assert edited["details"][0]["id"] == detail_id

    persisted = await purchase_order_client.get(f"/api/v1/purchases/{purchase_id}", headers=headers)
    assert persisted.status_code == 200, persisted.text
    assert persisted.json()["details"][0]["id"] == detail_id


async def test_purchase_receiving_partial_then_complete_workflow_and_audit(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-receiving-workflow",
        is_superuser=True,
    )
    order = await _sent_order(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    order_id = order["id"]
    order_details = order["details"]
    assert isinstance(order_details, list)
    order_detail = order_details[0]
    assert isinstance(order_detail, dict)
    order_detail_id = order_detail["id"]

    receivable = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}/receivable",
        headers=headers,
    )
    assert receivable.status_code == 200, receivable.text
    first_line = receivable.json()["lines"][0]
    assert Decimal(first_line["quantity_ordered"]) == Decimal("4")
    assert Decimal(first_line["quantity_received"]) == Decimal("0")
    assert Decimal(first_line["quantity_pending"]) == Decimal("4")

    first = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order_id,
            "supplier_invoice_number": "FAC-E2E-001",
            "supplier_invoice_date": datetime.now(UTC).date().isoformat(),
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
            "notes": "Primera recepción parcial",
        },
    )
    assert first.status_code == 201, first.text
    first_purchase = first.json()
    first_purchase_id = first_purchase["id"]
    assert first_purchase["status"] == "draft"
    assert first_purchase["purchase_order_id"] == order_id
    assert first_purchase["branch_id"] == str(branch_id)
    assert first_purchase["warehouse_id"] == str(warehouse_id)
    assert first_purchase["details"][0]["purchase_order_detail_id"] == order_detail_id
    assert Decimal(first_purchase["subtotal"]) == Decimal("25")
    assert Decimal(first_purchase["tax"]) == Decimal("3.25")
    assert Decimal(first_purchase["total"]) == Decimal("28.25")

    received_first = await purchase_order_client.post(
        f"/api/v1/purchases/{first_purchase_id}/receive",
        headers=headers,
    )
    assert received_first.status_code == 200, received_first.text
    assert received_first.json()["status"] == "received"

    order_after_first = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}",
        headers=headers,
    )
    assert order_after_first.status_code == 200, order_after_first.text
    assert order_after_first.json()["status"] == "partially_received"

    receivable_after_first = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}/receivable",
        headers=headers,
    )
    assert receivable_after_first.status_code == 200, receivable_after_first.text
    line_after_first = receivable_after_first.json()["lines"][0]
    assert Decimal(line_after_first["quantity_received"]) == Decimal("2")
    assert Decimal(line_after_first["quantity_pending"]) == Decimal("2")

    immutable = await purchase_order_client.put(
        f"/api/v1/purchases/{first_purchase_id}",
        headers=headers,
        json={
            "supplier_invoice_number": "FAC-E2E-001",
            "supplier_invoice_date": datetime.now(UTC).date().isoformat(),
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
            "notes": "No debe poder modificarse",
        },
    )
    assert immutable.status_code == 422
    assert immutable.json()["code"] == "purchase_not_editable"

    verified = await purchase_order_client.post(
        f"/api/v1/purchases/{first_purchase_id}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": first_purchase["details"][0]["id"],
                    "quantity_accepted": "2.000000",
                    "inventory_location_id": str(await _receiving_location_id(warehouse_id)),
                }
            ]
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"

    closed = await purchase_order_client.post(
        f"/api/v1/purchases/{first_purchase_id}/close",
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    second = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order_id,
            "supplier_invoice_number": "FAC-E2E-002",
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
            "notes": "Recepción final",
        },
    )
    assert second.status_code == 201, second.text
    second_purchase_id = second.json()["id"]

    received_second = await purchase_order_client.post(
        f"/api/v1/purchases/{second_purchase_id}/receive",
        headers=headers,
    )
    assert received_second.status_code == 200, received_second.text

    completed_order = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}",
        headers=headers,
    )
    assert completed_order.status_code == 200, completed_order.text
    assert completed_order.json()["status"] == "received"

    listed = await purchase_order_client.get(
        "/api/v1/purchases",
        headers=headers,
        params={"branch_id": str(branch_id), "purchase_order_id": order_id},
    )
    assert listed.status_code == 200, listed.text
    listed_ids = {item["id"] for item in listed.json()["items"]}
    assert {first_purchase_id, second_purchase_id}.issubset(listed_ids)

    audit = await purchase_order_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "company_id": str(company_id),
            "branch_id": str(branch_id),
            "resource_type": "purchases",
            "resource_id": first_purchase_id,
            "size": 50,
        },
    )
    assert audit.status_code == 200, audit.text
    audit_items = audit.json()["items"]
    actions = {item["action"] for item in audit_items}
    assert {"CREATE", "RECEIVE", "VERIFY", "CLOSE"}.issubset(actions)
    assert all(item["branch_id"] == str(branch_id) for item in audit_items)


async def test_purchase_receiving_rechecks_stale_draft_and_prevents_over_receipt(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-receiving-stale-draft",
        is_superuser=True,
    )
    order = await _sent_order(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    order_id = order["id"]
    order_details = order["details"]
    assert isinstance(order_details, list)
    order_detail = order_details[0]
    assert isinstance(order_detail, dict)
    order_detail_id = order_detail["id"]

    draft_ids: list[str] = []
    for suffix in ("A", "B"):
        draft = await purchase_order_client.post(
            "/api/v1/purchases",
            headers=headers,
            json={
                "purchase_order_id": order_id,
                "supplier_invoice_number": f"FAC-STALE-{suffix}",
                "lines": [
                    {
                        "purchase_order_detail_id": order_detail_id,
                        "quantity_received": "3.000000",
                    }
                ],
            },
        )
        assert draft.status_code == 201, draft.text
        draft_ids.append(draft.json()["id"])

    first_received = await purchase_order_client.post(
        f"/api/v1/purchases/{draft_ids[0]}/receive",
        headers=headers,
    )
    assert first_received.status_code == 200, first_received.text

    stale_receive = await purchase_order_client.post(
        f"/api/v1/purchases/{draft_ids[1]}/receive",
        headers=headers,
    )
    assert stale_receive.status_code == 422
    assert stale_receive.json()["code"] == "purchase_quantity_exceeded"

    stale_after = await purchase_order_client.get(
        f"/api/v1/purchases/{draft_ids[1]}",
        headers=headers,
    )
    assert stale_after.status_code == 200, stale_after.text
    assert stale_after.json()["status"] == "draft"

    order_after = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}",
        headers=headers,
    )
    assert order_after.status_code == 200, order_after.text
    assert order_after.json()["status"] == "partially_received"

    receivable = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}/receivable",
        headers=headers,
    )
    assert receivable.status_code == 200, receivable.text
    line = receivable.json()["lines"][0]
    assert Decimal(line["quantity_received"]) == Decimal("3")
    assert Decimal(line["quantity_pending"]) == Decimal("1")


async def test_purchase_receiving_requires_rbac_permission(
    purchase_order_client: AsyncClient,
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
        purchase_order_client,
        company_id=company_id,
        username="purchase-receiving-no-role",
        is_superuser=False,
    )

    response = await purchase_order_client.get("/api/v1/purchases", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_rejected_receipt_stays_pending_and_creates_no_inventory_movement(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-rejected-receipt-e2e",
        is_superuser=True,
    )
    order = await _sent_order(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    order_id = order["id"]
    order_detail_id = order["details"][0]["id"]

    created = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order_id,
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    purchase_id = created.json()["id"]

    received = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase_id}/receive",
        headers=headers,
    )
    assert received.status_code == 200, received.text

    verified = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase_id}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": created.json()["details"][0]["id"],
                    "quantity_accepted": "0",
                    "inventory_location_id": None,
                }
            ]
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"
    assert verified.json()["inventory_movement_id"] is None
    assert Decimal(verified.json()["details"][0]["quantity_rejected"]) == Decimal("2")

    order_after = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}", headers=headers
    )
    assert order_after.status_code == 200, order_after.text
    assert order_after.json()["status"] == "sent"

    receivable = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}/receivable", headers=headers
    )
    assert receivable.status_code == 200, receivable.text
    assert Decimal(receivable.json()["lines"][0]["quantity_received"]) == Decimal("0")
    assert Decimal(receivable.json()["lines"][0]["quantity_pending"]) == Decimal("4")

    async with async_session_factory() as session:
        movement_id = await session.scalar(
            select(InventoryMovementModel.id).where(
                InventoryMovementModel.company_id == company_id,
                InventoryMovementModel.source_reference == f"purchase-receipt:{purchase_id}",
            )
        )
    assert movement_id is None


async def test_cross_warehouse_receipt_location_rolls_back_verification(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    async with async_session_factory() as session:
        foreign_location_id = await session.scalar(
            select(Location.id)
            .join(Warehouse, Warehouse.id == Location.warehouse_id)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .where(
                Branch.company_id == company_id,
                Location.warehouse_id != warehouse_id,
                Location.is_active.is_(True),
                Location.lifecycle_status == "active",
                Location.deleted_at.is_(None),
                Warehouse.is_active.is_(True),
                Warehouse.operational_status == "active",
                Warehouse.deleted_at.is_(None),
            )
            .limit(1)
        )
    assert foreign_location_id is not None

    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-cross-warehouse-location-e2e",
        is_superuser=True,
    )
    order = await _sent_order(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    order_id = order["id"]
    order_detail_id = order["details"][0]["id"]

    created = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order_id,
            "lines": [
                {
                    "purchase_order_detail_id": order_detail_id,
                    "quantity_received": "2.000000",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    purchase_id = created.json()["id"]
    purchase_detail_id = created.json()["details"][0]["id"]

    received = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase_id}/receive",
        headers=headers,
    )
    assert received.status_code == 200, received.text

    rejected = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase_id}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": purchase_detail_id,
                    "quantity_accepted": "1",
                    "inventory_location_id": str(foreign_location_id),
                }
            ]
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "purchase_receipt_location_invalid"

    purchase_after = await purchase_order_client.get(
        f"/api/v1/purchases/{purchase_id}", headers=headers
    )
    assert purchase_after.status_code == 200, purchase_after.text
    assert purchase_after.json()["status"] == "received"
    assert purchase_after.json()["details"][0]["quantity_accepted"] is None

    order_after = await purchase_order_client.get(
        f"/api/v1/purchase-orders/{order_id}", headers=headers
    )
    assert order_after.status_code == 200, order_after.text
    assert order_after.json()["status"] == "partially_received"

    async with async_session_factory() as session:
        movement_id = await session.scalar(
            select(InventoryMovementModel.id).where(
                InventoryMovementModel.company_id == company_id,
                InventoryMovementModel.source_reference == f"purchase-receipt:{purchase_id}",
            )
        )
    assert movement_id is None


async def test_retaceo_workflow_uses_purchase_details_and_audits(
    purchase_order_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="retaceo-workflow",
        is_superuser=True,
    )
    order = await _sent_order(
        purchase_order_client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
        quantity="2.000000",
    )
    order_details = order["details"]
    assert isinstance(order_details, list)
    order_detail = order_details[0]
    assert isinstance(order_detail, dict)

    purchase_response = await purchase_order_client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "purchase_order_id": order["id"],
            "supplier_invoice_number": "FAC-RET-001",
            "lines": [
                {
                    "purchase_order_detail_id": order_detail["id"],
                    "quantity_received": "2.000000",
                }
            ],
        },
    )
    assert purchase_response.status_code == 201, purchase_response.text
    purchase = purchase_response.json()
    purchase_id = purchase["id"]

    received = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase_id}/receive",
        headers=headers,
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received"

    verified = await purchase_order_client.post(
        f"/api/v1/purchases/{purchase_id}/verify",
        headers=headers,
        json={
            "lines": [
                {
                    "purchase_detail_id": purchase["details"][0]["id"],
                    "quantity_accepted": "2.000000",
                    "inventory_location_id": str(await _receiving_location_id(warehouse_id)),
                }
            ]
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"

    created = await purchase_order_client.post(
        "/api/v1/retaceos",
        headers=headers,
        json={
            "purchase_id": purchase_id,
            "total_freight": "5.000000",
            "total_expenses": "2.000000",
            "total_dai": "3.000000",
            "import_vat": "13.000000",
            "notes": "Retaceo E2E",
        },
    )
    assert created.status_code == 201, created.text
    retaceo = created.json()
    retaceo_id = retaceo["id"]
    purchase_detail = purchase["details"][0]
    expected_fob = Decimal(purchase_detail["subtotal"]) - Decimal(purchase_detail["discount"])

    assert retaceo["status"] == "draft"
    assert retaceo["purchase_id"] == purchase_id
    assert retaceo["branch_id"] == str(branch_id)
    assert retaceo["details"][0]["purchase_detail_id"] == purchase_detail["id"]
    assert Decimal(retaceo["total_fob"]) == expected_fob
    # Cost concepts start unallocated; only line-level allocations affect
    # landed unit costs. The UI requires this explicit distribution step.
    assert Decimal(retaceo["total_cost"]) == expected_fob
    assert Decimal(retaceo["import_vat"]) == Decimal("13")

    def allocated_costs(
        costs: list[dict[str, object]], *, freight_amount: str = "5.000000"
    ) -> list[dict[str, object]]:
        allocations: list[dict[str, object]] = []
        for cost in costs:
            classification = str(cost["classification"])
            amount = (
                freight_amount
                if classification == "freight"
                else str(cost["amount"])
            )
            allocations.append(
                {
                    "id": cost["id"],
                    "classification": classification,
                    "title": cost["title"],
                    "amount": amount,
                    "allocations": (
                        []
                        if classification == "import_vat"
                        else [
                            {
                                "purchase_detail_id": purchase_detail["id"],
                                "amount": amount,
                            }
                        ]
                    ),
                }
            )
        return allocations

    created_costs = retaceo["costs"]
    assert isinstance(created_costs, list)

    updated = await purchase_order_client.put(
        f"/api/v1/retaceos/{retaceo_id}",
        headers=headers,
        json={
            "total_freight": "5.000000",
            "total_expenses": "2.000000",
            "total_dai": "3.000000",
            "import_vat": "13.000000",
            "notes": "Retaceo con costos distribuidos",
            "costs": allocated_costs(created_costs),
        },
    )
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["total_cost"]) == expected_fob + Decimal("10")
    assert Decimal(updated.json()["freight_percentage"]) == Decimal("20")
    assert Decimal(updated.json()["expense_percentage"]) == Decimal("8")
    assert Decimal(updated.json()["dai_percentage"]) == Decimal("12")

    updated_costs = updated.json()["costs"]
    assert isinstance(updated_costs, list)
    updated = await purchase_order_client.put(
        f"/api/v1/retaceos/{retaceo_id}",
        headers=headers,
        json={
            "total_freight": "6.000000",
            "total_expenses": "2.000000",
            "total_dai": "3.000000",
            "import_vat": "13.000000",
            "notes": "Retaceo ajustado",
            "costs": allocated_costs(updated_costs, freight_amount="6.000000"),
        },
    )
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["total_cost"]) == expected_fob + Decimal("11")

    storage = _enable_purchase_order_document_services(
        purchase_order_client,
        monkeypatch,
        PurchaseOrderE2EScanner(ScanResult(clean=True)),
    )
    for cost in updated.json()["costs"]:
        cost_id = cost["id"]
        payload = f"%PDF-1.7\nComprobante E2E: {cost['title']}".encode()
        base = f"/api/v1/retaceos/{retaceo_id}/costs/{cost_id}/documents"
        initiated = await purchase_order_client.post(
            f"{base}/uploads",
            headers=headers,
            json={
                "file_name": f"retaceo-{cost_id}.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(payload),
                "checksum_sha256": hashlib.sha256(payload).hexdigest(),
            },
        )
        assert initiated.status_code == 201, initiated.text
        document_id = initiated.json()["document"]["document_id"]
        storage.put(document_id, payload)
        completed = await purchase_order_client.post(
            f"{base}/{document_id}/complete",
            headers=headers,
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "active"

    calculated = await purchase_order_client.post(
        f"/api/v1/retaceos/{retaceo_id}/calculate",
        headers=headers,
    )
    assert calculated.status_code == 200, calculated.text
    assert calculated.json()["status"] == "calculated"

    immutable = await purchase_order_client.put(
        f"/api/v1/retaceos/{retaceo_id}",
        headers=headers,
        json={
            "total_freight": "1.000000",
            "total_expenses": "1.000000",
            "total_dai": "1.000000",
            "import_vat": "1.000000",
        },
    )
    assert immutable.status_code == 422
    assert immutable.json()["code"] == "retaceo_not_editable"

    verified = await purchase_order_client.post(
        f"/api/v1/retaceos/{retaceo_id}/verify",
        headers=headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "verified"

    closed = await purchase_order_client.post(
        f"/api/v1/retaceos/{retaceo_id}/close",
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    fetched = await purchase_order_client.get(
        f"/api/v1/retaceos/{retaceo_id}",
        headers=headers,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "closed"

    listed = await purchase_order_client.get(
        "/api/v1/retaceos",
        headers=headers,
        params={"purchase_id": purchase_id, "branch_id": str(branch_id)},
    )
    assert listed.status_code == 200, listed.text
    assert retaceo_id in {item["id"] for item in listed.json()["items"]}

    audit = await purchase_order_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "company_id": str(company_id),
            "branch_id": str(branch_id),
            "resource_type": "retaceos",
            "resource_id": retaceo_id,
            "size": 50,
        },
    )
    assert audit.status_code == 200, audit.text
    audit_items = audit.json()["items"]
    actions = {item["action"] for item in audit_items}
    assert {"CREATE", "UPDATE", "CALCULATE", "VERIFY", "CLOSE"}.issubset(actions)
    assert all(item["branch_id"] == str(branch_id) for item in audit_items)


async def test_retaceo_requires_rbac_permission(
    purchase_order_client: AsyncClient,
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
        purchase_order_client,
        company_id=company_id,
        username="retaceo-no-role",
        is_superuser=False,
    )

    response = await purchase_order_client.get("/api/v1/retaceos", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


class PurchaseOrderE2EObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.declarations: dict[str, tuple[str, dict[str, str]]] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str,
        metadata: dict[str, str],
        expires_seconds: int,
    ) -> PresignedUpload:
        del expires_seconds
        self.declarations[key] = (content_type, metadata)
        return PresignedUpload(
            url=f"http://object-storage.test/upload/{uuid.uuid4()}",
            headers={"Content-Type": content_type},
        )

    def put(self, document_id: str, payload: bytes) -> None:
        key = next(
            key
            for key, (_content_type, metadata) in self.declarations.items()
            if metadata["document-id"] == document_id
        )
        self.objects[key] = payload

    async def presign_download(
        self,
        key: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        del key, content_type, expires_seconds
        return f"http://object-storage.test/download/{uuid.uuid4()}?filename={filename}"

    async def presign_preview(
        self,
        key: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        del key, content_type, expires_seconds
        return f"http://object-storage.test/preview/{uuid.uuid4()}?filename={filename}"

    async def head(self, key: str) -> StoredObjectInfo | None:
        if key not in self.objects:
            return None
        content_type, metadata = self.declarations[key]
        return StoredObjectInfo(
            size_bytes=len(self.objects[key]),
            content_type=content_type,
            etag="purchase-order-e2e-etag",
            metadata=metadata,
        )

    async def download_to(self, key: str, destination: Path, max_bytes: int) -> None:
        del max_bytes
        destination.write_bytes(self.objects[key])

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def upload_from(
        self,
        key: str,
        source: Path,
        *,
        content_type: str,
        metadata: dict[str, str],
    ) -> StoredObjectInfo:
        payload = source.read_bytes()
        self.objects[key] = payload
        self.declarations[key] = (content_type, metadata)
        return StoredObjectInfo(
            size_bytes=len(payload),
            content_type=content_type,
            etag="purchase-order-e2e-etag",
            metadata=metadata,
        )

    async def health(self) -> bool:
        return True


class PurchaseOrderE2EScanner:
    def __init__(self, result: ScanResult) -> None:
        self.result = result

    async def scan(self, path: Path) -> ScanResult:
        assert path.exists()
        return self.result

    async def health(self) -> bool:
        return True


def _enable_purchase_order_document_services(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    scanner: PurchaseOrderE2EScanner,
) -> PurchaseOrderE2EObjectStorage:
    storage = PurchaseOrderE2EObjectStorage()
    monkeypatch.setattr(settings, "OBJECT_STORAGE_ENABLED", True)
    app = client._transport.app
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_malware_scanner] = lambda: scanner
    return storage


async def _active_expense_type_id(company_id: uuid.UUID) -> uuid.UUID:
    async with async_session_factory() as session:
        expense_type = await session.scalar(
            select(ExpenseTypeModel)
            .where(
                ExpenseTypeModel.company_id == company_id,
                ExpenseTypeModel.is_active.is_(True),
            )
            .order_by(ExpenseTypeModel.created_at, ExpenseTypeModel.id)
            .limit(1)
        )
        if expense_type is None:
            expense_type = ExpenseTypeModel(
                id=uuid.uuid4(),
                company_id=company_id,
                name="E2E Purchase Order Freight",
                description="Tipo de gasto estable para pruebas E2E de órdenes de compra.",
                is_active=True,
            )
            session.add(expense_type)
            await session.commit()
        return expense_type.id


async def _draft_order_with_expense(
    client: AsyncClient,
    *,
    headers: dict[str, str],
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    product_id: int,
    supplier_id: int,
    currency: str,
) -> dict[str, object]:
    purchase_request = await _approved_purchase_request(
        client,
        headers=headers,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
    quotation = await _selected_quotation(
        client,
        headers=headers,
        purchase_request=purchase_request,
        supplier_id=supplier_id,
        currency=currency,
    )
    payload = _order_payload(
        quotation=quotation,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        quantity="1.000000",
        notes="Orden con soporte documental",
    )
    payload["expenses"] = [
        {
            "expense_type_id": str(await _active_expense_type_id(company_id)),
            "amount": "7.500000",
            "description": "Flete documentado",
        }
    ]
    created = await client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_purchase_order_expense_document_clean_flow(
    purchase_order_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-expense-document",
        is_superuser=True,
    )
    created = await _draft_order_with_expense(
        purchase_order_client,
        headers=headers,
        company_id=company_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    order_id = created["id"]
    expenses = created["expenses"]
    assert isinstance(expenses, list)
    expense = expenses[0]
    assert isinstance(expense, dict)
    expense_id = expense["id"]

    submitted = await purchase_order_client.post(
        f"/api/v1/purchase-orders/{order_id}/submit",
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "pending_approval"

    payload = b"%PDF-1.7\npurchase-order expense document"
    storage = _enable_purchase_order_document_services(
        purchase_order_client,
        monkeypatch,
        PurchaseOrderE2EScanner(ScanResult(clean=True)),
    )
    base = f"/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents"
    initiated = await purchase_order_client.post(
        f"{base}/uploads",
        headers=headers,
        json={
            "file_name": "po-expense-e2e-flete.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    assert initiated.status_code == 201, initiated.text
    assert "file_path" not in initiated.text
    assert "bucket" not in initiated.text
    assert "object_key" not in initiated.text
    document_id = initiated.json()["document"]["document_id"]
    assert initiated.json()["document"]["status"] == "pending_upload"

    storage.put(document_id, payload)

    completed = await purchase_order_client.post(
        f"{base}/{document_id}/complete",
        headers=headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "active"
    assert completed.json()["uploaded_at"] is not None

    listed = await purchase_order_client.get(base, headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["document_id"] for item in listed.json()] == [document_id]

    download = await purchase_order_client.post(
        f"{base}/{document_id}/download-url",
        headers=headers,
    )
    assert download.status_code == 200, download.text
    assert download.json()["url"].startswith("http://object-storage.test/download/")

    async with async_session_factory() as session:
        expense_actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.resource_id == str(expense_id))
                )
            ).all()
        )
        document_actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.resource_id == document_id)
                )
            ).all()
        )

    assert {
        "PURCHASE_ORDER_EXPENSE_DOCUMENT_INITIATED",
        "PURCHASE_ORDER_EXPENSE_DOCUMENT_COMPLETED",
    } <= expense_actions
    assert {
        "DOCUMENT_UPLOAD_INITIATED",
        "DOCUMENT_ACTIVATED",
        "DOCUMENT_DOWNLOAD_URL_ISSUED",
    } <= document_actions


async def test_purchase_order_expense_document_rejects_draft_order(
    purchase_order_client: AsyncClient,
) -> None:
    company_id, branch_id, warehouse_id, product_id, supplier_id, currency = await _reference_ids()
    headers = await _headers(
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-expense-draft",
        is_superuser=True,
    )
    created = await _draft_order_with_expense(
        purchase_order_client,
        headers=headers,
        company_id=company_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        supplier_id=supplier_id,
        currency=currency,
    )
    expenses = created["expenses"]
    assert isinstance(expenses, list)
    expense = expenses[0]
    assert isinstance(expense, dict)

    response = await purchase_order_client.post(
        (f"/api/v1/purchase-orders/{created['id']}/expenses/{expense['id']}/documents/uploads"),
        headers=headers,
        json={
            "file_name": "po-expense-e2e-draft.pdf",
            "content_type": "application/pdf",
            "size_bytes": 32,
            "checksum_sha256": "a" * 64,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "purchase_order_expense_document_requires_stable_expense"


async def test_purchase_order_expense_documents_require_permission(
    purchase_order_client: AsyncClient,
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
        purchase_order_client,
        company_id=company_id,
        username="purchase-order-expense-no-role",
        is_superuser=False,
    )
    order_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    base = f"/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents"

    listed = await purchase_order_client.get(base, headers=headers)
    initiated = await purchase_order_client.post(
        f"{base}/uploads",
        headers=headers,
        json={
            "file_name": "po-expense-e2e-denied.pdf",
            "content_type": "application/pdf",
            "size_bytes": 32,
            "checksum_sha256": "b" * 64,
        },
    )

    assert listed.status_code == 403
    assert listed.json()["code"] == "forbidden"
    assert initiated.status_code == 403
    assert initiated.json()["code"] == "forbidden"

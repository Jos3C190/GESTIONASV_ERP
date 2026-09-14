from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
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
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.purchase_order import PurchaseOrderModel
from app.infrastructure.models.purchase_quotation import (
    ExpenseTypeModel,
    PurchaseQuotationModel,
)
from app.infrastructure.models.purchase_request import PurchaseRequestModel
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.supplier_master_data import CurrencyModel
from httpx import AsyncClient
from sqlalchemy import and_, delete, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


@pytest.fixture
async def purchase_order_client(e2e_client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Clean procurement rows before the shared E2E fixture deletes users."""
    try:
        yield e2e_client
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(PurchaseOrderModel))
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
                    Warehouse.storage_eligible.is_(True),
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
            "justification": "Compra para validar órdenes",
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

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.api.v1.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderExpenseDocumentInitiate,
    PurchaseOrderExpenseDocumentResponse,
    PurchaseOrderUpdate,
)
from app.application.rbac.catalogue import ALL_PERMISSION_CODES
from app.main import create_app
from pydantic import ValidationError as PydanticValidationError


def _create_payload() -> dict[str, object]:
    return {
        "purchase_quotation_id": str(uuid.uuid4()),
        "branch_id": str(uuid.uuid4()),
        "warehouse_id": str(uuid.uuid4()),
        "expected_date": datetime.now(UTC).isoformat(),
        "notes": "  Orden urgente  ",
        "lines": [
            {
                "purchase_quotation_detail_id": str(uuid.uuid4()),
                "quantity": "2.500000",
            }
        ],
        "expenses": [
            {
                "expense_type_id": str(uuid.uuid4()),
                "amount": "15.250000",
                "description": "  Flete negociado  ",
            }
        ],
    }


def test_purchase_order_create_schema_trims_text_and_parses_decimal() -> None:
    payload = PurchaseOrderCreate.model_validate(_create_payload())

    assert payload.notes == "Orden urgente"
    assert payload.lines[0].quantity == Decimal("2.500000")
    assert payload.expenses[0].amount == Decimal("15.250000")
    assert payload.expenses[0].description == "Flete negociado"


def test_purchase_order_create_requires_lines() -> None:
    raw = _create_payload()
    raw["lines"] = []

    with pytest.raises(PydanticValidationError):
        PurchaseOrderCreate.model_validate(raw)


def test_purchase_order_create_rejects_computed_or_supplier_fields() -> None:
    for extra_field, value in (
        ("supplier_id", 99),
        ("subtotal", "10"),
        ("tax", "1.30"),
        ("additional_expenses", "2"),
        ("total", "13.30"),
        ("currency", "USD"),
        ("payment_terms", "30 días"),
    ):
        raw = _create_payload()
        raw[extra_field] = value
        with pytest.raises(PydanticValidationError):
            PurchaseOrderCreate.model_validate(raw)


def test_purchase_order_update_cannot_change_source_quotation() -> None:
    raw = _create_payload()

    with pytest.raises(PydanticValidationError):
        PurchaseOrderUpdate.model_validate(raw)


def test_purchase_order_schema_rejects_invalid_amounts() -> None:
    raw = _create_payload()
    raw["lines"] = [
        {
            "purchase_quotation_detail_id": str(uuid.uuid4()),
            "quantity": "0",
        }
    ]

    with pytest.raises(PydanticValidationError):
        PurchaseOrderCreate.model_validate(raw)


def test_purchase_order_permissions_are_registered() -> None:
    assert {
        "purchase_orders:read",
        "purchase_orders:manage",
        "purchase_orders:approve",
        "purchase_orders:send",
    }.issubset(ALL_PERMISSION_CODES)


def test_purchase_order_routes_are_registered_in_openapi() -> None:
    application = create_app()
    fastapi_app = getattr(application, "app", application)
    paths = fastapi_app.openapi()["paths"]

    assert {"get", "post"}.issubset(paths["/api/v1/purchase-orders"])
    assert {"get", "put"}.issubset(paths["/api/v1/purchase-orders/{order_id}"])
    for action in ("submit", "approve", "send", "cancel"):
        assert "post" in paths[f"/api/v1/purchase-orders/{{order_id}}/{action}"]


def test_purchase_order_expense_document_input_rejects_storage_fields() -> None:
    valid = {
        "file_name": "flete.pdf",
        "content_type": "application/pdf",
        "size_bytes": 128,
        "checksum_sha256": "a" * 64,
    }

    parsed = PurchaseOrderExpenseDocumentInitiate.model_validate(valid)
    assert parsed.file_name == "flete.pdf"

    for forbidden in ("file_path", "object_key", "bucket", "folder_id"):
        payload = dict(valid)
        payload[forbidden] = "should-not-be-accepted"
        with pytest.raises(PydanticValidationError):
            PurchaseOrderExpenseDocumentInitiate.model_validate(payload)


def test_purchase_order_expense_document_response_has_no_storage_path() -> None:
    response = PurchaseOrderExpenseDocumentResponse(
        id=uuid.uuid4(),
        purchase_order_expense_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        file_name="flete.pdf",
        file_type="application/pdf",
        size_bytes=128,
        status="active",
    )

    data = response.model_dump()
    assert "file_path" not in data
    assert "object_key" not in data
    assert "bucket" not in data


def test_purchase_order_expense_document_routes_are_registered_in_openapi() -> None:
    application = create_app()
    fastapi_app = getattr(application, "app", application)
    paths = fastapi_app.openapi()["paths"]
    base = "/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents"

    assert "get" in paths[base]
    assert "post" in paths[f"{base}/uploads"]
    assert "post" in paths[f"{base}/{{document_id}}/complete"]
    assert "post" in paths[f"{base}/{{document_id}}/download-url"]


def test_purchase_order_schemas_reject_naive_expected_date() -> None:
    raw = _create_payload()
    raw["expected_date"] = "2026-09-20T10:30:00"

    with pytest.raises(PydanticValidationError):
        PurchaseOrderCreate.model_validate(raw)

    update = dict(raw)
    update.pop("purchase_quotation_id")
    with pytest.raises(PydanticValidationError):
        PurchaseOrderUpdate.model_validate(update)


def test_purchase_order_expense_document_filename_matches_storage_limit() -> None:
    valid = {
        "content_type": "application/pdf",
        "size_bytes": 128,
        "checksum_sha256": "a" * 64,
    }

    PurchaseOrderExpenseDocumentInitiate.model_validate({**valid, "file_name": f"{'a' * 251}.pdf"})
    with pytest.raises(PydanticValidationError):
        PurchaseOrderExpenseDocumentInitiate.model_validate(
            {**valid, "file_name": f"{'a' * 252}.pdf"}
        )

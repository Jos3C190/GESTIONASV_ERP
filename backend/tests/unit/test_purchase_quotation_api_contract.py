from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.api.v1.schemas.purchase_quotation import (
    PurchaseQuotationCreate,
    PurchaseQuotationRecordResponse,
)
from app.application.rbac.catalogue import ALL_PERMISSION_CODES
from app.main import create_app
from pydantic import ValidationError as PydanticValidationError


def _create_payload() -> dict[str, object]:
    return {
        "supplier_id": 1,
        "currency": " usd ",
        "notes": "  Compra urgente  ",
        "requests": [
            {
                "purchase_request_id": str(uuid.uuid4()),
                "lines": [
                    {
                        "purchase_request_detail_id": str(uuid.uuid4()),
                        "quantity": "2.500000",
                    }
                ],
            }
        ],
    }


def _response_payload() -> dict[str, object]:
    return {
        "quotation_date": datetime.now(UTC).isoformat(),
        "lines": [
            {
                "product_id": 1,
                "unit_id": 1,
                "quantity": "2.500000",
                "unit_price": "10.250000",
                "tax_rate": "13",
            }
        ],
    }


def test_purchase_quotation_create_schema_trims_text_and_parses_decimal() -> None:
    payload = PurchaseQuotationCreate.model_validate(_create_payload())

    assert payload.currency == "usd"
    assert payload.notes == "Compra urgente"
    assert payload.requests[0].lines[0].quantity == Decimal("2.500000")


def test_purchase_quotation_create_schema_requires_request_coverage() -> None:
    raw = _create_payload()
    raw["requests"] = []

    with pytest.raises(PydanticValidationError):
        PurchaseQuotationCreate.model_validate(raw)


def test_purchase_quotation_create_schema_rejects_computed_fields() -> None:
    raw = _create_payload()
    raw["total"] = "100.00"

    with pytest.raises(PydanticValidationError):
        PurchaseQuotationCreate.model_validate(raw)


def test_purchase_quotation_response_schema_rejects_invalid_amounts() -> None:
    raw = _response_payload()
    raw["lines"] = [
        {
            "product_id": 1,
            "unit_id": 1,
            "quantity": "1",
            "unit_price": "-1",
        }
    ]

    with pytest.raises(PydanticValidationError):
        PurchaseQuotationRecordResponse.model_validate(raw)


def test_purchase_quotation_permissions_are_registered() -> None:
    assert {
        "purchase_quotations:read",
        "purchase_quotations:manage",
        "purchase_quotations:select",
    }.issubset(ALL_PERMISSION_CODES)


def test_purchase_quotation_routes_are_registered_in_openapi() -> None:
    application = create_app()
    fastapi_app = getattr(application, "app", application)
    paths = fastapi_app.openapi()["paths"]

    assert {"get", "post"}.issubset(paths["/api/v1/purchase-quotations"])
    assert "get" in paths["/api/v1/purchase-quotations/{quotation_id}"]
    assert "get" in paths["/api/v1/purchase-quotations/comparison/{purchase_request_id}"]
    assert "put" in paths["/api/v1/purchase-quotations/{quotation_id}/response"]
    for action in ("send", "evaluate", "select", "reject", "cancel"):
        assert "post" in paths[f"/api/v1/purchase-quotations/{{quotation_id}}/{action}"]

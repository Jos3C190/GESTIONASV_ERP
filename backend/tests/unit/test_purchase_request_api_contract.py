from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.api.v1.schemas.purchase_request import PurchaseRequestCreate
from app.application.rbac.catalogue import ALL_PERMISSION_CODES
from app.main import create_app
from pydantic import ValidationError as PydanticValidationError


def _payload() -> dict[str, object]:
    return {
        "branch_id": str(uuid.uuid4()),
        "warehouse_id": str(uuid.uuid4()),
        "justification": "  Reposición de materia prima  ",
        "details": [{"product_id": 1, "quantity": "2.500000"}],
    }


def test_purchase_request_schema_trims_text_and_parses_decimal() -> None:
    payload = PurchaseRequestCreate.model_validate(_payload())

    assert payload.justification == "Reposición de materia prima"
    assert payload.details[0].quantity == Decimal("2.500000")


def test_purchase_request_schema_requires_at_least_one_detail() -> None:
    raw = _payload()
    raw["details"] = []

    with pytest.raises(PydanticValidationError):
        PurchaseRequestCreate.model_validate(raw)


def test_purchase_request_schema_rejects_non_positive_quantity() -> None:
    raw = _payload()
    raw["details"] = [{"product_id": 1, "quantity": "0"}]

    with pytest.raises(PydanticValidationError):
        PurchaseRequestCreate.model_validate(raw)


def test_purchase_request_schema_rejects_client_supplied_unit_id() -> None:
    raw = _payload()
    raw["details"] = [{"product_id": 1, "quantity": "1", "unit_id": 99}]

    with pytest.raises(PydanticValidationError):
        PurchaseRequestCreate.model_validate(raw)


def test_purchase_request_permissions_are_registered() -> None:
    assert {
        "purchase_requests:read",
        "purchase_requests:manage",
        "purchase_requests:approve",
    }.issubset(ALL_PERMISSION_CODES)


def test_purchase_request_routes_are_registered_in_openapi() -> None:
    application = create_app()
    fastapi_app = getattr(application, "app", application)
    paths = fastapi_app.openapi()["paths"]

    assert {"get", "post"}.issubset(paths["/api/v1/purchase-requests"])
    assert {"get", "put"}.issubset(paths["/api/v1/purchase-requests/{request_id}"])
    for action in ("submit", "approve", "reject", "cancel"):
        assert "post" in paths[f"/api/v1/purchase-requests/{{request_id}}/{action}"]

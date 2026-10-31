"""Return reasons must remain meaningful after whitespace normalization."""

import uuid
from unittest.mock import MagicMock

import pytest
from app.api.v1.schemas.sales_return import (
    SalesReturnCancellation,
    SalesReturnLineCreate,
    SalesReturnResolveLine,
)
from app.application.sales.returns import SalesReturnService
from app.core.exceptions import ValidationError as ApplicationValidationError
from pydantic import ValidationError


def payload(schema, reason):
    if schema is SalesReturnCancellation:
        return {"reason": reason}
    if schema is SalesReturnLineCreate:
        return {
            "reason": reason,
            "delivery_allocation_id": uuid.uuid4(),
            "quantity_base": "1",
            "declared_condition": "resalable",
        }
    return {
        "reason": reason,
        "return_line_id": uuid.uuid4(),
        "quantity_base": "1",
        "condition": "resalable",
        "decision": "accepted",
    }


@pytest.mark.parametrize(
    "schema", [SalesReturnCancellation, SalesReturnLineCreate, SalesReturnResolveLine]
)
@pytest.mark.parametrize("reason", ["   ", " a ", "\t\n", " ab ", "x" * 501])
def test_invalid_reason_is_rejected_after_trimming(schema, reason):
    with pytest.raises(ValidationError):
        schema(**payload(schema, reason))


@pytest.mark.parametrize(
    "schema", [SalesReturnCancellation, SalesReturnLineCreate, SalesReturnResolveLine]
)
def test_valid_reason_is_normalized(schema):
    assert schema(**payload(schema, "  Empaque revisado  ")).reason == "Empaque revisado"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["create_draft", "resolve"])
async def test_service_rejects_blank_reason_before_any_database_operation(action):
    session = MagicMock()
    service = SalesReturnService(session, MagicMock(), MagicMock())
    kwargs = {
        "company_id": uuid.uuid4(),
        "actor_id": uuid.uuid4(),
        "idempotency_key": "blank-reason",
        "request": None,
    }
    if action == "create_draft":
        kwargs.update(
            sale_id=uuid.uuid4(),
            document_ids=[],
            notes=None,
            lines=[payload(SalesReturnLineCreate, "   ")],
        )
    else:
        kwargs.update(return_id=uuid.uuid4(), lines=[payload(SalesReturnResolveLine, "   ")])
    with pytest.raises(ApplicationValidationError):
        await getattr(service, action)(**kwargs)
    assert session.mock_calls == []

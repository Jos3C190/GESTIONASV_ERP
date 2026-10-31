from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.api.v1.routers import inventory_trace
from app.api.v1.routers.inventory_trace import public_router
from app.api.v1.schemas.inventory_trace import (
    PublicHandlingUnitTraceOut,
    PublicTraceOriginOut,
    PublicTraceResolveIn,
    TraceCapabilityCreateIn,
)
from app.infrastructure.repositories.inventory_trace_capability_repository import (
    digest_trace_token,
)
from pydantic import ValidationError
from starlette.requests import Request


def test_trace_token_is_validated_and_stored_as_a_one_way_digest() -> None:
    token = "a" * 43

    assert PublicTraceResolveIn(token=token).token == token
    assert digest_trace_token(token) != token
    assert len(digest_trace_token(token)) == 64
    with pytest.raises(ValidationError):
        PublicTraceResolveIn(token="../not-a-capability")


def test_public_trace_schema_excludes_company_and_operator_identifiers() -> None:
    assert "company_id" not in PublicHandlingUnitTraceOut.model_fields
    assert "posted_by" not in PublicHandlingUnitTraceOut.model_fields
    assert "operator" not in PublicHandlingUnitTraceOut.model_fields
    assert "requests" not in PublicTraceOriginOut.model_fields


def test_public_trace_endpoint_has_no_authentication_dependency() -> None:
    route = next(
        route for route in public_router.routes if getattr(route, "path", "").endswith("/resolve")
    )
    assert not any(
        dependency.call.__name__ == "require_permission"
        for dependency in route.dependant.dependencies
        if hasattr(dependency.call, "__name__")
    )


@pytest.mark.parametrize("has_receipt_lot", [False, True])
@pytest.mark.asyncio
async def test_qr_capability_uses_traceability_without_requiring_a_receipt_label(
    monkeypatch: pytest.MonkeyPatch, has_receipt_lot: bool
) -> None:
    company_id = uuid4()
    branch_id = uuid4()
    handling_unit_id = uuid4()
    actor_id = uuid4()
    created_at = datetime(2026, 10, 16, tzinfo=UTC)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/inventory/trace-capabilities",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )
    authorize = AsyncMock(return_value=(company_id, branch_id))
    monkeypatch.setattr(inventory_trace, "_authorize_unit", authorize)

    class FakeInventoryRepository:
        def __init__(self, session):
            self.session = session

    class FakeInventoryUseCases:
        def __init__(self, repository):
            self.repository = repository

        async def get_handling_unit_traceability(self, *, company_id, handling_unit_id):
            return {
                "handling_unit": {
                    "id": handling_unit_id,
                    "receipt_lot_id": uuid4() if has_receipt_lot else None,
                },
                "origin": {"purchase_code": None},
            }

    monkeypatch.setattr(inventory_trace, "SqlAlchemyInventoryRepository", FakeInventoryRepository)
    monkeypatch.setattr(inventory_trace, "InventoryUseCases", FakeInventoryUseCases)
    label_preview = AsyncMock()

    class FakeInventoryLabelRepository:
        def __init__(self, session):
            self.session = session
            self.preview = label_preview

    monkeypatch.setattr(
        inventory_trace, "SqlAlchemyInventoryLabelRepository", FakeInventoryLabelRepository
    )

    class FakeTraceCapabilityRepository:
        def __init__(self, session):
            self.session = session

        async def create(self, *, company_id, handling_unit_id, actor_id):
            return SimpleNamespace(id=uuid4(), created_at=created_at), "a" * 43

    monkeypatch.setattr(
        inventory_trace,
        "SqlAlchemyInventoryTraceCapabilityRepository",
        FakeTraceCapabilityRepository,
    )
    audit = SimpleNamespace(record=AsyncMock())
    session = object()

    result = await inventory_trace.create_trace_capability(
        TraceCapabilityCreateIn(handling_unit_id=handling_unit_id),
        request,
        session,  # type: ignore[arg-type]
        SimpleNamespace(id=actor_id),  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
    )

    assert result.token == "a" * 43
    authorize.assert_awaited_once_with(
        request, session, SimpleNamespace(id=actor_id), handling_unit_id
    )
    audit.record.assert_awaited_once()
    if has_receipt_lot:
        label_preview.assert_awaited_once_with(
            company_id=company_id, handling_unit_id=handling_unit_id
        )
    else:
        label_preview.assert_not_awaited()


@pytest.mark.asyncio
async def test_qr_capability_rejects_a_unit_without_a_resolvable_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid4()
    handling_unit_id = uuid4()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/inventory/trace-capabilities",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )
    monkeypatch.setattr(
        inventory_trace, "_authorize_unit", AsyncMock(return_value=(company_id, None))
    )

    class FakeInventoryRepository:
        def __init__(self, session):
            self.session = session

    class FakeInventoryUseCases:
        def __init__(self, repository):
            self.repository = repository

        async def get_handling_unit_traceability(self, *, company_id, handling_unit_id):
            return None

    monkeypatch.setattr(inventory_trace, "SqlAlchemyInventoryRepository", FakeInventoryRepository)
    monkeypatch.setattr(inventory_trace, "InventoryUseCases", FakeInventoryUseCases)
    capability_create = AsyncMock()

    class FakeTraceCapabilityRepository:
        def __init__(self, session):
            self.create = capability_create

    monkeypatch.setattr(
        inventory_trace,
        "SqlAlchemyInventoryTraceCapabilityRepository",
        FakeTraceCapabilityRepository,
    )

    with pytest.raises(inventory_trace.HTTPException) as error:
        await inventory_trace.create_trace_capability(
            TraceCapabilityCreateIn(handling_unit_id=handling_unit_id),
            request,
            object(),  # type: ignore[arg-type]
            SimpleNamespace(id=uuid4()),  # type: ignore[arg-type]
            SimpleNamespace(record=AsyncMock()),  # type: ignore[arg-type]
        )

    assert error.value.status_code == 404
    capability_create.assert_not_awaited()

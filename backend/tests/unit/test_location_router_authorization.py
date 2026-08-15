"""Tenant-boundary tests for the new location router's resource guards."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api.v1.company_access import set_effective_company_id
from app.api.v1.routers import locations as location_router
from app.domain.entities.location import WarehouseLocationScope
from fastapi import HTTPException
from starlette.requests import Request

pytestmark = pytest.mark.unit


def _request(company_id: uuid.UUID) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/locations",
            "headers": [(b"x-company-id", str(company_id).encode("ascii"))],
        }
    )
    set_effective_company_id(request, company_id)
    return request


def _scope(company_id: uuid.UUID) -> WarehouseLocationScope:
    return WarehouseLocationScope(
        warehouse_id=uuid.uuid4(),
        company_id=company_id,
        branch_id=uuid.uuid4(),
        warehouse_active=True,
        operational_status="active",
    )


@pytest.mark.asyncio
async def test_warehouse_guard_uses_persisted_scope_and_hides_cross_tenant_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_company = uuid.uuid4()
    persisted_scope = _scope(uuid.uuid4())
    use_cases = SimpleNamespace(warehouse_scope=AsyncMock(return_value=persisted_scope))
    branch_check = AsyncMock()
    monkeypatch.setattr(location_router, "resolve_branch_scope", branch_check)

    with pytest.raises(HTTPException) as error:
        await location_router._authorize_warehouse(
            _request(selected_company),
            AsyncMock(),
            SimpleNamespace(id=uuid.uuid4(), is_superuser=True),
            use_cases,
            persisted_scope.warehouse_id,
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Almacén no encontrado."
    branch_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_warehouse_guard_checks_branch_scope_after_company_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_company = uuid.uuid4()
    persisted_scope = _scope(selected_company)
    use_cases = SimpleNamespace(warehouse_scope=AsyncMock(return_value=persisted_scope))
    branch_check = AsyncMock()
    monkeypatch.setattr(location_router, "resolve_branch_scope", branch_check)
    session = AsyncMock()
    current = SimpleNamespace(id=uuid.uuid4(), is_superuser=False)

    await location_router._authorize_warehouse(
        _request(selected_company),
        session,
        current,
        use_cases,
        persisted_scope.warehouse_id,
    )

    branch_check.assert_awaited_once_with(
        session,
        current,
        selected_company,
        persisted_scope.branch_id,
    )


@pytest.mark.asyncio
async def test_batch_guard_cannot_cross_tenants_even_with_global_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_company = uuid.uuid4()
    persisted_scope = _scope(uuid.uuid4())
    use_cases = SimpleNamespace(batch_scope=AsyncMock(return_value=persisted_scope))
    branch_check = AsyncMock()
    monkeypatch.setattr(location_router, "resolve_branch_scope", branch_check)

    with pytest.raises(HTTPException) as error:
        await location_router._authorize_batch(
            _request(selected_company),
            AsyncMock(),
            SimpleNamespace(id=uuid.uuid4(), is_superuser=True),
            use_cases,
            uuid.uuid4(),
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Lote no encontrado."
    branch_check.assert_not_awaited()

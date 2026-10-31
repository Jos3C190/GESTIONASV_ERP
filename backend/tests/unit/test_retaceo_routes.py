"""API surface checks for retaceo routes and DTOs."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api.v1.routers import purchase_orders
from app.domain.entities.actual_expense import ActualExpenseClosure
from app.main import create_app


def test_retaceo_routes_are_registered_in_openapi() -> None:
    app = create_app()
    inner = getattr(app, "app", app)
    paths = inner.openapi()["paths"]

    assert "/api/v1/retaceos" in paths
    assert "/api/v1/retaceos/cost-categories" in paths
    assert "get" in paths["/api/v1/purchase-orders/{order_id}/actual-expenses"]
    assert "post" in paths["/api/v1/purchase-orders/{order_id}/actual-expenses"]
    assert "get" in paths["/api/v1/purchase-orders/{order_id}/actual-expenses/availability"]
    assert "/api/v1/retaceos/{retaceo_id}" in paths
    assert "/api/v1/retaceos/{retaceo_id}/calculate" in paths
    assert "/api/v1/retaceos/{retaceo_id}/verify" in paths
    assert "/api/v1/retaceos/{retaceo_id}/cancel" in paths
    assert "/api/v1/retaceos/{retaceo_id}/close" in paths


@pytest.mark.asyncio
async def test_actual_expense_availability_checks_document_visibility_and_serializes_reason(
    monkeypatch,
):
    company_id, order_id, warehouse_id, retaceo_id = (uuid.uuid4() for _ in range(4))
    order = SimpleNamespace(id=order_id, branch_id=None, warehouse_id=warehouse_id)
    current, session, request = object(), object(), object()
    visible = AsyncMock()
    use_cases = SimpleNamespace(get_order=AsyncMock(return_value=order))
    repository = SimpleNamespace(
        get_actual_expense_closure=AsyncMock(
            return_value=ActualExpenseClosure(retaceo_id, "RET-00021")
        )
    )
    monkeypatch.setattr(purchase_orders, "request_company_id", lambda _: company_id)
    monkeypatch.setattr(purchase_orders, "resolve_document_warehouse_scope", visible)
    monkeypatch.setattr(purchase_orders, "SqlAlchemyPurchaseOrderRepository", lambda _: repository)
    result = await purchase_orders.actual_expense_availability(
        order_id, request, session, current, use_cases
    )
    use_cases.get_order.assert_awaited_once_with(company_id, order_id, branch_id=None)
    visible.assert_awaited_once_with(
        session, current, company_id, document_branch_id=None, warehouse_id=warehouse_id
    )
    assert not result.can_record
    assert result.closed_retaceo_id == retaceo_id
    assert "RET-00021" in result.reason

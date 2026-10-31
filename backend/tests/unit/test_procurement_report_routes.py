"""Exports retain the visibility checks of their source documents."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from app.api.v1.routers import purchase_consolidations, retaceos
from app.domain.entities.tabular_report import ProcurementReportContext
from app.main import create_app
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from tests.unit.test_retaceo_use_cases import FakeRetaceoRepository, _create, _ids, _purchase


@pytest.mark.parametrize("export_format", ["pdf", "xlsx"])
@pytest.mark.asyncio
async def test_retaceo_export_checks_warehouse_scope_before_rendering(monkeypatch, export_format):
    purchase = _purchase(_ids())
    item = await _create(FakeRetaceoRepository(), purchase)
    visibility = AsyncMock()
    context = AsyncMock(return_value=ProcurementReportContext("Grupo Lorena"))
    monkeypatch.setattr(
        retaceos, "_visible_retaceo", AsyncMock(return_value=(purchase.company_id, item))
    )
    monkeypatch.setattr(retaceos, "resolve_document_warehouse_scope", visibility)
    monkeypatch.setattr(
        retaceos, "ProcurementReportRepository", lambda _: SimpleNamespace(context=context)
    )
    monkeypatch.setattr(retaceos, "render_pdf", lambda _: b"%PDF-report")
    monkeypatch.setattr(retaceos, "render_xlsx", lambda _: b"xlsx-report")
    purchases = SimpleNamespace(get_purchase=AsyncMock(return_value=purchase))
    response = await retaceos.export_retaceo(
        item.id, object(), object(), object(), export_format, object(), purchases
    )
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="{item.code}.{export_format}"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.body == (b"%PDF-report" if export_format == "pdf" else b"xlsx-report")
    assert visibility.await_args.kwargs["warehouse_id"] == purchase.warehouse_id
    context.assert_awaited_once_with(purchase.company_id, item)
    visibility.side_effect = HTTPException(403)
    context.reset_mock()
    with pytest.raises(HTTPException):
        await retaceos.export_retaceo(
            item.id, object(), object(), object(), export_format, object(), purchases
        )
    context.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidation_export_checks_all_source_branches_before_rendering(monkeypatch):
    company_id, consolidation_id = uuid.uuid4(), uuid.uuid4()
    item = SimpleNamespace(code="CON-001")
    cases = SimpleNamespace(get=AsyncMock(return_value=item))
    scope = AsyncMock(side_effect=HTTPException(403))
    repository = Mock()
    monkeypatch.setattr(purchase_consolidations, "request_company_id", lambda _: company_id)
    monkeypatch.setattr(purchase_consolidations, "_assert_consolidation_scope", scope)
    monkeypatch.setattr(purchase_consolidations, "ProcurementReportRepository", repository)
    with pytest.raises(HTTPException):
        await purchase_consolidations.export_consolidation(
            consolidation_id, object(), object(), object(), cases
        )
    cases.get.assert_awaited_once_with(company_id, consolidation_id)
    repository.assert_not_called()


def test_export_routes_publish_pdf_and_excel_format_choices():
    app = create_app()
    schema = getattr(app, "app", app).openapi()
    operation = schema["paths"]["/api/v1/retaceos/{retaceo_id}/export"]["get"]
    parameter = next(row for row in operation["parameters"] if row["name"] == "format")
    assert parameter["schema"]["enum"] == ["pdf", "xlsx"]
    assert "get" in schema["paths"]["/api/v1/purchase-consolidations/{consolidation_id}/export"]


@pytest.mark.asyncio
async def test_exports_are_not_public_download_links():
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        for path in (
            f"/api/v1/retaceos/{uuid.uuid4()}/export?format=pdf",
            f"/api/v1/purchase-consolidations/{uuid.uuid4()}/export",
        ):
            response = await client.get(path)
            assert response.status_code == 401

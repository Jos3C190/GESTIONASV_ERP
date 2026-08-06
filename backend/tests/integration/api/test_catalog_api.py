"""Integration tests for catalog and supplier endpoints protection."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app


@pytest.fixture
async def api_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_catalog_endpoints_require_auth(api_client: AsyncClient):
    """Verify unauthenticated requests return 401 Unauthorized."""
    res_countries = await api_client.get("/api/v1/catalog/countries")
    assert res_countries.status_code == 401

    res_categories = await api_client.get("/api/v1/catalog/categories")
    assert res_categories.status_code == 401

    res_products = await api_client.get("/api/v1/catalog/products")
    assert res_products.status_code == 401

    res_suppliers = await api_client.get("/api/v1/suppliers")
    assert res_suppliers.status_code == 401

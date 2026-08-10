"""Security boundary tests for lifecycle API endpoints."""

from __future__ import annotations

import pytest
from app.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def api_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/v1/lifecycle/trash", None),
        (
            "DELETE",
            "/api/v1/lifecycle/products/1",
            {"reason": "Registro duplicado"},
        ),
        ("POST", "/api/v1/lifecycle/products/1/restore", None),
    ],
)
async def test_lifecycle_endpoints_require_authentication(
    api_client: AsyncClient,
    method: str,
    path: str,
    json_body: dict[str, str] | None,
) -> None:
    response = await api_client.request(method, path, json=json_body)

    assert response.status_code == 401

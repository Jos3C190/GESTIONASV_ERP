"""Browser preflights for commercial idempotent commands require no database."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sales/quotations",
        "/api/v1/sales/demo/returns",
        "/api/v1/sales/deliveries/demo/confirm",
    ],
)
async def test_commercial_preflight_allows_idempotency_header(
    client: AsyncClient, path: str
) -> None:
    response = await client.options(
        path,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key,x-company-id,x-branch-id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.asyncio
async def test_commercial_preflight_still_rejects_an_untrusted_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/sales/quotations",
        headers={
            "Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers

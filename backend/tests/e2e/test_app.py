"""End-to-end tests against the assembled FastAPI app via httpx ASGI transport.

These do NOT touch a real database: the lifespan migration step is overridden
to a no-op so the app boots even without Postgres. We assert on the parts of
the API that have no DB dependency (root, /health/live, security headers, CORS,
error handling).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def app_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Boot the app with migrations disabled so it works without a DB."""
    async def _noop_migrations() -> None:
        return None

    # Patch the migration runner before create_app() is called.
    import app.main as main_module

    monkeypatch.setattr(main_module, "_run_migrations", _noop_migrations)

    app = main_module.create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


pytestmark = pytest.mark.e2e


async def test_root_endpoint(app_client: AsyncClient) -> None:
    r = await app_client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] in {"ERP System", "erp-system"}
    assert body["status"] == "ok"


async def test_health_live(app_client: AsyncClient) -> None:
    r = await app_client.get("/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    names = {c["name"] for c in body["components"]}
    assert "process" in names


async def test_security_headers_present(app_client: AsyncClient) -> None:
    r = await app_client.get("/health/live")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    csp = r.headers.get("content-security-policy", "")
    assert "default-src" in csp


async def test_cors_preflight(app_client: AsyncClient) -> None:
    r = await app_client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") in ("http://localhost:5173", "*")


async def test_cors_headers_are_present_on_auth_errors(app_client: AsyncClient) -> None:
    """Expired/missing sessions must not be misreported as a CORS failure."""
    r = await app_client.get(
        "/api/v1/auth/me",
        headers={"Origin": "http://localhost:5173"},
    )
    assert r.status_code == 401
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.headers.get("access-control-allow-credentials") == "true"


async def test_unknown_route_returns_404(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/does-not-exist")
    assert r.status_code == 404


async def test_openapi_available_in_test(app_client: AsyncClient) -> None:
    r = await app_client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema
    assert "/health/live" in schema["paths"]

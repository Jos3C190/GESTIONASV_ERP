"""API surface checks for retaceo routes and DTOs."""

from __future__ import annotations

from app.main import create_app


def test_retaceo_routes_are_registered_in_openapi() -> None:
    app = create_app()
    inner = getattr(app, "app", app)
    paths = inner.openapi()["paths"]

    assert "/api/v1/retaceos" in paths
    assert "/api/v1/retaceos/{retaceo_id}" in paths
    assert "/api/v1/retaceos/{retaceo_id}/calculate" in paths
    assert "/api/v1/retaceos/{retaceo_id}/verify" in paths
    assert "/api/v1/retaceos/{retaceo_id}/cancel" in paths
    assert "/api/v1/retaceos/{retaceo_id}/close" in paths

"""Server-side access to Traccar shared by the tracking and fleet routers.

Visibility never depends on Traccar data: the ERP decides which devices a user
sees from ``fleet_vehicles.traccar_device_id`` and the user's branch scope. The
``erp*`` attributes written to Traccar only label devices and geofences there.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.application.tracking import TraccarUnavailableError, traccar_call
from app.core.config import settings

UNAVAILABLE = "El servidor GPS no está disponible."
NOT_CONFIGURED = "El servidor GPS no está configurado."


def traccar_credentials() -> tuple[str, str, str] | None:
    if settings.TRACCAR_URL and settings.TRACCAR_USER and settings.TRACCAR_PASSWORD:
        return settings.TRACCAR_URL, settings.TRACCAR_USER, settings.TRACCAR_PASSWORD
    return None


async def traccar(path: str, *, method: str = "GET", body: object | None = None) -> Any:
    """Call Traccar or fail with 409 (not configured) / 503 (unreachable)."""
    credentials = traccar_credentials()
    if credentials is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NOT_CONFIGURED)
    try:
        return await traccar_call(*credentials, path, method=method, body=body)
    except TraccarUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from exc

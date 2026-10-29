"""Live GPS positions, geofences and events from Traccar for the tracking module."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.company_access import require_company_access
from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.tracking import (
    GeofenceCreate,
    GeofenceOut,
    TrackingEventOut,
    TrackingSnapshotOut,
)
from app.application.tracking import (
    KNOTS_TO_KMH,
    TraccarUnavailableError,
    belongs_to_company,
    build_area,
    build_events,
    build_tracked_devices,
    fetch_traccar_snapshot,
    to_geofence,
    traccar_call,
)
from app.core.config import settings

router = APIRouter(prefix="/tracking", tags=["tracking"])

_UNAVAILABLE = "El servidor GPS no está disponible."


def _credentials() -> tuple[str, str, str] | None:
    if settings.TRACCAR_URL and settings.TRACCAR_USER and settings.TRACCAR_PASSWORD:
        return settings.TRACCAR_URL, settings.TRACCAR_USER, settings.TRACCAR_PASSWORD
    return None


def _require_credentials() -> tuple[str, str, str]:
    credentials = _credentials()
    if credentials is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "El servidor GPS no está configurado.")
    return credentials


async def _call(path: str, *, method: str = "GET", body: object | None = None) -> Any:
    try:
        return await traccar_call(*_require_credentials(), path, method=method, body=body)
    except TraccarUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc


async def _company_items(path: str, company_id: uuid.UUID) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = await _call(path) or []
    return [item for item in items if belongs_to_company(item, str(company_id))]


@router.get("/positions", response_model=TrackingSnapshotOut)
async def get_tracking_positions(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> TrackingSnapshotOut:
    await require_company_access(session, current, company_id)
    credentials = _credentials()
    if credentials is None:
        return TrackingSnapshotOut(configured=False, devices=[])
    try:
        devices, positions = await fetch_traccar_snapshot(*credentials)
    except TraccarUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc
    return TrackingSnapshotOut.model_validate(
        {"configured": True, "devices": build_tracked_devices(devices, positions, str(company_id))}
    )


@router.get("/geofences", response_model=list[GeofenceOut])
async def list_geofences(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> list[GeofenceOut]:
    await require_company_access(session, current, company_id)
    geofences = await _company_items("/api/geofences", company_id)
    return [
        GeofenceOut.model_validate(item)
        for item in (to_geofence(geofence) for geofence in geofences)
        if item is not None
    ]


@router.post(
    "/geofences",
    response_model=GeofenceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tracking:geofences"))],
)
async def create_geofence(
    body: GeofenceCreate,
    session: SessionDep,
    current: CurrentUser,
) -> GeofenceOut:
    await require_company_access(session, current, body.company_id)
    attributes: dict[str, object] = {"erpCompanyId": str(body.company_id)}
    if body.speed_limit_kmh is not None:
        # Traccar evalúa el exceso de velocidad dentro de la geocerca con este límite en nudos.
        attributes["speedLimit"] = round(body.speed_limit_kmh / KNOTS_TO_KMH, 2)
    created = await _call(
        "/api/geofences",
        method="POST",
        body={
            "name": body.name.strip(),
            "description": (body.description or "").strip(),
            "area": build_area(body.shape.model_dump()),
            "attributes": attributes,
        },
    )
    # Traccar solo genera eventos de geocerca para los dispositivos enlazados a ella.
    devices = await _company_items("/api/devices", body.company_id)
    await asyncio.gather(
        *(
            _call(
                "/api/permissions",
                method="POST",
                body={"deviceId": device["id"], "geofenceId": created["id"]},
            )
            for device in devices
        )
    )
    geofence = to_geofence(created)
    if geofence is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Traccar devolvió una geocerca inválida.")
    return GeofenceOut.model_validate(geofence)


@router.delete(
    "/geofences/{geofence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("tracking:geofences"))],
)
async def delete_geofence(
    geofence_id: int,
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> None:
    await require_company_access(session, current, company_id)
    owned = await _company_items("/api/geofences", company_id)
    if not any(item["id"] == geofence_id for item in owned):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Geocerca no encontrada.")
    await _call(f"/api/geofences/{geofence_id}", method="DELETE")


@router.get("/events", response_model=list[TrackingEventOut])
async def list_tracking_events(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    hours: int = Query(default=24, ge=1, le=168),
) -> list[TrackingEventOut]:
    await require_company_access(session, current, company_id)
    devices = await _company_items("/api/devices", company_id)
    if not devices:
        return []
    now = datetime.now(UTC)
    query = urlencode(
        [("deviceId", device["id"]) for device in devices]
        + [
            ("from", (now - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")),
            ("to", now.isoformat().replace("+00:00", "Z")),
        ]
    )
    events, geofences = await asyncio.gather(
        _call(f"/api/reports/events?{query}"),
        _company_items("/api/geofences", company_id),
    )
    events = events or []
    position_ids = sorted({event["positionId"] for event in events if event.get("positionId")})
    positions: list[dict[str, Any]] = []
    # Traccar acepta varios ?id= por consulta; se agrupan para no saturar la URL.
    for start in range(0, len(position_ids), 100):
        chunk = position_ids[start : start + 100]
        positions += (
            await _call(f"/api/positions?{urlencode([('id', pid) for pid in chunk])}") or []
        )
    return [
        TrackingEventOut.model_validate(item)
        for item in build_events(
            events,
            {device["id"]: device for device in devices},
            {geofence["id"]: str(geofence.get("name", "")) for geofence in geofences},
            {position["id"]: position for position in positions},
        )
    ]

"""Live GPS positions from Traccar for the tracking module."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.api.v1.company_access import require_company_access
from app.api.v1.deps import CurrentUser, SessionDep
from app.api.v1.schemas.tracking import TrackingSnapshotOut
from app.application.tracking import (
    TraccarUnavailableError,
    build_tracked_devices,
    fetch_traccar_snapshot,
)
from app.core.config import settings

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/positions", response_model=TrackingSnapshotOut)
async def get_tracking_positions(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> TrackingSnapshotOut:
    await require_company_access(session, current, company_id)
    if not (settings.TRACCAR_URL and settings.TRACCAR_USER and settings.TRACCAR_PASSWORD):
        return TrackingSnapshotOut(configured=False, devices=[])
    try:
        devices, positions = await fetch_traccar_snapshot(
            settings.TRACCAR_URL, settings.TRACCAR_USER, settings.TRACCAR_PASSWORD
        )
    except TraccarUnavailableError as exc:
        raise HTTPException(503, "El servidor GPS no está disponible.") from exc
    return TrackingSnapshotOut.model_validate(
        {"configured": True, "devices": build_tracked_devices(devices, positions, str(company_id))}
    )

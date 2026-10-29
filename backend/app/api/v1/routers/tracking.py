"""Live GPS positions, geofences and events from Traccar for the tracking module."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.orm import aliased

from app.api.v1.company_access import require_company_access
from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.tracking import (
    GeofenceCreate,
    GeofenceOut,
    TrackedTransferOut,
    TrackingEventOut,
    TrackingSnapshotOut,
    TransferTrackOut,
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
from app.application.tracking.transfers import build_transfer_progress, plan_route
from app.core.config import settings
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Warehouse

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


# ---------------- Traslados en tránsito ----------------

_ACTIVE_TRANSFER_STATUSES = ("in_transit", "incident")


def _transfer_query(company_id: uuid.UUID) -> Select[Any]:
    origin_wh, destination_wh = aliased(Warehouse), aliased(Warehouse)
    origin_br, destination_br = aliased(Branch), aliased(Branch)
    return (
        select(
            InventoryTransferModel,
            InventoryVehicleModel,
            origin_wh.name,
            origin_br.name,
            origin_br.latitude,
            origin_br.longitude,
            destination_wh.name,
            destination_br.name,
            destination_br.latitude,
            destination_br.longitude,
        )
        .join(origin_wh, origin_wh.id == InventoryTransferModel.origin_warehouse_id)
        .join(origin_br, origin_br.id == origin_wh.branch_id)
        .join(destination_wh, destination_wh.id == InventoryTransferModel.destination_warehouse_id)
        .join(destination_br, destination_br.id == destination_wh.branch_id)
        .outerjoin(
            InventoryVehicleModel, InventoryVehicleModel.id == InventoryTransferModel.vehicle_id
        )
        .where(InventoryTransferModel.company_id == company_id)
    )


def _place(warehouse: str, branch: str, lat: object, lng: object) -> dict[str, Any]:
    return {
        "warehouse_name": warehouse,
        "branch_name": branch,
        "latitude": float(lat) if lat is not None else None,  # type: ignore[arg-type]
        "longitude": float(lng) if lng is not None else None,  # type: ignore[arg-type]
    }


def _transfer_row(row: Any) -> dict[str, Any]:
    transfer, vehicle, o_wh, o_br, o_lat, o_lng, d_wh, d_br, d_lat, d_lng = row
    return {
        "id": transfer.id,
        "code": transfer.code,
        "status": transfer.status,
        "dispatched_at": transfer.dispatched_at,
        "vehicle_code": vehicle.code if vehicle else None,
        "vehicle_name": vehicle.name if vehicle else None,
        "origin": _place(o_wh, o_br, o_lat, o_lng),
        "destination": _place(d_wh, d_br, d_lat, d_lng),
    }


@router.get(
    "/transfers",
    response_model=list[TrackedTransferOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_tracked_transfers(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> list[TrackedTransferOut]:
    await require_company_access(session, current, company_id)
    rows = (
        await session.execute(
            _transfer_query(company_id)
            .where(InventoryTransferModel.status.in_(_ACTIVE_TRANSFER_STATUSES))
            .order_by(InventoryTransferModel.dispatched_at.desc().nulls_last())
            .limit(100)
        )
    ).all()
    return [TrackedTransferOut.model_validate(_transfer_row(row)) for row in rows]


def _matches_vehicle(device: dict[str, Any], vehicle_code: str) -> bool:
    code = vehicle_code.strip().lower()
    return code in {
        str(device.get("name", "")).strip().lower(),
        str(device.get("uniqueId", "")).strip().lower(),
    }


@router.get(
    "/transfers/{transfer_id}",
    response_model=TransferTrackOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_transfer_track(
    transfer_id: uuid.UUID,
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> TransferTrackOut:
    await require_company_access(session, current, company_id)
    row = (
        await session.execute(
            _transfer_query(company_id).where(InventoryTransferModel.id == transfer_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Traslado no encontrado.")
    data = _transfer_row(row)
    origin, destination = data["origin"], data["destination"]
    data.update(gps_configured=_credentials() is not None, device_found=False)
    if None in (
        origin["latitude"],
        origin["longitude"],
        destination["latitude"],
        destination["longitude"],
    ):
        # Sin coordenadas de sucursal no hay ruta que dibujar; se devuelve el traslado tal cual.
        return TransferTrackOut.model_validate(data)
    origin_point = (origin["longitude"], origin["latitude"])
    destination_point = (destination["longitude"], destination["latitude"])
    route = await plan_route(settings.OSRM_URL, origin_point, destination_point)
    data["route"] = route

    positions: list[dict[str, Any]] = []
    if data["gps_configured"] and data["vehicle_code"]:
        devices = await _company_items("/api/devices", company_id)
        device = next((d for d in devices if _matches_vehicle(d, data["vehicle_code"])), None)
        if device is not None:
            data["device_found"] = True
            now = datetime.now(UTC)
            start = data["dispatched_at"] or now - timedelta(hours=12)
            query = urlencode(
                {
                    "deviceId": device["id"],
                    "from": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                    "to": now.isoformat().replace("+00:00", "Z"),
                }
            )
            positions = await _call(f"/api/positions?{query}") or []
            if not positions:
                # Sin historial desde el despacho, al menos la última posición conocida.
                latest = (
                    await _call(f"/api/positions?{urlencode({'deviceId': device['id']})}") or []
                )
                positions = latest[-1:]
    data.update(
        build_transfer_progress(
            route=route,
            destination=destination_point,
            positions=positions,
            now=datetime.now(UTC),
        )
    )
    return TransferTrackOut.model_validate(data)

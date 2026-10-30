"""Live GPS positions, geofences and events from Traccar for the tracking module.

Every endpoint is bound to the request's authorised company and to the
branches the user may see (the same scope as Fleet): a branch user only sees
the GPS devices of its branch's vehicles, the geofences of its branch (plus
company-wide ones) and the transfers that leave from or arrive at it.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Select, or_, select

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import FleetScope, get_fleet_scope
from app.api.v1.schemas.tracking import (
    GeofenceCreate,
    GeofenceOut,
    SitesOut,
    TrackedTransferOut,
    TrackingAlertOut,
    TrackingAlertsOut,
    TrackingEventOut,
    TrackingSnapshotOut,
    TransferRouteOut,
    TransferTrackOut,
)
from app.api.v1.simulator import open_simulations, simulation_devices_since, tracking_device
from app.api.v1.site_sync import load_sites, run_site_sync, sync_if_stale, sync_state
from app.api.v1.traccar_access import UNAVAILABLE, traccar, traccar_credentials
from app.api.v1.transfer_tracking import (
    ACTIVE_TRANSFER_STATUSES,
    capture_track,
    compute_trip,
    stored_track,
    transfer_query,
    trip_context,
)
from app.application.fleet.views import build_vehicle_views
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.tracking import (
    KNOTS_TO_KMH,
    TraccarUnavailableError,
    build_area,
    build_events,
    build_tracked_devices,
    fetch_traccar_snapshot,
    to_geofence,
)
from app.application.tracking.devices import (
    BRANCH_ATTRIBUTE,
    COMPANY_ATTRIBUTE,
    geofence_branch,
    geofence_visible,
)
from app.application.tracking.sites import is_site_geofence
from app.application.tracking.transfers import (
    plan_route,
)
from app.core.config import settings
from app.core.exceptions import ConflictError
from app.infrastructure.models.fleet import (
    FleetVehicleModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.tracking import TrackingAlertModel
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/tracking", tags=["tracking"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
READ = [Depends(require_permission("tracking:read"))]
MANAGE_GEOFENCES = [Depends(require_permission("tracking:geofences"))]


async def _scope(
    request: Request, session: SessionDep, current: CurrentUser, checker: CheckPermissionUseCase
) -> FleetScope:
    return await get_fleet_scope(session, current, checker, effective_company_id(request))


async def _linked_vehicles(
    session: SessionDep, scope: FleetScope, branch_ids: list[uuid.UUID] | None
) -> list[FleetVehicleModel]:
    vehicles = await FleetRepository(session).all_vehicles(scope.company_id, branch_ids)
    return [vehicle for vehicle in vehicles if vehicle.status != "retired"]


# ---------------------------------------------------------------- positions


@router.get("/positions", response_model=TrackingSnapshotOut, dependencies=READ)
async def get_tracking_positions(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID | None = Query(None),
) -> TrackingSnapshotOut:
    scope = await _scope(request, session, current, checker)
    vehicles = await _linked_vehicles(session, scope, scope.list_filter(branch_id))
    counts = {
        "vehicles_total": len(vehicles),
        "vehicles_with_gps": sum(1 for vehicle in vehicles if vehicle.traccar_device_id),
    }
    # Con una sesión de simulación abierta, la unidad se lee de su GPS virtual.
    simulations = await open_simulations(session, scope.company_id, [v.id for v in vehicles])
    sources = {vehicle.id: tracking_device(vehicle, simulations) for vehicle in vehicles}
    linked = [vehicle for vehicle in vehicles if sources[vehicle.id][0] is not None]
    credentials = traccar_credentials()
    if credentials is None:
        return TrackingSnapshotOut(configured=False, devices=[], **counts)
    if not linked:
        return TrackingSnapshotOut(configured=True, devices=[], **counts)
    try:
        devices, positions = await fetch_traccar_snapshot(*credentials)
    except TraccarUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from exc
    views = {
        view["id"]: view
        for view in await build_vehicle_views(
            FleetRepository(session), scope.company_id, linked, today=datetime.now(UTC).date()
        )
    }
    by_device = {sources[vehicle.id][0]: vehicle for vehicle in linked}
    tracked = build_tracked_devices(
        [device for device in devices if device.get("id") in by_device], positions
    )
    for item in tracked:
        view = views[by_device[item["id"]].id]
        trip = view["current_transfer"]
        item["name"] = view["code"]
        item["simulated"] = sources[by_device[item["id"]].id][1]
        item["vehicle"] = {
            "id": view["id"],
            "code": view["code"],
            "plate": view["plate"],
            "kind": view["kind"],
            "brand": view["brand"],
            "model": view["model"],
            "branch_id": view["branch_id"],
            "branch_name": view["branch_name"],
            "operational_status": view["operational_status"],
            "driver_name": view["driver"]["name"] if view["driver"] else None,
            "transfer_code": trip["code"] if trip else None,
            "transfer_destination": trip["destination_branch"] if trip else None,
        }
    return TrackingSnapshotOut.model_validate({"configured": True, "devices": tracked, **counts})


# ---------------------------------------------------------------- geofences


async def _visible_geofences(scope: FleetScope) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = await traccar("/api/geofences") or []
    return [item for item in items if geofence_visible(item, scope)]


def _can_manage(scope: FleetScope, branch_id: uuid.UUID | None) -> bool:
    # Las geocercas de toda la empresa solo las administra quien ve todas las sucursales.
    return scope.all_branches if branch_id is None else scope.allows(branch_id)


async def _geofence_out(
    session: SessionDep, scope: FleetScope, items: list[dict[str, Any]]
) -> list[GeofenceOut]:
    branch_ids = [branch for item in items if (branch := geofence_branch(item)) is not None]
    names = await FleetRepository(session).branch_names(scope.company_id, branch_ids)
    result: list[GeofenceOut] = []
    for item in items:
        geofence = to_geofence(item)
        if geofence is None:
            continue
        branch = geofence_branch(item)
        system = is_site_geofence(item)
        geofence.update(
            branch_id=branch,
            branch_name=names.get(branch) if branch else None,
            can_manage=not system and _can_manage(scope, branch),
            system=system,
        )
        result.append(GeofenceOut.model_validate(geofence))
    return result


@router.get("/geofences", response_model=list[GeofenceOut], dependencies=READ)
async def list_geofences(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[GeofenceOut]:
    scope = await _scope(request, session, current, checker)
    await sync_if_stale(session, scope.company_id)
    return await _geofence_out(session, scope, await _visible_geofences(scope))


@router.post(
    "/geofences",
    response_model=GeofenceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=MANAGE_GEOFENCES,
)
async def create_geofence(
    body: GeofenceCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> GeofenceOut:
    scope = await _scope(request, session, current, checker)
    if body.branch_id is not None:
        scope.require_target(body.branch_id)
        if await FleetRepository(session).branch(scope.company_id, body.branch_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sucursal no encontrada.")
    elif not scope.all_branches:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Solo quien administra todas las sucursales puede crear geocercas de toda la empresa.",
        )
    attributes: dict[str, object] = {COMPANY_ATTRIBUTE: str(scope.company_id)}
    if body.branch_id is not None:
        attributes[BRANCH_ATTRIBUTE] = str(body.branch_id)
    if body.speed_limit_kmh is not None:
        # Traccar evalúa el exceso de velocidad dentro de la geocerca con este límite en nudos.
        attributes["speedLimit"] = round(body.speed_limit_kmh / KNOTS_TO_KMH, 2)
    created = await traccar(
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
    vehicles = await _linked_vehicles(
        session, scope, None if body.branch_id is None else [body.branch_id]
    )
    await asyncio.gather(
        *(
            traccar(
                "/api/permissions",
                method="POST",
                body={"deviceId": vehicle.traccar_device_id, "geofenceId": created["id"]},
            )
            for vehicle in vehicles
            if vehicle.traccar_device_id is not None
        ),
        *(
            traccar(
                "/api/permissions",
                method="POST",
                body={"deviceId": simulation.traccar_device_id, "geofenceId": created["id"]},
            )
            for simulation in (
                await open_simulations(session, scope.company_id, [v.id for v in vehicles])
            ).values()
        ),
    )
    result = await _geofence_out(session, scope, [created])
    if not result:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Traccar devolvió una geocerca inválida.")
    return result[0]


@router.delete(
    "/geofences/{geofence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=MANAGE_GEOFENCES,
)
async def delete_geofence(
    geofence_id: int,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> None:
    scope = await _scope(request, session, current, checker)
    target = next(
        (item for item in await _visible_geofences(scope) if item["id"] == geofence_id), None
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Geocerca no encontrada.")
    if is_site_geofence(target):
        raise ConflictError(
            "Esta geocerca representa una sucursal o almacén; se administra desde esos módulos.",
            code="system_geofence",
        )
    if not _can_manage(scope, geofence_branch(target)):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "No puede eliminar geocercas de toda la empresa."
        )
    await traccar(f"/api/geofences/{geofence_id}", method="DELETE")


# ---------------------------------------------------------------- sites


@router.get("/sites", response_model=SitesOut, dependencies=READ)
async def list_sites(
    request: Request,
    session: SessionDep,
) -> SitesOut:
    """Every operating branch and warehouse of the company, for all its branches to see."""
    company_id = effective_company_id(request)
    await sync_if_stale(session, company_id)
    sites, missing = await load_sites(session, company_id)
    return SitesOut.model_validate(
        {
            "sites": [asdict(site) for site in sites],
            "missing": missing,
            "sync": await sync_state(session, company_id),
        }
    )


@router.post("/sites/sync", response_model=SitesOut, dependencies=MANAGE_GEOFENCES)
async def sync_sites(request: Request, session: SessionDep) -> SitesOut:
    """Reconcile the automatic geofences now (e.g. after Traccar was down)."""
    company_id = effective_company_id(request)
    await run_site_sync(company_id)
    session.expire_all()
    sites, missing = await load_sites(session, company_id)
    return SitesOut.model_validate(
        {
            "sites": [asdict(site) for site in sites],
            "missing": missing,
            "sync": await sync_state(session, company_id),
        }
    )


# ---------------------------------------------------------------- events


@router.get("/events", response_model=list[TrackingEventOut], dependencies=READ)
async def list_tracking_events(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    hours: int = Query(default=24, ge=1, le=168),
    branch_id: uuid.UUID | None = Query(None),
) -> list[TrackingEventOut]:
    scope = await _scope(request, session, current, checker)
    vehicles = await _linked_vehicles(session, scope, scope.list_filter(branch_id))
    by_device = {v.traccar_device_id: v for v in vehicles if v.traccar_device_id is not None}
    now = datetime.now(UTC)
    # Los eventos de GPS virtuales (abiertos o usados en la ventana) también se muestran.
    in_scope = {vehicle.id: vehicle for vehicle in vehicles}
    simulated_devices = {
        device_id: in_scope[vehicle_id]
        for device_id, vehicle_id in (
            await simulation_devices_since(session, scope.company_id, now - timedelta(hours=hours))
        ).items()
        if vehicle_id in in_scope
    }
    by_device.update(simulated_devices)
    if not by_device or traccar_credentials() is None:
        return []
    query = urlencode(
        [("deviceId", device_id) for device_id in by_device]
        + [
            ("from", (now - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")),
            ("to", now.isoformat().replace("+00:00", "Z")),
        ]
    )
    events, geofences = await asyncio.gather(
        traccar(f"/api/reports/events?{query}"), _visible_geofences(scope)
    )
    events = events or []
    position_ids = sorted({event["positionId"] for event in events if event.get("positionId")})
    positions: list[dict[str, Any]] = []
    # Traccar acepta varios ?id= por consulta; se agrupan para no saturar la URL.
    for start in range(0, len(position_ids), 100):
        chunk = position_ids[start : start + 100]
        positions += (
            await traccar(f"/api/positions?{urlencode([('id', pid) for pid in chunk])}") or []
        )
    devices = {
        device_id: {
            "id": device_id,
            "name": vehicle.code,
            "uniqueId": vehicle.gps_device_unique_id
            if device_id not in simulated_devices
            else f"sim:{vehicle.code}",
        }
        for device_id, vehicle in by_device.items()
    }
    system_ids = {geofence["id"] for geofence in geofences if is_site_geofence(geofence)}
    return [
        TrackingEventOut.model_validate(
            {
                **item,
                "geofence_system": item.get("geofence_id") in system_ids,
                "simulated": item.get("device_id") in simulated_devices,
            }
        )
        for item in build_events(
            events,
            devices,
            {geofence["id"]: str(geofence.get("name", "")) for geofence in geofences},
            {position["id"]: position for position in positions},
        )
    ]


# ---------------------------------------------------------------- transfers in transit


def _scoped_transfers(scope: FleetScope) -> Select[Any]:
    return transfer_query(
        scope.company_id, None if scope.all_branches else sorted(scope.branch_ids)
    )


@router.get("/transfers", response_model=list[TrackedTransferOut], dependencies=READ)
async def list_tracked_transfers(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[TrackedTransferOut]:
    scope = await _scope(request, session, current, checker)
    rows = (
        await session.execute(
            _scoped_transfers(scope)
            .where(InventoryTransferModel.status.in_(ACTIVE_TRANSFER_STATUSES))
            .order_by(InventoryTransferModel.dispatched_at.desc().nulls_last())
            .limit(100)
        )
    ).all()
    return [TrackedTransferOut.model_validate(trip_context(row).data) for row in rows]


@router.get("/transfers/{transfer_id}", response_model=TransferTrackOut, dependencies=READ)
async def get_transfer_track(
    transfer_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> TransferTrackOut:
    scope = await _scope(request, session, current, checker)
    row = (
        await session.execute(
            _scoped_transfers(scope).where(InventoryTransferModel.id == transfer_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Traslado no encontrado.")
    ctx = trip_context(row)
    if ctx.final and await stored_track(session, ctx.transfer.id) is None:
        # Si la captura al recibir falló (Traccar caído), se intenta de nuevo al consultarlo.
        with suppress(HTTPException):
            await capture_track(session, ctx)
    data, _ = await compute_trip(session, ctx)
    data["alerts"] = [
        _alert_out(alert, data)
        for alert in await session.scalars(
            select(TrackingAlertModel)
            .where(
                TrackingAlertModel.transfer_id == transfer_id,
                TrackingAlertModel.resolved_at.is_(None),
            )
            .order_by(TrackingAlertModel.opened_at.desc())
        )
    ]
    return TransferTrackOut.model_validate(data)


# ---------------------------------------------------------------- alerts


def _alert_out(alert: TrackingAlertModel, trip: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": alert.id,
        "transfer_id": alert.transfer_id,
        "transfer_code": (trip or {}).get("code"),
        "vehicle_code": (trip or {}).get("vehicle_code"),
        "kind": alert.kind,
        "severity": alert.severity,
        "message": alert.message,
        "details": alert.details,
        "opened_at": alert.opened_at,
        "last_seen_at": alert.last_seen_at,
        "resolved_at": alert.resolved_at,
        "acknowledged_at": alert.acknowledged_at,
        "simulated": alert.simulated,
    }


def _alert_scope(scope: FleetScope) -> list[Any]:
    conditions: list[Any] = [TrackingAlertModel.company_id == scope.company_id]
    if not scope.all_branches:
        branches = sorted(scope.branch_ids)
        conditions.append(
            or_(
                TrackingAlertModel.origin_branch_id.in_(branches),
                TrackingAlertModel.destination_branch_id.in_(branches),
            )
        )
    return conditions


@router.get("/alerts", response_model=TrackingAlertsOut, dependencies=READ)
async def list_tracking_alerts(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    state: str = Query("open", pattern="^(open|recent)$"),
) -> TrackingAlertsOut:
    """Alerts of the transfers leaving from or arriving at the user's branches."""
    scope = await _scope(request, session, current, checker)
    conditions = _alert_scope(scope)
    if state == "open":
        conditions.append(TrackingAlertModel.resolved_at.is_(None))
    else:
        conditions.append(TrackingAlertModel.opened_at >= datetime.now(UTC) - timedelta(days=7))
    rows = (
        await session.execute(
            select(
                TrackingAlertModel,
                InventoryTransferModel.code,
                InventoryVehicleModel.code,
                FleetVehicleModel.code,
            )
            .join(
                InventoryTransferModel, InventoryTransferModel.id == TrackingAlertModel.transfer_id
            )
            .outerjoin(
                InventoryVehicleModel,
                InventoryVehicleModel.id == InventoryTransferModel.vehicle_id,
            )
            .outerjoin(
                FleetVehicleModel,
                (FleetVehicleModel.company_id == InventoryTransferModel.company_id)
                & (FleetVehicleModel.inventory_vehicle_id == InventoryTransferModel.vehicle_id),
            )
            .where(*conditions)
            .execution_options(include_deleted=True)
            .order_by(TrackingAlertModel.opened_at.desc())
            .limit(200)
        )
    ).all()
    items = [
        _alert_out(alert, {"code": code, "vehicle_code": fleet_code or vehicle_code})
        for alert, code, vehicle_code, fleet_code in rows
    ]
    unacknowledged = sum(
        1 for item in items if item["resolved_at"] is None and item["acknowledged_at"] is None
    )
    return TrackingAlertsOut.model_validate(
        {
            "items": items,
            "unacknowledged": unacknowledged,
            "monitor_active": traccar_credentials() is not None,
        }
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=TrackingAlertOut, dependencies=READ)
async def acknowledge_tracking_alert(
    alert_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> TrackingAlertOut:
    """Mark an alert as seen; it stays open until its condition clears."""
    scope = await _scope(request, session, current, checker)
    alert = await session.scalar(
        select(TrackingAlertModel)
        .where(TrackingAlertModel.id == alert_id, *_alert_scope(scope))
        .with_for_update()
    )
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta no encontrada.")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = current.id
        await session.flush()
    return TrackingAlertOut.model_validate(_alert_out(alert))


@router.get("/route", response_model=TransferRouteOut, dependencies=READ)
async def get_driving_route(
    from_lng: float = Query(ge=-180, le=180),
    from_lat: float = Query(ge=-90, le=90),
    to_lng: float = Query(ge=-180, le=180),
    to_lat: float = Query(ge=-90, le=90),
) -> TransferRouteOut:
    """Driving route between two points."""
    route = await plan_route(settings.OSRM_URL, (from_lng, from_lat), (to_lng, to_lat))
    return TransferRouteOut.model_validate(route)

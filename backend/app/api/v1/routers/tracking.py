"""Live GPS positions, geofences and events from Traccar for the tracking module.

Every endpoint is bound to the request's authorised company and to the
branches the user may see (the same scope as Fleet): a branch user only sees
the GPS devices of its branch's vehicles, the geofences of its branch (plus
company-wide ones) and the transfers that leave from or arrive at it.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import aliased

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
    TrackingEventOut,
    TrackingSnapshotOut,
    TransferRouteOut,
    TransferTrackOut,
)
from app.api.v1.site_sync import load_sites, run_site_sync, sync_if_stale, sync_state
from app.api.v1.traccar_access import UNAVAILABLE, traccar, traccar_credentials
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
    build_transfer_progress,
    match_trail,
    plan_route,
    raw_trail,
    resolve_active_route,
)
from app.core.config import settings
from app.core.exceptions import ConflictError
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Warehouse
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
    linked = [vehicle for vehicle in vehicles if vehicle.traccar_device_id is not None]
    counts = {"vehicles_total": len(vehicles), "vehicles_with_gps": len(linked)}
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
    by_device = {vehicle.traccar_device_id: vehicle for vehicle in linked}
    tracked = build_tracked_devices(
        [device for device in devices if device.get("id") in by_device], positions
    )
    for item in tracked:
        view = views[by_device[item["id"]].id]
        trip = view["current_transfer"]
        item["name"] = view["code"]
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
        )
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
    if not by_device or traccar_credentials() is None:
        return []
    now = datetime.now(UTC)
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
        positions += await traccar(f"/api/positions?{urlencode([('id', pid) for pid in chunk])}") or []
    devices = {
        device_id: {"id": device_id, "name": vehicle.code, "uniqueId": vehicle.gps_device_unique_id}
        for device_id, vehicle in by_device.items()
    }
    system_ids = {geofence["id"] for geofence in geofences if is_site_geofence(geofence)}
    return [
        TrackingEventOut.model_validate(
            {**item, "geofence_system": item.get("geofence_id") in system_ids}
        )
        for item in build_events(
            events,
            devices,
            {geofence["id"]: str(geofence.get("name", "")) for geofence in geofences},
            {position["id"]: position for position in positions},
        )
    ]


# ---------------------------------------------------------------- transfers in transit

_ACTIVE_TRANSFER_STATUSES = ("in_transit", "incident")


def _transfer_query(scope: FleetScope) -> Select[Any]:
    origin_wh, destination_wh = aliased(Warehouse), aliased(Warehouse)
    origin_br, destination_br = aliased(Branch), aliased(Branch)
    statement = (
        select(
            InventoryTransferModel,
            InventoryVehicleModel,
            FleetVehicleModel,
            Employee.first_name,
            Employee.last_name,
            origin_wh.name,
            origin_br.name,
            func.coalesce(origin_wh.latitude, origin_br.latitude),
            func.coalesce(origin_wh.longitude, origin_br.longitude),
            destination_wh.name,
            destination_br.name,
            func.coalesce(destination_wh.latitude, destination_br.latitude),
            func.coalesce(destination_wh.longitude, destination_br.longitude),
            func.coalesce(destination_wh.geofence_radius_m, destination_br.geofence_radius_m),
        )
        .join(origin_wh, origin_wh.id == InventoryTransferModel.origin_warehouse_id)
        .join(origin_br, origin_br.id == origin_wh.branch_id)
        .join(destination_wh, destination_wh.id == InventoryTransferModel.destination_warehouse_id)
        .join(destination_br, destination_br.id == destination_wh.branch_id)
        .outerjoin(
            InventoryVehicleModel, InventoryVehicleModel.id == InventoryTransferModel.vehicle_id
        )
        .outerjoin(
            FleetVehicleModel,
            (FleetVehicleModel.company_id == InventoryTransferModel.company_id)
            & (FleetVehicleModel.inventory_vehicle_id == InventoryTransferModel.vehicle_id),
        )
        .outerjoin(DriverModel, DriverModel.id == InventoryTransferModel.driver_id)
        .outerjoin(Employee, Employee.id == DriverModel.employee_id)
        .where(InventoryTransferModel.company_id == scope.company_id)
        .execution_options(include_deleted=True)
    )
    if not scope.all_branches:
        branches = sorted(scope.branch_ids)
        statement = statement.where(
            or_(origin_br.id.in_(branches), destination_br.id.in_(branches))
        )
    return statement


def _place(warehouse: str, branch: str, lat: object, lng: object) -> dict[str, Any]:
    return {
        "warehouse_name": warehouse,
        "branch_name": branch,
        "latitude": float(lat) if lat is not None else None,  # type: ignore[arg-type]
        "longitude": float(lng) if lng is not None else None,  # type: ignore[arg-type]
    }


def _transfer_row(row: Any) -> tuple[dict[str, Any], FleetVehicleModel | None]:
    (
        transfer,
        vehicle,
        fleet,
        first,
        last,
        o_wh,
        o_br,
        o_lat,
        o_lng,
        d_wh,
        d_br,
        d_lat,
        d_lng,
        d_radius,
    ) = row
    data = {
        "id": transfer.id,
        "code": transfer.code,
        "status": transfer.status,
        "dispatched_at": transfer.dispatched_at,
        "vehicle_code": fleet.code if fleet else (vehicle.code if vehicle else None),
        "vehicle_name": f"{fleet.brand} {fleet.model}" if fleet else (vehicle.name if vehicle else None),
        "vehicle_plate": fleet.plate if fleet else None,
        "driver_name": f"{first} {last}".strip() if first else None,
        "origin": _place(o_wh, o_br, o_lat, o_lng),
        "destination": _place(d_wh, d_br, d_lat, d_lng),
        "arrival_radius_m": d_radius,
    }
    return data, fleet


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
            _transfer_query(scope)
            .where(InventoryTransferModel.status.in_(_ACTIVE_TRANSFER_STATUSES))
            .order_by(InventoryTransferModel.dispatched_at.desc().nulls_last())
            .limit(100)
        )
    ).all()
    return [TrackedTransferOut.model_validate(_transfer_row(row)[0]) for row in rows]


async def _device_positions(device_id: int, since: datetime | None) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    start = since or now - timedelta(hours=12)
    query = urlencode(
        {
            "deviceId": device_id,
            "from": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "to": now.isoformat().replace("+00:00", "Z"),
        }
    )
    positions: list[dict[str, Any]] = await traccar(f"/api/positions?{query}") or []
    if positions:
        return positions
    # Sin historial desde el despacho, al menos la última posición conocida.
    latest: list[dict[str, Any]] = (
        await traccar(f"/api/positions?{urlencode({'deviceId': device_id})}") or []
    )
    return latest[-1:]


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
        await session.execute(_transfer_query(scope).where(InventoryTransferModel.id == transfer_id))
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Traslado no encontrado.")
    data, fleet = _transfer_row(row)
    arrival_radius_m = data.pop("arrival_radius_m")
    origin, destination = data["origin"], data["destination"]
    data.update(gps_configured=traccar_credentials() is not None, device_found=False)
    if None in (
        origin["latitude"],
        origin["longitude"],
        destination["latitude"],
        destination["longitude"],
    ):
        # Sin coordenadas de origen o destino no hay ruta que dibujar; se devuelve tal cual.
        return TransferTrackOut.model_validate(data)
    origin_point = (origin["longitude"], origin["latitude"])
    destination_point = (destination["longitude"], destination["latitude"])
    route = await plan_route(settings.OSRM_URL, origin_point, destination_point)
    data["route"] = route

    positions: list[dict[str, Any]] = []
    if data["gps_configured"] and fleet is not None and fleet.traccar_device_id is not None:
        data["device_found"] = True
        positions = await _device_positions(fleet.traccar_device_id, data["dispatched_at"])
    trail, trail_matched = await match_trail(
        settings.OSRM_URL, str(transfer_id), raw_trail(positions)
    )
    active_route, rerouted, deviation = route, False, None
    if positions:
        vehicle_at = raw_trail(positions)[-1]
        active_route, rerouted, deviation = await resolve_active_route(
            settings.OSRM_URL, str(transfer_id), route, destination_point, vehicle_at
        )
    data.update(
        build_transfer_progress(
            route=route,
            destination=destination_point,
            positions=positions,
            now=datetime.now(UTC),
            trail=trail,
            active_route=active_route,
            rerouted=rerouted,
            deviation_m=deviation,
            arrival_radius_m=arrival_radius_m,
        ),
        trail_matched=trail_matched,
    )
    return TransferTrackOut.model_validate(data)


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

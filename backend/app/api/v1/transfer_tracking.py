"""Trip of a transfer: route, GPS trail, progress, stored evidence and alerts.

Shared by the tracking router (what users see) and the tracking monitor (what
raises alerts while nobody is looking). The trail window is always
``dispatched_at → received_at`` (or now while in transit); once a transfer is
closed its trail is copied into the ERP and served from there.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.v1.after_commit import run_after_commit
from app.api.v1.traccar_access import traccar, traccar_credentials
from app.application.tracking.alerts import Condition, TripSnapshot
from app.application.tracking.trails import (
    compact_points,
    fixes,
    positions_from_points,
    trail_stats,
)
from app.application.tracking.transfers import (
    build_transfer_progress,
    match_trail,
    plan_route,
    raw_trail,
    resolve_active_route,
)
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import DriverModel, FleetVehicleModel
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.tracking import (
    TrackingAlertModel,
    TrackingSimulationModel,
    TransferTrackModel,
)

logger = logging.getLogger(__name__)

ACTIVE_TRANSFER_STATUSES = ("in_transit", "incident")
#: Closed after the trip: their trail ends at reception and is stored by the ERP.
FINAL_TRANSFER_STATUSES = ("received", "closed_with_adjustment")
#: Without a recorded reception time, a trail is never read beyond this.
MAX_TRIP = timedelta(days=3)


@dataclass(slots=True)
class TripContext:
    transfer: InventoryTransferModel
    fleet: FleetVehicleModel | None
    data: dict[str, Any]
    origin_branch_id: uuid.UUID
    destination_branch_id: uuid.UUID
    arrival_radius_m: float | None
    #: GPS read for the trip: the simulator's virtual device while a session is open.
    device_id: int | None = None
    simulated: bool = False

    @property
    def final(self) -> bool:
        return self.transfer.status in FINAL_TRANSFER_STATUSES

    @property
    def window(self) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        start = self.transfer.dispatched_at or now - timedelta(hours=12)
        end = (self.transfer.received_at or min(now, start + MAX_TRIP)) if self.final else now
        return start, max(end, start)


def transfer_query(company_id: uuid.UUID, branch_ids: list[uuid.UUID] | None) -> Select[Any]:
    """Transfers of the company; ``branch_ids`` keeps those leaving from or arriving at them."""
    origin_wh, destination_wh = aliased(Warehouse), aliased(Warehouse)
    origin_br, destination_br = aliased(Branch), aliased(Branch)
    simulation = aliased(TrackingSimulationModel)
    statement = (
        select(
            InventoryTransferModel,
            InventoryVehicleModel,
            FleetVehicleModel,
            Employee.first_name,
            Employee.last_name,
            origin_wh.name,
            origin_br.name,
            # Un almacén en otro edificio usa sus coordenadas; si no, las de su sucursal.
            func.coalesce(origin_wh.latitude, origin_br.latitude),
            func.coalesce(origin_wh.longitude, origin_br.longitude),
            destination_wh.name,
            destination_br.name,
            func.coalesce(destination_wh.latitude, destination_br.latitude),
            func.coalesce(destination_wh.longitude, destination_br.longitude),
            func.coalesce(destination_wh.geofence_radius_m, destination_br.geofence_radius_m),
            origin_br.id,
            destination_br.id,
            simulation.traccar_device_id,
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
        .outerjoin(
            simulation,
            (simulation.vehicle_id == FleetVehicleModel.id) & (simulation.state != "ended"),
        )
        .outerjoin(DriverModel, DriverModel.id == InventoryTransferModel.driver_id)
        .outerjoin(Employee, Employee.id == DriverModel.employee_id)
        .where(InventoryTransferModel.company_id == company_id)
        .execution_options(include_deleted=True)
    )
    if branch_ids is not None:
        statement = statement.where(
            or_(origin_br.id.in_(branch_ids), destination_br.id.in_(branch_ids))
        )
    return statement


def _place(warehouse: str, branch: str, lat: object, lng: object) -> dict[str, Any]:
    return {
        "warehouse_name": warehouse,
        "branch_name": branch,
        "latitude": float(lat) if lat is not None else None,  # type: ignore[arg-type]
        "longitude": float(lng) if lng is not None else None,  # type: ignore[arg-type]
    }


def trip_context(row: Any) -> TripContext:
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
        origin_branch_id,
        destination_branch_id,
        simulation_device,
    ) = row
    data = {
        "id": transfer.id,
        "code": transfer.code,
        "status": transfer.status,
        "dispatched_at": transfer.dispatched_at,
        "received_at": transfer.received_at,
        "vehicle_code": fleet.code if fleet else (vehicle.code if vehicle else None),
        "vehicle_name": f"{fleet.brand} {fleet.model}"
        if fleet
        else (vehicle.name if vehicle else None),
        "vehicle_plate": fleet.plate if fleet else None,
        "driver_name": f"{first} {last}".strip() if first else None,
        "origin": _place(o_wh, o_br, o_lat, o_lng),
        "destination": _place(d_wh, d_br, d_lat, d_lng),
    }
    simulated = simulation_device is not None and settings.simulator_enabled
    data["simulated"] = simulated
    return TripContext(
        transfer=transfer,
        fleet=fleet,
        data=data,
        origin_branch_id=origin_branch_id,
        destination_branch_id=destination_branch_id,
        arrival_radius_m=float(d_radius) if d_radius is not None else None,
        device_id=simulation_device
        if simulated
        else (fleet.traccar_device_id if fleet is not None else None),
        simulated=simulated,
    )


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def device_positions(
    device_id: int, start: datetime, end: datetime, *, live: bool
) -> list[dict[str, Any]]:
    """Positions of the trip window; while live, at least the latest known one."""
    query = urlencode({"deviceId": device_id, "from": _iso(start), "to": _iso(end)})
    positions: list[dict[str, Any]] = await traccar(f"/api/positions?{query}") or []
    if positions or not live:
        return positions
    latest: list[dict[str, Any]] = (
        await traccar(f"/api/positions?{urlencode({'deviceId': device_id})}") or []
    )
    return latest[-1:]


async def stored_track(session: AsyncSession, transfer_id: uuid.UUID) -> TransferTrackModel | None:
    return await session.get(TransferTrackModel, transfer_id)


def _last_position(positions: list[dict[str, Any]]) -> dict[str, Any] | None:
    located = [p for p in positions if p.get("latitude") is not None]
    if not located:
        return None
    last = located[-1]
    fix = fixes([last])
    return {
        "latitude": float(last["latitude"]),
        "longitude": float(last["longitude"]),
        "speed_kmh": round(fix[0].speed_kmh, 1) if fix else 0.0,
        "course": float(last.get("course") or 0),
        "fix_time": fix[0].at if fix else None,
    }


async def compute_trip(session: AsyncSession, ctx: TripContext) -> tuple[dict[str, Any], list[Any]]:
    """The tracking view of a transfer and the raw positions it was built from."""
    data = dict(ctx.data)
    origin, destination = data["origin"], data["destination"]
    stored = await stored_track(session, ctx.transfer.id) if ctx.final else None
    device_id = ctx.device_id
    data.update(
        gps_configured=traccar_credentials() is not None,
        device_found=stored is not None or device_id is not None,
        track_stored=stored is not None,
        simulated=stored.simulated if stored is not None else ctx.simulated,
    )
    positions: list[dict[str, Any]] = []
    trail: list[Any] | None = None
    trail_matched = False
    if stored is not None:
        positions = positions_from_points(stored.points)
        trail = [tuple(point) for point in stored.matched] or None
        trail_matched = stored.trail_matched
    elif data["gps_configured"] and device_id is not None:
        start, end = ctx.window
        positions = await device_positions(device_id, start, end, live=not ctx.final)
    if trail is None:
        trail, trail_matched = await match_trail(
            settings.OSRM_URL, str(ctx.transfer.id), raw_trail(positions)
        )
    if None in (
        origin["latitude"],
        origin["longitude"],
        destination["latitude"],
        destination["longitude"],
    ):
        # Sin coordenadas de origen o destino no hay ruta ni avance, pero sí el recorrido
        # y la última posición: el monitor sigue vigilando el viaje.
        data.update(
            trail=[list(point) for point in trail],
            trail_matched=trail_matched,
            position=_last_position(positions),
            arrived=ctx.final,
        )
        return data, positions
    origin_point = (origin["longitude"], origin["latitude"])
    destination_point = (destination["longitude"], destination["latitude"])
    route = await plan_route(settings.OSRM_URL, origin_point, destination_point)
    data["route"] = route

    active_route, rerouted, deviation = route, False, None
    if positions and not ctx.final:
        vehicle_at = raw_trail(positions)[-1]
        active_route, rerouted, deviation = await resolve_active_route(
            settings.OSRM_URL, str(ctx.transfer.id), route, destination_point, vehicle_at
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
            arrival_radius_m=ctx.arrival_radius_m,
        ),
        trail_matched=trail_matched,
    )
    if ctx.final:
        # Un traslado cerrado ya llegó: no hay ruta pendiente ni hora estimada.
        data.update(arrived=True, eta=None, remaining_m=0, remaining_route=[], off_route=False)
    return data, positions


async def capture_track(session: AsyncSession, ctx: TripContext) -> TransferTrackModel | None:
    """Copy a closed transfer's trail into the ERP (idempotent)."""
    if not ctx.final or ctx.transfer.dispatched_at is None:
        return None
    existing = await stored_track(session, ctx.transfer.id)
    if existing is not None:
        return existing
    device_id = ctx.device_id
    if device_id is None or traccar_credentials() is None:
        return None
    start, end = ctx.window
    positions = await device_positions(device_id, start, end, live=False)
    points = compact_points(positions)
    matched, trail_matched = await match_trail(
        settings.OSRM_URL, str(ctx.transfer.id), raw_trail(positions)
    )
    distance, top_speed = trail_stats(points)
    track = TransferTrackModel(
        transfer_id=ctx.transfer.id,
        company_id=ctx.transfer.company_id,
        traccar_device_id=device_id,
        started_at=start,
        ended_at=end,
        points=points,
        matched=[list(point) for point in matched],
        trail_matched=trail_matched,
        point_count=len(points),
        distance_m=distance,
        max_speed_kmh=top_speed,
        simulated=ctx.simulated,
    )
    session.add(track)
    await session.flush()
    return track


# ---------------------------------------------------------------- alerts


def trip_snapshot(
    ctx: TripContext,
    data: dict[str, Any],
    positions: list[dict[str, Any]],
    sites: list[tuple[float, float, float]],
) -> TripSnapshot:
    route = data.get("route") or {}
    eta = data.get("eta")
    return TripSnapshot(
        now=datetime.now(UTC),
        dispatched_at=ctx.transfer.dispatched_at,
        destination_name=ctx.data["destination"]["warehouse_name"],
        gps_linked=ctx.device_id is not None,
        fixes=fixes(positions),
        planned_duration_s=route.get("duration_s"),
        eta=eta if isinstance(eta, datetime) else None,
        arrived=bool(data.get("arrived")),
        off_route=bool(data.get("off_route")),
        off_route_m=float(data.get("off_route_m") or 0),
        sites=sites,
    )


async def apply_conditions(
    session: AsyncSession, ctx: TripContext, conditions: list[Condition]
) -> None:
    """Open, refresh or resolve the transfer's alerts to match ``conditions``."""
    now = datetime.now(UTC)
    current = {
        alert.kind: alert
        for alert in await session.scalars(
            select(TrackingAlertModel)
            .where(
                TrackingAlertModel.transfer_id == ctx.transfer.id,
                TrackingAlertModel.resolved_at.is_(None),
            )
            .with_for_update()
        )
    }
    wanted = {condition.kind: condition for condition in conditions}
    for kind, alert in list(current.items()):
        # Una alerta simulada nunca continúa como real (ni al revés): se cierra y se abre otra.
        if kind not in wanted or alert.simulated != ctx.simulated:
            alert.resolved_at = now
            current.pop(kind)
    await session.flush()
    for kind, condition in wanted.items():
        existing = current.get(kind)
        if existing is None:
            session.add(
                TrackingAlertModel(
                    company_id=ctx.transfer.company_id,
                    transfer_id=ctx.transfer.id,
                    origin_branch_id=ctx.origin_branch_id,
                    destination_branch_id=ctx.destination_branch_id,
                    kind=kind,
                    severity=condition.severity,
                    message=condition.message,
                    details=condition.details,
                    opened_at=now,
                    last_seen_at=now,
                    simulated=ctx.simulated,
                )
            )
        else:
            existing.severity = condition.severity
            existing.message = condition.message
            existing.details = condition.details
            existing.last_seen_at = now
    await session.flush()


async def close_alerts(session: AsyncSession, transfer_id: uuid.UUID) -> None:
    """A closed or cancelled transfer has nothing left to watch."""
    now = datetime.now(UTC)
    for alert in await session.scalars(
        select(TrackingAlertModel).where(
            TrackingAlertModel.transfer_id == transfer_id,
            TrackingAlertModel.resolved_at.is_(None),
        )
    ):
        alert.resolved_at = now
    await session.flush()


async def archive_trip(company_id: uuid.UUID, transfer_id: uuid.UUID) -> None:
    """After a transfer closes: store its trail and resolve its alerts (own session)."""
    async with async_session_factory() as session:
        row = (
            await session.execute(
                transfer_query(company_id, None).where(InventoryTransferModel.id == transfer_id)
            )
        ).first()
        if row is None:
            return
        ctx = trip_context(row)
        if ctx.transfer.status in ACTIVE_TRANSFER_STATUSES:
            return
        await close_alerts(session, transfer_id)
        try:
            await capture_track(session, ctx)
        except HTTPException as exc:
            # El monitor y la consulta del traslado reintentan la copia más tarde.
            logger.warning(
                "transfer_track_capture_failed transfer_id=%s %s", transfer_id, exc.detail
            )
        await session.commit()


def archive_trip_on_commit(
    session: AsyncSession, company_id: uuid.UUID, transfer_id: uuid.UUID
) -> None:
    run_after_commit(session, lambda: archive_trip(company_id, transfer_id))


__all__ = [
    "ACTIVE_TRANSFER_STATUSES",
    "FINAL_TRANSFER_STATUSES",
    "TripContext",
    "apply_conditions",
    "archive_trip",
    "archive_trip_on_commit",
    "capture_track",
    "close_alerts",
    "compute_trip",
    "device_positions",
    "stored_track",
    "transfer_query",
    "trip_context",
    "trip_snapshot",
]

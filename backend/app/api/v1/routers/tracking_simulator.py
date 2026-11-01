"""Tracking simulator: drive virtual GPS devices to test tracking end to end.

Only available when ``TRACKING_SIMULATOR_ENABLED`` is on and never in
production. A session stands in for one vehicle of the user's branch scope:
either following a route on its own (a transfer's trip or points on the map)
or driven live with the joystick. Reports reach Traccar over OsmAnd like a
driver's phone, so geofence events, alerts and trails are the real ones,
marked as simulated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import FleetScope, get_fleet_scope
from app.api.v1.schemas.tracking import (
    SimulationControl,
    SimulationCreate,
    SimulationDrive,
    SimulationDriveOut,
    SimulationOut,
    SimulatorOut,
)
from app.api.v1.simulator import (
    ReportError,
    apply_position,
    end_simulation,
    ensure_virtual_device,
    open_simulations,
    send_report,
    simulator_enabled,
)
from app.api.v1.traccar_access import traccar_credentials
from app.api.v1.transfer_tracking import (
    ACTIVE_TRANSFER_STATUSES,
    transfer_query,
    trip_context,
)
from app.application.audit.audit_service import AuditService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.tracking.simulation import (
    detour_waypoint,
    path_length,
    plausible_drive,
    point_at,
)
from app.application.tracking.transfers import (
    LngLat,
    distance_m,
    downsample,
    nearest_road,
    plan_path,
)
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.tracking import TrackingSimulationModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/tracking/simulator", tags=["tracking"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
READ = [Depends(require_permission("tracking:read"))]
SIMULATE = [Depends(require_permission("tracking:simulate"))]

#: Default length of the "long stop" and "signal loss" actions: enough to raise the alerts.
DEFAULT_STOP_MINUTES = 25
DEFAULT_SIGNAL_MINUTES = 12
#: Joystick reports closer than this are kept but not forwarded to Traccar.
DRIVE_REPORT_S = 0.9
MIN_ROUTE_POINTS = 2
#: Closer than this the unit is already at its starting point.
AT_START_M = 30


def _require_enabled() -> None:
    if not simulator_enabled():
        raise NotFoundError("El simulador no está habilitado.", code="simulator_disabled")
    if traccar_credentials() is None:
        raise ConflictError("El servidor GPS no está configurado.", code="gps_not_configured")


async def _scope(
    request: Request, session: SessionDep, current: CurrentUser, checker: CheckPermissionUseCase
) -> FleetScope:
    return await get_fleet_scope(session, current, checker, effective_company_id(request))


async def _can_simulate(
    current: CurrentUser, checker: CheckPermissionUseCase, company_id: uuid.UUID
) -> bool:
    if current.is_superuser:
        return True
    return bool((await checker.execute(current.id, company_id, "tracking:simulate")).allowed)


def _point(value: list[float] | LngLat) -> LngLat:
    return float(value[0]), float(value[1])


def _position(simulation: TrackingSimulationModel) -> LngLat:
    return float(simulation.longitude), float(simulation.latitude)


async def _active_transfers(
    session: SessionDep, company_id: uuid.UUID, inventory_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
    if not inventory_ids:
        return {}
    rows = await session.execute(
        select(
            InventoryTransferModel.vehicle_id,
            InventoryTransferModel.id,
            InventoryTransferModel.code,
        )
        .where(
            InventoryTransferModel.company_id == company_id,
            InventoryTransferModel.vehicle_id.in_(inventory_ids),
            InventoryTransferModel.status.in_(ACTIVE_TRANSFER_STATUSES),
        )
        .order_by(InventoryTransferModel.dispatched_at.desc().nulls_last())
    )
    result: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    for vehicle_id, transfer_id, code in rows:
        result.setdefault(vehicle_id, (transfer_id, code))
    return result


async def _sessions_out(
    session: SessionDep,
    simulations: list[TrackingSimulationModel],
    *,
    scope: FleetScope,
    can_simulate: bool,
) -> list[SimulationOut]:
    if not simulations:
        return []
    vehicles = {
        vehicle.id: vehicle
        for vehicle in await session.scalars(
            select(FleetVehicleModel)
            .where(FleetVehicleModel.id.in_([item.vehicle_id for item in simulations]))
            .execution_options(include_deleted=True)
        )
    }
    transfer_ids = [item.transfer_id for item in simulations if item.transfer_id]
    transfers: dict[uuid.UUID, str] = {}
    if transfer_ids:
        for transfer_id, code in await session.execute(
            select(InventoryTransferModel.id, InventoryTransferModel.code).where(
                InventoryTransferModel.id.in_(transfer_ids)
            )
        ):
            transfers[transfer_id] = code
    user_ids = [item.started_by for item in simulations if item.started_by]
    names: dict[uuid.UUID, str] = {}
    if user_ids:
        for user_id, username, first, last in await session.execute(
            select(User.id, User.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, Employee.user_id == User.id)
            .where(User.id.in_(user_ids))
        ):
            names[user_id] = f"{first} {last}".strip() if first else username
    result = []
    for item in simulations:
        vehicle = vehicles.get(item.vehicle_id)
        result.append(
            SimulationOut.model_validate(
                {
                    "id": item.id,
                    "vehicle_id": item.vehicle_id,
                    "vehicle_code": vehicle.code if vehicle else "",
                    "vehicle_plate": vehicle.plate if vehicle else "",
                    "branch_id": item.branch_id,
                    "transfer_id": item.transfer_id,
                    "transfer_code": transfers.get(item.transfer_id) if item.transfer_id else None,
                    "traccar_device_id": item.traccar_device_id,
                    "mode": item.mode,
                    "state": item.state,
                    "route": item.route,
                    "stops": item.stops,
                    "leg": item.leg,
                    "route_length_m": float(item.route_length_m),
                    "progress_m": float(item.progress_m),
                    "speed_kmh": float(item.speed_kmh),
                    "current_speed_kmh": float(item.current_speed_kmh),
                    "longitude": float(item.longitude),
                    "latitude": float(item.latitude),
                    "course": float(item.course),
                    "advanced_at": item.advanced_at,
                    "stop_until": item.stop_until,
                    "signal_lost_until": item.signal_lost_until,
                    "last_report_at": item.last_report_at,
                    "started_at": item.started_at,
                    "started_by_name": names.get(item.started_by) if item.started_by else None,
                    "can_control": can_simulate and scope.allows(item.branch_id),
                }
            )
        )
    return result


async def _scoped_simulation(
    session: SessionDep, scope: FleetScope, simulation_id: uuid.UUID
) -> TrackingSimulationModel:
    simulation = await session.scalar(
        select(TrackingSimulationModel)
        .where(
            TrackingSimulationModel.id == simulation_id,
            TrackingSimulationModel.company_id == scope.company_id,
            TrackingSimulationModel.state != "ended",
        )
        .with_for_update()
    )
    if simulation is None:
        raise NotFoundError("Sesión de simulación no encontrada.", code="simulation_not_found")
    scope.require(simulation.branch_id, not_found="Sesión de simulación no encontrada.")
    return simulation


async def _report(simulation: TrackingSimulationModel) -> None:
    try:
        await send_report(
            simulation,
            _position(simulation),
            speed_kmh=float(simulation.current_speed_kmh),
            course=float(simulation.course),
        )
    except ReportError as exc:
        raise ConflictError(
            "Traccar no aceptó la posición simulada (receptor OsmAnd, puerto 5055).",
            code="osmand_unavailable",
        ) from exc


# ---------------------------------------------------------------- state


@router.get("", response_model=SimulatorOut, dependencies=READ)
async def get_simulator(
    request: Request, session: SessionDep, current: CurrentUser, checker: Checker
) -> SimulatorOut:
    """Whether the simulator is available and the sessions open in the user's branches."""
    if not simulator_enabled():
        return SimulatorOut(enabled=False, ready=False, can_simulate=False)
    scope = await _scope(request, session, current, checker)
    can_simulate = await _can_simulate(current, checker, scope.company_id)
    vehicles = [
        vehicle
        for vehicle in await FleetRepository(session).all_vehicles(
            scope.company_id, scope.list_filter(None)
        )
        if vehicle.status != "retired"
    ]
    simulations = await open_simulations(session, scope.company_id, [v.id for v in vehicles])
    vehicles_out: list[dict[str, Any]] = []
    if can_simulate:
        branches = {
            branch.id: branch
            for branch in await session.scalars(
                select(Branch).where(Branch.id.in_({vehicle.branch_id for vehicle in vehicles}))
            )
        }
        transfers = await _active_transfers(
            session,
            scope.company_id,
            [v.inventory_vehicle_id for v in vehicles if v.inventory_vehicle_id is not None],
        )
        for vehicle in vehicles:
            branch = branches.get(vehicle.branch_id)
            transfer = (
                transfers.get(vehicle.inventory_vehicle_id)
                if vehicle.inventory_vehicle_id
                else None
            )
            start = (
                [float(branch.longitude), float(branch.latitude)]
                if branch is not None
                and branch.latitude is not None
                and branch.longitude is not None
                else None
            )
            vehicles_out.append(
                {
                    "id": vehicle.id,
                    "code": vehicle.code,
                    "plate": vehicle.plate,
                    "kind": vehicle.kind,
                    "branch_id": vehicle.branch_id,
                    "branch_name": branch.name if branch else "",
                    "has_gps": vehicle.traccar_device_id is not None,
                    "transfer_id": transfer[0] if transfer else None,
                    "transfer_code": transfer[1] if transfer else None,
                    "start": start,
                }
            )
    return SimulatorOut.model_validate(
        {
            "enabled": True,
            "server_time": datetime.now(UTC),
            "ready": traccar_credentials() is not None,
            "can_simulate": can_simulate,
            "vehicles": vehicles_out,
            "sessions": await _sessions_out(
                session, list(simulations.values()), scope=scope, can_simulate=can_simulate
            ),
        }
    )


# ---------------------------------------------------------------- sessions


async def _transfer_route(
    session: SessionDep, scope: FleetScope, vehicle: FleetVehicleModel, transfer_id: uuid.UUID
) -> list[LngLat]:
    row = (
        await session.execute(
            transfer_query(scope.company_id, None).where(InventoryTransferModel.id == transfer_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Traslado no encontrado.", code="transfer_not_found")
    ctx = trip_context(row)
    if ctx.transfer.status not in ACTIVE_TRANSFER_STATUSES:
        raise ConflictError("El traslado no está en tránsito.", code="transfer_not_in_transit")
    if ctx.fleet is None or ctx.fleet.id != vehicle.id:
        raise ConflictError(
            "El traslado no viaja en ese vehículo.", code="transfer_vehicle_mismatch"
        )
    origin, destination = ctx.data["origin"], ctx.data["destination"]
    if None in (
        origin["longitude"],
        origin["latitude"],
        destination["longitude"],
        destination["latitude"],
    ):
        raise ConflictError(
            "El origen o el destino del traslado no tiene ubicación en el mapa.",
            code="transfer_without_location",
        )
    return [
        (origin["longitude"], origin["latitude"]),
        (destination["longitude"], destination["latitude"]),
    ]


async def _planned_route(
    session: SessionDep, scope: FleetScope, vehicle: FleetVehicleModel, body: SimulationCreate
) -> tuple[list[LngLat], list[LngLat]]:
    if body.transfer_id is not None and body.waypoints:
        raise ValidationError(
            "Elija un traslado o puntos en el mapa, no ambos.", code="simulation_source"
        )
    if body.transfer_id is not None:
        stops = await _transfer_route(session, scope, vehicle, body.transfer_id)
    elif len(body.waypoints) >= MIN_ROUTE_POINTS:
        stops = [_point(item) for item in body.waypoints]
    else:
        raise ValidationError(
            "Indique un traslado o al menos dos puntos del recorrido.", code="simulation_source"
        )
    return stops, await _street_path(stops)


async def _street_path(stops: list[LngLat]) -> list[LngLat]:
    planned = await plan_path(settings.OSRM_URL, stops)
    route = downsample([_point(item) for item in planned["coordinates"]])
    if len(route) < MIN_ROUTE_POINTS or path_length(route) < 1:
        raise ValidationError("El recorrido es demasiado corto.", code="simulation_route")
    return route


def _follow(simulation: TrackingSimulationModel, route: list[LngLat], leg: str) -> None:
    """Put the unit on a new route that starts where it is now."""
    simulation.mode = "route"
    simulation.leg = leg
    simulation.route = [list(point) for point in route]
    simulation.route_length_m = Decimal(f"{path_length(route):.1f}")
    simulation.progress_m = Decimal("0")
    simulation.state = "running"
    simulation.stop_until = None


async def _joystick_start(
    repo: FleetRepository, scope: FleetScope, vehicle: FleetVehicleModel, body: SimulationCreate
) -> LngLat:
    if body.transfer_id is not None or body.waypoints:
        raise ValidationError(
            "El joystick no usa recorrido: solo un punto de inicio.", code="simulation_source"
        )
    if body.start is not None:
        return _point(body.start)
    branch = await repo.branch(scope.company_id, vehicle.branch_id)
    if branch is None or branch.latitude is None or branch.longitude is None:
        raise ValidationError(
            "Indique dónde aparece la unidad: su sucursal no tiene ubicación.",
            code="simulation_start",
        )
    return float(branch.longitude), float(branch.latitude)


@router.post(
    "/sessions",
    response_model=SimulationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=SIMULATE,
)
async def start_simulation(
    body: SimulationCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> SimulationOut:
    _require_enabled()
    scope = await _scope(request, session, current, checker)
    repo = FleetRepository(session)
    vehicle = await repo.get_vehicle(scope.company_id, body.vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehículo no encontrado.", code="vehicle_not_found")
    scope.require(vehicle.branch_id, not_found="Vehículo no encontrado.")
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    if await open_simulations(session, scope.company_id, [vehicle.id]):
        raise ConflictError(
            "Ese vehículo ya tiene una simulación en curso.", code="simulation_exists"
        )

    if body.mode == "route":
        stops, route = await _planned_route(session, scope, vehicle, body)
        start, course = point_at(route, 0)
    else:
        route = []
        start, course = await _joystick_start(repo, scope, vehicle, body), 0.0
        stops = [start]

    device_id, unique_id = await ensure_virtual_device(vehicle)
    now = datetime.now(UTC)
    async with session.begin_nested():
        simulation = TrackingSimulationModel(
            company_id=scope.company_id,
            vehicle_id=vehicle.id,
            branch_id=vehicle.branch_id,
            transfer_id=body.transfer_id,
            traccar_device_id=device_id,
            device_unique_id=unique_id,
            mode=body.mode,
            state="running",
            route=[list(point) for point in route],
            stops=[list(point) for point in stops],
            leg="outbound",
            route_length_m=Decimal(f"{path_length(route):.1f}"),
            progress_m=Decimal("0"),
            speed_kmh=Decimal(f"{body.speed_kmh:.1f}"),
            current_speed_kmh=Decimal("0"),
            longitude=Decimal(f"{start[0]:.6f}"),
            latitude=Decimal(f"{start[1]:.6f}"),
            course=Decimal(f"{course:.1f}"),
            last_activity_at=now,
            started_by=current.id,
            started_at=now,
            advanced_at=now,
        )
        session.add(simulation)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "Ese vehículo ya tiene una simulación en curso.", code="simulation_exists"
            ) from exc
        await _report(simulation)
        await audit.record(
            action="SIMULATION_START",
            user_id=current.id,
            company_id=scope.company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={
                "simulation_id": str(simulation.id),
                "mode": body.mode,
                "transfer_id": str(body.transfer_id) if body.transfer_id else None,
                "speed_kmh": body.speed_kmh,
            },
        )
    return (await _sessions_out(session, [simulation], scope=scope, can_simulate=True))[0]


@router.post(
    "/sessions/{simulation_id}/control", response_model=SimulationOut, dependencies=SIMULATE
)
async def control_simulation(  # noqa: C901 - one branch per action keeps the rules visible
    simulation_id: uuid.UUID,
    body: SimulationControl,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> SimulationOut:
    _require_enabled()
    scope = await _scope(request, session, current, checker)
    simulation = await _scoped_simulation(session, scope, simulation_id)
    now = datetime.now(UTC)
    on_route = simulation.mode == "route"
    action = body.action
    if action in {"pause", "resume", "detour", "restart", "outbound"} and not on_route:
        raise ConflictError(
            "Esa acción es para trayectos automáticos.", code="simulation_action_invalid"
        )
    if action == "pause":
        if simulation.state == "running":
            simulation.state = "paused"
    elif action == "resume":
        simulation.stop_until = None
        if simulation.state == "paused":
            simulation.state = "running"
    elif action == "stop":
        simulation.stop_until = now + timedelta(minutes=body.minutes or DEFAULT_STOP_MINUTES)
    elif action == "signal_loss":
        simulation.signal_lost_until = now + timedelta(
            minutes=body.minutes or DEFAULT_SIGNAL_MINUTES
        )
    elif action == "signal_restore":
        simulation.signal_lost_until = None
        simulation.last_report_at = None  # El motor informa de inmediato.
    elif action == "speed":
        if body.speed_kmh is None:
            raise ValidationError("Indique la velocidad.", code="simulation_speed")
        simulation.speed_kmh = Decimal(f"{body.speed_kmh:.1f}")
    elif action == "detour":
        if simulation.state == "arrived":
            raise ConflictError("La unidad ya llegó a su destino.", code="simulation_arrived")
        route = [_point(item) for item in simulation.route]
        waypoint = detour_waypoint(route, float(simulation.progress_m))
        if waypoint is None:
            raise ConflictError(
                "Queda muy poco recorrido para desviarse.", code="simulation_detour_short"
            )
        planned = await plan_path(settings.OSRM_URL, [_position(simulation), waypoint, route[-1]])
        detour = downsample([_point(item) for item in planned["coordinates"]])
        simulation.route = [list(point) for point in detour]
        simulation.route_length_m = Decimal(f"{path_length(detour):.1f}")
        simulation.progress_m = Decimal("0")
        simulation.state = "running"
    elif action == "restart":
        route = [_point(item) for item in simulation.route]
        start, course = point_at(route, 0)
        simulation.progress_m = Decimal("0")
        simulation.state = "running"
        simulation.stop_until = None
        apply_position(simulation, start, course, 0)
        simulation.last_report_at = None
    elif action in {"return", "outbound", "take_control"}:
        await _round_trip(simulation, action)
    simulation.last_activity_at = now
    simulation.advanced_at = now
    await session.flush()
    can_simulate = await _can_simulate(current, checker, scope.company_id)
    return (await _sessions_out(session, [simulation], scope=scope, can_simulate=can_simulate))[0]


async def _round_trip(simulation: TrackingSimulationModel, action: str) -> None:
    """Go back to the starting point, set off again, or hand the unit to the joystick."""
    stops = [_point(item) for item in simulation.stops]
    here = _position(simulation)
    if action == "take_control":
        # El joystick retoma la unidad donde esté; el recorrido automático se descarta.
        simulation.mode = "joystick"
        simulation.leg = "outbound"
        simulation.route = []
        simulation.route_length_m = Decimal("0")
        simulation.progress_m = Decimal("0")
        simulation.state = "running"
        simulation.stop_until = None
        simulation.current_speed_kmh = Decimal("0")
        return
    if action == "return":
        if not stops:
            raise ConflictError("La sesión no tiene punto de inicio.", code="simulation_no_start")
        if distance_m(here, stops[0]) <= AT_START_M:
            raise ConflictError(
                "La unidad ya está en el punto inicial.", code="simulation_at_start"
            )
        # Ruta nueva por calles desde donde está hasta donde empezó.
        _follow(simulation, await _street_path([here, stops[0]]), "return")
        return
    if len(stops) < MIN_ROUTE_POINTS:
        raise ConflictError(
            "La sesión no tiene un recorrido de ida que repetir.", code="simulation_no_route"
        )
    _follow(simulation, await _street_path([here, *stops[1:]]), "outbound")


@router.post(
    "/sessions/{simulation_id}/drive", response_model=SimulationDriveOut, dependencies=SIMULATE
)
async def drive_simulation(
    simulation_id: uuid.UUID,
    body: SimulationDrive,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> SimulationDriveOut:
    """Joystick: the browser drives the unit and the server forwards it to Traccar."""
    _require_enabled()
    scope = await _scope(request, session, current, checker)
    target: LngLat = (body.longitude, body.latitude)
    snapped = target
    if body.snap:
        # Antes de bloquear la sesión: la consulta a OSRM no debe retener el bloqueo.
        snapped = await nearest_road(settings.OSRM_URL, target)
    simulation = await _scoped_simulation(session, scope, simulation_id)
    if simulation.mode != "joystick":
        raise ConflictError(
            "La sesión sigue un trayecto automático.", code="simulation_action_invalid"
        )
    now = datetime.now(UTC)
    if not plausible_drive(_position(simulation), simulation.last_report_at, snapped, now):
        raise ConflictError(
            "El salto de posición es imposible para un vehículo.", code="simulation_teleport"
        )
    apply_position(simulation, snapped, body.course, body.speed_kmh)
    simulation.last_activity_at = now
    lost = simulation.signal_lost_until is not None and now < simulation.signal_lost_until
    due = (
        simulation.last_report_at is None
        or (now - simulation.last_report_at).total_seconds() >= DRIVE_REPORT_S
    )
    reported = False
    if not lost and due:
        await _report(simulation)
        reported = True
    await session.flush()
    return SimulationDriveOut(
        longitude=snapped[0],
        latitude=snapped[1],
        snapped=snapped != target,
        reported=reported,
    )


@router.delete(
    "/sessions/{simulation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=SIMULATE,
)
async def end_simulation_session(
    simulation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> Response:
    # Finalizar siempre está permitido, aunque el simulador se haya desactivado.
    scope = await _scope(request, session, current, checker)
    simulation = await _scoped_simulation(session, scope, simulation_id)
    await end_simulation(
        session, simulation, reason="Finalizada por el usuario.", actor_id=current.id
    )
    await audit.record(
        action="SIMULATION_END",
        user_id=current.id,
        company_id=scope.company_id,
        branch_id=simulation.branch_id,
        resource_type="fleet_vehicles",
        resource_id=str(simulation.vehicle_id),
        after_state={"simulation_id": str(simulation.id), "reason": simulation.end_reason},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

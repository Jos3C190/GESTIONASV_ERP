"""Vehicle operations: odometer, maintenance plans and orders, fuel and alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import FleetScope, get_fleet_scope
from app.api.v1.routers.fleet import scoped_vehicle
from app.api.v1.schemas.fleet import (
    FleetAlertOut,
    FuelLogIn,
    FuelLogOut,
    FuelStatsOut,
    MaintenanceCancelIn,
    MaintenanceCompleteIn,
    MaintenanceOrderIn,
    MaintenanceOrderOut,
    MaintenancePlanIn,
    MaintenancePlanOut,
    OdometerReadingIn,
    OdometerReadingOut,
)
from app.application.audit.audit_service import AuditService
from app.application.fleet.driver_views import build_driver_views
from app.application.fleet.operations import (
    OdometerBounds,
    fuel_efficiency,
    fuel_stats,
    in_future,
    odometer_error,
    unit_price,
)
from app.application.fleet.views import build_vehicle_views, plan_due
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleModel,
    FuelLogModel,
    MaintenanceOrderModel,
    MaintenancePlanModel,
    OdometerReadingModel,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-operations"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]

OPEN_ORDER_STATUSES = ("scheduled", "in_progress")


def _now() -> datetime:
    return datetime.now(UTC)


async def _context(
    request: Request, session: SessionDep, current: CurrentUser, checker: CheckPermissionUseCase
) -> tuple[uuid.UUID, FleetScope, FleetRepository]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    return company_id, scope, FleetRepository(session)


def _require_operable(vehicle: FleetVehicleModel) -> None:
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")


# ------------------------------------------------------------------ odometer


async def record_odometer(
    session: SessionDep,
    vehicle: FleetVehicleModel,
    *,
    reading_km: Decimal,
    read_at: datetime,
    source: str,
    actor_id: uuid.UUID,
    notes: str | None = None,
) -> OdometerReadingModel:
    """Store a reading after checking it against the vehicle's history."""
    if in_future(read_at, _now()):
        raise ValidationError("La fecha de la lectura no puede ser futura.", code="odometer_future")
    minimum = await session.scalar(
        select(func.max(OdometerReadingModel.reading_km)).where(
            OdometerReadingModel.vehicle_id == vehicle.id, OdometerReadingModel.read_at <= read_at
        )
    )
    maximum = await session.scalar(
        select(func.min(OdometerReadingModel.reading_km)).where(
            OdometerReadingModel.vehicle_id == vehicle.id, OdometerReadingModel.read_at > read_at
        )
    )
    error = odometer_error(Decimal(reading_km), OdometerBounds(minimum, maximum))
    if error:
        raise ConflictError(error, code="odometer_out_of_order")
    reading = OdometerReadingModel(
        company_id=vehicle.company_id,
        vehicle_id=vehicle.id,
        reading_km=reading_km,
        read_at=read_at,
        source=source,
        notes=notes,
        recorded_by=actor_id,
    )
    session.add(reading)
    await session.flush()
    vehicle.odometer_km = max(Decimal(vehicle.odometer_km), Decimal(reading_km))
    await session.flush()
    return reading


@router.get(
    "/vehicles/{vehicle_id}/odometer",
    response_model=list[OdometerReadingOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_odometer(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[OdometerReadingOut]:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    rows = await session.execute(
        select(OdometerReadingModel, User.username)
        .outerjoin(User, User.id == OdometerReadingModel.recorded_by)
        .where(OdometerReadingModel.vehicle_id == vehicle.id)
        .order_by(OdometerReadingModel.read_at.desc())
        .limit(100)
    )
    return [
        OdometerReadingOut(
            id=reading.id,
            reading_km=reading.reading_km,
            read_at=reading.read_at,
            source=reading.source,
            notes=reading.notes,
            recorded_by_name=username,
        )
        for reading, username in rows.all()
    ]


@router.post(
    "/vehicles/{vehicle_id}/odometer",
    response_model=OdometerReadingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def add_odometer(
    vehicle_id: uuid.UUID,
    body: OdometerReadingIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> OdometerReadingOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    _require_operable(vehicle)
    async with session.begin_nested():
        reading = await record_odometer(
            session,
            vehicle,
            reading_km=body.reading_km,
            read_at=body.read_at or _now(),
            source="manual",
            actor_id=current.id,
            notes=(body.notes or "").strip() or None,
        )
        await audit.record(
            action="ODOMETER_READING",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"reading_km": str(reading.reading_km)},
        )
    return OdometerReadingOut(
        id=reading.id,
        reading_km=reading.reading_km,
        read_at=reading.read_at,
        source=reading.source,
        notes=reading.notes,
        recorded_by_name=current.username,
    )


# ------------------------------------------------------------------ maintenance plans


def _plan_out(plan: MaintenancePlanModel, vehicle: FleetVehicleModel) -> MaintenancePlanOut:
    due = plan_due(plan, Decimal(vehicle.odometer_km), _now().date())
    return MaintenancePlanOut(
        id=plan.id,
        name=plan.name,
        interval_km=plan.interval_km,
        interval_days=plan.interval_days,
        last_service_km=plan.last_service_km,
        last_service_on=plan.last_service_on,
        due_km=due["due_km"],
        due_on=due["due_on"],
        state=due["state"],
        is_active=plan.is_active,
    )


async def _plan(
    session: SessionDep, vehicle: FleetVehicleModel, plan_id: uuid.UUID, *, active_only: bool = True
) -> MaintenancePlanModel:
    plan = await session.scalar(
        select(MaintenancePlanModel).where(
            MaintenancePlanModel.id == plan_id,
            MaintenancePlanModel.vehicle_id == vehicle.id,
            MaintenancePlanModel.company_id == vehicle.company_id,
        )
    )
    if plan is None or (active_only and not plan.is_active):
        raise NotFoundError(
            "Plan de mantenimiento no encontrado.", code="maintenance_plan_not_found"
        )
    return plan


def _validate_plan(body: MaintenancePlanIn, vehicle: FleetVehicleModel) -> None:
    if body.interval_km is None and body.interval_days is None:
        raise ValidationError(
            "Defina el intervalo en kilómetros, en días o en ambos.",
            code="maintenance_interval_required",
        )
    if body.last_service_km is not None and body.last_service_km > Decimal(vehicle.odometer_km):
        raise ValidationError(
            "El último servicio no puede superar el odómetro actual.",
            code="maintenance_last_km_invalid",
        )
    if body.last_service_on is not None and body.last_service_on > _now().date():
        raise ValidationError(
            "La fecha del último servicio no puede ser futura.",
            code="maintenance_last_date_invalid",
        )


@router.get(
    "/vehicles/{vehicle_id}/maintenance-plans",
    response_model=list[MaintenancePlanOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_plans(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[MaintenancePlanOut]:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    plans = await session.scalars(
        select(MaintenancePlanModel)
        .where(
            MaintenancePlanModel.vehicle_id == vehicle.id, MaintenancePlanModel.is_active.is_(True)
        )
        .order_by(MaintenancePlanModel.name)
    )
    return [_plan_out(plan, vehicle) for plan in plans]


@router.post(
    "/vehicles/{vehicle_id}/maintenance-plans",
    response_model=MaintenancePlanOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def create_plan(
    vehicle_id: uuid.UUID,
    body: MaintenancePlanIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> MaintenancePlanOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    _require_operable(vehicle)
    _validate_plan(body, vehicle)
    duplicate = await session.scalar(
        select(MaintenancePlanModel.id).where(
            MaintenancePlanModel.vehicle_id == vehicle.id,
            MaintenancePlanModel.is_active.is_(True),
            func.lower(MaintenancePlanModel.name) == body.name.strip().lower(),
        )
    )
    if duplicate is not None:
        raise ConflictError(
            "Ya existe un plan activo con ese nombre.", code="maintenance_plan_exists"
        )
    async with session.begin_nested():
        plan = MaintenancePlanModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            name=body.name.strip(),
            interval_km=body.interval_km,
            interval_days=body.interval_days,
            last_service_km=body.last_service_km,
            last_service_on=body.last_service_on,
            created_by=current.id,
        )
        session.add(plan)
        await session.flush()
        await audit.record(
            action="CREATE_MAINTENANCE_PLAN",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"plan_id": str(plan.id), "name": plan.name},
        )
    return _plan_out(plan, vehicle)


@router.put(
    "/vehicles/{vehicle_id}/maintenance-plans/{plan_id}",
    response_model=MaintenancePlanOut,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def update_plan(
    vehicle_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: MaintenancePlanIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> MaintenancePlanOut:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    plan = await _plan(session, vehicle, plan_id)
    _validate_plan(body, vehicle)
    plan.name = body.name.strip()
    plan.interval_km = body.interval_km
    plan.interval_days = body.interval_days
    plan.last_service_km = body.last_service_km
    plan.last_service_on = body.last_service_on
    await session.flush()
    return _plan_out(plan, vehicle)


@router.delete(
    "/vehicles/{vehicle_id}/maintenance-plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def deactivate_plan(
    vehicle_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> None:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    plan = await _plan(session, vehicle, plan_id)
    # Se desactiva (no se borra) porque las órdenes históricas lo referencian.
    plan.is_active = False
    await session.flush()


# ------------------------------------------------------------------ maintenance orders


async def _order(
    session: SessionDep, vehicle: FleetVehicleModel, order_id: uuid.UUID
) -> MaintenanceOrderModel:
    order = await session.scalar(
        select(MaintenanceOrderModel)
        .where(
            MaintenanceOrderModel.id == order_id,
            MaintenanceOrderModel.vehicle_id == vehicle.id,
            MaintenanceOrderModel.company_id == vehicle.company_id,
        )
        .with_for_update()
    )
    if order is None:
        raise NotFoundError(
            "Orden de mantenimiento no encontrada.", code="maintenance_order_not_found"
        )
    return order


async def _order_out(session: SessionDep, order: MaintenanceOrderModel) -> MaintenanceOrderOut:
    plan_name = (
        await session.scalar(
            select(MaintenancePlanModel.name).where(MaintenancePlanModel.id == order.plan_id)
        )
        if order.plan_id
        else None
    )
    return MaintenanceOrderOut(
        id=order.id,
        plan_id=order.plan_id,
        plan_name=plan_name,
        kind=order.kind,
        status=order.status,  # type: ignore[arg-type]
        title=order.title,
        description=order.description,
        workshop=order.workshop,
        scheduled_on=order.scheduled_on,
        started_at=order.started_at,
        completed_at=order.completed_at,
        odometer_km=order.odometer_km,
        cost=order.cost,
        cancel_reason=order.cancel_reason,
        created_at=order.created_at,
    )


async def _release_vehicle(
    session: SessionDep, vehicle: FleetVehicleModel, *, exclude: uuid.UUID
) -> None:
    """Return the vehicle to service when no other order keeps it in the workshop."""
    other = await session.scalar(
        select(MaintenanceOrderModel.id).where(
            MaintenanceOrderModel.vehicle_id == vehicle.id,
            MaintenanceOrderModel.status == "in_progress",
            MaintenanceOrderModel.id != exclude,
        )
    )
    if other is None and vehicle.status == "maintenance":
        vehicle.status = "active"


@router.get(
    "/vehicles/{vehicle_id}/maintenance-orders",
    response_model=list[MaintenanceOrderOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_orders(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[MaintenanceOrderOut]:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    orders = await session.scalars(
        select(MaintenanceOrderModel)
        .where(MaintenanceOrderModel.vehicle_id == vehicle.id)
        .order_by(MaintenanceOrderModel.created_at.desc())
        .limit(100)
    )
    return [await _order_out(session, order) for order in orders]


@router.post(
    "/vehicles/{vehicle_id}/maintenance-orders",
    response_model=MaintenanceOrderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def create_order(
    vehicle_id: uuid.UUID,
    body: MaintenanceOrderIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> MaintenanceOrderOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    _require_operable(vehicle)
    if body.plan_id is not None:
        await _plan(session, vehicle, body.plan_id)
    async with session.begin_nested():
        order = MaintenanceOrderModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            plan_id=body.plan_id,
            kind=body.kind,
            status="scheduled",
            title=body.title.strip(),
            description=(body.description or "").strip() or None,
            workshop=(body.workshop or "").strip() or None,
            scheduled_on=body.scheduled_on,
            created_by=current.id,
        )
        session.add(order)
        await session.flush()
        await audit.record(
            action="CREATE_MAINTENANCE_ORDER",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"order_id": str(order.id), "title": order.title},
        )
    return await _order_out(session, order)


@router.post(
    "/vehicles/{vehicle_id}/maintenance-orders/{order_id}/start",
    response_model=MaintenanceOrderOut,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def start_order(
    vehicle_id: uuid.UUID,
    order_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> MaintenanceOrderOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    _require_operable(vehicle)
    order = await _order(session, vehicle, order_id)
    if order.status != "scheduled":
        raise ConflictError(
            "Solo una orden programada puede iniciarse.", code="maintenance_order_state"
        )
    if vehicle.inventory_vehicle_id is not None and await repo.active_transfers(
        company_id, [vehicle.inventory_vehicle_id]
    ):
        raise ConflictError(
            "El vehículo está en un traslado; inicie el mantenimiento cuando regrese.",
            code="vehicle_on_road",
        )
    async with session.begin_nested():
        order.status = "in_progress"
        order.started_at = _now()
        vehicle.status = "maintenance"
        await session.flush()
        await audit.record(
            action="START_MAINTENANCE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"order_id": str(order.id), "status": "maintenance"},
            required=True,
        )
    return await _order_out(session, order)


@router.post(
    "/vehicles/{vehicle_id}/maintenance-orders/{order_id}/complete",
    response_model=MaintenanceOrderOut,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def complete_order(
    vehicle_id: uuid.UUID,
    order_id: uuid.UUID,
    body: MaintenanceCompleteIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> MaintenanceOrderOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    order = await _order(session, vehicle, order_id)
    if order.status != "in_progress":
        raise ConflictError(
            "Solo una orden en curso puede completarse.", code="maintenance_order_state"
        )
    completed_at = _now()
    async with session.begin_nested():
        await record_odometer(
            session,
            vehicle,
            reading_km=body.odometer_km,
            read_at=completed_at,
            source="maintenance",
            actor_id=current.id,
            notes=f"Cierre de mantenimiento: {order.title}",
        )
        order.status = "completed"
        order.completed_at = completed_at
        order.odometer_km = body.odometer_km
        order.cost = body.cost
        order.closed_by = current.id
        if body.workshop:
            order.workshop = body.workshop.strip()
        if body.notes:
            order.description = "\n".join(filter(None, [order.description, body.notes.strip()]))
        if order.plan_id is not None:
            plan = await _plan(session, vehicle, order.plan_id, active_only=False)
            plan.last_service_km = body.odometer_km
            plan.last_service_on = completed_at.date()
        await _release_vehicle(session, vehicle, exclude=order.id)
        await session.flush()
        await audit.record(
            action="COMPLETE_MAINTENANCE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={
                "order_id": str(order.id),
                "cost": str(body.cost),
                "odometer_km": str(body.odometer_km),
                "status": vehicle.status,
            },
            required=True,
        )
    return await _order_out(session, order)


@router.post(
    "/vehicles/{vehicle_id}/maintenance-orders/{order_id}/cancel",
    response_model=MaintenanceOrderOut,
    dependencies=[Depends(require_permission("fleet:maintenance"))],
)
async def cancel_order(
    vehicle_id: uuid.UUID,
    order_id: uuid.UUID,
    body: MaintenanceCancelIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> MaintenanceOrderOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    order = await _order(session, vehicle, order_id)
    if order.status not in OPEN_ORDER_STATUSES:
        raise ConflictError("La orden ya está cerrada.", code="maintenance_order_state")
    async with session.begin_nested():
        was_running = order.status == "in_progress"
        order.status = "cancelled"
        order.cancel_reason = body.reason.strip()
        order.closed_by = current.id
        if was_running:
            await _release_vehicle(session, vehicle, exclude=order.id)
        await session.flush()
        await audit.record(
            action="CANCEL_MAINTENANCE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"order_id": str(order.id)},
            metadata={"reason": order.cancel_reason},
            required=True,
        )
    return await _order_out(session, order)


# ------------------------------------------------------------------ fuel


@router.get(
    "/vehicles/{vehicle_id}/fuel-logs",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_fuel(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> dict[str, Any]:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    rows = (
        await session.execute(
            select(FuelLogModel, Employee.first_name, Employee.last_name)
            .outerjoin(DriverModel, DriverModel.id == FuelLogModel.driver_id)
            .outerjoin(Employee, Employee.id == DriverModel.employee_id)
            .where(FuelLogModel.vehicle_id == vehicle.id)
            .execution_options(include_deleted=True)
            .order_by(FuelLogModel.filled_at)
        )
    ).all()
    logs = [row[0] for row in rows]
    efficiency = fuel_efficiency(logs)
    items = [
        FuelLogOut(
            id=log.id,
            filled_at=log.filled_at,
            liters=log.liters,
            total_amount=log.total_amount,
            unit_price=unit_price(log.total_amount, log.liters),
            odometer_km=log.odometer_km,
            full_tank=log.full_tank,
            station=log.station,
            driver_id=log.driver_id,
            driver_name=f"{first} {last}".strip() if first else None,
            km_per_liter=efficiency.get(log.id),
        )
        for log, first, last in rows
    ]
    items.reverse()
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "stats": FuelStatsOut.model_validate(fuel_stats(logs, efficiency)).model_dump(mode="json"),
    }


@router.post(
    "/vehicles/{vehicle_id}/fuel-logs",
    response_model=FuelLogOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:fuel"))],
)
async def add_fuel(
    vehicle_id: uuid.UUID,
    body: FuelLogIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FuelLogOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    _require_operable(vehicle)
    driver_name: str | None = None
    if body.driver_id is not None:
        row = await repo.driver_with_employee(company_id, body.driver_id)
        if row is None or row[0].branch_id != vehicle.branch_id:
            raise ValidationError(
                "El conductor debe pertenecer a la sucursal del vehículo.",
                code="fuel_driver_invalid",
            )
        driver_name = f"{row[1].first_name} {row[1].last_name}".strip()
    async with session.begin_nested():
        await record_odometer(
            session,
            vehicle,
            reading_km=body.odometer_km,
            read_at=body.filled_at,
            source="fuel",
            actor_id=current.id,
            notes="Carga de combustible",
        )
        log = FuelLogModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            driver_id=body.driver_id,
            filled_at=body.filled_at,
            liters=body.liters,
            total_amount=body.total_amount,
            odometer_km=body.odometer_km,
            full_tank=body.full_tank,
            station=(body.station or "").strip() or None,
            recorded_by=current.id,
        )
        session.add(log)
        await session.flush()
        await audit.record(
            action="FUEL_LOG",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"liters": str(log.liters), "amount": str(log.total_amount)},
        )
    return FuelLogOut(
        id=log.id,
        filled_at=log.filled_at,
        liters=log.liters,
        total_amount=log.total_amount,
        unit_price=unit_price(log.total_amount, log.liters),
        odometer_km=log.odometer_km,
        full_tank=log.full_tank,
        station=log.station,
        driver_id=log.driver_id,
        driver_name=driver_name,
        km_per_liter=None,
    )


# ------------------------------------------------------------------ alerts


@router.get(
    "/alerts",
    response_model=list[FleetAlertOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def fleet_alerts(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID | None = Query(None),
) -> list[FleetAlertOut]:
    """Every fitness issue of the vehicles and drivers in scope, blocking first."""
    company_id, scope, repo = await _context(request, session, current, checker)
    branches = scope.list_filter(branch_id)
    vehicles = await repo.all_vehicles(company_id, branches)
    alerts: list[FleetAlertOut] = []
    for view in await build_vehicle_views(repo, company_id, vehicles, today=_now().date()):
        for issue in view["compliance"]["issues"]:
            alerts.append(
                FleetAlertOut(
                    vehicle_id=view["id"],
                    driver_id=None,
                    subject=f"{view['code']} · {view['plate']}",
                    branch_name=view["branch_name"],
                    **issue,
                )
            )
    can_read_drivers = (
        current.is_superuser
        or (await checker.execute(current.id, company_id, "drivers:read")).allowed
    )
    if can_read_drivers:
        rows, _ = await repo.list_drivers(
            company_id, branches, status="active", search=None, page=1, size=10_000
        )
        for view in await build_driver_views(repo, company_id, rows, today=_now().date()):
            for issue in view["compliance"]["issues"]:
                alerts.append(
                    FleetAlertOut(
                        vehicle_id=None,
                        driver_id=view["id"],
                        subject=view["employee"]["name"],
                        branch_name=view["branch_name"],
                        **issue,
                    )
                )
    alerts.sort(key=lambda alert: (alert.severity != "blocking", alert.subject))
    return alerts

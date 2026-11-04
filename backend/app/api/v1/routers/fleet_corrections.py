"""Fix what was captured wrong: nothing is deleted, the wrong record is voided with a reason."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import get_fleet_scope
from app.api.v1.routers.fleet import scoped_vehicle
from app.api.v1.routers.fleet_operations import (
    create_fuel_log,
    fuel_driver_name,
    fuel_log_out,
)
from app.api.v1.schemas.fleet import (
    FleetVehicleOut,
    FuelCorrectionIn,
    FuelLogOut,
    MeterReplacementIn,
    OdometerTotalOut,
    VoidRecordIn,
)
from app.application.audit.audit_service import AuditService
from app.application.fleet.operations import in_future, total_distance
from app.application.fleet.views import build_vehicle_views
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.models.fleet import (
    FleetVehicleModel,
    FuelLogModel,
    MaintenancePlanModel,
    OdometerReadingModel,
)
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-corrections"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_CORRECT = [Depends(require_permission("fleet:correct_records"))]


async def _vehicle(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    vehicle_id: uuid.UUID,
) -> tuple[uuid.UUID, FleetRepository, FleetVehicleModel]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    repo = FleetRepository(session)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    return company_id, repo, vehicle


async def _refresh_meter(session: SessionDep, vehicle: FleetVehicleModel) -> None:
    """The current value is the highest valid reading since the last meter replacement."""
    valid = (
        OdometerReadingModel.vehicle_id == vehicle.id,
        OdometerReadingModel.voided_at.is_(None),
    )
    start = await session.scalar(
        select(func.max(OdometerReadingModel.read_at)).where(
            *valid, OdometerReadingModel.source == "meter_replacement"
        )
    )
    highest = select(func.max(OdometerReadingModel.reading_km)).where(*valid)
    if start is not None:
        highest = highest.where(OdometerReadingModel.read_at >= start)
    vehicle.odometer_km = await session.scalar(highest) or Decimal("0")


async def _shift_plans(session: SessionDep, vehicle: FleetVehicleModel, delta: Decimal) -> None:
    """Keep what was left until the next service when the meter's scale changes.

    The result can be negative: the service happened on the previous meter.
    """
    plans = await session.scalars(
        select(MaintenancePlanModel).where(
            MaintenancePlanModel.vehicle_id == vehicle.id,
            MaintenancePlanModel.is_active.is_(True),
            MaintenancePlanModel.last_service_km.is_not(None),
        )
    )
    for plan in plans:
        plan.last_service_km = Decimal(plan.last_service_km or 0) + delta


def _void(record: OdometerReadingModel | FuelLogModel, actor: uuid.UUID, reason: str) -> None:
    record.voided_at = datetime.now(UTC)
    record.voided_by = actor
    record.void_reason = reason.strip()


async def _reading(
    session: SessionDep, vehicle: FleetVehicleModel, reading_id: uuid.UUID
) -> OdometerReadingModel:
    reading = await session.scalar(
        select(OdometerReadingModel)
        .where(
            OdometerReadingModel.id == reading_id,
            OdometerReadingModel.vehicle_id == vehicle.id,
        )
        .with_for_update()
    )
    if reading is None:
        raise NotFoundError("Lectura no encontrada.", code="odometer_reading_not_found")
    if reading.voided_at is not None:
        raise ConflictError("La lectura ya está anulada.", code="record_already_voided")
    return reading


async def _vehicle_out(
    repo: FleetRepository, company_id: uuid.UUID, vehicle: FleetVehicleModel
) -> FleetVehicleOut:
    views = await build_vehicle_views(repo, company_id, [vehicle], today=datetime.now(UTC).date())
    return FleetVehicleOut.model_validate(views[0])


@router.post(
    "/vehicles/{vehicle_id}/odometer/{reading_id}/void",
    response_model=FleetVehicleOut,
    dependencies=_CORRECT,
)
async def void_reading(
    vehicle_id: uuid.UUID,
    reading_id: uuid.UUID,
    body: VoidRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, repo, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    reading = await _reading(session, vehicle, reading_id)
    if reading.source == "fuel":
        raise ConflictError(
            "Esta lectura viene de una carga de combustible; corrija la carga.",
            code="odometer_from_fuel",
        )
    if reading.source == "meter_replacement":
        later = await session.scalar(
            select(func.count())
            .select_from(OdometerReadingModel)
            .where(
                OdometerReadingModel.vehicle_id == vehicle.id,
                OdometerReadingModel.voided_at.is_(None),
                OdometerReadingModel.id != reading.id,
                OdometerReadingModel.read_at >= reading.read_at,
            )
        )
        if later:
            raise ConflictError(
                "Ya hay lecturas con este tablero; anúlelas antes de deshacer el cambio.",
                code="meter_has_later_readings",
            )
    before = str(vehicle.odometer_km)
    async with session.begin_nested():
        _void(reading, current.id, body.reason)
        await session.flush()
        await _refresh_meter(session, vehicle)
        if reading.source == "meter_replacement":
            await _shift_plans(session, vehicle, Decimal(vehicle.odometer_km) - reading.reading_km)
        await session.flush()
        await audit.record(
            action="VOID_ODOMETER_READING",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"odometer_km": before, "reading": str(reading.reading_km)},
            after_state={"odometer_km": str(vehicle.odometer_km)},
            metadata={"reason": body.reason},
            required=True,
        )
    return await _vehicle_out(repo, company_id, vehicle)


@router.post(
    "/vehicles/{vehicle_id}/odometer/replace-meter",
    response_model=FleetVehicleOut,
    dependencies=_CORRECT,
)
async def replace_meter(
    vehicle_id: uuid.UUID,
    body: MeterReplacementIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, repo, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    read_at = body.read_at or datetime.now(UTC)
    if in_future(read_at, datetime.now(UTC)):
        raise ValidationError("La fecha no puede ser futura.", code="odometer_future")
    latest = await session.scalar(
        select(func.max(OdometerReadingModel.read_at)).where(
            OdometerReadingModel.vehicle_id == vehicle.id,
            OdometerReadingModel.voided_at.is_(None),
        )
    )
    if latest is not None and read_at < latest:
        raise ConflictError(
            "El cambio debe ser posterior a la última lectura registrada.",
            code="odometer_out_of_order",
        )
    old = Decimal(vehicle.odometer_km)
    new = Decimal(body.reading_km)
    async with session.begin_nested():
        session.add(
            OdometerReadingModel(
                company_id=company_id,
                vehicle_id=vehicle.id,
                reading_km=new,
                read_at=read_at,
                source="meter_replacement",
                notes=f"Cambio de tablero (marcaba {old}): {body.reason.strip()}"[:500],
                recorded_by=current.id,
            )
        )
        vehicle.odometer_km = new
        await _shift_plans(session, vehicle, new - old)
        await session.flush()
        await audit.record(
            action="REPLACE_METER",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"odometer_km": str(old)},
            after_state={"odometer_km": str(new)},
            metadata={"reason": body.reason},
            required=True,
        )
    return await _vehicle_out(repo, company_id, vehicle)


@router.get(
    "/vehicles/{vehicle_id}/odometer/total",
    response_model=OdometerTotalOut,
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def odometer_total(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> OdometerTotalOut:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    vehicle = await scoped_vehicle(FleetRepository(session), scope, vehicle_id)
    rows = await session.execute(
        select(OdometerReadingModel.reading_km, OdometerReadingModel.source)
        .where(
            OdometerReadingModel.vehicle_id == vehicle.id,
            OdometerReadingModel.voided_at.is_(None),
        )
        .order_by(OdometerReadingModel.read_at, OdometerReadingModel.created_at)
    )
    readings = [(Decimal(reading), source) for reading, source in rows.all()]
    return OdometerTotalOut(
        total=total_distance(readings),
        replacements=sum(1 for _, source in readings if source == "meter_replacement"),
    )


async def _void_fuel(
    session: SessionDep,
    vehicle: FleetVehicleModel,
    log_id: uuid.UUID,
    actor: uuid.UUID,
    reason: str,
) -> FuelLogModel:
    log = await session.scalar(
        select(FuelLogModel)
        .where(FuelLogModel.id == log_id, FuelLogModel.vehicle_id == vehicle.id)
        .with_for_update()
    )
    if log is None:
        raise NotFoundError("Carga no encontrada.", code="fuel_log_not_found")
    if log.voided_at is not None:
        raise ConflictError("La carga ya está anulada.", code="record_already_voided")
    _void(log, actor, reason)
    # La lectura de la carga era igual de falsa: sin esto, seguiría bloqueando el odómetro.
    reading = await session.scalar(
        select(OdometerReadingModel)
        .where(
            OdometerReadingModel.vehicle_id == vehicle.id,
            OdometerReadingModel.source == "fuel",
            OdometerReadingModel.read_at == log.filled_at,
            OdometerReadingModel.reading_km == log.odometer_km,
            OdometerReadingModel.voided_at.is_(None),
        )
        .limit(1)
    )
    if reading is not None:
        _void(reading, actor, reason)
    await session.flush()
    await _refresh_meter(session, vehicle)
    await session.flush()
    return log


@router.post(
    "/vehicles/{vehicle_id}/fuel-logs/{log_id}/void",
    response_model=FleetVehicleOut,
    dependencies=_CORRECT,
)
async def void_fuel_log(
    vehicle_id: uuid.UUID,
    log_id: uuid.UUID,
    body: VoidRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, repo, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    async with session.begin_nested():
        log = await _void_fuel(session, vehicle, log_id, current.id, body.reason)
        await audit.record(
            action="VOID_FUEL_LOG",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"log_id": str(log.id), "liters": str(log.liters)},
            metadata={"reason": body.reason},
            required=True,
        )
    return await _vehicle_out(repo, company_id, vehicle)


@router.put(
    "/vehicles/{vehicle_id}/fuel-logs/{log_id}",
    response_model=FuelLogOut,
    dependencies=_CORRECT,
)
async def correct_fuel_log(
    vehicle_id: uuid.UUID,
    log_id: uuid.UUID,
    body: FuelCorrectionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FuelLogOut:
    company_id, repo, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    driver_name = await fuel_driver_name(repo, company_id, vehicle, body.driver_id)
    async with session.begin_nested():
        old = await _void_fuel(session, vehicle, log_id, current.id, body.reason)
        new = await create_fuel_log(session, vehicle, body, current.id)
        await audit.record(
            action="CORRECT_FUEL_LOG",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={
                "log_id": str(old.id),
                "liters": str(old.liters),
                "amount": str(old.total_amount),
                "odometer_km": str(old.odometer_km),
            },
            after_state={
                "log_id": str(new.id),
                "liters": str(new.liters),
                "amount": str(new.total_amount),
                "odometer_km": str(new.odometer_km),
            },
            metadata={"reason": body.reason},
            required=True,
        )
    return fuel_log_out(new, driver_name)

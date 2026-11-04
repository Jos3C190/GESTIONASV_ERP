"""A company's fleet rules, plus who has a vehicle: branch loans and reservations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import get_fleet_scope
from app.api.v1.routers.fleet import require_not_on_road, scoped_vehicle
from app.api.v1.schemas.fleet import (
    FleetLoanIn,
    FleetLoanOut,
    FleetReservationIn,
    FleetReservationOut,
    FleetSettingsIn,
    FleetSettingsOut,
    VoidRecordIn,
)
from app.application.audit.audit_service import AuditService
from app.application.fleet.costs import business_today
from app.application.fleet.settings import settings_from
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.models.fleet import (
    FleetReservationModel,
    FleetSettingsModel,
    FleetVehicleLoanModel,
    FleetVehicleModel,
)
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-schedule"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_READ = [Depends(require_permission("fleet:read"))]


# ------------------------------------------------------------------ settings


@router.get("/settings", response_model=FleetSettingsOut, dependencies=_READ)
async def get_settings(request: Request, session: SessionDep) -> FleetSettingsOut:
    row = await session.get(FleetSettingsModel, effective_company_id(request))
    return FleetSettingsOut.model_validate(settings_from(row), from_attributes=True)


@router.put(
    "/settings",
    response_model=FleetSettingsOut,
    dependencies=[Depends(require_permission("fleet:settings"))],
)
async def save_settings(
    body: FleetSettingsIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: Audit,
) -> FleetSettingsOut:
    company_id = effective_company_id(request)
    # La primera vez, dos guardados a la vez no deben chocar al crear la fila.
    existed = await session.get(FleetSettingsModel, company_id)
    before = FleetSettingsOut.model_validate(settings_from(existed), from_attributes=True)
    await session.execute(
        insert(FleetSettingsModel).values(company_id=company_id).on_conflict_do_nothing()
    )
    row = await session.get(
        FleetSettingsModel, company_id, with_for_update=True, populate_existing=True
    )
    assert row is not None
    async with session.begin_nested():
        for field, value in body.model_dump().items():
            setattr(row, field, value)
        row.updated_by = current.id
        await session.flush()
        await audit.record(
            action="UPDATE_FLEET_SETTINGS",
            user_id=current.id,
            company_id=company_id,
            resource_type="fleet_settings",
            resource_id=str(company_id),
            before_state=before.model_dump(),
            after_state=body.model_dump(),
            required=True,
        )
    return FleetSettingsOut.model_validate(settings_from(row), from_attributes=True)


# ------------------------------------------------------------------ shared


async def _vehicle(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    vehicle_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[uuid.UUID, FleetRepository, FleetVehicleModel]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    repo = FleetRepository(session)
    return company_id, repo, await scoped_vehicle(repo, scope, vehicle_id, lock=lock)


# ------------------------------------------------------------------ loans


async def _loans(session: SessionDep, *conditions: object) -> list[FleetLoanOut]:
    origin = aliased(Branch)
    target = aliased(Branch)
    rows = await session.execute(
        select(FleetVehicleLoanModel, origin.name, target.name, User.username)
        .join(origin, origin.id == FleetVehicleLoanModel.from_branch_id)
        .join(target, target.id == FleetVehicleLoanModel.to_branch_id)
        .outerjoin(User, User.id == FleetVehicleLoanModel.created_by)
        .where(*conditions)  # type: ignore[arg-type]
        .execution_options(include_deleted=True)
        .order_by(FleetVehicleLoanModel.created_at.desc())
        .limit(100)
    )
    return [
        FleetLoanOut(
            id=loan.id,
            from_branch_id=loan.from_branch_id,
            from_branch_name=from_name,
            to_branch_id=loan.to_branch_id,
            to_branch_name=to_name,
            starts_on=loan.starts_on,
            expected_return_on=loan.expected_return_on,
            reason=loan.reason,
            returned_at=loan.returned_at,
            created_by_name=created_by,
        )
        for loan, from_name, to_name, created_by in rows.all()
    ]


@router.get("/vehicles/{vehicle_id}/loans", response_model=list[FleetLoanOut], dependencies=_READ)
async def list_loans(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[FleetLoanOut]:
    _, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    return await _loans(session, FleetVehicleLoanModel.vehicle_id == vehicle.id)


@router.post(
    "/vehicles/{vehicle_id}/loans",
    response_model=FleetLoanOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:loans"))],
)
async def lend_vehicle(
    vehicle_id: uuid.UUID,
    body: FleetLoanIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetLoanOut:
    company_id, repo, vehicle = await _vehicle(
        request, session, current, checker, vehicle_id, lock=True
    )
    # Como al cambiar de sucursal: solo se entrega a una sucursal a la que se tiene acceso.
    (await get_fleet_scope(session, current, checker, company_id)).require_target(body.to_branch_id)
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    if vehicle.status == "maintenance":
        raise ConflictError("El vehículo está en el taller.", code="vehicle_in_maintenance")
    if await repo.open_coupling(vehicle.id):
        raise ConflictError(
            "Desenganche el remolque antes de prestar el vehículo.", code="vehicle_is_coupled"
        )
    if body.to_branch_id == vehicle.branch_id:
        raise ValidationError(
            "Elija una sucursal distinta a la del vehículo.", code="loan_same_branch"
        )
    target = await repo.branch(company_id, body.to_branch_id)
    if target is None or not target.is_active:
        raise ValidationError("La sucursal no existe o no está activa.", code="branch_inactive")
    today = business_today()
    if body.expected_return_on < today:
        raise ValidationError(
            "La devolución esperada no puede ser una fecha pasada.", code="loan_return_past"
        )
    await require_not_on_road(repo, vehicle, "prestarlo")
    try:
        async with session.begin_nested():
            loan = FleetVehicleLoanModel(
                company_id=company_id,
                vehicle_id=vehicle.id,
                from_branch_id=vehicle.branch_id,
                to_branch_id=body.to_branch_id,
                starts_on=today,
                expected_return_on=body.expected_return_on,
                reason=body.reason.strip(),
                created_by=current.id,
            )
            session.add(loan)
            await session.flush()
    except IntegrityError as exc:
        raise ConflictError("El vehículo ya está prestado.", code="vehicle_on_loan") from exc
    await audit.record(
        action="LEND_VEHICLE",
        user_id=current.id,
        company_id=company_id,
        branch_id=vehicle.branch_id,
        resource_type="fleet_vehicles",
        resource_id=str(vehicle.id),
        after_state={"loan_id": str(loan.id), "to_branch_id": str(loan.to_branch_id)},
        metadata={"reason": loan.reason},
        required=True,
    )
    return (await _loans(session, FleetVehicleLoanModel.id == loan.id))[0]


@router.post(
    "/vehicles/{vehicle_id}/loans/{loan_id}/return",
    response_model=FleetLoanOut,
    dependencies=[Depends(require_permission("fleet:loans"))],
)
async def return_vehicle(
    vehicle_id: uuid.UUID,
    loan_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetLoanOut:
    company_id, repo, vehicle = await _vehicle(
        request, session, current, checker, vehicle_id, lock=True
    )
    loan = await session.scalar(
        select(FleetVehicleLoanModel)
        .where(FleetVehicleLoanModel.id == loan_id, FleetVehicleLoanModel.vehicle_id == vehicle.id)
        .with_for_update()
    )
    if loan is None:
        raise NotFoundError("Préstamo no encontrado.", code="fleet_loan_not_found")
    if loan.returned_at is not None:
        raise ConflictError("El vehículo ya fue devuelto.", code="loan_already_returned")
    await require_not_on_road(repo, vehicle, "devolverlo")
    async with session.begin_nested():
        loan.returned_at = datetime.now(UTC)
        loan.returned_by = current.id
        await session.flush()
        await audit.record(
            action="RETURN_VEHICLE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"loan_id": str(loan.id)},
            required=True,
        )
    return (await _loans(session, FleetVehicleLoanModel.id == loan.id))[0]


# ------------------------------------------------------------------ reservations


async def _reservations(session: SessionDep, *conditions: object) -> list[FleetReservationOut]:
    rows = await session.execute(
        select(FleetReservationModel, User.username)
        .outerjoin(User, User.id == FleetReservationModel.reserved_by)
        .where(*conditions)  # type: ignore[arg-type]
        .order_by(FleetReservationModel.starts_at.desc())
        .limit(100)
    )
    return [
        FleetReservationOut(
            id=reservation.id,
            starts_at=reservation.starts_at,
            ends_at=reservation.ends_at,
            reason=reservation.reason,
            status=reservation.status,
            reserved_by_name=reserved_by,
            cancel_reason=reservation.cancel_reason,
        )
        for reservation, reserved_by in rows.all()
    ]


@router.get(
    "/vehicles/{vehicle_id}/reservations",
    response_model=list[FleetReservationOut],
    dependencies=_READ,
)
async def list_reservations(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[FleetReservationOut]:
    _, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    return await _reservations(session, FleetReservationModel.vehicle_id == vehicle.id)


@router.post(
    "/vehicles/{vehicle_id}/reservations",
    response_model=FleetReservationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:reservations"))],
)
async def reserve_vehicle(
    vehicle_id: uuid.UUID,
    body: FleetReservationIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetReservationOut:
    company_id, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    if body.ends_at <= body.starts_at:
        raise ValidationError(
            "El fin de la reserva debe ser posterior al inicio.", code="reservation_dates"
        )
    if body.ends_at <= datetime.now(UTC):
        raise ValidationError("La reserva ya habría terminado.", code="reservation_past")
    try:
        async with session.begin_nested():
            reservation = FleetReservationModel(
                company_id=company_id,
                vehicle_id=vehicle.id,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                reason=body.reason.strip(),
                reserved_by=current.id,
            )
            session.add(reservation)
            await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "El vehículo ya está reservado en esas fechas.", code="reservation_overlap"
        ) from exc
    await audit.record(
        action="RESERVE_VEHICLE",
        user_id=current.id,
        company_id=company_id,
        branch_id=vehicle.branch_id,
        resource_type="fleet_vehicles",
        resource_id=str(vehicle.id),
        after_state={"reservation_id": str(reservation.id)},
        required=True,
    )
    return (await _reservations(session, FleetReservationModel.id == reservation.id))[0]


@router.post(
    "/vehicles/{vehicle_id}/reservations/{reservation_id}/cancel",
    response_model=FleetReservationOut,
    dependencies=[Depends(require_permission("fleet:reservations"))],
)
async def cancel_reservation(
    vehicle_id: uuid.UUID,
    reservation_id: uuid.UUID,
    body: VoidRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetReservationOut:
    company_id, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    # Se puede cancelar también en un vehículo ya dado de baja: esas fechas ya no aplican.
    reservation = await session.scalar(
        select(FleetReservationModel)
        .where(
            FleetReservationModel.id == reservation_id,
            FleetReservationModel.vehicle_id == vehicle.id,
        )
        .with_for_update()
    )
    if reservation is None:
        raise NotFoundError("Reserva no encontrada.", code="fleet_reservation_not_found")
    if reservation.status != "active":
        raise ConflictError("La reserva ya está cancelada.", code="reservation_cancelled")
    async with session.begin_nested():
        reservation.status = "cancelled"
        reservation.cancelled_by = current.id
        reservation.cancel_reason = body.reason.strip()
        await session.flush()
        await audit.record(
            action="CANCEL_RESERVATION",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"reservation_id": str(reservation.id)},
            metadata={"reason": reservation.cancel_reason},
            required=True,
        )
    return (await _reservations(session, FleetReservationModel.id == reservation.id))[0]

"""Drivers: employees with a driving profile, their license and vehicle assignment.

A driver always is an employee of the same company with an active assignment
in the driver's home branch. Drivers and vehicles are branch-scoped exactly
like the fleet (:mod:`app.api.v1.fleet_scope`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
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
from app.api.v1.routers.fleet import scoped_vehicle
from app.api.v1.routers.owned_documents import (
    OwnedDocumentsSpec,
    OwnerContext,
    build_owned_documents_router,
)
from app.api.v1.schemas.fleet import (
    AssignmentEndIn,
    AssignmentIn,
    AssignmentOut,
    DriverBranchIn,
    DriverCandidateOut,
    DriverCreate,
    DriverOut,
    DriversPage,
    DriverStatusIn,
    DriverTripOut,
    DriverUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.fleet.compliance import Issue, license_issue
from app.application.fleet.driver_views import build_driver_views, driver_fitness
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.document_categories import DRIVER_CATEGORY_CODES
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleModel,
    VehicleDriverAssignmentModel,
)
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(tags=["drivers"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]

OVERRIDE_PERMISSION = "fleet:compliance_override"
MIN_REASON_LENGTH = 3
#: Issues that no override can bypass: the person cannot drive for the company.
HARD_BLOCKS = frozenset({"driver_not_active", "employee_not_active"})


def _today() -> Any:
    return datetime.now(UTC).date()


def _state(driver: DriverModel) -> dict[str, object]:
    return {
        "employee_id": str(driver.employee_id),
        "branch_id": str(driver.branch_id),
        "license_class": driver.license_class,
        "status": driver.status,
    }


async def _context(
    request: Request, session: SessionDep, current: CurrentUser, checker: CheckPermissionUseCase
) -> tuple[uuid.UUID, FleetScope, FleetRepository]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    return company_id, scope, FleetRepository(session)


async def scoped_driver(
    repo: FleetRepository, scope: FleetScope, driver_id: uuid.UUID, *, lock: bool = False
) -> DriverModel:
    driver = await repo.get_driver(scope.company_id, driver_id, lock=lock)
    if driver is None:
        raise NotFoundError("Conductor no encontrado.", code="driver_not_found")
    scope.require(driver.branch_id, not_found="Conductor no encontrado.")
    return driver


async def _view(repo: FleetRepository, company_id: uuid.UUID, driver_id: uuid.UUID) -> DriverOut:
    row = await repo.driver_with_employee(company_id, driver_id)
    if row is None:
        raise NotFoundError("Conductor no encontrado.", code="driver_not_found")
    views = await build_driver_views(repo, company_id, [row], today=_today())
    return DriverOut.model_validate(views[0])


async def _end_assignment(
    session: SessionDep,
    assignment: VehicleDriverAssignmentModel,
    *,
    actor_id: uuid.UUID,
    reason: str,
) -> None:
    assignment.ends_at = datetime.now(UTC)
    assignment.ended_by = actor_id
    assignment.end_reason = reason
    await session.flush()


def _summarize(issues: list[Issue]) -> str:
    return " ".join(issue.message for issue in issues if issue.severity == "blocking")


# ------------------------------------------------------------------ drivers


@router.get(
    "/drivers",
    response_model=DriversPage,
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def list_drivers(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID | None = Query(None),
    driver_status: str | None = Query(
        None, alias="status", pattern="^(active|suspended|inactive)$"
    ),
    search: str | None = Query(None, max_length=80),
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=100),
) -> DriversPage:
    company_id, scope, repo = await _context(request, session, current, checker)
    rows, total = await repo.list_drivers(
        company_id,
        scope.list_filter(branch_id),
        status=driver_status,
        search=search,
        page=page,
        size=size,
    )
    views = await build_driver_views(repo, company_id, rows, today=_today())
    return DriversPage(
        items=[DriverOut.model_validate(view) for view in views],
        meta={
            "page": page,
            "size": size,
            "total": total,
            "pages": (total + size - 1) // size if total else 1,
        },
    )


@router.get(
    "/drivers/summary",
    response_model=dict[str, int],
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def drivers_summary(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID | None = Query(None),
) -> dict[str, int]:
    company_id, scope, repo = await _context(request, session, current, checker)
    rows, total = await repo.list_drivers(
        company_id, scope.list_filter(branch_id), status=None, search=None, page=1, size=10_000
    )
    views = await build_driver_views(repo, company_id, rows, today=_today())
    states = [view["compliance"]["state"] for view in views if view["status"] == "active"]
    return {
        "total": total,
        "active": sum(1 for view in views if view["status"] == "active"),
        "fit": states.count("ok"),
        "warning": states.count("warning"),
        "blocked": states.count("blocked"),
        "assigned": sum(1 for view in views if view["vehicle"]),
    }


@router.get(
    "/drivers/candidates",
    response_model=list[DriverCandidateOut],
    dependencies=[Depends(require_permission("drivers:create"))],
)
async def driver_candidates(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID = Query(...),
    search: str | None = Query(None, max_length=80),
) -> list[DriverCandidateOut]:
    company_id, scope, repo = await _context(request, session, current, checker)
    scope.require_target(branch_id)
    employees = await repo.driver_candidates(company_id, branch_id, search)
    return [
        DriverCandidateOut(
            employee_id=employee.id,
            code=employee.employee_code,
            name=f"{employee.first_name} {employee.last_name}".strip(),
            position=employee.position,
            photo_url=employee.photo_url,
        )
        for employee in employees
    ]


@router.get(
    "/drivers/{driver_id}",
    response_model=DriverOut,
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def get_driver(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> DriverOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, driver_id)
    return await _view(repo, company_id, driver.id)


@router.post(
    "/drivers",
    response_model=DriverOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("drivers:create"))],
)
async def create_driver(
    body: DriverCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> DriverOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    scope.require_target(body.branch_id)
    employee = await session.get(Employee, body.employee_id)
    if employee is None or employee.company_id != company_id or employee.deleted_at is not None:
        raise NotFoundError("Empleado no encontrado.", code="employee_not_found")
    if employee.status != "activo":
        raise ConflictError(
            "Solo un empleado activo puede ser conductor.", code="employee_not_active"
        )
    if not await repo.employee_has_branch_assignment(employee.id, body.branch_id):
        raise ConflictError(
            "El empleado no tiene una asignación activa en esa sucursal.",
            code="employee_branch_unassigned",
        )
    async with session.begin_nested():
        driver = DriverModel(
            company_id=company_id,
            employee_id=employee.id,
            branch_id=body.branch_id,
            license_class=body.license_class,
            notes=(body.notes or "").strip() or None,
            status="active",
            created_by=current.id,
            updated_by=current.id,
        )
        session.add(driver)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "El empleado ya tiene un perfil de conductor.", code="driver_exists"
            ) from exc
        await audit.record(
            action="CREATE",
            user_id=current.id,
            company_id=company_id,
            branch_id=driver.branch_id,
            resource_type="drivers",
            resource_id=str(driver.id),
            after_state=_state(driver),
            required=True,
        )
    return await _view(repo, company_id, driver.id)


@router.patch(
    "/drivers/{driver_id}",
    response_model=DriverOut,
    dependencies=[Depends(require_permission("drivers:update"))],
)
async def update_driver(
    driver_id: uuid.UUID,
    body: DriverUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> DriverOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, driver_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("license_class") and changes["license_class"] != driver.license_class:
        vehicle_info = (await repo.open_vehicles_for_drivers([driver.id])).get(driver.id)
        if (
            vehicle_info is not None
            and license_issue(changes["license_class"], vehicle_info["kind"]) is not None
        ):
            raise ConflictError(
                f"La nueva clase de licencia no permite conducir {vehicle_info['code']}; "
                "finalice la asignación primero.",
                code="license_class_incompatible",
            )
    before = _state(driver)
    async with session.begin_nested():
        if changes.get("license_class"):
            driver.license_class = changes["license_class"]
        if "notes" in changes:
            driver.notes = (changes["notes"] or "").strip() or None
        driver.updated_by = current.id
        await session.flush()
        await audit.record(
            action="UPDATE",
            user_id=current.id,
            company_id=company_id,
            branch_id=driver.branch_id,
            resource_type="drivers",
            resource_id=str(driver.id),
            before_state=before,
            after_state=_state(driver),
            required=True,
        )
    return await _view(repo, company_id, driver.id)


@router.post(
    "/drivers/{driver_id}/status",
    response_model=DriverOut,
    dependencies=[Depends(require_permission("drivers:update"))],
)
async def change_driver_status(
    driver_id: uuid.UUID,
    body: DriverStatusIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> DriverOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, driver_id, lock=True)
    if body.status == driver.status:
        return await _view(repo, company_id, driver.id)
    reason = (body.reason or "").strip()
    if body.status != "active" and len(reason) < MIN_REASON_LENGTH:
        raise ValidationError("Indique el motivo del cambio de estado.", code="reason_required")
    if body.status == "active":
        employee = await session.get(Employee, driver.employee_id)
        if employee is None or employee.status != "activo":
            raise ConflictError("El empleado no está activo.", code="employee_not_active")
        if not await repo.employee_has_branch_assignment(driver.employee_id, driver.branch_id):
            raise ConflictError(
                "El empleado ya no tiene asignación activa en la sucursal base; cámbiela primero.",
                code="employee_branch_unassigned",
            )
    before = _state(driver)
    async with session.begin_nested():
        if body.status != "active":
            # Un conductor suspendido o inactivo no puede quedar al mando de un vehículo.
            assignment = await repo.open_assignment_for_driver(driver.id)
            if assignment is not None:
                await _end_assignment(
                    session,
                    assignment,
                    actor_id=current.id,
                    reason=f"Conductor {'suspendido' if body.status == 'suspended' else 'inactivo'}: {reason}",
                )
        driver.status = body.status
        driver.status_reason = reason or None
        driver.updated_by = current.id
        await session.flush()
        await audit.record(
            action="STATUS_CHANGE",
            user_id=current.id,
            company_id=company_id,
            branch_id=driver.branch_id,
            resource_type="drivers",
            resource_id=str(driver.id),
            before_state=before,
            after_state=_state(driver),
            metadata={"reason": reason or None},
            required=True,
        )
    return await _view(repo, company_id, driver.id)


@router.post(
    "/drivers/{driver_id}/branch",
    response_model=DriverOut,
    dependencies=[Depends(require_permission("drivers:update"))],
)
async def change_driver_branch(
    driver_id: uuid.UUID,
    body: DriverBranchIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> DriverOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, driver_id, lock=True)
    scope.require_target(body.branch_id)
    if body.branch_id == driver.branch_id:
        return await _view(repo, company_id, driver.id)
    if not await repo.employee_has_branch_assignment(driver.employee_id, body.branch_id):
        raise ConflictError(
            "El empleado no tiene una asignación activa en la sucursal destino.",
            code="employee_branch_unassigned",
        )
    if await repo.open_assignment_for_driver(driver.id) is not None:
        raise ConflictError(
            "Finalice la asignación del vehículo antes de cambiar la sucursal del conductor.",
            code="driver_has_vehicle",
        )
    before = _state(driver)
    async with session.begin_nested():
        driver.branch_id = body.branch_id
        driver.updated_by = current.id
        await session.flush()
        await audit.record(
            action="CHANGE_BRANCH",
            user_id=current.id,
            company_id=company_id,
            branch_id=body.branch_id,
            resource_type="drivers",
            resource_id=str(driver.id),
            before_state=before,
            after_state=_state(driver),
            metadata={"reason": body.reason},
            required=True,
        )
    return await _view(repo, company_id, driver.id)


@router.get(
    "/drivers/{driver_id}/assignments",
    response_model=list[AssignmentOut],
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def driver_assignments(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[AssignmentOut]:
    _, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, driver_id)
    return [
        AssignmentOut.model_validate(item)
        for item in await repo.assignment_history(driver_id=driver.id)
    ]


@router.get(
    "/drivers/{driver_id}/trips",
    response_model=list[DriverTripOut],
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def driver_trips(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[DriverTripOut]:
    company_id, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, driver_id)
    return [
        DriverTripOut.model_validate(item)
        for item in await repo.driver_trips(company_id, driver.id)
    ]


# ------------------------------------------------------------------ assignments


async def assign_driver_to_vehicle(
    *,
    session: SessionDep,
    repo: FleetRepository,
    checker: CheckPermissionUseCase,
    current: CurrentUser,
    audit: AuditService,
    vehicle: FleetVehicleModel,
    driver: DriverModel,
    override_reason: str | None,
) -> VehicleDriverAssignmentModel:
    """Assign a driver to a vehicle, closing their previous assignments."""
    company_id = vehicle.company_id
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    if driver.branch_id != vehicle.branch_id:
        raise ConflictError(
            "El conductor y el vehículo deben pertenecer a la misma sucursal.",
            code="driver_vehicle_branch_mismatch",
        )
    employee = await session.get(Employee, driver.employee_id)
    issues, _ = (
        await driver_fitness(
            repo,
            company_id,
            [(driver, employee)],
            today=_today(),
            vehicle_kinds={driver.id: vehicle.kind},
        )
    )[driver.id]
    blocking = [issue for issue in issues if issue.severity == "blocking"]
    if any(issue.code in HARD_BLOCKS for issue in blocking):
        raise ConflictError(_summarize(blocking), code="driver_not_fit")
    if blocking:
        allowed = (
            current.is_superuser
            or (await checker.execute(current.id, company_id, OVERRIDE_PERMISSION)).allowed
        )
        if not override_reason or not allowed:
            raise ConflictError(
                _summarize(blocking)
                + (
                    ""
                    if allowed
                    else " Solo un usuario con autorización de excepciones puede asignarlo."
                ),
                code="driver_not_fit",
            )
    previous_vehicle = await repo.open_assignment_for_vehicle(vehicle.id, lock=True)
    if previous_vehicle is not None and previous_vehicle.driver_id == driver.id:
        return previous_vehicle
    if previous_vehicle is not None:
        await _end_assignment(
            session, previous_vehicle, actor_id=current.id, reason="Reasignación del vehículo."
        )
    previous_driver = await repo.open_assignment_for_driver(driver.id)
    if previous_driver is not None:
        await _end_assignment(
            session, previous_driver, actor_id=current.id, reason="Asignado a otro vehículo."
        )
    assignment = VehicleDriverAssignmentModel(
        company_id=company_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        starts_at=datetime.now(UTC),
        assigned_by=current.id,
    )
    session.add(assignment)
    await session.flush()
    await audit.record(
        action="ASSIGN_DRIVER",
        user_id=current.id,
        company_id=company_id,
        branch_id=vehicle.branch_id,
        resource_type="fleet_vehicles",
        resource_id=str(vehicle.id),
        after_state={"driver_id": str(driver.id), "assignment_id": str(assignment.id)},
        metadata={
            "compliance_override": override_reason if blocking else None,
            "issues": [issue.message for issue in blocking],
        },
        required=True,
    )
    return assignment


@router.post(
    "/fleet/vehicles/{vehicle_id}/assignment",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("drivers:assign"))],
)
async def assign_driver(
    vehicle_id: uuid.UUID,
    body: AssignmentIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> AssignmentOut:
    _, scope, repo = await _context(request, session, current, checker)
    async with session.begin_nested():
        vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
        driver = await scoped_driver(repo, scope, body.driver_id, lock=True)
        await assign_driver_to_vehicle(
            session=session,
            repo=repo,
            checker=checker,
            current=current,
            audit=audit,
            vehicle=vehicle,
            driver=driver,
            override_reason=body.override_reason,
        )
    history = await repo.assignment_history(vehicle_id=vehicle.id)
    return AssignmentOut.model_validate(history[0])


@router.post(
    "/fleet/vehicles/{vehicle_id}/assignment/end",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("drivers:assign"))],
)
async def end_vehicle_assignment(
    vehicle_id: uuid.UUID,
    body: AssignmentEndIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> None:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    assignment = await repo.open_assignment_for_vehicle(vehicle.id, lock=True)
    if assignment is None:
        raise NotFoundError("El vehículo no tiene conductor asignado.", code="assignment_not_found")
    async with session.begin_nested():
        await _end_assignment(session, assignment, actor_id=current.id, reason=body.reason.strip())
        await audit.record(
            action="END_ASSIGNMENT",
            user_id=current.id,
            company_id=vehicle.company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"driver_id": str(assignment.driver_id)},
            metadata={"reason": body.reason.strip()},
            required=True,
        )


@router.get(
    "/fleet/vehicles/{vehicle_id}/assignments",
    response_model=list[AssignmentOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def vehicle_assignments(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[AssignmentOut]:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    return [
        AssignmentOut.model_validate(item)
        for item in await repo.assignment_history(vehicle_id=vehicle.id)
    ]


# ------------------------------------------------------------------ license documents


async def _resolve_driver_owner(
    owner_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
) -> OwnerContext:
    company_id, scope, repo = await _context(request, session, current, checker)
    driver = await scoped_driver(repo, scope, owner_id)
    # Las licencias viven en el expediente del empleado: RR. HH. las ve en su módulo.
    return OwnerContext(company_id=company_id, owner_id=driver.employee_id)


documents_router = build_owned_documents_router(
    OwnedDocumentsSpec(
        path="",
        module="employees",
        owner_type="employee",
        read="drivers:read",
        upload="drivers:documents",
        update="drivers:documents",
        download="drivers:read",
        resolve=_resolve_driver_owner,
        category_codes=DRIVER_CATEGORY_CODES,
    ),
    prefix="/drivers",
    tag="driver-documents",
)

__all__ = ["assign_driver_to_vehicle", "documents_router", "router", "scoped_driver"]

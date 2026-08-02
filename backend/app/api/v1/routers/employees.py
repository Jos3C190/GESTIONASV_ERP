"""Employees router — CRUD + link/unlink user account."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.v1.company_access import require_company_access, resolve_branch_scope
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.common import MessageOut
from app.api.v1.schemas.employees import (
    CreateEmployeeRequest,
    EmployeeOut,
    EmployeeStatsOut,
    Page,
    PageMeta,
    UpdateEmployeeRequest,
)
from app.application.audit.audit_service import AuditService, employee_to_audit_state
from app.application.employees.employee_crud import (
    CreateEmployeeInput,
    CreateEmployeeUseCase,
    DeleteEmployeeUseCase,
    GetEmployeeUseCase,
    ListEmployeesInput,
    ListEmployeesUseCase,
    UpdateEmployeeInput,
    UpdateEmployeeUseCase,
)
from app.domain.entities.employee import EmployeeStatus
from app.domain.ports.department_repository import DepartmentRepository
from app.domain.ports.employee_repository import EmployeeRepository
from app.infrastructure.models.employee import (
    DepartmentBranchAssignment,
    EmployeeBranchAssignment,
)
from app.infrastructure.media_assets import attach_media_by_url

router = APIRouter(prefix="/employees", tags=["employees"])


def _request_branch_id(request: Request) -> uuid.UUID | None:
    raw = request.headers.get("X-Branch-ID")
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(422, "El encabezado X-Branch-ID no es válido.") from exc


async def _require_employee_scope(
    session: SessionDep,
    current: CurrentUser,
    request: Request,
    *,
    employee_id: uuid.UUID,
    company_id: uuid.UUID,
) -> uuid.UUID | None:
    branch_id = _request_branch_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    if branch_id is not None:
        assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == employee_id,
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        )
        if assignment is None:
            raise HTTPException(404, "Empleado no encontrado en la sucursal seleccionada.")
    return branch_id


def _get_emp_repo(session: SessionDep) -> EmployeeRepository:
    from app.infrastructure.repositories import SqlAlchemyEmployeeRepository

    return SqlAlchemyEmployeeRepository(session)


def _get_dept_repo(session: SessionDep) -> DepartmentRepository:
    from app.infrastructure.repositories import SqlAlchemyDepartmentRepository

    return SqlAlchemyDepartmentRepository(session)


@router.get(
    "",
    response_model=Page[EmployeeOut],
    status_code=status.HTTP_200_OK,
    summary="Listar empleados (paginado)",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def list_employees(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    department_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    branch_id: uuid.UUID | None = Query(None),
) -> Page[EmployeeOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    uc = ListEmployeesUseCase(repo)
    result = await uc.execute(
        ListEmployeesInput(
            page=page,
            size=size,
            search=search,
            department_id=department_id,
            status=status_filter,
            company_id=company_id,
            branch_id=branch_id,
        )
    )
    return Page[EmployeeOut](
        items=[EmployeeOut.model_validate(e, from_attributes=True) for e in result.items],
        meta=PageMeta(page=result.page, size=result.size, total=result.total, pages=result.pages),
    )


@router.get(
    "/stats",
    response_model=EmployeeStatsOut,
    status_code=status.HTTP_200_OK,
    summary="Estadísticas agregadas de empleados",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def get_employee_stats(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    branch_id: uuid.UUID | None = Query(None),
) -> EmployeeStatsOut:
    """Returns aggregate counts via a single SQL GROUP BY — scales to any number of employees."""
    await resolve_branch_scope(session, current, company_id, branch_id)
    stats = await repo.get_stats(company_id, branch_id)
    return EmployeeStatsOut(
        total=stats.total,
        active=stats.active,
        inactive=stats.inactive,
        on_leave=stats.on_leave,
        terminated=stats.terminated,
        linked_to_user=stats.linked_to_user,
    )


@router.get(
    "/{emp_id}",
    response_model=EmployeeOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener empleado por id",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def get_employee(
    emp_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    branch_id: uuid.UUID | None = Query(None),
) -> EmployeeOut:
    uc = GetEmployeeUseCase(repo)
    e = await uc.execute(emp_id)
    await resolve_branch_scope(session, current, e.company_id, branch_id)
    if branch_id is not None:
        assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == emp_id,
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        )
        if assignment is None:
            raise HTTPException(404, "Empleado no encontrado en la sucursal seleccionada.")
    return EmployeeOut.model_validate(e, from_attributes=True)


@router.post(
    "",
    response_model=EmployeeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear empleado",
    dependencies=[Depends(require_permission("employees:create"))],
)
async def create_employee(
    body: CreateEmployeeRequest,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    dept_repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> EmployeeOut:
    await require_company_access(session, current, body.company_id, require_active=True)
    branch_id = _request_branch_id(request)
    await resolve_branch_scope(session, current, body.company_id, branch_id)
    if branch_id is not None and body.department_id is not None:
        enabled = await session.scalar(
            select(DepartmentBranchAssignment.id).where(
                DepartmentBranchAssignment.department_id == body.department_id,
                DepartmentBranchAssignment.branch_id == branch_id,
                DepartmentBranchAssignment.is_active.is_(True),
            )
        )
        if enabled is None:
            raise HTTPException(
                409, "El departamento debe estar habilitado en la sucursal seleccionada."
            )
    uc = CreateEmployeeUseCase(repo, dept_repo)
    e = await uc.execute(
        CreateEmployeeInput(
            company_id=body.company_id,
            employee_code=body.employee_code,
            first_name=body.first_name,
            last_name=body.last_name,
            user_id=body.user_id,
            document_id=body.document_id,
            birth_date=body.birth_date,
            phone=body.phone,
            address=body.address,
            department_id=body.department_id,
            position=body.position,
            hire_date=body.hire_date,
            status=EmployeeStatus(body.status),
            photo_url=body.photo_url,
        )
    )
    await attach_media_by_url(
        session, secure_url=e.photo_url, company_id=e.company_id,
        owner_type="employee", owner_id=e.id, replace_single=True,
    )
    if branch_id is not None:
        session.add(
            EmployeeBranchAssignment(
                employee_id=e.id,
                branch_id=branch_id,
                is_primary=True,
                assigned_from=datetime.now(UTC).date(),
                position=e.position,
                is_active=True,
            )
        )
        await session.flush()
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=e.company_id,
        branch_id=branch_id,
        resource_type="employees",
        resource_id=str(e.id),
        after_state=employee_to_audit_state(e),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return EmployeeOut.model_validate(e, from_attributes=True)


@router.patch(
    "/{emp_id}",
    response_model=EmployeeOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar empleado",
    dependencies=[Depends(require_permission("employees:update"))],
)
async def update_employee(
    emp_id: uuid.UUID,
    body: UpdateEmployeeRequest,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    dept_repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> EmployeeOut:
    before = await GetEmployeeUseCase(repo).execute(emp_id)
    branch_id = await _require_employee_scope(
        session,
        current,
        request,
        employee_id=emp_id,
        company_id=before.company_id,
    )
    active_assignments = (
        (
            await session.execute(
                select(EmployeeBranchAssignment).where(
                    EmployeeBranchAssignment.employee_id == emp_id,
                    EmployeeBranchAssignment.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if body.status in {"inactivo", "baja"} and active_assignments:
        raise HTTPException(
            409, "Finalice primero las asignaciones activas del empleado a sucursales."
        )
    if body.department_id and body.department_id != before.department_id:
        for assignment in active_assignments:
            enabled = await session.scalar(
                select(DepartmentBranchAssignment.id).where(
                    DepartmentBranchAssignment.department_id == body.department_id,
                    DepartmentBranchAssignment.branch_id == assignment.branch_id,
                    DepartmentBranchAssignment.is_active.is_(True),
                )
            )
            if enabled is None:
                raise HTTPException(
                    409,
                    "El nuevo departamento debe estar habilitado en todas las sucursales activas del empleado.",
                )
    uc = UpdateEmployeeUseCase(repo, dept_repo)
    e = await uc.execute(
        UpdateEmployeeInput(
            emp_id=emp_id,
            first_name=body.first_name,
            last_name=body.last_name,
            document_id=body.document_id,
            birth_date=body.birth_date,
            phone=body.phone,
            address=body.address,
            department_id=body.department_id,
            position=body.position,
            hire_date=body.hire_date,
            termination_date=body.termination_date,
            status=EmployeeStatus(body.status) if body.status else None,
            photo_url=body.photo_url,
        )
    )
    await attach_media_by_url(
        session, secure_url=e.photo_url, company_id=e.company_id,
        owner_type="employee", owner_id=e.id, replace_single=True,
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=e.company_id,
        branch_id=branch_id,
        resource_type="employees",
        resource_id=str(emp_id),
        before_state=employee_to_audit_state(before),
        after_state=employee_to_audit_state(e),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return EmployeeOut.model_validate(e, from_attributes=True)


@router.delete(
    "/{emp_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Eliminar empleado (soft delete)",
    dependencies=[Depends(require_permission("employees:delete"))],
)
async def delete_employee(
    emp_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    before = await GetEmployeeUseCase(repo).execute(emp_id)
    branch_id = await _require_employee_scope(
        session,
        current,
        request,
        employee_id=emp_id,
        company_id=before.company_id,
    )
    active_assignment = await session.scalar(
        select(EmployeeBranchAssignment.id).where(
            EmployeeBranchAssignment.employee_id == emp_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
    )
    if active_assignment:
        raise HTTPException(
            409, "Finalice primero las asignaciones activas del empleado a sucursales."
        )
    uc = DeleteEmployeeUseCase(repo)
    await uc.execute(emp_id)
    await audit.record(
        action="LOGICAL_DELETE",
        user_id=current.id,
        company_id=before.company_id,
        branch_id=branch_id,
        resource_type="employees",
        resource_id=str(emp_id),
        before_state=employee_to_audit_state(before),
        after_state={**employee_to_audit_state(before), "deleted": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return MessageOut(message="Empleado eliminado.", code="employee_deleted")

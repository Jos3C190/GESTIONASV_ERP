"""Employees router — CRUD + link/unlink user account."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.common import MessageOut
from app.api.v1.schemas.employees import (
    CreateEmployeeRequest,
    EmployeeOut,
    EmployeeStatsOut,
    LinkUserRequest,
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
    LinkUserInput,
    LinkUserUseCase,
    ListEmployeesInput,
    ListEmployeesUseCase,
    UnlinkUserUseCase,
    UpdateEmployeeInput,
    UpdateEmployeeUseCase,
)
from app.domain.entities.employee import EmployeeStatus
from app.domain.ports.department_repository import DepartmentRepository
from app.domain.ports.employee_repository import EmployeeRepository

router = APIRouter(prefix="/employees", tags=["employees"])


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
    repo: EmployeeRepository = Depends(_get_emp_repo),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    department_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> Page[EmployeeOut]:
    uc = ListEmployeesUseCase(repo)
    result = await uc.execute(
        ListEmployeesInput(
            page=page, size=size, search=search, department_id=department_id, status=status_filter
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
    repo: EmployeeRepository = Depends(_get_emp_repo),
) -> EmployeeStatsOut:
    """Returns aggregate counts via a single SQL GROUP BY — scales to any number of employees."""
    stats = await repo.get_stats()
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
    repo: EmployeeRepository = Depends(_get_emp_repo),
) -> EmployeeOut:
    uc = GetEmployeeUseCase(repo)
    e = await uc.execute(emp_id)
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
    repo: EmployeeRepository = Depends(_get_emp_repo),
    dept_repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> EmployeeOut:
    uc = CreateEmployeeUseCase(repo, dept_repo)
    e = await uc.execute(
        CreateEmployeeInput(
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
    await audit.record(
        action="CREATE",
        user_id=current.id,
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
    repo: EmployeeRepository = Depends(_get_emp_repo),
    dept_repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> EmployeeOut:
    before = await GetEmployeeUseCase(repo).execute(emp_id)
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
    await audit.record(
        action="UPDATE",
        user_id=current.id,
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
    repo: EmployeeRepository = Depends(_get_emp_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    before = await GetEmployeeUseCase(repo).execute(emp_id)
    uc = DeleteEmployeeUseCase(repo)
    await uc.execute(emp_id)
    await audit.record(
        action="LOGICAL_DELETE",
        user_id=current.id,
        resource_type="employees",
        resource_id=str(emp_id),
        before_state=employee_to_audit_state(before),
        after_state={**employee_to_audit_state(before), "deleted": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return MessageOut(message="Empleado eliminado.", code="employee_deleted")


@router.post(
    "/{emp_id}/link-user",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Vincular empleado a cuenta de usuario",
    dependencies=[Depends(require_permission("employees:update"))],
)
async def link_user(
    emp_id: uuid.UUID,
    body: LinkUserRequest,
    request: Request,
    current: CurrentUser,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    before = await GetEmployeeUseCase(repo).execute(emp_id)
    uc = LinkUserUseCase(repo)
    await uc.execute(LinkUserInput(emp_id=emp_id, user_id=body.user_id))
    after = await GetEmployeeUseCase(repo).execute(emp_id)
    await audit.record(
        action="LINK_USER",
        user_id=current.id,
        resource_type="employees",
        resource_id=str(emp_id),
        before_state=employee_to_audit_state(before),
        after_state=employee_to_audit_state(after),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return MessageOut(message="Usuario vinculado.", code="user_linked")


@router.post(
    "/{emp_id}/unlink-user",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Desvincular cuenta de usuario del empleado",
    dependencies=[Depends(require_permission("employees:update"))],
)
async def unlink_user(
    emp_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    repo: EmployeeRepository = Depends(_get_emp_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    before = await GetEmployeeUseCase(repo).execute(emp_id)
    uc = UnlinkUserUseCase(repo)
    await uc.execute(emp_id)
    after = await GetEmployeeUseCase(repo).execute(emp_id)
    await audit.record(
        action="UNLINK_USER",
        user_id=current.id,
        resource_type="employees",
        resource_id=str(emp_id),
        before_state=employee_to_audit_state(before),
        after_state=employee_to_audit_state(after),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return MessageOut(message="Usuario desvinculado.", code="user_unlinked")

"""Departments router — CRUD + hierarchy."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import require_company_access, require_company_wide_scope
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.common import MessageOut, Page, PageMeta
from app.api.v1.schemas.employees import (
    CreateDepartmentRequest,
    DepartmentOut,
    UpdateDepartmentRequest,
)
from app.api.v1.schemas.lifecycle import SoftDeleteRequest
from app.application.audit.audit_service import (
    AuditService,
    department_to_audit_state,
)
from app.application.employees.department_crud import (
    CreateDepartmentInput,
    CreateDepartmentUseCase,
    GetDepartmentUseCase,
    ListDepartmentsUseCase,
    UpdateDepartmentInput,
    UpdateDepartmentUseCase,
)
from app.application.lifecycle import LifecycleService
from app.domain.ports.department_repository import DepartmentRepository
from app.infrastructure.repositories import SqlAlchemyLifecycleRepository

router = APIRouter(prefix="/departments", tags=["departments"])


def _get_dept_repo(session: SessionDep) -> DepartmentRepository:
    from app.infrastructure.repositories import SqlAlchemyDepartmentRepository

    return SqlAlchemyDepartmentRepository(session)


@router.get(
    "",
    response_model=Page[DepartmentOut],
    status_code=status.HTTP_200_OK,
    summary="Listar departamentos",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def list_departments(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: DepartmentRepository = Depends(_get_dept_repo),
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    level: str | None = Query(None, pattern="^(root|child)$"),
) -> Page[DepartmentOut]:
    await require_company_access(session, current, company_id)
    uc = ListDepartmentsUseCase(repo)
    depts, total = await uc.execute_page(
        company_id,
        page=page,
        size=size,
        search=search,
        level=level,
    )
    return Page(
        items=[DepartmentOut.model_validate(d, from_attributes=True) for d in depts],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.get(
    "/catalogue",
    response_model=list[DepartmentOut],
    status_code=status.HTTP_200_OK,
    summary="Catálogo completo de departamentos",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def department_catalogue(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: DepartmentRepository = Depends(_get_dept_repo),
) -> list[DepartmentOut]:
    await require_company_access(session, current, company_id)
    depts = await ListDepartmentsUseCase(repo).execute(company_id)
    return [DepartmentOut.model_validate(dept, from_attributes=True) for dept in depts]


@router.get(
    "/{dept_id}",
    response_model=DepartmentOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener departamento por id",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def get_department(
    dept_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: DepartmentRepository = Depends(_get_dept_repo),
) -> DepartmentOut:
    uc = GetDepartmentUseCase(repo)
    d = await uc.execute(dept_id)
    await require_company_access(session, current, d.company_id)
    return DepartmentOut.model_validate(d, from_attributes=True)


@router.post(
    "",
    response_model=DepartmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear departamento",
    dependencies=[Depends(require_permission("departments:manage"))],
)
async def create_department(
    body: CreateDepartmentRequest,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> DepartmentOut:
    await require_company_access(session, current, body.company_id, require_active=True)
    await require_company_wide_scope(session, current, body.company_id)
    uc = CreateDepartmentUseCase(repo)
    d = await uc.execute(
        CreateDepartmentInput(
            company_id=body.company_id,
            name=body.name,
            description=body.description,
            parent_department_id=body.parent_department_id,
        )
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=d.company_id,
        resource_type="departments",
        resource_id=str(d.id),
        after_state=department_to_audit_state(d),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return DepartmentOut.model_validate(d, from_attributes=True)


@router.patch(
    "/{dept_id}",
    response_model=DepartmentOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar departamento",
    dependencies=[Depends(require_permission("departments:manage"))],
)
async def update_department(
    dept_id: uuid.UUID,
    body: UpdateDepartmentRequest,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> DepartmentOut:
    before = await GetDepartmentUseCase(repo).execute(dept_id)
    await require_company_access(session, current, before.company_id, require_active=True)
    await require_company_wide_scope(session, current, before.company_id)
    uc = UpdateDepartmentUseCase(repo)
    d = await uc.execute(
        UpdateDepartmentInput(
            dept_id=dept_id,
            name=body.name,
            description=body.description,
            parent_department_id=body.parent_department_id,
        )
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=d.company_id,
        resource_type="departments",
        resource_id=str(dept_id),
        before_state=department_to_audit_state(before),
        after_state=department_to_audit_state(d),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return DepartmentOut.model_validate(d, from_attributes=True)


@router.delete(
    "/{dept_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Eliminar departamento lógicamente (ruta de compatibilidad)",
    deprecated=True,
    dependencies=[Depends(require_permission("departments:delete"))],
)
async def delete_department(
    dept_id: uuid.UUID,
    body: SoftDeleteRequest,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    repo: DepartmentRepository = Depends(_get_dept_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    before = await GetDepartmentUseCase(repo).execute(dept_id)
    await require_company_access(session, current, before.company_id, require_active=True)
    await require_company_wide_scope(session, current, before.company_id)
    deleted = await LifecycleService(SqlAlchemyLifecycleRepository(session)).delete(
        "departments",
        str(dept_id),
        company_id=before.company_id,
        actor_id=current.id,
        reason=body.reason,
    )
    if deleted.operation_applied:
        await audit.record(
            action="LOGICAL_DELETE",
            user_id=current.id,
            company_id=before.company_id,
            resource_type="departments",
            resource_id=str(dept_id),
            before_state={
                **department_to_audit_state(before),
                "label": deleted.label,
                "deleted_at": None,
                "deleted_by": None,
                "deletion_reason": None,
            },
            after_state={
                "label": deleted.label,
                "deleted_at": deleted.deleted_at.isoformat() if deleted.deleted_at else None,
                "deleted_by": str(deleted.deleted_by) if deleted.deleted_by else None,
                "deletion_reason": deleted.deletion_reason,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            required=True,
        )
    return MessageOut(
        message=(
            "Departamento eliminado."
            if deleted.operation_applied
            else "El departamento ya estaba en la papelera."
        ),
        code="dept_deleted" if deleted.operation_applied else "dept_already_deleted",
    )

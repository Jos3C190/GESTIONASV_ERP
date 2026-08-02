"""Enterprise workforce placement and department presence per branch."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update

from app.api.v1.company_access import (
    get_branch_context,
    require_company_access,
    resolve_branch_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.application.audit.audit_service import AuditService
from app.infrastructure.models.employee import (
    Department,
    DepartmentBranchAssignment,
    Employee,
    EmployeeBranchAssignment,
)
from app.infrastructure.models.organization import Branch

router = APIRouter(tags=["workforce"])


class EmployeeBranchAssignmentIn(BaseModel):
    employee_id: uuid.UUID
    branch_id: uuid.UUID
    is_primary: bool = False
    assigned_from: date = Field(default_factory=date.today)
    assigned_until: date | None = None
    position: str | None = Field(None, max_length=120)
    shift: str | None = Field(None, max_length=32)

    @model_validator(mode="after")
    def dates(self):
        if self.assigned_until and self.assigned_until < self.assigned_from:
            raise ValueError("La fecha final no puede ser anterior a la inicial.")
        return self


class DepartmentBranchAssignmentIn(BaseModel):
    department_id: uuid.UUID
    branch_id: uuid.UUID
    manager_employee_id: uuid.UUID | None = None
    opened_at: date = Field(default_factory=date.today)


def dump(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, date | datetime):
            value = value.isoformat()
        elif isinstance(value, uuid.UUID):
            value = str(value)
        result[column.name] = value
    return result


async def validate_employee_branch(
    session: SessionDep, current: CurrentUser, employee_id: uuid.UUID, branch_id: uuid.UUID
):
    employee, branch = (
        await session.get(Employee, employee_id),
        await session.get(Branch, branch_id),
    )
    if employee is None or employee.deleted_at is not None:
        raise HTTPException(404, "Empleado no encontrado.")
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    await require_company_access(session, current, employee.company_id, require_active=True)
    if employee.company_id != branch.company_id:
        raise HTTPException(409, "El empleado y la sucursal pertenecen a empresas diferentes.")
    await resolve_branch_scope(session, current, employee.company_id, branch_id)
    if employee.status in {"inactivo", "baja"}:
        raise HTTPException(409, "No se puede asignar un empleado inactivo o dado de baja.")
    if not branch.is_active:
        raise HTTPException(409, "La sucursal está inactiva.")
    if employee.department_id:
        enabled = await session.scalar(
            select(DepartmentBranchAssignment.id).where(
                DepartmentBranchAssignment.department_id == employee.department_id,
                DepartmentBranchAssignment.branch_id == branch_id,
                DepartmentBranchAssignment.is_active.is_(True),
            )
        )
        if enabled is None:
            raise HTTPException(
                409, "El departamento del empleado no está habilitado en esta sucursal."
            )
    return employee, branch


@router.get(
    "/employees/{employee_id}/branch-assignments",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def list_employee_assignments(
    employee_id: uuid.UUID, session: SessionDep, current: CurrentUser
):
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "Empleado no encontrado.")
    context = await get_branch_context(session, current, employee.company_id)
    stmt = select(EmployeeBranchAssignment).where(
        EmployeeBranchAssignment.employee_id == employee_id
    )
    if not context.access_all_branches:
        stmt = stmt.where(
            EmployeeBranchAssignment.branch_id.in_(
                {branch.id for branch in context.branches}
            )
        )
    rows = (
        (
            await session.execute(
                stmt.order_by(EmployeeBranchAssignment.assigned_from.desc())
            )
        )
        .scalars()
        .all()
    )
    return [dump(x) for x in rows]


@router.post(
    "/employee-branch-assignments",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("employees:update"))],
)
async def assign_employee(
    body: EmployeeBranchAssignmentIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
):
    await validate_employee_branch(session, current, body.employee_id, body.branch_id)
    existing = await session.scalar(
        select(EmployeeBranchAssignment.id).where(
            EmployeeBranchAssignment.employee_id == body.employee_id,
            EmployeeBranchAssignment.branch_id == body.branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
    )
    if existing:
        raise HTTPException(409, "El empleado ya tiene una asignación activa en esta sucursal.")
    if body.is_primary:
        await session.execute(
            update(EmployeeBranchAssignment)
            .where(
                EmployeeBranchAssignment.employee_id == body.employee_id,
                EmployeeBranchAssignment.is_active.is_(True),
                EmployeeBranchAssignment.is_primary.is_(True),
            )
            .values(is_primary=False)
        )
    obj = EmployeeBranchAssignment(**body.model_dump(), is_active=True)
    session.add(obj)
    await session.flush()
    await audit.record(
        action="ASSIGN_BRANCH",
        user_id=current.id,
        company_id=employee.company_id,
        branch_id=obj.branch_id,
        resource_type="employee_branch_assignments",
        resource_id=str(obj.id),
        after_state=dump(obj),
        ip_address=request.client.host if request.client else None,
    )
    return dump(obj)


@router.post(
    "/employee-branch-assignments/{assignment_id}/end",
    dependencies=[Depends(require_permission("employees:update"))],
)
async def end_employee_assignment(
    assignment_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
):
    obj = await session.get(EmployeeBranchAssignment, assignment_id)
    if obj is None:
        raise HTTPException(404, "Asignación no encontrada.")
    employee = await session.get(Employee, obj.employee_id)
    await require_company_access(session, current, employee.company_id, require_active=True)
    await resolve_branch_scope(session, current, employee.company_id, obj.branch_id)
    before = dump(obj)
    obj.is_active = False
    obj.assigned_until = datetime.now(UTC).date()
    obj.is_primary = False
    await session.flush()
    await audit.record(
        action="END_BRANCH_ASSIGNMENT",
        user_id=current.id,
        company_id=employee.company_id,
        branch_id=obj.branch_id,
        resource_type="employee_branch_assignments",
        resource_id=str(obj.id),
        before_state=before,
        after_state=dump(obj),
        ip_address=request.client.host if request.client else None,
    )
    return dump(obj)


@router.get(
    "/departments/{department_id}/branch-assignments",
    dependencies=[Depends(require_permission("employees:read"))],
)
async def list_department_assignments(
    department_id: uuid.UUID, session: SessionDep, current: CurrentUser
):
    dept = await session.get(Department, department_id)
    if dept is None:
        raise HTTPException(404, "Departamento no encontrado.")
    context = await get_branch_context(session, current, dept.company_id)
    stmt = select(DepartmentBranchAssignment).where(
        DepartmentBranchAssignment.department_id == department_id
    )
    if not context.access_all_branches:
        stmt = stmt.where(
            DepartmentBranchAssignment.branch_id.in_(
                {branch.id for branch in context.branches}
            )
        )
    rows = (
        (
            await session.execute(stmt)
        )
        .scalars()
        .all()
    )
    return [dump(x) for x in rows]


@router.post(
    "/department-branch-assignments",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("departments:manage"))],
)
async def enable_department(
    body: DepartmentBranchAssignmentIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
):
    dept, branch = (
        await session.get(Department, body.department_id),
        await session.get(Branch, body.branch_id),
    )
    if dept is None or branch is None:
        raise HTTPException(404, "Departamento o sucursal no encontrado.")
    await require_company_access(session, current, dept.company_id, require_active=True)
    if dept.company_id != branch.company_id:
        raise HTTPException(409, "El departamento y la sucursal pertenecen a empresas diferentes.")
    await resolve_branch_scope(session, current, dept.company_id, branch.id)
    if body.manager_employee_id:
        manager = await session.get(Employee, body.manager_employee_id)
        if manager is None or manager.company_id != dept.company_id or manager.status != "activo":
            raise HTTPException(
                409, "El responsable debe ser un empleado activo de la misma empresa."
            )
        manager_assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == body.manager_employee_id,
                EmployeeBranchAssignment.branch_id == body.branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        )
        if manager_assignment is None:
            raise HTTPException(409, "El responsable debe estar asignado a la sucursal.")
    existing = await session.scalar(
        select(DepartmentBranchAssignment).where(
            DepartmentBranchAssignment.department_id == body.department_id,
            DepartmentBranchAssignment.branch_id == body.branch_id,
        )
    )
    if existing:
        existing.is_active = True
        existing.closed_at = None
        existing.manager_employee_id = body.manager_employee_id
        obj = existing
    else:
        obj = DepartmentBranchAssignment(**body.model_dump(), is_active=True)
        session.add(obj)
    await session.flush()
    await audit.record(
        action="ENABLE_BRANCH",
        user_id=current.id,
        company_id=dept.company_id,
        branch_id=obj.branch_id,
        resource_type="department_branch_assignments",
        resource_id=str(obj.id),
        after_state=dump(obj),
        ip_address=request.client.host if request.client else None,
    )
    return dump(obj)


@router.post(
    "/department-branch-assignments/{assignment_id}/end",
    dependencies=[Depends(require_permission("departments:manage"))],
)
async def disable_department(
    assignment_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
):
    obj = await session.get(DepartmentBranchAssignment, assignment_id)
    if obj is None:
        raise HTTPException(404, "Asignación no encontrada.")
    dept = await session.get(Department, obj.department_id)
    await require_company_access(session, current, dept.company_id, require_active=True)
    await resolve_branch_scope(session, current, dept.company_id, obj.branch_id)
    active_employee = await session.scalar(
        select(EmployeeBranchAssignment.id)
        .join(Employee, Employee.id == EmployeeBranchAssignment.employee_id)
        .where(
            Employee.department_id == obj.department_id,
            EmployeeBranchAssignment.branch_id == obj.branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
    )
    if active_employee:
        raise HTTPException(409, "Reasigne primero a los empleados activos de este departamento.")
    before = dump(obj)
    obj.is_active = False
    obj.closed_at = datetime.now(UTC).date()
    await session.flush()
    await audit.record(
        action="DISABLE_BRANCH",
        user_id=current.id,
        company_id=dept.company_id,
        branch_id=obj.branch_id,
        resource_type="department_branch_assignments",
        resource_id=str(obj.id),
        before_state=before,
        after_state=dump(obj),
        ip_address=request.client.host if request.client else None,
    )
    return dump(obj)

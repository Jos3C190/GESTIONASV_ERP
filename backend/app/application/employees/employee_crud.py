"""Use cases: Employee CRUD + link/unlink user account."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.entities.employee import Employee, EmployeeStatus
from app.domain.ports.department_repository import DepartmentRepository
from app.domain.ports.employee_repository import EmployeeRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CreateEmployeeInput:
    company_id: uuid.UUID
    employee_code: str
    first_name: str
    last_name: str
    user_id: uuid.UUID | None = None
    document_id: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    address: str | None = None
    department_id: uuid.UUID | None = None
    position: str | None = None
    hire_date: date | None = None
    status: EmployeeStatus = EmployeeStatus.ACTIVO
    photo_url: str | None = None


class CreateEmployeeUseCase:
    def __init__(
        self, employees: EmployeeRepository, departments: DepartmentRepository
    ) -> None:
        self._employees = employees
        self._departments = departments

    async def execute(self, inp: CreateEmployeeInput) -> Employee:
        if await self._employees.get_by_code(inp.company_id, inp.employee_code):
            raise ConflictError(
                "El código de empleado ya existe.", code="employee_code_taken"
            )
        if inp.department_id is not None:
            dept = await self._departments.get_by_id(inp.department_id)
            if dept is None:
                raise ConflictError(
                    "Departamento no encontrado.", code="dept_not_found"
                )
            if dept.company_id != inp.company_id:
                raise ConflictError("El departamento pertenece a otra empresa.", code="dept_company_mismatch")
        emp = Employee(
            id=uuid.uuid4(),
            company_id=inp.company_id,
            user_id=inp.user_id,
            employee_code=inp.employee_code,
            first_name=inp.first_name,
            last_name=inp.last_name,
            document_id=inp.document_id,
            birth_date=inp.birth_date,
            phone=inp.phone,
            address=inp.address,
            department_id=inp.department_id,
            position=inp.position,
            hire_date=inp.hire_date,
            status=inp.status,
            photo_url=inp.photo_url,
        )
        created = await self._employees.add(emp)
        log.info("employee_created", emp_id=str(created.id), code=created.employee_code)
        return created


@dataclass(frozen=True, slots=True)
class UpdateEmployeeInput:
    emp_id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    document_id: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    address: str | None = None
    department_id: uuid.UUID | None = None
    position: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    status: EmployeeStatus | None = None
    photo_url: str | None = None


class UpdateEmployeeUseCase:
    def __init__(
        self, employees: EmployeeRepository, departments: DepartmentRepository
    ) -> None:
        self._employees = employees
        self._departments = departments

    async def execute(self, inp: UpdateEmployeeInput) -> Employee:
        emp = await self._employees.get_by_id(inp.emp_id)
        if emp is None:
            raise NotFoundError("Empleado no encontrado.", code="employee_not_found")

        new_dept = inp.department_id if inp.department_id is not None else emp.department_id
        if new_dept is not None and new_dept != emp.department_id:
            dept = await self._departments.get_by_id(new_dept)
            if dept is None:
                raise ConflictError("Departamento no encontrado.", code="dept_not_found")

        updated = Employee(
            id=emp.id,
            company_id=emp.company_id,
            user_id=emp.user_id,
            employee_code=emp.employee_code,
            first_name=inp.first_name or emp.first_name,
            last_name=inp.last_name or emp.last_name,
            document_id=inp.document_id if inp.document_id is not None else emp.document_id,
            birth_date=inp.birth_date if inp.birth_date is not None else emp.birth_date,
            phone=inp.phone if inp.phone is not None else emp.phone,
            address=inp.address if inp.address is not None else emp.address,
            department_id=new_dept,
            position=inp.position if inp.position is not None else emp.position,
            hire_date=inp.hire_date if inp.hire_date is not None else emp.hire_date,
            termination_date=inp.termination_date if inp.termination_date is not None else emp.termination_date,
            status=inp.status if inp.status is not None else emp.status,
            photo_url=inp.photo_url if inp.photo_url is not None else emp.photo_url,
            created_at=emp.created_at,
            updated_at=emp.updated_at,
            deleted_at=emp.deleted_at,
        )
        result = await self._employees.update(updated)
        log.info("employee_updated", emp_id=str(emp.id))
        return result


@dataclass(frozen=True, slots=True)
class ListEmployeesInput:
    page: int = 1
    size: int = 20
    search: str | None = None
    department_id: uuid.UUID | None = None
    status: str | None = None
    company_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ListEmployeesResult:
    items: Sequence[Employee]
    total: int
    page: int
    size: int
    pages: int


class ListEmployeesUseCase:
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def execute(self, inp: ListEmployeesInput) -> ListEmployeesResult:
        page = max(inp.page, 1)
        size = max(min(inp.size, 100), 1)
        offset = (page - 1) * size
        items, total = await self._employees.list_active(
            offset=offset,
            limit=size,
            search=inp.search,
            department_id=inp.department_id,
            status=inp.status,
            company_id=inp.company_id,
            branch_id=inp.branch_id,
        )
        pages = (total + size - 1) // size if total else 1
        return ListEmployeesResult(items=items, total=total, page=page, size=size, pages=pages)


class GetEmployeeUseCase:
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def execute(self, emp_id: uuid.UUID) -> Employee:
        emp = await self._employees.get_by_id(emp_id)
        if emp is None:
            raise NotFoundError("Empleado no encontrado.", code="employee_not_found")
        return emp


class DeleteEmployeeUseCase:
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def execute(self, emp_id: uuid.UUID) -> bool:
        emp = await self._employees.get_by_id(emp_id)
        if emp is None:
            raise NotFoundError("Empleado no encontrado.", code="employee_not_found")
        if emp.user_id is not None:
            raise ConflictError(
                "No se puede eliminar un empleado que posee una cuenta de usuario.",
                code="employee_has_user",
            )
        ok = await self._employees.soft_delete(emp_id)
        if ok:
            log.info("employee_deleted", emp_id=str(emp_id))
        return ok


@dataclass(frozen=True, slots=True)
class LinkUserInput:
    emp_id: uuid.UUID
    user_id: uuid.UUID


class LinkUserUseCase:
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def execute(self, inp: LinkUserInput) -> bool:
        emp = await self._employees.get_by_id(inp.emp_id)
        if emp is None:
            raise NotFoundError("Empleado no encontrado.", code="employee_not_found")
        if emp.user_id is not None:
            raise ConflictError(
                "El empleado ya tiene una cuenta vinculada.", code="already_linked"
            )
        ok = await self._employees.link_to_user(inp.emp_id, inp.user_id)
        log.info("employee_linked", emp_id=str(inp.emp_id), user_id=str(inp.user_id))
        return ok

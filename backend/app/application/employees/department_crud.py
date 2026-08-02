"""Use cases: Department CRUD with hierarchy + cycle detection.

Business rules:
- Cannot create a cycle (A->B->A) in the parent chain.
- Cannot delete a department that still has employees (reassign first).
- Cannot set a department as its own parent.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.entities.employee import Department
from app.domain.ports.department_repository import DepartmentRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CreateDepartmentInput:
    company_id: uuid.UUID
    name: str
    description: str | None = None
    parent_department_id: uuid.UUID | None = None


class CreateDepartmentUseCase:
    def __init__(self, departments: DepartmentRepository) -> None:
        self._departments = departments

    async def execute(self, inp: CreateDepartmentInput) -> Department:
        if await self._departments.get_by_name(inp.company_id, inp.name):
            raise ConflictError("El nombre de departamento ya existe.", code="dept_name_taken")

        # Validate parent exists and no cycle (creating a new node can't form
        # a cycle unless parent == self, which is impossible since we don't
        # have an id yet, but we verify the parent exists).
        if inp.parent_department_id is not None:
            parent = await self._departments.get_by_id(inp.parent_department_id)
            if parent is None:
                raise BusinessRuleError(
                    "Departamento padre no encontrado.", code="parent_not_found"
                )
            if parent.company_id != inp.company_id:
                raise BusinessRuleError("El departamento padre pertenece a otra empresa.", code="parent_company_mismatch")

        dept = Department(
            id=uuid.uuid4(),
            company_id=inp.company_id,
            name=inp.name,
            description=inp.description,
            parent_department_id=inp.parent_department_id,
        )
        created = await self._departments.add(dept)
        log.info("department_created", dept_id=str(created.id), name=created.name)
        return created


@dataclass(frozen=True, slots=True)
class UpdateDepartmentInput:
    dept_id: uuid.UUID
    name: str | None = None
    description: str | None = None
    parent_department_id: uuid.UUID | None = None


class UpdateDepartmentUseCase:
    def __init__(self, departments: DepartmentRepository) -> None:
        self._departments = departments

    async def execute(self, inp: UpdateDepartmentInput) -> Department:
        dept = await self._departments.get_by_id(inp.dept_id)
        if dept is None:
            raise NotFoundError("Departamento no encontrado.", code="dept_not_found")

        new_name = inp.name if inp.name is not None else dept.name
        new_parent = inp.parent_department_id if inp.parent_department_id is not None else dept.parent_department_id

        # Name uniqueness
        if new_name != dept.name:
            existing = await self._departments.get_by_name(dept.company_id, new_name)
            if existing and existing.id != dept.id:
                raise ConflictError("El nombre de departamento ya existe.", code="dept_name_taken")

        # Cycle detection: cannot be own parent, and cannot create a cycle.
        if new_parent is not None:
            if new_parent == dept.id:
                raise BusinessRuleError(
                    "Un departamento no puede ser su propio padre.",
                    code="dept_self_parent",
                )
            chain = await self._departments.get_ancestor_chain(new_parent)
            chain_ids = {d.id for d in chain}
            if dept.id in chain_ids:
                raise BusinessRuleError(
                    "No se puede crear un ciclo en la jerarquía de departamentos.",
                    code="dept_cycle_detected",
                )
            parent = await self._departments.get_by_id(new_parent)
            if parent is None:
                raise BusinessRuleError(
                    "Departamento padre no encontrado.", code="parent_not_found"
                )

        updated = Department(
            id=dept.id,
            company_id=dept.company_id,
            name=new_name,
            description=inp.description if inp.description is not None else dept.description,
            parent_department_id=new_parent,
            created_at=dept.created_at,
            updated_at=dept.updated_at,
        )
        result = await self._departments.update(updated)
        log.info("department_updated", dept_id=str(dept.id))
        return result


class DeleteDepartmentUseCase:
    def __init__(self, departments: DepartmentRepository) -> None:
        self._departments = departments

    async def execute(self, dept_id: uuid.UUID) -> bool:
        dept = await self._departments.get_by_id(dept_id)
        if dept is None:
            raise NotFoundError("Departamento no encontrado.", code="dept_not_found")
        if await self._departments.has_employees(dept_id):
            raise BusinessRuleError(
                "No puede eliminar un departamento con empleados asignados. Reasigne primero.",
                code="dept_has_employees",
            )
        ok = await self._departments.delete(dept_id)
        if ok:
            log.info("department_deleted", dept_id=str(dept_id))
        return ok


class ListDepartmentsUseCase:
    def __init__(self, departments: DepartmentRepository) -> None:
        self._departments = departments

    async def execute(self, company_id: uuid.UUID) -> Sequence[Department]:
        return await self._departments.list_all(company_id)

    async def execute_page(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        search: str | None = None,
        level: str | None = None,
    ) -> tuple[Sequence[Department], int]:
        return await self._departments.list_page(
            company_id,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            level=level,
        )


class GetDepartmentUseCase:
    def __init__(self, departments: DepartmentRepository) -> None:
        self._departments = departments

    async def execute(self, dept_id: uuid.UUID) -> Department:
        dept = await self._departments.get_by_id(dept_id)
        if dept is None:
            raise NotFoundError("Departamento no encontrado.", code="dept_not_found")
        return dept

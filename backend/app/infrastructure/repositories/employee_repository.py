"""SQLAlchemy EmployeeRepository."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.employee import Employee as DomainEmp
from app.domain.entities.employee import EmployeeStatus
from app.domain.ports.employee_repository import EmployeeStats
from app.infrastructure.models.employee import Employee as ORMEmployee
from app.infrastructure.models.employee import EmployeeBranchAssignment


def _to_domain(orm: ORMEmployee) -> DomainEmp:
    return DomainEmp(
        id=orm.id,
        company_id=orm.company_id,
        user_id=orm.user_id,
        employee_code=orm.employee_code,
        first_name=orm.first_name,
        last_name=orm.last_name,
        document_id=orm.document_id,
        birth_date=orm.birth_date,
        phone=orm.phone,
        address=orm.address,
        department_id=orm.department_id,
        position=orm.position,
        hire_date=orm.hire_date,
        termination_date=orm.termination_date,
        status=EmployeeStatus(orm.status),
        photo_url=orm.photo_url,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        deleted_at=orm.deleted_at,
    )


class SqlAlchemyEmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, emp_id: uuid.UUID) -> DomainEmp | None:
        stmt = select(ORMEmployee).where(
            ORMEmployee.id == emp_id, ORMEmployee.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_code(self, company_id: uuid.UUID, code: str) -> DomainEmp | None:
        stmt = select(ORMEmployee).where(
            ORMEmployee.company_id == company_id, ORMEmployee.employee_code == code, ORMEmployee.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_user_id(self, user_id: uuid.UUID) -> DomainEmp | None:
        stmt = select(ORMEmployee).where(
            ORMEmployee.user_id == user_id, ORMEmployee.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def list_active(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        department_id: uuid.UUID | None = None,
        status: str | None = None,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[Sequence[DomainEmp], int]:
        base = select(ORMEmployee).where(ORMEmployee.deleted_at.is_(None))
        count_base = select(func.count(ORMEmployee.id)).where(ORMEmployee.deleted_at.is_(None))
        if company_id is not None:
            base = base.where(ORMEmployee.company_id == company_id)
            count_base = count_base.where(ORMEmployee.company_id == company_id)
        if branch_id is not None:
            base = base.join(EmployeeBranchAssignment).where(
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
            count_base = count_base.join(EmployeeBranchAssignment).where(
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        if search:
            like = f"%{search}%"
            cond = or_(
                ORMEmployee.first_name.ilike(like),
                ORMEmployee.last_name.ilike(like),
                ORMEmployee.employee_code.ilike(like),
            )
            base = base.where(cond)
            count_base = count_base.where(cond)
        if department_id is not None:
            base = base.where(ORMEmployee.department_id == department_id)
            count_base = count_base.where(ORMEmployee.department_id == department_id)
        if status is not None:
            base = base.where(ORMEmployee.status == status)
            count_base = count_base.where(ORMEmployee.status == status)
        base = base.order_by(ORMEmployee.created_at.desc()).offset(offset).limit(limit)
        items = (await self._session.execute(base)).scalars().all()
        total = int((await self._session.execute(count_base)).scalar_one())
        return [_to_domain(o) for o in items], total

    async def add(self, emp: DomainEmp) -> DomainEmp:
        orm = ORMEmployee(
            company_id=emp.company_id,
            user_id=emp.user_id,
            employee_code=emp.employee_code,
            first_name=emp.first_name,
            last_name=emp.last_name,
            document_id=emp.document_id,
            birth_date=emp.birth_date,
            phone=emp.phone,
            address=emp.address,
            department_id=emp.department_id,
            position=emp.position,
            hire_date=emp.hire_date,
            termination_date=emp.termination_date,
            status=emp.status.value,
            photo_url=emp.photo_url,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_domain(orm)

    async def update(self, emp: DomainEmp) -> DomainEmp:
        stmt = (
            update(ORMEmployee)
            .where(ORMEmployee.id == emp.id, ORMEmployee.deleted_at.is_(None))
            .values(
                user_id=emp.user_id,
                first_name=emp.first_name,
                last_name=emp.last_name,
                document_id=emp.document_id,
                birth_date=emp.birth_date,
                phone=emp.phone,
                address=emp.address,
                department_id=emp.department_id,
                position=emp.position,
                hire_date=emp.hire_date,
                termination_date=emp.termination_date,
                status=emp.status.value,
                photo_url=emp.photo_url,
            )
            .returning(ORMEmployee)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise LookupError(f"Employee {emp.id} not found")
        return _to_domain(orm)

    async def soft_delete(self, emp_id: uuid.UUID) -> bool:
        stmt = (
            update(ORMEmployee)
            .where(ORMEmployee.id == emp_id, ORMEmployee.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def link_to_user(self, emp_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = (
            update(ORMEmployee)
            .where(ORMEmployee.id == emp_id, ORMEmployee.deleted_at.is_(None))
            .values(user_id=user_id)
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def get_stats(
        self,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> EmployeeStats:
        """Single GROUP BY query — O(1) cost regardless of employee count."""
        base = select(
            ORMEmployee.status,
            func.count(ORMEmployee.id).label("cnt"),
        ).where(ORMEmployee.deleted_at.is_(None)).group_by(ORMEmployee.status)

        linked_stmt = select(func.count(ORMEmployee.id)).where(
            ORMEmployee.deleted_at.is_(None),
            ORMEmployee.user_id.is_not(None),
        )
        if company_id is not None:
            base = base.where(ORMEmployee.company_id == company_id)
            linked_stmt = linked_stmt.where(ORMEmployee.company_id == company_id)
        if branch_id is not None:
            base = base.join(EmployeeBranchAssignment).where(
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
            linked_stmt = linked_stmt.join(EmployeeBranchAssignment).where(
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )

        rows = (await self._session.execute(base)).all()
        linked = int((await self._session.execute(linked_stmt)).scalar_one())

        counts: dict[str, int] = {row.status: row.cnt for row in rows}
        total = sum(counts.values())
        return EmployeeStats(
            total=total,
            active=counts.get("activo", 0),
            inactive=counts.get("inactivo", 0),
            on_leave=counts.get("vacaciones", 0),
            terminated=counts.get("baja", 0),
            linked_to_user=linked,
        )

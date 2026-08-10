"""SQLAlchemy DepartmentRepository — with hierarchy + cycle detection."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.employee import Department as DomainDept
from app.infrastructure.models.employee import Department as ORMDept
from app.infrastructure.models.employee import Employee as ORMEmployee


def _to_domain(orm: ORMDept) -> DomainDept:
    return DomainDept(
        id=orm.id,
        company_id=orm.company_id,
        name=orm.name,
        description=orm.description,
        parent_department_id=orm.parent_department_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SqlAlchemyDepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, dept_id: uuid.UUID) -> DomainDept | None:
        stmt = select(ORMDept).where(ORMDept.id == dept_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_name(self, company_id: uuid.UUID, name: str) -> DomainDept | None:
        stmt = select(ORMDept).where(ORMDept.company_id == company_id, ORMDept.name == name)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def list_all(self, company_id: uuid.UUID) -> Sequence[DomainDept]:
        stmt = select(ORMDept).where(ORMDept.company_id == company_id).order_by(ORMDept.name)
        result = await self._session.execute(stmt)
        return [_to_domain(d) for d in result.scalars().all()]

    async def list_page(
        self,
        company_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        level: str | None = None,
    ) -> tuple[Sequence[DomainDept], int]:
        conditions = [ORMDept.company_id == company_id]
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append((ORMDept.name.ilike(pattern)) | (ORMDept.description.ilike(pattern)))
        if level == "root":
            conditions.append(ORMDept.parent_department_id.is_(None))
        elif level == "child":
            conditions.append(ORMDept.parent_department_id.is_not(None))

        total_stmt = select(func.count(ORMDept.id)).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(ORMDept)
            .where(*conditions)
            .order_by(ORMDept.name, ORMDept.id)
            .offset(offset)
            .limit(limit)
        )
        records = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(record) for record in records], total

    async def list_children(self, parent_id: uuid.UUID) -> Sequence[DomainDept]:
        stmt = (
            select(ORMDept).where(ORMDept.parent_department_id == parent_id).order_by(ORMDept.name)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(d) for d in result.scalars().all()]

    async def get_ancestor_chain(self, dept_id: uuid.UUID) -> Sequence[DomainDept]:
        """Walk up the parent chain until root. Used for cycle detection."""
        chain: list[DomainDept] = []
        current_id = dept_id
        seen: set[uuid.UUID] = set()
        while current_id is not None and current_id not in seen:
            seen.add(current_id)
            dept = await self.get_by_id(current_id)
            if dept is None:
                break
            chain.append(dept)
            current_id = dept.parent_department_id
        return chain

    async def add(self, dept: DomainDept) -> DomainDept:
        orm = ORMDept(
            company_id=dept.company_id,
            name=dept.name,
            description=dept.description,
            parent_department_id=dept.parent_department_id,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_domain(orm)

    async def update(self, dept: DomainDept) -> DomainDept:
        stmt = (
            update(ORMDept)
            .where(ORMDept.id == dept.id)
            .values(
                name=dept.name,
                description=dept.description,
                parent_department_id=dept.parent_department_id,
            )
            .returning(ORMDept)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise LookupError(f"Department {dept.id} not found")
        return _to_domain(orm)

    async def delete(self, dept_id: uuid.UUID) -> bool:
        stmt = (
            update(ORMDept)
            .where(ORMDept.id == dept_id, ORMDept.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC), deletion_reason="Eliminado desde Departamentos")
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def has_employees(self, dept_id: uuid.UUID) -> bool:
        stmt = select(func.count(ORMEmployee.id)).where(
            ORMEmployee.department_id == dept_id,
            ORMEmployee.deleted_at.is_(None),
        )
        count = int((await self._session.execute(stmt)).scalar_one())
        return count > 0

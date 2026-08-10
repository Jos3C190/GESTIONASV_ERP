"""SQLAlchemy PermissionRepository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.rbac import Permission as DomainPermission
from app.infrastructure.models.rbac import Permission as ORMPermission
from app.infrastructure.models.rbac import RolePermission


def _to_domain(orm: ORMPermission) -> DomainPermission:
    return DomainPermission(
        id=orm.id,
        code=orm.code,
        description=orm.description,
        module=orm.module,
        created_at=orm.created_at,
    )


class SqlAlchemyPermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, permission_id: uuid.UUID) -> DomainPermission | None:
        stmt = select(ORMPermission).where(ORMPermission.id == permission_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_code(self, code: str) -> DomainPermission | None:
        stmt = select(ORMPermission).where(ORMPermission.code == code)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def list_all(self) -> Sequence[DomainPermission]:
        stmt = select(ORMPermission).order_by(ORMPermission.module, ORMPermission.code)
        result = await self._session.execute(stmt)
        return [_to_domain(p) for p in result.scalars().all()]

    async def list_by_module(self, module: str) -> Sequence[DomainPermission]:
        stmt = (
            select(ORMPermission).where(ORMPermission.module == module).order_by(ORMPermission.code)
        )
        result = await self._session.execute(stmt)
        return [_to_domain(p) for p in result.scalars().all()]

    async def add(self, permission: DomainPermission) -> DomainPermission:
        orm = ORMPermission(
            code=permission.code,
            description=permission.description,
            module=permission.module,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_domain(orm)

    async def update(self, permission: DomainPermission) -> DomainPermission:
        result = await self._session.execute(
            update(ORMPermission)
            .where(ORMPermission.id == permission.id)
            .values(
                code=permission.code,
                description=permission.description,
                module=permission.module,
            )
            .returning(ORMPermission)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            raise LookupError(f"Permission {permission.id} not found")
        return _to_domain(orm)

    async def is_assigned(self, permission_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(RolePermission.permission_id)
            .where(RolePermission.permission_id == permission_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def delete(self, permission_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(ORMPermission)
            .where(ORMPermission.id == permission_id, ORMPermission.deleted_at.is_(None))
            .values(
                deleted_at=datetime.now(UTC),
                deletion_reason="Eliminado desde Roles y permisos",
            )
        )
        return (result.rowcount or 0) > 0

    async def bulk_add(self, permissions: Sequence[DomainPermission]) -> int:
        if not permissions:
            return 0
        orms = [
            ORMPermission(code=p.code, description=p.description, module=p.module)
            for p in permissions
        ]
        self._session.add_all(orms)
        await self._session.flush()
        return len(orms)

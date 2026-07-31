"""SQLAlchemy RoleRepository — concrete implementation of the domain port.

Handles role CRUD, role<->permission assignment, user<->role assignment, and
the effective-permissions query (the union of all permissions across a user's
roles).
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.rbac import Permission as DomainPermission
from app.domain.entities.rbac import Role as DomainRole
from app.domain.entities.rbac import UserRoleAssignment
from app.infrastructure.models.rbac import (
    Permission as ORMPermission,
)
from app.infrastructure.models.rbac import (
    Role as ORMRole,
)
from app.infrastructure.models.rbac import RolePermission, UserRole


def _perm_to_domain(orm: ORMPermission) -> DomainPermission:
    return DomainPermission(
        id=orm.id,
        code=orm.code,
        description=orm.description,
        module=orm.module,
        created_at=orm.created_at,
    )


def _role_to_domain(orm: ORMRole, perms: tuple[DomainPermission, ...] = ()) -> DomainRole:
    return DomainRole(
        id=orm.id,
        name=orm.name,
        description=orm.description,
        is_system=orm.is_system,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        permissions=perms,
    )


class SqlAlchemyRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, role_id: uuid.UUID, *, load_permissions: bool = False
    ) -> DomainRole | None:
        stmt = select(ORMRole).where(ORMRole.id == role_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        perms = await self.get_permissions_for_role(role_id) if load_permissions else ()
        return _role_to_domain(orm, tuple(perms))

    async def get_by_name(
        self, name: str, *, load_permissions: bool = False
    ) -> DomainRole | None:
        stmt = select(ORMRole).where(ORMRole.name == name)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        perms = await self.get_permissions_for_role(orm.id) if load_permissions else ()
        return _role_to_domain(orm, tuple(perms))

    async def list_all(self, *, load_permissions: bool = False) -> Sequence[DomainRole]:
        stmt = select(ORMRole).order_by(ORMRole.name)
        result = await self._session.execute(stmt)
        roles = result.scalars().all()
        if not load_permissions:
            return [_role_to_domain(r) for r in roles]
        # Batch-load permissions for all roles in 2 queries (not N+1).
        role_ids = [r.id for r in roles]
        perm_map = await self._batch_load_permissions(role_ids)
        return [
            _role_to_domain(r, tuple(perm_map.get(r.id, [])))
            for r in roles
        ]

    async def _batch_load_permissions(
        self, role_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[DomainPermission]]:
        """Load permissions for multiple roles in a single JOIN query."""
        if not role_ids:
            return {}
        stmt = (
            select(RolePermission.role_id, ORMPermission)
            .join(ORMPermission, ORMPermission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_(role_ids))
            .order_by(ORMPermission.code)
        )
        result = await self._session.execute(stmt)
        out: dict[uuid.UUID, list[DomainPermission]] = {}
        for role_id, perm in result.all():
            out.setdefault(role_id, []).append(_perm_to_domain(perm))
        return out

    async def add(self, role: DomainRole) -> DomainRole:
        orm = ORMRole(name=role.name, description=role.description, is_system=role.is_system)
        self._session.add(orm)
        await self._session.flush()
        return _role_to_domain(orm)

    async def update(self, role: DomainRole) -> DomainRole:
        stmt = (
            update(ORMRole)
            .where(ORMRole.id == role.id)
            .values(name=role.name, description=role.description)
            .returning(ORMRole)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise LookupError(f"Role {role.id} not found")
        return _role_to_domain(orm)

    async def delete(self, role_id: uuid.UUID) -> bool:
        stmt = delete(ORMRole).where(ORMRole.id == role_id, ORMRole.is_system.is_(False))
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def is_assigned(self, role_id: uuid.UUID) -> bool:
        stmt = select(UserRole.user_id).where(UserRole.role_id == role_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def set_permissions(
        self, role_id: uuid.UUID, permission_ids: set[uuid.UUID]
    ) -> None:
        await self._session.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )
        if permission_ids:
            await self._session.execute(
                insert(RolePermission),
                [{"role_id": role_id, "permission_id": pid} for pid in permission_ids],
            )

    async def get_permissions_for_role(self, role_id: uuid.UUID) -> Sequence[DomainPermission]:
        stmt = (
            select(ORMPermission)
            .join(RolePermission, RolePermission.permission_id == ORMPermission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(ORMPermission.code)
        )
        result = await self._session.execute(stmt)
        return [_perm_to_domain(p) for p in result.scalars().all()]

    async def get_effective_permissions_for_user(
        self, user_id: uuid.UUID
    ) -> Sequence[DomainPermission]:
        # UNION of permissions across all the user's roles.
        stmt = (
            select(ORMPermission)
            .join(RolePermission, RolePermission.permission_id == ORMPermission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
            .distinct()
            .order_by(ORMPermission.code)
        )
        result = await self._session.execute(stmt)
        return [_perm_to_domain(p) for p in result.scalars().all()]

    async def get_roles_for_user(self, user_id: uuid.UUID) -> Sequence[DomainRole]:
        stmt = (
            select(ORMRole)
            .join(UserRole, UserRole.role_id == ORMRole.id)
            .where(UserRole.user_id == user_id)
            .order_by(ORMRole.name)
        )
        result = await self._session.execute(stmt)
        return [_role_to_domain(r) for r in result.scalars().all()]

    async def assign_role_to_user(
        self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID
    ) -> bool:
        existing = await self._session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False  # idempotent
        self._session.add(
            UserRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by)
        )
        await self._session.flush()
        return True

    async def revoke_role_from_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        stmt = delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role_id
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def list_user_role_assignments(self, user_id: uuid.UUID) -> Sequence[UserRoleAssignment]:
        stmt = (
            select(UserRole, ORMRole)
            .join(ORMRole, ORMRole.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
            .order_by(ORMRole.name)
        )
        result = await self._session.execute(stmt)
        return [
            UserRoleAssignment(
                user_id=ur.user_id,
                role_id=ur.role_id,
                assigned_by=ur.assigned_by,
                assigned_at=ur.assigned_at,
            )
            for ur, _role in result.all()
        ]

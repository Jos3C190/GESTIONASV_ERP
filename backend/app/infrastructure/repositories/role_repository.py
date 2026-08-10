"""SQLAlchemy RoleRepository — concrete implementation of the domain port.

Handles role CRUD, role<->permission assignment, user<->role assignment, and
the effective-permissions query (the union of all permissions across a user's
roles).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, exists, func, insert, or_, select, update
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
        company_id=orm.company_id,
        description=orm.description,
        is_system=orm.is_system,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        permissions=perms,
    )


class SqlAlchemyRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _scope(company_id: uuid.UUID):
        return or_(ORMRole.company_id == company_id, ORMRole.company_id.is_(None))

    async def get_by_id(
        self, company_id: uuid.UUID, role_id: uuid.UUID, *, load_permissions: bool = False
    ) -> DomainRole | None:
        stmt = select(ORMRole).where(ORMRole.id == role_id, self._scope(company_id))
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        perms = await self.get_permissions_for_role(company_id, role_id) if load_permissions else ()
        return _role_to_domain(orm, tuple(perms))

    async def get_by_name(
        self, company_id: uuid.UUID, name: str, *, load_permissions: bool = False
    ) -> DomainRole | None:
        stmt = select(ORMRole).where(ORMRole.name == name, self._scope(company_id))
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        perms = await self.get_permissions_for_role(company_id, orm.id) if load_permissions else ()
        return _role_to_domain(orm, tuple(perms))

    async def list_all(
        self, company_id: uuid.UUID, *, load_permissions: bool = False
    ) -> Sequence[DomainRole]:
        stmt = select(ORMRole).where(self._scope(company_id)).order_by(ORMRole.name)
        result = await self._session.execute(stmt)
        roles = result.scalars().all()
        if not load_permissions:
            return [_role_to_domain(r) for r in roles]
        # Batch-load permissions for all roles in 2 queries (not N+1).
        role_ids = [r.id for r in roles]
        perm_map = await self._batch_load_permissions(role_ids)
        return [_role_to_domain(r, tuple(perm_map.get(r.id, []))) for r in roles]

    async def list_page(
        self,
        company_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        is_system: bool | None = None,
        module: str | None = None,
        load_permissions: bool = False,
    ) -> tuple[Sequence[DomainRole], int]:
        conditions = [self._scope(company_id)]
        if search:
            pattern = f"%{search.strip()}%"
            permission_match = exists(
                select(1)
                .select_from(RolePermission)
                .join(ORMPermission, ORMPermission.id == RolePermission.permission_id)
                .where(
                    RolePermission.role_id == ORMRole.id,
                    ORMPermission.code.ilike(pattern),
                )
            )
            conditions.append(
                or_(
                    ORMRole.name.ilike(pattern),
                    ORMRole.description.ilike(pattern),
                    permission_match,
                )
            )
        if is_system is not None:
            conditions.append(ORMRole.is_system.is_(is_system))
        if module:
            conditions.append(
                exists(
                    select(1)
                    .select_from(RolePermission)
                    .join(ORMPermission, ORMPermission.id == RolePermission.permission_id)
                    .where(
                        RolePermission.role_id == ORMRole.id,
                        ORMPermission.module == module,
                    )
                )
            )

        total_stmt = select(func.count(ORMRole.id)).where(*conditions)
        total = int((await self._session.execute(total_stmt)).scalar_one())
        stmt = (
            select(ORMRole)
            .where(*conditions)
            .order_by(ORMRole.name, ORMRole.id)
            .offset(offset)
            .limit(limit)
        )
        roles = list((await self._session.execute(stmt)).scalars().all())
        if not load_permissions:
            return [_role_to_domain(role) for role in roles], total
        permission_map = await self._batch_load_permissions([role.id for role in roles])
        return (
            [_role_to_domain(role, tuple(permission_map.get(role.id, []))) for role in roles],
            total,
        )

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
        orm = ORMRole(
            company_id=role.company_id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
        )
        self._session.add(orm)
        await self._session.flush()
        return _role_to_domain(orm)

    async def update(self, role: DomainRole) -> DomainRole:
        stmt = (
            update(ORMRole)
            .where(ORMRole.id == role.id, ORMRole.company_id == role.company_id)
            .values(name=role.name, description=role.description)
            .returning(ORMRole)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise LookupError(f"Role {role.id} not found")
        return _role_to_domain(orm)

    async def delete(self, company_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        stmt = (
            update(ORMRole)
            .where(
                ORMRole.id == role_id,
                ORMRole.company_id == company_id,
                ORMRole.is_system.is_(False),
                ORMRole.deleted_at.is_(None),
            )
            .values(
                deleted_at=datetime.now(UTC),
                deletion_reason="Eliminado desde Roles y permisos",
            )
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def is_assigned(self, company_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        stmt = (
            select(UserRole.user_id)
            .where(UserRole.company_id == company_id, UserRole.role_id == role_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def set_permissions(
        self, company_id: uuid.UUID, role_id: uuid.UUID, permission_ids: set[uuid.UUID]
    ) -> None:
        if await self.get_by_id(company_id, role_id) is None:
            raise LookupError("role_not_found")
        await self._session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        if permission_ids:
            await self._session.execute(
                insert(RolePermission),
                [{"role_id": role_id, "permission_id": pid} for pid in permission_ids],
            )

    async def get_permissions_for_role(
        self, company_id: uuid.UUID, role_id: uuid.UUID
    ) -> Sequence[DomainPermission]:
        if await self.get_by_id(company_id, role_id) is None:
            return ()
        stmt = (
            select(ORMPermission)
            .join(RolePermission, RolePermission.permission_id == ORMPermission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(ORMPermission.code)
        )
        result = await self._session.execute(stmt)
        return [_perm_to_domain(p) for p in result.scalars().all()]

    async def get_effective_permissions_for_user(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> Sequence[DomainPermission]:
        # UNION of permissions across all the user's roles.
        stmt = (
            select(ORMPermission)
            .join(RolePermission, RolePermission.permission_id == ORMPermission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id, UserRole.company_id == company_id)
            .distinct()
            .order_by(ORMPermission.code)
        )
        result = await self._session.execute(stmt)
        return [_perm_to_domain(p) for p in result.scalars().all()]

    async def get_roles_for_user(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> Sequence[DomainRole]:
        stmt = (
            select(ORMRole)
            .join(UserRole, UserRole.role_id == ORMRole.id)
            .where(UserRole.user_id == user_id, UserRole.company_id == company_id)
            .order_by(ORMRole.name)
        )
        result = await self._session.execute(stmt)
        return [_role_to_domain(r) for r in result.scalars().all()]

    async def get_roles_for_users(
        self, user_ids: Sequence[uuid.UUID], company_id: uuid.UUID
    ) -> dict[uuid.UUID, Sequence[DomainRole]]:
        """Load roles for a page of users with one query instead of an N+1 loop."""
        if not user_ids:
            return {}
        stmt = (
            select(UserRole.user_id, ORMRole)
            .join(ORMRole, ORMRole.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids), UserRole.company_id == company_id)
            .order_by(UserRole.user_id, ORMRole.name)
        )
        result = await self._session.execute(stmt)
        roles_by_user: dict[uuid.UUID, list[DomainRole]] = {user_id: [] for user_id in user_ids}
        for user_id, role in result.all():
            roles_by_user[user_id].append(_role_to_domain(role))
        return roles_by_user

    async def assign_role_to_user(
        self, user_id: uuid.UUID, company_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID
    ) -> bool:
        existing = await self._session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.company_id == company_id,
                UserRole.role_id == role_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False  # idempotent
        self._session.add(
            UserRole(
                user_id=user_id, company_id=company_id, role_id=role_id, assigned_by=assigned_by
            )
        )
        await self._session.flush()
        return True

    async def revoke_role_from_user(
        self, user_id: uuid.UUID, company_id: uuid.UUID, role_id: uuid.UUID
    ) -> bool:
        stmt = delete(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.company_id == company_id,
            UserRole.role_id == role_id,
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def list_user_role_assignments(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> Sequence[UserRoleAssignment]:
        stmt = (
            select(UserRole, ORMRole)
            .join(ORMRole, ORMRole.id == UserRole.role_id)
            .where(UserRole.user_id == user_id, UserRole.company_id == company_id)
            .order_by(ORMRole.name)
        )
        result = await self._session.execute(stmt)
        return [
            UserRoleAssignment(
                user_id=ur.user_id,
                role_id=ur.role_id,
                company_id=ur.company_id,
                assigned_by=ur.assigned_by,
                assigned_at=ur.assigned_at,
            )
            for ur, _role in result.all()
        ]

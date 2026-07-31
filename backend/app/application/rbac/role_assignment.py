"""Use cases: assign/revoke roles to/from users."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.logging import get_logger
from app.domain.ports.role_repository import RoleRepository
from app.domain.ports.user_repository import UserRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AssignRoleInput:
    user_id: uuid.UUID
    role_id: uuid.UUID
    assigned_by: uuid.UUID


class AssignRoleUseCase:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def execute(self, inp: AssignRoleInput) -> bool:
        user = await self._users.get_by_id(inp.user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")
        role = await self._roles.get_by_id(inp.role_id)
        if role is None:
            raise NotFoundError("Rol no encontrado.", code="role_not_found")

        # Cannot assign SUPER_ADMIN role to self (redundant with is_superuser
        # flag, but defends against accidental elevation).
        if inp.user_id == inp.assigned_by and role.name == "SUPER_ADMIN":
            raise BusinessRuleError(
                "No puede asignarse el rol SUPER_ADMIN a sí mismo.",
                code="self_superadmin_assign_forbidden",
            )

        created = await self._roles.assign_role_to_user(
            inp.user_id, inp.role_id, inp.assigned_by
        )
        log.info(
            "role_assigned",
            user_id=str(inp.user_id),
            role_id=str(inp.role_id),
            assigned_by=str(inp.assigned_by),
            created=created,
        )
        return created


@dataclass(frozen=True, slots=True)
class RevokeRoleInput:
    user_id: uuid.UUID
    role_id: uuid.UUID
    actor_id: uuid.UUID


class RevokeRoleUseCase:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def execute(self, inp: RevokeRoleInput) -> bool:
        user = await self._users.get_by_id(inp.user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")
        role = await self._roles.get_by_id(inp.role_id)
        if role is None:
            raise NotFoundError("Rol no encontrado.", code="role_not_found")

        # Cannot revoke SUPER_ADMIN from self.
        if role.name == "SUPER_ADMIN" and inp.user_id == inp.actor_id:
            raise BusinessRuleError(
                "No puede revocar su propio rol de superadministrador.",
                code="self_superadmin_revoke_forbidden",
            )

        assigned_roles = await self._roles.get_roles_for_user(inp.user_id)
        if any(assigned.id == inp.role_id for assigned in assigned_roles) and len(
            assigned_roles
        ) <= 1:
            raise BusinessRuleError(
                "El usuario debe conservar al menos un rol.",
                code="user_requires_role",
            )

        ok = await self._roles.revoke_role_from_user(inp.user_id, inp.role_id)
        log.info(
            "role_revoked",
            user_id=str(inp.user_id),
            role_id=str(inp.role_id),
            actor_id=str(inp.actor_id),
            revoked=ok,
        )
        return ok


class GetUserRolesUseCase:
    def __init__(self, roles: RoleRepository) -> None:
        self._roles = roles

    async def execute(self, user_id: uuid.UUID):
        return await self._roles.get_roles_for_user(user_id)

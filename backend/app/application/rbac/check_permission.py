"""Use case: CheckEffectivePermission — the heart of the RBAC engine.

Computes whether a user has a given permission code. Superusers always pass
(shortcut) without touching the DB. Non-superusers get their effective
permissions (union across roles) and we check membership.

This is called by the `require_permission` FastAPI dependency on every
protected request — keep it cheap. A Redis cache hook is the documented
Phase 6+ optimisation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.ports.role_repository import RoleRepository
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class PermissionCheckResult:
    allowed: bool
    reason: str


class CheckPermissionUseCase:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def execute(
        self, user_id: uuid.UUID, company_id: uuid.UUID, required_permission: str
    ) -> PermissionCheckResult:
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return PermissionCheckResult(allowed=False, reason="user_invalid")
        if user.is_superuser:
            return PermissionCheckResult(allowed=True, reason="superuser")
        perms = await self._roles.get_effective_permissions_for_user(user_id, company_id)
        codes = {p.code for p in perms}
        if required_permission in codes:
            return PermissionCheckResult(allowed=True, reason="granted")
        return PermissionCheckResult(allowed=False, reason="not_granted")


class GetEffectivePermissionsUseCase:
    """Returns the list of effective permission codes for a user (for /me/permissions)."""

    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def execute(self, user_id: uuid.UUID, company_id: uuid.UUID) -> tuple[str, ...]:
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return ()
        if user.is_superuser:
            # Return a sentinel indicating all permissions; the API layer can
            # materialise the full catalogue for the frontend.
            return ("*",)
        perms = await self._roles.get_effective_permissions_for_user(user_id, company_id)
        return tuple(p.code for p in perms)

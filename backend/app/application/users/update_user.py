"""Use case: UpdateUser — change editable attributes (active flag, superuser flag).

Enforces critical business rules (OWASP A01 / A04):
- A user cannot deactivate or demote themselves (prevent self-lockout).
- Cannot demote/remove the last active superadmin (prevent admin lockout of
  the whole system).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.logging import get_logger
from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class UpdateUserInput:
    target_id: uuid.UUID
    actor_id: uuid.UUID
    is_active: bool | None = None
    is_superuser: bool | None = None


class UpdateUserUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, inp: UpdateUserInput) -> User:
        user = await self._users.get_by_id(inp.target_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")

        new_active = inp.is_active if inp.is_active is not None else user.is_active
        new_superuser = inp.is_superuser if inp.is_superuser is not None else user.is_superuser

        # Rule 1: cannot self-deactivate or self-demote.
        if inp.target_id == inp.actor_id:
            if inp.is_active is False:
                raise AuthorizationError(
                    "No puede desactivar su propia cuenta.", code="self_deactivate_forbidden"
                )
            if inp.is_superuser is False:
                raise AuthorizationError(
                    "No puede revocar su propio rol de superadministrador.",
                    code="self_demote_forbidden",
                )

        # Rule 2: cannot remove the last active superadmin.
        if user.is_superuser and user.is_active and (new_superuser is False or new_active is False):
            count = await self._users.count_active_superadmins()
            if count <= 1:
                raise BusinessRuleError(
                    "No puede dejar el sistema sin superadministradores activos.",
                    code="last_superadmin_protected",
                )

        if new_active == user.is_active and new_superuser == user.is_superuser:
            # No changes — return as-is.
            return user

        updated = User(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            is_active=new_active,
            is_superuser=new_superuser,
            mfa_enabled=user.mfa_enabled,
            last_login_at=user.last_login_at,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            password_changed_at=user.password_changed_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        )
        result = await self._users.update(updated)
        log.info(
            "user_updated",
            user_id=str(user.id),
            actor_id=str(inp.actor_id),
            active=new_active,
            superuser=new_superuser,
        )
        return result

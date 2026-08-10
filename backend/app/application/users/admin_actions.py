"""Use cases: ForcePasswordReset, UnlockAccount, DeactivateUser.

These are admin actions on a target user. All enforce the actor-vs-target and
last-superadmin business rules where applicable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _ActorTargetInput:
    target_id: uuid.UUID
    actor_id: uuid.UUID


# ---------------- ForcePasswordReset ----------------


@dataclass(frozen=True, slots=True)
class ForcePasswordResetInput(_ActorTargetInput):
    new_password: str


class ForcePasswordResetUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, inp: ForcePasswordResetInput) -> User:
        user = await self._users.get_by_id(inp.target_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")

        # Cannot reset own password via this admin endpoint (use the profile flow).
        if inp.target_id == inp.actor_id:
            raise AuthorizationError(
                "Use el flujo de perfil para cambiar su propia contraseña.",
                code="self_reset_forbidden",
            )

        updated = user.with_password_hash(hash_password(inp.new_password))
        result = await self._users.update(updated)
        log.info("password_forced_reset", user_id=str(user.id), actor_id=str(inp.actor_id))
        return result


# ---------------- UnlockAccount ----------------


class UnlockAccountUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, target_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(target_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")

        if user.locked_until is None and user.failed_login_attempts == 0:
            return user  # already unlocked — idempotent

        updated = User(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            mfa_enabled=user.mfa_enabled,
            last_login_at=user.last_login_at,
            failed_login_attempts=0,
            locked_until=None,
            password_changed_at=user.password_changed_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        )
        result = await self._users.update(updated)
        log.info("account_unlocked", user_id=str(user.id))
        return result


# ---------------- DeactivateUser (operational state, not deletion) ----------------


class DeactivateUserUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, target_id: uuid.UUID, actor_id: uuid.UUID) -> bool:
        if target_id == actor_id:
            raise AuthorizationError(
                "No puede desactivar su propia cuenta.", code="self_deactivate_forbidden"
            )

        user = await self._users.get_by_id(target_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")

        if user.is_superuser and user.is_active:
            count = await self._users.count_active_superadmins()
            if count <= 1:
                raise BusinessRuleError(
                    "No puede dejar el sistema sin superadministradores activos.",
                    code="last_superadmin_protected",
                )

        if not user.is_active:
            return False
        ok = await self._users.deactivate(target_id)
        if ok:
            log.info("user_deactivated", user_id=str(target_id), actor_id=str(actor_id))
        return ok

"""Use case for an authenticated user changing their own password."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.password_policy import PasswordPolicy
from app.core.exceptions import AuthenticationError, BusinessRuleError
from app.core.security import hash_password, verify_password
from app.domain.entities.user import User
from app.domain.ports.refresh_token_repository import RefreshTokenRepository
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class ChangePasswordInput:
    user_id: uuid.UUID
    current_password: str
    new_password: str


class ChangePasswordUseCase:
    def __init__(
        self,
        users: UserRepository,
        sessions: RefreshTokenRepository,
        policy: PasswordPolicy,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._policy = policy

    async def execute(self, inp: ChangePasswordInput) -> User:
        user = await self._users.get_by_id(inp.user_id)
        if user is None or not verify_password(
            inp.current_password, user.password_hash
        ):
            raise AuthenticationError(
                "La contraseña actual es incorrecta.",
                code="current_password_invalid",
            )
        validation = self._policy.validate(inp.new_password)
        if not validation.valid:
            raise BusinessRuleError(
                "; ".join(validation.reasons),
                code="weak_password",
            )
        if verify_password(inp.new_password, user.password_hash):
            raise BusinessRuleError(
                "La nueva contraseña debe ser diferente.",
                code="password_unchanged",
            )
        updated = await self._users.update(
            user.with_password_hash(hash_password(inp.new_password))
        )
        await self._sessions.revoke_all_for_user(user.id)
        return updated

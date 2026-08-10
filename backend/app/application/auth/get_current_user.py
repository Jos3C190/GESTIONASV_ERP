"""Use case: GetCurrentUser — return the authenticated user's profile."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.exceptions import AuthenticationError
from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class GetCurrentUserResult:
    user: User


class GetCurrentUserUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, user_id: uuid.UUID) -> GetCurrentUserResult:
        user = await self._users.get_by_id(user_id)
        if user is None or user.is_deleted:
            raise AuthenticationError("Usuario no encontrado.", code="user_not_found")
        if not user.is_active:
            raise AuthenticationError("La cuenta está inactiva.", code="account_inactive")
        return GetCurrentUserResult(user=user)

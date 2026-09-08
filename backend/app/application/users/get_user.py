"""Use case: GetUser — fetch a single user by id."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.exceptions import NotFoundError
from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class GetUserResult:
    user: User


class GetUserUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, user_id: uuid.UUID) -> GetUserResult:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.", code="user_not_found")
        return GetUserResult(user=user)

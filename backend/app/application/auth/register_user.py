"""Use case: RegisterUser — create a new user (used by seed and admin CRUD).

Validates the password policy, hashes with Argon2, and ensures username/email
uniqueness. Phase 1b will add permission checks at the API layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.password_policy import PasswordPolicy
from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RegisterUserInput:
    username: str
    email: str
    password: str
    is_active: bool = True
    is_superuser: bool = False


class RegisterUserUseCase:
    def __init__(self, users: UserRepository, policy: PasswordPolicy | None = None) -> None:
        self._users = users
        self._policy = policy or PasswordPolicy()

    async def execute(self, inp: RegisterUserInput) -> User:
        # Password policy
        result = self._policy.validate(inp.password)
        if not result.valid:
            raise BusinessRuleError("; ".join(result.reasons), code="weak_password")

        # Uniqueness checks (case-insensitive for email)
        if await self._users.get_by_username(inp.username):
            raise ConflictError("El nombre de usuario ya existe.", code="username_taken")
        if await self._users.get_by_email(inp.email):
            raise ConflictError("El correo ya está registrado.", code="email_taken")

        hashed = hash_password(inp.password)
        new_user = User(
            id=uuid.uuid4(),  # repo will use server-generated id; placeholder here
            username=inp.username,
            email=inp.email,
            password_hash=hashed,
            is_active=inp.is_active,
            is_superuser=inp.is_superuser,
        )
        created = await self._users.add(new_user)
        log.info("user_registered", user_id=str(created.id), username=created.username)
        return created

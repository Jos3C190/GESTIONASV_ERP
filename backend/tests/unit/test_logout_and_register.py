"""Unit tests for LogoutUseCase and RegisterUserUseCase."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.auth.authenticate_user import AuthenticateUserUseCase, LoginInput
from app.application.auth.logout import LogoutInput, LogoutUseCase
from app.application.auth.register_user import RegisterUserInput, RegisterUserUseCase
from app.application.password_policy import PasswordPolicy
from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.security import hash_password, verify_password
from app.domain.entities.user import User

from tests.unit.fakes import (
    FakeTokenService,
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)


async def _login(users, sessions, tokens) -> str:
    uc = AuthenticateUserUseCase(users, sessions, tokens)
    user = User(
        id=uuid.uuid4(),
        username="carol",
        email="carol@example.com",
        password_hash=hash_password("Strong!Passw0rd2026"),
        is_active=True,
        password_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await users.add(user)
    result = await uc.execute(LoginInput(login="carol", password="Strong!Passw0rd2026"))
    return result.refresh_token


async def test_logout_revokes_token() -> None:
    users = InMemoryUserRepository()
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService()
    raw = await _login(users, sessions, tokens)

    uc = LogoutUseCase(sessions, tokens)
    await uc.execute(LogoutInput(raw_refresh_token=raw))

    stored = await sessions.get_by_hash(tokens.hash_refresh_token(raw))
    assert stored.revoked_at is not None


async def test_logout_unknown_token_is_idempotent() -> None:
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService()
    uc = LogoutUseCase(sessions, tokens)
    # Should not raise
    await uc.execute(LogoutInput(raw_refresh_token="never-existed"))


# ---------------- RegisterUser ----------------


async def test_register_user_success() -> None:
    users = InMemoryUserRepository()
    uc = RegisterUserUseCase(users, PasswordPolicy())
    created = await uc.execute(
        RegisterUserInput(
            username="newuser",
            email="new@example.com",
            password="Strong!Passw0rd2026",
        )
    )
    assert created.username == "newuser"
    assert verify_password("Strong!Passw0rd2026", created.password_hash)
    assert created.is_active
    assert not created.is_superuser


async def test_register_rejects_weak_password() -> None:
    users = InMemoryUserRepository()
    uc = RegisterUserUseCase(users, PasswordPolicy())
    with pytest.raises(BusinessRuleError) as exc:
        await uc.execute(
            RegisterUserInput(username="weak", email="weak@example.com", password="short")
        )
    assert exc.value.code == "weak_password"


async def test_register_rejects_known_leaked_password() -> None:
    users = InMemoryUserRepository()
    uc = RegisterUserUseCase(users, PasswordPolicy())
    with pytest.raises(BusinessRuleError):
        await uc.execute(
            RegisterUserInput(
                username="leaked",
                email="leaked@example.com",
                password="password123!!!",  # in deny-list + too weak anyway
            )
        )


async def test_register_rejects_duplicate_username() -> None:
    users = InMemoryUserRepository()
    uc = RegisterUserUseCase(users, PasswordPolicy())
    await uc.execute(
        RegisterUserInput(username="dup", email="first@example.com", password="Strong!Passw0rd2026")
    )
    with pytest.raises(ConflictError) as exc:
        await uc.execute(
            RegisterUserInput(
                username="dup", email="second@example.com", password="Strong!Passw0rd2026"
            )
        )
    assert exc.value.code == "username_taken"


async def test_register_rejects_duplicate_email() -> None:
    users = InMemoryUserRepository()
    uc = RegisterUserUseCase(users, PasswordPolicy())
    await uc.execute(
        RegisterUserInput(username="first", email="dup@example.com", password="Strong!Passw0rd2026")
    )
    with pytest.raises(ConflictError) as exc:
        await uc.execute(
            RegisterUserInput(
                username="second", email="dup@example.com", password="Strong!Passw0rd2026"
            )
        )
    assert exc.value.code == "email_taken"

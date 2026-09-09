"""Unit tests for AuthenticateUserUseCase (no DB, in-memory fakes)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.auth.authenticate_user import (
    MAX_FAILED_ATTEMPTS,
    AuthenticateUserUseCase,
    LoginInput,
)
from app.core.exceptions import AuthenticationError
from app.core.security import hash_password
from app.domain.entities.user import User

from tests.unit.fakes import (
    FakeTokenService,
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)


def _make_user(*, active=True, locked_until=None, failed=0, password="Strong!Passw0rd2026") -> User:
    return User(
        id=uuid.uuid4(),
        username="alice",
        email="alice@example.com",
        password_hash=hash_password(password),
        is_active=active,
        is_superuser=False,
        failed_login_attempts=failed,
        locked_until=locked_until,
        password_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def auth_setup() -> tuple:
    users = InMemoryUserRepository()
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService()
    uc = AuthenticateUserUseCase(users, sessions, tokens)
    return users, sessions, tokens, uc


async def test_login_success_returns_tokens(auth_setup) -> None:
    users, sessions, tokens, uc = auth_setup
    await users.add(_make_user())

    result = await uc.execute(LoginInput(login="alice@example.com", password="Strong!Passw0rd2026"))
    assert result.access_token
    assert result.refresh_token
    assert result.username == "alice"
    # refresh token stored with hash, not raw
    stored = await sessions.get_by_hash(tokens.hash_refresh_token(result.refresh_token))
    assert stored is not None
    assert stored.is_active


async def test_login_accepts_username_or_email(auth_setup) -> None:
    users, _, _, uc = auth_setup
    await users.add(_make_user())
    result = await uc.execute(LoginInput(login="alice", password="Strong!Passw0rd2026"))
    assert result.username == "alice"


async def test_login_wrong_password_raises_generic(auth_setup) -> None:
    users, _, _, uc = auth_setup
    await users.add(_make_user())
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(LoginInput(login="alice", password="wrong-password"))
    # Generic message, no hint about user existence
    assert exc.value.code == "invalid_credentials"


async def test_login_nonexistent_user_raises_generic(auth_setup) -> None:
    _, _, _, uc = auth_setup
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(LoginInput(login="ghost@example.com", password="whatever"))
    assert exc.value.code == "invalid_credentials"


async def test_login_inactive_user_raises_generic(auth_setup) -> None:
    users, _, _, uc = auth_setup
    await users.add(_make_user(active=False))
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(LoginInput(login="alice", password="Strong!Passw0rd2026"))
    assert exc.value.code == "invalid_credentials"


async def test_login_locked_account_raises_specific_code(auth_setup) -> None:
    from datetime import timedelta

    users, _, _, uc = auth_setup
    await users.add(_make_user(locked_until=datetime.now(UTC) + timedelta(minutes=5)))
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(LoginInput(login="alice", password="Strong!Passw0rd2026"))
    assert exc.value.code == "account_locked"


async def test_failed_attempts_increment_and_lock(auth_setup) -> None:
    users, _, _, uc = auth_setup
    user = await users.add(_make_user())

    for i in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthenticationError):
            await uc.execute(LoginInput(login="alice", password="bad"))
        updated = await users.get_by_id(user.id)
        assert updated.failed_login_attempts == i + 1

    # After the threshold the account is locked
    updated = await users.get_by_id(user.id)
    assert updated.locked_until is not None
    assert updated.is_locked


async def test_successful_login_resets_counters(auth_setup) -> None:
    users, _, _, uc = auth_setup
    user = await users.add(_make_user(failed=3))

    result = await uc.execute(LoginInput(login="alice", password="Strong!Passw0rd2026"))
    assert result.username == "alice"
    updated = await users.get_by_id(user.id)
    assert updated.failed_login_attempts == 0
    assert updated.locked_until is None
    assert updated.last_login_at is not None

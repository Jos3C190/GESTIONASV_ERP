"""Unit tests for RefreshTokenUseCase (rotation + reuse detection)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.application.auth.authenticate_user import AuthenticateUserUseCase, LoginInput
from app.application.auth.refresh_token import RefreshInput, RefreshTokenUseCase
from app.core.exceptions import AuthenticationError
from app.core.security import hash_password
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
        username="bob",
        email="bob@example.com",
        password_hash=hash_password("Strong!Passw0rd2026"),
        is_active=True,
        password_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await users.add(user)
    result = await uc.execute(LoginInput(login="bob", password="Strong!Passw0rd2026"))
    return result.refresh_token


async def test_refresh_rotates_token_and_issues_new_access() -> None:
    users = InMemoryUserRepository()
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService()
    raw = await _login(users, sessions, tokens)

    uc = RefreshTokenUseCase(users, sessions, tokens)
    result = await uc.execute(RefreshInput(raw_refresh_token=raw))
    assert result.access_token
    assert result.refresh_token  # new raw
    assert result.refresh_token != raw

    # The old token is now revoked
    old_stored = await sessions.get_by_hash(tokens.hash_refresh_token(raw))
    assert old_stored.revoked_at is not None


async def test_refresh_reuse_revokes_all_sessions() -> None:
    users = InMemoryUserRepository()
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService()
    raw = await _login(users, sessions, tokens)

    uc = RefreshTokenUseCase(users, sessions, tokens)
    first = await uc.execute(RefreshInput(raw_refresh_token=raw))
    # First refresh succeeds and gives a new token

    # Reusing the OLD token again must trigger reuse detection
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(RefreshInput(raw_refresh_token=raw))
    assert exc.value.code == "session_revoked"

    # The new token from the first refresh must ALSO be revoked
    new_stored = await sessions.get_by_hash(tokens.hash_refresh_token(first.refresh_token))
    assert new_stored.revoked_at is not None


async def test_refresh_unknown_token_raises() -> None:
    users = InMemoryUserRepository()
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService()
    uc = RefreshTokenUseCase(users, sessions, tokens)
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(RefreshInput(raw_refresh_token="never-issued-token"))
    assert exc.value.code == "token_invalid"


async def test_refresh_expired_token_triggers_reuse_protection() -> None:
    users = InMemoryUserRepository()
    sessions = InMemoryRefreshTokenRepository()
    tokens = FakeTokenService(refresh_ttl_days=0)  # 0 days -> immediate expiry
    # Bypass login and insert an expired token directly
    user = User(
        id=uuid.uuid4(),
        username="exp",
        email="exp@example.com",
        password_hash=hash_password("Strong!Passw0rd2026"),
        is_active=True,
        password_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await users.add(user)
    raw = tokens.generate_refresh_token()
    from app.domain.entities.auth import RefreshToken

    await sessions.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=tokens.hash_refresh_token(raw),
            user_agent=None,
            ip_address=None,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
            revoked_at=None,
            rotated_from=None,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    uc = RefreshTokenUseCase(users, sessions, tokens)
    with pytest.raises(AuthenticationError) as exc:
        await uc.execute(RefreshInput(raw_refresh_token=raw))
    assert exc.value.code == "session_revoked"

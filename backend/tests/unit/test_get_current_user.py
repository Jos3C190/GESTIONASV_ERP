"""Authentication-boundary tests for access tokens and user state."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.auth.get_current_user import GetCurrentUserUseCase
from app.core.exceptions import AuthenticationError
from app.domain.entities.user import User

from tests.unit.fakes import InMemoryUserRepository


def _user(*, active: bool) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        username="usuario",
        email="usuario@example.test",
        password_hash="not-a-real-password-hash",
        is_active=active,
        created_at=now,
        updated_at=now,
    )


async def test_current_user_accepts_an_active_visible_account() -> None:
    repository = InMemoryUserRepository()
    stored = await repository.add(_user(active=True))

    result = await GetCurrentUserUseCase(repository).execute(stored.id)

    assert result.user.id == stored.id


async def test_current_user_rejects_inactive_account_even_with_valid_access_token() -> None:
    repository = InMemoryUserRepository()
    stored = await repository.add(_user(active=False))

    with pytest.raises(AuthenticationError) as exc:
        await GetCurrentUserUseCase(repository).execute(stored.id)

    assert exc.value.code == "account_inactive"

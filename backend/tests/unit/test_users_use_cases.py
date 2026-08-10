"""Unit tests for user management use cases (in-memory fakes)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.users.admin_actions import (
    DeactivateUserUseCase,
    ForcePasswordResetInput,
    ForcePasswordResetUseCase,
    UnlockAccountUseCase,
)
from app.application.users.get_user import GetUserUseCase
from app.application.users.list_users import ListUsersInput, ListUsersUseCase
from app.application.users.update_user import UpdateUserInput, UpdateUserUseCase
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.security import hash_password, verify_password
from app.domain.entities.user import User

from tests.unit.fakes import InMemoryUserRepository


def _make_user(
    *,
    uid: uuid.UUID | None = None,
    username: str = "alice",
    email: str = "alice@example.com",
    active: bool = True,
    superuser: bool = False,
    locked: bool = False,
    failed: int = 0,
) -> User:
    from datetime import timedelta

    return User(
        id=uid or uuid.uuid4(),
        username=username,
        email=email,
        password_hash=hash_password("Strong!Passw0rd2026"),
        is_active=active,
        is_superuser=superuser,
        failed_login_attempts=failed,
        locked_until=datetime.now(UTC) + timedelta(minutes=5) if locked else None,
        password_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def _seed(repo: InMemoryUserRepository, *users: User) -> None:
    for u in users:
        await repo.add(u)


# ---------------- ListUsers ----------------


async def test_list_users_returns_paginated_result() -> None:
    repo = InMemoryUserRepository()
    for i in range(25):
        await repo.add(_make_user(username=f"u{i}", email=f"u{i}@e.com"))
    uc = ListUsersUseCase(repo)
    result = await uc.execute(ListUsersInput(page=1, size=10))
    assert len(result.items) == 10
    assert result.total == 25
    assert result.page == 1
    assert result.pages == 3


async def test_list_users_search_filters() -> None:
    repo = InMemoryUserRepository()
    await _seed(
        repo, _make_user(username="alice"), _make_user(username="bob", email="bob@example.com")
    )
    uc = ListUsersUseCase(repo)
    result = await uc.execute(ListUsersInput(page=1, size=10, search="ali"))
    assert len(result.items) == 1
    assert result.items[0].username == "alice"


async def test_list_users_empty_result() -> None:
    repo = InMemoryUserRepository()
    uc = ListUsersUseCase(repo)
    result = await uc.execute(ListUsersInput(page=1, size=10, search="zzz"))
    assert result.items == []
    assert result.total == 0
    assert result.pages == 1


async def test_list_users_status_filter_applies_before_pagination() -> None:
    repo = InMemoryUserRepository()
    for i in range(12):
        await repo.add(_make_user(username=f"active{i}", email=f"active{i}@e.com"))
    for i in range(3):
        await repo.add(
            _make_user(username=f"inactive{i}", email=f"inactive{i}@e.com", active=False)
        )
    result = await ListUsersUseCase(repo).execute(
        ListUsersInput(page=1, size=2, status_filter="inactive")
    )
    assert len(result.items) == 2
    assert result.total == 3
    assert result.pages == 2
    assert all(not user.is_active for user in result.items)


# ---------------- GetUser ----------------


async def test_get_user_success() -> None:
    repo = InMemoryUserRepository()
    created = await repo.add(_make_user())
    uc = GetUserUseCase(repo)
    result = await uc.execute(created.id)
    assert result.user.username == "alice"


async def test_get_user_not_found() -> None:
    repo = InMemoryUserRepository()
    uc = GetUserUseCase(repo)
    with pytest.raises(NotFoundError):
        await uc.execute(uuid.uuid4())


# ---------------- UpdateUser ----------------


async def test_update_user_activate() -> None:
    repo = InMemoryUserRepository()
    target = await repo.add(_make_user(active=False))
    actor = await repo.add(_make_user(username="admin", superuser=True))
    uc = UpdateUserUseCase(repo)
    updated = await uc.execute(
        UpdateUserInput(target_id=target.id, actor_id=actor.id, is_active=True)
    )
    assert updated.is_active is True


async def test_update_user_cannot_self_deactivate() -> None:
    repo = InMemoryUserRepository()
    admin = await repo.add(_make_user(username="admin", superuser=True))
    uc = UpdateUserUseCase(repo)
    with pytest.raises(AuthorizationError) as exc:
        await uc.execute(UpdateUserInput(target_id=admin.id, actor_id=admin.id, is_active=False))
    assert exc.value.code == "self_deactivate_forbidden"


async def test_update_user_cannot_self_demote() -> None:
    repo = InMemoryUserRepository()
    admin = await repo.add(_make_user(username="admin", superuser=True))
    uc = UpdateUserUseCase(repo)
    with pytest.raises(AuthorizationError) as exc:
        await uc.execute(UpdateUserInput(target_id=admin.id, actor_id=admin.id, is_superuser=False))
    assert exc.value.code == "self_demote_forbidden"


async def test_update_user_cannot_remove_last_superadmin() -> None:
    repo = InMemoryUserRepository()
    admin = await repo.add(_make_user(username="admin", superuser=True))
    actor = await repo.add(_make_user(username="other", email="other@e.com", superuser=False))
    uc = UpdateUserUseCase(repo)
    with pytest.raises(BusinessRuleError) as exc:
        await uc.execute(UpdateUserInput(target_id=admin.id, actor_id=actor.id, is_superuser=False))
    assert exc.value.code == "last_superadmin_protected"


async def test_update_user_can_demote_when_two_superadmins() -> None:
    repo = InMemoryUserRepository()
    admin1 = await repo.add(_make_user(username="admin1", superuser=True))
    admin2 = await repo.add(_make_user(username="admin2", email="a2@e.com", superuser=True))
    uc = UpdateUserUseCase(repo)
    updated = await uc.execute(
        UpdateUserInput(target_id=admin1.id, actor_id=admin2.id, is_superuser=False)
    )
    assert updated.is_superuser is False


async def test_update_user_no_changes_returns_as_is() -> None:
    repo = InMemoryUserRepository()
    target = await repo.add(_make_user())
    actor = await repo.add(_make_user(username="admin", superuser=True))
    uc = UpdateUserUseCase(repo)
    result = await uc.execute(UpdateUserInput(target_id=target.id, actor_id=actor.id))
    assert result.is_active is True


# ---------------- ForcePasswordReset ----------------


async def test_force_password_reset_success() -> None:
    repo = InMemoryUserRepository()
    target = await repo.add(_make_user())
    actor = await repo.add(_make_user(username="admin", superuser=True))
    uc = ForcePasswordResetUseCase(repo)
    updated = await uc.execute(
        ForcePasswordResetInput(
            target_id=target.id, actor_id=actor.id, new_password="New!Strong2026"
        )
    )
    assert verify_password("New!Strong2026", updated.password_hash)


async def test_force_password_reset_cannot_self() -> None:
    repo = InMemoryUserRepository()
    admin = await repo.add(_make_user(username="admin", superuser=True))
    uc = ForcePasswordResetUseCase(repo)
    with pytest.raises(AuthorizationError) as exc:
        await uc.execute(
            ForcePasswordResetInput(
                target_id=admin.id, actor_id=admin.id, new_password="New!Strong2026"
            )
        )
    assert exc.value.code == "self_reset_forbidden"


async def test_force_password_reset_not_found() -> None:
    repo = InMemoryUserRepository()
    uc = ForcePasswordResetUseCase(repo)
    with pytest.raises(NotFoundError):
        await uc.execute(
            ForcePasswordResetInput(
                target_id=uuid.uuid4(), actor_id=uuid.uuid4(), new_password="New!Strong2026"
            )
        )


# ---------------- UnlockAccount ----------------


async def test_unlock_account_success() -> None:
    repo = InMemoryUserRepository()
    target = await repo.add(_make_user(locked=True, failed=5))
    uc = UnlockAccountUseCase(repo)
    updated = await uc.execute(target.id)
    assert updated.failed_login_attempts == 0
    assert updated.locked_until is None


async def test_unlock_account_idempotent_when_already_unlocked() -> None:
    repo = InMemoryUserRepository()
    target = await repo.add(_make_user())
    uc = UnlockAccountUseCase(repo)
    updated = await uc.execute(target.id)
    assert updated.failed_login_attempts == 0


# ---------------- DeactivateUser ----------------


async def test_deactivate_user_success() -> None:
    repo = InMemoryUserRepository()
    target = await repo.add(_make_user())
    actor = await repo.add(_make_user(username="admin", superuser=True))
    uc = DeactivateUserUseCase(repo)
    ok = await uc.execute(target.id, actor.id)
    assert ok is True
    deactivated = await repo.get_by_id(target.id)
    assert deactivated is not None
    assert deactivated.is_active is False
    assert deactivated.deleted_at is None


async def test_deactivate_user_cannot_self() -> None:
    repo = InMemoryUserRepository()
    admin = await repo.add(_make_user(username="admin", superuser=True))
    uc = DeactivateUserUseCase(repo)
    with pytest.raises(AuthorizationError) as exc:
        await uc.execute(admin.id, admin.id)
    assert exc.value.code == "self_deactivate_forbidden"


async def test_deactivate_user_cannot_remove_last_superadmin() -> None:
    repo = InMemoryUserRepository()
    admin = await repo.add(_make_user(username="admin", superuser=True))
    actor = await repo.add(_make_user(username="other", email="o@e.com", superuser=False))
    uc = DeactivateUserUseCase(repo)
    with pytest.raises(BusinessRuleError) as exc:
        await uc.execute(admin.id, actor.id)
    assert exc.value.code == "last_superadmin_protected"


async def test_deactivate_user_not_found() -> None:
    repo = InMemoryUserRepository()
    uc = DeactivateUserUseCase(repo)
    with pytest.raises(NotFoundError):
        await uc.execute(uuid.uuid4(), uuid.uuid4())

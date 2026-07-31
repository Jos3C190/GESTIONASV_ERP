"""Unit tests for RBAC use cases (in-memory fakes)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.application.rbac.check_permission import (
    CheckPermissionUseCase,
    GetEffectivePermissionsUseCase,
)
from app.application.rbac.role_assignment import (
    AssignRoleInput,
    AssignRoleUseCase,
    RevokeRoleInput,
    RevokeRoleUseCase,
)
from app.application.rbac.role_crud import (
    CreateRoleInput,
    CreateRoleUseCase,
    DeleteRoleUseCase,
    SetRolePermissionsInput,
    SetRolePermissionsUseCase,
    UpdateRoleInput,
    UpdateRoleUseCase,
)
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.domain.entities.rbac import Permission, Role
from app.domain.entities.user import User

from tests.unit.fakes import InMemoryUserRepository
from tests.unit.rbac_fakes import (
    InMemoryPermissionRepository,
    InMemoryRoleRepository,
)


def _make_user(*, superuser=False, active=True, uid=None, username="alice", email="alice@example.com") -> User:
    return User(
        id=uid or uuid.uuid4(),
        username=username,
        email=email,
        password_hash=hash_password("Strong!Passw0rd2026"),
        is_active=active,
        is_superuser=superuser,
        password_changed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_perm(code="users:read", module="users") -> Permission:
    return Permission(id=uuid.uuid4(), code=code, module=module, description=code)


async def _seed_perms(repo: InMemoryPermissionRepository, *codes: str) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for c in codes:
        p = await repo.add(Permission(id=uuid.uuid4(), code=c, module=c.split(":")[0]))
        ids[c] = p.id
    return ids


# ---------------- CheckPermission ----------------


async def test_check_permission_superuser_always_passes() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    admin = await users.add(_make_user(superuser=True))
    uc = CheckPermissionUseCase(users, roles)
    result = await uc.execute(admin.id, "anything:whatever")
    assert result.allowed
    assert result.reason == "superuser"


async def test_check_permission_non_superadmin_granted() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    perms = InMemoryPermissionRepository()
    perm_ids = await _seed_perms(perms, "users:read")
    role = await roles.add(Role(id=uuid.uuid4(), name="ADMIN"))
    all_perms = list(await perms.list_all())
    roles.register_perms(all_perms)
    await roles.set_permissions(role.id, {perm_ids["users:read"]})
    user = await users.add(_make_user(superuser=False))
    await roles.assign_role_to_user(user.id, role.id, uuid.uuid4())
    uc = CheckPermissionUseCase(users, roles)
    result = await uc.execute(user.id, "users:read")
    assert result.allowed
    assert result.reason == "granted"


async def test_check_permission_not_granted() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user(superuser=False))
    uc = CheckPermissionUseCase(users, roles)
    result = await uc.execute(user.id, "users:delete")
    assert not result.allowed
    assert result.reason == "not_granted"


async def test_check_permission_inactive_user_denied() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user(superuser=True, active=False))
    uc = CheckPermissionUseCase(users, roles)
    result = await uc.execute(user.id, "users:read")
    assert not result.allowed


# ---------------- GetEffectivePermissions ----------------


async def test_effective_permissions_superuser_returns_star() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    admin = await users.add(_make_user(superuser=True))
    uc = GetEffectivePermissionsUseCase(users, roles)
    result = await uc.execute(admin.id)
    assert result == ("*",)


async def test_effective_permissions_union_of_roles() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    perms = InMemoryPermissionRepository()
    perm_ids = await _seed_perms(perms, "users:read", "employees:read")
    r1 = await roles.add(Role(id=uuid.uuid4(), name="R1"))
    r2 = await roles.add(Role(id=uuid.uuid4(), name="R2"))
    all_perms = list(await perms.list_all())
    roles.register_perms(all_perms)
    await roles.set_permissions(r1.id, {perm_ids["users:read"]})
    await roles.set_permissions(r2.id, {perm_ids["employees:read"]})
    user = await users.add(_make_user(superuser=False))
    await roles.assign_role_to_user(user.id, r1.id, uuid.uuid4())
    await roles.assign_role_to_user(user.id, r2.id, uuid.uuid4())
    uc = GetEffectivePermissionsUseCase(users, roles)
    result = await uc.execute(user.id)
    assert set(result) == {"users:read", "employees:read"}


# ---------------- Role CRUD ----------------


async def test_create_role_success() -> None:
    roles = InMemoryRoleRepository()
    uc = CreateRoleUseCase(roles)
    r = await uc.execute(CreateRoleInput(name="NEW_ROLE", description="test"))
    assert r.name == "NEW_ROLE"
    assert r.is_system is False


async def test_create_role_duplicate_name() -> None:
    roles = InMemoryRoleRepository()
    uc = CreateRoleUseCase(roles)
    await uc.execute(CreateRoleInput(name="DUP"))
    with pytest.raises(ConflictError):
        await uc.execute(CreateRoleInput(name="DUP"))


async def test_update_role_success() -> None:
    roles = InMemoryRoleRepository()
    created = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="OLD"))
    uc = UpdateRoleUseCase(roles)
    updated = await uc.execute(UpdateRoleInput(role_id=created.id, name="NEW"))
    assert updated.name == "NEW"


async def test_update_role_not_found() -> None:
    roles = InMemoryRoleRepository()
    with pytest.raises(NotFoundError):
        await UpdateRoleUseCase(roles).execute(UpdateRoleInput(role_id=uuid.uuid4(), name="X"))


async def test_delete_role_success() -> None:
    roles = InMemoryRoleRepository()
    created = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="DEL"))
    ok = await DeleteRoleUseCase(roles).execute(created.id)
    assert ok is True


async def test_delete_system_role_forbidden() -> None:
    roles = InMemoryRoleRepository()
    role = await roles.add(Role(id=uuid.uuid4(), name="SYS", is_system=True))
    with pytest.raises(BusinessRuleError) as exc:
        await DeleteRoleUseCase(roles).execute(role.id)
    assert exc.value.code == "system_role_protected"


async def test_set_role_permissions() -> None:
    roles = InMemoryRoleRepository()
    perms = InMemoryPermissionRepository()
    await _seed_perms(perms, "users:read", "users:create")
    roles.register_perms(list(await perms.list_all()))
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="R"))
    uc = SetRolePermissionsUseCase(roles, perms)
    updated = await uc.execute(
        SetRolePermissionsInput(role_id=role.id, permission_codes=("users:read", "users:create"))
    )
    assert len(updated.permissions) == 2


async def test_set_role_permissions_rejects_unknown_code() -> None:
    roles = InMemoryRoleRepository()
    perms = InMemoryPermissionRepository()
    roles.register_perms(list(await perms.list_all()))
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="R"))
    uc = SetRolePermissionsUseCase(roles, perms)
    with pytest.raises(BusinessRuleError):
        await uc.execute(SetRolePermissionsInput(role_id=role.id, permission_codes=("unknown:perm",)))


# ---------------- Role assignment ----------------


async def test_assign_role_success() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user())
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="R"))
    actor = await users.add(_make_user(username="admin", email="admin@e.com", superuser=True))
    uc = AssignRoleUseCase(users, roles)
    created = await uc.execute(
        AssignRoleInput(user_id=user.id, role_id=role.id, assigned_by=actor.id)
    )
    assert created is True


async def test_assign_role_idempotent() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user())
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="R"))
    actor = await users.add(_make_user(username="admin", email="a@e.com"))
    uc = AssignRoleUseCase(users, roles)
    await uc.execute(AssignRoleInput(user_id=user.id, role_id=role.id, assigned_by=actor.id))
    created = await uc.execute(AssignRoleInput(user_id=user.id, role_id=role.id, assigned_by=actor.id))
    assert created is False


async def test_assign_superadmin_to_self_forbidden() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    admin = await users.add(_make_user(username="admin", email="a@e.com", superuser=True))
    role = await roles.add(Role(id=uuid.uuid4(), name="SUPER_ADMIN", is_system=True))
    uc = AssignRoleUseCase(users, roles)
    with pytest.raises(BusinessRuleError) as exc:
        await uc.execute(AssignRoleInput(user_id=admin.id, role_id=role.id, assigned_by=admin.id))
    assert exc.value.code == "self_superadmin_assign_forbidden"


async def test_revoke_role_success() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user())
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="R"))
    fallback_role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="FALLBACK"))
    actor = await users.add(_make_user(username="admin", email="a@e.com"))
    await AssignRoleUseCase(users, roles).execute(
        AssignRoleInput(user_id=user.id, role_id=role.id, assigned_by=actor.id)
    )
    await AssignRoleUseCase(users, roles).execute(
        AssignRoleInput(user_id=user.id, role_id=fallback_role.id, assigned_by=actor.id)
    )
    uc = RevokeRoleUseCase(users, roles)
    ok = await uc.execute(RevokeRoleInput(user_id=user.id, role_id=role.id, actor_id=actor.id))
    assert ok is True


async def test_revoke_last_role_forbidden() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user())
    actor = await users.add(_make_user(username="admin", email="a@e.com"))
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="ONLY"))
    await AssignRoleUseCase(users, roles).execute(
        AssignRoleInput(user_id=user.id, role_id=role.id, assigned_by=actor.id)
    )
    with pytest.raises(BusinessRuleError) as exc:
        await RevokeRoleUseCase(users, roles).execute(
            RevokeRoleInput(user_id=user.id, role_id=role.id, actor_id=actor.id)
        )
    assert exc.value.code == "user_requires_role"


async def test_revoke_superadmin_from_self_forbidden() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    admin = await users.add(_make_user(username="admin", email="a@e.com", superuser=True))
    role = await roles.add(Role(id=uuid.uuid4(), name="SUPER_ADMIN", is_system=True))
    uc = RevokeRoleUseCase(users, roles)
    with pytest.raises(BusinessRuleError) as exc:
        await uc.execute(RevokeRoleInput(user_id=admin.id, role_id=role.id, actor_id=admin.id))
    assert exc.value.code == "self_superadmin_revoke_forbidden"


async def test_revoke_role_not_assigned() -> None:
    users = InMemoryUserRepository()
    roles = InMemoryRoleRepository()
    user = await users.add(_make_user())
    role = await CreateRoleUseCase(roles).execute(CreateRoleInput(name="R"))
    actor = await users.add(_make_user(username="admin", email="a@e.com"))
    uc = RevokeRoleUseCase(users, roles)
    ok = await uc.execute(RevokeRoleInput(user_id=user.id, role_id=role.id, actor_id=actor.id))
    assert ok is False

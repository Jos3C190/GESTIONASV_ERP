"""Integration coverage for purchase-request RBAC migration data."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

import pytest
from alembic import command
from alembic.config import Config
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.organization import Company, UserCompany
from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole
from app.infrastructure.models.user import User
from app.infrastructure.repositories.role_repository import SqlAlchemyRoleRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PURCHASE_PERMISSION_CODES = frozenset(
    {
        "purchase_requests:read",
        "purchase_requests:manage",
        "purchase_requests:approve",
    }
)


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def _run_alembic(action: Literal["upgrade", "downgrade"], target: str) -> None:
    getattr(command, action)(_alembic_config(), target)


async def _purchase_permissions(session: AsyncSession) -> list[Permission]:
    return list(
        (
            await session.scalars(
                select(Permission)
                .where(Permission.code.in_(PURCHASE_PERMISSION_CODES))
                .order_by(Permission.code)
            )
        ).all()
    )


@pytest.fixture
async def migration_at_0043() -> AsyncIterator[None]:
    """Replay revision 0044 against the migrated, seeded test database."""

    await dispose_engine()
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "0043")
    try:
        yield
    finally:
        await dispose_engine()
        _run_alembic("upgrade", "head")
        await dispose_engine()


@pytest.fixture
async def migration_at_head() -> AsyncIterator[None]:
    """Keep tests that exercise downgrade isolated and restore head."""

    await dispose_engine()
    _run_alembic("upgrade", "head")
    try:
        yield
    finally:
        await dispose_engine()
        _run_alembic("upgrade", "head")
        await dispose_engine()


async def test_purchase_request_permissions_are_created_from_empty_catalogue(
    migration_at_0043: None,
) -> None:
    async with async_session_factory() as session:
        permissions = await _purchase_permissions(session)
        await session.execute(
            delete(RolePermission).where(
                RolePermission.permission_id.in_(permission.id for permission in permissions)
            )
        )
        await session.execute(
            delete(Permission).where(Permission.id.in_(permission.id for permission in permissions))
        )
        await session.commit()

    await dispose_engine()
    _run_alembic("upgrade", "0044")
    await dispose_engine()

    async with async_session_factory() as session:
        permissions = await _purchase_permissions(session)
        assert len(permissions) == len(PURCHASE_PERMISSION_CODES)
        assert {permission.code for permission in permissions} == PURCHASE_PERMISSION_CODES

        super_admin = await session.scalar(
            select(Role).where(
                Role.name == "SUPER_ADMIN",
                Role.is_system.is_(True),
                Role.company_id.is_(None),
                Role.deleted_at.is_(None),
            )
        )
        assert super_admin is not None

        assigned_permission_ids = set(
            (
                await session.scalars(
                    select(RolePermission.permission_id).where(
                        RolePermission.role_id == super_admin.id,
                        RolePermission.permission_id.in_(
                            permission.id for permission in permissions
                        ),
                    )
                )
            ).all()
        )
        assert assigned_permission_ids == {permission.id for permission in permissions}


async def test_purchase_request_permissions_are_idempotent_and_reconcile_existing_super_admin(
    migration_at_0043: None,
) -> None:
    async with async_session_factory() as session:
        permissions = await _purchase_permissions(session)
        permission_ids_before = {permission.code: permission.id for permission in permissions}
        super_admin = await session.scalar(
            select(Role).where(
                Role.name == "SUPER_ADMIN",
                Role.is_system.is_(True),
                Role.company_id.is_(None),
                Role.deleted_at.is_(None),
            )
        )
        assert super_admin is not None
        permission_to_reconcile = permissions[0]
        await session.execute(
            delete(RolePermission).where(
                RolePermission.role_id == super_admin.id,
                RolePermission.permission_id == permission_to_reconcile.id,
            )
        )
        await session.commit()

    await dispose_engine()
    _run_alembic("upgrade", "0044")
    await dispose_engine()

    async with async_session_factory() as session:
        permissions = await _purchase_permissions(session)
        assert {
            permission.code: permission.id for permission in permissions
        } == permission_ids_before
        super_admin = await session.scalar(
            select(Role).where(
                Role.name == "SUPER_ADMIN",
                Role.is_system.is_(True),
                Role.company_id.is_(None),
                Role.deleted_at.is_(None),
            )
        )
        assert super_admin is not None
        assigned_permission_ids = set(
            (
                await session.scalars(
                    select(RolePermission.permission_id).where(
                        RolePermission.role_id == super_admin.id,
                        RolePermission.permission_id.in_(
                            permission.id for permission in permissions
                        ),
                    )
                )
            ).all()
        )
        assert assigned_permission_ids == {permission.id for permission in permissions}

    # A second downgrade/upgrade replay must neither duplicate permissions nor
    # lose the grants that were already present before the replay.
    await dispose_engine()
    _run_alembic("downgrade", "0043")
    _run_alembic("upgrade", "0044")
    await dispose_engine()

    async with async_session_factory() as session:
        permissions_after_replay = await _purchase_permissions(session)
        assert {
            permission.code: permission.id for permission in permissions_after_replay
        } == permission_ids_before
        assert len(permissions_after_replay) == len(PURCHASE_PERMISSION_CODES)


async def test_purchase_request_permissions_reconcile_database_already_at_0044(
    migration_at_0043: None,
) -> None:
    """A database that applied the original 0044 still receives the RBAC fix."""
    await dispose_engine()
    _run_alembic("upgrade", "0044")

    async with async_session_factory() as session:
        permissions = await _purchase_permissions(session)
        assert len(permissions) == len(PURCHASE_PERMISSION_CODES)
        await session.execute(
            delete(RolePermission).where(
                RolePermission.permission_id.in_(permission.id for permission in permissions)
            )
        )
        await session.execute(
            delete(Permission).where(Permission.id.in_(permission.id for permission in permissions))
        )
        await session.commit()

    await dispose_engine()
    _run_alembic("upgrade", "head")
    await dispose_engine()

    async with async_session_factory() as session:
        permissions = await _purchase_permissions(session)
        assert {permission.code for permission in permissions} == PURCHASE_PERMISSION_CODES


async def test_purchase_request_downgrade_preserves_shared_rbac_rows(
    migration_at_head: None,
) -> None:
    async with async_session_factory() as session:
        company_id = await session.scalar(select(Company.id).limit(1))
        permission = await session.scalar(
            select(Permission).where(Permission.code == "purchase_requests:read")
        )
        assert company_id is not None
        assert permission is not None

        role = Role(
            company_id=company_id,
            name=f"purchase-migration-shared-{uuid.uuid4().hex[:12]}",
            description="Role used to verify shared RBAC preservation",
            is_system=False,
        )
        session.add(role)
        await session.flush()
        session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await session.commit()
        role_id = role.id
        permission_id = permission.id

    await dispose_engine()
    _run_alembic("downgrade", "0043")
    await dispose_engine()

    async with async_session_factory() as session:
        assert await session.get(Permission, permission_id) is not None
        assert await session.get(RolePermission, (role_id, permission_id)) is not None

    await dispose_engine()
    _run_alembic("upgrade", "0044")
    await dispose_engine()
    async with async_session_factory() as session:
        await session.execute(delete(Role).where(Role.id == role_id))
        await session.commit()


async def test_purchase_request_permissions_are_effective_for_assigned_user(
    migration_at_head: None,
) -> None:
    async with async_session_factory() as session:
        company_id = await session.scalar(select(Company.id).limit(1))
        permissions = await _purchase_permissions(session)
        assert company_id is not None
        assert len(permissions) == len(PURCHASE_PERMISSION_CODES)

        suffix = uuid.uuid4().hex[:12]
        user = User(
            username=f"purchase-rbac-{suffix}",
            email=f"purchase-rbac-{suffix}@example.test",
            password_hash="integration-test-only",
            is_active=True,
            is_superuser=False,
        )
        role = Role(
            company_id=company_id,
            name=f"purchase-rbac-{suffix}",
            description="Role used to verify effective purchase-request permissions",
            is_system=False,
        )
        session.add_all([user, role])
        await session.flush()
        session.add(UserCompany(user_id=user.id, company_id=company_id, is_default=True))
        session.add(UserRole(user_id=user.id, company_id=company_id, role_id=role.id))
        session.add_all(
            RolePermission(role_id=role.id, permission_id=permission.id)
            for permission in permissions
        )
        await session.flush()

        effective = SqlAlchemyRoleRepository(session)
        effective_codes = {
            permission.code
            for permission in await effective.get_effective_permissions_for_user(
                user.id, company_id
            )
        }
        assert effective_codes == PURCHASE_PERMISSION_CODES

        check = CheckPermissionUseCase(SqlAlchemyUserRepository(session), effective)
        for code in PURCHASE_PERMISSION_CODES:
            result = await check.execute(user.id, company_id, code)
            assert result.allowed is True
            assert result.reason == "granted"
        denied = await check.execute(user.id, company_id, "purchase_requests:delete")
        assert denied.allowed is False
        assert denied.reason == "not_granted"

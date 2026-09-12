"""Integration coverage for purchase-quotation RBAC migration data."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

import pytest
from alembic import command
from alembic.config import Config
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.rbac import Permission, Role, RolePermission
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

QUOTATION_PERMISSION_CODES = frozenset(
    {
        "purchase_quotations:read",
        "purchase_quotations:manage",
        "purchase_quotations:select",
    }
)


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def _run_alembic(action: Literal["upgrade", "downgrade"], target: str) -> None:
    getattr(command, action)(_alembic_config(), target)


async def _quotation_permissions(session: AsyncSession) -> list[Permission]:
    return list(
        (
            await session.scalars(
                select(Permission)
                .where(Permission.code.in_(QUOTATION_PERMISSION_CODES))
                .order_by(Permission.code)
            )
        ).all()
    )


@pytest.fixture
async def migration_at_0048() -> AsyncIterator[None]:
    await dispose_engine()
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "0048")
    try:
        yield
    finally:
        await dispose_engine()
        _run_alembic("upgrade", "head")
        await dispose_engine()


async def test_purchase_quotation_permissions_are_created_and_granted(
    migration_at_0048: None,
) -> None:
    async with async_session_factory() as session:
        existing = await _quotation_permissions(session)
        await session.execute(
            delete(RolePermission).where(
                RolePermission.permission_id.in_(permission.id for permission in existing)
            )
        )
        await session.execute(
            delete(Permission).where(Permission.id.in_(permission.id for permission in existing))
        )
        await session.commit()

    await dispose_engine()
    _run_alembic("upgrade", "0049")
    await dispose_engine()

    async with async_session_factory() as session:
        permissions = await _quotation_permissions(session)
        assert {permission.code for permission in permissions} == QUOTATION_PERMISSION_CODES

        super_admin = await session.scalar(
            select(Role).where(
                Role.name == "SUPER_ADMIN",
                Role.is_system.is_(True),
                Role.company_id.is_(None),
                Role.deleted_at.is_(None),
            )
        )
        assert super_admin is not None

        assigned_ids = set(
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
        assert assigned_ids == {permission.id for permission in permissions}


async def test_purchase_quotation_permission_migration_is_idempotent(
    migration_at_0048: None,
) -> None:
    await dispose_engine()
    _run_alembic("upgrade", "0049")
    await dispose_engine()

    async with async_session_factory() as session:
        before = await _quotation_permissions(session)
        ids_before = {permission.code: permission.id for permission in before}
        assert set(ids_before) == QUOTATION_PERMISSION_CODES

    await dispose_engine()
    _run_alembic("downgrade", "0048")
    _run_alembic("upgrade", "0049")
    await dispose_engine()

    async with async_session_factory() as session:
        after = await _quotation_permissions(session)
        assert {permission.code: permission.id for permission in after} == ids_before

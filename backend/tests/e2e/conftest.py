"""E2E fixtures for the real FastAPI app and isolated ``erp_db_test``.

The root test fixture rebuilds, migrates and seeds that database once per
suite. Development data is never used by setup, execution or cleanup.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def e2e_client() -> AsyncIterator[AsyncClient]:
    """Boot the real app with a real DB connection. Cleans auth tables before
    and after each test for isolation. Also resets rate limiters."""
    from app.infrastructure.db.session import async_session_factory, dispose_engine
    from app.main import create_app
    from app.middlewares.rate_limit import _login_limiter, _refresh_limiter, _reset_limiter

    # Reset rate limiters so tests don't interfere with each other.
    _login_limiter._buckets.clear()
    _refresh_limiter._buckets.clear()
    _reset_limiter._buckets.clear()

    # Clean auth tables before yielding.
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    # Cleanup after test.
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()
    await dispose_engine()


async def seed_user(
    *,
    username: str = "alice",
    email: str = "alice@example.com",
    password: str = "Strong!Passw0rd2026",
    is_superuser: bool = False,
    is_active: bool = True,
) -> str:
    """Insert a user directly via the ORM and return their id as a string.
    Used by e2e tests to set up known state before hitting the API.
    """
    from app.core.security import hash_password
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.employee import Employee as ORMEmployee
    from app.infrastructure.models.organization import UserCompany
    from app.infrastructure.models.user import User as ORMUser

    async with async_session_factory() as session:
        orm = ORMUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=is_active,
            is_superuser=is_superuser,
        )
        session.add(orm)
        await session.flush()
        company_id = await get_test_company_id(session=session)
        session.add(
            UserCompany(
                user_id=orm.id,
                company_id=company_id,
                is_default=True,
                access_all_branches=True,
            )
        )
        session.add(
            ORMEmployee(
                company_id=company_id,
                employee_code=f"TST-{orm.id.hex[:12].upper()}",
                first_name=username,
                last_name="Prueba",
                user_id=orm.id,
                status="activo",
            )
        )
        await session.commit()
        await session.refresh(orm)
        return str(orm.id)


async def get_test_company_id(*, session: AsyncSession | None = None) -> uuid.UUID:
    """Return the stable active company used by E2E operational-context tests."""
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.organization import Company
    from sqlalchemy import select

    async def _read(active_session: AsyncSession) -> uuid.UUID:
        return (
            await active_session.execute(
                select(Company.id)
                .where(Company.is_active.is_(True))
                .order_by(Company.created_at, Company.id)
                .limit(1)
            )
        ).scalar_one()

    if session is not None:
        return await _read(session)
    async with async_session_factory() as owned_session:
        return await _read(owned_session)


async def count_users() -> int:
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.user import User as ORMUser
    from sqlalchemy import func, select

    async with async_session_factory() as session:
        return int((await session.execute(select(func.count(ORMUser.id)))).scalar_one())


pytestmark = pytest.mark.e2e

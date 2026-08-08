"""Async engine + session factory.

Single shared engine per process. `get_async_session` is the FastAPI dependency
used by endpoints. Tests can override the engine via `set_test_engine`.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _build_engine(url: str) -> AsyncEngine:
    connect_args: dict[str, Any] = {}
    if "+asyncpg" in url or "postgresql" in url:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    return create_async_engine(
        url,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args=connect_args,
        future=True,
    )


async_engine: AsyncEngine = _build_engine(settings.DATABASE_URL)
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Yields a session, rolls back only on unexpected
    errors. Business exceptions (AppError) are treated as normal flow: the
    session is committed so partial writes (e.g. failed login counters) are
    persisted. Unexpected exceptions trigger a rollback.
    """
    from app.core.exceptions import AppError

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except AppError:
            # Business rule violation — persist any audit/counter writes done
            # before the error was raised, then let the exception propagate to
            # the exception handler.
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Imperative context (for use cases / scripts outside FastAPI)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """DEV ONLY — creates tables from metadata. Production uses Alembic."""
    from app.infrastructure.db.base import Base
    from app.infrastructure import models  # noqa: F401 — register tables

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    await async_engine.dispose()


# --- Test overrides ---
_test_engine: AsyncEngine | None = None


def set_test_engine(engine: AsyncEngine) -> None:
    """Rebind the session factory to a test engine (conftest.py uses this)."""
    global _test_engine, async_session_factory
    _test_engine = engine
    async_session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
    )


def get_engine() -> AsyncEngine:
    return _test_engine if _test_engine is not None else async_engine


__all__: dict[str, Any] = {
    "async_engine": async_engine,
    "async_session_factory": async_session_factory,
    "get_async_session": get_async_session,
    "session_scope": session_scope,
    "create_all": create_all,
    "dispose_engine": dispose_engine,
    "set_test_engine": set_test_engine,
    "get_engine": get_engine,
}
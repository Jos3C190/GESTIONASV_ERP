"""Shared pytest fixtures.

Pure unit runs remain database-free. Whenever integration or E2E tests are
collected, the suite rebuilds a dedicated ``erp_db_test`` database, migrates it
and loads the canonical seed. Validation must never mutate development data.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Assignment is intentional: Compose injects the development DSN and using
# ``setdefault`` here would silently make E2E tests mutate it.
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["OBSERVABILITY_ENABLED"] = "false"
# The application container enables Redis/OCR for local development.  In-process
# E2E clients must not share that durable rate-limit state across test cases.
os.environ["REDIS_ENABLED"] = "false"
os.environ["OCR_ENABLED"] = "false"
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+asyncpg://erp_admin:change_me_in_production_please@db:5432/erp_db_test",
)
TEST_DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_TEST_SYNC",
    TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://"),
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL_SYNC"] = TEST_DATABASE_URL_SYNC
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("SUPER_ADMIN_PASSWORD", "TestOnly!SuperAdmin2026")


def _has_database_tests(request: pytest.FixtureRequest) -> bool:
    return any(
        item.get_closest_marker("integration") is not None
        or item.get_closest_marker("e2e") is not None
        for item in request.session.items
    )


def _prepare_postgres_database() -> None:
    """Create and rebuild only the dedicated test database."""
    from alembic import command
    from alembic.config import Config
    from psycopg import connect, sql

    database_name = TEST_DATABASE_URL_SYNC.rsplit("/", 1)[-1].split("?", 1)[0]
    if database_name != "erp_db_test":
        raise RuntimeError(
            "Las pruebas con base de datos solo pueden ejecutarse sobre erp_db_test."
        )

    psycopg_dsn = TEST_DATABASE_URL_SYNC.replace("postgresql+psycopg://", "postgresql://")
    admin_dsn = f"{psycopg_dsn.rsplit('/', 1)[0]}/postgres"
    with connect(admin_dsn, autocommit=True) as admin:
        exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if exists is None:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    with connect(psycopg_dsn, autocommit=True) as database:
        database.execute("DROP SCHEMA IF EXISTS public CASCADE")
        database.execute("CREATE SCHEMA public")
        database.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER")
        database.execute("GRANT ALL ON SCHEMA public TO public")

    backend_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_root / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL_SYNC)
    command.upgrade(alembic_config, "head")

    from app.infrastructure.db.session import dispose_engine
    from seed.seed_data import bootstrap

    async def seed_and_release_pool() -> None:
        await bootstrap(force=True)
        # asyncpg connections belong to the loop that created them. Releasing
        # the bootstrap pool prevents tests from inheriting closed-loop handles.
        await dispose_engine()

    asyncio.run(seed_and_release_pool())


@pytest.fixture(scope="session", autouse=True)
def _isolated_database(request: pytest.FixtureRequest):
    """Prepare PostgreSQL only when the collected tests actually need it."""
    if _has_database_tests(request):
        _prepare_postgres_database()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the FastAPI app via ASGI transport (in-process).
    Migrations are mocked so the app boots without a DB. Used for non-DB tests.
    """
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

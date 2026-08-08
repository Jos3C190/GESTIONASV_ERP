"""FastAPI application factory + startup/shutdown hooks.

Startup:
- configure logging
- run Alembic migrations to head (so containers are self-bootstrapping)
- expose OpenAPI at /docs and /redoc (only when DEBUG=true in production we
  disable /docs)

Shutdown:
- dispose the DB engine pool
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.session import dispose_engine
from app.middlewares import RequestContextMiddleware, SecurityHeadersMiddleware

log = get_logger(__name__)


async def _run_migrations() -> None:
    """Run Alembic to head on startup. Failures log and re-raise so the
    container restarts (healthcheck will then mark it unhealthy).

    We run Alembic's high-level `command.upgrade` in a worker thread because
    Alembic's command API is sync. The async DSN is converted to a sync one
    (asyncpg -> psycopg) for this one-shot call; the app's own async engine
    is untouched.
    """
    import asyncio
    import concurrent.futures
    import re

    from alembic import command
    from alembic.config import Config as AlembicConfig

    from app.core.logging import get_logger

    log = get_logger(__name__)

    sync_url = settings.DATABASE_URL_SYNC or re.sub(
        r"\+asyncpg://", "://", settings.DATABASE_URL
    )
    masked = sync_url.replace(settings.POSTGRES_PASSWORD, "***")
    log.info("migrations_start", url=masked)

    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", sync_url)

    def _upgrade() -> None:
        command.upgrade(cfg, "head")

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        await loop.run_in_executor(pool, _upgrade)

    log.info("migrations_done")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("startup", environment=settings.ENVIRONMENT, debug=settings.DEBUG)
    try:
        await _run_migrations()
    except Exception:
        log.exception("migration_failed")
        raise
    yield
    log.info("shutdown")
    await dispose_engine()


def create_app() -> FastAPI:
    docs_url = "/docs" if not settings.is_production else None
    redoc_url = "/redoc" if not settings.is_production else None
    openapi_url = "/openapi.json" if not settings.is_production else None

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="ERP System — backend API. Phase 0 (foundation).",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
        debug=settings.DEBUG,
    )

    # Middlewares (order matters: outermost first).
    # CORS is the outermost so preflight always works.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-Company-ID",
            "X-Branch-ID",
        ],
        expose_headers=["X-Request-Id"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Routers
    app.include_router(api_router)

    # Exception handlers
    register_exception_handlers(app)

    # Root welcome (kept minimal — full API is under /health and /api/v1/*)
    @app.get("/", tags=["root"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "app": settings.APP_NAME,
            "status": "ok",
            "docs": "/docs" if not settings.is_production else "disabled",
            "health": "/health",
        }

    return app


app = create_app()

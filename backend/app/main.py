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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.session import dispose_engine
from app.infrastructure.observability import initialize_observability, shutdown_observability
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

    sync_url = settings.DATABASE_URL_SYNC or re.sub(r"\+asyncpg://", "://", settings.DATABASE_URL)
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
    initialize_observability("erp-backend", app=app)
    log.info("startup", environment=settings.ENVIRONMENT, debug=settings.DEBUG)
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        try:
            await _run_migrations()
        except Exception:
            log.exception("migration_failed")
            raise
    yield
    log.info("shutdown")
    await dispose_engine()
    shutdown_observability()


def create_app() -> FastAPI | CORSMiddleware:
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

    # Register request and security middleware on the FastAPI application.
    # CORS is applied as a wrapper below so it also decorates error responses
    # produced by FastAPI's outer exception middleware.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Routers
    app.include_router(api_router)

    # Exception handlers
    register_exception_handlers(app)

    # Instrument before Starlette builds its middleware stack. Lifespan calls
    # the same idempotent initializer again to reattach the OTLP log handler.
    initialize_observability("erp-backend", app=app)

    # Root welcome (kept minimal — full API is under /health and /api/v1/*)
    @app.get("/", tags=["root"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "app": settings.APP_NAME,
            "status": "ok",
            "docs": "/docs" if not settings.is_production else "disabled",
            "health": "/health",
        }

    # Wrap the complete application instead of registering CORS as an inner
    # FastAPI middleware. Starlette's documented pattern guarantees that
    # authentication and validation errors retain CORS headers as well.
    cors_app = CORSMiddleware(
        app,
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
            "traceparent",
            "tracestate",
        ],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
    )
    # Keep FastAPI's testing/dependency-override contract available on the
    # outer ASGI wrapper. The inner application reads the same dictionary,
    # so security fixtures can continue to replace dependencies safely.
    cors_app.dependency_overrides = app.dependency_overrides  # type: ignore[attr-defined]
    return cors_app


app = create_app()

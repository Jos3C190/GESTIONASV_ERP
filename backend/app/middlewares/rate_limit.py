"""Distributed rate limiting with an in-memory availability fallback."""

from __future__ import annotations

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.infrastructure.rate_limiter import (
    FallbackRateLimitStore,
    InMemoryRateLimitStore,
    RedisRateLimitStore,
    parse_rate_limit,
)
from app.infrastructure.redis_client import get_redis_client


def _store() -> FallbackRateLimitStore:
    primary = None
    if settings.REDIS_ENABLED and settings.REDIS_URL:
        primary = RedisRateLimitStore(get_redis_client())
    return FallbackRateLimitStore(primary, InMemoryRateLimitStore())


_rate_limit_store = _store()


async def _check(request: Request, operation: str, configured_limit: str) -> None:
    limit, window_seconds = parse_rate_limit(configured_limit)
    ip = request.client.host if request.client else "unknown"
    allowed = await _rate_limit_store.allow(
        f"{operation}:{ip}", limit=limit, window_seconds=window_seconds
    )
    if not allowed:
        raise RateLimitError(
            "Demasiados intentos. Espere antes de intentar nuevamente.", code="rate_limited"
        )


async def rate_limit_login(request: Request) -> None:
    await _check(request, "login", settings.LOGIN_RATE_LIMIT)


async def rate_limit_refresh(request: Request) -> None:
    await _check(request, "refresh", settings.REFRESH_RATE_LIMIT)


async def rate_limit_reset(request: Request) -> None:
    await _check(request, "reset", settings.RESET_RATE_LIMIT)

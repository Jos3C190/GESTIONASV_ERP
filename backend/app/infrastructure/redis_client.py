from __future__ import annotations

from functools import lru_cache
from typing import cast

from redis.asyncio import Redis

from app.core.config import settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL is not configured")
    return cast(
        Redis,
        Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            health_check_interval=5,
        ),
    )


async def redis_health() -> bool:
    if not settings.REDIS_ENABLED or not settings.REDIS_URL:
        return False
    try:
        return bool(await get_redis_client().ping())
    except Exception:
        return False

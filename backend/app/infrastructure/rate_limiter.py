from __future__ import annotations

import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, cast

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.domain.ports.rate_limiter import RateLimitStore

log = get_logger(__name__)

SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
if redis.call('ZCARD', key) >= limit then
  return 0
end
redis.call('ZADD', key, now_ms, ARGV[4])
redis.call('PEXPIRE', key, window_ms)
return 1
"""


@dataclass
class _Window:
    hits: list[float] = field(default_factory=list)


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._buckets: dict[str, _Window] = defaultdict(_Window)

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        window = self._buckets[key]
        window.hits = [hit for hit in window.hits if hit > cutoff]
        if len(window.hits) >= limit:
            return False
        window.hits.append(now)
        return True

    async def health(self) -> bool:
        return True

    def clear(self) -> None:
        self._buckets.clear()


class RedisRateLimitStore:
    def __init__(self, client: Redis, namespace: str = "erp:ratelimit") -> None:
        self._client = client
        self._namespace = namespace

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now_ms = int(time.time() * 1000)
        evaluation = self._client.eval(
            SLIDING_WINDOW_SCRIPT,
            1,
            f"{self._namespace}:{key}",
            str(now_ms),
            str(window_seconds * 1000),
            str(limit),
            f"{now_ms}:{uuid.uuid4().hex}",
        )
        result = await cast(Awaitable[Any], evaluation)
        return bool(result)

    async def health(self) -> bool:
        return bool(await self._client.ping())


def parse_rate_limit(value: str) -> tuple[int, int]:
    try:
        count_text, unit = (part.strip().lower() for part in value.split("/", 1))
        count = int(count_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid rate limit: {value}") from exc
    units = {
        "second": 1,
        "seconds": 1,
        "minute": 60,
        "minutes": 60,
        "hour": 3600,
        "hours": 3600,
    }
    if count < 1 or unit not in units:
        raise ValueError(f"Invalid rate limit: {value}")
    return count, units[unit]


class FallbackRateLimitStore:
    def __init__(self, primary: RateLimitStore | None, fallback: InMemoryRateLimitStore) -> None:
        self._primary = primary
        self._fallback = fallback

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        if self._primary is not None:
            try:
                return await self._primary.allow(key, limit=limit, window_seconds=window_seconds)
            except Exception as exc:
                log.warning("redis_rate_limit_fallback", error=str(exc)[:200])
        return await self._fallback.allow(key, limit=limit, window_seconds=window_seconds)

    async def health(self) -> bool:
        if self._primary is None:
            return False
        try:
            return await self._primary.health()
        except Exception:
            return False

    def clear_fallback(self) -> None:
        self._fallback.clear()

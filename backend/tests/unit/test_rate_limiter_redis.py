from __future__ import annotations

import pytest
from app.infrastructure.rate_limiter import (
    FallbackRateLimitStore,
    InMemoryRateLimitStore,
    RedisRateLimitStore,
    parse_rate_limit,
)


class FakeRedis:
    def __init__(self, result: int = 1) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []

    async def eval(self, *args: object) -> int:
        self.calls.append(args)
        return self.result

    async def ping(self) -> bool:
        return True


class UnavailableStore:
    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        raise ConnectionError("redis unavailable")

    async def health(self) -> bool:
        raise ConnectionError("redis unavailable")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("10/minute", (10, 60)), ("30/minutes", (30, 60)), ("5/hour", (5, 3600))],
)
def test_parse_rate_limit(value: str, expected: tuple[int, int]) -> None:
    assert parse_rate_limit(value) == expected


@pytest.mark.parametrize("value", ["0/minute", "abc/minute", "10/day", "10"])
def test_rejects_invalid_rate_limit(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid rate limit"):
        parse_rate_limit(value)


@pytest.mark.asyncio
async def test_redis_store_uses_atomic_sliding_window_script() -> None:
    redis = FakeRedis(result=1)
    store = RedisRateLimitStore(redis)  # type: ignore[arg-type]

    assert await store.allow("login:127.0.0.1", limit=10, window_seconds=60)
    assert len(redis.calls) == 1
    call = redis.calls[0]
    assert call[1] == 1
    assert call[2] == "erp:ratelimit:login:127.0.0.1"
    assert call[4] == "60000"
    assert call[5] == "10"


@pytest.mark.asyncio
async def test_redis_outage_falls_back_to_process_memory() -> None:
    fallback = InMemoryRateLimitStore()
    store = FallbackRateLimitStore(UnavailableStore(), fallback)

    assert await store.allow("reset:127.0.0.1", limit=2, window_seconds=60)
    assert await store.allow("reset:127.0.0.1", limit=2, window_seconds=60)
    assert not await store.allow("reset:127.0.0.1", limit=2, window_seconds=60)
    assert not await store.health()

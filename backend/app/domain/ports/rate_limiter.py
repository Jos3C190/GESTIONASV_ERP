from __future__ import annotations

from typing import Protocol


class RateLimitStore(Protocol):
    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool: ...
    async def health(self) -> bool: ...

"""Port: RefreshTokenRepository (sessions)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.auth import RefreshToken


class RefreshTokenRepository(Protocol):
    async def add(self, token: RefreshToken) -> RefreshToken: ...

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def revoke(self, token_id: uuid.UUID) -> bool: ...

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int: ...

    async def list_active_for_user(self, user_id: uuid.UUID) -> Sequence[RefreshToken]: ...

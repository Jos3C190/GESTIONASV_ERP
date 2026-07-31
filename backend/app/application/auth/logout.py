"""Use case: Logout — revoke the presented refresh token."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.ports.refresh_token_repository import RefreshTokenRepository
from app.domain.ports.token_service import TokenService

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LogoutInput:
    raw_refresh_token: str


class LogoutUseCase:
    def __init__(self, sessions: RefreshTokenRepository, tokens: TokenService) -> None:
        self._sessions = sessions
        self._tokens = tokens

    async def execute(self, inp: LogoutInput) -> uuid.UUID | None:
        token_hash = self._tokens.hash_refresh_token(inp.raw_refresh_token)
        stored = await self._sessions.get_by_hash(token_hash)
        if stored is None:
            # Idempotent logout — don't leak whether the token existed.
            log.info("logout_noop_token_unknown")
            return None
        await self._sessions.revoke(stored.id)
        log.info("logout_success", user_id=str(stored.user_id))
        return stored.user_id

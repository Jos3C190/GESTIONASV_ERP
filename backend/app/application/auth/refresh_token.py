"""Use case: RefreshToken — rotate refresh tokens with reuse detection.

If a revoked/expired refresh token is presented, we treat it as a possible
theft signal and revoke ALL the user's sessions (defense per OWASP A07).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.domain.entities.auth import RefreshToken
from app.domain.ports.refresh_token_repository import RefreshTokenRepository
from app.domain.ports.token_service import TokenService
from app.domain.ports.user_repository import UserRepository

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RefreshInput:
    raw_refresh_token: str
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshResult:
    access_token: str
    refresh_token: str  # new raw token (rotated)
    expires_in_seconds: int
    user_id: uuid.UUID


class RefreshTokenUseCase:
    def __init__(
        self,
        users: UserRepository,
        sessions: RefreshTokenRepository,
        tokens: TokenService,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._tokens = tokens

    async def execute(self, inp: RefreshInput) -> RefreshResult:
        token_hash = self._tokens.hash_refresh_token(inp.raw_refresh_token)
        stored = await self._sessions.get_by_hash(token_hash)

        if stored is None:
            log.warning("refresh_token_unknown")
            raise AuthenticationError("Token inválido.", code="token_invalid")

        # Reuse / theft detection: a revoked or expired token presented again
        # means a possible stolen-token scenario. Revoke ALL user sessions.
        if stored.revoked_at is not None or stored.is_expired:
            log.warning(
                "refresh_token_reuse_detected",
                user_id=str(stored.user_id),
                token_id=str(stored.id),
            )
            count = await self._sessions.revoke_all_for_user(stored.user_id)
            log.warning("all_sessions_revoked", user_id=str(stored.user_id), count=count)
            raise AuthenticationError(
                "Sesión invalidada por seguridad. Inicie sesión nuevamente.",
                code="session_revoked",
            )

        user = await self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active or user.is_deleted:
            raise AuthenticationError("Usuario no válido.", code="user_invalid")

        # Rotate: revoke the presented token, issue a new one chained to it.
        await self._sessions.revoke(stored.id)

        access = self._tokens.issue_access_token(
            user_id=user.id, username=user.username, is_superuser=user.is_superuser
        )
        raw_new = self._tokens.generate_refresh_token()
        new_domain = RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=self._tokens.hash_refresh_token(raw_new),
            user_agent=inp.user_agent,
            ip_address=inp.ip_address,
            expires_at=datetime.now(UTC) + self._tokens.refresh_ttl,
            revoked_at=None,
            rotated_from=stored.id,
            created_at=datetime.now(UTC),
        )
        await self._sessions.add(new_domain)

        log.info("token_refreshed", user_id=str(user.id))
        return RefreshResult(
            access_token=access,
            refresh_token=raw_new,
            expires_in_seconds=int(self._tokens.access_ttl.total_seconds()),
            user_id=user.id,
        )

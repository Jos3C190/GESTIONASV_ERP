"""JWT TokenService — concrete implementation of the domain port.

Issues short-lived HS256 access tokens (JWT) and provides utilities to hash
and verify opaque refresh tokens. Refresh tokens are random 32-byte URLs-safe
strings; only their hash is stored (so a DB leak doesn't expose live sessions).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.domain.ports.token_service import AccessTokenPayload

log = get_logger(__name__)


class JwtTokenService:
    """PyJWT-backed implementation of TokenService."""

    def __init__(
        self,
        *,
        secret: str | None = None,
        algorithm: str | None = None,
        access_ttl_minutes: int | None = None,
        refresh_ttl_days: int | None = None,
    ) -> None:
        self._secret = secret or settings.JWT_SECRET_KEY
        self._algorithm = algorithm or settings.JWT_ALGORITHM
        self._access_ttl = timedelta(
            minutes=access_ttl_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        self._refresh_ttl = timedelta(days=refresh_ttl_days or settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # -------- access token --------
    def issue_access_token(self, *, user_id: uuid.UUID, username: str, is_superuser: bool) -> str:
        now = datetime.now(UTC)
        jti = secrets.token_urlsafe(12)
        payload = {
            "sub": str(user_id),
            "username": username,
            "is_superuser": is_superuser,
            "iat": int(now.timestamp()),
            "exp": int((now + self._access_ttl).timestamp()),
            "jti": jti,
            "type": "access",
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify_access_token(self, token: str) -> AccessTokenPayload:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Sesión expirada.", code="token_expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Token inválido.", code="token_invalid") from exc

        if payload.get("type") != "access":
            raise AuthenticationError("Tipo de token inválido.", code="token_type_invalid")

        try:
            return AccessTokenPayload(
                sub=uuid.UUID(str(payload["sub"])),
                username=str(payload["username"]),
                is_superuser=bool(payload["is_superuser"]),
                exp=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
                iat=datetime.fromtimestamp(int(payload["iat"]), tz=UTC),
                jti=str(payload["jti"]),
            )
        except (KeyError, ValueError) as exc:
            log.warning("token_payload_invalid", error=str(exc))
            raise AuthenticationError("Token malformado.", code="token_malformed") from exc

    # -------- refresh token --------
    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_refresh_token(self, raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_refresh_token_hash(self, raw: str, hashed: str) -> bool:
        computed = self.hash_refresh_token(raw)
        return hmac.compare_digest(computed, hashed)

    @property
    def refresh_ttl(self) -> timedelta:
        return self._refresh_ttl

    @property
    def access_ttl(self) -> timedelta:
        return self._access_ttl

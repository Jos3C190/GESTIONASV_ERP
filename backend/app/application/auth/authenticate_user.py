"""Use case: AuthenticateUser (login).

Implements progressive lockout (OWASP A07): each failed attempt increments
`failed_login_attempts`; after MAX_FAILED attempts the account is locked for
an increasing backoff window. Successful login resets counters.

Returns generic errors so the caller cannot distinguish "user not found"
from "wrong password" (anti-enumeration).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.security import needs_rehash, verify_password
from app.domain.entities.auth import RefreshToken
from app.domain.entities.user import User
from app.domain.ports.refresh_token_repository import RefreshTokenRepository
from app.domain.ports.token_service import TokenService
from app.domain.ports.user_repository import UserRepository

log = get_logger(__name__)

MAX_FAILED_ATTEMPTS = 5
BASE_LOCKOUT_MINUTES = 1
MAX_LOCKOUT_MINUTES = 30


@dataclass(frozen=True, slots=True)
class LoginInput:
    login: str  # email or username
    password: str
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    refresh_token: str  # raw, returned once to the caller
    refresh_token_id: uuid.UUID
    expires_in_seconds: int
    user_id: uuid.UUID
    username: str


class AuthenticateUserUseCase:
    def __init__(
        self,
        users: UserRepository,
        sessions: RefreshTokenRepository,
        tokens: TokenService,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._tokens = tokens

    async def execute(self, inp: LoginInput) -> LoginResult:
        user = await self._users.get_by_email_or_username(inp.login)

        # Generic message — never reveal whether the user exists.
        generic = AuthenticationError("Credenciales inválidas.", code="invalid_credentials")

        if user is None or user.is_deleted or not user.is_active:
            log.info("login_failed_user_not_found_or_inactive", login=inp.login[:64])
            raise generic

        if user.is_locked:
            log.info("login_failed_account_locked", user_id=str(user.id))
            raise AuthenticationError(
                "Cuenta bloqueada por intentos fallidos. Intente más tarde.",
                code="account_locked",
            )

        ok = verify_password(inp.password, user.password_hash)
        if not ok:
            await self._register_failed_attempt(user)
            raise generic

        # Success path: reset counters, update last_login.
        updated = user.__class__(  # rebuild with reset counters
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            mfa_enabled=user.mfa_enabled,
            last_login_at=datetime.now(UTC),
            failed_login_attempts=0,
            locked_until=None,
            password_changed_at=user.password_changed_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        )

        # Rehash if stored params are weaker than current policy (Argon2 feature).
        if needs_rehash(user.password_hash):
            from app.core.security import hash_password

            updated = updated.with_password_hash(hash_password(inp.password))
            log.info("password_rehashed_on_login", user_id=str(user.id))

        await self._users.update(updated)

        # Issue access + refresh tokens.
        access = self._tokens.issue_access_token(
            user_id=updated.id, username=updated.username, is_superuser=updated.is_superuser
        )
        raw_refresh = self._tokens.generate_refresh_token()
        refresh_domain = RefreshToken(
            id=uuid.uuid4(),
            user_id=updated.id,
            token_hash=self._tokens.hash_refresh_token(raw_refresh),
            user_agent=inp.user_agent,
            ip_address=inp.ip_address,
            expires_at=datetime.now(UTC) + self._tokens.refresh_ttl,
            revoked_at=None,
            rotated_from=None,
            created_at=datetime.now(UTC),
        )
        stored = await self._sessions.add(refresh_domain)

        log.info("login_success", user_id=str(updated.id))
        return LoginResult(
            access_token=access,
            refresh_token=raw_refresh,
            refresh_token_id=stored.id,
            expires_in_seconds=int(self._tokens.access_ttl.total_seconds()),
            user_id=updated.id,
            username=updated.username,
        )

    async def _register_failed_attempt(self, user: User) -> None:
        """Increment failed counter and lock if threshold reached."""
        attempts = getattr(user, "failed_login_attempts", 0) + 1
        locked_until = None
        if attempts >= MAX_FAILED_ATTEMPTS:
            # Exponential backoff capped at MAX_LOCKOUT_MINUTES.
            factor = min(2 ** (attempts - MAX_FAILED_ATTEMPTS), MAX_LOCKOUT_MINUTES)
            minutes = min(BASE_LOCKOUT_MINUTES * factor, MAX_LOCKOUT_MINUTES)
            locked_until = datetime.now(UTC) + timedelta(minutes=minutes)
            log.warning(
                "account_locked_after_failures",
                user_id=str(user.id),
                attempts=attempts,
                locked_minutes=minutes,
            )
        updated = User(
            id=user.id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            mfa_enabled=user.mfa_enabled,
            last_login_at=user.last_login_at,
            failed_login_attempts=attempts,
            locked_until=locked_until,
            password_changed_at=user.password_changed_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        )
        await self._users.update(updated)

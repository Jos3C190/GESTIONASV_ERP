"""In-memory fakes for ports, used by unit tests (no DB)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt
from app.core.config import settings
from app.domain.entities.auth import RefreshToken
from app.domain.entities.user import User
from app.domain.ports.token_service import AccessTokenPayload


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        u = self._by_id.get(user_id)
        return u if u and not u.is_deleted else None

    async def get_by_email(self, email: str) -> User | None:
        for u in self._by_id.values():
            if u.email.lower() == email.lower() and not u.is_deleted:
                return u
        return None

    async def get_by_username(self, username: str) -> User | None:
        for u in self._by_id.values():
            if u.username.lower() == username.lower() and not u.is_deleted:
                return u
        return None

    async def get_by_email_or_username(self, login: str) -> User | None:
        for u in self._by_id.values():
            if (
                u.email.lower() == login.lower() or u.username.lower() == login.lower()
            ) and not u.is_deleted:
                return u
        return None

    async def list_active(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        status_filter: str | None = None,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[Sequence[User], int]:
        items = [u for u in self._by_id.values() if not u.is_deleted]
        if search:
            s = search.lower()
            items = [u for u in items if s in u.username.lower() or s in u.email.lower()]
        now = datetime.now(UTC)
        if status_filter == "active":
            items = [
                u
                for u in items
                if u.is_active and (u.locked_until is None or u.locked_until <= now)
            ]
        elif status_filter == "inactive":
            items = [u for u in items if not u.is_active]
        elif status_filter == "superuser":
            items = [u for u in items if u.is_superuser]
        total = len(items)
        return items[offset : offset + limit], total

    async def count_active_superadmins(self) -> int:
        return sum(
            1 for u in self._by_id.values() if u.is_superuser and u.is_active and not u.is_deleted
        )

    async def add(self, user: User) -> User:
        # Use a fresh server-generated id
        new_id = uuid.uuid4()
        now = datetime.now(UTC)
        created = User(
            id=new_id,
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            mfa_enabled=user.mfa_enabled,
            last_login_at=user.last_login_at,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            password_changed_at=user.password_changed_at or now,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self._by_id[new_id] = created
        return created

    async def update(self, user: User) -> User:
        if user.id not in self._by_id:
            raise LookupError(f"User {user.id} not found")
        self._by_id[user.id] = user
        return user

    async def soft_delete(self, user_id: uuid.UUID) -> bool:
        u = self._by_id.get(user_id)
        if u is None or u.is_deleted:
            return False
        self._by_id[user_id] = User(
            id=u.id,
            username=u.username,
            email=u.email,
            password_hash=u.password_hash,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            mfa_enabled=u.mfa_enabled,
            last_login_at=u.last_login_at,
            failed_login_attempts=u.failed_login_attempts,
            locked_until=u.locked_until,
            password_changed_at=u.password_changed_at,
            created_at=u.created_at,
            updated_at=u.updated_at,
            deleted_at=datetime.now(UTC),
        )
        return True


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, RefreshToken] = {}

    async def add(self, token: RefreshToken) -> RefreshToken:
        now = datetime.now(UTC)
        stored = RefreshToken(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            user_agent=token.user_agent,
            ip_address=token.ip_address,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
            rotated_from=token.rotated_from,
            created_at=token.created_at or now,
        )
        self._by_id[token.id] = stored
        return stored

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for t in self._by_id.values():
            if t.token_hash == token_hash:
                return t
        return None

    async def revoke(self, token_id: uuid.UUID) -> bool:
        t = self._by_id.get(token_id)
        if t is None or t.revoked_at is not None:
            return False
        self._by_id[token_id] = RefreshToken(
            id=t.id,
            user_id=t.user_id,
            token_hash=t.token_hash,
            user_agent=t.user_agent,
            ip_address=t.ip_address,
            expires_at=t.expires_at,
            revoked_at=datetime.now(UTC),
            rotated_from=t.rotated_from,
            created_at=t.created_at,
        )
        return True

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        count = 0
        for tid, t in list(self._by_id.items()):
            if t.user_id == user_id and t.revoked_at is None:
                await self.revoke(tid)
                count += 1
        return count

    async def list_active_for_user(self, user_id: uuid.UUID) -> Sequence[RefreshToken]:
        return [t for t in self._by_id.values() if t.user_id == user_id and t.revoked_at is None]


class FakeTokenService:
    """In-memory token service with real JWT for access + SHA256 for refresh."""

    def __init__(
        self,
        *,
        secret: str | None = None,
        access_ttl_minutes: int = 15,
        refresh_ttl_days: int = 7,
    ) -> None:
        self._secret = secret or settings.JWT_SECRET_KEY
        self._access_ttl = timedelta(minutes=access_ttl_minutes)
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    def issue_access_token(self, *, user_id: uuid.UUID, username: str, is_superuser: bool) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "username": username,
            "is_superuser": is_superuser,
            "iat": int(now.timestamp()),
            "exp": int((now + self._access_ttl).timestamp()),
            "jti": secrets.token_urlsafe(12),
            "type": "access",
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify_access_token(self, token: str) -> AccessTokenPayload:
        payload = jwt.decode(token, self._secret, algorithms=["HS256"])
        return AccessTokenPayload(
            sub=uuid.UUID(str(payload["sub"])),
            username=str(payload["username"]),
            is_superuser=bool(payload["is_superuser"]),
            exp=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
            iat=datetime.fromtimestamp(int(payload["iat"]), tz=UTC),
            jti=str(payload["jti"]),
        )

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_refresh_token(self, raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_refresh_token_hash(self, raw: str, hashed: str) -> bool:
        return hmac.compare_digest(self.hash_refresh_token(raw), hashed)

    @property
    def refresh_ttl(self) -> timedelta:
        return self._refresh_ttl

    @property
    def access_ttl(self) -> timedelta:
        return self._access_ttl

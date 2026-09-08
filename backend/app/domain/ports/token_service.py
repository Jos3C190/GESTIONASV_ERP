"""Port: TokenService — JWT issuance/verification and token hashing.

Abstracts the cryptographic details so the application layer stays testable
without touching PyJWT or hashing directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AccessTokenPayload:
    sub: uuid.UUID  # user id
    username: str
    is_superuser: bool
    exp: datetime
    iat: datetime
    jti: str


class TokenService(Protocol):
    """Issues and verifies short-lived access tokens (JWT)."""

    @property
    def refresh_ttl(self) -> timedelta: ...

    @property
    def access_ttl(self) -> timedelta: ...

    def issue_access_token(
        self, *, user_id: uuid.UUID, username: str, is_superuser: bool
    ) -> str: ...

    def verify_access_token(self, token: str) -> AccessTokenPayload: ...

    def hash_refresh_token(self, raw: str) -> str:
        """One-way hash for storage. Raw token never persisted."""

    def generate_refresh_token(self) -> str:
        """Generate a cryptographically random refresh token (raw)."""

    def verify_refresh_token_hash(self, raw: str, hashed: str) -> bool: ...

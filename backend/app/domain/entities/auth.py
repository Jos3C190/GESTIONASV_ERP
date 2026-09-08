"""Domain entity: RefreshToken (session)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class RefreshToken:
    id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    user_agent: str | None
    ip_address: str | None
    expires_at: datetime
    revoked_at: datetime | None = None
    rotated_from: uuid.UUID | None = None
    created_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at > datetime.now(UTC)

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= datetime.now(UTC)

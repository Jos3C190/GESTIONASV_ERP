"""Domain entity: User.

Pure Python, no framework deps. The ORM model lives in infrastructure; this
entity is what use cases operate on. Repositories convert between the two.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class User:
    """Domain User entity (immutable). Use cases return new instances on change."""

    id: uuid.UUID
    username: str
    email: str
    password_hash: str
    is_active: bool = True
    is_superuser: bool = False
    mfa_enabled: bool = False
    last_login_at: datetime | None = None
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    password_changed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return self.locked_until > datetime.now(UTC)

    @property
    def status(self) -> UserStatus:
        if self.is_deleted:
            return UserStatus.DELETED
        if not self.is_active:
            return UserStatus.INACTIVE
        if self.is_locked:
            return UserStatus.LOCKED
        return UserStatus.ACTIVE

    def with_password_hash(self, new_hash: str) -> User:
        """Return a copy with an updated password hash (for rehash on verify)."""
        return User(
            id=self.id,
            username=self.username,
            email=self.email,
            password_hash=new_hash,
            is_active=self.is_active,
            is_superuser=self.is_superuser,
            mfa_enabled=self.mfa_enabled,
            last_login_at=self.last_login_at,
            failed_login_attempts=self.failed_login_attempts,
            locked_until=self.locked_until,
            password_changed_at=datetime.now(UTC),
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

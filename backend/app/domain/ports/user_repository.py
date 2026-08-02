"""Port: UserRepository.

The contract the application layer depends on for user persistence. Concrete
implementations live in infrastructure.repositories. Use cases never import
the concrete implementation — only this Protocol.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.user import User


class UserRepository(Protocol):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_username(self, username: str) -> User | None: ...

    async def get_by_email_or_username(self, login: str) -> User | None: ...

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
        """Return (users, total_count)."""

    async def count_active_superadmins(self) -> int:
        """Count non-deleted users with is_superuser=True and is_active=True."""

    async def add(self, user: User) -> User: ...

    async def update(self, user: User) -> User: ...

    async def soft_delete(self, user_id: uuid.UUID) -> bool: ...

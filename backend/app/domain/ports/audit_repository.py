"""Port: AuditRepository — append-only (add + list, no update/delete)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.domain.entities.audit import AuditLog


class AuditRepository(Protocol):
    """Append-only repository. Only add and list are exposed — never update
    or delete. This is the architectural enforcement of the append-only rule,
    complementing the lack of UPDATE/DELETE endpoints."""

    async def add(self, log: AuditLog) -> AuditLog: ...

    async def get_by_id(self, log_id: uuid.UUID) -> AuditLog | None: ...

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[Sequence[AuditLog], bool]:
        """Return (logs, has_more). Paginated by offset/limit."""

    async def count(
        self,
        *,
        user_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int: ...

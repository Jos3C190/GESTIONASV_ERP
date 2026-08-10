"""Port for auditable soft-delete and restore operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DeletedRecord:
    resource: str
    record_id: str
    label: str
    company_id: uuid.UUID | None
    deleted_at: datetime | None
    deleted_by: uuid.UUID | None
    deletion_reason: str | None
    operation_applied: bool = True


class LifecycleRepository(Protocol):
    async def list_deleted(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        resource: str | None = None,
        search: str | None = None,
        include_global: bool = False,
        include_all_companies: bool = False,
    ) -> tuple[list[DeletedRecord], int]: ...

    async def soft_delete(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        allow_global: bool = False,
    ) -> DeletedRecord: ...

    async def restore(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        allow_global: bool = False,
    ) -> DeletedRecord: ...

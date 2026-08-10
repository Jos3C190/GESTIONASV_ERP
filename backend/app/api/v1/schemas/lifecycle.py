"""DTOs for soft-delete, trash and restore operations."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.api.v1.schemas.common import PageMeta


class SoftDeleteRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DeletedRecordOut(BaseModel):
    resource: str
    record_id: str
    label: str
    company_id: uuid.UUID | None
    deleted_at: datetime | None
    deleted_by: uuid.UUID | None
    deletion_reason: str | None
    operation_applied: bool = True


class DeletedRecordsPage(BaseModel):
    items: list[DeletedRecordOut]
    meta: PageMeta

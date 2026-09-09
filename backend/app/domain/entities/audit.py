"""Domain entity: AuditLog (immutable, append-only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditLog:
    id: uuid.UUID
    action: str
    user_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    before_state: dict[str, object] | None = None
    after_state: dict[str, object] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    status: str = "success"
    metadata: dict[str, object] | None = None
    created_at: datetime | None = None

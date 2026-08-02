"""Audit log DTOs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.api.v1.schemas.common import ORMOut, PageMeta


class AuditLogOut(ORMOut):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    status: str
    metadata: dict[str, Any] | None = None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    meta: PageMeta

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DocumentDerivative:
    id: uuid.UUID
    company_id: uuid.UUID
    document_id: uuid.UUID
    kind: str
    status: str
    bucket: str
    object_key: str
    content_type: str = "application/pdf"
    size_bytes: int | None = None
    checksum_sha256: str | None = None
    etag: str | None = None
    attempts: int = 0
    failure_code: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    object_deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

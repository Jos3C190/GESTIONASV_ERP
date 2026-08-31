from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DocumentAsset:
    id: uuid.UUID
    company_id: uuid.UUID
    original_filename: str
    extension: str
    declared_content_type: str
    size_bytes: int
    checksum_sha256: str
    bucket: str
    object_key: str
    status: str = "pending_upload"
    detected_content_type: str | None = None
    etag: str | None = None
    failure_code: str | None = None
    malware_name: str | None = None
    upload_expires_at: datetime | None = None
    scan_started_at: datetime | None = None
    scanned_at: datetime | None = None
    object_deleted_at: datetime | None = None
    uploaded_by: uuid.UUID | None = None
    deleted_at: datetime | None = None
    deleted_by: uuid.UUID | None = None
    deletion_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    ocr_status: str | None = None
    ocr_available: bool = False
    ocr_failure_code: str | None = None
    ocr_completed_at: datetime | None = None

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.common import PageMeta

DocumentStatus = Literal[
    "pending_upload", "pending_scan", "scanning", "active", "quarantined", "rejected"
]
OcrStatus = Literal["pending", "processing", "ready", "failed", "skipped"]
DownloadVariant = Literal["original", "ocr"]


class InitiateDocumentIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        return value.strip().lower()


class DocumentOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    original_filename: str
    extension: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    status: DocumentStatus
    failure_code: str | None
    upload_expires_at: datetime | None
    scanned_at: datetime | None
    uploaded_by: uuid.UUID | None
    created_at: datetime | None
    updated_at: datetime | None
    ocr_status: OcrStatus | None = None
    ocr_available: bool = False
    ocr_failure_code: str | None = None
    ocr_completed_at: datetime | None = None


class InitiateDocumentOut(BaseModel):
    document_id: uuid.UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


class DocumentsPage(BaseModel):
    items: list[DocumentOut]
    meta: PageMeta


class DownloadUrlOut(BaseModel):
    url: str
    expires_at: datetime

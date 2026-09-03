from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.common import PageMeta


def _normalize_category_text(value: Any) -> Any:
    """Normalize human-entered category labels before length validation.

    Pydantic's ``min_length`` constraint runs against the raw value.  Without
    this pre-validator a value containing only spaces would pass the API
    schema and be persisted as an unusable blank label after the router's
    ``strip()`` call.
    """
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return value


DocumentStatus = Literal[
    "pending_upload", "pending_scan", "scanning", "active", "quarantined", "rejected"
]
RecordStatus = Literal[
    "processing",
    "active",
    "current",
    "expiring",
    "expired",
    "replaced",
    "quarantined",
    "rejected",
    "deleted",
]
OcrStatus = Literal["pending", "processing", "ready", "failed", "skipped"]
DownloadVariant = Literal["original", "ocr"]
DocumentFolderParent = Literal["root", "general", "employees", "employee"]
DocumentFolderKind = Literal["module", "employee", "category"]


class InitiateDocumentIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        return value.strip().lower()


class DocumentMetadataIn(BaseModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    reference_code: str | None = Field(default=None, max_length=120)
    issuer: str | None = Field(default=None, max_length=180)
    issued_on: date | None = None
    expires_on: date | None = None
    confidentiality: Literal["internal", "restricted"] = "restricted"
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value]


class InitiateRecordIn(InitiateDocumentIn, DocumentMetadataIn):
    """Technical upload declaration plus business metadata."""


class UpdateDocumentMetadataIn(DocumentMetadataIn):
    pass


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
    # Business projection fields are optional so existing clients that only
    # consume the technical document contract remain fully compatible.
    module: Literal["general", "employees"] | None = None
    owner_type: str | None = None
    owner_id: uuid.UUID | None = None
    owner_label: str | None = None
    owner_deleted: bool = False
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    category_group: str | None = None
    title: str | None = None
    description: str | None = None
    reference_code: str | None = None
    issuer: str | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    confidentiality: Literal["internal", "restricted"] | None = None
    tags: list[str] = Field(default_factory=list)
    business_status: RecordStatus | None = None
    version_group_id: uuid.UUID | None = None
    version_number: int | None = None
    is_current: bool | None = None
    replaces_document_id: uuid.UUID | None = None


class InitiateDocumentOut(BaseModel):
    document_id: uuid.UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


class DocumentCategoryOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    module: str
    code: str
    name: str
    group_name: str
    description: str | None
    sort_order: int
    is_active: bool
    document_count: int = 0


class CreateDocumentCategoryIn(BaseModel):
    module: Literal["general", "employees"]
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    group_name: str = Field(default="General", min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=10000)

    _normalize_labels = field_validator("name", "group_name", mode="before")(
        _normalize_category_text
    )
    _normalize_description = field_validator("description", mode="before")(_normalize_category_text)


class UpdateDocumentCategoryIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    group_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None

    _normalize_labels = field_validator("name", "group_name", mode="before")(
        _normalize_category_text
    )
    _normalize_description = field_validator("description", mode="before")(_normalize_category_text)


class DocumentRecordOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    module: str
    owner_type: str | None
    owner_id: uuid.UUID | None
    owner_label: str | None
    owner_deleted: bool
    category_id: uuid.UUID
    category_name: str | None
    category_group: str | None
    title: str
    description: str | None
    reference_code: str | None
    issuer: str | None
    issued_on: date | None
    expires_on: date | None
    confidentiality: Literal["internal", "restricted"]
    tags: list[str]
    version_group_id: uuid.UUID
    version_number: int
    is_current: bool
    replaces_document_id: uuid.UUID | None
    business_status: RecordStatus
    original_filename: str
    extension: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    technical_status: DocumentStatus
    failure_code: str | None
    upload_expires_at: datetime | None
    scanned_at: datetime | None
    uploaded_by: uuid.UUID | None
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime | None
    updated_at: datetime | None
    ocr_status: OcrStatus | None = None
    ocr_available: bool = False
    ocr_failure_code: str | None = None
    ocr_completed_at: datetime | None = None


class DocumentRecordsPage(BaseModel):
    items: list[DocumentRecordOut]
    meta: PageMeta


class DocumentBreadcrumbOut(BaseModel):
    label: str
    href: str


class DocumentFolderOut(BaseModel):
    """Safe projection of a virtual document-library folder."""

    id: str
    kind: DocumentFolderKind
    name: str
    module: Literal["general", "employees"]
    parent_id: str | None
    employee_id: str | None = None
    category_id: str | None = None
    employee_code: str | None = None
    employee_status: str | None = None
    document_count: int = 0
    active_count: int = 0
    expiring_count: int = 0
    expired_count: int = 0
    latest_document_at: datetime | None = None
    can_upload: bool = False


class DocumentFoldersPage(BaseModel):
    items: list[DocumentFolderOut]
    meta: PageMeta
    breadcrumbs: list[DocumentBreadcrumbOut]


class DocumentsPage(BaseModel):
    items: list[DocumentOut]
    meta: PageMeta


class DownloadUrlOut(BaseModel):
    url: str
    expires_at: datetime

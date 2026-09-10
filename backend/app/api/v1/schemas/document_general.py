from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.documents import DocumentMetadataIn, InitiateDocumentOut


def _clean_name(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return value


class GeneralFolderCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None

    _normalize_name = field_validator("name", mode="before")(_clean_name)


class GeneralFolderRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    _normalize_name = field_validator("name", mode="before")(_clean_name)


class GeneralEntryMoveIn(BaseModel):
    parent_id: uuid.UUID | None = None


class GeneralBatchMoveItemIn(BaseModel):
    entry_id: uuid.UUID
    kind: Literal["folder", "file"]


class GeneralBatchMoveIn(BaseModel):
    parent_id: uuid.UUID | None = None
    items: list[GeneralBatchMoveItemIn] = Field(min_length=1, max_length=200)


class GeneralEntryOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    kind: Literal["folder", "file"]
    name: str
    parent_id: uuid.UUID | None
    document_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    title: str | None = None
    original_filename: str | None = None
    extension: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    technical_status: str | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    business_status: str | None = None
    version_number: int | None = None
    is_current: bool | None = None


class GeneralContentsPage(BaseModel):
    items: list[GeneralEntryOut]
    meta: PageMeta
    breadcrumbs: list[GeneralBreadcrumbOut] = Field(default_factory=list)


class GeneralBreadcrumbOut(BaseModel):
    id: uuid.UUID | None
    label: str
    href: str


class GeneralDeletionOut(BaseModel):
    batch_id: uuid.UUID


class GeneralDeletionBatchOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    root_folder_id: uuid.UUID
    label: str
    entry_count: int
    created_at: datetime
    actor_id: uuid.UUID | None


class GeneralDeletionBatchPage(BaseModel):
    items: list[GeneralDeletionBatchOut]
    meta: PageMeta


class GeneralFolderTreeOut(BaseModel):
    items: list[GeneralEntryOut]



class GeneralImportManifestItemIn(BaseModel):
    kind: Literal["folder", "file"]
    relative_path: str = Field(min_length=1, max_length=2000)
    size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = Field(default=None, max_length=160)


class GeneralImportPrepareIn(BaseModel):
    parent_id: uuid.UUID | None = None
    metadata: DocumentMetadataIn = Field(default_factory=DocumentMetadataIn)
    items: list[GeneralImportManifestItemIn] = Field(min_length=1, max_length=1000)


GeneralImportItemStatus = Literal[
    "ready", "authorized", "completed", "skipped", "failed_retryable",
    "failed_permanent", "cancelled"
]


class GeneralImportItemOut(BaseModel):
    id: uuid.UUID
    kind: Literal["folder", "file"]
    source_path: str
    source_name: str
    resolved_path: str
    resolved_name: str
    parent_folder_id: uuid.UUID | None
    entry_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    size_bytes: int | None = None
    content_type: str | None = None
    extension: str | None = None
    status: GeneralImportItemStatus
    failure_code: str | None = None
    failure_message: str | None = None
    attempts: int


class GeneralImportOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    root_entry_id: uuid.UUID | None
    status: Literal["preparing", "ready", "running", "completed", "partial", "cancelled", "expired"]
    total_files: int
    total_folders: int
    total_entries: int
    total_bytes: int
    completed_files: int
    skipped_files: int
    failed_files: int
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    items: list[GeneralImportItemOut] = Field(default_factory=list)
    meta: PageMeta | None = None


class GeneralImportTicketIn(BaseModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class GeneralImportTicketOut(BaseModel):
    item: GeneralImportItemOut
    ticket: InitiateDocumentOut

__all__ = [
    "GeneralBatchMoveIn",
    "GeneralBatchMoveItemIn",
    "GeneralContentsPage",
    "GeneralDeletionBatchOut",
    "GeneralDeletionBatchPage",
    "GeneralDeletionOut",
    "GeneralEntryMoveIn",
    "GeneralEntryOut",
    "GeneralFolderCreateIn",
    "GeneralFolderRenameIn",
    "GeneralFolderTreeOut",
    "GeneralImportItemOut",
    "GeneralImportManifestItemIn",
    "GeneralImportOut",
    "GeneralImportPrepareIn",
    "GeneralImportTicketIn",
    "GeneralImportTicketOut",
]

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.common import PageMeta


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


__all__ = [
    "GeneralContentsPage",
    "GeneralDeletionBatchOut",
    "GeneralDeletionBatchPage",
    "GeneralDeletionOut",
    "GeneralEntryMoveIn",
    "GeneralEntryOut",
    "GeneralFolderCreateIn",
    "GeneralFolderRenameIn",
    "GeneralFolderTreeOut",
]

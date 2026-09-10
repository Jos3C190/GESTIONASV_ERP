"""Domain entities for recursive imports in the General document workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

GeneralImportStatus = Literal[
    "preparing", "ready", "running", "completed", "partial", "cancelled", "expired"
]
GeneralImportItemKind = Literal["folder", "file"]
GeneralImportItemStatus = Literal[
    "ready",
    "authorized",
    "completed",
    "skipped",
    "failed_retryable",
    "failed_permanent",
    "cancelled",
]


@dataclass(slots=True)
class DocumentGeneralImport:
    id: uuid.UUID
    company_id: uuid.UUID
    actor_id: uuid.UUID
    parent_id: uuid.UUID | None
    root_entry_id: uuid.UUID | None
    status: GeneralImportStatus
    total_files: int
    total_folders: int
    total_entries: int
    total_bytes: int
    metadata: dict[str, object] = field(default_factory=dict)
    completed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(slots=True)
class DocumentGeneralImportItem:
    id: uuid.UUID
    import_id: uuid.UUID
    kind: GeneralImportItemKind
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
    status: GeneralImportItemStatus = "ready"
    failure_code: str | None = None
    failure_message: str | None = None
    attempts: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "DocumentGeneralImport",
    "DocumentGeneralImportItem",
    "GeneralImportItemKind",
    "GeneralImportItemStatus",
    "GeneralImportStatus",
]

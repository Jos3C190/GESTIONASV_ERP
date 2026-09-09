"""Mutable entries for the general document workspace."""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

GeneralEntryKind = Literal["folder", "file"]
MAX_GENERAL_ENTRY_NAME = 200
MIN_PRINTABLE_CODEPOINT = 32


def normalize_general_entry_name(value: str) -> str:
    """Return the comparison key used for sibling uniqueness.

    NFKC folds compatibility characters, whitespace is collapsed and casefold
    makes the comparison independent of case.  The display name is kept
    separately so renaming never changes a document asset's original name.
    """
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def clean_general_entry_name(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if any(ord(char) < MIN_PRINTABLE_CODEPOINT for char in normalized):
        raise ValueError("El nombre no es válido.")
    cleaned = " ".join(normalized.strip().split())
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("El nombre no puede estar vacío.")
    if len(cleaned) > MAX_GENERAL_ENTRY_NAME:
        raise ValueError("El nombre no es válido.")
    if any(separator in cleaned for separator in ("/", "\\")):
        raise ValueError("El nombre no puede contener separadores de ruta.")
    return cleaned


@dataclass(frozen=True, slots=True)
class GeneralDeletionBatch:
    id: uuid.UUID
    company_id: uuid.UUID
    root_folder_id: uuid.UUID
    label: str
    entry_count: int
    created_at: datetime
    actor_id: uuid.UUID | None


@dataclass(slots=True)
class DocumentGeneralEntry:
    id: uuid.UUID
    company_id: uuid.UUID
    parent_id: uuid.UUID | None
    kind: GeneralEntryKind
    document_id: uuid.UUID | None
    name: str
    normalized_name: str
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    deletion_batch_id: uuid.UUID | None = None
    document_title: str | None = None
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

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


__all__ = [
    "DocumentGeneralEntry",
    "GeneralDeletionBatch",
    "GeneralEntryKind",
    "clean_general_entry_name",
    "normalize_general_entry_name",
]

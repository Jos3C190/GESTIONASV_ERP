from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.domain.entities.document_general_entry import DocumentGeneralEntry, GeneralDeletionBatch


class DocumentGeneralRepository(Protocol):
    async def add(self, entry: DocumentGeneralEntry) -> DocumentGeneralEntry: ...

    async def get(
        self, company_id: uuid.UUID, entry_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentGeneralEntry | None: ...

    async def get_by_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentGeneralEntry | None: ...

    async def save(self, entry: DocumentGeneralEntry) -> DocumentGeneralEntry: ...

    async def sibling_exists(
        self,
        company_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        normalized_name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool: ...

    async def list_contents(
        self,
        company_id: uuid.UUID,
        *,
        parent_id: uuid.UUID | None,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        status: str | None = None,
        sort: str = "name",
        descending: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> tuple[Sequence[DocumentGeneralEntry], int]: ...

    async def list_tree(
        self, company_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Sequence[DocumentGeneralEntry]: ...

    async def list_deletion_batches(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[Sequence[GeneralDeletionBatch], int]: ...

    async def descendants(
        self, company_id: uuid.UUID, entry_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Sequence[DocumentGeneralEntry]: ...

    async def create_deletion_batch(
        self, company_id: uuid.UUID, actor_id: uuid.UUID
    ) -> uuid.UUID: ...

    async def soft_delete_batch(
        self,
        company_id: uuid.UUID,
        entry_ids: Sequence[uuid.UUID],
        batch_id: uuid.UUID,
        actor_id: uuid.UUID,
        deleted_at: datetime,
    ) -> None: ...

    async def restore_batch(
        self, company_id: uuid.UUID, batch_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None: ...

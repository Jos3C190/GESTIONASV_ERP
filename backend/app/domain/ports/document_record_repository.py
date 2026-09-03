from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.document_folder import DocumentFolder
from app.domain.entities.document_record import DocumentCategory, DocumentRecord


class DocumentRecordRepository(Protocol):
    async def add(self, record: DocumentRecord) -> DocumentRecord: ...

    async def get(
        self, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentRecord | None: ...

    async def save(self, record: DocumentRecord) -> DocumentRecord: ...

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        module: str | None = None,
        owner_type: str | None = None,
        owner_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        search: str | None = None,
        include_versions: bool = False,
        include_deleted: bool = False,
        document_status: str | None = None,
        storage_status: str | None = None,
        confidentiality: str | None = None,
        expires_within_days: int | None = None,
        include_restricted: bool = True,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[Sequence[DocumentRecord], int]: ...

    async def list_folders(
        self,
        company_id: uuid.UUID,
        *,
        parent: str,
        employee_id: uuid.UUID | None = None,
        page: int,
        size: int,
        search: str | None = None,
        branch_id: uuid.UUID | None = None,
        include_restricted: bool = True,
        allowed_modules: set[str] | None = None,
        upload_modules: set[str] | None = None,
    ) -> tuple[Sequence[DocumentFolder], int]: ...

    async def list_versions(self, document_id: uuid.UUID) -> Sequence[DocumentRecord]: ...

    async def next_version_number(self, version_group_id: uuid.UUID) -> int: ...

    async def set_current_version(
        self,
        *,
        version_group_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> DocumentRecord | None: ...

    async def categories(
        self, company_id: uuid.UUID, *, module: str | None = None, include_inactive: bool = False
    ) -> Sequence[DocumentCategory]: ...

    async def get_category(
        self, category_id: uuid.UUID, company_id: uuid.UUID, *, include_inactive: bool = False
    ) -> DocumentCategory | None: ...

    async def add_category(self, category: DocumentCategory) -> DocumentCategory: ...

    async def save_category(self, category: DocumentCategory) -> DocumentCategory: ...

    async def count_category_documents(
        self,
        category_id: uuid.UUID,
        *,
        include_restricted: bool = True,
        branch_id: uuid.UUID | None = None,
    ) -> int: ...

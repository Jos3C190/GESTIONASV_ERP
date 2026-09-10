from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.document_general_import import (
    DocumentGeneralImport,
    DocumentGeneralImportItem,
)


class DocumentGeneralImportRepository(Protocol):
    async def add_import(self, item: DocumentGeneralImport) -> DocumentGeneralImport: ...
    async def save_import(self, item: DocumentGeneralImport) -> DocumentGeneralImport: ...
    async def get_import(
        self, company_id: uuid.UUID, import_id: uuid.UUID
    ) -> DocumentGeneralImport | None: ...
    async def add_item(self, item: DocumentGeneralImportItem) -> DocumentGeneralImportItem: ...
    async def save_item(self, item: DocumentGeneralImportItem) -> DocumentGeneralImportItem: ...
    async def get_item(
        self, company_id: uuid.UUID, import_id: uuid.UUID, item_id: uuid.UUID
    ) -> DocumentGeneralImportItem | None: ...
    async def list_items(
        self, company_id: uuid.UUID, import_id: uuid.UUID, *, page: int, size: int
    ) -> Sequence[DocumentGeneralImportItem]: ...
    async def count_items(self, company_id: uuid.UUID, import_id: uuid.UUID) -> int: ...

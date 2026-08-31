from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.domain.entities.document import DocumentAsset


class DocumentRepository(Protocol):
    async def add(self, document: DocumentAsset) -> DocumentAsset: ...
    async def get(
        self, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentAsset | None: ...
    async def save(self, document: DocumentAsset) -> DocumentAsset: ...
    async def list(
        self, company_id: uuid.UUID, *, page: int, size: int, search: str | None, status: str | None
    ) -> tuple[Sequence[DocumentAsset], int]: ...
    async def count_pending(self, user_id: uuid.UUID) -> int: ...
    async def claim_for_scan(
        self, document_id: uuid.UUID, now: datetime
    ) -> DocumentAsset | None: ...

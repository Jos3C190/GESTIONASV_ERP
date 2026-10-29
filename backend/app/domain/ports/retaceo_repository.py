"""Persistence port for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities.retaceo import Retaceo, RetaceoCostDocument, RetaceoStatus


@dataclass(frozen=True, slots=True)
class RetaceoCostReference:
    retaceo_id: uuid.UUID
    cost_id: uuid.UUID
    status: RetaceoStatus
    is_active: bool


@dataclass(frozen=True, slots=True)
class RetaceoCostDocumentReference:
    retaceo_id: uuid.UUID
    cost_id: uuid.UUID
    status: RetaceoStatus
    document: RetaceoCostDocument


class RetaceoRepository(Protocol):
    async def list_retaceos(
        self,
        company_id: uuid.UUID,
        *,
        status: RetaceoStatus | None = None,
        purchase_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Retaceo], int]: ...

    async def get_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None: ...

    async def get_retaceo_for_update(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None: ...

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def add_retaceo(self, retaceo: Retaceo) -> Retaceo: ...

    async def replace_draft(self, retaceo: Retaceo) -> Retaceo | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        status: RetaceoStatus,
    ) -> Retaceo | None: ...

    async def get_cost_reference(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> RetaceoCostReference | None: ...

    async def add_cost_document(
        self,
        attachment: RetaceoCostDocument,
        company_id: uuid.UUID,
    ) -> RetaceoCostDocument: ...

    async def get_cost_document(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> RetaceoCostDocumentReference | None: ...

    async def list_cost_documents(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> tuple[RetaceoCostDocument, ...]: ...

    async def mark_cost_document_uploaded(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        file_type: str,
        uploaded_at: datetime,
    ) -> RetaceoCostDocument | None: ...

    async def soft_delete_cost_document(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        deleted_at: datetime,
    ) -> RetaceoCostDocument | None: ...

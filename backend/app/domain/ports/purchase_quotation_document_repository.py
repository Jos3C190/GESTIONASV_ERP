"""Persistence port for original supplier documents attached to quotations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.entities.purchase_quotation_document import PurchaseQuotationDocument


@dataclass(frozen=True, slots=True)
class PurchaseQuotationDocumentReference:
    quotation_id: uuid.UUID
    status: PurchaseQuotationStatus


class PurchaseQuotationDocumentRepository(Protocol):
    async def get_quotation_reference(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> PurchaseQuotationDocumentReference | None: ...

    async def add_document(
        self, attachment: PurchaseQuotationDocument
    ) -> PurchaseQuotationDocument: ...

    async def get_document(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseQuotationDocument | None: ...

    async def list_documents(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> Sequence[PurchaseQuotationDocument]: ...

    async def mark_uploaded(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        file_type: str,
        uploaded_at: datetime,
    ) -> PurchaseQuotationDocument | None: ...

    async def detach_document(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        deleted_at: datetime,
    ) -> PurchaseQuotationDocument | None: ...

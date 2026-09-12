"""Persistence port for purchase-order expense document associations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.entities.purchase_order import PurchaseOrderStatus
from app.domain.entities.purchase_order_expense_document import PurchaseOrderExpenseDocument


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseReference:
    order_id: uuid.UUID
    expense_id: uuid.UUID
    status: PurchaseOrderStatus


class PurchaseOrderExpenseDocumentRepository(Protocol):
    async def get_expense_reference(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> PurchaseOrderExpenseReference | None: ...

    async def add_document(
        self,
        attachment: PurchaseOrderExpenseDocument,
    ) -> PurchaseOrderExpenseDocument: ...

    async def get_document(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseOrderExpenseDocument | None: ...

    async def list_documents(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> Sequence[PurchaseOrderExpenseDocument]: ...

    async def mark_uploaded(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        file_type: str,
        uploaded_at: datetime,
    ) -> PurchaseOrderExpenseDocument | None: ...

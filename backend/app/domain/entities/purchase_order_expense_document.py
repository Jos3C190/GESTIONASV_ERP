"""Domain entity for documents attached to purchase-order expenses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

FILE_NAME_MAX_LENGTH = 255
FILE_TYPE_MAX_LENGTH = 160


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseDocument:
    id: uuid.UUID
    company_id: uuid.UUID
    purchase_order_expense_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    file_type: str
    uploaded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.file_name.strip() or len(self.file_name) > FILE_NAME_MAX_LENGTH:
            raise ValueError("El nombre del documento no es válido.")
        if not self.file_type.strip() or len(self.file_type) > FILE_TYPE_MAX_LENGTH:
            raise ValueError("El tipo del documento no es válido.")

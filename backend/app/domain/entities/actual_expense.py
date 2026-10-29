"""Documented actual spending, independent from a purchase-order budget."""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ActualExpenseClosure:
    retaceo_id: uuid.UUID
    retaceo_code: str


@dataclass(frozen=True, slots=True)
class ActualExpenseAvailability:
    can_record: bool
    reason: str | None = None
    closed_retaceo_id: uuid.UUID | None = None
    closed_retaceo_code: str | None = None


def is_fixed_retaceo_category(name: str) -> bool:
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", name.casefold())
        if not unicodedata.combining(char)
    ).strip()
    return normalized.startswith("flete") or normalized in {
        "fob",
        "dai",
        "aranceles",
        "aranceles de importacion",
        "iva de importacion",
    }


@dataclass(frozen=True, slots=True)
class ActualPurchaseExpense:
    id: uuid.UUID
    company_id: uuid.UUID
    purchase_order_id: uuid.UUID
    expense_type_id: uuid.UUID
    amount: Decimal
    incurred_on: date
    reference: str
    description: str
    allocated_amount: Decimal = Decimal("0")
    created_at: datetime | None = None

    @property
    def unallocated_amount(self) -> Decimal:
        return max(Decimal("0"), self.amount - self.allocated_amount)

    def __post_init__(self) -> None:
        if not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("El gasto real debe ser mayor que cero.")
        if not self.reference.strip() or not self.description.strip():
            raise ValueError("El gasto real requiere referencia y descripción.")

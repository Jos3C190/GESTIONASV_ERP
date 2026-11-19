"""DTOs de las notas de crédito y de débito sobre un crédito fiscal (bloque V4c)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.sales_invoice import FiscalDocumentOut

Nature = Literal["taxed", "exempt", "not_subject"]


class CreditLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ccf_line_number: int = Field(ge=1)
    kind: Literal["return", "discount"]
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)

    @model_validator(mode="after")
    def _one_measure(self) -> CreditLineIn:
        if self.kind == "return" and (self.quantity is None or self.amount is not None):
            raise ValueError("Una devolución lleva la cantidad devuelta, no un monto.")
        if self.kind == "discount" and (self.amount is None or self.quantity is not None):
            raise ValueError("Una rebaja lleva el monto, no una cantidad.")
        return self


class CreditNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=300)
    lines: list[CreditLineIn] = Field(min_length=1, max_length=2000)


class DebitChargeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=3, max_length=1000)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    nature: Nature | None = None
    ccf_line_number: int | None = Field(default=None, ge=1)


class DebitNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=300)
    charges: list[DebitChargeIn] = Field(min_length=1, max_length=2000)


class CcfLineOut(BaseModel):
    number: int
    code: str | None
    description: str
    nature: Nature
    quantity: Decimal
    unit_price: Decimal
    net: Decimal
    returned: Decimal
    credited: Decimal
    remaining_quantity: Decimal
    remaining_amount: Decimal


class NoteLineOut(BaseModel):
    line_number: int
    ccf_line_number: int | None
    kind: Literal["return", "discount", "charge"]
    nature: Nature
    description: str
    quantity: Decimal | None
    amount: Decimal


class NoteOut(BaseModel):
    document: FiscalDocumentOut
    lines: list[NoteLineOut]


class NotesOverviewOut(BaseModel):
    ccf_id: uuid.UUID
    deadline: date | None
    withholding: bool
    perception: bool
    credit_blocker: str | None
    debit_blocker: str | None
    lines: list[CcfLineOut]
    notes: list[NoteOut]

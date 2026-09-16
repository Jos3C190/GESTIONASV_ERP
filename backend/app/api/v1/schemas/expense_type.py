"""Read-only DTOs for expense-type options."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class ExpenseTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None


__all__ = ["ExpenseTypeResponse"]

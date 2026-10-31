"""Read-only DTOs for expense-type options."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ExpenseTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None


class ExpenseTypeCatalogResponse(ExpenseTypeResponse):
    is_active: bool
    usage_count: int


class ExpenseTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class ExpenseTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool


__all__ = [
    "ExpenseTypeCatalogResponse",
    "ExpenseTypeCreate",
    "ExpenseTypeResponse",
    "ExpenseTypeUpdate",
]

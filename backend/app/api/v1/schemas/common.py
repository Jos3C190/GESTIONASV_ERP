"""Common, reusable Pydantic DTOs."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PageMeta(BaseModel):
    page: int
    size: int
    total: int
    pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class HealthComponent(BaseModel):
    name: str
    status: str
    detail: str | None = None


class HealthReport(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: str
    components: list[HealthComponent]


class MessageOut(BaseModel):
    message: str
    code: str | None = None

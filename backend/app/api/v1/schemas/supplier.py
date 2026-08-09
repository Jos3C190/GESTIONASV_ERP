"""Pydantic v2 DTOs for Suppliers and Supplier Contacts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.api.v1.schemas.common import ORMOut


# --- Supplier Contacts ---
class SupplierContactCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)


class SupplierContactUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    is_active: bool | None = None


class SupplierContactResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_supplier_contact")
    supplier_id: int = Field(..., serialization_alias="id_supplier")
    full_name: str
    phone: str | None = None
    email: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Supplier ---
class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    country_id: int = Field(..., alias="country")
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    website: str | None = Field(None, max_length=200)


class SupplierUpdate(BaseModel):
    code: str | None = Field(None, min_length=2, max_length=50)
    name: str | None = Field(None, min_length=2, max_length=200)
    country_id: int | None = Field(None, alias="country")
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    website: str | None = Field(None, max_length=200)
    is_active: bool | None = None


class SupplierResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_supplier")
    uuid: uuid.UUID
    company_id: uuid.UUID
    code: str
    name: str
    country_id: int = Field(..., serialization_alias="country")
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    is_active: bool
    contacts: list[SupplierContactResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

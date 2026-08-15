"""Pydantic v2 DTOs for Suppliers and Supplier Contacts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.media_image import SingleImageDraft, normalize_single_image_draft


class SupplierImageInput(BaseModel):
    source_type: Literal["cloudinary", "external"]
    url: str = Field(..., min_length=10, max_length=2048)
    media_asset_id: UUID | None = None
    alt_text: str | None = Field(None, max_length=160)

    @model_validator(mode="after")
    def validate_source(self) -> SupplierImageInput:
        normalized = normalize_single_image_draft(
            SingleImageDraft(
                source_type=self.source_type,
                url=self.url,
                media_asset_id=self.media_asset_id,
                alt_text=self.alt_text,
            )
        )
        self.source_type = normalized.source_type
        self.url = normalized.url
        self.alt_text = normalized.alt_text
        return self


class SupplierImageResponse(ORMOut):
    id: UUID
    source_type: Literal["cloudinary", "external"]
    url: str
    media_asset_id: UUID | None = None
    alt_text: str | None = None


# --- Supplier Contacts ---
class SupplierContactCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    image: SupplierImageInput | None = None


class SupplierContactUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    is_active: bool | None = None
    image: SupplierImageInput | None = None


class SupplierContactResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_supplier_contact")
    supplier_id: int = Field(..., serialization_alias="id_supplier")
    uuid: UUID | None = None
    full_name: str
    phone: str | None = None
    email: str | None = None
    is_active: bool
    avatar_image: SupplierImageResponse | None = None
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
    image: SupplierImageInput | None = None


class SupplierUpdate(BaseModel):
    code: str | None = Field(None, min_length=2, max_length=50)
    name: str | None = Field(None, min_length=2, max_length=200)
    country_id: int | None = Field(None, alias="country")
    address: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)
    website: str | None = Field(None, max_length=200)
    is_active: bool | None = None
    image: SupplierImageInput | None = None


class SupplierResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_supplier")
    uuid: UUID
    company_id: UUID
    code: str
    name: str
    country_id: int = Field(..., serialization_alias="country")
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    is_active: bool
    logo_image: SupplierImageResponse | None = None
    contacts: list[SupplierContactResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

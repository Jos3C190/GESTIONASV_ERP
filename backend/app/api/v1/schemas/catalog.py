"""Pydantic v2 DTOs for Catalog: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.api.v1.schemas.common import ORMOut


# --- Country ---
class CountryResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_country")
    name: str
    iso_code_2: str
    iso_code_3: str
    phone_code: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Category ---
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class CategoryResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_category")
    uuid: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- SubCategory ---
class SubCategoryCreate(BaseModel):
    category_id: int = Field(..., alias="id_category")
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None


class SubCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class SubCategoryResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_sub_category")
    category_id: int = Field(..., serialization_alias="id_category")
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Unit ---
class UnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)


class UnitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None


class UnitResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_unit")
    name: str
    type: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Product ---
class ProductCreate(BaseModel):
    category_id: int = Field(..., alias="id_category")
    sub_category_id: int | None = Field(None, alias="id_sub_category")
    sku: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=200)
    purchase_unit_id: int = Field(..., alias="purchase_unit")
    sale_unit_id: int = Field(..., alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = None
    dimensions: str | None = None
    description: str | None = None
    presentation: str | None = None


class ProductUpdate(BaseModel):
    category_id: int | None = Field(None, alias="id_category")
    sub_category_id: int | None = Field(None, alias="id_sub_category")
    sku: str | None = Field(None, min_length=2, max_length=100)
    name: str | None = Field(None, min_length=2, max_length=200)
    purchase_unit_id: int | None = Field(None, alias="purchase_unit")
    sale_unit_id: int | None = Field(None, alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = None
    dimensions: str | None = None
    description: str | None = None
    presentation: str | None = None
    is_active: bool | None = None


class ProductResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_product")
    uuid: uuid.UUID
    category_id: int = Field(..., serialization_alias="id_category")
    sub_category_id: int | None = Field(None, serialization_alias="id_sub_category")
    sku: str
    name: str
    purchase_unit_id: int = Field(..., serialization_alias="purchase_unit")
    sale_unit_id: int = Field(..., serialization_alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = None
    dimensions: str | None = None
    description: str | None = None
    presentation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

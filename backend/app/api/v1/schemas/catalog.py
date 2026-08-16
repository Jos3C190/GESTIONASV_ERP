"""Pydantic v2 DTOs for Catalog: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.common import ORMOut

DimensionUnit = Literal["mm", "cm", "m", "in", "ft"]
WeightUnit = Literal["mg", "g", "kg", "t", "oz", "lb"]


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
    company_id: uuid.UUID
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
    company_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Unit ---
class UnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    symbol: str = Field(..., min_length=1, max_length=20)
    description: str | None = Field(None, max_length=500)


class UnitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None
    code: str | None = Field(None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    symbol: str | None = Field(None, min_length=1, max_length=20)
    description: str | None = Field(None, max_length=500)
    alias: str | None = Field(None, max_length=100)
    version: int = Field(..., ge=1)


class UnitResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_unit")
    name: str
    type: str
    code: str
    symbol: str
    owner_company_id: uuid.UUID | None = None
    description: str | None = None
    is_standard: bool
    is_enabled: bool
    alias: str | None = None
    version: int
    configuration_version: int
    usage_count: int = 0
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UnitConfigurationUpdate(BaseModel):
    version: int = Field(..., ge=1)
    alias: str | None = Field(None, max_length=100)


# --- Product ---
class ProductImageInput(BaseModel):
    id: uuid.UUID | None = None
    source_type: Literal["cloudinary", "external"]
    url: str = Field(..., min_length=10, max_length=2048)
    media_asset_id: uuid.UUID | None = None
    alt_text: str | None = Field(None, max_length=160)
    position: int = Field(..., ge=0, le=19)
    is_cover: bool = False

    @model_validator(mode="after")
    def validate_source(self) -> ProductImageInput:
        if self.source_type == "external":
            parsed = urlparse(self.url.strip())
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if parsed.scheme.lower() != "https" or not hostname:
                raise ValueError("Las imágenes externas deben usar una URL HTTPS válida.")
            if parsed.username or parsed.password:
                raise ValueError("La URL de imagen no puede contener credenciales.")
            if hostname == "localhost" or hostname.endswith(".localhost"):
                raise ValueError("No se permiten URLs locales para imágenes externas.")
            if self.media_asset_id is not None:
                raise ValueError("Una imagen externa no puede referenciar un asset Cloudinary.")
        elif self.media_asset_id is None:
            raise ValueError("Una imagen Cloudinary debe referenciar su asset cargado.")
        return self


class ProductImageResponse(ORMOut):
    id: uuid.UUID
    product_id: int
    source_type: Literal["cloudinary", "external"]
    url: str
    media_asset_id: uuid.UUID | None = None
    alt_text: str | None = None
    position: int
    is_cover: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    category_id: int = Field(..., alias="id_category")
    sub_category_id: int | None = Field(None, alias="id_sub_category")
    sku: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=200)
    purchase_unit_id: int = Field(..., alias="purchase_unit")
    sale_unit_id: int = Field(..., alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = Field(None, max_length=50)
    dimension_length: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_width: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_height: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_unit: DimensionUnit | None = None
    weight: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    weight_unit: WeightUnit | None = None
    description: str | None = None
    presentation: str | None = None
    images: list[ProductImageInput] | None = Field(None, max_length=20)

    @model_validator(mode="after")
    def validate_measurement_pairs(self) -> ProductCreate:
        has_dimensions = any(
            value is not None for value in (self.dimension_length, self.dimension_width, self.dimension_height)
        )
        if has_dimensions != (self.dimension_unit is not None):
            raise ValueError("Las dimensiones requieren una unidad y no se permite unidad sin medidas.")
        if (self.weight is None) != (self.weight_unit is None):
            raise ValueError("El peso requiere una unidad y no se permite unidad sin peso.")
        return self


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    category_id: int | None = Field(None, alias="id_category")
    sub_category_id: int | None = Field(None, alias="id_sub_category")
    sku: str | None = Field(None, min_length=2, max_length=100)
    name: str | None = Field(None, min_length=2, max_length=200)
    purchase_unit_id: int | None = Field(None, alias="purchase_unit")
    sale_unit_id: int | None = Field(None, alias="sale_unit")
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = Field(None, max_length=50)
    dimension_length: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_width: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_height: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    dimension_unit: DimensionUnit | None = None
    weight: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=3)
    weight_unit: WeightUnit | None = None
    description: str | None = None
    presentation: str | None = None
    is_active: bool | None = None
    images: list[ProductImageInput] | None = Field(None, max_length=20)


class ProductResponse(ORMOut):
    id: int = Field(..., serialization_alias="id_product")
    uuid: uuid.UUID
    company_id: uuid.UUID
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
    dimensions_legacy: str | None = None
    dimension_length: Decimal | None = None
    dimension_width: Decimal | None = None
    dimension_height: Decimal | None = None
    dimension_unit: DimensionUnit | None = None
    weight: Decimal | None = None
    weight_unit: WeightUnit | None = None
    dimension_summary: str | None = None
    volume: Decimal | None = None
    volume_unit: str | None = None
    description: str | None = None
    presentation: str | None = None
    is_active: bool
    images: list[ProductImageResponse] = Field(default_factory=list)
    image_count: int = 0
    cover_image: ProductImageResponse | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

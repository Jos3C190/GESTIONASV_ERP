"""Domain entities: Country, Category, SubCategory, Unit, Product."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.product_image import ProductImage


@dataclass(frozen=True, slots=True)
class Country:
    id: int
    name: str
    iso_code_2: str
    iso_code_3: str
    phone_code: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Category:
    id: int
    uuid: uuid.UUID
    company_id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SubCategory:
    id: int
    company_id: uuid.UUID
    category_id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Unit:
    id: int
    name: str
    type: str
    code: str
    symbol: str
    owner_company_id: uuid.UUID | None = None
    description: str | None = None
    is_standard: bool = True
    is_enabled: bool = True
    alias: str | None = None
    version: int = 1
    configuration_version: int = 1
    usage_count: int = 0
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Product:
    id: int
    uuid: uuid.UUID
    company_id: uuid.UUID
    category_id: int
    sub_category_id: int | None
    sku: str
    name: str
    purchase_unit_id: int
    sale_unit_id: int
    original_code: str | None = None
    internal_code: str | None = None
    size: str | None = None
    dimensions: str | None = None
    description: str | None = None
    presentation: str | None = None
    is_active: bool = True
    images: tuple[ProductImage, ...] = ()
    image_count: int = 0
    cover_image: ProductImage | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

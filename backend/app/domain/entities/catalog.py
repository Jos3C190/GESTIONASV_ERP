"""Domain entities: Country, Category, SubCategory, Unit, Product."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.entities.product_image import ProductImage
from app.domain.entities.product_master import ProductIdentifier, ProductSupplier
from app.domain.entities.product_variants import ProductFamilyAttribute, ProductVariant
from app.domain.product_measurements import calculate_volume, format_dimension_summary


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
    dimensions_legacy: str | None = None
    dimension_length: Decimal | None = None
    dimension_width: Decimal | None = None
    dimension_height: Decimal | None = None
    dimension_unit: str | None = None
    weight: Decimal | None = None
    weight_unit: str | None = None
    description: str | None = None
    presentation: str | None = None
    product_kind: str = "goods"
    lifecycle_status: str = "active"
    can_purchase: bool = True
    can_sell: bool = True
    sales_name: str | None = None
    internal_name: str | None = None
    document_name: str | None = None
    sales_description: str | None = None
    purchase_description: str | None = None
    internal_notes: str | None = None
    keywords: tuple[str, ...] = ()
    origin_country_id: int | None = None
    brand_id: uuid.UUID | None = None
    manufacturer_id: uuid.UUID | None = None
    storage_condition: str | None = None
    storage_temperature_min_c: Decimal | None = None
    storage_temperature_max_c: Decimal | None = None
    storage_humidity_max_percent: Decimal | None = None
    is_fragile: bool = False
    keep_dry: bool = False
    keep_upright: bool = False
    stackable: bool = True
    max_stack_height: Decimal | None = None
    handling_notes: str | None = None
    identifiers: tuple[ProductIdentifier, ...] = ()
    supplier_links: tuple[ProductSupplier, ...] = ()
    is_active: bool = True
    images: tuple[ProductImage, ...] = ()
    image_count: int = 0
    cover_image: ProductImage | None = None
    variant_mode: str = "standalone"
    variant_count: int = 0
    variant_attributes: tuple[ProductFamilyAttribute, ...] = ()
    variants: tuple[ProductVariant, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Resolved only by paginated catalogue queries. Keeping it optional keeps
    # the domain compatible with detail/create flows that do not join the
    # category table.
    category_name: str | None = None

    @property
    def dimension_summary(self) -> str | None:
        return format_dimension_summary(
            self.dimension_length,
            self.dimension_width,
            self.dimension_height,
            self.dimension_unit,
        ) or self.dimensions_legacy or self.dimensions

    @property
    def volume(self) -> Decimal | None:
        return calculate_volume(
            self.dimension_length,
            self.dimension_width,
            self.dimension_height,
            self.dimension_unit,
        )

    @property
    def volume_unit(self) -> str | None:
        return "m³" if self.volume is not None else None

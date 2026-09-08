"""Catalog repository port interface."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit
from app.domain.entities.product_image import ProductImageDraft
from app.domain.entities.product_variants import (
    ProductVariant,
    ProductVariantConfigDraft,
    ProductVariantIdentifierDraft,
    ProductVariantUpdateDraft,
)


class CatalogRepository(Protocol):
    # Countries
    async def list_countries(self, active_only: bool = True) -> list[Country]: ...

    async def get_country_by_id(self, country_id: int) -> Country | None: ...

    async def create_country(
        self, name: str, iso_code_2: str, iso_code_3: str, phone_code: str
    ) -> Country: ...

    # Categories
    async def list_categories(
        self, company_id: uuid.UUID, active_only: bool = True
    ) -> list[Category]: ...

    async def get_category_by_id(
        self, company_id: uuid.UUID, category_id: int
    ) -> Category | None: ...

    async def get_category_by_uuid(
        self, company_id: uuid.UUID, cat_uuid: uuid.UUID
    ) -> Category | None: ...

    async def create_category(
        self, company_id: uuid.UUID, name: str, description: str | None = None
    ) -> Category: ...

    async def update_category(
        self, company_id: uuid.UUID, category_id: int, **changes: object
    ) -> Category | None: ...

    # SubCategories
    async def list_sub_categories(
        self, company_id: uuid.UUID, category_id: int | None = None, active_only: bool = True
    ) -> list[SubCategory]: ...

    async def get_sub_category_by_id(
        self, company_id: uuid.UUID, sub_category_id: int
    ) -> SubCategory | None: ...

    async def create_sub_category(
        self, company_id: uuid.UUID, category_id: int, name: str, description: str | None = None
    ) -> SubCategory: ...

    async def update_sub_category(
        self, company_id: uuid.UUID, sub_category_id: int, **changes: object
    ) -> SubCategory | None: ...

    # Units
    async def list_units(self, company_id: uuid.UUID, active_only: bool = True) -> list[Unit]: ...

    async def list_global_units(self, active_only: bool = False) -> list[Unit]: ...

    async def get_unit_by_id(
        self, company_id: uuid.UUID, unit_id: int, *, require_enabled: bool = False
    ) -> Unit | None: ...

    async def get_unit_by_code(self, company_id: uuid.UUID | None, code: str) -> Unit | None: ...

    async def count_unit_usage(self, unit_id: int, company_id: uuid.UUID | None = None) -> int: ...

    async def create_unit(self, company_id: uuid.UUID | None, **values: object) -> Unit: ...

    async def update_unit(
        self, company_id: uuid.UUID | None, unit_id: int, expected_version: int, **changes: object
    ) -> Unit | None: ...

    async def configure_unit(
        self,
        company_id: uuid.UUID,
        unit_id: int,
        expected_version: int,
        *,
        enabled: bool,
        alias: str | None = None,
    ) -> Unit | None: ...

    # Products
    async def list_products(
        self,
        company_id: uuid.UUID,
        category_id: int | None = None,
        sub_category_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]: ...

    async def get_product_by_id(self, company_id: uuid.UUID, product_id: int) -> Product | None: ...

    async def get_product_by_uuid(
        self, company_id: uuid.UUID, prod_uuid: uuid.UUID
    ) -> Product | None: ...

    async def get_product_by_sku(self, company_id: uuid.UUID, sku: str) -> Product | None: ...

    async def create_product(
        self,
        company_id: uuid.UUID,
        category_id: int,
        sub_category_id: int | None,
        sku: str,
        name: str,
        purchase_unit_id: int,
        sale_unit_id: int,
        original_code: str | None = None,
        internal_code: str | None = None,
        size: str | None = None,
        dimension_length: object = None,
        dimension_width: object = None,
        dimension_height: object = None,
        dimension_unit: str | None = None,
        weight: object = None,
        weight_unit: str | None = None,
        description: str | None = None,
        presentation: str | None = None,
        product_kind: str = "goods",
        lifecycle_status: str = "active",
        can_purchase: bool = True,
        can_sell: bool = True,
        sales_name: str | None = None,
        internal_name: str | None = None,
        document_name: str | None = None,
        sales_description: str | None = None,
        purchase_description: str | None = None,
        internal_notes: str | None = None,
        keywords: list[str] | None = None,
        origin_country_id: int | None = None,
        brand_id: uuid.UUID | None = None,
        manufacturer_id: uuid.UUID | None = None,
        storage_condition: str | None = None,
        storage_temperature_min_c: object = None,
        storage_temperature_max_c: object = None,
        storage_humidity_max_percent: object = None,
        is_fragile: bool = False,
        keep_dry: bool = False,
        keep_upright: bool = False,
        stackable: bool = True,
        max_stack_height: object = None,
        handling_notes: str | None = None,
        is_active: bool = True,
        images: list[ProductImageDraft] | None = None,
        identifiers: tuple[ProductVariantIdentifierDraft, ...] | None = None,
        variant_config: ProductVariantConfigDraft | None = None,
    ) -> Product: ...

    async def update_product(
        self,
        company_id: uuid.UUID,
        product_id: int,
        **kwargs: object,
    ) -> Product | None: ...

    async def get_variant(
        self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID
    ) -> ProductVariant | None: ...

    async def update_variant(
        self,
        company_id: uuid.UUID,
        product_id: int,
        variant_id: uuid.UUID,
        draft: ProductVariantUpdateDraft,
    ) -> ProductVariant | None: ...

    async def replace_variant_config(
        self, company_id: uuid.UUID, product_id: int, config: ProductVariantConfigDraft
    ) -> Product: ...

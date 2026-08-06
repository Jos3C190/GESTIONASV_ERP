"""Catalog repository port interface."""
from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit


class CatalogRepository(Protocol):
    # Countries
    async def list_countries(self, active_only: bool = True) -> list[Country]:
        ...

    async def get_country_by_id(self, country_id: int) -> Country | None:
        ...

    async def create_country(self, name: str, iso_code_2: str, iso_code_3: str, phone_code: str) -> Country:
        ...

    # Categories
    async def list_categories(self, active_only: bool = True) -> list[Category]:
        ...

    async def get_category_by_id(self, category_id: int) -> Category | None:
        ...

    async def get_category_by_uuid(self, cat_uuid: uuid.UUID) -> Category | None:
        ...

    async def create_category(self, name: str, description: str | None = None) -> Category:
        ...

    async def update_category(self, category_id: int, name: str | None = None, description: str | None = None, is_active: bool | None = None) -> Category | None:
        ...

    # SubCategories
    async def list_sub_categories(self, category_id: int | None = None, active_only: bool = True) -> list[SubCategory]:
        ...

    async def get_sub_category_by_id(self, sub_category_id: int) -> SubCategory | None:
        ...

    async def create_sub_category(self, category_id: int, name: str, description: str | None = None) -> SubCategory:
        ...

    async def update_sub_category(self, sub_category_id: int, name: str | None = None, description: str | None = None, is_active: bool | None = None) -> SubCategory | None:
        ...

    # Units
    async def list_units(self, active_only: bool = True) -> list[Unit]:
        ...

    async def get_unit_by_id(self, unit_id: int) -> Unit | None:
        ...

    async def create_unit(self, name: str, type_: str) -> Unit:
        ...

    async def update_unit(self, unit_id: int, name: str | None = None, type_: str | None = None, is_active: bool | None = None) -> Unit | None:
        ...

    # Products
    async def list_products(
        self,
        category_id: int | None = None,
        sub_category_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        ...

    async def get_product_by_id(self, product_id: int) -> Product | None:
        ...

    async def get_product_by_uuid(self, prod_uuid: uuid.UUID) -> Product | None:
        ...

    async def get_product_by_sku(self, sku: str) -> Product | None:
        ...

    async def create_product(
        self,
        category_id: int,
        sub_category_id: int | None,
        sku: str,
        name: str,
        purchase_unit_id: int,
        sale_unit_id: int,
        original_code: str | None = None,
        internal_code: str | None = None,
        size: str | None = None,
        dimensions: str | None = None,
        description: str | None = None,
        presentation: str | None = None,
    ) -> Product:
        ...

    async def update_product(
        self,
        product_id: int,
        **kwargs,
    ) -> Product | None:
        ...

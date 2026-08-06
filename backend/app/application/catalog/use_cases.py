"""Application use cases for Catalog: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit
from app.domain.ports.catalog_repository import CatalogRepository


class CatalogUseCases:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repo = repository

    # --- Countries ---
    async def list_countries(self, active_only: bool = True) -> list[Country]:
        return await self._repo.list_countries(active_only=active_only)

    async def get_country(self, country_id: int) -> Country:
        country = await self._repo.get_country_by_id(country_id)
        if not country:
            raise NotFoundError("País no encontrado", code="country_not_found")
        return country

    # --- Categories ---
    async def list_categories(self, active_only: bool = True) -> list[Category]:
        return await self._repo.list_categories(active_only=active_only)

    async def get_category(self, category_id: int) -> Category:
        category = await self._repo.get_category_by_id(category_id)
        if not category:
            raise NotFoundError("Categoría no encontrada", code="category_not_found")
        return category

    async def create_category(self, name: str, description: str | None = None) -> Category:
        return await self._repo.create_category(name=name, description=description)

    async def update_category(
        self, category_id: int, name: str | None = None, description: str | None = None, is_active: bool | None = None
    ) -> Category:
        category = await self._repo.update_category(
            category_id=category_id, name=name, description=description, is_active=is_active
        )
        if not category:
            raise NotFoundError("Categoría no encontrada", code="category_not_found")
        return category

    # --- SubCategories ---
    async def list_sub_categories(self, category_id: int | None = None, active_only: bool = True) -> list[SubCategory]:
        return await self._repo.list_sub_categories(category_id=category_id, active_only=active_only)

    async def create_sub_category(self, category_id: int, name: str, description: str | None = None) -> SubCategory:
        await self.get_category(category_id)
        return await self._repo.create_sub_category(category_id=category_id, name=name, description=description)

    async def update_sub_category(
        self, sub_category_id: int, name: str | None = None, description: str | None = None, is_active: bool | None = None
    ) -> SubCategory:
        sub = await self._repo.update_sub_category(
            sub_category_id=sub_category_id, name=name, description=description, is_active=is_active
        )
        if not sub:
            raise NotFoundError("Subcategoría no encontrada", code="sub_category_not_found")
        return sub

    # --- Units ---
    async def list_units(self, active_only: bool = True) -> list[Unit]:
        return await self._repo.list_units(active_only=active_only)

    async def create_unit(self, name: str, type_: str) -> Unit:
        return await self._repo.create_unit(name=name, type_=type_)

    async def update_unit(
        self, unit_id: int, name: str | None = None, type_: str | None = None, is_active: bool | None = None
    ) -> Unit:
        unit = await self._repo.update_unit(unit_id=unit_id, name=name, type_=type_, is_active=is_active)
        if not unit:
            raise NotFoundError("Unidad de medida no encontrada", code="unit_not_found")
        return unit

    # --- Products ---
    async def list_products(
        self,
        category_id: int | None = None,
        sub_category_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        return await self._repo.list_products(
            category_id=category_id,
            sub_category_id=sub_category_id,
            search=search,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )

    async def get_product(self, product_id: int) -> Product:
        product = await self._repo.get_product_by_id(product_id)
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

    async def get_product_by_uuid(self, prod_uuid: uuid.UUID) -> Product:
        product = await self._repo.get_product_by_uuid(prod_uuid)
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

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
        # Validate unique SKU
        existing = await self._repo.get_product_by_sku(sku)
        if existing:
            raise ConflictError(f"El SKU '{sku}' ya está registrado", code="sku_already_exists")

        # Validate category and units exist
        await self.get_category(category_id)
        if sub_category_id is not None:
            sub = await self._repo.get_sub_category_by_id(sub_category_id)
            if not sub:
                raise NotFoundError("Subcategoría no encontrada", code="sub_category_not_found")
        
        unit_p = await self._repo.get_unit_by_id(purchase_unit_id)
        if not unit_p:
            raise NotFoundError("Unidad de compra no encontrada", code="purchase_unit_not_found")

        unit_s = await self._repo.get_unit_by_id(sale_unit_id)
        if not unit_s:
            raise NotFoundError("Unidad de venta no encontrada", code="sale_unit_not_found")

        return await self._repo.create_product(
            category_id=category_id,
            sub_category_id=sub_category_id,
            sku=sku,
            name=name,
            purchase_unit_id=purchase_unit_id,
            sale_unit_id=sale_unit_id,
            original_code=original_code,
            internal_code=internal_code,
            size=size,
            dimensions=dimensions,
            description=description,
            presentation=presentation,
        )

    async def update_product(self, product_id: int, **kwargs) -> Product:
        product = await self._repo.update_product(product_id=product_id, **kwargs)
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

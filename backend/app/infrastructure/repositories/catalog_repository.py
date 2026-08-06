"""SQLAlchemy implementation of CatalogRepository."""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit
from app.infrastructure.models.catalog import (
    CategoryModel, CountryModel, ProductModel, SubCategoryModel, UnitModel,
)


def _to_country(orm: CountryModel) -> Country:
    return Country(
        id=orm.id_country,
        name=orm.name,
        iso_code_2=orm.iso_code_2,
        iso_code_3=orm.iso_code_3,
        phone_code=orm.phone_code,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_category(orm: CategoryModel) -> Category:
    return Category(
        id=orm.id_category,
        uuid=orm.uuid,
        name=orm.name,
        description=orm.description,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_sub_category(orm: SubCategoryModel) -> SubCategory:
    return SubCategory(
        id=orm.id_sub_category,
        category_id=orm.id_category,
        name=orm.name,
        description=orm.description,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_unit(orm: UnitModel) -> Unit:
    return Unit(
        id=orm.id_unit,
        name=orm.name,
        type=orm.type,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_product(orm: ProductModel) -> Product:
    return Product(
        id=orm.id_product,
        uuid=orm.uuid,
        category_id=orm.id_category,
        sub_category_id=orm.id_sub_category,
        sku=orm.sku,
        name=orm.name,
        purchase_unit_id=orm.purchase_unit,
        sale_unit_id=orm.sale_unit,
        original_code=orm.original_code,
        internal_code=orm.internal_code,
        size=orm.size,
        dimensions=orm.dimensions,
        description=orm.description,
        presentation=orm.presentation,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SqlAlchemyCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Countries ---
    async def list_countries(self, active_only: bool = True) -> list[Country]:
        stmt = select(CountryModel)
        if active_only:
            stmt = stmt.where(CountryModel.is_active.is_(True))
        stmt = stmt.order_by(CountryModel.name)
        res = await self._session.execute(stmt)
        return [_to_country(c) for c in res.scalars().all()]

    async def get_country_by_id(self, country_id: int) -> Country | None:
        stmt = select(CountryModel).where(CountryModel.id_country == country_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_country(orm) if orm else None

    async def create_country(self, name: str, iso_code_2: str, iso_code_3: str, phone_code: str) -> Country:
        orm = CountryModel(name=name, iso_code_2=iso_code_2.upper(), iso_code_3=iso_code_3.upper(), phone_code=phone_code)
        self._session.add(orm)
        await self._session.flush()
        return _to_country(orm)

    # --- Categories ---
    async def list_categories(self, active_only: bool = True) -> list[Category]:
        stmt = select(CategoryModel)
        if active_only:
            stmt = stmt.where(CategoryModel.is_active.is_(True))
        stmt = stmt.order_by(CategoryModel.name)
        res = await self._session.execute(stmt)
        return [_to_category(c) for c in res.scalars().all()]

    async def get_category_by_id(self, category_id: int) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.id_category == category_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_category(orm) if orm else None

    async def get_category_by_uuid(self, cat_uuid: uuid.UUID) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.uuid == cat_uuid)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_category(orm) if orm else None

    async def create_category(self, name: str, description: str | None = None) -> Category:
        orm = CategoryModel(name=name, description=description)
        self._session.add(orm)
        await self._session.flush()
        return _to_category(orm)

    async def update_category(
        self, category_id: int, name: str | None = None, description: str | None = None, is_active: bool | None = None
    ) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.id_category == category_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        if name is not None:
            orm.name = name
        if description is not None:
            orm.description = description
        if is_active is not None:
            orm.is_active = is_active
        await self._session.flush()
        return _to_category(orm)

    # --- SubCategories ---
    async def list_sub_categories(self, category_id: int | None = None, active_only: bool = True) -> list[SubCategory]:
        stmt = select(SubCategoryModel)
        if category_id is not None:
            stmt = stmt.where(SubCategoryModel.id_category == category_id)
        if active_only:
            stmt = stmt.where(SubCategoryModel.is_active.is_(True))
        stmt = stmt.order_by(SubCategoryModel.name)
        res = await self._session.execute(stmt)
        return [_to_sub_category(s) for s in res.scalars().all()]

    async def get_sub_category_by_id(self, sub_category_id: int) -> SubCategory | None:
        stmt = select(SubCategoryModel).where(SubCategoryModel.id_sub_category == sub_category_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_sub_category(orm) if orm else None

    async def create_sub_category(self, category_id: int, name: str, description: str | None = None) -> SubCategory:
        orm = SubCategoryModel(id_category=category_id, name=name, description=description)
        self._session.add(orm)
        await self._session.flush()
        return _to_sub_category(orm)

    async def update_sub_category(
        self, sub_category_id: int, name: str | None = None, description: str | None = None, is_active: bool | None = None
    ) -> SubCategory | None:
        stmt = select(SubCategoryModel).where(SubCategoryModel.id_sub_category == sub_category_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        if name is not None:
            orm.name = name
        if description is not None:
            orm.description = description
        if is_active is not None:
            orm.is_active = is_active
        await self._session.flush()
        return _to_sub_category(orm)

    # --- Units ---
    async def list_units(self, active_only: bool = True) -> list[Unit]:
        stmt = select(UnitModel)
        if active_only:
            stmt = stmt.where(UnitModel.is_active.is_(True))
        stmt = stmt.order_by(UnitModel.name)
        res = await self._session.execute(stmt)
        return [_to_unit(u) for u in res.scalars().all()]

    async def get_unit_by_id(self, unit_id: int) -> Unit | None:
        stmt = select(UnitModel).where(UnitModel.id_unit == unit_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_unit(orm) if orm else None

    async def create_unit(self, name: str, type_: str) -> Unit:
        orm = UnitModel(name=name, type=type_)
        self._session.add(orm)
        await self._session.flush()
        return _to_unit(orm)

    async def update_unit(
        self, unit_id: int, name: str | None = None, type_: str | None = None, is_active: bool | None = None
    ) -> Unit | None:
        stmt = select(UnitModel).where(UnitModel.id_unit == unit_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        if name is not None:
            orm.name = name
        if type_ is not None:
            orm.type = type_
        if is_active is not None:
            orm.is_active = is_active
        await self._session.flush()
        return _to_unit(orm)

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
        conditions = []
        if category_id is not None:
            conditions.append(ProductModel.id_category == category_id)
        if sub_category_id is not None:
            conditions.append(ProductModel.id_sub_category == sub_category_id)
        if active_only:
            conditions.append(ProductModel.is_active.is_(True))
        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    ProductModel.name.ilike(pattern),
                    ProductModel.sku.ilike(pattern),
                    ProductModel.original_code.ilike(pattern),
                    ProductModel.internal_code.ilike(pattern),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(ProductModel).where(*conditions)
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()

        # Query items
        stmt = (
            select(ProductModel)
            .where(*conditions)
            .order_by(ProductModel.name)
            .offset(skip)
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        items = [_to_product(p) for p in res.scalars().all()]
        return items, total

    async def get_product_by_id(self, product_id: int) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.id_product == product_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

    async def get_product_by_uuid(self, prod_uuid: uuid.UUID) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.uuid == prod_uuid)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

    async def get_product_by_sku(self, sku: str) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.sku == sku)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

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
        orm = ProductModel(
            id_category=category_id,
            id_sub_category=sub_category_id,
            sku=sku,
            name=name,
            purchase_unit=purchase_unit_id,
            sale_unit=sale_unit_id,
            original_code=original_code,
            internal_code=internal_code,
            size=size,
            dimensions=dimensions,
            description=description,
            presentation=presentation,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_product(orm)

    async def update_product(self, product_id: int, **kwargs) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.id_product == product_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        for key, value in kwargs.items():
            if hasattr(orm, key) and value is not None:
                setattr(orm, key, value)
        await self._session.flush()
        return _to_product(orm)

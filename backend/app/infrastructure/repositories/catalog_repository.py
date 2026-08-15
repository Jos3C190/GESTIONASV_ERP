"""SQLAlchemy implementation of CatalogRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit
from app.domain.entities.product_image import ProductImage, ProductImageDraft
from app.infrastructure.models.catalog import (
    CategoryModel,
    CompanyUnitModel,
    CountryModel,
    ProductModel,
    SubCategoryModel,
    UnitModel,
)
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.models.product_image import ProductImageModel


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
        company_id=orm.company_id,
        name=orm.name,
        description=orm.description,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_sub_category(orm: SubCategoryModel) -> SubCategory:
    return SubCategory(
        id=orm.id_sub_category,
        company_id=orm.company_id,
        category_id=orm.id_category,
        name=orm.name,
        description=orm.description,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_unit(orm: UnitModel, config: CompanyUnitModel | None = None, usage_count: int = 0) -> Unit:
    return Unit(
        id=orm.id_unit,
        name=orm.name,
        type=orm.type,
        code=orm.code,
        symbol=orm.symbol,
        owner_company_id=orm.owner_company_id,
        description=orm.description,
        is_standard=orm.is_standard,
        is_enabled=config.is_enabled if config else orm.is_active,
        alias=config.alias if config else None,
        version=orm.version,
        configuration_version=config.version if config else orm.version,
        usage_count=usage_count,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_product_image(orm: ProductImageModel) -> ProductImage:
    return ProductImage(
        id=orm.id,
        product_id=orm.product_id,
        source_type=orm.source_type,
        url=orm.url,
        media_asset_id=orm.media_asset_id,
        alt_text=orm.alt_text,
        position=orm.position,
        is_cover=orm.is_cover,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_product(
    orm: ProductModel,
    *,
    image_count: int | None = None,
    cover_image: ProductImage | None = None,
) -> Product:
    loaded_images = orm.__dict__.get("images")
    images = tuple(_to_product_image(image) for image in loaded_images or [])
    resolved_cover = cover_image or next((image for image in images if image.is_cover), None)
    return Product(
        id=orm.id_product,
        uuid=orm.uuid,
        company_id=orm.company_id,
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
        images=images,
        image_count=image_count if image_count is not None else len(images),
        cover_image=resolved_cover,
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
    async def list_categories(self, company_id: uuid.UUID, active_only: bool = True) -> list[Category]:
        stmt = select(CategoryModel).where(CategoryModel.company_id == company_id)
        if active_only:
            stmt = stmt.where(CategoryModel.is_active.is_(True))
        stmt = stmt.order_by(CategoryModel.name)
        res = await self._session.execute(stmt)
        return [_to_category(c) for c in res.scalars().all()]

    async def get_category_by_id(self, company_id: uuid.UUID, category_id: int) -> Category | None:
        stmt = select(CategoryModel).where(
            CategoryModel.company_id == company_id, CategoryModel.id_category == category_id
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_category(orm) if orm else None

    async def get_category_by_uuid(self, company_id: uuid.UUID, cat_uuid: uuid.UUID) -> Category | None:
        stmt = select(CategoryModel).where(
            CategoryModel.company_id == company_id, CategoryModel.uuid == cat_uuid
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_category(orm) if orm else None

    async def create_category(self, company_id: uuid.UUID, name: str, description: str | None = None) -> Category:
        orm = CategoryModel(company_id=company_id, name=name, description=description)
        self._session.add(orm)
        await self._session.flush()
        return _to_category(orm)

    async def update_category(
        self, company_id: uuid.UUID, category_id: int, **changes: object
    ) -> Category | None:
        stmt = select(CategoryModel).where(
            CategoryModel.company_id == company_id, CategoryModel.id_category == category_id
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        for field in ("name", "description", "is_active"):
            if field in changes:
                setattr(orm, field, changes[field])
        await self._session.flush()
        return _to_category(orm)

    # --- SubCategories ---
    async def list_sub_categories(self, company_id: uuid.UUID, category_id: int | None = None, active_only: bool = True) -> list[SubCategory]:
        stmt = select(SubCategoryModel).where(SubCategoryModel.company_id == company_id)
        if category_id is not None:
            stmt = stmt.where(SubCategoryModel.id_category == category_id)
        if active_only:
            stmt = stmt.where(SubCategoryModel.is_active.is_(True))
        stmt = stmt.order_by(SubCategoryModel.name)
        res = await self._session.execute(stmt)
        return [_to_sub_category(s) for s in res.scalars().all()]

    async def get_sub_category_by_id(self, company_id: uuid.UUID, sub_category_id: int) -> SubCategory | None:
        stmt = select(SubCategoryModel).where(
            SubCategoryModel.company_id == company_id,
            SubCategoryModel.id_sub_category == sub_category_id,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_sub_category(orm) if orm else None

    async def create_sub_category(self, company_id: uuid.UUID, category_id: int, name: str, description: str | None = None) -> SubCategory:
        orm = SubCategoryModel(company_id=company_id, id_category=category_id, name=name, description=description)
        self._session.add(orm)
        await self._session.flush()
        return _to_sub_category(orm)

    async def update_sub_category(
        self, company_id: uuid.UUID, sub_category_id: int, **changes: object
    ) -> SubCategory | None:
        stmt = select(SubCategoryModel).where(
            SubCategoryModel.company_id == company_id,
            SubCategoryModel.id_sub_category == sub_category_id,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        for field in ("name", "description", "is_active"):
            if field in changes:
                setattr(orm, field, changes[field])
        await self._session.flush()
        return _to_sub_category(orm)

    # --- Units ---
    async def list_units(self, company_id: uuid.UUID, active_only: bool = True) -> list[Unit]:
        usage = (
            select(func.count(ProductModel.id_product))
            .where(
                ProductModel.company_id == company_id,
                or_(ProductModel.purchase_unit == UnitModel.id_unit, ProductModel.sale_unit == UnitModel.id_unit),
            )
            .correlate(UnitModel)
            .scalar_subquery()
        )
        stmt = (
            select(UnitModel, CompanyUnitModel, usage)
            .join(CompanyUnitModel, CompanyUnitModel.unit_id == UnitModel.id_unit)
            .where(
                CompanyUnitModel.company_id == company_id,
                or_(UnitModel.owner_company_id.is_(None), UnitModel.owner_company_id == company_id),
            )
        )
        if active_only:
            stmt = stmt.where(UnitModel.is_active.is_(True), CompanyUnitModel.is_enabled.is_(True))
        stmt = stmt.order_by(UnitModel.is_standard.desc(), UnitModel.name)
        res = await self._session.execute(stmt)
        return [_to_unit(unit, config, int(count or 0)) for unit, config, count in res.all()]

    async def list_global_units(self, active_only: bool = False) -> list[Unit]:
        stmt = select(UnitModel).where(UnitModel.owner_company_id.is_(None))
        if active_only:
            stmt = stmt.where(UnitModel.is_active.is_(True))
        result = await self._session.execute(stmt.order_by(UnitModel.name))
        return [_to_unit(unit) for unit in result.scalars().all()]

    async def get_unit_by_id(
        self, company_id: uuid.UUID, unit_id: int, *, require_enabled: bool = False
    ) -> Unit | None:
        usage = (
            select(func.count(ProductModel.id_product))
            .where(
                ProductModel.company_id == company_id,
                or_(ProductModel.purchase_unit == unit_id, ProductModel.sale_unit == unit_id),
            )
            .scalar_subquery()
        )
        stmt = (
            select(UnitModel, CompanyUnitModel, usage)
            .join(CompanyUnitModel, CompanyUnitModel.unit_id == UnitModel.id_unit)
            .where(
                UnitModel.id_unit == unit_id,
                CompanyUnitModel.company_id == company_id,
                or_(UnitModel.owner_company_id.is_(None), UnitModel.owner_company_id == company_id),
            )
        )
        if require_enabled:
            stmt = stmt.where(UnitModel.is_active.is_(True), CompanyUnitModel.is_enabled.is_(True))
        res = await self._session.execute(stmt)
        row = res.one_or_none()
        return _to_unit(row[0], row[1], int(row[2] or 0)) if row else None

    async def get_unit_by_code(self, company_id: uuid.UUID | None, code: str) -> Unit | None:
        scope = UnitModel.owner_company_id.is_(None)
        if company_id is not None:
            scope = or_(UnitModel.owner_company_id.is_(None), UnitModel.owner_company_id == company_id)
        result = await self._session.execute(
            select(UnitModel).where(scope, func.lower(UnitModel.code) == code.strip().lower())
        )
        unit = result.scalars().first()
        return _to_unit(unit) if unit else None

    async def count_unit_usage(self, unit_id: int, company_id: uuid.UUID | None = None) -> int:
        stmt = select(func.count(ProductModel.id_product)).where(
            or_(ProductModel.purchase_unit == unit_id, ProductModel.sale_unit == unit_id)
        )
        if company_id is not None:
            stmt = stmt.where(ProductModel.company_id == company_id)
        return int((await self._session.scalar(stmt)) or 0)

    async def create_unit(self, company_id: uuid.UUID | None, **values: object) -> Unit:
        orm = UnitModel(
            owner_company_id=company_id,
            is_standard=company_id is None,
            name=str(values["name"]).strip(),
            type=str(values["type_"]).strip(),
            code=str(values["code"]).strip().upper(),
            symbol=str(values["symbol"]).strip(),
            description=values.get("description"),
        )
        self._session.add(orm)
        await self._session.flush()
        if company_id is not None:
            config = CompanyUnitModel(company_id=company_id, unit_id=orm.id_unit)
            self._session.add(config)
            await self._session.flush()
            return _to_unit(orm, config)
        # Standards become available to every existing company.
        from app.infrastructure.models.organization import Company

        company_ids = (await self._session.execute(select(Company.id))).scalars().all()
        for existing_company_id in company_ids:
            self._session.add(CompanyUnitModel(company_id=existing_company_id, unit_id=orm.id_unit))
        await self._session.flush()
        return _to_unit(orm)

    async def update_unit(
        self, company_id: uuid.UUID | None, unit_id: int, expected_version: int, **changes: object
    ) -> Unit | None:
        stmt = select(UnitModel).where(UnitModel.id_unit == unit_id, UnitModel.owner_company_id == company_id)
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        if orm.version != expected_version:
            return None
        field_map = {"type_": "type"}
        for field in ("name", "type_", "code", "symbol", "description", "is_active"):
            if field in changes and changes[field] is not None:
                value = changes[field]
                if field == "code":
                    value = str(value).strip().upper()
                setattr(orm, field_map.get(field, field), value)
        orm.version += 1
        await self._session.flush()
        if company_id is None:
            return _to_unit(orm)
        config = await self._session.get(CompanyUnitModel, (company_id, unit_id))
        return _to_unit(orm, config)

    async def configure_unit(
        self,
        company_id: uuid.UUID,
        unit_id: int,
        expected_version: int,
        *,
        enabled: bool,
        alias: str | None = None,
    ) -> Unit | None:
        config = await self._session.get(CompanyUnitModel, (company_id, unit_id))
        if config is None or config.version != expected_version:
            return None
        unit = await self._session.get(UnitModel, unit_id)
        if unit is None or (unit.owner_company_id is not None and unit.owner_company_id != company_id):
            return None
        config.is_enabled = enabled
        config.alias = alias.strip() if alias else None
        config.version += 1
        await self._session.flush()
        return _to_unit(unit, config)

    # --- Products ---
    async def list_products(
        self,
        company_id: uuid.UUID,
        category_id: int | None = None,
        sub_category_id: int | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        conditions = [ProductModel.company_id == company_id]
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

        # Query items. The gallery is deliberately not loaded here; only its
        # count and cover are projected for the catalogue table.
        stmt = (
            select(ProductModel, func.count(ProductImageModel.id).label("image_count"))
            .outerjoin(ProductImageModel, ProductImageModel.product_id == ProductModel.id_product)
            .where(*conditions)
            .group_by(ProductModel.id_product)
            .order_by(ProductModel.name)
            .offset(skip)
            .limit(limit)
            .options(noload(ProductModel.images))
        )
        res = await self._session.execute(stmt)
        rows = res.all()
        product_ids = [product.id_product for product, _count in rows]
        covers: dict[int, ProductImage] = {}
        if product_ids:
            cover_rows = await self._session.execute(
                select(ProductImageModel).where(
                    ProductImageModel.product_id.in_(product_ids), ProductImageModel.is_cover.is_(True)
                )
            )
            covers = {
                image.product_id: _to_product_image(image) for image in cover_rows.scalars().all()
            }
        items = [
            _to_product(product, image_count=int(count), cover_image=covers.get(product.id_product))
            for product, count in rows
        ]
        return items, total

    async def get_product_by_id(self, company_id: uuid.UUID, product_id: int) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.company_id == company_id, ProductModel.id_product == product_id
        ).options(selectinload(ProductModel.images))
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

    async def get_product_by_uuid(self, company_id: uuid.UUID, prod_uuid: uuid.UUID) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.company_id == company_id, ProductModel.uuid == prod_uuid
        ).options(selectinload(ProductModel.images))
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

    async def get_product_by_sku(self, company_id: uuid.UUID, sku: str) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.company_id == company_id, ProductModel.sku == sku
        ).options(noload(ProductModel.images))
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

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
        dimensions: str | None = None,
        description: str | None = None,
        presentation: str | None = None,
        images: list[ProductImageDraft] | None = None,
    ) -> Product:
        orm = ProductModel(
            company_id=company_id,
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
        if images is not None:
            await self._sync_product_images(orm, company_id, images)
        return await self._get_product_with_images(company_id, orm.id_product)

    async def update_product(self, company_id: uuid.UUID, product_id: int, **kwargs) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.company_id == company_id, ProductModel.id_product == product_id
        )
        res = await self._session.execute(stmt.options(selectinload(ProductModel.images)))
        orm = res.scalar_one_or_none()
        if not orm:
            return None
        field_map = {
            "category_id": "id_category",
            "sub_category_id": "id_sub_category",
            "purchase_unit_id": "purchase_unit",
            "sale_unit_id": "sale_unit",
        }
        images = kwargs.pop("images", None) if "images" in kwargs else None
        for key, value in kwargs.items():
            orm_field = field_map.get(key, key)
            if hasattr(orm, orm_field):
                setattr(orm, orm_field, value)
        await self._session.flush()
        if images is not None:
            await self._sync_product_images(orm, company_id, images)
        return await self._get_product_with_images(company_id, product_id)

    async def _get_product_with_images(self, company_id: uuid.UUID, product_id: int) -> Product:
        result = await self._session.execute(
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
            .execution_options(populate_existing=True)
            .options(selectinload(ProductModel.images))
        )
        orm = result.scalar_one()
        return _to_product(orm)

    async def _sync_product_images(
        self, product: ProductModel, company_id: uuid.UUID, drafts: list[ProductImageDraft]
    ) -> None:
        """Replace a product gallery atomically and claim staged media assets."""
        existing = (
            await self._session.execute(
                select(ProductImageModel).where(ProductImageModel.product_id == product.id_product)
            )
        ).scalars().all()
        incoming_asset_ids = {
            draft.media_asset_id
            for draft in drafts
            if getattr(draft, "source_type", None) == "cloudinary"
            and getattr(draft, "media_asset_id", None) is not None
        }

        for image in existing:
            if image.media_asset_id and image.media_asset_id not in incoming_asset_ids:
                asset = await self._session.get(MediaAsset, image.media_asset_id)
                if asset is not None:
                    asset.status = "detached"
                    asset.owner_type = None
                    asset.owner_id = None
            await self._session.delete(image)
        if existing:
            await self._session.flush()

        for draft in drafts:
            media_asset_id = draft.media_asset_id
            source_type = draft.source_type
            if source_type == "cloudinary":
                asset = await self._session.scalar(
                    select(MediaAsset).where(
                        MediaAsset.id == media_asset_id,
                        MediaAsset.company_id == company_id,
                        MediaAsset.purpose == "product_image",
                        MediaAsset.status.in_(("staged", "active")),
                    )
                )
                if asset is None:
                    raise ValueError("El asset Cloudinary no existe, no pertenece a la empresa o ya fue usado.")
                if asset.owner_id not in (None, product.uuid) or asset.owner_type not in (None, "product"):
                    raise ValueError("El asset Cloudinary ya está asociado a otro recurso.")
                asset.status = "active"
                asset.owner_type = "product"
                asset.owner_id = product.uuid
                url = asset.secure_url
            else:
                url = draft.url
            self._session.add(
                ProductImageModel(
                    product_id=product.id_product,
                    media_asset_id=media_asset_id,
                    source_type=source_type,
                    url=url,
                    alt_text=draft.alt_text,
                    position=draft.position,
                    is_cover=draft.is_cover,
                )
            )
        await self._session.flush()

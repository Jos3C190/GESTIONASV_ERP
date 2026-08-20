"""SQLAlchemy implementation of CatalogRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.core.exceptions import ConcurrencyError
from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit
from app.domain.entities.product_image import ProductImage, ProductImageDraft
from app.domain.entities.product_master import ProductIdentifier, ProductSupplier
from app.domain.entities.product_variants import (
    ProductFamilyAttribute,
    ProductFamilyAttributeValue,
    ProductVariant,
    ProductVariantConfigDraft,
    ProductVariantImageDraft,
    ProductVariantUpdateDraft,
    ProductVariantValue,
)
from app.domain.product_variants import normalize_variant_token
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
from app.infrastructure.models.product_master import ProductIdentifierModel, ProductSupplierModel
from app.infrastructure.models.product_variant import (
    ProductFamilyAttributeModel,
    ProductFamilyAttributeValueModel,
    ProductSkuRegistryModel,
    ProductVariantAttributeValueModel,
    ProductVariantImageModel,
    ProductVariantModel,
)

MAX_VARIANT_ATTRIBUTES = 5
MAX_VARIANTS_PER_FAMILY = 500


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


def _to_product_identifier(orm: ProductIdentifierModel) -> ProductIdentifier:
    return ProductIdentifier(
        id=orm.id,
        product_id=orm.product_id,
        company_id=orm.company_id,
        identifier_type=orm.identifier_type,
        value=orm.value,
        normalized_value=orm.normalized_value,
        is_primary=orm.is_primary,
        is_active=orm.is_active,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        variant_id=orm.variant_id,
    )


def _to_variant_image(orm: ProductVariantImageModel, variant_id: uuid.UUID):
    return ProductImage(
        id=orm.id,
        product_id=None,
        variant_id=variant_id,
        source_type=orm.source_type,
        url=orm.url,
        media_asset_id=orm.media_asset_id,
        alt_text=orm.alt_text,
        position=0,
        is_cover=True,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_family_attribute(orm: ProductFamilyAttributeModel) -> ProductFamilyAttribute:
    values = tuple(
        ProductFamilyAttributeValue(
            id=value.id,
            attribute_id=value.attribute_id,
            code=value.code,
            label=value.label,
            position=value.position,
            is_active=value.is_active,
        )
        for value in (orm.values or [])
    )
    return ProductFamilyAttribute(
        id=orm.id,
        product_id=orm.product_id,
        code=orm.code,
        name=orm.name,
        position=orm.position,
        is_active=orm.is_active,
        values=values,
    )


def _to_variant(orm: ProductVariantModel, parent_name: str) -> ProductVariant:
    assignments = []
    for assignment in orm.attribute_values or []:
        attribute = assignment.attribute
        value = assignment.value
        if attribute is not None and value is not None:
            assignments.append(ProductVariantValue(attribute.code, value.code, value.label))
    assignments.sort(key=lambda item: item.attribute_code)
    suffix = " / ".join(f"{item.attribute_code}: {item.label}" for item in assignments)
    display_name = orm.name_override or (f"{parent_name} — {suffix}" if suffix else parent_name)
    identifiers = tuple(_to_product_identifier(item) for item in (orm.identifiers or []))
    image = _to_variant_image(orm.image, orm.id) if orm.image is not None else None
    return ProductVariant(
        id=orm.id,
        product_id=orm.product_id,
        company_id=orm.company_id,
        sku=orm.sku,
        name_override=orm.name_override,
        display_name=display_name,
        combination_key=orm.combination_key,
        lifecycle_status=orm.lifecycle_status,
        is_active=orm.is_active,
        values=tuple(assignments),
        identifiers=identifiers,
        image=image,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_product_supplier(orm: ProductSupplierModel) -> ProductSupplier:
    return ProductSupplier(
        id=orm.id,
        product_id=orm.product_id,
        supplier_id=orm.supplier_id,
        company_id=orm.company_id,
        supplier_product_code=orm.supplier_product_code,
        unit_cost=orm.unit_cost,
        currency_code=orm.currency_code,
        minimum_order_qty=orm.minimum_order_qty,
        order_multiple=orm.order_multiple,
        lead_time_days=orm.lead_time_days,
        is_preferred=orm.is_preferred,
        status=orm.status,
        valid_from=orm.valid_from,
        valid_until=orm.valid_until,
        notes=orm.notes,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_product(
    orm: ProductModel,
    *,
    image_count: int | None = None,
    variant_count: int | None = None,
    cover_image: ProductImage | None = None,
    category_name: str | None = None,
) -> Product:
    loaded_images = orm.__dict__.get("images")
    images = tuple(_to_product_image(image) for image in loaded_images or [])
    loaded_identifiers = orm.__dict__.get("identifiers")
    loaded_suppliers = orm.__dict__.get("supplier_links")
    resolved_cover = cover_image or next((image for image in images if image.is_cover), None)
    loaded_attributes = orm.__dict__.get("variant_attributes")
    loaded_variants = orm.__dict__.get("variants")
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
        dimensions_legacy=orm.dimensions_legacy,
        dimension_length=orm.dimension_length,
        dimension_width=orm.dimension_width,
        dimension_height=orm.dimension_height,
        dimension_unit=orm.dimension_unit,
        weight=orm.weight,
        weight_unit=orm.weight_unit,
        description=orm.description,
        presentation=orm.presentation,
        product_kind=orm.product_kind,
        lifecycle_status=orm.lifecycle_status,
        can_purchase=orm.can_purchase,
        can_sell=orm.can_sell,
        sales_name=orm.sales_name,
        internal_name=orm.internal_name,
        document_name=orm.document_name,
        sales_description=orm.sales_description,
        purchase_description=orm.purchase_description,
        internal_notes=orm.internal_notes,
        keywords=tuple(orm.keywords or []),
        origin_country_id=orm.origin_country_id,
        brand_id=orm.brand_id,
        manufacturer_id=orm.manufacturer_id,
        storage_condition=orm.storage_condition,
        storage_temperature_min_c=orm.storage_temperature_min_c,
        storage_temperature_max_c=orm.storage_temperature_max_c,
        storage_humidity_max_percent=orm.storage_humidity_max_percent,
        is_fragile=orm.is_fragile,
        keep_dry=orm.keep_dry,
        keep_upright=orm.keep_upright,
        stackable=orm.stackable,
        max_stack_height=orm.max_stack_height,
        handling_notes=orm.handling_notes,
        identifiers=tuple(_to_product_identifier(item) for item in loaded_identifiers or []),
        supplier_links=tuple(_to_product_supplier(item) for item in loaded_suppliers or []),
        is_active=orm.is_active,
        images=images,
        image_count=image_count if image_count is not None else len(images),
        cover_image=resolved_cover,
        variant_mode=orm.variant_mode,
        variant_count=variant_count if variant_count is not None else len(loaded_variants or []),
        variant_attributes=tuple(_to_family_attribute(item) for item in loaded_attributes or []),
        variants=tuple(_to_variant(item, orm.name) for item in loaded_variants or []),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        category_name=category_name,
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

    async def create_country(
        self, name: str, iso_code_2: str, iso_code_3: str, phone_code: str
    ) -> Country:
        orm = CountryModel(
            name=name,
            iso_code_2=iso_code_2.upper(),
            iso_code_3=iso_code_3.upper(),
            phone_code=phone_code,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_country(orm)

    # --- Categories ---
    async def list_categories(
        self, company_id: uuid.UUID, active_only: bool = True
    ) -> list[Category]:
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

    async def get_category_by_uuid(
        self, company_id: uuid.UUID, cat_uuid: uuid.UUID
    ) -> Category | None:
        stmt = select(CategoryModel).where(
            CategoryModel.company_id == company_id, CategoryModel.uuid == cat_uuid
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_category(orm) if orm else None

    async def create_category(
        self, company_id: uuid.UUID, name: str, description: str | None = None
    ) -> Category:
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
    async def list_sub_categories(
        self, company_id: uuid.UUID, category_id: int | None = None, active_only: bool = True
    ) -> list[SubCategory]:
        stmt = select(SubCategoryModel).where(SubCategoryModel.company_id == company_id)
        if category_id is not None:
            stmt = stmt.where(SubCategoryModel.id_category == category_id)
        if active_only:
            stmt = stmt.where(SubCategoryModel.is_active.is_(True))
        stmt = stmt.order_by(SubCategoryModel.name)
        res = await self._session.execute(stmt)
        return [_to_sub_category(s) for s in res.scalars().all()]

    async def get_sub_category_by_id(
        self, company_id: uuid.UUID, sub_category_id: int
    ) -> SubCategory | None:
        stmt = select(SubCategoryModel).where(
            SubCategoryModel.company_id == company_id,
            SubCategoryModel.id_sub_category == sub_category_id,
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_sub_category(orm) if orm else None

    async def create_sub_category(
        self, company_id: uuid.UUID, category_id: int, name: str, description: str | None = None
    ) -> SubCategory:
        orm = SubCategoryModel(
            company_id=company_id, id_category=category_id, name=name, description=description
        )
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
                or_(
                    ProductModel.purchase_unit == UnitModel.id_unit,
                    ProductModel.sale_unit == UnitModel.id_unit,
                ),
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
            scope = or_(
                UnitModel.owner_company_id.is_(None), UnitModel.owner_company_id == company_id
            )
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
        stmt = select(UnitModel).where(
            UnitModel.id_unit == unit_id, UnitModel.owner_company_id == company_id
        )
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
        if unit is None or (
            unit.owner_company_id is not None and unit.owner_company_id != company_id
        ):
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
        # Soft-deleted products belong to the recycle bin, not to the active
        # catalogue. Keeping this predicate here also keeps the table and its
        # server-side distribution insights on the same population.
        conditions = [ProductModel.company_id == company_id, ProductModel.deleted_at.is_(None)]
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
            select(
                ProductModel,
                CategoryModel.name,
                func.count(distinct(ProductImageModel.id)).label("image_count"),
                func.count(distinct(ProductVariantModel.id)).label("variant_count"),
            )
            .join(
                CategoryModel,
                (CategoryModel.id_category == ProductModel.id_category)
                & (CategoryModel.company_id == company_id),
            )
            .outerjoin(ProductImageModel, ProductImageModel.product_id == ProductModel.id_product)
            .outerjoin(
                ProductVariantModel, ProductVariantModel.product_id == ProductModel.id_product
            )
            .where(*conditions)
            .group_by(ProductModel.id_product, CategoryModel.name)
            .order_by(ProductModel.name)
            .offset(skip)
            .limit(limit)
            .options(
                noload(ProductModel.images),
                noload(ProductModel.identifiers),
                noload(ProductModel.supplier_links),
                noload(ProductModel.variants),
                noload(ProductModel.variant_attributes),
            )
        )
        res = await self._session.execute(stmt)
        rows = res.all()
        product_ids = [
            product.id_product
            for product, _category_name, _image_count, _variant_count in rows
        ]
        covers: dict[int, ProductImage] = {}
        if product_ids:
            cover_rows = await self._session.execute(
                select(ProductImageModel).where(
                    ProductImageModel.product_id.in_(product_ids),
                    ProductImageModel.is_cover.is_(True),
                )
            )
            covers = {
                image.product_id: _to_product_image(image) for image in cover_rows.scalars().all()
            }
        items = [
            _to_product(
                product,
                image_count=int(image_count),
                variant_count=int(variant_count),
                cover_image=covers.get(product.id_product),
                category_name=category_name,
            )
            for product, category_name, image_count, variant_count in rows
        ]
        return items, total

    async def get_product_by_id(self, company_id: uuid.UUID, product_id: int) -> Product | None:
        stmt = (
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
            .options(
                selectinload(ProductModel.images),
                selectinload(ProductModel.identifiers),
                selectinload(ProductModel.supplier_links),
                selectinload(ProductModel.variant_attributes).selectinload(
                    ProductFamilyAttributeModel.values
                ),
                selectinload(ProductModel.variants)
                .selectinload(ProductVariantModel.attribute_values)
                .options(
                    selectinload(ProductVariantAttributeValueModel.attribute),
                    selectinload(ProductVariantAttributeValueModel.value),
                ),
                selectinload(ProductModel.variants).selectinload(ProductVariantModel.identifiers),
                selectinload(ProductModel.variants).selectinload(ProductVariantModel.image),
            )
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

    async def get_product_by_uuid(
        self, company_id: uuid.UUID, prod_uuid: uuid.UUID
    ) -> Product | None:
        stmt = (
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.uuid == prod_uuid)
            .options(
                selectinload(ProductModel.images),
                selectinload(ProductModel.identifiers),
                selectinload(ProductModel.supplier_links),
                selectinload(ProductModel.variant_attributes).selectinload(
                    ProductFamilyAttributeModel.values
                ),
                selectinload(ProductModel.variants)
                .selectinload(ProductVariantModel.attribute_values)
                .options(
                    selectinload(ProductVariantAttributeValueModel.attribute),
                    selectinload(ProductVariantAttributeValueModel.value),
                ),
                selectinload(ProductModel.variants).selectinload(ProductVariantModel.identifiers),
                selectinload(ProductModel.variants).selectinload(ProductVariantModel.image),
            )
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()
        return _to_product(orm) if orm else None

    async def get_product_by_sku(self, company_id: uuid.UUID, sku: str) -> Product | None:
        stmt = (
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.sku == sku)
            .options(
                noload(ProductModel.images),
                noload(ProductModel.identifiers),
                noload(ProductModel.supplier_links),
                noload(ProductModel.variants),
                noload(ProductModel.variant_attributes),
            )
        )
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
        variant_config: ProductVariantConfigDraft | None = None,
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
            dimension_length=dimension_length,
            dimension_width=dimension_width,
            dimension_height=dimension_height,
            dimension_unit=dimension_unit,
            weight=weight,
            weight_unit=weight_unit,
            description=description,
            presentation=presentation,
            product_kind=product_kind,
            lifecycle_status=lifecycle_status,
            can_purchase=can_purchase,
            can_sell=can_sell,
            sales_name=sales_name,
            internal_name=internal_name,
            document_name=document_name,
            sales_description=sales_description,
            purchase_description=purchase_description,
            internal_notes=internal_notes,
            keywords=keywords or [],
            origin_country_id=origin_country_id,
            brand_id=brand_id,
            manufacturer_id=manufacturer_id,
            storage_condition=storage_condition,
            storage_temperature_min_c=storage_temperature_min_c,
            storage_temperature_max_c=storage_temperature_max_c,
            storage_humidity_max_percent=storage_humidity_max_percent,
            is_fragile=is_fragile,
            keep_dry=keep_dry,
            keep_upright=keep_upright,
            stackable=stackable,
            max_stack_height=max_stack_height,
            handling_notes=handling_notes,
            is_active=is_active,
        )
        self._session.add(orm)
        await self._session.flush()
        normalized_sku = sku.strip().casefold()
        existing_sku = await self._session.scalar(
            select(ProductSkuRegistryModel)
            .where(
                ProductSkuRegistryModel.company_id == company_id,
                ProductSkuRegistryModel.normalized_sku == normalized_sku,
            )
            .with_for_update()
        )
        if existing_sku is not None:
            raise ValueError(f"El SKU '{sku}' ya está registrado en esta empresa.")
        self._session.add(
            ProductSkuRegistryModel(
                company_id=company_id,
                normalized_sku=normalized_sku,
                product_id=orm.id_product,
            )
        )
        await self._session.flush()
        if images is not None:
            await self._sync_product_images(orm, company_id, images)
        if variant_config is not None:
            await self._sync_variant_config(orm, company_id, variant_config)
        return await self._get_product_with_images(company_id, orm.id_product)

    async def update_product(
        self, company_id: uuid.UUID, product_id: int, **kwargs
    ) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.company_id == company_id, ProductModel.id_product == product_id
        )
        res = await self._session.execute(
            stmt.options(
                selectinload(ProductModel.images),
                selectinload(ProductModel.identifiers),
                selectinload(ProductModel.supplier_links),
            )
        )
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
        variant_config = kwargs.pop("variant_config", None) if "variant_config" in kwargs else None
        old_sku = orm.sku
        for key, value in kwargs.items():
            orm_field = field_map.get(key, key)
            if hasattr(orm, orm_field):
                setattr(orm, orm_field, value)
        await self._session.flush()
        if orm.sku != old_sku:
            normalized_sku = orm.sku.strip().casefold()
            target_registry = await self._session.scalar(
                select(ProductSkuRegistryModel)
                .where(
                    ProductSkuRegistryModel.company_id == company_id,
                    ProductSkuRegistryModel.normalized_sku == normalized_sku,
                )
                .with_for_update()
            )
            if target_registry is not None and target_registry.product_id != product_id:
                raise ValueError(f"El SKU '{orm.sku}' ya está registrado en esta empresa.")
            registry = await self._session.scalar(
                select(ProductSkuRegistryModel)
                .where(
                    ProductSkuRegistryModel.company_id == company_id,
                    ProductSkuRegistryModel.product_id == product_id,
                )
                .with_for_update()
            )
            if registry is not None:
                registry.normalized_sku = normalized_sku
            else:
                self._session.add(
                    ProductSkuRegistryModel(
                        company_id=company_id,
                        normalized_sku=normalized_sku,
                        product_id=product_id,
                    )
                )
            await self._session.flush()
        if images is not None:
            await self._sync_product_images(orm, company_id, images)
        if variant_config is not None:
            await self._sync_variant_config(orm, company_id, variant_config)
        return await self._get_product_with_images(company_id, product_id)

    async def _get_product_with_images(self, company_id: uuid.UUID, product_id: int) -> Product:
        result = await self._session.execute(
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(ProductModel.images),
                selectinload(ProductModel.identifiers),
                selectinload(ProductModel.supplier_links),
                selectinload(ProductModel.variant_attributes).selectinload(
                    ProductFamilyAttributeModel.values
                ),
                selectinload(ProductModel.variants)
                .selectinload(ProductVariantModel.attribute_values)
                .options(
                    selectinload(ProductVariantAttributeValueModel.attribute),
                    selectinload(ProductVariantAttributeValueModel.value),
                ),
                selectinload(ProductModel.variants).selectinload(ProductVariantModel.identifiers),
                selectinload(ProductModel.variants).selectinload(ProductVariantModel.image),
            )
        )
        orm = result.scalar_one()
        # ``replace_variant_config`` may have created family attributes in the
        # same AsyncSession.  SQLAlchemy can keep those newly-added children in
        # an unloaded relationship even after the parent query's selectinload,
        # which would make ``_to_family_attribute`` trigger an implicit lazy
        # load (and MissingGreenlet) while serializing the response.  Reload
        # the family graph explicitly and attach it to the instance dictionary
        # so response mapping never performs I/O.
        attributes_result = await self._session.execute(
            select(ProductFamilyAttributeModel)
            .where(
                ProductFamilyAttributeModel.company_id == company_id,
                ProductFamilyAttributeModel.product_id == product_id,
            )
            .options(selectinload(ProductFamilyAttributeModel.values))
            .order_by(ProductFamilyAttributeModel.position)
        )
        orm.__dict__["variant_attributes"] = list(attributes_result.scalars().all())
        return _to_product(orm)

    async def _sync_product_images(
        self, product: ProductModel, company_id: uuid.UUID, drafts: list[ProductImageDraft]
    ) -> None:
        """Replace a product gallery atomically and claim staged media assets."""
        existing = (
            (
                await self._session.execute(
                    select(ProductImageModel).where(
                        ProductImageModel.product_id == product.id_product
                    )
                )
            )
            .scalars()
            .all()
        )
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
                    raise ValueError(
                        "El asset Cloudinary no existe, no pertenece a la empresa o ya fue usado."
                    )
                if asset.owner_id not in (None, product.uuid) or asset.owner_type not in (
                    None,
                    "product",
                ):
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

    async def get_variant(
        self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID
    ) -> ProductVariant | None:
        stmt = (
            select(ProductVariantModel)
            .where(
                ProductVariantModel.company_id == company_id,
                ProductVariantModel.product_id == product_id,
                ProductVariantModel.id == variant_id,
            )
            .options(
                selectinload(ProductVariantModel.attribute_values).options(
                    selectinload(ProductVariantAttributeValueModel.attribute),
                    selectinload(ProductVariantAttributeValueModel.value),
                ),
                selectinload(ProductVariantModel.identifiers),
                selectinload(ProductVariantModel.image),
            )
        )
        variant = await self._session.scalar(stmt)
        if variant is None:
            return None
        parent = await self._session.scalar(
            select(ProductModel).where(
                ProductModel.company_id == company_id,
                ProductModel.id_product == product_id,
            )
        )
        return _to_variant(variant, parent.name if parent else "")

    async def update_variant(  # noqa: C901 - one transaction validates all variant fields
        self,
        company_id: uuid.UUID,
        product_id: int,
        variant_id: uuid.UUID,
        draft: ProductVariantUpdateDraft,
    ) -> ProductVariant | None:
        """Update one variant without replacing the family graph."""
        parent = await self._session.scalar(
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
            .with_for_update()
        )
        if parent is None:
            return None

        variant = await self._session.scalar(
            select(ProductVariantModel)
            .where(
                ProductVariantModel.company_id == company_id,
                ProductVariantModel.product_id == product_id,
                ProductVariantModel.id == variant_id,
            )
            .options(
                selectinload(ProductVariantModel.attribute_values).options(
                    selectinload(ProductVariantAttributeValueModel.attribute),
                    selectinload(ProductVariantAttributeValueModel.value),
                ),
                selectinload(ProductVariantModel.identifiers),
                selectinload(ProductVariantModel.image),
            )
            .with_for_update()
        )
        if variant is None:
            return None
        if variant.updated_at != draft.expected_updated_at:
            raise ConcurrencyError(
                "La variante fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
                code="variant_stale",
            )

        fields = draft.provided_fields
        if "sku" in fields:
            sku = draft.sku or ""
            normalized_sku = sku.casefold()
            matching_registries = (
                (
                    await self._session.execute(
                        select(ProductSkuRegistryModel)
                        .where(
                            ProductSkuRegistryModel.company_id == company_id,
                            ProductSkuRegistryModel.normalized_sku == normalized_sku,
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            target_registry = next(
                (registry for registry in matching_registries if registry.variant_id == variant.id),
                None,
            )
            if any(registry.variant_id != variant.id for registry in matching_registries):
                raise ValueError(f"El SKU '{sku}' ya está registrado en esta empresa.")
            old_normalized_sku = variant.sku.casefold()
            if target_registry is None and old_normalized_sku != normalized_sku:
                old_registry = await self._session.scalar(
                    select(ProductSkuRegistryModel)
                    .where(
                        ProductSkuRegistryModel.company_id == company_id,
                        ProductSkuRegistryModel.normalized_sku == old_normalized_sku,
                        ProductSkuRegistryModel.variant_id == variant.id,
                    )
                    .with_for_update()
                )
                if old_registry is not None:
                    old_registry.normalized_sku = normalized_sku
                else:
                    self._session.add(
                        ProductSkuRegistryModel(
                            company_id=company_id,
                            normalized_sku=normalized_sku,
                            variant_id=variant.id,
                        )
                    )
            elif target_registry is None:
                self._session.add(
                    ProductSkuRegistryModel(
                        company_id=company_id,
                        normalized_sku=normalized_sku,
                        variant_id=variant.id,
                    )
                )
            variant.sku = sku

        if "name_override" in fields:
            variant.name_override = draft.name_override

        if "lifecycle_status" in fields:
            lifecycle_status = draft.lifecycle_status
            if lifecycle_status == "active" and parent.lifecycle_status != "active":
                raise ValueError(
                    "No se puede activar una variante si el producto padre no está activo."
                )
            variant.lifecycle_status = lifecycle_status
            variant.is_active = lifecycle_status == "active"

        if "identifiers" in fields:
            identifiers = draft.identifiers or ()
            seen_identifiers: set[tuple[str, str]] = set()
            for identifier in identifiers:
                normalized = "".join(ch for ch in identifier.value if ch.isalnum()).upper()
                key = (identifier.identifier_type, normalized)
                if key in seen_identifiers:
                    raise ValueError("La variante no puede repetir identificadores.")
                seen_identifiers.add(key)
                matching_identifiers = (
                    (
                        await self._session.execute(
                            select(ProductIdentifierModel)
                            .where(
                                ProductIdentifierModel.company_id == company_id,
                                ProductIdentifierModel.identifier_type
                                == identifier.identifier_type,
                                ProductIdentifierModel.normalized_value == normalized,
                            )
                            .with_for_update()
                        )
                    )
                    .scalars()
                    .all()
                )
                if any(
                    existing_identifier.variant_id != variant.id
                    for existing_identifier in matching_identifiers
                ):
                    raise ValueError("El identificador ya está registrado en esta empresa.")
            if sum(1 for item in identifiers if item.is_primary) > len(
                {item.identifier_type for item in identifiers if item.is_primary}
            ):
                raise ValueError("Solo puede existir un identificador principal por tipo.")
            await self._session.execute(
                delete(ProductIdentifierModel).where(
                    ProductIdentifierModel.variant_id == variant.id
                )
            )
            await self._session.flush()
            for identifier in identifiers:
                self._session.add(
                    ProductIdentifierModel(
                        company_id=company_id,
                        product_id=None,
                        variant_id=variant.id,
                        identifier_type=identifier.identifier_type,
                        value=identifier.value,
                        normalized_value="".join(
                            ch for ch in identifier.value if ch.isalnum()
                        ).upper(),
                        is_primary=identifier.is_primary,
                    )
                )

        if "image" in fields:
            await self._sync_variant_image(variant, company_id, draft.image)

        variant.updated_at = datetime.now(UTC)
        await self._session.flush()
        return await self.get_variant(company_id, product_id, variant_id)

    async def replace_variant_config(
        self,
        company_id: uuid.UUID,
        product_id: int,
        config: ProductVariantConfigDraft,
    ) -> Product:
        parent = await self._session.scalar(
            select(ProductModel)
            .where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
            .with_for_update()
        )
        if parent is None:
            return None  # type: ignore[return-value]
        await self._sync_variant_config(parent, company_id, config)
        return await self._get_product_with_images(company_id, product_id)

    async def _sync_variant_config(  # noqa: C901 - family replacement validates a graph atomically
        self,
        product: ProductModel,
        company_id: uuid.UUID,
        config: ProductVariantConfigDraft,
    ) -> None:
        """Replace a family graph while preserving retired variant history."""
        if not config.attributes or not config.variants:
            raise ValueError("Una familia debe tener atributos y al menos una variante.")
        if (
            len(config.attributes) > MAX_VARIANT_ATTRIBUTES
            or len(config.variants) > MAX_VARIANTS_PER_FAMILY
        ):
            raise ValueError("Una familia admite como máximo 5 atributos y 500 variantes.")

        existing_attributes = (
            (
                await self._session.execute(
                    select(ProductFamilyAttributeModel)
                    .where(
                        ProductFamilyAttributeModel.company_id == company_id,
                        ProductFamilyAttributeModel.product_id == product.id_product,
                    )
                    .options(selectinload(ProductFamilyAttributeModel.values))
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        attributes_by_code = {
            normalize_variant_token(item.code): item for item in existing_attributes
        }
        incoming_attributes: dict[str, ProductFamilyAttributeModel] = {}
        value_maps: dict[str, dict[str, ProductFamilyAttributeValueModel]] = {}

        for position, attribute_draft in enumerate(config.attributes):
            code = normalize_variant_token(attribute_draft.code)
            if not code or code in incoming_attributes:
                raise ValueError("Los atributos de una familia deben tener códigos únicos.")
            normalized_value_codes = [
                normalize_variant_token(value.code) for value in attribute_draft.values
            ]
            if not attribute_draft.values or len(set(normalized_value_codes)) != len(
                normalized_value_codes
            ):
                raise ValueError("Cada atributo debe tener valores únicos y no vacíos.")
            attribute = attributes_by_code.get(code)
            # A newly-created SQLAlchemy relationship is not populated yet.
            # Reading ``attribute.values`` here would trigger an implicit lazy
            # load, which is not allowed outside a greenlet in AsyncSession
            # and surfaced as a 500 on the first variant configuration.
            attribute_values = []
            if attribute is None:
                attribute = ProductFamilyAttributeModel(
                    company_id=company_id,
                    product_id=product.id_product,
                    code=code,
                    name=attribute_draft.name,
                    position=position,
                    is_active=True,
                )
                self._session.add(attribute)
                await self._session.flush()
            else:
                attribute.name = attribute_draft.name
                attribute.position = position
                attribute.is_active = True
                attribute_values = list(attribute.values or [])
            incoming_attributes[code] = attribute
            value_maps[code] = {
                normalize_variant_token(value.code): value for value in attribute_values
            }
            incoming_value_codes: set[str] = set()
            for value_position, value_draft in enumerate(attribute_draft.values):
                value_code = normalize_variant_token(value_draft.code)
                if not value_code or value_code in incoming_value_codes:
                    raise ValueError("Los valores de un atributo deben tener códigos únicos.")
                incoming_value_codes.add(value_code)
                value = value_maps[code].get(value_code)
                if value is None:
                    value = ProductFamilyAttributeValueModel(
                        company_id=company_id,
                        product_id=product.id_product,
                        attribute_id=attribute.id,
                        code=value_code,
                        label=value_draft.label,
                        normalized_label=normalize_variant_token(value_draft.label),
                        position=value_position,
                        is_active=True,
                    )
                    self._session.add(value)
                else:
                    value.label = value_draft.label
                    value.normalized_label = normalize_variant_token(value_draft.label)
                    value.position = value_position
                    value.is_active = True
                value_maps[code][value_code] = value
            for old_code, old_value in value_maps[code].copy().items():
                if old_code not in incoming_value_codes:
                    old_value.is_active = False

        for old_code, old_attribute in attributes_by_code.items():
            if old_code not in incoming_attributes:
                old_attribute.is_active = False
        await self._session.flush()

        existing_variants = (
            (
                await self._session.execute(
                    select(ProductVariantModel)
                    .where(
                        ProductVariantModel.company_id == company_id,
                        ProductVariantModel.product_id == product.id_product,
                    )
                    .options(
                        selectinload(ProductVariantModel.attribute_values),
                        selectinload(ProductVariantModel.identifiers),
                        selectinload(ProductVariantModel.image),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        by_id = {item.id: item for item in existing_variants}
        by_combination = {item.combination_key: item for item in existing_variants}
        requested_ids = {draft.id for draft in config.variants if draft.id is not None}
        if requested_ids:
            referenced_variants = (
                await self._session.execute(
                    select(ProductVariantModel.id, ProductVariantModel.product_id).where(
                        ProductVariantModel.company_id == company_id,
                        ProductVariantModel.id.in_(requested_ids),
                    )
                )
            ).all()
            referenced_ids = {row.id for row in referenced_variants}
            if referenced_ids != requested_ids or any(
                row.product_id != product.id_product for row in referenced_variants
            ):
                raise ValueError("Una variante referenciada no pertenece a este producto.")
        seen_ids: set[uuid.UUID] = set()
        seen_combinations: set[str] = set()
        seen_skus: set[str] = set()

        for variant_draft in config.variants:
            assignment_rows: list[
                tuple[ProductFamilyAttributeModel, ProductFamilyAttributeValueModel]
            ] = []
            seen_attribute_codes: set[str] = set()
            for assignment in variant_draft.values:
                attribute_code = normalize_variant_token(assignment.attribute_code)
                value_code = normalize_variant_token(assignment.value_code)
                if (
                    attribute_code in seen_attribute_codes
                    or attribute_code not in incoming_attributes
                ):
                    raise ValueError("La variante contiene un atributo inválido o repetido.")
                value = value_maps[attribute_code].get(value_code)
                if value is None or not value.is_active:
                    raise ValueError("La variante contiene un valor inválido.")
                seen_attribute_codes.add(attribute_code)
                assignment_rows.append((incoming_attributes[attribute_code], value))
            if seen_attribute_codes != set(incoming_attributes):
                raise ValueError("Cada variante debe definir exactamente un valor por atributo.")
            combination_key = "|".join(
                f"{attribute.id}:{value.id}"
                for attribute, value in sorted(assignment_rows, key=lambda item: item[0].position)
            )
            if combination_key in seen_combinations:
                raise ValueError("La familia contiene combinaciones repetidas.")
            seen_combinations.add(combination_key)

            sku = variant_draft.sku.strip()
            normalized_sku = sku.casefold()
            if normalized_sku in seen_skus:
                raise ValueError(f"El SKU de variante '{sku}' está repetido.")
            seen_skus.add(normalized_sku)
            variant = (
                by_id.get(variant_draft.id)
                if variant_draft.id
                else by_combination.get(combination_key)
            )
            if variant is not None and variant.product_id != product.id_product:
                raise ValueError("La variante no pertenece a este producto.")
            old_normalized_sku = variant.sku.casefold() if variant is not None else None
            if variant is None:
                variant = ProductVariantModel(
                    company_id=company_id,
                    product_id=product.id_product,
                    sku=sku,
                    combination_key=combination_key,
                    name_override=variant_draft.name_override,
                    lifecycle_status=variant_draft.lifecycle_status,
                    is_active=variant_draft.lifecycle_status == "active",
                )
                self._session.add(variant)
                await self._session.flush()
            else:
                variant.sku = sku
                variant.combination_key = combination_key
                variant.name_override = variant_draft.name_override
                variant.lifecycle_status = variant_draft.lifecycle_status
                variant.is_active = variant_draft.lifecycle_status == "active"
            if variant.is_active and product.lifecycle_status != "active":
                raise ValueError("No se puede activar una variante si la familia no está activa.")
            seen_ids.add(variant.id)

            registry = await self._session.scalar(
                select(ProductSkuRegistryModel)
                .where(
                    ProductSkuRegistryModel.company_id == company_id,
                    ProductSkuRegistryModel.normalized_sku == normalized_sku,
                )
                .with_for_update()
            )
            if registry is not None and registry.variant_id != variant.id:
                raise ValueError(f"El SKU '{sku}' ya está registrado en esta empresa.")
            if registry is None:
                old_registry = None
                if old_normalized_sku and old_normalized_sku != normalized_sku:
                    old_registry = await self._session.scalar(
                        select(ProductSkuRegistryModel)
                        .where(
                            ProductSkuRegistryModel.company_id == company_id,
                            ProductSkuRegistryModel.normalized_sku == old_normalized_sku,
                            ProductSkuRegistryModel.variant_id == variant.id,
                        )
                        .with_for_update()
                    )
                if old_registry is not None:
                    old_registry.normalized_sku = normalized_sku
                else:
                    self._session.add(
                        ProductSkuRegistryModel(
                            company_id=company_id,
                            normalized_sku=normalized_sku,
                            variant_id=variant.id,
                        )
                    )
            elif old_normalized_sku and old_normalized_sku != normalized_sku:
                old_registry = await self._session.scalar(
                    select(ProductSkuRegistryModel)
                    .where(
                        ProductSkuRegistryModel.company_id == company_id,
                        ProductSkuRegistryModel.normalized_sku == old_normalized_sku,
                        ProductSkuRegistryModel.variant_id == variant.id,
                    )
                    .with_for_update()
                )
                if old_registry is not None and old_registry.id != registry.id:
                    await self._session.delete(old_registry)

            await self._session.execute(
                delete(ProductVariantAttributeValueModel).where(
                    ProductVariantAttributeValueModel.variant_id == variant.id
                )
            )
            await self._session.flush()
            for attribute, value in assignment_rows:
                self._session.add(
                    ProductVariantAttributeValueModel(
                        company_id=company_id,
                        product_id=product.id_product,
                        variant_id=variant.id,
                        attribute_id=attribute.id,
                        value_id=value.id,
                    )
                )

            old_identifiers = (
                (
                    await self._session.execute(
                        select(ProductIdentifierModel).where(
                            ProductIdentifierModel.company_id == company_id,
                            ProductIdentifierModel.variant_id == variant.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for identifier in old_identifiers:
                await self._session.delete(identifier)
            await self._session.flush()
            for identifier_draft in variant_draft.identifiers:
                normalized = "".join(ch for ch in identifier_draft.value if ch.isalnum()).upper()
                self._session.add(
                    ProductIdentifierModel(
                        company_id=company_id,
                        product_id=None,
                        variant_id=variant.id,
                        identifier_type=identifier_draft.identifier_type,
                        value=identifier_draft.value.strip(),
                        normalized_value=normalized,
                        is_primary=identifier_draft.is_primary,
                    )
                )
            await self._sync_variant_image(variant, company_id, variant_draft.image)
            await self._session.flush()

        for variant in existing_variants:
            if variant.id not in seen_ids:
                variant.lifecycle_status = "retired"
                variant.is_active = False
        product.variant_mode = "template"
        await self._session.flush()

    async def _sync_variant_image(
        self,
        variant: ProductVariantModel,
        company_id: uuid.UUID,
        draft: ProductVariantImageDraft | None,
    ) -> None:
        existing = await self._session.scalar(
            select(ProductVariantImageModel).where(
                ProductVariantImageModel.variant_id == variant.id
            )
        )
        if existing is not None:
            if existing.media_asset_id and (
                draft is None or existing.media_asset_id != draft.media_asset_id
            ):
                asset = await self._session.get(MediaAsset, existing.media_asset_id)
                if asset is not None:
                    asset.status = "detached"
                    asset.owner_type = None
                    asset.owner_id = None
            await self._session.delete(existing)
            await self._session.flush()
        if draft is None:
            return
        source_type = draft.source_type.strip().lower()
        if source_type == "cloudinary":
            asset = await self._session.scalar(
                select(MediaAsset).where(
                    MediaAsset.id == draft.media_asset_id,
                    MediaAsset.company_id == company_id,
                    MediaAsset.purpose == "product_image",
                    MediaAsset.status.in_(("staged", "active")),
                )
            )
            if asset is None:
                raise ValueError(
                    "El asset Cloudinary de la variante no existe o no pertenece a la empresa."
                )
            if asset.owner_id not in (None, variant.id) or asset.owner_type not in (
                None,
                "product_variant",
            ):
                raise ValueError("El asset Cloudinary ya está asociado a otro recurso.")
            asset.status = "active"
            asset.owner_type = "product_variant"
            asset.owner_id = variant.id
            url = asset.secure_url
        else:
            url = draft.url.strip()
        self._session.add(
            ProductVariantImageModel(
                variant_id=variant.id,
                media_asset_id=draft.media_asset_id,
                source_type=source_type,
                url=url,
                alt_text=draft.alt_text.strip() if draft.alt_text else None,
            )
        )
        await self._session.flush()

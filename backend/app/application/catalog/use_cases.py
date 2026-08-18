"""Application use cases for Catalog: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid

from app.core.exceptions import ConcurrencyError, ConflictError, NotFoundError, ValidationError
from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit
from app.domain.entities.product_image import (
    ProductImageDraft,
    normalize_product_image_drafts,
)
from app.domain.entities.product_variants import (
    ProductVariantConfigDraft,
    ProductVariantUpdateDraft,
)
from app.domain.ports.catalog_repository import CatalogRepository
from app.domain.product_master import normalize_keywords
from app.domain.product_measurements import validate_measurements
from app.domain.product_variants import normalize_variant_config, normalize_variant_update


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
    async def list_categories(self, company_id: uuid.UUID, active_only: bool = True) -> list[Category]:
        return await self._repo.list_categories(company_id, active_only=active_only)

    async def get_category(self, company_id: uuid.UUID, category_id: int) -> Category:
        category = await self._repo.get_category_by_id(company_id, category_id)
        if not category:
            raise NotFoundError("Categoría no encontrada", code="category_not_found")
        return category

    async def create_category(self, company_id: uuid.UUID, name: str, description: str | None = None) -> Category:
        return await self._repo.create_category(company_id, name=name, description=description)

    async def update_category(
        self, company_id: uuid.UUID, category_id: int, **changes: object
    ) -> Category:
        if changes.get("name") is None and "name" in changes:
            raise ValidationError("El nombre de la categoría es obligatorio.", code="category_name_required")
        category = await self._repo.update_category(company_id, category_id, **changes)
        if not category:
            raise NotFoundError("Categoría no encontrada", code="category_not_found")
        return category

    # --- SubCategories ---
    async def list_sub_categories(self, company_id: uuid.UUID, category_id: int | None = None, active_only: bool = True) -> list[SubCategory]:
        return await self._repo.list_sub_categories(company_id, category_id=category_id, active_only=active_only)

    async def get_sub_category(self, company_id: uuid.UUID, sub_category_id: int) -> SubCategory:
        sub_category = await self._repo.get_sub_category_by_id(company_id, sub_category_id)
        if not sub_category:
            raise NotFoundError("SubcategorÃ­a no encontrada", code="sub_category_not_found")
        return sub_category

    async def create_sub_category(self, company_id: uuid.UUID, category_id: int, name: str, description: str | None = None) -> SubCategory:
        await self.get_category(company_id, category_id)
        return await self._repo.create_sub_category(company_id, category_id=category_id, name=name, description=description)

    async def update_sub_category(
        self, company_id: uuid.UUID, sub_category_id: int, **changes: object
    ) -> SubCategory:
        if changes.get("name") is None and "name" in changes:
            raise ValidationError("El nombre de la subcategoría es obligatorio.", code="subcategory_name_required")
        sub = await self._repo.update_sub_category(company_id, sub_category_id, **changes)
        if not sub:
            raise NotFoundError("Subcategoría no encontrada", code="sub_category_not_found")
        return sub

    # --- Units ---
    async def list_units(self, company_id: uuid.UUID, active_only: bool = True) -> list[Unit]:
        return await self._repo.list_units(company_id, active_only=active_only)

    async def list_global_units(self, active_only: bool = False) -> list[Unit]:
        return await self._repo.list_global_units(active_only=active_only)

    async def get_unit(self, company_id: uuid.UUID, unit_id: int, *, require_enabled: bool = False) -> Unit:
        unit = await self._repo.get_unit_by_id(company_id, unit_id, require_enabled=require_enabled)
        if not unit:
            raise NotFoundError("Unidad de medida no disponible para esta empresa", code="unit_not_available")
        return unit

    async def create_unit(
        self,
        company_id: uuid.UUID | None,
        *,
        name: str,
        type_: str,
        code: str,
        symbol: str,
        description: str | None = None,
    ) -> Unit:
        if await self._repo.get_unit_by_code(company_id, code):
            raise ConflictError(
                f"El código '{code.strip().upper()}' ya está registrado o reservado por una unidad estándar.",
                code="unit_code_already_exists",
            )
        return await self._repo.create_unit(
            company_id,
            name=name,
            type_=type_,
            code=code,
            symbol=symbol,
            description=description,
        )

    async def update_unit(
        self,
        company_id: uuid.UUID | None,
        unit_id: int,
        expected_version: int,
        **changes: object,
    ) -> Unit:
        if changes.get("is_active") is False:
            usage = await self._repo.count_unit_usage(unit_id, company_id)
            if usage:
                raise ConflictError(
                    f"La unidad está vinculada a {usage} producto(s) y no puede desactivarse.",
                    code="unit_in_use",
                )
        unit = await self._repo.update_unit(company_id, unit_id, expected_version, **changes)
        if not unit:
            raise ConcurrencyError(
                "La unidad fue modificada por otro usuario o ya no está disponible. Recargue e intente de nuevo.",
                code="unit_version_conflict",
            )
        return unit

    async def configure_unit(
        self,
        company_id: uuid.UUID,
        unit_id: int,
        expected_version: int,
        *,
        enabled: bool,
        alias: str | None = None,
    ) -> Unit:
        current = await self.get_unit(company_id, unit_id)
        if not enabled and current.usage_count > 0:
            raise ConflictError(
                f"La unidad está vinculada a {current.usage_count} producto(s) y no puede desactivarse.",
                code="unit_in_use",
            )
        updated = await self._repo.configure_unit(
            company_id, unit_id, expected_version, enabled=enabled, alias=alias
        )
        if not updated:
            raise ConcurrencyError(
                "La configuración fue modificada por otro usuario. Recargue e intente de nuevo.",
                code="unit_version_conflict",
            )
        return updated

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
        return await self._repo.list_products(
            company_id,
            category_id=category_id,
            sub_category_id=sub_category_id,
            search=search,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )

    async def get_product(self, company_id: uuid.UUID, product_id: int) -> Product:
        product = await self._repo.get_product_by_id(company_id, product_id)
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

    async def get_product_by_uuid(self, company_id: uuid.UUID, prod_uuid: uuid.UUID) -> Product:
        product = await self._repo.get_product_by_uuid(company_id, prod_uuid)
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

    async def get_variant(self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID):
        variant = await self._repo.get_variant(company_id, product_id, variant_id)
        if not variant:
            raise NotFoundError("Variante no encontrada", code="product_variant_not_found")
        return variant

    async def update_variant(
        self,
        company_id: uuid.UUID,
        product_id: int,
        variant_id: uuid.UUID,
        draft: ProductVariantUpdateDraft,
    ):
        try:
            return await self._repo.update_variant(
                company_id,
                product_id,
                variant_id,
                normalize_variant_update(draft),
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_variant_invalid") from exc

    async def replace_variant_config(
        self,
        company_id: uuid.UUID,
        product_id: int,
        variant_config: ProductVariantConfigDraft,
    ) -> Product:
        try:
            product = await self._repo.replace_variant_config(
                company_id,
                product_id,
                self._normalize_variant_config(variant_config),
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_variants_invalid") from exc
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

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
        images: list[ProductImageDraft] | None = None,
        variant_config: ProductVariantConfigDraft | None = None,
    ) -> Product:
        # Validate unique SKU
        existing = await self._repo.get_product_by_sku(company_id, sku)
        if existing:
            raise ConflictError(f"El SKU '{sku}' ya está registrado", code="sku_already_exists")

        # Validate category and units exist
        await self.get_category(company_id, category_id)
        if sub_category_id is not None:
            sub = await self._repo.get_sub_category_by_id(company_id, sub_category_id)
            if not sub:
                raise NotFoundError("Subcategoría no encontrada", code="sub_category_not_found")
            if sub.category_id != category_id:
                raise ValidationError(
                    "La subcategoría no pertenece a la categoría seleccionada.",
                    code="subcategory_category_mismatch",
                )

        unit_p = await self._repo.get_unit_by_id(company_id, purchase_unit_id, require_enabled=True)
        if not unit_p:
            raise NotFoundError("Unidad de compra no encontrada", code="purchase_unit_not_found")

        unit_s = await self._repo.get_unit_by_id(company_id, sale_unit_id, require_enabled=True)
        if not unit_s:
            raise NotFoundError("Unidad de venta no encontrada", code="sale_unit_not_found")

        try:
            length, width, height, product_weight = validate_measurements(
                dimension_length=dimension_length,
                dimension_width=dimension_width,
                dimension_height=dimension_height,
                dimension_unit=dimension_unit,
                weight=weight,
                weight_unit=weight_unit,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_measurements_invalid") from exc

        normalized_images = self._normalize_images(images)
        normalized_variants = self._normalize_variant_config(variant_config)
        try:
            normalized_keywords = normalize_keywords(keywords)
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_keywords_invalid") from exc
        if (product_kind == "service" and any(
            value is not None for value in (storage_condition, storage_temperature_min_c, storage_temperature_max_c, storage_humidity_max_percent, max_stack_height, handling_notes)
        )) or (product_kind == "service" and (not stackable or any((is_fragile, keep_dry, keep_upright)))):
            raise ValidationError("Los datos de almacenamiento solo aplican a bienes físicos.", code="product_service_storage_invalid")
        is_active = lifecycle_status in ("active",)
        try:
            return await self._repo.create_product(
                company_id,
                category_id=category_id,
                sub_category_id=sub_category_id,
                sku=sku,
                name=name,
                purchase_unit_id=purchase_unit_id,
                sale_unit_id=sale_unit_id,
                original_code=original_code,
                internal_code=internal_code,
                size=size,
                dimension_length=length,
                dimension_width=width,
                dimension_height=height,
                dimension_unit=dimension_unit,
                weight=product_weight,
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
                keywords=normalized_keywords,
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
                images=normalized_images,
                variant_config=normalized_variants,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_variants_invalid") from exc

    async def update_product(self, company_id: uuid.UUID, product_id: int, **changes: object) -> Product:  # noqa: C901
        changes = dict(changes)
        current = await self.get_product(company_id, product_id)
        images_provided, normalized_images = self._extract_images(changes)
        variants_provided = "variant_config" in changes
        normalized_variants = self._normalize_variant_config(changes.pop("variant_config", None)) if variants_provided else None
        required = ("category_id", "sku", "name", "purchase_unit_id", "sale_unit_id")
        if any(field in changes and changes[field] is None for field in required):
            raise ValidationError("No se puede vaciar un campo obligatorio del producto.", code="product_required_field")

        category_id = int(changes.get("category_id", current.category_id))
        await self.get_category(company_id, category_id)
        sub_category_id = changes.get("sub_category_id", current.sub_category_id)
        if sub_category_id is not None:
            sub = await self._repo.get_sub_category_by_id(company_id, int(sub_category_id))
            if not sub:
                raise NotFoundError("Subcategoría no encontrada", code="sub_category_not_found")
            if sub.category_id != category_id:
                raise ValidationError(
                    "La subcategoría no pertenece a la categoría seleccionada.",
                    code="subcategory_category_mismatch",
                )
        for field, code in (("purchase_unit_id", "purchase_unit_not_found"), ("sale_unit_id", "sale_unit_not_found")):
            unit_id = int(changes.get(field, getattr(current, field)))
            if await self._repo.get_unit_by_id(company_id, unit_id, require_enabled=True) is None:
                raise NotFoundError("Unidad de medida no encontrada", code=code)
        if "sku" in changes:
            duplicate = await self._repo.get_product_by_sku(company_id, str(changes["sku"]))
            if duplicate and duplicate.id != product_id:
                raise ConflictError("El SKU ya está registrado en esta empresa.", code="sku_already_exists")

        changes = self._validate_measurement_changes(current, changes)

        if "keywords" in changes:
            try:
                changes["keywords"] = normalize_keywords(changes["keywords"])
            except ValueError as exc:
                raise ValidationError(str(exc), code="product_keywords_invalid") from exc
        effective_kind = str(changes.get("product_kind", current.product_kind))
        storage_keys = ("storage_condition", "storage_temperature_min_c", "storage_temperature_max_c", "storage_humidity_max_percent", "max_stack_height", "handling_notes", "is_fragile", "keep_dry", "keep_upright")
        if effective_kind == "service" and (changes.get("stackable", current.stackable) is False or any(changes.get(key, getattr(current, key)) not in (None, False) for key in storage_keys)):
            raise ValidationError("Los datos de almacenamiento solo aplican a bienes físicos.", code="product_service_storage_invalid")
        if "lifecycle_status" in changes:
            if current.lifecycle_status == "retired" and changes["lifecycle_status"] == "active":
                raise ConflictError(
                    "Un producto retirado no puede reactivarse; cree una nueva ficha.",
                    code="product_retired_immutable",
                )
            changes["is_active"] = changes["lifecycle_status"] == "active"
        elif "is_active" in changes and changes["is_active"] is not None:
            if current.lifecycle_status == "retired" and changes["is_active"]:
                raise ConflictError(
                    "Un producto retirado no puede reactivarse; cree una nueva ficha.",
                    code="product_retired_immutable",
                )
            changes["lifecycle_status"] = "active" if changes["is_active"] else "blocked"

        repository_changes = dict(changes)
        if images_provided:
            repository_changes["images"] = normalized_images
        if variants_provided:
            repository_changes["variant_config"] = normalized_variants
        try:
            product = await self._repo.update_product(company_id, product_id, **repository_changes)
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_variants_invalid") from exc
        if not product:
            raise NotFoundError("Producto no encontrado", code="product_not_found")
        return product

    @staticmethod
    def _validate_measurement_changes(current: Product, changes: dict[str, object]) -> dict[str, object]:
        measurement_fields = {
            "dimension_length",
            "dimension_width",
            "dimension_height",
            "dimension_unit",
            "weight",
            "weight_unit",
        }
        if not measurement_fields.intersection(changes):
            return changes
        if changes.get("weight", object()) is None and "weight_unit" not in changes:
            changes["weight_unit"] = None
        dimension_names = ("dimension_length", "dimension_width", "dimension_height")
        if all(changes.get(field, object()) is None for field in dimension_names) and "dimension_unit" not in changes:
            changes["dimension_unit"] = None
        effective = {
            field: changes[field] if field in changes else getattr(current, field)
            for field in measurement_fields
        }
        try:
            length, width, height, product_weight = validate_measurements(**effective)
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_measurements_invalid") from exc
        # Explicitly clearing a measurement also clears its paired unit. This
        # keeps PATCH semantics ergonomic while preserving strict DB checks.
        if product_weight is None and "weight_unit" not in changes:
            changes["weight_unit"] = None
        if not any(value is not None for value in (length, width, height)) and "dimension_unit" not in changes:
            changes["dimension_unit"] = None
        for field, value in (
            ("dimension_length", length),
            ("dimension_width", width),
            ("dimension_height", height),
            ("weight", product_weight),
        ):
            if field in changes:
                changes[field] = value
        return changes

    @staticmethod
    def _extract_images(changes: dict[str, object]) -> tuple[bool, list[ProductImageDraft] | None]:
        if "images" not in changes:
            return False, None
        images = changes.pop("images")
        return True, CatalogUseCases._normalize_images(images)

    @staticmethod
    def _normalize_images(images: object) -> list[ProductImageDraft]:
        if images is None:
            return []
        if not isinstance(images, list) or any(not isinstance(image, ProductImageDraft) for image in images):
            raise ValidationError("La galería de imágenes no es válida.", code="product_images_invalid")
        try:
            return normalize_product_image_drafts(images)
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_images_invalid") from exc

    @staticmethod
    def _normalize_variant_config(config: ProductVariantConfigDraft | None) -> ProductVariantConfigDraft | None:
        if config is None:
            return None
        try:
            return normalize_variant_config(config)
        except ValueError as exc:
            raise ValidationError(str(exc), code="product_variants_invalid") from exc

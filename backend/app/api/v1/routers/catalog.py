"""Catalog API Router: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, distinct, func, or_, select

from app.api.v1.company_access import (
    request_company_id,
    require_company_access,
    require_company_wide_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.catalog import (
    CatalogOptionResponse,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    CountryResponse,
    ProductCreate,
    ProductDistributionResponse,
    ProductImageInput,
    ProductResponse,
    ProductUpdate,
    ProductVariantConfigInput,
    ProductVariantResponse,
    ProductVariantUpdateInput,
    SubCategoryCreate,
    SubCategoryResponse,
    SubCategoryUpdate,
    UnitConfigurationUpdate,
    UnitCreate,
    UnitResponse,
    UnitUpdate,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.application.audit.audit_service import AuditService
from app.application.catalog.use_cases import CatalogUseCases
from app.core.exceptions import AuthorizationError
from app.domain.entities.product_image import ProductImageDraft
from app.domain.entities.product_variants import (
    ProductFamilyAttributeDraft,
    ProductFamilyAttributeValueDraft,
    ProductVariantConfigDraft,
    ProductVariantDraft,
    ProductVariantIdentifierDraft,
    ProductVariantImageDraft,
    ProductVariantUpdateDraft,
    ProductVariantValueDraft,
)
from app.infrastructure.models.catalog import CategoryModel, ProductModel, SubCategoryModel
from app.infrastructure.repositories import SqlAlchemyCatalogRepository, SqlAlchemyRoleRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _product_scope_conditions(
    company_id: uuid.UUID,
    *,
    category_id: int | None,
    sub_category_id: int | None,
    search: str | None,
    active_only: bool,
):
    conditions = [ProductModel.company_id == company_id, ProductModel.deleted_at.is_(None)]
    if category_id is not None:
        conditions.append(ProductModel.id_category == category_id)
    if sub_category_id is not None:
        conditions.append(ProductModel.id_sub_category == sub_category_id)
    if active_only:
        conditions.append(ProductModel.is_active.is_(True))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                ProductModel.name.ilike(pattern),
                ProductModel.sku.ilike(pattern),
                ProductModel.original_code.ilike(pattern),
                ProductModel.internal_code.ilike(pattern),
            )
        )
    return conditions


def _status_action(before_active: bool, after_active: bool) -> str:
    if before_active == after_active:
        return "UPDATE"
    return "ACTIVATE" if after_active else "DEACTIVATE"


def _get_catalog_use_cases(session: SessionDep) -> CatalogUseCases:
    repo = SqlAlchemyCatalogRepository(session)
    return CatalogUseCases(repo)


async def _require_product_images_permission(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID
) -> None:
    if current.is_superuser:
        return
    permissions = await SqlAlchemyRoleRepository(session).get_effective_permissions_for_user(
        current.id, company_id
    )
    if "products:images" not in {permission.code for permission in permissions}:
        raise AuthorizationError("Permiso requerido: products:images", code="forbidden")


async def _require_product_permission(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID, code: str
) -> None:
    if current.is_superuser:
        return
    permissions = await SqlAlchemyRoleRepository(session).get_effective_permissions_for_user(
        current.id, company_id
    )
    if code not in {permission.code for permission in permissions}:
        raise AuthorizationError(f"Permiso requerido: {code}", code="forbidden")


def _image_drafts(images: list[ProductImageInput] | None) -> list[ProductImageDraft] | None:
    if images is None:
        return None
    return [
        ProductImageDraft(
            id=image.id,
            source_type=image.source_type,
            url=image.url,
            media_asset_id=image.media_asset_id,
            alt_text=image.alt_text,
            position=image.position,
            is_cover=image.is_cover,
        )
        for image in images
    ]


def _product_identifier_drafts(payload: ProductCreate | ProductUpdate):
    if "identifiers" not in payload.model_fields_set or payload.identifiers is None:
        return None
    return tuple(
        ProductVariantIdentifierDraft(
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
            is_active=identifier.is_active,
        )
        for identifier in payload.identifiers
    )


def _gallery_audit_state(product: object) -> list[dict[str, object]]:
    return [
        {
            "id": str(image.id),
            "source_type": image.source_type,
            "position": image.position,
            "is_cover": image.is_cover,
        }
        for image in getattr(product, "images", ())
    ]


def _variant_config_drafts(
    payload: ProductVariantConfigInput | None,
) -> ProductVariantConfigDraft | None:
    if payload is None:
        return None
    return ProductVariantConfigDraft(
        attributes=tuple(
            ProductFamilyAttributeDraft(
                code=attribute.code,
                name=attribute.name,
                position=attribute.position,
                values=tuple(
                    ProductFamilyAttributeValueDraft(
                        code=value.code,
                        label=value.label,
                        position=value.position,
                    )
                    for value in attribute.values
                ),
            )
            for attribute in payload.attributes
        ),
        variants=tuple(
            ProductVariantDraft(
                id=variant.id,
                sku=variant.sku,
                name_override=variant.name_override,
                lifecycle_status=variant.lifecycle_status,
                values=tuple(
                    ProductVariantValueDraft(
                        attribute_code=value.attribute_code,
                        value_code=value.value_code,
                    )
                    for value in variant.values
                ),
                identifiers=tuple(
                    ProductVariantIdentifierDraft(
                        identifier_type=identifier.identifier_type,
                        value=identifier.value,
                        is_primary=identifier.is_primary,
                        is_active=identifier.is_active,
                    )
                    for identifier in variant.identifiers
                ),
                image=(
                    ProductVariantImageDraft(
                        source_type=variant.image.source_type,
                        url=variant.image.url,
                        media_asset_id=variant.image.media_asset_id,
                        alt_text=variant.image.alt_text,
                    )
                    if variant.image is not None
                    else None
                ),
            )
            for variant in payload.variants
        ),
    )


def _variant_config_has_images(payload: ProductVariantConfigInput | None) -> bool:
    return bool(payload and any(variant.image is not None for variant in payload.variants))


def _variant_config_has_identifiers(payload: ProductVariantConfigInput | None) -> bool:
    return bool(payload and any(variant.identifiers for variant in payload.variants))


def _variant_update_draft(payload: ProductVariantUpdateInput) -> ProductVariantUpdateDraft:
    provided = frozenset(
        {"sku", "name_override", "lifecycle_status", "identifiers", "image"}.intersection(
            payload.model_fields_set
        )
    )
    return ProductVariantUpdateDraft(
        expected_updated_at=payload.expected_updated_at,
        provided_fields=provided,
        sku=payload.sku,
        name_override=payload.name_override,
        lifecycle_status=payload.lifecycle_status,
        identifiers=(
            tuple(
                ProductVariantIdentifierDraft(
                    identifier_type=identifier.identifier_type,
                    value=identifier.value,
                    is_primary=identifier.is_primary,
                    is_active=identifier.is_active,
                )
                for identifier in payload.identifiers
            )
            if "identifiers" in provided and payload.identifiers is not None
            else None
        ),
        image=(
            ProductVariantImageDraft(
                source_type=payload.image.source_type,
                url=payload.image.url,
                media_asset_id=payload.image.media_asset_id,
                alt_text=payload.image.alt_text,
            )
            if "image" in provided and payload.image is not None
            else None
        ),
    )


def _single_variant_audit_state(variant: object) -> dict[str, object]:
    return {
        "id": str(variant.id),
        "sku": variant.sku,
        "name_override": variant.name_override,
        "combination_key": variant.combination_key,
        "lifecycle_status": variant.lifecycle_status,
        "values": [
            {
                "attribute_code": value.attribute_code,
                "value_code": value.value_code,
                "label": value.label,
            }
            for value in variant.values
        ],
        "identifiers": [
            {
                "id": str(identifier.id),
                "identifier_type": identifier.identifier_type,
                "value": identifier.value,
                "is_primary": identifier.is_primary,
                "is_active": identifier.is_active,
            }
            for identifier in variant.identifiers
        ],
        "image": (
            {
                "id": str(variant.image.id),
                "source_type": variant.image.source_type,
            }
            if variant.image
            else None
        ),
    }


def _product_has_variant_images(product: object) -> bool:
    return any(
        getattr(variant, "image", None) is not None for variant in getattr(product, "variants", ())
    )


def _product_has_variant_identifiers(product: object) -> bool:
    return any(
        bool(getattr(variant, "identifiers", ())) for variant in getattr(product, "variants", ())
    )


def _variant_audit_state(product: object) -> list[dict[str, object]]:
    return [
        {
            "id": str(variant.id),
            "sku": variant.sku,
            "combination_key": variant.combination_key,
            "lifecycle_status": variant.lifecycle_status,
            "values": [
                {
                    "attribute_code": value.attribute_code,
                    "value_code": value.value_code,
                    "label": value.label,
                }
                for value in variant.values
            ],
            "identifiers": [
                {
                    "id": str(identifier.id),
                    "identifier_type": identifier.identifier_type,
                    "value": identifier.value,
                    "is_primary": identifier.is_primary,
                    "is_active": identifier.is_active,
                }
                for identifier in variant.identifiers
            ],
            "image_id": str(variant.image.id) if variant.image else None,
        }
        for variant in getattr(product, "variants", ())
    ]


def _product_identifier_audit_state(product: object) -> list[dict[str, object]]:
    return [
        {
            "id": str(identifier.id),
            "identifier_type": identifier.identifier_type,
            "is_primary": identifier.is_primary,
            "is_active": identifier.is_active,
        }
        for identifier in getattr(product, "identifiers", ())
    ]


# --- Countries ---
@router.get(
    "/countries",
    response_model=list[CountryResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar países",
    dependencies=[Depends(require_permission("reference_data:read"))],
)
async def list_countries(
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[CountryResponse]:
    return await use_cases.list_countries(active_only=active_only)


@router.get(
    "/countries/{country_id}",
    response_model=CountryResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener país por ID",
    dependencies=[Depends(require_permission("reference_data:read"))],
)
async def get_country(
    country_id: int,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> CountryResponse:
    return await use_cases.get_country(country_id)


# --- Categories ---
@router.get(
    "/category-options",
    response_model=Page[CatalogOptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Buscar categorías para filtros",
    dependencies=[Depends(require_permission("products:read"))],
)
async def category_options(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    q: str | None = Query(None, max_length=100),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> Page[CatalogOptionResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    conditions = [CategoryModel.company_id == company_id, CategoryModel.deleted_at.is_(None)]
    if active_only:
        conditions.append(CategoryModel.is_active.is_(True))
    if q and q.strip():
        conditions.append(CategoryModel.name.ilike(f"%{q.strip()}%"))
    total = int(
        (await session.execute(select(func.count()).select_from(CategoryModel).where(*conditions)))
        .scalar_one()
    )
    rows = (
        await session.execute(
            select(CategoryModel.id_category, CategoryModel.name)
            .where(*conditions)
            .order_by(CategoryModel.name, CategoryModel.id_category)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[CatalogOptionResponse(id=int(row.id_category), label=row.name) for row in rows],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar categorías",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_categories(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[CategoryResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return await use_cases.list_categories(company_id, active_only=active_only)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def create_category(
    payload: CategoryCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> CategoryResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    if (
        payload.lifecycle_status != "active"
        or payload.product_kind != "goods"
        or any(
            value not in (None, False, "", [])
            for value in (
                payload.sales_name,
                payload.internal_name,
                payload.document_name,
                payload.sales_description,
                payload.purchase_description,
                payload.internal_notes,
                payload.keywords,
                payload.origin_country_id,
                payload.brand_id,
                payload.manufacturer_id,
                payload.storage_condition,
                payload.storage_temperature_min_c,
                payload.storage_temperature_max_c,
                payload.storage_humidity_max_percent,
                payload.max_stack_height,
                payload.handling_notes,
            )
        )
        or any((payload.is_fragile, payload.keep_dry, payload.keep_upright))
    ):
        await _require_product_permission(session, current, company_id, "products:master_data")
    if payload.lifecycle_status != "active":
        await _require_product_permission(session, current, company_id, "products:lifecycle")
    created = await use_cases.create_category(
        company_id, name=payload.name, description=payload.description
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="product_categories",
        resource_id=str(created.id),
        after_state={"name": created.name},
    )
    return created


@router.put(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar categoría",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> CategoryResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_category(company_id, category_id)
    updated = await use_cases.update_category(
        company_id, category_id, **payload.model_dump(exclude_unset=True)
    )
    await audit.record(
        action=_status_action(before.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
        resource_type="product_categories",
        resource_id=str(category_id),
        before_state={"name": before.name, "is_active": before.is_active},
        after_state={"name": updated.name, "is_active": updated.is_active},
    )
    return updated


# --- SubCategories ---
@router.get(
    "/sub-category-options",
    response_model=Page[CatalogOptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Buscar subcategorías para filtros",
    dependencies=[Depends(require_permission("products:read"))],
)
async def sub_category_options(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    category_id: int | None = Query(None),
    q: str | None = Query(None, max_length=100),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> Page[CatalogOptionResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    conditions = [
        SubCategoryModel.company_id == company_id,
        SubCategoryModel.deleted_at.is_(None),
    ]
    if category_id is not None:
        conditions.append(SubCategoryModel.id_category == category_id)
    if active_only:
        conditions.append(SubCategoryModel.is_active.is_(True))
    if q and q.strip():
        conditions.append(SubCategoryModel.name.ilike(f"%{q.strip()}%"))
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(SubCategoryModel).where(*conditions)
            )
        ).scalar_one()
    )
    rows = (
        await session.execute(
            select(SubCategoryModel.id_sub_category, SubCategoryModel.name, SubCategoryModel.id_category)
            .where(*conditions)
            .order_by(SubCategoryModel.name, SubCategoryModel.id_sub_category)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[
            CatalogOptionResponse(
                id=int(row.id_sub_category), label=row.name, parent_id=int(row.id_category)
            )
            for row in rows
        ],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/sub-categories",
    response_model=list[SubCategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar subcategorías",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_sub_categories(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    category_id: int | None = Query(None),
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[SubCategoryResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return await use_cases.list_sub_categories(
        company_id, category_id=category_id, active_only=active_only
    )


@router.post(
    "/sub-categories",
    response_model=SubCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear subcategoría",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def create_sub_category(
    payload: SubCategoryCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> SubCategoryResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    created = await use_cases.create_sub_category(
        company_id,
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="sub_categories",
        resource_id=str(created.id),
        after_state={"category_id": created.category_id, "name": created.name},
    )
    return created


@router.put(
    "/sub-categories/{sub_category_id}",
    response_model=SubCategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar subcategoría",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def update_sub_category(
    sub_category_id: int,
    payload: SubCategoryUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> SubCategoryResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_sub_category(company_id, sub_category_id)
    updated = await use_cases.update_sub_category(
        company_id, sub_category_id, **payload.model_dump(exclude_unset=True)
    )
    await audit.record(
        action=_status_action(before.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
        resource_type="sub_categories",
        resource_id=str(sub_category_id),
        before_state={
            "category_id": before.category_id,
            "name": before.name,
            "is_active": before.is_active,
        },
        after_state={
            "category_id": updated.category_id,
            "name": updated.name,
            "is_active": updated.is_active,
        },
    )
    return updated


# --- Units ---
@router.get(
    "/units",
    response_model=list[UnitResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar unidades de medida",
    dependencies=[Depends(require_permission("reference_data:read"))],
)
async def list_units(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[UnitResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return await use_cases.list_units(company_id, active_only=active_only)


@router.get(
    "/units/global",
    response_model=list[UnitResponse],
    dependencies=[Depends(require_permission("units:manage_global"))],
    summary="Listar catálogo global de unidades",
)
async def list_global_units(
    current: CurrentUser,
    active_only: bool = Query(False),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[UnitResponse]:
    if not current.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso reservado al superadministrador.")
    return await use_cases.list_global_units(active_only=active_only)


@router.post(
    "/units/global",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("units:manage_global"))],
    summary="Crear unidad estándar global",
)
async def create_global_unit(
    payload: UnitCreate,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    if not current.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso reservado al superadministrador.")
    created = await use_cases.create_unit(
        None,
        name=payload.name,
        type_=payload.type,
        code=payload.code,
        symbol=payload.symbol,
        description=payload.description,
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        resource_type="measurement_units_global",
        resource_id=str(created.id),
        after_state={"code": created.code, "name": created.name},
    )
    return created


@router.put(
    "/units/global/{unit_id}",
    response_model=UnitResponse,
    dependencies=[Depends(require_permission("units:manage_global"))],
    summary="Actualizar unidad estándar global",
)
async def update_global_unit(
    unit_id: int,
    payload: UnitUpdate,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    if not current.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso reservado al superadministrador.")
    changes = payload.model_dump(exclude={"version"}, exclude_unset=True)
    updated = await use_cases.update_unit(None, unit_id, payload.version, **changes)
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        resource_type="measurement_units_global",
        resource_id=str(unit_id),
        after_state={"code": updated.code, "name": updated.name, "version": updated.version},
    )
    return updated


@router.post(
    "/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear unidad de medida",
    dependencies=[Depends(require_permission("units:create"))],
)
async def create_unit(
    payload: UnitCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    created = await use_cases.create_unit(
        company_id,
        name=payload.name,
        type_=payload.type,
        code=payload.code,
        symbol=payload.symbol,
        description=payload.description,
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="measurement_units",
        resource_id=str(created.id),
        after_state={"code": created.code, "name": created.name},
    )
    return created


@router.put(
    "/units/{unit_id}",
    response_model=UnitResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar unidad de medida",
    dependencies=[Depends(require_permission("units:update"))],
)
async def update_unit(
    unit_id: int,
    payload: UnitUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_unit(company_id, unit_id)
    if before.is_standard:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Las unidades estándar solo pueden configurarse, no editarse.",
        )
    changes = payload.model_dump(exclude={"version", "alias"}, exclude_unset=True)
    updated = await use_cases.update_unit(company_id, unit_id, payload.version, **changes)
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="measurement_units",
        resource_id=str(unit_id),
        before_state={"code": before.code, "name": before.name, "version": before.version},
        after_state={"code": updated.code, "name": updated.name, "version": updated.version},
    )
    return updated


async def _configure_unit(
    unit_id: int,
    payload: UnitConfigurationUpdate,
    enabled: bool,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases,
    audit: AuditService,
) -> UnitResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_unit(company_id, unit_id)
    updated = await use_cases.configure_unit(
        company_id, unit_id, payload.version, enabled=enabled, alias=payload.alias
    )
    await audit.record(
        action="ACTIVATE" if enabled else "DEACTIVATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="company_units",
        resource_id=str(unit_id),
        before_state={
            "is_enabled": before.is_enabled,
            "alias": before.alias,
            "version": before.version,
        },
        after_state={
            "is_enabled": updated.is_enabled,
            "alias": updated.alias,
            "version": updated.version,
        },
    )
    return updated


@router.post(
    "/units/{unit_id}/activate",
    response_model=UnitResponse,
    dependencies=[Depends(require_permission("units:activate"))],
)
async def activate_unit(
    unit_id: int,
    payload: UnitConfigurationUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> UnitResponse:
    return await _configure_unit(
        unit_id, payload, True, request, session, current, use_cases, audit
    )


@router.post(
    "/units/{unit_id}/deactivate",
    response_model=UnitResponse,
    dependencies=[Depends(require_permission("units:deactivate"))],
)
async def deactivate_unit(
    unit_id: int,
    payload: UnitConfigurationUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> UnitResponse:
    return await _configure_unit(
        unit_id, payload, False, request, session, current, use_cases, audit
    )


# --- Products ---
@router.get(
    "/products",
    response_model=Page[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar productos paginados",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_products(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    category_id: int | None = Query(None),
    sub_category_id: int | None = Query(None),
    search: str | None = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> Page[ProductResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    skip = (page - 1) * size
    items, total = await use_cases.list_products(
        company_id,
        category_id=category_id,
        sub_category_id=sub_category_id,
        search=search,
        active_only=active_only,
        skip=skip,
        limit=size,
    )
    pages = (total + size - 1) // size if total > 0 else 0
    return Page(
        items=[ProductResponse.model_validate(p) for p in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/products/stats",
    dependencies=[Depends(require_permission("products:read"))],
    summary="Obtener indicadores de productos",
)
async def product_stats(request: Request, session: SessionDep, current: CurrentUser):
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id, require_active=True)
    row = (
        await session.execute(
            select(
                func.count(ProductModel.id_product),
                func.count(ProductModel.id_product).filter(ProductModel.is_active.is_(True)),
                func.count(distinct(ProductModel.id_category)).filter(
                    ProductModel.is_active.is_(True)
                ),
            ).where(ProductModel.company_id == company_id, ProductModel.deleted_at.is_(None))
        )
    ).one()
    total, active, categories = (int(value or 0) for value in row)
    return {"total": total, "active": active, "inactive": total - active, "categories": categories}


@router.get(
    "/products/distribution",
    response_model=ProductDistributionResponse,
    status_code=status.HTTP_200_OK,
    summary="Distribución agregada del catálogo",
    dependencies=[Depends(require_permission("products:read"))],
)
async def product_distribution(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    category_id: int | None = Query(None),
    sub_category_id: int | None = Query(None),
    search: str | None = Query(None, max_length=100),
    active_only: bool = Query(False),
) -> ProductDistributionResponse:
    """Return bounded server-side aggregates for the catalogue insights.

    The endpoint deliberately returns at most six named groups plus an
    informational ``Otros``/``Sin subcategoría`` bucket. This keeps the
    browser payload bounded even when a company has thousands of categories.
    """
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    conditions = _product_scope_conditions(
        company_id,
        category_id=category_id,
        sub_category_id=sub_category_id,
        search=search,
        active_only=active_only,
    )
    scope_total = int(
        (await session.execute(select(func.count()).select_from(ProductModel).where(*conditions)))
        .scalar_one()
    )

    category_count = func.count(ProductModel.id_product)
    category_rows = (
        await session.execute(
            select(CategoryModel.id_category, CategoryModel.name, category_count.label("value"))
            .join(
                ProductModel,
                (ProductModel.id_category == CategoryModel.id_category)
                & (ProductModel.company_id == company_id),
            )
            .where(*conditions, CategoryModel.deleted_at.is_(None))
            .group_by(CategoryModel.id_category, CategoryModel.name)
            .order_by(desc(category_count), CategoryModel.name)
            .limit(6)
        )
    ).all()
    category_items = [
        {"id": int(row.id_category), "label": row.name, "value": int(row.value), "filterable": True}
        for row in category_rows
    ]
    category_other = scope_total - sum(item["value"] for item in category_items)
    if category_other > 0:
        category_items.append(
            {"id": None, "label": "Otros", "value": category_other, "filterable": False}
        )

    sub_count = func.count(ProductModel.id_product)
    sub_rows = (
        await session.execute(
            select(
                SubCategoryModel.id_sub_category,
                SubCategoryModel.name,
                SubCategoryModel.id_category,
                sub_count.label("value"),
            )
            .join(
                ProductModel,
                (ProductModel.id_sub_category == SubCategoryModel.id_sub_category)
                & (ProductModel.company_id == company_id),
            )
            .where(
                *conditions,
                ProductModel.id_sub_category.is_not(None),
                SubCategoryModel.deleted_at.is_(None),
            )
            .group_by(
                SubCategoryModel.id_sub_category,
                SubCategoryModel.name,
                SubCategoryModel.id_category,
            )
            .order_by(desc(sub_count), SubCategoryModel.name)
            .limit(6)
        )
    ).all()
    sub_items = [
        {
            "id": int(row.id_sub_category),
            "parent_id": int(row.id_category),
            "label": row.name,
            "value": int(row.value),
            "filterable": True,
        }
        for row in sub_rows
    ]
    sub_none = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ProductModel)
                .where(*conditions, ProductModel.id_sub_category.is_(None))
            )
        ).scalar_one()
    )
    sub_other = scope_total - sum(item["value"] for item in sub_items) - sub_none
    if sub_other > 0:
        sub_items.append(
            {"id": None, "label": "Otros", "value": sub_other, "filterable": False}
        )
    if sub_none > 0:
        sub_items.append(
            {"id": None, "label": "Sin subcategoría", "value": sub_none, "filterable": False}
        )

    return ProductDistributionResponse(
        scope_total=scope_total, categories=category_items, subcategories=sub_items
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener producto por ID",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product(
    product_id: int,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> ProductResponse:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return await use_cases.get_product(company_id, product_id)


@router.get(
    "/products/{product_id}/variants",
    response_model=list[ProductVariantResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar variantes del producto",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_product_variants(
    product_id: int,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[ProductVariantResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    product = await use_cases.get_product(company_id, product_id)
    return [ProductVariantResponse.model_validate(variant) for variant in product.variants]


@router.get(
    "/products/{product_id}/variants/{variant_id}",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener una variante",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product_variant(
    product_id: int,
    variant_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> ProductVariantResponse:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    variant = await use_cases.get_variant(company_id, product_id, variant_id)
    return ProductVariantResponse.model_validate(variant)


@router.patch(
    "/products/{product_id}/variants/{variant_id}",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar una variante",
    dependencies=[Depends(require_permission("products:read"))],
)
async def update_product_variant(  # noqa: C901 - dynamic permissions and audit events are explicit
    product_id: int,
    variant_id: uuid.UUID,
    payload: ProductVariantUpdateInput,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ProductVariantResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    provided = payload.model_fields_set
    if provided.intersection({"sku", "name_override", "lifecycle_status"}):
        await _require_product_permission(session, current, company_id, "products:variants")
    if "identifiers" in provided:
        await _require_product_permission(session, current, company_id, "products:identifiers")
    if "image" in provided:
        await _require_product_images_permission(session, current, company_id)

    before = await use_cases.get_variant(company_id, product_id, variant_id)
    async with session.begin_nested():
        updated = await use_cases.update_variant(
            company_id,
            product_id,
            variant_id,
            _variant_update_draft(payload),
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Variante no encontrada")
        before_state = _single_variant_audit_state(before)
        after_state = _single_variant_audit_state(updated)
        actions: list[str] = []
        if provided.intersection({"sku", "name_override", "lifecycle_status"}):
            actions.append("UPDATE_VARIANT")
        if before.sku != updated.sku:
            actions.append("CHANGE_VARIANT_SKU")
        if before.lifecycle_status != updated.lifecycle_status:
            actions.append("CHANGE_VARIANT_STATUS")
        if "identifiers" in provided:
            actions.append("UPDATE_VARIANT_IDENTIFIERS")
        if "image" in provided:
            actions.append("UPDATE_VARIANT_IMAGE")
        for action in actions:
            await audit.record(
                action=action,
                user_id=current.id,
                company_id=company_id,
                resource_type="product_variants",
                resource_id=str(variant_id),
                before_state=before_state,
                after_state=after_state,
            )
    return ProductVariantResponse.model_validate(updated)


@router.post(
    "/products/{product_id}/variants/preview",
    status_code=status.HTTP_200_OK,
    summary="Previsualizar combinaciones de variantes",
    dependencies=[Depends(require_permission("products:variants"))],
)
async def preview_product_variants(
    product_id: int,
    payload: ProductVariantConfigInput,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> dict[str, object]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    await use_cases.get_product(company_id, product_id)
    if _variant_config_has_images(payload):
        await _require_product_images_permission(session, current, company_id)
    if _variant_config_has_identifiers(payload):
        await _require_product_permission(session, current, company_id, "products:identifiers")
    return {
        "attribute_count": len(payload.attributes),
        "variant_count": len(payload.variants),
        "attributes": payload.attributes,
        "variants": payload.variants,
    }


@router.put(
    "/products/{product_id}/variant-config",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Guardar familia y variantes",
    dependencies=[Depends(require_permission("products:variants"))],
)
async def replace_product_variant_config(
    product_id: int,
    payload: ProductVariantConfigInput,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ProductResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_product(company_id, product_id)
    if _variant_config_has_images(payload) or _product_has_variant_images(before):
        await _require_product_images_permission(session, current, company_id)
    if _variant_config_has_identifiers(payload) or _product_has_variant_identifiers(before):
        await _require_product_permission(session, current, company_id, "products:identifiers")
    async with session.begin_nested():
        updated = await use_cases.replace_variant_config(
            company_id,
            product_id,
            _variant_config_drafts(payload),
        )
        await audit.record(
            action="UPDATE_VARIANTS",
            user_id=current.id,
            company_id=company_id,
            resource_type="products",
            resource_id=str(product_id),
            before_state={
                "variant_mode": before.variant_mode,
                "variants": _variant_audit_state(before),
            },
            after_state={
                "variant_mode": updated.variant_mode,
                "variants": _variant_audit_state(updated),
            },
        )
    return updated


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def create_product(
    payload: ProductCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ProductResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    if payload.images is not None:
        await _require_product_images_permission(session, current, company_id)
    if payload.identifiers is not None:
        await _require_product_permission(session, current, company_id, "products:identifiers")
    if payload.variant_config is not None:
        await _require_product_permission(session, current, company_id, "products:variants")
        if _variant_config_has_images(payload.variant_config):
            await _require_product_images_permission(session, current, company_id)
        if _variant_config_has_identifiers(payload.variant_config):
            await _require_product_permission(session, current, company_id, "products:identifiers")
    async with session.begin_nested():
        created = await use_cases.create_product(
            company_id,
            category_id=payload.category_id,
            sub_category_id=payload.sub_category_id,
            sku=payload.sku,
            name=payload.name,
            purchase_unit_id=payload.purchase_unit_id,
            sale_unit_id=payload.sale_unit_id,
            original_code=payload.original_code,
            internal_code=payload.internal_code,
            size=payload.size,
            dimension_length=payload.dimension_length,
            dimension_width=payload.dimension_width,
            dimension_height=payload.dimension_height,
            dimension_unit=payload.dimension_unit,
            weight=payload.weight,
            weight_unit=payload.weight_unit,
            description=payload.description,
            presentation=payload.presentation,
            product_kind=payload.product_kind,
            lifecycle_status=payload.lifecycle_status,
            can_purchase=payload.can_purchase,
            can_sell=payload.can_sell,
            sales_name=payload.sales_name,
            internal_name=payload.internal_name,
            document_name=payload.document_name,
            sales_description=payload.sales_description,
            purchase_description=payload.purchase_description,
            internal_notes=payload.internal_notes,
            keywords=payload.keywords,
            origin_country_id=payload.origin_country_id,
            brand_id=payload.brand_id,
            manufacturer_id=payload.manufacturer_id,
            storage_condition=payload.storage_condition,
            storage_temperature_min_c=payload.storage_temperature_min_c,
            storage_temperature_max_c=payload.storage_temperature_max_c,
            storage_humidity_max_percent=payload.storage_humidity_max_percent,
            is_fragile=payload.is_fragile,
            keep_dry=payload.keep_dry,
            keep_upright=payload.keep_upright,
            stackable=payload.stackable,
            max_stack_height=payload.max_stack_height,
            handling_notes=payload.handling_notes,
            images=_image_drafts(payload.images),
            identifiers=_product_identifier_drafts(payload),
            variant_config=_variant_config_drafts(payload.variant_config),
        )
        await audit.record(
            action="CREATE",
            user_id=current.id,
            company_id=company_id,
            resource_type="products",
            resource_id=str(created.id),
            after_state={
                "sku": created.sku,
                "name": created.name,
                "images": _gallery_audit_state(created),
                "identifiers": _product_identifier_audit_state(created),
                "variant_mode": created.variant_mode,
                "variants": _variant_audit_state(created),
            },
        )
    return created


@router.put(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar producto",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ProductResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_product(company_id, product_id)
    update_data = payload.model_dump(exclude_unset=True)
    master_fields = {
        "product_kind",
        "sales_name",
        "internal_name",
        "document_name",
        "sales_description",
        "purchase_description",
        "internal_notes",
        "keywords",
        "origin_country_id",
        "brand_id",
        "manufacturer_id",
        "storage_condition",
        "storage_temperature_min_c",
        "storage_temperature_max_c",
        "storage_humidity_max_percent",
        "is_fragile",
        "keep_dry",
        "keep_upright",
        "stackable",
        "max_stack_height",
        "handling_notes",
        "can_purchase",
        "can_sell",
    }
    if master_fields.intersection(update_data):
        await _require_product_permission(session, current, company_id, "products:master_data")
    if "lifecycle_status" in update_data or "is_active" in update_data:
        await _require_product_permission(session, current, company_id, "products:lifecycle")
    if "images" in update_data:
        await _require_product_images_permission(session, current, company_id)
        update_data["images"] = _image_drafts(payload.images)
    if "identifiers" in update_data:
        await _require_product_permission(session, current, company_id, "products:identifiers")
        update_data["identifiers"] = _product_identifier_drafts(payload)
    if "variant_config" in update_data:
        await _require_product_permission(session, current, company_id, "products:variants")
        if _variant_config_has_images(payload.variant_config) or _product_has_variant_images(
            before
        ):
            await _require_product_images_permission(session, current, company_id)
        if _variant_config_has_identifiers(
            payload.variant_config
        ) or _product_has_variant_identifiers(before):
            await _require_product_permission(session, current, company_id, "products:identifiers")
        update_data["variant_config"] = _variant_config_drafts(payload.variant_config)
    async with session.begin_nested():
        updated = await use_cases.update_product(company_id, product_id, **update_data)
        await audit.record(
            action=(
                "UPDATE_VARIANTS"
                if "variant_config" in update_data
                else "UPDATE_IDENTIFIERS"
                if "identifiers" in update_data
                else "UPDATE_IMAGES"
                if "images" in update_data
                else _status_action(before.is_active, updated.is_active)
            ),
            user_id=current.id,
            company_id=company_id,
            resource_type="products",
            resource_id=str(product_id),
            before_state={
                "sku": before.sku,
                "name": before.name,
                "is_active": before.is_active,
                "images": _gallery_audit_state(before),
                "identifiers": _product_identifier_audit_state(before),
                "variants": _variant_audit_state(before),
            },
            after_state={
                "sku": updated.sku,
                "name": updated.name,
                "is_active": updated.is_active,
                "images": _gallery_audit_state(updated),
                "identifiers": _product_identifier_audit_state(updated),
                "variants": _variant_audit_state(updated),
            },
        )
    return updated

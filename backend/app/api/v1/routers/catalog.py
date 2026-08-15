"""Catalog API Router: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import distinct, func, select

from app.api.v1.company_access import (
    request_company_id,
    require_company_access,
    require_company_wide_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.catalog import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    CountryResponse,
    ProductCreate,
    ProductImageInput,
    ProductResponse,
    ProductUpdate,
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
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.repositories import SqlAlchemyCatalogRepository, SqlAlchemyRoleRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])


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
    created = await use_cases.create_category(company_id, name=payload.name, description=payload.description)
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="product_categories", resource_id=str(created.id), after_state={"name": created.name})
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
    updated = await use_cases.update_category(company_id, category_id, **payload.model_dump(exclude_unset=True))
    await audit.record(action=_status_action(before.is_active, updated.is_active), user_id=current.id, company_id=company_id, resource_type="product_categories", resource_id=str(category_id), before_state={"name": before.name, "is_active": before.is_active}, after_state={"name": updated.name, "is_active": updated.is_active})
    return updated


# --- SubCategories ---
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
    return await use_cases.list_sub_categories(company_id, category_id=category_id, active_only=active_only)


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
    created = await use_cases.create_sub_category(company_id, category_id=payload.category_id, name=payload.name, description=payload.description)
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
    updated = await use_cases.update_sub_category(company_id, sub_category_id, **payload.model_dump(exclude_unset=True))
    await audit.record(
        action=_status_action(before.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
        resource_type="sub_categories",
        resource_id=str(sub_category_id),
        before_state={"category_id": before.category_id, "name": before.name, "is_active": before.is_active},
        after_state={"category_id": updated.category_id, "name": updated.name, "is_active": updated.is_active},
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
    created = await use_cases.create_unit(None, name=payload.name, type_=payload.type, code=payload.code, symbol=payload.symbol, description=payload.description)
    await audit.record(action="CREATE", user_id=current.id, resource_type="measurement_units_global", resource_id=str(created.id), after_state={"code": created.code, "name": created.name})
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
    await audit.record(action="UPDATE", user_id=current.id, resource_type="measurement_units_global", resource_id=str(unit_id), after_state={"code": updated.code, "name": updated.name, "version": updated.version})
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
    created = await use_cases.create_unit(company_id, name=payload.name, type_=payload.type, code=payload.code, symbol=payload.symbol, description=payload.description)
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="measurement_units", resource_id=str(created.id), after_state={"code": created.code, "name": created.name})
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
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Las unidades estándar solo pueden configurarse, no editarse.")
    changes = payload.model_dump(exclude={"version", "alias"}, exclude_unset=True)
    updated = await use_cases.update_unit(company_id, unit_id, payload.version, **changes)
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="measurement_units", resource_id=str(unit_id), before_state={"code": before.code, "name": before.name, "version": before.version}, after_state={"code": updated.code, "name": updated.name, "version": updated.version})
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
    updated = await use_cases.configure_unit(company_id, unit_id, payload.version, enabled=enabled, alias=payload.alias)
    await audit.record(action="ACTIVATE" if enabled else "DEACTIVATE", user_id=current.id, company_id=company_id, resource_type="company_units", resource_id=str(unit_id), before_state={"is_enabled": before.is_enabled, "alias": before.alias, "version": before.version}, after_state={"is_enabled": updated.is_enabled, "alias": updated.alias, "version": updated.version})
    return updated


@router.post("/units/{unit_id}/activate", response_model=UnitResponse, dependencies=[Depends(require_permission("units:activate"))])
async def activate_unit(unit_id: int, payload: UnitConfigurationUpdate, request: Request, session: SessionDep, current: CurrentUser, use_cases: CatalogUseCases = Depends(_get_catalog_use_cases), audit: AuditService = Depends(get_audit_service)) -> UnitResponse:
    return await _configure_unit(unit_id, payload, True, request, session, current, use_cases, audit)


@router.post("/units/{unit_id}/deactivate", response_model=UnitResponse, dependencies=[Depends(require_permission("units:deactivate"))])
async def deactivate_unit(unit_id: int, payload: UnitConfigurationUpdate, request: Request, session: SessionDep, current: CurrentUser, use_cases: CatalogUseCases = Depends(_get_catalog_use_cases), audit: AuditService = Depends(get_audit_service)) -> UnitResponse:
    return await _configure_unit(unit_id, payload, False, request, session, current, use_cases, audit)


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
            ).where(ProductModel.company_id == company_id)
        )
    ).one()
    total, active, categories = (int(value or 0) for value in row)
    return {"total": total, "active": active, "inactive": total - active, "categories": categories}


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
        dimensions=payload.dimensions,
        description=payload.description,
        presentation=payload.presentation,
        images=_image_drafts(payload.images),
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="products",
        resource_id=str(created.id),
        after_state={"sku": created.sku, "name": created.name, "images": _gallery_audit_state(created)},
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
    if "images" in update_data:
        await _require_product_images_permission(session, current, company_id)
        update_data["images"] = _image_drafts(payload.images)
    updated = await use_cases.update_product(company_id, product_id, **update_data)
    await audit.record(
        action="UPDATE_IMAGES" if "images" in update_data else _status_action(before.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
        resource_type="products",
        resource_id=str(product_id),
        before_state={
            "sku": before.sku,
            "name": before.name,
            "is_active": before.is_active,
            "images": _gallery_audit_state(before),
        },
        after_state={
            "sku": updated.sku,
            "name": updated.name,
            "is_active": updated.is_active,
            "images": _gallery_audit_state(updated),
        },
    )
    return updated

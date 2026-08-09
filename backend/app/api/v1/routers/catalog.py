"""Catalog API Router: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

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
    ProductResponse,
    ProductUpdate,
    SubCategoryCreate,
    SubCategoryResponse,
    SubCategoryUpdate,
    UnitCreate,
    UnitResponse,
    UnitUpdate,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.application.audit.audit_service import AuditService
from app.application.catalog.use_cases import CatalogUseCases
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.repositories import SqlAlchemyCatalogRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _get_catalog_use_cases(session: SessionDep) -> CatalogUseCases:
    repo = SqlAlchemyCatalogRepository(session)
    return CatalogUseCases(repo)


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
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="product_categories", resource_id=str(category_id), before_state={"name": before.name, "is_active": before.is_active}, after_state={"name": updated.name, "is_active": updated.is_active})
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
        action="UPDATE",
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
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[UnitResponse]:
    return await use_cases.list_units(active_only=active_only)


@router.post(
    "/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear unidad de medida",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def create_unit(
    payload: UnitCreate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    if not current.is_superuser:
        raise HTTPException(403, "Las unidades de medida son administradas globalmente.")
    return await use_cases.create_unit(name=payload.name, type_=payload.type)


@router.put(
    "/units/{unit_id}",
    response_model=UnitResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar unidad de medida",
    dependencies=[Depends(require_permission("products:manage"))],
)
async def update_unit(
    unit_id: int,
    payload: UnitUpdate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    if not current.is_superuser:
        raise HTTPException(403, "Las unidades de medida son administradas globalmente.")
    return await use_cases.update_unit(
        unit_id=unit_id, name=payload.name, type_=payload.type, is_active=payload.is_active
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
    )
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="products", resource_id=str(created.id), after_state={"sku": created.sku, "name": created.name})
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
    updated = await use_cases.update_product(company_id, product_id, **update_data)
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="products", resource_id=str(product_id), before_state={"sku": before.sku, "name": before.name, "is_active": before.is_active}, after_state={"sku": updated.sku, "name": updated.name, "is_active": updated.is_active})
    return updated

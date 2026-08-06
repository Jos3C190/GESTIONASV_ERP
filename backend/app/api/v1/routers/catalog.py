"""Catalog API Router: Countries, Categories, SubCategories, Units, Products."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import CurrentUser, SessionDep, require_permission
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
from app.application.catalog.use_cases import CatalogUseCases
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
    dependencies=[Depends(require_permission("catalog:read"))],
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
    dependencies=[Depends(require_permission("catalog:read"))],
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
    dependencies=[Depends(require_permission("catalog:read"))],
)
async def list_categories(
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[CategoryResponse]:
    return await use_cases.list_categories(active_only=active_only)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def create_category(
    payload: CategoryCreate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> CategoryResponse:
    return await use_cases.create_category(name=payload.name, description=payload.description)


@router.put(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar categoría",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> CategoryResponse:
    return await use_cases.update_category(
        category_id=category_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )


# --- SubCategories ---
@router.get(
    "/sub-categories",
    response_model=list[SubCategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar subcategorías",
    dependencies=[Depends(require_permission("catalog:read"))],
)
async def list_sub_categories(
    category_id: int | None = Query(None),
    active_only: bool = Query(True),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> list[SubCategoryResponse]:
    return await use_cases.list_sub_categories(category_id=category_id, active_only=active_only)


@router.post(
    "/sub-categories",
    response_model=SubCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear subcategoría",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def create_sub_category(
    payload: SubCategoryCreate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> SubCategoryResponse:
    return await use_cases.create_sub_category(
        category_id=payload.category_id, name=payload.name, description=payload.description
    )


@router.put(
    "/sub-categories/{sub_category_id}",
    response_model=SubCategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar subcategoría",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def update_sub_category(
    sub_category_id: int,
    payload: SubCategoryUpdate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> SubCategoryResponse:
    return await use_cases.update_sub_category(
        sub_category_id=sub_category_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )


# --- Units ---
@router.get(
    "/units",
    response_model=list[UnitResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar unidades de medida",
    dependencies=[Depends(require_permission("catalog:read"))],
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
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def create_unit(
    payload: UnitCreate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    return await use_cases.create_unit(name=payload.name, type_=payload.type)


@router.put(
    "/units/{unit_id}",
    response_model=UnitResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar unidad de medida",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def update_unit(
    unit_id: int,
    payload: UnitUpdate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> UnitResponse:
    return await use_cases.update_unit(
        unit_id=unit_id, name=payload.name, type_=payload.type, is_active=payload.is_active
    )


# --- Products ---
@router.get(
    "/products",
    response_model=Page[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar productos paginados",
    dependencies=[Depends(require_permission("catalog:read"))],
)
async def list_products(
    category_id: int | None = Query(None),
    sub_category_id: int | None = Query(None),
    search: str | None = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> Page[ProductResponse]:
    skip = (page - 1) * size
    items, total = await use_cases.list_products(
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
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener producto por ID",
    dependencies=[Depends(require_permission("catalog:read"))],
)
async def get_product(
    product_id: int,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> ProductResponse:
    return await use_cases.get_product(product_id)


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def create_product(
    payload: ProductCreate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> ProductResponse:
    return await use_cases.create_product(
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


@router.put(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar producto",
    dependencies=[Depends(require_permission("catalog:write"))],
)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    current: CurrentUser,
    use_cases: CatalogUseCases = Depends(_get_catalog_use_cases),
) -> ProductResponse:
    update_data = payload.model_dump(exclude_unset=True)
    return await use_cases.update_product(product_id, **update_data)

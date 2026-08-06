"""Suppliers API Router: Suppliers and Supplier Contacts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.common import MessageOut, Page, PageMeta
from app.api.v1.schemas.supplier import (
    SupplierContactCreate,
    SupplierContactResponse,
    SupplierContactUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.application.suppliers.use_cases import SupplierUseCases
from app.infrastructure.repositories import (
    SqlAlchemyCatalogRepository,
    SqlAlchemySupplierRepository,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _get_supplier_use_cases(session: SessionDep) -> SupplierUseCases:
    supplier_repo = SqlAlchemySupplierRepository(session)
    catalog_repo = SqlAlchemyCatalogRepository(session)
    return SupplierUseCases(supplier_repo, catalog_repo)


@router.get(
    "",
    response_model=Page[SupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar proveedores paginados",
    dependencies=[Depends(require_permission("suppliers:read"))],
)
async def list_suppliers(
    country_id: int | None = Query(None),
    search: str | None = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> Page[SupplierResponse]:
    skip = (page - 1) * size
    items, total = await use_cases.list_suppliers(
        country_id=country_id,
        search=search,
        active_only=active_only,
        skip=skip,
        limit=size,
    )
    pages = (total + size - 1) // size if total > 0 else 0
    return Page(
        items=[SupplierResponse.model_validate(s) for s in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener proveedor por ID",
    dependencies=[Depends(require_permission("suppliers:read"))],
)
async def get_supplier(
    supplier_id: int,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> SupplierResponse:
    return await use_cases.get_supplier(supplier_id)


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
    dependencies=[Depends(require_permission("suppliers:write"))],
)
async def create_supplier(
    payload: SupplierCreate,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> SupplierResponse:
    return await use_cases.create_supplier(
        code=payload.code,
        name=payload.name,
        country_id=payload.country_id,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
    )


@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar proveedor",
    dependencies=[Depends(require_permission("suppliers:write"))],
)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> SupplierResponse:
    update_data = payload.model_dump(exclude_unset=True)
    return await use_cases.update_supplier(supplier_id, **update_data)


# --- Supplier Contacts ---
@router.post(
    "/{supplier_id}/contacts",
    response_model=SupplierContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar contacto a proveedor",
    dependencies=[Depends(require_permission("suppliers:write"))],
)
async def add_contact(
    supplier_id: int,
    payload: SupplierContactCreate,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> SupplierContactResponse:
    return await use_cases.add_contact(
        supplier_id=supplier_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
    )


@router.put(
    "/contacts/{contact_id}",
    response_model=SupplierContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar contacto de proveedor",
    dependencies=[Depends(require_permission("suppliers:write"))],
)
async def update_contact(
    contact_id: int,
    payload: SupplierContactUpdate,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> SupplierContactResponse:
    return await use_cases.update_contact(
        contact_id=contact_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        is_active=payload.is_active,
    )


@router.delete(
    "/contacts/{contact_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Eliminar contacto de proveedor",
    dependencies=[Depends(require_permission("suppliers:write"))],
)
async def delete_contact(
    contact_id: int,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> MessageOut:
    await use_cases.delete_contact(contact_id)
    return MessageOut(message="Contacto eliminado exitosamente")

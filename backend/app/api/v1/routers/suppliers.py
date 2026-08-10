"""Suppliers API Router: Suppliers and Supplier Contacts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import distinct, func, select

from app.api.v1.company_access import (
    request_company_id,
    require_company_access,
    require_company_wide_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.common import MessageOut, Page, PageMeta
from app.api.v1.schemas.supplier import (
    SupplierContactCreate,
    SupplierContactResponse,
    SupplierContactUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.suppliers.use_cases import SupplierUseCases
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.repositories import (
    SqlAlchemyCatalogRepository,
    SqlAlchemySupplierRepository,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _status_action(before_active: bool, after_active: bool) -> str:
    if before_active == after_active:
        return "UPDATE"
    return "ACTIVATE" if after_active else "DEACTIVATE"


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
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    country_id: int | None = Query(None),
    search: str | None = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> Page[SupplierResponse]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    skip = (page - 1) * size
    items, total = await use_cases.list_suppliers(
        company_id,
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
    "/stats",
    dependencies=[Depends(require_permission("suppliers:read"))],
    summary="Obtener indicadores de proveedores",
)
async def supplier_stats(request: Request, session: SessionDep, current: CurrentUser):
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id, require_active=True)
    row = (
        await session.execute(
            select(
                func.count(SupplierModel.id_supplier),
                func.count(SupplierModel.id_supplier).filter(SupplierModel.is_active.is_(True)),
                func.count(distinct(SupplierModel.country_id)).filter(
                    SupplierModel.is_active.is_(True)
                ),
            ).where(SupplierModel.company_id == company_id)
        )
    ).one()
    total, active, countries = (int(value or 0) for value in row)
    return {"total": total, "active": active, "inactive": total - active, "countries": countries}


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener proveedor por ID",
    dependencies=[Depends(require_permission("suppliers:read"))],
)
async def get_supplier(
    supplier_id: int,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
) -> SupplierResponse:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    return await use_cases.get_supplier(company_id, supplier_id)


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proveedor",
    dependencies=[Depends(require_permission("suppliers:manage"))],
)
async def create_supplier(
    payload: SupplierCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> SupplierResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    created = await use_cases.create_supplier(
        company_id,
        code=payload.code,
        name=payload.name,
        country_id=payload.country_id,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="suppliers",
        resource_id=str(created.id),
        after_state={"code": created.code, "name": created.name},
    )
    return created


@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar proveedor",
    dependencies=[Depends(require_permission("suppliers:manage"))],
)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> SupplierResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_supplier(company_id, supplier_id)
    update_data = payload.model_dump(exclude_unset=True)
    updated = await use_cases.update_supplier(company_id, supplier_id, **update_data)
    await audit.record(
        action=_status_action(before.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
        resource_type="suppliers",
        resource_id=str(supplier_id),
        before_state={"code": before.code, "name": before.name, "is_active": before.is_active},
        after_state={"code": updated.code, "name": updated.name, "is_active": updated.is_active},
    )
    return updated


# --- Supplier Contacts ---
@router.post(
    "/{supplier_id}/contacts",
    response_model=SupplierContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar contacto a proveedor",
    dependencies=[Depends(require_permission("suppliers:manage"))],
)
async def add_contact(
    supplier_id: int,
    payload: SupplierContactCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> SupplierContactResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    created = await use_cases.add_contact(
        company_id,
        supplier_id=supplier_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="supplier_contacts",
        resource_id=str(created.id),
        after_state={"supplier_id": created.supplier_id, "full_name": created.full_name},
    )
    return created


@router.put(
    "/contacts/{contact_id}",
    response_model=SupplierContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar contacto de proveedor",
    dependencies=[Depends(require_permission("suppliers:manage"))],
)
async def update_contact(
    contact_id: int,
    payload: SupplierContactUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> SupplierContactResponse:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_contact(company_id, contact_id)
    updated = await use_cases.update_contact(
        company_id,
        contact_id=contact_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        is_active=payload.is_active,
    )
    await audit.record(
        action=_status_action(before.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
        resource_type="supplier_contacts",
        resource_id=str(contact_id),
        before_state={
            "supplier_id": before.supplier_id,
            "full_name": before.full_name,
            "is_active": before.is_active,
        },
        after_state={
            "supplier_id": updated.supplier_id,
            "full_name": updated.full_name,
            "is_active": updated.is_active,
        },
    )
    return updated


@router.post(
    "/contacts/{contact_id}/deactivate",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar contacto de proveedor",
    dependencies=[Depends(require_permission("suppliers:manage"))],
)
async def deactivate_contact(
    contact_id: int,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await use_cases.get_contact(company_id, contact_id)
    await use_cases.deactivate_contact(company_id, contact_id)
    if before.is_active:
        await audit.record(
            action="DEACTIVATE",
            user_id=current.id,
            company_id=company_id,
            resource_type="supplier_contacts",
            resource_id=str(contact_id),
            before_state={"is_active": True},
            after_state={"is_active": False},
        )
    return MessageOut(
        message=(
            "Contacto desactivado exitosamente"
            if before.is_active
            else "El contacto ya estaba desactivado"
        )
    )


@router.delete(
    "/contacts/{contact_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar contacto de proveedor (compatibilidad)",
    deprecated=True,
    dependencies=[Depends(require_permission("suppliers:manage"))],
)
async def deactivate_contact_legacy(
    contact_id: int,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: SupplierUseCases = Depends(_get_supplier_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    return await deactivate_contact(contact_id, request, session, current, use_cases, audit)

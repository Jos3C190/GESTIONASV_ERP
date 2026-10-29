"""Read-only expense-type options for purchase-order forms."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_order_use_cases,
    require_permission,
)
from app.api.v1.schemas.expense_type import (
    ExpenseTypeCatalogResponse,
    ExpenseTypeCreate,
    ExpenseTypeResponse,
    ExpenseTypeUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.purchase_orders import PurchaseOrderUseCases
from app.core.exceptions import ConflictError

router = APIRouter(prefix="/expense-types", tags=["expense-types"])


def _catalog_out(item) -> ExpenseTypeCatalogResponse:
    return ExpenseTypeCatalogResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        is_active=item.is_active,
        usage_count=item.usage_count,
    )


def _audit_state(item) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "description": item.description,
        "is_active": item.is_active,
        "usage_count": item.usage_count,
    }


@router.get(
    "",
    response_model=list[ExpenseTypeResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar tipos de gasto activos",
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def list_expense_types(
    request: Request,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> list[ExpenseTypeResponse]:
    company_id = request_company_id(request)
    items = await use_cases.list_active_expense_types(company_id)
    return [
        ExpenseTypeResponse(
            id=item.id,
            name=item.name,
            description=item.description,
        )
        for item in items
    ]


@router.get(
    "/catalog",
    response_model=list[ExpenseTypeCatalogResponse],
    status_code=status.HTTP_200_OK,
    summary="Administrar catálogo de tipos de gasto",
    dependencies=[Depends(require_permission("expense_types:manage"))],
)
async def list_expense_type_catalog(
    request: Request,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> list[ExpenseTypeCatalogResponse]:
    company_id = request_company_id(request)
    items = await use_cases.list_expense_type_catalog(company_id)
    return [_catalog_out(item) for item in items]


@router.post(
    "",
    response_model=ExpenseTypeCatalogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear tipo de gasto",
    dependencies=[Depends(require_permission("expense_types:manage"))],
)
async def create_expense_type(
    payload: ExpenseTypeCreate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ExpenseTypeCatalogResponse:
    company_id = request_company_id(request)
    try:
        item = await use_cases.create_expense_type(
            company_id,
            name=payload.name,
            description=payload.description,
        )
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Ya existe un tipo de gasto con ese nombre en esta empresa.",
            code="expense_type_duplicate",
        ) from exc
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="expense_types",
        resource_id=str(item.id),
        after_state=_audit_state(item),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _catalog_out(item)


@router.patch(
    "/{expense_type_id}",
    response_model=ExpenseTypeCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar o cambiar estado del tipo de gasto",
    dependencies=[Depends(require_permission("expense_types:manage"))],
)
async def update_expense_type(
    expense_type_id: uuid.UUID,
    payload: ExpenseTypeUpdate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ExpenseTypeCatalogResponse:
    company_id = request_company_id(request)
    before = await use_cases.list_expense_type_catalog(company_id)
    previous = next((entry for entry in before if entry.id == expense_type_id), None)
    try:
        item = await use_cases.update_expense_type(
            company_id,
            expense_type_id,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
        )
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Ya existe un tipo de gasto con ese nombre en esta empresa.",
            code="expense_type_duplicate",
        ) from exc
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="expense_types",
        resource_id=str(item.id),
        before_state=_audit_state(previous) if previous is not None else None,
        after_state=_audit_state(item),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _catalog_out(item)

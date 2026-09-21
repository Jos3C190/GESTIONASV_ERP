"""Retaceo HTTP API with tenant scope, branch scope, RBAC and audit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_use_cases,
    get_retaceo_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.retaceo import RetaceoCreate, RetaceoResponse, RetaceoUpdate
from app.application.audit.audit_service import AuditService
from app.application.purchases import PurchaseUseCases
from app.application.retaceos import RetaceoUseCases
from app.domain.entities.retaceo import Retaceo, RetaceoStatus

router = APIRouter(prefix="/retaceos", tags=["retaceos"])


def _retaceo_audit_state(item: Retaceo) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "purchase_id": str(item.purchase_id),
        "branch_id": str(item.branch_id),
        "created_by_id": str(item.created_by_id),
        "currency": item.currency,
        "total_fob": str(item.total_fob),
        "total_freight": str(item.total_freight),
        "total_expenses": str(item.total_expenses),
        "total_dai": str(item.total_dai),
        "import_vat": str(item.import_vat),
        "total_cost": str(item.total_cost),
        "status": item.status.value,
        "notes": item.notes,
        "details": [
            {
                "id": str(detail.id),
                "purchase_detail_id": str(detail.purchase_detail_id),
                "product_id": detail.product_id,
                "unit_id": detail.unit_id,
                "quantity": str(detail.quantity),
                "cost_fob": str(detail.cost_fob),
                "freight": str(detail.freight),
                "expenses": str(detail.expenses),
                "dai": str(detail.dai),
                "total_cost": str(detail.total_cost),
                "unit_cost": str(detail.unit_cost),
            }
            for detail in item.details
        ],
    }


async def _audit_change(
    *,
    action: str,
    request: Request,
    current: CurrentUser,
    audit: AuditService,
    company_id: uuid.UUID,
    item: Retaceo,
    before: Retaceo | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=current.id,
        company_id=company_id,
        branch_id=item.branch_id,
        resource_type="retaceos",
        resource_id=str(item.id),
        before_state=_retaceo_audit_state(before) if before is not None else None,
        after_state=_retaceo_audit_state(item),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


async def _visible_retaceo(
    *,
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases,
) -> tuple[uuid.UUID, Retaceo]:
    company_id = request_company_id(request)
    item = await use_cases.get_retaceo(company_id, retaceo_id)
    await resolve_branch_scope(session, current, company_id, item.branch_id)
    return company_id, item


@router.get(
    "",
    response_model=Page[RetaceoResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar retaceos",
    dependencies=[Depends(require_permission("retaceos:read"))],
)
async def list_retaceos(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    status_filter: RetaceoStatus | None = Query(None, alias="status"),
    purchase_id: uuid.UUID | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
) -> Page[RetaceoResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    items, total = await use_cases.list_retaceos(
        company_id,
        status=status_filter,
        purchase_id=purchase_id,
        branch_id=branch_id,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[RetaceoResponse.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/{retaceo_id}",
    response_model=RetaceoResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener retaceo",
    dependencies=[Depends(require_permission("retaceos:read"))],
)
async def get_retaceo(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
) -> RetaceoResponse:
    _company_id, item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    return RetaceoResponse.model_validate(item)


@router.post(
    "",
    response_model=RetaceoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear borrador de retaceo desde compra",
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def create_retaceo(
    payload: RetaceoCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    purchase_use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> RetaceoResponse:
    company_id = request_company_id(request)
    purchase = await purchase_use_cases.get_purchase(company_id, payload.purchase_id)
    await resolve_branch_scope(session, current, company_id, purchase.branch_id)
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=current.id,
        purchase_id=payload.purchase_id,
        total_freight=payload.total_freight,
        total_expenses=payload.total_expenses,
        total_dai=payload.total_dai,
        import_vat=payload.import_vat,
        notes=payload.notes,
    )
    await _audit_change(
        action="CREATE",
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=created,
    )
    return RetaceoResponse.model_validate(created)


@router.put(
    "/{retaceo_id}",
    response_model=RetaceoResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar borrador de retaceo",
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def update_retaceo(
    retaceo_id: uuid.UUID,
    payload: RetaceoUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> RetaceoResponse:
    company_id, before = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    updated = await use_cases.update_draft(
        company_id=company_id,
        retaceo_id=retaceo_id,
        total_freight=payload.total_freight,
        total_expenses=payload.total_expenses,
        total_dai=payload.total_dai,
        import_vat=payload.import_vat,
        notes=payload.notes,
    )
    await _audit_change(
        action="UPDATE",
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=updated,
        before=before,
    )
    return RetaceoResponse.model_validate(updated)


async def _transition_retaceo(
    *,
    action: str,
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases,
    audit: AuditService,
) -> RetaceoResponse:
    company_id, before = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    if action == "CALCULATE":
        updated = await use_cases.calculate_retaceo(company_id, retaceo_id)
    elif action == "VERIFY":
        updated = await use_cases.verify_retaceo(company_id, retaceo_id)
    elif action == "CANCEL":
        updated = await use_cases.cancel_retaceo(company_id, retaceo_id)
    elif action == "CLOSE":
        updated = await use_cases.close_retaceo(company_id, retaceo_id)
    else:
        raise ValueError(f"Acción de retaceo no soportada: {action}")

    await _audit_change(
        action=action,
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=updated,
        before=before,
    )
    return RetaceoResponse.model_validate(updated)


@router.post(
    "/{retaceo_id}/calculate",
    response_model=RetaceoResponse,
    status_code=status.HTTP_200_OK,
    summary="Congelar cálculo de retaceo",
    dependencies=[Depends(require_permission("retaceos:calculate"))],
)
async def calculate_retaceo(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> RetaceoResponse:
    return await _transition_retaceo(
        action="CALCULATE",
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{retaceo_id}/verify",
    response_model=RetaceoResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar retaceo calculado",
    dependencies=[Depends(require_permission("retaceos:verify"))],
)
async def verify_retaceo(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> RetaceoResponse:
    return await _transition_retaceo(
        action="VERIFY",
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{retaceo_id}/cancel",
    response_model=RetaceoResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar retaceo",
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def cancel_retaceo(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> RetaceoResponse:
    return await _transition_retaceo(
        action="CANCEL",
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{retaceo_id}/close",
    response_model=RetaceoResponse,
    status_code=status.HTTP_200_OK,
    summary="Cerrar retaceo verificado",
    dependencies=[Depends(require_permission("retaceos:verify"))],
)
async def close_retaceo(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> RetaceoResponse:
    return await _transition_retaceo(
        action="CLOSE",
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )

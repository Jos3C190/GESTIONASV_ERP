"""Purchase-request HTTP API with tenant scope, RBAC and audit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_request_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.purchase_request import (
    PurchaseRequestCreate,
    PurchaseRequestDetailInput,
    PurchaseRequestResponse,
    PurchaseRequestUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.purchase_requests import PurchaseRequestLineDraft, PurchaseRequestUseCases
from app.domain.entities.purchase_request import PurchaseRequest, PurchaseRequestStatus

router = APIRouter(prefix="/purchase-requests", tags=["purchase-requests"])


def _line_drafts(
    details: tuple[PurchaseRequestDetailInput, ...],
) -> tuple[PurchaseRequestLineDraft, ...]:
    return tuple(
        PurchaseRequestLineDraft(
            product_id=detail.product_id,
            quantity=detail.quantity,
            description=detail.description,
            notes=detail.notes,
        )
        for detail in details
    )


def _detail_audit_state(detail: object) -> dict[str, object]:
    return {
        "id": str(getattr(detail, "id", "")),
        "product_id": getattr(detail, "product_id", None),
        "unit_id": getattr(detail, "unit_id", None),
        "quantity": str(getattr(detail, "quantity", "")),
        "description": getattr(detail, "description", None),
        "notes": getattr(detail, "notes", None),
    }


def _purchase_request_audit_state(item: PurchaseRequest) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "branch_id": str(item.branch_id),
        "warehouse_id": str(item.warehouse_id),
        "requested_by_id": str(item.requested_by_id),
        "request_date": item.request_date.isoformat(),
        "required_date": item.required_date.isoformat() if item.required_date else None,
        "justification": item.justification,
        "status": item.status.value,
        "notes": item.notes,
        "details": [_detail_audit_state(detail) for detail in item.details],
    }


def _audit_request_metadata(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def _visible_request(
    *,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases,
    request_id: uuid.UUID,
) -> tuple[uuid.UUID, PurchaseRequest]:
    company_id = request_company_id(request)
    item = await use_cases.get_request(company_id, request_id)
    await resolve_branch_scope(session, current, company_id, item.branch_id)
    return company_id, item


@router.get(
    "",
    response_model=Page[PurchaseRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar solicitudes de compra",
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def list_purchase_requests(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    status_filter: PurchaseRequestStatus | None = Query(None, alias="status"),
    branch_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
) -> Page[PurchaseRequestResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    items, total = await use_cases.list_requests(
        company_id,
        status=status_filter,
        branch_id=branch_id,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[PurchaseRequestResponse.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/{request_id}",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener solicitud de compra",
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def get_purchase_request(
    request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
) -> PurchaseRequestResponse:
    _company_id, item = await _visible_request(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        request_id=request_id,
    )
    return PurchaseRequestResponse.model_validate(item)


@router.post(
    "",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear solicitud de compra",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def create_purchase_request(
    payload: PurchaseRequestCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseRequestResponse:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, payload.branch_id)
    created = await use_cases.create_request(
        company_id=company_id,
        requested_by_id=current.id,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        required_date=payload.required_date,
        justification=payload.justification,
        notes=payload.notes,
        lines=_line_drafts(payload.details),
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=created.branch_id,
        resource_type="purchase_requests",
        resource_id=str(created.id),
        after_state=_purchase_request_audit_state(created),
        required=True,
        **_audit_request_metadata(request),
    )
    return PurchaseRequestResponse.model_validate(created)


@router.put(
    "/{request_id}",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar borrador de solicitud de compra",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def update_purchase_request(
    request_id: uuid.UUID,
    payload: PurchaseRequestUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseRequestResponse:
    company_id, before = await _visible_request(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        request_id=request_id,
    )
    await resolve_branch_scope(session, current, company_id, payload.branch_id)
    updated = await use_cases.replace_draft(
        company_id=company_id,
        request_id=request_id,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        required_date=payload.required_date,
        justification=payload.justification,
        notes=payload.notes,
        lines=_line_drafts(payload.details),
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=updated.branch_id,
        resource_type="purchase_requests",
        resource_id=str(updated.id),
        before_state=_purchase_request_audit_state(before),
        after_state=_purchase_request_audit_state(updated),
        required=True,
        **_audit_request_metadata(request),
    )
    return PurchaseRequestResponse.model_validate(updated)


async def _transition_purchase_request(
    *,
    action: str,
    request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases,
    audit: AuditService,
) -> PurchaseRequestResponse:
    company_id, before = await _visible_request(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        request_id=request_id,
    )
    operations = {
        "SUBMIT": use_cases.submit_request,
        "APPROVE": use_cases.approve_request,
        "REJECT": use_cases.reject_request,
        "CANCEL": use_cases.cancel_request,
    }
    updated = await operations[action](company_id, request_id)
    await audit.record(
        action=action,
        user_id=current.id,
        company_id=company_id,
        branch_id=updated.branch_id,
        resource_type="purchase_requests",
        resource_id=str(updated.id),
        before_state=_purchase_request_audit_state(before),
        after_state=_purchase_request_audit_state(updated),
        required=True,
        **_audit_request_metadata(request),
    )
    return PurchaseRequestResponse.model_validate(updated)


@router.post(
    "/{request_id}/submit",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar solicitud de compra a aprobación",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def submit_purchase_request(
    request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseRequestResponse:
    return await _transition_purchase_request(
        action="SUBMIT",
        request_id=request_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{request_id}/approve",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprobar solicitud de compra",
    dependencies=[Depends(require_permission("purchase_requests:approve"))],
)
async def approve_purchase_request(
    request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseRequestResponse:
    return await _transition_purchase_request(
        action="APPROVE",
        request_id=request_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{request_id}/reject",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Rechazar solicitud de compra",
    dependencies=[Depends(require_permission("purchase_requests:approve"))],
)
async def reject_purchase_request(
    request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseRequestResponse:
    return await _transition_purchase_request(
        action="REJECT",
        request_id=request_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{request_id}/cancel",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar solicitud de compra",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def cancel_purchase_request(
    request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseRequestUseCases = Depends(get_purchase_request_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseRequestResponse:
    return await _transition_purchase_request(
        action="CANCEL",
        request_id=request_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )

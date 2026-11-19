"""Invalidar o corregir un documento fiscal emitido (bloque V4b).

Consultar el plazo y el historial pide ``sales_invoices:read``. Invalidar y corregir piden
``sales_invoices:invalidate``; invalidar cancelando el pedido pide además ``sales:cancel``.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_check_permission_use_case,
    get_fiscal_invalidation_use_cases,
    require_permission,
)
from app.api.v1.routers.sales_invoices import document_out
from app.api.v1.schemas.sales_invalidation import (
    CorrectIn,
    CorrectionOut,
    InvalidateIn,
    InvalidationOut,
    InvalidationOverviewOut,
    PersonOut,
)
from app.application.audit.audit_service import AuditService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales_invoices.invalidation import FiscalInvalidationUseCases, Requester
from app.core.exceptions import AuthorizationError
from app.domain.entities.sales_fiscal_invalidation import FiscalInvalidation
from app.infrastructure.dte_worker import enqueue_fiscal_document, enqueue_fiscal_invalidation

router = APIRouter(prefix="/sales/fiscal-documents", tags=["sales-invoices"])

UseCases = Annotated[FiscalInvalidationUseCases, Depends(get_fiscal_invalidation_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_invoices:read"))]
_INVALIDATE = [Depends(require_permission("sales_invoices:invalidate"))]


def invalidation_out(item: FiscalInvalidation) -> InvalidationOut:
    return InvalidationOut(
        id=item.id,
        document_id=item.document_id,
        kind=int(item.kind),  # type: ignore[arg-type]
        reason=item.reason,
        requester=PersonOut(**asdict(item.requester)),
        responsible=PersonOut(**asdict(item.responsible)) if item.responsible else None,
        replacement_document_id=item.replacement_document_id,
        cancel_order=item.cancel_order,
        status=item.status.value,
        attempts=item.attempts,
        event_generation_code=item.event_generation_code,
        event_seal=item.event_seal,
        error_code=item.error_code,
        error_message=item.error_message,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
    )


def _requester(body: CorrectIn | InvalidateIn) -> Requester:
    return Requester(
        body.requester.name, body.requester.document_type, body.requester.document_number
    )


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    item: FiscalInvalidation,
    details: dict[str, Any] | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=item.company_id,
        resource_type="sales_fiscal_document",
        resource_id=str(item.document_id),
        after_state={
            "invalidation_id": str(item.id),
            "kind": int(item.kind),
            "reason": item.reason,
            "requester": item.requester.name,
            "cancel_order": item.cancel_order,
            "replacement_document_id": (
                str(item.replacement_document_id) if item.replacement_document_id else None
            ),
            **(details or {}),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


@router.get(
    "/{document_id}/invalidation",
    response_model=InvalidationOverviewOut,
    summary="Plazo para invalidar el documento y sus solicitudes",
    dependencies=_READ,
)
async def invalidation_overview(
    document_id: uuid.UUID, company_id: CompanyId, cases: UseCases
) -> InvalidationOverviewOut:
    window = await cases.window(company_id, document_id)
    history = await cases.history(company_id, document_id)
    return InvalidationOverviewOut(
        deadline=window.deadline if window else None,
        expired=window.expired if window else False,
        estimated=window.estimated if window else False,
        history=[invalidation_out(item) for item in history],
    )


@router.post(
    "/{document_id}/invalidate",
    response_model=InvalidationOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Anular el documento (rescindir la operación) y, si se pide, cancelar el pedido",
    dependencies=_INVALIDATE,
)
async def invalidate_document(
    document_id: uuid.UUID,
    body: InvalidateIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
    checker: Checker,
) -> InvalidationOut:
    if (
        body.cancel_order
        and not (await checker.execute(current.id, company_id, "sales:cancel")).allowed
    ):
        raise AuthorizationError("Permiso requerido: sales:cancel", code="forbidden")
    item = await cases.invalidate(
        company_id,
        document_id,
        actor_id=current.id,
        reason=body.reason,
        requester=_requester(body),
        cancel_order=body.cancel_order,
    )
    await _record(audit, request, action="REQUEST_INVALIDATION", actor=current.id, item=item)
    await enqueue_fiscal_invalidation(item.id)
    return invalidation_out(item)


@router.post(
    "/{document_id}/correct",
    response_model=CorrectionOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Corregir el documento: emitir el reemplazo e invalidar el original al sellarse",
    dependencies=_INVALIDATE,
)
async def correct_document(
    document_id: uuid.UUID,
    body: CorrectIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> CorrectionOut:
    correction = await cases.correct(
        company_id, document_id, actor_id=current.id, requester=_requester(body)
    )
    await _record(
        audit,
        request,
        action="CORRECT_FISCAL_DOCUMENT",
        actor=current.id,
        item=correction.invalidation,
    )
    await enqueue_fiscal_document(correction.replacement.id)
    await enqueue_fiscal_invalidation(correction.invalidation.id)
    return CorrectionOut(
        replacement=document_out(correction.replacement),
        invalidation=invalidation_out(correction.invalidation),
    )

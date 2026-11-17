"""Contingencia de facturación por establecimiento (bloque V4a).

Consultar las ventanas pide ``sales_invoices:read``; activarlas, cerrarlas, reenviar el evento y
registrar al responsable piden ``sales_invoices:contingency``. Cada acción queda en la bitácora.
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
    get_contingency_use_cases,
    require_permission,
)
from app.api.v1.schemas.sales_contingency import (
    ContingencyActivateIn,
    ContingencyDocumentsOut,
    ContingencyOverviewOut,
    ContingencyResponsibleIn,
    ContingencyResponsibleOut,
    ContingencyWindowOut,
)
from app.application.audit.audit_service import AuditService
from app.application.sales_invoices.contingency import ContingencyUseCases
from app.domain.entities.fiscal_contingency import ContingencyResponsible, ContingencyWindow
from app.domain.entities.sales_fiscal_document import CONTINGENCY_TYPES

router = APIRouter(prefix="/sales/contingencies", tags=["sales-contingencies"])

UseCases = Annotated[ContingencyUseCases, Depends(get_contingency_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_invoices:read"))]
_OPERATE = [Depends(require_permission("sales_invoices:contingency"))]


def _window_out(window: ContingencyWindow, branches: dict[str, str]) -> ContingencyWindowOut:
    return ContingencyWindowOut(
        id=window.id,
        establishment_code=window.establishment_code,
        branch_name=branches.get(window.establishment_code or ""),
        status=window.status,
        contingency_type=window.contingency_type,
        contingency_label=CONTINGENCY_TYPES.get(window.contingency_type, "Otro"),
        reason=window.reason,
        forced=window.forced,
        started_at=window.started_at,
        ended_at=window.ended_at,
        documents=ContingencyDocumentsOut(**asdict(window.documents)),
        event_status=window.event_status,
        event_seal=window.event_seal,
        event_sealed_at=window.event_sealed_at,
        event_deadline=window.event_deadline,
        event_overdue=window.event_overdue,
        transmission_deadline=window.transmission_deadline,
        transmission_overdue=window.transmission_overdue,
        last_error=window.last_error,
    )


def _responsible_out(
    responsible: ContingencyResponsible | None,
) -> ContingencyResponsibleOut | None:
    return ContingencyResponsibleOut(**asdict(responsible)) if responsible else None


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


def _window_state(window: ContingencyWindow) -> dict[str, Any]:
    return {
        "establishment_code": window.establishment_code,
        "status": window.status,
        "contingency_type": window.contingency_type,
        "reason": window.reason,
        "documents": window.documents.total,
        "event_status": window.event_status,
        "event_seal": window.event_seal,
    }


@router.get(
    "",
    response_model=ContingencyOverviewOut,
    summary="Ventanas de contingencia de la empresa y su responsable",
    dependencies=_READ,
)
async def list_contingencies(company_id: CompanyId, cases: UseCases) -> ContingencyOverviewOut:
    overview = await cases.overview(company_id)
    branches = await cases.establishment_codes(company_id)
    return ContingencyOverviewOut(
        windows=[_window_out(window, branches) for window in overview.windows],
        responsible=_responsible_out(await cases.responsible(company_id)),
        active=any(window.status == "ACTIVA" for window in overview.windows),
    )


@router.post(
    "",
    response_model=ContingencyWindowOut,
    status_code=status.HTTP_201_CREATED,
    summary="Activar la contingencia de un establecimiento",
    dependencies=_OPERATE,
)
async def activate_contingency(
    body: ContingencyActivateIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ContingencyWindowOut:
    window = await cases.activate(
        company_id,
        establishment_id=body.establishment_id,
        contingency_type=body.contingency_type,
        reason=body.reason,
    )
    await _record(
        audit,
        request,
        action="ACTIVATE_CONTINGENCY",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_contingency",
        resource_id=str(window.id),
        after={**_window_state(window), "establishment_id": str(body.establishment_id)},
    )
    return _window_out(window, await cases.establishment_codes(company_id))


@router.post(
    "/{window_id}/close",
    response_model=ContingencyWindowOut,
    summary="Cerrar la contingencia e informar el evento",
    dependencies=_OPERATE,
)
async def close_contingency(
    window_id: int,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ContingencyWindowOut:
    window = await cases.close(company_id, window_id)
    await _record(
        audit,
        request,
        action="CLOSE_CONTINGENCY",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_contingency",
        resource_id=str(window.id),
        after=_window_state(window),
    )
    return _window_out(window, await cases.establishment_codes(company_id))


@router.post(
    "/{window_id}/event",
    response_model=ContingencyWindowOut,
    summary="Reenviar el Evento de Contingencia",
    dependencies=_OPERATE,
)
async def send_contingency_event(
    window_id: int,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ContingencyWindowOut:
    window = await cases.send_event(company_id, window_id)
    await _record(
        audit,
        request,
        action="SEND_CONTINGENCY_EVENT",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_contingency",
        resource_id=str(window.id),
        after=_window_state(window),
    )
    return _window_out(window, await cases.establishment_codes(company_id))


@router.put(
    "/responsible",
    response_model=ContingencyResponsibleOut,
    summary="Registrar al responsable que firma el Evento de Contingencia",
    dependencies=_OPERATE,
)
async def save_responsible(
    body: ContingencyResponsibleIn,
    request: Request,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> ContingencyResponsibleOut:
    before, saved = await cases.save_responsible(
        company_id,
        name=body.name,
        document_type=body.document_type,
        document_number=body.document_number,
        actor_id=current.id,
    )
    await _record(
        audit,
        request,
        action="UPDATE" if before else "CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="company_contingency_responsible",
        resource_id=str(company_id),
        before=asdict(before) if before else None,
        after=asdict(saved),
    )
    out = _responsible_out(saved)
    assert out is not None
    return out

"""Evento de retorno sobre una factura sellada (bloque V4d2).

Consultar el saldo y los retornos pide ``sales_invoices:read``; registrar y anular un retorno pide
``sales_invoices:returns``. El retorno queda pendiente y el trabajador DTE lo transmite y lo envía
al cliente.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.v1.after_commit import run_after_commit
from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_sales_fiscal_return_use_cases,
    require_permission,
)
from app.api.v1.schemas.sales_fiscal_return import (
    AnnulReturnIn,
    FiscalReturnOut,
    ReturnIn,
    ReturnLineOut,
    ReturnsOverviewOut,
)
from app.api.v1.schemas.sales_invalidation import PersonOut
from app.api.v1.schemas.sales_note import CcfLineOut
from app.application.audit.audit_service import AuditService
from app.application.sales_invoices.returns import SalesFiscalReturnUseCases
from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.domain.entities.sales_fiscal_returns import ReturnLineRequest
from app.domain.ports.sales_fiscal_return_repository import FiscalReturn
from app.infrastructure.dte_worker import (
    dte_client,
    enqueue_fiscal_return,
    enqueue_return_annulment,
)

router = APIRouter(tags=["sales-invoices"])

UseCases = Annotated[SalesFiscalReturnUseCases, Depends(get_sales_fiscal_return_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_invoices:read"))]
_RETURNS = [Depends(require_permission("sales_invoices:returns"))]


def return_out(item: FiscalReturn) -> FiscalReturnOut:
    requester = item.annul_requester
    return FiscalReturnOut(
        id=item.id,
        document_id=item.document_id,
        reason=item.reason,
        status=item.status.value,
        total=item.total,
        generation_code=item.generation_code,
        seal=item.seal,
        error_code=item.error_code,
        error_message=item.error_message,
        issued_at=item.issued_at,
        has_json=item.dte_json is not None,
        lines=[
            ReturnLineOut(
                line_number=line.line_number,
                invoice_line_number=line.invoice_line_number,
                nature=line.nature.value,
                description=line.description,
                quantity=line.quantity,
                amount=line.amount,
                vat=line.vat,
            )
            for line in item.lines
        ],
        annul_status=item.annul_status.value if item.annul_status else None,
        annul_requester=(
            PersonOut(
                name=requester.name,
                document_type=requester.document_type,
                document_number=requester.document_number,
            )
            if requester
            else None
        ),
        annul_seal=item.annul_seal,
        annul_error_code=item.annul_error_code,
        annul_error_message=item.annul_error_message,
        annulled_at=item.annulled_at,
        created_at=item.created_at,
    )


async def _invoice_scope(
    cases: SalesFiscalReturnUseCases,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> uuid.UUID:
    invoice = await cases.invoice(company_id, document_id)
    await resolve_branch_scope(session, current, company_id, invoice.branch_id)
    return invoice.branch_id


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    branch_id: uuid.UUID,
    item: FiscalReturn,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=item.company_id,
        branch_id=branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(item.document_id),
        after_state={
            "return_id": str(item.id),
            "status": item.status.value,
            "annul_status": item.annul_status.value if item.annul_status else None,
            "total": str(item.total),
            "reason": item.reason,
            "lines": [
                {"invoice_line": line.invoice_line_number, "quantity": str(line.quantity)}
                for line in item.lines
            ],
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


def _require_service() -> None:
    if not settings.DTE_SERVICE_URL:
        raise BusinessRuleError(
            "La facturación electrónica no está configurada en este servidor.",
            code="sales_invoice_service_unavailable",
        )


@router.get(
    "/sales/fiscal-documents/{document_id}/returns",
    response_model=ReturnsOverviewOut,
    summary="Saldo de la factura por línea, plazo y sus eventos de retorno",
    dependencies=_READ,
)
async def returns_overview(
    document_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> ReturnsOverviewOut:
    await _invoice_scope(cases, session, current, company_id, document_id)
    overview = await cases.overview(company_id, document_id)
    return ReturnsOverviewOut(
        invoice_id=overview.invoice.id,
        deadline=overview.deadline,
        withholding=overview.withholding,
        blocker=overview.blocker,
        lines=[
            CcfLineOut(
                number=b.line.number,
                code=b.line.code,
                description=b.line.description,
                nature=b.line.nature.value,
                quantity=b.line.quantity,
                unit_price=b.line.unit_price,
                net=b.line.net,
                returned=b.returned,
                credited=b.credited,
                remaining_quantity=b.remaining_quantity,
                remaining_amount=b.remaining_amount,
            )
            for b in overview.balances
        ],
        returns=[return_out(item) for item in overview.returns],
    )


@router.post(
    "/sales/fiscal-documents/{document_id}/returns",
    response_model=FiscalReturnOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Registrar un evento de retorno sobre la factura",
    dependencies=_RETURNS,
)
async def register_return(
    document_id: uuid.UUID,
    body: ReturnIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> FiscalReturnOut:
    _require_service()
    branch_id = await _invoice_scope(cases, session, current, company_id, document_id)
    item = await cases.register(
        company_id,
        document_id,
        actor_id=current.id,
        reason=body.reason,
        lines=[ReturnLineRequest(line.invoice_line_number, line.quantity) for line in body.lines],
    )
    await _record(
        audit,
        request,
        action="ISSUE_FISCAL_RETURN",
        actor=current.id,
        branch_id=branch_id,
        item=item,
    )
    run_after_commit(session, lambda: enqueue_fiscal_return(item.id))
    return return_out(item)


@router.post(
    "/sales/fiscal-returns/{return_id}/annul",
    response_model=FiscalReturnOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Anular un evento de retorno (invalidación tipo 2 del evento)",
    dependencies=_RETURNS,
)
async def annul_return(
    return_id: uuid.UUID,
    body: AnnulReturnIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> FiscalReturnOut:
    _require_service()
    found = await cases.get(company_id, return_id)
    branch_id = await _invoice_scope(cases, session, current, company_id, found.document_id)
    item = await cases.annul(
        company_id,
        return_id,
        actor_id=current.id,
        requester=ContingencyResponsible(
            body.requester.name, body.requester.document_type, body.requester.document_number
        ),
    )
    await _record(
        audit,
        request,
        action="ANNUL_FISCAL_RETURN",
        actor=current.id,
        branch_id=branch_id,
        item=item,
    )
    run_after_commit(session, lambda: enqueue_return_annulment(item.id))
    return return_out(item)


@router.get(
    "/sales/fiscal-returns/{return_id}/json",
    summary="JSON del evento de retorno",
    dependencies=_READ,
)
async def return_json(
    return_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> Response:
    item = await cases.get(company_id, return_id)
    await _invoice_scope(cases, session, current, company_id, item.document_id)
    if item.dte_json is None:
        raise BusinessRuleError(
            "El evento de retorno todavía no tiene su JSON.", code="sales_return_not_issued"
        )
    return Response(
        content=json.dumps(item.dte_json, ensure_ascii=False),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="retorno-{item.generation_code}.json"'
        },
    )


@router.get(
    "/sales/fiscal-returns/{return_id}/pdf",
    summary="PDF del evento de retorno",
    dependencies=_READ,
)
async def return_pdf(
    return_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> Response:
    item = await cases.get(company_id, return_id)
    await _invoice_scope(cases, session, current, company_id, item.document_id)
    invoice = await cases.invoice(company_id, item.document_id)
    client = dte_client()
    if client is None or item.generation_code is None or item.dte_json is None:
        raise BusinessRuleError(
            "El evento de retorno todavía no tiene su PDF.", code="sales_return_not_issued"
        )
    pdf = await client.invalidation_pdf(
        str(invoice.issuer_snapshot["nit"]), str(item.generation_code).upper()
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="retorno-{item.generation_code}.pdf"'},
    )

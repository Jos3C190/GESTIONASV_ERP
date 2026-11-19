"""Notas de crédito y de débito sobre un crédito fiscal sellado (bloque V4c).

Consultar el saldo y las notas pide ``sales_invoices:read``; emitirlas pide ``sales_invoices:notes``.
La nota queda pendiente y el trabajador DTE la emite y la envía por correo al cliente.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_sales_fiscal_note_use_cases,
    require_permission,
)
from app.api.v1.routers.sales_invoices import document_out
from app.api.v1.schemas.sales_invoice import FiscalDocumentOut
from app.api.v1.schemas.sales_note import (
    CcfLineOut,
    CreditNoteIn,
    DebitNoteIn,
    NoteLineOut,
    NoteOut,
    NotesOverviewOut,
)
from app.application.audit.audit_service import AuditService
from app.application.sales_invoices.notes import SalesFiscalNoteUseCases
from app.core.config import settings
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_notes import (
    CreditLineRequest,
    DebitChargeRequest,
    Nature,
    NoteLineKind,
)
from app.domain.ports.sales_fiscal_repository import FiscalDocument
from app.infrastructure.dte_worker import enqueue_fiscal_document

router = APIRouter(prefix="/sales/fiscal-documents", tags=["sales-invoices"])

UseCases = Annotated[SalesFiscalNoteUseCases, Depends(get_sales_fiscal_note_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_invoices:read"))]
_NOTES = [Depends(require_permission("sales_invoices:notes"))]


async def _scope(
    cases: SalesFiscalNoteUseCases,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    document = await cases.ccf(company_id, document_id)
    await resolve_branch_scope(session, current, company_id, document.branch_id)


async def _record(
    audit: AuditService, request: Request, *, action: str, actor: uuid.UUID, note: FiscalDocument
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=note.company_id,
        branch_id=note.branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(note.id),
        after_state={
            "status": note.status.value,
            "document_type": note.document_type,
            "related_document_id": str(note.related_document_id),
            "sale_id": str(note.sale_id),
            "total": str(note.total),
            "reason": note.note_reason,
            "mode": note.mode,
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
    "/{document_id}/notes",
    response_model=NotesOverviewOut,
    summary="Saldo del crédito fiscal por línea, plazo y sus notas",
    dependencies=_READ,
)
async def notes_overview(
    document_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> NotesOverviewOut:
    await _scope(cases, session, current, company_id, document_id)
    overview = await cases.overview(company_id, document_id)
    return NotesOverviewOut(
        ccf_id=overview.ccf.id,
        deadline=overview.deadline,
        withholding=overview.withholding,
        perception=overview.perception,
        credit_blocker=overview.credit_blocker,
        debit_blocker=overview.debit_blocker,
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
        notes=[
            NoteOut(
                document=document_out(note),
                lines=[
                    NoteLineOut(
                        line_number=line.line_number,
                        ccf_line_number=line.ccf_line_number,
                        kind=line.kind,  # type: ignore[arg-type]
                        nature=line.nature,  # type: ignore[arg-type]
                        description=line.description,
                        quantity=line.quantity,
                        amount=line.amount,
                    )
                    for line in overview.lines.get(note.id, [])
                ],
            )
            for note in overview.notes
        ],
    )


@router.post(
    "/{document_id}/credit-note",
    response_model=FiscalDocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Emitir una nota de crédito sobre el crédito fiscal",
    dependencies=_NOTES,
)
async def issue_credit_note(
    document_id: uuid.UUID,
    body: CreditNoteIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> FiscalDocumentOut:
    _require_service()
    await _scope(cases, session, current, company_id, document_id)
    note = await cases.credit_note(
        company_id,
        document_id,
        actor_id=current.id,
        reason=body.reason,
        requests=[
            CreditLineRequest(
                ccf_line_number=line.ccf_line_number,
                kind=NoteLineKind(line.kind),
                quantity=line.quantity,
                amount=line.amount,
            )
            for line in body.lines
        ],
    )
    await _record(audit, request, action="ISSUE_CREDIT_NOTE", actor=current.id, note=note)
    # Se confirma antes de encolar para que el trabajador encuentre la fila.
    await session.commit()
    await enqueue_fiscal_document(note.id)
    return document_out(note)


@router.post(
    "/{document_id}/debit-note",
    response_model=FiscalDocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Emitir una nota de débito sobre el crédito fiscal",
    dependencies=_NOTES,
)
async def issue_debit_note(
    document_id: uuid.UUID,
    body: DebitNoteIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> FiscalDocumentOut:
    _require_service()
    await _scope(cases, session, current, company_id, document_id)
    note = await cases.debit_note(
        company_id,
        document_id,
        actor_id=current.id,
        reason=body.reason,
        requests=[
            DebitChargeRequest(
                description=charge.description,
                quantity=charge.quantity,
                unit_price=charge.unit_price,
                nature=Nature(charge.nature) if charge.nature else None,
                ccf_line_number=charge.ccf_line_number,
            )
            for charge in body.charges
        ],
    )
    await _record(audit, request, action="ISSUE_DEBIT_NOTE", actor=current.id, note=note)
    await session.commit()
    await enqueue_fiscal_document(note.id)
    return document_out(note)

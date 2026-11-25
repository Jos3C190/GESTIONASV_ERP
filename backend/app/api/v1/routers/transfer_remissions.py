"""Nota de remisión de un traslado (bloque V4d).

La nota se crea sola al despachar (ver ``inventory_transfers.dispatch_transfer``). Aquí se consulta
desde el traslado y, si Hacienda la rechazó o la emisión falló, se emite de nuevo con los datos del
despacho. La corrección de una nota sellada (tipo 1) va por la invalidación del documento fiscal.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder

from app.api.v1.after_commit import run_after_commit
from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_transfer_remission_use_cases,
    require_permission,
)
from app.api.v1.routers.inventory_transfers import (
    _require_dynamic_permission,
    _transfer_branch_scope,
)
from app.api.v1.routers.sales_invoices import document_out
from app.api.v1.schemas.sales_invoice import FiscalDocumentOut, TransferRemissionOut
from app.application.audit.audit_service import AuditService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales_invoices.remission import TransferRemissionUseCases
from app.infrastructure.dte_worker import enqueue_fiscal_document

router = APIRouter(prefix="/inventory/transfers", tags=["inventory-transfers"])

CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
UseCases = Annotated[TransferRemissionUseCases, Depends(get_transfer_remission_use_cases)]


def enqueue_after_commit(session: SessionDep, document_id: uuid.UUID) -> None:
    run_after_commit(session, lambda: enqueue_fiscal_document(document_id))


@router.get(
    "/{transfer_id}/remission",
    response_model=TransferRemissionOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def transfer_remission(
    transfer_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
) -> TransferRemissionOut:
    await _transfer_branch_scope(session, current, company_id, transfer_id)
    status = await cases.status(company_id, transfer_id)
    return TransferRemissionOut(
        enabled=status.enabled,
        document=document_out(status.document) if status.document else None,
    )


@router.post(
    "/{transfer_id}/remission/reissue",
    response_model=FiscalDocumentOut,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def reissue_transfer_remission(
    transfer_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> FiscalDocumentOut:
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    document = await cases.reissue(company_id, transfer_id, current.id)
    out = document_out(document)
    await audit.record(
        action="REISSUE_TRANSFER_REMISSION",
        user_id=current.id,
        company_id=company_id,
        branch_id=branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(document.id),
        after_state=jsonable_encoder(out),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    enqueue_after_commit(session, document.id)
    return out

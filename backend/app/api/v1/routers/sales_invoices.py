"""Facturar el pedido y consultar sus documentos fiscales (bloque V3b).

Las rutas del pedido usan el convertidor UUID para convivir con ``/sales/fiscal-documents``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from app.api.v1.company_access import get_branch_context, request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_object_storage,
    get_sales_invoice_email_use_cases,
    get_sales_invoice_use_cases,
    require_permission,
)
from app.api.v1.schemas.sales_invoice import (
    DownloadUrlOut,
    FiscalDocumentOut,
    FiscalDocumentPage,
    FiscalEmailHistoryOut,
    FiscalEmailIn,
    FiscalEmailOut,
    InvoiceIn,
    InvoiceOptionsOut,
    PointOfSaleOut,
)
from app.application.audit.audit_service import AuditService
from app.application.sales_invoices import SalesInvoiceUseCases
from app.application.sales_invoices.emails import SalesInvoiceEmailUseCases
from app.core.config import settings
from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.entities.sales_renta import validate_renta
from app.domain.ports.object_storage import ObjectStorage
from app.domain.ports.sales_fiscal_repository import (
    FiscalDocument,
    FiscalDocumentEmail,
    FiscalDocumentFilters,
)
from app.infrastructure.dte_worker import enqueue_fiscal_document, enqueue_fiscal_email

router = APIRouter(prefix="/sales", tags=["sales-invoices"])

UseCases = Annotated[SalesInvoiceUseCases, Depends(get_sales_invoice_use_cases)]
EmailUseCases = Annotated[SalesInvoiceEmailUseCases, Depends(get_sales_invoice_email_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Storage = Annotated[ObjectStorage, Depends(get_object_storage)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_invoices:read"))]
_ISSUE = [Depends(require_permission("sales_invoices:issue"))]
_STATUS_PATTERN = "^(pending|contingency|issued|simulated|rejected|failed|invalidated)$"
_SERVICE_MISSING = "La facturación electrónica no está configurada en este servidor."


def document_out(document: FiscalDocument) -> FiscalDocumentOut:
    return FiscalDocumentOut(
        id=document.id,
        company_id=document.company_id,
        branch_id=document.branch_id,
        sale_id=document.sale_id,
        transfer_id=document.transfer_id,
        transfer_code=document.transfer_code,
        sale_code=document.sale_code,
        customer_name=document.customer_name,
        customer_email=document.customer_email,
        establishment_code=document.establishment_code,
        point_of_sale_code=document.point_of_sale_code,
        document_type=document.document_type,  # type: ignore[arg-type]
        mode=document.mode,
        status=document.status.value,
        generation_code=document.generation_code,
        control_number=document.control_number,
        total=document.total,
        seal=document.seal,
        attempts=document.attempts,
        error_code=document.error_code,
        error_message=document.error_message,
        has_json=document.dte_json is not None,
        has_pdf=document.pdf_object_key is not None,
        issued_at=document.issued_at,
        contingency_type=document.contingency_type,
        contingency_reason=document.contingency_reason,
        contingency_at=document.contingency_at,
        replaces_document_id=document.replaces_document_id,
        superseded_by_id=document.superseded_by_id,
        renta_operation_type=document.renta_operation_type,
        renta_income_type=document.renta_income_type,
        related_document_id=document.related_document_id,
        note_reason=document.note_reason,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _require_service() -> None:
    if not settings.DTE_SERVICE_URL:
        raise BusinessRuleError(_SERVICE_MISSING, code="sales_invoice_service_unavailable")


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    document: FiscalDocument,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=document.company_id,
        branch_id=document.branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(document.id),
        after_state={
            "status": document.status.value,
            "sale_id": str(document.sale_id),
            "document_type": document.document_type,
            "mode": document.mode,
            "total": str(document.total),
            "point_of_sale_id": str(document.point_of_sale_id),
            "issuer_sha256": document.issuer_snapshot.get("snapshotSha256"),
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


async def _scoped(
    use_cases: SalesInvoiceUseCases,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> FiscalDocument:
    document = await use_cases.get(company_id, document_id)
    await resolve_branch_scope(session, current, company_id, document.branch_id)
    return document


# --- pedido ------------------------------------------------------------------------------------


@router.get(
    "/{order_id:uuid}/invoice-options",
    response_model=InvoiceOptionsOut,
    summary="Qué hace falta para facturar el pedido",
    dependencies=_READ,
)
async def invoice_options(
    order_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
) -> InvoiceOptionsOut:
    order = await use_cases.order(company_id, order_id)
    await resolve_branch_scope(session, current, company_id, order.branch_id)
    options = await use_cases.options(company_id, order_id)
    blockers = list(options.blockers)
    if not settings.DTE_SERVICE_URL:
        blockers.insert(0, _SERVICE_MISSING)
    return InvoiceOptionsOut(
        document_type=options.document_type,
        mode=options.mode,
        establishment_code=options.establishment_code,
        points_of_sale=[
            PointOfSaleOut(id=p.id, code=p.code, name=p.name) for p in options.points_of_sale
        ],
        blockers=blockers,
        document=document_out(options.document) if options.document else None,
        previous_document=document_out(options.previous) if options.previous else None,
        renta_operation_type=options.renta.operation_type if options.renta else None,
        renta_income_type=options.renta.income_type if options.renta else None,
    )


@router.post(
    "/{order_id:uuid}/invoice",
    response_model=FiscalDocumentOut,
    status_code=202,
    summary="Facturar el pedido confirmado",
    dependencies=_ISSUE,
)
async def invoice_order(
    order_id: uuid.UUID,
    body: InvoiceIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    audit: Audit,
) -> FiscalDocumentOut:
    _require_service()
    order = await use_cases.order(company_id, order_id)
    await resolve_branch_scope(session, current, company_id, order.branch_id)
    renta = (
        validate_renta(body.renta_operation_type, body.renta_income_type)
        if body.renta_operation_type is not None or body.renta_income_type is not None
        else None
    )
    issued = await use_cases.issue(
        company_id, order_id, current.id, body.point_of_sale_id, renta=renta
    )
    if issued.created:
        await _record(
            audit,
            request,
            action="ISSUE_FISCAL_DOCUMENT",
            actor=current.id,
            document=issued.document,
        )
    else:
        response.status_code = 200
    # Se confirma antes de encolar para que el trabajador encuentre la fila.
    await session.commit()
    if issued.created:
        await enqueue_fiscal_document(issued.document.id)
    return document_out(issued.document)


# --- documentos fiscales -------------------------------------------------------------------------


@router.get(
    "/fiscal-documents",
    response_model=FiscalDocumentPage,
    summary="Documentos fiscales de la empresa",
    dependencies=_READ,
)
async def list_fiscal_documents(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    branch_id: uuid.UUID | None = None,
    sale_id: uuid.UUID | None = None,
    status: Annotated[str | None, Query(pattern=_STATUS_PATTERN)] = None,
    document_type: Annotated[str | None, Query(pattern="^(01|03|04|05|06)$")] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FiscalDocumentPage:
    branch_ids: tuple[uuid.UUID, ...] | None = None
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    else:
        context = await get_branch_context(session, current, company_id)
        if not context.access_all_branches:
            branch_ids = tuple(item.id for item in context.branches)
    filters = FiscalDocumentFilters(
        branch_ids=branch_ids,
        branch_id=branch_id,
        sale_id=sale_id,
        status=status,
        document_type=document_type,
        search=q,
    )
    items, total = await use_cases.list_documents(company_id, filters, page=page, size=size)
    return FiscalDocumentPage(
        items=[document_out(item) for item in items],
        page=page,
        size=size,
        total=total,
        pages=max(1, -(-total // size)),
    )


@router.get(
    "/fiscal-documents/{document_id:uuid}",
    response_model=FiscalDocumentOut,
    summary="Un documento fiscal",
    dependencies=_READ,
)
async def get_fiscal_document(
    document_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
) -> FiscalDocumentOut:
    return document_out(await _scoped(use_cases, session, current, company_id, document_id))


@router.post(
    "/fiscal-documents/{document_id:uuid}/retry",
    response_model=FiscalDocumentOut,
    status_code=202,
    summary="Reintentar la emisión con la misma clave de idempotencia",
    dependencies=_ISSUE,
)
async def retry_fiscal_document(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    audit: Audit,
) -> FiscalDocumentOut:
    _require_service()
    await _scoped(use_cases, session, current, company_id, document_id)
    document = await use_cases.retry(company_id, document_id)
    await _record(
        audit, request, action="RETRY_FISCAL_DOCUMENT", actor=current.id, document=document
    )
    await session.commit()
    await enqueue_fiscal_document(document.id)
    return document_out(document)


@router.get(
    "/fiscal-documents/{document_id:uuid}/json",
    summary="JSON del DTE tal como lo entregó el servicio",
    dependencies=_READ,
)
async def download_fiscal_json(
    document_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
) -> JSONResponse:
    document = await _scoped(use_cases, session, current, company_id, document_id)
    if document.dte_json is None:
        raise ConflictError(
            "El JSON del DTE aún no está disponible.", code="sales_invoice_not_ready"
        )
    filename = f"{document.control_number}.json"
    return JSONResponse(
        content=document.dte_json,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/fiscal-documents/{document_id:uuid}/pdf",
    response_model=DownloadUrlOut,
    summary="Enlace temporal para ver el PDF del DTE en el navegador",
    dependencies=_READ,
)
async def download_fiscal_pdf(
    document_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    storage: Storage,
) -> DownloadUrlOut:
    document = await _scoped(use_cases, session, current, company_id, document_id)
    if document.pdf_object_key is None:
        raise ConflictError(
            "El PDF del DTE aún no está disponible.", code="sales_invoice_not_ready"
        )
    url = await storage.presign_preview(
        document.pdf_object_key,
        filename=f"{document.control_number}.pdf",
        content_type="application/pdf",
        expires_seconds=settings.OBJECT_STORAGE_DOWNLOAD_TTL_SECONDS,
    )
    return DownloadUrlOut(url=url)


# --- correo ---------------------------------------------------------------------------------------


def _email_out(email: FiscalDocumentEmail) -> FiscalEmailOut:
    return FiscalEmailOut(
        id=email.id,
        document_id=email.document_id,
        recipients=list(email.recipients),
        origin=email.origin,  # type: ignore[arg-type]
        status=email.status,  # type: ignore[arg-type]
        attempts=email.attempts,
        error_code=email.error_code,
        error_message=email.error_message,
        requested_by_name=email.requested_by_name,
        invalidation_id=email.invalidation_id,
        sent_at=email.sent_at,
        created_at=email.created_at,
    )


@router.get(
    "/fiscal-documents/{document_id:uuid}/emails",
    response_model=FiscalEmailHistoryOut,
    summary="Envíos por correo del documento fiscal",
    dependencies=_READ,
)
async def fiscal_document_emails(
    document_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    emails: EmailUseCases,
) -> FiscalEmailHistoryOut:
    document = await _scoped(use_cases, session, current, company_id, document_id)
    items = await emails.history(company_id, document_id)
    return FiscalEmailHistoryOut(
        enabled=await emails.available(company_id),
        customer_email=document.customer_email,
        items=[_email_out(item) for item in items],
    )


@router.post(
    "/fiscal-documents/{document_id:uuid}/emails",
    response_model=FiscalEmailOut,
    status_code=202,
    summary="Enviar el documento fiscal por correo",
    dependencies=_ISSUE,
)
async def send_fiscal_document_email(
    document_id: uuid.UUID,
    body: FiscalEmailIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    emails: EmailUseCases,
    audit: Audit,
) -> FiscalEmailOut:
    await _scoped(use_cases, session, current, company_id, document_id)
    document, email = await emails.request(company_id, document_id, current.id, body.recipients)
    await audit.record(
        action="REQUEST_FISCAL_DOCUMENT_EMAIL",
        user_id=current.id,
        company_id=company_id,
        branch_id=document.branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(document.id),
        after_state={"email_id": str(email.id), "recipients": list(email.recipients)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    await session.commit()
    await enqueue_fiscal_email(email.id)
    return _email_out(email)

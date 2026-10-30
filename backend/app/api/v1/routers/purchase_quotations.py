"""Purchase-quotation HTTP API with tenant scope, RBAC and strict audit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.v1.company_access import get_branch_context, request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_consolidation_use_cases,
    get_purchase_quotation_document_service,
    get_purchase_quotation_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.documents import DownloadUrlOut
from app.api.v1.schemas.purchase_quotation import (
    PurchaseQuotationComparisonResponse,
    PurchaseQuotationCreate,
    PurchaseQuotationDocumentInitiate,
    PurchaseQuotationDocumentResponse,
    PurchaseQuotationDocumentUploadResponse,
    PurchaseQuotationExpenseInput,
    PurchaseQuotationRecordResponse,
    PurchaseQuotationRequestInput,
    PurchaseQuotationResponse,
    PurchaseQuotationResponseLineInput,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import InitiateDocumentInput
from app.application.purchase_consolidations import PurchaseConsolidationUseCases
from app.application.purchase_quotations import (
    PurchaseQuotationExpenseDraft,
    PurchaseQuotationRequestDraft,
    PurchaseQuotationRequestLineDraft,
    PurchaseQuotationResponseLineDraft,
    PurchaseQuotationUseCases,
)
from app.application.purchase_quotations.documents import PurchaseQuotationDocumentService
from app.domain.entities.document import DocumentAsset
from app.domain.entities.purchase_quotation import PurchaseQuotation, PurchaseQuotationStatus
from app.domain.entities.purchase_quotation_document import PurchaseQuotationDocument
from app.infrastructure.models.organization import Branch, Warehouse

router = APIRouter(prefix="/purchase-quotations", tags=["purchase-quotations"])


def _request_drafts(
    requests: tuple[PurchaseQuotationRequestInput, ...],
) -> tuple[PurchaseQuotationRequestDraft, ...]:
    return tuple(
        PurchaseQuotationRequestDraft(
            purchase_request_id=item.purchase_request_id,
            lines=tuple(
                PurchaseQuotationRequestLineDraft(
                    purchase_request_detail_id=line.purchase_request_detail_id,
                    quantity=line.quantity,
                )
                for line in item.lines
            ),
        )
        for item in requests
    )


def _response_line_drafts(
    lines: tuple[PurchaseQuotationResponseLineInput, ...],
) -> tuple[PurchaseQuotationResponseLineDraft, ...]:
    return tuple(
        PurchaseQuotationResponseLineDraft(
            product_id=line.product_id,
            unit_id=line.unit_id,
            offered_quantity=line.offered_quantity,
            unit_price=line.unit_price,
            discount=line.discount,
            tax_rate=line.tax_rate,
            delivery_days=line.delivery_days,
            available_quantity=line.available_quantity,
            notes=line.notes,
        )
        for line in lines
    )


def _expense_drafts(
    expenses: tuple[PurchaseQuotationExpenseInput, ...],
) -> tuple[PurchaseQuotationExpenseDraft, ...]:
    return tuple(
        PurchaseQuotationExpenseDraft(
            expense_type_id=expense.expense_type_id,
            amount=expense.amount,
            description=expense.description,
        )
        for expense in expenses
    )


def _quotation_audit_state(item: PurchaseQuotation) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "supplier_id": item.supplier_id,
        "quotation_date": item.quotation_date.isoformat(),
        "valid_until": item.valid_until.isoformat() if item.valid_until else None,
        "currency": item.currency,
        "payment_terms": item.payment_terms,
        "delivery_days": item.delivery_days,
        "subtotal": str(item.subtotal),
        "discount": str(item.discount),
        "tax": str(item.tax),
        "total": str(item.total),
        "status": item.status.value,
        "notes": item.notes,
        "response_notes": item.response_notes,
        "consolidation_id": str(item.consolidation_id) if item.consolidation_id else None,
        "consolidation_code": item.consolidation_code,
        "version_number": item.version_number,
        "sent_at": item.sent_at.isoformat() if item.sent_at else None,
        "request_links": [
            {
                "purchase_request_id": str(link.purchase_request_id),
                "details": [
                    {
                        "purchase_request_detail_id": str(detail.purchase_request_detail_id),
                        "quantity": str(detail.quantity),
                    }
                    for detail in link.details
                ],
            }
            for link in item.request_links
        ],
        "details": [
            {
                "product_id": detail.product_id,
                "unit_id": detail.unit_id,
                "quantity": str(detail.quantity),
                "offered_quantity": (
                    str(detail.offered_quantity) if detail.offered_quantity is not None else None
                ),
                "unit_price": str(detail.unit_price),
                "discount": str(detail.discount),
                "tax_rate": str(detail.tax_rate),
                "total": str(detail.total),
                "delivery_days": detail.delivery_days,
                "available_quantity": (
                    str(detail.available_quantity)
                    if detail.available_quantity is not None
                    else None
                ),
            }
            for detail in item.details
        ],
        "snapshots": [
            {
                "purchase_quotation_detail_id": str(snapshot.purchase_quotation_detail_id),
                "consolidation_line_id": str(snapshot.consolidation_line_id),
                "product_sku": snapshot.product_sku,
                "product_name": snapshot.product_name,
                "unit_name": snapshot.unit_name,
                "branch_quantity": str(snapshot.branch_quantity),
                "central_quantity": str(snapshot.central_quantity),
                "sources": [
                    {
                        "purchase_request_id": str(source.purchase_request_id),
                        "purchase_request_detail_id": str(source.purchase_request_detail_id),
                        "request_code": source.request_code,
                        "branch_name": source.branch_name,
                        "warehouse_name": source.warehouse_name,
                        "requester_name": source.requester_name,
                        "required_date": source.required_date.isoformat()
                        if source.required_date
                        else None,
                        "included_quantity": str(source.included_quantity),
                    }
                    for source in snapshot.sources
                ],
            }
            for snapshot in item.snapshots
        ],
        "expenses": [
            {
                "expense_type_id": str(expense.expense_type_id),
                "amount": str(expense.amount),
                "description": expense.description,
            }
            for expense in item.expenses
        ],
    }


async def _audit_change(
    *,
    action: str,
    request: Request,
    current: CurrentUser,
    audit: AuditService,
    company_id: uuid.UUID,
    item: PurchaseQuotation,
    before: PurchaseQuotation | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=current.id,
        company_id=company_id,
        resource_type="purchase_quotations",
        resource_id=str(item.id),
        before_state=_quotation_audit_state(before) if before is not None else None,
        after_state=_quotation_audit_state(item),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


async def _visible_purchase_quotation(
    *,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseQuotationUseCases,
    quotation_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    consolidation_id: uuid.UUID | None = None,
    consolidation_use_cases: PurchaseConsolidationUseCases | None = None,
) -> tuple[uuid.UUID, PurchaseQuotation]:
    company_id = request_company_id(request)
    if consolidation_id is not None:
        if consolidation_use_cases is None:
            raise HTTPException(
                status_code=500, detail="No se pudo validar el consolidado de origen."
            )
        consolidation = await consolidation_use_cases.get(company_id, consolidation_id)
        context = await get_branch_context(session, current, company_id)
        if not context.access_all_branches:
            inaccessible = {
                source.branch_id
                for line in consolidation.lines
                for source in line.sources
                if not context.can_access(source.branch_id)
            }
            if inaccessible:
                raise HTTPException(
                    status_code=403,
                    detail="No tiene acceso a todas las sucursales del consolidado.",
                )
        if consolidation.central_warehouse_id is not None:
            central_warehouse_result = await session.execute(
                select(
                    Warehouse.company_id,
                    Warehouse.branch_id,
                    Warehouse.is_central,
                    Branch.is_headquarters,
                )
                .outerjoin(
                    Branch,
                    (Branch.id == Warehouse.branch_id)
                    & (Branch.company_id == Warehouse.company_id),
                )
                .where(
                    Warehouse.id == consolidation.central_warehouse_id,
                    Warehouse.company_id == company_id,
                    Warehouse.deleted_at.is_(None),
                    Warehouse.is_active.is_(True),
                    Warehouse.operational_status == "active",
                )
            )
            central_warehouse = central_warehouse_result.one_or_none()
            if central_warehouse is None or central_warehouse.branch_id is None:
                raise HTTPException(status_code=404, detail="Almacén central no encontrado.")
            if central_warehouse.is_central and not central_warehouse.is_headquarters:
                raise HTTPException(
                    status_code=409, detail="La bodega central no está vinculada a la matriz."
                )
            await resolve_branch_scope(session, current, company_id, central_warehouse.branch_id)
        item = await use_cases.get_quotation(company_id, quotation_id)
        if item.consolidation_id != consolidation_id:
            raise HTTPException(
                status_code=404, detail="Cotización no encontrada en este consolidado."
            )
        return company_id, item

    await resolve_branch_scope(session, current, company_id, branch_id)
    item = await use_cases.get_quotation(
        company_id,
        quotation_id,
        branch_id=branch_id,
    )
    return company_id, item


@router.get(
    "",
    response_model=Page[PurchaseQuotationResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar cotizaciones de compra",
    dependencies=[Depends(require_permission("purchase_quotations:read"))],
)
async def list_purchase_quotations(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    status_filter: PurchaseQuotationStatus | None = Query(None, alias="status"),
    supplier_id: int | None = Query(None, gt=0),
    branch_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
) -> Page[PurchaseQuotationResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    items, total = await use_cases.list_quotations(
        company_id,
        branch_id=branch_id,
        status=status_filter,
        supplier_id=supplier_id,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[PurchaseQuotationResponse.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/comparison/{purchase_request_id}",
    response_model=list[PurchaseQuotationComparisonResponse],
    status_code=status.HTTP_200_OK,
    summary="Comparar ofertas para una solicitud de compra",
    dependencies=[Depends(require_permission("purchase_quotations:read"))],
)
async def compare_purchase_quotation_offers(
    purchase_request_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    branch_id: uuid.UUID | None = Query(None),
    currency: str | None = Query(None, min_length=3, max_length=3),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
) -> list[PurchaseQuotationComparisonResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    rows = await use_cases.compare_offers(
        company_id,
        purchase_request_id,
        branch_id=branch_id,
        currency=currency,
    )
    return [PurchaseQuotationComparisonResponse.model_validate(row) for row in rows]


@router.get(
    "/{quotation_id}",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener cotización de compra",
    dependencies=[Depends(require_permission("purchase_quotations:read"))],
)
async def get_purchase_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
) -> PurchaseQuotationResponse:
    _, item = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    return PurchaseQuotationResponse.model_validate(item)


def _quotation_document_out(
    attachment: PurchaseQuotationDocument,
    document: DocumentAsset,
) -> PurchaseQuotationDocumentResponse:
    return PurchaseQuotationDocumentResponse(
        id=attachment.id,
        purchase_quotation_id=attachment.purchase_quotation_id,
        document_id=attachment.document_id,
        file_name=attachment.file_name,
        file_type=attachment.file_type,
        size_bytes=document.size_bytes,
        status=document.status,
        failure_code=document.failure_code,
        uploaded_at=attachment.uploaded_at,
        created_at=attachment.created_at,
        updated_at=attachment.updated_at,
    )


@router.post(
    "/{quotation_id}/documents/uploads",
    response_model=PurchaseQuotationDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar carga del documento original de una oferta de proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def initiate_purchase_quotation_document(
    quotation_id: uuid.UUID,
    payload: PurchaseQuotationDocumentInitiate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    service: PurchaseQuotationDocumentService = Depends(get_purchase_quotation_document_service),
) -> PurchaseQuotationDocumentUploadResponse:
    company_id, _ = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    upload = await service.initiate(
        company_id,
        current.id,
        quotation_id,
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=current.id,
            filename=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            checksum_sha256=payload.checksum_sha256,
        ),
    )
    return PurchaseQuotationDocumentUploadResponse(
        document=_quotation_document_out(upload.attachment, upload.ticket.document),
        upload_url=upload.ticket.upload_url,
        required_headers=upload.ticket.required_headers,
        expires_at=upload.ticket.expires_at,
    )


@router.post(
    "/{quotation_id}/documents/{document_id}/complete",
    response_model=PurchaseQuotationDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Completar y revisar el documento de oferta del proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def complete_purchase_quotation_document(
    quotation_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    service: PurchaseQuotationDocumentService = Depends(get_purchase_quotation_document_service),
) -> PurchaseQuotationDocumentResponse:
    company_id, _ = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    view = await service.complete(company_id, current.id, quotation_id, document_id)
    return _quotation_document_out(view.attachment, view.document)


@router.get(
    "/{quotation_id}/documents",
    response_model=list[PurchaseQuotationDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar documentos originales de la oferta del proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:read"))],
)
async def list_purchase_quotation_documents(
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    service: PurchaseQuotationDocumentService = Depends(get_purchase_quotation_document_service),
) -> list[PurchaseQuotationDocumentResponse]:
    company_id, _ = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    views = await service.list_documents(company_id, quotation_id)
    return [_quotation_document_out(view.attachment, view.document) for view in views]


@router.delete(
    "/{quotation_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar un documento adjunto de la oferta del proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def remove_purchase_quotation_document(
    quotation_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    service: PurchaseQuotationDocumentService = Depends(get_purchase_quotation_document_service),
) -> None:
    company_id, _ = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    await service.remove(company_id, current.id, quotation_id, document_id)


@router.post(
    "/{quotation_id}/documents/{document_id}/download-url",
    response_model=DownloadUrlOut,
    status_code=status.HTTP_200_OK,
    summary="Generar URL temporal de descarga para documento de oferta",
    dependencies=[Depends(require_permission("purchase_quotations:read"))],
)
async def create_purchase_quotation_document_download_url(
    quotation_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    service: PurchaseQuotationDocumentService = Depends(get_purchase_quotation_document_service),
) -> DownloadUrlOut:
    company_id, _ = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    url, expires_at = await service.download_url(company_id, current.id, quotation_id, document_id)
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    "",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear borrador de solicitud de cotización",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def create_purchase_quotation(
    payload: PurchaseQuotationCreate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=current.id,
        supplier_id=payload.supplier_id,
        currency=payload.currency,
        requests=_request_drafts(payload.requests),
        branch_id=branch_id,
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
    return PurchaseQuotationResponse.model_validate(created)


@router.put(
    "/{quotation_id}/response",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Registrar respuesta del proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def record_purchase_quotation_response(
    quotation_id: uuid.UUID,
    payload: PurchaseQuotationRecordResponse,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    company_id, before = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidations,
    )
    updated = await use_cases.record_response(
        company_id=company_id,
        quotation_id=quotation_id,
        quotation_date=payload.quotation_date,
        valid_until=payload.valid_until,
        payment_terms=payload.payment_terms,
        delivery_days=payload.delivery_days,
        lines=_response_line_drafts(payload.lines),
        expenses=_expense_drafts(payload.expenses),
        notes=payload.notes,
    )
    await _audit_change(
        action="RECEIVE",
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=updated,
        before=before,
    )
    return PurchaseQuotationResponse.model_validate(updated)


async def _transition_purchase_quotation(
    *,
    action: str,
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None,
    consolidation_id: uuid.UUID | None,
    use_cases: PurchaseQuotationUseCases,
    consolidation_use_cases: PurchaseConsolidationUseCases,
    audit: AuditService,
) -> PurchaseQuotationResponse:
    company_id, before = await _visible_purchase_quotation(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        quotation_id=quotation_id,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        consolidation_use_cases=consolidation_use_cases,
    )
    if action == "SEND":
        updated = await use_cases.send_request(company_id, quotation_id)
    elif action == "EVALUATE":
        updated = await use_cases.start_evaluation(company_id, quotation_id)
    elif action == "SELECT":
        updated = await use_cases.select_offer(company_id, quotation_id)
    elif action == "REJECT":
        updated = await use_cases.reject_offer(company_id, quotation_id)
    elif action == "CANCEL":
        updated = await use_cases.cancel_quotation(company_id, quotation_id)
    else:
        raise ValueError(f"Acción de cotización no soportada: {action}")

    await _audit_change(
        action=action,
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=updated,
        before=before,
    )
    return PurchaseQuotationResponse.model_validate(updated)


@router.post(
    "/{quotation_id}/send",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar solicitud de cotización al proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def send_purchase_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="SEND",
        quotation_id=quotation_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        use_cases=use_cases,
        consolidation_use_cases=consolidations,
        audit=audit,
    )


@router.post(
    "/{quotation_id}/evaluate",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Pasar cotización a evaluación",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def evaluate_purchase_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="EVALUATE",
        quotation_id=quotation_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        use_cases=use_cases,
        consolidation_use_cases=consolidations,
        audit=audit,
    )


@router.post(
    "/{quotation_id}/select",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Seleccionar oferta ganadora",
    dependencies=[Depends(require_permission("purchase_quotations:select"))],
)
async def select_purchase_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="SELECT",
        quotation_id=quotation_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        use_cases=use_cases,
        consolidation_use_cases=consolidations,
        audit=audit,
    )


@router.post(
    "/{quotation_id}/reject",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rechazar oferta del proveedor",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def reject_purchase_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="REJECT",
        quotation_id=quotation_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        use_cases=use_cases,
        consolidation_use_cases=consolidations,
        audit=audit,
    )


@router.post(
    "/{quotation_id}/cancel",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar solicitud de cotización",
    dependencies=[Depends(require_permission("purchase_quotations:manage"))],
)
async def cancel_purchase_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="CANCEL",
        quotation_id=quotation_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        consolidation_id=consolidation_id,
        use_cases=use_cases,
        consolidation_use_cases=consolidations,
        audit=audit,
    )

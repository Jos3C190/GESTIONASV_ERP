"""Retaceo HTTP API with tenant scope, branch scope, RBAC and audit."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.api.v1.company_access import (
    request_company_id,
    require_company_wide_scope,
    resolve_branch_scope,
    resolve_document_warehouse_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_use_cases,
    get_retaceo_cost_document_service,
    get_retaceo_use_cases,
    require_permission,
)
from app.api.v1.routers.inventory import _execute
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.documents import DownloadUrlOut
from app.api.v1.schemas.expense_type import ExpenseTypeResponse
from app.api.v1.schemas.retaceo import (
    RetaceoAverageComparisonResponse,
    RetaceoCostDocumentInitiate,
    RetaceoCostDocumentResponse,
    RetaceoCostDocumentUploadResponse,
    RetaceoCreate,
    RetaceoResponse,
    RetaceoUpdate,
    RetaceoValuationStatus,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import InitiateDocumentInput
from app.application.procurement_reports import retaceo_report
from app.application.purchases import PurchaseUseCases
from app.application.retaceos import RetaceoUseCases
from app.application.retaceos.cost_documents import (
    RetaceoCostDocumentService,
    RetaceoCostDocumentView,
)
from app.application.retaceos.use_cases import RetaceoCostDraft, RetaceoFobDraft
from app.domain.entities.retaceo import Retaceo, RetaceoCostAllocation, RetaceoStatus
from app.infrastructure.procurement_report_renderer import render_pdf, render_xlsx
from app.infrastructure.repositories.procurement_report_repository import (
    ProcurementReportRepository,
)

router = APIRouter(prefix="/retaceos", tags=["retaceos"])


@router.get(
    "/{retaceo_id}/export",
    response_class=Response,
    dependencies=[Depends(require_permission("retaceos:read"))],
)
async def export_retaceo(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    export_format: Literal["pdf", "xlsx"] = Query("pdf", alias="format"),
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    purchases: PurchaseUseCases = Depends(get_purchase_use_cases),
) -> Response:
    company_id, item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    purchase = await purchases.get_purchase(company_id, item.purchase_id)
    await resolve_document_warehouse_scope(
        session,
        current,
        company_id,
        document_branch_id=purchase.branch_id,
        warehouse_id=purchase.warehouse_id,
    )
    context = await ProcurementReportRepository(session).context(company_id, item)
    report = retaceo_report(item, context)
    payload = await run_in_threadpool(render_pdf if export_format == "pdf" else render_xlsx, report)
    media_type = (
        "application/pdf"
        if export_format == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return Response(
        payload,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{item.code}.{export_format}"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/cost-categories",
    response_model=list[ExpenseTypeResponse],
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def cost_categories(
    request: Request, use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases)
) -> list[ExpenseTypeResponse]:
    rows = await use_cases.cost_categories(request_company_id(request))
    return [
        ExpenseTypeResponse(id=row.id, name=row.name, description=row.description) for row in rows
    ]


@router.get(
    "/{retaceo_id}/average-comparison",
    response_model=RetaceoAverageComparisonResponse,
    dependencies=[
        Depends(require_permission("retaceos:read")),
        Depends(require_permission("inventory:valuation")),
    ],
)
async def average_comparison(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
) -> RetaceoAverageComparisonResponse:
    company_id, _ = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    await require_company_wide_scope(session, current, company_id)
    result = await _execute(session, use_cases.average_comparison(company_id, retaceo_id))
    return RetaceoAverageComparisonResponse.model_validate(result)


@router.get(
    "/{retaceo_id}/valuation-status",
    response_model=RetaceoValuationStatus,
    dependencies=[Depends(require_permission("retaceos:read"))],
)
async def valuation_status(
    retaceo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
) -> RetaceoValuationStatus:
    from app.infrastructure.repositories.inventory_valuation_repository import (
        SqlAlchemyInventoryValuationRepository,
    )

    company_id, item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    return RetaceoValuationStatus(
        enabled=await SqlAlchemyInventoryValuationRepository(session).enabled(company_id),
        inventory_after_retaceo=await use_cases.inventory_after_retaceo(
            company_id, item.purchase_id
        ),
    )


def _retaceo_audit_state(item: Retaceo) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "purchase_id": str(item.purchase_id),
        "branch_id": str(item.branch_id) if item.branch_id is not None else None,
        "created_by_id": str(item.created_by_id),
        "currency": item.currency,
        "total_fob": str(item.total_fob),
        "manual_entry": item.manual_entry,
        "total_freight": str(item.total_freight),
        "total_expenses": str(item.total_expenses),
        "total_dai": str(item.total_dai),
        "import_vat": str(item.import_vat),
        "total_cost": str(item.total_cost),
        "status": item.status.value,
        "applied_at": item.applied_at.isoformat() if item.applied_at else None,
        "origin_country": item.origin_country,
        "import_invoice_number": item.import_invoice_number,
        "import_invoice_date": item.import_invoice_date.isoformat()
        if item.import_invoice_date
        else None,
        "import_policy_number": item.import_policy_number,
        "import_policy_date": item.import_policy_date.isoformat()
        if item.import_policy_date
        else None,
        "applied_by": str(item.applied_by) if item.applied_by else None,
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
        "costs": [
            {
                "id": str(cost.id),
                "source_purchase_order_expense_id": (
                    str(cost.source_purchase_order_expense_id)
                    if cost.source_purchase_order_expense_id
                    else None
                ),
                "expense_type_id": str(cost.expense_type_id) if cost.expense_type_id else None,
                "incurred_on": cost.incurred_on.isoformat() if cost.incurred_on else None,
                "classification": cost.classification.value,
                "title": cost.title,
                "description": cost.description,
                "amount": str(cost.amount),
                "is_active": cost.is_active,
                "allocations": [
                    {
                        "purchase_detail_id": str(allocation.purchase_detail_id),
                        "amount": str(allocation.amount),
                    }
                    for allocation in cost.allocations
                ],
                "documents": [
                    {
                        "document_id": str(document.document_id),
                        "file_name": document.file_name,
                        "file_type": document.file_type,
                        "uploaded_at": (
                            document.uploaded_at.isoformat() if document.uploaded_at else None
                        ),
                    }
                    for document in cost.documents
                ],
            }
            for cost in item.costs
        ],
    }


def _cost_document_out(view: RetaceoCostDocumentView) -> RetaceoCostDocumentResponse:
    return RetaceoCostDocumentResponse(
        id=view.attachment.id,
        retaceo_cost_id=view.attachment.retaceo_cost_id,
        document_id=view.attachment.document_id,
        file_name=view.attachment.file_name,
        file_type=view.attachment.file_type,
        size_bytes=view.document.size_bytes,
        status=view.document.status,
        failure_code=view.document.failure_code,
        uploaded_at=view.attachment.uploaded_at,
        created_at=view.attachment.created_at,
        updated_at=view.attachment.updated_at,
    )


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
        manual_entry=True,
        company_id=company_id,
        created_by_id=current.id,
        purchase_id=payload.purchase_id,
        import_data=payload.import_data.to_domain() if payload.import_data is not None else None,
        fob_lines=tuple(
            RetaceoFobDraft(line.purchase_detail_id, line.amount) for line in payload.fob_lines
        )
        if payload.fob_lines is not None
        else None,
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
        import_data=payload.import_data.to_domain() if payload.import_data is not None else None,
        total_freight=payload.total_freight,
        fob_lines=tuple(
            RetaceoFobDraft(line.purchase_detail_id, line.amount) for line in payload.fob_lines
        )
        if payload.fob_lines is not None
        else None,
        total_expenses=payload.total_expenses,
        total_dai=payload.total_dai,
        import_vat=payload.import_vat,
        notes=payload.notes,
        costs=(
            tuple(
                RetaceoCostDraft(
                    id=cost.id,
                    classification=cost.classification,
                    title=cost.title,
                    description=cost.description,
                    amount=cost.amount,
                    expense_type_id=cost.expense_type_id,
                    source_purchase_order_expense_id=cost.source_purchase_order_expense_id,
                    incurred_on=cost.incurred_on,
                    allocations=tuple(
                        RetaceoCostAllocation(
                            purchase_detail_id=allocation.purchase_detail_id,
                            amount=allocation.amount,
                        )
                        for allocation in cost.allocations
                    ),
                )
                for cost in payload.costs
            )
            if payload.costs is not None
            else None
        ),
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


@router.post(
    "/{retaceo_id}/costs/{cost_id}/documents/uploads",
    response_model=RetaceoCostDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar carga de comprobante de un gasto de retaceo",
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def initiate_retaceo_cost_document(
    retaceo_id: uuid.UUID,
    cost_id: uuid.UUID,
    payload: RetaceoCostDocumentInitiate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    service: RetaceoCostDocumentService = Depends(get_retaceo_cost_document_service),
) -> RetaceoCostDocumentUploadResponse:
    company_id, _item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    upload = await service.initiate(
        company_id,
        current.id,
        retaceo_id,
        cost_id,
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=current.id,
            filename=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            checksum_sha256=payload.checksum_sha256,
        ),
    )
    return RetaceoCostDocumentUploadResponse(
        document=_cost_document_out(
            RetaceoCostDocumentView(upload.attachment, upload.ticket.document)
        ),
        upload_url=upload.ticket.upload_url,
        required_headers=upload.ticket.required_headers,
        expires_at=upload.ticket.expires_at,
    )


@router.post(
    "/{retaceo_id}/costs/{cost_id}/documents/{document_id}/complete",
    response_model=RetaceoCostDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Completar comprobante de un gasto de retaceo",
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def complete_retaceo_cost_document(
    retaceo_id: uuid.UUID,
    cost_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    service: RetaceoCostDocumentService = Depends(get_retaceo_cost_document_service),
) -> RetaceoCostDocumentResponse:
    company_id, _item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    view = await service.complete(company_id, current.id, retaceo_id, cost_id, document_id)
    return _cost_document_out(view)


@router.delete(
    "/{retaceo_id}/costs/{cost_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desvincular un comprobante de un gasto de retaceo",
    dependencies=[Depends(require_permission("retaceos:manage"))],
)
async def remove_retaceo_cost_document(
    retaceo_id: uuid.UUID,
    cost_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    service: RetaceoCostDocumentService = Depends(get_retaceo_cost_document_service),
) -> None:
    company_id, _item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    await service.remove(company_id, current.id, retaceo_id, cost_id, document_id)


@router.get(
    "/{retaceo_id}/costs/{cost_id}/documents",
    response_model=list[RetaceoCostDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar comprobantes de un gasto de retaceo",
    dependencies=[Depends(require_permission("retaceos:read"))],
)
async def list_retaceo_cost_documents(
    retaceo_id: uuid.UUID,
    cost_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    service: RetaceoCostDocumentService = Depends(get_retaceo_cost_document_service),
) -> list[RetaceoCostDocumentResponse]:
    company_id, _item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    views = await service.list_documents(company_id, retaceo_id, cost_id)
    return [_cost_document_out(view) for view in views]


@router.post(
    "/{retaceo_id}/costs/{cost_id}/documents/{document_id}/download-url",
    response_model=DownloadUrlOut,
    status_code=status.HTTP_200_OK,
    summary="Generar URL temporal de descarga del comprobante",
    dependencies=[Depends(require_permission("retaceos:read"))],
)
async def create_retaceo_cost_document_download_url(
    retaceo_id: uuid.UUID,
    cost_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: RetaceoUseCases = Depends(get_retaceo_use_cases),
    service: RetaceoCostDocumentService = Depends(get_retaceo_cost_document_service),
) -> DownloadUrlOut:
    company_id, _item = await _visible_retaceo(
        retaceo_id=retaceo_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    url, expires_at = await service.download_url(
        company_id, retaceo_id, cost_id, document_id, current.id
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


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


@router.post(
    "/{retaceo_id}/apply",
    response_model=RetaceoResponse,
    summary="Aplicar una vez el costo verificado al inventario",
    dependencies=[
        Depends(require_permission("retaceos:verify")),
        Depends(require_permission("inventory:valuation")),
    ],
)
async def apply_retaceo(
    retaceo_id: uuid.UUID,
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
    await require_company_wide_scope(session, current, company_id)
    # Savepoint also rolls back on AppError (the shared session may commit it).
    async with session.begin_nested():
        updated = await _execute(
            session, use_cases.apply_retaceo(company_id, retaceo_id, current.id)
        )
        if before.applied_at is None:
            await _audit_change(
                action="APPLY",
                request=request,
                current=current,
                audit=audit,
                company_id=company_id,
                item=updated,
                before=before,
            )
    return RetaceoResponse.model_validate(updated)

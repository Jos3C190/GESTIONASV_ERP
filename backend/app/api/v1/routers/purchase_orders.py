"""Purchase-order HTTP API with tenant scope, RBAC and strict audit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.company_access import (
    request_company_id,
    resolve_branch_scope,
    resolve_document_warehouse_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_order_expense_document_service,
    get_purchase_order_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.documents import DownloadUrlOut
from app.api.v1.schemas.purchase_order import (
    ActualExpenseAvailabilityResponse,
    ActualExpenseCreate,
    ActualExpenseResponse,
    PurchaseOrderCreate,
    PurchaseOrderExpenseDocumentInitiate,
    PurchaseOrderExpenseDocumentResponse,
    PurchaseOrderExpenseDocumentUploadResponse,
    PurchaseOrderExpenseInput,
    PurchaseOrderFromConsolidationCreate,
    PurchaseOrderLineInput,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import InitiateDocumentInput
from app.application.purchase_orders import (
    PurchaseOrderExpenseDraft,
    PurchaseOrderLineDraft,
    PurchaseOrderUseCases,
)
from app.application.purchase_orders.actual_expenses import ActualExpenseUseCases
from app.application.purchase_orders.expense_documents import (
    PurchaseOrderExpenseDocumentService,
)
from app.domain.entities.document import DocumentAsset
from app.domain.entities.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.domain.entities.purchase_order_expense_document import (
    PurchaseOrderExpenseDocument,
)
from app.infrastructure.repositories.purchase_order_repository import (
    SqlAlchemyPurchaseOrderRepository,
)

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _line_drafts(
    lines: tuple[PurchaseOrderLineInput, ...],
) -> tuple[PurchaseOrderLineDraft, ...]:
    return tuple(
        PurchaseOrderLineDraft(
            purchase_quotation_detail_id=line.purchase_quotation_detail_id,
            quantity=line.quantity,
            purchase_consolidation_award_id=line.purchase_consolidation_award_id,
        )
        for line in lines
    )


def _expense_drafts(
    expenses: tuple[PurchaseOrderExpenseInput, ...],
) -> tuple[PurchaseOrderExpenseDraft, ...]:
    return tuple(
        PurchaseOrderExpenseDraft(
            expense_type_id=expense.expense_type_id,
            amount=expense.amount,
            description=expense.description,
        )
        for expense in expenses
    )


def _order_audit_state(item: PurchaseOrder) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "supplier_id": item.supplier_id,
        "branch_id": str(item.branch_id) if item.branch_id is not None else None,
        "warehouse_id": str(item.warehouse_id),
        "purchase_quotation_id": str(item.purchase_quotation_id),
        "created_by_id": str(item.created_by_id),
        "order_date": item.order_date.isoformat(),
        "expected_date": item.expected_date.isoformat() if item.expected_date else None,
        "currency": item.currency,
        "payment_terms": item.payment_terms,
        "subtotal": str(item.subtotal),
        "discount": str(item.discount),
        "tax": str(item.tax),
        "additional_expenses": str(item.additional_expenses),
        "total": str(item.total),
        "status": item.status.value,
        "notes": item.notes,
        "details": [
            {
                "id": str(detail.id),
                "purchase_quotation_detail_id": str(detail.purchase_quotation_detail_id),
                "purchase_consolidation_award_id": (
                    str(detail.purchase_consolidation_award_id)
                    if detail.purchase_consolidation_award_id
                    else None
                ),
                "product_id": detail.product_id,
                "unit_id": detail.unit_id,
                "quantity": str(detail.quantity),
                "unit_price": str(detail.unit_price),
                "discount": str(detail.discount),
                "subtotal": str(detail.subtotal),
                "tax_rate": str(detail.tax_rate),
                "tax_amount": str(detail.tax_amount),
                "total": str(detail.total),
            }
            for detail in item.details
        ],
        "expenses": [
            {
                "id": str(expense.id),
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
    item: PurchaseOrder,
    before: PurchaseOrder | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=current.id,
        company_id=company_id,
        resource_type="purchase_orders",
        resource_id=str(item.id),
        before_state=_order_audit_state(before) if before is not None else None,
        after_state=_order_audit_state(item),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


async def _visible_purchase_order(
    *,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseOrderUseCases,
    order_id: uuid.UUID,
    branch_id: uuid.UUID | None,
) -> tuple[uuid.UUID, PurchaseOrder]:
    company_id = request_company_id(request)
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    item = await use_cases.get_order(
        company_id,
        order_id,
        branch_id=branch_id,
    )
    if item is None:
        raise HTTPException(404, "Orden de compra no encontrada.")
    await resolve_document_warehouse_scope(
        session,
        current,
        company_id,
        document_branch_id=item.branch_id,
        warehouse_id=item.warehouse_id,
    )
    return company_id, item


@router.get(
    "/{order_id}/actual-expenses/availability",
    response_model=ActualExpenseAvailabilityResponse,
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def actual_expense_availability(
    order_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> ActualExpenseAvailabilityResponse:
    company_id, order = await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        order_id=order_id,
        branch_id=None,
        use_cases=use_cases,
    )
    available = await ActualExpenseUseCases(
        SqlAlchemyPurchaseOrderRepository(session)
    ).availability(company_id, order)
    return ActualExpenseAvailabilityResponse.model_validate(available)


@router.get(
    "/{order_id}/actual-expenses",
    response_model=list[ActualExpenseResponse],
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def list_actual_expenses(
    order_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> list[ActualExpenseResponse]:
    company_id, _ = await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=None,
    )
    rows = await SqlAlchemyPurchaseOrderRepository(session).list_actual_expenses(
        company_id, order_id
    )
    return [ActualExpenseResponse.model_validate(row) for row in rows]


@router.post(
    "/{order_id}/actual-expenses",
    response_model=ActualExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def create_actual_expense(
    order_id: uuid.UUID,
    payload: ActualExpenseCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> ActualExpenseResponse:
    company_id, _ = await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=None,
    )
    item = await ActualExpenseUseCases(SqlAlchemyPurchaseOrderRepository(session)).create(
        company_id=company_id, order_id=order_id, **payload.model_dump()
    )
    result = ActualExpenseResponse.model_validate(item)
    await audit.record(
        action="ACTUAL_EXPENSE_RECORDED",
        user_id=current.id,
        company_id=company_id,
        resource_type="purchase_order_expenses",
        resource_id=str(item.id),
        after_state=result.model_dump(mode="json"),
        required=True,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return result


async def _authorize_order_destination(
    *,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    selected_branch_id: uuid.UUID | None,
    document_branch_id: uuid.UUID | None,
    warehouse_id: uuid.UUID,
) -> uuid.UUID:
    if document_branch_id is not None:
        await resolve_branch_scope(session, current, company_id, document_branch_id)
    effective_branch_id = await resolve_document_warehouse_scope(
        session,
        current,
        company_id,
        document_branch_id=document_branch_id,
        warehouse_id=warehouse_id,
    )
    if selected_branch_id is not None and effective_branch_id != selected_branch_id:
        raise HTTPException(403, "La bodega destino no pertenece a la sucursal seleccionada.")
    return effective_branch_id


@router.get(
    "",
    response_model=Page[PurchaseOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar órdenes de compra",
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def list_purchase_orders(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    status_filter: PurchaseOrderStatus | None = Query(None, alias="status"),
    supplier_id: int | None = Query(None, gt=0),
    branch_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> Page[PurchaseOrderResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    items, total = await use_cases.list_orders(
        company_id,
        branch_id=branch_id,
        status=status_filter,
        supplier_id=supplier_id,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[PurchaseOrderResponse.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/{order_id}",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener orden de compra",
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def get_purchase_order(
    order_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> PurchaseOrderResponse:
    _, item = await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    return PurchaseOrderResponse.model_validate(item)


@router.post(
    "",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear orden de compra desde cotización seleccionada",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    await _authorize_order_destination(
        session=session,
        current=current,
        company_id=company_id,
        selected_branch_id=branch_id,
        document_branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
    )
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=current.id,
        purchase_quotation_id=payload.purchase_quotation_id,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        lines=_line_drafts(payload.lines),
        quotation_branch_id=branch_id,
        expected_date=payload.expected_date,
        expenses=_expense_drafts(payload.expenses),
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
    return PurchaseOrderResponse.model_validate(created)


@router.post(
    "/from-consolidation/{consolidation_id}/{quotation_id}",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear orden de compra desde cantidades adjudicadas",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def create_purchase_order_from_consolidation(
    consolidation_id: uuid.UUID,
    quotation_id: uuid.UUID,
    payload: PurchaseOrderFromConsolidationCreate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    await _authorize_order_destination(
        session=session,
        current=current,
        company_id=company_id,
        selected_branch_id=branch_id,
        document_branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
    )
    created = await use_cases.create_draft_from_consolidation_awards(
        company_id=company_id,
        created_by_id=current.id,
        consolidation_id=consolidation_id,
        purchase_quotation_id=quotation_id,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        expected_date=payload.expected_date,
        expenses=_expense_drafts(payload.expenses),
        notes=payload.notes,
    )
    await _audit_change(
        action="CREATE_FROM_CONSOLIDATION_AWARDS",
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=created,
    )
    return PurchaseOrderResponse.model_validate(created)


@router.put(
    "/{order_id}",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar orden de compra en borrador",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def update_purchase_order(
    order_id: uuid.UUID,
    payload: PurchaseOrderUpdate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    company_id, before = await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    await _authorize_order_destination(
        session=session,
        current=current,
        company_id=company_id,
        selected_branch_id=branch_id,
        document_branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
    )
    updated = await use_cases.update_draft(
        company_id=company_id,
        order_id=order_id,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        lines=_line_drafts(payload.lines),
        quotation_branch_id=branch_id,
        expected_date=payload.expected_date,
        expenses=_expense_drafts(payload.expenses),
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
    return PurchaseOrderResponse.model_validate(updated)


async def _transition_purchase_order(
    *,
    action: str,
    order_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None,
    use_cases: PurchaseOrderUseCases,
    audit: AuditService,
) -> PurchaseOrderResponse:
    company_id, before = await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    if action == "SUBMIT":
        updated = await use_cases.submit_order(company_id, order_id)
    elif action == "APPROVE":
        updated = await use_cases.approve_order(company_id, order_id)
    elif action == "SEND":
        updated = await use_cases.send_order(company_id, order_id)
    elif action == "CANCEL":
        updated = await use_cases.cancel_order(company_id, order_id)
    else:
        raise ValueError(f"Acción de orden de compra no soportada: {action}")

    await _audit_change(
        action=action,
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=updated,
        before=before,
    )
    return PurchaseOrderResponse.model_validate(updated)


@router.post(
    "/{order_id}/submit",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar orden de compra a aprobación",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def submit_purchase_order(
    order_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    return await _transition_purchase_order(
        action="SUBMIT",
        order_id=order_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{order_id}/approve",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprobar orden de compra",
    dependencies=[Depends(require_permission("purchase_orders:approve"))],
)
async def approve_purchase_order(
    order_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    return await _transition_purchase_order(
        action="APPROVE",
        order_id=order_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{order_id}/send",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar orden de compra aprobada al proveedor",
    dependencies=[Depends(require_permission("purchase_orders:send"))],
)
async def send_purchase_order(
    order_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    return await _transition_purchase_order(
        action="SEND",
        order_id=order_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{order_id}/cancel",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar orden de compra antes de enviarla al proveedor",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def cancel_purchase_order(
    order_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseOrderResponse:
    return await _transition_purchase_order(
        action="CANCEL",
        order_id=order_id,
        request=request,
        current=current,
        session=session,
        branch_id=branch_id,
        use_cases=use_cases,
        audit=audit,
    )


def _expense_document_out(
    attachment: PurchaseOrderExpenseDocument,
    document: DocumentAsset,
) -> PurchaseOrderExpenseDocumentResponse:
    return PurchaseOrderExpenseDocumentResponse(
        id=attachment.id,
        purchase_order_expense_id=attachment.purchase_order_expense_id,
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
    "/{order_id}/expenses/{expense_id}/documents/uploads",
    response_model=PurchaseOrderExpenseDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar carga de documento para un gasto de orden de compra",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def initiate_purchase_order_expense_document(
    order_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: PurchaseOrderExpenseDocumentInitiate,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    service: PurchaseOrderExpenseDocumentService = Depends(
        get_purchase_order_expense_document_service
    ),
) -> PurchaseOrderExpenseDocumentUploadResponse:
    company_id = request_company_id(request)
    await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    upload = await service.initiate(
        order_id,
        expense_id,
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=current.id,
            filename=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            checksum_sha256=payload.checksum_sha256,
        ),
    )
    return PurchaseOrderExpenseDocumentUploadResponse(
        document=_expense_document_out(upload.attachment, upload.ticket.document),
        upload_url=upload.ticket.upload_url,
        required_headers=upload.ticket.required_headers,
        expires_at=upload.ticket.expires_at,
    )


@router.post(
    "/{order_id}/expenses/{expense_id}/documents/{document_id}/complete",
    response_model=PurchaseOrderExpenseDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Completar y escanear documento de gasto",
    dependencies=[Depends(require_permission("purchase_orders:manage"))],
)
async def complete_purchase_order_expense_document(
    order_id: uuid.UUID,
    expense_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    service: PurchaseOrderExpenseDocumentService = Depends(
        get_purchase_order_expense_document_service
    ),
) -> PurchaseOrderExpenseDocumentResponse:
    company_id = request_company_id(request)
    await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    view = await service.complete(
        company_id,
        order_id,
        expense_id,
        document_id,
        current.id,
    )
    return _expense_document_out(view.attachment, view.document)


@router.get(
    "/{order_id}/expenses/{expense_id}/documents",
    response_model=list[PurchaseOrderExpenseDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar documentos de un gasto de orden de compra",
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def list_purchase_order_expense_documents(
    order_id: uuid.UUID,
    expense_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    service: PurchaseOrderExpenseDocumentService = Depends(
        get_purchase_order_expense_document_service
    ),
) -> list[PurchaseOrderExpenseDocumentResponse]:
    company_id = request_company_id(request)
    await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    views = await service.list_documents(company_id, order_id, expense_id)
    return [_expense_document_out(view.attachment, view.document) for view in views]


@router.post(
    "/{order_id}/expenses/{expense_id}/documents/{document_id}/download-url",
    response_model=DownloadUrlOut,
    status_code=status.HTTP_200_OK,
    summary="Generar URL temporal de descarga para documento de gasto",
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def create_purchase_order_expense_document_download_url(
    order_id: uuid.UUID,
    expense_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    branch_id: uuid.UUID | None = Query(None),
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    service: PurchaseOrderExpenseDocumentService = Depends(
        get_purchase_order_expense_document_service
    ),
) -> DownloadUrlOut:
    company_id = request_company_id(request)
    await _visible_purchase_order(
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        order_id=order_id,
        branch_id=branch_id,
    )
    url, expires_at = await service.download_url(
        company_id,
        order_id,
        expense_id,
        document_id,
        current.id,
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)

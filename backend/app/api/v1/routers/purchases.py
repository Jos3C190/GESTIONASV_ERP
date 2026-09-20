"""Purchase-receipt HTTP API with tenant scope, branch scope, RBAC and audit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_order_use_cases,
    get_purchase_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.purchase import (
    PurchaseCreate,
    PurchaseLineInput,
    PurchaseReceivableLineResponse,
    PurchaseReceivableResponse,
    PurchaseResponse,
    PurchaseUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.purchase_orders import PurchaseOrderUseCases
from app.application.purchases import PurchaseLineDraft, PurchaseUseCases
from app.domain.entities.purchase import Purchase, PurchaseStatus

router = APIRouter(prefix="/purchases", tags=["purchases"])
order_router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _line_drafts(lines: tuple[PurchaseLineInput, ...]) -> tuple[PurchaseLineDraft, ...]:
    return tuple(
        PurchaseLineDraft(
            purchase_order_detail_id=line.purchase_order_detail_id,
            quantity_received=line.quantity_received,
        )
        for line in lines
    )


def _purchase_audit_state(item: Purchase) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "purchase_order_id": str(item.purchase_order_id),
        "supplier_id": item.supplier_id,
        "branch_id": str(item.branch_id),
        "warehouse_id": str(item.warehouse_id),
        "created_by_id": str(item.created_by_id),
        "purchase_date": item.purchase_date.isoformat(),
        "supplier_invoice_number": item.supplier_invoice_number,
        "supplier_invoice_date": (
            item.supplier_invoice_date.isoformat() if item.supplier_invoice_date else None
        ),
        "currency": item.currency,
        "subtotal": str(item.subtotal),
        "discount": str(item.discount),
        "tax": str(item.tax),
        "total": str(item.total),
        "status": item.status.value,
        "notes": item.notes,
        "details": [
            {
                "id": str(detail.id),
                "purchase_order_detail_id": str(detail.purchase_order_detail_id),
                "product_id": detail.product_id,
                "unit_id": detail.unit_id,
                "quantity_ordered": str(detail.quantity_ordered),
                "quantity_received": str(detail.quantity_received),
                "unit_price": str(detail.unit_price),
                "discount": str(detail.discount),
                "subtotal": str(detail.subtotal),
                "tax_rate": str(detail.tax_rate),
                "tax_amount": str(detail.tax_amount),
                "total": str(detail.total),
            }
            for detail in item.details
        ],
    }


async def _audit_change(
    *,
    action: str,
    request: Request,
    current: CurrentUser,
    audit: AuditService,
    company_id: uuid.UUID,
    item: Purchase,
    before: Purchase | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=current.id,
        company_id=company_id,
        branch_id=item.branch_id,
        resource_type="purchases",
        resource_id=str(item.id),
        before_state=_purchase_audit_state(before) if before is not None else None,
        after_state=_purchase_audit_state(item),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


async def _visible_purchase(
    *,
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases,
) -> tuple[uuid.UUID, Purchase]:
    company_id = request_company_id(request)
    item = await use_cases.get_purchase(company_id, purchase_id)
    await resolve_branch_scope(session, current, company_id, item.branch_id)
    return company_id, item


@router.get(
    "",
    response_model=Page[PurchaseResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar compras y recepciones",
    dependencies=[Depends(require_permission("purchases:read"))],
)
async def list_purchases(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    status_filter: PurchaseStatus | None = Query(None, alias="status"),
    supplier_id: int | None = Query(None, gt=0),
    purchase_order_id: uuid.UUID | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
) -> Page[PurchaseResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    items, total = await use_cases.list_purchases(
        company_id,
        status=status_filter,
        supplier_id=supplier_id,
        purchase_order_id=purchase_order_id,
        branch_id=branch_id,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[PurchaseResponse.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener compra o recepción",
    dependencies=[Depends(require_permission("purchases:read"))],
)
async def get_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
) -> PurchaseResponse:
    _company_id, item = await _visible_purchase(
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    return PurchaseResponse.model_validate(item)


@router.post(
    "",
    response_model=PurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear borrador de recepción desde orden de compra",
    dependencies=[Depends(require_permission("purchases:manage"))],
)
async def create_purchase(
    payload: PurchaseCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    order_use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseResponse:
    company_id = request_company_id(request)
    order = await order_use_cases.get_order(company_id, payload.purchase_order_id)
    await resolve_branch_scope(session, current, company_id, order.branch_id)
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=current.id,
        purchase_order_id=payload.purchase_order_id,
        lines=_line_drafts(payload.lines),
        supplier_invoice_number=payload.supplier_invoice_number,
        supplier_invoice_date=payload.supplier_invoice_date,
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
    return PurchaseResponse.model_validate(created)


@router.put(
    "/{purchase_id}",
    response_model=PurchaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar borrador de recepción",
    dependencies=[Depends(require_permission("purchases:manage"))],
)
async def update_purchase(
    purchase_id: uuid.UUID,
    payload: PurchaseUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseResponse:
    company_id, before = await _visible_purchase(
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    updated = await use_cases.update_draft(
        company_id=company_id,
        purchase_id=purchase_id,
        lines=_line_drafts(payload.lines),
        supplier_invoice_number=payload.supplier_invoice_number,
        supplier_invoice_date=payload.supplier_invoice_date,
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
    return PurchaseResponse.model_validate(updated)


async def _transition_purchase(
    *,
    action: str,
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases,
    audit: AuditService,
) -> PurchaseResponse:
    company_id, before = await _visible_purchase(
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
    )
    if action == "RECEIVE":
        updated = await use_cases.receive_purchase(company_id, purchase_id)
    elif action == "VERIFY":
        updated = await use_cases.verify_purchase(company_id, purchase_id)
    elif action == "CANCEL":
        updated = await use_cases.cancel_purchase(company_id, purchase_id)
    elif action == "CLOSE":
        updated = await use_cases.close_purchase(company_id, purchase_id)
    else:
        raise ValueError(f"Acción de compra no soportada: {action}")
    await _audit_change(
        action=action,
        request=request,
        current=current,
        audit=audit,
        company_id=company_id,
        item=updated,
        before=before,
    )
    return PurchaseResponse.model_validate(updated)


@router.post(
    "/{purchase_id}/receive",
    response_model=PurchaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirmar recepción de compra",
    dependencies=[Depends(require_permission("purchases:receive"))],
)
async def receive_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseResponse:
    return await _transition_purchase(
        action="RECEIVE",
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{purchase_id}/verify",
    response_model=PurchaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar recepción de compra",
    dependencies=[Depends(require_permission("purchases:verify"))],
)
async def verify_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseResponse:
    return await _transition_purchase(
        action="VERIFY",
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{purchase_id}/cancel",
    response_model=PurchaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancelar borrador de recepción",
    dependencies=[Depends(require_permission("purchases:manage"))],
)
async def cancel_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseResponse:
    return await _transition_purchase(
        action="CANCEL",
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@router.post(
    "/{purchase_id}/close",
    response_model=PurchaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Cerrar recepción verificada",
    dependencies=[Depends(require_permission("purchases:verify"))],
)
async def close_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseResponse:
    return await _transition_purchase(
        action="CLOSE",
        purchase_id=purchase_id,
        request=request,
        session=session,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )


@order_router.get(
    "/{order_id}/receivable",
    response_model=PurchaseReceivableResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar cantidades pendientes de recibir",
    dependencies=[Depends(require_permission("purchases:read"))],
)
async def get_purchase_order_receivable(
    order_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    order_use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> PurchaseReceivableResponse:
    company_id = request_company_id(request)
    order = await order_use_cases.get_order(company_id, order_id)
    await resolve_branch_scope(session, current, company_id, order.branch_id)
    lines = await use_cases.get_receivable_lines(company_id, order_id)
    return PurchaseReceivableResponse(
        purchase_order_id=order.id,
        code=order.code,
        status=order.status,
        supplier_id=order.supplier_id,
        branch_id=order.branch_id,
        warehouse_id=order.warehouse_id,
        currency=order.currency,
        lines=tuple(
            PurchaseReceivableLineResponse(
                purchase_order_detail_id=line.purchase_order_detail_id,
                product_id=line.product_id,
                unit_id=line.unit_id,
                quantity_ordered=line.quantity_ordered,
                quantity_received=line.quantity_received,
                quantity_pending=line.quantity_pending,
                unit_price=line.unit_price,
                discount=line.discount,
                tax_rate=line.tax_rate,
                notes=line.notes,
            )
            for line in lines
        ),
    )

"""Purchase-quotation HTTP API with tenant scope, RBAC and strict audit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_purchase_quotation_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.purchase_quotation import (
    PurchaseQuotationComparisonResponse,
    PurchaseQuotationCreate,
    PurchaseQuotationExpenseInput,
    PurchaseQuotationRecordResponse,
    PurchaseQuotationRequestInput,
    PurchaseQuotationResponse,
    PurchaseQuotationResponseLineInput,
)
from app.application.audit.audit_service import AuditService
from app.application.purchase_quotations import (
    PurchaseQuotationExpenseDraft,
    PurchaseQuotationRequestDraft,
    PurchaseQuotationRequestLineDraft,
    PurchaseQuotationResponseLineDraft,
    PurchaseQuotationUseCases,
)
from app.domain.entities.purchase_quotation import PurchaseQuotation, PurchaseQuotationStatus

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
            quantity=line.quantity,
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


@router.get(
    "",
    response_model=Page[PurchaseQuotationResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar cotizaciones de compra",
    dependencies=[Depends(require_permission("purchase_quotations:read"))],
)
async def list_purchase_quotations(
    request: Request,
    status_filter: PurchaseQuotationStatus | None = Query(None, alias="status"),
    supplier_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
) -> Page[PurchaseQuotationResponse]:
    company_id = request_company_id(request)
    items, total = await use_cases.list_quotations(
        company_id,
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
    currency: str | None = Query(None, min_length=3, max_length=3),
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
) -> list[PurchaseQuotationComparisonResponse]:
    company_id = request_company_id(request)
    rows = await use_cases.compare_offers(
        company_id,
        purchase_request_id,
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
) -> PurchaseQuotationResponse:
    company_id = request_company_id(request)
    item = await use_cases.get_quotation(company_id, quotation_id)
    return PurchaseQuotationResponse.model_validate(item)


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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    company_id = request_company_id(request)
    created = await use_cases.create_draft(
        company_id=company_id,
        created_by_id=current.id,
        supplier_id=payload.supplier_id,
        currency=payload.currency,
        requests=_request_drafts(payload.requests),
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    company_id = request_company_id(request)
    before = await use_cases.get_quotation(company_id, quotation_id)
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
    use_cases: PurchaseQuotationUseCases,
    audit: AuditService,
) -> PurchaseQuotationResponse:
    company_id = request_company_id(request)
    before = await use_cases.get_quotation(company_id, quotation_id)
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="SEND",
        quotation_id=quotation_id,
        request=request,
        current=current,
        use_cases=use_cases,
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="EVALUATE",
        quotation_id=quotation_id,
        request=request,
        current=current,
        use_cases=use_cases,
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="SELECT",
        quotation_id=quotation_id,
        request=request,
        current=current,
        use_cases=use_cases,
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="REJECT",
        quotation_id=quotation_id,
        request=request,
        current=current,
        use_cases=use_cases,
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
    use_cases: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    return await _transition_purchase_quotation(
        action="CANCEL",
        quotation_id=quotation_id,
        request=request,
        current=current,
        use_cases=use_cases,
        audit=audit,
    )

"""Cotización de venta rediseñada (bloque V2d).

Precio de lista automático, descuentos con tope, impuestos del motor fiscal, autorización,
respuesta del cliente y versión imprimible. Toda acción queda en la bitácora.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.api.v1.company_access import get_branch_context, request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_sales_quotation_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.sales_quotation import (
    AuthorizationReasonOut,
    QuotationActionIn,
    QuotationDraftIn,
    QuotationLineOut,
    QuotationNoteIn,
    QuotationOut,
    QuotationPage,
    QuotationPageMeta,
    QuotationReasonIn,
    QuotationSettingsIn,
    QuotationSettingsOut,
    QuotationUpdateIn,
)
from app.application.audit.audit_service import AuditService
from app.application.price_lists import today_in_el_salvador
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales_quotations import (
    Actor,
    Change,
    Draft,
    DraftLine,
    SalesQuotationUseCases,
)
from app.application.sales_quotations.use_cases import QuotationView
from app.domain.entities.sales_margin import REASON_TEXT, AuthorizationReason
from app.domain.ports.sales_quotation_repository import Quotation, QuotationFilters
from app.infrastructure.sales_quotation_pdf import render_quotation_pdf

router = APIRouter(prefix="/sales", tags=["sales-quotations"])

UseCases = Annotated[SalesQuotationUseCases, Depends(get_sales_quotation_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales_quotations:read"))]
_MANAGE = [Depends(require_permission("sales_quotations:manage"))]
_CONFIRM = [Depends(require_permission("sales_quotations:confirm"))]
_AUTHORIZE = [Depends(require_permission("sales_discounts:authorize"))]
_STATUS_PATTERN = "^(draft|pending_authorization|issued|expired|accepted|rejected|cancelled)$"


async def _allowed(
    checker: CheckPermissionUseCase, user: uuid.UUID, company: uuid.UUID, code: str
) -> bool:
    return (await checker.execute(user, company, code)).allowed


async def _costs_visible(
    checker: CheckPermissionUseCase, user: uuid.UUID, company: uuid.UUID
) -> bool:
    """El margen lo ve quien puede ver costos y quien autoriza descuentos."""

    return await _allowed(checker, user, company, "sales_costs:read") or await _allowed(
        checker, user, company, "sales_discounts:authorize"
    )


def _reasons(codes: tuple[str, ...]) -> list[AuthorizationReasonOut]:
    return [
        AuthorizationReasonOut(code=code, message=REASON_TEXT[AuthorizationReason(code)])
        for code in codes
    ]


def _out(view: QuotationView, costs_visible: bool) -> QuotationOut:
    quotation = view.quotation
    totals = quotation.totals
    people = view.people
    return QuotationOut(
        id=quotation.id,
        company_id=quotation.company_id,
        branch_id=quotation.branch_id,
        customer_id=quotation.customer_id,
        customer_code=view.customer.code,
        customer_name=view.customer.draft.name,
        code=quotation.code,
        quotation_date=quotation.quotation_date,
        valid_until=quotation.valid_until,
        document_type=quotation.document_type,  # type: ignore[arg-type]
        price_list_id=quotation.price_list_id,
        price_list_name=view.price_list_name,
        prices_include_vat=quotation.prices_include_vat,
        global_discount_percent=quotation.global_discount_percent,
        status=quotation.status.value,
        expired=view.expired,
        version=quotation.version,
        notes=quotation.notes,
        total_not_subject=totals.total_not_subject,
        total_exempt=totals.total_exempt,
        total_taxed=totals.total_taxed,
        subtotal_sales=totals.subtotal_sales,
        total_discount=totals.total_discount,
        subtotal=totals.subtotal,
        vat=totals.vat,
        vat_perceived=totals.vat_perceived,
        vat_withheld=totals.vat_withheld,
        total=totals.total,
        total_in_words=totals.total_in_words,
        requires_authorization=quotation.requires_authorization,
        authorization_reasons=_reasons(quotation.authorization_reasons),
        costs_visible=costs_visible,
        created_by_id=quotation.created_by_id,
        created_by_name=people.of(quotation.created_by_id),
        issued_by_name=people.of(quotation.issued_by_id),
        issued_at=quotation.issued_at,
        authorized_by_name=people.of(quotation.authorized_by_id),
        authorized_at=quotation.authorized_at,
        authorization_note=quotation.authorization_note,
        customer_response_by_name=people.of(quotation.customer_response_by_id),
        customer_response_at=quotation.customer_response_at,
        rejection_reason=quotation.rejection_reason,
        cancelled_by_name=people.of(quotation.cancelled_by_id),
        cancelled_at=quotation.cancelled_at,
        cancellation_reason=quotation.cancellation_reason,
        sale_id=view.sale.id if view.sale else None,
        sale_code=view.sale.code if view.sale else None,
        lines=[
            QuotationLineOut(
                id=line.id,
                line_number=number,
                product_id=line.identity.product_id,
                variant_id=line.identity.variant_id,
                inventory_item_id=line.identity.inventory_item_id,
                product_sku=line.identity.product_sku,
                product_name=line.identity.product_name,
                unit_id=line.identity.unit_id,
                unit_name=line.identity.unit_name,
                base_unit_id=line.identity.base_unit_id,
                base_unit_name=line.identity.base_unit_name,
                unit_factor=line.identity.unit_factor,
                quantity=line.quantity,
                quantity_base=line.quantity_base,
                price_list_id=line.price_list_id,
                list_price=line.list_price,
                price_overridden=line.price_overridden,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                suggested_discount_percent=line.suggested_discount_percent,
                suggested_discount_source=line.suggested_discount_source,  # type: ignore[arg-type]
                tax_treatment=line.tax_treatment,  # type: ignore[arg-type]
                item_type=line.item_type,  # type: ignore[arg-type]
                document_unit_price=line.document_unit_price,
                discount_amount=line.discount_amount,
                not_subject=line.not_subject,
                exempt=line.exempt,
                taxed=line.taxed,
                vat_item=line.vat_item,
                line_total=line.line_total,
                cost=line.cost if costs_visible else None,
                margin_percent=line.margin_percent if costs_visible else None,
                authorization_reasons=_reasons(line.authorization_reasons),
            )
            for number, line in enumerate(quotation.lines, start=1)
        ],
        created_at=quotation.created_at,
        updated_at=quotation.updated_at,
    )


def _state(quotation: Quotation) -> dict[str, Any]:
    """Lo que queda en la bitácora: estado, totales y, por línea, precios y descuentos."""

    return {
        "code": quotation.code,
        "status": quotation.status.value,
        "version": quotation.version,
        "customer_id": str(quotation.customer_id),
        "branch_id": str(quotation.branch_id),
        "document_type": quotation.document_type,
        "valid_until": quotation.valid_until.isoformat(),
        "global_discount_percent": str(quotation.global_discount_percent),
        "total": str(quotation.totals.total),
        "requires_authorization": quotation.requires_authorization,
        "authorization_reasons": list(quotation.authorization_reasons),
        "authorization_note": quotation.authorization_note,
        "rejection_reason": quotation.rejection_reason,
        "cancellation_reason": quotation.cancellation_reason,
        "lines": [
            {
                "product_sku": line.identity.product_sku,
                "unit_id": line.identity.unit_id,
                "quantity": str(line.quantity),
                "list_price": str(line.list_price) if line.list_price is not None else None,
                "unit_price": str(line.unit_price),
                "price_overridden": line.price_overridden,
                "discount_percent": str(line.discount_percent),
                "suggested_discount_percent": str(line.suggested_discount_percent),
                "cost": str(line.cost) if line.cost is not None else None,
                "margin_percent": (
                    str(line.margin_percent) if line.margin_percent is not None else None
                ),
                "authorization_reasons": list(line.authorization_reasons),
            }
            for line in quotation.lines
        ],
    }


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    change: Change,
) -> None:
    quotation = change.quotation
    after = {**_state(quotation), **change.details}
    await audit.record(
        action=action,
        user_id=actor,
        company_id=quotation.company_id,
        branch_id=quotation.branch_id,
        resource_type="sales_quotation",
        resource_id=str(quotation.id),
        before_state=_state(change.before) if change.before else None,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


def _draft(body: QuotationDraftIn) -> Draft:
    return Draft(
        branch_id=body.branch_id,
        customer_id=body.customer_id,
        document_type=body.document_type,
        valid_until=body.valid_until,
        global_discount_percent=body.global_discount_percent,
        notes=body.notes,
        lines=tuple(
            DraftLine(
                product_id=line.product_id,
                variant_id=line.variant_id,
                unit_id=line.unit_id,
                quantity=line.quantity,
                discount_percent=line.discount_percent,
                manual_price=line.manual_price,
            )
            for line in body.lines
        ),
    )


async def _actor(
    checker: CheckPermissionUseCase, current: CurrentUser, company: uuid.UUID
) -> Actor:
    return Actor(
        user_id=current.id,
        can_override_price=await _allowed(checker, current.id, company, "sales_prices:override"),
    )


async def _scoped(
    use_cases: SalesQuotationUseCases,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    quotation_id: uuid.UUID,
) -> Quotation:
    quotation = await use_cases.get(company_id, quotation_id)
    await resolve_branch_scope(session, current, company_id, quotation.branch_id)
    return quotation


async def _respond(
    use_cases: SalesQuotationUseCases,
    checker: CheckPermissionUseCase,
    current: CurrentUser,
    quotation: Quotation,
) -> QuotationOut:
    visible = await _costs_visible(checker, current.id, quotation.company_id)
    return _out(await use_cases.view(quotation), visible)


# --- configuración ---------------------------------------------------------------------------


@router.get(
    "/settings/quotations",
    response_model=QuotationSettingsOut,
    summary="Días de vigencia por defecto de las cotizaciones",
    dependencies=[Depends(require_any_permission("sales_quotations:read", "fiscal_settings:read"))],
)
async def quotation_settings(company_id: CompanyId, use_cases: UseCases) -> QuotationSettingsOut:
    return QuotationSettingsOut(quotation_validity_days=await use_cases.validity_days(company_id))


@router.put(
    "/settings/quotations",
    response_model=QuotationSettingsOut,
    summary="Cambiar los días de vigencia por defecto",
    dependencies=[Depends(require_permission("fiscal_settings:manage"))],
)
async def save_quotation_settings(
    body: QuotationSettingsIn,
    request: Request,
    company_id: CompanyId,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> QuotationSettingsOut:
    before, after = await use_cases.save_validity_days(
        company_id, body.quotation_validity_days, current.id
    )
    await audit.record(
        action="SALES_SETTINGS_UPDATED",
        user_id=current.id,
        company_id=company_id,
        resource_type="sales_settings",
        resource_id=str(company_id),
        before_state={"quotation_validity_days": before},
        after_state={"quotation_validity_days": after},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return QuotationSettingsOut(quotation_validity_days=after)


# --- consulta y borrador -----------------------------------------------------------------------


@router.get(
    "/quotations",
    response_model=QuotationPage,
    summary="Cotizaciones de la empresa en las sucursales del usuario",
    dependencies=_READ,
)
async def list_quotations(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    branch_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    status: str | None = Query(default=None, pattern=_STATUS_PATTERN),
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> QuotationPage:
    branch_ids: tuple[uuid.UUID, ...] | None = None
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    else:
        context = await get_branch_context(session, current, company_id)
        if not context.access_all_branches:
            branch_ids = tuple(item.id for item in context.branches)
    filters = QuotationFilters(
        branch_ids=branch_ids,
        branch_id=branch_id,
        customer_id=customer_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        today=today_in_el_salvador(),
    )
    rows, total = await use_cases.page(company_id, filters, page, size)
    visible = await _costs_visible(checker, current.id, company_id)
    return QuotationPage(
        items=[_out(await use_cases.view(row), visible) for row in rows],
        meta=QuotationPageMeta(page=page, size=size, total=total, pages=(total + size - 1) // size),
    )


@router.post(
    "/quotations/preview",
    response_model=QuotationOut,
    summary="Calcular una cotización sin guardarla",
    dependencies=_MANAGE,
)
async def preview_quotation(
    body: QuotationDraftIn,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
) -> QuotationOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    actor = await _actor(checker, current, company_id)
    quotation = await use_cases.preview(company_id, actor, _draft(body))
    return await _respond(use_cases, checker, current, quotation)


@router.post(
    "/quotations",
    response_model=QuotationOut,
    status_code=201,
    summary="Crear un borrador de cotización",
    dependencies=_MANAGE,
)
async def create_quotation(
    body: QuotationDraftIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> QuotationOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    actor = await _actor(checker, current, company_id)
    change = await use_cases.create(company_id, actor, _draft(body), idempotency_key)
    if not change.replayed:
        await _record(
            audit, request, action="SALES_QUOTATION_CREATED", actor=current.id, change=change
        )
    return await _respond(use_cases, checker, current, change.quotation)


@router.get(
    "/quotations/{quotation_id}",
    response_model=QuotationOut,
    summary="Detalle de una cotización",
    dependencies=_READ,
)
async def get_quotation(
    quotation_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
) -> QuotationOut:
    quotation = await _scoped(use_cases, session, current, company_id, quotation_id)
    return await _respond(use_cases, checker, current, quotation)


@router.get(
    "/quotations/{quotation_id}/pdf",
    summary="Versión imprimible de la cotización (sin costos ni márgenes)",
    dependencies=_READ,
    response_class=Response,
)
async def quotation_pdf(
    quotation_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
) -> Response:
    quotation = await _scoped(use_cases, session, current, company_id, quotation_id)
    view = await use_cases.view(quotation)
    content = render_quotation_pdf(view, await use_cases.document_header(view))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{quotation.code}.pdf"'},
    )


@router.put(
    "/quotations/{quotation_id}",
    response_model=QuotationOut,
    summary="Editar un borrador; se recalculan precios, descuentos e impuestos",
    dependencies=_MANAGE,
)
async def update_quotation(
    quotation_id: uuid.UUID,
    body: QuotationUpdateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    actor = await _actor(checker, current, company_id)
    change = await use_cases.update(
        company_id, actor, quotation_id, body.expected_version, _draft(body)
    )
    await _record(audit, request, action="SALES_QUOTATION_UPDATED", actor=current.id, change=change)
    return await _respond(use_cases, checker, current, change.quotation)


# --- acciones ----------------------------------------------------------------------------------


@router.post(
    "/quotations/{quotation_id}/issue",
    response_model=QuotationOut,
    summary="Emitir: queda Emitida o, si pasa el tope del usuario, Por autorizar",
    dependencies=_CONFIRM,
)
async def issue_quotation(
    quotation_id: uuid.UUID,
    body: QuotationActionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    change = await use_cases.issue(company_id, current.id, quotation_id, body.expected_version)
    action = (
        "SALES_QUOTATION_SUBMITTED_FOR_AUTHORIZATION"
        if change.quotation.status.value == "pending_authorization"
        else "SALES_QUOTATION_ISSUED"
    )
    await _record(audit, request, action=action, actor=current.id, change=change)
    return await _respond(use_cases, checker, current, change.quotation)


@router.post(
    "/quotations/{quotation_id}/authorize",
    response_model=QuotationOut,
    summary="Autorizar descuentos fuera de tope o precios bajo costo; queda Emitida",
    dependencies=_AUTHORIZE,
)
async def authorize_quotation(
    quotation_id: uuid.UUID,
    body: QuotationNoteIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    change = await use_cases.authorize(
        company_id, current.id, quotation_id, body.expected_version, body.note
    )
    await _record(
        audit, request, action="SALES_QUOTATION_AUTHORIZED", actor=current.id, change=change
    )
    return await _respond(use_cases, checker, current, change.quotation)


@router.post(
    "/quotations/{quotation_id}/return",
    response_model=QuotationOut,
    summary="Devolver a borrador una cotización por autorizar, con lo que debe corregirse",
    dependencies=_AUTHORIZE,
)
async def return_quotation(
    quotation_id: uuid.UUID,
    body: QuotationReasonIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    change = await use_cases.return_to_draft(
        company_id, current.id, quotation_id, body.expected_version, body.reason
    )
    await _record(
        audit, request, action="SALES_QUOTATION_RETURNED", actor=current.id, change=change
    )
    return await _respond(use_cases, checker, current, change.quotation)


@router.post(
    "/quotations/{quotation_id}/accept",
    response_model=QuotationOut,
    summary="Registrar que el cliente aceptó la cotización",
    dependencies=_CONFIRM,
)
async def accept_quotation(
    quotation_id: uuid.UUID,
    body: QuotationActionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    change = await use_cases.accept(company_id, current.id, quotation_id, body.expected_version)
    await _record(
        audit, request, action="SALES_QUOTATION_ACCEPTED", actor=current.id, change=change
    )
    return await _respond(use_cases, checker, current, change.quotation)


@router.post(
    "/quotations/{quotation_id}/reject",
    response_model=QuotationOut,
    summary="Registrar que el cliente rechazó la cotización y por qué",
    dependencies=_CONFIRM,
)
async def reject_quotation(
    quotation_id: uuid.UUID,
    body: QuotationReasonIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    change = await use_cases.reject(
        company_id, current.id, quotation_id, body.expected_version, body.reason
    )
    await _record(
        audit, request, action="SALES_QUOTATION_REJECTED", actor=current.id, change=change
    )
    return await _respond(use_cases, checker, current, change.quotation)


@router.post(
    "/quotations/{quotation_id}/cancel",
    response_model=QuotationOut,
    summary="Cancelar la cotización",
    dependencies=_CONFIRM,
)
async def cancel_quotation(
    quotation_id: uuid.UUID,
    body: QuotationReasonIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> QuotationOut:
    await _scoped(use_cases, session, current, company_id, quotation_id)
    change = await use_cases.cancel(
        company_id, current.id, quotation_id, body.expected_version, body.reason
    )
    await _record(
        audit, request, action="SALES_QUOTATION_CANCELLED", actor=current.id, change=change
    )
    return await _respond(use_cases, checker, current, change.quotation)

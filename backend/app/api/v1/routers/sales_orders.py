"""Pedido de venta (bloque V2e).

Usa las rutas ``/sales`` de la venta B06, que se rehízo en su lugar. Los identificadores van
con convertidor UUID para no capturar ``/sales/returns`` ni ``/sales/deliveries``.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.v1.company_access import get_branch_context, request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_sales_delivery_service,
    get_sales_order_use_cases,
    get_sales_quotation_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.routers.sales_quotations import (
    allowed,
    costs_visible_for,
    document_line_fields,
    reasons_out,
)
from app.api.v1.schemas.sales_order import (
    AutoDeliveryOut,
    DeliveryIn,
    OrderActionIn,
    OrderDraftIn,
    OrderFromQuotationIn,
    OrderLineOut,
    OrderNoteIn,
    OrderOut,
    OrderPage,
    OrderReasonIn,
    OrderSettings,
    OrderUpdateIn,
)
from app.api.v1.schemas.sales_quotation import QuotationPageMeta
from app.application.audit.audit_service import AuditService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales.deliveries import SalesDeliveryService
from app.application.sales_documents.pricing import Actor, DraftLine
from app.application.sales_orders import Change, Delivery, OrderDraft, OrderView, SalesOrderUseCases
from app.application.sales_quotations import SalesQuotationUseCases
from app.domain.entities.sales_order import DeliveryMode, OrderStatus
from app.domain.ports.sales_order_repository import Order, OrderFilters

router = APIRouter(prefix="/sales", tags=["sales-orders"])

UseCases = Annotated[SalesOrderUseCases, Depends(get_sales_order_use_cases)]
Quotations = Annotated[SalesQuotationUseCases, Depends(get_sales_quotation_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Deliveries = Annotated[SalesDeliveryService, Depends(get_sales_delivery_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_permission("sales:read"))]
_MANAGE = [Depends(require_permission("sales:manage"))]
_CONFIRM = [Depends(require_permission("sales:confirm"))]
_CANCEL = [Depends(require_permission("sales:cancel"))]
# Descuentos fuera de tope o crédito (V5b): cada motivo pide su permiso dentro del caso de uso.
_AUTHORIZE = [
    Depends(require_any_permission("sales_discounts:authorize", "sales_credit:authorize"))
]
_STATUS_PATTERN = "^(draft|pending_authorization|confirmed|cancelled)$"
ZERO = Decimal("0")
QUANTITY = Decimal("0.000001")


def _progress(order: Order) -> str:
    delivered = sum((item.delivered_base for item in order.lines), ZERO)
    if delivered <= 0:
        return "pending"
    if all(item.delivered_base >= item.line.quantity_base for item in order.lines):
        return "complete"
    return "partial"


def _out(view: OrderView, costs_visible: bool) -> OrderOut:
    order = view.order
    totals = order.totals
    people = view.people
    open_order = order.status in (OrderStatus.DRAFT, OrderStatus.PENDING_AUTHORIZATION)
    lines = []
    for number, item in enumerate(order.lines, start=1):
        item_id = item.line.identity.inventory_item_id
        lines.append(
            OrderLineOut(
                **document_line_fields(item.line, number, costs_visible),
                source_quotation_line_id=item.source_quotation_line_id,
                quantity_delivered_base=item.delivered_base.quantize(QUANTITY),
                quantity_pending_base=max(
                    ZERO, item.line.quantity_base - item.delivered_base
                ).quantize(QUANTITY),
                available_base=(
                    view.availability.free(item_id).quantize(QUANTITY)
                    if open_order and view.availability is not None
                    else None
                ),
            )
        )
    return OrderOut(
        id=order.id,
        company_id=order.company_id,
        branch_id=order.branch_id,
        customer_id=order.customer_id,
        customer_code=view.customer.code,
        customer_name=view.customer.draft.name,
        quotation_id=order.quotation_id,
        quotation_code=view.quotation_code,
        exchange_return_id=order.exchange_return_id,
        exchange_return_code=view.exchange_return_code,
        code=order.code,
        document_type=order.document_type,  # type: ignore[arg-type]
        price_list_id=order.price_list_id,
        price_list_name=view.price_list_name,
        prices_include_vat=order.prices_include_vat,
        global_discount_percent=order.global_discount_percent,
        status=order.status.value,
        delivery_progress=_progress(order),  # type: ignore[arg-type]
        version=order.version,
        notes=order.notes,
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
        requires_authorization=order.requires_authorization,
        authorization_reasons=reasons_out(order.authorization_reasons),
        costs_visible=costs_visible,
        promised_date=order.promised_date,
        delivery_mode=order.delivery_mode.value,
        delivery_address_id=order.delivery_address_id,
        delivery_address_text=order.delivery_address_text,
        payment_terms=order.payment_terms.value,
        credit_days=order.credit_days,
        created_by_id=order.created_by_id,
        created_by_name=people.of(order.created_by_id),
        confirmed_by_name=people.of(order.confirmed_by_id),
        confirmed_at=order.confirmed_at,
        authorized_by_name=people.of(order.authorized_by_id),
        authorized_at=order.authorized_at,
        authorization_note=order.authorization_note,
        cancelled_by_name=people.of(order.cancelled_by_id),
        cancelled_at=order.cancelled_at,
        cancellation_reason=order.cancellation_reason,
        lines=lines,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _state(order: Order) -> dict[str, Any]:
    """Lo que queda en la bitácora: estado, entrega, totales y, por línea, precios y descuentos."""

    return {
        "code": order.code,
        "status": order.status.value,
        "version": order.version,
        "customer_id": str(order.customer_id),
        "branch_id": str(order.branch_id),
        "quotation_id": str(order.quotation_id) if order.quotation_id else None,
        "exchange_return_id": str(order.exchange_return_id) if order.exchange_return_id else None,
        "document_type": order.document_type,
        "promised_date": order.promised_date.isoformat(),
        "delivery_mode": order.delivery_mode.value,
        "delivery_address_text": order.delivery_address_text,
        "payment_terms": order.payment_terms.value,
        "credit_days": order.credit_days,
        "global_discount_percent": str(order.global_discount_percent),
        "total": str(order.totals.total),
        "requires_authorization": order.requires_authorization,
        "authorization_reasons": list(order.authorization_reasons),
        "authorization_note": order.authorization_note,
        "cancellation_reason": order.cancellation_reason,
        "lines": [
            {
                "product_sku": item.line.identity.product_sku,
                "inventory_item_id": str(item.line.identity.inventory_item_id),
                "quantity": str(item.line.quantity),
                "quantity_base": str(item.line.quantity_base),
                "list_price": str(item.line.list_price)
                if item.line.list_price is not None
                else None,
                "unit_price": str(item.line.unit_price),
                "price_overridden": item.line.price_overridden,
                "discount_percent": str(item.line.discount_percent),
                "cost": str(item.line.cost) if item.line.cost is not None else None,
                "authorization_reasons": list(item.line.authorization_reasons),
            }
            for item in order.lines
        ],
    }


async def _record(
    audit: AuditService, request: Request, *, action: str, actor: uuid.UUID, change: Change
) -> None:
    order = change.order
    await audit.record(
        action=action,
        user_id=actor,
        company_id=order.company_id,
        branch_id=order.branch_id,
        resource_type="sale",
        resource_id=str(order.id),
        before_state=_state(change.before) if change.before else None,
        after_state={**_state(order), **change.details},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


def _delivery(body: DeliveryIn) -> Delivery:
    return Delivery(
        promised_date=body.promised_date,
        mode=DeliveryMode(body.delivery_mode),
        address_id=body.delivery_address_id,
    )


def _draft(body: OrderDraftIn) -> OrderDraft:
    return OrderDraft(
        branch_id=body.branch_id,
        customer_id=body.customer_id,
        document_type=body.document_type,
        global_discount_percent=body.global_discount_percent,
        notes=body.notes,
        exchange_return_id=body.exchange_return_id,
        delivery=_delivery(body),
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
        can_override_price=await allowed(checker, current.id, company, "sales_prices:override"),
    )


async def _scoped(
    use_cases: SalesOrderUseCases,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    order_id: uuid.UUID,
) -> Order:
    order = await use_cases.get(company_id, order_id)
    await resolve_branch_scope(session, current, company_id, order.branch_id)
    return order


async def _respond(
    use_cases: SalesOrderUseCases,
    checker: CheckPermissionUseCase,
    current: CurrentUser,
    order: Order,
    auto_delivery: AutoDeliveryOut | None = None,
) -> OrderOut:
    visible = await costs_visible_for(checker, current.id, order.company_id)
    open_order = order.status in (OrderStatus.DRAFT, OrderStatus.PENDING_AUTHORIZATION)
    out = _out(await use_cases.view(order, with_availability=open_order), visible)
    out.auto_delivery = auto_delivery
    return out


async def _deliver_confirmed(
    deliveries: SalesDeliveryService,
    use_cases: SalesOrderUseCases,
    request: Request,
    current: CurrentUser,
    order: Order,
) -> tuple[Order, AutoDeliveryOut | None]:
    """Al quedar confirmado, descuenta las existencias y deja la salida en el kardex."""

    if order.status is not OrderStatus.CONFIRMED:
        return order, None
    if not await deliveries.auto_deliver_enabled(order.company_id):
        return order, None
    result = await deliveries.auto_deliver(
        company_id=order.company_id, actor_id=current.id, sale_id=order.id, request=request
    )
    # La entrega cambia el avance del pedido: se vuelve a leer.
    return await use_cases.get(order.company_id, order.id), AutoDeliveryOut(**result)


# --- configuración ---------------------------------------------------------------------------


@router.get(
    "/settings/orders",
    response_model=OrderSettings,
    summary="Si confirmar un pedido descuenta las existencias",
    dependencies=[Depends(require_any_permission("sales:read", "fiscal_settings:read"))],
)
async def order_settings(company_id: CompanyId, deliveries: Deliveries) -> OrderSettings:
    return OrderSettings(auto_deliver_on_confirm=await deliveries.auto_deliver_enabled(company_id))


@router.put(
    "/settings/orders",
    response_model=OrderSettings,
    summary="Cambiar si confirmar un pedido descuenta las existencias",
    dependencies=[Depends(require_permission("fiscal_settings:manage"))],
)
async def save_order_settings(
    body: OrderSettings,
    request: Request,
    company_id: CompanyId,
    current: CurrentUser,
    deliveries: Deliveries,
    audit: Audit,
) -> OrderSettings:
    before, after = await deliveries.set_auto_deliver(
        company_id, body.auto_deliver_on_confirm, current.id
    )
    await audit.record(
        action="SALES_SETTINGS_UPDATED",
        user_id=current.id,
        company_id=company_id,
        resource_type="sales_settings",
        resource_id=str(company_id),
        before_state={"auto_deliver_on_confirm": before},
        after_state={"auto_deliver_on_confirm": after},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return OrderSettings(auto_deliver_on_confirm=after)


# --- consulta y borrador -----------------------------------------------------------------------


@router.get("", response_model=OrderPage, summary="Pedidos de la empresa", dependencies=_READ)
async def list_orders(
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
) -> OrderPage:
    branch_ids: tuple[uuid.UUID, ...] | None = None
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    else:
        context = await get_branch_context(session, current, company_id)
        if not context.access_all_branches:
            branch_ids = tuple(item.id for item in context.branches)
    filters = OrderFilters(
        branch_ids=branch_ids,
        branch_id=branch_id,
        customer_id=customer_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    rows, total = await use_cases.page(company_id, filters, page, size)
    visible = await costs_visible_for(checker, current.id, company_id)
    return OrderPage(
        items=[_out(await use_cases.view(row), visible) for row in rows],
        meta=QuotationPageMeta(page=page, size=size, total=total, pages=(total + size - 1) // size),
    )


@router.post(
    "/preview",
    response_model=OrderOut,
    summary="Calcular un pedido sin guardarlo, con el disponible por línea",
    dependencies=_MANAGE,
)
async def preview_order(
    body: OrderDraftIn,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
) -> OrderOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    order = await use_cases.preview(
        company_id, await _actor(checker, current, company_id), _draft(body)
    )
    return await _respond(use_cases, checker, current, order)


@router.post(
    "", response_model=OrderOut, status_code=201, summary="Crear un pedido", dependencies=_MANAGE
)
async def create_order(
    body: OrderDraftIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> OrderOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    actor = await _actor(checker, current, company_id)
    change = await use_cases.create(company_id, actor, _draft(body), idempotency_key)
    if not change.replayed:
        await _record(audit, request, action="SALES_ORDER_CREATED", actor=current.id, change=change)
    return await _respond(use_cases, checker, current, change.order)


@router.post(
    "/quotations/{quotation_id:uuid}/order",
    response_model=OrderOut,
    status_code=201,
    summary="Crear el pedido de una cotización aceptada, con sus condiciones",
    dependencies=[Depends(require_permission("sales_quotations:convert"))],
)
async def order_from_quotation(
    quotation_id: uuid.UUID,
    body: OrderFromQuotationIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
    quotations: Quotations,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> OrderOut:
    quotation = await quotations.get(company_id, quotation_id)
    await resolve_branch_scope(session, current, company_id, quotation.branch_id)
    actor = await _actor(checker, current, company_id)
    change = await use_cases.create_from_quotation(
        company_id, actor, quotation_id, _delivery(body), idempotency_key, body.notes
    )
    if not change.replayed:
        await _record(
            audit,
            request,
            action="SALES_ORDER_CREATED_FROM_QUOTATION",
            actor=current.id,
            change=change,
        )
    return await _respond(use_cases, checker, current, change.order)


@router.get(
    "/{order_id:uuid}", response_model=OrderOut, summary="Detalle de un pedido", dependencies=_READ
)
async def get_order(
    order_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
) -> OrderOut:
    order = await _scoped(use_cases, session, current, company_id, order_id)
    return await _respond(use_cases, checker, current, order)


@router.put(
    "/{order_id:uuid}",
    response_model=OrderOut,
    summary="Editar un borrador; se recalculan precios, descuentos e impuestos",
    dependencies=_MANAGE,
)
async def update_order(
    order_id: uuid.UUID,
    body: OrderUpdateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> OrderOut:
    await _scoped(use_cases, session, current, company_id, order_id)
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    actor = await _actor(checker, current, company_id)
    change = await use_cases.update(
        company_id, actor, order_id, body.expected_version, _draft(body)
    )
    await _record(audit, request, action="SALES_ORDER_UPDATED", actor=current.id, change=change)
    return await _respond(use_cases, checker, current, change.order)


# --- acciones ----------------------------------------------------------------------------------


@router.post(
    "/{order_id:uuid}/confirm",
    response_model=OrderOut,
    summary="Confirmar y apartar existencias; si pasa el tope, queda Por autorizar",
    dependencies=_CONFIRM,
)
async def confirm_order(
    order_id: uuid.UUID,
    body: OrderActionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
    deliveries: Deliveries,
) -> OrderOut:
    await _scoped(use_cases, session, current, company_id, order_id)
    change = await use_cases.confirm(company_id, current.id, order_id, body.expected_version)
    action = (
        "SALES_ORDER_CONFIRMED"
        if change.order.status is OrderStatus.CONFIRMED
        else "SALES_ORDER_SUBMITTED_FOR_AUTHORIZATION"
    )
    await _record(audit, request, action=action, actor=current.id, change=change)
    order, auto = await _deliver_confirmed(deliveries, use_cases, request, current, change.order)
    return await _respond(use_cases, checker, current, order, auto)


@router.post(
    "/{order_id:uuid}/authorize",
    response_model=OrderOut,
    summary="Autorizar y confirmar un pedido por autorizar",
    dependencies=_AUTHORIZE,
)
async def authorize_order(
    order_id: uuid.UUID,
    body: OrderNoteIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
    deliveries: Deliveries,
) -> OrderOut:
    await _scoped(use_cases, session, current, company_id, order_id)
    change = await use_cases.authorize(
        company_id,
        current.id,
        order_id,
        body.expected_version,
        body.note,
        can_authorize_discounts=(
            await checker.execute(current.id, company_id, "sales_discounts:authorize")
        ).allowed,
        can_authorize_credit=(
            await checker.execute(current.id, company_id, "sales_credit:authorize")
        ).allowed,
    )
    await _record(audit, request, action="SALES_ORDER_AUTHORIZED", actor=current.id, change=change)
    order, auto = await _deliver_confirmed(deliveries, use_cases, request, current, change.order)
    return await _respond(use_cases, checker, current, order, auto)


@router.post(
    "/{order_id:uuid}/authorize-credit",
    response_model=OrderOut,
    summary="Autorizar el crédito de un pedido confirmado para poder facturarlo",
    dependencies=[Depends(require_permission("sales_credit:authorize"))],
)
async def authorize_order_credit(
    order_id: uuid.UUID,
    body: OrderNoteIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> OrderOut:
    await _scoped(use_cases, session, current, company_id, order_id)
    change = await use_cases.authorize_credit(
        company_id, current.id, order_id, body.expected_version, body.note
    )
    await _record(
        audit, request, action="SALES_ORDER_CREDIT_AUTHORIZED", actor=current.id, change=change
    )
    return await _respond(use_cases, checker, current, change.order)


@router.post(
    "/{order_id:uuid}/return",
    response_model=OrderOut,
    summary="Devolver a borrador un pedido por autorizar",
    dependencies=_AUTHORIZE,
)
async def return_order(
    order_id: uuid.UUID,
    body: OrderReasonIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> OrderOut:
    await _scoped(use_cases, session, current, company_id, order_id)
    change = await use_cases.return_to_draft(
        company_id, current.id, order_id, body.expected_version, body.reason
    )
    await _record(audit, request, action="SALES_ORDER_RETURNED", actor=current.id, change=change)
    return await _respond(use_cases, checker, current, change.order)


@router.post(
    "/{order_id:uuid}/cancel",
    response_model=OrderOut,
    summary="Cancelar el pedido y liberar lo apartado",
    dependencies=_CANCEL,
)
async def cancel_order(
    order_id: uuid.UUID,
    body: OrderReasonIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    use_cases: UseCases,
    checker: Checker,
    audit: Audit,
) -> OrderOut:
    await _scoped(use_cases, session, current, company_id, order_id)
    change = await use_cases.cancel(
        company_id, current.id, order_id, body.expected_version, body.reason
    )
    await _record(audit, request, action="SALES_ORDER_CANCELLED", actor=current.id, change=change)
    return await _respond(use_cases, checker, current, change.order)

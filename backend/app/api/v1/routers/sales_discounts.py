"""Topes de descuento por rol, escalas por volumen y evaluación de líneas (bloque V2c)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_check_permission_use_case,
    get_sales_discount_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.sales_discount import (
    DiscountPolicyIn,
    DiscountPolicyOut,
    EvaluationIn,
    EvaluationLineOut,
    EvaluationOut,
    RolePolicyOut,
    VolumeDiscountIn,
    VolumeDiscountOut,
)
from app.application.audit.audit_service import AuditService
from app.application.price_lists import today_in_el_salvador
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales_discounts import EvaluatedLine, LineRequest, SalesDiscountUseCases
from app.domain.entities.price_list import PriceKey
from app.domain.entities.sales_margin import NONE_ALLOWED, REASON_TEXT, DiscountPolicy
from app.domain.ports.sales_discount_repository import RolePolicy, VolumeDiscount

router = APIRouter(tags=["sales-discounts"])

UseCases = Annotated[SalesDiscountUseCases, Depends(get_sales_discount_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
_MANAGE_POLICIES = [Depends(require_permission("sales_discounts:manage"))]
_READ_LISTS = [Depends(require_permission("price_lists:read"))]
_MANAGE_LISTS = [Depends(require_permission("price_lists:manage"))]
_SELLING = [
    Depends(require_any_permission("sales_quotations:read", "sales:read", "price_lists:read"))
]


def _policy_out(policy: DiscountPolicy) -> DiscountPolicyOut:
    return DiscountPolicyOut(
        max_line_discount_percent=policy.max_line_percent,
        max_global_discount_percent=policy.max_global_percent,
        can_sell_below_cost=policy.can_sell_below_cost,
    )


def _role_out(role: RolePolicy) -> RolePolicyOut:
    policy = role.policy or NONE_ALLOWED
    return RolePolicyOut(
        role_id=role.role_id,
        role_name=role.role_name,
        configured=role.policy is not None,
        updated_at=role.updated_at,
        **_policy_out(policy).model_dump(),
    )


def _scale_out(scale: VolumeDiscount) -> VolumeDiscountOut:
    today = today_in_el_salvador()
    if scale.valid_from > today:
        state = "scheduled"
    elif scale.valid_to is not None and scale.valid_to < today:
        state = "expired"
    else:
        state = "current"
    return VolumeDiscountOut(
        id=scale.id,
        price_list_id=scale.price_list_id,
        product_id=scale.product_id,
        variant_id=scale.variant_id,
        unit_id=scale.unit_id,
        min_quantity=scale.min_quantity,
        discount_percent=scale.discount_percent,
        valid_from=scale.valid_from,
        valid_to=scale.valid_to,
        status=state,
    )


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=request_company_id(request),
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_state=before,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


@router.get(
    "/sales/discount-policies",
    response_model=list[RolePolicyOut],
    summary="Topes de descuento de cada rol de la empresa",
    dependencies=_MANAGE_POLICIES,
)
async def role_policies(request: Request, use_cases: UseCases) -> list[RolePolicyOut]:
    roles = await use_cases.role_policies(request_company_id(request))
    return [_role_out(r) for r in roles]


@router.put(
    "/sales/discount-policies/{role_id}",
    response_model=RolePolicyOut,
    summary="Fijar los topes de descuento de un rol",
    dependencies=_MANAGE_POLICIES,
)
async def save_policy(
    role_id: uuid.UUID,
    body: DiscountPolicyIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> RolePolicyOut:
    before, after = await use_cases.save_policy(
        request_company_id(request),
        role_id,
        DiscountPolicy(
            max_line_percent=body.max_line_discount_percent,
            max_global_percent=body.max_global_discount_percent,
            can_sell_below_cost=body.can_sell_below_cost,
        ),
        current.id,
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        resource_type="sales_discount_policy",
        resource_id=role_id,
        before=_role_out(before).model_dump(mode="json"),
        after=_role_out(after).model_dump(mode="json"),
    )
    return _role_out(after)


@router.get(
    "/sales/my-discount-policy",
    response_model=DiscountPolicyOut,
    summary="Topes de descuento del usuario actual",
    dependencies=_SELLING,
)
async def my_policy(
    request: Request, current: CurrentUser, use_cases: UseCases
) -> DiscountPolicyOut:
    return _policy_out(await use_cases.user_policy(request_company_id(request), current.id))


@router.get(
    "/price-lists/{list_id}/volume-discounts",
    response_model=list[VolumeDiscountOut],
    summary="Escalas de descuento por volumen de una lista",
    dependencies=_READ_LISTS,
)
async def volume_discounts(
    list_id: uuid.UUID, request: Request, use_cases: UseCases
) -> list[VolumeDiscountOut]:
    scales = await use_cases.volume_discounts(request_company_id(request), list_id)
    return [_scale_out(s) for s in scales]


@router.post(
    "/price-lists/{list_id}/volume-discounts",
    response_model=VolumeDiscountOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una escala de descuento por volumen",
    dependencies=_MANAGE_LISTS,
)
async def add_volume_discount(
    list_id: uuid.UUID,
    body: VolumeDiscountIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> VolumeDiscountOut:
    scale = await use_cases.add_volume_discount(
        request_company_id(request),
        list_id,
        PriceKey(body.product_id, body.variant_id, body.unit_id, None),
        body.min_quantity,
        body.discount_percent,
        body.valid_from,
        current.id,
    )
    out = _scale_out(scale)
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        resource_type="sales_volume_discount",
        resource_id=scale.id,
        after=out.model_dump(mode="json"),
    )
    return out


@router.delete(
    "/price-lists/volume-discounts/{scale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Anular una escala programada o terminar hoy una vigente",
    dependencies=_MANAGE_LISTS,
)
async def remove_volume_discount(
    scale_id: uuid.UUID, request: Request, current: CurrentUser, use_cases: UseCases, audit: Audit
) -> None:
    scale = await use_cases.remove_volume_discount(request_company_id(request), scale_id)
    await _record(
        audit,
        request,
        action="DELETE",
        actor=current.id,
        resource_type="sales_volume_discount",
        resource_id=scale_id,
        before=_scale_out(scale).model_dump(mode="json"),
    )


def _line_out(line: EvaluatedLine, with_costs: bool) -> EvaluationLineOut:
    request, evaluation, price_list = line.request, line.evaluation, line.price_list
    reasons = list(evaluation.reasons) if evaluation else []
    return EvaluationLineOut(
        product_id=request.product_id,
        variant_id=request.variant_id,
        unit_id=request.unit_id,
        quantity=request.quantity,
        found=line.found,
        message=line.message,
        price_list_id=price_list.id if price_list else None,
        price_list_name=price_list.name if price_list else None,
        prices_include_vat=price_list.prices_include_vat if price_list else None,
        list_price=evaluation.list_price if evaluation else None,
        suggested_discount_percent=line.suggested.percent if line.suggested else None,
        suggested_discount_source=line.suggested.source.value if line.suggested else None,
        discount_percent=evaluation.discount_percent if evaluation else None,
        net_price=evaluation.net_price if evaluation else None,
        cost=evaluation.cost if evaluation and with_costs else None,
        margin_percent=evaluation.margin_percent if evaluation and with_costs else None,
        requires_authorization=bool(reasons),
        reasons=[r.value for r in reasons],
        reason_messages=[REASON_TEXT[r] for r in reasons],
    )


@router.post(
    "/sales/discount-evaluation",
    response_model=EvaluationOut,
    summary="Evaluar precios y descuentos propuestos contra los topes del usuario",
    dependencies=_SELLING,
)
async def evaluate(
    body: EvaluationIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    checker: Checker,
) -> EvaluationOut:
    company_id = request_company_id(request)
    with_costs = (await checker.execute(current.id, company_id, "sales_costs:read")).allowed
    result = await use_cases.evaluate(
        company_id,
        current.id,
        customer_id=body.customer_id,
        branch_id=body.branch_id,
        on=body.on,
        lines=[
            LineRequest(
                product_id=line.product_id,
                variant_id=line.variant_id,
                unit_id=line.unit_id,
                quantity=line.quantity,
                discount_percent=line.discount_percent,
            )
            for line in body.lines
        ],
        global_discount_percent=body.global_discount_percent,
    )
    return EvaluationOut(
        policy=_policy_out(result.policy),
        lines=[_line_out(line, with_costs) for line in result.lines],
        global_discount_percent=result.global_discount_percent,
        global_reasons=[r.value for r in result.global_reasons],
        requires_authorization=result.requires_authorization,
    )

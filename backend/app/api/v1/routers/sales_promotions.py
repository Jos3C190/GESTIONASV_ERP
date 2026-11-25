"""Promociones por sucursal (pedido del ingeniero, 24/11/2026).

Consultar pide ``sales:read`` o ``sales_promotions:manage``; crear y terminar piden
``sales_promotions:manage``. Cada cambio queda en la bitácora de auditoría.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.company_access import (
    get_branch_context,
    request_company_id,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_sales_discount_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.sales_promotion import PromotionIn, PromotionOut
from app.application.audit.audit_service import AuditService
from app.application.price_lists import today_in_el_salvador
from app.application.sales_discounts import SalesDiscountUseCases
from app.domain.entities.sales_margin import BranchPromotion

router = APIRouter(prefix="/sales/promotions", tags=["sales-promotions"])

UseCases = Annotated[SalesDiscountUseCases, Depends(get_sales_discount_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_READ = [Depends(require_any_permission("sales:read", "sales_promotions:manage"))]
_MANAGE = [Depends(require_permission("sales_promotions:manage"))]

State = Literal["current", "scheduled", "expired", "ended"]


def _state(promotion: BranchPromotion) -> State:
    today = today_in_el_salvador()
    if promotion.ended:
        return "ended"
    if promotion.valid_from > today:
        return "scheduled"
    if promotion.valid_to is not None and promotion.valid_to < today:
        return "expired"
    return "current"


def promotion_out(promotion: BranchPromotion) -> PromotionOut:
    return PromotionOut(
        id=promotion.id,
        branch_id=promotion.branch_id,
        branch_name=promotion.branch_name,
        product_id=promotion.product_id,
        product_name=promotion.product_name,
        product_sku=promotion.product_sku,
        discount_percent=promotion.discount_percent,
        valid_from=promotion.valid_from,
        valid_to=promotion.valid_to,
        notes=promotion.notes,
        status=_state(promotion),
    )


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    promotion: BranchPromotion,
    before: dict[str, Any] | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=promotion.company_id,
        branch_id=promotion.branch_id,
        resource_type="sales_branch_promotion",
        resource_id=str(promotion.id),
        before_state=before,
        after_state=promotion_out(promotion).model_dump(mode="json"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


@router.get(
    "",
    response_model=list[PromotionOut],
    summary="Promociones por sucursal de la empresa",
    dependencies=_READ,
)
async def list_promotions(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    branch_id: uuid.UUID | None = None,
    include_ended: bool = False,
) -> list[PromotionOut]:
    branch_ids: tuple[uuid.UUID, ...] | None = None
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
        branch_ids = (branch_id,)
    else:
        context = await get_branch_context(session, current, company_id)
        if not context.access_all_branches:
            branch_ids = tuple(item.id for item in context.branches)
    found = await cases.promotions(company_id, branch_ids=branch_ids, include_ended=include_ended)
    return [promotion_out(item) for item in found]


@router.post(
    "",
    response_model=PromotionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una promoción de un producto en una sucursal",
    dependencies=_MANAGE,
)
async def create_promotion(
    body: PromotionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> PromotionOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    created = await cases.add_promotion(
        company_id,
        current.id,
        branch_id=body.branch_id,
        product_id=body.product_id,
        discount_percent=body.discount_percent,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        notes=body.notes,
    )
    await _record(audit, request, action="CREATE", actor=current.id, promotion=created)
    return promotion_out(created)


@router.post(
    "/{promotion_id}/end",
    response_model=PromotionOut,
    summary="Terminar una promoción: deja de aplicarse desde ahora",
    dependencies=_MANAGE,
)
async def end_promotion(
    promotion_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
) -> PromotionOut:
    found = await cases.promotion(company_id, promotion_id)
    await resolve_branch_scope(session, current, company_id, found.branch_id)
    before, after = await cases.end_promotion(company_id, current.id, promotion_id)
    await _record(
        audit,
        request,
        action="END_PROMOTION",
        actor=current.id,
        promotion=after,
        before=promotion_out(before).model_dump(mode="json"),
    )
    return promotion_out(after)

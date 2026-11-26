"""Análisis comercial y metas de venta por sucursal (V9a).

Las cifras de venta piden ``sales_analytics:read``; el costo y el margen, además, ``sales_costs:read``.
Definir metas pide ``sales_goals:manage``. Cada usuario ve solo las sucursales de su alcance.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_sales_analytics_use_cases,
    require_permission,
)
from app.api.v1.schemas.sales_analytics import (
    AnalysisOut,
    BranchGoalOut,
    BucketOut,
    GoalsIn,
    GoalsOut,
    TotalsOut,
)
from app.application.audit.audit_service import AuditService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales_analytics import SalesAnalyticsUseCases, parse_period
from app.domain.entities.sales_analytics import Analysis, Bucket
from app.domain.ports.sales_analytics_repository import BranchGoal

router = APIRouter(prefix="/sales", tags=["sales-analytics"])

UseCases = Annotated[SalesAnalyticsUseCases, Depends(get_sales_analytics_use_cases)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]
_TZ = ZoneInfo("America/El_Salvador")


async def _scope(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID, branch_id: uuid.UUID | None
) -> tuple[uuid.UUID, ...] | None:
    """Sin sucursal: todas (si el usuario las ve todas); con sucursal: solo esa."""

    await resolve_branch_scope(session, current, company_id, branch_id)
    return (branch_id,) if branch_id is not None else None


def _bucket_out(item: Bucket, costs: bool) -> BucketOut:
    return BucketOut(
        key=item.key,
        label=item.label,
        net_sales=item.net_sales,
        documents=item.documents,
        quantity=item.quantity,
        cost=item.cost if costs else None,
        margin=item.margin if costs else None,
        margin_percent=item.margin_percent if costs else None,
        goal=item.goal,
        goal_percent=item.goal_percent,
    )


def analysis_out(result: Analysis) -> AnalysisOut:
    costs = result.costs_visible
    totals = result.totals
    return AnalysisOut(
        start=result.start,
        end=result.end,
        costs_visible=costs,
        totals=TotalsOut(
            net_sales=totals.net_sales,
            documents=totals.documents,
            average_ticket=totals.average_ticket,
            returns=totals.returns,
            returns_percent=totals.returns_percent,
            cost=totals.cost if costs else None,
            margin=totals.margin if costs else None,
            margin_percent=totals.margin_percent if costs else None,
        ),
        **{
            name: [_bucket_out(item, costs) for item in getattr(result, name)]
            for name in (
                "by_day",
                "by_hour",
                "by_branch",
                "by_category",
                "top_customers",
                "top_products",
                "bottom_products",
            )
        },
    )


@router.get(
    "/analytics",
    response_model=AnalysisOut,
    summary="Ventas sin IVA, devoluciones, metas y (con permiso) costo y margen del rango",
    dependencies=[Depends(require_permission("sales_analytics:read"))],
)
async def sales_analysis(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    checker: Checker,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    branch_id: uuid.UUID | None = None,
) -> AnalysisOut:
    today = datetime.now(_TZ).date()
    scope = await _scope(session, current, company_id, branch_id)
    costs = (await checker.execute(current.id, company_id, "sales_costs:read")).allowed
    result = await cases.analysis(
        company_id,
        scope,
        start or today.replace(day=1),
        end or today,
        costs_visible=costs,
    )
    return analysis_out(result)


def _goals_out(period: str, goals: list[BranchGoal]) -> GoalsOut:
    return GoalsOut(
        period=period,
        goals=[
            BranchGoalOut(
                branch_id=item.branch_id, branch_name=item.branch_name, amount=item.amount
            )
            for item in goals
        ],
    )


def _goal_state(goals: list[BranchGoal]) -> dict[str, Any]:
    return {str(item.branch_id): str(item.amount) if item.amount else None for item in goals}


@router.get(
    "/goals/{period}",
    response_model=GoalsOut,
    summary="Metas de venta del mes por sucursal",
    dependencies=[Depends(require_permission("sales_analytics:read"))],
)
async def month_goals(
    period: str,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    branch_id: uuid.UUID | None = None,
) -> GoalsOut:
    scope = await _scope(session, current, company_id, branch_id)
    return _goals_out(period, await cases.month_goals(company_id, scope, period))


@router.put(
    "/goals/{period}",
    response_model=GoalsOut,
    summary="Definir las metas de venta del mes (monto vacío quita la meta)",
    dependencies=[Depends(require_permission("sales_goals:manage"))],
)
async def save_goals(
    period: str,
    body: GoalsIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    cases: UseCases,
    audit: Audit,
    branch_id: uuid.UUID | None = None,
) -> GoalsOut:
    scope = await _scope(session, current, company_id, branch_id)
    key = parse_period(period).key
    before, after = await cases.save_goals(
        company_id,
        scope,
        key,
        [(item.branch_id, item.amount) for item in body.goals],
        current.id,
    )
    await audit.record(
        action="SET_SALES_GOALS",
        user_id=current.id,
        company_id=company_id,
        branch_id=branch_id,
        resource_type="sales_goals",
        resource_id=key,
        before_state=_goal_state(before),
        after_state=_goal_state(after),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _goals_out(key, after)

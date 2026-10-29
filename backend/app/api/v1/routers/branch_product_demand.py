"""Demand history and manual demand levels for products requested by a branch."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.branch_product_demand import (
    BranchDemandUnitTotal,
    BranchProductDemandItem,
    BranchProductDemandLevelResponse,
    BranchProductDemandLevelUpdate,
    BranchProductDemandResponse,
)
from app.application.audit.audit_service import AuditService
from app.infrastructure.models.branch_product_demand import BranchProductDemandLevelModel
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)

router = APIRouter(tags=["branch-product-demand"])
_EL_SALVADOR_TIMEZONE = ZoneInfo("America/El_Salvador")
_DEMAND_STATUSES = (
    "submitted",
    "rejected",
    "approved",
    "partially_quoted",
    "quoted",
    "partially_ordered",
    "completed",
)


def _period_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    local_start = datetime.combine(start, time.min, tzinfo=_EL_SALVADOR_TIMEZONE)
    local_end_exclusive = datetime.combine(
        end + timedelta(days=1), time.min, tzinfo=_EL_SALVADOR_TIMEZONE
    )
    return local_start.astimezone(UTC), local_end_exclusive.astimezone(UTC)


async def _branch_for_company(
    session: AsyncSession,
    current: CurrentUser,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> Branch:
    branch = await session.scalar(
        select(Branch).where(Branch.id == branch_id, Branch.company_id == company_id)
    )
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    return branch


@router.get(
    "/branches/{branch_id}/product-demand",
    response_model=BranchProductDemandResponse,
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def get_branch_product_demand(
    branch_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> BranchProductDemandResponse:
    company_id = request_company_id(request)
    await _branch_for_company(session, current, company_id, branch_id)

    end = date_to or datetime.now(_EL_SALVADOR_TIMEZONE).date()
    start = date_from or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, "La fecha inicial no puede ser posterior a la fecha final.")
    if (end - start).days > 365:
        raise HTTPException(422, "El período no puede exceder 366 días.")
    starts_at, ends_at = _period_bounds(start, end)

    common_filters = (
        PurchaseRequestModel.company_id == company_id,
        PurchaseRequestModel.branch_id == branch_id,
        PurchaseRequestModel.status.in_(_DEMAND_STATUSES),
        PurchaseRequestModel.request_date >= starts_at,
        PurchaseRequestModel.request_date < ends_at,
    )
    product_rows = (
        await session.execute(
            select(
                ProductModel.id_product,
                ProductModel.sku,
                ProductModel.name,
                func.count(func.distinct(PurchaseRequestModel.id)).label("request_count"),
                func.max(PurchaseRequestModel.request_date).label("last_requested_at"),
            )
            .join(
                PurchaseRequestDetailModel,
                (PurchaseRequestDetailModel.company_id == ProductModel.company_id)
                & (PurchaseRequestDetailModel.product_id == ProductModel.id_product),
            )
            .join(
                PurchaseRequestModel,
                (PurchaseRequestModel.id == PurchaseRequestDetailModel.purchase_request_id)
                & (PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id),
            )
            .where(ProductModel.company_id == company_id, *common_filters)
            .group_by(ProductModel.id_product, ProductModel.sku, ProductModel.name)
            .order_by(ProductModel.name, ProductModel.id_product)
        )
    ).all()

    unit_rows = (
        await session.execute(
            select(
                ProductModel.id_product,
                CompanyUnitModel.unit_id,
                func.coalesce(CompanyUnitModel.alias, UnitModel.name).label("unit_name"),
                UnitModel.symbol,
                func.sum(PurchaseRequestDetailModel.quantity).label("quantity"),
            )
            .join(
                PurchaseRequestDetailModel,
                (PurchaseRequestDetailModel.company_id == ProductModel.company_id)
                & (PurchaseRequestDetailModel.product_id == ProductModel.id_product),
            )
            .join(
                PurchaseRequestModel,
                (PurchaseRequestModel.id == PurchaseRequestDetailModel.purchase_request_id)
                & (PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id),
            )
            .join(
                CompanyUnitModel,
                (CompanyUnitModel.company_id == PurchaseRequestDetailModel.company_id)
                & (CompanyUnitModel.unit_id == PurchaseRequestDetailModel.unit_id),
            )
            .join(UnitModel, UnitModel.id_unit == CompanyUnitModel.unit_id)
            .where(ProductModel.company_id == company_id, *common_filters)
            .group_by(
                ProductModel.id_product,
                CompanyUnitModel.unit_id,
                CompanyUnitModel.alias,
                UnitModel.name,
                UnitModel.symbol,
            )
        )
    ).all()
    units_by_product: dict[int, list[BranchDemandUnitTotal]] = {}
    for row in unit_rows:
        units_by_product.setdefault(row.id_product, []).append(
            BranchDemandUnitTotal(
                unit_id=row.unit_id,
                unit_name=row.unit_name,
                unit_symbol=row.symbol,
                quantity=row.quantity,
            )
        )

    level_rows = (
        await session.execute(
            select(
                BranchProductDemandLevelModel.product_id,
                BranchProductDemandLevelModel.level,
            ).where(
                BranchProductDemandLevelModel.company_id == company_id,
                BranchProductDemandLevelModel.branch_id == branch_id,
            )
        )
    ).all()
    levels = {row.product_id: row.level for row in level_rows}

    items = [
        BranchProductDemandItem(
            product_id=row.id_product,
            sku=row.sku,
            product_name=row.name,
            request_count=row.request_count,
            last_requested_at=row.last_requested_at,
            unit_totals=units_by_product.get(row.id_product, []),
            demand_level=levels.get(row.id_product),
        )
        for row in product_rows
    ]
    return BranchProductDemandResponse(
        branch_id=branch_id,
        period_start=start,
        period_end=end,
        items=items,
    )


@router.put(
    "/branches/{branch_id}/product-demand/{product_id}",
    response_model=BranchProductDemandLevelResponse,
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def update_branch_product_demand_level(
    branch_id: uuid.UUID,
    product_id: int,
    body: BranchProductDemandLevelUpdate,
    session: SessionDep,
    current: CurrentUser,
    request: Request,
    audit: AuditService = Depends(get_audit_service),
) -> BranchProductDemandLevelResponse:
    company_id = request_company_id(request)
    await _branch_for_company(session, current, company_id, branch_id)
    product = await session.scalar(
        select(ProductModel.id_product).where(
            ProductModel.id_product == product_id,
            ProductModel.company_id == company_id,
        )
    )
    if product is None:
        raise HTTPException(404, "Producto no encontrado.")

    record = await session.scalar(
        select(BranchProductDemandLevelModel).where(
            BranchProductDemandLevelModel.company_id == company_id,
            BranchProductDemandLevelModel.branch_id == branch_id,
            BranchProductDemandLevelModel.product_id == product_id,
        )
    )
    before_level = record.level if record else None
    if body.level is None:
        if record is not None:
            await session.delete(record)
            await session.flush()
        after_level = None
        updated_at = None
    else:
        if record is None:
            record = BranchProductDemandLevelModel(
                company_id=company_id,
                branch_id=branch_id,
                product_id=product_id,
                level=body.level,
                updated_by_id=current.id,
            )
            session.add(record)
        else:
            record.level = body.level
            record.updated_by_id = current.id
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(409, "No se pudo guardar el nivel de demanda.") from exc
        after_level = record.level
        updated_at = record.updated_at

    await audit.record(
        action="UPDATE_BRANCH_PRODUCT_DEMAND_LEVEL",
        user_id=current.id,
        company_id=company_id,
        branch_id=branch_id,
        resource_type="branch_product_demand_levels",
        resource_id=f"{branch_id}:{product_id}",
        before_state={"level": before_level},
        after_state={"level": after_level},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return BranchProductDemandLevelResponse(
        branch_id=branch_id,
        product_id=product_id,
        level=after_level,
        updated_at=updated_at,
    )

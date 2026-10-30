"""PostgreSQL repository for purchase consolidations and work-list filters."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import cast as type_cast
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, and_, cast, exists, func, literal, or_, select, tuple_, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.domain.entities.purchase_consolidation import (
    BranchDemandLevel,
    ConsolidationEvent,
    ConsolidationLine,
    ConsolidationQuotationStatusChange,
    ConsolidationSource,
    ConsolidationWorkItem,
    PurchaseConsolidation,
    PurchaseConsolidationAward,
    PurchaseConsolidationStatus,
)
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.purchase_consolidation import (
    PurchaseConsolidationAwardModel,
    PurchaseConsolidationEventModel,
    PurchaseConsolidationLineModel,
    PurchaseConsolidationModel,
    PurchaseConsolidationSourceModel,
)
from app.infrastructure.models.purchase_quotation import PurchaseQuotationModel
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.models.user import User

_EL_SALVADOR_TIMEZONE = ZoneInfo("America/El_Salvador")


def _local_date_start_utc(value: date) -> datetime:
    """Return the UTC instant where an El Salvador calendar date begins."""

    return datetime.combine(value, time.min, tzinfo=_EL_SALVADOR_TIMEZONE).astimezone(UTC)


def _purchase_request_date_conditions(
    date_from: date | None,
    date_to: date | None,
) -> tuple[ColumnElement[bool], ...]:
    conditions: list[ColumnElement[bool]] = []
    if date_from:
        conditions.append(PurchaseRequestModel.request_date >= _local_date_start_utc(date_from))
    if date_to:
        conditions.append(
            PurchaseRequestModel.request_date < _local_date_start_utc(date_to + timedelta(days=1))
        )
    return tuple(conditions)


def _consolidation_period_conditions(
    date_from: date | None,
    date_to: date | None,
) -> tuple[ColumnElement[bool], ...]:
    conditions: list[ColumnElement[bool]] = []
    if date_from:
        conditions.append(PurchaseConsolidationModel.period_end >= date_from)
    if date_to:
        conditions.append(PurchaseConsolidationModel.period_start <= date_to)
    return tuple(conditions)


class SqlAlchemyPurchaseConsolidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_work_items(
        self,
        company_id: uuid.UUID,
        *,
        item_type: str | None,
        status: str | None,
        query: str | None,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID | None,
        category_id: int | None,
        date_from: date | None,
        date_to: date | None,
        consolidation_id: uuid.UUID | None,
        skip: int,
        limit: int,
    ) -> tuple[list[ConsolidationWorkItem], int]:
        request_filters = [PurchaseRequestModel.company_id == company_id]
        consolidation_filters = [PurchaseConsolidationModel.company_id == company_id]
        if status:
            request_filters.append(PurchaseRequestModel.status == status)
            consolidation_filters.append(PurchaseConsolidationModel.status == status)
        if branch_id:
            request_filters.append(PurchaseRequestModel.branch_id == branch_id)
            matching_branch_source = exists(
                select(1)
                .select_from(PurchaseConsolidationSourceModel)
                .join(
                    PurchaseRequestModel,
                    and_(
                        PurchaseRequestModel.id
                        == PurchaseConsolidationSourceModel.purchase_request_id,
                        PurchaseRequestModel.company_id
                        == PurchaseConsolidationSourceModel.company_id,
                    ),
                )
                .join(
                    PurchaseConsolidationLineModel,
                    PurchaseConsolidationLineModel.id
                    == PurchaseConsolidationSourceModel.consolidation_line_id,
                )
                .where(
                    PurchaseConsolidationLineModel.consolidation_id
                    == PurchaseConsolidationModel.id,
                    PurchaseConsolidationSourceModel.company_id == company_id,
                    PurchaseRequestModel.branch_id == branch_id,
                )
                .correlate(PurchaseConsolidationModel)
            )
            outside_branch_source = exists(
                select(1)
                .select_from(PurchaseConsolidationSourceModel)
                .join(
                    PurchaseRequestModel,
                    and_(
                        PurchaseRequestModel.id
                        == PurchaseConsolidationSourceModel.purchase_request_id,
                        PurchaseRequestModel.company_id
                        == PurchaseConsolidationSourceModel.company_id,
                    ),
                )
                .join(
                    PurchaseConsolidationLineModel,
                    PurchaseConsolidationLineModel.id
                    == PurchaseConsolidationSourceModel.consolidation_line_id,
                )
                .where(
                    PurchaseConsolidationLineModel.consolidation_id
                    == PurchaseConsolidationModel.id,
                    PurchaseConsolidationSourceModel.company_id == company_id,
                    PurchaseRequestModel.branch_id != branch_id,
                )
                .correlate(PurchaseConsolidationModel)
            )
            central_warehouse_in_branch = exists(
                select(1)
                .select_from(Warehouse)
                .where(
                    Warehouse.id == PurchaseConsolidationModel.central_warehouse_id,
                    Warehouse.branch_id == branch_id,
                )
                .correlate(PurchaseConsolidationModel)
            )
            consolidation_filters.append(
                or_(
                    and_(matching_branch_source, ~outside_branch_source),
                    and_(~matching_branch_source, central_warehouse_in_branch),
                )
            )
        if warehouse_id:
            request_filters.append(PurchaseRequestModel.warehouse_id == warehouse_id)
            consolidation_filters.append(
                or_(
                    PurchaseConsolidationModel.central_warehouse_id == warehouse_id,
                    exists(
                        select(1)
                        .select_from(PurchaseConsolidationSourceModel)
                        .join(
                            PurchaseRequestModel,
                            and_(
                                PurchaseRequestModel.id
                                == PurchaseConsolidationSourceModel.purchase_request_id,
                                PurchaseRequestModel.company_id
                                == PurchaseConsolidationSourceModel.company_id,
                            ),
                        )
                        .join(
                            PurchaseConsolidationLineModel,
                            PurchaseConsolidationLineModel.id
                            == PurchaseConsolidationSourceModel.consolidation_line_id,
                        )
                        .where(
                            PurchaseConsolidationLineModel.consolidation_id
                            == PurchaseConsolidationModel.id,
                            PurchaseConsolidationSourceModel.company_id == company_id,
                            PurchaseRequestModel.warehouse_id == warehouse_id,
                        )
                        .correlate(PurchaseConsolidationModel)
                    ),
                )
            )
        if category_id is not None:
            request_filters.append(
                exists(
                    select(1)
                    .select_from(PurchaseRequestDetailModel)
                    .join(
                        ProductModel,
                        and_(
                            ProductModel.id_product == PurchaseRequestDetailModel.product_id,
                            ProductModel.company_id == PurchaseRequestDetailModel.company_id,
                        ),
                    )
                    .where(
                        PurchaseRequestDetailModel.purchase_request_id == PurchaseRequestModel.id,
                        PurchaseRequestDetailModel.company_id == company_id,
                        ProductModel.company_id == company_id,
                        ProductModel.id_category == category_id,
                    )
                    .correlate(PurchaseRequestModel)
                )
            )
            consolidation_filters.append(
                exists(
                    select(1)
                    .select_from(PurchaseConsolidationLineModel)
                    .join(
                        ProductModel,
                        and_(
                            ProductModel.id_product == PurchaseConsolidationLineModel.product_id,
                            ProductModel.company_id == PurchaseConsolidationLineModel.company_id,
                        ),
                    )
                    .where(
                        PurchaseConsolidationLineModel.consolidation_id
                        == PurchaseConsolidationModel.id,
                        PurchaseConsolidationLineModel.company_id == company_id,
                        ProductModel.company_id == company_id,
                        ProductModel.id_category == category_id,
                    )
                    .correlate(PurchaseConsolidationModel)
                )
            )
        request_filters.extend(_purchase_request_date_conditions(date_from, date_to))
        consolidation_filters.extend(_consolidation_period_conditions(date_from, date_to))
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            request_filters.append(
                or_(
                    PurchaseRequestModel.code.ilike(pattern),
                    PurchaseRequestModel.justification.ilike(pattern),
                    User.username.ilike(pattern),
                )
            )
            consolidation_filters.append(
                or_(
                    PurchaseConsolidationModel.code.ilike(pattern),
                    PurchaseConsolidationModel.notes.ilike(pattern),
                )
            )
        if consolidation_id:
            request_filters.append(
                exists(
                    select(1)
                    .select_from(PurchaseConsolidationSourceModel)
                    .join(
                        PurchaseConsolidationLineModel,
                        PurchaseConsolidationLineModel.id
                        == PurchaseConsolidationSourceModel.consolidation_line_id,
                    )
                    .where(
                        PurchaseConsolidationSourceModel.purchase_request_id
                        == PurchaseRequestModel.id,
                        PurchaseConsolidationSourceModel.company_id == company_id,
                        PurchaseConsolidationLineModel.consolidation_id == consolidation_id,
                    )
                    .correlate(PurchaseRequestModel)
                )
            )
            consolidation_filters.append(PurchaseConsolidationModel.id == consolidation_id)

        request_count = (
            select(func.count())
            .select_from(PurchaseRequestDetailModel)
            .where(PurchaseRequestDetailModel.purchase_request_id == PurchaseRequestModel.id)
            .correlate(PurchaseRequestModel)
            .scalar_subquery()
        )
        source_count = (
            select(func.count())
            .select_from(PurchaseConsolidationSourceModel)
            .join(
                PurchaseConsolidationLineModel,
                PurchaseConsolidationLineModel.id
                == PurchaseConsolidationSourceModel.consolidation_line_id,
            )
            .where(PurchaseConsolidationLineModel.consolidation_id == PurchaseConsolidationModel.id)
            .correlate(PurchaseConsolidationModel)
            .scalar_subquery()
        )
        line_count = (
            select(func.count())
            .select_from(PurchaseConsolidationLineModel)
            .where(PurchaseConsolidationLineModel.consolidation_id == PurchaseConsolidationModel.id)
            .correlate(PurchaseConsolidationModel)
            .scalar_subquery()
        )

        requests = (
            select(
                PurchaseRequestModel.id.label("id"),
                PurchaseRequestModel.code.label("code"),
                literal("individual").label("item_type"),
                PurchaseRequestModel.status.label("status"),
                PurchaseRequestModel.request_date.label("request_date"),
                User.username.label("requester_name"),
                PurchaseRequestModel.required_date.label("required_date"),
                PurchaseRequestModel.branch_id.label("branch_id"),
                Branch.name.label("branch_name"),
                PurchaseRequestModel.warehouse_id.label("warehouse_id"),
                Warehouse.name.label("warehouse_name"),
                request_count.label("line_count"),
                literal(0).label("source_count"),
            )
            .join(Branch, Branch.id == PurchaseRequestModel.branch_id)
            .join(Warehouse, Warehouse.id == PurchaseRequestModel.warehouse_id)
            .outerjoin(User, User.id == PurchaseRequestModel.requested_by_id)
            .where(*request_filters)
        )

        consolidations = (
            select(
                PurchaseConsolidationModel.id.label("id"),
                PurchaseConsolidationModel.code.label("code"),
                literal("consolidated").label("item_type"),
                PurchaseConsolidationModel.status.label("status"),
                PurchaseConsolidationModel.created_at.label("request_date"),
                literal(None, type_=User.__table__.c.username.type).label("requester_name"),
                literal(None, type_=PurchaseRequestModel.__table__.c.required_date.type).label(
                    "required_date"
                ),
                literal(None, type_=PurchaseRequestModel.__table__.c.branch_id.type).label(
                    "branch_id"
                ),
                literal(None, type_=Branch.__table__.c.name.type).label("branch_name"),
                PurchaseConsolidationModel.central_warehouse_id.label("warehouse_id"),
                Warehouse.name.label("warehouse_name"),
                line_count.label("line_count"),
                source_count.label("source_count"),
            )
            .outerjoin(Warehouse, Warehouse.id == PurchaseConsolidationModel.central_warehouse_id)
            .where(*consolidation_filters)
        )
        if item_type == "individual":
            combined = requests.subquery()
        elif item_type == "consolidated":
            combined = consolidations.subquery()
        else:
            combined = union_all(requests, consolidations).subquery()

        total = await self._session.scalar(select(func.count()).select_from(combined))
        result = await self._session.execute(
            select(combined)
            .order_by(combined.c.request_date.desc(), combined.c.code.desc())
            .offset(skip)
            .limit(limit)
        )
        items = [
            ConsolidationWorkItem(
                id=row.id,
                code=row.code,
                item_type=row.item_type,
                status=row.status,
                request_date=row.request_date,
                requester_name=row.requester_name,
                required_date=row.required_date,
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                warehouse_id=row.warehouse_id,
                warehouse_name=row.warehouse_name,
                line_count=int(row.line_count or 0),
                source_count=int(row.source_count or 0),
            )
            for row in result
        ]
        return items, int(total or 0)

    async def list_approved_requests(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
        query: str | None,
        skip: int,
        limit: int,
        request_ids: tuple[uuid.UUID, ...] = (),
    ) -> tuple[list[dict[str, object]], int]:
        filters = [
            PurchaseRequestModel.company_id == company_id,
            PurchaseRequestModel.status == "approved",
        ]
        if request_ids:
            filters.append(PurchaseRequestModel.id.in_(request_ids))
        else:
            filters.extend(_purchase_request_date_conditions(date_from, date_to))
            if branch_id:
                filters.append(PurchaseRequestModel.branch_id == branch_id)
            if warehouse_id:
                filters.append(PurchaseRequestModel.warehouse_id == warehouse_id)
            if query and query.strip():
                pattern = f"%{query.strip()}%"
                filters.append(
                    or_(
                        PurchaseRequestModel.code.ilike(pattern),
                        PurchaseRequestModel.justification.ilike(pattern),
                    )
                )
        filters.append(
            ~exists(
                select(1)
                .select_from(PurchaseRequestDetailModel)
                .join(
                    PurchaseConsolidationSourceModel,
                    PurchaseConsolidationSourceModel.purchase_request_detail_id
                    == PurchaseRequestDetailModel.id,
                )
                .join(
                    PurchaseConsolidationLineModel,
                    PurchaseConsolidationLineModel.id
                    == PurchaseConsolidationSourceModel.consolidation_line_id,
                )
                .join(
                    PurchaseConsolidationModel,
                    and_(
                        PurchaseConsolidationModel.id
                        == PurchaseConsolidationLineModel.consolidation_id,
                        PurchaseConsolidationModel.company_id
                        == PurchaseConsolidationLineModel.company_id,
                    ),
                )
                .where(
                    PurchaseRequestDetailModel.purchase_request_id == PurchaseRequestModel.id,
                    PurchaseRequestDetailModel.company_id == PurchaseRequestModel.company_id,
                    PurchaseConsolidationSourceModel.purchase_request_detail_id
                    == PurchaseRequestDetailModel.id,
                    PurchaseConsolidationSourceModel.company_id
                    == PurchaseRequestDetailModel.company_id,
                    PurchaseConsolidationSourceModel.company_id == company_id,
                    PurchaseConsolidationModel.status
                    != PurchaseConsolidationStatus.CANCELLED.value,
                )
            )
        )
        base = (
            select(PurchaseRequestModel)
            .options(
                selectinload(PurchaseRequestModel.details),
                selectinload(PurchaseRequestModel.branch),
                selectinload(PurchaseRequestModel.warehouse),
            )
            .where(*filters)
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        result = await self._session.execute(
            base.order_by(
                PurchaseRequestModel.request_date.desc(), PurchaseRequestModel.code.desc()
            )
            .offset(skip)
            .limit(limit)
        )
        request_models = result.scalars().all()
        requester_names: dict[uuid.UUID, str | None] = {}
        if request_models:
            requester_rows = await self._session.execute(
                select(PurchaseRequestModel.id, User.username)
                .outerjoin(User, User.id == PurchaseRequestModel.requested_by_id)
                .where(
                    PurchaseRequestModel.company_id == company_id,
                    PurchaseRequestModel.id.in_([model.id for model in request_models]),
                )
            )
            requester_names = {row.id: row.username for row in requester_rows}
        detail_ids = [detail.id for model in request_models for detail in model.details]
        detail_labels: dict[uuid.UUID, tuple[str, str, str]] = {}
        request_counts: dict[tuple[uuid.UUID, int], int] = {}
        if detail_ids:
            label_rows = await self._session.execute(
                select(
                    PurchaseRequestDetailModel.id,
                    ProductModel.sku,
                    ProductModel.name,
                    func.coalesce(CompanyUnitModel.alias, UnitModel.name),
                )
                .join(
                    ProductModel,
                    and_(
                        ProductModel.id_product == PurchaseRequestDetailModel.product_id,
                        ProductModel.company_id == PurchaseRequestDetailModel.company_id,
                    ),
                )
                .join(
                    CompanyUnitModel,
                    and_(
                        CompanyUnitModel.company_id == PurchaseRequestDetailModel.company_id,
                        CompanyUnitModel.unit_id == PurchaseRequestDetailModel.unit_id,
                    ),
                )
                .join(UnitModel, UnitModel.id_unit == PurchaseRequestDetailModel.unit_id)
                .where(
                    PurchaseRequestDetailModel.company_id == company_id,
                    PurchaseRequestDetailModel.id.in_(detail_ids),
                )
            )
            detail_labels = {row[0]: (row[1], row[2], row[3]) for row in label_rows}
            branch_product_pairs = list(
                {
                    (model.branch_id, detail.product_id)
                    for model in request_models
                    for detail in model.details
                }
            )
            if branch_product_pairs:
                history_rows = await self._session.execute(
                    select(
                        PurchaseRequestModel.branch_id,
                        PurchaseRequestDetailModel.product_id,
                        func.count(func.distinct(PurchaseRequestModel.id)),
                    )
                    .join(
                        PurchaseRequestDetailModel,
                        and_(
                            PurchaseRequestDetailModel.purchase_request_id
                            == PurchaseRequestModel.id,
                            PurchaseRequestDetailModel.company_id
                            == PurchaseRequestModel.company_id,
                        ),
                    )
                    .where(
                        PurchaseRequestModel.company_id == company_id,
                        PurchaseRequestModel.status.in_(
                            (
                                "approved",
                                "partially_quoted",
                                "quoted",
                                "partially_ordered",
                                "completed",
                            )
                        ),
                        *_purchase_request_date_conditions(date_from, date_to),
                        tuple_(
                            PurchaseRequestModel.branch_id, PurchaseRequestDetailModel.product_id
                        ).in_(branch_product_pairs),
                    )
                    .group_by(PurchaseRequestModel.branch_id, PurchaseRequestDetailModel.product_id)
                )
                request_counts = {(row[0], row[1]): int(row[2]) for row in history_rows}
        output = []
        for model in request_models:
            output.append(
                {
                    "id": model.id,
                    "code": model.code,
                    "request_date": model.request_date,
                    "requester_name": requester_names.get(model.id),
                    "required_date": model.required_date,
                    "branch_id": model.branch_id,
                    "branch_name": model.branch.name if model.branch else None,
                    "warehouse_id": model.warehouse_id,
                    "warehouse_name": model.warehouse.name if model.warehouse else None,
                    "line_count": len(model.details),
                    "details": [
                        {
                            "id": detail.id,
                            "product_id": detail.product_id,
                            "product_sku": detail_labels.get(
                                detail.id,
                                (
                                    f"PRD-{detail.product_id}",
                                    f"Producto {detail.product_id}",
                                    f"Unidad {detail.unit_id}",
                                ),
                            )[0],
                            "product_name": detail_labels.get(
                                detail.id,
                                (
                                    f"PRD-{detail.product_id}",
                                    f"Producto {detail.product_id}",
                                    f"Unidad {detail.unit_id}",
                                ),
                            )[1],
                            "unit_id": detail.unit_id,
                            "unit_name": detail_labels.get(
                                detail.id,
                                (
                                    f"PRD-{detail.product_id}",
                                    f"Producto {detail.product_id}",
                                    f"Unidad {detail.unit_id}",
                                ),
                            )[2],
                            "quantity": detail.quantity,
                            "request_count": request_counts.get(
                                (model.branch_id, detail.product_id), 0
                            ),
                        }
                        for detail in model.details
                    ],
                }
            )
        return output, int(total or 0)

    async def resolve_selected_requests(
        self, company_id: uuid.UUID, request_ids: tuple[uuid.UUID, ...]
    ) -> list[dict[str, object]]:
        """Explain eligibility for selected, company-owned requests.

        Only non-cancelled consolidations are returned. DISTINCT avoids repeating
        one consolidation when a request contributes more than one detail line.
        Branch authorization and destination-document visibility are enforced by
        the API before this result is exposed.
        """
        selected_ids = tuple(dict.fromkeys(request_ids))
        if not selected_ids:
            return []

        request_rows = await self._session.execute(
            select(
                PurchaseRequestModel.id, PurchaseRequestModel.code, PurchaseRequestModel.status
            ).where(
                PurchaseRequestModel.company_id == company_id,
                PurchaseRequestModel.id.in_(selected_ids),
            )
        )
        requests = {row.id: row for row in request_rows}
        if not requests:
            return []

        consolidation_rows = await self._session.execute(
            select(
                PurchaseConsolidationSourceModel.purchase_request_id,
                PurchaseConsolidationModel.id,
                PurchaseConsolidationModel.code,
                PurchaseConsolidationModel.status,
            )
            .join(
                PurchaseConsolidationLineModel,
                and_(
                    PurchaseConsolidationLineModel.id
                    == PurchaseConsolidationSourceModel.consolidation_line_id,
                    PurchaseConsolidationLineModel.company_id
                    == PurchaseConsolidationSourceModel.company_id,
                ),
            )
            .join(
                PurchaseConsolidationModel,
                and_(
                    PurchaseConsolidationModel.id
                    == PurchaseConsolidationLineModel.consolidation_id,
                    PurchaseConsolidationModel.company_id
                    == PurchaseConsolidationLineModel.company_id,
                ),
            )
            .where(
                PurchaseConsolidationSourceModel.company_id == company_id,
                PurchaseConsolidationSourceModel.purchase_request_id.in_(tuple(requests)),
                PurchaseConsolidationModel.status != PurchaseConsolidationStatus.CANCELLED.value,
            )
            .distinct()
            .order_by(
                PurchaseConsolidationSourceModel.purchase_request_id,
                PurchaseConsolidationModel.code,
            )
        )
        consolidations_by_request: dict[uuid.UUID, dict[uuid.UUID, dict[str, object]]] = {}
        for row in consolidation_rows:
            consolidations_by_request.setdefault(row.purchase_request_id, {})[row.id] = {
                "id": row.id,
                "code": row.code,
                "status": row.status,
            }

        resolutions: list[dict[str, object]] = []
        for request_id in selected_ids:
            item = requests.get(request_id)
            if item is None:
                continue
            consolidations = tuple(consolidations_by_request.get(request_id, {}).values())
            eligibility = (
                "already_consolidated"
                if consolidations
                else "eligible"
                if item.status == "approved"
                else "not_eligible"
            )
            resolutions.append(
                {
                    "id": item.id,
                    "code": item.code,
                    "eligibility": eligibility,
                    "consolidations": consolidations,
                }
            )
        return resolutions

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        await self._session.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtext(f"purchase_consolidations:{company_id}"))
            )
        )
        value = await self._session.scalar(
            select(
                func.coalesce(
                    func.max(cast(func.substr(PurchaseConsolidationModel.code, 4), Integer)), 0
                )
            ).where(PurchaseConsolidationModel.company_id == company_id)
        )
        return f"CD-{int(value or 0) + 1:05d}"

    async def central_warehouse_available(
        self, company_id: uuid.UUID, warehouse_id: uuid.UUID
    ) -> bool:
        return bool(
            await self._session.scalar(
                select(func.count())
                .select_from(Warehouse)
                .join(
                    Branch,
                    (Branch.id == Warehouse.branch_id)
                    & (Branch.company_id == Warehouse.company_id),
                )
                .where(
                    Warehouse.id == warehouse_id,
                    Warehouse.company_id == company_id,
                    Warehouse.deleted_at.is_(None),
                    Warehouse.operational_status == "active",
                    Warehouse.is_central.is_(True),
                    Branch.is_headquarters.is_(True),
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                )
            )
        )

    async def has_active_source(self, company_id: uuid.UUID, detail_id: uuid.UUID) -> bool:
        await self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtext(f"purchase_consolidation_source:{company_id}:{detail_id}")
                )
            )
        )
        return bool(
            await self._session.scalar(
                select(func.count())
                .select_from(PurchaseConsolidationSourceModel)
                .join(
                    PurchaseConsolidationLineModel,
                    PurchaseConsolidationLineModel.id
                    == PurchaseConsolidationSourceModel.consolidation_line_id,
                )
                .join(
                    PurchaseConsolidationModel,
                    PurchaseConsolidationModel.id
                    == PurchaseConsolidationLineModel.consolidation_id,
                )
                .where(
                    PurchaseConsolidationSourceModel.company_id == company_id,
                    PurchaseConsolidationSourceModel.purchase_request_detail_id == detail_id,
                    PurchaseConsolidationModel.status
                    != PurchaseConsolidationStatus.CANCELLED.value,
                )
            )
        )

    async def create(self, consolidation: PurchaseConsolidation) -> PurchaseConsolidation:
        model = PurchaseConsolidationModel(
            id=consolidation.id,
            company_id=consolidation.company_id,
            code=consolidation.code,
            period_start=consolidation.period_start,
            period_end=consolidation.period_end,
            status=consolidation.status.value,
            created_by_id=consolidation.created_by_id,
            central_warehouse_id=consolidation.central_warehouse_id,
            notes=consolidation.notes,
        )
        model.lines = [self._line_model(consolidation, line) for line in consolidation.lines]
        model.events = [
            PurchaseConsolidationEventModel(
                id=uuid.uuid4(),
                company_id=consolidation.company_id,
                consolidation_id=consolidation.id,
                actor_id=consolidation.created_by_id,
                action="created",
                reason="Consolidado creado desde solicitudes aprobadas.",
                changes={"source_count": sum(len(line.sources) for line in consolidation.lines)},
            )
        ]
        self._session.add(model)
        await self._session.flush()
        saved = await self.get(consolidation.company_id, consolidation.id)
        assert saved is not None
        return saved

    async def get(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID, *, for_update: bool = False
    ) -> PurchaseConsolidation | None:
        statement = (
            select(PurchaseConsolidationModel)
            .options(
                selectinload(PurchaseConsolidationModel.central_warehouse),
                selectinload(PurchaseConsolidationModel.lines)
                .selectinload(PurchaseConsolidationLineModel.sources)
                .selectinload(PurchaseConsolidationSourceModel.purchase_request)
                .selectinload(PurchaseRequestModel.branch),
                selectinload(PurchaseConsolidationModel.lines)
                .selectinload(PurchaseConsolidationLineModel.sources)
                .selectinload(PurchaseConsolidationSourceModel.purchase_request)
                .selectinload(PurchaseRequestModel.warehouse),
            )
            .where(
                PurchaseConsolidationModel.company_id == company_id,
                PurchaseConsolidationModel.id == consolidation_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=PurchaseConsolidationModel)
        model = await self._session.scalar(statement)
        if model is None:
            return None
        return await self._to_entity(model)

    async def save_draft(  # noqa: C901
        self,
        consolidation: PurchaseConsolidation,
        *,
        actor_id: uuid.UUID,
        change_reason: str,
    ) -> PurchaseConsolidation | None:
        model = await self._get_model(consolidation.company_id, consolidation.id, for_update=True)
        if model is None or model.status != PurchaseConsolidationStatus.DRAFT.value:
            return None
        old_sources = {source.id: source for line in model.lines for source in line.sources}
        incoming_sources = {
            source.id: source for line in consolidation.lines for source in line.sources
        }
        if not set(old_sources).issubset(incoming_sources):
            raise ValueError("No se permite eliminar la procedencia de una línea del consolidado.")
        old_lines = {line.id: line for line in model.lines}
        changes: list[dict[str, object]] = []
        for line in consolidation.lines:
            existing_line = old_lines.get(line.id)
            if existing_line is None:
                existing_line = self._line_model(consolidation, line)
                model.lines.append(existing_line)
                changes.append(
                    {
                        "action": "line_added",
                        "product_id": line.product_id,
                        "unit_id": line.unit_id,
                        "central_quantity": str(line.central_quantity),
                    }
                )
            else:
                if existing_line.central_quantity != line.central_quantity:
                    changes.append(
                        {
                            "action": "central_quantity_changed",
                            "line_id": str(line.id),
                            "before": str(existing_line.central_quantity),
                            "after": str(line.central_quantity),
                            "reason": line.central_reason,
                        }
                    )
                    existing_line.central_quantity = line.central_quantity
                    existing_line.central_reason = line.central_reason
                existing_sources = {source.id: source for source in existing_line.sources}
                for source in line.sources:
                    persisted = existing_sources.get(source.id)
                    if persisted is None:
                        persisted = PurchaseConsolidationSourceModel(
                            id=source.id,
                            company_id=consolidation.company_id,
                            consolidation_line_id=line.id,
                            purchase_request_id=source.purchase_request_id,
                            purchase_request_detail_id=source.purchase_request_detail_id,
                            requested_quantity=source.requested_quantity,
                            included_quantity=source.included_quantity,
                            reason=source.reason,
                            demand_level=source.demand_level.value if source.demand_level else None,
                        )
                        existing_line.sources.append(persisted)
                        changes.append(
                            {
                                "action": "source_added",
                                "source_id": str(source.id),
                                "request_code": source.request_code,
                                "included_quantity": str(source.included_quantity),
                            }
                        )
                    elif (
                        persisted.included_quantity != source.included_quantity
                        or persisted.reason != source.reason
                    ):
                        changes.append(
                            {
                                "action": "source_quantity_changed",
                                "source_id": str(source.id),
                                "request_code": source.request_code,
                                "before": str(persisted.included_quantity),
                                "after": str(source.included_quantity),
                                "reason": source.reason,
                            }
                        )
                        persisted.included_quantity = source.included_quantity
                        persisted.reason = source.reason
                    desired_demand_level = (
                        source.demand_level.value if source.demand_level else None
                    )
                    if persisted.demand_level != desired_demand_level:
                        changes.append(
                            {
                                "action": "source_demand_level_changed",
                                "source_id": str(source.id),
                                "request_code": source.request_code,
                                "before": persisted.demand_level,
                                "after": desired_demand_level,
                            }
                        )
                        persisted.demand_level = desired_demand_level
        if model.central_warehouse_id != consolidation.central_warehouse_id:
            changes.append(
                {
                    "action": "central_warehouse_changed",
                    "before": str(model.central_warehouse_id)
                    if model.central_warehouse_id
                    else None,
                    "after": str(consolidation.central_warehouse_id)
                    if consolidation.central_warehouse_id
                    else None,
                }
            )
            model.central_warehouse_id = consolidation.central_warehouse_id
        if model.notes != consolidation.notes:
            changes.append(
                {"action": "notes_changed", "before": model.notes, "after": consolidation.notes}
            )
        model.notes = consolidation.notes
        if changes:
            model.events.append(
                PurchaseConsolidationEventModel(
                    id=uuid.uuid4(),
                    company_id=consolidation.company_id,
                    consolidation_id=consolidation.id,
                    actor_id=actor_id,
                    action="draft_updated",
                    reason=change_reason,
                    changes={"items": changes},
                )
            )
        await self._session.flush()
        return await self.get(consolidation.company_id, consolidation.id)

    async def cancel(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidation | None:
        model = await self._get_model(company_id, consolidation_id, for_update=True)
        if model is None:
            return None
        if model.status != PurchaseConsolidationStatus.DRAFT.value:
            return None
        model.status = PurchaseConsolidationStatus.CANCELLED.value
        model.events.append(
            PurchaseConsolidationEventModel(
                id=uuid.uuid4(),
                company_id=company_id,
                consolidation_id=consolidation_id,
                actor_id=actor_id,
                action="cancelled",
                reason=reason,
                changes={"status": "cancelled"},
            )
        )
        await self._session.flush()
        return await self.get(company_id, consolidation_id)

    async def close(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
        coverage_basis: str = "awarded_in_consolidation",
        unawarded_lines: tuple[dict[str, object], ...] = (),
        quotation_status_changes: tuple[ConsolidationQuotationStatusChange, ...] = (),
    ) -> PurchaseConsolidation | None:
        model = await self._get_model(company_id, consolidation_id, for_update=True)
        if model is None or model.status not in {
            PurchaseConsolidationStatus.DRAFT.value,
            PurchaseConsolidationStatus.FROZEN.value,
        }:
            return None
        status_change_details: list[dict[str, str]] = []
        if quotation_status_changes:
            quotation_ids = tuple(change.quotation_id for change in quotation_status_changes)
            quotations = await self._session.scalars(
                select(PurchaseQuotationModel)
                .where(
                    PurchaseQuotationModel.company_id == company_id,
                    PurchaseQuotationModel.consolidation_id == consolidation_id,
                    PurchaseQuotationModel.id.in_(quotation_ids),
                )
                .with_for_update()
            )
            quotations_by_id = {quotation.id: quotation for quotation in quotations}
            if len(quotations_by_id) != len(quotation_status_changes):
                return None
            for change in quotation_status_changes:
                quotation = quotations_by_id[change.quotation_id]
                if quotation.status != change.expected_status.value:
                    return None
                quotation.status = change.target_status.value
                status_change_details.append(
                    {
                        "quotation_id": str(quotation.id),
                        "quotation_code": quotation.code,
                        "before": change.expected_status.value,
                        "after": change.target_status.value,
                    }
                )
        previous_status = model.status
        model.status = PurchaseConsolidationStatus.CLOSED.value
        model.events.append(
            PurchaseConsolidationEventModel(
                id=uuid.uuid4(),
                company_id=company_id,
                consolidation_id=consolidation_id,
                actor_id=actor_id,
                action="closed",
                reason=reason,
                changes={
                    "status": {
                        "before": previous_status,
                        "after": PurchaseConsolidationStatus.CLOSED.value,
                    },
                    "coverage_basis": coverage_basis,
                    "unawarded_lines": list(unawarded_lines),
                    "quotation_status_changes": status_change_details,
                },
            )
        )
        await self._session.flush()
        return await self.get(company_id, consolidation_id)

    async def list_awards(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> tuple[PurchaseConsolidationAward, ...]:
        rows = await self._session.scalars(
            select(PurchaseConsolidationAwardModel)
            .where(
                PurchaseConsolidationAwardModel.company_id == company_id,
                PurchaseConsolidationAwardModel.consolidation_id == consolidation_id,
            )
            .order_by(
                PurchaseConsolidationAwardModel.created_at, PurchaseConsolidationAwardModel.id
            )
        )
        return tuple(self._award_to_entity(row) for row in rows)

    async def create_award(
        self, award: PurchaseConsolidationAward
    ) -> PurchaseConsolidationAward | None:
        consolidation = await self._session.scalar(
            select(PurchaseConsolidationModel)
            .options(selectinload(PurchaseConsolidationModel.events))
            .where(
                PurchaseConsolidationModel.company_id == award.company_id,
                PurchaseConsolidationModel.id == award.consolidation_id,
            )
            .with_for_update(of=PurchaseConsolidationModel)
        )
        if consolidation is None:
            return None
        model = PurchaseConsolidationAwardModel(
            id=award.id,
            company_id=award.company_id,
            consolidation_id=award.consolidation_id,
            consolidation_line_id=award.consolidation_line_id,
            purchase_quotation_id=award.purchase_quotation_id,
            purchase_quotation_detail_id=award.purchase_quotation_detail_id,
            supplier_id=award.supplier_id,
            quantity=award.quantity,
            reason=award.reason,
            decided_by_id=award.decided_by_id,
        )
        consolidation.events.append(
            PurchaseConsolidationEventModel(
                id=uuid.uuid4(),
                company_id=award.company_id,
                consolidation_id=award.consolidation_id,
                actor_id=award.decided_by_id,
                action="award_created",
                reason=award.reason,
                changes={
                    "award_id": str(award.id),
                    "line_id": str(award.consolidation_line_id),
                    "quotation_id": str(award.purchase_quotation_id),
                    "quotation_detail_id": str(award.purchase_quotation_detail_id),
                    "supplier_id": award.supplier_id,
                    "quantity": str(award.quantity),
                },
            )
        )
        self._session.add(model)
        await self._session.flush()
        return self._award_to_entity(model)

    async def revoke_award(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        award_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        reason: str,
    ) -> PurchaseConsolidationAward | None:
        model = await self._session.scalar(
            select(PurchaseConsolidationAwardModel)
            .where(
                PurchaseConsolidationAwardModel.company_id == company_id,
                PurchaseConsolidationAwardModel.consolidation_id == consolidation_id,
                PurchaseConsolidationAwardModel.id == award_id,
                PurchaseConsolidationAwardModel.revoked_at.is_(None),
            )
            .with_for_update()
        )
        if model is None:
            return None
        model.revoked_at = datetime.now(UTC)
        model.revoked_by_id = actor_id
        model.revocation_reason = reason
        consolidation = await self._session.scalar(
            select(PurchaseConsolidationModel)
            .options(selectinload(PurchaseConsolidationModel.events))
            .where(
                PurchaseConsolidationModel.company_id == company_id,
                PurchaseConsolidationModel.id == consolidation_id,
            )
        )
        if consolidation is None:
            return None
        consolidation.events.append(
            PurchaseConsolidationEventModel(
                id=uuid.uuid4(),
                company_id=company_id,
                consolidation_id=consolidation_id,
                actor_id=actor_id,
                action="award_revoked",
                reason=reason,
                changes={
                    "award_id": str(model.id),
                    "line_id": str(model.consolidation_line_id),
                    "quotation_id": str(model.purchase_quotation_id),
                    "quotation_detail_id": str(model.purchase_quotation_detail_id),
                    "supplier_id": model.supplier_id,
                    "quantity": str(model.quantity),
                },
            )
        )
        await self._session.flush()
        return self._award_to_entity(model)

    @staticmethod
    def _award_to_entity(model: PurchaseConsolidationAwardModel) -> PurchaseConsolidationAward:
        return PurchaseConsolidationAward(
            id=model.id,
            company_id=model.company_id,
            consolidation_id=model.consolidation_id,
            consolidation_line_id=model.consolidation_line_id,
            purchase_quotation_id=model.purchase_quotation_id,
            purchase_quotation_detail_id=model.purchase_quotation_detail_id,
            supplier_id=model.supplier_id,
            quantity=model.quantity,
            reason=model.reason,
            decided_by_id=model.decided_by_id,
            created_at=model.created_at,
            revoked_at=model.revoked_at,
            revoked_by_id=model.revoked_by_id,
            revocation_reason=model.revocation_reason,
        )

    async def _get_model(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID, *, for_update: bool = False
    ) -> PurchaseConsolidationModel | None:
        statement = (
            select(PurchaseConsolidationModel)
            .options(
                selectinload(PurchaseConsolidationModel.lines).selectinload(
                    PurchaseConsolidationLineModel.sources
                )
            )
            .where(
                PurchaseConsolidationModel.company_id == company_id,
                PurchaseConsolidationModel.id == consolidation_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=PurchaseConsolidationModel)
        return type_cast(PurchaseConsolidationModel | None, await self._session.scalar(statement))

    def _line_model(
        self, consolidation: PurchaseConsolidation, line: ConsolidationLine
    ) -> PurchaseConsolidationLineModel:
        return PurchaseConsolidationLineModel(
            id=line.id,
            company_id=consolidation.company_id,
            consolidation_id=consolidation.id,
            product_id=line.product_id,
            unit_id=line.unit_id,
            central_quantity=line.central_quantity,
            central_reason=line.central_reason,
            sources=[
                PurchaseConsolidationSourceModel(
                    id=source.id,
                    company_id=consolidation.company_id,
                    consolidation_line_id=line.id,
                    purchase_request_id=source.purchase_request_id,
                    purchase_request_detail_id=source.purchase_request_detail_id,
                    requested_quantity=source.requested_quantity,
                    included_quantity=source.included_quantity,
                    reason=source.reason,
                    demand_level=source.demand_level.value if source.demand_level else None,
                )
                for source in line.sources
            ],
        )

    async def _to_entity(self, model: PurchaseConsolidationModel) -> PurchaseConsolidation:
        line_ids = [line.id for line in model.lines]
        labels: dict[uuid.UUID, tuple[str, str, str]] = {}
        request_ids = {
            source.purchase_request_id for line in model.lines for source in line.sources
        }
        request_metadata: dict[uuid.UUID, tuple[str | None, datetime | None]] = {}
        if request_ids:
            request_rows = await self._session.execute(
                select(
                    PurchaseRequestModel.id,
                    User.username,
                    PurchaseRequestModel.required_date,
                )
                .outerjoin(User, User.id == PurchaseRequestModel.requested_by_id)
                .where(
                    PurchaseRequestModel.company_id == model.company_id,
                    PurchaseRequestModel.id.in_(request_ids),
                )
            )
            request_metadata = {row.id: (row.username, row.required_date) for row in request_rows}
        if line_ids:
            result = await self._session.execute(
                select(
                    PurchaseConsolidationLineModel.id,
                    ProductModel.sku,
                    ProductModel.name,
                    func.coalesce(CompanyUnitModel.alias, UnitModel.name),
                )
                .join(
                    ProductModel,
                    and_(
                        ProductModel.id_product == PurchaseConsolidationLineModel.product_id,
                        ProductModel.company_id == PurchaseConsolidationLineModel.company_id,
                    ),
                )
                .join(
                    CompanyUnitModel,
                    and_(
                        CompanyUnitModel.company_id == PurchaseConsolidationLineModel.company_id,
                        CompanyUnitModel.unit_id == PurchaseConsolidationLineModel.unit_id,
                    ),
                )
                .join(UnitModel, UnitModel.id_unit == PurchaseConsolidationLineModel.unit_id)
                .where(
                    PurchaseConsolidationLineModel.company_id == model.company_id,
                    PurchaseConsolidationLineModel.id.in_(line_ids),
                )
            )
            labels = {row[0]: (row[1], row[2], row[3]) for row in result}
        lines = []
        for line in model.lines:
            sku, name, unit_name = labels.get(
                line.id,
                (f"PRD-{line.product_id}", f"Producto {line.product_id}", f"Unidad {line.unit_id}"),
            )
            sources_list = []
            for source in line.sources:
                requester_name, required_date = request_metadata.get(
                    source.purchase_request_id, (None, None)
                )
                sources_list.append(
                    ConsolidationSource(
                        id=source.id,
                        purchase_request_id=source.purchase_request_id,
                        purchase_request_detail_id=source.purchase_request_detail_id,
                        request_code=source.purchase_request.code
                        if source.purchase_request
                        else "",
                        branch_id=source.purchase_request.branch_id
                        if source.purchase_request
                        else uuid.UUID(int=0),
                        branch_name=source.purchase_request.branch.name
                        if source.purchase_request and source.purchase_request.branch
                        else None,
                        warehouse_id=source.purchase_request.warehouse_id
                        if source.purchase_request
                        else uuid.UUID(int=0),
                        warehouse_name=source.purchase_request.warehouse.name
                        if source.purchase_request and source.purchase_request.warehouse
                        else None,
                        requester_name=requester_name,
                        required_date=required_date,
                        requested_quantity=source.requested_quantity,
                        included_quantity=source.included_quantity,
                        reason=source.reason,
                        demand_level=BranchDemandLevel(source.demand_level)
                        if source.demand_level
                        else None,
                    )
                )
            sources = tuple(
                sorted(
                    sources_list,
                    key=lambda source: (
                        source.request_code,
                        str(source.purchase_request_detail_id),
                    ),
                )
            )
            lines.append(
                ConsolidationLine(
                    id=line.id,
                    product_id=line.product_id,
                    product_sku=sku,
                    product_name=name,
                    unit_id=line.unit_id,
                    unit_name=unit_name,
                    central_quantity=line.central_quantity,
                    central_reason=line.central_reason,
                    sources=sources,
                )
            )
        return PurchaseConsolidation(
            id=model.id,
            company_id=model.company_id,
            code=model.code,
            period_start=model.period_start,
            period_end=model.period_end,
            status=PurchaseConsolidationStatus(model.status),
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            central_warehouse_id=model.central_warehouse_id,
            central_warehouse_name=model.central_warehouse.name
            if model.central_warehouse
            else None,
            notes=model.notes,
            lines=tuple(lines),
            events=tuple(
                ConsolidationEvent(
                    id=event.id,
                    actor_id=event.actor_id,
                    action=event.action,
                    reason=event.reason,
                    changes=event.changes,
                    created_at=event.created_at,
                )
                for event in model.events
            ),
        )

"""SQL read adapter for the company's physical and valued Kardex."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import ColumnElement, Select

from app.domain.entities.inventory import ZERO
from app.domain.entities.inventory_kardex import LOCAL_TZ, snapshot_quantity
from app.domain.ports.inventory_kardex_read_repository import InventoryKardexReadRepository
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.inventory_valuation import (
    InventoryValuationEntryModel,
)
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_kardex_context import (
    InventoryKardexContextRepository,
)
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)


def _reference_matches(column: ColumnElement[str], value: str) -> ColumnElement[bool]:
    for code, prefix in (
        ("TR-", "inventory_transfer"),
        ("AJ-", "adjustment"),
        ("DEV-", "customer-return"),
    ):
        if value.startswith(code):
            return column.startswith(f"{prefix}:{value}:", autoescape=True) | (
                column == f"{prefix}:{value}"
            )
    return column == value


def _physical_projection(company_id: uuid.UUID, warehouse_id: uuid.UUID) -> Select[Any]:
    """Build one warehouse's movement projection used by all physical balances."""
    line = InventoryMovementLineModel
    movement = InventoryMovementModel
    quantity = line.quantity_base
    entered = and_(
        line.to_warehouse_id == warehouse_id,
        or_(line.from_warehouse_id.is_(None), line.from_warehouse_id != warehouse_id),
    )
    exited = and_(
        line.from_warehouse_id == warehouse_id,
        or_(line.to_warehouse_id.is_(None), line.to_warehouse_id != warehouse_id),
    )
    incoming = case((entered, quantity), else_=ZERO)
    outgoing = case((exited, quantity), else_=ZERO)
    net = incoming - outgoing
    from_location, to_location = aliased(Location), aliased(Location)
    from_warehouse, to_warehouse = aliased(Warehouse), aliased(Warehouse)
    return (
        select(
            line.id.label("id"),
            movement.id.label("movement_id"),
            movement.movement_type.label("movement_type"),
            movement.source_reference.label("source_reference"),
            movement.posted_at.label("posted_at"),
            movement.posted_by.label("posted_by"),
            User.username.label("operator"),
            line.line_number.label("line_number"),
            line.inventory_item_id.label("inventory_item_id"),
            func.coalesce(ProductVariantModel.name_override, ProductModel.name).label(
                "product_name"
            ),
            func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("product_sku"),
            UnitModel.symbol.label("base_unit_symbol"),
            line.lot_code.label("lot_code"),
            func.coalesce(
                line.inventory_lot_detail_id, InventoryHandlingUnitModel.inventory_lot_detail_id
            ).label("inventory_lot_detail_id"),
            InventoryLotDetailModel.code.label("receipt_lot_code"),
            InventoryLotModel.code.label("receipt_lot_header_code"),
            line.handling_unit_id.label("handling_unit_id"),
            InventoryHandlingUnitModel.code.label("handling_unit_code"),
            line.from_warehouse_id.label("from_warehouse_id"),
            from_warehouse.code.label("from_warehouse_code"),
            from_warehouse.name.label("from_warehouse_name"),
            line.from_location_id.label("from_location_id"),
            from_location.code.label("from_location_code"),
            line.from_stock_status.label("from_stock_status"),
            line.to_warehouse_id.label("to_warehouse_id"),
            to_warehouse.code.label("to_warehouse_code"),
            to_warehouse.name.label("to_warehouse_name"),
            line.to_location_id.label("to_location_id"),
            to_location.code.label("to_location_code"),
            line.to_stock_status.label("to_stock_status"),
            quantity.label("quantity_base"),
            incoming.label("incoming_quantity"),
            outgoing.label("outgoing_quantity"),
            net.label("net_quantity"),
        )
        .join(
            movement, and_(movement.company_id == line.company_id, movement.id == line.movement_id)
        )
        .join(
            InventoryItemModel,
            and_(
                InventoryItemModel.company_id == line.company_id,
                InventoryItemModel.id == line.inventory_item_id,
            ),
        )
        .outerjoin(
            ProductVariantModel,
            and_(
                ProductVariantModel.company_id == company_id,
                ProductVariantModel.id == InventoryItemModel.variant_id,
            ),
        )
        .outerjoin(
            ProductModel,
            and_(
                ProductModel.company_id == company_id,
                ProductModel.id_product
                == func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id),
            ),
        )
        .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
        .outerjoin(User, User.id == movement.posted_by)
        .outerjoin(
            InventoryHandlingUnitModel,
            and_(
                InventoryHandlingUnitModel.company_id == line.company_id,
                InventoryHandlingUnitModel.id == line.handling_unit_id,
            ),
        )
        .outerjoin(
            InventoryLotDetailModel,
            and_(
                InventoryLotDetailModel.company_id == line.company_id,
                InventoryLotDetailModel.id
                == func.coalesce(
                    line.inventory_lot_detail_id,
                    InventoryHandlingUnitModel.inventory_lot_detail_id,
                ),
            ),
        )
        .outerjoin(
            InventoryLotModel,
            and_(
                InventoryLotModel.company_id == InventoryLotDetailModel.company_id,
                InventoryLotModel.id == InventoryLotDetailModel.inventory_lot_id,
            ),
        )
        .outerjoin(from_location, from_location.id == line.from_location_id)
        .outerjoin(to_location, to_location.id == line.to_location_id)
        .outerjoin(
            from_warehouse,
            and_(
                from_warehouse.company_id == company_id, from_warehouse.id == line.from_warehouse_id
            ),
        )
        .outerjoin(
            to_warehouse,
            and_(to_warehouse.company_id == company_id, to_warehouse.id == line.to_warehouse_id),
        )
        .where(
            line.company_id == company_id,
            or_(line.from_warehouse_id == warehouse_id, line.to_warehouse_id == warehouse_id),
        )
    )


class SqlAlchemyInventoryKardexReadRepository(InventoryKardexReadRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def context(
        self,
        company_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        return await InventoryKardexContextRepository(self.session).context(
            company_id, item_id, warehouse_id
        )

    async def get_warehouse_scope(
        self, *, warehouse_id: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID | None] | None:
        row = (
            await self.session.execute(
                select(Warehouse.company_id, Warehouse.branch_id).where(
                    Warehouse.id == warehouse_id
                )
            )
        ).one_or_none()
        return (row[0], row[1]) if row is not None else None

    async def search_items(
        self, *, company_id: uuid.UUID, warehouse_id: uuid.UUID, query: str
    ) -> list[dict[str, Any]]:
        await SqlAlchemyInventoryValuationRepository(self.session).lock(company_id)
        search = query.strip()
        term = f"%{search}%"
        item = InventoryItemModel
        movement_line = InventoryMovementLineModel
        movement = InventoryMovementModel
        last_movement_at = (
            select(func.max(movement.posted_at))
            .select_from(movement_line)
            .join(
                movement,
                and_(
                    movement.id == movement_line.movement_id,
                    movement.company_id == company_id,
                ),
            )
            .where(
                movement_line.company_id == company_id,
                movement_line.inventory_item_id == item.id,
                or_(
                    movement_line.from_warehouse_id == warehouse_id,
                    movement_line.to_warehouse_id == warehouse_id,
                ),
            )
            .correlate(item)
            .scalar_subquery()
        )
        search_filters: list[ColumnElement[bool]] = [
            ProductModel.name.ilike(term),
            ProductModel.sku.ilike(term),
            ProductModel.internal_code.ilike(term),
            ProductModel.original_code.ilike(term),
            ProductVariantModel.sku.ilike(term),
            ProductVariantModel.name_override.ilike(term),
        ]
        try:
            requested_item_id = uuid.UUID(search)
        except ValueError:
            pass
        else:
            search_filters.append(item.id == requested_item_id)
        product_id = func.coalesce(item.product_id, ProductVariantModel.product_id)
        history_exists = (
            select(InventoryMovementLineModel.id)
            .where(
                InventoryMovementLineModel.company_id == company_id,
                InventoryMovementLineModel.inventory_item_id == item.id,
                or_(
                    InventoryMovementLineModel.from_warehouse_id == warehouse_id,
                    InventoryMovementLineModel.to_warehouse_id == warehouse_id,
                ),
            )
            .exists()
        )
        balance_exists = (
            select(InventoryBalanceModel.id)
            .where(
                InventoryBalanceModel.company_id == company_id,
                InventoryBalanceModel.inventory_item_id == item.id,
                InventoryBalanceModel.warehouse_id == warehouse_id,
                InventoryBalanceModel.quantity_base > 0,
            )
            .exists()
        )
        rows = (
            (
                await self.session.execute(
                    select(
                        item.id.label("inventory_item_id"),
                        func.coalesce(ProductVariantModel.name_override, ProductModel.name).label(
                            "product_name"
                        ),
                        func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("sku"),
                        UnitModel.symbol.label("base_unit_symbol"),
                        last_movement_at.label("last_movement_at"),
                    )
                    .outerjoin(
                        ProductVariantModel,
                        and_(
                            ProductVariantModel.company_id == company_id,
                            ProductVariantModel.id == item.variant_id,
                        ),
                    )
                    .outerjoin(
                        ProductModel,
                        and_(
                            ProductModel.company_id == company_id,
                            ProductModel.id_product == product_id,
                        ),
                    )
                    .join(UnitModel, UnitModel.id_unit == item.base_unit_id)
                    .where(
                        item.company_id == company_id,
                        or_(history_exists, balance_exists),
                        *([or_(*search_filters)] if search else []),
                    )
                    .order_by(
                        *([last_movement_at.desc().nulls_last()] if not search else []),
                        func.coalesce(ProductVariantModel.name_override, ProductModel.name),
                        item.id,
                    )
                    .limit(20)
                )
            )
            .mappings()
            .all()
        )
        return [
            {
                **row,
                "product_name": row["product_name"] or "Producto sin nombre",
                "base_unit_symbol": row["base_unit_symbol"] or "unidad base",
            }
            for row in rows
        ]

    async def _physical_kardex_period(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        start_at: datetime,
        end_exclusive: datetime,
        lot_code: str | None,
        movement_type: str | None,
        source_reference: str | None,
        page: int,
        page_size: int,
    ) -> tuple[Any, int, list[Any]]:
        predicates = [
            InventoryMovementLineModel.inventory_item_id == inventory_item_id,
            InventoryMovementModel.posted_at >= start_at,
            InventoryMovementModel.posted_at < end_exclusive,
        ]
        period = (
            _physical_projection(company_id, warehouse_id)
            .where(*predicates)
            .subquery("physical_kardex_period_source")
        )
        if lot_code:
            period = (
                select(period)
                .where(
                    or_(
                        period.c.lot_code == lot_code,
                        period.c.receipt_lot_code == lot_code,
                        period.c.receipt_lot_header_code == lot_code,
                    )
                )
                .subquery("physical_kardex_lot_filtered")
            )
        ordered = select(
            period,
            func.sum(period.c.net_quantity)
            .over(
                order_by=(period.c.posted_at, period.c.line_number, period.c.id),
                rows=(None, 0),
            )
            .label("running_net"),
        ).subquery("physical_kardex_period")
        count_query = select(func.count()).select_from(ordered)
        page_query = select(ordered)
        if movement_type:
            count_query = count_query.where(ordered.c.movement_type == movement_type)
            page_query = page_query.where(ordered.c.movement_type == movement_type)
        if source_reference:
            count_query = count_query.where(
                _reference_matches(ordered.c.source_reference, source_reference)
            )
            page_query = page_query.where(
                _reference_matches(ordered.c.source_reference, source_reference)
            )
        total = int(await self.session.scalar(count_query) or 0)
        raw_rows = (
            (
                await self.session.execute(
                    page_query.order_by(ordered.c.posted_at, ordered.c.line_number, ordered.c.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .mappings()
            .all()
        )
        return period, total, [dict(row) for row in raw_rows]

    async def _physical_kardex_balances(
        self,
        *,
        setting: Any,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        lot_code: str | None,
        start_at: datetime,
        end_exclusive: datetime,
    ) -> tuple[bool, Decimal | None, bool, Decimal | None]:
        opening_known = setting is not None and start_at >= setting.opened_at
        closing_known = setting is not None and end_exclusive >= setting.opened_at
        opening = closing = None
        if setting is None:
            return opening_known, opening, closing_known, closing

        baseline = snapshot_quantity(
            setting.physical_snapshot,
            warehouse_id=warehouse_id,
            inventory_item_id=inventory_item_id,
            lot_code=lot_code,
        )
        predicates = [
            InventoryMovementLineModel.inventory_item_id == inventory_item_id,
            InventoryMovementModel.posted_at >= setting.opened_at,
        ]
        if lot_code:
            receipt_code_exists = await self.session.scalar(
                select(InventoryLotDetailModel.id)
                .join(
                    InventoryLotModel,
                    and_(
                        InventoryLotModel.company_id == InventoryLotDetailModel.company_id,
                        InventoryLotModel.id == InventoryLotDetailModel.inventory_lot_id,
                    ),
                )
                .where(
                    InventoryLotDetailModel.company_id == company_id,
                    InventoryLotDetailModel.inventory_item_id == inventory_item_id,
                    or_(
                        InventoryLotDetailModel.code == lot_code,
                        InventoryLotModel.code == lot_code,
                    ),
                )
                .limit(1)
            )
            if receipt_code_exists is not None:
                return False, None, False, None
            predicates.append(InventoryMovementLineModel.lot_code == lot_code)

        async def quantity_since_cut(boundary: datetime) -> Decimal:
            movement_rows = (
                _physical_projection(company_id, warehouse_id)
                .where(
                    *predicates,
                    InventoryMovementModel.posted_at < boundary,
                )
                .subquery("physical_kardex_since_cut")
            )
            amount = await self.session.scalar(
                select(func.coalesce(func.sum(movement_rows.c.net_quantity), 0))
            )
            return Decimal(str(amount or 0))

        if opening_known:
            opening = baseline + await quantity_since_cut(start_at)
        if closing_known:
            closing = baseline + await quantity_since_cut(end_exclusive)
        return opening_known, opening, closing_known, closing

    async def _physical_kardex_authorized_warehouses(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        raw_rows: list[Any],
        access_all_branches: bool,
        accessible_branch_ids: set[uuid.UUID],
        accessible_warehouse_ids: set[uuid.UUID] | None = None,
    ) -> tuple[set[uuid.UUID], dict[uuid.UUID, uuid.UUID]]:
        handling_unit_ids = {row["handling_unit_id"] for row in raw_rows if row["handling_unit_id"]}
        unit_warehouse_by_id: dict[uuid.UUID, uuid.UUID] = {}
        if handling_unit_ids:
            scopes = (
                await self.session.execute(
                    select(
                        InventoryHandlingUnitModel.id,
                        InventoryHandlingUnitModel.warehouse_id,
                    ).where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id.in_(handling_unit_ids),
                    )
                )
            ).all()
            unit_warehouse_by_id = {row[0]: row[1] for row in scopes}

        endpoint_ids = {
            endpoint
            for row in raw_rows
            for endpoint in (row["from_warehouse_id"], row["to_warehouse_id"])
            if endpoint is not None and endpoint != warehouse_id
        }
        endpoint_ids.update(
            warehouse_id_value
            for warehouse_id_value in unit_warehouse_by_id.values()
            if warehouse_id_value != warehouse_id
        )
        authorized = {warehouse_id}
        if endpoint_ids:
            endpoint_scopes = (
                await self.session.execute(
                    select(Warehouse.id, Warehouse.branch_id).where(
                        Warehouse.company_id == company_id,
                        Warehouse.id.in_(endpoint_ids),
                    )
                )
            ).all()
            authorized.update(
                endpoint_warehouse_id
                for endpoint_warehouse_id, branch_id in endpoint_scopes
                if (access_all_branches or branch_id in accessible_branch_ids)
                and (
                    accessible_warehouse_ids is None
                    or endpoint_warehouse_id in accessible_warehouse_ids
                )
            )
        return authorized, unit_warehouse_by_id

    @staticmethod
    def _physical_kardex_items(
        *,
        raw_rows: list[Any],
        warehouse_id: uuid.UUID,
        opening: Decimal | None,
        authorized: set[uuid.UUID],
        unit_warehouse_by_id: dict[uuid.UUID, uuid.UUID],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        hidden_endpoint_fields = (
            "warehouse_id",
            "warehouse_code",
            "warehouse_name",
            "location_id",
            "location_code",
            "stock_status",
        )
        for raw in raw_rows:
            row = dict(raw)
            row["from_warehouse_external"] = row["from_warehouse_id"] is None
            row["to_warehouse_external"] = row["to_warehouse_id"] is None
            row["balance_after"] = (
                opening + Decimal(str(row["running_net"] or 0)) if opening is not None else None
            )
            for prefix in ("from", "to"):
                if row[f"{prefix}_warehouse_id"] not in authorized:
                    for field in hidden_endpoint_fields:
                        row[f"{prefix}_{field}"] = None
            if (
                row["handling_unit_id"] is not None
                and unit_warehouse_by_id.get(row["handling_unit_id"]) not in authorized
            ):
                row["handling_unit_id"] = None
                row["handling_unit_code"] = None
            row["is_internal"] = (
                row["from_warehouse_id"] == warehouse_id and row["to_warehouse_id"] == warehouse_id
            )
            items.append(row)
        return items

    async def _physical_kardex_totals(
        self, *, period: Any, movement_type: str | None, source_reference: str | None = None
    ) -> tuple[Decimal, Decimal]:
        totals_query = select(
            func.coalesce(func.sum(period.c.incoming_quantity), 0).label("incoming_quantity"),
            func.coalesce(func.sum(period.c.outgoing_quantity), 0).label("outgoing_quantity"),
        ).select_from(period)
        if movement_type:
            totals_query = totals_query.where(period.c.movement_type == movement_type)
        if source_reference:
            totals_query = totals_query.where(
                _reference_matches(period.c.source_reference, source_reference)
            )
        totals = (await self.session.execute(totals_query)).one()
        return (
            Decimal(str(totals.incoming_quantity or 0)),
            Decimal(str(totals.outgoing_quantity or 0)),
        )

    async def physical_kardex(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        period_from: date,
        period_to: date,
        movement_type: str | None,
        lot_code: str | None,
        source_reference: str | None = None,
        page: int,
        page_size: int,
        access_all_branches: bool,
        accessible_branch_ids: set[uuid.UUID],
        accessible_warehouse_ids: set[uuid.UUID] | None = None,
    ) -> dict[str, Any] | None:
        item_exists = await self.session.scalar(
            select(InventoryItemModel.id).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == inventory_item_id,
            )
        )
        if item_exists is None:
            return None
        if source_reference:
            source_reference = await InventoryKardexContextRepository(
                self.session
            ).source_reference(company_id, source_reference)
        valuation = SqlAlchemyInventoryValuationRepository(self.session)
        await valuation.lock(company_id)
        setting = await valuation.settings(company_id)
        start_at = datetime.combine(period_from, time.min, tzinfo=LOCAL_TZ)
        end_exclusive = datetime.combine(period_to + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
        period, total, raw_rows = await self._physical_kardex_period(
            company_id=company_id,
            warehouse_id=warehouse_id,
            inventory_item_id=inventory_item_id,
            start_at=start_at,
            end_exclusive=end_exclusive,
            lot_code=lot_code,
            movement_type=movement_type,
            source_reference=source_reference,
            page=page,
            page_size=page_size,
        )
        opening_known, opening, closing_known, closing = await self._physical_kardex_balances(
            setting=setting,
            company_id=company_id,
            warehouse_id=warehouse_id,
            inventory_item_id=inventory_item_id,
            lot_code=lot_code,
            start_at=start_at,
            end_exclusive=end_exclusive,
        )
        authorized, unit_warehouse_by_id = await self._physical_kardex_authorized_warehouses(
            company_id=company_id,
            warehouse_id=warehouse_id,
            raw_rows=raw_rows,
            access_all_branches=access_all_branches,
            accessible_branch_ids=accessible_branch_ids,
            accessible_warehouse_ids=accessible_warehouse_ids,
        )
        items = self._physical_kardex_items(
            raw_rows=raw_rows,
            warehouse_id=warehouse_id,
            opening=opening,
            authorized=authorized,
            unit_warehouse_by_id=unit_warehouse_by_id,
        )
        incoming_quantity, outgoing_quantity = await self._physical_kardex_totals(
            period=period, movement_type=movement_type, source_reference=source_reference
        )
        await InventoryKardexContextRepository(self.session).enrich(company_id, items)
        return {
            "opening_known": opening_known,
            "opening_quantity": opening,
            "closing_known": closing_known,
            "closing_quantity": closing,
            "incoming_quantity": incoming_quantity,
            "outgoing_quantity": outgoing_quantity,
            "items": items,
            "total": total,
            "cut_opened_at": setting.opened_at if setting is not None else None,
            "has_cut": setting is not None,
        }

    async def reconciliation(
        self,
        *,
        company_id: uuid.UUID,
        page: int,
        page_size: int,
        as_of: date | None = None,
        query: str = "",
        difference_only: bool = False,
    ) -> dict[str, Any]:
        from app.infrastructure.repositories.inventory_reconciliation import reconciliation

        return await reconciliation(
            self.session,
            company_id=company_id,
            page=page,
            page_size=page_size,
            as_of=as_of,
            query=query,
            difference_only=difference_only,
        )

    async def valued_kardex(
        self,
        *,
        company_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        period_from: date,
        period_to: date,
        page: int,
        page_size: int,
    ) -> dict[str, Any] | None:
        exists = await self.session.scalar(
            select(InventoryItemModel.id).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == inventory_item_id,
            )
        )
        if exists is None:
            return None
        valuation = SqlAlchemyInventoryValuationRepository(self.session)
        await valuation.lock(company_id)
        setting = await valuation.settings(company_id)
        if setting is None:
            return {
                "setting": None,
                "opening_known": False,
                "opening_quantity": None,
                "opening_value": None,
                "closing_known": False,
                "closing_quantity": None,
                "closing_value": None,
                "period_value_change": None,
                "entries": [],
                "page": page,
                "page_size": page_size,
                "total": 0,
            }
        entries_model = InventoryValuationEntryModel
        scope = [
            entries_model.company_id == company_id,
            entries_model.inventory_item_id == inventory_item_id,
        ]
        period_filter = [
            *scope,
            entries_model.accounting_date >= period_from,
            entries_model.accounting_date <= period_to,
        ]
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(entries_model).where(*period_filter)
            )
            or 0
        )
        opening_row = await self.session.scalar(
            select(entries_model)
            .where(*scope, entries_model.accounting_date < period_from)
            .order_by(entries_model.sequence.desc())
            .limit(1)
        )
        closing_row = await self.session.scalar(
            select(entries_model)
            .where(*scope, entries_model.accounting_date <= period_to)
            .order_by(entries_model.sequence.desc())
            .limit(1)
        )
        opening_known = setting.opened_at.astimezone(LOCAL_TZ).date() < period_from
        closing_known = setting.opened_at.astimezone(LOCAL_TZ).date() <= period_to
        change = await self.session.scalar(
            select(func.coalesce(func.sum(entries_model.inventory_delta), 0)).where(*period_filter)
        )
        entry_rows = list(
            (
                await self.session.scalars(
                    select(entries_model)
                    .where(*period_filter)
                    .order_by(entries_model.sequence)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        entry_fields = (
            "id",
            "inventory_item_id",
            "sequence",
            "kind",
            "quantity_base",
            "source_value",
            "original_entry_id",
            "movement_line_id",
            "purchase_detail_id",
            "retaceo_id",
            "source_reference",
            "operational_date",
            "accounting_date",
            "posted_at",
            "posted_by",
            "inventory_delta",
            "balance_quantity",
            "balance_value",
            "average_unit_cost",
            "cost_breakdown",
        )
        entry_payloads = [
            {field: getattr(row, field) for field in entry_fields} for row in entry_rows
        ]
        await InventoryKardexContextRepository(self.session).enrich(company_id, entry_payloads)
        return {
            "setting": {
                "company_id": setting.company_id,
                "currency": setting.currency,
                "opened_at": setting.opened_at,
                "opened_by": setting.opened_by,
                "opening_reference": setting.opening_reference,
            },
            "opening_known": opening_known,
            "opening_quantity": (opening_row.balance_quantity if opening_row else ZERO)
            if opening_known
            else None,
            "opening_value": (opening_row.balance_value if opening_row else ZERO)
            if opening_known
            else None,
            "closing_known": closing_known,
            "closing_quantity": (closing_row.balance_quantity if closing_row else ZERO)
            if closing_known
            else None,
            "closing_value": (closing_row.balance_value if closing_row else ZERO)
            if closing_known
            else None,
            "period_value_change": Decimal(str(change or 0)),
            "entries": entry_payloads,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

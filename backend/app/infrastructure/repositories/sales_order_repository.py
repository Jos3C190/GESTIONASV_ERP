"""Pedidos de venta en PostgreSQL (bloque V2e).

El pedido vive en las tablas ``sales`` y ``sales_lines`` (la venta B06 rehecha en su lugar).
La reserva comercial no tiene tabla propia: se calcula con lo pendiente de entregar de los
pedidos confirmados de la sucursal.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_fiscal_document import INVOICEABLE_DOCUMENTS
from app.domain.entities.sales_order import DeliveryMode, OrderStatus, PaymentTerms
from app.domain.ports.sales_document import DocumentTotals
from app.domain.ports.sales_order_repository import (
    DeliveryAddress,
    Order,
    OrderFilters,
    OrderLine,
)
from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.models.sales import (
    SaleLineModel,
    SaleModel,
    SalesCustomerDeliveryAddressModel,
)
from app.infrastructure.models.sales_delivery import SalesDeliveryLineModel, SalesDeliveryModel
from app.infrastructure.models.sales_fiscal import SalesFiscalDocumentModel
from app.infrastructure.repositories.sales_quotation_repository import (
    TOTAL_FIELDS,
    SalesDocumentSupport,
    document_line,
    line_columns,
)

ZERO = Decimal("0")
_HEADER_FIELDS = (
    "branch_id",
    "customer_id",
    "quotation_id",
    "code",
    "document_type",
    "price_list_id",
    "prices_include_vat",
    "global_discount_percent",
    "version",
    "notes",
    "requires_authorization",
    "promised_date",
    "delivery_address_id",
    "delivery_address_text",
    "credit_days",
    "created_by_id",
    "confirmed_by_id",
    "confirmed_at",
    "authorized_by_id",
    "authorized_at",
    "authorization_note",
    "cancelled_by_id",
    "cancelled_at",
    "cancellation_reason",
)


def _order(
    row: SaleModel, lines: list[SaleLineModel], delivered: dict[uuid.UUID, Decimal]
) -> Order:
    header: dict[str, Any] = {name: getattr(row, name) for name in _HEADER_FIELDS}
    return Order(
        id=row.id,
        company_id=row.company_id,
        status=OrderStatus(row.status),
        delivery_mode=DeliveryMode(row.delivery_mode),
        payment_terms=PaymentTerms(row.payment_terms),
        totals=DocumentTotals(**{name: getattr(row, name) for name in TOTAL_FIELDS}),
        authorization_reasons=tuple(row.authorization_reasons or ()),
        lines=[
            OrderLine(
                line=document_line(line),
                source_quotation_line_id=line.source_quotation_line_id,
                delivered_base=delivered.get(line.id, ZERO),
            )
            for line in lines
        ],
        created_at=row.created_at,
        updated_at=row.updated_at,
        **header,
    )


def _apply_header(row: SaleModel, order: Order) -> None:
    for name in _HEADER_FIELDS:
        setattr(row, name, getattr(order, name))
    for name in TOTAL_FIELDS:
        setattr(row, name, getattr(order.totals, name))
    row.status = order.status.value
    row.delivery_mode = order.delivery_mode.value
    row.payment_terms = order.payment_terms.value
    row.authorization_reasons = list(order.authorization_reasons)


def _line_row(order: Order, number: int, item: OrderLine) -> SaleLineModel:
    return SaleLineModel(
        company_id=order.company_id,
        sale_id=order.id,
        line_number=number,
        source_quotation_line_id=item.source_quotation_line_id,
        authorization_reasons=list(item.line.authorization_reasons),
        **line_columns(item.line),
    )


def _confirmed_delivered() -> Select[Any]:
    """Unidad base entregada por línea de pedido, solo en entregas confirmadas."""

    return (
        select(
            SalesDeliveryLineModel.sale_line_id.label("line_id"),
            func.sum(SalesDeliveryLineModel.quantity_base).label("delivered"),
        )
        .join(
            SalesDeliveryModel,
            (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
            & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
        )
        .where(SalesDeliveryModel.status == "confirmed")
        .group_by(SalesDeliveryLineModel.sale_line_id)
    )


class SqlAlchemySalesOrderRepository(SalesDocumentSupport):
    RESOURCE_TYPE = "sale"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def _children(
        self, company_id: uuid.UUID, order_ids: list[uuid.UUID]
    ) -> tuple[dict[uuid.UUID, list[SaleLineModel]], dict[uuid.UUID, Decimal]]:
        grouped: dict[uuid.UUID, list[SaleLineModel]] = {i: [] for i in order_ids}
        if not order_ids:
            return grouped, {}
        rows = await self._session.scalars(
            select(SaleLineModel)
            .where(SaleLineModel.company_id == company_id, SaleLineModel.sale_id.in_(order_ids))
            .order_by(SaleLineModel.line_number)
        )
        lines = list(rows.all())
        for line in lines:
            grouped[line.sale_id].append(line)
        delivered_query = _confirmed_delivered().subquery()
        delivered_rows = await self._session.execute(
            select(delivered_query.c.line_id, delivered_query.c.delivered).where(
                delivered_query.c.line_id.in_([line.id for line in lines])
            )
        )
        delivered = {row[0]: Decimal(row[1] or ZERO) for row in delivered_rows.all()}
        return grouped, delivered

    async def _row(
        self, company_id: uuid.UUID, order_id: uuid.UUID, *, lock: bool
    ) -> SaleModel | None:
        statement = select(SaleModel).where(
            SaleModel.company_id == company_id, SaleModel.id == order_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row: SaleModel | None = await self._session.scalar(statement)
        return row

    async def get(
        self, company_id: uuid.UUID, order_id: uuid.UUID, *, lock: bool = False
    ) -> Order | None:
        row = await self._row(company_id, order_id, lock=lock)
        if row is None:
            return None
        lines, delivered = await self._children(company_id, [row.id])
        return _order(row, lines[row.id], delivered)

    async def for_quotation(self, company_id: uuid.UUID, quotation_id: uuid.UUID) -> Order | None:
        order_id = await self._session.scalar(
            select(SaleModel.id).where(
                SaleModel.company_id == company_id, SaleModel.quotation_id == quotation_id
            )
        )
        return await self.get(company_id, order_id) if order_id else None

    async def page(
        self, company_id: uuid.UUID, filters: OrderFilters, page: int, size: int
    ) -> tuple[list[Order], int]:
        conditions: list[Any] = [SaleModel.company_id == company_id]
        if filters.branch_id:
            conditions.append(SaleModel.branch_id == filters.branch_id)
        elif filters.branch_ids is not None:
            conditions.append(
                SaleModel.branch_id.in_(filters.branch_ids)
                if filters.branch_ids
                else SaleModel.id.is_(None)
            )
        if filters.customer_id:
            conditions.append(SaleModel.customer_id == filters.customer_id)
        if filters.status:
            conditions.append(SaleModel.status == filters.status)
        if filters.from_date:
            conditions.append(SaleModel.promised_date >= filters.from_date)
        if filters.to_date:
            conditions.append(SaleModel.promised_date <= filters.to_date)
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(SaleModel).where(*conditions)
            )
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(SaleModel)
                    .where(*conditions)
                    .order_by(SaleModel.promised_date.desc(), SaleModel.created_at.desc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).all()
        )
        lines, delivered = await self._children(company_id, [row.id for row in rows])
        return [_order(row, lines[row.id], delivered) for row in rows], total

    async def add(self, order: Order) -> None:
        row = SaleModel(id=order.id, company_id=order.company_id, currency="USD")
        _apply_header(row, order)
        self._session.add(row)
        await self._session.flush()
        self._session.add_all(
            _line_row(order, number, item) for number, item in enumerate(order.lines, start=1)
        )
        await self._session.flush()
        await self._session.refresh(row)
        order.created_at, order.updated_at = row.created_at, row.updated_at

    async def save(self, order: Order, *, replace_lines: bool) -> None:
        row = await self._row(order.company_id, order.id, lock=False)
        if row is None:
            raise LookupError(order.id)
        if replace_lines:
            # Las líneas solo cambian en borrador (lo exige un trigger): se reemplazan antes de
            # cambiar el estado de la cabecera.
            await self._session.execute(
                delete(SaleLineModel).where(
                    SaleLineModel.company_id == order.company_id,
                    SaleLineModel.sale_id == order.id,
                )
            )
            await self._session.flush()
            self._session.add_all(
                _line_row(order, number, item) for number, item in enumerate(order.lines, start=1)
            )
            await self._session.flush()
        _apply_header(row, order)
        await self._session.flush()
        await self._session.refresh(row)
        order.updated_at = row.updated_at

    async def invoiced(self, company_id: uuid.UUID, order_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(SalesFiscalDocumentModel.id).where(
                SalesFiscalDocumentModel.company_id == company_id,
                SalesFiscalDocumentModel.sale_id == order_id,
                # Cuenta la factura o el CCF, no sus notas (V4c).
                SalesFiscalDocumentModel.document_type.in_(INVOICEABLE_DOCUMENTS),
                # Un rechazado o un invalidado no cuenta (V4b).
                SalesFiscalDocumentModel.status.in_(
                    ("pending", "contingency", "issued", "simulated")
                ),
            )
        )
        return found is not None

    async def delivery_address(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, address_id: uuid.UUID
    ) -> DeliveryAddress | None:
        row = await self._session.scalar(
            select(SalesCustomerDeliveryAddressModel).where(
                SalesCustomerDeliveryAddressModel.company_id == company_id,
                SalesCustomerDeliveryAddressModel.customer_id == customer_id,
                SalesCustomerDeliveryAddressModel.id == address_id,
                SalesCustomerDeliveryAddressModel.is_active.is_(True),
            )
        )
        if row is None:
            return None
        text = f"{row.label}: {row.address_line}"
        if row.contact_name or row.phone:
            text += " · " + " ".join(part for part in (row.contact_name, row.phone) if part)
        return DeliveryAddress(id=row.id, text=text[:400])

    async def lock_reservations(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, items: set[uuid.UUID]
    ) -> None:
        # Orden estable para que dos confirmaciones no se bloqueen entre sí.
        for item in sorted(items, key=str):
            await self._session.scalar(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtext(f"sales-reservation:{company_id}:{branch_id}:{item}")
                    )
                )
            )

    async def on_hand(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, items: set[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]:
        if not items:
            return {}
        unit = InventoryHandlingUnitModel
        today = datetime.now(ZoneInfo("America/El_Salvador")).date()
        rows = await self._session.execute(
            select(unit.inventory_item_id, func.sum(unit.quantity_base))
            .join(
                Warehouse,
                (Warehouse.id == unit.warehouse_id) & (Warehouse.company_id == unit.company_id),
            )
            .join(
                Location,
                (Location.id == unit.location_id) & (Location.warehouse_id == unit.warehouse_id),
            )
            .where(
                unit.company_id == company_id,
                unit.inventory_item_id.in_(items),
                unit.closed_at.is_(None),
                unit.stock_status == "available",
                (unit.expiry_date.is_(None) | (unit.expiry_date >= today)),
                Warehouse.branch_id == branch_id,
                Warehouse.is_active.is_(True),
                Warehouse.is_transit.is_(False),
                Warehouse.operational_status == "active",
                Warehouse.deleted_at.is_(None),
                Location.is_active.is_(True),
                Location.lifecycle_status == "active",
                Location.storage_eligible.is_(True),
                Location.deleted_at.is_(None),
                Location.location_type != "virtual",
            )
            .group_by(unit.inventory_item_id)
        )
        return {row[0]: Decimal(row[1] or ZERO) for row in rows.all()}

    async def reserved(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        items: set[uuid.UUID],
        exclude_order: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        if not items:
            return {}
        delivered = _confirmed_delivered().subquery()
        pending = func.greatest(
            SaleLineModel.quantity_base - func.coalesce(delivered.c.delivered, 0), 0
        )
        conditions: list[Any] = [
            SaleModel.company_id == company_id,
            SaleModel.branch_id == branch_id,
            SaleModel.status == OrderStatus.CONFIRMED.value,
            SaleLineModel.inventory_item_id.in_(items),
        ]
        if exclude_order is not None:
            conditions.append(SaleModel.id != exclude_order)
        rows = await self._session.execute(
            select(SaleLineModel.inventory_item_id, func.sum(pending))
            .join(
                SaleModel,
                (SaleModel.company_id == SaleLineModel.company_id)
                & (SaleModel.id == SaleLineModel.sale_id),
            )
            .outerjoin(delivered, delivered.c.line_id == SaleLineModel.id)
            .where(*conditions)
            .group_by(SaleLineModel.inventory_item_id)
        )
        return {row[0]: Decimal(row[1] or ZERO) for row in rows.all()}

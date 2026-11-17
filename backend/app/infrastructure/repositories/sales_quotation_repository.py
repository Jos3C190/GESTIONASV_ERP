"""Cotizaciones de venta en PostgreSQL (bloque V2d)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_quotation import DEFAULT_VALIDITY_DAYS, QuotationStatus
from app.domain.ports.sales_quotation_repository import (
    LineIdentity,
    LinkedSale,
    PeopleNames,
    Quotation,
    QuotationFilters,
    QuotationLine,
    QuotationTotals,
)
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.sales import (
    SaleModel,
    SalesIdempotencyModel,
    SalesQuotationLineModel,
    SalesQuotationModel,
)
from app.infrastructure.models.sales_pricing import SalesSettingsModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.sales_line_identity import line_identity

_HEADER_FIELDS = (
    "branch_id",
    "customer_id",
    "code",
    "quotation_date",
    "valid_until",
    "document_type",
    "price_list_id",
    "prices_include_vat",
    "global_discount_percent",
    "version",
    "notes",
    "requires_authorization",
    "created_by_id",
    "issued_by_id",
    "issued_at",
    "authorized_by_id",
    "authorized_at",
    "authorization_note",
    "customer_response_by_id",
    "customer_response_at",
    "rejection_reason",
    "cancelled_by_id",
    "cancelled_at",
    "cancellation_reason",
)
_TOTAL_FIELDS = (
    "total_not_subject",
    "total_exempt",
    "total_taxed",
    "subtotal_sales",
    "total_discount",
    "subtotal",
    "vat",
    "vat_perceived",
    "vat_withheld",
    "total",
    "total_in_words",
)
_LINE_FIELDS = (
    "quantity",
    "quantity_base",
    "price_list_id",
    "list_price",
    "price_overridden",
    "unit_price",
    "discount_percent",
    "suggested_discount_percent",
    "suggested_discount_source",
    "tax_treatment",
    "item_type",
    "document_unit_price",
    "discount_amount",
    "not_subject",
    "exempt",
    "taxed",
    "vat_item",
    "line_total",
    "cost",
    "margin_percent",
)
_IDENTITY_FIELDS = (
    "product_id",
    "variant_id",
    "inventory_item_id",
    "packaging_definition_id",
    "packaging_version",
    "unit_id",
    "base_unit_id",
    "unit_factor",
    "product_sku",
    "product_name",
    "unit_name",
    "base_unit_name",
)


def _line(row: SalesQuotationLineModel) -> QuotationLine:
    identity = LineIdentity(**{name: getattr(row, name) for name in _IDENTITY_FIELDS})
    values: dict[str, Any] = {name: getattr(row, name) for name in _LINE_FIELDS}
    return QuotationLine(
        identity=identity,
        authorization_reasons=tuple(row.authorization_reasons or ()),
        id=row.id,
        **values,
    )


def _quotation(row: SalesQuotationModel, lines: list[SalesQuotationLineModel]) -> Quotation:
    header: dict[str, Any] = {name: getattr(row, name) for name in _HEADER_FIELDS}
    totals = QuotationTotals(**{name: getattr(row, name) for name in _TOTAL_FIELDS})
    return Quotation(
        id=row.id,
        company_id=row.company_id,
        status=QuotationStatus(row.status),
        totals=totals,
        authorization_reasons=tuple(row.authorization_reasons or ()),
        lines=[_line(line) for line in lines],
        created_at=row.created_at,
        updated_at=row.updated_at,
        **header,
    )


def _line_row(quotation: Quotation, number: int, line: QuotationLine) -> SalesQuotationLineModel:
    return SalesQuotationLineModel(
        company_id=quotation.company_id,
        quotation_id=quotation.id,
        line_number=number,
        authorization_reasons=list(line.authorization_reasons),
        **{name: getattr(line.identity, name) for name in _IDENTITY_FIELDS},
        **{name: getattr(line, name) for name in _LINE_FIELDS},
    )


def _apply_header(row: SalesQuotationModel, quotation: Quotation) -> None:
    for name in _HEADER_FIELDS:
        setattr(row, name, getattr(quotation, name))
    for name in _TOTAL_FIELDS:
        setattr(row, name, getattr(quotation.totals, name))
    row.status = quotation.status.value
    row.authorization_reasons = list(quotation.authorization_reasons)


class SqlAlchemySalesQuotationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def line_identity(
        self, company_id: uuid.UUID, product_id: int, variant_id: uuid.UUID | None, unit_id: int
    ) -> LineIdentity:
        return await line_identity(self._session, company_id, product_id, variant_id, unit_id)

    async def branch_is_active(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(Branch.id).where(
                Branch.company_id == company_id,
                Branch.id == branch_id,
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
            )
        )
        return found is not None

    async def _lines(
        self, company_id: uuid.UUID, quotation_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[SalesQuotationLineModel]]:
        grouped: dict[uuid.UUID, list[SalesQuotationLineModel]] = {i: [] for i in quotation_ids}
        if not quotation_ids:
            return grouped
        rows = await self._session.scalars(
            select(SalesQuotationLineModel)
            .where(
                SalesQuotationLineModel.company_id == company_id,
                SalesQuotationLineModel.quotation_id.in_(quotation_ids),
            )
            .order_by(SalesQuotationLineModel.line_number)
        )
        for row in rows.all():
            grouped[row.quotation_id].append(row)
        return grouped

    async def _row(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID, *, lock: bool
    ) -> SalesQuotationModel | None:
        statement = select(SalesQuotationModel).where(
            SalesQuotationModel.company_id == company_id, SalesQuotationModel.id == quotation_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row: SalesQuotationModel | None = await self._session.scalar(statement)
        return row

    async def get(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID, *, lock: bool = False
    ) -> Quotation | None:
        row = await self._row(company_id, quotation_id, lock=lock)
        if row is None:
            return None
        lines = await self._lines(company_id, [row.id])
        return _quotation(row, lines[row.id])

    async def page(
        self, company_id: uuid.UUID, filters: QuotationFilters, page: int, size: int
    ) -> tuple[list[Quotation], int]:
        model = SalesQuotationModel
        conditions: list[Any] = [model.company_id == company_id]
        if filters.branch_id:
            conditions.append(model.branch_id == filters.branch_id)
        elif filters.branch_ids is not None:
            conditions.append(
                model.branch_id.in_(filters.branch_ids)
                if filters.branch_ids
                else model.id.is_(None)
            )
        if filters.customer_id:
            conditions.append(model.customer_id == filters.customer_id)
        if filters.from_date:
            conditions.append(model.quotation_date >= filters.from_date)
        if filters.to_date:
            conditions.append(model.quotation_date <= filters.to_date)
        issued = QuotationStatus.ISSUED.value
        if filters.status == "expired" and filters.today:
            conditions += [model.status == issued, model.valid_until < filters.today]
        elif filters.status == issued and filters.today:
            conditions += [model.status == issued, model.valid_until >= filters.today]
        elif filters.status:
            conditions.append(model.status == filters.status)
        total = int(
            await self._session.scalar(select(func.count()).select_from(model).where(*conditions))
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(model)
                    .where(*conditions)
                    .order_by(model.quotation_date.desc(), model.created_at.desc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).all()
        )
        lines = await self._lines(company_id, [row.id for row in rows])
        return [_quotation(row, lines[row.id]) for row in rows], total

    async def add(self, quotation: Quotation) -> None:
        row = SalesQuotationModel(id=quotation.id, company_id=quotation.company_id, currency="USD")
        _apply_header(row, quotation)
        self._session.add(row)
        await self._session.flush()
        self._session.add_all(
            _line_row(quotation, number, line)
            for number, line in enumerate(quotation.lines, start=1)
        )
        await self._session.flush()
        await self._session.refresh(row)
        quotation.created_at, quotation.updated_at = row.created_at, row.updated_at

    async def save(self, quotation: Quotation, *, replace_lines: bool) -> None:
        row = await self._row(quotation.company_id, quotation.id, lock=False)
        if row is None:
            raise LookupError(quotation.id)
        _apply_header(row, quotation)
        if replace_lines:
            await self._session.execute(
                delete(SalesQuotationLineModel).where(
                    SalesQuotationLineModel.company_id == quotation.company_id,
                    SalesQuotationLineModel.quotation_id == quotation.id,
                )
            )
            await self._session.flush()
            self._session.add_all(
                _line_row(quotation, number, line)
                for number, line in enumerate(quotation.lines, start=1)
            )
        await self._session.flush()
        await self._session.refresh(row)
        quotation.updated_at = row.updated_at

    async def linked_sale(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> LinkedSale | None:
        found = (
            await self._session.execute(
                select(SaleModel.id, SaleModel.code).where(
                    SaleModel.company_id == company_id, SaleModel.quotation_id == quotation_id
                )
            )
        ).first()
        return LinkedSale(id=found[0], code=found[1]) if found else None

    async def user_names(self, user_ids: set[uuid.UUID]) -> PeopleNames:
        if not user_ids:
            return PeopleNames({})
        rows = await self._session.execute(
            select(User.id, User.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, (Employee.user_id == User.id) & Employee.deleted_at.is_(None))
            .where(User.id.in_(user_ids))
        )
        names: dict[uuid.UUID, str] = {}
        for user_id, username, first, last in rows.tuples().all():
            full = f"{first or ''} {last or ''}".strip()
            names.setdefault(user_id, full or username)
        return PeopleNames(names)

    async def validity_days(self, company_id: uuid.UUID) -> int:
        days = await self._session.scalar(
            select(SalesSettingsModel.quotation_validity_days).where(
                SalesSettingsModel.company_id == company_id
            )
        )
        return days if days is not None else DEFAULT_VALIDITY_DAYS

    async def save_validity_days(
        self, company_id: uuid.UUID, days: int, actor_id: uuid.UUID
    ) -> None:
        row = await self._session.get(SalesSettingsModel, company_id)
        if row is None:
            row = SalesSettingsModel(company_id=company_id)
            self._session.add(row)
        row.quotation_validity_days = days
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def lock_key(self, company_id: uuid.UUID, action: str, key: str) -> None:
        await self._session.scalar(
            select(func.pg_advisory_xact_lock(func.hashtext(f"{company_id}:{action}:{key}")))
        )

    async def remembered(
        self, company_id: uuid.UUID, action: str, key: str
    ) -> tuple[str, uuid.UUID] | None:
        row = await self._session.scalar(
            select(SalesIdempotencyModel).where(
                SalesIdempotencyModel.company_id == company_id,
                SalesIdempotencyModel.action == action,
                SalesIdempotencyModel.idempotency_key == key,
            )
        )
        return (row.fingerprint, row.resource_id) if row else None

    async def remember(
        self,
        company_id: uuid.UUID,
        action: str,
        key: str,
        fingerprint: str,
        resource_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        self._session.add(
            SalesIdempotencyModel(
                company_id=company_id,
                action=action,
                idempotency_key=key,
                fingerprint=fingerprint,
                resource_type="quotation",
                resource_id=resource_id,
                actor_id=actor_id,
            )
        )
        await self._session.flush()

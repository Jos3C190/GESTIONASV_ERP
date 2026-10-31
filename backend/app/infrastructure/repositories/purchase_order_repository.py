"""SQLAlchemy implementation of the purchase-order repository port."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import cast as type_cast

from sqlalchemy import Integer, Select, and_, exists, func, or_, select, union_all
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import ColumnElement, Subquery

from app.domain.entities.actual_expense import ActualExpenseClosure, ActualPurchaseExpense
from app.domain.entities.purchase_order import (
    PurchaseOrder,
    PurchaseOrderDetail,
    PurchaseOrderExpense,
    PurchaseOrderStatus,
)
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.entities.purchase_request import PurchaseRequestStatus
from app.domain.ports.purchase_order_repository import (
    PurchaseOrderAwardReference,
    PurchaseOrderDestinationReference,
    PurchaseOrderExpenseTypeReference,
    PurchaseOrderQuotationDetailReference,
    PurchaseOrderQuotationReference,
)
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.purchase_consolidation import (
    PurchaseConsolidationAwardModel,
    PurchaseConsolidationModel,
)
from app.infrastructure.models.purchase_order import (
    PurchaseOrderDetailModel,
    PurchaseOrderExpenseModel,
    PurchaseOrderModel,
)
from app.infrastructure.models.purchase_quotation import (
    ExpenseTypeModel,
    PurchaseQuotationDetailModel,
    PurchaseQuotationExpenseModel,
    PurchaseQuotationModel,
    PurchaseQuotationRequestDetailModel,
    PurchaseQuotationRequestModel,
)
from app.infrastructure.models.purchase_request import PurchaseRequestModel
from app.infrastructure.models.retaceo import RetaceoCostModel, RetaceoModel

COMMITTED_ORDER_STATUS_VALUES = (
    PurchaseOrderStatus.SENT.value,
    PurchaseOrderStatus.PARTIALLY_RECEIVED.value,
    PurchaseOrderStatus.RECEIVED.value,
    PurchaseOrderStatus.CLOSED.value,
)


def _to_detail(model: PurchaseOrderDetailModel) -> PurchaseOrderDetail:
    return PurchaseOrderDetail(
        id=model.id,
        purchase_order_id=model.purchase_order_id,
        purchase_quotation_detail_id=model.purchase_quotation_detail_id,
        product_id=model.product_id,
        quantity=model.quantity,
        unit_id=model.unit_id,
        unit_price=model.unit_price,
        discount=model.discount,
        subtotal=model.subtotal,
        tax_rate=model.tax_rate,
        tax_amount=model.tax_amount,
        total=model.total,
        notes=model.notes,
        purchase_consolidation_award_id=model.purchase_consolidation_award_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_expense(model: PurchaseOrderExpenseModel) -> PurchaseOrderExpense:
    return PurchaseOrderExpense(
        id=model.id,
        purchase_order_id=model.purchase_order_id,
        expense_type_id=model.expense_type_id,
        amount=model.amount,
        description=model.description,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_entity(model: PurchaseOrderModel) -> PurchaseOrder:
    return PurchaseOrder(
        id=model.id,
        company_id=model.company_id,
        code=model.code,
        supplier_id=model.supplier_id,
        branch_id=model.branch_id,
        warehouse_id=model.warehouse_id,
        purchase_quotation_id=model.purchase_quotation_id,
        created_by_id=model.created_by_id,
        order_date=model.order_date,
        expected_date=model.expected_date,
        currency=model.currency,
        payment_terms=model.payment_terms,
        details=tuple(_to_detail(detail) for detail in model.details),
        expenses=tuple(_to_expense(expense) for expense in model.expenses if not expense.is_actual),
        subtotal=model.subtotal,
        discount=model.discount,
        tax=model.tax,
        additional_expenses=model.additional_expenses,
        total=model.total,
        status=PurchaseOrderStatus(model.status),
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPurchaseOrderRepository:
    async def get_actual_expense_closure(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> ActualExpenseClosure | None:
        row = (
            await self._session.execute(
                select(RetaceoModel.id, RetaceoModel.code)
                .join(
                    PurchaseModel,
                    and_(
                        PurchaseModel.id == RetaceoModel.purchase_id,
                        PurchaseModel.company_id == RetaceoModel.company_id,
                    ),
                )
                .where(
                    RetaceoModel.company_id == company_id,
                    PurchaseModel.company_id == company_id,
                    PurchaseModel.purchase_order_id == order_id,
                    RetaceoModel.status == "closed",
                )
                .order_by(RetaceoModel.updated_at.desc(), RetaceoModel.id)
                .limit(1)
            )
        ).first()
        return ActualExpenseClosure(row.id, row.code) if row else None

    async def actual_expense_usage(
        self,
        company_id: uuid.UUID,
        expense_ids: tuple[uuid.UUID, ...],
        *,
        exclude_retaceo_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        if not expense_ids:
            return {}
        statement = (
            select(
                RetaceoCostModel.source_purchase_order_expense_id, func.sum(RetaceoCostModel.amount)
            )
            .join(RetaceoModel, RetaceoModel.id == RetaceoCostModel.retaceo_id)
            .where(
                RetaceoCostModel.company_id == company_id,
                RetaceoModel.company_id == company_id,
                RetaceoCostModel.source_purchase_order_expense_id.in_(expense_ids),
                RetaceoCostModel.is_active.is_(True),
                RetaceoModel.status != "cancelled",
            )
            .group_by(RetaceoCostModel.source_purchase_order_expense_id)
        )
        if exclude_retaceo_id is not None:
            statement = statement.where(RetaceoModel.id != exclude_retaceo_id)
        return {row[0]: row[1] for row in (await self._session.execute(statement)).all()}

    async def list_actual_expenses(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> tuple[ActualPurchaseExpense, ...]:
        rows = list(
            (
                await self._session.scalars(
                    select(PurchaseOrderExpenseModel)
                    .where(
                        PurchaseOrderExpenseModel.company_id == company_id,
                        PurchaseOrderExpenseModel.purchase_order_id == order_id,
                        PurchaseOrderExpenseModel.is_actual.is_(True),
                    )
                    .order_by(
                        PurchaseOrderExpenseModel.incurred_on, PurchaseOrderExpenseModel.created_at
                    )
                )
            ).all()
        )
        for row in rows:
            if row.incurred_on is None or row.reference is None or row.description is None:
                raise ValueError("Un gasto real debe tener fecha, referencia y descripción.")
        usage = await self.actual_expense_usage(company_id, tuple(row.id for row in rows))
        return tuple(
            ActualPurchaseExpense(
                id=row.id,
                company_id=row.company_id,
                purchase_order_id=row.purchase_order_id,
                expense_type_id=row.expense_type_id,
                amount=row.amount,
                incurred_on=type_cast(date, row.incurred_on),
                reference=type_cast(str, row.reference),
                description=type_cast(str, row.description),
                allocated_amount=usage.get(row.id, Decimal("0")),
                created_at=row.created_at,
            )
            for row in rows
        )

    async def add_actual_expense(self, expense: ActualPurchaseExpense) -> ActualPurchaseExpense:
        self._session.add(
            PurchaseOrderExpenseModel(
                id=expense.id,
                company_id=expense.company_id,
                purchase_order_id=expense.purchase_order_id,
                expense_type_id=expense.expense_type_id,
                amount=expense.amount,
                description=expense.description,
                is_actual=True,
                incurred_on=expense.incurred_on,
                reference=expense.reference,
            )
        )
        await self._session.flush()
        return next(
            row
            for row in await self.list_actual_expenses(
                expense.company_id, expense.purchase_order_id
            )
            if row.id == expense.id
        )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_orders(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        status: PurchaseOrderStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], int]:
        conditions = [PurchaseOrderModel.company_id == company_id]
        if branch_id is not None:
            conditions.append(self._effective_branch_condition(company_id, branch_id))
        if status is not None:
            conditions.append(PurchaseOrderModel.status == status.value)
        if supplier_id is not None:
            conditions.append(PurchaseOrderModel.supplier_id == supplier_id)
        total = await self._session.scalar(
            select(func.count()).select_from(PurchaseOrderModel).where(*conditions)
        )
        result = await self._session.execute(
            self._base_statement()
            .where(*conditions)
            .order_by(
                PurchaseOrderModel.order_date.desc(),
                PurchaseOrderModel.code.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        return [_to_entity(model) for model in result.scalars().unique().all()], int(total or 0)

    async def get_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrder | None:
        model = await self._get_model(company_id, order_id, branch_id=branch_id)
        return _to_entity(model) if model is not None else None

    async def get_order_for_update(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder | None:
        model = await self._get_model(company_id, order_id, for_update=True)
        return _to_entity(model) if model is not None else None

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        lock_name = f"purchase_orders:{company_id}"
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_name))))
        last_number = await self._session.scalar(
            select(
                func.coalesce(
                    func.max(sa_cast(func.substr(PurchaseOrderModel.code, 4), Integer)),
                    0,
                )
            ).where(
                PurchaseOrderModel.company_id == company_id,
                PurchaseOrderModel.code.op("~")(r"^OC-[0-9]+$"),
            )
        )
        return f"OC-{int(last_number or 0) + 1:05d}"

    async def get_quotation_reference_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrderQuotationReference | None:
        statement = (
            select(PurchaseQuotationModel)
            .options(selectinload(PurchaseQuotationModel.details))
            .where(
                PurchaseQuotationModel.company_id == company_id,
                PurchaseQuotationModel.id == quotation_id,
            )
        )
        if branch_id is not None:
            statement = statement.where(*self._quotation_branch_scope_conditions(branch_id))
        result = await self._session.execute(statement.with_for_update())
        model = result.scalars().unique().one_or_none()
        if model is None:
            return None
        return PurchaseOrderQuotationReference(
            id=model.id,
            supplier_id=model.supplier_id,
            currency=model.currency,
            payment_terms=model.payment_terms,
            status=PurchaseQuotationStatus(model.status),
            consolidation_id=model.consolidation_id,
            details=tuple(
                PurchaseOrderQuotationDetailReference(
                    id=detail.id,
                    product_id=detail.product_id,
                    unit_id=detail.unit_id,
                    quantity=detail.quantity,
                    available_quantity=detail.available_quantity,
                    unit_price=detail.unit_price,
                    discount=detail.discount,
                    subtotal=detail.subtotal,
                    tax_rate=detail.tax_rate,
                    notes=detail.notes,
                )
                for detail in model.details
            ),
        )

    async def get_consolidation_status_for_update(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> str | None:
        result = await self._session.execute(
            select(PurchaseConsolidationModel.status)
            .where(
                PurchaseConsolidationModel.company_id == company_id,
                PurchaseConsolidationModel.id == consolidation_id,
            )
            .with_for_update(of=PurchaseConsolidationModel)
        )
        return result.scalar_one_or_none()

    async def list_active_awards_for_quotation_for_update(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> tuple[PurchaseOrderAwardReference, ...]:
        result = await self._session.execute(
            select(PurchaseConsolidationAwardModel)
            .where(
                PurchaseConsolidationAwardModel.company_id == company_id,
                PurchaseConsolidationAwardModel.consolidation_id == consolidation_id,
                PurchaseConsolidationAwardModel.purchase_quotation_id == quotation_id,
                PurchaseConsolidationAwardModel.revoked_at.is_(None),
            )
            .order_by(
                PurchaseConsolidationAwardModel.created_at, PurchaseConsolidationAwardModel.id
            )
            .with_for_update(of=PurchaseConsolidationAwardModel)
        )
        return tuple(
            PurchaseOrderAwardReference(
                id=award.id,
                purchase_quotation_detail_id=award.purchase_quotation_detail_id,
                supplier_id=award.supplier_id,
                quantity=award.quantity,
            )
            for award in result.scalars().all()
        )

    async def get_ordered_award_quantities(
        self,
        company_id: uuid.UUID,
        award_ids: tuple[uuid.UUID, ...],
        *,
        exclude_order_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        if not award_ids:
            return {}
        conditions = [
            PurchaseOrderDetailModel.company_id == company_id,
            PurchaseOrderModel.company_id == company_id,
            PurchaseOrderDetailModel.purchase_consolidation_award_id.in_(award_ids),
            PurchaseOrderModel.status != PurchaseOrderStatus.CANCELLED.value,
        ]
        if exclude_order_id is not None:
            conditions.append(PurchaseOrderModel.id != exclude_order_id)
        result = await self._session.execute(
            select(
                PurchaseOrderDetailModel.purchase_consolidation_award_id,
                func.sum(PurchaseOrderDetailModel.quantity),
            )
            .join(
                PurchaseOrderModel,
                and_(
                    PurchaseOrderModel.company_id == PurchaseOrderDetailModel.company_id,
                    PurchaseOrderModel.id == PurchaseOrderDetailModel.purchase_order_id,
                ),
            )
            .where(*conditions)
            .group_by(PurchaseOrderDetailModel.purchase_consolidation_award_id)
        )
        return {
            award_id: quantity
            for award_id, quantity in result.all()
            if award_id is not None and quantity is not None
        }

    @staticmethod
    def _quotation_branch_scope_conditions(branch_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
        """Allow scoped order creation only from a single-branch quotation."""
        scoped_link = PurchaseQuotationRequestModel.__table__.alias("scoped_quotation_request")
        scoped_request = PurchaseRequestModel.__table__.alias("scoped_purchase_request")
        scoped_join = scoped_link.join(
            scoped_request,
            and_(
                scoped_request.c.id == scoped_link.c.purchase_request_id,
                scoped_request.c.company_id == scoped_link.c.company_id,
            ),
        )
        correlated = (
            scoped_link.c.company_id == PurchaseQuotationModel.company_id,
            scoped_link.c.purchase_quotation_id == PurchaseQuotationModel.id,
        )
        has_in_scope_request = exists(
            select(1)
            .select_from(scoped_join)
            .where(*correlated, scoped_request.c.branch_id == branch_id)
        )
        has_out_of_scope_request = exists(
            select(1)
            .select_from(scoped_join)
            .where(*correlated, scoped_request.c.branch_id != branch_id)
        )
        return has_in_scope_request, ~has_out_of_scope_request

    async def get_destination_reference(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID,
    ) -> PurchaseOrderDestinationReference | None:
        if branch_id is None:
            warehouse = await self._session.scalar(
                select(Warehouse)
                .join(
                    Branch,
                    (Branch.id == Warehouse.branch_id)
                    & (Branch.company_id == Warehouse.company_id),
                )
                .where(
                    Warehouse.id == warehouse_id,
                    Warehouse.company_id == company_id,
                    Warehouse.is_central.is_(True),
                    Warehouse.is_transit.is_(False),
                    Branch.is_headquarters.is_(True),
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                    Warehouse.deleted_at.is_(None),
                )
            )
            if warehouse is None:
                return None
            return PurchaseOrderDestinationReference(
                branch_id=None,
                warehouse_id=warehouse.id,
                branch_is_active=None,
                branch_operational_status=None,
                warehouse_is_active=warehouse.is_active,
                warehouse_operational_status=warehouse.operational_status,
                warehouse_storage_eligible=warehouse.storage_eligible,
                warehouse_is_central=warehouse.is_central,
            )

        result = await self._session.execute(
            select(Branch, Warehouse)
            .select_from(Branch)
            .join(
                Warehouse,
                Warehouse.company_id == Branch.company_id,
            )
            .where(
                Branch.company_id == company_id,
                Branch.id == branch_id,
                Branch.deleted_at.is_(None),
                Warehouse.id == warehouse_id,
                Warehouse.deleted_at.is_(None),
                Warehouse.is_transit.is_(False),
                (Warehouse.branch_id == branch_id)
                | (
                    Warehouse.is_central.is_(True)
                    & Warehouse.branch_id.in_(
                        select(Branch.id).where(
                            Branch.company_id == company_id,
                            Branch.is_headquarters.is_(True),
                            Branch.is_active.is_(True),
                            Branch.operational_status == "active",
                            Branch.deleted_at.is_(None),
                        )
                    )
                ),
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        branch, warehouse = row
        return PurchaseOrderDestinationReference(
            branch_id=branch.id,
            warehouse_id=warehouse.id,
            branch_is_active=branch.is_active,
            branch_operational_status=branch.operational_status,
            warehouse_is_active=warehouse.is_active,
            warehouse_operational_status=warehouse.operational_status,
            warehouse_storage_eligible=warehouse.storage_eligible,
            warehouse_is_central=warehouse.is_central,
        )

    async def list_active_expense_types(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]:
        result = await self._session.execute(
            select(
                ExpenseTypeModel.id,
                ExpenseTypeModel.name,
                ExpenseTypeModel.description,
            )
            .where(
                ExpenseTypeModel.company_id == company_id,
                ExpenseTypeModel.is_active.is_(True),
            )
            .order_by(func.lower(ExpenseTypeModel.name), ExpenseTypeModel.id)
        )
        return tuple(
            PurchaseOrderExpenseTypeReference(
                id=expense_type_id,
                name=name,
                description=description,
            )
            for expense_type_id, name, description in result.all()
        )

    @staticmethod
    def _expense_type_usage(company_id: uuid.UUID) -> Subquery:
        return union_all(
            select(
                PurchaseOrderExpenseModel.expense_type_id.label("expense_type_id"),
                func.count().label("usage_count"),
            )
            .where(PurchaseOrderExpenseModel.company_id == company_id)
            .group_by(PurchaseOrderExpenseModel.expense_type_id),
            select(
                PurchaseQuotationExpenseModel.expense_type_id.label("expense_type_id"),
                func.count().label("usage_count"),
            )
            .where(PurchaseQuotationExpenseModel.company_id == company_id)
            .group_by(PurchaseQuotationExpenseModel.expense_type_id),
            select(
                RetaceoCostModel.expense_type_id.label("expense_type_id"),
                func.count().label("usage_count"),
            )
            .where(
                RetaceoCostModel.company_id == company_id,
                RetaceoCostModel.expense_type_id.is_not(None),
            )
            .group_by(RetaceoCostModel.expense_type_id),
        ).subquery()

    async def list_expense_type_catalog(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]:
        usage = self._expense_type_usage(company_id)
        result = await self._session.execute(
            select(
                ExpenseTypeModel.id,
                ExpenseTypeModel.name,
                ExpenseTypeModel.description,
                ExpenseTypeModel.is_active,
                func.coalesce(func.sum(usage.c.usage_count), 0),
            )
            .outerjoin(usage, usage.c.expense_type_id == ExpenseTypeModel.id)
            .where(ExpenseTypeModel.company_id == company_id)
            .group_by(
                ExpenseTypeModel.id,
                ExpenseTypeModel.name,
                ExpenseTypeModel.description,
                ExpenseTypeModel.is_active,
            )
            .order_by(ExpenseTypeModel.is_active.desc(), func.lower(ExpenseTypeModel.name))
        )
        return tuple(
            PurchaseOrderExpenseTypeReference(
                id=expense_type_id,
                name=name,
                description=description,
                is_active=is_active,
                usage_count=int(usage_count or 0),
            )
            for expense_type_id, name, description, is_active, usage_count in result.all()
        )

    async def get_expense_type(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
    ) -> PurchaseOrderExpenseTypeReference | None:
        usage = self._expense_type_usage(company_id)
        result = await self._session.execute(
            select(
                ExpenseTypeModel.id,
                ExpenseTypeModel.name,
                ExpenseTypeModel.description,
                ExpenseTypeModel.is_active,
                func.coalesce(func.sum(usage.c.usage_count), 0),
            )
            .outerjoin(usage, usage.c.expense_type_id == ExpenseTypeModel.id)
            .where(
                ExpenseTypeModel.company_id == company_id,
                ExpenseTypeModel.id == expense_type_id,
            )
            .group_by(
                ExpenseTypeModel.id,
                ExpenseTypeModel.name,
                ExpenseTypeModel.description,
                ExpenseTypeModel.is_active,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return PurchaseOrderExpenseTypeReference(
            id=row[0],
            name=row[1],
            description=row[2],
            is_active=row[3],
            usage_count=int(row[4] or 0),
        )

    async def create_expense_type(
        self,
        company_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> PurchaseOrderExpenseTypeReference:
        model = ExpenseTypeModel(
            id=uuid.uuid4(),
            company_id=company_id,
            name=name,
            description=description,
            is_active=True,
        )
        self._session.add(model)
        await self._session.flush()
        return PurchaseOrderExpenseTypeReference(
            id=model.id,
            name=model.name,
            description=model.description,
            is_active=model.is_active,
            usage_count=0,
        )

    async def update_expense_type(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> PurchaseOrderExpenseTypeReference | None:
        result = await self._session.execute(
            select(ExpenseTypeModel).where(
                ExpenseTypeModel.company_id == company_id,
                ExpenseTypeModel.id == expense_type_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.name = name
        model.description = description
        model.is_active = is_active
        await self._session.flush()
        return await self.get_expense_type(company_id, expense_type_id)

    async def is_expense_type_active(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
    ) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(ExpenseTypeModel)
            .where(
                ExpenseTypeModel.company_id == company_id,
                ExpenseTypeModel.id == expense_type_id,
                ExpenseTypeModel.is_active.is_(True),
            )
        )
        return bool(count)

    async def get_ordered_quantities(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        exclude_order_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        conditions = [
            PurchaseOrderDetailModel.company_id == company_id,
            PurchaseOrderModel.company_id == company_id,
            PurchaseOrderModel.purchase_quotation_id == quotation_id,
            PurchaseOrderModel.status != PurchaseOrderStatus.CANCELLED.value,
        ]
        if exclude_order_id is not None:
            conditions.append(PurchaseOrderModel.id != exclude_order_id)
        result = await self._session.execute(
            select(
                PurchaseOrderDetailModel.purchase_quotation_detail_id,
                func.sum(PurchaseOrderDetailModel.quantity),
            )
            .join(
                PurchaseOrderModel,
                and_(
                    PurchaseOrderModel.company_id == PurchaseOrderDetailModel.company_id,
                    PurchaseOrderModel.id == PurchaseOrderDetailModel.purchase_order_id,
                ),
            )
            .join(
                PurchaseQuotationDetailModel,
                and_(
                    PurchaseQuotationDetailModel.company_id == PurchaseOrderDetailModel.company_id,
                    PurchaseQuotationDetailModel.id
                    == PurchaseOrderDetailModel.purchase_quotation_detail_id,
                    PurchaseQuotationDetailModel.purchase_quotation_id
                    == PurchaseOrderModel.purchase_quotation_id,
                ),
            )
            .where(*conditions)
            .group_by(PurchaseOrderDetailModel.purchase_quotation_detail_id)
        )
        quantities: dict[uuid.UUID, Decimal] = {}
        for detail_id, quantity in result.all():
            assert quantity is not None
            quantities[detail_id] = quantity
        return quantities

    async def add_order(self, order: PurchaseOrder) -> PurchaseOrder:
        model = self._order_model(order)
        self._session.add(model)
        await self._session.flush()
        persisted = await self.get_order(order.company_id, order.id)
        assert persisted is not None
        return persisted

    async def replace_draft(self, order: PurchaseOrder) -> PurchaseOrder | None:
        model = await self._get_model(order.company_id, order.id)
        if model is None:
            return None
        model.supplier_id = order.supplier_id
        model.branch_id = order.branch_id
        model.warehouse_id = order.warehouse_id
        model.purchase_quotation_id = order.purchase_quotation_id
        model.expected_date = order.expected_date
        model.currency = order.currency
        model.payment_terms = order.payment_terms
        model.subtotal = order.subtotal
        model.discount = order.discount
        model.tax = order.tax
        model.additional_expenses = order.additional_expenses
        model.total = order.total
        model.notes = order.notes
        model.details = [self._detail_model(order.company_id, detail) for detail in order.details]
        model.expenses = [
            self._expense_model(order.company_id, expense) for expense in order.expenses
        ]
        await self._session.flush()
        return await self.get_order(order.company_id, order.id)

    async def update_status(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        status: PurchaseOrderStatus,
    ) -> PurchaseOrder | None:
        model = await self._get_model(company_id, order_id)
        if model is None:
            return None
        model.status = status.value
        await self._session.flush()
        return await self.get_order(company_id, order_id)

    async def advance_purchase_request_order_statuses(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> None:
        request_ids = tuple(
            (
                await self._session.scalars(
                    select(PurchaseQuotationRequestModel.purchase_request_id)
                    .where(
                        PurchaseQuotationRequestModel.company_id == company_id,
                        PurchaseQuotationRequestModel.purchase_quotation_id == quotation_id,
                    )
                    .distinct()
                )
            ).all()
        )
        for request_id in sorted(request_ids, key=lambda item: item.int):
            await self._advance_request_status(company_id, request_id)

    async def _advance_request_status(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> None:
        result = await self._session.execute(
            select(PurchaseRequestModel)
            .options(selectinload(PurchaseRequestModel.details))
            .where(
                PurchaseRequestModel.company_id == company_id,
                PurchaseRequestModel.id == request_id,
            )
            .with_for_update()
        )
        request = result.scalar_one_or_none()
        if request is None:
            return
        current = PurchaseRequestStatus(request.status)
        if current not in {
            PurchaseRequestStatus.QUOTED,
            PurchaseRequestStatus.PARTIALLY_ORDERED,
        }:
            return
        coverage = await self._safe_order_coverage(company_id, request_id)
        if not coverage:
            return
        fully_ordered = all(
            coverage.get(detail.id, Decimal("0")) >= detail.quantity for detail in request.details
        )
        has_ordered_quantity = any(
            coverage.get(detail.id, Decimal("0")) > 0 for detail in request.details
        )
        if fully_ordered:
            target = PurchaseRequestStatus.COMPLETED
        elif has_ordered_quantity:
            target = PurchaseRequestStatus.PARTIALLY_ORDERED
        else:
            return
        if current is target:
            return
        if (
            current is PurchaseRequestStatus.PARTIALLY_ORDERED
            and target is not PurchaseRequestStatus.COMPLETED
        ):
            return
        request.status = target.value
        await self._session.flush()

    async def _safe_order_coverage(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> dict[uuid.UUID, Decimal]:
        result = await self._session.execute(
            select(
                PurchaseQuotationRequestDetailModel.purchase_quotation_detail_id,
                PurchaseQuotationRequestDetailModel.purchase_request_detail_id,
                PurchaseQuotationRequestDetailModel.quantity,
            )
            .join(
                PurchaseQuotationRequestModel,
                and_(
                    PurchaseQuotationRequestModel.id
                    == PurchaseQuotationRequestDetailModel.purchase_quotation_request_id,
                    PurchaseQuotationRequestModel.company_id
                    == PurchaseQuotationRequestDetailModel.company_id,
                ),
            )
            .where(
                PurchaseQuotationRequestDetailModel.company_id == company_id,
                PurchaseQuotationRequestModel.purchase_request_id == request_id,
            )
        )
        link_rows = [
            (quotation_detail_id, request_detail_id, quantity)
            for quotation_detail_id, request_detail_id, quantity in result.all()
        ]
        if not link_rows:
            return {}

        quotation_detail_ids = {row[0] for row in link_rows}
        scope_result = await self._session.execute(
            select(
                PurchaseQuotationRequestDetailModel.purchase_quotation_detail_id,
                func.count(PurchaseQuotationRequestDetailModel.id),
                func.sum(PurchaseQuotationRequestDetailModel.quantity),
            )
            .where(
                PurchaseQuotationRequestDetailModel.company_id == company_id,
                PurchaseQuotationRequestDetailModel.purchase_quotation_detail_id.in_(
                    quotation_detail_ids
                ),
            )
            .group_by(PurchaseQuotationRequestDetailModel.purchase_quotation_detail_id)
        )
        scope: dict[uuid.UUID, tuple[int, Decimal]] = {}
        for detail_id, link_count, scope_quantity in scope_result.all():
            assert scope_quantity is not None
            scope[detail_id] = (int(link_count), scope_quantity)

        ordered_result = await self._session.execute(
            select(
                PurchaseOrderDetailModel.purchase_quotation_detail_id,
                func.sum(PurchaseOrderDetailModel.quantity),
            )
            .join(
                PurchaseOrderModel,
                and_(
                    PurchaseOrderModel.company_id == PurchaseOrderDetailModel.company_id,
                    PurchaseOrderModel.id == PurchaseOrderDetailModel.purchase_order_id,
                ),
            )
            .join(
                PurchaseQuotationDetailModel,
                and_(
                    PurchaseQuotationDetailModel.company_id == PurchaseOrderDetailModel.company_id,
                    PurchaseQuotationDetailModel.id
                    == PurchaseOrderDetailModel.purchase_quotation_detail_id,
                    PurchaseQuotationDetailModel.purchase_quotation_id
                    == PurchaseOrderModel.purchase_quotation_id,
                ),
            )
            .where(
                PurchaseOrderDetailModel.company_id == company_id,
                PurchaseOrderDetailModel.purchase_quotation_detail_id.in_(quotation_detail_ids),
                PurchaseOrderModel.company_id == company_id,
                PurchaseOrderModel.status.in_(COMMITTED_ORDER_STATUS_VALUES),
            )
            .group_by(PurchaseOrderDetailModel.purchase_quotation_detail_id)
        )
        ordered: dict[uuid.UUID, Decimal] = {}
        for detail_id, quantity in ordered_result.all():
            assert quantity is not None
            ordered[detail_id] = quantity

        coverage: dict[uuid.UUID, Decimal] = {}
        for quotation_detail_id, request_detail_id, linked_quantity in link_rows:
            link_count, scope_quantity = scope[quotation_detail_id]
            ordered_quantity = ordered.get(quotation_detail_id, Decimal("0"))
            if link_count == 1:
                allocated = min(ordered_quantity, linked_quantity)
            elif ordered_quantity >= scope_quantity:
                allocated = linked_quantity
            else:
                # A consolidated quotation detail can belong to several request
                # details. Without an order-detail -> request-detail FK, a partial
                # order cannot be allocated exactly, so we deliberately do not
                # guess which request consumed it.
                allocated = Decimal("0")
            coverage[request_detail_id] = coverage.get(request_detail_id, Decimal("0")) + allocated
        return coverage

    async def _get_model(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrderModel | None:
        statement = self._base_statement().where(
            PurchaseOrderModel.company_id == company_id,
            PurchaseOrderModel.id == order_id,
        )
        if branch_id is not None:
            statement = statement.where(self._effective_branch_condition(company_id, branch_id))
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalars().unique().one_or_none()

    @staticmethod
    def _base_statement() -> Select[tuple[PurchaseOrderModel]]:
        return select(PurchaseOrderModel).options(
            selectinload(PurchaseOrderModel.details),
            selectinload(PurchaseOrderModel.expenses),
        )

    @staticmethod
    def _effective_branch_condition(
        company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> ColumnElement[bool]:
        central_warehouse_in_branch = exists(
            select(1)
            .select_from(Warehouse)
            .join(
                Branch,
                (Branch.id == Warehouse.branch_id) & (Branch.company_id == Warehouse.company_id),
            )
            .where(
                Warehouse.id == PurchaseOrderModel.warehouse_id,
                Warehouse.company_id == company_id,
                Warehouse.branch_id == branch_id,
                Warehouse.is_central.is_(True),
                Branch.is_headquarters.is_(True),
            )
        )
        return or_(
            PurchaseOrderModel.branch_id == branch_id,
            and_(PurchaseOrderModel.branch_id.is_(None), central_warehouse_in_branch),
        )

    @classmethod
    def _order_model(cls, order: PurchaseOrder) -> PurchaseOrderModel:
        return PurchaseOrderModel(
            id=order.id,
            company_id=order.company_id,
            code=order.code,
            supplier_id=order.supplier_id,
            branch_id=order.branch_id,
            warehouse_id=order.warehouse_id,
            purchase_quotation_id=order.purchase_quotation_id,
            created_by_id=order.created_by_id,
            order_date=order.order_date,
            expected_date=order.expected_date,
            currency=order.currency,
            payment_terms=order.payment_terms,
            subtotal=order.subtotal,
            discount=order.discount,
            tax=order.tax,
            additional_expenses=order.additional_expenses,
            total=order.total,
            status=order.status.value,
            notes=order.notes,
            details=[cls._detail_model(order.company_id, detail) for detail in order.details],
            expenses=[cls._expense_model(order.company_id, expense) for expense in order.expenses],
        )

    @staticmethod
    def _detail_model(
        company_id: uuid.UUID,
        detail: PurchaseOrderDetail,
    ) -> PurchaseOrderDetailModel:
        return PurchaseOrderDetailModel(
            id=detail.id,
            company_id=company_id,
            purchase_order_id=detail.purchase_order_id,
            purchase_quotation_detail_id=detail.purchase_quotation_detail_id,
            product_id=detail.product_id,
            quantity=detail.quantity,
            unit_id=detail.unit_id,
            unit_price=detail.unit_price,
            discount=detail.discount,
            subtotal=detail.subtotal,
            tax_rate=detail.tax_rate,
            tax_amount=detail.tax_amount,
            total=detail.total,
            notes=detail.notes,
            purchase_consolidation_award_id=detail.purchase_consolidation_award_id,
        )

    @staticmethod
    def _expense_model(
        company_id: uuid.UUID,
        expense: PurchaseOrderExpense,
    ) -> PurchaseOrderExpenseModel:
        return PurchaseOrderExpenseModel(
            id=expense.id,
            company_id=company_id,
            purchase_order_id=expense.purchase_order_id,
            expense_type_id=expense.expense_type_id,
            description=expense.description,
            amount=expense.amount,
        )

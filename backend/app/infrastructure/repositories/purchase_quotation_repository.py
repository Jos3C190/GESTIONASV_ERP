"""SQLAlchemy implementation of the purchase-quotation repository port."""

from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import Integer, Select, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.purchase_quotation import (
    PurchaseQuotation,
    PurchaseQuotationDetail,
    PurchaseQuotationExpense,
    PurchaseQuotationRequest,
    PurchaseQuotationRequestDetail,
    PurchaseQuotationStatus,
)
from app.domain.entities.purchase_request import PurchaseRequestStatus
from app.domain.ports.purchase_quotation_repository import (
    PurchaseQuotationCoverageReference,
    PurchaseQuotationRequestDetailReference,
    PurchaseQuotationRequestReference,
    PurchaseQuotationSupplierReference,
)
from app.infrastructure.models.purchase_quotation import (
    ExpenseTypeModel,
    PurchaseQuotationDetailModel,
    PurchaseQuotationExpenseModel,
    PurchaseQuotationModel,
    PurchaseQuotationRequestDetailModel,
    PurchaseQuotationRequestModel,
)
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.supplier_master_data import CurrencyModel

COMPARABLE_STATUS_VALUES = (
    PurchaseQuotationStatus.RECEIVED.value,
    PurchaseQuotationStatus.UNDER_EVALUATION.value,
    PurchaseQuotationStatus.SELECTED.value,
)


def _to_request_detail(
    model: PurchaseQuotationRequestDetailModel,
) -> PurchaseQuotationRequestDetail:
    return PurchaseQuotationRequestDetail(
        id=model.id,
        purchase_quotation_request_id=model.purchase_quotation_request_id,
        purchase_request_detail_id=model.purchase_request_detail_id,
        quantity=model.quantity,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_request_link(model: PurchaseQuotationRequestModel) -> PurchaseQuotationRequest:
    return PurchaseQuotationRequest(
        id=model.id,
        purchase_quotation_id=model.purchase_quotation_id,
        purchase_request_id=model.purchase_request_id,
        details=tuple(_to_request_detail(detail) for detail in model.details),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_detail(model: PurchaseQuotationDetailModel) -> PurchaseQuotationDetail:
    return PurchaseQuotationDetail(
        id=model.id,
        purchase_quotation_id=model.purchase_quotation_id,
        product_id=model.product_id,
        unit_id=model.unit_id,
        quantity=model.quantity,
        unit_price=model.unit_price,
        discount=model.discount,
        subtotal=model.subtotal,
        tax_rate=model.tax_rate,
        tax_amount=model.tax_amount,
        total=model.total,
        delivery_days=model.delivery_days,
        available_quantity=model.available_quantity,
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_expense(model: PurchaseQuotationExpenseModel) -> PurchaseQuotationExpense:
    return PurchaseQuotationExpense(
        id=model.id,
        purchase_quotation_id=model.purchase_quotation_id,
        expense_type_id=model.expense_type_id,
        amount=model.amount,
        description=model.description,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_entity(model: PurchaseQuotationModel) -> PurchaseQuotation:
    return PurchaseQuotation(
        id=model.id,
        company_id=model.company_id,
        code=model.code,
        supplier_id=model.supplier_id,
        quotation_date=model.quotation_date,
        currency=model.currency,
        created_by_id=model.created_by_id,
        request_links=tuple(_to_request_link(link) for link in model.request_links),
        details=tuple(_to_detail(detail) for detail in model.details),
        expenses=tuple(_to_expense(expense) for expense in model.expenses),
        valid_until=model.valid_until,
        payment_terms=model.payment_terms,
        delivery_days=model.delivery_days,
        subtotal=model.subtotal,
        discount=model.discount,
        tax=model.tax,
        total=model.total,
        status=PurchaseQuotationStatus(model.status),
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPurchaseQuotationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_quotations(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseQuotationStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseQuotation], int]:
        conditions = [PurchaseQuotationModel.company_id == company_id]
        if status is not None:
            conditions.append(PurchaseQuotationModel.status == status.value)
        if supplier_id is not None:
            conditions.append(PurchaseQuotationModel.supplier_id == supplier_id)
        total = await self._session.scalar(
            select(func.count()).select_from(PurchaseQuotationModel).where(*conditions)
        )
        result = await self._session.execute(
            self._base_statement()
            .where(*conditions)
            .order_by(
                PurchaseQuotationModel.quotation_date.desc(),
                PurchaseQuotationModel.code.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        return [_to_entity(model) for model in result.scalars().unique().all()], int(total or 0)

    async def get_quotation(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation | None:
        model = await self._get_model(company_id, quotation_id)
        return _to_entity(model) if model is not None else None

    async def get_quotation_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation | None:
        model = await self._get_model(company_id, quotation_id, for_update=True)
        return _to_entity(model) if model is not None else None

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        lock_name = f"purchase_quotations:{company_id}"
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_name))))
        last_number = await self._session.scalar(
            select(
                func.coalesce(
                    func.max(cast(func.substr(PurchaseQuotationModel.code, 5), Integer)),
                    0,
                )
            ).where(
                PurchaseQuotationModel.company_id == company_id,
                PurchaseQuotationModel.code.op("~")(r"^COT-[0-9]+$"),
            )
        )
        return f"COT-{int(last_number or 0) + 1:05d}"

    async def get_supplier_reference(
        self,
        company_id: uuid.UUID,
        supplier_id: int,
    ) -> PurchaseQuotationSupplierReference | None:
        row = (
            await self._session.execute(
                select(
                    SupplierModel.id_supplier,
                    SupplierModel.is_active,
                    SupplierModel.supplier_status,
                ).where(
                    SupplierModel.company_id == company_id,
                    SupplierModel.id_supplier == supplier_id,
                    SupplierModel.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return PurchaseQuotationSupplierReference(
            supplier_id=row.id_supplier,
            is_active=row.is_active,
            supplier_status=row.supplier_status,
        )

    async def is_currency_active(self, currency: str) -> bool:
        count = await self._session.scalar(
            select(func.count())
            .select_from(CurrencyModel)
            .where(CurrencyModel.code == currency, CurrencyModel.is_active.is_(True))
        )
        return bool(count)

    async def get_request_reference(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseQuotationRequestReference | None:
        result = await self._session.execute(
            select(PurchaseRequestModel)
            .options(selectinload(PurchaseRequestModel.details))
            .where(
                PurchaseRequestModel.company_id == company_id,
                PurchaseRequestModel.id == request_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return PurchaseQuotationRequestReference(
            id=model.id,
            status=PurchaseRequestStatus(model.status),
            details=tuple(
                PurchaseQuotationRequestDetailReference(
                    id=detail.id,
                    product_id=detail.product_id,
                    unit_id=detail.unit_id,
                    quantity=detail.quantity,
                )
                for detail in model.details
            ),
        )

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

    async def get_coverage_references(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> tuple[PurchaseQuotationCoverageReference, ...]:
        result = await self._session.execute(
            select(
                PurchaseQuotationRequestModel.purchase_request_id,
                PurchaseQuotationRequestDetailModel.purchase_request_detail_id,
                PurchaseRequestDetailModel.product_id,
                PurchaseRequestDetailModel.unit_id,
                PurchaseQuotationRequestDetailModel.quantity,
            )
            .join(
                PurchaseQuotationRequestDetailModel,
                and_(
                    PurchaseQuotationRequestDetailModel.purchase_quotation_request_id
                    == PurchaseQuotationRequestModel.id,
                    PurchaseQuotationRequestDetailModel.company_id
                    == PurchaseQuotationRequestModel.company_id,
                ),
            )
            .join(
                PurchaseRequestDetailModel,
                and_(
                    PurchaseRequestDetailModel.id
                    == PurchaseQuotationRequestDetailModel.purchase_request_detail_id,
                    PurchaseRequestDetailModel.company_id
                    == PurchaseQuotationRequestDetailModel.company_id,
                ),
            )
            .where(
                PurchaseQuotationRequestModel.company_id == company_id,
                PurchaseQuotationRequestModel.purchase_quotation_id == quotation_id,
            )
        )
        return tuple(
            PurchaseQuotationCoverageReference(
                purchase_request_id=row.purchase_request_id,
                purchase_request_detail_id=row.purchase_request_detail_id,
                product_id=row.product_id,
                unit_id=row.unit_id,
                quantity=row.quantity,
            )
            for row in result.all()
        )

    async def add_quotation(self, quotation: PurchaseQuotation) -> PurchaseQuotation:
        model = PurchaseQuotationModel(
            id=quotation.id,
            company_id=quotation.company_id,
            code=quotation.code,
            supplier_id=quotation.supplier_id,
            quotation_date=quotation.quotation_date,
            valid_until=quotation.valid_until,
            currency=quotation.currency,
            payment_terms=quotation.payment_terms,
            delivery_days=quotation.delivery_days,
            subtotal=quotation.subtotal,
            discount=quotation.discount,
            tax=quotation.tax,
            total=quotation.total,
            status=quotation.status.value,
            notes=quotation.notes,
            created_by_id=quotation.created_by_id,
            request_links=[
                self._request_link_model(quotation.company_id, link)
                for link in quotation.request_links
            ],
            details=[
                self._detail_model(quotation.company_id, detail) for detail in quotation.details
            ],
            expenses=[
                self._expense_model(quotation.company_id, expense) for expense in quotation.expenses
            ],
        )
        self._session.add(model)
        await self._session.flush()
        persisted = await self.get_quotation(quotation.company_id, quotation.id)
        assert persisted is not None
        return persisted

    async def replace_response(self, quotation: PurchaseQuotation) -> PurchaseQuotation | None:
        model = await self._get_model(quotation.company_id, quotation.id)
        if model is None:
            return None
        model.quotation_date = quotation.quotation_date
        model.valid_until = quotation.valid_until
        model.payment_terms = quotation.payment_terms
        model.delivery_days = quotation.delivery_days
        model.subtotal = quotation.subtotal
        model.discount = quotation.discount
        model.tax = quotation.tax
        model.total = quotation.total
        model.status = quotation.status.value
        model.notes = quotation.notes
        model.details = [
            self._detail_model(quotation.company_id, detail) for detail in quotation.details
        ]
        model.expenses = [
            self._expense_model(quotation.company_id, expense) for expense in quotation.expenses
        ]
        await self._session.flush()
        return await self.get_quotation(quotation.company_id, quotation.id)

    async def update_status(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        status: PurchaseQuotationStatus,
    ) -> PurchaseQuotation | None:
        model = await self._get_model(company_id, quotation_id)
        if model is None:
            return None
        model.status = status.value
        await self._session.flush()
        return await self.get_quotation(company_id, quotation_id)

    async def list_comparable(
        self,
        company_id: uuid.UUID,
        purchase_request_id: uuid.UUID,
    ) -> list[PurchaseQuotation]:
        result = await self._session.execute(
            self._base_statement()
            .join(
                PurchaseQuotationRequestModel,
                and_(
                    PurchaseQuotationRequestModel.purchase_quotation_id
                    == PurchaseQuotationModel.id,
                    PurchaseQuotationRequestModel.company_id == PurchaseQuotationModel.company_id,
                ),
            )
            .where(
                PurchaseQuotationModel.company_id == company_id,
                PurchaseQuotationRequestModel.purchase_request_id == purchase_request_id,
                PurchaseQuotationModel.status.in_(COMPARABLE_STATUS_VALUES),
            )
            .order_by(PurchaseQuotationModel.total, PurchaseQuotationModel.code)
        )
        return [_to_entity(model) for model in result.scalars().unique().all()]

    async def advance_purchase_request_quotation_statuses(
        self,
        company_id: uuid.UUID,
        request_ids: tuple[uuid.UUID, ...],
    ) -> None:
        for request_id in dict.fromkeys(request_ids):
            await self._advance_request_status(company_id, request_id)

    async def _advance_request_status(self, company_id: uuid.UUID, request_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(PurchaseRequestModel)
            .options(selectinload(PurchaseRequestModel.details))
            .where(
                PurchaseRequestModel.company_id == company_id,
                PurchaseRequestModel.id == request_id,
            )
        )
        request = result.scalar_one_or_none()
        if request is None:
            return
        current = PurchaseRequestStatus(request.status)
        if current not in {
            PurchaseRequestStatus.APPROVED,
            PurchaseRequestStatus.PARTIALLY_QUOTED,
        }:
            return
        coverage = await self._response_coverage(company_id, request_id)
        if not coverage:
            return
        fully_quoted = all(
            coverage.get(detail.id, Decimal("0")) >= detail.quantity for detail in request.details
        )
        target = (
            PurchaseRequestStatus.QUOTED if fully_quoted else PurchaseRequestStatus.PARTIALLY_QUOTED
        )
        if current is PurchaseRequestStatus.PARTIALLY_QUOTED and target is current:
            return
        request.status = target.value
        await self._session.flush()

    async def _response_coverage(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> dict[uuid.UUID, Decimal]:
        result = await self._session.execute(
            select(
                PurchaseQuotationRequestDetailModel.purchase_request_detail_id,
                PurchaseQuotationDetailModel.quantity,
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
            .join(
                PurchaseQuotationModel,
                and_(
                    PurchaseQuotationModel.id
                    == PurchaseQuotationRequestModel.purchase_quotation_id,
                    PurchaseQuotationModel.company_id == PurchaseQuotationRequestModel.company_id,
                ),
            )
            .join(
                PurchaseRequestDetailModel,
                and_(
                    PurchaseRequestDetailModel.id
                    == PurchaseQuotationRequestDetailModel.purchase_request_detail_id,
                    PurchaseRequestDetailModel.company_id
                    == PurchaseQuotationRequestDetailModel.company_id,
                ),
            )
            .join(
                PurchaseQuotationDetailModel,
                and_(
                    PurchaseQuotationDetailModel.purchase_quotation_id == PurchaseQuotationModel.id,
                    PurchaseQuotationDetailModel.company_id == PurchaseQuotationModel.company_id,
                    PurchaseQuotationDetailModel.product_id
                    == PurchaseRequestDetailModel.product_id,
                    PurchaseQuotationDetailModel.unit_id == PurchaseRequestDetailModel.unit_id,
                ),
            )
            .where(
                PurchaseQuotationModel.company_id == company_id,
                PurchaseQuotationRequestModel.purchase_request_id == request_id,
                PurchaseQuotationModel.status.in_(COMPARABLE_STATUS_VALUES),
            )
        )
        coverage: defaultdict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        for detail_id, quantity in result.all():
            coverage[detail_id] = max(coverage[detail_id], quantity)
        return dict(coverage)

    async def _get_model(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseQuotationModel | None:
        statement = self._base_statement().where(
            PurchaseQuotationModel.company_id == company_id,
            PurchaseQuotationModel.id == quotation_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalars().unique().one_or_none()

    @staticmethod
    def _base_statement() -> Select[tuple[PurchaseQuotationModel]]:
        return select(PurchaseQuotationModel).options(
            selectinload(PurchaseQuotationModel.request_links).selectinload(
                PurchaseQuotationRequestModel.details
            ),
            selectinload(PurchaseQuotationModel.details),
            selectinload(PurchaseQuotationModel.expenses),
        )

    @staticmethod
    def _request_link_model(
        company_id: uuid.UUID,
        link: PurchaseQuotationRequest,
    ) -> PurchaseQuotationRequestModel:
        return PurchaseQuotationRequestModel(
            id=link.id,
            company_id=company_id,
            purchase_quotation_id=link.purchase_quotation_id,
            purchase_request_id=link.purchase_request_id,
            details=[
                PurchaseQuotationRequestDetailModel(
                    id=detail.id,
                    company_id=company_id,
                    purchase_quotation_request_id=detail.purchase_quotation_request_id,
                    purchase_request_detail_id=detail.purchase_request_detail_id,
                    quantity=detail.quantity,
                )
                for detail in link.details
            ],
        )

    @staticmethod
    def _detail_model(
        company_id: uuid.UUID,
        detail: PurchaseQuotationDetail,
    ) -> PurchaseQuotationDetailModel:
        return PurchaseQuotationDetailModel(
            id=detail.id,
            company_id=company_id,
            purchase_quotation_id=detail.purchase_quotation_id,
            product_id=detail.product_id,
            unit_id=detail.unit_id,
            quantity=detail.quantity,
            unit_price=detail.unit_price,
            discount=detail.discount,
            subtotal=detail.subtotal,
            tax_rate=detail.tax_rate,
            tax_amount=detail.tax_amount,
            total=detail.total,
            delivery_days=detail.delivery_days,
            available_quantity=detail.available_quantity,
            notes=detail.notes,
        )

    @staticmethod
    def _expense_model(
        company_id: uuid.UUID,
        expense: PurchaseQuotationExpense,
    ) -> PurchaseQuotationExpenseModel:
        return PurchaseQuotationExpenseModel(
            id=expense.id,
            company_id=company_id,
            purchase_quotation_id=expense.purchase_quotation_id,
            expense_type_id=expense.expense_type_id,
            description=expense.description,
            amount=expense.amount,
        )

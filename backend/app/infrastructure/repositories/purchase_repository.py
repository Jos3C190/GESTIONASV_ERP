"""SQLAlchemy implementation of the purchase-receipt repository."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Integer, Select, and_, func, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.purchase import Purchase, PurchaseDetail, PurchaseStatus
from app.infrastructure.models.purchase import PurchaseDetailModel, PurchaseModel

COUNTED_RECEIPT_STATUS_VALUES = (
    PurchaseStatus.RECEIVED.value,
    PurchaseStatus.VERIFIED.value,
    PurchaseStatus.CLOSED.value,
)


def _to_detail(model: PurchaseDetailModel) -> PurchaseDetail:
    return PurchaseDetail(
        id=model.id,
        purchase_id=model.purchase_id,
        purchase_order_detail_id=model.purchase_order_detail_id,
        product_id=model.product_id,
        quantity_ordered=model.quantity_ordered,
        quantity_received=model.quantity_received,
        unit_id=model.unit_id,
        unit_price=model.unit_price,
        discount=model.discount,
        subtotal=model.subtotal,
        tax_rate=model.tax_rate,
        tax_amount=model.tax_amount,
        total=model.total,
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_entity(model: PurchaseModel) -> Purchase:
    return Purchase(
        id=model.id,
        company_id=model.company_id,
        code=model.code,
        purchase_order_id=model.purchase_order_id,
        supplier_id=model.supplier_id,
        branch_id=model.branch_id,
        warehouse_id=model.warehouse_id,
        created_by_id=model.created_by_id,
        purchase_date=model.purchase_date,
        supplier_invoice_number=model.supplier_invoice_number,
        supplier_invoice_date=model.supplier_invoice_date,
        currency=model.currency,
        details=tuple(_to_detail(detail) for detail in model.details),
        subtotal=model.subtotal,
        discount=model.discount,
        tax=model.tax,
        total=model.total,
        status=PurchaseStatus(model.status),
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPurchaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_purchases(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseStatus | None = None,
        supplier_id: int | None = None,
        purchase_order_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]:
        conditions = [PurchaseModel.company_id == company_id]
        if status is not None:
            conditions.append(PurchaseModel.status == status.value)
        if supplier_id is not None:
            conditions.append(PurchaseModel.supplier_id == supplier_id)
        if purchase_order_id is not None:
            conditions.append(PurchaseModel.purchase_order_id == purchase_order_id)
        if branch_id is not None:
            conditions.append(PurchaseModel.branch_id == branch_id)
        total = await self._session.scalar(
            select(func.count()).select_from(PurchaseModel).where(*conditions)
        )
        result = await self._session.execute(
            self._base_statement()
            .where(*conditions)
            .order_by(PurchaseModel.purchase_date.desc(), PurchaseModel.code.desc())
            .offset(skip)
            .limit(limit)
        )
        return [_to_entity(model) for model in result.scalars().unique().all()], int(total or 0)

    async def get_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase | None:
        model = await self._get_model(company_id, purchase_id)
        return _to_entity(model) if model is not None else None

    async def get_purchase_for_update(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase | None:
        model = await self._get_model(company_id, purchase_id, for_update=True)
        return _to_entity(model) if model is not None else None

    async def allocate_next_code(self, company_id: uuid.UUID) -> str:
        lock_name = f"purchases:{company_id}"
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(lock_name))))
        last_number = await self._session.scalar(
            select(
                func.coalesce(
                    func.max(sa_cast(func.substr(PurchaseModel.code, 5), Integer)),
                    0,
                )
            ).where(
                PurchaseModel.company_id == company_id,
                PurchaseModel.code.op("~")(r"^COM-[0-9]+$"),
            )
        )
        return f"COM-{int(last_number or 0) + 1:05d}"

    async def get_received_quantities(
        self,
        company_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        exclude_purchase_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]:
        conditions = [
            PurchaseDetailModel.company_id == company_id,
            PurchaseModel.company_id == company_id,
            PurchaseModel.purchase_order_id == purchase_order_id,
            PurchaseModel.status.in_(COUNTED_RECEIPT_STATUS_VALUES),
        ]
        if exclude_purchase_id is not None:
            conditions.append(PurchaseModel.id != exclude_purchase_id)
        result = await self._session.execute(
            select(
                PurchaseDetailModel.purchase_order_detail_id,
                func.sum(PurchaseDetailModel.quantity_received),
            )
            .join(
                PurchaseModel,
                and_(
                    PurchaseModel.company_id == PurchaseDetailModel.company_id,
                    PurchaseModel.id == PurchaseDetailModel.purchase_id,
                ),
            )
            .where(*conditions)
            .group_by(PurchaseDetailModel.purchase_order_detail_id)
        )
        quantities: dict[uuid.UUID, Decimal] = {}
        for detail_id, quantity in result.all():
            assert quantity is not None
            quantities[detail_id] = quantity
        return quantities

    async def add_purchase(self, purchase: Purchase) -> Purchase:
        self._session.add(self._purchase_model(purchase))
        await self._session.flush()
        persisted = await self.get_purchase(purchase.company_id, purchase.id)
        assert persisted is not None
        return persisted

    async def replace_draft(self, purchase: Purchase) -> Purchase | None:
        model = await self._get_model(purchase.company_id, purchase.id)
        if model is None:
            return None
        model.supplier_invoice_number = purchase.supplier_invoice_number
        model.supplier_invoice_date = purchase.supplier_invoice_date
        model.subtotal = purchase.subtotal
        model.discount = purchase.discount
        model.tax = purchase.tax
        model.total = purchase.total
        model.notes = purchase.notes
        model.details = [
            self._detail_model(purchase.company_id, detail) for detail in purchase.details
        ]
        await self._session.flush()
        return await self.get_purchase(purchase.company_id, purchase.id)

    async def update_status(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        status: PurchaseStatus,
    ) -> Purchase | None:
        model = await self._get_model(company_id, purchase_id)
        if model is None:
            return None
        model.status = status.value
        await self._session.flush()
        return await self.get_purchase(company_id, purchase_id)

    async def _get_model(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseModel | None:
        statement = self._base_statement().where(
            PurchaseModel.company_id == company_id,
            PurchaseModel.id == purchase_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalars().unique().one_or_none()

    @staticmethod
    def _base_statement() -> Select[tuple[PurchaseModel]]:
        return select(PurchaseModel).options(selectinload(PurchaseModel.details))

    @classmethod
    def _purchase_model(cls, purchase: Purchase) -> PurchaseModel:
        return PurchaseModel(
            id=purchase.id,
            company_id=purchase.company_id,
            code=purchase.code,
            purchase_order_id=purchase.purchase_order_id,
            supplier_id=purchase.supplier_id,
            branch_id=purchase.branch_id,
            warehouse_id=purchase.warehouse_id,
            created_by_id=purchase.created_by_id,
            purchase_date=purchase.purchase_date,
            supplier_invoice_number=purchase.supplier_invoice_number,
            supplier_invoice_date=purchase.supplier_invoice_date,
            currency=purchase.currency,
            subtotal=purchase.subtotal,
            discount=purchase.discount,
            tax=purchase.tax,
            total=purchase.total,
            status=purchase.status.value,
            notes=purchase.notes,
            details=[cls._detail_model(purchase.company_id, detail) for detail in purchase.details],
        )

    @staticmethod
    def _detail_model(
        company_id: uuid.UUID,
        detail: PurchaseDetail,
    ) -> PurchaseDetailModel:
        return PurchaseDetailModel(
            id=detail.id,
            company_id=company_id,
            purchase_id=detail.purchase_id,
            purchase_order_detail_id=detail.purchase_order_detail_id,
            product_id=detail.product_id,
            quantity_ordered=detail.quantity_ordered,
            quantity_received=detail.quantity_received,
            unit_id=detail.unit_id,
            unit_price=detail.unit_price,
            discount=detail.discount,
            subtotal=detail.subtotal,
            tax_rate=detail.tax_rate,
            tax_amount=detail.tax_amount,
            total=detail.total,
            notes=detail.notes,
        )

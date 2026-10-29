"""SQLAlchemy implementation of the purchase-receipt repository."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Integer, Select, and_, case, exists, func, or_, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseInventoryWorkflow,
    PurchaseStatus,
)
from app.domain.entities.purchase_conversion import PurchaseValuationConversion
from app.infrastructure.models.organization import Branch, Warehouse
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
        quantity_accepted=model.quantity_accepted,
        inventory_location_id=model.inventory_location_id,
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
        inventory_movement_id=model.inventory_movement_id,
        supplier_id=model.supplier_id,
        branch_id=model.branch_id,
        warehouse_id=model.warehouse_id,
        created_by_id=model.created_by_id,
        purchase_date=model.purchase_date,
        supplier_invoice_number=model.supplier_invoice_number,
        supplier_invoice_date=model.supplier_invoice_date,
        currency=model.currency,
        valuation_conversion=(
            PurchaseValuationConversion.from_dict(model.valuation_conversion)
            if model.valuation_conversion is not None
            else None
        ),
        details=tuple(_to_detail(detail) for detail in model.details),
        subtotal=model.subtotal,
        discount=model.discount,
        tax=model.tax,
        total=model.total,
        status=PurchaseStatus(model.status),
        inventory_workflow=PurchaseInventoryWorkflow(model.inventory_workflow),
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
            central_warehouse_in_branch = exists(
                select(1)
                .select_from(Warehouse)
                .join(
                    Branch,
                    (Branch.id == Warehouse.branch_id)
                    & (Branch.company_id == Warehouse.company_id),
                )
                .where(
                    Warehouse.id == PurchaseModel.warehouse_id,
                    Warehouse.company_id == company_id,
                    Warehouse.branch_id == branch_id,
                    Warehouse.is_central.is_(True),
                    Branch.is_headquarters.is_(True),
                )
            )
            conditions.append(
                or_(
                    PurchaseModel.branch_id == branch_id,
                    and_(PurchaseModel.branch_id.is_(None), central_warehouse_in_branch),
                )
            )
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
                func.sum(
                    case(
                        (
                            PurchaseModel.status == PurchaseStatus.RECEIVED.value,
                            PurchaseDetailModel.quantity_received,
                        ),
                        else_=func.coalesce(
                            PurchaseDetailModel.quantity_accepted,
                            PurchaseDetailModel.quantity_received,
                        ),
                    )
                ),
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

        existing_by_order_detail = {
            detail.purchase_order_detail_id: detail for detail in model.details
        }
        replacement_details: list[PurchaseDetailModel] = []
        for detail in purchase.details:
            existing = existing_by_order_detail.pop(detail.purchase_order_detail_id, None)
            if existing is None:
                replacement_details.append(self._detail_model(purchase.company_id, detail))
                continue

            # Keep the persisted row (and its stable id) for existing order lines.
            # Replacing the whole relationship makes SQLAlchemy INSERT the new
            # children before deleting the old ones, violating the unique
            # (purchase_id, purchase_order_detail_id) constraint on draft edits.
            existing.product_id = detail.product_id
            existing.quantity_ordered = detail.quantity_ordered
            existing.quantity_received = detail.quantity_received
            existing.unit_id = detail.unit_id
            existing.unit_price = detail.unit_price
            existing.discount = detail.discount
            existing.subtotal = detail.subtotal
            existing.tax_rate = detail.tax_rate
            existing.tax_amount = detail.tax_amount
            existing.total = detail.total
            existing.quantity_accepted = detail.quantity_accepted
            existing.inventory_location_id = detail.inventory_location_id
            existing.notes = detail.notes
            replacement_details.append(existing)

        # Lines removed from the draft are orphaned and deleted by the existing
        # relationship cascade; unchanged lines remain attached to their rows.
        model.details = replacement_details
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

    async def complete_verification(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        *,
        accepted_quantities: dict[uuid.UUID, tuple[Decimal, uuid.UUID | None]],
        inventory_movement_id: uuid.UUID | None,
        valuation_conversion: PurchaseValuationConversion | None = None,
    ) -> Purchase | None:
        model = await self._get_model(company_id, purchase_id, for_update=True)
        if model is None:
            return None
        detail_ids = {detail.id for detail in model.details}
        if detail_ids != set(accepted_quantities):
            return None
        for detail in model.details:
            quantity, location_id = accepted_quantities[detail.id]
            detail.quantity_accepted = quantity
            detail.inventory_location_id = location_id
        model.inventory_movement_id = inventory_movement_id
        model.valuation_conversion = (
            valuation_conversion.to_dict() if valuation_conversion else None
        )
        model.status = PurchaseStatus.VERIFIED.value
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
            inventory_movement_id=purchase.inventory_movement_id,
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
            inventory_workflow=purchase.inventory_workflow.value,
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
            quantity_accepted=detail.quantity_accepted,
            inventory_location_id=detail.inventory_location_id,
            notes=detail.notes,
        )

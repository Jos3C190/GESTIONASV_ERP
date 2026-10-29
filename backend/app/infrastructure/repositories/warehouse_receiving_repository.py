"""Scoped operational projections of purchases for warehouse staff."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.ports.warehouse_receiving import WarehouseReceipt, WarehouseReceiptLine
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.retaceo import RetaceoModel


class SqlAlchemyWarehouseReceivingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending(
        self, company_id: uuid.UUID, warehouse_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[WarehouseReceipt], int]:
        conditions = (
            PurchaseModel.company_id == company_id,
            PurchaseModel.warehouse_id == warehouse_id,
            PurchaseModel.status == "received",
        )
        total = await self.session.scalar(
            select(func.count()).select_from(PurchaseModel).where(*conditions)
        )
        purchases = list(
            await self.session.scalars(
                select(PurchaseModel)
                .options(selectinload(PurchaseModel.details))
                .where(*conditions)
                .order_by(PurchaseModel.purchase_date, PurchaseModel.id)
                .offset(skip)
                .limit(limit)
            )
        )
        return await self._project(company_id, purchases), int(total or 0)

    async def get_receipt(
        self, company_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> WarehouseReceipt | None:
        purchase = await self.session.scalar(
            select(PurchaseModel)
            .options(selectinload(PurchaseModel.details))
            .where(PurchaseModel.company_id == company_id, PurchaseModel.id == purchase_id)
            .execution_options(populate_existing=True)
        )
        projected = await self._project(company_id, [purchase]) if purchase else []
        return projected[0] if projected else None

    async def _project(
        self, company_id: uuid.UUID, purchases: list[PurchaseModel]
    ) -> list[WarehouseReceipt]:
        product_ids = {detail.product_id for purchase in purchases for detail in purchase.details}
        products = {
            row.id_product: row
            for row in await self.session.scalars(
                select(ProductModel).where(
                    ProductModel.company_id == company_id, ProductModel.id_product.in_(product_ids)
                )
            )
        }
        unit_ids = {detail.unit_id for purchase in purchases for detail in purchase.details}
        units = {
            row.id_unit: row
            for row in await self.session.scalars(
                select(UnitModel).where(UnitModel.id_unit.in_(unit_ids))
            )
        }
        retaceos = list(
            await self.session.scalars(
                select(RetaceoModel).where(
                    RetaceoModel.company_id == company_id,
                    RetaceoModel.purchase_id.in_([purchase.id for purchase in purchases]),
                    RetaceoModel.status == "closed",
                )
            )
        )
        closed = {row.purchase_id: row.code for row in retaceos}
        return [
            WarehouseReceipt(
                id=purchase.id,
                code=purchase.code,
                warehouse_id=purchase.warehouse_id,
                purchase_date=purchase.purchase_date,
                status=purchase.status,
                ready=purchase.inventory_workflow == "receipt_before_retaceo"
                or purchase.id in closed,
                retaceo_code=closed.get(purchase.id),
                lines=tuple(
                    WarehouseReceiptLine(
                        id=detail.id,
                        product_name=products[detail.product_id].name,
                        product_sku=products[detail.product_id].sku,
                        unit_symbol=units[detail.unit_id].symbol,
                        quantity_received=detail.quantity_received,
                        quantity_accepted=detail.quantity_accepted,
                    )
                    for detail in purchase.details
                ),
            )
            for purchase in purchases
        ]

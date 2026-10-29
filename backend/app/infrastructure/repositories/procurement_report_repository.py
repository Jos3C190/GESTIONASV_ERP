"""Company-scoped descriptive data for read-only procurement exports."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.retaceo import Retaceo
from app.domain.entities.tabular_report import ProcurementReportContext
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.organization import Company
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.purchase_order import PurchaseOrderModel
from app.infrastructure.models.supplier import SupplierModel


class ProcurementReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def context(
        self, company_id: uuid.UUID, item: Retaceo | None = None
    ) -> ProcurementReportContext:
        company = (
            await self.session.execute(
                select(Company.name, Company.nit, Company.nrc).where(Company.id == company_id)
            )
        ).one()
        if item is None:
            return ProcurementReportContext(company.name, company.nit, company.nrc)
        purchase = (
            await self.session.execute(
                select(
                    PurchaseModel.code,
                    PurchaseOrderModel.code.label("order_code"),
                    SupplierModel.name.label("supplier_name"),
                )
                .join(PurchaseOrderModel, PurchaseOrderModel.id == PurchaseModel.purchase_order_id)
                .join(SupplierModel, SupplierModel.id_supplier == PurchaseModel.supplier_id)
                .where(
                    PurchaseModel.id == item.purchase_id,
                    PurchaseModel.company_id == company_id,
                    PurchaseOrderModel.company_id == company_id,
                    SupplierModel.company_id == company_id,
                )
            )
        ).one()
        products = (
            await self.session.execute(
                select(ProductModel.id_product, ProductModel.sku, ProductModel.name).where(
                    ProductModel.company_id == company_id,
                    ProductModel.id_product.in_([row.product_id for row in item.details]),
                )
            )
        ).all()
        units = (
            await self.session.execute(
                select(UnitModel.id_unit, UnitModel.name).where(
                    UnitModel.id_unit.in_([row.unit_id for row in item.details])
                )
            )
        ).all()
        return ProcurementReportContext(
            company.name,
            company.nit,
            company.nrc,
            purchase.code,
            purchase.order_code,
            purchase.supplier_name,
            {row.id_product: (row.sku, row.name) for row in products},
            dict(units),
        )

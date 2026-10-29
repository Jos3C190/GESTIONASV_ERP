"""Company-scoped labels for read-only inventory statements."""

import uuid
from contextlib import suppress
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import Branch, Company, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.retaceo import RetaceoModel
from app.infrastructure.models.sales_delivery import SalesDeliveryModel
from app.infrastructure.models.user import User


def _readable_reference(row, labels, retaceo_codes):
    reference = row.get("source_reference") or ""
    prefix, _, tail = reference.partition(":")
    if reference in labels:
        return labels[reference]
    if prefix in {"inventory_transfer", "adjustment", "customer-return", "customer_return"}:
        return tail.split(":", 1)[0]
    return retaceo_codes.get(row.get("retaceo_id")) or reference or "Sin referencia"


class InventoryKardexContextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def source_reference(self, company_id: uuid.UUID, reference: str) -> str:
        for prefix, model in (
            ("purchase-receipt", PurchaseModel),
            ("sales_delivery", SalesDeliveryModel),
        ):
            key = await self.session.scalar(
                select(model.id).where(model.company_id == company_id, model.code == reference)
            )
            if key:
                return f"{prefix}:{key}"
        return reference

    async def _receipt_lots(self, company_id, rows):
        ids = {row["movement_line_id"] for row in rows if row.get("movement_line_id")}
        if not ids:
            return {}
        line, unit, detail, lot = (
            InventoryMovementLineModel,
            InventoryHandlingUnitModel,
            InventoryLotDetailModel,
            InventoryLotModel,
        )
        return dict(
            (
                await self.session.execute(
                    select(line.id, func.coalesce(detail.code, lot.code, line.lot_code))
                    .select_from(line)
                    .outerjoin(
                        unit, and_(unit.company_id == company_id, unit.id == line.handling_unit_id)
                    )
                    .outerjoin(
                        detail,
                        and_(
                            detail.company_id == company_id,
                            detail.id
                            == func.coalesce(
                                line.inventory_lot_detail_id, unit.inventory_lot_detail_id
                            ),
                        ),
                    )
                    .outerjoin(
                        lot, and_(lot.company_id == company_id, lot.id == detail.inventory_lot_id)
                    )
                    .where(line.company_id == company_id, line.id.in_(ids))
                )
            ).all()
        )

    async def context(self, company_id: uuid.UUID, item_id=None, warehouse_id=None):
        company = (
            await self.session.execute(
                select(Company.name, Company.nit, Company.nrc).where(Company.id == company_id)
            )
        ).one()
        result = {
            "company_name": company.name,
            "nit": company.nit,
            "nrc": company.nrc,
            "product_name": None,
            "sku": None,
            "base_unit_symbol": None,
            "warehouse_name": None,
            "warehouse_code": None,
            "branch_name": None,
        }
        if item_id:
            row = (
                (
                    await self.session.execute(
                        select(
                            func.coalesce(
                                ProductVariantModel.name_override, ProductModel.name
                            ).label("product_name"),
                            func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("sku"),
                            UnitModel.symbol.label("base_unit_symbol"),
                        )
                        .select_from(InventoryItemModel)
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
                                == func.coalesce(
                                    InventoryItemModel.product_id, ProductVariantModel.product_id
                                ),
                            ),
                        )
                        .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                        .where(
                            InventoryItemModel.company_id == company_id,
                            InventoryItemModel.id == item_id,
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row:
                result.update(row)
        if warehouse_id:
            row = (
                (
                    await self.session.execute(
                        select(
                            Warehouse.name.label("warehouse_name"),
                            Warehouse.code.label("warehouse_code"),
                            Branch.name.label("branch_name"),
                        )
                        .outerjoin(
                            Branch,
                            and_(Branch.company_id == company_id, Branch.id == Warehouse.branch_id),
                        )
                        .where(Warehouse.company_id == company_id, Warehouse.id == warehouse_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row:
                result.update(row)
        return result

    async def enrich(self, company_id: uuid.UUID, rows: list[dict[str, Any]]) -> None:
        """Resolve opaque receipt/delivery IDs in batches; keep the original reference."""
        sources: dict[str, tuple[str, uuid.UUID]] = {}
        for row in rows:
            reference = row.get("source_reference") or ""
            prefix, _, tail = reference.partition(":")
            if prefix in {"purchase-receipt", "sales_delivery"}:
                with suppress(ValueError):
                    sources[reference] = (prefix, uuid.UUID(tail))
        labels: dict[str, str] = {}
        for prefix, model in (
            ("purchase-receipt", PurchaseModel),
            ("sales_delivery", SalesDeliveryModel),
        ):
            ids = {item_id for kind, item_id in sources.values() if kind == prefix}
            if ids:
                for key, code in (
                    await self.session.execute(
                        select(model.id, model.code).where(
                            model.company_id == company_id, model.id.in_(ids)
                        )
                    )
                ).all():
                    labels[f"{prefix}:{key}"] = code
        retaceos = {row["retaceo_id"] for row in rows if row.get("retaceo_id")}
        retaceo_codes = (
            dict(
                (
                    await self.session.execute(
                        select(RetaceoModel.id, RetaceoModel.code).where(
                            RetaceoModel.company_id == company_id, RetaceoModel.id.in_(retaceos)
                        )
                    )
                ).all()
            )
            if retaceos
            else {}
        )
        actors = {row["posted_by"] for row in rows if row.get("posted_by")}
        operators = (
            dict(
                (
                    await self.session.execute(
                        select(User.id, User.username).where(User.id.in_(actors))
                    )
                ).all()
            )
            if actors
            else {}
        )
        lots = await self._receipt_lots(company_id, rows)
        for row in rows:
            row["document_reference"] = _readable_reference(row, labels, retaceo_codes)
            row["operator"] = operators.get(row.get("posted_by")) or row.get("operator")
            if "inventory_delta" in row:
                row["receipt_lot_code"] = lots.get(row.get("movement_line_id"))
                quantity = row["quantity_base"]
                row["applied_unit_cost"] = (
                    abs(row["inventory_delta"] / quantity).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    if quantity and row["kind"] not in {"cost_adjustment", "supplier_credit"}
                    else None
                )

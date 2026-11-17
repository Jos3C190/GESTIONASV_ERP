"""Application service for the base sales workflow (no stock movements)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.application.audit.audit_service import AuditService
from app.core.exceptions import NotFoundError
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryItemModel, InventoryPackagingModel
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.sales import (
    SaleModel,
    SalesCustomerModel,
)
from app.infrastructure.repositories.sales_line_identity import unit_label, unit_name, unit_symbol
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

SV_TZ = ZoneInfo("America/El_Salvador")
ZERO_MONEY = Decimal("0.00")
IDEMPOTENCY_KEY_MAX_LENGTH = 120


def local_today() -> date:
    return datetime.now(SV_TZ).date()


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _decimal_string(value: Decimal | int | None) -> str | None:
    return str(value) if value is not None else None


class SalesService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    async def _audit(
        self,
        *,
        action: str,
        actor_id: uuid.UUID,
        company_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        request: Any,
        branch_id: uuid.UUID | None = None,
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
    ) -> None:
        await self.audit.record(
            action=action,
            user_id=actor_id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type=resource_type,
            resource_id=str(resource_id),
            before_state=before,
            after_state=after,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            required=True,
        )

    async def get_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> SalesCustomerModel:
        row = await self.session.scalar(
            select(SalesCustomerModel).where(
                SalesCustomerModel.company_id == company_id, SalesCustomerModel.id == customer_id
            )
        )
        if row is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        return row

    async def catalog(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        products = list(
            (
                await self.session.scalars(
                    select(ProductModel)
                    .where(
                        ProductModel.company_id == company_id,
                        ProductModel.is_active.is_(True),
                        ProductModel.can_sell.is_(True),
                        ProductModel.product_kind == "goods",
                        ProductModel.lifecycle_status == "active",
                        ProductModel.deleted_at.is_(None),
                    )
                    .order_by(ProductModel.name)
                )
            ).all()
        )
        result: list[dict[str, Any]] = []
        for product in products:
            if product.variant_mode == "standalone":
                item = await self.session.scalar(
                    select(InventoryItemModel).where(
                        InventoryItemModel.company_id == company_id,
                        InventoryItemModel.product_id == product.id_product,
                        InventoryItemModel.is_active.is_(True),
                    )
                )
                if item:
                    result.append(await self._catalog_option(product, None, item))
                continue
            variants = list(
                (
                    await self.session.scalars(
                        select(ProductVariantModel)
                        .where(
                            ProductVariantModel.company_id == company_id,
                            ProductVariantModel.product_id == product.id_product,
                            ProductVariantModel.is_active.is_(True),
                            ProductVariantModel.lifecycle_status == "active",
                        )
                        .order_by(ProductVariantModel.sku)
                    )
                ).all()
            )
            for variant in variants:
                item = await self.session.scalar(
                    select(InventoryItemModel).where(
                        InventoryItemModel.company_id == company_id,
                        InventoryItemModel.variant_id == variant.id,
                        InventoryItemModel.is_active.is_(True),
                    )
                )
                if item:
                    result.append(await self._catalog_option(product, variant, item))
        return result

    async def _catalog_option(
        self, product: ProductModel, variant: ProductVariantModel | None, item: InventoryItemModel
    ) -> dict[str, Any]:
        units: list[dict[str, Any]] = []
        package_rows = list(
            (
                await self.session.scalars(
                    select(InventoryPackagingModel)
                    .where(
                        InventoryPackagingModel.company_id == item.company_id,
                        InventoryPackagingModel.inventory_item_id == item.id,
                        InventoryPackagingModel.is_current.is_(True),
                        InventoryPackagingModel.is_active.is_(True),
                    )
                    .order_by(InventoryPackagingModel.name)
                )
            ).all()
        )
        base_unit = await unit_name(self.session, item.company_id, item.base_unit_id)
        units.append(
            {
                "unit_id": item.base_unit_id,
                "name": base_unit,
                "factor": "1",
                "packaging_definition_id": None,
                "packaging_version": None,
            }
        )
        for package in package_rows:
            if package.packaging_unit_id is None:
                continue
            symbol = await unit_symbol(self.session, item.company_id, package.packaging_unit_id)
            units.append(
                {
                    "unit_id": package.packaging_unit_id,
                    "name": unit_label(package.name, symbol),
                    "factor": str(package.base_quantity),
                    "packaging_definition_id": str(package.id),
                    "packaging_version": package.version,
                }
            )
        display_name = (
            (variant.name_override if variant and variant.name_override else None)
            or product.sales_name
            or product.name
        )
        return {
            "product_id": product.id_product,
            "variant_id": str(variant.id) if variant else None,
            "inventory_item_id": str(item.id),
            "sku": variant.sku if variant else product.sku,
            "name": display_name,
            "base_unit_id": item.base_unit_id,
            "base_unit_name": base_unit,
            "units": units,
        }

    async def get_sale(
        self, company_id: uuid.UUID, sale_id: uuid.UUID, *, lock: bool = False
    ) -> SaleModel:
        statement = select(SaleModel).where(
            SaleModel.company_id == company_id, SaleModel.id == sale_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            raise NotFoundError("Venta no encontrada.", code="sales_sale_not_found")
        return row

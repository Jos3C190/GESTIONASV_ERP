"""Identidad del artículo y la unidad de una línea de venta (producto, variante, empaque)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessRuleError, ValidationError
from app.domain.ports.sales_quotation_repository import LineIdentity
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.inventory import InventoryItemModel, InventoryPackagingModel
from app.infrastructure.models.product_variant import ProductVariantModel


def unit_label(name: str, symbol: str) -> str:
    """Nombre legible de la unidad sin repetir un símbolo que ya trae."""

    clean_name = name.strip()
    clean_symbol = symbol.strip()
    if not clean_name:
        return clean_symbol
    if not clean_symbol or clean_name == clean_symbol or clean_name.endswith(f"({clean_symbol})"):
        return clean_name
    return f"{clean_name} ({clean_symbol})"


async def _enabled_unit(session: AsyncSession, company_id: uuid.UUID, unit_id: int) -> UnitModel:
    row = await session.scalar(
        select(UnitModel)
        .join(
            CompanyUnitModel,
            and_(
                CompanyUnitModel.unit_id == UnitModel.id_unit,
                CompanyUnitModel.company_id == company_id,
            ),
        )
        .where(
            UnitModel.id_unit == unit_id,
            CompanyUnitModel.is_enabled.is_(True),
            UnitModel.is_active.is_(True),
        )
    )
    if row is None:
        raise BusinessRuleError(
            "La unidad de venta no está habilitada para la empresa.",
            code="sales_unit_not_enabled",
        )
    return row


async def unit_name(session: AsyncSession, company_id: uuid.UUID, unit_id: int) -> str:
    row = await _enabled_unit(session, company_id, unit_id)
    return unit_label(row.name, row.symbol)


async def unit_symbol(session: AsyncSession, company_id: uuid.UUID, unit_id: int) -> str:
    return (await _enabled_unit(session, company_id, unit_id)).symbol


async def _sellable_product(
    session: AsyncSession, company_id: uuid.UUID, product_id: int
) -> ProductModel:
    product = await session.scalar(
        select(ProductModel).where(
            ProductModel.company_id == company_id,
            ProductModel.id_product == product_id,
            ProductModel.is_active.is_(True),
            ProductModel.can_sell.is_(True),
            ProductModel.product_kind == "goods",
            ProductModel.lifecycle_status == "active",
            ProductModel.deleted_at.is_(None),
        )
    )
    if product is None:
        raise BusinessRuleError(
            "El producto no existe, está inactivo o no se puede vender.",
            code="sales_product_unavailable",
        )
    return product


async def _variant(
    session: AsyncSession,
    company_id: uuid.UUID,
    product: ProductModel,
    variant_id: uuid.UUID | None,
) -> ProductVariantModel | None:
    if product.variant_mode == "standalone":
        if variant_id is not None:
            raise ValidationError(
                "El producto independiente no admite una variante.", code="sales_variant_invalid"
            )
        return None
    if variant_id is None:
        raise ValidationError(
            "Selecciona una variante activa del producto.", code="sales_variant_required"
        )
    variant = await session.scalar(
        select(ProductVariantModel).where(
            ProductVariantModel.company_id == company_id,
            ProductVariantModel.product_id == product.id_product,
            ProductVariantModel.id == variant_id,
            ProductVariantModel.is_active.is_(True),
            ProductVariantModel.lifecycle_status == "active",
        )
    )
    if variant is None:
        raise BusinessRuleError(
            "La variante no existe o está inactiva.", code="sales_variant_unavailable"
        )
    return variant


async def line_identity(
    session: AsyncSession,
    company_id: uuid.UUID,
    product_id: int,
    variant_id: uuid.UUID | None,
    unit_id: int,
) -> LineIdentity:
    product = await _sellable_product(session, company_id, product_id)
    variant = await _variant(session, company_id, product, variant_id)
    item = await session.scalar(
        select(InventoryItemModel).where(
            InventoryItemModel.company_id == company_id,
            InventoryItemModel.product_id == product_id
            if variant_id is None
            else InventoryItemModel.variant_id == variant_id,
            InventoryItemModel.is_active.is_(True),
        )
    )
    if item is None:
        raise BusinessRuleError(
            "El artículo no tiene identidad inventariable configurada. Configura el producto "
            "en Inventario para poder cotizarlo.",
            code="sales_inventory_item_missing",
        )
    factor = Decimal("1")
    packaging_id: uuid.UUID | None = None
    packaging_version: int | None = None
    base_name = await unit_name(session, company_id, item.base_unit_id)
    name = base_name
    if unit_id != item.base_unit_id:
        packages = list(
            (
                await session.scalars(
                    select(InventoryPackagingModel).where(
                        InventoryPackagingModel.company_id == company_id,
                        InventoryPackagingModel.inventory_item_id == item.id,
                        InventoryPackagingModel.packaging_unit_id == unit_id,
                        InventoryPackagingModel.is_current.is_(True),
                        InventoryPackagingModel.is_active.is_(True),
                    )
                )
            ).all()
        )
        if len(packages) != 1:
            raise BusinessRuleError(
                "La unidad elegida no tiene una equivalencia vigente para este producto.",
                code="sales_unit_conversion_missing",
            )
        package = packages[0]
        factor = package.base_quantity
        packaging_id = package.id
        packaging_version = package.version
        name = unit_label(package.name, await unit_symbol(session, company_id, unit_id))
    return LineIdentity(
        product_id=product_id,
        variant_id=variant_id,
        inventory_item_id=item.id,
        packaging_definition_id=packaging_id,
        packaging_version=packaging_version,
        unit_id=unit_id,
        base_unit_id=item.base_unit_id,
        unit_factor=factor,
        product_sku=variant.sku if variant else product.sku,
        product_name=(
            (variant.name_override if variant and variant.name_override else None)
            or product.sales_name
            or product.name
        ),
        unit_name=name,
        base_unit_name=base_name,
    )

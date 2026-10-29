"""Read balances without adding HU quantities; atomic individual stock opening."""

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.inventory import InventoryUseCases
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.models.organization import Location
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)


class SqlAlchemyInventoryWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def stock(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        q: str,
        location_id: uuid.UUID | None,
        stock_status: str | None,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        name = func.coalesce(
            ProductVariantModel.name_override, ProductModel.name, "Producto sin nombre"
        )
        sku = func.coalesce(ProductVariantModel.sku, ProductModel.sku)
        b = InventoryBalanceModel
        statement = (
            select(
                b.inventory_item_id,
                name.label("product_name"),
                sku.label("sku"),
                func.coalesce(UnitModel.symbol, "u").label("base_unit_symbol"),
                b.location_id,
                Location.code.label("location_code"),
                b.stock_status,
                b.lot_code,
                b.expiry_date,
                b.quantity_base,
            )
            .join(
                InventoryItemModel,
                and_(
                    InventoryItemModel.company_id == b.company_id,
                    InventoryItemModel.id == b.inventory_item_id,
                ),
            )
            .outerjoin(
                ProductVariantModel,
                and_(
                    ProductVariantModel.company_id == b.company_id,
                    ProductVariantModel.id == InventoryItemModel.variant_id,
                ),
            )
            .outerjoin(
                ProductModel,
                and_(
                    ProductModel.company_id == b.company_id,
                    ProductModel.id_product
                    == func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id),
                ),
            )
            .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
            .join(
                Location,
                and_(Location.id == b.location_id, Location.warehouse_id == b.warehouse_id),
            )
            .where(b.company_id == company_id, b.warehouse_id == warehouse_id, b.quantity_base > 0)
        )
        for word in q.strip().split():
            statement = statement.where(
                or_(
                    name.icontains(word, autoescape=True),
                    sku.icontains(word, autoescape=True),
                    b.lot_code.icontains(word, autoescape=True),
                    Location.code.icontains(word, autoescape=True),
                )
            )
        if location_id:
            statement = statement.where(b.location_id == location_id)
        if stock_status:
            statement = statement.where(b.stock_status == stock_status)
        total = await self.session.scalar(select(func.count()).select_from(statement.subquery()))
        rows = (
            (
                await self.session.execute(
                    statement.order_by(name, b.location_id, b.id)
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .mappings()
            .all()
        )
        return {
            "items": [dict(row) for row in rows],
            "total": total or 0,
            "page": page,
            "size": size,
        }

    async def open_product(
        self, *, company_id: uuid.UUID, actor_id: uuid.UUID, command: dict[str, Any]
    ) -> dict[str, Any]:
        valuation = SqlAlchemyInventoryValuationRepository(self.session)
        await valuation.lock(company_id)
        item_id = command["inventory_item_id"]
        item = await self.session.scalar(
            select(InventoryItemModel)
            .where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == item_id,
                InventoryItemModel.is_active.is_(True),
            )
            .with_for_update()
        )
        if item is None:
            raise InventoryOperationError(
                "Producto inventariable no encontrado.",
                code="opening_item_not_found",
                status_code=404,
            )
        today = datetime.now(ZoneInfo("America/El_Salvador")).date()
        setting = await valuation.settings(company_id)
        if (
            setting is None
            or command["operational_date"]
            < setting.opened_at.astimezone(ZoneInfo("America/El_Salvador")).date()
            or command["operational_date"] > today
        ):
            raise InventoryOperationError(
                "Use una fecha entre el corte de valoración y hoy.", code="opening_date_invalid"
            )
        if command.get("expiry_date") and command["expiry_date"] < command["operational_date"]:
            raise InventoryOperationError(
                "El vencimiento no puede ser anterior al ingreso.", code="opening_expiry_invalid"
            )
        location = await self.session.scalar(
            select(Location).where(
                Location.id == command["location_id"],
                Location.warehouse_id == command["warehouse_id"],
                Location.is_active.is_(True),
                Location.deleted_at.is_(None),
                Location.lifecycle_status == "active",
                Location.storage_eligible.is_(True),
            )
        )
        if location is None:
            raise InventoryOperationError(
                "Seleccione una ubicación de almacenamiento activa de esta bodega.",
                code="opening_location_invalid",
            )
        key = f"product-opening:{command['idempotency_key']}"
        existing = await self.session.scalar(
            select(InventoryMovementModel).where(
                InventoryMovementModel.company_id == company_id,
                InventoryMovementModel.idempotency_key == key,
            )
        )
        if existing is None:
            # The same company lock is taken by all physical and valued commands.
            history = [
                select(InventoryMovementLineModel.id).where(
                    InventoryMovementLineModel.company_id == company_id,
                    InventoryMovementLineModel.inventory_item_id == item_id,
                ),
                select(InventoryValuationEntryModel.id).where(
                    InventoryValuationEntryModel.company_id == company_id,
                    InventoryValuationEntryModel.inventory_item_id == item_id,
                ),
                select(InventoryHandlingUnitModel.id).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.inventory_item_id == item_id,
                ),
                select(InventoryBalanceModel.id).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item_id,
                ),
            ]
            for query in history:
                if await self.session.scalar(select(exists(query))):
                    raise InventoryOperationError(
                        "El producto ya tiene historial o unidades en preparación. Use un ajuste documentado.",
                        code="opening_history_exists",
                        status_code=409,
                    )
        result = await InventoryUseCases(SqlAlchemyInventoryRepository(self.session)).post_movement(
            company_id=company_id,
            actor_id=actor_id,
            movement_type="opening",
            idempotency_key=key,
            source_reference=f"SI:{command['document_reference']}",
            lines=[
                {
                    "inventory_item_id": item_id,
                    "quantity_base": command["quantity_base"],
                    "from_location_id": None,
                    "to_location_id": location.id,
                    "to_stock_status": "available",
                    "actual_measures": {
                        "gross_weight_kg": command["gross_weight_kg"],
                        "volume_m3": command["volume_m3"],
                        "length_m": None,
                        "width_m": None,
                        "height_m": None,
                    },
                    "lot_code": command.get("lot_code"),
                    "expiry_date": command.get("expiry_date"),
                    "valuation_kind": "opening",
                    "valuation_value": (command["quantity_base"] * command["unit_cost"]).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    ),
                    "operational_date": command["operational_date"],
                    "accounting_date": command["operational_date"],
                    "opening_reason": command["reason"],
                }
            ],
        )
        return {**result, "created": existing is None}

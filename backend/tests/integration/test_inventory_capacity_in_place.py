"""Un cambio de estado sin moverse de ubicación no cuenta dos veces la misma unidad.

La sesión trabaja con ``autoflush=False``: el movimiento descuenta el saldo del origen en memoria
y la revisión de capacidad lee la ocupación de la base. Sin volcar antes ese descuento, la unidad
que sale seguía ocupando la ubicación y además se sumaba como entrada (V9b: impedía fraccionar
cualquier pallet que ocupara más de la mitad de su ubicación).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import InventoryBalanceModel, InventoryItemModel
from app.infrastructure.models.inventory_valuation import InventoryValuationSettingModel
from app.infrastructure.models.organization import Branch, Location, Warehouse, WarehouseCategory
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from sqlalchemy import and_, select

from tests.e2e.conftest import get_test_company_id

pytestmark = pytest.mark.integration


async def test_status_change_in_place_does_not_double_count_capacity() -> None:
    suffix = uuid.uuid4().hex
    company_id = await get_test_company_id()
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            category = await session.scalar(
                select(WarehouseCategory)
                .where(
                    WarehouseCategory.company_id == company_id,
                    WarehouseCategory.is_active.is_(True),
                    WarehouseCategory.deleted_at.is_(None),
                )
                .limit(1)
            )
            if category is None:
                category = WarehouseCategory(
                    company_id=company_id, name=f"IT-CAP-{suffix[:8]}", is_active=True
                )
                session.add(category)
                await session.flush()
            branch_id = await session.scalar(
                select(Branch.id)
                .where(
                    Branch.company_id == company_id,
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                )
                .order_by(Branch.created_at, Branch.id)
                .limit(1)
            )
            assert branch_id is not None
            warehouse = Warehouse(
                company_id=company_id,
                branch_id=branch_id,
                warehouse_category_id=category.id,
                name=f"IT Capacidad {suffix[:8]}",
                code=f"ITCAP-{suffix[:8]}",
                is_central=False,
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            session.add(warehouse)
            await session.flush()
            # 15 kg certificados: cabe una unidad de 10 kg, no dos.
            location = Location(
                warehouse_id=warehouse.id,
                code=f"IT-CAP-{suffix[:8]}",
                aisle="01",
                rack="01",
                level="01",
                position="01",
                storage_eligible=True,
                capacity_enforcement_mode="enforce",
                certified_max_weight_kg=Decimal("15"),
                operational_max_weight_kg=Decimal("14"),
                certified_usable_volume_m3=Decimal("1"),
                operational_usable_volume_m3=Decimal("1"),
            )
            actor = User(
                username=f"inventory-capacity-{suffix[:12]}",
                email=f"inventory-capacity-{suffix[:12]}@example.test",
                password_hash="not-used-by-this-repository-test",
                is_superuser=True,
            )
            session.add_all([location, actor])
            await session.flush()
            product = await session.scalar(
                select(ProductModel)
                .join(
                    CompanyUnitModel,
                    and_(
                        CompanyUnitModel.company_id == ProductModel.company_id,
                        CompanyUnitModel.unit_id == ProductModel.purchase_unit,
                    ),
                )
                .outerjoin(
                    InventoryItemModel,
                    and_(
                        InventoryItemModel.company_id == ProductModel.company_id,
                        InventoryItemModel.product_id == ProductModel.id_product,
                    ),
                )
                .where(
                    ProductModel.company_id == company_id,
                    ProductModel.deleted_at.is_(None),
                    ProductModel.is_active.is_(True),
                    ProductModel.lifecycle_status == "active",
                    ProductModel.can_purchase.is_(True),
                    CompanyUnitModel.is_enabled.is_(True),
                    InventoryItemModel.id.is_(None),
                )
                .order_by(ProductModel.id_product)
                .limit(1)
            )
            assert product is not None
            item = InventoryItemModel(
                company_id=company_id,
                product_id=product.id_product,
                variant_id=None,
                base_unit_id=product.purchase_unit,
                is_active=True,
            )
            session.add(item)
            session.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=datetime.now(UTC),
                    opened_by=actor.id,
                    opening_reference=f"IT-CAP-CUT-{suffix}",
                    opening_fingerprint="d" * 64,
                    physical_snapshot=[],
                )
            )
            await session.flush()

            inventory = SqlAlchemyInventoryRepository(session)
            received = await inventory.post_movement(
                company_id=company_id,
                idempotency_key=f"it-capacity-receipt-{suffix}",
                movement_type="receipt",
                source_reference=f"integration-capacity:{suffix}",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "to_location_id": location.id,
                        "to_stock_status": "available",
                        "quantity_base": Decimal("10"),
                        "valuation_currency": "USD",
                        "valuation_value": Decimal("100"),
                        "handling_unit_code": f"IT-CAP-HU-{suffix}",
                        "actual_measures": {
                            "gross_weight_kg": Decimal("10"),
                            "length_m": Decimal("0.2"),
                            "width_m": Decimal("0.2"),
                            "height_m": Decimal("0.2"),
                        },
                    }
                ],
                actor_id=actor.id,
            )
            unit_id = received["lines"][0]["handling_unit_id"]

            # Pasar la unidad a cuarentena sin moverla: 10 kg siguen siendo 10 kg.
            await inventory.post_movement(
                company_id=company_id,
                idempotency_key=f"it-capacity-quarantine-{suffix}",
                movement_type="transfer",
                source_reference=f"integration-capacity:{suffix}:quarantine",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "handling_unit_id": unit_id,
                        "from_location_id": location.id,
                        "to_location_id": location.id,
                        "from_stock_status": "available",
                        "to_stock_status": "quarantine",
                        "quantity_base": Decimal("10"),
                    }
                ],
                actor_id=actor.id,
            )
            await session.flush()
            balances = {
                row.stock_status: row.occupied_weight_kg
                for row in await session.scalars(
                    select(InventoryBalanceModel).where(
                        InventoryBalanceModel.location_id == location.id
                    )
                )
            }
            assert balances.get("available", Decimal("0")) == Decimal("0")
            assert balances["quarantine"] == Decimal("10")
        finally:
            await transaction.rollback()
    await dispose_engine()

"""PostgreSQL integration checks for inventory-movement idempotency."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementModel,
)
from app.infrastructure.models.organization import Branch, Location, Warehouse, WarehouseCategory
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from sqlalchemy import and_, func, select

from tests.e2e.conftest import get_test_company_id

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_quarantine_release_retry_reuses_one_postgres_movement_and_balance() -> None:
    suffix = uuid.uuid4().hex
    receipt_key = f"it-receipt-{suffix}"
    release_key = f"it-release-{suffix}"
    company_id = await get_test_company_id()

    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            actor = User(
                username=f"inventory-retry-{suffix[:16]}",
                email=f"inventory-retry-{suffix[:16]}@example.test",
                password_hash="not-used-by-this-repository-test",
            )
            session.add(actor)
            await session.flush()
            actor_id = actor.id
            warehouse_id = await session.scalar(
                select(Warehouse.id)
                .join(Branch, Branch.id == Warehouse.branch_id)
                .where(
                    Branch.company_id == company_id,
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                    Warehouse.is_active.is_(True),
                    Warehouse.operational_status == "active",
                    Warehouse.storage_eligible.is_(True),
                    Warehouse.deleted_at.is_(None),
                )
                .order_by(Warehouse.created_at, Warehouse.id)
                .limit(1)
            )
            assert warehouse_id is not None
            locations = list(
                (
                    await session.scalars(
                        select(Location).where(
                            Location.warehouse_id == warehouse_id,
                            Location.is_active.is_(True),
                            Location.lifecycle_status == "active",
                            Location.deleted_at.is_(None),
                        )
                    )
                ).all()
            )
            source = next(
                (location for location in locations if location.location_type == "receiving"),
                None,
            )
            destination = next(
                (location for location in locations if location.storage_eligible),
                None,
            )
            assert source is not None
            assert destination is not None

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
            await session.flush()

            repository = SqlAlchemyInventoryRepository(session)
            receipt = await repository.post_movement(
                company_id=company_id,
                idempotency_key=receipt_key,
                movement_type="receipt",
                source_reference=f"integration-test-receipt:{suffix}",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "to_location_id": source.id,
                        "to_stock_status": "quarantine",
                        "quantity_base": Decimal("1"),
                        "handling_unit_code": f"IT-HU-{suffix}",
                        "actual_measures": {
                            "gross_weight_kg": Decimal("1"),
                            "length_m": Decimal("0.1"),
                            "width_m": Decimal("0.1"),
                            "height_m": Decimal("0.1"),
                        },
                    }
                ],
                actor_id=actor_id,
            )
            handling_unit_id = receipt["lines"][0]["handling_unit_id"]
            assert isinstance(handling_unit_id, uuid.UUID)

            release_reference = f"quarantine-release:{handling_unit_id}:{release_key}"
            release_line = {
                "inventory_item_id": item.id,
                "handling_unit_id": handling_unit_id,
                "from_location_id": source.id,
                "to_location_id": destination.id,
                "from_stock_status": "quarantine",
                "to_stock_status": "available",
                "quantity_base": Decimal("1"),
            }
            first_release = await repository.post_movement(
                company_id=company_id,
                idempotency_key=release_key,
                movement_type="putaway",
                source_reference=release_reference,
                lines=[release_line],
                actor_id=actor_id,
            )

            # A new repository instance must read the persisted ledger row and reuse it.
            retried_release = await SqlAlchemyInventoryRepository(session).post_movement(
                company_id=company_id,
                idempotency_key=release_key,
                movement_type="putaway",
                source_reference=release_reference,
                lines=[release_line],
                actor_id=actor_id,
            )
            assert retried_release["id"] == first_release["id"]

            movement_count = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == company_id,
                    InventoryMovementModel.idempotency_key == release_key,
                )
            )
            available_balance = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item.id,
                    InventoryBalanceModel.location_id == destination.id,
                    InventoryBalanceModel.stock_status == "available",
                )
            )
            quarantine_balance = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item.id,
                    InventoryBalanceModel.location_id == source.id,
                    InventoryBalanceModel.stock_status == "quarantine",
                )
            )
            assert movement_count == 1
            assert available_balance is not None
            assert available_balance.quantity_base == Decimal("1")
            assert quarantine_balance is not None
            assert quarantine_balance.quantity_base == Decimal("0")
        finally:
            # The test ledger is append-only; rollback removes its synthetic fixture safely.
            await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_partial_branch_transfer_preserves_remainder_and_records_receipt_count() -> None:
    suffix = uuid.uuid4().hex
    company_id = await get_test_company_id()

    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            actor = User(
                username=f"inventory-split-{suffix[:16]}",
                email=f"inventory-split-{suffix[:16]}@example.test",
                password_hash="not-used-by-this-repository-test",
            )
            session.add(actor)
            await session.flush()

            category_id = await session.scalar(
                select(WarehouseCategory.id)
                .where(
                    WarehouseCategory.company_id == company_id,
                    WarehouseCategory.is_active.is_(True),
                    WarehouseCategory.deleted_at.is_(None),
                )
                .order_by(WarehouseCategory.id)
                .limit(1)
            )
            if category_id is None:
                category = WarehouseCategory(
                    company_id=company_id,
                    name=f"IT-{suffix[:12]}",
                    is_active=True,
                )
                session.add(category)
                await session.flush()
                category_id = category.id

            headquarters_branch_id = await session.scalar(
                select(Branch.id)
                .where(
                    Branch.company_id == company_id,
                    Branch.is_headquarters.is_(True),
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                )
                .order_by(Branch.created_at, Branch.id)
                .limit(1)
            )
            branch_id = await session.scalar(
                select(Branch.id)
                .where(
                    Branch.company_id == company_id,
                    Branch.is_headquarters.is_(False),
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                )
                .order_by(Branch.created_at, Branch.id)
                .limit(1)
            )
            assert headquarters_branch_id is not None
            assert branch_id is not None

            central_warehouse = Warehouse(
                company_id=company_id,
                branch_id=headquarters_branch_id,
                warehouse_category_id=category_id,
                name=f"IT Central {suffix[:8]}",
                code=f"ITC-{suffix[:8]}",
                is_central=True,
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            branch_warehouse = Warehouse(
                company_id=company_id,
                branch_id=branch_id,
                warehouse_category_id=category_id,
                name=f"IT Sucursal {suffix[:8]}",
                code=f"ITS-{suffix[:8]}",
                is_central=False,
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            session.add_all([central_warehouse, branch_warehouse])
            await session.flush()

            central_location = Location(
                warehouse_id=central_warehouse.id,
                code=f"IT-C-{suffix[:8]}",
                aisle="01",
                rack="01",
                level="01",
                position="01",
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            branch_location = Location(
                warehouse_id=branch_warehouse.id,
                code=f"IT-B-{suffix[:8]}",
                aisle="01",
                rack="01",
                level="01",
                position="01",
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            session.add_all([central_location, branch_location])
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
            await session.flush()

            repository = SqlAlchemyInventoryRepository(session)
            receipt = await repository.post_movement(
                company_id=company_id,
                idempotency_key=f"split-receipt-{suffix}",
                movement_type="receipt",
                source_reference=f"integration-test-receipt:{suffix}",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "to_location_id": central_location.id,
                        "to_stock_status": "available",
                        "quantity_base": Decimal("100"),
                        "handling_unit_code": f"IT-SPLIT-{suffix}",
                        "actual_measures": {
                            "gross_weight_kg": Decimal("100"),
                            "length_m": Decimal("0.5"),
                            "width_m": Decimal("0.5"),
                            "height_m": Decimal("0.4"),
                        },
                    }
                ],
                actor_id=actor.id,
            )
            parent_id = receipt["lines"][0]["handling_unit_id"]
            assert isinstance(parent_id, uuid.UUID)

            dispatch = await repository.post_movement(
                company_id=company_id,
                idempotency_key=f"split-dispatch-{suffix}",
                movement_type="transfer",
                source_reference=f"TR-TEST · Solicitud SCR-TEST-{suffix[:8]}",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "handling_unit_id": parent_id,
                        "from_location_id": central_location.id,
                        "to_location_id": branch_location.id,
                        "from_stock_status": "available",
                        "to_stock_status": "in_transit",
                        "quantity_base": Decimal("40"),
                    }
                ],
                actor_id=actor.id,
            )
            transit_child_id = dispatch["lines"][0]["handling_unit_id"]
            assert isinstance(transit_child_id, uuid.UUID)

            dispatched_parent = await session.get(InventoryHandlingUnitModel, parent_id)
            transit_child = await session.get(InventoryHandlingUnitModel, transit_child_id)
            assert dispatched_parent is not None
            assert transit_child is not None
            assert dispatched_parent.quantity_base == Decimal("60")
            assert dispatched_parent.measurement_source == "split_estimate"
            assert transit_child.origin_handling_unit_id == parent_id
            assert transit_child.quantity_base == Decimal("40")
            assert transit_child.stock_status == "in_transit"

            received = await repository.post_movement(
                company_id=company_id,
                idempotency_key=f"split-receive-{suffix}",
                movement_type="transfer",
                source_reference=f"RECIBIDO · TR-TEST-{suffix[:8]}",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "handling_unit_id": transit_child_id,
                        "from_location_id": branch_location.id,
                        "to_location_id": branch_location.id,
                        "from_stock_status": "in_transit",
                        "to_stock_status": "quarantine",
                        "quantity_base": Decimal("35"),
                    }
                ],
                actor_id=actor.id,
            )
            received_child_id = received["lines"][0]["handling_unit_id"]
            assert isinstance(received_child_id, uuid.UUID)

            transit_remainder = await session.get(InventoryHandlingUnitModel, transit_child_id)
            received_child = await session.get(InventoryHandlingUnitModel, received_child_id)
            central_balance = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item.id,
                    InventoryBalanceModel.location_id == central_location.id,
                    InventoryBalanceModel.stock_status == "available",
                )
            )
            transit_balance = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item.id,
                    InventoryBalanceModel.location_id == branch_location.id,
                    InventoryBalanceModel.stock_status == "in_transit",
                )
            )
            quarantine_balance = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.inventory_item_id == item.id,
                    InventoryBalanceModel.location_id == branch_location.id,
                    InventoryBalanceModel.stock_status == "quarantine",
                )
            )

            assert transit_remainder is not None
            assert received_child is not None
            assert central_balance is not None
            assert transit_balance is not None
            assert quarantine_balance is not None
            assert transit_remainder.quantity_base == Decimal("5")
            assert transit_remainder.stock_status == "in_transit"
            assert received_child.origin_handling_unit_id == transit_child_id
            assert received_child.quantity_base == Decimal("35")
            assert received_child.stock_status == "quarantine"
            assert received_child.measurement_status == "incomplete"
            assert received_child.occupied_weight_kg == Decimal("0")
            assert received_child.occupied_volume_m3 == Decimal("0")
            assert central_balance.quantity_base == Decimal("60")
            assert transit_balance.quantity_base == Decimal("5")
            assert quarantine_balance.quantity_base == Decimal("35")
        finally:
            await transaction.rollback()
    await dispose_engine()

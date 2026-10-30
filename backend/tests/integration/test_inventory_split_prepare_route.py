"""PostgreSQL integration checks for the available-unit split command."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.api.v1 import company_access
from app.api.v1.routers import inventory as inventory_router
from app.api.v1.schemas.inventory import HandlingUnitSplitPrepareIn
from app.application.audit.audit_service import AuditService
from app.core.exceptions import AppError
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.organization import (
    Branch,
    Location,
    Warehouse,
    WarehouseCategory,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from sqlalchemy import and_, func, select
from starlette.requests import Request

from tests.e2e.conftest import get_test_company_id

pytestmark = pytest.mark.integration


def _request(company_id: uuid.UUID) -> Request:
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/inventory/handling-units/test/prepare-split",
            "raw_path": b"/api/v1/inventory/handling-units/test/prepare-split",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
    )
    company_access.set_effective_company_id(request, company_id)
    return request


@pytest.mark.asyncio
async def test_prepare_split_route_replays_conflicts_and_rolls_back_atomically(monkeypatch) -> None:
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
                .order_by(WarehouseCategory.id)
                .limit(1)
            )
            if category is None:
                category = WarehouseCategory(
                    company_id=company_id,
                    name=f"IT-SPLIT-{suffix[:8]}",
                    is_active=True,
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
                name=f"IT Split {suffix[:8]}",
                code=f"ITSPL-{suffix[:8]}",
                is_central=False,
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            session.add(warehouse)
            await session.flush()
            source_location = Location(
                warehouse_id=warehouse.id,
                code=f"IT-SRC-{suffix[:8]}",
                aisle="01",
                rack="01",
                level="01",
                position="01",
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            destination_location = Location(
                warehouse_id=warehouse.id,
                code=f"IT-DST-{suffix[:8]}",
                aisle="01",
                rack="01",
                level="01",
                position="02",
                storage_eligible=True,
                capacity_enforcement_mode="disabled",
            )
            actor = User(
                username=f"inventory-split-route-{suffix[:12]}",
                email=f"inventory-split-route-{suffix[:12]}@example.test",
                password_hash="not-used-by-this-repository-test",
                is_superuser=True,
            )
            session.add_all([source_location, destination_location, actor])
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
            session.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=datetime.now(UTC),
                    opened_by=actor.id,
                    opening_reference=f"IT-SPLIT-CUT-{suffix}",
                    opening_fingerprint="c" * 64,
                    physical_snapshot=[],
                )
            )
            await session.flush()

            inventory = SqlAlchemyInventoryRepository(session)

            async def receive(code: str, quantity: Decimal) -> uuid.UUID:
                result = await inventory.post_movement(
                    company_id=company_id,
                    idempotency_key=f"it-split-receipt-{suffix}-{code}",
                    movement_type="receipt",
                    source_reference=f"integration-split:{suffix}:{code}",
                    lines=[
                        {
                            "inventory_item_id": item.id,
                            "to_location_id": source_location.id,
                            "to_stock_status": "available",
                            "quantity_base": quantity,
                            "valuation_currency": "USD",
                            "valuation_value": quantity * Decimal("10"),
                            "handling_unit_code": f"IT-SPLIT-HU-{suffix}-{code}",
                            "actual_measures": {
                                "gross_weight_kg": quantity,
                                "length_m": Decimal("0.2"),
                                "width_m": Decimal("0.2"),
                                "height_m": Decimal("0.2"),
                            },
                        }
                    ],
                    actor_id=actor.id,
                )
                return result["lines"][0]["handling_unit_id"]

            parent_id = await receive("main", Decimal("10"))

            async def allow_move_permission(checker, current, company, code) -> None:
                assert current.id == actor.id
                assert company == company_id
                assert code == "inventory:move"

            monkeypatch.setattr(
                inventory_router, "_require_dynamic_permission", allow_move_permission
            )
            body = HandlingUnitSplitPrepareIn(
                idempotency_key=f"it-prepare-split-{suffix}",
                split_quantity_base=Decimal("4"),
                destination_location_id=destination_location.id,
            )
            request = _request(company_id)
            audit = AuditService(SqlAlchemyAuditRepository(session))
            first = await inventory_router.prepare_handling_unit_split(
                handling_unit_id=parent_id,
                body=body,
                request=request,
                session=session,
                current=actor,
                checker=object(),
                audit=audit,
            )
            replay = await inventory_router.prepare_handling_unit_split(
                handling_unit_id=parent_id,
                body=body,
                request=request,
                session=session,
                current=actor,
                checker=object(),
                audit=audit,
            )
            assert replay.split_handling_unit_id == first.split_handling_unit_id
            assert replay.remainder_handling_unit_id == first.remainder_handling_unit_id
            assert replay.quarantine_movement.id == first.quarantine_movement.id
            assert replay.split_movement.id == first.split_movement.id
            assert first.remainder_quantity_base == Decimal("6")
            assert first.split_quantity_base == Decimal("4")
            assert first.stock_status.value == "quarantine"

            key_digest = hashlib.sha256(f"{company_id}:{body.idempotency_key}".encode()).hexdigest()
            movement_keys = [
                f"hu-split:{key_digest}:quarantine",
                f"hu-split:{key_digest}:split",
            ]
            assert (
                await session.scalar(
                    select(func.count(InventoryMovementModel.id)).where(
                        InventoryMovementModel.company_id == company_id,
                        InventoryMovementModel.idempotency_key.in_(movement_keys),
                    )
                )
                == 2
            )
            assert (
                await session.scalar(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.company_id == company_id,
                        AuditLog.action == "PREPARE_SPLIT",
                        AuditLog.resource_id == str(parent_id),
                    )
                )
                == 1
            )
            parent = await session.get(InventoryHandlingUnitModel, parent_id)
            child = await session.get(InventoryHandlingUnitModel, first.split_handling_unit_id)
            assert parent is not None
            assert child is not None
            assert parent.quantity_base == Decimal("6")
            assert child.quantity_base == Decimal("4")
            assert parent.stock_status == child.stock_status == "quarantine"
            assert child.origin_handling_unit_id == parent_id
            listed = await inventory.list_handling_units(
                company_id=company_id, warehouse_id=warehouse.id
            )
            assert {row["id"] for row in listed} == {parent_id, child.id}
            for row in listed:
                assert row["product_name"] == product.name
                assert row["product_sku"] == product.sku
                assert row["base_unit_name"]
                assert row["base_unit_symbol"]
            assert (
                await inventory.list_handling_units(
                    company_id=uuid.uuid4(), warehouse_id=warehouse.id
                )
                == []
            )
            balances = list(
                (
                    await session.scalars(
                        select(InventoryBalanceModel).where(
                            InventoryBalanceModel.company_id == company_id,
                            InventoryBalanceModel.inventory_item_id == item.id,
                            InventoryBalanceModel.location_id.in_(
                                [source_location.id, destination_location.id]
                            ),
                            InventoryBalanceModel.stock_status == "quarantine",
                        )
                    )
                ).all()
            )
            assert sum((balance.quantity_base for balance in balances), Decimal("0")) == Decimal(
                "10"
            )
            split_valuation = await session.get(InventoryCostAverageModel, (company_id, item.id))
            assert split_valuation is not None
            assert split_valuation.quantity_base == Decimal("10.000000")
            assert split_valuation.inventory_value == Decimal("100.000000")
            assert split_valuation.average_unit_cost == Decimal("10.000000")

            conflicting_body = body.model_copy(update={"split_quantity_base": Decimal("5")})
            with pytest.raises(AppError) as conflict:
                await inventory_router.prepare_handling_unit_split(
                    handling_unit_id=parent_id,
                    body=conflicting_body,
                    request=request,
                    session=session,
                    current=actor,
                    checker=object(),
                    audit=audit,
                )
            assert getattr(conflict.value, "status_code", None) == 409

            rollback_parent_id = await receive("rollback", Decimal("5"))
            actual_use_cases = inventory_router._use_cases

            class FailOnSecondMovement:
                def __init__(self, delegate) -> None:
                    self.delegate = delegate
                    self.calls = 0

                async def post_movement(self, **kwargs):
                    self.calls += 1
                    if self.calls == 2:
                        raise InventoryOperationError(
                            "Synthetic second movement failure.",
                            code="synthetic_split_failure",
                            status_code=409,
                        )
                    return await self.delegate.post_movement(**kwargs)

            monkeypatch.setattr(
                inventory_router,
                "_use_cases",
                lambda active_session: FailOnSecondMovement(actual_use_cases(active_session)),
            )
            rollback_key = f"it-prepare-split-rollback-{suffix}"
            rollback_body = HandlingUnitSplitPrepareIn(
                idempotency_key=rollback_key,
                split_quantity_base=Decimal("2"),
                destination_location_id=destination_location.id,
            )
            with pytest.raises(AppError) as rollback_error:
                await inventory_router.prepare_handling_unit_split(
                    handling_unit_id=rollback_parent_id,
                    body=rollback_body,
                    request=request,
                    session=session,
                    current=actor,
                    checker=object(),
                    audit=audit,
                )
            assert getattr(rollback_error.value, "status_code", None) == 409
            unmodified_parent = await session.get(InventoryHandlingUnitModel, rollback_parent_id)
            assert unmodified_parent is not None
            assert unmodified_parent.quantity_base == Decimal("5")
            assert unmodified_parent.stock_status == "available"
            rollback_digest = hashlib.sha256(f"{company_id}:{rollback_key}".encode()).hexdigest()
            assert (
                await session.scalar(
                    select(func.count(InventoryMovementModel.id)).where(
                        InventoryMovementModel.company_id == company_id,
                        InventoryMovementModel.idempotency_key.in_(
                            [
                                f"hu-split:{rollback_digest}:quarantine",
                                f"hu-split:{rollback_digest}:split",
                            ]
                        ),
                    )
                )
                == 0
            )
            rollback_valuation = await session.get(InventoryCostAverageModel, (company_id, item.id))
            assert rollback_valuation is not None
            assert rollback_valuation.quantity_base == Decimal("15.000000")
            assert rollback_valuation.inventory_value == Decimal("150.000000")
        finally:
            await transaction.rollback()
    await dispose_engine()

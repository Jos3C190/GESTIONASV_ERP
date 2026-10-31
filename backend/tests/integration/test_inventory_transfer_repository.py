"""PostgreSQL checks for the B03 transfer document lifecycle and B04 boundaries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api.v1.routers.inventory import (
    InventoryBoundaryError,
    _reject_legacy_transfer_through_vehicle_transit,
    _reject_legacy_transfer_without_document,
)
from app.api.v1.routers.inventory_transfers import _persist_command
from app.api.v1.schemas.inventory import MovementLineIn
from app.api.v1.schemas.inventory_transfer import InventoryTransferOut
from app.application.inventory_transfers.use_cases import InventoryTransferUseCases
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_transfer import TransferDomainError
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
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
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)
from sqlalchemy import and_, func, select

from tests.e2e.conftest import get_test_company_id

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class TransferFixture:
    company_id: uuid.UUID
    actor_id: uuid.UUID
    origin: Warehouse
    destination: Warehouse
    source_location: Location
    destination_location: Location
    item: InventoryItemModel
    handling_unit_id: uuid.UUID
    vehicle_id: uuid.UUID


async def _create_context(session, suffix: str) -> TransferFixture:
    company_id = await get_test_company_id(session=session)
    actor = User(
        username=f"transfer-{suffix[:16]}",
        email=f"transfer-{suffix[:16]}@example.test",
        password_hash="not-used-by-this-repository-test",
    )
    session.add(actor)
    await session.flush()

    headquarters_id = await session.scalar(
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
    destination_branch_id = await session.scalar(
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
    assert headquarters_id is not None
    assert destination_branch_id is not None

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
            name=f"Transfer test {suffix[:8]}",
            is_active=True,
        )
        session.add(category)
        await session.flush()

    origin = Warehouse(
        company_id=company_id,
        branch_id=headquarters_id,
        warehouse_category_id=category.id,
        name=f"Transfer central {suffix[:8]}",
        code=f"ITC-{suffix[:8]}",
        is_central=True,
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    destination = Warehouse(
        company_id=company_id,
        branch_id=destination_branch_id,
        warehouse_category_id=category.id,
        name=f"Transfer branch {suffix[:8]}",
        code=f"ITB-{suffix[:8]}",
        is_central=False,
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    session.add_all([origin, destination])
    await session.flush()

    source_location = Location(
        warehouse_id=origin.id,
        code=f"IT-S-{suffix[:8]}",
        aisle="01",
        rack="01",
        level="01",
        position="01",
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    destination_location = Location(
        warehouse_id=destination.id,
        code=f"IT-D-{suffix[:8]}",
        aisle="01",
        rack="01",
        level="01",
        position="01",
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    session.add_all([source_location, destination_location])
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

    # Each transfer must preserve an active, non-zero company/product average.
    # This is a synthetic setting isolated to erp_db_test.
    session.add(
        InventoryValuationSettingModel(
            company_id=company_id,
            currency="USD",
            opened_at=datetime.now(UTC),
            opened_by=actor.id,
            opening_reference=f"TRANSFER-TEST-{suffix}",
            opening_fingerprint="a" * 64,
            physical_snapshot=[],
        )
    )
    await session.flush()

    receipt = await SqlAlchemyInventoryRepository(session).post_movement(
        company_id=company_id,
        idempotency_key=f"transfer-seed-{suffix}",
        movement_type="receipt",
        source_reference=f"transfer-integration-receipt:{suffix}",
        lines=[
            {
                "inventory_item_id": item.id,
                "to_location_id": source_location.id,
                "to_stock_status": "available",
                "quantity_base": Decimal("10"),
                "valuation_value": Decimal("25"),
                "valuation_currency": "USD",
                "handling_unit_code": f"IT-HU-{suffix}",
                "actual_measures": {
                    "gross_weight_kg": Decimal("10"),
                    "length_m": Decimal("0.5"),
                    "width_m": Decimal("0.5"),
                    "height_m": Decimal("0.4"),
                },
            }
        ],
        actor_id=actor.id,
    )

    transit_warehouse = await session.scalar(
        select(Warehouse).where(
            Warehouse.company_id == company_id,
            Warehouse.is_transit.is_(True),
            Warehouse.deleted_at.is_(None),
        )
    )
    if transit_warehouse is None:
        transit_category = WarehouseCategory(
            company_id=company_id,
            name=f"Transit test {suffix[:8]}",
            is_active=True,
        )
        session.add(transit_category)
        await session.flush()
        transit_warehouse = Warehouse(
            company_id=company_id,
            branch_id=headquarters_id,
            warehouse_category_id=transit_category.id,
            name=f"Transit test {suffix[:8]}",
            code=f"ITT-{suffix[:8]}",
            warehouse_type="transit",
            is_central=False,
            is_transit=True,
            capacity_profile="transit",
            capacity_enforcement_mode="disabled",
            storage_eligible=False,
        )
        session.add(transit_warehouse)
        await session.flush()

    vehicle = await SqlAlchemyInventoryTransferRepository(session).create_vehicle(
        company_id=company_id,
        code=f"IT-{suffix[:8]}",
        name=f"Vehículo prueba {suffix[:8]}",
        actor_id=actor.id,
    )
    return TransferFixture(
        company_id=company_id,
        actor_id=actor.id,
        origin=origin,
        destination=destination,
        source_location=source_location,
        destination_location=destination_location,
        item=item,
        handling_unit_id=receipt["lines"][0]["handling_unit_id"],
        vehicle_id=vehicle["id"],
    )


@pytest.mark.asyncio
async def test_transfer_preparation_dispatch_partial_receipt_and_idempotent_replay() -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            repository = SqlAlchemyInventoryTransferRepository(session)
            use_cases = InventoryTransferUseCases(repository)
            valuation_before = await session.get(
                InventoryCostAverageModel,
                (context.company_id, context.item.id),
            )
            assert valuation_before is not None
            valuation_snapshot = (
                valuation_before.quantity_base,
                valuation_before.inventory_value,
                valuation_before.average_unit_cost,
            )
            create_key = f"transfer-create-{suffix}"
            create_lines = [
                {
                    "handling_unit_id": context.handling_unit_id,
                    "quantity_base": Decimal("10"),
                    "demand_allocations": [],
                    "excess_reason": "Despacho manual de demostración",
                }
            ]
            before_movement_count = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            )
            before_unit_count = await session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(
                    InventoryHandlingUnitModel.company_id == context.company_id,
                    InventoryHandlingUnitModel.inventory_item_id == context.item.id,
                )
            )
            created = await use_cases.create_transfer(
                company_id=context.company_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                notes="Preparación inicial",
                lines=create_lines,
                idempotency_key=create_key,
                actor_id=context.actor_id,
            )
            assert created["status"] == "preparation"
            assert created["lines"][0]["quantity_dispatched"] == Decimal("0")
            after_prepare_count = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            )
            assert after_prepare_count == before_movement_count
            source_unit_after_prepare = await session.get(
                InventoryHandlingUnitModel, context.handling_unit_id
            )
            after_unit_count = await session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(
                    InventoryHandlingUnitModel.company_id == context.company_id,
                    InventoryHandlingUnitModel.inventory_item_id == context.item.id,
                )
            )
            assert source_unit_after_prepare is not None
            assert source_unit_after_prepare.quantity_base == Decimal("10")
            assert source_unit_after_prepare.closed_at is None
            assert after_unit_count == before_unit_count

            # Preparations do not reserve or move stock; an abandoned draft can
            # be cancelled without a compensating movement.
            cancelled_preparation = await use_cases.create_transfer(
                company_id=context.company_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                lines=create_lines,
                idempotency_key=f"transfer-cancel-create-{suffix}",
                actor_id=context.actor_id,
            )
            cancelled = await use_cases.cancel_transfer(
                company_id=context.company_id,
                transfer_id=cancelled_preparation["id"],
                idempotency_key=f"transfer-cancel-{suffix}",
                actor_id=context.actor_id,
            )
            assert cancelled["status"] == "cancelled"
            after_cancel_count = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            )
            assert after_cancel_count == before_movement_count

            original_transfer_id = created["id"]
            updated = await use_cases.update_transfer(
                company_id=context.company_id,
                transfer_id=original_transfer_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                notes="Preparación editada",
                lines=create_lines,
                idempotency_key=f"transfer-update-{suffix}",
                actor_id=context.actor_id,
            )
            assert updated["notes"] == "Preparación editada"

            replayed_create = await use_cases.create_transfer(
                company_id=context.company_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                notes="Preparación inicial",
                lines=create_lines,
                idempotency_key=create_key,
                actor_id=context.actor_id,
            )
            assert replayed_create["id"] == str(original_transfer_id)
            assert replayed_create["notes"] == "Preparación inicial"
            assert replayed_create["lines"][0]["quantity_planned"] == "10.000000"
            with pytest.raises(TransferDomainError) as changed_replay:
                await use_cases.create_transfer(
                    company_id=context.company_id,
                    origin_warehouse_id=context.origin.id,
                    destination_warehouse_id=context.destination.id,
                    vehicle_id=context.vehicle_id,
                    notes="Cuerpo distinto",
                    lines=create_lines,
                    idempotency_key=create_key,
                    actor_id=context.actor_id,
                )
            assert changed_replay.value.code == "transfer_idempotency_conflict"

            with pytest.raises(TransferDomainError) as over_dispatch:
                await use_cases.create_transfer(
                    company_id=context.company_id,
                    origin_warehouse_id=context.origin.id,
                    destination_warehouse_id=context.destination.id,
                    vehicle_id=context.vehicle_id,
                    lines=[
                        {
                            **create_lines[0],
                            "quantity_base": Decimal("10.000001"),
                        }
                    ],
                    idempotency_key=f"transfer-over-dispatch-{suffix}",
                    actor_id=context.actor_id,
                )
            assert over_dispatch.value.code == "transfer_over_dispatch"

            transfer_detail_id = updated["lines"][0]["id"]
            dispatched = await use_cases.dispatch_transfer(
                company_id=context.company_id,
                transfer_id=original_transfer_id,
                vehicle_id=context.vehicle_id,
                idempotency_key=f"transfer-dispatch-{suffix}",
                actor_id=context.actor_id,
            )
            assert dispatched["status"] == "in_transit"
            assert dispatched["dispatch_movement_id"] is not None
            vehicle = await session.get(InventoryVehicleModel, context.vehicle_id)
            assert vehicle is not None
            in_transit = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == context.company_id,
                    InventoryBalanceModel.inventory_item_id == context.item.id,
                    InventoryBalanceModel.location_id == vehicle.transit_location_id,
                    InventoryBalanceModel.stock_status == "in_transit",
                )
            )
            assert in_transit is not None
            assert in_transit.quantity_base == Decimal("10")
            with pytest.raises(TransferDomainError, match="No puede desactivar"):
                await use_cases.set_vehicle_status(
                    company_id=context.company_id,
                    vehicle_id=context.vehicle_id,
                    status="inactive",
                )
            await session.refresh(vehicle)
            assert vehicle.status == "active"

            non_storage_location = Location(
                warehouse_id=context.destination.id,
                code=f"IT-X-{suffix[:8]}",
                aisle="01",
                rack="02",
                level="01",
                position="01",
                storage_eligible=False,
                lifecycle_status="active",
                location_type="staging",
            )
            session.add(non_storage_location)
            await session.flush()
            with pytest.raises(TransferDomainError, match="ubicación receptora activa"):
                await use_cases.receive_transfer(
                    company_id=context.company_id,
                    transfer_id=original_transfer_id,
                    lines=[
                        {
                            "transfer_detail_id": transfer_detail_id,
                            "destination_location_id": non_storage_location.id,
                            "quantity_base": Decimal("1"),
                        }
                    ],
                    idempotency_key=f"transfer-invalid-location-{suffix}",
                    actor_id=context.actor_id,
                )

            receive_key = f"transfer-receive-8-{suffix}"
            partial = await use_cases.receive_transfer(
                company_id=context.company_id,
                transfer_id=original_transfer_id,
                lines=[
                    {
                        "transfer_detail_id": transfer_detail_id,
                        "destination_location_id": context.destination_location.id,
                        "quantity_base": Decimal("8"),
                    }
                ],
                idempotency_key=receive_key,
                actor_id=context.actor_id,
            )
            assert partial["status"] == "in_transit"
            assert partial["lines"][0]["quantity_received"] == Decimal("8")
            assert partial["lines"][0]["quantity_in_transit"] == Decimal("2")

            replayed_partial = await use_cases.receive_transfer(
                company_id=context.company_id,
                transfer_id=original_transfer_id,
                lines=[
                    {
                        "transfer_detail_id": transfer_detail_id,
                        "destination_location_id": context.destination_location.id,
                        "quantity_base": Decimal("8"),
                    }
                ],
                idempotency_key=receive_key,
                actor_id=context.actor_id,
            )
            assert replayed_partial["status"] == "in_transit"
            assert replayed_partial["lines"][0]["quantity_received"] == "8.000000"

            with pytest.raises(TransferDomainError, match="supera"):
                await use_cases.receive_transfer(
                    company_id=context.company_id,
                    transfer_id=original_transfer_id,
                    lines=[
                        {
                            "transfer_detail_id": transfer_detail_id,
                            "destination_location_id": context.destination_location.id,
                            "quantity_base": Decimal("3"),
                        }
                    ],
                    idempotency_key=f"transfer-over-receive-{suffix}",
                    actor_id=context.actor_id,
                )

            completed = await use_cases.receive_transfer(
                company_id=context.company_id,
                transfer_id=original_transfer_id,
                lines=[
                    {
                        "transfer_detail_id": transfer_detail_id,
                        "destination_location_id": context.destination_location.id,
                        "quantity_base": Decimal("2"),
                    }
                ],
                idempotency_key=f"transfer-receive-2-{suffix}",
                actor_id=context.actor_id,
            )
            assert completed["status"] == "received"
            assert completed["lines"][0]["quantity_received"] == Decimal("10")

            replayed_dispatch = await use_cases.dispatch_transfer(
                company_id=context.company_id,
                transfer_id=original_transfer_id,
                vehicle_id=context.vehicle_id,
                idempotency_key=f"transfer-dispatch-{suffix}",
                actor_id=context.actor_id,
            )
            assert replayed_dispatch["status"] == "in_transit"

            total = await session.scalar(
                select(func.sum(InventoryBalanceModel.quantity_base)).where(
                    InventoryBalanceModel.company_id == context.company_id,
                    InventoryBalanceModel.inventory_item_id == context.item.id,
                )
            )
            assert total == Decimal("10")
            valuation_after = await session.get(
                InventoryCostAverageModel,
                (context.company_id, context.item.id),
            )
            assert valuation_after is not None
            assert (
                valuation_after.quantity_base,
                valuation_after.inventory_value,
                valuation_after.average_unit_cost,
            ) == valuation_snapshot
            movement_count = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id,
                    InventoryMovementModel.source_reference.like(
                        f"inventory_transfer:{created['code']}:%"
                    ),
                )
            )
            assert movement_count == 3
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_transfer_incident_never_removes_unresolved_inventory() -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            repository = SqlAlchemyInventoryTransferRepository(session)
            use_cases = InventoryTransferUseCases(repository)
            transfer = await use_cases.create_transfer(
                company_id=context.company_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                lines=[
                    {
                        "handling_unit_id": context.handling_unit_id,
                        "quantity_base": Decimal("10"),
                        "demand_allocations": [],
                        "excess_reason": "Traslado manual de demostración",
                    }
                ],
                idempotency_key=f"transfer-incident-create-{suffix}",
                actor_id=context.actor_id,
            )
            transfer = await use_cases.dispatch_transfer(
                company_id=context.company_id,
                transfer_id=transfer["id"],
                vehicle_id=context.vehicle_id,
                idempotency_key=f"transfer-incident-dispatch-{suffix}",
                actor_id=context.actor_id,
            )
            with pytest.raises(TransferDomainError) as cancel_after_dispatch:
                await use_cases.cancel_transfer(
                    company_id=context.company_id,
                    transfer_id=transfer["id"],
                    idempotency_key=f"transfer-incident-cancel-after-dispatch-{suffix}",
                    actor_id=context.actor_id,
                )
            assert cancel_after_dispatch.value.code == "transfer_not_in_preparation"
            still_in_transit = await use_cases.get_transfer(context.company_id, transfer["id"])
            assert still_in_transit is not None
            assert still_in_transit["status"] == "in_transit"
            assert still_in_transit["lines"][0]["quantity_in_transit"] == Decimal("10")
            incident = await use_cases.open_incident(
                company_id=context.company_id,
                transfer_id=transfer["id"],
                idempotency_key=f"transfer-incident-open-{suffix}",
                actor_id=context.actor_id,
                reason="Diferencia en tránsito",
                evidence_reference="evidencia-prueba-01",
            )
            assert incident["status"] == "incident"
            assert incident["incidents"][0]["evidence_reference"] == "evidencia-prueba-01"
            with pytest.raises(TransferDomainError, match="ajuste autorizado"):
                await use_cases.resolve_incident(
                    company_id=context.company_id,
                    transfer_id=transfer["id"],
                    idempotency_key=f"transfer-incident-close-{suffix}",
                    actor_id=context.actor_id,
                    resolution="close_received",
                    resolution_notes="La diferencia debe resolverse con ajuste.",
                )
            current = await use_cases.get_transfer(context.company_id, transfer["id"])
            assert current is not None
            assert current["status"] == "incident"
            assert current["lines"][0]["quantity_in_transit"] == Decimal("10")

            vehicle = await session.get(InventoryVehicleModel, context.vehicle_id)
            assert vehicle is not None
            vehicle_balance = await session.scalar(
                select(InventoryBalanceModel).where(
                    InventoryBalanceModel.company_id == context.company_id,
                    InventoryBalanceModel.inventory_item_id == context.item.id,
                    InventoryBalanceModel.location_id == vehicle.transit_location_id,
                    InventoryBalanceModel.stock_status == "in_transit",
                )
            )
            assert vehicle_balance is not None
            assert vehicle_balance.quantity_base == Decimal("10")
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_demand_allocation_cannot_exceed_planned_transfer_quantity() -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            request = PurchaseRequestModel(
                company_id=context.company_id,
                code=f"ITR-{suffix[:12]}",
                branch_id=context.destination.branch_id,
                warehouse_id=context.destination.id,
                requested_by_id=context.actor_id,
                justification="Demanda ficticia para verificar asignación de traslado.",
                status="approved",
            )
            session.add(request)
            await session.flush()
            request_line = PurchaseRequestDetailModel(
                purchase_request_id=request.id,
                company_id=context.company_id,
                product_id=context.item.product_id,
                unit_id=context.item.base_unit_id,
                quantity=Decimal("10"),
            )
            session.add(request_line)
            await session.flush()

            repository = SqlAlchemyInventoryTransferRepository(session)
            with pytest.raises(TransferDomainError) as error:
                await repository.create_transfer(
                    company_id=context.company_id,
                    origin_warehouse_id=context.origin.id,
                    destination_warehouse_id=context.destination.id,
                    vehicle_id=context.vehicle_id,
                    actor_id=context.actor_id,
                    idempotency_key=f"transfer-overallocated-{suffix}",
                    lines=[
                        {
                            "handling_unit_id": context.handling_unit_id,
                            "quantity_base": Decimal("8"),
                            "demand_allocations": [
                                {
                                    "purchase_request_detail_id": request_line.id,
                                    "allocated_quantity": Decimal("9"),
                                }
                            ],
                        }
                    ],
                )
            assert error.value.code == "transfer_demand_allocation_exceeds_line"
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_demand_progress_tracks_assignment_dispatch_and_partial_receipt_once() -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            request = PurchaseRequestModel(
                company_id=context.company_id,
                code=f"ITR-P-{suffix[:12]}",
                branch_id=context.destination.branch_id,
                warehouse_id=context.destination.id,
                requested_by_id=context.actor_id,
                justification="Demanda ficticia para validar el avance del traslado.",
                status="approved",
            )
            session.add(request)
            await session.flush()
            request_line = PurchaseRequestDetailModel(
                purchase_request_id=request.id,
                company_id=context.company_id,
                product_id=context.item.product_id,
                unit_id=context.item.base_unit_id,
                quantity=Decimal("10"),
            )
            session.add(request_line)
            await session.flush()

            use_cases = InventoryTransferUseCases(SqlAlchemyInventoryTransferRepository(session))
            transfer = await use_cases.create_transfer(
                company_id=context.company_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                actor_id=context.actor_id,
                idempotency_key=f"transfer-demand-create-{suffix}",
                lines=[
                    {
                        "handling_unit_id": context.handling_unit_id,
                        "quantity_base": Decimal("8"),
                        "demand_allocations": [
                            {
                                "purchase_request_detail_id": request_line.id,
                                "allocated_quantity": Decimal("6"),
                            }
                        ],
                        "excess_reason": "Dos unidades excedentes autorizadas para demo",
                    }
                ],
            )

            async def demand_snapshot() -> dict[str, Decimal]:
                rows = await use_cases.list_demand(
                    company_id=context.company_id,
                    branch_id=context.destination.branch_id,
                    product_id=context.item.product_id,
                )
                matching = [
                    row for row in rows if row["purchase_request_detail_id"] == request_line.id
                ]
                assert len(matching) == 1
                return matching[0]

            before_dispatch = await demand_snapshot()
            assert before_dispatch["quantity_assigned"] == Decimal("6")
            assert before_dispatch["quantity_dispatched"] == Decimal("0")
            assert before_dispatch["quantity_pending"] == Decimal("4")

            dispatched = await use_cases.dispatch_transfer(
                company_id=context.company_id,
                transfer_id=transfer["id"],
                vehicle_id=context.vehicle_id,
                idempotency_key=f"transfer-demand-dispatch-{suffix}",
                actor_id=context.actor_id,
            )
            after_dispatch = await demand_snapshot()
            assert after_dispatch["quantity_assigned"] == Decimal("6")
            assert after_dispatch["quantity_dispatched"] == Decimal("6")
            assert after_dispatch["quantity_in_transit"] == Decimal("6")
            assert after_dispatch["quantity_pending"] == Decimal("4")

            await use_cases.receive_transfer(
                company_id=context.company_id,
                transfer_id=dispatched["id"],
                lines=[
                    {
                        "transfer_detail_id": dispatched["lines"][0]["id"],
                        "destination_location_id": context.destination_location.id,
                        "quantity_base": Decimal("4"),
                    }
                ],
                idempotency_key=f"transfer-demand-receive-{suffix}",
                actor_id=context.actor_id,
            )
            after_partial_receipt = await demand_snapshot()
            assert after_partial_receipt["quantity_assigned"] == Decimal("6")
            assert after_partial_receipt["quantity_dispatched"] == Decimal("6")
            assert after_partial_receipt["quantity_received"] == Decimal("4")
            assert after_partial_receipt["quantity_in_transit"] == Decimal("2")
            assert after_partial_receipt["quantity_pending"] == Decimal("4")
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_legacy_movement_endpoint_cannot_bypass_transfer_documents() -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            vehicle = await session.get(InventoryVehicleModel, context.vehicle_id)
            assert vehicle is not None
            with pytest.raises(InventoryBoundaryError) as error:
                await _reject_legacy_transfer_through_vehicle_transit(
                    session, {vehicle.transit_location_id}
                )
            assert error.value.code == "inventory_transfer_document_required"
            await _reject_legacy_transfer_through_vehicle_transit(
                session, {context.source_location.id}
            )
            cross_warehouse_line = MovementLineIn(
                inventory_item_id=context.item.id,
                from_location_id=context.source_location.id,
                to_location_id=context.destination_location.id,
                from_stock_status="available",
                to_stock_status="quarantine",
                quantity_base=Decimal("1"),
            )
            with pytest.raises(InventoryBoundaryError) as cross_warehouse_error:
                await _reject_legacy_transfer_without_document(session, [cross_warehouse_line])
            assert cross_warehouse_error.value.code == "inventory_transfer_document_required"

            same_warehouse_line = MovementLineIn(
                inventory_item_id=context.item.id,
                from_location_id=context.source_location.id,
                to_location_id=context.source_location.id,
                from_stock_status="available",
                to_stock_status="quarantine",
                quantity_base=Decimal("1"),
            )
            await _reject_legacy_transfer_without_document(session, [same_warehouse_line])

            legacy_transit_line = same_warehouse_line.model_copy(
                update={"to_stock_status": "in_transit"}
            )
            with pytest.raises(InventoryBoundaryError) as transit_error:
                await _reject_legacy_transfer_without_document(session, [legacy_transit_line])
            assert transit_error.value.code == "inventory_transfer_document_required"
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_transfer_command_savepoint_rolls_back_partial_movement_failures(monkeypatch) -> None:
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            second_receipt = await SqlAlchemyInventoryRepository(session).post_movement(
                company_id=context.company_id,
                idempotency_key=f"transfer-savepoint-second-receipt-{suffix}",
                movement_type="receipt",
                source_reference=f"transfer-savepoint-receipt:{suffix}",
                lines=[
                    {
                        "inventory_item_id": context.item.id,
                        "to_location_id": context.source_location.id,
                        "to_stock_status": "available",
                        "quantity_base": Decimal("10"),
                        "valuation_value": Decimal("25"),
                        "valuation_currency": "USD",
                        "handling_unit_code": f"IT-HU-SECOND-{suffix[:8]}",
                        "actual_measures": {
                            "gross_weight_kg": Decimal("10"),
                            "length_m": Decimal("0.5"),
                            "width_m": Decimal("0.5"),
                            "height_m": Decimal("0.4"),
                        },
                    }
                ],
                actor_id=context.actor_id,
            )
            repository = SqlAlchemyInventoryTransferRepository(session)
            use_cases = InventoryTransferUseCases(repository)
            line_specs = [
                {
                    "handling_unit_id": handling_unit_id,
                    "quantity_base": Decimal("10"),
                    "demand_allocations": [],
                    "excess_reason": "Despacho manual de prueba",
                }
                for handling_unit_id in (
                    context.handling_unit_id,
                    second_receipt["lines"][0]["handling_unit_id"],
                )
            ]
            for failure_index, failure in enumerate(
                (
                    InventoryOperationError(
                        "Fallo funcional simulado en la segunda línea.",
                        code="transfer_test_second_line",
                    ),
                    RuntimeError("Fallo inesperado simulado en la segunda línea."),
                ),
                start=1,
            ):
                transfer = await use_cases.create_transfer(
                    company_id=context.company_id,
                    origin_warehouse_id=context.origin.id,
                    destination_warehouse_id=context.destination.id,
                    vehicle_id=context.vehicle_id,
                    lines=line_specs,
                    idempotency_key=f"transfer-savepoint-create-{failure_index}-{suffix}",
                    actor_id=context.actor_id,
                )
                valuation_before = await session.get(
                    InventoryCostAverageModel,
                    (context.company_id, context.item.id),
                )
                assert valuation_before is not None
                valuation_snapshot = (
                    valuation_before.quantity_base,
                    valuation_before.inventory_value,
                    valuation_before.average_unit_cost,
                )
                balance_snapshot = list(
                    (
                        await session.execute(
                            select(
                                InventoryBalanceModel.location_id,
                                InventoryBalanceModel.stock_status,
                                InventoryBalanceModel.quantity_base,
                            )
                            .where(
                                InventoryBalanceModel.company_id == context.company_id,
                                InventoryBalanceModel.inventory_item_id == context.item.id,
                            )
                            .order_by(
                                InventoryBalanceModel.location_id,
                                InventoryBalanceModel.stock_status,
                            )
                        )
                    ).all()
                )
                movement_source = f"inventory_transfer:{transfer['code']}:dispatch"
                original_post_movement = SqlAlchemyInventoryRepository.post_movement

                async def post_first_line_then_fail(
                    inventory_repository: SqlAlchemyInventoryRepository,
                    *,
                    _failure=failure,
                    _movement_source=movement_source,
                    _original_post_movement=original_post_movement,
                    **kwargs,
                ):
                    if kwargs.get("source_reference") == _movement_source:
                        await _original_post_movement(
                            inventory_repository,
                            **{**kwargs, "lines": kwargs["lines"][:1]},
                        )
                        raise _failure
                    return await _original_post_movement(inventory_repository, **kwargs)

                monkeypatch.setattr(
                    SqlAlchemyInventoryRepository,
                    "post_movement",
                    post_first_line_then_fail,
                )
                audit = AsyncMock()
                operation = use_cases.dispatch_transfer(
                    company_id=context.company_id,
                    transfer_id=transfer["id"],
                    vehicle_id=context.vehicle_id,
                    idempotency_key=f"transfer-savepoint-dispatch-{failure_index}-{suffix}",
                    actor_id=context.actor_id,
                )
                with pytest.raises(
                    InventoryBoundaryError
                    if isinstance(failure, InventoryOperationError)
                    else RuntimeError
                ):
                    await _persist_command(
                        session=session,
                        audit=audit,
                        current=SimpleNamespace(id=context.actor_id),
                        request=SimpleNamespace(client=None, headers={}),
                        company_id=context.company_id,
                        branch_id=context.origin.branch_id,
                        action="DISPATCH_TRANSFER",
                        resource_type="inventory_transfers",
                        resource_id=str(transfer["id"]),
                        operation=operation,
                        response_model=InventoryTransferOut,
                    )

                monkeypatch.setattr(
                    SqlAlchemyInventoryRepository,
                    "post_movement",
                    original_post_movement,
                )
                persisted_transfer = await session.scalar(
                    select(InventoryTransferModel).where(
                        InventoryTransferModel.company_id == context.company_id,
                        InventoryTransferModel.id == transfer["id"],
                    )
                )
                assert persisted_transfer is not None
                await session.refresh(persisted_transfer)
                assert persisted_transfer.status == "preparation"
                assert persisted_transfer.dispatch_command_id is None
                assert persisted_transfer.dispatch_movement_id is None
                assert (
                    await session.scalar(
                        select(func.count(InventoryMovementModel.id)).where(
                            InventoryMovementModel.company_id == context.company_id,
                            InventoryMovementModel.source_reference == movement_source,
                        )
                    )
                    == 0
                )
                assert (
                    list(
                        (
                            await session.execute(
                                select(
                                    InventoryBalanceModel.location_id,
                                    InventoryBalanceModel.stock_status,
                                    InventoryBalanceModel.quantity_base,
                                )
                                .where(
                                    InventoryBalanceModel.company_id == context.company_id,
                                    InventoryBalanceModel.inventory_item_id == context.item.id,
                                )
                                .order_by(
                                    InventoryBalanceModel.location_id,
                                    InventoryBalanceModel.stock_status,
                                )
                            )
                        ).all()
                    )
                    == balance_snapshot
                )
                valuation_after = await session.get(
                    InventoryCostAverageModel,
                    (context.company_id, context.item.id),
                )
                assert valuation_after is not None
                assert (
                    valuation_after.quantity_base,
                    valuation_after.inventory_value,
                    valuation_after.average_unit_cost,
                ) == valuation_snapshot
                assert (
                    await session.scalar(
                        select(func.count(AuditLog.id)).where(
                            AuditLog.company_id == context.company_id,
                            AuditLog.action == "DISPATCH_TRANSFER",
                            AuditLog.resource_id == str(transfer["id"]),
                        )
                    )
                    == 0
                )
                audit.record.assert_not_awaited()
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()

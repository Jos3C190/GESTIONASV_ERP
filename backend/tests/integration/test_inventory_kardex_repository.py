"""PostgreSQL integration coverage for the Kardex SQL read adapter."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.domain.entities.inventory_kardex import LOCAL_TZ
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.catalog import CategoryModel, CompanyUnitModel, ProductModel
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.inventory import (
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_valuation import (
    InventoryValuationEntryModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.organization import (
    Branch,
    Company,
    Location,
    Warehouse,
    WarehouseCategory,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_kardex_read_repository import (
    SqlAlchemyInventoryKardexReadRepository,
)
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)
from sqlalchemy import and_, select

from tests.e2e.conftest import get_test_company_id

pytestmark = pytest.mark.integration


async def _concurrency_company(session, suffix: str) -> uuid.UUID:
    """Give committed concurrency fixtures their own company and valuation settings."""
    seed_company_id = await get_test_company_id(session=session)
    seed_company = await session.get(Company, seed_company_id)
    assert seed_company is not None
    unit_id = await session.scalar(
        select(CompanyUnitModel.unit_id)
        .where(
            CompanyUnitModel.company_id == seed_company_id,
            CompanyUnitModel.is_enabled.is_(True),
        )
        .order_by(CompanyUnitModel.unit_id)
        .limit(1)
    )
    assert unit_id is not None
    geography = {
        "department_id": seed_company.department_id,
        "municipality_id": seed_company.municipality_id,
        "district_id": seed_company.district_id,
    }
    company = Company(
        name=f"IT Kardex concurrency {suffix}",
        commercial_name=f"IT Kardex concurrency {suffix}",
        nit=suffix,
        nrc=suffix,
        address="Synthetic integration fixture",
        **geography,
    )
    session.add(company)
    await session.flush()
    category = CategoryModel(company_id=company.id, name="Integration inventory")
    session.add_all(
        [
            category,
            Branch(
                company_id=company.id,
                name="Integration branch",
                code="IT-CONC",
                address="Synthetic integration fixture",
                **geography,
            ),
        ]
    )
    await session.flush()
    # Migration 0023 enrolls new companies in the shared unit catalog.
    company_unit = await session.get(CompanyUnitModel, (company.id, unit_id))
    assert company_unit is not None
    company_unit.is_enabled = True
    session.add(
        ProductModel(
            company_id=company.id,
            id_category=category.id_category,
            sku=f"IT-CONC-{suffix}",
            name="Integration concurrency product",
            purchase_unit=unit_id,
            sale_unit=unit_id,
        )
    )
    await session.flush()
    return company.id


async def _test_inventory_fixture(session, company_id: uuid.UUID, suffix: str):
    """Create a disposable warehouse, location, user, and inventory item."""
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
            name=f"IT-KDX-{suffix[:8]}",
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
        name=f"IT Kardex {suffix[:8]}",
        code=f"ITK-{suffix[:8]}",
        is_central=False,
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    session.add(warehouse)
    await session.flush()
    location = Location(
        warehouse_id=warehouse.id,
        code=f"IT-KDX-{suffix[:8]}",
        aisle="01",
        rack="01",
        level="01",
        position="01",
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    session.add(location)

    actor = User(
        username=f"inventory-kardex-{suffix[:16]}",
        email=f"inventory-kardex-{suffix[:16]}@example.test",
        password_hash="not-used-by-this-repository-test",
    )
    session.add(actor)
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
    return warehouse, location, actor, item, product


@pytest.mark.asyncio
async def test_kardex_sql_reads_pages_totals_unknown_values_and_company_scope() -> None:
    suffix = uuid.uuid4().hex
    company_id = await get_test_company_id()

    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            warehouse, location, actor, item, product = await _test_inventory_fixture(
                session, company_id, suffix
            )
            movements = SqlAlchemyInventoryRepository(session)
            for index, quantity in enumerate((Decimal("2"), Decimal("3")), start=1):
                await movements.post_movement(
                    company_id=company_id,
                    idempotency_key=f"it-kardex-{suffix}-{index}",
                    movement_type="receipt",
                    source_reference=f"integration-kardex:{suffix}:{index}",
                    lines=[
                        {
                            "inventory_item_id": item.id,
                            "to_location_id": location.id,
                            "to_stock_status": "quarantine",
                            "quantity_base": quantity,
                            "handling_unit_code": f"IT-KDX-HU-{suffix}-{index}",
                            "actual_measures": {
                                "gross_weight_kg": quantity,
                                "length_m": Decimal("0.1"),
                                "width_m": Decimal("0.1"),
                                "height_m": Decimal("0.1"),
                            },
                        }
                    ],
                    actor_id=actor.id,
                )

            kardex = SqlAlchemyInventoryKardexReadRepository(session)
            assert await kardex.get_warehouse_scope(warehouse_id=warehouse.id) == (
                company_id,
                warehouse.branch_id,
            )
            options = await kardex.search_items(
                company_id=company_id,
                warehouse_id=warehouse.id,
                query=product.sku or product.name[:8],
            )
            assert [row["inventory_item_id"] for row in options] == [item.id]

            today = datetime.now(LOCAL_TZ).date()
            period_from = today - timedelta(days=1)
            period_to = today + timedelta(days=1)
            physical_page_1 = await kardex.physical_kardex(
                company_id=company_id,
                warehouse_id=warehouse.id,
                inventory_item_id=item.id,
                period_from=period_from,
                period_to=period_to,
                movement_type="receipt",
                lot_code=None,
                page=1,
                page_size=1,
                access_all_branches=False,
                accessible_branch_ids={warehouse.branch_id},
            )
            physical_page_2 = await kardex.physical_kardex(
                company_id=company_id,
                warehouse_id=warehouse.id,
                inventory_item_id=item.id,
                period_from=period_from,
                period_to=period_to,
                movement_type="receipt",
                lot_code=None,
                page=2,
                page_size=1,
                access_all_branches=False,
                accessible_branch_ids={warehouse.branch_id},
            )
            assert physical_page_1 is not None
            assert physical_page_2 is not None
            assert physical_page_1["total"] == 2
            assert len(physical_page_1["items"]) == len(physical_page_2["items"]) == 1
            assert physical_page_1["items"][0]["id"] != physical_page_2["items"][0]["id"]
            assert physical_page_1["incoming_quantity"] == Decimal("5")
            assert physical_page_1["outgoing_quantity"] == Decimal("0")
            assert physical_page_1["opening_known"] is False
            assert physical_page_1["closing_known"] is False

            reconciliation = await kardex.reconciliation(
                company_id=company_id, page=1, page_size=200
            )
            assert reconciliation["page"] == 1
            assert reconciliation["page_size"] == 200
            assert reconciliation["total"] >= 1
            row = next(
                value for value in reconciliation["items"] if value["inventory_item_id"] == item.id
            )
            assert row["physical_quantity"] == Decimal("5")
            assert row["valued_quantity"] is None
            assert row["inventory_value"] is None

            valued = await kardex.valued_kardex(
                company_id=company_id,
                inventory_item_id=item.id,
                period_from=period_from,
                period_to=period_to,
                page=1,
                page_size=10,
            )
            assert valued is not None
            assert valued["setting"] is None
            assert valued["opening_known"] is False
            assert valued["closing_known"] is False
            assert valued["entries"] == []

            other_company_id = uuid.uuid4()
            assert (
                await kardex.search_items(
                    company_id=other_company_id,
                    warehouse_id=warehouse.id,
                    query=product.sku or product.name[:8],
                )
                == []
            )
            assert (
                await kardex.physical_kardex(
                    company_id=other_company_id,
                    warehouse_id=warehouse.id,
                    inventory_item_id=item.id,
                    period_from=period_from,
                    period_to=period_to,
                    movement_type=None,
                    lot_code=None,
                    page=1,
                    page_size=10,
                    access_all_branches=True,
                    accessible_branch_ids=set(),
                )
                is None
            )
            assert (
                await kardex.valued_kardex(
                    company_id=other_company_id,
                    inventory_item_id=item.id,
                    period_from=period_from,
                    period_to=period_to,
                    page=1,
                    page_size=10,
                )
                is None
            )
            isolated = await kardex.reconciliation(
                company_id=other_company_id, page=1, page_size=10
            )
            assert isolated["total"] == 0
            assert isolated["items"] == []
        finally:
            await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_kardex_sql_orders_timestamp_ties_filters_lot_and_uses_local_day_cutoffs() -> None:
    suffix = uuid.uuid4().hex
    company_id = await get_test_company_id()

    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            warehouse, location, actor, item, _ = await _test_inventory_fixture(
                session, company_id, suffix
            )
            cutoff = datetime(2026, 10, 1, 0, 0, tzinfo=LOCAL_TZ)
            session.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=cutoff,
                    opened_by=actor.id,
                    opening_reference=f"IT-KDX-CUT-{suffix}",
                    opening_fingerprint="b" * 64,
                    physical_snapshot=[],
                )
            )
            await session.flush()

            rows = [
                # Prior local day contributes to the opening balance.
                (datetime(2026, 10, 5, 23, 59, 59, 999999, tzinfo=LOCAL_TZ), "LOT-A", "2"),
                # Same local timestamp: deterministic order must use movement-line UUID.
                (datetime(2026, 10, 6, 0, 0, tzinfo=LOCAL_TZ), "LOT-A", "3"),
                (datetime(2026, 10, 6, 0, 0, tzinfo=LOCAL_TZ), "LOT-A", "4"),
                (datetime(2026, 10, 6, 12, 0, tzinfo=LOCAL_TZ), "LOT-B", "5"),
                # The end of the selected local day is included.
                (datetime(2026, 10, 6, 23, 59, 59, 999999, tzinfo=LOCAL_TZ), "LOT-A", "1"),
                # Midnight belongs to the next local day and is excluded.
                (datetime(2026, 10, 7, 0, 0, tzinfo=LOCAL_TZ), "LOT-A", "8"),
            ]
            for index, (posted_at, lot_code, quantity_text) in enumerate(rows, start=1):
                movement = InventoryMovementModel(
                    company_id=company_id,
                    movement_type="receipt",
                    idempotency_key=f"it-kdx-boundary-{suffix}-{index}",
                    request_fingerprint=f"{index:064x}",
                    source_reference=f"integration-kardex-boundary:{suffix}:{index}",
                    posted_at=posted_at,
                    posted_by=actor.id,
                    created_at=posted_at,
                )
                session.add(movement)
                await session.flush()
                session.add(
                    InventoryMovementLineModel(
                        id=uuid.UUID(int=index),
                        company_id=company_id,
                        movement_id=movement.id,
                        line_number=1,
                        inventory_item_id=item.id,
                        handling_unit_id=None,
                        lot_code=lot_code,
                        expiry_date=None,
                        from_warehouse_id=None,
                        from_location_id=None,
                        to_warehouse_id=warehouse.id,
                        to_location_id=location.id,
                        from_stock_status=None,
                        to_stock_status="quarantine",
                        quantity_base=Decimal(quantity_text),
                        occupied_weight_kg=Decimal("1"),
                        occupied_volume_m3=Decimal("0.001"),
                        measurement_status="complete",
                        packaging_snapshot=None,
                    )
                )
            await session.flush()

            kardex = SqlAlchemyInventoryKardexReadRepository(session)
            first = await kardex.physical_kardex(
                company_id=company_id,
                warehouse_id=warehouse.id,
                inventory_item_id=item.id,
                period_from=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                period_to=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                movement_type=None,
                lot_code="LOT-A",
                page=1,
                page_size=1,
                access_all_branches=False,
                accessible_branch_ids={warehouse.branch_id},
            )
            second = await kardex.physical_kardex(
                company_id=company_id,
                warehouse_id=warehouse.id,
                inventory_item_id=item.id,
                period_from=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                period_to=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                movement_type=None,
                lot_code="LOT-A",
                page=2,
                page_size=1,
                access_all_branches=False,
                accessible_branch_ids={warehouse.branch_id},
            )
            third = await kardex.physical_kardex(
                company_id=company_id,
                warehouse_id=warehouse.id,
                inventory_item_id=item.id,
                period_from=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                period_to=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                movement_type=None,
                lot_code="LOT-A",
                page=3,
                page_size=1,
                access_all_branches=False,
                accessible_branch_ids={warehouse.branch_id},
            )
            assert first is not None
            assert second is not None
            assert third is not None
            assert first["total"] == second["total"] == third["total"] == 3
            assert [
                row["quantity_base"] for page in (first, second, third) for row in page["items"]
            ] == [
                Decimal("3"),
                Decimal("4"),
                Decimal("1"),
            ]
            assert first["items"][0]["id"] < second["items"][0]["id"]
            assert first["opening_known"] is True
            assert first["opening_quantity"] == Decimal("2")
            assert first["closing_known"] is True
            assert first["closing_quantity"] == Decimal("10")
            assert first["incoming_quantity"] == Decimal("8")
            assert first["outgoing_quantity"] == Decimal("0")
            assert [
                row["balance_after"] for page in (first, second, third) for row in page["items"]
            ] == [
                Decimal("5"),
                Decimal("9"),
                Decimal("10"),
            ]

            other_lot = await kardex.physical_kardex(
                company_id=company_id,
                warehouse_id=warehouse.id,
                inventory_item_id=item.id,
                period_from=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                period_to=datetime(2026, 10, 6, tzinfo=LOCAL_TZ).date(),
                movement_type=None,
                lot_code="LOT-B",
                page=1,
                page_size=1,
                access_all_branches=False,
                accessible_branch_ids={warehouse.branch_id},
            )
            assert other_lot is not None
            assert other_lot["total"] == 1
            assert other_lot["incoming_quantity"] == Decimal("5")
            assert other_lot["items"][0]["lot_code"] == "LOT-B"
        finally:
            await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_reconciliation_waits_for_atomic_receipt_and_valuation_commit(monkeypatch) -> None:
    """A reconciliation sees the same committed physical and valued receipt."""
    suffix = uuid.uuid4().hex
    async with async_session_factory() as setup:
        company_id = await _concurrency_company(setup, suffix)
        warehouse, location, actor, item, _ = await _test_inventory_fixture(
            setup, company_id, f"IT-CONC-{suffix[:10]}"
        )
        setup.add(
            Employee(
                company_id=company_id,
                user_id=actor.id,
                employee_code=f"IT-B4-{suffix[:12]}",
                first_name="Prueba",
                last_name="Consistencia",
                status="activo",
            )
        )
        await setup.flush()
        await setup.commit()

    writer = async_session_factory()
    writer_transaction = await writer.begin()
    try:
        await SqlAlchemyInventoryValuationRepository(writer).lock(company_id)
        await SqlAlchemyInventoryRepository(writer).post_movement(
            company_id=company_id,
            idempotency_key=f"it-b4-consistency-concurrent-{suffix}",
            movement_type="receipt",
            source_reference=f"IT-B4-CONSISTENCY-CONCURRENT-{suffix}",
            lines=[
                {
                    "inventory_item_id": item.id,
                    "to_location_id": location.id,
                    "to_stock_status": "quarantine",
                    "quantity_base": Decimal("10"),
                    "handling_unit_code": f"IT-B4-CONSISTENCY-NEW-{suffix[:12]}",
                    "actual_measures": {
                        "gross_weight_kg": Decimal("10"),
                        "length_m": Decimal("1"),
                        "width_m": Decimal("1"),
                        "height_m": Decimal("1"),
                    },
                }
            ],
            actor_id=actor.id,
        )

        reader_waiting = asyncio.Event()
        original_lock = SqlAlchemyInventoryValuationRepository.lock

        async def signal_reader_before_lock(self, requested_company_id):
            if self.session.sync_session.info.get("b4_reconciliation_reader"):
                reader_waiting.set()
            await original_lock(self, requested_company_id)

        monkeypatch.setattr(
            SqlAlchemyInventoryValuationRepository, "lock", signal_reader_before_lock
        )

        async def read_reconciliation():
            async with async_session_factory() as reader:
                reader.sync_session.info["b4_reconciliation_reader"] = True
                return await SqlAlchemyInventoryKardexReadRepository(reader).reconciliation(
                    company_id=company_id, page=1, page_size=200
                )

        reader_task = asyncio.create_task(read_reconciliation())
        await asyncio.wait_for(reader_waiting.wait(), timeout=5)
        assert not reader_task.done(), "La conciliación debe esperar el lock de la recepción."
        await asyncio.wait_for(writer_transaction.commit(), timeout=5)
        result = await asyncio.wait_for(reader_task, timeout=5)

        row = next(entry for entry in result["items"] if entry["inventory_item_id"] == item.id)
        assert result["valuation_enabled"] is False
        assert row["physical_quantity"] == Decimal("10.000000")
        assert row["valued_quantity"] is None
        assert row["inventory_value"] is None
        assert row["quantity_difference"] is None
    finally:
        if writer_transaction.is_active:
            await writer_transaction.rollback()
        await writer.close()
        await dispose_engine()


@pytest.mark.parametrize("write_kind", ["transfer", "retaceo"])
@pytest.mark.asyncio
async def test_reconciliation_waits_for_transfer_or_landed_cost_commit(
    monkeypatch, write_kind: str
) -> None:
    """The company lock prevents reconciliation from mixing either write."""
    suffix = uuid.uuid4().hex
    async with async_session_factory() as setup:
        company_id = await _concurrency_company(setup, suffix)
        warehouse, location, actor, item, _ = await _test_inventory_fixture(
            setup, company_id, f"IT-WR-{suffix[:10]}"
        )
        employee = Employee(
            company_id=company_id,
            user_id=actor.id,
            employee_code=f"IT-WR-{suffix[:12]}",
            first_name="Prueba",
            last_name="Consistencia",
            status="activo",
        )
        setup.add(employee)
        destination = Location(
            warehouse_id=warehouse.id,
            code=f"IT-WR-{suffix[:8]}",
            aisle="02",
            rack="01",
            level="01",
            position="01",
            storage_eligible=True,
            capacity_enforcement_mode="disabled",
        )
        setup.add(destination)
        await setup.flush()
        setup_valuation = SqlAlchemyInventoryValuationRepository(setup)
        existing_setting = await setup_valuation.settings(company_id)
        receipt_line = {
            "inventory_item_id": item.id,
            "to_location_id": location.id,
            "to_stock_status": "available",
            "quantity_base": Decimal("10"),
            "handling_unit_code": f"IT-WR-HU-{suffix[:12]}",
            "actual_measures": {
                "gross_weight_kg": Decimal("10"),
                "length_m": Decimal("1"),
                "width_m": Decimal("1"),
                "height_m": Decimal("1"),
            },
        }
        if existing_setting is not None:
            receipt_line.update(
                {
                    "valuation_currency": existing_setting.currency,
                    "valuation_value": Decimal("100"),
                }
            )
        receipt_movement = await SqlAlchemyInventoryRepository(setup).post_movement(
            company_id=company_id,
            idempotency_key=f"it-b4-write-receipt-{suffix}",
            movement_type="receipt",
            source_reference=f"IT-B4-WR-RECEIPT-{suffix}",
            lines=[receipt_line],
            actor_id=actor.id,
        )
        if existing_setting is None:
            setup.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=datetime.now(UTC),
                    opened_by=actor.id,
                    opening_reference=f"IT-WR-OPEN-{suffix}",
                    opening_fingerprint=hashlib.sha256(suffix.encode()).hexdigest(),
                    physical_snapshot=[],
                )
            )
            await setup.flush()
            original_receipt = await setup_valuation.append(
                company_id=company_id,
                item_id=item.id,
                kind="receipt",
                quantity=Decimal("10"),
                value=Decimal("100"),
                actor_id=actor.id,
                key=f"it-b4-write-value-receipt-{suffix}",
                reference=f"IT-B4-WR-VALUED-RECEIPT-{suffix}",
            )
        else:
            original_receipt_id = await setup.scalar(
                select(InventoryValuationEntryModel.id).where(
                    InventoryValuationEntryModel.movement_line_id
                    == receipt_movement["lines"][0]["id"]
                )
            )
            assert original_receipt_id is not None
            original_receipt = await setup.get(InventoryValuationEntryModel, original_receipt_id)
            assert original_receipt is not None
        await setup.commit()

    writer = async_session_factory()
    writer_transaction = await writer.begin()
    try:
        writer_valuation = SqlAlchemyInventoryValuationRepository(writer)
        await writer_valuation.lock(company_id)
        if write_kind == "transfer":
            await SqlAlchemyInventoryRepository(writer).post_movement(
                company_id=company_id,
                idempotency_key=f"it-b4-write-transfer-{suffix}",
                movement_type="transfer",
                source_reference=f"IT-B4-WR-TRANSFER-{suffix}",
                lines=[
                    {
                        "inventory_item_id": item.id,
                        "handling_unit_id": receipt_movement["lines"][0]["handling_unit_id"],
                        "from_location_id": location.id,
                        "to_location_id": destination.id,
                        "from_stock_status": "available",
                        "to_stock_status": "in_transit",
                        "quantity_base": Decimal("4"),
                    }
                ],
                actor_id=actor.id,
            )
            expected_value = Decimal("100.000000")
        else:
            await writer_valuation.append(
                company_id=company_id,
                item_id=item.id,
                kind="cost_adjustment",
                quantity=Decimal("0"),
                value=Decimal("20"),
                actor_id=actor.id,
                key=f"it-b4-write-retaceo-{suffix}",
                reference=f"IT-B4-WR-RETACEO-{suffix}",
                original_id=original_receipt.id,
            )
            expected_value = Decimal("120.000000")

        reader_waiting = asyncio.Event()
        original_lock = SqlAlchemyInventoryValuationRepository.lock

        async def signal_reader_before_lock(self, requested_company_id):
            if self.session.sync_session.info.get("b4_reconciliation_writer_case"):
                reader_waiting.set()
            await original_lock(self, requested_company_id)

        monkeypatch.setattr(
            SqlAlchemyInventoryValuationRepository, "lock", signal_reader_before_lock
        )

        async def read_reconciliation():
            async with async_session_factory() as reader:
                reader.sync_session.info["b4_reconciliation_writer_case"] = True
                return await SqlAlchemyInventoryKardexReadRepository(reader).reconciliation(
                    company_id=company_id, page=1, page_size=200
                )

        reader_task = asyncio.create_task(read_reconciliation())
        await asyncio.wait_for(reader_waiting.wait(), timeout=5)
        assert not reader_task.done(), f"La conciliación no debe adelantarse al {write_kind}."
        await asyncio.wait_for(writer_transaction.commit(), timeout=5)
        result = await asyncio.wait_for(reader_task, timeout=5)

        row = next(entry for entry in result["items"] if entry["inventory_item_id"] == item.id)
        assert result["valuation_enabled"] is True
        assert row["physical_quantity"] == Decimal("10.000000")
        assert row["valued_quantity"] == Decimal("10.000000")
        assert row["inventory_value"] == expected_value
        assert row["average_unit_cost"] == expected_value / Decimal("10")
        assert row["quantity_difference"] == Decimal("0.000000")
    finally:
        if writer_transaction.is_active:
            await writer_transaction.rollback()
        await writer.close()
        await dispose_engine()

"""Registration cut reconstructs a nonempty baseline and respects local midnight."""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from app.domain.entities.inventory_kardex import LOCAL_TZ
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.inventory import InventoryMovementLineModel, InventoryMovementModel
from app.infrastructure.models.inventory_valuation import (
    InventoryValuationEntryModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.organization import Warehouse
from app.infrastructure.repositories.inventory_kardex_read_repository import (
    SqlAlchemyInventoryKardexReadRepository,
)

from tests.integration.test_inventory_kardex_repository import (
    _concurrency_company,
    _test_inventory_fixture,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_cut_uses_baseline_plus_external_changes_and_persisted_cost_at_local_midnight():
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            company_id = await _concurrency_company(session, suffix)
            warehouse, location, actor, item, _ = await _test_inventory_fixture(
                session, company_id, suffix
            )
            session.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=datetime(2026, 10, 1, tzinfo=LOCAL_TZ),
                    opened_by=actor.id,
                    opening_reference="BASE-CORTE",
                    opening_fingerprint="f" * 64,
                    physical_snapshot=[
                        {"inventory_item_id": str(item.id), "quantity_base": "4"},
                        {"inventory_item_id": str(item.id), "quantity_base": "6"},
                    ],
                )
            )
            await session.flush()
            for sequence, (moment, quantity, amount, balance, value, average) in enumerate(
                [
                    (datetime(2026, 10, 1, 1, tzinfo=LOCAL_TZ), "10", "68", "10", "68", "6.8"),
                    (
                        datetime(2026, 10, 2, 23, 59, 59, tzinfo=LOCAL_TZ),
                        "2",
                        "20",
                        "12",
                        "88",
                        "7.333333",
                    ),
                    (datetime(2026, 10, 3, 0, 0, tzinfo=LOCAL_TZ), "8", "160", "20", "248", "12.4"),
                ],
                1,
            ):
                session.add(
                    InventoryValuationEntryModel(
                        company_id=company_id,
                        inventory_item_id=item.id,
                        sequence=sequence,
                        kind="opening" if sequence == 1 else "receipt",
                        quantity_base=Decimal(quantity),
                        source_value=Decimal(amount),
                        source_reference=f"DEMO-{sequence}",
                        idempotency_key=f"cut-value-{sequence}",
                        fingerprint=f"{sequence:064x}",
                        operational_date=moment.date(),
                        accounting_date=moment.date(),
                        posted_at=moment,
                        posted_by=actor.id,
                        inventory_delta=Decimal(amount),
                        balance_quantity=Decimal(balance),
                        balance_value=Decimal(value),
                        average_unit_cost=Decimal(average),
                        cost_breakdown=[],
                    )
                )
                if sequence == 1:
                    continue  # Already included in the approved physical baseline.
                movement = InventoryMovementModel(
                    company_id=company_id,
                    movement_type="receipt",
                    idempotency_key=f"cut-move-{sequence}",
                    request_fingerprint=f"{sequence:064x}",
                    source_reference=f"DEMO-{sequence}",
                    posted_at=moment,
                    posted_by=actor.id,
                    created_at=moment,
                )
                session.add(movement)
                await session.flush()
                session.add(
                    InventoryMovementLineModel(
                        company_id=company_id,
                        movement_id=movement.id,
                        line_number=1,
                        inventory_item_id=item.id,
                        to_warehouse_id=warehouse.id,
                        to_location_id=location.id,
                        to_stock_status="available",
                        quantity_base=Decimal(quantity),
                        occupied_weight_kg=Decimal("1"),
                        occupied_volume_m3=Decimal("0.001"),
                        measurement_status="complete",
                    )
                )
            await session.flush()
            repo = SqlAlchemyInventoryKardexReadRepository(session)
            for cut, quantity, value in [
                (date(2026, 10, 1), 10, 68),
                (date(2026, 10, 2), 12, 88),
                (date(2026, 10, 3), 20, 248),
            ]:
                result = await repo.reconciliation(
                    company_id=company_id, page=1, page_size=1, as_of=cut
                )
                row = result["items"][0]
                assert row["physical_quantity"] == quantity
                assert row["valued_quantity"] == quantity
                assert row["quantity_difference"] == 0
                assert row["inventory_value"] == value
                assert result["inventory_value"] == value
            early = await repo.reconciliation(
                company_id=company_id, page=1, page_size=1, as_of=date(2026, 9, 30)
            )
            assert early["balance_known"] is False
            assert early["items"][0]["physical_quantity"] is None
            other = Warehouse(
                company_id=company_id,
                branch_id=warehouse.branch_id,
                warehouse_category_id=warehouse.warehouse_category_id,
                code="SAME-BRANCH-PRIVATE",
                name="Bodega privada",
                is_central=False,
            )
            session.add(other)
            await session.flush()
            allowed, _ = await repo._physical_kardex_authorized_warehouses(
                company_id=company_id,
                warehouse_id=warehouse.id,
                raw_rows=[
                    {
                        "handling_unit_id": None,
                        "from_warehouse_id": warehouse.id,
                        "to_warehouse_id": other.id,
                    }
                ],
                access_all_branches=True,
                accessible_branch_ids={warehouse.branch_id},
                accessible_warehouse_ids={warehouse.id},
            )
            assert allowed == {warehouse.id}
        finally:
            await transaction.rollback()
    await dispose_engine()

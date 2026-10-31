"""PostgreSQL valuation-ledger acceptance for late landed costs and returns."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.inventory import InventoryMovementLineModel
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryValuationEntryModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id
from tests.integration.test_inventory_kardex_repository import _test_inventory_fixture

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgres_late_retaceo_and_supplier_return_conserve_exact_value() -> None:
    suffix = uuid.uuid4().hex
    company_id = await get_test_company_id()

    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            _, _, actor, remaining_item, _ = await _test_inventory_fixture(
                session, company_id, f"{suffix[:7]}a{suffix[8:]}"
            )
            _, _, _, return_item, _ = await _test_inventory_fixture(
                session, company_id, f"{suffix[:7]}b{suffix[8:]}"
            )
            session.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=datetime.now(UTC),
                    opened_by=actor.id,
                    opening_reference=f"IT-B4-{suffix}",
                    opening_fingerprint="a" * 64,
                    physical_snapshot=[],
                )
            )
            await session.flush()
            valuation = SqlAlchemyInventoryValuationRepository(session)

            receipt = await valuation.append(
                company_id=company_id,
                item_id=remaining_item.id,
                kind="receipt",
                quantity=Decimal("10"),
                value=Decimal("100"),
                actor_id=actor.id,
                key=f"it-b4-retaceo-receipt-{suffix}",
                reference=f"IT-B4-RECEIPT-{suffix}",
            )
            issue = await valuation.append(
                company_id=company_id,
                item_id=remaining_item.id,
                kind="issue",
                quantity=Decimal("6"),
                value=Decimal("0"),
                actor_id=actor.id,
                key=f"it-b4-retaceo-issue-{suffix}",
                reference=f"IT-B4-ISSUE-{suffix}",
            )
            adjustment = await valuation.append(
                company_id=company_id,
                item_id=remaining_item.id,
                kind="cost_adjustment",
                quantity=Decimal("0"),
                value=Decimal("20"),
                actor_id=actor.id,
                key=f"it-b4-retaceo-adjustment-{suffix}",
                reference=f"IT-B4-RETACEO-{suffix}",
                original_id=receipt.id,
            )

            assert adjustment.inventory_delta == Decimal("8.000000")
            assert adjustment.cost_breakdown == [
                {
                    "event_id": str(issue.id),
                    "kind": "issue",
                    "cost_delta": "12.000000",
                    "source_reference": f"IT-B4-ISSUE-{suffix}",
                    "sequence": str(issue.sequence),
                    "ledger_page": "0",
                }
            ]
            remaining_balance = await session.get(
                InventoryCostAverageModel, (company_id, remaining_item.id)
            )
            assert remaining_balance is not None
            assert remaining_balance.quantity_base == Decimal("4.000000")
            assert remaining_balance.inventory_value == Decimal("48.000000")
            assert (
                await session.scalar(
                    select(func.count(InventoryMovementLineModel.id)).where(
                        InventoryMovementLineModel.company_id == company_id,
                        InventoryMovementLineModel.inventory_item_id == remaining_item.id,
                    )
                )
                == 0
            )
            retry = await valuation.append(
                company_id=company_id,
                item_id=remaining_item.id,
                kind="cost_adjustment",
                quantity=Decimal("0"),
                value=Decimal("20"),
                actor_id=actor.id,
                key=f"it-b4-retaceo-adjustment-{suffix}",
                reference=f"IT-B4-RETACEO-{suffix}",
                original_id=receipt.id,
            )
            assert retry.id == adjustment.id
            assert (
                await session.scalar(
                    select(func.count(InventoryValuationEntryModel.id)).where(
                        InventoryValuationEntryModel.company_id == company_id,
                        InventoryValuationEntryModel.idempotency_key
                        == f"it-b4-retaceo-adjustment-{suffix}",
                    )
                )
                == 1
            )

            # Customer returns recover the effective cost of the original issue,
            # including the later landed-cost adjustment (12 per unit, not 10).
            customer_return = await valuation.append(
                company_id=company_id,
                item_id=remaining_item.id,
                kind="customer_return",
                quantity=Decimal("1"),
                value=Decimal("0"),
                actor_id=actor.id,
                key=f"it-b8-customer-return-after-retaceo-{suffix}",
                reference=f"IT-B8-CUSTOMER-RETURN-{suffix}",
                original_id=issue.id,
            )
            assert customer_return.inventory_delta == Decimal("12.000000")
            assert customer_return.balance_quantity == Decimal("5.000000")
            assert customer_return.balance_value == Decimal("60.000000")

            await valuation.append(
                company_id=company_id,
                item_id=return_item.id,
                kind="receipt",
                quantity=Decimal("10"),
                value=Decimal("100"),
                actor_id=actor.id,
                key=f"it-b4-return-receipt-a-{suffix}",
                reference=f"IT-B4-RETURN-RECEIPT-A-{suffix}",
            )
            await valuation.append(
                company_id=company_id,
                item_id=return_item.id,
                kind="receipt",
                quantity=Decimal("10"),
                value=Decimal("200"),
                actor_id=actor.id,
                key=f"it-b4-return-receipt-b-{suffix}",
                reference=f"IT-B4-RETURN-RECEIPT-B-{suffix}",
            )
            issued = await valuation.append(
                company_id=company_id,
                item_id=return_item.id,
                kind="issue",
                quantity=Decimal("15"),
                value=Decimal("0"),
                actor_id=actor.id,
                key=f"it-b4-return-issue-{suffix}",
                reference=f"IT-B4-RETURN-ISSUE-{suffix}",
            )
            returned = await valuation.append(
                company_id=company_id,
                item_id=return_item.id,
                kind="supplier_return",
                quantity=Decimal("5"),
                value=Decimal("0"),
                actor_id=actor.id,
                key=f"it-b4-supplier-return-{suffix}",
                reference=f"IT-B4-SUPPLIER-RETURN-{suffix}",
            )
            credit = await valuation.append(
                company_id=company_id,
                item_id=return_item.id,
                kind="supplier_credit",
                quantity=Decimal("0"),
                value=Decimal("100"),
                actor_id=actor.id,
                key=f"it-b4-supplier-credit-{suffix}",
                reference=f"IT-B4-SUPPLIER-CREDIT-{suffix}",
                original_id=returned.id,
            )
            return_balance = await session.get(
                InventoryCostAverageModel, (company_id, return_item.id)
            )
            assert return_balance is not None
            assert return_balance.quantity_base == Decimal("0.000000")
            assert return_balance.inventory_value == Decimal("0.000000")
            assert credit.cost_breakdown == [
                {
                    "event_id": str(returned.id),
                    "kind": "supplier_credit",
                    "credit_net": "100",
                    "inventory_cost": "75.000000",
                    "cost_difference": "25.000000",
                    "source_reference": f"IT-B4-SUPPLIER-RETURN-{suffix}",
                    "sequence": str(returned.sequence),
                    "ledger_page": "0",
                }
            ]
            assert issued.balance_value == Decimal("75.000000")
            assert returned.balance_quantity == Decimal("0.000000")
            assert returned.balance_value == Decimal("0.000000")
            assert credit.balance_quantity == Decimal("0.000000")
            assert credit.balance_value == Decimal("0.000000")
            assert credit.cost_breakdown[0]["inventory_cost"] == "75.000000"
            assert credit.cost_breakdown[0]["cost_difference"] == "25.000000"
        finally:
            await transaction.rollback()
    await dispose_engine()

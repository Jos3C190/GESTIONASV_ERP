"""Storage-only checks in one rolled-back transaction; no operational receipt is posted."""

import asyncio
import json
import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy import select

import app.infrastructure.models  # noqa: F401
from app.application.retaceos.use_cases import RetaceoFobDraft, RetaceoUseCases
from app.domain.entities.actual_expense import ActualPurchaseExpense
from app.domain.entities.purchase import PurchaseInventoryWorkflow
from app.domain.entities.retaceo import RetaceoCost, RetaceoCostAllocation, RetaceoCostClass, RetaceoStatus
from app.infrastructure.db.session import async_session_factory, async_engine
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.repositories.purchase_order_repository import SqlAlchemyPurchaseOrderRepository
from app.infrastructure.repositories.purchase_repository import SqlAlchemyPurchaseRepository
from app.infrastructure.repositories.retaceo_repository import SqlAlchemyRetaceoRepository


async def main():
    actual_id, retaceo_id = uuid.uuid4(), uuid.uuid4()
    async with async_session_factory() as session:
        try:
            row = await session.scalar(select(PurchaseModel).where(PurchaseModel.code == 'COM-00024'))
            assert row is not None
            purchase = await SqlAlchemyPurchaseRepository(session).get_purchase(row.company_id, row.id)
            orders = SqlAlchemyPurchaseOrderRepository(session)
            before = await orders.get_order(purchase.company_id, purchase.purchase_order_id)
            category = next(item for item in await orders.list_active_expense_types(purchase.company_id) if item.name == 'Otros')
            expense = ActualPurchaseExpense(actual_id, purchase.company_id, purchase.purchase_order_id,
                category.id, Decimal('40'), date(2026, 10, 27), 'QA-ROLLBACK', 'Verificación transaccional sin confirmar')
            await orders.add_actual_expense(expense)
            after = await orders.get_order(purchase.company_id, purchase.purchase_order_id)
            assert before.total == after.total and before.expenses == after.expenses
            assert any(item.id == actual_id for item in await orders.list_actual_expenses(purchase.company_id, purchase.purchase_order_id))
            eligible = tuple(line for line in purchase.details if (line.quantity_accepted or line.quantity_received) > 0)
            details = tuple(RetaceoFobDraft(line.id, Decimal('100')) for line in eligible)
            cost = RetaceoCost(uuid.uuid4(), retaceo_id, RetaceoCostClass.EXPENSE,
                'Otros: prueba de almacenamiento', Decimal('40'),
                allocations=(RetaceoCostAllocation(eligible[0].id, Decimal('40')),),
                source_purchase_order_expense_id=actual_id, expense_type_id=category.id,
                description='No es una operación de recepción; se revierte toda la transacción', incurred_on=expense.incurred_on)
            # A detached domain fixture exercises storage mapping only; the persisted purchase is untouched.
            fixture = replace(purchase, inventory_workflow=PurchaseInventoryWorkflow.AFTER_RETACEO)
            repository = SqlAlchemyRetaceoRepository(session)
            draft = RetaceoUseCases(repository, SqlAlchemyPurchaseRepository(session))._build_from_purchase(
                retaceo_id=retaceo_id, code='QA-' + retaceo_id.hex[:20], purchase=fixture,
                created_by_id=purchase.created_by_id, total_freight=Decimal('0'), total_expenses=Decimal('40'),
                total_dai=Decimal('0'), import_vat=Decimal('0'), notes='QA rollback', costs=(cost,),
                fob_lines=details, manual_entry=True)
            saved = await repository.add_retaceo(draft)
            assert saved.manual_entry and saved.costs[0].incurred_on == expense.incurred_on
            usage = await orders.actual_expense_usage(purchase.company_id, (actual_id,))
            assert usage[actual_id] == Decimal('40')
            await repository.update_status(purchase.company_id, retaceo_id, RetaceoStatus.CANCELLED)
            assert actual_id not in await orders.actual_expense_usage(purchase.company_id, (actual_id,))
        finally:
            await session.rollback()
    async with async_session_factory() as session:
        assert await SqlAlchemyRetaceoRepository(session).get_retaceo(purchase.company_id, retaceo_id) is None
        assert not any(item.id == actual_id for item in await SqlAlchemyPurchaseOrderRepository(session).list_actual_expenses(purchase.company_id, purchase.purchase_order_id))
    await async_engine.dispose()
    print(json.dumps({'budget_unchanged': True, 'manual_mapping': True, 'expense_usage': True, 'cancel_releases_reservation': True, 'rollback_confirmed': True}))


asyncio.run(main())

"""Exercise a hypothetical zero-charge correction in a transaction always rolled back.

FOB 1900 is confirmed by Rodrigo; zero freight/DAI/VAT here are test inputs only.
No real retaceo, cost or stock change is committed by this script.
"""
import asyncio
import json
from decimal import Decimal

from sqlalchemy import select

import app.infrastructure.models  # noqa: F401
from app.application.retaceos.use_cases import RetaceoFobDraft, RetaceoUseCases
from app.infrastructure.db.session import async_engine, async_session_factory
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.repositories.purchase_order_repository import SqlAlchemyPurchaseOrderRepository
from app.infrastructure.repositories.purchase_repository import SqlAlchemyPurchaseRepository
from app.infrastructure.repositories.retaceo_repository import SqlAlchemyRetaceoRepository
from app.infrastructure.repositories.inventory_valuation_repository import SqlAlchemyInventoryValuationRepository


async def main():
    async with async_session_factory() as session:
        try:
            model = await session.scalar(select(PurchaseModel).where(PurchaseModel.code == 'COM-00024'))
            purchase = await SqlAlchemyPurchaseRepository(session).get_purchase(model.company_id, model.id)
            original = tuple((line.id, line.subtotal, line.discount, line.total) for line in purchase.details)
            valuation = SqlAlchemyInventoryValuationRepository(session)
            repository = SqlAlchemyRetaceoRepository(session)
            cases = RetaceoUseCases(repository, SqlAlchemyPurchaseRepository(session), SqlAlchemyPurchaseOrderRepository(session), valuation=valuation)
            eligible = [line for line in purchase.details if (line.quantity_accepted or line.quantity_received) > 0]
            assert len(eligible) == 1
            item = await cases.create_draft(
                company_id=purchase.company_id, created_by_id=purchase.created_by_id, purchase_id=purchase.id,
                total_freight=Decimal('0'), total_dai=Decimal('0'), total_expenses=Decimal('0'), import_vat=Decimal('0'),
                fob_lines=(RetaceoFobDraft(eligible[0].id, Decimal('1900')),),
                notes='PRUEBA CON ROLLBACK: descuento 5% confirmado por Rodrigo; FOB 1900. Flete, DAI e IVA cero son solo datos de esta simulación, no hechos de la compra.')
            preview = await cases.average_comparison(purchase.company_id, item.id)
            assert preview.value_only and preview.lines[0].incoming_quantity == 0
            before_rows = list((await session.scalars(select(InventoryValuationEntryModel).where(InventoryValuationEntryModel.company_id == purchase.company_id))).all())
            historical = {row.id: (row.source_value, row.inventory_delta, row.balance_quantity, row.balance_value) for row in before_rows}
            await cases.calculate_retaceo(purchase.company_id, item.id)
            await cases.verify_retaceo(purchase.company_id, item.id)
            await cases.apply_retaceo(purchase.company_id, item.id, purchase.created_by_id)
            posted = await cases.average_comparison(purchase.company_id, item.id)
            assert posted.value_only and posted.mode == 'posted'
            assert posted.lines[0].resulting_quantity == preview.lines[0].resulting_quantity
            assert posted.lines[0].resulting_value == preview.lines[0].resulting_value
            assert all((row.source_value, row.inventory_delta, row.balance_quantity, row.balance_value) == historical[row.id] for row in before_rows)
            after_purchase = await SqlAlchemyPurchaseRepository(session).get_purchase(purchase.company_id, purchase.id)
            assert original == tuple((line.id, line.subtotal, line.discount, line.total) for line in after_purchase.details)
            await cases.apply_retaceo(purchase.company_id, item.id, purchase.created_by_id)
            report = {'preview_matches_posted': True, 'original_receipt_and_history_unchanged': True, 'quantity_unchanged': True, 'idempotent': True, 'hypothetical_fob': '1900', 'rollback': True}
        finally:
            await session.rollback()
    async with async_session_factory() as session:
        assert await SqlAlchemyRetaceoRepository(session).get_retaceo(purchase.company_id, item.id) is None
    await async_engine.dispose()
    print(json.dumps(report))


asyncio.run(main())

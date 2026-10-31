"""Rehearse COM-00022 with a fictional 500 CRC/USD rate; always roll back."""
import asyncio
import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.api.v1.schemas.purchase import PurchaseResponse
from app.application.audit.audit_service import AuditService
from app.application.purchases import PurchaseUseCases
from app.application.retaceos import RetaceoUseCases
from app.core.exceptions import ConflictError, BusinessRuleError
from app.domain.entities.purchase import PurchaseStatus, PurchaseVerificationLine
from app.domain.entities.purchase_conversion import PurchaseValuationConversion
from app.infrastructure.db.session import async_engine, async_session_factory
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel, InventoryRetaceoApplicationModel
from app.infrastructure.models.organization import Location
from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.repositories.inventory_valuation_repository import SqlAlchemyInventoryValuationRepository
from app.infrastructure.repositories.purchase_inventory_gateway import SqlAlchemyPurchaseInventoryGateway
from app.infrastructure.repositories.purchase_order_repository import SqlAlchemyPurchaseOrderRepository
from app.infrastructure.repositories.purchase_repository import SqlAlchemyPurchaseRepository
from app.infrastructure.repositories.retaceo_repository import SqlAlchemyRetaceoRepository
from seed.configure_demo_flour_presentations import COMPANY_ID, stock_fingerprint
from uuid import UUID

RECEIPT_ID = UUID('3efec936-fd3f-46d9-9e41-a09181fe9425')


async def main():
    assert async_engine.url.database == 'erp_db'
    before = None
    try:
        async with async_session_factory() as session:
            try:
                before = await stock_fingerprint(session)
                repository = SqlAlchemyPurchaseRepository(session)
                purchase = await repository.get_purchase(COMPANY_ID, RECEIPT_ID)
                assert purchase and purchase.status is PurchaseStatus.RECEIVED
                assert purchase.currency == 'CRC' and purchase.inventory_movement_id is None
                assert purchase.valuation_conversion is None
                orders = SqlAlchemyPurchaseOrderRepository(session)
                gateway = SqlAlchemyPurchaseInventoryGateway(session)
                use_cases = PurchaseUseCases(repository, orders, gateway)
                assert await use_cases.valuation_currency(COMPANY_ID) == 'USD'
                lines = []
                for detail in purchase.details:
                    code = 'A01-R01-N01-P01' if detail.product_id == 1 else 'A02-R01-N01-P01'
                    location = await session.scalar(select(Location.id).where(
                        Location.warehouse_id == purchase.warehouse_id, Location.code == code,
                        Location.is_active.is_(True), Location.lifecycle_status == 'active',
                    ))
                    assert location is not None
                    lines.append(PurchaseVerificationLine(detail.id, detail.quantity_received, location))
                try:
                    async with session.begin_nested():
                        await use_cases.verify_purchase(COMPANY_ID, RECEIPT_ID, lines=tuple(lines), actor_id=purchase.created_by_id)
                except ConflictError as missing:
                    assert missing.code == 'purchase_valuation_conversion_required'
                    print('MISSING_RATE_REJECTED_WITHOUT_WRITES')
                else:
                    raise AssertionError('Foreign receipt was accepted without a rate')
                assert before == await stock_fingerprint(session)
                conversion = PurchaseValuationConversion('USD', Decimal('500'), date(2026, 10, 21), 'SIMULACION FICTICIA - NO TASA DE MERCADO')
                verified = await use_cases.verify_purchase(
                    COMPANY_ID, RECEIPT_ID, lines=tuple(lines), actor_id=purchase.created_by_id,
                    valuation_conversion=conversion,
                )
                assert verified.status is PurchaseStatus.VERIFIED
                assert verified.currency == 'CRC' and verified.valuation_conversion == conversion
                assert [d.unit_price for d in verified.details] == [d.unit_price for d in purchase.details]
                response = PurchaseResponse.model_validate(verified).model_dump(mode='json')
                assert response['valuation_conversion']['rate'] == '500'
                await AuditService(SqlAlchemyAuditRepository(session)).record(
                    action='VERIFY', company_id=COMPANY_ID, resource_type='purchases',
                    resource_id=str(RECEIPT_ID), after_state=response,
                    metadata={'source': 'fictional_conversion_rehearsal_rolled_back'}, required=True,
                )
                entries = (await session.scalars(select(InventoryValuationEntryModel).where(
                    InventoryValuationEntryModel.company_id == COMPANY_ID,
                    InventoryValuationEntryModel.purchase_detail_id.in_([d.id for d in purchase.details]),
                    InventoryValuationEntryModel.kind == 'receipt',
                ))).all()
                for detail in purchase.details:
                    rows = [entry for entry in entries if entry.purchase_detail_id == detail.id]
                    assert sum((row.source_value for row in rows), Decimal('0')) == conversion.convert(detail.subtotal - detail.discount)
                after_verification = await stock_fingerprint(session)
                try:
                    await use_cases.verify_purchase(COMPANY_ID, RECEIPT_ID, lines=tuple(lines), actor_id=purchase.created_by_id, valuation_conversion=conversion)
                except BusinessRuleError as duplicate:
                    assert duplicate.code == 'purchase_not_verifiable'
                    print('SECOND_VERIFICATION_REJECTED')
                else:
                    raise AssertionError('A verified receipt was accepted again')
                assert after_verification == await stock_fingerprint(session)
                print(json.dumps({
                    'status_in_simulation': verified.status.value, 'source_currency': verified.currency,
                    'valuation_currency': conversion.currency, 'fictional_crc_per_usd': str(conversion.rate),
                    'original_fob_crc': str(sum((d.subtotal - d.discount for d in purchase.details), Decimal('0'))),
                    'posted_fob_usd': str(sum((entry.source_value for entry in entries), Decimal('0'))),
                    'rate_and_reference_persisted_within_transaction': response['valuation_conversion'],
                }))
                # Exercise conversion through the real landed-cost SQL bridge.
                # The legacy cost builder is used here, not a claim about attachments UI.
                valuation = SqlAlchemyInventoryValuationRepository(session)
                retaceos = RetaceoUseCases(SqlAlchemyRetaceoRepository(session), repository, valuation=valuation)
                draft = await retaceos.create_draft(
                    company_id=COMPANY_ID, created_by_id=purchase.created_by_id, purchase_id=RECEIPT_ID,
                    total_freight=Decimal('0'), total_expenses=Decimal('500'), total_dai=Decimal('0'),
                    import_vat=Decimal('0'), notes='Simulación FX con rollback; gasto ficticio CRC 500',
                )
                await retaceos.calculate_retaceo(COMPANY_ID, draft.id)
                await retaceos.verify_retaceo(COMPANY_ID, draft.id)
                await retaceos.apply_retaceo(COMPANY_ID, draft.id, purchase.created_by_id)
                summary = await session.scalar(select(InventoryRetaceoApplicationModel).where(
                    InventoryRetaceoApplicationModel.company_id == COMPANY_ID,
                    InventoryRetaceoApplicationModel.retaceo_id == draft.id,
                ))
                assert summary.summary['conversion'] == conversion.to_dict()
                first_summary = json.dumps(summary.summary, sort_keys=True)
                await retaceos.apply_retaceo(COMPANY_ID, draft.id, purchase.created_by_id)
                assert json.dumps(summary.summary, sort_keys=True) == first_summary
                print(json.dumps({'retaceo_applied_twice_without_duplicate': True, 'retaceo_summary': summary.summary}))
            finally:
                await session.rollback()
        async with async_session_factory() as session:
            assert before == await stock_fingerprint(session)
            persisted = await SqlAlchemyPurchaseRepository(session).get_purchase(COMPANY_ID, RECEIPT_ID)
            assert persisted.status is PurchaseStatus.RECEIVED
            assert persisted.currency == 'CRC' and persisted.valuation_conversion is None
            assert persisted.inventory_movement_id is None
            remaining = await session.scalar(select(InventoryRetaceoApplicationModel).where(
                InventoryRetaceoApplicationModel.company_id == COMPANY_ID,
                InventoryRetaceoApplicationModel.purchase_id == RECEIPT_ID,
            ))
            assert remaining is None
            print('ROLLBACK_VERIFIED_ALL_COMPANY_INVENTORY_PURCHASES_UNCHANGED')
    finally:
        await async_engine.dispose()


asyncio.run(main())

"""Exercise the real application boundary, always rolling simulated stock back."""
import asyncio
import json

from sqlalchemy import select

from app.application.purchases import PurchaseUseCases
from app.domain.entities.purchase import PurchaseStatus, PurchaseVerificationLine
from app.infrastructure.db.session import async_engine, async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import Location
from app.infrastructure.repositories.purchase_inventory_gateway import SqlAlchemyPurchaseInventoryGateway
from app.infrastructure.repositories.purchase_order_repository import SqlAlchemyPurchaseOrderRepository
from app.infrastructure.repositories.purchase_repository import SqlAlchemyPurchaseRepository
from seed.configure_demo_flour_presentations import COMPANY_ID, RECEIPT_ID, stock_fingerprint


async def main():
    if async_engine.url.database != "erp_db":
        raise RuntimeError("Unexpected database")
    before = None
    try:
        async with async_session_factory() as session:
            try:
                before = await stock_fingerprint(session)
                repository = SqlAlchemyPurchaseRepository(session)
                purchase = await repository.get_purchase(COMPANY_ID, RECEIPT_ID)
                assert purchase and purchase.status is PurchaseStatus.RECEIVED
                assert purchase.inventory_movement_id is None
                locations = {}
                for code in ("A01-R01-N01-P01", "A02-R01-N01-P01"):
                    locations[code] = await session.scalar(select(Location.id).where(
                        Location.warehouse_id == purchase.warehouse_id,
                        Location.code == code,
                        Location.is_active.is_(True),
                        Location.lifecycle_status == "active",
                    ))
                    assert locations[code], f"Location unavailable: {code}"
                lines = tuple(PurchaseVerificationLine(
                    detail.id, detail.quantity_received,
                    locations["A01-R01-N01-P01" if detail.product_id == 1 else "A02-R01-N01-P01"],
                ) for detail in purchase.details)
                use_cases = PurchaseUseCases(
                    repository, SqlAlchemyPurchaseOrderRepository(session),
                    SqlAlchemyPurchaseInventoryGateway(session),
                )
                simulated = await use_cases.verify_purchase(
                    COMPANY_ID, RECEIPT_ID, lines=lines, actor_id=purchase.created_by_id,
                )
                assert simulated.status is PurchaseStatus.VERIFIED
                assert simulated.inventory_movement_id is not None
                print(json.dumps({
                    "simulation": "complete_application_verification",
                    "status_within_transaction": simulated.status.value,
                    "movement_created_temporarily": str(simulated.inventory_movement_id),
                    "received_quantities_preserved": [str(d.quantity_received) for d in simulated.details],
                    "accepted_quantities": [str(d.quantity_accepted) for d in simulated.details],
                }))
            finally:
                await session.rollback()
        async with async_session_factory() as session:
            after = await stock_fingerprint(session)
            assert before == after, "Rollback did not restore all inventory and purchase rows"
            persisted = await SqlAlchemyPurchaseRepository(session).get_purchase(COMPANY_ID, RECEIPT_ID)
            assert persisted.status is PurchaseStatus.RECEIVED
            assert persisted.inventory_movement_id is None
            audit_rows = (await session.scalars(select(AuditLog).where(
                AuditLog.company_id == COMPANY_ID,
                AuditLog.resource_type == "inventory_packaging_definitions",
                AuditLog.metadata_["source"].astext == "user_authorized_demo_maintenance",
                AuditLog.metadata_["receipt"].astext == str(RECEIPT_ID),
            ))).all()
            assert len(audit_rows) == 2
            print(json.dumps({
                "rollback_verified": True, "all_company_stock_and_purchase_rows_unchanged": True,
                "persisted_receipt_status": persisted.status.value,
                "persisted_inventory_movement_id": None,
                "persisted_presentation_audits": [
                    {"id": str(row.id), "action": row.action,
                     "resource_id": row.resource_id, "presentation": row.after_state["code"]}
                    for row in audit_rows
                ],
            }))
    finally:
        await async_engine.dispose()


asyncio.run(main())

"""PostgreSQL invariants for the authorized inventory adjustment workflow."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.application.inventory import InventoryUseCases
from app.application.inventory_transfers.use_cases import InventoryTransferUseCases
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryMovementModel,
    InventoryPackagingModel,
)
from app.infrastructure.models.inventory_adjustment import (
    InventoryAdjustmentDocumentModel,
    InventoryAdjustmentModel,
)
from app.infrastructure.models.inventory_transfer import InventoryTransferDetailModel
from app.infrastructure.models.inventory_valuation import InventoryCostAverageModel
from app.infrastructure.models.organization import UserCompany
from app.infrastructure.repositories.inventory_adjustment_repository import (
    SqlAlchemyInventoryAdjustmentRepository,
)
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from tests.integration.test_inventory_transfer_repository import _create_context

pytestmark = pytest.mark.integration


async def _attach_valid_evidence(session, *, company_id, actor_id, adjustment_id, suffix: str):
    now = datetime.now(UTC)
    checksum = (suffix[:1] or "a") * 64
    asset = DocumentAssetModel(
        company_id=company_id,
        original_filename=f"support-{suffix[:12]}.pdf",
        extension="pdf",
        declared_content_type="application/pdf",
        detected_content_type="application/pdf",
        size_bytes=512,
        checksum_sha256=checksum,
        bucket="adjustment-test",
        object_key=f"adjustments/{suffix}.pdf",
        status="active",
        upload_expires_at=now + timedelta(hours=1),
        scanned_at=now,
        uploaded_by=actor_id,
    )
    session.add(asset)
    await session.flush()
    session.add(InventoryAdjustmentDocumentModel(
        company_id=company_id,
        adjustment_id=adjustment_id,
        document_id=asset.id,
        checksum_sha256=checksum,
        original_filename=asset.original_filename,
        linked_by_id=actor_id,
        linked_at=now,
        upload_completed_at=now,
    ))
    await session.flush()


@pytest.mark.asyncio
async def test_adjustment_application_uses_average_is_idempotent_and_rolls_back_late_failure(monkeypatch):
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            session.add(UserCompany(
                user_id=context.actor_id,
                company_id=context.company_id,
                is_default=True,
                access_all_branches=True,
            ))
            await session.flush()
            repository = SqlAlchemyInventoryAdjustmentRepository(session)
            before_average = await session.get(
                InventoryCostAverageModel, (context.company_id, context.item.id)
            )
            assert before_average is not None
            assert before_average.quantity_base == Decimal("10.000000")
            assert before_average.inventory_value == Decimal("25.000000")
            before_movement_count = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            )
            with pytest.raises(InventoryAdjustmentError, match="supera"):
                async with session.begin_nested():
                    await repository.create_adjustment(
                        company_id=context.company_id,
                        actor_id=context.actor_id,
                        warehouse_id=context.origin.id,
                        operational_date=date(2026, 10, 19),
                        accounting_date=date(2026, 10, 19),
                        reason="Salida mayor al saldo",
                        document_reference="ACTA-B05-INSUFICIENTE",
                        notes=None,
                        lines=[{
                            "inventory_item_id": context.item.id,
                            "location_id": context.source_location.id,
                            "direction": "decrease",
                            "quantity_base": Decimal("11"),
                            "stock_status": "available",
                            "handling_unit_id": context.handling_unit_id,
                        }],
                        idempotency_key=f"adjustment-insufficient-{suffix}",
                    )

            body = {
                "company_id": context.company_id,
                "actor_id": context.actor_id,
                "warehouse_id": context.origin.id,
                "operational_date": date(2026, 10, 19),
                "accounting_date": date(2026, 10, 19),
                "reason": "Conteo físico de ajuste",
                "document_reference": "ACTA-B05-001",
                "notes": None,
                "lines": [{
                    "inventory_item_id": context.item.id,
                    "location_id": context.source_location.id,
                    "direction": "increase",
                    "quantity_base": Decimal("2"),
                    "stock_status": "quarantine",
                    "documented_unit_cost": Decimal("3"),
                    "documented_total_cost": None,
                    "actual_gross_weight_kg": Decimal("1"),
                    "actual_volume_m3": Decimal("0.5"),
                }],
                "idempotency_key": f"adjustment-create-{suffix}",
            }
            draft = await repository.create_adjustment(**body)
            assert draft["status"] == "draft"
            assert draft["lines"][0]["documented_unit_cost"] == Decimal("3.000000")
            assert draft["lines"][0]["documented_total_cost"] == Decimal("6.000000")
            assert await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            ) == before_movement_count

            with pytest.raises(InventoryAdjustmentError, match="comprobante"):
                await repository.approve_adjustment(
                    company_id=context.company_id,
                    adjustment_id=draft["id"],
                    actor_id=context.actor_id,
                    expected_version=1,
                )
            await _attach_valid_evidence(
                session,
                company_id=context.company_id,
                actor_id=context.actor_id,
                adjustment_id=draft["id"],
                suffix=f"evidence-{suffix}",
            )
            approved = await repository.approve_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                expected_version=1,
            )
            assert approved["status"] == "approved"
            assert await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            ) == before_movement_count

            evidence_link = await session.scalar(select(InventoryAdjustmentDocumentModel).where(
                InventoryAdjustmentDocumentModel.company_id == context.company_id,
                InventoryAdjustmentDocumentModel.adjustment_id == draft["id"],
                InventoryAdjustmentDocumentModel.detached_at.is_(None),
            ))
            assert evidence_link is not None
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    await session.execute(update(DocumentAssetModel).where(
                        DocumentAssetModel.company_id == context.company_id,
                        DocumentAssetModel.id == evidence_link.document_id,
                    ).values(status="rejected"))
            assert await session.scalar(select(DocumentAssetModel.status).where(
                DocumentAssetModel.company_id == context.company_id,
                DocumentAssetModel.id == evidence_link.document_id,
            )) == "active"

            applied = await repository.apply_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                idempotency_key=f"adjustment-apply-{suffix}",
            )
            assert applied["status"] == "applied"
            assert applied["lines"][0]["movement_id"] is not None
            applied_again = await repository.apply_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                idempotency_key=f"adjustment-apply-{suffix}",
            )
            assert applied_again["applied_at"] == applied["applied_at"]
            assert await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            ) == before_movement_count + 1
            average = await session.get(
                InventoryCostAverageModel, (context.company_id, context.item.id)
            )
            assert average is not None
            assert average.quantity_base == Decimal("12.000000")
            assert average.inventory_value == Decimal("31.000000")
            assert average.average_unit_cost == Decimal("2.583333")

            rollback_body = {**body, "document_reference": "ACTA-B05-002", "idempotency_key": f"adjustment-create-fail-{suffix}"}
            rollback_draft = await repository.create_adjustment(**rollback_body)
            await _attach_valid_evidence(
                session,
                company_id=context.company_id,
                actor_id=context.actor_id,
                adjustment_id=rollback_draft["id"],
                suffix=f"rollback-{suffix}",
            )
            await repository.approve_adjustment(
                company_id=context.company_id,
                adjustment_id=rollback_draft["id"],
                actor_id=context.actor_id,
                expected_version=1,
            )
            movement_count_before_failure = await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            )
            average_before_failure = (average.quantity_base, average.inventory_value)
            handling_unit_count_before_failure = await session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(
                    InventoryHandlingUnitModel.company_id == context.company_id,
                    InventoryHandlingUnitModel.inventory_item_id == context.item.id,
                )
            )
            original_post = InventoryUseCases.post_movement

            async def post_then_fail(self, **kwargs):
                await original_post(self, **kwargs)
                raise InventoryAdjustmentError("Fallo tardío de prueba", code="forced_late_failure")

            monkeypatch.setattr(InventoryUseCases, "post_movement", post_then_fail)
            with pytest.raises(InventoryAdjustmentError, match="Fallo tardío"):
                async with session.begin_nested():
                    await repository.apply_adjustment(
                        company_id=context.company_id,
                        adjustment_id=rollback_draft["id"],
                        actor_id=context.actor_id,
                        idempotency_key=f"adjustment-apply-fail-{suffix}",
                    )
            monkeypatch.setattr(InventoryUseCases, "post_movement", original_post)
            await session.refresh(average)
            persisted_draft = await session.get(InventoryAdjustmentModel, rollback_draft["id"])
            assert persisted_draft is not None
            assert persisted_draft.status == "approved"
            assert await session.scalar(
                select(func.count(InventoryMovementModel.id)).where(
                    InventoryMovementModel.company_id == context.company_id
                )
            ) == movement_count_before_failure
            assert (average.quantity_base, average.inventory_value) == average_before_failure
            assert await session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(
                    InventoryHandlingUnitModel.company_id == context.company_id,
                    InventoryHandlingUnitModel.inventory_item_id == context.item.id,
                )
            ) == handling_unit_count_before_failure
        finally:
            await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_transfer_loss_adjustment_closes_transit_without_falsifying_receipt():
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            session.add(UserCompany(
                user_id=context.actor_id,
                company_id=context.company_id,
                is_default=True,
                access_all_branches=True,
            ))
            await session.flush()

            transfer_repository = SqlAlchemyInventoryTransferRepository(session)
            transfers = InventoryTransferUseCases(transfer_repository)
            transfer = await transfers.create_transfer(
                company_id=context.company_id,
                origin_warehouse_id=context.origin.id,
                destination_warehouse_id=context.destination.id,
                vehicle_id=context.vehicle_id,
                actor_id=context.actor_id,
                idempotency_key=f"adjustment-loss-create-{suffix}",
                lines=[{
                    "handling_unit_id": context.handling_unit_id,
                    "quantity_base": Decimal("10"),
                    "demand_allocations": [],
                    "excess_reason": "Prueba aislada de pérdida en tránsito",
                }],
            )
            dispatched = await transfers.dispatch_transfer(
                company_id=context.company_id,
                transfer_id=transfer["id"],
                vehicle_id=context.vehicle_id,
                idempotency_key=f"adjustment-loss-dispatch-{suffix}",
                actor_id=context.actor_id,
            )
            transfer_detail_id = dispatched["lines"][0]["id"]
            received = await transfers.receive_transfer(
                company_id=context.company_id,
                transfer_id=transfer["id"],
                lines=[{
                    "transfer_detail_id": transfer_detail_id,
                    "destination_location_id": context.destination_location.id,
                    "quantity_base": Decimal("8"),
                }],
                idempotency_key=f"adjustment-loss-receive-{suffix}",
                actor_id=context.actor_id,
            )
            assert received["status"] == "in_transit"
            incident_transfer = await transfers.open_incident(
                company_id=context.company_id,
                transfer_id=transfer["id"],
                idempotency_key=f"adjustment-loss-incident-{suffix}",
                actor_id=context.actor_id,
                reason="Faltan dos unidades en el conteo del vehículo.",
                evidence_reference="ACTA-INCIDENTE-B05",
            )
            incident_id = next(
                row["id"] for row in incident_transfer["incidents"] if row["status"] == "open"
            )
            transfer_detail = await session.scalar(select(InventoryTransferDetailModel).where(
                InventoryTransferDetailModel.company_id == context.company_id,
                InventoryTransferDetailModel.transfer_id == transfer["id"],
                InventoryTransferDetailModel.id == transfer_detail_id,
            ))
            assert transfer_detail is not None
            transit_unit = await session.scalar(select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == context.company_id,
                InventoryHandlingUnitModel.id == transfer_detail.transit_handling_unit_id,
            ))
            assert transit_unit is not None
            assert transit_unit.quantity_base == Decimal("2.000000")

            adjustments = SqlAlchemyInventoryAdjustmentRepository(session)
            draft = await adjustments.create_adjustment(
                company_id=context.company_id,
                actor_id=context.actor_id,
                warehouse_id=context.origin.id,
                operational_date=date(2026, 10, 19),
                accounting_date=date(2026, 10, 19),
                reason="Pérdida confirmada durante el traslado.",
                document_reference="ACTA-INCIDENTE-B05",
                notes="Prueba de 10 despachadas, 8 recibidas y 2 ajustadas.",
                idempotency_key=f"adjustment-loss-create-doc-{suffix}",
                transfer_id=transfer["id"],
                transfer_incident_id=incident_id,
                lines=[{
                    "inventory_item_id": context.item.id,
                    "location_id": transit_unit.location_id,
                    "direction": "decrease",
                    "quantity_base": Decimal("2"),
                    "stock_status": "in_transit",
                    "handling_unit_id": transit_unit.id,
                    "transfer_detail_id": transfer_detail_id,
                }],
            )
            await _attach_valid_evidence(
                session,
                company_id=context.company_id,
                actor_id=context.actor_id,
                adjustment_id=draft["id"],
                suffix=f"loss-evidence-{suffix}",
            )
            approved = await adjustments.approve_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                expected_version=1,
            )
            assert approved["status"] == "approved"

            applied = await adjustments.apply_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                idempotency_key=f"adjustment-loss-apply-{suffix}",
            )
            assert applied["status"] == "applied"
            current_transfer = await transfers.get_transfer(context.company_id, transfer["id"])
            assert current_transfer is not None
            assert current_transfer["status"] == "closed_with_adjustment"
            assert current_transfer["lines"][0]["quantity_dispatched"] == Decimal("10.000000")
            assert current_transfer["lines"][0]["quantity_received"] == Decimal("8.000000")
            assert current_transfer["lines"][0]["quantity_adjusted_out"] == Decimal("2.000000")
            assert current_transfer["lines"][0]["quantity_in_transit"] == Decimal("0.000000")
            average = await session.get(
                InventoryCostAverageModel,
                (context.company_id, context.item.id),
            )
            assert average is not None
            assert average.quantity_base == Decimal("8.000000")
            assert average.inventory_value == Decimal("20.000000")
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_ordinary_negative_adjustment_correction_preserves_origin_and_compensates_value():
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            session.add(UserCompany(
                user_id=context.actor_id,
                company_id=context.company_id,
                is_default=True,
                access_all_branches=True,
            ))
            await session.flush()

            packaging = InventoryPackagingModel(
                company_id=context.company_id,
                inventory_item_id=context.item.id,
                code=f"CORR-{suffix[:8]}",
                name="Caja de prueba",
                packaging_type="box",
                base_quantity=Decimal("10"),
                gross_weight_kg=Decimal("10"),
                volume_m3=Decimal("0.5"),
                is_current=True,
                is_active=True,
            )
            session.add(packaging)
            await session.flush()
            handling_unit = await session.get(InventoryHandlingUnitModel, context.handling_unit_id)
            assert handling_unit is not None
            handling_unit.packaging_definition_id = packaging.id
            await session.flush()

            repository = SqlAlchemyInventoryAdjustmentRepository(session)
            original = await repository.create_adjustment(
                company_id=context.company_id,
                actor_id=context.actor_id,
                warehouse_id=context.origin.id,
                operational_date=date(2026, 10, 19),
                accounting_date=date(2026, 10, 19),
                reason="Merma confirmada en conteo",
                document_reference="ACTA-CORR-ORIGINAL",
                notes=None,
                idempotency_key=f"correction-original-create-{suffix}",
                lines=[{
                    "inventory_item_id": context.item.id,
                    "location_id": context.source_location.id,
                    "direction": "decrease",
                    "quantity_base": Decimal("2"),
                    "stock_status": "available",
                    "handling_unit_id": context.handling_unit_id,
                }],
            )
            await _attach_valid_evidence(
                session,
                company_id=context.company_id,
                actor_id=context.actor_id,
                adjustment_id=original["id"],
                suffix=f"correction-original-{suffix}",
            )
            await repository.approve_adjustment(
                company_id=context.company_id,
                adjustment_id=original["id"],
                actor_id=context.actor_id,
                expected_version=1,
            )
            applied_original = await repository.apply_adjustment(
                company_id=context.company_id,
                adjustment_id=original["id"],
                actor_id=context.actor_id,
                idempotency_key=f"correction-original-apply-{suffix}",
            )
            assert applied_original["status"] == "applied"
            assert applied_original["lines"][0]["movement_line_id"] is not None

            correction = await repository.create_correction(
                company_id=context.company_id,
                adjustment_id=original["id"],
                actor_id=context.actor_id,
                reason="La merma fue registrada por error",
                document_reference="ACTA-CORR-RECTIFICACION",
                operational_date=date(2026, 10, 19),
                accounting_date=date(2026, 10, 19),
            )
            assert correction["status"] == "draft"
            assert correction["correction_of_id"] == original["id"]
            assert correction["lines"][0]["direction"] == "increase"
            assert correction["lines"][0]["quantity_base"] == Decimal("2.000000")
            assert correction["lines"][0]["documented_total_cost"] == Decimal("5.000000")

            await _attach_valid_evidence(
                session,
                company_id=context.company_id,
                actor_id=context.actor_id,
                adjustment_id=correction["id"],
                suffix=f"correction-new-{suffix}",
            )
            await repository.approve_adjustment(
                company_id=context.company_id,
                adjustment_id=correction["id"],
                actor_id=context.actor_id,
                expected_version=1,
            )
            applied_correction = await repository.apply_adjustment(
                company_id=context.company_id,
                adjustment_id=correction["id"],
                actor_id=context.actor_id,
                idempotency_key=f"correction-new-apply-{suffix}",
            )

            persisted_original = await repository.get_adjustment(context.company_id, original["id"])
            assert persisted_original is not None
            assert persisted_original["status"] == "applied"
            assert persisted_original["lines"][0]["movement_id"] == applied_original["lines"][0]["movement_id"]
            assert applied_correction["status"] == "applied"
            assert applied_correction["lines"][0]["movement_id"] != applied_original["lines"][0]["movement_id"]

            average = await session.get(
                InventoryCostAverageModel,
                (context.company_id, context.item.id),
            )
            assert average is not None
            assert average.quantity_base == Decimal("10.000000")
            assert average.inventory_value == Decimal("25.000000")
            restored_units = list((await session.scalars(select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == context.company_id,
                InventoryHandlingUnitModel.location_id == context.source_location.id,
                InventoryHandlingUnitModel.stock_status == "quarantine",
                InventoryHandlingUnitModel.quantity_base == Decimal("2.000000"),
                InventoryHandlingUnitModel.closed_at.is_(None),
            ))).all())
            assert len(restored_units) == 1
            assert restored_units[0].quantity_base == Decimal("2.000000")
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


@pytest.mark.asyncio
async def test_positive_adjustment_without_documented_cost_uses_existing_average():
    suffix = uuid.uuid4().hex
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            context = await _create_context(session, suffix)
            session.add(UserCompany(
                user_id=context.actor_id,
                company_id=context.company_id,
                is_default=True,
                access_all_branches=True,
            ))
            await session.flush()
            average = await session.get(
                InventoryCostAverageModel,
                (context.company_id, context.item.id),
            )
            assert average is not None
            assert average.average_unit_cost == Decimal("2.500000")

            repository = SqlAlchemyInventoryAdjustmentRepository(session)
            draft = await repository.create_adjustment(
                company_id=context.company_id,
                actor_id=context.actor_id,
                warehouse_id=context.origin.id,
                operational_date=date(2026, 10, 19),
                accounting_date=date(2026, 10, 19),
                reason="Diferencia positiva de conteo",
                document_reference="ACTA-PROMEDIO-B05",
                notes=None,
                idempotency_key=f"adjustment-average-create-{suffix}",
                lines=[{
                    "inventory_item_id": context.item.id,
                    "location_id": context.source_location.id,
                    "direction": "increase",
                    "quantity_base": Decimal("2"),
                    "stock_status": "quarantine",
                    "actual_gross_weight_kg": Decimal("1"),
                    "actual_volume_m3": Decimal("0.5"),
                }],
            )
            assert draft["lines"][0]["documented_total_cost"] is None
            await _attach_valid_evidence(
                session,
                company_id=context.company_id,
                actor_id=context.actor_id,
                adjustment_id=draft["id"],
                suffix=f"average-evidence-{suffix}",
            )
            await repository.approve_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                expected_version=1,
            )
            applied = await repository.apply_adjustment(
                company_id=context.company_id,
                adjustment_id=draft["id"],
                actor_id=context.actor_id,
                idempotency_key=f"adjustment-average-apply-{suffix}",
            )

            assert applied["status"] == "applied"
            assert applied["lines"][0]["documented_total_cost"] is None
            await session.refresh(average)
            assert average.quantity_base == Decimal("12.000000")
            assert average.inventory_value == Decimal("30.000000")
            assert average.average_unit_cost == Decimal("2.500000")
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()

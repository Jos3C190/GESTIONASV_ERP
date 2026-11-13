"""PostgreSQL checks for partial reception, discrepancies and their adjustments."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from app.application.inventory_transfers.use_cases import InventoryTransferUseCases
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.domain.entities.inventory_transfer import TransferDomainError
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
)
from app.infrastructure.models.inventory_adjustment import (
    InventoryAdjustmentDocumentModel,
    InventoryAdjustmentModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferDetailModel,
    InventoryTransferDiscrepancyModel,
    InventoryTransferModel,
)
from app.infrastructure.models.inventory_valuation import InventoryCostAverageModel
from app.infrastructure.models.organization import UserCompany
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.repositories.inventory_adjustment_repository import (
    SqlAlchemyInventoryAdjustmentRepository,
)
from app.infrastructure.repositories.inventory_repository import (
    SqlAlchemyInventoryRepository,
    _require_labelled_split_in_quarantine,
)
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from tests.integration.test_inventory_transfer_repository import TransferFixture, _create_context
from tests.integration.test_inventory_transfer_routes import (
    ALL_ROUTES,
    BranchRouteFixture,
    _approve,
    _create,
    _expect,
    _flush_in_savepoint,
    _lines,
    _new_driver,
    _submit,
)
from tests.integration.test_inventory_transfer_routes import (
    _run as _run_routes,
)

pytestmark = pytest.mark.integration

D = Decimal
DAMAGE = {"damage_type": "broken", "damage_notes": "Cajas rotas al descargar"}


@dataclass(slots=True)
class Ctx:
    session: Any
    base: TransferFixture
    transfers: InventoryTransferUseCases
    repository: SqlAlchemyInventoryTransferRepository
    adjustments: SqlAlchemyInventoryAdjustmentRepository
    suffix: str

    @property
    def company_id(self) -> uuid.UUID:
        return self.base.company_id

    @property
    def actor_id(self) -> uuid.UUID:
        return self.base.actor_id

    @property
    def destination_location(self) -> uuid.UUID:
        return self.base.destination_location.id

    def key(self, name: str) -> str:
        return f"{name}-{self.suffix}"

    async def restock(self, tag: str, quantity: str = "10") -> uuid.UUID:
        """More stock in the origin (a new handling unit), valued like the first one."""
        receipt = await SqlAlchemyInventoryRepository(self.session).post_movement(
            company_id=self.company_id,
            idempotency_key=f"restock-{tag}-{self.suffix}",
            movement_type="receipt",
            source_reference=f"transfer-discrepancy-restock:{tag}:{self.suffix}",
            lines=[
                {
                    "inventory_item_id": self.base.item.id,
                    "to_location_id": self.base.source_location.id,
                    "to_stock_status": "available",
                    "quantity_base": D(quantity),
                    "valuation_value": D(quantity) * D("2.5"),
                    "valuation_currency": "USD",
                    "handling_unit_code": f"RS-{tag}-{self.suffix}",
                    "actual_measures": {
                        "gross_weight_kg": D("10"),
                        "length_m": D("0.5"),
                        "width_m": D("0.5"),
                        "height_m": D("0.4"),
                    },
                }
            ],
            actor_id=self.actor_id,
        )
        unit_id: uuid.UUID = receipt["lines"][0]["handling_unit_id"]
        return unit_id

    async def dispatched(
        self,
        name: str = "t",
        quantity: str = "10",
        allocation: uuid.UUID | None = None,
        unit_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        line: dict[str, Any] = {
            "handling_unit_id": unit_id or self.base.handling_unit_id,
            "quantity_base": D(quantity),
            "demand_allocations": [],
            "excess_reason": "Despacho manual de prueba",
        }
        if allocation is not None:
            line["demand_allocations"] = [
                {"purchase_request_detail_id": allocation, "allocated_quantity": D(quantity)}
            ]
            line["excess_reason"] = None
        created = await self.transfers.create_transfer(
            company_id=self.company_id,
            origin_warehouse_id=self.base.origin.id,
            destination_warehouse_id=self.base.destination.id,
            vehicle_id=self.base.vehicle_id,
            lines=[line],
            idempotency_key=self.key(f"{name}-create"),
            actor_id=self.actor_id,
        )
        return await self.transfers.dispatch_transfer(
            company_id=self.company_id,
            transfer_id=created["id"],
            vehicle_id=self.base.vehicle_id,
            idempotency_key=self.key(f"{name}-dispatch"),
            actor_id=self.actor_id,
        )

    async def receive(self, transfer: dict[str, Any], key: str, **line: Any) -> dict[str, Any]:
        line.setdefault("destination_location_id", self.destination_location)
        line.setdefault("transfer_detail_id", transfer["lines"][0]["id"])
        return await self.transfers.receive_transfer(
            company_id=self.company_id,
            transfer_id=transfer["id"],
            lines=[line],
            idempotency_key=self.key(key),
            actor_id=self.actor_id,
        )

    async def command(self, name: str, transfer: dict[str, Any], key: str, **kwargs: Any):
        return await getattr(self.transfers, name)(
            company_id=self.company_id,
            transfer_id=transfer["id"],
            idempotency_key=self.key(key),
            actor_id=self.actor_id,
            **kwargs,
        )

    async def resolve_behind_the_back(self, discrepancy_id: uuid.UUID) -> None:
        """Close a discrepancy without the commands (as a concurrent request would have)."""
        row = await self.session.get(InventoryTransferDiscrepancyModel, discrepancy_id)
        assert row is not None
        row.status = "resolved"
        row.resolution = "released"
        row.resolved_by_id = self.actor_id
        row.resolved_at = datetime.now(UTC)
        await self.session.flush()

    async def get(self, transfer: dict[str, Any]) -> dict[str, Any]:
        current = await self.transfers.get_transfer(self.company_id, transfer["id"])
        assert current is not None
        return current

    async def unit(self, unit_id: uuid.UUID) -> InventoryHandlingUnitModel:
        unit = await self.session.get(InventoryHandlingUnitModel, unit_id)
        assert unit is not None
        await self.session.refresh(unit)
        return unit

    async def stock(self, location_id: uuid.UUID, status: str) -> Decimal:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(InventoryBalanceModel.quantity_base), 0)).where(
                InventoryBalanceModel.company_id == self.company_id,
                InventoryBalanceModel.inventory_item_id == self.base.item.id,
                InventoryBalanceModel.location_id == location_id,
                InventoryBalanceModel.stock_status == status,
            )
        )
        return Decimal(value)

    async def average(self) -> SimpleNamespace:
        """A snapshot (the ORM row is shared, so a later refresh would change it)."""
        row = await self.session.get(
            InventoryCostAverageModel, (self.company_id, self.base.item.id)
        )
        assert row is not None
        await self.session.refresh(row)
        return SimpleNamespace(
            quantity_base=Decimal(row.quantity_base),
            inventory_value=Decimal(row.inventory_value),
            average_unit_cost=Decimal(row.average_unit_cost),
        )

    async def attach_evidence(self, adjustment_id: uuid.UUID, tag: str) -> None:
        now = datetime.now(UTC)
        checksum = "b" * 64
        asset = DocumentAssetModel(
            company_id=self.company_id,
            original_filename=f"support-{tag[:12]}.pdf",
            extension="pdf",
            declared_content_type="application/pdf",
            detected_content_type="application/pdf",
            size_bytes=512,
            checksum_sha256=checksum,
            bucket="adjustment-test",
            object_key=f"adjustments/{tag}-{self.suffix}.pdf",
            status="active",
            upload_expires_at=now + timedelta(hours=1),
            scanned_at=now,
            uploaded_by=self.actor_id,
        )
        self.session.add(asset)
        await self.session.flush()
        self.session.add(
            InventoryAdjustmentDocumentModel(
                company_id=self.company_id,
                adjustment_id=adjustment_id,
                document_id=asset.id,
                checksum_sha256=checksum,
                original_filename=asset.original_filename,
                linked_by_id=self.actor_id,
                linked_at=now,
                upload_completed_at=now,
            )
        )
        await self.session.flush()

    async def prepare_adjustment(
        self, transfer: dict[str, Any], discrepancy: dict[str, Any], key: str, **extra: Any
    ) -> dict[str, Any]:
        return await self.adjustments.create_discrepancy_adjustment(
            company_id=self.company_id,
            actor_id=self.actor_id,
            transfer_id=transfer["id"],
            discrepancy_id=discrepancy["id"],
            idempotency_key=self.key(key),
            operational_date=date(2026, 10, 19),
            accounting_date=date(2026, 10, 19),
            reason="Regularización de la diferencia del traslado.",
            document_reference="ACTA-DIFERENCIA-01",
            **extra,
        )

    async def approve_and_apply(self, adjustment: dict[str, Any], key: str) -> dict[str, Any]:
        await self.attach_evidence(adjustment["id"], key)
        approved = await self.adjustments.approve_adjustment(
            company_id=self.company_id,
            adjustment_id=adjustment["id"],
            actor_id=self.actor_id,
            expected_version=adjustment["version"],
        )
        assert approved["status"] == "approved"
        return await self.adjustments.apply_adjustment(
            company_id=self.company_id,
            adjustment_id=adjustment["id"],
            actor_id=self.actor_id,
            idempotency_key=self.key(f"{key}-apply"),
        )


async def _run(body: Callable[[Ctx], Awaitable[None]]) -> None:
    suffix = uuid.uuid4().hex
    try:
        async with async_session_factory() as session:
            transaction = await session.begin()
            try:
                base = await _create_context(session, suffix)
                session.add(
                    UserCompany(
                        user_id=base.actor_id,
                        company_id=base.company_id,
                        is_default=True,
                        access_all_branches=True,
                    )
                )
                await session.flush()
                repository = SqlAlchemyInventoryTransferRepository(session)
                await body(
                    Ctx(
                        session=session,
                        base=base,
                        transfers=InventoryTransferUseCases(repository),
                        repository=repository,
                        adjustments=SqlAlchemyInventoryAdjustmentRepository(session),
                        suffix=suffix,
                    )
                )
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await dispose_engine()


def _same_response(first: dict[str, Any], replay: dict[str, Any]) -> bool:
    """A replay returns the saved response, which was stored as JSON."""
    return (
        str(first["id"]) == str(replay["id"])
        and first["status"] == replay["status"]
        and len(first["discrepancies"]) == len(replay["discrepancies"])
    )


def _damaged(discrepancies: list[dict[str, Any]]) -> dict[str, Any]:
    return next(row for row in discrepancies if row["kind"] == "damage")


# --------------------------------------------------------------------------- reception


@pytest.mark.asyncio
async def test_partial_receipt_keeps_the_transfer_on_the_road_until_the_rest_arrives() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        partial = await ctx.receive(transfer, "r1", quantity_base=D("4"))
        assert partial["status"] == "partially_received"
        line = partial["lines"][0]
        assert line["quantity_received"] == D("4")
        assert line["quantity_pending_reception"] == D("6")
        assert line["quantity_short_open"] == D("0")
        assert partial["received_at"] is None
        assert partial["closed_at"] is None
        assert partial["discrepancies"] == []
        assert partial["has_open_discrepancies"] is False

        done = await ctx.receive(transfer, "r2", quantity_base=D("6"))
        assert done["status"] == "received"
        assert done["received_at"] is not None
        assert done["closed_at"] is not None
        assert done["received_by_id"] == ctx.actor_id
        assert done["lines"][0]["quantity_pending_reception"] == D("0")
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("10")

    await _run(body)


@pytest.mark.asyncio
async def test_good_and_damaged_goods_arrive_in_one_line_and_the_damage_is_posted_first() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer,
            "r1",
            quantity_base=D("6"),
            damaged_quantity=D("4"),
            evidence_reference="FOTO-DESCARGA-01",
            **DAMAGE,
        )
        assert received["status"] == "discrepancy"
        assert received["received_at"] is not None
        assert received["closed_at"] is None
        assert received["has_open_discrepancies"] is True
        assert received["origin_count_pending"] is False
        line = received["lines"][0]
        assert line["quantity_received"] == D("10")
        assert line["quantity_received_damaged"] == D("4")
        assert line["quantity_pending_reception"] == D("0")
        conditions = {row["condition"]: row["quantity_received"] for row in line["receipts"]}
        assert conditions == {"damaged": D("4"), "good": D("6")}

        damage = _damaged(received["discrepancies"])
        assert damage["status"] == "open"
        assert damage["source"] == "receipt"
        assert damage["quantity"] == D("4")
        assert damage["damage_type"] == "broken"
        assert damage["notes"] == DAMAGE["damage_notes"]
        assert damage["evidence_reference"] == "FOTO-DESCARGA-01"
        assert damage["location_id"] == ctx.destination_location
        assert damage["origin_count_required"] is False
        assert damage["adjustment"] is None

        # The movement posts the damaged part first and the good part second.
        movement_id = line["receipts"][0]["movement_id"]
        statuses = list(
            (
                await ctx.session.scalars(
                    select(InventoryMovementLineModel.to_stock_status)
                    .where(InventoryMovementLineModel.movement_id == movement_id)
                    .order_by(InventoryMovementLineModel.line_number)
                )
            ).all()
        )
        assert statuses == ["damaged", "quarantine"]

        assert await ctx.stock(ctx.destination_location, "damaged") == D("4")
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("6")
        unit = await ctx.unit(damage["handling_unit_id"])
        assert unit.stock_status == "damaged"
        assert unit.quantity_base == D("4")
        assert unit.location_id == ctx.destination_location
        # The sellable part is separate from the damaged one.
        good_unit = await ctx.unit(
            next(r["handling_unit_id"] for r in line["receipts"] if r["condition"] == "good")
        )
        assert good_unit.stock_status == "quarantine"
        assert good_unit.quantity_base == D("6")

    await _run(body)


@pytest.mark.asyncio
async def test_everything_damaged_moves_the_whole_unit_to_damaged_stock() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("0"), damaged_quantity=D("10"), **DAMAGE
        )
        assert received["status"] == "discrepancy"
        line = received["lines"][0]
        assert [row["condition"] for row in line["receipts"]] == ["damaged"]
        assert await ctx.stock(ctx.destination_location, "damaged") == D("10")
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("0")
        damage = _damaged(received["discrepancies"])
        unit = await ctx.unit(damage["handling_unit_id"])
        assert unit.stock_status == "damaged"
        assert unit.quantity_base == D("10")

    await _run(body)


@pytest.mark.asyncio
async def test_a_partial_receipt_with_damage_keeps_waiting_for_the_rest() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        partial = await ctx.receive(
            transfer, "r1", quantity_base=D("3"), damaged_quantity=D("2"), **DAMAGE
        )
        # Something is still on the way, so the open damage does not decide the status yet.
        assert partial["status"] == "partially_received"
        assert partial["lines"][0]["quantity_pending_reception"] == D("5")
        assert len(partial["discrepancies"]) == 1
        done = await ctx.receive(transfer, "r2", quantity_base=D("5"))
        assert done["status"] == "discrepancy"
        assert done["lines"][0]["quantity_received_damaged"] == D("2")
        assert await ctx.stock(ctx.destination_location, "damaged") == D("2")
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("8")

    await _run(body)


@pytest.mark.asyncio
async def test_a_surplus_opens_a_discrepancy_without_adding_stock() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer,
            "r1",
            quantity_base=D("10"),
            surplus_quantity=D("2"),
            surplus_notes="Llegaron dos cajas de más en el camión",
        )
        assert received["status"] == "discrepancy"
        assert received["origin_count_pending"] is True
        surplus = next(row for row in received["discrepancies"] if row["kind"] == "surplus")
        assert surplus["quantity"] == D("2")
        assert surplus["origin_count_required"] is True
        assert surplus["handling_unit_id"] is None
        assert surplus["location_id"] == ctx.destination_location
        assert received["lines"][0]["quantity_surplus"] == D("2")
        # The surplus is not stock until an approved adjustment says so.
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("10")

    await _run(body)


@pytest.mark.asyncio
async def test_receipt_errors_leave_nothing_behind() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()

        async def refuse(code: str, **line: Any) -> None:
            with pytest.raises(TransferDomainError) as raised:
                async with ctx.session.begin_nested():
                    await ctx.receive(transfer, f"bad-{code}", **line)
            assert raised.value.code == code, raised.value.message

        await refuse("transfer_receipt_empty", quantity_base=D("0"))
        await refuse(
            "transfer_over_receipt", quantity_base=D("8"), damaged_quantity=D("3"), **DAMAGE
        )
        await refuse(
            "transfer_surplus_requires_full_receipt",
            quantity_base=D("5"),
            surplus_quantity=D("1"),
            surplus_notes="Una caja de más",
        )
        await refuse(
            "transfer_damage_details_required", quantity_base=D("5"), damaged_quantity=D("1")
        )
        await refuse(
            "transfer_surplus_notes_required", quantity_base=D("10"), surplus_quantity=D("1")
        )
        await refuse(
            "transfer_receipt_location_invalid",
            quantity_base=D("5"),
            damaged_quantity=D("1"),
            damaged_location_id=ctx.base.source_location.id,
            **DAMAGE,
        )
        current = await ctx.get(transfer)
        assert current["status"] == "in_transit"
        assert current["lines"][0]["quantity_received"] == D("0")
        assert current["discrepancies"] == []

    await _run(body)


@pytest.mark.asyncio
async def test_demand_allocations_count_what_arrived_and_what_arrived_damaged() -> None:
    async def body(ctx: Ctx) -> None:
        request = PurchaseRequestModel(
            company_id=ctx.company_id,
            code=f"ITR-D-{ctx.suffix[:12]}",
            branch_id=ctx.base.destination.branch_id,
            warehouse_id=ctx.base.destination.id,
            requested_by_id=ctx.actor_id,
            justification="Demanda ficticia para comprobar las averías recibidas.",
            status="approved",
        )
        ctx.session.add(request)
        await ctx.session.flush()
        request_line = PurchaseRequestDetailModel(
            purchase_request_id=request.id,
            company_id=ctx.company_id,
            product_id=ctx.base.item.product_id,
            unit_id=ctx.base.item.base_unit_id,
            quantity=D("10"),
        )
        ctx.session.add(request_line)
        await ctx.session.flush()
        transfer = await ctx.dispatched(allocation=request_line.id)
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        allocation = received["lines"][0]["demand_allocations"][0]
        assert allocation["quantity_received"] == D("10")
        assert allocation["quantity_damaged"] == D("4")

    await _run(body)


# --------------------------------------------------------------------------- incidents


@pytest.mark.asyncio
async def test_an_incident_can_be_opened_from_partial_reception_and_resumed() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("4"))
        incident = await ctx.command(
            "open_incident", transfer, "inc", reason="El vehículo sufrió un desperfecto."
        )
        assert incident["status"] == "incident"
        resumed = await ctx.command(
            "resolve_incident",
            transfer,
            "inc-resume",
            resolution="resume_transit",
            resolution_notes="El vehículo continúa su camino.",
        )
        # Part of the load already arrived, so the transfer goes back to partial reception.
        assert resumed["status"] == "partially_received"
        done = await ctx.receive(transfer, "r2", quantity_base=D("6"))
        assert done["status"] == "received"

    await _run(body)


@pytest.mark.asyncio
async def test_resuming_an_incident_before_anything_arrived_returns_to_in_transit() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.command("open_incident", transfer, "inc", reason="Retraso por accidente vial.")
        resumed = await ctx.command(
            "resolve_incident",
            transfer,
            "inc-resume",
            resolution="resume_transit",
            resolution_notes="Se despejó la vía y continúa.",
        )
        assert resumed["status"] == "in_transit"

    await _run(body)


# --------------------------------------------------------------------------- reception close


@pytest.mark.asyncio
async def test_closing_the_reception_declares_the_missing_goods_as_shortages() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        with pytest.raises(TransferDomainError) as nothing:
            await ctx.command("close_reception", transfer, "close-0", reason="No llegó el resto")
        assert nothing.value.code == "transfer_reception_close_requires_receipt"
        assert nothing.value.message == "Si no llegó nada, reporta una incidencia del traslado."

        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        closed = await ctx.command(
            "close_reception",
            transfer,
            "close",
            reason="El resto no llegó en el vehículo",
            evidence_reference="ACTA-RECEPCION-01",
        )
        assert closed["status"] == "discrepancy"
        assert closed["received_at"] is not None
        shortage = closed["discrepancies"][0]
        assert shortage["kind"] == "shortage"
        assert shortage["status"] == "open"
        assert shortage["source"] == "reception_close"
        assert shortage["quantity"] == D("4")
        assert shortage["origin_count_required"] is True
        assert shortage["evidence_reference"] == "ACTA-RECEPCION-01"
        assert closed["origin_count_pending"] is True
        line = closed["lines"][0]
        assert line["quantity_short_open"] == D("4")
        assert line["quantity_pending_reception"] == D("0")
        # What is declared missing is still in the vehicle until it is written off.
        assert line["quantity_in_transit"] == D("4")
        with pytest.raises(TransferDomainError) as again:
            await ctx.command("close_reception", transfer, "close-2", reason="Otra vez el cierre")
        assert again.value.code == "transfer_reception_close_not_allowed"

    await _run(body)


@pytest.mark.asyncio
async def test_a_shortage_that_turns_up_reopens_the_reception_and_closes_clean() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        closed = await ctx.command(
            "close_reception", transfer, "close", reason="El resto no llegó en el vehículo"
        )
        shortage = closed["discrepancies"][0]
        found = await ctx.command(
            "mark_shortage_found",
            transfer,
            "found",
            discrepancy_id=shortage["id"],
            notes="Apareció en la bodega de carga.",
        )
        assert found["status"] == "partially_received"
        row = found["discrepancies"][0]
        assert row["status"] == "cancelled"
        assert row["resolution"] == "found"
        assert found["lines"][0]["quantity_pending_reception"] == D("4")
        done = await ctx.receive(transfer, "r2", quantity_base=D("4"))
        # The shortage was cancelled, so nothing was left to adjust.
        assert done["status"] == "received"
        assert done["closed_at"] is not None

    await _run(body)


@pytest.mark.asyncio
async def test_the_origin_count_is_recorded_once() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        closed = await ctx.command("close_reception", transfer, "close", reason="Resto no llegó")
        shortage = closed["discrepancies"][0]
        counted = await ctx.command(
            "acknowledge_origin_count",
            transfer,
            "count",
            discrepancy_id=shortage["id"],
            notes="Se contó el origen: coincide.",
        )
        row = counted["discrepancies"][0]
        assert row["origin_counted_by_id"] == ctx.actor_id
        assert row["origin_counted_at"] is not None
        assert row["origin_count_notes"] == "Se contó el origen: coincide."
        assert counted["origin_count_pending"] is False
        assert counted["status"] == "discrepancy"
        with pytest.raises(TransferDomainError) as repeated:
            await ctx.command(
                "acknowledge_origin_count",
                transfer,
                "count-2",
                discrepancy_id=shortage["id"],
                notes="Segundo conteo en el origen.",
            )
        assert repeated.value.code == "transfer_origin_count_already_recorded"
        # A damage never asks for an origin count.
        other = await ctx.dispatched("second", unit_id=await ctx.restock("second"))
        damaged = await ctx.receive(
            other, "o1", quantity_base=D("0"), damaged_quantity=D("10"), **DAMAGE
        )
        with pytest.raises(TransferDomainError) as invalid:
            await ctx.command(
                "acknowledge_origin_count",
                other,
                "count-3",
                discrepancy_id=_damaged(damaged["discrepancies"])["id"],
                notes="No corresponde a una avería",
            )
        assert invalid.value.code == "transfer_discrepancy_action_invalid"

    await _run(body)


# --------------------------------------------------------------------------- damage handling


@pytest.mark.asyncio
async def test_releasing_a_damage_returns_it_to_quarantine_and_closes_with_adjustment() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        damage = _damaged(received["discrepancies"])
        released = await ctx.command(
            "release_damage",
            transfer,
            "release",
            discrepancy_id=damage["id"],
            notes="Inspección: el producto está en buen estado.",
        )
        row = _damaged(released["discrepancies"])
        assert row["status"] == "resolved"
        assert row["resolution"] == "released"
        assert released["status"] == "closed_with_adjustment"
        assert released["closed_at"] is not None
        unit = await ctx.unit(damage["handling_unit_id"])
        assert unit.stock_status == "quarantine"
        assert await ctx.stock(ctx.destination_location, "damaged") == D("0")
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("10")
        with pytest.raises(TransferDomainError) as again:
            await ctx.command(
                "release_damage",
                transfer,
                "release-2",
                discrepancy_id=damage["id"],
                notes="Segunda liberación",
            )
        assert again.value.code == "transfer_discrepancy_not_open"

    await _run(body)


@pytest.mark.asyncio
async def test_a_claim_closes_the_transfer_and_the_damage_can_be_released_later() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        damage = _damaged(received["discrepancies"])
        with pytest.raises(TransferDomainError) as wrong_kind:
            await ctx.command(
                "mark_shortage_found",
                transfer,
                "wrong",
                discrepancy_id=damage["id"],
                notes="No es un faltante",
            )
        assert wrong_kind.value.code == "transfer_discrepancy_action_invalid"

        claimed = await ctx.command(
            "claim_discrepancy",
            transfer,
            "claim",
            discrepancy_id=damage["id"],
            claim_reference="RECLAMO-TRANSPORTISTA-77",
        )
        row = _damaged(claimed["discrepancies"])
        assert row["status"] == "in_claim"
        assert row["claim_reference"] == "RECLAMO-TRANSPORTISTA-77"
        assert row["claimed_by_id"] == ctx.actor_id
        # A damage in claim does not hold the transfer back.
        assert claimed["status"] == "closed_with_adjustment"
        assert claimed["has_open_discrepancies"] is False
        assert await ctx.stock(ctx.destination_location, "damaged") == D("4")

        released = await ctx.command(
            "release_damage",
            transfer,
            "release",
            discrepancy_id=damage["id"],
            notes="Tras el reclamo se inspeccionó y está bien.",
        )
        assert _damaged(released["discrepancies"])["resolution"] == "released"
        # A final state is never reopened.
        assert released["status"] == "closed_with_adjustment"
        assert await ctx.stock(ctx.destination_location, "damaged") == D("0")

    await _run(body)


@pytest.mark.asyncio
async def test_a_dismissed_surplus_is_cancelled_and_the_transfer_closes_clean() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer,
            "r1",
            quantity_base=D("10"),
            surplus_quantity=D("2"),
            surplus_notes="Parecían dos cajas de más",
        )
        surplus = received["discrepancies"][0]
        dismissed = await ctx.command(
            "dismiss_surplus",
            transfer,
            "dismiss",
            discrepancy_id=surplus["id"],
            notes="Se recontó: fue un error de conteo.",
        )
        row = dismissed["discrepancies"][0]
        assert row["status"] == "cancelled"
        assert row["resolution"] == "dismissed"
        assert dismissed["lines"][0]["quantity_surplus"] == D("0")
        assert dismissed["status"] == "received"

    await _run(body)


# --------------------------------------------------------------------------- engine rule


def test_labelled_lots_may_be_split_into_damaged_stock_only_on_a_transfer_receipt() -> None:
    kwargs = {"label_confirmation_required": True, "from_status": "in_transit"}
    _require_labelled_split_in_quarantine(
        movement_type="transfer", to_status="quarantine", **kwargs
    )
    _require_labelled_split_in_quarantine(movement_type="transfer", to_status="damaged", **kwargs)
    for movement_type, to_status in (("transfer", "available"), ("putaway", "damaged")):
        with pytest.raises(Exception, match="Fraccione la unidad nueva"):
            _require_labelled_split_in_quarantine(
                movement_type=movement_type, to_status=to_status, **kwargs
            )


# --------------------------------------------------------------------------- adjustments


@pytest.mark.asyncio
async def test_a_shortage_adjustment_is_unique_immutable_and_settles_the_transfer() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        closed = await ctx.command(
            "close_reception", transfer, "close", reason="El resto no llegó en el vehículo"
        )
        shortage = closed["discrepancies"][0]
        average_before = await ctx.average()

        draft = await ctx.prepare_adjustment(transfer, shortage, "adj")
        assert draft["status"] == "draft"
        assert draft["transfer_id"] == transfer["id"]
        assert draft["transfer_incident_id"] is None
        assert draft["transfer_discrepancy_id"] == shortage["id"]
        assert draft["transfer_discrepancy_kind"] == "shortage"
        assert draft["transfer_reference"] == transfer["code"]
        assert draft["warehouse_id"] == ctx.base.origin.id
        line = draft["lines"][0]
        assert (line["direction"], line["stock_status"], line["quantity_base"]) == (
            "decrease",
            "in_transit",
            D("4"),
        )
        # One active adjustment per discrepancy: another key or the same one returns it.
        for key in ("adj", "adj-other-key"):
            again = await ctx.prepare_adjustment(transfer, shortage, key)
            assert again["id"] == draft["id"]
        with pytest.raises(InventoryAdjustmentError) as changed:
            await ctx.prepare_adjustment(transfer, shortage, "adj", notes="Contenido distinto")
        assert changed.value.code == "adjustment_idempotency_conflict"

        # The linked adjustment cannot be edited or corrected.
        with pytest.raises(InventoryAdjustmentError) as immutable:
            await ctx.adjustments.update_adjustment(
                company_id=ctx.company_id,
                adjustment_id=draft["id"],
                actor_id=ctx.actor_id,
                operational_date=date(2026, 10, 19),
                accounting_date=date(2026, 10, 19),
                reason="Intento de edición",
                document_reference="ACTA",
                notes=None,
                lines=[],
            )
        assert immutable.value.code == "adjustment_linked_document_immutable"
        # Claiming applies to damages only; and a shortage with a draft cannot be marked found
        # silently: the stale draft is refused when it is approved.
        applied = await ctx.approve_and_apply(draft, "adj")
        assert applied["status"] == "applied"
        with pytest.raises(InventoryAdjustmentError) as correction:
            await ctx.adjustments.create_correction(
                company_id=ctx.company_id,
                adjustment_id=draft["id"],
                actor_id=ctx.actor_id,
                reason="Corrección",
                document_reference="ACTA",
                operational_date=date(2026, 10, 19),
                accounting_date=date(2026, 10, 19),
            )
        assert correction.value.code == "adjustment_correction_not_supported"

        current = await ctx.get(transfer)
        row = current["discrepancies"][0]
        assert (row["status"], row["resolution"]) == ("resolved", "written_off")
        assert row["adjustment"]["code"] == draft["code"]
        assert current["status"] == "closed_with_adjustment"
        assert current["closed_at"] is not None
        assert current["lines"][0]["quantity_adjusted_out"] == D("4")
        assert current["lines"][0]["quantity_in_transit"] == D("0")
        average_after = await ctx.average()
        assert average_after.quantity_base == average_before.quantity_base - D("4")

    await _run(body)


@pytest.mark.asyncio
async def test_a_damage_write_off_removes_the_damaged_stock_at_average_cost() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        damage = _damaged(received["discrepancies"])
        average_before = await ctx.average()
        draft = await ctx.prepare_adjustment(transfer, damage, "damage-adj")
        # A damage lives at the destination and carries no transfer id, only its discrepancy.
        assert draft["transfer_id"] is None
        assert draft["transfer_discrepancy_id"] == damage["id"]
        assert draft["transfer_discrepancy_kind"] == "damage"
        assert draft["linked_transfer_id"] == transfer["id"]
        assert draft["warehouse_id"] == ctx.base.destination.id
        assert draft["lines"][0]["stock_status"] == "damaged"
        # It cannot be claimed while an adjustment is in progress.
        with pytest.raises(TransferDomainError) as busy:
            await ctx.command(
                "claim_discrepancy",
                transfer,
                "claim",
                discrepancy_id=damage["id"],
                claim_reference="RECLAMO-01",
            )
        assert busy.value.code == "transfer_discrepancy_has_adjustment"

        await ctx.approve_and_apply(draft, "damage-adj")
        current = await ctx.get(transfer)
        assert (_damaged(current["discrepancies"])["resolution"]) == "written_off"
        assert current["status"] == "closed_with_adjustment"
        assert await ctx.stock(ctx.destination_location, "damaged") == D("0")
        assert await ctx.stock(ctx.destination_location, "quarantine") == D("6")
        average_after = await ctx.average()
        assert average_after.quantity_base == average_before.quantity_base - D("4")
        assert average_after.inventory_value == D("15.000000")

    await _run(body)


@pytest.mark.asyncio
async def test_a_surplus_regularisation_enters_quarantine_at_documented_or_average_cost() -> None:
    async def body(ctx: Ctx) -> None:
        first = await ctx.dispatched("a")
        received = await ctx.receive(
            first,
            "ra",
            quantity_base=D("10"),
            surplus_quantity=D("2"),
            surplus_notes="Llegaron dos unidades de más",
        )
        surplus = received["discrepancies"][0]
        average_before = await ctx.average()
        with pytest.raises(InventoryAdjustmentError) as measures:
            # Without a registered presentation or measures the surplus cannot be packed.
            await ctx.prepare_adjustment(
                first, surplus, "no-measures", actual_gross_weight_kg=D("1")
            )
        assert measures.value.code == "adjustment_surplus_measures_required"
        draft = await ctx.prepare_adjustment(
            first,
            surplus,
            "surplus",
            actual_gross_weight_kg=D("2"),
            actual_volume_m3=D("0.01"),
            documented_total_cost=D("8"),
        )
        line = draft["lines"][0]
        assert (line["direction"], line["stock_status"]) == ("increase", "quarantine")
        assert line["location_id"] == ctx.destination_location
        applied = await ctx.approve_and_apply(draft, "surplus")
        assert applied["status"] == "applied"
        current = await ctx.get(first)
        row = current["discrepancies"][0]
        assert (row["status"], row["resolution"]) == ("resolved", "regularized")
        assert row["handling_unit_id"] is not None
        unit = await ctx.unit(row["handling_unit_id"])
        assert (unit.stock_status, unit.quantity_base) == ("quarantine", D("2"))
        assert current["status"] == "closed_with_adjustment"
        average_after = await ctx.average()
        assert average_after.quantity_base == average_before.quantity_base + D("2")
        assert average_after.inventory_value == average_before.inventory_value + D("8")

        # Without a documented cost the surplus enters at the current average.
        second = await ctx.dispatched("b", unit_id=await ctx.restock("b"))
        received_b = await ctx.receive(
            second,
            "rb",
            quantity_base=D("10"),
            surplus_quantity=D("1"),
            surplus_notes="Una unidad de más",
        )
        average_mid = await ctx.average()
        draft_b = await ctx.prepare_adjustment(
            second,
            received_b["discrepancies"][0],
            "surplus-b",
            actual_gross_weight_kg=D("1"),
            actual_volume_m3=D("0.01"),
        )
        await ctx.approve_and_apply(draft_b, "surplus-b")
        average_end = await ctx.average()
        assert average_end.quantity_base == average_mid.quantity_base + D("1")
        assert average_end.inventory_value == (
            average_mid.inventory_value + average_mid.average_unit_cost
        ).quantize(D("0.000001"))

    await _run(body)


@pytest.mark.asyncio
async def test_an_old_approval_cannot_be_applied_against_a_closed_discrepancy() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        damage = _damaged(received["discrepancies"])
        draft = await ctx.prepare_adjustment(transfer, damage, "stale")
        await ctx.attach_evidence(draft["id"], "stale")
        approved = await ctx.adjustments.approve_adjustment(
            company_id=ctx.company_id,
            adjustment_id=draft["id"],
            actor_id=ctx.actor_id,
            expected_version=draft["version"],
        )
        assert approved["status"] == "approved"
        # Meanwhile the damage is closed by someone else.
        await ctx.resolve_behind_the_back(damage["id"])
        with pytest.raises(InventoryAdjustmentError) as stale:
            await ctx.adjustments.apply_adjustment(
                company_id=ctx.company_id,
                adjustment_id=draft["id"],
                actor_id=ctx.actor_id,
                idempotency_key=ctx.key("stale-apply"),
            )
        assert stale.value.code == "adjustment_transfer_discrepancy_closed"
        # A draft written before the discrepancy closed cannot be approved either.
        other = await ctx.dispatched("other", unit_id=await ctx.restock("other"))
        other_received = await ctx.receive(
            other, "r2", quantity_base=D("5"), damaged_quantity=D("5"), **DAMAGE
        )
        other_damage = _damaged(other_received["discrepancies"])
        other_draft = await ctx.prepare_adjustment(other, other_damage, "stale-2")
        await ctx.attach_evidence(other_draft["id"], "stale-2")
        await ctx.resolve_behind_the_back(other_damage["id"])
        with pytest.raises(InventoryAdjustmentError) as stale_approval:
            await ctx.adjustments.approve_adjustment(
                company_id=ctx.company_id,
                adjustment_id=other_draft["id"],
                actor_id=ctx.actor_id,
                expected_version=other_draft["version"],
            )
        assert stale_approval.value.code == "adjustment_transfer_discrepancy_closed"
        # Cancelling the obsolete draft frees the discrepancy for a new one.
        cancelled = await ctx.adjustments.cancel_adjustment(
            company_id=ctx.company_id,
            adjustment_id=other_draft["id"],
            actor_id=ctx.actor_id,
            reason="Obsoleto: la diferencia ya se resolvió.",
        )
        assert cancelled["status"] == "cancelled"

    await _run(body)


@pytest.mark.asyncio
async def test_the_database_allows_one_active_adjustment_per_discrepancy() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        damage = _damaged(received["discrepancies"])
        draft = await ctx.prepare_adjustment(transfer, damage, "one")
        row = await ctx.session.get(InventoryAdjustmentModel, draft["id"])
        assert row is not None
        clone = InventoryAdjustmentModel(
            company_id=ctx.company_id,
            code=f"AJ-DUP-{ctx.suffix[:10]}",
            warehouse_id=row.warehouse_id,
            operational_date=row.operational_date,
            accounting_date=row.accounting_date,
            reason="Duplicado",
            document_reference="DUP",
            status="draft",
            version=1,
            transfer_discrepancy_id=damage["id"],
            created_by_id=ctx.actor_id,
            created_at=datetime.now(UTC),
        )

        async def insert() -> None:
            async with ctx.session.begin_nested():
                ctx.session.add(clone)
                await ctx.session.flush()

        with pytest.raises(IntegrityError):
            await insert()
        row_discrepancy = await ctx.session.get(InventoryTransferDiscrepancyModel, damage["id"])
        assert row_discrepancy is not None

    await _run(body)


@pytest.mark.asyncio
async def test_a_documented_loss_during_an_incident_stays_on_record_as_a_resolved_shortage() -> (
    None
):
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("8"))
        incident = await ctx.command(
            "open_incident", transfer, "inc", reason="Faltan dos unidades."
        )
        incident_id = next(r["id"] for r in incident["incidents"] if r["status"] == "open")
        detail = await ctx.session.scalar(
            select(InventoryTransferDetailModel).where(
                InventoryTransferDetailModel.id == transfer["lines"][0]["id"]
            )
        )
        assert detail is not None
        unit = await ctx.unit(detail.transit_handling_unit_id)
        draft = await ctx.adjustments.create_adjustment(
            company_id=ctx.company_id,
            actor_id=ctx.actor_id,
            warehouse_id=ctx.base.origin.id,
            operational_date=date(2026, 10, 19),
            accounting_date=date(2026, 10, 19),
            reason="Pérdida confirmada durante el traslado.",
            document_reference="ACTA-INCIDENTE-01",
            notes=None,
            idempotency_key=ctx.key("loss"),
            transfer_id=transfer["id"],
            transfer_incident_id=incident_id,
            lines=[
                {
                    "inventory_item_id": ctx.base.item.id,
                    "location_id": unit.location_id,
                    "direction": "decrease",
                    "quantity_base": D("2"),
                    "stock_status": "in_transit",
                    "handling_unit_id": unit.id,
                    "transfer_detail_id": detail.id,
                }
            ],
        )
        assert draft["transfer_discrepancy_id"] is None
        await ctx.approve_and_apply(draft, "loss")
        current = await ctx.get(transfer)
        assert current["status"] == "closed_with_adjustment"
        # The trip's trail needs a reception time even when it closed with a loss.
        assert current["received_at"] is not None
        assert current["closed_at"] is not None
        shortage = current["discrepancies"][0]
        assert shortage["kind"] == "shortage"
        assert shortage["source"] == "incident"
        assert (shortage["status"], shortage["resolution"]) == ("resolved", "written_off")
        assert shortage["quantity"] == D("2")
        assert shortage["incident_id"] == incident_id
        assert shortage["origin_count_required"] is True
        assert current["origin_count_pending"] is True

    await _run(body)


@pytest.mark.asyncio
async def test_listing_filters_find_open_discrepancies_and_pending_origin_counts() -> None:
    async def body(ctx: Ctx) -> None:
        clean = await ctx.dispatched("clean")
        await ctx.receive(clean, "rc", quantity_base=D("10"))
        extra = await ctx.dispatched("extra", unit_id=await ctx.restock("extra"))
        received = await ctx.receive(
            extra,
            "rx",
            quantity_base=D("10"),
            surplus_quantity=D("1"),
            surplus_notes="Una unidad de más al descargar",
        )

        async def ids(**filters: bool) -> set[uuid.UUID]:
            rows = await ctx.transfers.list_transfers(company_id=ctx.company_id, **filters)
            return {row["id"] for row in rows}

        assert extra["id"] in await ids(with_open_discrepancies=True)
        assert extra["id"] in await ids(origin_count_pending=True)
        assert clean["id"] not in await ids(with_open_discrepancies=True)
        assert clean["id"] not in await ids(origin_count_pending=True)
        assert {clean["id"], extra["id"]} <= await ids()
        surplus = received["discrepancies"][0]
        await ctx.command(
            "dismiss_surplus",
            extra,
            "dismiss",
            discrepancy_id=surplus["id"],
            notes="Error de conteo.",
        )
        # Dismissed, nothing is open; the origin still has to be counted.
        assert extra["id"] not in await ids(with_open_discrepancies=True)
        assert extra["id"] in await ids(origin_count_pending=True)
        await ctx.command(
            "acknowledge_origin_count",
            extra,
            "count",
            discrepancy_id=surplus["id"],
            notes="Origen contado: sin diferencias.",
        )
        assert extra["id"] not in await ids(origin_count_pending=True)

    await _run(body)


# --------------------------------------------------------------------------- idempotency


@pytest.mark.asyncio
async def test_the_new_commands_replay_and_refuse_a_changed_payload() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))

        async def twice(name: str, key: str, changed: dict[str, Any], **kwargs: Any):
            first = await ctx.command(name, transfer, key, **kwargs)
            replay = await ctx.command(name, transfer, key, **kwargs)
            assert _same_response(first, replay)
            with pytest.raises(TransferDomainError) as conflict:
                await ctx.command(name, transfer, key, **{**kwargs, **changed})
            assert conflict.value.code == "transfer_idempotency_conflict"
            return first

        closed = await twice(
            "close_reception",
            "close",
            {"reason": "Otro motivo distinto del anterior"},
            reason="El resto no llegó en el vehículo",
        )
        assert len(closed["discrepancies"]) == 1
        shortage = closed["discrepancies"][0]
        counted = await twice(
            "acknowledge_origin_count",
            "count",
            {"notes": "Un conteo distinto en el origen"},
            discrepancy_id=shortage["id"],
            notes="Se contó el origen: coincide.",
        )
        assert counted["origin_count_pending"] is False
        found = await twice(
            "mark_shortage_found",
            "found",
            {"notes": "Otra explicación distinta"},
            discrepancy_id=shortage["id"],
            notes="Apareció en la bodega de carga.",
        )
        assert found["status"] == "partially_received"
        assert len(found["discrepancies"]) == 1

    await _run(body)


@pytest.mark.asyncio
async def test_damage_commands_replay_and_refuse_a_changed_payload() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        damage = _damaged(received["discrepancies"])
        claim = {"discrepancy_id": damage["id"], "claim_reference": "RECLAMO-01"}
        first = await ctx.command("claim_discrepancy", transfer, "claim", **claim)
        assert _same_response(
            first, await ctx.command("claim_discrepancy", transfer, "claim", **claim)
        )
        with pytest.raises(TransferDomainError) as conflict:
            await ctx.command(
                "claim_discrepancy",
                transfer,
                "claim",
                discrepancy_id=damage["id"],
                claim_reference="RECLAMO-OTRO",
            )
        assert conflict.value.code == "transfer_idempotency_conflict"

        release = {"discrepancy_id": damage["id"], "notes": "Inspección favorable de la avería."}
        released = await ctx.command("release_damage", transfer, "release", **release)
        movements_before = await ctx.session.scalar(
            select(func.count(InventoryMovementLineModel.id)).where(
                InventoryMovementLineModel.company_id == ctx.company_id
            )
        )
        assert _same_response(
            released, await ctx.command("release_damage", transfer, "release", **release)
        )
        movements_after = await ctx.session.scalar(
            select(func.count(InventoryMovementLineModel.id)).where(
                InventoryMovementLineModel.company_id == ctx.company_id
            )
        )
        assert movements_after == movements_before
        with pytest.raises(TransferDomainError) as release_conflict:
            await ctx.command(
                "release_damage",
                transfer,
                "release",
                discrepancy_id=damage["id"],
                notes="Otra nota distinta de liberación",
            )
        assert release_conflict.value.code == "transfer_idempotency_conflict"

    await _run(body)


@pytest.mark.asyncio
async def test_dismissing_a_surplus_and_preparing_adjustments_replay_with_their_key() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer,
            "r1",
            quantity_base=D("10"),
            surplus_quantity=D("2"),
            surplus_notes="Dos cajas de más al descargar",
        )
        surplus = received["discrepancies"][0]
        payload = {"discrepancy_id": surplus["id"], "notes": "Fue un error de conteo."}
        first = await ctx.command("dismiss_surplus", transfer, "dismiss", **payload)
        assert _same_response(
            first, await ctx.command("dismiss_surplus", transfer, "dismiss", **payload)
        )
        with pytest.raises(TransferDomainError) as conflict:
            await ctx.command(
                "dismiss_surplus",
                transfer,
                "dismiss",
                discrepancy_id=surplus["id"],
                notes="Otra nota distinta de descarte",
            )
        assert conflict.value.code == "transfer_idempotency_conflict"

    await _run(body)


@pytest.mark.asyncio
async def test_an_old_receipt_payload_keeps_its_fingerprint_and_replays_from_new_clients() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        detail_id = transfer["lines"][0]["id"]
        legacy = [
            {
                "transfer_detail_id": detail_id,
                "destination_location_id": ctx.destination_location,
                "quantity_base": D("4"),
            }
        ]
        modern = [
            {
                **legacy[0],
                "damaged_quantity": D("0"),
                "damage_type": None,
                "damage_notes": None,
                "damaged_location_id": None,
                "surplus_quantity": D("0"),
                "surplus_notes": None,
                "surplus_location_id": None,
                "evidence_reference": None,
            }
        ]
        repo = SqlAlchemyInventoryTransferRepository
        old_fingerprint = repo._fingerprint(
            "receive", {"transfer_id": transfer["id"], "lines": legacy}
        )
        assert (
            repo._fingerprint(
                "receive",
                {
                    "transfer_id": transfer["id"],
                    "lines": repo._receipt_fingerprint_lines(modern),
                },
            )
            == old_fingerprint
        )
        # A real value does change it.
        changed = [{**modern[0], "damaged_quantity": D("1")}]
        assert (
            repo._fingerprint(
                "receive",
                {"transfer_id": transfer["id"], "lines": repo._receipt_fingerprint_lines(changed)},
            )
            != old_fingerprint
        )
        first = await ctx.transfers.receive_transfer(
            company_id=ctx.company_id,
            transfer_id=transfer["id"],
            lines=legacy,
            idempotency_key=ctx.key("legacy"),
            actor_id=ctx.actor_id,
        )
        replay = await ctx.transfers.receive_transfer(
            company_id=ctx.company_id,
            transfer_id=transfer["id"],
            lines=modern,
            idempotency_key=ctx.key("legacy"),
            actor_id=ctx.actor_id,
        )
        assert str(replay["id"]) == str(first["id"])
        assert replay["status"] == first["status"] == "partially_received"
        assert first["lines"][0]["quantity_received"] == D("4")

    await _run(body)


# --------------------------------------------------------------------------- transport


async def _approved(ctx: BranchRouteFixture, key: str) -> dict[str, Any]:
    draft = await _create(ctx, ctx.branch_b, key)
    pending = await _submit(ctx, draft["id"], f"{key}-submit")
    return await _approve(ctx, draft["id"], pending["approval_round"], f"{key}-approve")


@pytest.mark.asyncio
async def test_the_transport_is_saved_when_preparing_and_required_to_send() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "transport")
        assert draft["vehicle"]["id"] == ctx.base.vehicle_id
        assert draft["driver"]["id"] == ctx.driver_id
        assert draft["approved_vehicle"] is None
        assert draft["approved_driver"] is None

        no_driver = await ctx.use_cases.create_transfer(
            company_id=ctx.company_id,
            origin_warehouse_id=ctx.branch_a.id,
            destination_warehouse_id=ctx.branch_b.id,
            vehicle_id=ctx.base.vehicle_id,
            lines=_lines(ctx.unit_a),
            idempotency_key=f"no-driver-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert no_driver["driver"] is None
        error = await _expect(
            _submit(ctx, no_driver["id"], "no-driver"), "transfer_assignment_required", 422
        )
        assert (
            error.message == "Elige vehículo y conductor antes de enviar el traslado a aprobación."
        )
        # A driver that does not exist is refused when it is chosen.
        await _expect(
            ctx.use_cases.update_transfer(
                company_id=ctx.company_id,
                transfer_id=no_driver["id"],
                origin_warehouse_id=ctx.branch_a.id,
                destination_warehouse_id=ctx.branch_b.id,
                vehicle_id=ctx.base.vehicle_id,
                driver_id=uuid.uuid4(),
                notes=None,
                lines=_lines(ctx.unit_a),
                idempotency_key=f"bad-driver-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_driver_unavailable",
            422,
        )
        # What the router evaluated must still be what is saved when the request is stored.
        await _expect(
            ctx.use_cases.submit_transfer(
                company_id=ctx.company_id,
                transfer_id=draft["id"],
                idempotency_key=f"stale-review-{ctx.suffix}",
                actor_id=ctx.creator_id,
                expected_vehicle_id=ctx.base.vehicle_id,
                expected_driver_id=uuid.uuid4(),
            ),
            "transfer_assignment_changed",
            409,
        )
        pending = await ctx.use_cases.submit_transfer(
            company_id=ctx.company_id,
            transfer_id=draft["id"],
            idempotency_key=f"fresh-review-{ctx.suffix}",
            actor_id=ctx.creator_id,
            expected_vehicle_id=ctx.base.vehicle_id,
            expected_driver_id=ctx.driver_id,
            assignment_review={
                "warnings": [{"code": "vehicle_reserved", "message": "Al despachar"}]
            },
        )
        assert pending["status"] == "pending_approval"

    await _run_routes(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_approval_keeps_a_copy_of_the_transport_and_rejection_or_withdrawal_drop_it() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        rejected_draft = await _create(ctx, ctx.branch_b, "reject-copy")
        pending = await _submit(ctx, rejected_draft["id"], "reject-copy-submit")
        rejected = await ctx.use_cases.reject_transfer(
            company_id=ctx.company_id,
            transfer_id=rejected_draft["id"],
            idempotency_key=f"reject-copy-{ctx.suffix}",
            actor_id=ctx.approver_id,
            expected_round=pending["approval_round"],
            reason="Falta corregir el destino",
        )
        assert rejected["approved_vehicle"] is None
        assert rejected["driver"]["id"] == ctx.driver_id

        await _submit(ctx, rejected_draft["id"], "withdraw-copy-submit")
        withdrawn = await ctx.use_cases.withdraw_transfer(
            company_id=ctx.company_id,
            transfer_id=rejected_draft["id"],
            idempotency_key=f"withdraw-copy-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert withdrawn["status"] == "preparation"
        assert withdrawn["approved_vehicle"] is None

        approved = await _approved(ctx, "copy")
        assert approved["approved_vehicle"]["id"] == ctx.base.vehicle_id
        assert approved["approved_driver"]["id"] == ctx.driver_id
        row = await session.get(InventoryTransferModel, approved["id"])
        assert (row.approved_vehicle_id, row.approved_driver_id) == (
            ctx.base.vehicle_id,
            ctx.driver_id,
        )

    await _run_routes(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_a_request_sent_without_transport_cannot_be_approved() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        draft = await _create(ctx, ctx.branch_b, "legacy")
        pending = await _submit(ctx, draft["id"])
        row = await session.get(InventoryTransferModel, draft["id"])
        await _flush_in_savepoint(session, row, driver_id=None)
        error = await _expect(
            _approve(ctx, draft["id"], pending["approval_round"]),
            "transfer_assignment_required",
            409,
        )
        assert error.message == (
            "Esta solicitud se envió sin vehículo ni conductor; recházala o pide que la "
            "retiren y la completen."
        )

    await _run_routes(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_dispatching_with_other_transport_than_approved_needs_a_reason() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        approved = await _approved(ctx, "swap")
        other_vehicle = await ctx.use_cases.create_vehicle(
            company_id=ctx.company_id,
            code=f"SW-{ctx.suffix[:8]}",
            name="Vehículo de reemplazo",
            actor_id=ctx.creator_id,
        )

        async def dispatch(key: str, **kwargs: Any):
            return await ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=approved["id"],
                idempotency_key=f"swap-{key}-{ctx.suffix}",
                actor_id=ctx.creator_id,
                **kwargs,
            )

        no_reason = await _expect(
            dispatch("a", vehicle_id=other_vehicle["id"]),
            "transfer_substitution_reason_required",
            422,
        )
        assert no_reason.message == (
            "Indica por qué cambias el vehículo o el conductor aprobado (mínimo 10 caracteres)."
        )
        await _expect(
            dispatch(
                "b",
                vehicle_id=other_vehicle["id"],
                substitution_code="nope",
                substitution_reason="El vehículo aprobado no arranca",
            ),
            "transfer_substitution_code_invalid",
            422,
        )
        await _expect(
            dispatch(
                "c",
                vehicle_id=other_vehicle["id"],
                substitution_code="vehicle_unfit",
                substitution_reason="corto",
            ),
            "transfer_substitution_reason_required",
            422,
        )
        dispatched = await dispatch(
            "d",
            vehicle_id=other_vehicle["id"],
            driver_id=ctx.driver_id,
            substitution_code="vehicle_unfit",
            substitution_reason="  El vehículo aprobado no arranca  ",
        )
        assert dispatched["status"] == "in_transit"
        assert dispatched["vehicle"]["id"] == other_vehicle["id"]
        assert dispatched["approved_vehicle"]["id"] == ctx.base.vehicle_id
        substitution = dispatched["assignment_substitution"]
        assert substitution["code"] == "vehicle_unfit"
        assert substitution["reason"] == "El vehículo aprobado no arranca"
        assert substitution["by_id"] == ctx.creator_id
        assert substitution["at"] is not None

    await _run_routes(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_dispatching_the_approved_transport_needs_no_reason_and_uses_the_saved_driver() -> (
    None
):
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        approved = await _approved(ctx, "same")
        dispatched = await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=approved["id"],
            vehicle_id=ctx.base.vehicle_id,
            idempotency_key=f"same-dispatch-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert dispatched["assignment_substitution"] is None
        # The driver saved at preparation is the default when dispatch names none.
        assert dispatched["driver"]["id"] == ctx.driver_id

    await _run_routes(body, **ALL_ROUTES)


@pytest.mark.asyncio
async def test_a_different_driver_than_the_approved_one_is_also_a_substitution() -> None:
    async def body(session: Any, ctx: BranchRouteFixture) -> None:
        approved = await _approved(ctx, "driver")
        other_driver = await _new_driver(
            session, ctx.company_id, ctx.branch_a.branch_id, f"x{ctx.suffix}"
        )
        await _expect(
            ctx.use_cases.dispatch_transfer(
                company_id=ctx.company_id,
                transfer_id=approved["id"],
                vehicle_id=ctx.base.vehicle_id,
                driver_id=other_driver,
                idempotency_key=f"driver-a-{ctx.suffix}",
                actor_id=ctx.creator_id,
            ),
            "transfer_substitution_reason_required",
            422,
        )
        dispatched = await ctx.use_cases.dispatch_transfer(
            company_id=ctx.company_id,
            transfer_id=approved["id"],
            vehicle_id=ctx.base.vehicle_id,
            driver_id=other_driver,
            substitution_code="driver_unavailable",
            substitution_reason="El conductor aprobado está enfermo",
            idempotency_key=f"driver-b-{ctx.suffix}",
            actor_id=ctx.creator_id,
        )
        assert dispatched["driver"]["id"] == other_driver
        assert dispatched["approved_driver"]["id"] == ctx.driver_id
        assert dispatched["assignment_substitution"]["code"] == "driver_unavailable"

    await _run_routes(body, **ALL_ROUTES)

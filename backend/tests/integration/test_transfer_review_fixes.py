"""PostgreSQL checks for the review fixes of partial reception and discrepancies."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.domain.entities.inventory_transfer import TransferDomainError
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.organization import Location
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_transfer_settlement import on_road_clause
from sqlalchemy import select

from tests.integration.test_transfer_receipt_discrepancies import (
    DAMAGE,
    Ctx,
    _damaged,
    _run,
)

pytestmark = pytest.mark.integration

D = Decimal


async def _two_line_transfer(ctx: Ctx) -> dict[str, Any]:
    """A dispatched central transfer with two lines of ten units each."""
    second = await ctx.restock("two")
    lines = [
        {
            "handling_unit_id": unit_id,
            "quantity_base": D("10"),
            "demand_allocations": [],
            "excess_reason": "Despacho manual de prueba",
        }
        for unit_id in (ctx.base.handling_unit_id, second)
    ]
    created = await ctx.transfers.create_transfer(
        company_id=ctx.company_id,
        origin_warehouse_id=ctx.base.origin.id,
        destination_warehouse_id=ctx.base.destination.id,
        vehicle_id=ctx.base.vehicle_id,
        lines=lines,
        idempotency_key=ctx.key("two-create"),
        actor_id=ctx.actor_id,
    )
    return await ctx.transfers.dispatch_transfer(
        company_id=ctx.company_id,
        transfer_id=created["id"],
        vehicle_id=ctx.base.vehicle_id,
        idempotency_key=ctx.key("two-dispatch"),
        actor_id=ctx.actor_id,
    )


async def _on_the_road(ctx: Ctx, transfer: dict[str, Any]) -> bool:
    found = await ctx.session.scalar(
        select(InventoryTransferModel.id).where(
            InventoryTransferModel.id == transfer["id"], on_road_clause()
        )
    )
    return found is not None


async def _new_location(ctx: Ctx, tag: str) -> Location:
    location = Location(
        warehouse_id=ctx.base.destination.id,
        code=f"IT-{tag}-{ctx.suffix[:8]}",
        aisle="01",
        rack=tag,
        level="01",
        position="01",
        storage_eligible=True,
        capacity_enforcement_mode="disabled",
    )
    ctx.session.add(location)
    await ctx.session.flush()
    return location


async def _move_damaged(ctx: Ctx, unit_id: uuid.UUID, location: Location, tag: str) -> None:
    unit = await ctx.unit(unit_id)
    await SqlAlchemyInventoryRepository(ctx.session).post_movement(
        company_id=ctx.company_id,
        idempotency_key=f"move-damaged-{tag}-{ctx.suffix}",
        movement_type="transfer",
        source_reference=f"move-damaged:{tag}:{ctx.suffix}",
        lines=[
            {
                "inventory_item_id": ctx.base.item.id,
                "handling_unit_id": unit.id,
                "from_location_id": unit.location_id,
                "to_location_id": location.id,
                "from_stock_status": "damaged",
                "to_stock_status": "damaged",
                "quantity_base": unit.quantity_base,
            }
        ],
        actor_id=ctx.actor_id,
    )


async def _damage_transfer(ctx: Ctx, tag: str) -> tuple[dict[str, Any], dict[str, Any]]:
    transfer = await ctx.dispatched(tag, unit_id=await ctx.restock(tag))
    received = await ctx.receive(
        transfer, f"r-{tag}", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
    )
    return transfer, _damaged(received["discrepancies"])


# --------------------------------------------------------------------------- M2, M3, M4


@pytest.mark.asyncio
async def test_a_second_close_declares_only_what_is_not_covered_by_an_open_shortage() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await _two_line_transfer(ctx)
        first, second = (line["id"] for line in transfer["lines"])
        partial = await ctx.transfers.receive_transfer(
            company_id=ctx.company_id,
            transfer_id=transfer["id"],
            lines=[
                {
                    "transfer_detail_id": first,
                    "destination_location_id": ctx.destination_location,
                    "quantity_base": D("6"),
                },
                {
                    "transfer_detail_id": second,
                    "destination_location_id": ctx.destination_location,
                    "quantity_base": D("3"),
                },
            ],
            idempotency_key=ctx.key("both"),
            actor_id=ctx.actor_id,
        )
        assert partial["status"] == "partially_received"
        # While it is partly received the vehicle and the driver are still on the road.
        assert await _on_the_road(ctx, transfer)

        closed = await ctx.command("close_reception", transfer, "close-1", reason="No llegó más")
        assert {row["quantity"] for row in closed["discrepancies"]} == {D("4"), D("7")}
        assert not await _on_the_road(ctx, transfer)
        shortage_first = next(
            row for row in closed["discrepancies"] if row["transfer_detail_id"] == first
        )
        found = await ctx.command(
            "mark_shortage_found",
            transfer,
            "found",
            discrepancy_id=shortage_first["id"],
            notes="Apareció en la bodega de carga.",
        )
        assert found["status"] == "partially_received"
        # The trip ended when the reception closed; finding goods does not send the truck back.
        assert found["received_at"] is not None
        assert not await _on_the_road(ctx, transfer)

        # The second line still has its shortage open: it cannot be received until it turns up.
        with pytest.raises(TransferDomainError) as covered:
            await ctx.transfers.receive_transfer(
                company_id=ctx.company_id,
                transfer_id=transfer["id"],
                lines=[
                    {
                        "transfer_detail_id": second,
                        "destination_location_id": ctx.destination_location,
                        "quantity_base": D("1"),
                    }
                ],
                idempotency_key=ctx.key("blocked"),
                actor_id=ctx.actor_id,
            )
        assert covered.value.code == "transfer_discrepancy_open"
        assert covered.value.status_code == 409
        assert covered.value.message == (
            "Esta línea tiene un faltante abierto; márcalo como «Llegó la mercadería» "
            "antes de recibirla."
        )

        # Closing again only declares the line that is not covered (no duplicate, no crash).
        again = await ctx.command("close_reception", transfer, "close-2", reason="Sigue sin llegar")
        open_by_line = {
            row["transfer_detail_id"]: row["quantity"]
            for row in again["discrepancies"]
            if row["status"] == "open"
        }
        assert open_by_line == {first: D("4"), second: D("7")}
        assert len(again["discrepancies"]) == 3
        assert again["status"] == "discrepancy"

    await _run(body)


@pytest.mark.asyncio
async def test_closing_with_everything_already_declared_says_nothing_is_left() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        await ctx.command("close_reception", transfer, "close-1", reason="No llegó más")
        # The transfer is now in discrepancy: it cannot be closed again, and nothing is created.
        with pytest.raises(TransferDomainError) as raised:
            await ctx.command("close_reception", transfer, "close-2", reason="Otra vez")
        assert raised.value.code == "transfer_reception_close_not_allowed"
        count = len((await ctx.get(transfer))["discrepancies"])
        assert count == 1

    await _run(body)


# --------------------------------------------------------------------------- M5


@pytest.mark.asyncio
async def test_release_follows_a_damaged_unit_moved_inside_the_destination_warehouse() -> None:
    async def body(ctx: Ctx) -> None:
        transfer, damage = await _damage_transfer(ctx, "rel")
        moved_to = await _new_location(ctx, "R1")
        await _move_damaged(ctx, damage["handling_unit_id"], moved_to, "rel")
        released = await ctx.command(
            "release_damage",
            transfer,
            "release",
            discrepancy_id=damage["id"],
            notes="Inspección favorable tras moverla.",
        )
        assert _damaged(released["discrepancies"])["resolution"] == "released"
        unit = await ctx.unit(damage["handling_unit_id"])
        assert (unit.stock_status, unit.location_id) == ("quarantine", moved_to.id)

    await _run(body)


@pytest.mark.asyncio
async def test_a_write_off_follows_the_damaged_unit_before_and_after_it_is_prepared() -> None:
    async def body(ctx: Ctx) -> None:
        # Prepared after the move: the line points where the unit is now.
        transfer, damage = await _damage_transfer(ctx, "after")
        first_move = await _new_location(ctx, "W1")
        await _move_damaged(ctx, damage["handling_unit_id"], first_move, "after")
        draft = await ctx.prepare_adjustment(transfer, damage, "after-adj")
        assert draft["lines"][0]["location_id"] == first_move.id

        # Prepared before the move: applying follows the unit to its new location.
        other, other_damage = await _damage_transfer(ctx, "before")
        draft_before = await ctx.prepare_adjustment(other, other_damage, "before-adj")
        assert draft_before["lines"][0]["location_id"] == ctx.destination_location
        second_move = await _new_location(ctx, "W2")
        await _move_damaged(ctx, other_damage["handling_unit_id"], second_move, "before")
        applied = await ctx.approve_and_apply(draft_before, "before-adj")
        assert applied["status"] == "applied"
        assert applied["lines"][0]["location_id"] == second_move.id
        current = await ctx.get(other)
        assert _damaged(current["discrepancies"])["resolution"] == "written_off"
        assert current["status"] == "closed_with_adjustment"

    await _run(body)


@pytest.mark.asyncio
async def test_a_damaged_unit_that_changed_status_cannot_be_released_or_written_off() -> None:
    async def body(ctx: Ctx) -> None:
        transfer, damage = await _damage_transfer(ctx, "status")
        unit = await ctx.unit(damage["handling_unit_id"])
        unit.stock_status = "quarantine"
        await ctx.session.flush()
        with pytest.raises(TransferDomainError) as release:
            await ctx.command(
                "release_damage",
                transfer,
                "release",
                discrepancy_id=damage["id"],
                notes="Intento de liberación.",
            )
        assert release.value.code == "transfer_discrepancy_unit_changed"
        assert "cambió de estado" in release.value.message
        with pytest.raises(InventoryAdjustmentError) as adjustment:
            await ctx.prepare_adjustment(transfer, damage, "status-adj")
        assert adjustment.value.code == "transfer_discrepancy_unit_changed"
        assert "cambió de estado" in adjustment.value.message

    await _run(body)


# --------------------------------------------------------------------------- m1


@pytest.mark.asyncio
async def test_release_found_and_dismiss_wait_for_the_adjustment_in_progress() -> None:
    async def body(ctx: Ctx) -> None:
        # A damage with a draft adjustment cannot be released.
        transfer, damage = await _damage_transfer(ctx, "dmg")
        draft = await ctx.prepare_adjustment(transfer, damage, "dmg-adj")
        with pytest.raises(TransferDomainError) as release:
            await ctx.command(
                "release_damage",
                transfer,
                "release",
                discrepancy_id=damage["id"],
                notes="Intento de liberación.",
            )
        assert release.value.code == "transfer_discrepancy_has_adjustment"
        assert f"Cancela el ajuste {draft['code']} primero" in release.value.message

        # A shortage with a draft adjustment cannot be marked as arrived.
        short_transfer = await ctx.dispatched("short", unit_id=await ctx.restock("short"))
        await ctx.receive(short_transfer, "rs", quantity_base=D("6"))
        closed = await ctx.command("close_reception", short_transfer, "close", reason="No llegó")
        shortage = closed["discrepancies"][0]
        short_draft = await ctx.prepare_adjustment(short_transfer, shortage, "short-adj")
        with pytest.raises(TransferDomainError) as found:
            await ctx.command(
                "mark_shortage_found",
                short_transfer,
                "found",
                discrepancy_id=shortage["id"],
                notes="Intento de llegada.",
            )
        assert found.value.code == "transfer_discrepancy_has_adjustment"
        assert f"Cancela el ajuste {short_draft['code']} primero" in found.value.message

        # A surplus with a draft adjustment cannot be dismissed.
        extra = await ctx.dispatched("extra", unit_id=await ctx.restock("extra"))
        received = await ctx.receive(
            extra,
            "rx",
            quantity_base=D("10"),
            surplus_quantity=D("1"),
            surplus_notes="Una unidad de más al descargar",
        )
        surplus = received["discrepancies"][0]
        extra_draft = await ctx.prepare_adjustment(
            extra, surplus, "extra-adj", actual_gross_weight_kg=D("1"), actual_volume_m3=D("0.01")
        )
        with pytest.raises(TransferDomainError) as dismiss:
            await ctx.command(
                "dismiss_surplus",
                extra,
                "dismiss",
                discrepancy_id=surplus["id"],
                notes="Intento de descarte.",
            )
        assert dismiss.value.code == "transfer_discrepancy_has_adjustment"
        assert f"Cancela el ajuste {extra_draft['code']} primero" in dismiss.value.message

        # Once the draft is cancelled the command works, and the cancelled draft is not shown.
        await ctx.adjustments.cancel_adjustment(
            company_id=ctx.company_id,
            adjustment_id=draft["id"],
            actor_id=ctx.actor_id,
            reason="Mejor se libera la mercadería.",
        )
        released = await ctx.command(
            "release_damage",
            transfer,
            "release-2",
            discrepancy_id=damage["id"],
            notes="Inspección favorable de la avería.",
        )
        row = _damaged(released["discrepancies"])
        assert row["status"] == "resolved"
        assert row["adjustment"] is None

    await _run(body)


@pytest.mark.asyncio
async def test_an_open_discrepancy_shows_its_draft_and_a_closed_one_only_the_applied() -> None:
    async def body(ctx: Ctx) -> None:
        transfer, damage = await _damage_transfer(ctx, "vis")
        draft = await ctx.prepare_adjustment(transfer, damage, "vis-adj")
        current = await ctx.get(transfer)
        shown = _damaged(current["discrepancies"])["adjustment"]
        assert shown is not None
        assert (shown["code"], shown["status"]) == (draft["code"], "draft")
        await ctx.approve_and_apply(draft, "vis-adj")
        closed = await ctx.get(transfer)
        applied = _damaged(closed["discrepancies"])["adjustment"]
        assert applied["status"] == "applied"

    await _run(body)


# --------------------------------------------------------------------------- m4


@pytest.mark.asyncio
async def test_cancelling_a_transfer_stamps_when_it_closed() -> None:
    async def body(ctx: Ctx) -> None:
        created = await ctx.transfers.create_transfer(
            company_id=ctx.company_id,
            origin_warehouse_id=ctx.base.origin.id,
            destination_warehouse_id=ctx.base.destination.id,
            vehicle_id=ctx.base.vehicle_id,
            lines=[
                {
                    "handling_unit_id": ctx.base.handling_unit_id,
                    "quantity_base": D("10"),
                    "demand_allocations": [],
                    "excess_reason": "Preparación que se cancela",
                }
            ],
            idempotency_key=ctx.key("cancel-create"),
            actor_id=ctx.actor_id,
        )
        assert created["closed_at"] is None
        cancelled = await ctx.command("cancel_transfer", created, "cancel")
        assert cancelled["status"] == "cancelled"
        assert cancelled["closed_at"] is not None

    await _run(body)

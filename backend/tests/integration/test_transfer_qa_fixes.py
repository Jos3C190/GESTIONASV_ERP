"""PostgreSQL checks for the findings of the final review and the browser QA."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from app.application.fleet.costs import business_today
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.domain.entities.inventory_transfer import TransferDomainError
from app.infrastructure.models.inventory_valuation import InventoryValuationSettingModel

from tests.integration.test_transfer_receipt_discrepancies import DAMAGE, Ctx, _damaged, _run

pytestmark = pytest.mark.integration

D = Decimal


async def _ids(ctx: Ctx, **filters: bool) -> set:
    rows = await ctx.transfers.list_transfers(company_id=ctx.company_id, **filters)
    return {row["id"] for row in rows}


@pytest.mark.asyncio
async def test_a_found_shortage_and_a_dismissed_surplus_leave_nothing_to_count_at_origin() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        closed = await ctx.command("close_reception", transfer, "close", reason="No llegó el resto")
        shortage = closed["discrepancies"][0]
        assert closed["origin_count_pending"] is True
        found = await ctx.command(
            "mark_shortage_found",
            transfer,
            "found",
            discrepancy_id=shortage["id"],
            notes="Apareció en la bodega de carga.",
        )
        row = found["discrepancies"][0]
        assert row["status"] == "cancelled"
        assert row["origin_count_required"] is False
        assert found["origin_count_pending"] is False
        assert transfer["id"] not in await _ids(ctx, origin_count_pending=True)

        # A surplus that was dismissed behaves the same.
        extra = await ctx.dispatched("extra", unit_id=await ctx.restock("extra"))
        received = await ctx.receive(
            extra,
            "rx",
            quantity_base=D("10"),
            surplus_quantity=D("1"),
            surplus_notes="Una unidad de más al descargar",
        )
        assert received["origin_count_pending"] is True
        dismissed = await ctx.command(
            "dismiss_surplus",
            extra,
            "dismiss",
            discrepancy_id=received["discrepancies"][0]["id"],
            notes="Error de conteo.",
        )
        assert dismissed["discrepancies"][0]["origin_count_required"] is False
        assert dismissed["origin_count_pending"] is False
        assert extra["id"] not in await _ids(ctx, origin_count_pending=True)

    await _run(body)


@pytest.mark.asyncio
async def test_a_count_already_taken_is_kept_when_the_shortage_is_found() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        closed = await ctx.command("close_reception", transfer, "close", reason="No llegó el resto")
        shortage = closed["discrepancies"][0]
        await ctx.command(
            "acknowledge_origin_count",
            transfer,
            "count",
            discrepancy_id=shortage["id"],
            notes="Se contó el origen: coincide.",
        )
        found = await ctx.command(
            "mark_shortage_found",
            transfer,
            "found",
            discrepancy_id=shortage["id"],
            notes="Apareció en la bodega de carga.",
        )
        row = found["discrepancies"][0]
        assert row["origin_count_required"] is True
        assert row["origin_counted_at"] is not None
        assert found["origin_count_pending"] is False

    await _run(body)


@pytest.mark.asyncio
async def test_receiving_a_transfer_closed_with_open_shortages_explains_what_to_do() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        await ctx.receive(transfer, "r1", quantity_base=D("6"))
        await ctx.command("close_reception", transfer, "close", reason="No llegó el resto")
        with pytest.raises(TransferDomainError) as open_shortage:
            await ctx.receive(transfer, "r2", quantity_base=D("1"))
        assert open_shortage.value.code == "transfer_discrepancy_open"
        assert open_shortage.value.status_code == 409
        assert open_shortage.value.message == (
            "La recepción se cerró con faltantes abiertos; marca «Llegó la mercadería» "
            "en el faltante para seguir recibiendo."
        )

        # Without open shortages the general message applies (and it is clearer now).
        other = await ctx.dispatched("other", unit_id=await ctx.restock("other"))
        await ctx.receive(other, "ro", quantity_base=D("0"), damaged_quantity=D("10"), **DAMAGE)
        with pytest.raises(TransferDomainError) as general:
            await ctx.receive(other, "ro2", quantity_base=D("1"))
        assert general.value.code == "transfer_not_receivable"
        assert (
            general.value.message
            == "Solo se reciben traslados en tránsito o con recepción parcial."
        )

    await _run(body)


@pytest.mark.asyncio
async def test_the_payload_says_whether_the_valuation_opening_is_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        assert received["valuation_ready"] is True
        damage = _damaged(received["discrepancies"])

        # Without an approved opening no adjustment can be prepared (it could never be applied).
        # The opening cannot be deleted (valuation history is immutable): look as if it was not there.
        original_get = ctx.session.get

        async def get_without_opening(model: Any, *args: Any, **kwargs: Any) -> Any:
            if model is InventoryValuationSettingModel:
                return None
            return await original_get(model, *args, **kwargs)

        monkeypatch.setattr(ctx.session, "get", get_without_opening)
        current = await ctx.get(transfer)
        assert current["valuation_ready"] is False
        with pytest.raises(InventoryAdjustmentError) as raised:
            await ctx.prepare_adjustment(transfer, damage, "no-opening")
        assert raised.value.code == "valuation_opening_required"
        assert raised.value.status_code == 409
        assert raised.value.message == (
            "Aprueba el saldo inicial de valuación antes de preparar ajustes de inventario."
        )

    await _run(body)


@pytest.mark.asyncio
async def test_the_lot_written_on_the_unit_reaches_the_transfer_and_the_adjustment() -> None:
    async def body(ctx: Ctx) -> None:
        unit_id = await ctx.restock("lot", lot_code="HAR-SM-2026-01")
        transfer = await ctx.dispatched("lot", unit_id=unit_id)
        assert transfer["lines"][0]["lot_code"] == "HAR-SM-2026-01"
        received = await ctx.receive(
            transfer, "r1", quantity_base=D("6"), damaged_quantity=D("4"), **DAMAGE
        )
        assert received["lines"][0]["lot_code"] == "HAR-SM-2026-01"
        draft = await ctx.prepare_adjustment(transfer, _damaged(received["discrepancies"]), "lot")
        assert draft["lines"][0]["lot_code"] == "HAR-SM-2026-01"

    await _run(body)


@pytest.mark.asyncio
async def test_new_transfer_codes_use_the_business_date() -> None:
    async def body(ctx: Ctx) -> None:
        transfer = await ctx.dispatched()
        assert transfer["code"].startswith(f"TR-{business_today():%Y%m%d}-")

    await _run(body)

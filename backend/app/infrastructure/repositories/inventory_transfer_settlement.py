"""The only writer of a transfer's status after it has been dispatched.

Receptions, incidents, reception closes, adjustments and the resolution of
discrepancies all change quantities and differences; once they have, they call
:func:`settle_transfer` and the pure rule in the domain decides the status.
Callers hold the transfer row lock; this module takes the detail and
discrepancy locks, always in that order.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inventory_transfer import (
    FINAL_STATUSES,
    ON_ROAD_STATUSES,
    TRIP_FINISHED_STATUSES,
    DiscrepancyKind,
    DiscrepancyStatus,
    TransferStatus,
    settle_transfer_status,
)
from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferDetailModel,
    InventoryTransferDiscrepancyModel,
    InventoryTransferIncidentModel,
    InventoryTransferModel,
)

ZERO = Decimal("0")
#: A shortage in one of these still covers part of what has not arrived.
_COVERING_STATUSES = (DiscrepancyStatus.OPEN, DiscrepancyStatus.IN_CLAIM)


def on_road_clause() -> ColumnElement[bool]:
    """SQL: the transfer is still travelling, so its vehicle and driver are busy.

    A trip that already finished once (``received_at`` is set) stays finished even if a
    shortage that turned up puts the transfer back to waiting for goods.
    """
    return and_(
        InventoryTransferModel.status.in_([status.value for status in ON_ROAD_STATUSES]),
        InventoryTransferModel.received_at.is_(None),
    )


def is_on_road(transfer: InventoryTransferModel) -> bool:
    return transfer.status in ON_ROAD_STATUSES and transfer.received_at is None


async def locked_damaged_unit(
    session: AsyncSession,
    discrepancy: InventoryTransferDiscrepancyModel,
    destination_warehouse_id: uuid.UUID,
) -> tuple[InventoryHandlingUnitModel | None, str | None]:
    """Lock the unit that holds a damage, wherever it is now, and say why it no longer fits.

    The unit may have been moved to another location of the destination warehouse; that is
    fine. It may not have changed status, left the warehouse or been consumed in part.
    """
    unit = (
        await session.scalar(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == discrepancy.company_id,
                InventoryHandlingUnitModel.id == discrepancy.handling_unit_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if discrepancy.handling_unit_id is not None
        else None
    )
    if unit is None or unit.closed_at is not None or unit.location_id is None:
        return None, (
            "La unidad averiada ya no existe o fue cerrada; revisa su historial de movimientos."
        )
    if unit.stock_status != "damaged":
        return None, (
            f"La unidad averiada cambió de estado (ahora está «{unit.stock_status}»); "
            "revisa su historial de movimientos."
        )
    if unit.warehouse_id != destination_warehouse_id:
        return None, (
            "La unidad averiada fue movida fuera de la bodega destino del traslado; "
            "devuélvela antes de continuar."
        )
    if Decimal(unit.quantity_base) < Decimal(discrepancy.quantity):
        return None, (
            f"La unidad averiada se consumió en parte: quedan {Decimal(unit.quantity_base):f} y "
            f"la avería es de {Decimal(discrepancy.quantity):f}."
        )
    return unit, None


def detail_pending(detail: InventoryTransferDetailModel) -> Decimal:
    """What was dispatched and has not been received, returned or adjusted out."""
    return (
        Decimal(detail.quantity_dispatched)
        - Decimal(detail.quantity_received)
        - Decimal(detail.quantity_returned)
        - Decimal(detail.quantity_adjusted_out)
    )


async def settle_transfer(
    session: AsyncSession,
    transfer: InventoryTransferModel,
    actor_id: uuid.UUID,
    now: datetime,
) -> TransferStatus:
    """Recompute and store the status of a dispatched transfer."""
    details = list(
        (
            await session.scalars(
                select(InventoryTransferDetailModel)
                .where(
                    InventoryTransferDetailModel.company_id == transfer.company_id,
                    InventoryTransferDetailModel.transfer_id == transfer.id,
                )
                .order_by(InventoryTransferDetailModel.id)
                .with_for_update()
            )
        ).all()
    )
    discrepancies = list(
        (
            await session.scalars(
                select(InventoryTransferDiscrepancyModel)
                .where(
                    InventoryTransferDiscrepancyModel.company_id == transfer.company_id,
                    InventoryTransferDiscrepancyModel.transfer_id == transfer.id,
                )
                .order_by(InventoryTransferDiscrepancyModel.id)
                .with_for_update()
            )
        ).all()
    )
    incident_open = (
        await session.scalar(
            select(InventoryTransferIncidentModel.id).where(
                InventoryTransferIncidentModel.company_id == transfer.company_id,
                InventoryTransferIncidentModel.transfer_id == transfer.id,
                InventoryTransferIncidentModel.status == "open",
            )
        )
    ) is not None
    covered: dict[uuid.UUID, Decimal] = {}
    for discrepancy in discrepancies:
        if discrepancy.kind == DiscrepancyKind.SHORTAGE and (
            discrepancy.status in _COVERING_STATUSES
        ):
            covered[discrepancy.transfer_detail_id] = covered.get(
                discrepancy.transfer_detail_id, ZERO
            ) + Decimal(discrepancy.quantity)
    uncovered_pending = sum(
        (max(ZERO, detail_pending(detail) - covered.get(detail.id, ZERO)) for detail in details),
        ZERO,
    )
    outcome = settle_transfer_status(
        current_status=transfer.status,
        uncovered_pending=uncovered_pending,
        has_open_discrepancies=any(
            discrepancy.status == DiscrepancyStatus.OPEN for discrepancy in discrepancies
        ),
        had_discrepancy=any(
            discrepancy.status != DiscrepancyStatus.CANCELLED for discrepancy in discrepancies
        ),
        had_loss=any(Decimal(detail.quantity_adjusted_out) > 0 for detail in details),
        received_any=any(Decimal(detail.quantity_received) > 0 for detail in details),
        incident_open=incident_open,
    )
    if transfer.status in FINAL_STATUSES:
        return outcome
    transfer.status = outcome.value
    if outcome in TRIP_FINISHED_STATUSES and transfer.received_at is None:
        transfer.received_at = now
        transfer.received_by_id = actor_id
    if outcome in (TransferStatus.RECEIVED, TransferStatus.CLOSED_WITH_ADJUSTMENT):
        transfer.closed_at = now
    await session.flush()
    return outcome

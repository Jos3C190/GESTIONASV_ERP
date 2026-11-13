"""Watch transfers in transit and raise alerts while nobody has tracking open.

Runs as its own service (``python -m app.infrastructure.tracking_monitor``).
Every cycle it evaluates each transfer on the road (arrival, delay, long stop,
GPS silence, deviation), keeps one open alert per transfer and kind, and
archives the trail of transfers closed while the GPS server was unreachable.
Only one monitor works at a time (PostgreSQL advisory lock). The same service
runs the tracking simulator engine (``tracking_simulator``) on a faster tick.
"""

from __future__ import annotations

import asyncio
import signal
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import exists, select, text

from app.api.v1.site_sync import load_sites
from app.api.v1.traccar_access import traccar_credentials
from app.api.v1.transfer_tracking import (
    FINAL_TRANSFER_STATUSES,
    apply_conditions,
    archive_trip,
    compute_trip,
    on_road_clause,
    transfer_query,
    trip_context,
    trip_snapshot,
)
from app.application.tracking.alerts import evaluate_trip
from app.application.tracking.simulation import TICK_SECONDS
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.tracking import TrackingAlertModel, TransferTrackModel
from app.infrastructure.tracking_simulator import tick as simulator_tick

log = get_logger(__name__)

#: Closed transfers whose trail is still missing are retried for this long.
ARCHIVE_WINDOW = timedelta(days=7)


async def _watch_company(company_id: uuid.UUID) -> int:
    async with async_session_factory() as session:
        sites = [
            (site.longitude, site.latitude, float(site.radius_m))
            for site in (await load_sites(session, company_id))[0]
        ]
        rows = (
            await session.execute(transfer_query(company_id, None).where(on_road_clause()))
        ).all()
    evaluated = 0
    for row in rows:
        ctx = trip_context(row)
        try:
            async with async_session_factory() as session:
                data, positions = await compute_trip(session, ctx)
                conditions = evaluate_trip(trip_snapshot(ctx, data, positions, sites))
                await apply_conditions(session, ctx, conditions)
                await session.commit()
            evaluated += 1
        except HTTPException as exc:
            log.warning(
                "tracking_monitor_transfer_skipped", transfer=ctx.transfer.code, detail=exc.detail
            )
        except Exception:
            log.exception("tracking_monitor_transfer_failed", transfer=ctx.transfer.code)
    return evaluated


async def _archive_pending() -> int:
    """Closed transfers still missing their trail or with alerts left open."""
    since = datetime.now(UTC) - ARCHIVE_WINDOW
    async with async_session_factory() as session:
        missing_track = ~exists().where(TransferTrackModel.transfer_id == InventoryTransferModel.id)
        open_alert = exists().where(
            TrackingAlertModel.transfer_id == InventoryTransferModel.id,
            TrackingAlertModel.resolved_at.is_(None),
        )
        rows = (
            await session.execute(
                select(InventoryTransferModel.company_id, InventoryTransferModel.id).where(
                    (
                        InventoryTransferModel.status.in_(FINAL_TRANSFER_STATUSES)
                        & InventoryTransferModel.dispatched_at.is_not(None)
                        & (InventoryTransferModel.received_at >= since)
                        & missing_track
                    )
                    | (~on_road_clause() & open_alert)
                )
            )
        ).all()
    for company_id, transfer_id in rows:
        try:
            await archive_trip(company_id, transfer_id)
        except Exception:
            log.exception("tracking_monitor_archive_failed", transfer_id=str(transfer_id))
    return len(rows)


async def run_once() -> None:
    if traccar_credentials() is None:
        return
    async with async_session_factory() as lock_session:
        locked = await lock_session.scalar(
            text("SELECT pg_try_advisory_lock(hashtext('tracking-monitor'))")
        )
        if not locked:
            return
        try:
            companies = (
                await lock_session.scalars(
                    select(InventoryTransferModel.company_id).where(on_road_clause()).distinct()
                )
            ).all()
            evaluated = 0
            for company_id in companies:
                evaluated += await _watch_company(company_id)
            archived = await _archive_pending()
            log.info("tracking_monitor_cycle", transfers=evaluated, archived=archived)
        finally:
            await lock_session.execute(
                text("SELECT pg_advisory_unlock(hashtext('tracking-monitor'))")
            )


async def _every(stop: asyncio.Event, seconds: float, job: Callable[[], Awaitable[object]]) -> None:
    while not stop.is_set():
        try:
            await job()
        except Exception:
            log.exception("tracking_monitor_failed", job=getattr(job, "__name__", "job"))
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except TimeoutError:
            continue


async def main() -> None:
    configure_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop.set)
    await asyncio.gather(
        _every(stop, settings.TRACKING_MONITOR_INTERVAL_SECONDS, run_once),
        # El simulador también cierra sesiones abiertas si la función se desactiva.
        _every(stop, TICK_SECONDS, simulator_tick),
    )


if __name__ == "__main__":
    asyncio.run(main())

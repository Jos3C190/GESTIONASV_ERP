"""Engine of the tracking simulator, run by the tracking monitor service.

Every couple of seconds it advances the route sessions (acceleration, stops,
arrival), keeps parked and joystick units alive with a heartbeat, and ends
sessions that expired, lost their vehicle or outlived the feature being on.
Only one engine works at a time (PostgreSQL advisory lock); sessions a user is
changing right now are skipped for one tick instead of waiting.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from app.api.v1.simulator import (
    ReportError,
    apply_position,
    end_simulation,
    send_report,
    simulator_enabled,
)
from app.api.v1.traccar_access import traccar_credentials
from app.application.tracking.simulation import (
    TICK_SECONDS,
    SimSnapshot,
    expiry_reason,
    step,
)
from app.core.logging import get_logger
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.tracking import TrackingSimulationModel

log = get_logger(__name__)

#: A late tick never moves a unit more than this many seconds at once.
MAX_STEP_SECONDS = 10.0

#: Monotonic time of the previous tick, to move units by the real elapsed time.
_clock: dict[str, float] = {}


def snapshot_of(simulation: TrackingSimulationModel) -> SimSnapshot:
    return SimSnapshot(
        mode=simulation.mode,  # type: ignore[arg-type]
        state=simulation.state,  # type: ignore[arg-type]
        route=[(float(point[0]), float(point[1])) for point in simulation.route],
        route_length_m=float(simulation.route_length_m),
        progress_m=float(simulation.progress_m),
        speed_kmh=float(simulation.speed_kmh),
        current_speed_kmh=float(simulation.current_speed_kmh),
        position=(float(simulation.longitude), float(simulation.latitude)),
        course=float(simulation.course),
        stop_until=simulation.stop_until,
        signal_lost_until=simulation.signal_lost_until,
        last_report_at=simulation.last_report_at,
    )


def _ending_reason(
    simulation: TrackingSimulationModel, vehicle: FleetVehicleModel | None, now: datetime
) -> str | None:
    if not simulator_enabled():
        return "El simulador se desactivó."
    if vehicle is None or vehicle.deleted_at is not None or vehicle.status == "retired":
        return "El vehículo ya no está disponible."
    if vehicle.branch_id != simulation.branch_id:
        return "El vehículo cambió de sucursal."
    return expiry_reason(simulation.started_at, simulation.last_activity_at, now)


async def tick(now: datetime | None = None, dt: float | None = None) -> int:
    """Advance every open session once; returns how many positions were reported."""
    clock = time.monotonic()
    if dt is None:
        previous = _clock.get("last")
        dt = TICK_SECONDS if previous is None else clock - previous
    _clock["last"] = clock
    dt = max(0.0, min(dt, MAX_STEP_SECONDS))
    moment = now or datetime.now(UTC)
    reported = 0
    async with async_session_factory() as session:
        locked = await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtext('tracking-simulator'))")
        )
        if not locked:
            return 0
        simulations = list(
            await session.scalars(
                select(TrackingSimulationModel)
                .where(TrackingSimulationModel.state != "ended")
                .with_for_update(skip_locked=True)
            )
        )
        for simulation in simulations:
            vehicle = await session.get(
                FleetVehicleModel,
                simulation.vehicle_id,
                execution_options={"include_deleted": True},
            )
            reason = _ending_reason(simulation, vehicle, moment)
            if reason is not None:
                await end_simulation(session, simulation, reason=reason, actor_id=None)
                log.info("tracking_simulation_ended", simulation=str(simulation.id), reason=reason)
                continue
            if traccar_credentials() is None:
                continue
            result = step(snapshot_of(simulation), moment, dt)
            simulation.state = result.state
            simulation.progress_m = Decimal(f"{result.progress_m:.1f}")
            simulation.advanced_at = moment
            simulation.stop_until = result.stop_until
            simulation.signal_lost_until = result.signal_lost_until
            apply_position(simulation, result.position, result.course, result.current_speed_kmh)
            if result.report:
                try:
                    # Las esquinas cruzadas en este tick van primero, con su hora estimada.
                    for vertex, heading, fraction in result.corners:
                        await send_report(
                            simulation,
                            vertex,
                            speed_kmh=result.current_speed_kmh,
                            course=heading,
                            at=moment - timedelta(seconds=dt * (1 - fraction)),
                        )
                        reported += 1
                    await send_report(
                        simulation,
                        result.position,
                        speed_kmh=result.current_speed_kmh,
                        course=result.course,
                        at=moment,
                    )
                    reported += 1
                except ReportError as exc:
                    log.warning(
                        "tracking_simulation_report_failed",
                        simulation=str(simulation.id),
                        error=str(exc),
                    )
        await session.commit()
    return reported


__all__ = ["MAX_STEP_SECONDS", "snapshot_of", "tick"]

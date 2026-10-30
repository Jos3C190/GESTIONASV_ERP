"""Server side of the tracking simulator, shared by its router and its engine.

A session owns a *virtual* Traccar device per vehicle (``erp-sim-…``). While a
session is open, tracking reads that vehicle from the virtual device; its real
GPS keeps reporting to Traccar and comes back as the source when the session
ends. Nothing here exists in production (``settings.simulator_enabled``).
"""

from __future__ import annotations

import asyncio
import logging
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.traccar_access import traccar
from app.application.tracking.devices import (
    BRANCH_ATTRIBUTE,
    COMPANY_ATTRIBUTE,
    VEHICLE_ATTRIBUTE,
    geofence_applies,
)
from app.application.tracking.simulation import (
    SIMULATED_ATTRIBUTE,
    osmand_params,
    osmand_url,
    unique_id_for,
)
from app.application.tracking.transfers import LngLat
from app.core.config import settings
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.tracking import TrackingAlertModel, TrackingSimulationModel

logger = logging.getLogger(__name__)

OSMAND_TIMEOUT_S = 4
HTTP_ERROR = 400


class ReportError(RuntimeError):
    """Traccar did not accept a simulated position."""


def simulator_enabled() -> bool:
    return settings.simulator_enabled


# ---------------------------------------------------------------- device source


async def open_simulations(
    session: AsyncSession, company_id: uuid.UUID, vehicle_ids: Iterable[uuid.UUID] | None = None
) -> dict[uuid.UUID, TrackingSimulationModel]:
    """Open sessions by vehicle (none while the simulator is off)."""
    if not simulator_enabled():
        return {}
    statement = select(TrackingSimulationModel).where(
        TrackingSimulationModel.company_id == company_id,
        TrackingSimulationModel.state != "ended",
    )
    if vehicle_ids is not None:
        ids = list(vehicle_ids)
        if not ids:
            return {}
        statement = statement.where(TrackingSimulationModel.vehicle_id.in_(ids))
    return {item.vehicle_id: item for item in await session.scalars(statement)}


async def simulation_devices_since(
    session: AsyncSession, company_id: uuid.UUID, since: datetime
) -> dict[int, uuid.UUID]:
    """Virtual devices used since ``since`` (open or recently ended), to label past events."""
    rows = await session.execute(
        select(TrackingSimulationModel.traccar_device_id, TrackingSimulationModel.vehicle_id).where(
            TrackingSimulationModel.company_id == company_id,
            or_(
                TrackingSimulationModel.ended_at.is_(None),
                TrackingSimulationModel.ended_at >= since,
            ),
        )
    )
    return {int(device_id): vehicle_id for device_id, vehicle_id in rows}


def tracking_device(
    vehicle: FleetVehicleModel, simulations: dict[uuid.UUID, TrackingSimulationModel]
) -> tuple[int | None, bool]:
    """Device tracking reads for ``vehicle`` and whether it is the simulator's."""
    simulation = simulations.get(vehicle.id)
    if simulation is not None:
        return simulation.traccar_device_id, True
    return vehicle.traccar_device_id, False


# ---------------------------------------------------------------- Traccar device


def _device_body(existing: dict[str, Any] | None, vehicle: FleetVehicleModel) -> dict[str, Any]:
    attributes = dict((existing or {}).get("attributes") or {})
    attributes.update(
        {
            COMPANY_ATTRIBUTE: str(vehicle.company_id),
            BRANCH_ATTRIBUTE: str(vehicle.branch_id),
            VEHICLE_ATTRIBUTE: str(vehicle.id),
            SIMULATED_ATTRIBUTE: True,
        }
    )
    body = dict(existing or {})
    body.update(
        {
            "name": f"SIM · {vehicle.code}",
            "uniqueId": unique_id_for(vehicle.id),
            "category": "truck",
            "contact": vehicle.plate,
            "attributes": attributes,
        }
    )
    return body


async def ensure_virtual_device(vehicle: FleetVehicleModel) -> tuple[int, str]:
    """Create or relabel the vehicle's virtual GPS and link its geofences."""
    unique_id = unique_id_for(vehicle.id)
    found: list[dict[str, Any]] = (
        await traccar(f"/api/devices?{urlencode({'uniqueId': unique_id})}") or []
    )
    existing = found[0] if found else None
    body = _device_body(existing, vehicle)
    device = (
        await traccar(f"/api/devices/{existing['id']}", method="PUT", body=body)
        if existing is not None
        else await traccar("/api/devices", method="POST", body=body)
    )
    device_id = int(device["id"])
    await link_geofences(device_id, vehicle.company_id, vehicle.branch_id)
    return device_id, unique_id


async def link_geofences(device_id: int, company_id: uuid.UUID, branch_id: uuid.UUID) -> None:
    """Traccar only raises geofence events for linked devices: the same set as a real GPS."""
    geofences: list[dict[str, Any]] = await traccar("/api/geofences") or []
    linked: list[dict[str, Any]] = (
        await traccar(f"/api/geofences?{urlencode({'deviceId': device_id})}") or []
    )
    linked_ids = {item["id"] for item in linked}
    for geofence in geofences:
        applies = geofence_applies(geofence, company_id, branch_id)
        link = {"deviceId": device_id, "geofenceId": geofence["id"]}
        if applies and geofence["id"] not in linked_ids:
            await traccar("/api/permissions", method="POST", body=link)
        elif not applies and geofence["id"] in linked_ids:
            await traccar("/api/permissions", method="DELETE", body=link)


# ---------------------------------------------------------------- reports


def _send(url: str) -> None:
    request = urllib.request.Request(url, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=OSMAND_TIMEOUT_S) as response:  # noqa: S310
            if response.status >= HTTP_ERROR:
                raise ReportError(f"HTTP {response.status}")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ReportError(str(exc)) from exc


async def send_report(
    simulation: TrackingSimulationModel,
    position: LngLat,
    *,
    speed_kmh: float,
    course: float,
    at: datetime | None = None,
) -> None:
    """Report a position to Traccar exactly as the phone app of a driver would."""
    base = osmand_url(settings.TRACCAR_OSMAND_URL, settings.TRACCAR_URL)
    if base is None:
        raise ReportError("Traccar no está configurado.")
    moment = at or datetime.now(UTC)
    query = urlencode(
        osmand_params(simulation.device_unique_id, position, moment, speed_kmh, course)
    )
    await asyncio.to_thread(_send, f"{base}/?{query}")
    simulation.last_report_at = moment


def apply_position(
    simulation: TrackingSimulationModel, position: LngLat, course: float, speed_kmh: float
) -> None:
    simulation.longitude = Decimal(f"{position[0]:.6f}")
    simulation.latitude = Decimal(f"{position[1]:.6f}")
    simulation.course = Decimal(f"{course % 360:.1f}")
    simulation.current_speed_kmh = Decimal(f"{max(speed_kmh, 0.0):.1f}")


# ---------------------------------------------------------------- lifecycle


async def end_simulation(
    session: AsyncSession,
    simulation: TrackingSimulationModel,
    *,
    reason: str,
    actor_id: uuid.UUID | None,
) -> None:
    """Close the session and resolve the alerts it raised; tracking returns to the real GPS."""
    now = datetime.now(UTC)
    simulation.state = "ended"
    simulation.ended_at = now
    simulation.ended_by = actor_id
    simulation.end_reason = reason
    simulation.current_speed_kmh = Decimal("0")
    vehicle = await session.get(FleetVehicleModel, simulation.vehicle_id)
    if vehicle is not None and vehicle.inventory_vehicle_id is not None:
        transfers = select(InventoryTransferModel.id).where(
            InventoryTransferModel.company_id == simulation.company_id,
            InventoryTransferModel.vehicle_id == vehicle.inventory_vehicle_id,
        )
        for alert in await session.scalars(
            select(TrackingAlertModel).where(
                TrackingAlertModel.transfer_id.in_(transfers),
                TrackingAlertModel.simulated.is_(True),
                TrackingAlertModel.resolved_at.is_(None),
            )
        ):
            alert.resolved_at = now
    await session.flush()


async def safe_link_geofences(simulation: TrackingSimulationModel) -> None:
    try:
        await link_geofences(
            simulation.traccar_device_id, simulation.company_id, simulation.branch_id
        )
    except HTTPException:
        logger.warning("simulator_geofence_link_failed simulation_id=%s", simulation.id)


__all__ = [
    "ReportError",
    "apply_position",
    "end_simulation",
    "ensure_virtual_device",
    "link_geofences",
    "open_simulations",
    "safe_link_geofences",
    "send_report",
    "simulation_devices_since",
    "simulator_enabled",
    "tracking_device",
]

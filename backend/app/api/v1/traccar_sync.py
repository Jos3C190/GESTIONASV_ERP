"""Keep Traccar device labels and geofence links in line with the fleet record."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException

from app.api.v1.traccar_access import traccar
from app.application.tracking.devices import (
    BRANCH_ATTRIBUTE,
    COMPANY_ATTRIBUTE,
    VEHICLE_ATTRIBUTE,
    geofence_applies,
)
from app.infrastructure.models.fleet import FleetVehicleModel

logger = logging.getLogger(__name__)


async def sync_geofence_links(vehicle: FleetVehicleModel) -> None:
    """Link the device to the geofences of its company and branch, and only those."""
    device_id = vehicle.traccar_device_id
    if device_id is None:
        return
    geofences: list[dict[str, Any]] = await traccar("/api/geofences") or []
    linked: list[dict[str, Any]] = (
        await traccar(f"/api/geofences?{urlencode({'deviceId': device_id})}") or []
    )
    linked_ids = {item["id"] for item in linked}
    for geofence in geofences:
        applies = geofence_applies(geofence, vehicle.company_id, vehicle.branch_id)
        link = {"deviceId": device_id, "geofenceId": geofence["id"]}
        if applies and geofence["id"] not in linked_ids:
            await traccar("/api/permissions", method="POST", body=link)
        elif not applies and geofence["id"] in linked_ids:
            await traccar("/api/permissions", method="DELETE", body=link)


async def sync_device_branch(vehicle: FleetVehicleModel) -> None:
    """Best effort after a branch change: relabel the device and its geofence links.

    Visibility is decided by the ERP, so a Traccar outage only delays geofence events.
    """
    if vehicle.traccar_device_id is None:
        return
    try:
        device = await traccar(f"/api/devices/{vehicle.traccar_device_id}")
        attributes = dict(device.get("attributes") or {})
        attributes[BRANCH_ATTRIBUTE] = str(vehicle.branch_id)
        await traccar(
            f"/api/devices/{vehicle.traccar_device_id}",
            method="PUT",
            body={**device, "attributes": attributes},
        )
        await sync_geofence_links(vehicle)
    except HTTPException:
        logger.warning("traccar_branch_sync_failed vehicle_id=%s", vehicle.id)


async def release_device(vehicle: FleetVehicleModel) -> None:
    """Remove the ERP labels and geofence links from the vehicle's current device."""
    device_id = vehicle.traccar_device_id
    if device_id is None:
        return
    device = await traccar(f"/api/devices/{device_id}")
    attributes = {
        key: value
        for key, value in (device.get("attributes") or {}).items()
        if key not in {COMPANY_ATTRIBUTE, BRANCH_ATTRIBUTE, VEHICLE_ATTRIBUTE}
    }
    await traccar(
        f"/api/devices/{device_id}", method="PUT", body={**device, "attributes": attributes}
    )
    linked: list[dict[str, Any]] = (
        await traccar(f"/api/geofences?{urlencode({'deviceId': device_id})}") or []
    )
    for geofence in linked:
        if geofence_applies(geofence, vehicle.company_id, vehicle.branch_id):
            await traccar(
                "/api/permissions",
                method="DELETE",
                body={"deviceId": device_id, "geofenceId": geofence["id"]},
            )

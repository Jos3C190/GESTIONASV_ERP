"""Link a fleet vehicle to its GPS device in Traccar."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import get_fleet_scope
from app.api.v1.routers.fleet import scoped_vehicle
from app.api.v1.schemas.fleet import FleetVehicleOut
from app.api.v1.traccar_access import traccar
from app.api.v1.traccar_sync import release_device, sync_geofence_links
from app.application.audit.audit_service import AuditService
from app.application.fleet.views import build_vehicle_views
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.tracking.devices import device_body, device_owner
from app.application.tracking.simulation import is_simulator_unique_id
from app.core.exceptions import ConflictError
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.repositories.fleet_repository import FleetRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fleet", tags=["fleet-gps"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


class GpsDeviceIn(BaseModel):
    #: IMEI or identifier the tracker reports to Traccar.
    unique_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")


async def _view(session: SessionDep, vehicle: FleetVehicleModel) -> FleetVehicleOut:
    views = await build_vehicle_views(
        FleetRepository(session), vehicle.company_id, [vehicle], today=datetime.now(UTC).date()
    )
    return FleetVehicleOut.model_validate(views[0])


@router.put(
    "/vehicles/{vehicle_id}/gps-device",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:gps"))],
)
async def link_gps_device(
    vehicle_id: uuid.UUID,
    body: GpsDeviceIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    repo = FleetRepository(session)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    unique_id = body.unique_id.strip()
    if is_simulator_unique_id(unique_id):
        raise ConflictError(
            "Ese identificador está reservado para el GPS virtual del simulador.",
            code="gps_device_reserved",
        )
    if vehicle.gps_device_unique_id == unique_id:
        return await _view(session, vehicle)
    taken = await session.scalar(
        select(FleetVehicleModel.id).where(
            FleetVehicleModel.gps_device_unique_id == unique_id,
            FleetVehicleModel.id != vehicle.id,
        )
    )
    if taken is not None:
        raise ConflictError(
            "Ese dispositivo GPS ya está vinculado a otro vehículo.", code="gps_device_taken"
        )
    found: list[dict[str, Any]] = (
        await traccar(f"/api/devices?{urlencode({'uniqueId': unique_id})}") or []
    )
    existing = found[0] if found else None
    if existing is not None:
        owner = device_owner(existing)
        if owner is not None and owner != company_id:
            raise ConflictError(
                "El dispositivo está registrado por otra empresa.", code="gps_device_taken"
            )
        other = await session.scalar(
            select(FleetVehicleModel.id).where(
                FleetVehicleModel.traccar_device_id == existing["id"],
                FleetVehicleModel.id != vehicle.id,
            )
        )
        if other is not None:
            raise ConflictError(
                "Ese dispositivo GPS ya está vinculado a otro vehículo.", code="gps_device_taken"
            )
    if vehicle.traccar_device_id is not None:
        await release_device(vehicle)
    payload = device_body(
        existing=existing,
        unique_id=unique_id,
        code=vehicle.code,
        plate=vehicle.plate,
        company_id=company_id,
        branch_id=vehicle.branch_id,
        vehicle_id=vehicle.id,
    )
    device = (
        await traccar(f"/api/devices/{existing['id']}", method="PUT", body=payload)
        if existing is not None
        else await traccar("/api/devices", method="POST", body=payload)
    )
    before = {"gps_device_unique_id": vehicle.gps_device_unique_id}
    async with session.begin_nested():
        vehicle.gps_device_unique_id = unique_id
        vehicle.traccar_device_id = int(device["id"])
        vehicle.updated_by = current.id
        await session.flush()
        await audit.record(
            action="LINK_GPS_DEVICE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state=before,
            after_state={"gps_device_unique_id": unique_id},
            required=True,
        )
    await sync_geofence_links(vehicle)
    return await _view(session, vehicle)


@router.delete(
    "/vehicles/{vehicle_id}/gps-device",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:gps"))],
)
async def unlink_gps_device(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    vehicle = await scoped_vehicle(FleetRepository(session), scope, vehicle_id, lock=True)
    if vehicle.traccar_device_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El vehículo no tiene GPS vinculado.")
    try:
        await release_device(vehicle)
    except HTTPException:
        # El ERP deja de mostrar el dispositivo aunque Traccar no responda ahora.
        logger.warning("traccar_release_failed vehicle_id=%s", vehicle.id)
    before = {"gps_device_unique_id": vehicle.gps_device_unique_id}
    async with session.begin_nested():
        vehicle.gps_device_unique_id = None
        vehicle.traccar_device_id = None
        vehicle.updated_by = current.id
        await session.flush()
        await audit.record(
            action="UNLINK_GPS_DEVICE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state=before,
            after_state={"gps_device_unique_id": None},
            required=True,
        )
    return await _view(session, vehicle)

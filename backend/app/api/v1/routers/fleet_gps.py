"""Link a fleet vehicle to its GPS device in Traccar."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
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
from app.api.v1.traccar_access import traccar, traccar_credentials
from app.api.v1.traccar_sync import release_device, sync_geofence_links
from app.application.audit.audit_service import AuditService
from app.application.fleet.views import build_vehicle_views
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.tracking.device_setup import (
    PHONE_PREFIX,
    client_config_uri,
    device_signal,
    enabled_trackers,
    is_phone_identifier,
    new_phone_identifier,
    public_server,
)
from app.application.tracking.devices import device_body, device_owner
from app.application.tracking.simulation import is_simulator_unique_id
from app.application.tracking.traccar import build_tracked_devices
from app.core.config import settings
from app.core.exceptions import ConflictError
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.repositories.fleet_repository import FleetRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fleet", tags=["fleet-gps"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


class GpsDeviceIn(BaseModel):
    #: ``phone`` gets a generated identifier; ``tracker`` sends the one it reports.
    kind: Literal["tracker", "phone"] = "tracker"
    #: IMEI or identifier the tracker reports to Traccar.
    unique_id: str | None = Field(
        default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"
    )
    #: A phone normally keeps its identifier; replacing it must cut off the previous phone.
    replace: bool = False

    @model_validator(mode="after")
    def _matches_kind(self) -> GpsDeviceIn:
        if (self.kind == "tracker") != (self.unique_id is not None):
            raise ValueError("unique_id is required for a tracker and not allowed for a phone")
        return self


class TrackerModelOut(BaseModel):
    key: str
    brand: str
    models: str
    port: int
    short_identifier: bool


class GpsSetupOut(BaseModel):
    configured: bool
    server_url: str | None
    host: str | None
    private_network: bool
    #: Only once a phone identifier is linked; it holds that identifier.
    phone_config_uri: str | None
    trackers: list[TrackerModelOut]


class GpsStatusOut(BaseModel):
    state: Literal["unlinked", "waiting", "reporting", "silent", "unavailable"]
    kind: Literal["phone", "tracker"] | None
    #: Whether a new device could connect: Traccar and its public address are set.
    server_configured: bool
    last_update: datetime | None = None
    battery_level: float | None = None


def _server_configured() -> bool:
    return (
        traccar_credentials() is not None and public_server(settings.TRACCAR_PUBLIC_URL) is not None
    )


def _target_identifier(vehicle: FleetVehicleModel, body: GpsDeviceIn) -> str:
    if body.kind == "phone":
        # Repetir el paso no debe invalidar un código que ya se escaneó.
        current = vehicle.gps_device_unique_id
        keep = current and is_phone_identifier(current) and not body.replace
        return current if keep and current else new_phone_identifier()
    unique_id = (body.unique_id or "").strip()
    if unique_id.startswith(PHONE_PREFIX):
        raise ConflictError(
            "Ese identificador está reservado para teléfonos.", code="gps_device_reserved"
        )
    if is_simulator_unique_id(unique_id):
        raise ConflictError(
            "Ese identificador está reservado para el GPS virtual del simulador.",
            code="gps_device_reserved",
        )
    return unique_id


async def _view(session: SessionDep, vehicle: FleetVehicleModel) -> FleetVehicleOut:
    views = await build_vehicle_views(
        FleetRepository(session), vehicle.company_id, [vehicle], today=datetime.now(UTC).date()
    )
    return FleetVehicleOut.model_validate(views[0])


@router.get(
    "/vehicles/{vehicle_id}/gps-setup",
    response_model=GpsSetupOut,
    dependencies=[Depends(require_permission("fleet:gps"))],
)
async def get_gps_setup(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> GpsSetupOut:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    vehicle = await scoped_vehicle(FleetRepository(session), scope, vehicle_id)
    server = public_server(settings.TRACCAR_PUBLIC_URL)
    unique_id = vehicle.gps_device_unique_id
    return GpsSetupOut(
        configured=_server_configured(),
        server_url=server.url if server else None,
        host=server.host if server else None,
        private_network=server.private if server else False,
        phone_config_uri=(
            client_config_uri(server.url, unique_id)
            if server and unique_id and is_phone_identifier(unique_id)
            else None
        ),
        trackers=[
            TrackerModelOut(
                key=model.key,
                brand=model.brand,
                models=model.models,
                port=model.port,
                short_identifier=model.short_identifier,
            )
            for model in enabled_trackers(settings.TRACCAR_TRACKER_MODELS)
        ],
    )


@router.get(
    "/vehicles/{vehicle_id}/gps-status",
    response_model=GpsStatusOut,
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def get_gps_status(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> GpsStatusOut:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    vehicle = await scoped_vehicle(FleetRepository(session), scope, vehicle_id)
    configured = _server_configured()
    if vehicle.traccar_device_id is None:
        return GpsStatusOut(state="unlinked", kind=None, server_configured=configured)
    kind: Literal["phone", "tracker"] = (
        "phone" if is_phone_identifier(vehicle.gps_device_unique_id) else "tracker"
    )
    device_id = vehicle.traccar_device_id
    try:
        device = await traccar(f"/api/devices/{device_id}")
        positions = await traccar(f"/api/positions?{urlencode({'deviceId': device_id})}") or []
    except HTTPException:
        # Un fallo del servidor GPS no dice nada del equipo: no se finge un estado.
        return GpsStatusOut(state="unavailable", kind=kind, server_configured=configured)
    tracked = build_tracked_devices([device], positions)[0]
    position = tracked["position"] or {}
    return GpsStatusOut(
        state=device_signal(tracked["last_update"], datetime.now(UTC)),
        kind=kind,
        server_configured=configured,
        last_update=tracked["last_update"],
        battery_level=position.get("battery_level"),
    )


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
    unique_id = _target_identifier(vehicle, body)
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

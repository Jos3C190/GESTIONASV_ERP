"""The company's vehicle type catalogue and the tractor/trailer couplings it allows."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

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
from app.api.v1.schemas.fleet import (
    FleetVehicleOut,
    VehicleCouplingIn,
    VehicleTypeCatalogOut,
    VehicleTypeIn,
    VehicleTypeUpdate,
)
from app.application.audit.audit_service import AuditService
from app.application.fleet.views import build_vehicle_views, vehicle_type_view
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError
from app.infrastructure.models.fleet import (
    FleetVehicleCouplingModel,
    FleetVehicleModel,
    FleetVehicleTypeModel,
)
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-vehicle-types"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_MANAGE = [Depends(require_permission("fleet:manage_types"))]

_DUPLICATE = "Ya existe un tipo de vehículo con ese nombre en esta empresa."


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")[:15] or "tipo"


def _catalog_out(item: FleetVehicleTypeModel, usage: int) -> VehicleTypeCatalogOut:
    return VehicleTypeCatalogOut(**vehicle_type_view(item), id=item.id, usage_count=usage)


async def _vehicle_view(
    repo: FleetRepository, company_id: uuid.UUID, vehicle: FleetVehicleModel
) -> FleetVehicleOut:
    views = await build_vehicle_views(repo, company_id, [vehicle], today=datetime.now(UTC).date())
    return FleetVehicleOut.model_validate(views[0])


@router.get(
    "/vehicle-types",
    response_model=list[VehicleTypeCatalogOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_vehicle_types(
    request: Request,
    session: SessionDep,
    include_inactive: bool = Query(False),
) -> list[VehicleTypeCatalogOut]:
    company_id = effective_company_id(request)
    repo = FleetRepository(session)
    usage = await repo.vehicle_type_usage(company_id)
    items = await repo.vehicle_types(company_id, include_inactive=include_inactive)
    return [_catalog_out(item, usage.get(item.code, 0)) for item in items]


@router.post(
    "/vehicle-types",
    response_model=VehicleTypeCatalogOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_MANAGE,
)
async def create_vehicle_type(
    body: VehicleTypeIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: Audit,
) -> VehicleTypeCatalogOut:
    company_id = effective_company_id(request)
    item = FleetVehicleTypeModel(
        company_id=company_id,
        # El sufijo evita repetir el código de un nombre parecido o ya renombrado.
        code=f"{_slug(body.name)}_{uuid.uuid4().hex[:8]}",
        name=body.name,
        plural=body.plural or body.name,
        license_classes=sorted(set(body.license_classes)),
        base_image=body.base_image,
        requires_plate=body.requires_plate,
        requires_capacity=body.requires_capacity,
        meter_unit=body.meter_unit,
        fuel_applicable=body.fuel_applicable,
        can_tow=body.can_tow,
        is_towable=body.is_towable,
        is_system=False,
    )
    try:
        async with session.begin_nested():
            session.add(item)
            await session.flush()
    except IntegrityError as exc:
        raise ConflictError(_DUPLICATE, code="vehicle_type_duplicate") from exc
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="fleet_vehicle_types",
        resource_id=str(item.id),
        after_state=vehicle_type_view(item),
        required=True,
    )
    return _catalog_out(item, 0)


async def _require_type_change_is_safe(
    session: SessionDep, item: FleetVehicleTypeModel, body: VehicleTypeUpdate, usage: int
) -> None:
    """Changes that would make the vehicles already registered wrong are refused."""
    if not usage:
        return
    if body.meter_unit != item.meter_unit:
        raise ConflictError(
            f"{usage} vehículos miden su uso en la unidad actual; cambiarla falsearía sus lecturas.",
            code="vehicle_type_in_use",
        )
    base = select(func.count()).where(
        FleetVehicleModel.company_id == item.company_id,
        FleetVehicleModel.kind == item.code,
        FleetVehicleModel.deleted_at.is_(None),
    )
    if body.requires_plate and await session.scalar(base.where(FleetVehicleModel.plate.is_(None))):
        raise ConflictError(
            "Hay vehículos de este tipo sin placa; regístrela antes de exigirla.",
            code="vehicle_type_in_use",
        )
    if body.requires_capacity and await session.scalar(
        base.where(FleetVehicleModel.capacity_kg.is_(None))
    ):
        raise ConflictError(
            "Hay vehículos de este tipo sin capacidad; regístrela antes de exigirla.",
            code="vehicle_type_in_use",
        )
    if body.fuel_applicable and await session.scalar(
        base.where(FleetVehicleModel.fuel_type == "none")
    ):
        raise ConflictError(
            "Hay vehículos de este tipo sin combustible; indíquelo antes de exigirlo.",
            code="vehicle_type_in_use",
        )


@router.patch(
    "/vehicle-types/{type_id}",
    response_model=VehicleTypeCatalogOut,
    dependencies=_MANAGE,
)
async def update_vehicle_type(
    type_id: uuid.UUID,
    body: VehicleTypeUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: Audit,
) -> VehicleTypeCatalogOut:
    company_id = effective_company_id(request)
    item = await session.scalar(
        select(FleetVehicleTypeModel)
        .where(FleetVehicleTypeModel.id == type_id, FleetVehicleTypeModel.company_id == company_id)
        .with_for_update()
    )
    if item is None:
        raise NotFoundError("Tipo de vehículo no encontrado.", code="vehicle_type_not_found")
    usage = (await FleetRepository(session).vehicle_type_usage(company_id)).get(item.code, 0)
    await _require_type_change_is_safe(session, item, body, usage)
    if usage and (body.can_tow != item.can_tow or body.is_towable != item.is_towable):
        coupled = await session.scalar(
            select(func.count())
            .select_from(FleetVehicleCouplingModel)
            .join(
                FleetVehicleModel,
                FleetVehicleModel.id.in_(
                    [FleetVehicleCouplingModel.tractor_id, FleetVehicleCouplingModel.trailer_id]
                ),
            )
            .where(
                FleetVehicleModel.company_id == company_id,
                FleetVehicleModel.kind == item.code,
                FleetVehicleCouplingModel.ended_at.is_(None),
            )
        )
        if coupled:
            raise ConflictError(
                "Hay vehículos de este tipo enganchados; desengánchelos primero.",
                code="vehicle_type_in_use",
            )
    before = vehicle_type_view(item)
    try:
        async with session.begin_nested():
            item.name = body.name
            item.plural = body.plural or body.name
            item.license_classes = sorted(set(body.license_classes))
            item.base_image = body.base_image
            item.requires_plate = body.requires_plate
            item.requires_capacity = body.requires_capacity
            item.meter_unit = body.meter_unit
            item.fuel_applicable = body.fuel_applicable
            item.can_tow = body.can_tow
            item.is_towable = body.is_towable
            item.is_active = body.is_active
            await session.flush()
    except IntegrityError as exc:
        raise ConflictError(_DUPLICATE, code="vehicle_type_duplicate") from exc
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="fleet_vehicle_types",
        resource_id=str(item.id),
        before_state=before,
        after_state=vehicle_type_view(item),
        required=True,
    )
    return _catalog_out(item, usage)


# ------------------------------------------------------------------ couplings


async def _on_road(repo: FleetRepository, vehicle: FleetVehicleModel) -> bool:
    if vehicle.inventory_vehicle_id is None:
        return False
    return bool(await repo.active_transfers(vehicle.company_id, [vehicle.inventory_vehicle_id]))


def _coupling_state(coupling: FleetVehicleCouplingModel) -> dict[str, Any]:
    return {
        "coupling_id": str(coupling.id),
        "tractor_id": str(coupling.tractor_id),
        "trailer_id": str(coupling.trailer_id),
    }


@router.put(
    "/vehicles/{vehicle_id}/coupling",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def couple_trailer(
    vehicle_id: uuid.UUID,
    body: VehicleCouplingIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    repo = FleetRepository(session)
    tractor = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    trailer = await scoped_vehicle(repo, scope, body.trailer_id, lock=True)
    tractor_type = await repo.vehicle_type(company_id, tractor.kind)
    trailer_type = await repo.vehicle_type(company_id, trailer.kind)
    if tractor_type is None or not tractor_type.can_tow:
        raise ConflictError("Este vehículo no puede remolcar.", code="vehicle_cannot_tow")
    if trailer_type is None or not trailer_type.is_towable:
        raise ConflictError("Ese vehículo no es un remolque.", code="vehicle_not_towable")
    if tractor.branch_id != trailer.branch_id:
        raise ConflictError(
            "El cabezal y el remolque deben pertenecer a la misma sucursal.",
            code="coupling_branch_mismatch",
        )
    if "retired" in (tractor.status, trailer.status):
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    if await repo.open_coupling(tractor.id) or await repo.open_coupling(trailer.id):
        raise ConflictError(
            "El cabezal o el remolque ya están enganchados.", code="vehicle_is_coupled"
        )
    if await _on_road(repo, tractor):
        raise ConflictError("El cabezal está en un traslado.", code="vehicle_on_road")
    async with session.begin_nested():
        coupling = FleetVehicleCouplingModel(
            company_id=company_id,
            tractor_id=tractor.id,
            trailer_id=trailer.id,
            created_by=current.id,
        )
        session.add(coupling)
        await session.flush()
        await audit.record(
            action="COUPLE_TRAILER",
            user_id=current.id,
            company_id=company_id,
            branch_id=tractor.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(tractor.id),
            after_state=_coupling_state(coupling),
            required=True,
        )
    return await _vehicle_view(repo, company_id, tractor)


@router.delete(
    "/vehicles/{vehicle_id}/coupling",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def uncouple_trailer(
    vehicle_id: uuid.UUID,
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
    coupling = await repo.open_coupling(vehicle.id)
    if coupling is None:
        raise NotFoundError("El vehículo no está enganchado.", code="vehicle_not_coupled")
    tractor = await repo.get_vehicle(company_id, coupling.tractor_id)
    if tractor is not None and await _on_road(repo, tractor):
        raise ConflictError("El cabezal está en un traslado.", code="vehicle_on_road")
    async with session.begin_nested():
        coupling.ended_at = datetime.now(UTC)
        coupling.ended_by = current.id
        await session.flush()
        await audit.record(
            action="UNCOUPLE_TRAILER",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state=_coupling_state(coupling),
            required=True,
        )
    return await _vehicle_view(repo, company_id, vehicle)

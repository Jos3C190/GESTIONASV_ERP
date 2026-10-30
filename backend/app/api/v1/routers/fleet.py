"""Fleet vehicles: catalogue, status, home branch, gallery and documents.

Fleet is the source of truth for vehicles. Creating a vehicle also creates its
inventory "transit location" used by transfers, and status changes are kept in
sync with it. All routes are company-bound and branch-scoped through
:mod:`app.api.v1.fleet_scope`.
"""

from __future__ import annotations

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
from app.api.v1.fleet_scope import FleetScope, get_fleet_scope
from app.api.v1.routers.owned_documents import (
    OwnedDocumentsSpec,
    OwnerContext,
    build_owned_documents_router,
)
from app.api.v1.schemas.fleet import (
    FleetSummaryOut,
    FleetVehicleCreate,
    FleetVehicleOut,
    FleetVehiclesPage,
    FleetVehicleUpdate,
    VehicleBranchIn,
    VehiclePhotoIn,
    VehiclePhotoOut,
    VehicleStatusIn,
)
from app.api.v1.traccar_sync import sync_device_branch
from app.application.audit.audit_service import AuditService
from app.application.fleet.compliance import license_issue
from app.application.fleet.views import build_vehicle_views, summarize
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.inventory_transfer import TransferDomainError
from app.infrastructure.media_assets import attach_media_by_url
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleModel,
    FleetVehiclePhotoModel,
    OdometerReadingModel,
)
from app.infrastructure.models.inventory_transfer import InventoryVehicleModel
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.repositories.fleet_repository import FleetRepository
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)

router = APIRouter(prefix="/fleet", tags=["fleet"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]

MAX_PHOTOS = 20
MIN_REASON_LENGTH = 3
_CONFLICT_FIELDS = {
    "code": "Ya existe un vehículo con ese código en la empresa.",
    "plate": "Ya existe un vehículo con esa placa en la empresa.",
    "vin": "Ya existe un vehículo con ese VIN en la empresa.",
}


def _today() -> Any:
    return datetime.now(UTC).date()


def _state(vehicle: FleetVehicleModel) -> dict[str, object]:
    return {
        "code": vehicle.code,
        "plate": vehicle.plate,
        "vin": vehicle.vin,
        "kind": vehicle.kind,
        "brand": vehicle.brand,
        "model": vehicle.model,
        "year": vehicle.year,
        "capacity_kg": str(vehicle.capacity_kg),
        "fuel_type": vehicle.fuel_type,
        "status": vehicle.status,
        "branch_id": str(vehicle.branch_id),
    }


def _inventory_name(vehicle: FleetVehicleModel) -> str:
    return f"{vehicle.brand} {vehicle.model} ({vehicle.plate})"[:120]


async def _context(
    request: Request, session: SessionDep, current: CurrentUser, checker: CheckPermissionUseCase
) -> tuple[uuid.UUID, FleetScope, FleetRepository]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    return company_id, scope, FleetRepository(session)


async def scoped_vehicle(
    repo: FleetRepository,
    scope: FleetScope,
    vehicle_id: uuid.UUID,
    *,
    lock: bool = False,
) -> FleetVehicleModel:
    vehicle = await repo.get_vehicle(scope.company_id, vehicle_id, lock=lock)
    if vehicle is None:
        raise NotFoundError("Vehículo no encontrado.", code="vehicle_not_found")
    scope.require(vehicle.branch_id, not_found="Vehículo no encontrado.")
    return vehicle


async def _view(
    repo: FleetRepository, company_id: uuid.UUID, vehicle: FleetVehicleModel
) -> FleetVehicleOut:
    views = await build_vehicle_views(repo, company_id, [vehicle], today=_today())
    return FleetVehicleOut.model_validate(views[0])


async def _ensure_unique(
    repo: FleetRepository,
    company_id: uuid.UUID,
    *,
    code: str | None = None,
    plate: str | None = None,
    vin: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    field = await repo.conflicting_vehicle(
        company_id, code=code, plate=plate, vin=vin, exclude_id=exclude_id
    )
    if field is not None:
        raise ConflictError(_CONFLICT_FIELDS[field], code=f"vehicle_{field}_taken")


async def _require_not_on_road(
    repo: FleetRepository, vehicle: FleetVehicleModel, action: str
) -> None:
    if vehicle.inventory_vehicle_id is None:
        return
    trips = await repo.active_transfers(vehicle.company_id, [vehicle.inventory_vehicle_id])
    if trips:
        trip = next(iter(trips.values()))
        raise ConflictError(
            f"No se puede {action}: el vehículo está en el traslado {trip['code']}.",
            code="vehicle_on_road",
        )


async def _set_inventory_status(
    session: SessionDep, vehicle: FleetVehicleModel, inventory_status: str
) -> None:
    if vehicle.inventory_vehicle_id is None:
        return
    try:
        await SqlAlchemyInventoryTransferRepository(session).set_vehicle_status(
            company_id=vehicle.company_id,
            vehicle_id=vehicle.inventory_vehicle_id,
            status=inventory_status,
        )
    except TransferDomainError as exc:
        raise ConflictError(exc.message, code=exc.code) from exc


async def _ensure_driver_can_drive(
    session: SessionDep, repo: FleetRepository, vehicle: FleetVehicleModel, kind: str
) -> None:
    assignment = await repo.open_assignment_for_vehicle(vehicle.id)
    if assignment is None:
        return
    driver = await session.get(DriverModel, assignment.driver_id)
    if driver is not None and license_issue(driver.license_class, kind):
        raise ConflictError(
            "La licencia del conductor asignado no permite el nuevo tipo de vehículo; "
            "finalice la asignación primero.",
            code="license_class_incompatible",
        )


async def ensure_inventory_vehicle(
    session: SessionDep, vehicle: FleetVehicleModel, actor_id: uuid.UUID
) -> uuid.UUID | None:
    """Create the transfer "transit location" of a fleet vehicle when possible.

    It needs an active headquarters with an active central warehouse. Until the
    company has one, the vehicle works in Fleet but cannot be dispatched; the
    link is created on the next sync (vehicle update or transfers listing).
    """
    if vehicle.inventory_vehicle_id is not None:
        return vehicle.inventory_vehicle_id
    repository = SqlAlchemyInventoryTransferRepository(session)
    try:
        async with session.begin_nested():
            inventory = await repository.create_vehicle(
                company_id=vehicle.company_id,
                code=vehicle.code,
                name=_inventory_name(vehicle),
                actor_id=actor_id,
            )
    except TransferDomainError as exc:
        if exc.code == "transit_warehouse_not_configured":
            return None
        raise ConflictError(exc.message, code=exc.code) from exc
    return uuid.UUID(str(inventory["id"]))


# ------------------------------------------------------------------ listing


@router.get(
    "/vehicles",
    response_model=FleetVehiclesPage,
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_vehicles(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID | None = Query(None),
    vehicle_status: str | None = Query(
        None, alias="status", pattern="^(active|maintenance|out_of_service|retired)$"
    ),
    kind: str | None = Query(None, max_length=24),
    search: str | None = Query(None, max_length=80),
    include_retired: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=100),
) -> FleetVehiclesPage:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicles, total = await repo.list_vehicles(
        company_id,
        scope.list_filter(branch_id),
        status=vehicle_status,
        kind=kind,
        search=search,
        include_retired=include_retired,
        page=page,
        size=size,
    )
    views = await build_vehicle_views(repo, company_id, vehicles, today=_today())
    return FleetVehiclesPage(
        items=[FleetVehicleOut.model_validate(view) for view in views],
        meta={
            "page": page,
            "size": size,
            "total": total,
            "pages": (total + size - 1) // size if total else 1,
        },
    )


@router.get(
    "/vehicles/summary",
    response_model=FleetSummaryOut,
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def vehicles_summary(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    branch_id: uuid.UUID | None = Query(None),
) -> FleetSummaryOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicles = await repo.all_vehicles(company_id, scope.list_filter(branch_id))
    views = await build_vehicle_views(repo, company_id, vehicles, today=_today())
    return FleetSummaryOut.model_validate(summarize(views))


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> FleetVehicleOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    return await _view(repo, company_id, vehicle)


# ------------------------------------------------------------------ mutations


@router.post(
    "/vehicles",
    response_model=FleetVehicleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:create"))],
)
async def create_vehicle(
    body: FleetVehicleCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    scope.require_target(body.branch_id)
    branch = await repo.branch(company_id, body.branch_id)
    if branch is None or not branch.is_active:
        raise ValidationError("La sucursal no existe o no está activa.", code="branch_inactive")
    await _ensure_unique(repo, company_id, code=body.code, plate=body.plate, vin=body.vin)
    async with session.begin_nested():
        vehicle = FleetVehicleModel(
            company_id=company_id,
            branch_id=body.branch_id,
            code=body.code,
            plate=body.plate,
            vin=body.vin,
            kind=body.kind,
            brand=body.brand,
            model=body.model,
            year=body.year,
            color=body.color,
            capacity_kg=body.capacity_kg,
            fuel_type=body.fuel_type,
            odometer_km=body.odometer_km,
            notes=body.notes,
            status="active",
            created_by=current.id,
            updated_by=current.id,
        )
        vehicle.inventory_vehicle_id = await ensure_inventory_vehicle(session, vehicle, current.id)
        session.add(vehicle)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "Ya existe un vehículo con esos datos en la empresa.", code="vehicle_conflict"
            ) from exc
        if body.odometer_km > 0:
            session.add(
                OdometerReadingModel(
                    company_id=company_id,
                    vehicle_id=vehicle.id,
                    reading_km=body.odometer_km,
                    read_at=datetime.now(UTC),
                    source="manual",
                    notes="Lectura inicial al registrar el vehículo.",
                    recorded_by=current.id,
                )
            )
        await audit.record(
            action="CREATE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state=_state(vehicle),
            required=True,
        )
    return await _view(repo, company_id, vehicle)


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    body: FleetVehicleUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    if vehicle.status == "retired":
        raise ConflictError("Reactive el vehículo antes de editarlo.", code="vehicle_retired")
    changes = body.model_dump(exclude_unset=True)
    for required in ("plate", "kind", "brand", "model", "year", "capacity_kg", "fuel_type"):
        if required in changes and changes[required] is None:
            raise ValidationError(
                "Complete los datos obligatorios del vehículo.", code="vehicle_invalid"
            )
    await _ensure_unique(
        repo, company_id, plate=changes.get("plate"), vin=changes.get("vin"), exclude_id=vehicle.id
    )
    if "kind" in changes and changes["kind"] != vehicle.kind:
        await _ensure_driver_can_drive(session, repo, vehicle, changes["kind"])
    before = _state(vehicle)
    async with session.begin_nested():
        for field, value in changes.items():
            setattr(vehicle, field, value)
        vehicle.updated_by = current.id
        vehicle.inventory_vehicle_id = await ensure_inventory_vehicle(session, vehicle, current.id)
        if vehicle.inventory_vehicle_id is not None:
            inventory = await session.get(InventoryVehicleModel, vehicle.inventory_vehicle_id)
            if inventory is not None:
                inventory.name = _inventory_name(vehicle)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "Ya existe un vehículo con esos datos en la empresa.", code="vehicle_conflict"
            ) from exc
        await audit.record(
            action="UPDATE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state=before,
            after_state=_state(vehicle),
            required=True,
        )
    return await _view(repo, company_id, vehicle)


@router.post(
    "/vehicles/{vehicle_id}/status",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def change_vehicle_status(
    vehicle_id: uuid.UUID,
    body: VehicleStatusIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    if body.status == vehicle.status:
        return await _view(repo, company_id, vehicle)
    if vehicle.status == "maintenance":
        raise ConflictError(
            "El vehículo está en mantenimiento; complete o cancele la orden en curso.",
            code="vehicle_in_maintenance",
        )
    if body.status != "active":
        await _require_not_on_road(repo, vehicle, "cambiar su estado")
        if not body.reason or len(body.reason.strip()) < MIN_REASON_LENGTH:
            raise ValidationError("Indique el motivo del cambio de estado.", code="reason_required")
    if body.status == "retired" and await repo.open_assignment_for_vehicle(vehicle.id):
        raise ConflictError(
            "Finalice la asignación del conductor antes de dar de baja el vehículo.",
            code="vehicle_has_driver",
        )
    before = _state(vehicle)
    async with session.begin_nested():
        vehicle.status = body.status
        vehicle.updated_by = current.id
        await _set_inventory_status(
            session, vehicle, "active" if body.status == "active" else "inactive"
        )
        await session.flush()
        await audit.record(
            action="STATUS_CHANGE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state=before,
            after_state=_state(vehicle),
            metadata={"reason": body.reason},
            required=True,
        )
    return await _view(repo, company_id, vehicle)


@router.post(
    "/vehicles/{vehicle_id}/branch",
    response_model=FleetVehicleOut,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def change_vehicle_branch(
    vehicle_id: uuid.UUID,
    body: VehicleBranchIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetVehicleOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    scope.require_target(body.branch_id)
    if body.branch_id == vehicle.branch_id:
        return await _view(repo, company_id, vehicle)
    branch = await repo.branch(company_id, body.branch_id)
    if branch is None or not branch.is_active:
        raise ValidationError("La sucursal no existe o no está activa.", code="branch_inactive")
    await _require_not_on_road(repo, vehicle, "cambiarlo de sucursal")
    if await repo.open_assignment_for_vehicle(vehicle.id):
        raise ConflictError(
            "Finalice la asignación del conductor antes de cambiar la sucursal del vehículo.",
            code="vehicle_has_driver",
        )
    before = _state(vehicle)
    async with session.begin_nested():
        vehicle.branch_id = body.branch_id
        vehicle.updated_by = current.id
        await session.flush()
        await audit.record(
            action="CHANGE_BRANCH",
            user_id=current.id,
            company_id=company_id,
            branch_id=body.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state=before,
            after_state=_state(vehicle),
            metadata={"reason": body.reason},
            required=True,
        )
    await sync_device_branch(vehicle)
    return await _view(repo, company_id, vehicle)


# ------------------------------------------------------------------ gallery


def _photo_out(photo: FleetVehiclePhotoModel) -> VehiclePhotoOut:
    return VehiclePhotoOut(
        id=photo.id,
        url=photo.url,
        caption=photo.caption,
        position=photo.position,
        created_at=photo.created_at,
    )


@router.get(
    "/vehicles/{vehicle_id}/photos",
    response_model=list[VehiclePhotoOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def list_photos(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[VehiclePhotoOut]:
    _, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    return [_photo_out(photo) for photo in await repo.photos(vehicle.id)]


@router.post(
    "/vehicles/{vehicle_id}/photos",
    response_model=VehiclePhotoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def add_photo(
    vehicle_id: uuid.UUID,
    body: VehiclePhotoIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> VehiclePhotoOut:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id, lock=True)
    asset = await session.scalar(select(MediaAsset).where(MediaAsset.secure_url == body.url))
    if (
        asset is None
        or asset.company_id != company_id
        or asset.purpose != "vehicle_image"
        or asset.status not in {"staged", "detached"}
        or (asset.uploaded_by != current.id and not current.is_superuser)
    ):
        raise ValidationError(
            "La imagen no es válida para este vehículo; súbala de nuevo.",
            code="vehicle_photo_invalid",
        )
    count = int(
        await session.scalar(
            select(func.count(FleetVehiclePhotoModel.id)).where(
                FleetVehiclePhotoModel.vehicle_id == vehicle.id
            )
        )
        or 0
    )
    if count >= MAX_PHOTOS:
        raise ConflictError(
            f"La galería admite hasta {MAX_PHOTOS} fotos.", code="vehicle_photo_limit"
        )
    async with session.begin_nested():
        await attach_media_by_url(
            session,
            secure_url=body.url,
            company_id=company_id,
            owner_type="fleet_vehicle",
            owner_id=vehicle.id,
        )
        photo = FleetVehiclePhotoModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            url=asset.secure_url,
            public_id=asset.public_id,
            caption=(body.caption or "").strip() or None,
            position=count,
            uploaded_by=current.id,
        )
        session.add(photo)
        await session.flush()
        await audit.record(
            action="ADD_PHOTO",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"photo_id": str(photo.id)},
        )
    return _photo_out(photo)


@router.delete(
    "/vehicles/{vehicle_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("fleet:update"))],
)
async def delete_photo(
    vehicle_id: uuid.UUID,
    photo_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> None:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, vehicle_id)
    photo = await session.scalar(
        select(FleetVehiclePhotoModel).where(
            FleetVehiclePhotoModel.id == photo_id,
            FleetVehiclePhotoModel.vehicle_id == vehicle.id,
            FleetVehiclePhotoModel.company_id == company_id,
        )
    )
    if photo is None:
        raise NotFoundError("Foto no encontrada.", code="vehicle_photo_not_found")
    async with session.begin_nested():
        asset = await session.scalar(select(MediaAsset).where(MediaAsset.secure_url == photo.url))
        if asset is not None and asset.owner_id == vehicle.id:
            asset.status = "detached"
        await session.delete(photo)
        await session.flush()
        await audit.record(
            action="DELETE_PHOTO",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"photo_id": str(photo_id)},
        )


# ------------------------------------------------------------------ documents


async def _resolve_vehicle_owner(
    owner_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
) -> OwnerContext:
    company_id, scope, repo = await _context(request, session, current, checker)
    vehicle = await scoped_vehicle(repo, scope, owner_id)
    return OwnerContext(company_id=company_id, owner_id=vehicle.id)


documents_router = build_owned_documents_router(
    OwnedDocumentsSpec(
        path="/vehicles",
        module="fleet",
        owner_type="vehicle",
        read="fleet_documents:read",
        upload="fleet_documents:upload",
        update="fleet_documents:update",
        download="fleet_documents:download",
        resolve=_resolve_vehicle_owner,
    ),
    prefix="/fleet",
    tag="fleet-documents",
)

__all__ = ["documents_router", "router", "scoped_vehicle"]

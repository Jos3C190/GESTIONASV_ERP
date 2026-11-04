"""Pre-departure checks: a company's checklist, its results and resolving what failed."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
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
    FleetInspectionIn,
    FleetInspectionOut,
    InspectionItemIn,
    InspectionItemOut,
    InspectionItemUpdate,
    InspectionResultOut,
    VoidRecordIn,
)
from app.application.audit.audit_service import AuditService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.media_assets import attach_media_by_url
from app.infrastructure.models.fleet import (
    FleetInspectionItemModel,
    FleetInspectionModel,
    FleetInspectionResultModel,
    FleetVehicleModel,
)
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-inspections"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_READ = [Depends(require_permission("fleet:read"))]
_INSPECT = [Depends(require_permission("fleet:inspections"))]
_MANAGE = [Depends(require_permission("fleet:manage_types"))]


# ------------------------------------------------------------------ checklist


def _item_out(item: FleetInspectionItemModel) -> InspectionItemOut:
    return InspectionItemOut(
        id=item.id,
        name=item.name,
        is_critical=item.is_critical,
        is_active=item.is_active,
    )


@router.get("/inspection-items", response_model=list[InspectionItemOut], dependencies=_READ)
async def list_items(
    request: Request,
    session: SessionDep,
    include_inactive: bool = Query(False),
) -> list[InspectionItemOut]:
    statement = select(FleetInspectionItemModel).where(
        FleetInspectionItemModel.company_id == effective_company_id(request)
    )
    if not include_inactive:
        statement = statement.where(FleetInspectionItemModel.is_active.is_(True))
    items = await session.scalars(
        statement.order_by(FleetInspectionItemModel.sort_order, FleetInspectionItemModel.name)
    )
    return [_item_out(item) for item in items]


@router.post(
    "/inspection-items",
    response_model=InspectionItemOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_MANAGE,
)
async def create_item(
    body: InspectionItemIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: Audit,
) -> InspectionItemOut:
    company_id = effective_company_id(request)
    last = await session.scalar(
        select(func.max(FleetInspectionItemModel.sort_order)).where(
            FleetInspectionItemModel.company_id == company_id
        )
    )
    item = FleetInspectionItemModel(
        company_id=company_id,
        name=body.name.strip(),
        is_critical=body.is_critical,
        sort_order=(last or 0) + 10,
    )
    await _save_item(session, item)
    await audit.record(
        action="CREATE_INSPECTION_ITEM",
        user_id=current.id,
        company_id=company_id,
        resource_type="fleet_inspection_items",
        resource_id=str(item.id),
        after_state={"name": item.name, "is_critical": item.is_critical},
        required=True,
    )
    return _item_out(item)


async def _save_item(session: SessionDep, item: FleetInspectionItemModel) -> None:
    try:
        async with session.begin_nested():
            session.add(item)
            await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Ya existe un punto de inspección con ese nombre.", code="inspection_item_exists"
        ) from exc


@router.patch(
    "/inspection-items/{item_id}",
    response_model=InspectionItemOut,
    dependencies=_MANAGE,
)
async def update_item(
    item_id: uuid.UUID,
    body: InspectionItemUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: Audit,
) -> InspectionItemOut:
    company_id = effective_company_id(request)
    item = await session.scalar(
        select(FleetInspectionItemModel)
        .where(
            FleetInspectionItemModel.id == item_id,
            FleetInspectionItemModel.company_id == company_id,
        )
        .with_for_update()
    )
    if item is None:
        raise NotFoundError("Punto de inspección no encontrado.", code="inspection_item_not_found")
    before = {"name": item.name, "is_critical": item.is_critical, "is_active": item.is_active}
    # Las inspecciones ya hechas guardan su propia copia: cambiar esto no las reescribe.
    item.name = body.name.strip()
    item.is_critical = body.is_critical
    item.is_active = body.is_active
    await _save_item(session, item)
    await audit.record(
        action="UPDATE_INSPECTION_ITEM",
        user_id=current.id,
        company_id=company_id,
        resource_type="fleet_inspection_items",
        resource_id=str(item.id),
        before_state=before,
        after_state={
            "name": item.name,
            "is_critical": item.is_critical,
            "is_active": item.is_active,
        },
        required=True,
    )
    return _item_out(item)


# ------------------------------------------------------------------ inspections


async def _vehicle(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    vehicle_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[uuid.UUID, FleetRepository, FleetVehicleModel]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    repo = FleetRepository(session)
    # La sucursal que lo tiene prestado es la que debe inspeccionarlo antes de salir.
    return company_id, repo, await scoped_vehicle(repo, scope, vehicle_id, lock=lock, borrowed=True)


def _result_out(result: FleetInspectionResultModel, resolver: str | None) -> InspectionResultOut:
    return InspectionResultOut(
        id=result.id,
        item_name=result.item_name,
        is_critical=result.is_critical,
        passed=result.passed,
        notes=result.notes,
        photo_url=result.photo_url,
        resolved_at=result.resolved_at,
        resolved_by_name=resolver,
        resolution=result.resolution,
    )


async def _inspections(
    session: SessionDep, vehicle_id: uuid.UUID, inspection_id: uuid.UUID | None = None
) -> list[FleetInspectionOut]:
    # Las recientes, más cualquiera con una falla crítica abierta: lo que frena el despacho
    # siempre debe poder verse y resolverse, por antigua que sea.
    recent = (
        select(FleetInspectionModel.id)
        .where(FleetInspectionModel.vehicle_id == vehicle_id)
        .order_by(FleetInspectionModel.inspected_at.desc())
        .limit(50)
    )
    open_failures = select(FleetInspectionResultModel.inspection_id).where(
        FleetInspectionResultModel.vehicle_id == vehicle_id,
        FleetInspectionResultModel.is_critical.is_(True),
        FleetInspectionResultModel.passed.is_(False),
        FleetInspectionResultModel.resolved_at.is_(None),
    )
    statement = (
        select(FleetInspectionModel, User.username)
        .outerjoin(User, User.id == FleetInspectionModel.inspected_by)
        .where(FleetInspectionModel.vehicle_id == vehicle_id)
        .order_by(FleetInspectionModel.inspected_at.desc())
    )
    if inspection_id is not None:
        statement = statement.where(FleetInspectionModel.id == inspection_id)
    else:
        statement = statement.where(
            or_(FleetInspectionModel.id.in_(recent), FleetInspectionModel.id.in_(open_failures))
        )
    rows = (await session.execute(statement)).all()
    results: dict[uuid.UUID, list[InspectionResultOut]] = defaultdict(list)
    if rows:
        items = await session.execute(
            select(FleetInspectionResultModel, User.username)
            .outerjoin(User, User.id == FleetInspectionResultModel.resolved_by)
            .where(FleetInspectionResultModel.inspection_id.in_([row[0].id for row in rows]))
            .order_by(FleetInspectionResultModel.passed, FleetInspectionResultModel.item_name)
        )
        for result, resolver in items.all():
            results[result.inspection_id].append(_result_out(result, resolver))
    return [
        FleetInspectionOut(
            id=inspection.id,
            inspected_at=inspection.inspected_at,
            passed=inspection.passed,
            notes=inspection.notes,
            inspected_by_name=inspector,
            results=results[inspection.id],
        )
        for inspection, inspector in rows
    ]


@router.get(
    "/vehicles/{vehicle_id}/inspections",
    response_model=list[FleetInspectionOut],
    dependencies=_READ,
)
async def list_inspections(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[FleetInspectionOut]:
    _, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    return await _inspections(session, vehicle.id)


async def _require_photo(
    session: SessionDep, url: str, company_id: uuid.UUID, current: CurrentUser
) -> None:
    asset = await session.scalar(select(MediaAsset).where(MediaAsset.secure_url == url))
    if (
        asset is None
        or asset.company_id != company_id
        or asset.purpose != "vehicle_image"
        or asset.status not in {"staged", "detached"}
        or (asset.uploaded_by != current.id and not current.is_superuser)
    ):
        raise ValidationError(
            "La foto no es válida para esta inspección; súbala de nuevo.",
            code="inspection_photo_invalid",
        )


@router.post(
    "/vehicles/{vehicle_id}/inspections",
    response_model=FleetInspectionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_INSPECT,
)
async def add_inspection(
    vehicle_id: uuid.UUID,
    body: FleetInspectionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetInspectionOut:
    company_id, repo, vehicle = await _vehicle(
        request, session, current, checker, vehicle_id, lock=True
    )
    if vehicle.status == "retired":
        raise ConflictError("El vehículo está dado de baja.", code="vehicle_retired")
    if (
        body.driver_id is not None
        and await repo.driver_with_employee(company_id, body.driver_id) is None
    ):
        raise ValidationError("El conductor no existe.", code="inspection_driver_invalid")
    items = list(
        await session.scalars(
            select(FleetInspectionItemModel).where(
                FleetInspectionItemModel.company_id == company_id,
                FleetInspectionItemModel.is_active.is_(True),
            )
        )
    )
    by_id = {item.id: item for item in items}
    answered = {answer.item_id: answer for answer in body.results}
    if not by_id:
        raise ConflictError(
            "La empresa no tiene puntos de inspección activos.", code="inspection_no_items"
        )
    if set(answered) != set(by_id):
        raise ValidationError(
            "Revise todos los puntos de la lista antes de guardar.",
            code="inspection_incomplete",
        )
    for answer in body.results:
        if (
            not answer.passed
            and by_id[answer.item_id].is_critical
            and not (answer.notes or "").strip()
        ):
            raise ValidationError(
                f"Describa la falla en {by_id[answer.item_id].name}.",
                code="inspection_failure_notes_required",
            )
        if answer.photo_url:
            await _require_photo(session, answer.photo_url, company_id, current)
    failed = [answer for answer in body.results if not answer.passed]
    critical = [answer for answer in failed if by_id[answer.item_id].is_critical]
    async with session.begin_nested():
        inspection = FleetInspectionModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            driver_id=body.driver_id,
            inspected_at=datetime.now(UTC),
            passed=not critical,
            notes=(body.notes or "").strip() or None,
            inspected_by=current.id,
        )
        session.add(inspection)
        await session.flush()
        for answer in body.results:
            item = by_id[answer.item_id]
            result = FleetInspectionResultModel(
                company_id=company_id,
                inspection_id=inspection.id,
                vehicle_id=vehicle.id,
                item_id=item.id,
                item_name=item.name,
                is_critical=item.is_critical,
                passed=answer.passed,
                notes=(answer.notes or "").strip() or None,
                photo_url=answer.photo_url,
            )
            session.add(result)
            await session.flush()
            if answer.photo_url:
                await attach_media_by_url(
                    session,
                    secure_url=answer.photo_url,
                    company_id=company_id,
                    owner_type="fleet_inspection_result",
                    owner_id=result.id,
                )
        await audit.record(
            action="FLEET_INSPECTION",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={
                "inspection_id": str(inspection.id),
                "passed": inspection.passed,
                "failed": len(failed),
                "critical": len(critical),
            },
            required=True,
        )
    return (await _inspections(session, vehicle.id, inspection.id))[0]


@router.post(
    "/vehicles/{vehicle_id}/inspection-results/{result_id}/resolve",
    response_model=InspectionResultOut,
    dependencies=_INSPECT,
)
async def resolve_result(
    vehicle_id: uuid.UUID,
    result_id: uuid.UUID,
    body: VoidRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> InspectionResultOut:
    company_id, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    result = await session.scalar(
        select(FleetInspectionResultModel)
        .where(
            FleetInspectionResultModel.id == result_id,
            FleetInspectionResultModel.vehicle_id == vehicle.id,
        )
        .with_for_update()
    )
    if result is None:
        raise NotFoundError("Resultado no encontrado.", code="inspection_result_not_found")
    if result.passed:
        raise ConflictError("Ese punto no tuvo falla.", code="inspection_result_passed")
    if result.resolved_at is not None:
        raise ConflictError("La falla ya está resuelta.", code="inspection_already_resolved")
    async with session.begin_nested():
        result.resolved_at = datetime.now(UTC)
        result.resolved_by = current.id
        result.resolution = body.reason.strip()
        # La misma falla vista en otras inspecciones es una sola: se resuelve de una vez.
        repeated = await session.scalars(
            select(FleetInspectionResultModel).where(
                FleetInspectionResultModel.vehicle_id == vehicle.id,
                FleetInspectionResultModel.item_id == result.item_id,
                FleetInspectionResultModel.passed.is_(False),
                FleetInspectionResultModel.resolved_at.is_(None),
                FleetInspectionResultModel.id != result.id,
            )
        )
        for other in repeated:
            other.resolved_at = result.resolved_at
            other.resolved_by = result.resolved_by
            other.resolution = result.resolution
        await session.flush()
        await audit.record(
            action="RESOLVE_INSPECTION_FAILURE",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={"result_id": str(result.id), "item": result.item_name},
            metadata={"resolution": result.resolution},
            required=True,
        )
    return _result_out(result, current.username)

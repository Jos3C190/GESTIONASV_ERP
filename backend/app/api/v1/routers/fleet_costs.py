"""What the fleet costs: other costs per vehicle, and the report across fuel and service."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import get_fleet_scope
from app.api.v1.routers.fleet import active_supplier, scoped_vehicle
from app.api.v1.routers.fleet_operations import require_vehicle_document
from app.api.v1.schemas.fleet import (
    CostReportOut,
    FleetCostIn,
    FleetCostOut,
    FleetSupplierOut,
    VoidRecordIn,
)
from app.application.audit.audit_service import AuditService
from app.application.fleet.costs import (
    business_today,
    period_bounds,
    period_distance,
    report_rows,
    report_totals,
)
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.models.fleet import (
    FleetCostModel,
    FleetVehicleModel,
    FuelLogModel,
    MaintenanceOrderModel,
    OdometerReadingModel,
)
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-costs"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_READ = [Depends(require_permission("fleet:read"))]
_WRITE = [Depends(require_permission("fleet:costs"))]


@router.get("/suppliers", response_model=list[FleetSupplierOut], dependencies=_READ)
async def supplier_options(request: Request, session: SessionDep) -> list[FleetSupplierOut]:
    """Names to choose from in Fleet forms, without needing access to Purchasing."""
    company_id = effective_company_id(request)
    rows = await session.execute(
        select(SupplierModel.id_supplier, SupplierModel.code, SupplierModel.name)
        .where(SupplierModel.company_id == company_id, SupplierModel.is_active.is_(True))
        .order_by(SupplierModel.name)
    )
    return [FleetSupplierOut(id=row[0], code=row[1], name=row[2]) for row in rows.all()]


async def _vehicle(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    vehicle_id: uuid.UUID,
) -> tuple[uuid.UUID, FleetVehicleModel]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    vehicle = await scoped_vehicle(FleetRepository(session), scope, vehicle_id)
    return company_id, vehicle


async def _cost_rows(
    session: SessionDep, vehicle_id: uuid.UUID, cost_id: uuid.UUID | None = None
) -> list[FleetCostOut]:
    voider = aliased(User)
    statement = (
        select(FleetCostModel, SupplierModel.name, User.username, voider.username)
        .outerjoin(
            SupplierModel,
            (SupplierModel.company_id == FleetCostModel.company_id)
            & (SupplierModel.id_supplier == FleetCostModel.supplier_id),
        )
        .outerjoin(User, User.id == FleetCostModel.recorded_by)
        .outerjoin(voider, voider.id == FleetCostModel.voided_by)
        .where(FleetCostModel.vehicle_id == vehicle_id)
        .execution_options(include_deleted=True)
        .order_by(FleetCostModel.incurred_on.desc(), FleetCostModel.created_at.desc())
        .limit(200)
    )
    if cost_id is not None:
        statement = statement.where(FleetCostModel.id == cost_id)
    rows = await session.execute(statement)
    return [
        FleetCostOut(
            id=cost.id,
            category=cost.category,
            incurred_on=cost.incurred_on,
            amount=cost.amount,
            description=cost.description,
            supplier_id=cost.supplier_id,
            supplier_name=supplier_name,
            document_id=cost.document_id,
            recorded_by_name=recorded_by,
            voided_at=cost.voided_at,
            voided_by_name=voided_by,
            void_reason=cost.void_reason,
        )
        for cost, supplier_name, recorded_by, voided_by in rows.all()
    ]


@router.get(
    "/vehicles/{vehicle_id}/costs",
    response_model=list[FleetCostOut],
    dependencies=_READ,
)
async def list_costs(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[FleetCostOut]:
    _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    return await _cost_rows(session, vehicle.id)


# Una baja no borra lo que falta por pagar: un impuesto puede llegar después.
@router.post(
    "/vehicles/{vehicle_id}/costs",
    response_model=FleetCostOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_WRITE,
)
async def add_cost(
    vehicle_id: uuid.UUID,
    body: FleetCostIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetCostOut:
    company_id, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    if body.incurred_on > business_today():
        raise ValidationError("La fecha del costo no puede ser futura.", code="cost_future_date")
    if body.supplier_id is not None:
        await active_supplier(session, company_id, body.supplier_id)
    await require_vehicle_document(session, vehicle, body.document_id)
    async with session.begin_nested():
        cost = FleetCostModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            category=body.category,
            incurred_on=body.incurred_on,
            amount=body.amount,
            description=(body.description or "").strip() or None,
            supplier_id=body.supplier_id,
            document_id=body.document_id,
            recorded_by=current.id,
        )
        session.add(cost)
        await session.flush()
        await audit.record(
            action="FLEET_COST",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={
                "cost_id": str(cost.id),
                "category": cost.category,
                "amount": str(cost.amount),
                "incurred_on": str(cost.incurred_on),
            },
            required=True,
        )
    return (await _cost_rows(session, vehicle.id, cost.id))[0]


@router.post(
    "/vehicles/{vehicle_id}/costs/{cost_id}/void",
    response_model=FleetCostOut,
    dependencies=_WRITE,
)
async def void_cost(
    vehicle_id: uuid.UUID,
    cost_id: uuid.UUID,
    body: VoidRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetCostOut:
    company_id, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    cost = await session.scalar(
        select(FleetCostModel)
        .where(FleetCostModel.id == cost_id, FleetCostModel.vehicle_id == vehicle.id)
        .with_for_update()
    )
    if cost is None:
        raise NotFoundError("Costo no encontrado.", code="fleet_cost_not_found")
    if cost.voided_at is not None:
        raise ConflictError("El costo ya está anulado.", code="record_already_voided")
    async with session.begin_nested():
        cost.voided_at = datetime.now(UTC)
        cost.voided_by = current.id
        cost.void_reason = body.reason.strip()
        await session.flush()
        await audit.record(
            action="VOID_FLEET_COST",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"cost_id": str(cost.id), "amount": str(cost.amount)},
            metadata={"reason": cost.void_reason},
            required=True,
        )
    return (await _cost_rows(session, vehicle.id, cost.id))[0]


async def _distances(
    session: SessionDep, vehicle_ids: list[uuid.UUID], start: datetime, end: datetime
) -> dict[uuid.UUID, Decimal]:
    """Each vehicle's distance, measured from its last reading before the period."""
    valid = (
        OdometerReadingModel.vehicle_id.in_(vehicle_ids),
        OdometerReadingModel.voided_at.is_(None),
    )
    previous = (
        select(
            OdometerReadingModel.vehicle_id.label("vehicle_id"),
            func.max(OdometerReadingModel.read_at).label("read_at"),
        )
        .where(*valid, OdometerReadingModel.read_at < start)
        .group_by(OdometerReadingModel.vehicle_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            OdometerReadingModel.vehicle_id,
            OdometerReadingModel.reading_km,
            OdometerReadingModel.source,
        )
        .outerjoin(previous, previous.c.vehicle_id == OdometerReadingModel.vehicle_id)
        .where(
            *valid,
            OdometerReadingModel.read_at < end,
            OdometerReadingModel.read_at >= func.coalesce(previous.c.read_at, start),
        )
        .order_by(OdometerReadingModel.read_at, OdometerReadingModel.created_at)
    )
    readings: dict[uuid.UUID, list[tuple[Decimal, str]]] = defaultdict(list)
    for vehicle_id, reading, source in rows.all():
        readings[vehicle_id].append((Decimal(reading), source))
    return {vehicle_id: period_distance(items) for vehicle_id, items in readings.items()}


@router.get("/cost-report", response_model=CostReportOut, dependencies=_READ)
async def cost_report(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    date_from: date = Query(...),
    date_to: date = Query(...),
    branch_id: uuid.UUID | None = Query(None),
    vehicle_id: uuid.UUID | None = Query(None),
) -> CostReportOut:
    if date_from > date_to:
        raise ValidationError(
            "La fecha inicial no puede ser posterior a la final.", code="cost_report_range"
        )
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    repo = FleetRepository(session)
    if vehicle_id is not None:
        vehicles = [await scoped_vehicle(repo, scope, vehicle_id)]
    else:
        vehicles = await repo.all_vehicles(
            company_id, scope.list_filter(branch_id), include_retired=True
        )
    ids = [vehicle.id for vehicle in vehicles]
    start, end = period_bounds(date_from, date_to)

    async def _amounts(statement: Any) -> dict[uuid.UUID, Decimal]:
        return {row[0]: Decimal(row[1] or 0) for row in (await session.execute(statement)).all()}

    fuel = await _amounts(
        select(FuelLogModel.vehicle_id, func.sum(FuelLogModel.total_amount))
        .where(
            FuelLogModel.vehicle_id.in_(ids),
            FuelLogModel.voided_at.is_(None),
            FuelLogModel.filled_at >= start,
            FuelLogModel.filled_at < end,
        )
        .group_by(FuelLogModel.vehicle_id)
    )
    maintenance = await _amounts(
        select(MaintenanceOrderModel.vehicle_id, func.sum(MaintenanceOrderModel.cost))
        .where(
            MaintenanceOrderModel.vehicle_id.in_(ids),
            MaintenanceOrderModel.status == "completed",
            MaintenanceOrderModel.completed_at >= start,
            MaintenanceOrderModel.completed_at < end,
        )
        .group_by(MaintenanceOrderModel.vehicle_id)
    )
    other_filter = (
        FleetCostModel.vehicle_id.in_(ids),
        FleetCostModel.voided_at.is_(None),
        FleetCostModel.incurred_on >= date_from,
        FleetCostModel.incurred_on <= date_to,
    )
    other = await _amounts(
        select(FleetCostModel.vehicle_id, func.sum(FleetCostModel.amount))
        .where(*other_filter)
        .group_by(FleetCostModel.vehicle_id)
    )
    categories = await session.execute(
        select(FleetCostModel.category, func.sum(FleetCostModel.amount))
        .where(*other_filter)
        .group_by(FleetCostModel.category)
    )
    branches = await repo.branch_names(company_id, [vehicle.branch_id for vehicle in vehicles])
    types = {item.code: item for item in await repo.vehicle_types(company_id)}
    rows = report_rows(
        [
            {
                "vehicle_id": vehicle.id,
                "code": vehicle.code,
                "plate": vehicle.plate,
                "kind_name": types[vehicle.kind].name,
                "branch_name": branches.get(vehicle.branch_id, ""),
                "meter_unit": types[vehicle.kind].meter_unit,
                "retired": vehicle.status == "retired",
            }
            for vehicle in vehicles
        ],
        fuel=fuel,
        maintenance=maintenance,
        other=other,
        distance=await _distances(session, ids, start, end),
    )
    return CostReportOut.model_validate(
        {
            "date_from": date_from,
            "date_to": date_to,
            "rows": rows,
            "totals": report_totals(rows),
            "other_by_category": {row[0]: row[1] for row in categories.all()},
        }
    )

"""Accidents, thefts, fines and damage: what happened to a vehicle and how it ended."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
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
from app.api.v1.routers.drivers import scoped_driver
from app.api.v1.routers.fleet import scoped_vehicle, set_inventory_status
from app.api.v1.routers.fleet_operations import require_vehicle_document
from app.api.v1.schemas.fleet import FleetIncidentIn, FleetIncidentOut, FleetIncidentUpdate
from app.application.audit.audit_service import AuditService
from app.application.fleet.operations import in_future
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import DriverModel, FleetIncidentModel, FleetVehicleModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/fleet", tags=["fleet-incidents"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_WRITE = [Depends(require_permission("fleet:incidents"))]


async def _on_road(repo: FleetRepository, vehicle: FleetVehicleModel) -> bool:
    if vehicle.inventory_vehicle_id is None:
        return False
    return bool(await repo.active_transfers(vehicle.company_id, [vehicle.inventory_vehicle_id]))


async def _rows(session: SessionDep, *conditions: object) -> list[FleetIncidentOut]:
    closer = aliased(User)
    rows = await session.execute(
        select(
            FleetIncidentModel,
            FleetVehicleModel.code,
            Employee.first_name,
            Employee.last_name,
            User.username,
            closer.username,
        )
        .join(FleetVehicleModel, FleetVehicleModel.id == FleetIncidentModel.vehicle_id)
        .outerjoin(DriverModel, DriverModel.id == FleetIncidentModel.driver_id)
        .outerjoin(Employee, Employee.id == DriverModel.employee_id)
        .outerjoin(User, User.id == FleetIncidentModel.reported_by)
        .outerjoin(closer, closer.id == FleetIncidentModel.closed_by)
        .where(*conditions)  # type: ignore[arg-type]
        .execution_options(include_deleted=True)
        .order_by(FleetIncidentModel.occurred_at.desc())
        .limit(200)
    )
    return [
        FleetIncidentOut(
            id=incident.id,
            vehicle_id=incident.vehicle_id,
            vehicle_code=code,
            driver_id=incident.driver_id,
            driver_name=f"{first} {last}".strip() if first else None,
            kind=incident.kind,
            severity=incident.severity,
            responsible=incident.responsible,
            status=incident.status,
            occurred_at=incident.occurred_at,
            location=incident.location,
            description=incident.description,
            cost=incident.cost,
            insurance_claim=incident.insurance_claim,
            document_id=incident.document_id,
            resolution=incident.resolution,
            reported_by_name=reported_by,
            closed_at=incident.closed_at,
            closed_by_name=closed_by,
        )
        for incident, code, first, last, reported_by, closed_by in rows.all()
    ]


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
    return company_id, repo, await scoped_vehicle(repo, scope, vehicle_id, lock=lock)


@router.get(
    "/vehicles/{vehicle_id}/incidents",
    response_model=list[FleetIncidentOut],
    dependencies=[Depends(require_permission("fleet:read"))],
)
async def vehicle_incidents(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[FleetIncidentOut]:
    _, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    return await _rows(session, FleetIncidentModel.vehicle_id == vehicle.id)


@router.get(
    "/drivers/{driver_id}/incidents",
    response_model=list[FleetIncidentOut],
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def driver_incidents(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
) -> list[FleetIncidentOut]:
    company_id = effective_company_id(request)
    scope = await get_fleet_scope(session, current, checker, company_id)
    driver = await scoped_driver(FleetRepository(session), scope, driver_id)
    return await _rows(session, FleetIncidentModel.driver_id == driver.id)


# Un vehículo dado de baja aún puede recibir la multa o el reclamo que llegan después.
@router.post(
    "/vehicles/{vehicle_id}/incidents",
    response_model=FleetIncidentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_WRITE,
)
async def add_incident(
    vehicle_id: uuid.UUID,
    body: FleetIncidentIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetIncidentOut:
    company_id, repo, vehicle = await _vehicle(
        request, session, current, checker, vehicle_id, lock=True
    )
    if in_future(body.occurred_at, datetime.now(UTC)):
        raise ValidationError("La fecha del incidente no puede ser futura.", code="incident_future")
    if (
        body.driver_id is not None
        and await repo.driver_with_employee(company_id, body.driver_id) is None
    ):
        raise ValidationError("El conductor no existe.", code="incident_driver_invalid")
    await require_vehicle_document(session, vehicle, body.document_id)
    # Un robo en ruta es justo lo que hay que registrar: el incidente se guarda siempre, y
    # el vehículo solo se detiene si no está en un traslado.
    stop = (
        body.take_out_of_service
        and vehicle.status == "active"
        and not await _on_road(repo, vehicle)
    )
    async with session.begin_nested():
        incident = FleetIncidentModel(
            company_id=company_id,
            vehicle_id=vehicle.id,
            driver_id=body.driver_id,
            kind=body.kind,
            severity=body.severity,
            responsible=body.responsible,
            occurred_at=body.occurred_at,
            location=(body.location or "").strip() or None,
            description=body.description.strip(),
            cost=body.cost,
            insurance_claim=(body.insurance_claim or "").strip() or None,
            document_id=body.document_id,
            reported_by=current.id,
        )
        session.add(incident)
        if stop:
            vehicle.status = "out_of_service"
            vehicle.updated_by = current.id
            await set_inventory_status(session, vehicle, "inactive")
        await session.flush()
        await audit.record(
            action="FLEET_INCIDENT",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            after_state={
                "incident_id": str(incident.id),
                "kind": incident.kind,
                "severity": incident.severity,
                "cost": str(incident.cost) if incident.cost is not None else None,
                "status": vehicle.status,
            },
            required=True,
        )
    saved = (await _rows(session, FleetIncidentModel.id == incident.id))[0]
    return saved.model_copy(update={"vehicle_taken_out": stop})


@router.patch(
    "/vehicles/{vehicle_id}/incidents/{incident_id}",
    response_model=FleetIncidentOut,
    dependencies=_WRITE,
)
async def update_incident(
    vehicle_id: uuid.UUID,
    incident_id: uuid.UUID,
    body: FleetIncidentUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    audit: Audit,
) -> FleetIncidentOut:
    company_id, _, vehicle = await _vehicle(request, session, current, checker, vehicle_id)
    incident = await session.scalar(
        select(FleetIncidentModel)
        .where(FleetIncidentModel.id == incident_id, FleetIncidentModel.vehicle_id == vehicle.id)
        .with_for_update()
    )
    if incident is None:
        raise NotFoundError("Incidente no encontrado.", code="fleet_incident_not_found")
    changes = body.model_dump(exclude_unset=True)
    status_changed = "status" in changes and changes["status"] != incident.status
    if (
        status_changed
        and changes["status"] == "closed"
        and not (changes.get("resolution") or "").strip()
    ):
        raise ValidationError(
            "Indique cómo se resolvió el incidente.", code="incident_resolution_required"
        )
    await require_vehicle_document(session, vehicle, changes.get("document_id"))
    before = {
        "status": incident.status,
        "cost": str(incident.cost) if incident.cost is not None else None,
        "responsible": incident.responsible,
        "insurance_claim": incident.insurance_claim,
    }
    async with session.begin_nested():
        for field, value in changes.items():
            setattr(incident, field, value.strip() if isinstance(value, str) else value)
        if incident.insurance_claim == "":
            incident.insurance_claim = None
        # Corregir un costo de un incidente cerrado no cambia quién lo cerró ni cuándo.
        if status_changed:
            closing = incident.status == "closed"
            incident.closed_at = datetime.now(UTC) if closing else None
            incident.closed_by = current.id if closing else None
            if not closing:
                incident.resolution = None
        await session.flush()
        await audit.record(
            action="UPDATE_FLEET_INCIDENT",
            user_id=current.id,
            company_id=company_id,
            branch_id=vehicle.branch_id,
            resource_type="fleet_vehicles",
            resource_id=str(vehicle.id),
            before_state={"incident_id": str(incident.id), **before},
            after_state={
                "status": incident.status,
                "cost": str(incident.cost) if incident.cost is not None else None,
                "responsible": incident.responsible,
                "insurance_claim": incident.insurance_claim,
            },
            required=True,
        )
    return (await _rows(session, FleetIncidentModel.id == incident.id))[0]

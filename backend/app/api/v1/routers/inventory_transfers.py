"""Auditable, company-scoped transfer document commands and demand queries."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from decimal import Decimal
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
    assigned_warehouse_ids,
    authorize_warehouse_assignment,
    effective_company_id,
    get_branch_context,
    require_company_access,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.fleet_scope import get_fleet_scope
from app.api.v1.routers.inventory import InventoryBoundaryError
from app.api.v1.routers.inventory_adjustments import _persist as persist_adjustment
from app.api.v1.routers.inventory_adjustments import _redact_adjustment_costs
from app.api.v1.schemas.inventory_adjustment import InventoryAdjustmentOut
from app.api.v1.schemas.inventory_transfer import (
    AssignmentCheckIn,
    AssignmentCheckOut,
    AssignmentOptionsOut,
    DispatchCheckIn,
    DispatchCheckOut,
    DispatchDriverOptionOut,
    DispatchIssueOut,
    DispatchOptionsOut,
    DispatchVehicleOptionOut,
    InventoryTransferOut,
    InventoryVehicleOut,
    PendingApprovalCountOut,
    PlanningConflictOut,
    TransferApproveIn,
    TransferCloseReceptionIn,
    TransferCommandIn,
    TransferCreateIn,
    TransferDemandOut,
    TransferDiscrepancyAdjustmentIn,
    TransferDiscrepancyClaimIn,
    TransferDiscrepancyNotesIn,
    TransferDiscrepancyReleaseIn,
    TransferDispatchIn,
    TransferIncidentIn,
    TransferIncidentResolveIn,
    TransferPolicyIn,
    TransferPolicyOut,
    TransferReceiveIn,
    TransferRejectIn,
    TransferRouteOptionsOut,
    TransferUpdateIn,
)
from app.api.v1.transfer_tracking import archive_trip_on_commit
from app.application.audit.audit_service import AuditService
from app.application.fleet.compliance import Issue
from app.application.fleet.costs import business_today
from app.application.fleet.dispatch import HARD_BLOCKS as DISPATCH_HARD_BLOCKS
from app.application.fleet.dispatch import DispatchEvaluation, evaluate_dispatch
from app.application.fleet.driver_views import build_driver_views
from app.application.fleet.views import build_vehicle_views
from app.application.inventory import InventoryApplicationError
from app.application.inventory_adjustments import InventoryAdjustmentUseCases
from app.application.inventory_transfers.settings import policy_from
from app.application.inventory_transfers.use_cases import InventoryTransferUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.domain.entities.inventory_transfer import (
    TRIP_FINISHED_STATUSES,
    TransferDomainError,
    TransferRoute,
    TransferStatus,
)
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferDiscrepancyModel,
    InventoryTransferModel,
    InventoryTransferSettingsModel,
)
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.repositories.fleet_repository import FleetRepository
from app.infrastructure.repositories.inventory_adjustment_repository import (
    SqlAlchemyInventoryAdjustmentRepository,
)
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)

router = APIRouter(prefix="/inventory/transfers", tags=["inventory transfers"])
T = TypeVar("T", bound=BaseModel)
DISPATCH_OVERRIDE_PERMISSION = "fleet:compliance_override"
APPROVE_PERMISSION = "inventory:transfer_approve"
#: A transfer in these states has finished its trip (or never started it).
CLOSED_TRANSFER_STATUSES = (*TRIP_FINISHED_STATUSES, TransferStatus.CANCELLED)


def _use_cases(session: SessionDep) -> InventoryTransferUseCases:
    return InventoryTransferUseCases(SqlAlchemyInventoryTransferRepository(session))


async def _require_dynamic_permission(
    checker: CheckPermissionUseCase, current: CurrentUser, company_id: uuid.UUID, code: str
) -> None:
    decision = await checker.execute(current.id, company_id, code)
    if not decision.allowed:
        raise AuthorizationError(f"Permiso requerido: {code}", code="forbidden")


async def _authorize_origin_warehouse(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    warehouse_id: uuid.UUID,
) -> Warehouse:
    warehouse = await session.scalar(
        select(Warehouse).where(
            Warehouse.company_id == company_id,
            Warehouse.id == warehouse_id,
            Warehouse.deleted_at.is_(None),
        )
    )
    if warehouse is None:
        raise HTTPException(404, "Bodega de origen no encontrada.")
    if warehouse.is_transit or warehouse.branch_id is None:
        raise HTTPException(422, "El traslado debe salir de una bodega operativa.")
    await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse.id)
    return warehouse


def _domain_http_error(exc: TransferDomainError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}
    )


async def _approver_scope(
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> tuple[bool, list[uuid.UUID] | None]:
    """Whether the user can decide on transfers, and from which origin branches."""
    allowed = (await checker.execute(current.id, company_id, APPROVE_PERMISSION)).allowed
    if not allowed:
        return False, None
    context = await get_branch_context(session, current, company_id)
    return True, None if context.access_all_branches else [b.id for b in context.branches]


async def _policy_out(
    session: SessionDep, company_id: uuid.UUID, row: InventoryTransferSettingsModel | None
) -> TransferPolicyOut:
    policy = policy_from(row)
    counts = dict(
        (
            await session.execute(
                select(InventoryTransferModel.status, func.count(InventoryTransferModel.id))
                .where(
                    InventoryTransferModel.company_id == company_id,
                    InventoryTransferModel.status.in_(("pending_approval", "approved")),
                )
                .group_by(InventoryTransferModel.status)
            )
        )
        .tuples()
        .all()
    )
    return TransferPolicyOut(
        allow_branch_to_branch=policy.allow_branch_to_branch,
        allow_branch_to_central=policy.allow_branch_to_central,
        require_approval=policy.require_approval,
        updated_at=row.updated_at if row is not None else None,
        pending_count=counts.get("pending_approval", 0),
        approved_count=counts.get("approved", 0),
    )


async def _transfer_branch_scope(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    transfer_id: uuid.UUID,
    *,
    side: str = "either",
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    transfer = await session.scalar(
        select(InventoryTransferModel).where(
            InventoryTransferModel.company_id == company_id,
            InventoryTransferModel.id == transfer_id,
        )
    )
    if transfer is None:
        raise HTTPException(404, "Traslado no encontrado.")
    origin_branch_id = await session.scalar(
        select(Warehouse.branch_id).where(
            Warehouse.company_id == company_id,
            Warehouse.id == transfer.origin_warehouse_id,
        )
    )
    destination_branch_id = await session.scalar(
        select(Warehouse.branch_id).where(
            Warehouse.company_id == company_id,
            Warehouse.id == transfer.destination_warehouse_id,
        )
    )
    context = await get_branch_context(session, current, company_id)
    origin_access = bool(
        context.access_all_branches
        or (origin_branch_id is not None and context.can_access(origin_branch_id))
    )
    destination_access = bool(
        context.access_all_branches
        or (destination_branch_id is not None and context.can_access(destination_branch_id))
    )
    allowed = (
        origin_access
        if side == "origin"
        else destination_access
        if side == "destination"
        else origin_access or destination_access
    )
    if not allowed:
        raise HTTPException(403, "No tiene acceso al origen ni al destino de este traslado.")
    return origin_branch_id, destination_branch_id


async def _authorize_demand_branch(
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
) -> None:
    branch = await session.scalar(
        select(Branch).where(
            Branch.company_id == company_id,
            Branch.id == branch_id,
            Branch.is_active.is_(True),
            Branch.operational_status == "active",
            Branch.deleted_at.is_(None),
        )
    )
    if branch is None:
        raise HTTPException(404, "Sucursal de demanda no encontrada.")
    context = await get_branch_context(session, current, company_id)
    if context.access_all_branches or context.can_access(branch_id):
        return
    headquarters_id = await session.scalar(
        select(Branch.id).where(
            Branch.company_id == company_id,
            Branch.is_headquarters.is_(True),
            Branch.is_active.is_(True),
            Branch.operational_status == "active",
            Branch.deleted_at.is_(None),
        )
    )
    if headquarters_id is not None and context.can_access(headquarters_id):
        await _require_dynamic_permission(checker, current, company_id, "inventory:move")
        return
    raise HTTPException(403, "No tiene acceso a la demanda de esta sucursal.")


async def _persist_command(
    *,
    session: SessionDep,
    audit: AuditService,
    current: CurrentUser,
    request: Request,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    operation: Awaitable[dict[str, Any]],
    response_model: type[T],
) -> T:
    """Keep document, stock projection and required audit inside one savepoint."""
    try:
        async with session.begin_nested():
            result = await operation
            response = response_model.model_validate(result)
            if (
                isinstance(response, InventoryTransferOut)
                and response.status in CLOSED_TRANSFER_STATUSES
            ):
                # Al cerrarse el viaje se guarda su recorrido y se cierran sus alertas.
                archive_trip_on_commit(session, company_id, response.id)
            await audit.record(
                action=action,
                user_id=current.id,
                company_id=company_id,
                branch_id=branch_id,
                resource_type=resource_type,
                resource_id=resource_id or str(getattr(response, "id", None) or ""),
                after_state=jsonable_encoder(response),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                required=True,
            )
            return response
    except TransferDomainError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except (InventoryApplicationError, InventoryOperationError, InventoryAdjustmentError) as exc:
        raise InventoryBoundaryError(
            exc.message, code=exc.code, status_code=exc.status_code
        ) from exc
    except IntegrityError as exc:
        raise InventoryBoundaryError(
            "El inventario o la demanda cambiaron al mismo tiempo; recargue e intente de nuevo.",
            code="inventory_transfer_integrity_conflict",
            status_code=409,
        ) from exc


@router.get(
    "/demand",
    response_model=list[TransferDemandOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_transfer_demand(
    branch_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    product_id: int | None = Query(None, gt=0),
    search: str | None = Query(None, max_length=120),
    limit: int = Query(500, ge=1, le=1000),
) -> list[TransferDemandOut]:
    company_id = effective_company_id(request)
    await _authorize_demand_branch(session, current, checker, company_id, branch_id)
    rows = await _use_cases(session).list_demand(
        company_id=company_id,
        branch_id=branch_id,
        product_id=product_id,
        search=search,
        limit=limit,
    )
    return [TransferDemandOut.model_validate(row) for row in rows]


@router.get(
    "/vehicles",
    response_model=list[InventoryVehicleOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_vehicles(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
) -> list[InventoryVehicleOut]:
    """Transit vehicles of the branches the user operates.

    Vehicles are created and edited in Fleet; this catalogue is read-only.
    """
    company_id = effective_company_id(request)
    await require_company_access(session, current, company_id)
    scope = await get_fleet_scope(session, current, checker, company_id)
    branch_ids = None if scope.all_branches else list(scope.branch_ids)
    rows = await _use_cases(session).list_vehicles(company_id, branch_ids)
    return [InventoryVehicleOut.model_validate(row) for row in rows]


@router.get(
    "/settings",
    response_model=TransferPolicyOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_transfer_settings(request: Request, session: SessionDep) -> TransferPolicyOut:
    company_id = effective_company_id(request)
    row = await session.get(InventoryTransferSettingsModel, company_id)
    return await _policy_out(session, company_id, row)


@router.put(
    "/settings",
    response_model=TransferPolicyOut,
    dependencies=[Depends(require_permission("inventory:transfer_settings"))],
)
async def save_transfer_settings(
    body: TransferPolicyIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> TransferPolicyOut:
    company_id = effective_company_id(request)
    # La primera vez, dos guardados a la vez no deben chocar al crear la fila.
    await session.execute(
        insert(InventoryTransferSettingsModel)
        .values(company_id=company_id)
        .on_conflict_do_nothing()
    )
    row = await session.get(
        InventoryTransferSettingsModel, company_id, with_for_update=True, populate_existing=True
    )
    assert row is not None
    # What was saved is read after the lock, so a concurrent save is not reported as "before".
    before = policy_from(row)
    async with session.begin_nested():
        for field, value in body.model_dump().items():
            setattr(row, field, value)
        row.updated_by = current.id
        await session.flush()
        await audit.record(
            action="UPDATE_INVENTORY_TRANSFER_SETTINGS",
            user_id=current.id,
            company_id=company_id,
            resource_type="inventory_transfer_settings",
            resource_id=str(company_id),
            before_state={
                "allow_branch_to_branch": before.allow_branch_to_branch,
                "allow_branch_to_central": before.allow_branch_to_central,
                "require_approval": before.require_approval,
            },
            after_state=body.model_dump(),
            required=True,
        )
    return await _policy_out(session, company_id, row)


@router.get(
    "/route-options",
    response_model=TransferRouteOptionsOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def transfer_route_options(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    origin_warehouse_id: uuid.UUID | None = None,
) -> TransferRouteOptionsOut:
    """Warehouses the user may ship from and, for a chosen origin, where it can go."""
    company_id = effective_company_id(request)
    context = await get_branch_context(session, current, company_id)
    can_move = (await checker.execute(current.id, company_id, "inventory:move")).allowed
    try:
        options = await _use_cases(session).route_options(
            company_id=company_id,
            can_move=can_move,
            branch_ids=None
            if context.access_all_branches
            else [branch.id for branch in context.branches],
            warehouse_ids=await assigned_warehouse_ids(session, current, company_id),
            origin_warehouse_id=origin_warehouse_id,
        )
    except TransferDomainError as exc:
        raise _domain_http_error(exc) from exc
    return TransferRouteOptionsOut.model_validate(options)


@router.get(
    "/pending-approval-count",
    response_model=PendingApprovalCountOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def pending_approval_count(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
) -> PendingApprovalCountOut:
    company_id = effective_company_id(request)
    can_approve, branch_ids = await _approver_scope(session, current, checker, company_id)
    if not can_approve:
        return PendingApprovalCountOut(count=0)
    count = await _use_cases(session).pending_approval_count(
        company_id=company_id,
        actor_id=current.id,
        allow_self_approval=current.is_superuser,
        approver_branch_ids=branch_ids,
    )
    return PendingApprovalCountOut(count=count)


_CONFLICT_STATUS_LABELS = {"pending_approval": "en aprobación", "approved": "aprobado"}


async def _load_transfer(
    session: SessionDep, company_id: uuid.UUID, transfer_id: uuid.UUID
) -> InventoryTransferModel:
    transfer = await session.scalar(
        select(InventoryTransferModel).where(
            InventoryTransferModel.company_id == company_id,
            InventoryTransferModel.id == transfer_id,
        )
    )
    if transfer is None:
        raise HTTPException(404, "Traslado no encontrado.")
    return transfer


def _planning_issues_out(issues: list[Issue]) -> list[DispatchIssueOut]:
    # Nothing found while planning can be waived: it is either a warning or a hard stop.
    return [
        DispatchIssueOut(
            code=issue.code, severity=issue.severity, message=issue.message, overridable=False
        )
        for issue in issues
    ]


def _conflict_message(row: dict[str, Any]) -> str:
    subject = (
        "El vehículo y el conductor también están asignados"
        if row["same_vehicle"] and row["same_driver"]
        else "El vehículo también está asignado"
        if row["same_vehicle"]
        else "El conductor también está asignado"
    )
    return (
        f"{subject} a {row['code']} ({_CONFLICT_STATUS_LABELS.get(row['status'], row['status'])})."
    )


async def _planning_evaluation(
    session: SessionDep,
    company_id: uuid.UUID,
    *,
    origin_branch_id: uuid.UUID | None,
    inventory_vehicle_id: uuid.UUID,
    driver_id: uuid.UUID | None,
    transfer_id: uuid.UUID | None,
    lines: list[tuple[uuid.UUID, Decimal]] | None = None,
) -> tuple[DispatchEvaluation, list[PlanningConflictOut], tuple[Decimal, int] | None]:
    """Judge a transport chosen ahead of time: what only matters at departure is a warning."""
    if origin_branch_id is None:
        raise HTTPException(409, "La bodega de origen no pertenece a una sucursal.")
    repo = FleetRepository(session)
    load: tuple[Decimal, int] | None = None
    if lines:
        load = await repo.load_for_units(company_id, lines)
    elif transfer_id is not None:
        load = await repo.transfer_load(company_id, transfer_id)
    vehicle = await session.scalar(
        select(FleetVehicleModel).where(
            FleetVehicleModel.company_id == company_id,
            FleetVehicleModel.inventory_vehicle_id == inventory_vehicle_id,
        )
    )
    if vehicle is None:
        evaluation = DispatchEvaluation(
            vehicle_id=inventory_vehicle_id, driver_id=driver_id, stage="planning"
        )
        evaluation.vehicle_issues.append(
            Issue(
                "transfer_vehicle_not_in_fleet",
                "blocking",
                "El vehículo no está registrado en Flota.",
            )
        )
    else:
        evaluation = await evaluate_dispatch(
            repo,
            company_id,
            origin_branch_id=origin_branch_id,
            vehicle=vehicle,
            driver_id=driver_id,
            transfer_id=transfer_id,
            today=business_today(),
            stage="planning",
            load=load,
        )
    if driver_id is None:
        # While planning, the driver is chosen, never inferred from Fleet.
        evaluation.driver_id = None
        evaluation.driver_issues = [
            Issue("driver_required", "blocking", "Elige un conductor para el traslado.")
        ]
    conflicts = [
        PlanningConflictOut(
            transfer_id=row["transfer_id"],
            code=row["code"],
            status=row["status"],
            same_vehicle=row["same_vehicle"],
            same_driver=row["same_driver"],
            message=_conflict_message(row),
        )
        for row in await repo.planned_transfers(
            company_id,
            inventory_vehicle_id=inventory_vehicle_id,
            driver_id=driver_id,
            exclude=transfer_id,
        )
    ]
    return evaluation, conflicts, load


def _assignment_check_out(
    evaluation: DispatchEvaluation,
    conflicts: list[PlanningConflictOut],
    load: tuple[Decimal, int] | None,
) -> AssignmentCheckOut:
    return AssignmentCheckOut(
        vehicle_id=evaluation.vehicle_id,
        driver_id=evaluation.driver_id,
        vehicle_issues=_planning_issues_out(evaluation.vehicle_issues),
        driver_issues=_planning_issues_out(evaluation.driver_issues),
        planning_blocked=evaluation.planning_blocked,
        warnings=sum(1 for issue in evaluation.issues if issue.severity == "warning"),
        conflicts=conflicts,
        load_kg=load[0] if load is not None else None,
        load_missing_weight=load[1] if load is not None else 0,
    )


async def _require_fit_transport(
    session: SessionDep,
    company_id: uuid.UUID,
    transfer: InventoryTransferModel,
    origin_branch_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Stop a transfer whose vehicle or driver cannot be planned; summarise what remains."""
    assert transfer.vehicle_id is not None
    evaluation, conflicts, _ = await _planning_evaluation(
        session,
        company_id,
        origin_branch_id=origin_branch_id,
        inventory_vehicle_id=transfer.vehicle_id,
        driver_id=transfer.driver_id,
        transfer_id=transfer.id,
    )
    if evaluation.planning_blocked:
        raise HTTPException(
            409,
            detail={
                "code": "transfer_assignment_unfit",
                "message": "El vehículo o el conductor no es apto para el traslado: "
                + evaluation.summary(),
            },
        )
    return {
        "vehicle_id": str(transfer.vehicle_id),
        "driver_id": str(transfer.driver_id) if transfer.driver_id else None,
        "warnings": [
            {"code": issue.code, "message": issue.message}
            for issue in evaluation.issues
            if issue.severity == "warning"
        ],
        "conflicts": [conflict.code for conflict in conflicts],
    }


@router.get(
    "/assignment-options",
    response_model=AssignmentOptionsOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def assignment_options(
    origin_warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    transfer_id: uuid.UUID | None = None,
) -> AssignmentOptionsOut:
    """Vehicles and drivers of the origin branch that can be chosen while preparing."""
    company_id = effective_company_id(request)
    origin = await _authorize_origin_warehouse(session, current, company_id, origin_warehouse_id)
    transfer: InventoryTransferModel | None = None
    if transfer_id is not None:
        await _transfer_branch_scope(session, current, company_id, transfer_id, side="origin")
        transfer = await _load_transfer(session, company_id, transfer_id)
    assert origin.branch_id is not None
    options = await _transport_options(
        session, company_id, origin.branch_id, transfer=transfer, planning=True
    )
    return AssignmentOptionsOut.model_validate(options.model_dump())


@router.post(
    "/assignment-check",
    response_model=AssignmentCheckOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def assignment_check(
    body: AssignmentCheckIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> AssignmentCheckOut:
    """Judge the vehicle and driver chosen for a draft, with the weight of its lines."""
    company_id = effective_company_id(request)
    origin = await _authorize_origin_warehouse(
        session, current, company_id, body.origin_warehouse_id
    )
    if body.transfer_id is not None:
        await _transfer_branch_scope(session, current, company_id, body.transfer_id, side="origin")
    requested_units = {line.handling_unit_id for line in body.lines}
    if requested_units:
        in_origin = set(
            await session.scalars(
                select(InventoryHandlingUnitModel.id).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.warehouse_id == origin.id,
                    InventoryHandlingUnitModel.id.in_(requested_units),
                )
            )
        )
        if in_origin != requested_units:
            raise HTTPException(
                422,
                detail={
                    "code": "transfer_assignment_units_invalid",
                    "message": "Alguna unidad logística de la carga no está en la bodega de origen.",
                },
            )
    evaluation, conflicts, load = await _planning_evaluation(
        session,
        company_id,
        origin_branch_id=origin.branch_id,
        inventory_vehicle_id=body.vehicle_id,
        driver_id=body.driver_id,
        transfer_id=body.transfer_id,
        lines=[(line.handling_unit_id, line.quantity_base) for line in body.lines],
    )
    return _assignment_check_out(evaluation, conflicts, load)


@router.get(
    "",
    response_model=list[InventoryTransferOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_transfers(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    branch_id: uuid.UUID | None = None,
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern=(
            "^(preparation|pending_approval|approved|in_transit|partially_received|"
            "discrepancy|received|closed_with_adjustment|incident|cancelled)$"
        ),
    ),
    route_type: str | None = Query(
        None, pattern="^(central_distribution|branch_to_branch|branch_to_central)$"
    ),
    side: str | None = Query(None, pattern="^(origin|destination)$"),
    awaiting_my_approval: bool = False,
    origin_count_pending: bool = False,
    with_open_discrepancies: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> list[InventoryTransferOut]:
    company_id = effective_company_id(request)
    context = await get_branch_context(session, current, company_id)
    if branch_id is not None:
        if not context.access_all_branches and not context.can_access(branch_id):
            raise HTTPException(403, "No tiene acceso a esta sucursal.")
        filters: dict[str, Any] = {"branch_id": branch_id}
    else:
        filters = {
            "branch_ids": None
            if context.access_all_branches
            else [branch.id for branch in context.branches]
        }
    if awaiting_my_approval:
        can_approve, approver_branch_ids = await _approver_scope(
            session, current, checker, company_id
        )
        if not can_approve:
            return []
        filters.update(
            awaiting_approval_by=current.id,
            allow_self_approval=current.is_superuser,
            approver_branch_ids=approver_branch_ids,
        )
    rows = await _use_cases(session).list_transfers(
        company_id=company_id,
        status_filter=status_filter,
        route_type=route_type,
        side=side,
        origin_count_pending=origin_count_pending,
        with_open_discrepancies=with_open_discrepancies,
        page=page,
        size=size,
        **filters,
    )
    return [InventoryTransferOut.model_validate(row) for row in rows]


@router.post(
    "",
    response_model=InventoryTransferOut,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def create_transfer(
    body: TransferCreateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    origin = await _authorize_origin_warehouse(
        session, current, company_id, body.origin_warehouse_id
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=origin.branch_id,
        action="CREATE_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=None,
        operation=_use_cases(session).create_transfer(
            company_id=company_id,
            origin_warehouse_id=body.origin_warehouse_id,
            destination_warehouse_id=body.destination_warehouse_id,
            vehicle_id=body.vehicle_id,
            driver_id=body.driver_id,
            notes=body.notes,
            lines=[line.model_dump() for line in body.lines],
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )


@router.get(
    "/{transfer_id}",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_transfer(
    transfer_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    await _transfer_branch_scope(session, current, company_id, transfer_id)
    row = await _use_cases(session).get_transfer(company_id, transfer_id)
    if row is None:
        raise HTTPException(404, "Traslado no encontrado.")
    return InventoryTransferOut.model_validate(row)


@router.put(
    "/{transfer_id}",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def update_transfer(
    transfer_id: uuid.UUID,
    body: TransferUpdateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    origin_branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    current_origin_id = await session.scalar(
        select(InventoryTransferModel.origin_warehouse_id).where(
            InventoryTransferModel.company_id == company_id,
            InventoryTransferModel.id == transfer_id,
        )
    )
    if body.origin_warehouse_id != current_origin_id:
        # Moving the transfer to another origin is the same act as creating one from it.
        await _authorize_origin_warehouse(session, current, company_id, body.origin_warehouse_id)
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=origin_branch_id,
        action="UPDATE_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).update_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            origin_warehouse_id=body.origin_warehouse_id,
            destination_warehouse_id=body.destination_warehouse_id,
            vehicle_id=body.vehicle_id,
            driver_id=body.driver_id,
            notes=body.notes,
            lines=[line.model_dump() for line in body.lines],
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/cancel",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def cancel_transfer(
    transfer_id: uuid.UUID,
    body: TransferCommandIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="CANCEL_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).cancel_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/submit",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def submit_transfer(
    transfer_id: uuid.UUID,
    body: TransferCommandIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    transfer = await _load_transfer(session, company_id, transfer_id)
    review: dict[str, Any] | None = None
    if (
        transfer.status == TransferStatus.PREPARATION
        # Central distribution is never sent for approval; the domain says so.
        and transfer.route_type != TransferRoute.CENTRAL_DISTRIBUTION
        and transfer.vehicle_id is not None
        and transfer.driver_id is not None
    ):
        # The domain reports the missing transport itself; here it is judged.
        review = await _require_fit_transport(session, company_id, transfer, branch_id)
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="SUBMIT_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).submit_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            expected_vehicle_id=transfer.vehicle_id,
            expected_driver_id=transfer.driver_id,
            assignment_review=review,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/withdraw",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def withdraw_transfer(
    transfer_id: uuid.UUID,
    body: TransferCommandIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="WITHDRAW_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).withdraw_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/approve",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission(APPROVE_PERMISSION))],
)
async def approve_transfer(
    transfer_id: uuid.UUID,
    body: TransferApproveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    transfer = await _load_transfer(session, company_id, transfer_id)
    if (
        transfer.status == TransferStatus.PENDING_APPROVAL
        and transfer.vehicle_id is not None
        and transfer.driver_id is not None
    ):
        await _require_fit_transport(session, company_id, transfer, branch_id)
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="APPROVE_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).approve_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            expected_round=body.expected_round,
            allow_self_approval=current.is_superuser,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/reject",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission(APPROVE_PERMISSION))],
)
async def reject_transfer(
    transfer_id: uuid.UUID,
    body: TransferRejectIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="REJECT_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).reject_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            expected_round=body.expected_round,
            reason=body.reason,
            allow_self_approval=current.is_superuser,
        ),
        response_model=InventoryTransferOut,
    )


def _issues_out(issues: list[Issue]) -> list[DispatchIssueOut]:
    return [
        DispatchIssueOut(
            code=issue.code,
            severity=issue.severity,
            message=issue.message,
            overridable=issue.severity == "blocking" and issue.code not in DISPATCH_HARD_BLOCKS,
        )
        for issue in issues
    ]


async def _dispatch_subject(
    session: SessionDep,
    company_id: uuid.UUID,
    transfer_id: uuid.UUID,
    inventory_vehicle_id: uuid.UUID,
    lock: bool = False,
) -> FleetVehicleModel:
    statement = select(FleetVehicleModel).where(
        FleetVehicleModel.company_id == company_id,
        FleetVehicleModel.inventory_vehicle_id == inventory_vehicle_id,
    )
    # Al despachar de verdad, un préstamo o un segundo despacho deben esperar su turno.
    vehicle = await session.scalar(statement.with_for_update() if lock else statement)
    if vehicle is None:
        raise HTTPException(
            422,
            detail={
                "code": "transfer_vehicle_not_in_fleet",
                "message": "El vehículo no está registrado en Flota.",
            },
        )
    return vehicle


async def _lock_driver(
    session: SessionDep, vehicle: FleetVehicleModel, driver_id: uuid.UUID | None
) -> None:
    repo = FleetRepository(session)
    if driver_id is None:
        assignment = await repo.open_assignment_for_vehicle(vehicle.id)
        driver_id = assignment.driver_id if assignment is not None else None
    if driver_id is not None:
        await repo.get_driver(vehicle.company_id, driver_id, lock=True)


async def _evaluate(
    session: SessionDep,
    company_id: uuid.UUID,
    transfer_id: uuid.UUID,
    origin_branch_id: uuid.UUID | None,
    inventory_vehicle_id: uuid.UUID,
    driver_id: uuid.UUID | None,
    *,
    lock: bool = False,
) -> DispatchEvaluation:
    if origin_branch_id is None:
        raise HTTPException(409, "La bodega de origen no pertenece a una sucursal.")
    vehicle = await _dispatch_subject(session, company_id, transfer_id, inventory_vehicle_id, lock)
    if lock:
        await _lock_driver(session, vehicle, driver_id)
    return await evaluate_dispatch(
        FleetRepository(session),
        company_id,
        origin_branch_id=origin_branch_id,
        vehicle=vehicle,
        driver_id=driver_id,
        transfer_id=transfer_id,
        today=business_today(),
    )


async def _can_override(
    checker: CheckPermissionUseCase, current: CurrentUser, company_id: uuid.UUID
) -> bool:
    return bool(
        current.is_superuser
        or (await checker.execute(current.id, company_id, DISPATCH_OVERRIDE_PERMISSION)).allowed
    )


async def _transport_options(
    session: SessionDep,
    company_id: uuid.UUID,
    origin_branch_id: uuid.UUID,
    *,
    transfer: InventoryTransferModel | None,
    planning: bool,
) -> DispatchOptionsOut:
    """Fleet vehicles and drivers of the origin branch, as seen while planning or dispatching."""
    repo = FleetRepository(session)
    today = business_today()
    vehicles = [
        vehicle
        for vehicle in await repo.dispatchable_vehicles(company_id, origin_branch_id)
        if vehicle.inventory_vehicle_id is not None
    ]
    vehicle_views = await build_vehicle_views(repo, company_id, vehicles, today=today)
    rows, _ = await repo.list_drivers(
        company_id, [origin_branch_id], status="active", search=None, page=1, size=10_000
    )
    driver_views = await build_driver_views(repo, company_id, rows, today=today)
    branch_name = (await repo.branch_names(company_id, [origin_branch_id])).get(
        origin_branch_id, ""
    )
    transfer_id = transfer.id if transfer is not None else None

    def busy(view: dict[str, object]) -> str | None:
        if view["maintenance_in_progress"]:
            return "En el taller"
        trip = view["current_transfer"]
        if isinstance(trip, dict) and trip["id"] != transfer_id:
            return f"En ruta ({trip['code']})"
        return None

    def unavailable(view: dict[str, object]) -> str | None:
        if view["status"] != "active":
            return "En mantenimiento" if view["status"] == "maintenance" else "Fuera de servicio"
        # While planning, being busy now is only a note: the departure may be hours away.
        return None if planning else busy(view)

    return DispatchOptionsOut(
        origin_branch_id=origin_branch_id,
        origin_branch_name=branch_name,
        planned_vehicle_id=transfer.vehicle_id if transfer is not None else None,
        planned_driver_id=transfer.driver_id if transfer is not None else None,
        approved_vehicle_id=transfer.approved_vehicle_id if transfer is not None else None,
        approved_driver_id=transfer.approved_driver_id if transfer is not None else None,
        vehicles=[
            DispatchVehicleOptionOut(
                inventory_vehicle_id=view["inventory_vehicle_id"],
                fleet_vehicle_id=view["id"],
                code=view["code"],
                plate=view["plate"],
                kind=view["kind"],
                brand=view["brand"],
                model=view["model"],
                compliance_state=view["compliance"]["state"],
                available=unavailable(view) is None,
                unavailable_reason=unavailable(view),
                note=busy(view) if planning else None,
                driver_id=view["driver"]["driver_id"] if view["driver"] else None,
                driver_name=view["driver"]["name"] if view["driver"] else None,
            )
            for view in vehicle_views
        ],
        drivers=[
            DispatchDriverOptionOut(
                id=view["id"],
                name=view["employee"]["name"],
                license_class=view["license"]["license_class"],
                compliance_state=view["compliance"]["state"],
                current_vehicle_code=view["vehicle"]["code"] if view["vehicle"] else None,
            )
            for view in driver_views
        ],
    )


@router.get(
    "/{transfer_id}/dispatch-options",
    response_model=DispatchOptionsOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def dispatch_options(
    transfer_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> DispatchOptionsOut:
    """Fleet vehicles and drivers of the origin branch that could take the transfer."""
    company_id = effective_company_id(request)
    origin_branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    if origin_branch_id is None:
        raise HTTPException(409, "La bodega de origen no pertenece a una sucursal.")
    transfer = await _load_transfer(session, company_id, transfer_id)
    return await _transport_options(
        session, company_id, origin_branch_id, transfer=transfer, planning=False
    )


@router.get(
    "/{transfer_id}/assignment-check",
    response_model=AssignmentCheckOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def transfer_assignment_check(
    transfer_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> AssignmentCheckOut:
    """What the approver needs: is the transport saved in the transfer fit to be planned?"""
    company_id = effective_company_id(request)
    origin_branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    transfer = await _load_transfer(session, company_id, transfer_id)
    if transfer.vehicle_id is None:
        return AssignmentCheckOut(
            vehicle_id=None,
            driver_id=transfer.driver_id,
            vehicle_issues=[
                DispatchIssueOut(
                    code="vehicle_required",
                    severity="blocking",
                    message="El traslado no tiene vehículo asignado.",
                    overridable=False,
                )
            ],
            driver_issues=[]
            if transfer.driver_id is not None
            else [
                DispatchIssueOut(
                    code="driver_required",
                    severity="blocking",
                    message="Elige un conductor para el traslado.",
                    overridable=False,
                )
            ],
            planning_blocked=True,
            warnings=0,
            conflicts=[],
        )
    evaluation, conflicts, load = await _planning_evaluation(
        session,
        company_id,
        origin_branch_id=origin_branch_id,
        inventory_vehicle_id=transfer.vehicle_id,
        driver_id=transfer.driver_id,
        transfer_id=transfer.id,
    )
    return _assignment_check_out(evaluation, conflicts, load)


@router.post(
    "/{transfer_id}/dispatch-check",
    response_model=DispatchCheckOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def dispatch_check(
    transfer_id: uuid.UUID,
    body: DispatchCheckIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
) -> DispatchCheckOut:
    """Preview the fitness gate the dispatch will apply to this vehicle and driver."""
    company_id = effective_company_id(request)
    origin_branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    transfer = await _load_transfer(session, company_id, transfer_id)
    # The same default as the dispatch: the one asked for, the one saved, the one in Fleet.
    requested_driver_id = body.driver_id if body.driver_id is not None else transfer.driver_id
    evaluation = await _evaluate(
        session, company_id, transfer_id, origin_branch_id, body.vehicle_id, requested_driver_id
    )
    return DispatchCheckOut(
        vehicle_id=body.vehicle_id,
        driver_id=evaluation.driver_id,
        vehicle_issues=_issues_out(evaluation.vehicle_issues),
        driver_issues=_issues_out(evaluation.driver_issues),
        blocked=bool(evaluation.blocking),
        hard_blocked=evaluation.hard_blocked,
        can_override=await _can_override(checker, current, company_id),
    )


@router.post(
    "/{transfer_id}/dispatch",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def dispatch_transfer(
    transfer_id: uuid.UUID,
    body: TransferDispatchIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    transfer = await _load_transfer(session, company_id, transfer_id)
    # The driver saved at preparation is the default, before the one assigned in Fleet.
    requested_driver_id = body.driver_id if body.driver_id is not None else transfer.driver_id
    evaluation = await _evaluate(
        session, company_id, transfer_id, branch_id, body.vehicle_id, requested_driver_id, lock=True
    )
    substitution = transfer.status == TransferStatus.APPROVED and (
        (
            transfer.approved_vehicle_id is not None
            and transfer.approved_vehicle_id != body.vehicle_id
        )
        or (
            transfer.approved_driver_id is not None
            and transfer.approved_driver_id != evaluation.driver_id
        )
    )
    override_reason: str | None = None
    if evaluation.blocking:
        if evaluation.hard_blocked:
            raise HTTPException(
                409, detail={"code": "transfer_dispatch_blocked", "message": evaluation.summary()}
            )
        if not await _can_override(checker, current, company_id):
            raise HTTPException(
                409,
                detail={
                    "code": "transfer_dispatch_blocked",
                    "message": evaluation.summary()
                    + " Solo un usuario autorizado para excepciones puede despacharlo.",
                },
            )
        if not body.override_reason or not body.override_reason.strip():
            raise HTTPException(
                409,
                detail={
                    "code": "transfer_override_reason_required",
                    "message": evaluation.summary()
                    + " Indique el motivo de la excepción para despachar.",
                },
            )
        override_reason = body.override_reason.strip()
    dispatched = await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action=(
            "DISPATCH_TRANSFER_OVERRIDE"
            if override_reason
            else "DISPATCH_TRANSFER_SUBSTITUTION"
            if substitution
            else "DISPATCH_TRANSFER"
        ),
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).dispatch_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            vehicle_id=body.vehicle_id,
            driver_id=evaluation.driver_id,
            compliance_override_reason=override_reason,
            # Whatever the client sent is part of the request; the repository decides if needed.
            substitution_code=body.substitution_code,
            substitution_reason=body.substitution_reason,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )
    if substitution and override_reason:
        # The exception is the audit action; the change of transport is recorded on its own.
        await audit.record(
            action="DISPATCH_TRANSFER_SUBSTITUTION",
            user_id=current.id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="inventory_transfers",
            resource_id=str(transfer_id),
            after_state=jsonable_encoder(dispatched.assignment_substitution),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            required=True,
        )
    return dispatched


@router.post(
    "/{transfer_id}/receive",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def receive_transfer(
    transfer_id: uuid.UUID,
    body: TransferReceiveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    _, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="destination"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:receive")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=destination_branch_id,
        action="RECEIVE_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).receive_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            lines=[line.model_dump() for line in body.lines],
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/incidents",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def open_transfer_incident(
    transfer_id: uuid.UUID,
    body: TransferIncidentIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    origin_branch_id, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id
    )
    context = await get_branch_context(session, current, company_id)
    destination_access = context.access_all_branches or (
        destination_branch_id is not None and context.can_access(destination_branch_id)
    )
    origin_access = context.access_all_branches or (
        origin_branch_id is not None and context.can_access(origin_branch_id)
    )
    receive_allowed = (
        destination_access
        and (await checker.execute(current.id, company_id, "inventory:receive")).allowed
    )
    move_allowed = (
        origin_access and (await checker.execute(current.id, company_id, "inventory:move")).allowed
    )
    if receive_allowed:
        branch_id = destination_branch_id
    elif move_allowed:
        branch_id = origin_branch_id
    else:
        raise AuthorizationError(
            "Se requiere acceso al lado autorizado del traslado y el permiso de recepción o movimiento.",
            code="forbidden",
        )
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="OPEN_TRANSFER_INCIDENT",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).open_incident(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            reason=body.reason,
            evidence_reference=body.evidence_reference,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/incidents/resolve",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def resolve_transfer_incident(
    transfer_id: uuid.UUID,
    body: TransferIncidentResolveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    company_id = effective_company_id(request)
    origin_branch_id, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id
    )
    context = await get_branch_context(session, current, company_id)
    destination_access = context.access_all_branches or (
        destination_branch_id is not None and context.can_access(destination_branch_id)
    )
    origin_access = context.access_all_branches or (
        origin_branch_id is not None and context.can_access(origin_branch_id)
    )
    receive_allowed = (
        destination_access
        and (await checker.execute(current.id, company_id, "inventory:receive")).allowed
    )
    move_allowed = (
        origin_access and (await checker.execute(current.id, company_id, "inventory:move")).allowed
    )
    if receive_allowed:
        branch_id = destination_branch_id
    elif move_allowed:
        branch_id = origin_branch_id
    else:
        raise AuthorizationError(
            "Se requiere acceso al lado autorizado del traslado y el permiso de recepción o movimiento.",
            code="forbidden",
        )
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="RESOLVE_TRANSFER_INCIDENT",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).resolve_incident(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            resolution=body.resolution,
            resolution_notes=body.resolution_notes,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/close-reception",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def close_transfer_reception(
    transfer_id: uuid.UUID,
    body: TransferCloseReceptionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    """Stop waiting for what has not arrived: it becomes a shortage to resolve."""
    company_id = effective_company_id(request)
    _, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="destination"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:receive")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=destination_branch_id,
        action="CLOSE_TRANSFER_RECEPTION",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).close_reception(
            company_id=company_id,
            transfer_id=transfer_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            reason=body.reason,
            evidence_reference=body.evidence_reference,
        ),
        response_model=InventoryTransferOut,
    )


async def _discrepancy_kind(
    session: SessionDep,
    company_id: uuid.UUID,
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
) -> str:
    kind: str | None = await session.scalar(
        select(InventoryTransferDiscrepancyModel.kind).where(
            InventoryTransferDiscrepancyModel.company_id == company_id,
            InventoryTransferDiscrepancyModel.transfer_id == transfer_id,
            InventoryTransferDiscrepancyModel.id == discrepancy_id,
        )
    )
    if kind is None:
        raise HTTPException(404, "Diferencia no encontrada.")
    return kind


@router.post(
    "/{transfer_id}/discrepancies/{discrepancy_id}/adjustment",
    response_model=InventoryAdjustmentOut,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def prepare_discrepancy_adjustment(
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
    body: TransferDiscrepancyAdjustmentIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryAdjustmentOut:
    """Prepare (as a draft) the adjustment that regularises a shortage, damage or surplus."""
    company_id = effective_company_id(request)
    # Access to the transfer comes first, so nobody learns what a transfer holds without it.
    await _transfer_branch_scope(session, current, company_id, transfer_id, side="either")
    kind = await _discrepancy_kind(session, company_id, transfer_id, discrepancy_id)
    if kind != "shortage":
        # A shortage concerns both ends of the trip; damage and surplus live at the destination.
        await _transfer_branch_scope(session, current, company_id, transfer_id, side="destination")
    await _require_dynamic_permission(checker, current, company_id, "inventory:adjust")
    response = await persist_adjustment(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        action="CREATE_DISCREPANCY_ADJUSTMENT",
        adjustment_id=None,
        operation=InventoryAdjustmentUseCases(
            SqlAlchemyInventoryAdjustmentRepository(session)
        ).create_for_discrepancy(
            company_id=company_id,
            actor_id=current.id,
            transfer_id=transfer_id,
            discrepancy_id=discrepancy_id,
            idempotency_key=body.idempotency_key,
            operational_date=body.operational_date,
            accounting_date=body.accounting_date,
            reason=body.reason,
            document_reference=body.document_reference,
            notes=body.notes,
            packaging_definition_id=body.packaging_definition_id,
            actual_gross_weight_kg=body.actual_gross_weight_kg,
            actual_volume_m3=body.actual_volume_m3,
            inventory_lot_detail_id=body.inventory_lot_detail_id,
            documented_unit_cost=body.documented_unit_cost,
            documented_total_cost=body.documented_total_cost,
        ),
        model=InventoryAdjustmentOut,
    )
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response


@router.post(
    "/{transfer_id}/discrepancies/{discrepancy_id}/claim",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def claim_transfer_discrepancy(
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
    body: TransferDiscrepancyClaimIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    """A damage handed to the carrier or insurer stops blocking the transfer."""
    company_id = effective_company_id(request)
    _, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="destination"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:adjust_approve")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=destination_branch_id,
        action="CLAIM_TRANSFER_DISCREPANCY",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).claim_discrepancy(
            company_id=company_id,
            transfer_id=transfer_id,
            discrepancy_id=discrepancy_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            claim_reference=body.claim_reference,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/discrepancies/{discrepancy_id}/release",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def release_transfer_damage(
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
    body: TransferDiscrepancyReleaseIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    """After inspection, the damaged goods go to quarantine."""
    company_id = effective_company_id(request)
    _, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="destination"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:adjust_approve")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=destination_branch_id,
        action="RELEASE_TRANSFER_DAMAGE",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).release_damage(
            company_id=company_id,
            transfer_id=transfer_id,
            discrepancy_id=discrepancy_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            notes=body.notes,
            destination_location_id=body.destination_location_id,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/discrepancies/{discrepancy_id}/found",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def mark_transfer_shortage_found(
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
    body: TransferDiscrepancyNotesIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    """The missing goods arrived after all: the reception goes back to waiting for them."""
    company_id = effective_company_id(request)
    _, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="destination"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:receive")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=destination_branch_id,
        action="MARK_TRANSFER_SHORTAGE_FOUND",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).mark_shortage_found(
            company_id=company_id,
            transfer_id=transfer_id,
            discrepancy_id=discrepancy_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            notes=body.notes,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/discrepancies/{discrepancy_id}/dismiss",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def dismiss_transfer_surplus(
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
    body: TransferDiscrepancyNotesIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    """The surplus was a counting mistake: nothing enters stock."""
    company_id = effective_company_id(request)
    _, destination_branch_id = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="destination"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:adjust_approve")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=destination_branch_id,
        action="DISMISS_TRANSFER_SURPLUS",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).dismiss_surplus(
            company_id=company_id,
            transfer_id=transfer_id,
            discrepancy_id=discrepancy_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            notes=body.notes,
        ),
        response_model=InventoryTransferOut,
    )


@router.post(
    "/{transfer_id}/discrepancies/{discrepancy_id}/origin-count",
    response_model=InventoryTransferOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def record_transfer_origin_count(
    transfer_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
    body: TransferDiscrepancyNotesIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryTransferOut:
    """The origin warehouse counted its stock after a shortage or a surplus."""
    company_id = effective_company_id(request)
    origin_branch_id, _ = await _transfer_branch_scope(
        session, current, company_id, transfer_id, side="origin"
    )
    await _require_dynamic_permission(checker, current, company_id, "inventory:adjust")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=origin_branch_id,
        action="RECORD_TRANSFER_ORIGIN_COUNT",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).acknowledge_origin_count(
            company_id=company_id,
            transfer_id=transfer_id,
            discrepancy_id=discrepancy_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
            notes=body.notes,
        ),
        response_model=InventoryTransferOut,
    )

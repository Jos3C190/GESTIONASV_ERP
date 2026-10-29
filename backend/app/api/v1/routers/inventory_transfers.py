"""Auditable, company-scoped transfer document commands and demand queries."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
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
from app.api.v1.routers.inventory import InventoryBoundaryError
from app.api.v1.schemas.inventory_transfer import (
    InventoryTransferOut,
    InventoryVehicleCreateIn,
    InventoryVehicleOut,
    InventoryVehicleStatusIn,
    TransferCommandIn,
    TransferCreateIn,
    TransferDemandOut,
    TransferDispatchIn,
    TransferIncidentIn,
    TransferIncidentResolveIn,
    TransferReceiveIn,
    TransferUpdateIn,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryApplicationError
from app.application.inventory_transfers.use_cases import InventoryTransferUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_transfer import TransferDomainError
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)

router = APIRouter(prefix="/inventory/transfers", tags=["inventory transfers"])
T = TypeVar("T")


def _use_cases(session: SessionDep) -> InventoryTransferUseCases:
    return InventoryTransferUseCases(SqlAlchemyInventoryTransferRepository(session))


async def _require_dynamic_permission(
    checker: CheckPermissionUseCase, current: CurrentUser, company_id: uuid.UUID, code: str
) -> None:
    decision = await checker.execute(current.id, company_id, code)
    if not decision.allowed:
        raise AuthorizationError(f"Permiso requerido: {code}", code="forbidden")


async def _require_headquarters_scope(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID
) -> uuid.UUID:
    headquarters_id = await session.scalar(
        select(Branch.id).where(
            Branch.company_id == company_id,
            Branch.is_headquarters.is_(True),
            Branch.is_active.is_(True),
            Branch.operational_status == "active",
            Branch.deleted_at.is_(None),
        )
    )
    if headquarters_id is None:
        raise HTTPException(409, "La empresa no tiene una sucursal matriz activa.")
    await resolve_branch_scope(session, current, company_id, headquarters_id)
    return headquarters_id


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
    if not warehouse.is_central or warehouse.is_transit or warehouse.branch_id is None:
        raise HTTPException(422, "El traslado debe salir de una bodega central activa.")
    await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse.id)
    return warehouse


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
    operation: Awaitable[T],
    response_model: type[T],
) -> T:
    """Keep document, stock projection and required audit inside one savepoint."""
    try:
        async with session.begin_nested():
            result = await operation
            response = response_model.model_validate(result)
            await audit.record(
                action=action,
                user_id=current.id,
                company_id=company_id,
                branch_id=branch_id,
                resource_type=resource_type,
                resource_id=resource_id or str(getattr(response, "id", "")),
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
    except (InventoryApplicationError, InventoryOperationError) as exc:
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
) -> list[InventoryVehicleOut]:
    company_id = effective_company_id(request)
    await require_company_access(session, current, company_id)
    await _require_headquarters_scope(session, current, company_id)
    rows = await _use_cases(session).list_vehicles(company_id)
    return [InventoryVehicleOut.model_validate(row) for row in rows]


@router.post(
    "/vehicles",
    response_model=InventoryVehicleOut,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def create_vehicle(
    body: InventoryVehicleCreateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryVehicleOut:
    company_id = effective_company_id(request)
    await require_company_access(session, current, company_id)
    branch_id = await _require_headquarters_scope(session, current, company_id)
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="CREATE_VEHICLE",
        resource_type="inventory_vehicles",
        resource_id=None,
        operation=_use_cases(session).create_vehicle(
            company_id=company_id,
            code=body.code,
            name=body.name,
            actor_id=current.id,
        ),
        response_model=InventoryVehicleOut,
    )


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=InventoryVehicleOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def set_vehicle_status(
    vehicle_id: uuid.UUID,
    body: InventoryVehicleStatusIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> InventoryVehicleOut:
    company_id = effective_company_id(request)
    await require_company_access(session, current, company_id)
    branch_id = await _require_headquarters_scope(session, current, company_id)
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="SET_VEHICLE_STATUS",
        resource_type="inventory_vehicles",
        resource_id=str(vehicle_id),
        operation=_use_cases(session).set_vehicle_status(
            company_id=company_id,
            vehicle_id=vehicle_id,
            status=body.status,
        ),
        response_model=InventoryVehicleOut,
    )


@router.get(
    "",
    response_model=list[InventoryTransferOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_transfers(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    branch_id: uuid.UUID | None = None,
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(preparation|in_transit|received|closed_with_adjustment|incident|cancelled)$",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> list[InventoryTransferOut]:
    company_id = effective_company_id(request)
    context = await get_branch_context(session, current, company_id)
    if branch_id is not None:
        if not context.access_all_branches and not context.can_access(branch_id):
            raise HTTPException(403, "No tiene acceso a esta sucursal.")
        filters = {"branch_id": branch_id}
    else:
        filters = {
            "branch_ids": None
            if context.access_all_branches
            else [branch.id for branch in context.branches]
        }
    rows = await _use_cases(session).list_transfers(
        company_id=company_id,
        status_filter=status_filter,
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
    return await _persist_command(
        session=session,
        audit=audit,
        current=current,
        request=request,
        company_id=company_id,
        branch_id=branch_id,
        action="DISPATCH_TRANSFER",
        resource_type="inventory_transfers",
        resource_id=str(transfer_id),
        operation=_use_cases(session).dispatch_transfer(
            company_id=company_id,
            transfer_id=transfer_id,
            vehicle_id=body.vehicle_id,
            idempotency_key=body.idempotency_key,
            actor_id=current.id,
        ),
        response_model=InventoryTransferOut,
    )


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

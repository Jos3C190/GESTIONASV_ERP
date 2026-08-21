"""Inventory ledger, handling units, reservations and capacity API."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import date
from typing import Annotated, Any, TypeVar, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
    effective_company_id,
    require_company_wide_scope,
    require_resource_company,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.schemas.inventory import (
    CapacityDecisionOut,
    CapacityPreviewIn,
    CapacityReservationCreate,
    CapacityReservationCreated,
    CapacityReservationOut,
    CapacitySummaryOut,
    HandlingUnitMeasurementVerify,
    HandlingUnitOut,
    InventoryBalanceOut,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemSummaryOut,
    MovementConfirmIn,
    MovementOut,
    OperationalOverrideCreate,
    OperationalOverrideOut,
    PackagingCreate,
    PackagingOut,
    ReservationActionIn,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryApplicationError, InventoryUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AppError, AuthorizationError
from app.domain.entities.inventory import InventoryOperationError, StockStatus
from app.infrastructure.models.inventory import (
    CapacityOperationalOverrideModel,
    CapacityReservationModel,
    InventoryHandlingUnitModel,
)
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.repositories.inventory_repository import (
    SqlAlchemyInventoryRepository,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])
T = TypeVar("T")


class InventoryBoundaryError(AppError):
    """HTTP-safe inventory error raised only after the command transaction is reset."""

    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message, code=code)
        self.status_code = status_code


def _use_cases(session: SessionDep) -> InventoryUseCases:
    return InventoryUseCases(SqlAlchemyInventoryRepository(session))


async def _execute(session: SessionDep, operation: Awaitable[T]) -> T:
    """Translate inventory failures only after rolling back partial projections.

    The shared session intentionally commits generic business errors for login
    counters. Inventory commands need a stricter atomic boundary, especially a
    multi-line transfer, so their expected failures are rolled back explicitly.
    """
    try:
        return await operation
    except (InventoryApplicationError, InventoryOperationError) as exc:
        await session.rollback()
        raise InventoryBoundaryError(
            exc.message,
            code=exc.code,
            status_code=exc.status_code,
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise InventoryBoundaryError(
            "El inventario cambió al mismo tiempo o una referencia ya existe; recargue e intente de nuevo.",
            code="inventory_integrity_conflict",
            status_code=409,
        ) from exc


async def _authorize_warehouse(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    warehouse_id: uuid.UUID,
) -> uuid.UUID:
    row = (
        await session.execute(
            select(Branch.company_id, Branch.id)
            .select_from(Warehouse)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .where(Warehouse.id == warehouse_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Almacén no encontrado.")
    company_id = cast(uuid.UUID, row[0])
    branch_id = cast(uuid.UUID, row[1])
    require_resource_company(request, company_id, not_found_detail="Almacén no encontrado.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    return company_id


async def _authorize_location(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    row = (
        await session.execute(
            select(Branch.company_id, Branch.id, Warehouse.id)
            .select_from(Location)
            .join(Warehouse, Warehouse.id == Location.warehouse_id)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .where(Location.id == location_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    company_id = cast(uuid.UUID, row[0])
    branch_id = cast(uuid.UUID, row[1])
    warehouse_id = cast(uuid.UUID, row[2])
    require_resource_company(request, company_id, not_found_detail="Ubicación no encontrada.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    return company_id, warehouse_id


async def _authorize_locations(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_ids: set[uuid.UUID],
) -> None:
    for location_id in sorted(location_ids, key=str):
        await _authorize_location(request, session, current, location_id)


async def _require_dynamic_permission(
    checker: CheckPermissionUseCase,
    current: CurrentUser,
    company_id: uuid.UUID,
    code: str,
) -> None:
    decision = await checker.execute(current.id, company_id, code)
    if not decision.allowed:
        raise AuthorizationError(f"Permiso requerido: {code}", code="forbidden")


def _packaging_out(item: Any) -> PackagingOut:
    return PackagingOut(
        id=item.id,
        company_id=item.company_id,
        inventory_item_id=item.inventory_item_id,
        code=item.code,
        name=item.name,
        packaging_type=item.packaging_type,
        version=item.version,
        base_quantity=item.base_quantity,
        gross_weight_kg=item.measures.gross_weight_kg,
        length_m=item.measures.length_m,
        width_m=item.measures.width_m,
        height_m=item.measures.height_m,
        volume_m3=item.measures.derived_volume_m3,
        stackable=item.stackable,
        max_stack=item.max_stack,
        is_current=item.is_current,
        is_active=item.is_active,
        created_at=item.created_at,
    )


@router.post(
    "/items",
    response_model=InventoryItemOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory:manage_packaging"))],
)
async def create_inventory_item(
    body: InventoryItemCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> InventoryItemOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _execute(
        session,
        _use_cases(session).create_item(company_id=company_id, **body.model_dump()),
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_items",
        resource_id=str(item.id),
        after_state=jsonable_encoder(InventoryItemOut.model_validate(item)),
        required=True,
    )
    return InventoryItemOut.model_validate(item)


@router.get(
    "/items/by-target",
    response_model=InventoryItemOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_inventory_item_by_target(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    product_id: int | None = Query(None, gt=0),
    variant_id: uuid.UUID | None = None,
) -> InventoryItemOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _execute(
        session,
        _use_cases(session).get_item_by_target(
            company_id=company_id,
            product_id=product_id,
            variant_id=variant_id,
        ),
    )
    return InventoryItemOut.model_validate(item)


@router.get(
    "/items/{item_id}",
    response_model=InventoryItemOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_inventory_item(
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> InventoryItemOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _execute(session, _use_cases(session).get_item(company_id, item_id))
    return InventoryItemOut.model_validate(item)


@router.get(
    "/items/{item_id}/summary",
    response_model=InventoryItemSummaryOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_inventory_item_summary(
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> InventoryItemSummaryOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    summary = await _execute(
        session,
        _use_cases(session).inventory_item_summary(company_id=company_id, item_id=item_id),
    )
    return InventoryItemSummaryOut.model_validate(summary)


@router.get(
    "/items/{item_id}/packaging",
    response_model=list[PackagingOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_packaging(
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> list[PackagingOut]:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    items = await _execute(session, _use_cases(session).list_packaging(company_id, item_id))
    return [_packaging_out(item) for item in items]


@router.post(
    "/items/{item_id}/packaging",
    response_model=PackagingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory:manage_packaging"))],
)
async def create_packaging(
    item_id: uuid.UUID,
    body: PackagingCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> PackagingOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    item = await _execute(
        session,
        _use_cases(session).create_packaging(
            company_id=company_id,
            item_id=item_id,
            code=body.code,
            name=body.name,
            packaging_type=body.packaging_type,
            base_quantity=body.base_quantity,
            measures=body.measures.to_domain(),
            stackable=body.stackable,
            max_stack=body.max_stack,
            supersedes_id=body.supersedes_id,
        ),
    )
    response = _packaging_out(item)
    await audit.record(
        action="CREATE_VERSION" if body.supersedes_id else "CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_packaging_definitions",
        resource_id=str(item.id),
        after_state=jsonable_encoder(response),
        required=True,
    )
    return response


@router.delete(
    "/items/{item_id}/packaging/{packaging_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("inventory:manage_packaging"))],
)
async def deactivate_packaging(
    item_id: uuid.UUID,
    packaging_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> None:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    await _execute(
        session,
        _use_cases(session).deactivate_packaging(company_id, item_id, packaging_id),
    )
    await audit.record(
        action="DEACTIVATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_packaging_definitions",
        resource_id=str(packaging_id),
        required=True,
    )


@router.post(
    "/capacity/preview",
    response_model=CapacityDecisionOut,
    dependencies=[Depends(require_permission("inventory:capacity"))],
)
async def preview_capacity(
    body: CapacityPreviewIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> CapacityDecisionOut:
    company_id, _warehouse_id = await _authorize_location(
        request, session, current, body.location_id
    )
    decision = await _execute(
        session,
        _use_cases(session).preview_capacity(
            company_id=company_id,
            location_id=body.location_id,
            item_id=body.inventory_item_id,
            packaging_id=body.packaging_definition_id,
            quantity_base=body.quantity_base,
            stock_status=body.stock_status,
            actual_measures=(
                body.actual_measures.to_domain() if body.actual_measures else None
            ),
            override_id=body.operational_override_id,
            exclude_reservation_id=body.exclude_reservation_id,
        ),
    )
    return CapacityDecisionOut.model_validate(decision)


@router.post(
    "/capacity/reservations",
    response_model=CapacityReservationCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory:reserve"))],
)
async def reserve_capacity(
    body: CapacityReservationCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> CapacityReservationCreated:
    company_id, _warehouse_id = await _authorize_location(
        request, session, current, body.location_id
    )
    reservation, decision = await _execute(
        session,
        _use_cases(session).reserve_capacity(
            company_id=company_id,
            location_id=body.location_id,
            item_id=body.inventory_item_id,
            packaging_id=body.packaging_definition_id,
            quantity_base=body.quantity_base,
            stock_status=body.stock_status,
            actual_measures=(
                body.actual_measures.to_domain() if body.actual_measures else None
            ),
            duration_minutes=body.duration_minutes,
            actor_id=current.id,
            override_id=body.operational_override_id,
        ),
    )
    response = CapacityReservationCreated(
        reservation=CapacityReservationOut.model_validate(reservation),
        decision=CapacityDecisionOut.model_validate(decision),
    )
    await audit.record(
        action="RESERVE",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_capacity_reservations",
        resource_id=str(reservation.id),
        after_state=jsonable_encoder(response),
        required=True,
    )
    return response


@router.post(
    "/capacity/reservations/{reservation_id}/action",
    response_model=CapacityReservationOut,
    dependencies=[Depends(require_permission("inventory:reserve"))],
)
async def change_reservation_status(
    reservation_id: uuid.UUID,
    body: ReservationActionIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> CapacityReservationOut:
    persisted = await session.scalar(
        select(CapacityReservationModel).where(CapacityReservationModel.id == reservation_id)
    )
    if persisted is None:
        raise HTTPException(404, "Reserva no encontrada.")
    company_id, _warehouse_id = await _authorize_location(
        request, session, current, persisted.location_id
    )
    require_resource_company(request, persisted.company_id, not_found_detail="Reserva no encontrada.")
    reservation = await _execute(
        session,
        _use_cases(session).change_reservation_status(
            company_id=company_id,
            reservation_id=reservation_id,
            action=body.action,
            actor_id=current.id,
        ),
    )
    response = CapacityReservationOut.model_validate(reservation)
    audit_action = (
        "EXPIRE" if reservation.status.value == "expired" else body.action.upper()
    )
    await audit.record(
        action=audit_action,
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_capacity_reservations",
        resource_id=str(reservation_id),
        after_state=jsonable_encoder(response),
        required=True,
    )
    return response


@router.post(
    "/movements/confirm",
    response_model=MovementOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def confirm_movement(
    body: MovementConfirmIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> MovementOut:
    company_id = effective_company_id(request)
    permission = (
        "inventory:receive"
        if body.movement_type in {"receipt", "adjustment_in"}
        else "inventory:move"
    )
    await _require_dynamic_permission(checker, current, company_id, permission)
    location_ids = {
        location_id
        for line in body.lines
        for location_id in (line.from_location_id, line.to_location_id)
        if location_id is not None
    }
    await _authorize_locations(request, session, current, location_ids)
    movement = await _execute(
        session,
        _use_cases(session).post_movement(
            company_id=company_id,
            idempotency_key=body.idempotency_key,
            movement_type=body.movement_type,
            source_reference=body.source_reference,
            lines=[line.model_dump() for line in body.lines],
            actor_id=current.id,
            reservation_id=body.reservation_id,
        ),
    )
    response = MovementOut.model_validate(movement)
    await audit.record(
        action="CONFIRM",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_movements",
        resource_id=str(response.id),
        after_state={
            "movement_type": response.movement_type,
            "line_count": len(response.lines),
            "reservation_id": str(response.reservation_id) if response.reservation_id else None,
        },
        required=True,
    )
    return response


@router.get(
    "/warehouses/{warehouse_id}/handling-units",
    response_model=list[HandlingUnitOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_handling_units(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_id: uuid.UUID | None = None,
    inventory_item_id: uuid.UUID | None = None,
    stock_status: StockStatus | None = None,
    include_closed: bool = False,
) -> list[HandlingUnitOut]:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    items = await _execute(
        session,
        _use_cases(session).list_handling_units(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            item_id=inventory_item_id,
            stock_status=stock_status,
            include_closed=include_closed,
        ),
    )
    return [HandlingUnitOut.model_validate(item) for item in items]


@router.patch(
    "/handling-units/{handling_unit_id}/measurements",
    response_model=HandlingUnitOut,
    dependencies=[Depends(require_permission("inventory:receive"))],
)
async def verify_handling_unit_measurements(
    handling_unit_id: uuid.UUID,
    body: HandlingUnitMeasurementVerify,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> HandlingUnitOut:
    persisted = await session.scalar(
        select(InventoryHandlingUnitModel).where(
            InventoryHandlingUnitModel.id == handling_unit_id
        )
    )
    if persisted is None:
        raise HTTPException(404, "Unidad logística no encontrada.")
    company_id, _warehouse_id = await _authorize_location(
        request, session, current, persisted.location_id
    )
    require_resource_company(
        request, persisted.company_id, not_found_detail="Unidad logística no encontrada."
    )
    before_state = {
        "measurement_status": persisted.measurement_status,
        "occupied_weight_kg": str(persisted.occupied_weight_kg),
        "occupied_volume_m3": str(persisted.occupied_volume_m3),
    }
    item = await _execute(
        session,
        _use_cases(session).verify_handling_unit_measurements(
            company_id=company_id,
            handling_unit_id=handling_unit_id,
            measures=body.measures.to_domain(),
            source=body.source,
            actor_id=current.id,
        ),
    )
    response = HandlingUnitOut.model_validate(item)
    await audit.record(
        action="VERIFY_MEASUREMENTS",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_handling_units",
        resource_id=str(handling_unit_id),
        before_state=before_state,
        after_state=jsonable_encoder(response),
        required=True,
    )
    return response


@router.get(
    "/warehouses/{warehouse_id}/balances",
    response_model=list[InventoryBalanceOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_balances(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_id: uuid.UUID | None = None,
    inventory_item_id: uuid.UUID | None = None,
    stock_status: StockStatus | None = None,
    lot_code: str | None = Query(None, max_length=120),
    expiry_before: date | None = None,
) -> list[InventoryBalanceOut]:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    items = await _execute(
        session,
        _use_cases(session).list_balances(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            item_id=inventory_item_id,
            stock_status=stock_status,
            lot_code=lot_code,
            expiry_before=expiry_before,
        ),
    )
    return [InventoryBalanceOut.model_validate(item) for item in items]


@router.get(
    "/warehouses/{warehouse_id}/capacity-summary",
    response_model=CapacitySummaryOut,
    dependencies=[Depends(require_permission("inventory:capacity"))],
)
async def capacity_summary(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_id: uuid.UUID | None = None,
) -> CapacitySummaryOut:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    if location_id is not None:
        location_company_id, location_warehouse_id = await _authorize_location(
            request, session, current, location_id
        )
        if location_company_id != company_id or location_warehouse_id != warehouse_id:
            raise HTTPException(404, "Ubicación no encontrada en el almacén.")
    summary = await _execute(
        session,
        _use_cases(session).capacity_summary(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
        ),
    )
    return CapacitySummaryOut.model_validate(summary)


@router.post(
    "/capacity/operational-overrides",
    response_model=OperationalOverrideOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("capacity:override_operational"))],
)
async def create_operational_override(
    body: OperationalOverrideCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> OperationalOverrideOut:
    company_id, _warehouse_id = await _authorize_location(
        request, session, current, body.location_id
    )
    item = await _execute(
        session,
        _use_cases(session).create_operational_override(
            company_id=company_id,
            location_id=body.location_id,
            reason=body.reason,
            valid_until=body.valid_until,
            actor_id=current.id,
        ),
    )
    response = OperationalOverrideOut.model_validate(item)
    await audit.record(
        action="AUTHORIZE_OPERATIONAL_OVERRIDE",
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_capacity_operational_overrides",
        resource_id=str(response.id),
        after_state=jsonable_encoder(response),
        required=True,
    )
    return response


@router.delete(
    "/capacity/operational-overrides/{override_id}",
    response_model=OperationalOverrideOut,
    dependencies=[Depends(require_permission("capacity:override_operational"))],
)
async def revoke_operational_override(
    override_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> OperationalOverrideOut:
    persisted = await session.scalar(
        select(CapacityOperationalOverrideModel).where(
            CapacityOperationalOverrideModel.id == override_id
        )
    )
    if persisted is None:
        raise HTTPException(404, "Autorización operativa no encontrada.")
    company_id, _warehouse_id = await _authorize_location(
        request, session, current, persisted.location_id
    )
    require_resource_company(
        request,
        persisted.company_id,
        not_found_detail="Autorización operativa no encontrada.",
    )
    item = await _execute(
        session,
        _use_cases(session).revoke_operational_override(
            company_id=company_id,
            override_id=override_id,
            actor_id=current.id,
        ),
    )
    response = OperationalOverrideOut.model_validate(item)
    audit_action = "EXPIRE" if response.status == "expired" else "REVOKE_OPERATIONAL_OVERRIDE"
    await audit.record(
        action=audit_action,
        user_id=current.id,
        company_id=company_id,
        resource_type="inventory_capacity_operational_overrides",
        resource_id=str(override_id),
        after_state=jsonable_encoder(response),
        required=True,
    )
    return response

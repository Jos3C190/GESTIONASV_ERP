"""Inventory ledger, handling units, reservations and capacity API."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, TypeVar, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.api.v1.company_access import (
    authorize_warehouse_assignment,
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
    HandlingUnitSplitPrepareIn,
    HandlingUnitSplitPrepareOut,
    HandlingUnitTraceOut,
    InventoryBalanceOut,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemSummaryOut,
    InventoryMovementHistoryOut,
    MovementConfirmIn,
    MovementLineIn,
    MovementOut,
    OperationalOverrideCreate,
    OperationalOverrideOut,
    PackagingCreate,
    PackagingOut,
    ReservationActionIn,
    TransferHandlingUnitOut,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryApplicationError, InventoryUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AppError, AuthorizationError
from app.domain.entities.inventory import InventoryOperationError, StockStatus
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    CapacityOperationalOverrideModel,
    CapacityReservationModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.repositories.inventory_repository import (
    SqlAlchemyInventoryRepository,
)
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
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
            select(Warehouse.company_id, Warehouse.branch_id)
            .select_from(Warehouse)
            .where(Warehouse.id == warehouse_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Almacén no encontrado.")
    company_id = cast(uuid.UUID, row[0])
    branch_id = cast(uuid.UUID | None, row[1])
    require_resource_company(request, company_id, not_found_detail="Almacén no encontrado.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse_id)
    return company_id


async def _authorize_location(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    row = (
        await session.execute(
            select(Warehouse.company_id, Warehouse.branch_id, Warehouse.id)
            .select_from(Location)
            .join(Warehouse, Warehouse.id == Location.warehouse_id)
            .where(Location.id == location_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    company_id = cast(uuid.UUID, row[0])
    branch_id = cast(uuid.UUID | None, row[1])
    warehouse_id = cast(uuid.UUID, row[2])
    require_resource_company(request, company_id, not_found_detail="Ubicación no encontrada.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse_id)
    return company_id, warehouse_id


async def _authorize_locations(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    location_ids: set[uuid.UUID],
) -> None:
    for location_id in sorted(location_ids, key=str):
        await _authorize_location(request, session, current, location_id)


async def _reject_legacy_transfer_through_vehicle_transit(
    session: SessionDep, location_ids: set[uuid.UUID]
) -> None:
    """Keep the generic movement endpoint out of document-owned vehicle transit."""
    if not location_ids:
        return
    transit_location_id = await session.scalar(
        select(Location.id)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
        .where(
            Location.id.in_(location_ids),
            Warehouse.is_transit.is_(True),
        )
        .limit(1)
    )
    if transit_location_id is not None:
        raise InventoryBoundaryError(
            "El tránsito en vehículo requiere un documento de traslado; use sus acciones de despacho y recepción.",
            code="inventory_transfer_document_required",
            status_code=409,
        )


async def _reject_legacy_transfer_without_document(
    session: SessionDep, lines: list[MovementLineIn]
) -> None:
    """Require B03 documents for warehouse-to-warehouse and in-transit transfers."""
    if any(
        StockStatus.IN_TRANSIT in {line.from_stock_status, line.to_stock_status} for line in lines
    ):
        raise InventoryBoundaryError(
            "El tránsito de mercancía requiere un documento de traslado; use sus acciones de despacho y recepción.",
            code="inventory_transfer_document_required",
            status_code=409,
        )

    location_pairs = [
        (line.from_location_id, line.to_location_id)
        for line in lines
        if line.from_location_id is not None and line.to_location_id is not None
    ]
    location_ids = {location_id for pair in location_pairs for location_id in pair}
    if not location_ids:
        return
    rows = (
        await session.execute(
            select(Location.id, Location.warehouse_id).where(Location.id.in_(location_ids))
        )
    ).all()
    warehouse_by_location = dict(rows)
    if any(
        source_id in warehouse_by_location
        and destination_id in warehouse_by_location
        and warehouse_by_location[source_id] != warehouse_by_location[destination_id]
        for source_id, destination_id in location_pairs
    ):
        raise InventoryBoundaryError(
            "El movimiento entre bodegas requiere un documento de traslado; use el flujo de Traslados.",
            code="inventory_transfer_document_required",
            status_code=409,
        )


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
        packaging_unit_id=item.packaging_unit_id,
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
            packaging_unit_id=body.packaging_unit_id,
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
            actual_measures=(body.actual_measures.to_domain() if body.actual_measures else None),
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
            actual_measures=(body.actual_measures.to_domain() if body.actual_measures else None),
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
    require_resource_company(
        request, persisted.company_id, not_found_detail="Reserva no encontrada."
    )
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
    audit_action = "EXPIRE" if reservation.status.value == "expired" else body.action.upper()
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
    if any(
        line.valuation_kind == "customer_return" or line.valuation_original_entry_id is not None
        for line in body.lines
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "sales_return_document_required",
                "message": "Las devoluciones de cliente deben registrarse desde el documento de devolución de la venta.",
            },
        )
    if body.movement_type == "receipt":
        raise HTTPException(
            409,
            detail={
                "code": "purchase_receipt_document_required",
                "message": "Registre las recepciones desde su compra. Las compras nuevas requieren el retaceo cerrado antes de ingresar existencias.",
            },
        )
    if body.movement_type in {"adjustment_in", "adjustment_out"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "authorized_adjustment_document_required",
                "message": "Los ajustes deben registrarse desde el flujo autorizado de ajustes de inventario.",
            },
        )
    company_id = effective_company_id(request)
    transfer_receipt = (
        body.movement_type == "transfer"
        and bool(body.lines)
        and all(
            line.from_stock_status == StockStatus.IN_TRANSIT
            and line.to_stock_status == StockStatus.QUARANTINE
            for line in body.lines
        )
    )
    permission = (
        "inventory:receive"
        if body.movement_type in {"receipt", "adjustment_in"} or transfer_receipt
        else "inventory:move"
    )
    await _require_dynamic_permission(checker, current, company_id, permission)
    if any(
        line.valuation_kind is not None
        or line.valuation_value is not None
        or line.valuation_original_entry_id is not None
        or line.valuation_currency is not None
        for line in body.lines
    ):
        await _require_dynamic_permission(checker, current, company_id, "inventory:valuation")
    location_ids = {
        location_id
        for line in body.lines
        for location_id in (line.from_location_id, line.to_location_id)
        if location_id is not None
    }
    await _authorize_locations(request, session, current, location_ids)
    if body.movement_type == "transfer":
        await _reject_legacy_transfer_through_vehicle_transit(session, location_ids)
        await _reject_legacy_transfer_without_document(session, body.lines)
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


@dataclass(frozen=True)
class _HandlingUnitSplitReferences:
    source_reference: str
    movement_keys: tuple[str, str]
    movement_references: tuple[str, str]


@dataclass(frozen=True)
class _HandlingUnitSplitOrigin:
    quantity_base: Decimal
    inventory_item_id: uuid.UUID
    source_location_id: uuid.UUID
    is_replay: bool


def _handling_unit_split_references(
    company_id: uuid.UUID,
    handling_unit_id: uuid.UUID,
    body: HandlingUnitSplitPrepareIn,
) -> _HandlingUnitSplitReferences:
    key_digest = hashlib.sha256(f"{company_id}:{body.idempotency_key}".encode()).hexdigest()
    canonical = {
        "handling_unit_id": str(handling_unit_id),
        **body.model_dump(mode="json", exclude={"idempotency_key"}),
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    source_reference = f"hu-split:{key_digest}:{fingerprint}"
    return _HandlingUnitSplitReferences(
        source_reference=source_reference,
        movement_keys=(f"hu-split:{key_digest}:quarantine", f"hu-split:{key_digest}:split"),
        movement_references=(f"{source_reference}:quarantine", f"{source_reference}:split"),
    )


async def _load_handling_unit_split_origin(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    handling_unit_id: uuid.UUID,
    body: HandlingUnitSplitPrepareIn,
    references: _HandlingUnitSplitReferences,
) -> _HandlingUnitSplitOrigin:
    """Load a fresh source or verify the exact movement pair for an idempotent replay."""
    movement_keys = references.movement_keys
    existing = list(
        (
            await session.scalars(
                select(InventoryMovementModel)
                .where(
                    InventoryMovementModel.company_id == company_id,
                    InventoryMovementModel.idempotency_key.in_(movement_keys),
                )
                .order_by(InventoryMovementModel.idempotency_key)
                .with_for_update()
            )
        ).all()
    )
    existing_by_key = {row.idempotency_key: row for row in existing}
    if existing and (
        set(existing_by_key) != set(movement_keys)
        or any(
            existing_by_key[key].source_reference != movement_reference
            for key, movement_reference in zip(
                movement_keys, references.movement_references, strict=True
            )
            if key in existing_by_key
        )
    ):
        raise InventoryOperationError(
            "La clave de idempotencia ya se usó con otra preparación o el historial quedó incompleto.",
            code="handling_unit_split_idempotency_conflict",
            status_code=409,
        )

    if existing:
        stored_lines: dict[str, InventoryMovementLineModel] = {}
        for key in movement_keys:
            stored = list(
                (
                    await session.scalars(
                        select(InventoryMovementLineModel)
                        .where(
                            InventoryMovementLineModel.company_id == company_id,
                            InventoryMovementLineModel.movement_id == existing_by_key[key].id,
                        )
                        .order_by(InventoryMovementLineModel.line_number)
                    )
                ).all()
            )
            if len(stored) != 1:
                raise InventoryOperationError(
                    "El historial de la preparación no contiene sus dos movimientos completos.",
                    code="handling_unit_split_idempotency_conflict",
                    status_code=409,
                )
            stored_lines[key] = stored[0]
        quarantine_line = stored_lines[movement_keys[0]]
        split_line = stored_lines[movement_keys[1]]
        source_location_id = quarantine_line.from_location_id
        if (
            source_location_id is None
            or quarantine_line.handling_unit_id != handling_unit_id
            or quarantine_line.from_stock_status != "available"
            or quarantine_line.to_stock_status != "quarantine"
            or split_line.inventory_item_id != quarantine_line.inventory_item_id
            or split_line.quantity_base != body.split_quantity_base
            or split_line.to_location_id != body.destination_location_id
            or split_line.from_stock_status != "quarantine"
            or split_line.to_stock_status != "quarantine"
            or body.split_quantity_base >= quarantine_line.quantity_base
        ):
            raise InventoryOperationError(
                "La clave de idempotencia ya se usó con otra preparación.",
                code="handling_unit_split_idempotency_conflict",
                status_code=409,
            )
        return _HandlingUnitSplitOrigin(
            quantity_base=quarantine_line.quantity_base,
            inventory_item_id=quarantine_line.inventory_item_id,
            source_location_id=source_location_id,
            is_replay=True,
        )

    source = await session.scalar(
        select(InventoryHandlingUnitModel).where(
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.id == handling_unit_id,
        )
    )
    if source is None or source.closed_at is not None:
        raise InventoryOperationError(
            "Unidad logística no encontrada o cerrada.",
            code="handling_unit_not_available",
            status_code=404,
        )
    if source.stock_status != StockStatus.AVAILABLE.value:
        raise InventoryOperationError(
            "Solo una unidad disponible puede prepararse para fraccionamiento.",
            code="handling_unit_split_requires_available",
            status_code=409,
        )
    if body.split_quantity_base >= source.quantity_base:
        raise InventoryOperationError(
            "La cantidad a separar debe ser menor que la unidad completa.",
            code="handling_unit_split_quantity_invalid",
            status_code=422,
        )
    return _HandlingUnitSplitOrigin(
        quantity_base=source.quantity_base,
        inventory_item_id=source.inventory_item_id,
        source_location_id=source.location_id,
        is_replay=False,
    )


async def _authorize_handling_unit_split_destination(
    session: SessionDep,
    *,
    request: Request,
    current: CurrentUser,
    company_id: uuid.UUID,
    body: HandlingUnitSplitPrepareIn,
    source_location_id: uuid.UUID,
) -> None:
    destination = await session.execute(
        select(Location, Warehouse)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
        .where(
            Location.id == body.destination_location_id,
            Warehouse.company_id == company_id,
            Warehouse.is_active.is_(True),
            Warehouse.deleted_at.is_(None),
        )
    )
    destination_row = destination.one_or_none()
    if destination_row is None:
        raise InventoryOperationError(
            "La ubicación de fraccionamiento no está disponible.",
            code="handling_unit_split_destination_invalid",
            status_code=409,
        )
    destination_location, destination_warehouse = destination_row
    source_warehouse_id = await session.scalar(
        select(Location.warehouse_id).where(Location.id == source_location_id)
    )
    if (
        destination_warehouse.id != source_warehouse_id
        or not destination_location.is_active
        or destination_location.deleted_at is not None
        or destination_location.lifecycle_status != "active"
        or not destination_location.storage_eligible
    ):
        raise InventoryOperationError(
            "El destino debe ser una ubicación activa y apta para almacenamiento en la misma bodega.",
            code="handling_unit_split_destination_invalid",
            status_code=409,
        )
    await _authorize_locations(
        request,
        session,
        current,
        {source_location_id, body.destination_location_id},
    )


async def _execute_handling_unit_split(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    handling_unit_id: uuid.UUID,
    body: HandlingUnitSplitPrepareIn,
    references: _HandlingUnitSplitReferences,
    origin: _HandlingUnitSplitOrigin,
    current: CurrentUser,
    audit: AuditService,
) -> HandlingUnitSplitPrepareOut:
    inventory = _use_cases(session)
    quarantined = await inventory.post_movement(
        company_id=company_id,
        idempotency_key=references.movement_keys[0],
        movement_type="transfer",
        source_reference=references.movement_references[0],
        lines=[
            {
                "inventory_item_id": origin.inventory_item_id,
                "handling_unit_id": handling_unit_id,
                "from_location_id": origin.source_location_id,
                "to_location_id": origin.source_location_id,
                "from_stock_status": "available",
                "to_stock_status": "quarantine",
                "quantity_base": origin.quantity_base,
            }
        ],
        actor_id=current.id,
    )
    split = await inventory.post_movement(
        company_id=company_id,
        idempotency_key=references.movement_keys[1],
        movement_type="putaway",
        source_reference=references.movement_references[1],
        lines=[
            {
                "inventory_item_id": origin.inventory_item_id,
                "handling_unit_id": handling_unit_id,
                "from_location_id": origin.source_location_id,
                "to_location_id": body.destination_location_id,
                "from_stock_status": "quarantine",
                "to_stock_status": "quarantine",
                "quantity_base": body.split_quantity_base,
            }
        ],
        actor_id=current.id,
    )
    split_unit_id = split["lines"][0]["handling_unit_id"]
    source = await session.scalar(
        select(InventoryHandlingUnitModel).where(
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.id == handling_unit_id,
        )
    )
    split_unit = await session.scalar(
        select(InventoryHandlingUnitModel).where(
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.id == split_unit_id,
        )
    )
    if source is None or split_unit is None:
        raise InventoryOperationError(
            "No se pudieron recuperar las unidades resultantes del fraccionamiento.",
            code="handling_unit_split_result_missing",
            status_code=409,
        )
    response = HandlingUnitSplitPrepareOut(
        idempotency_key=body.idempotency_key,
        source_reference=references.source_reference,
        quarantine_movement=MovementOut.model_validate(quarantined),
        split_movement=MovementOut.model_validate(split),
        remainder_handling_unit_id=source.id,
        remainder_handling_unit_code=source.code,
        remainder_quantity_base=origin.quantity_base - body.split_quantity_base,
        split_handling_unit_id=split_unit.id,
        split_handling_unit_code=split_unit.code,
        split_quantity_base=body.split_quantity_base,
        stock_status=StockStatus.QUARANTINE,
        measurement_status=split_unit.measurement_status,
    )
    if not origin.is_replay:
        await audit.record(
            action="PREPARE_SPLIT",
            user_id=current.id,
            company_id=company_id,
            resource_type="inventory_handling_units",
            resource_id=str(handling_unit_id),
            after_state=jsonable_encoder(response),
            required=True,
        )
    return response


async def _prepare_handling_unit_split_transaction(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    handling_unit_id: uuid.UUID,
    body: HandlingUnitSplitPrepareIn,
    request: Request,
    current: CurrentUser,
    audit: AuditService,
) -> HandlingUnitSplitPrepareOut:
    references = _handling_unit_split_references(company_id, handling_unit_id, body)
    async with session.begin_nested():
        # Match regular movement commands: valuation lock precedes stock/location locks.
        await SqlAlchemyInventoryValuationRepository(session).lock(company_id)
        origin = await _load_handling_unit_split_origin(
            session,
            company_id=company_id,
            handling_unit_id=handling_unit_id,
            body=body,
            references=references,
        )
        await _authorize_handling_unit_split_destination(
            session,
            request=request,
            current=current,
            company_id=company_id,
            body=body,
            source_location_id=origin.source_location_id,
        )
        return await _execute_handling_unit_split(
            session,
            company_id=company_id,
            handling_unit_id=handling_unit_id,
            body=body,
            references=references,
            origin=origin,
            current=current,
            audit=audit,
        )


@router.post(
    "/handling-units/{handling_unit_id}/prepare-split",
    response_model=HandlingUnitSplitPrepareOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def prepare_handling_unit_split(
    handling_unit_id: uuid.UUID,
    body: HandlingUnitSplitPrepareIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> HandlingUnitSplitPrepareOut:
    """Atomically quarantine and split an available HU for fresh remeasurement."""
    company_id = effective_company_id(request)
    await _require_dynamic_permission(checker, current, company_id, "inventory:move")
    try:
        return await _prepare_handling_unit_split_transaction(
            session,
            company_id=company_id,
            handling_unit_id=handling_unit_id,
            body=body,
            request=request,
            current=current,
            audit=audit,
        )
    except (InventoryApplicationError, InventoryOperationError) as exc:
        raise InventoryBoundaryError(
            exc.message, code=exc.code, status_code=exc.status_code
        ) from exc
    except IntegrityError as exc:
        raise InventoryBoundaryError(
            "El inventario cambió al mismo tiempo o la clave ya existe; recargue e intente de nuevo.",
            code="inventory_integrity_conflict",
            status_code=409,
        ) from exc


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


@router.get(
    "/warehouses/{warehouse_id}/transfer-units",
    response_model=list[TransferHandlingUnitOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_transfer_units(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    stock_status: StockStatus = Query(...),
) -> list[TransferHandlingUnitOut]:
    if stock_status not in {StockStatus.AVAILABLE, StockStatus.IN_TRANSIT}:
        raise HTTPException(422, "Solo se consultan unidades disponibles o en tránsito.")

    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    product_id = func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id)
    latest_reference = (
        select(InventoryMovementModel.source_reference)
        .join(
            InventoryMovementLineModel,
            InventoryMovementLineModel.movement_id == InventoryMovementModel.id,
        )
        .where(
            InventoryMovementLineModel.company_id == company_id,
            InventoryMovementLineModel.handling_unit_id == InventoryHandlingUnitModel.id,
        )
        .order_by(InventoryMovementModel.posted_at.desc(), InventoryMovementModel.id.desc())
        .limit(1)
        .correlate(InventoryHandlingUnitModel)
        .scalar_subquery()
    )
    origin_unit = aliased(InventoryHandlingUnitModel)
    rows = (
        await session.execute(
            select(
                InventoryHandlingUnitModel,
                product_id.label("product_id"),
                func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("product_sku"),
                func.coalesce(ProductVariantModel.name_override, ProductModel.name).label(
                    "product_name"
                ),
                InventoryItemModel.base_unit_id.label("base_unit_id"),
                func.coalesce(CompanyUnitModel.alias, UnitModel.name).label("base_unit_name"),
                UnitModel.symbol.label("base_unit_symbol"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                Warehouse.branch_id.label("branch_id"),
                Branch.name.label("branch_name"),
                Location.code.label("location_code"),
                latest_reference.label("source_reference"),
                origin_unit.code.label("origin_handling_unit_code"),
                InventoryLotDetailModel.code.label("receipt_lot_code"),
                InventoryLotModel.code.label("receipt_lot_header_code"),
                InventoryLotModel.received_at.label("received_at"),
            )
            .join(
                InventoryItemModel,
                and_(
                    InventoryItemModel.company_id == InventoryHandlingUnitModel.company_id,
                    InventoryItemModel.id == InventoryHandlingUnitModel.inventory_item_id,
                ),
            )
            .outerjoin(
                ProductVariantModel,
                and_(
                    ProductVariantModel.company_id == InventoryItemModel.company_id,
                    ProductVariantModel.id == InventoryItemModel.variant_id,
                ),
            )
            .outerjoin(
                ProductModel,
                and_(
                    ProductModel.company_id == InventoryItemModel.company_id,
                    ProductModel.id_product == product_id,
                ),
            )
            .join(
                CompanyUnitModel,
                and_(
                    CompanyUnitModel.company_id == InventoryItemModel.company_id,
                    CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id,
                ),
            )
            .join(UnitModel, UnitModel.id_unit == CompanyUnitModel.unit_id)
            .join(Location, Location.id == InventoryHandlingUnitModel.location_id)
            .join(Warehouse, Warehouse.id == InventoryHandlingUnitModel.warehouse_id)
            .outerjoin(Branch, Branch.id == Warehouse.branch_id)
            .outerjoin(
                origin_unit,
                and_(
                    origin_unit.id == InventoryHandlingUnitModel.origin_handling_unit_id,
                    origin_unit.company_id == InventoryHandlingUnitModel.company_id,
                ),
            )
            .outerjoin(
                InventoryLotModel,
                and_(
                    InventoryLotModel.company_id == InventoryHandlingUnitModel.company_id,
                    InventoryLotModel.id == InventoryHandlingUnitModel.inventory_lot_id,
                ),
            )
            .outerjoin(
                InventoryLotDetailModel,
                and_(
                    InventoryLotDetailModel.company_id == InventoryHandlingUnitModel.company_id,
                    InventoryLotDetailModel.id
                    == InventoryHandlingUnitModel.inventory_lot_detail_id,
                    InventoryLotDetailModel.inventory_lot_id
                    == InventoryHandlingUnitModel.inventory_lot_id,
                    InventoryLotDetailModel.inventory_item_id
                    == InventoryHandlingUnitModel.inventory_item_id,
                ),
            )
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.warehouse_id == warehouse_id,
                InventoryHandlingUnitModel.stock_status == stock_status.value,
                InventoryHandlingUnitModel.closed_at.is_(None),
                *(
                    [
                        Location.storage_eligible.is_(True),
                        Location.is_active.is_(True),
                        Location.lifecycle_status == "active",
                    ]
                    if stock_status == StockStatus.AVAILABLE
                    else []
                ),
            )
            .order_by(
                ProductModel.name,
                ProductModel.id_product,
                InventoryHandlingUnitModel.created_at,
            )
        )
    ).all()
    response: list[TransferHandlingUnitOut] = []
    for row in rows:
        handling_unit = row[0]
        unit_data = {
            field_name: getattr(handling_unit, field_name)
            for field_name in HandlingUnitOut.model_fields
            if hasattr(handling_unit, field_name)
        }
        unit_data["receipt_lot_id"] = handling_unit.inventory_lot_id
        response.append(
            TransferHandlingUnitOut(
                **unit_data,
                product_id=row.product_id,
                product_sku=row.product_sku,
                product_name=row.product_name,
                base_unit_id=row.base_unit_id,
                base_unit_name=row.base_unit_name,
                base_unit_symbol=row.base_unit_symbol,
                warehouse_code=row.warehouse_code,
                warehouse_name=row.warehouse_name,
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                location_code=row.location_code,
                source_reference=row.source_reference,
                origin_handling_unit_code=row.origin_handling_unit_code,
                receipt_lot_code=row.receipt_lot_code,
                receipt_lot_header_code=row.receipt_lot_header_code,
                received_at=row.received_at,
            )
        )
    return response


@router.get(
    "/handling-units/{handling_unit_id}/traceability",
    response_model=HandlingUnitTraceOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_handling_unit_traceability(
    handling_unit_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> HandlingUnitTraceOut:
    persisted = await session.scalar(
        select(InventoryHandlingUnitModel).where(InventoryHandlingUnitModel.id == handling_unit_id)
    )
    if persisted is None:
        raise HTTPException(404, "Unidad logística no encontrada.")
    company_id = await _authorize_warehouse(request, session, current, persisted.warehouse_id)
    require_resource_company(
        request, persisted.company_id, not_found_detail="Unidad logística no encontrada."
    )
    trace = await _use_cases(session).get_handling_unit_traceability(
        company_id=company_id,
        handling_unit_id=handling_unit_id,
    )
    if trace is None:
        raise HTTPException(404, "Unidad logística no encontrada.")
    return HandlingUnitTraceOut.model_validate(trace)


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
        select(InventoryHandlingUnitModel).where(InventoryHandlingUnitModel.id == handling_unit_id)
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
    "/warehouses/{warehouse_id}/movements",
    response_model=list[InventoryMovementHistoryOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_warehouse_movements(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    limit: int = Query(10, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    movement_type: str | None = Query(None, min_length=1, max_length=30),
    period_from: date | None = None,
    period_to: date | None = None,
    q: str | None = Query(None, max_length=120),
    lot_code: str | None = Query(None, max_length=120),
    source_reference: str | None = Query(None, max_length=160),
    direction: str | None = Query(None, pattern="^(incoming|outgoing|internal)$"),
) -> list[InventoryMovementHistoryOut]:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    if period_from and period_to and period_from > period_to:
        raise HTTPException(422, "La fecha inicial debe ser anterior o igual a la final.")
    items = await _use_cases(session).list_movements(
        company_id=company_id,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset,
        movement_type=movement_type,
        period_from=period_from,
        period_to=period_to,
        query=q,
        lot_code=lot_code,
        source_reference=source_reference,
        direction=direction,
    )
    return [InventoryMovementHistoryOut.model_validate(item) for item in items]


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

"""Atomic, idempotent location assignment for one receipt lot and product."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
    authorize_warehouse_assignment,
    effective_company_id,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_inventory_use_cases,
    require_permission,
)
from app.api.v1.schemas.inventory_putaway_group import (
    ConfirmedPutawayAllocationOut,
    PutawayGroupConfirmIn,
    PutawayGroupConfirmOut,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryApplicationError, InventoryUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.inventory import InventoryOperationError, StockStatus
from app.domain.entities.inventory_release import (
    ReleaseRequirement,
    handling_unit_release_requirements,
)
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)

router = APIRouter(prefix="/inventory/putaway-groups", tags=["inventory"])


def _putaway_destination_status(
    *,
    is_partial: bool,
    measurement_status: str,
    measurement_source: str,
    expiry_date: date | None,
    label_confirmation_required: bool,
    label_confirmed: bool,
    today: date | None = None,
    retaceo_readiness_error: str | None = None,
    release_requirements: Iterable[str] | None = None,
) -> str:
    if release_requirements is not None:
        return "quarantine" if is_partial or release_requirements else "available"
    if today is None:
        raise ValueError("today is required when release requirements are not preloaded")
    requirements = handling_unit_release_requirements(
        is_partial=is_partial,
        measurement_status=measurement_status,
        measurement_source=measurement_source,
        expiry_date=expiry_date,
        today=today,
        label_confirmation_required=label_confirmation_required,
        label_confirmed=label_confirmed,
        retaceo_readiness_error=retaceo_readiness_error,
    )
    if requirements:
        return "quarantine"
    return "available"


def _requirements_after_partial_putaway(
    release_requirements: Iterable[str], *, label_confirmation_required: bool
) -> tuple[str, ...]:
    changed_requirements = [ReleaseRequirement.MEASUREMENT.value]
    if label_confirmation_required:
        changed_requirements.append(ReleaseRequirement.LABEL.value)
    return tuple(dict.fromkeys((*release_requirements, *changed_requirements)))


def _group_reference(
    company_id: uuid.UUID, body: PutawayGroupConfirmIn
) -> tuple[str, str, list[str]]:
    """Build stable persisted references for the group and its allocation movements."""
    key_digest = hashlib.sha256(f"{company_id}:{body.idempotency_key}".encode()).hexdigest()
    canonical_payload = body.model_dump(mode="json", exclude={"idempotency_key"})
    fingerprint = hashlib.sha256(
        json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    reference = f"putaway-group:{key_digest}:{fingerprint}"
    movement_keys = [f"putaway:{key_digest}:{index:03d}" for index in range(len(body.allocations))]
    return key_digest, reference, movement_keys


async def _lock_group_key(session: SessionDep, company_id: uuid.UUID, key_digest: str) -> None:
    lock_key = int.from_bytes(
        hashlib.sha256(f"putaway-group:{company_id}:{key_digest}".encode()).digest()[:8],
        byteorder="big",
        signed=True,
    )
    await session.execute(select(func.pg_advisory_xact_lock(lock_key)))


async def _load_replay_movements(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    key_digest: str,
    reference: str,
    movement_keys: list[str],
) -> dict[str, InventoryMovementModel] | None:
    movements = list(
        (
            await session.scalars(
                select(InventoryMovementModel)
                .where(
                    InventoryMovementModel.company_id == company_id,
                    InventoryMovementModel.source_reference.like(f"putaway-group:{key_digest}:%"),
                )
                .order_by(InventoryMovementModel.idempotency_key)
                .with_for_update()
            )
        ).all()
    )
    if not movements:
        return None
    if any(row.source_reference != reference for row in movements):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La clave de idempotencia ya se usó con otra asignación de bodega.",
        )

    by_key = {row.idempotency_key: row for row in movements}
    if len(by_key) != len(movement_keys) or set(by_key) != set(movement_keys):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El grupo de ubicación tiene un historial incompleto; no se repetirá parcialmente.",
        )
    return by_key


async def _load_replay_lines(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    by_key: dict[str, InventoryMovementModel],
) -> tuple[
    dict[str, InventoryMovementLineModel],
    set[uuid.UUID],
    set[uuid.UUID],
]:
    warehouse_ids: set[uuid.UUID] = set()
    handling_unit_ids: set[uuid.UUID] = set()
    replay_lines: dict[str, InventoryMovementLineModel] = {}
    for movement in by_key.values():
        lines = list(
            (
                await session.scalars(
                    select(InventoryMovementLineModel)
                    .where(
                        InventoryMovementLineModel.company_id == company_id,
                        InventoryMovementLineModel.movement_id == movement.id,
                    )
                    .order_by(InventoryMovementLineModel.line_number)
                )
            ).all()
        )
        if len(lines) != 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El movimiento guardado no coincide con la asignación del grupo.",
            )
        line = lines[0]
        replay_lines[movement.idempotency_key] = line
        if line.from_warehouse_id is not None:
            warehouse_ids.add(line.from_warehouse_id)
        if line.to_warehouse_id is not None:
            warehouse_ids.add(line.to_warehouse_id)
        if line.handling_unit_id is not None:
            handling_unit_ids.add(line.handling_unit_id)
    return replay_lines, warehouse_ids, handling_unit_ids


async def _authorize_replay_scope(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    current: CurrentUser,
    warehouse_ids: set[uuid.UUID],
    handling_unit_ids: set[uuid.UUID],
) -> None:
    if handling_unit_ids:
        current_warehouses = (
            (
                await session.execute(
                    select(InventoryHandlingUnitModel.warehouse_id).where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id.in_(handling_unit_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        warehouse_ids.update(current_warehouses)

    branch_rows = list(
        (
            await session.execute(
                select(Warehouse.id, Warehouse.branch_id).where(
                    Warehouse.company_id == company_id,
                    Warehouse.id.in_(warehouse_ids),
                )
            )
        ).all()
    )
    if {row.id for row in branch_rows} != warehouse_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La ubicación guardada no está disponible.")
    for _warehouse_id, branch_id in sorted(branch_rows, key=lambda row: str(row.id)):
        await resolve_branch_scope(session, current, company_id, branch_id)
        await authorize_warehouse_assignment(session, current, company_id, _warehouse_id)


async def _build_replay_allocations(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    body: PutawayGroupConfirmIn,
    by_key: dict[str, InventoryMovementModel],
    movement_keys: list[str],
    replay_lines: dict[str, InventoryMovementLineModel],
) -> list[ConfirmedPutawayAllocationOut]:
    confirmed: list[ConfirmedPutawayAllocationOut] = []
    for index, allocation in enumerate(body.allocations):
        movement = by_key[movement_keys[index]]
        line = replay_lines[movement.idempotency_key]
        if (
            line.to_location_id != allocation.destination_location_id
            or line.quantity_base != allocation.quantity_base
            or line.inventory_item_id != body.inventory_item_id
            or line.inventory_lot_detail_id != body.inventory_lot_detail_id
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El movimiento guardado no coincide con la asignación del grupo.",
            )
        handling_unit = await session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == line.handling_unit_id,
            )
        )
        destination_location_code = await session.scalar(
            select(Location.code).where(Location.id == allocation.destination_location_id)
        )
        if handling_unit is None or destination_location_code is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La unidad logística o el destino guardado ya no están disponibles para consulta.",
            )
        detail_code = await session.scalar(
            select(InventoryLotDetailModel.code).where(
                InventoryLotDetailModel.company_id == company_id,
                InventoryLotDetailModel.id == body.inventory_lot_detail_id,
            )
        )
        confirmed.append(
            ConfirmedPutawayAllocationOut.model_validate(
                {
                    "inventory_lot_detail_id": body.inventory_lot_detail_id,
                    "receipt_lot_detail_code": detail_code or "",
                    "source_handling_unit_id": allocation.handling_unit_id,
                    "handling_unit_id": line.handling_unit_id,
                    "handling_unit_code": handling_unit.code,
                    "movement_id": movement.id,
                    "destination_location_id": allocation.destination_location_id,
                    "destination_location_code": destination_location_code,
                    "quantity_base": line.quantity_base,
                    "stock_status": line.to_stock_status,
                    "measurement_status": line.measurement_status,
                    "measurement_source": handling_unit.measurement_source,
                }
            )
        )
    return confirmed


async def _replay_if_present(
    session: SessionDep,
    *,
    company_id: uuid.UUID,
    body: PutawayGroupConfirmIn,
    key_digest: str,
    reference: str,
    movement_keys: list[str],
    current: CurrentUser,
) -> PutawayGroupConfirmOut | None:
    by_key = await _load_replay_movements(
        session,
        company_id=company_id,
        key_digest=key_digest,
        reference=reference,
        movement_keys=movement_keys,
    )
    if by_key is None:
        return None
    # A retry is still a read of the persisted warehouse operation. Authorize
    # both the historical endpoints and the handling units' current locations
    # before returning any part of the saved response.
    replay_lines, warehouse_ids, handling_unit_ids = await _load_replay_lines(
        session, company_id=company_id, by_key=by_key
    )
    await _authorize_replay_scope(
        session,
        company_id=company_id,
        current=current,
        warehouse_ids=warehouse_ids,
        handling_unit_ids=handling_unit_ids,
    )
    confirmed = await _build_replay_allocations(
        session,
        company_id=company_id,
        body=body,
        by_key=by_key,
        movement_keys=movement_keys,
        replay_lines=replay_lines,
    )

    return PutawayGroupConfirmOut(
        idempotency_key=body.idempotency_key,
        receipt_lot_id=body.receipt_lot_id,
        inventory_lot_detail_id=body.inventory_lot_detail_id,
        receipt_lot_detail_code=(
            await session.scalar(
                select(InventoryLotDetailModel.code).where(
                    InventoryLotDetailModel.company_id == company_id,
                    InventoryLotDetailModel.id == body.inventory_lot_detail_id,
                )
            )
            or ""
        ),
        inventory_item_id=body.inventory_item_id,
        total_quantity_base=sum(
            (allocation.quantity_base for allocation in body.allocations), Decimal("0")
        ),
        allocations=confirmed,
        replayed=True,
    )


async def _validate_group(
    *,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    body: PutawayGroupConfirmIn,
) -> tuple[
    dict[uuid.UUID, InventoryHandlingUnitModel],
    dict[uuid.UUID, Location],
    uuid.UUID | None,
    bool,
    str,
]:
    lot, lot_details = await _load_lot_detail(session, company_id, body)
    unit_by_id = await _load_group_sources(session, company_id, body)
    locations, warehouse_id, branch_id = await _load_group_locations(
        session=session,
        current=current,
        company_id=company_id,
        units=unit_by_id,
        body=body,
    )
    _validate_receiving_sources(unit_by_id.values(), locations)
    _validate_group_destinations(body, locations, warehouse_id)
    _validate_allocations(unit_by_id, body)
    await _validate_lot_quantity(session, company_id, body, lot, lot_details)
    return unit_by_id, locations, branch_id, lot.label_confirmation_required, lot_details[0].code


async def _load_lot_detail(
    session: SessionDep,
    company_id: uuid.UUID,
    body: PutawayGroupConfirmIn,
) -> tuple[InventoryLotModel, list[InventoryLotDetailModel]]:
    lot = await session.scalar(
        select(InventoryLotModel)
        .where(
            InventoryLotModel.company_id == company_id,
            InventoryLotModel.id == body.receipt_lot_id,
        )
        .with_for_update()
    )
    if lot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote de recepción no encontrado.")

    lot_details = list(
        await session.scalars(
            select(InventoryLotDetailModel)
            .where(
                InventoryLotDetailModel.company_id == company_id,
                InventoryLotDetailModel.inventory_lot_id == body.receipt_lot_id,
                InventoryLotDetailModel.id == body.inventory_lot_detail_id,
                InventoryLotDetailModel.inventory_item_id == body.inventory_item_id,
                InventoryLotDetailModel.accepted_quantity_base > 0,
            )
            .order_by(InventoryLotDetailModel.id)
            .with_for_update()
        )
    )
    if not lot_details:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El producto no forma parte de la recepción aceptada de este lote.",
        )
    return lot, lot_details


async def _load_group_sources(
    session: SessionDep,
    company_id: uuid.UUID,
    body: PutawayGroupConfirmIn,
) -> dict[uuid.UUID, InventoryHandlingUnitModel]:
    handling_unit_ids = {allocation.handling_unit_id for allocation in body.allocations}
    units = list(
        (
            await session.scalars(
                select(InventoryHandlingUnitModel)
                .where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.inventory_lot_id == body.receipt_lot_id,
                    InventoryHandlingUnitModel.inventory_lot_detail_id
                    == body.inventory_lot_detail_id,
                    InventoryHandlingUnitModel.inventory_item_id == body.inventory_item_id,
                    InventoryHandlingUnitModel.id.in_(handling_unit_ids),
                )
                .order_by(InventoryHandlingUnitModel.id)
            )
        ).all()
    )
    unit_by_id = {unit.id: unit for unit in units}
    if set(unit_by_id) != handling_unit_ids:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Una unidad logística no pertenece a la línea de recepción seleccionada.",
        )

    allocated_by_unit: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for allocation in body.allocations:
        allocated_by_unit[allocation.handling_unit_id] += allocation.quantity_base
    for unit_id, unit in unit_by_id.items():
        if unit.closed_at is not None or unit.stock_status != "quarantine":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Solo se pueden ubicar unidades abiertas que sigan en cuarentena.",
            )
        if allocated_by_unit[unit_id] > unit.quantity_base:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La cantidad asignada supera lo que queda en la unidad logística.",
            )
    return unit_by_id


async def _load_group_locations(
    *,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    units: dict[uuid.UUID, InventoryHandlingUnitModel],
    body: PutawayGroupConfirmIn,
) -> tuple[dict[uuid.UUID, Location], uuid.UUID, uuid.UUID | None]:
    warehouse_ids = {unit.warehouse_id for unit in units.values()}
    destination_ids = {allocation.destination_location_id for allocation in body.allocations}
    source_locations = list(
        (
            await session.scalars(
                select(Location).where(
                    Location.id.in_({unit.location_id for unit in units.values()}),
                    Location.warehouse_id.in_(warehouse_ids),
                )
            )
        ).all()
    )
    destination_locations = list(
        (await session.scalars(select(Location).where(Location.id.in_(destination_ids)))).all()
    )
    location_by_id = {
        location.id: location for location in source_locations + destination_locations
    }
    if len(warehouse_ids) != 1 or not destination_ids.issubset(location_by_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Todas las unidades y destinos deben pertenecer a una sola bodega.",
        )
    warehouse_id = next(iter(warehouse_ids))
    warehouse = await session.scalar(
        select(Warehouse).where(
            Warehouse.id == warehouse_id,
            Warehouse.company_id == company_id,
            Warehouse.is_active.is_(True),
            Warehouse.deleted_at.is_(None),
        )
    )
    if warehouse is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "La bodega de recepción no está activa.")
    await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse.id)
    return location_by_id, warehouse_id, warehouse.branch_id


def _validate_receiving_sources(
    units: Iterable[InventoryHandlingUnitModel], locations: dict[uuid.UUID, Location]
) -> None:
    unit_rows = list(units)
    if any(unit.location_id not in locations for unit in unit_rows):
        raise HTTPException(status.HTTP_409_CONFLICT, "La ubicación de origen no está disponible.")
    if any(
        locations[unit.location_id].location_type != "receiving"
        or locations[unit.location_id].deleted_at is not None
        or not locations[unit.location_id].is_active
        for unit in unit_rows
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La asignación agrupada solo admite unidades pendientes en una ubicación de recepción.",
        )


def _validate_group_destinations(
    body: PutawayGroupConfirmIn,
    locations: dict[uuid.UUID, Location],
    warehouse_id: uuid.UUID,
) -> None:
    destination_ids = {allocation.destination_location_id for allocation in body.allocations}
    for destination_id in destination_ids:
        destination = locations[destination_id]
        if (
            destination.warehouse_id != warehouse_id
            or destination.deleted_at is not None
            or not destination.is_active
            or destination.lifecycle_status != "active"
            or not destination.storage_eligible
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cada destino debe estar activo, habilitado para almacenamiento y en la bodega de origen.",
            )


def _validate_allocations(
    unit_by_id: dict[uuid.UUID, InventoryHandlingUnitModel],
    body: PutawayGroupConfirmIn,
) -> None:
    for allocation in body.allocations:
        unit = unit_by_id[allocation.handling_unit_id]
        if unit.location_id == allocation.destination_location_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La unidad ya está en esa ubicación.",
            )


async def _validate_lot_quantity(
    session: SessionDep,
    company_id: uuid.UUID,
    body: PutawayGroupConfirmIn,
    lot: InventoryLotModel,
    lot_details: list[InventoryLotDetailModel],
) -> None:
    active_quantity = await session.scalar(
        select(func.coalesce(func.sum(InventoryHandlingUnitModel.quantity_base), 0)).where(
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.inventory_lot_id == body.receipt_lot_id,
            InventoryHandlingUnitModel.inventory_lot_detail_id == body.inventory_lot_detail_id,
            InventoryHandlingUnitModel.inventory_item_id == body.inventory_item_id,
            InventoryHandlingUnitModel.closed_at.is_(None),
        )
    )
    detail = next((row for row in lot_details if row.id == body.inventory_lot_detail_id), None)
    if detail is None or Decimal(str(active_quantity or 0)) > detail.accepted_quantity_base:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La cantidad activa supera lo aceptado para esta línea de recepción.",
        )


def _validate_lot_detail_totals(
    accepted_by_detail: dict[uuid.UUID, Decimal],
    active_by_detail: dict[uuid.UUID, Decimal],
    active_without_detail: Decimal,
    *,
    require_line_origin: bool,
) -> None:
    if require_line_origin and active_without_detail > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La recepción nueva tiene unidades sin vínculo a su línea de compra.",
        )
    for detail_id, quantity in active_by_detail.items():
        accepted = accepted_by_detail.get(detail_id)
        if accepted is None or quantity > accepted:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La cantidad de una línea supera lo aceptado en la recepción.",
            )
    active_total = sum(active_by_detail.values(), active_without_detail)
    accepted_total = sum(accepted_by_detail.values(), Decimal("0"))
    if active_total > accepted_total:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La cantidad de unidades del lote supera la cantidad aceptada en la recepción.",
        )


@router.post(
    "/confirm",
    response_model=PutawayGroupConfirmOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def confirm_putaway_group(
    body: PutawayGroupConfirmIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    inventory: Annotated[InventoryUseCases, Depends(get_inventory_use_cases)],
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> PutawayGroupConfirmOut:
    company_id = effective_company_id(request)
    allowed = await checker.execute(current.id, company_id, "inventory:move")
    if not allowed.allowed:
        raise AuthorizationError("Permiso requerido: inventory:move", code="forbidden")

    key_digest, reference, movement_keys = _group_reference(company_id, body)
    try:
        async with session.begin_nested():
            # The shared order is company valuation, physical scope, then handling units.
            await SqlAlchemyInventoryValuationRepository(session).lock(company_id)
            await _lock_group_key(session, company_id, key_digest)
            replay = await _replay_if_present(
                session,
                company_id=company_id,
                body=body,
                key_digest=key_digest,
                reference=reference,
                movement_keys=movement_keys,
                current=current,
            )
            if replay is not None:
                return replay

            (
                unit_by_id,
                locations,
                branch_id,
                label_confirmation_required,
                lot_details_code,
            ) = await _validate_group(
                session=session,
                current=current,
                company_id=company_id,
                body=body,
            )
            warehouse_id = next(iter(unit_by_id.values())).warehouse_id
            release_units = await inventory.list_handling_units(
                company_id=company_id,
                warehouse_id=warehouse_id,
                item_id=body.inventory_item_id,
                stock_status=StockStatus.QUARANTINE,
            )
            release_requirements_by_unit = {
                row["id"]: tuple(row.get("release_requirements", ())) for row in release_units
            }
            remaining_by_unit = {
                unit_id: unit.quantity_base for unit_id, unit in unit_by_id.items()
            }
            confirmed: list[ConfirmedPutawayAllocationOut] = []
            for index, allocation in enumerate(body.allocations):
                unit = unit_by_id[allocation.handling_unit_id]
                is_partial = allocation.quantity_base < remaining_by_unit[unit.id]
                target_status = _putaway_destination_status(
                    is_partial=is_partial,
                    measurement_status=unit.measurement_status,
                    measurement_source=unit.measurement_source,
                    expiry_date=unit.expiry_date,
                    label_confirmation_required=False,
                    label_confirmed=True,
                    release_requirements=release_requirements_by_unit.get(unit.id, ()),
                )
                movement = await inventory.post_movement(
                    company_id=company_id,
                    idempotency_key=movement_keys[index],
                    movement_type="putaway",
                    source_reference=reference,
                    lines=[
                        {
                            "inventory_item_id": body.inventory_item_id,
                            "handling_unit_id": allocation.handling_unit_id,
                            "from_location_id": unit.location_id,
                            "to_location_id": allocation.destination_location_id,
                            "from_stock_status": "quarantine",
                            "to_stock_status": target_status,
                            "quantity_base": allocation.quantity_base,
                        }
                    ],
                    actor_id=current.id,
                )
                line = movement["lines"][0]
                remaining_by_unit[unit.id] -= allocation.quantity_base
                if is_partial:
                    # A split revises the physical identity and estimate for the remainder.
                    # Later allocations in this same transaction must use that fresh state,
                    # not the pre-split eligibility loaded before the loop.
                    release_requirements_by_unit[unit.id] = _requirements_after_partial_putaway(
                        release_requirements_by_unit.get(unit.id, ()),
                        label_confirmation_required=label_confirmation_required,
                    )
                handling_unit_result = await session.scalar(
                    select(InventoryHandlingUnitModel).where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id == line["handling_unit_id"],
                    )
                )
                destination_location = locations[allocation.destination_location_id]
                if handling_unit_result is None:
                    raise HTTPException(  # noqa: TRY301
                        status.HTTP_409_CONFLICT,
                        "No se pudo recuperar la unidad logística resultante.",
                    )
                confirmed.append(
                    ConfirmedPutawayAllocationOut.model_validate(
                        {
                            "inventory_lot_detail_id": body.inventory_lot_detail_id,
                            "receipt_lot_detail_code": lot_details_code,
                            "source_handling_unit_id": allocation.handling_unit_id,
                            "handling_unit_id": line["handling_unit_id"],
                            "handling_unit_code": handling_unit_result.code,
                            "movement_id": movement["id"],
                            "destination_location_id": allocation.destination_location_id,
                            "destination_location_code": destination_location.code,
                            "quantity_base": line["quantity_base"],
                            "stock_status": target_status,
                            "measurement_status": line["measurement_status"],
                            "measurement_source": handling_unit_result.measurement_source,
                        }
                    )
                )

            response = PutawayGroupConfirmOut(
                idempotency_key=body.idempotency_key,
                receipt_lot_id=body.receipt_lot_id,
                inventory_lot_detail_id=body.inventory_lot_detail_id,
                receipt_lot_detail_code=lot_details_code,
                inventory_item_id=body.inventory_item_id,
                total_quantity_base=sum(
                    (allocation.quantity_base for allocation in body.allocations), Decimal("0")
                ),
                allocations=confirmed,
                replayed=False,
            )
            await audit.record(
                action="CONFIRM",
                user_id=current.id,
                company_id=company_id,
                branch_id=branch_id,
                resource_type="inventory_putaway_groups",
                resource_id=key_digest,
                after_state=jsonable_encoder(response),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                required=True,
            )
            return response
    except HTTPException:
        raise
    except (InventoryApplicationError, InventoryOperationError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail=getattr(exc, "message", str(exc)),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El inventario cambió durante la ubicación; recargue e intente de nuevo.",
        ) from exc

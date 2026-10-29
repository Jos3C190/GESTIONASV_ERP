"""PostgreSQL adapter for company-scoped, auditable inventory transfers."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.application.inventory import InventoryUseCases
from app.domain.entities.inventory_transfer import (
    TransferDomainError,
    require_dispatchable,
    require_preparation,
    require_receivable,
    validate_dispatch_quantity,
    validate_receipt_quantity,
)
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferCommandModel,
    InventoryTransferDemandAllocationModel,
    InventoryTransferDetailModel,
    InventoryTransferIncidentModel,
    InventoryTransferModel,
    InventoryTransferReceiptModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

_TRANSFERABLE_REQUEST_STATUSES = {"approved", "partially_quoted", "quoted", "partially_ordered", "completed"}
MAX_VEHICLE_CODE_LENGTH = 32


class SqlAlchemyInventoryTransferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _raise(message: str, code: str, status_code: int = 409) -> None:
        raise TransferDomainError(message, code=code, status_code=status_code)

    @staticmethod
    def _fingerprint(action: str, values: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"action": action, "values": values},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _advisory_key(company_id: uuid.UUID, action: str, key: str) -> int:
        digest = hashlib.blake2b(
            f"{company_id}:{action}:{key}".encode(), digest_size=8
        ).digest()
        return int.from_bytes(digest, byteorder="big", signed=True)

    async def _lock_idempotency(self, company_id: uuid.UUID, action: str, key: str) -> None:
        await self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    self._advisory_key(company_id, action, key)
                )
            )
        )

    async def _replay_command(
        self,
        *,
        company_id: uuid.UUID,
        action: str,
        key: str,
        fingerprint: str,
    ) -> dict[str, Any] | None:
        await self._lock_idempotency(company_id, action, key)
        command = await self._session.scalar(
            select(InventoryTransferCommandModel).where(
                InventoryTransferCommandModel.company_id == company_id,
                InventoryTransferCommandModel.action == action,
                InventoryTransferCommandModel.idempotency_key == key,
            )
        )
        if command is None:
            return None
        if command.request_fingerprint != fingerprint:
            self._raise(
                "La clave de idempotencia ya se usó con otro contenido.",
                "transfer_idempotency_conflict",
            )
        saved_response = (command.result or {}).get("response")
        if isinstance(saved_response, dict):
            return saved_response
        result = await self.get_transfer(company_id, command.transfer_id)
        if result is None:
            self._raise("El traslado de la operación repetida no existe.", "transfer_not_found", 404)
        return result

    async def _record_command(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        action: str,
        key: str,
        fingerprint: str,
        actor_id: uuid.UUID,
        result: dict[str, Any] | None = None,
    ) -> InventoryTransferCommandModel:
        command = InventoryTransferCommandModel(
            company_id=company_id,
            transfer_id=transfer_id,
            action=action,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            result=result or {},
            actor_id=actor_id,
            created_at=datetime.now(UTC),
        )
        self._session.add(command)
        await self._session.flush()
        return command

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): SqlAlchemyInventoryTransferRepository._json_value(item) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [SqlAlchemyInventoryTransferRepository._json_value(item) for item in value]
        return value

    async def _finish_command(
        self,
        command: InventoryTransferCommandModel,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
    ) -> dict[str, Any]:
        response = await self.get_transfer(company_id, transfer_id)
        if response is None:
            self._raise("No se pudo recuperar el traslado después de la operación.", "transfer_not_found", 404)
        command.result = {
            **(command.result or {}),
            "response": self._json_value(response),
        }
        await self._session.flush()
        return response

    async def _warehouse_pair(
        self,
        *,
        company_id: uuid.UUID,
        origin_id: uuid.UUID,
        destination_id: uuid.UUID,
    ) -> tuple[Warehouse, Warehouse]:
        rows = list(
            (
                await self._session.scalars(
                    select(Warehouse)
                    .where(
                        Warehouse.company_id == company_id,
                        Warehouse.id.in_([origin_id, destination_id]),
                        Warehouse.deleted_at.is_(None),
                    )
                    .order_by(Warehouse.id)
                    .with_for_update()
                )
            ).all()
        )
        by_id = {row.id: row for row in rows}
        origin, destination = by_id.get(origin_id), by_id.get(destination_id)
        if origin is None or destination is None:
            self._raise("No se encontraron las bodegas en la empresa seleccionada.", "transfer_warehouse_not_found", 404)
        if origin.id == destination.id:
            self._raise("El origen y el destino deben ser distintos.", "transfer_same_warehouse", 422)
        if not origin.is_active or origin.operational_status != "active" or origin.is_transit:
            self._raise("La bodega de origen no está habilitada para despachos.", "transfer_origin_invalid")
        if not origin.is_central:
            self._raise("El traslado a sucursal debe salir de la bodega central.", "transfer_origin_not_central", 422)
        if (
            not destination.is_active
            or destination.operational_status != "active"
            or destination.is_central
            or destination.is_transit
            or destination.branch_id is None
        ):
            self._raise("El destino debe ser una bodega activa de sucursal.", "transfer_destination_invalid", 422)
        source_branch = await self._session.scalar(
            select(Branch).where(
                Branch.id == origin.branch_id,
                Branch.company_id == company_id,
                Branch.is_headquarters.is_(True),
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
                Branch.deleted_at.is_(None),
            )
        )
        destination_branch = await self._session.scalar(
            select(Branch).where(
                Branch.id == destination.branch_id,
                Branch.company_id == company_id,
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
                Branch.deleted_at.is_(None),
            )
        )
        if source_branch is None or destination_branch is None:
            self._raise("El origen o destino no está asociado a una sucursal activa.", "transfer_branch_invalid")
        return origin, destination

    async def _validate_lines(
        self,
        *,
        company_id: uuid.UUID,
        origin: Warehouse,
        destination: Warehouse,
        lines: list[dict[str, Any]],
        exclude_transfer_id: uuid.UUID | None = None,
    ) -> None:
        units_by_id, request_details = await self._load_line_validation_context(
            company_id=company_id, lines=lines
        )
        for line in lines:
            item = await self._validate_transfer_line_identity(
                company_id=company_id,
                origin=origin,
                line=line,
                units_by_id=units_by_id,
            )
            self._validate_line_demand_allocations(
                destination=destination,
                line=line,
                item=item,
                request_details=request_details,
            )
        await self._validate_demand_allocation_totals(
            company_id=company_id,
            lines=lines,
            request_details=request_details,
            exclude_transfer_id=exclude_transfer_id,
        )

    async def _load_line_validation_context(
        self, *, company_id: uuid.UUID, lines: list[dict[str, Any]]
    ) -> tuple[
        dict[uuid.UUID, InventoryHandlingUnitModel],
        dict[uuid.UUID, tuple[PurchaseRequestDetailModel, PurchaseRequestModel]],
    ]:
        unit_ids = sorted({line["handling_unit_id"] for line in lines}, key=str)
        units = list(
            (
                await self._session.scalars(
                    select(InventoryHandlingUnitModel)
                    .where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id.in_(unit_ids),
                    )
                    .order_by(InventoryHandlingUnitModel.id)
                )
            ).all()
        )
        by_unit = {unit.id: unit for unit in units}
        request_detail_ids = sorted(
            {
                allocation["purchase_request_detail_id"]
                for line in lines
                for allocation in line.get("demand_allocations", [])
            },
            key=str,
        )
        request_details: dict[uuid.UUID, tuple[PurchaseRequestDetailModel, PurchaseRequestModel]] = {}
        if request_detail_ids:
            demand_rows = (
                await self._session.execute(
                    select(PurchaseRequestDetailModel, PurchaseRequestModel)
                    .join(
                        PurchaseRequestModel,
                        (PurchaseRequestModel.id == PurchaseRequestDetailModel.purchase_request_id)
                        & (PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id),
                    )
                    .where(
                        PurchaseRequestDetailModel.company_id == company_id,
                        PurchaseRequestDetailModel.id.in_(request_detail_ids),
                    )
                    .order_by(PurchaseRequestDetailModel.id)
                    .with_for_update(of=PurchaseRequestDetailModel)
                )
            ).all()
            request_details = {detail.id: (detail, request) for detail, request in demand_rows}
        return by_unit, request_details

    async def _validate_transfer_line_identity(
        self,
        *,
        company_id: uuid.UUID,
        origin: Warehouse,
        line: dict[str, Any],
        units_by_id: dict[uuid.UUID, InventoryHandlingUnitModel],
    ) -> InventoryItemModel:
        unit = units_by_id.get(line["handling_unit_id"])
        quantity = Decimal(line["quantity_base"])
        if unit is None or unit.closed_at is not None:
            self._raise("La unidad logística no existe o ya está cerrada.", "transfer_handling_unit_not_found", 404)
        if unit.warehouse_id != origin.id or unit.stock_status != "available" or unit.location_id is None:
            self._raise("La unidad debe estar disponible en la bodega central de origen.", "transfer_handling_unit_unavailable")
        if quantity > unit.quantity_base:
            self._raise("La cantidad planeada supera la existencia de la unidad.", "transfer_over_dispatch")
        item = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == unit.inventory_item_id,
            )
        )
        if item is None:
            self._raise("La identidad del producto no existe en esta empresa.", "transfer_item_not_found", 404)
        declared_lot_detail = line.get("inventory_lot_detail_id")
        if declared_lot_detail is not None and declared_lot_detail != unit.inventory_lot_detail_id:
            self._raise("El lote del traslado no coincide con el origen de la unidad.", "transfer_lot_mismatch", 422)
        line["inventory_item_id"] = unit.inventory_item_id
        line["inventory_lot_detail_id"] = unit.inventory_lot_detail_id
        return item

    def _validate_line_demand_allocations(
        self,
        *,
        destination: Warehouse,
        line: dict[str, Any],
        item: InventoryItemModel,
        request_details: dict[uuid.UUID, tuple[PurchaseRequestDetailModel, PurchaseRequestModel]],
    ) -> None:
        allocations = line.get("demand_allocations", [])
        quantity = Decimal(line["quantity_base"])
        allocated_sum = sum(
            (Decimal(allocation["allocated_quantity"]) for allocation in allocations),
            Decimal("0"),
        )
        if allocated_sum > quantity:
            self._raise(
                "La demanda vinculada supera la cantidad planeada de esta línea.",
                "transfer_demand_allocation_exceeds_line",
                422,
            )
        if allocated_sum < quantity and not str(line.get("excess_reason") or "").strip():
            self._raise(
                "Documente el motivo de la cantidad enviada sin una solicitud vinculada.",
                "transfer_excess_reason_required",
                422,
            )
        for allocation in allocations:
            linked = request_details.get(allocation["purchase_request_detail_id"])
            if linked is None:
                self._raise("La línea de solicitud no pertenece a esta empresa.", "transfer_request_detail_not_found", 404)
            request_detail, request = linked
            if (
                request.branch_id != destination.branch_id
                or request.status not in _TRANSFERABLE_REQUEST_STATUSES
                or item.product_id is None
                or request_detail.product_id != item.product_id
            ):
                self._raise("La solicitud no corresponde al producto o sucursal destino.", "transfer_request_scope_mismatch", 422)
            if request_detail.unit_id != item.base_unit_id:
                self._raise(
                    "La unidad solicitada no coincide con la unidad base; documente una conversión antes de asignar demanda.",
                    "transfer_request_unit_mismatch",
                    422,
                )
            if Decimal(allocation["allocated_quantity"]) > request_detail.quantity:
                self._raise("La asignación supera la cantidad solicitada.", "transfer_request_allocation_exceeds_requested")

    async def _validate_demand_allocation_totals(
        self,
        *,
        company_id: uuid.UUID,
        lines: list[dict[str, Any]],
        request_details: dict[uuid.UUID, tuple[PurchaseRequestDetailModel, PurchaseRequestModel]],
        exclude_transfer_id: uuid.UUID | None,
    ) -> None:
        request_detail_ids = sorted(
            {
                allocation["purchase_request_detail_id"]
                for line in lines
                for allocation in line.get("demand_allocations", [])
            },
            key=str,
        )
        if request_detail_ids:
            sums_stmt = (
                select(
                    InventoryTransferDemandAllocationModel.purchase_request_detail_id,
                    func.coalesce(func.sum(InventoryTransferDemandAllocationModel.allocated_quantity), 0),
                )
                .join(
                    InventoryTransferDetailModel,
                    (InventoryTransferDetailModel.company_id == InventoryTransferDemandAllocationModel.company_id)
                    & (InventoryTransferDetailModel.id == InventoryTransferDemandAllocationModel.transfer_detail_id),
                )
                .join(
                    InventoryTransferModel,
                    (InventoryTransferModel.company_id == InventoryTransferDetailModel.company_id)
                    & (InventoryTransferModel.id == InventoryTransferDetailModel.transfer_id),
                )
                .where(
                    InventoryTransferDemandAllocationModel.company_id == company_id,
                    InventoryTransferDemandAllocationModel.purchase_request_detail_id.in_(request_detail_ids),
                    InventoryTransferModel.status != "cancelled",
                )
                .group_by(InventoryTransferDemandAllocationModel.purchase_request_detail_id)
            )
            if exclude_transfer_id is not None:
                sums_stmt = sums_stmt.where(InventoryTransferModel.id != exclude_transfer_id)
            already_allocated = dict((await self._session.execute(sums_stmt)).all())
            requested_in_this_transfer: dict[uuid.UUID, Decimal] = {}
            for line in lines:
                for allocation in line.get("demand_allocations", []):
                    detail_id = allocation["purchase_request_detail_id"]
                    requested_in_this_transfer[detail_id] = (
                        requested_in_this_transfer.get(detail_id, Decimal("0"))
                        + Decimal(allocation["allocated_quantity"])
                    )
            for detail_id, planned in requested_in_this_transfer.items():
                requested_detail, _request = request_details[detail_id]
                if Decimal(already_allocated.get(detail_id, 0)) + planned > requested_detail.quantity:
                    self._raise("La demanda ya fue asignada a otro traslado.", "transfer_request_already_allocated")

    async def _validate_vehicle(
        self, company_id: uuid.UUID, vehicle_id: uuid.UUID | None
    ) -> None:
        if vehicle_id is None:
            return
        vehicle = await self._session.scalar(
            select(InventoryVehicleModel).where(
                InventoryVehicleModel.company_id == company_id,
                InventoryVehicleModel.id == vehicle_id,
                InventoryVehicleModel.status == "active",
            )
        )
        if vehicle is None:
            self._raise("Seleccione un vehículo activo de esta empresa.", "transfer_vehicle_unavailable", 422)

    async def _insert_details(
        self,
        *,
        company_id: uuid.UUID,
        transfer: InventoryTransferModel,
        lines: list[dict[str, Any]],
    ) -> None:
        for index, line in enumerate(lines, start=1):
            detail = InventoryTransferDetailModel(
                company_id=company_id,
                transfer_id=transfer.id,
                line_number=index,
                inventory_item_id=line["inventory_item_id"],
                inventory_lot_detail_id=line.get("inventory_lot_detail_id"),
                source_handling_unit_id=line["handling_unit_id"],
                quantity_planned=Decimal(line["quantity_base"]),
                notes=line.get("notes"),
                excess_reason=(str(line["excess_reason"]).strip() if line.get("excess_reason") else None),
            )
            self._session.add(detail)
            await self._session.flush()
            for allocation in line.get("demand_allocations", []):
                self._session.add(
                    InventoryTransferDemandAllocationModel(
                        company_id=company_id,
                        transfer_detail_id=detail.id,
                        purchase_request_detail_id=allocation["purchase_request_detail_id"],
                        allocated_quantity=Decimal(allocation["allocated_quantity"]),
                        quantity_dispatched=Decimal("0"),
                        quantity_received=Decimal("0"),
                    )
                )
        await self._session.flush()

    async def create_transfer(
        self,
        *,
        company_id: uuid.UUID,
        origin_warehouse_id: uuid.UUID,
        destination_warehouse_id: uuid.UUID,
        lines: list[dict[str, Any]],
        idempotency_key: str,
        actor_id: uuid.UUID,
        notes: str | None = None,
        vehicle_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        clean_lines = [dict(line) for line in lines]
        fingerprint = self._fingerprint(
            "create",
            {
                "origin_warehouse_id": origin_warehouse_id,
                "destination_warehouse_id": destination_warehouse_id,
                "vehicle_id": vehicle_id,
                "notes": notes,
                "lines": clean_lines,
            },
        )
        replay = await self._replay_command(
            company_id=company_id,
            action="create",
            key=idempotency_key,
            fingerprint=fingerprint,
        )
        if replay is not None:
            return replay
        origin, destination = await self._warehouse_pair(
            company_id=company_id,
            origin_id=origin_warehouse_id,
            destination_id=destination_warehouse_id,
        )
        await self._validate_lines(
            company_id=company_id, origin=origin, destination=destination, lines=clean_lines
        )
        await self._validate_vehicle(company_id, vehicle_id)
        transfer_id = uuid.uuid4()
        transfer = InventoryTransferModel(
            id=transfer_id,
            company_id=company_id,
            code=f"TR-{datetime.now(UTC):%Y%m%d}-{transfer_id.hex[:8].upper()}",
            origin_warehouse_id=origin.id,
            destination_warehouse_id=destination.id,
            vehicle_id=vehicle_id,
            status="preparation",
            notes=(notes.strip() if notes and notes.strip() else None),
            created_by_id=actor_id,
        )
        self._session.add(transfer)
        await self._session.flush()
        await self._insert_details(company_id=company_id, transfer=transfer, lines=clean_lines)
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="create",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def update_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        lines: list[dict[str, Any]],
        origin_warehouse_id: uuid.UUID | None = None,
        destination_warehouse_id: uuid.UUID | None = None,
        vehicle_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(
            "update",
            {
                "transfer_id": transfer_id,
                "origin_warehouse_id": origin_warehouse_id,
                "destination_warehouse_id": destination_warehouse_id,
                "vehicle_id": vehicle_id,
                "notes": notes,
                "lines": lines,
            },
        )
        replay = await self._replay_command(
            company_id=company_id, action="update", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(InventoryTransferModel.company_id == company_id, InventoryTransferModel.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        require_preparation(transfer.status)
        origin_id = origin_warehouse_id or transfer.origin_warehouse_id
        destination_id = destination_warehouse_id or transfer.destination_warehouse_id
        origin, destination = await self._warehouse_pair(
            company_id=company_id, origin_id=origin_id, destination_id=destination_id
        )
        clean_lines = [dict(line) for line in lines]
        await self._validate_lines(
            company_id=company_id,
            origin=origin,
            destination=destination,
            lines=clean_lines,
            exclude_transfer_id=transfer.id,
        )
        await self._validate_vehicle(company_id, vehicle_id)
        transfer.origin_warehouse_id = origin.id
        transfer.destination_warehouse_id = destination.id
        transfer.vehicle_id = vehicle_id
        transfer.notes = notes.strip() if notes and notes.strip() else None
        old_details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel).where(
                        InventoryTransferDetailModel.company_id == company_id,
                        InventoryTransferDetailModel.transfer_id == transfer.id,
                    )
                )
            ).all()
        )
        for detail in old_details:
            await self._session.delete(detail)
        await self._session.flush()
        await self._insert_details(company_id=company_id, transfer=transfer, lines=clean_lines)
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="update",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def cancel_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint("cancel", {"transfer_id": transfer_id})
        replay = await self._replay_command(
            company_id=company_id, action="cancel", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(InventoryTransferModel.company_id == company_id, InventoryTransferModel.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        require_preparation(transfer.status)
        transfer.status = "cancelled"
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="cancel",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def dispatch_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint("dispatch", {"transfer_id": transfer_id, "vehicle_id": vehicle_id})
        replay = await self._replay_command(
            company_id=company_id, action="dispatch", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(InventoryTransferModel.company_id == company_id, InventoryTransferModel.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel)
                    .where(
                        InventoryTransferDetailModel.company_id == company_id,
                        InventoryTransferDetailModel.transfer_id == transfer_id,
                    )
                    .order_by(InventoryTransferDetailModel.line_number)
                    .with_for_update()
                )
            ).all()
        )
        require_dispatchable(transfer.status, len(details))
        await self._warehouse_pair(
            company_id=company_id,
            origin_id=transfer.origin_warehouse_id,
            destination_id=transfer.destination_warehouse_id,
        )
        vehicle = await self._session.scalar(
            select(InventoryVehicleModel)
            .where(
                InventoryVehicleModel.company_id == company_id,
                InventoryVehicleModel.id == vehicle_id,
                InventoryVehicleModel.status == "active",
            )
            .with_for_update()
        )
        if vehicle is None:
            self._raise("Seleccione un vehículo activo de esta empresa.", "transfer_vehicle_unavailable", 422)
        if transfer.vehicle_id is not None and transfer.vehicle_id != vehicle.id:
            self._raise("El vehículo no coincide con el asignado a la preparación.", "transfer_vehicle_mismatch", 422)
        lines: list[dict[str, Any]] = []
        for detail in details:
            unit = await self._session.scalar(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == detail.source_handling_unit_id,
                )
            )
            if unit is None:
                self._raise("No se encuentra una unidad logística del traslado.", "transfer_handling_unit_not_found", 404)
            validate_dispatch_quantity(
                requested=Decimal(detail.quantity_planned), available=Decimal(unit.quantity_base)
            )
            lines.append(
                {
                    "inventory_item_id": detail.inventory_item_id,
                    "handling_unit_id": unit.id,
                    "from_location_id": unit.location_id,
                    "to_location_id": vehicle.transit_location_id,
                    "from_stock_status": "available",
                    "to_stock_status": "in_transit",
                    "quantity_base": detail.quantity_planned,
                }
            )
        now = datetime.now(UTC)
        movement = await InventoryUseCases(SqlAlchemyInventoryRepository(self._session)).post_movement(
            company_id=company_id,
            idempotency_key=f"transfer-dispatch:{transfer.id}:{idempotency_key}",
            movement_type="transfer",
            source_reference=f"inventory_transfer:{transfer.code}:dispatch",
            lines=lines,
            actor_id=actor_id,
        )
        for detail, movement_line in zip(details, movement["lines"], strict=True):
            detail.quantity_dispatched = detail.quantity_planned
            detail.transit_handling_unit_id = movement_line["handling_unit_id"]
            allocations = list(
                (
                    await self._session.scalars(
                        select(InventoryTransferDemandAllocationModel)
                        .where(
                            InventoryTransferDemandAllocationModel.company_id == company_id,
                            InventoryTransferDemandAllocationModel.transfer_detail_id == detail.id,
                        )
                        .order_by(InventoryTransferDemandAllocationModel.id)
                        .with_for_update()
                    )
                ).all()
            )
            for allocation in allocations:
                allocation.quantity_dispatched = allocation.allocated_quantity
        transfer.vehicle_id = vehicle.id
        transfer.status = "in_transit"
        transfer.dispatched_by_id = actor_id
        transfer.dispatched_at = now
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="dispatch",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
            result={"movement_id": str(movement["id"])},
        )
        transfer.dispatch_command_id = command.id
        transfer.dispatch_movement_id = movement["id"]
        await self._session.flush()
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def receive_transfer(  # noqa: C901 - coordinates one locked, atomic receipt workflow
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint("receive", {"transfer_id": transfer_id, "lines": lines})
        replay = await self._replay_command(
            company_id=company_id, action="receive", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(InventoryTransferModel.company_id == company_id, InventoryTransferModel.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        require_receivable(transfer.status)
        destination = await self._session.scalar(
            select(Warehouse).where(
                Warehouse.company_id == company_id,
                Warehouse.id == transfer.destination_warehouse_id,
                Warehouse.is_transit.is_(False),
                Warehouse.deleted_at.is_(None),
            )
        )
        if destination is None:
            self._raise("La bodega destino ya no está disponible.", "transfer_destination_invalid")
        detail_ids = sorted({line["transfer_detail_id"] for line in lines}, key=str)
        details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel)
                    .where(
                        InventoryTransferDetailModel.company_id == company_id,
                        InventoryTransferDetailModel.transfer_id == transfer.id,
                        InventoryTransferDetailModel.id.in_(detail_ids),
                    )
                    .order_by(InventoryTransferDetailModel.id)
                    .with_for_update()
                )
            ).all()
        )
        by_id = {detail.id: detail for detail in details}
        if len(by_id) != len(lines):
            self._raise("Una línea de recepción no pertenece a este traslado.", "transfer_detail_not_found", 404)
        inventory_lines: list[dict[str, Any]] = []
        ordered_details: list[InventoryTransferDetailModel] = []
        allocations_by_detail: dict[uuid.UUID, list[InventoryTransferDemandAllocationModel]] = {}
        for detail in details:
            allocations_by_detail[detail.id] = list(
                (
                    await self._session.scalars(
                        select(InventoryTransferDemandAllocationModel)
                        .where(
                            InventoryTransferDemandAllocationModel.company_id == company_id,
                            InventoryTransferDemandAllocationModel.transfer_detail_id == detail.id,
                        )
                        .order_by(InventoryTransferDemandAllocationModel.id)
                        .with_for_update()
                    )
                ).all()
            )
        for line in lines:
            detail = by_id[line["transfer_detail_id"]]
            remaining = Decimal(detail.quantity_dispatched) - Decimal(detail.quantity_received) - Decimal(detail.quantity_returned) - Decimal(detail.quantity_adjusted_out)
            quantity = Decimal(line["quantity_base"])
            validate_receipt_quantity(requested=quantity, remaining=remaining)
            if detail.transit_handling_unit_id is None:
                self._raise("La unidad logística pendiente no está asociada al tránsito.", "transfer_transit_unit_missing")
            unit = await self._session.scalar(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == detail.transit_handling_unit_id,
                )
            )
            if (
                unit is None
                or unit.warehouse_id != (await self._session.scalar(
                    select(InventoryVehicleModel.transit_warehouse_id).where(
                        InventoryVehicleModel.company_id == company_id,
                        InventoryVehicleModel.id == transfer.vehicle_id,
                    )
                ))
                or unit.stock_status != "in_transit"
                or unit.location_id is None
            ):
                self._raise("La unidad no se encuentra en el vehículo asociado al traslado.", "transfer_transit_unit_mismatch")
            target_location = await self._session.scalar(
                select(Location).where(
                    Location.id == line["destination_location_id"],
                    Location.warehouse_id == destination.id,
                    Location.is_active.is_(True),
                    Location.deleted_at.is_(None),
                    Location.lifecycle_status == "active",
                    Location.storage_eligible.is_(True),
                    Location.location_type != "virtual",
                )
            )
            if target_location is None:
                self._raise("El destino debe ser una ubicación receptora activa de la bodega destino.", "transfer_receipt_location_invalid", 422)
            inventory_lines.append(
                {
                    "inventory_item_id": detail.inventory_item_id,
                    "handling_unit_id": unit.id,
                    "from_location_id": unit.location_id,
                    "to_location_id": target_location.id,
                    "from_stock_status": "in_transit",
                    "to_stock_status": "quarantine",
                    "quantity_base": quantity,
                }
            )
            ordered_details.append(detail)

        movement = await InventoryUseCases(SqlAlchemyInventoryRepository(self._session)).post_movement(
            company_id=company_id,
            idempotency_key=f"transfer-receive:{transfer.id}:{idempotency_key}",
            movement_type="transfer",
            source_reference=f"inventory_transfer:{transfer.code}:receipt:{idempotency_key}",
            lines=inventory_lines,
            actor_id=actor_id,
        )
        now = datetime.now(UTC)
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="receive",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
            result={"movement_id": str(movement["id"])},
        )
        for detail, requested_line, movement_line in zip(
            ordered_details, lines, movement["lines"], strict=True
        ):
            qty = Decimal(requested_line["quantity_base"])
            detail.quantity_received = Decimal(detail.quantity_received) + qty
            unallocated_received = qty
            for allocation in allocations_by_detail[detail.id]:
                allocation_pending = (
                    Decimal(allocation.quantity_dispatched)
                    - Decimal(allocation.quantity_received)
                    - Decimal(allocation.quantity_adjusted_out)
                )
                assigned_receipt = min(unallocated_received, allocation_pending)
                if assigned_receipt > 0:
                    allocation.quantity_received = (
                        Decimal(allocation.quantity_received) + assigned_receipt
                    )
                    unallocated_received -= assigned_receipt
                if unallocated_received <= 0:
                    break
            if Decimal(detail.quantity_received) + Decimal(detail.quantity_returned) + Decimal(detail.quantity_adjusted_out) >= Decimal(detail.quantity_dispatched):
                detail.transit_handling_unit_id = None
            self._session.add(
                InventoryTransferReceiptModel(
                    company_id=company_id,
                    transfer_id=transfer.id,
                    transfer_detail_id=detail.id,
                    command_id=command.id,
                    movement_id=movement["id"],
                    handling_unit_id=movement_line["handling_unit_id"],
                    quantity_received=qty,
                    received_by_id=actor_id,
                    received_at=now,
                )
            )
        await self._session.flush()
        all_details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel).where(
                        InventoryTransferDetailModel.company_id == company_id,
                        InventoryTransferDetailModel.transfer_id == transfer.id,
                    )
                )
            ).all()
        )
        if all(
            Decimal(item.quantity_received) + Decimal(item.quantity_returned) + Decimal(item.quantity_adjusted_out)
            >= Decimal(item.quantity_dispatched)
            for item in all_details
        ):
            transfer.status = "received"
            transfer.received_by_id = actor_id
            transfer.received_at = now
        await self._session.flush()
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def open_incident(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        reason: str,
        evidence_reference: str | None = None,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(
            "incident", {"transfer_id": transfer_id, "reason": reason, "evidence_reference": evidence_reference}
        )
        replay = await self._replay_command(
            company_id=company_id, action="incident", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(InventoryTransferModel.company_id == company_id, InventoryTransferModel.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        if transfer.status != "in_transit":
            self._raise("Solo puede abrir una incidencia de un traslado en tránsito.", "transfer_incident_not_allowed")
        incident = await self._session.scalar(
            select(InventoryTransferIncidentModel).where(
                InventoryTransferIncidentModel.company_id == company_id,
                InventoryTransferIncidentModel.transfer_id == transfer.id,
                InventoryTransferIncidentModel.status == "open",
            )
        )
        if incident is not None:
            self._raise("El traslado ya tiene una incidencia abierta.", "transfer_incident_already_open")
        now = datetime.now(UTC)
        self._session.add(
            InventoryTransferIncidentModel(
                company_id=company_id,
                transfer_id=transfer.id,
                status="open",
                reason=reason,
                evidence_reference=(evidence_reference.strip() if evidence_reference else None),
                opened_by_id=actor_id,
                opened_at=now,
            )
        )
        transfer.status = "incident"
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="incident",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def resolve_incident(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        resolution: str,
        resolution_notes: str,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(
            "resolve", {"transfer_id": transfer_id, "resolution": resolution, "resolution_notes": resolution_notes}
        )
        replay = await self._replay_command(
            company_id=company_id, action="resolve", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(InventoryTransferModel.company_id == company_id, InventoryTransferModel.id == transfer_id)
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        if transfer.status != "incident":
            self._raise("El traslado no tiene una incidencia pendiente.", "transfer_incident_not_open")
        incident = await self._session.scalar(
            select(InventoryTransferIncidentModel)
            .where(
                InventoryTransferIncidentModel.company_id == company_id,
                InventoryTransferIncidentModel.transfer_id == transfer.id,
                InventoryTransferIncidentModel.status == "open",
            )
            .with_for_update()
        )
        if incident is None:
            self._raise("No se encontró la incidencia abierta.", "transfer_incident_not_found", 404)
        details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel)
                    .where(
                        InventoryTransferDetailModel.company_id == company_id,
                        InventoryTransferDetailModel.transfer_id == transfer.id,
                    )
                    .order_by(InventoryTransferDetailModel.id)
                    .with_for_update()
                )
            ).all()
        )
        pending = [
            detail
            for detail in details
            if Decimal(detail.quantity_dispatched)
            > Decimal(detail.quantity_received) + Decimal(detail.quantity_returned) + Decimal(detail.quantity_adjusted_out)
        ]
        has_adjusted_loss = any(Decimal(detail.quantity_adjusted_out) > 0 for detail in details)
        if resolution == "close_received" and has_adjusted_loss:
            self._raise(
                "Una pérdida documentada se cierra como 'Cerrado con ajuste', nunca como recibido.",
                "transfer_loss_cannot_be_marked_received",
            )
        if resolution == "close_received" and pending:
            self._raise(
                "No se puede cerrar recibido mientras quede cantidad sin recibir; una pérdida requiere un ajuste autorizado.",
                "transfer_incident_loss_adjustment_required",
            )
        if resolution == "resume_transit":
            if not pending:
                self._raise("No queda mercancía en tránsito; cierre la incidencia como recibida.", "transfer_no_pending_transit")
            for detail in pending:
                unit = await self._session.scalar(
                    select(InventoryHandlingUnitModel).where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id == detail.transit_handling_unit_id,
                    )
                )
                remaining = Decimal(detail.quantity_dispatched) - Decimal(detail.quantity_received) - Decimal(detail.quantity_returned) - Decimal(detail.quantity_adjusted_out)
                if unit is None or unit.stock_status != "in_transit" or Decimal(unit.quantity_base) < remaining:
                    self._raise(
                        "Confirme la cantidad realmente presente en el vehículo; la diferencia requiere un ajuste autorizado.",
                        "transfer_incident_quantity_unresolved",
                    )
            transfer.status = "in_transit"
        else:
            transfer.status = "received"
            transfer.received_by_id = actor_id
            transfer.received_at = datetime.now(UTC)
        now = datetime.now(UTC)
        incident.status = "resolved"
        incident.resolution = resolution
        incident.resolution_notes = resolution_notes.strip()
        incident.resolved_by_id = actor_id
        incident.resolved_at = now
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="resolve",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(
            command, company_id=company_id, transfer_id=transfer.id
        )

    async def _transfer_payload(self, transfer: InventoryTransferModel) -> dict[str, Any]:  # noqa: C901 - assembles the normalized transfer read projection
        origin, destination = await self._warehouse_pair_for_read(
            transfer.company_id, transfer.origin_warehouse_id, transfer.destination_warehouse_id
        )
        vehicle = None
        if transfer.vehicle_id is not None:
            record = await self._session.scalar(
                select(InventoryVehicleModel).where(
                    InventoryVehicleModel.company_id == transfer.company_id,
                    InventoryVehicleModel.id == transfer.vehicle_id,
                )
            )
            if record is not None:
                vehicle = {"id": record.id, "code": record.code, "name": record.name, "status": record.status}
        details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel)
                    .where(
                        InventoryTransferDetailModel.company_id == transfer.company_id,
                        InventoryTransferDetailModel.transfer_id == transfer.id,
                    )
                    .order_by(InventoryTransferDetailModel.line_number)
                )
            ).all()
        )
        item_ids = {detail.inventory_item_id for detail in details}
        item_rows = []
        if item_ids:
            item_rows = list(
                (
                    await self._session.execute(
                        select(
                            InventoryItemModel.id,
                            InventoryItemModel.product_id,
                            InventoryItemModel.variant_id,
                            InventoryItemModel.base_unit_id,
                            func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("sku"),
                            func.coalesce(ProductVariantModel.name_override, ProductModel.name).label("product_name"),
                            func.coalesce(CompanyUnitModel.alias, UnitModel.name).label("base_unit_name"),
                            UnitModel.symbol.label("base_unit_symbol"),
                        )
                        .outerjoin(
                            ProductVariantModel,
                            (ProductVariantModel.company_id == InventoryItemModel.company_id)
                            & (ProductVariantModel.id == InventoryItemModel.variant_id),
                        )
                        .join(
                            ProductModel,
                            (ProductModel.company_id == InventoryItemModel.company_id)
                            & (
                                ProductModel.id_product
                                == func.coalesce(
                                    InventoryItemModel.product_id,
                                    ProductVariantModel.product_id,
                                )
                            ),
                        )
                        .join(
                            CompanyUnitModel,
                            (CompanyUnitModel.company_id == InventoryItemModel.company_id)
                            & (CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id),
                        )
                        .join(UnitModel, UnitModel.id_unit == CompanyUnitModel.unit_id)
                        .where(
                            InventoryItemModel.company_id == transfer.company_id,
                            InventoryItemModel.id.in_(item_ids),
                        )
                    )
                ).all()
            )
        items_by_id = {row.id: row for row in item_rows}
        hu_ids = {detail.source_handling_unit_id for detail in details}
        hu_ids.update(detail.transit_handling_unit_id for detail in details if detail.transit_handling_unit_id)
        units_by_id: dict[uuid.UUID, InventoryHandlingUnitModel] = {}
        if hu_ids:
            units_by_id = {
                unit.id: unit
                for unit in (
                    await self._session.scalars(
                        select(InventoryHandlingUnitModel).where(
                            InventoryHandlingUnitModel.company_id == transfer.company_id,
                            InventoryHandlingUnitModel.id.in_(hu_ids),
                        )
                    )
                ).all()
            }
        lot_ids = {detail.inventory_lot_detail_id for detail in details if detail.inventory_lot_detail_id}
        lot_codes: dict[uuid.UUID, str] = {}
        if lot_ids:
            lot_codes = dict(
                (
                    await self._session.execute(
                        select(InventoryLotDetailModel.id, InventoryLotDetailModel.code).where(
                            InventoryLotDetailModel.company_id == transfer.company_id,
                            InventoryLotDetailModel.id.in_(lot_ids),
                        )
                    )
                ).all()
            )
        demand_rows: dict[uuid.UUID, list[dict[str, Any]]] = {}
        if details:
            rows = (
                await self._session.execute(
                    select(
                        InventoryTransferDemandAllocationModel.transfer_detail_id,
                        InventoryTransferDemandAllocationModel.purchase_request_detail_id,
                        InventoryTransferDemandAllocationModel.allocated_quantity,
                        InventoryTransferDemandAllocationModel.quantity_dispatched,
                        InventoryTransferDemandAllocationModel.quantity_received,
                        InventoryTransferDemandAllocationModel.quantity_adjusted_out,
                        PurchaseRequestModel.id.label("request_id"),
                        PurchaseRequestModel.code.label("request_code"),
                        PurchaseRequestModel.branch_id,
                        Branch.name.label("branch_name"),
                        PurchaseRequestDetailModel.quantity.label("quantity_requested"),
                    )
                    .join(
                        PurchaseRequestDetailModel,
                        (PurchaseRequestDetailModel.company_id == InventoryTransferDemandAllocationModel.company_id)
                        & (PurchaseRequestDetailModel.id == InventoryTransferDemandAllocationModel.purchase_request_detail_id),
                    )
                    .join(
                        PurchaseRequestModel,
                        (PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id)
                        & (PurchaseRequestModel.id == PurchaseRequestDetailModel.purchase_request_id),
                    )
                    .join(Branch, Branch.id == PurchaseRequestModel.branch_id)
                    .where(
                        InventoryTransferDemandAllocationModel.company_id == transfer.company_id,
                        InventoryTransferDemandAllocationModel.transfer_detail_id.in_([d.id for d in details]),
                    )
                )
            ).all()
            for row in rows:
                demand_rows.setdefault(row.transfer_detail_id, []).append(
                    {
                        "purchase_request_detail_id": row.purchase_request_detail_id,
                        "request_id": row.request_id,
                        "request_code": row.request_code,
                        "branch_id": row.branch_id,
                        "branch_name": row.branch_name,
                        "quantity_requested": row.quantity_requested,
                        "allocated_quantity": row.allocated_quantity,
                        "quantity_dispatched": row.quantity_dispatched,
                        "quantity_received": row.quantity_received,
                        "quantity_adjusted_out": row.quantity_adjusted_out,
                    }
                )
        receipt_rows = (
            await self._session.execute(
                select(InventoryTransferReceiptModel).where(
                    InventoryTransferReceiptModel.company_id == transfer.company_id,
                    InventoryTransferReceiptModel.transfer_id == transfer.id,
                ).order_by(InventoryTransferReceiptModel.received_at, InventoryTransferReceiptModel.id)
            )
        ).scalars().all()
        receipt_unit_ids = {receipt.handling_unit_id for receipt in receipt_rows}
        missing_receipt_unit_ids = receipt_unit_ids.difference(units_by_id)
        if missing_receipt_unit_ids:
            units_by_id.update(
                {
                    unit.id: unit
                    for unit in (
                        await self._session.scalars(
                            select(InventoryHandlingUnitModel).where(
                                InventoryHandlingUnitModel.company_id == transfer.company_id,
                                InventoryHandlingUnitModel.id.in_(missing_receipt_unit_ids),
                            )
                        )
                    ).all()
                }
            )
        incident_rows = (
            await self._session.execute(
                select(InventoryTransferIncidentModel).where(
                    InventoryTransferIncidentModel.company_id == transfer.company_id,
                    InventoryTransferIncidentModel.transfer_id == transfer.id,
                ).order_by(InventoryTransferIncidentModel.opened_at, InventoryTransferIncidentModel.id)
            )
        ).scalars().all()
        receipts_by_detail: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for receipt in receipt_rows:
            unit = units_by_id.get(receipt.handling_unit_id)
            receipts_by_detail.setdefault(receipt.transfer_detail_id, []).append(
                {
                    "id": receipt.id,
                    "movement_id": receipt.movement_id,
                    "handling_unit_id": receipt.handling_unit_id,
                    "handling_unit_code": unit.code if unit else None,
                    "quantity_received": receipt.quantity_received,
                    "received_by_id": receipt.received_by_id,
                    "received_at": receipt.received_at,
                }
            )
        detail_payloads: list[dict[str, Any]] = []
        for detail in details:
            item = items_by_id.get(detail.inventory_item_id)
            source_hu = units_by_id.get(detail.source_handling_unit_id)
            transit_hu = units_by_id.get(detail.transit_handling_unit_id) if detail.transit_handling_unit_id else None
            snapshot = (source_hu.packaging_snapshot if source_hu else None) or {}
            detail_payloads.append(
                {
                    "id": detail.id,
                    "line_number": detail.line_number,
                    "inventory_item_id": detail.inventory_item_id,
                    "product_id": item.product_id if item else None,
                    "variant_id": item.variant_id if item else None,
                    "sku": item.sku if item else None,
                    "product_name": item.product_name if item else "Producto no disponible",
                    "base_unit_id": item.base_unit_id if item else None,
                    "base_unit_name": item.base_unit_name if item else None,
                    "base_unit_symbol": item.base_unit_symbol if item else None,
                    "presentation_name": snapshot.get("name") or snapshot.get("packaging_name"),
                    "inventory_lot_detail_id": detail.inventory_lot_detail_id,
                    "inventory_lot_detail_code": lot_codes.get(detail.inventory_lot_detail_id),
                    "source_handling_unit_id": detail.source_handling_unit_id,
                    "source_handling_unit_code": source_hu.code if source_hu else None,
                    "transit_handling_unit_id": detail.transit_handling_unit_id,
                    "transit_handling_unit_code": transit_hu.code if transit_hu else None,
                    "quantity_planned": detail.quantity_planned,
                    "quantity_dispatched": detail.quantity_dispatched,
                    "quantity_received": detail.quantity_received,
                    "quantity_in_transit": Decimal(detail.quantity_dispatched) - Decimal(detail.quantity_received) - Decimal(detail.quantity_returned) - Decimal(detail.quantity_adjusted_out),
                    "quantity_adjusted_out": detail.quantity_adjusted_out,
                    "quantity_returned": detail.quantity_returned,
                    "excess_reason": detail.excess_reason,
                    "notes": detail.notes,
                    "demand_allocations": demand_rows.get(detail.id, []),
                    "receipts": receipts_by_detail.get(detail.id, []),
                }
            )
        return {
            "id": transfer.id,
            "company_id": transfer.company_id,
            "code": transfer.code,
            "origin_warehouse_id": transfer.origin_warehouse_id,
            "origin_warehouse_name": origin.name,
            "origin_branch_id": origin.branch_id,
            "destination_warehouse_id": transfer.destination_warehouse_id,
            "destination_warehouse_name": destination.name,
            "destination_branch_id": destination.branch_id,
            "vehicle": vehicle,
            "status": transfer.status,
            "notes": transfer.notes,
            "created_by_id": transfer.created_by_id,
            "created_at": transfer.created_at,
            "dispatched_by_id": transfer.dispatched_by_id,
            "dispatched_at": transfer.dispatched_at,
            "received_by_id": transfer.received_by_id,
            "received_at": transfer.received_at,
            "dispatch_movement_id": transfer.dispatch_movement_id,
            "lines": detail_payloads,
            "incidents": [
                {
                    "id": incident.id,
                    "status": incident.status,
                    "reason": incident.reason,
                    "evidence_reference": incident.evidence_reference,
                    "opened_by_id": incident.opened_by_id,
                    "opened_at": incident.opened_at,
                    "resolution": incident.resolution,
                    "resolution_notes": incident.resolution_notes,
                    "resolved_by_id": incident.resolved_by_id,
                    "resolved_at": incident.resolved_at,
                }
                for incident in incident_rows
            ],
        }

    async def _warehouse_pair_for_read(
        self, company_id: uuid.UUID, origin_id: uuid.UUID, destination_id: uuid.UUID
    ) -> tuple[Warehouse, Warehouse]:
        rows = list(
            (
                await self._session.scalars(
                    select(Warehouse).where(
                        Warehouse.company_id == company_id,
                        Warehouse.id.in_([origin_id, destination_id]),
                    )
                )
            ).all()
        )
        by_id = {row.id: row for row in rows}
        origin, destination = by_id.get(origin_id), by_id.get(destination_id)
        if origin is None or destination is None:
            self._raise("No se pudieron cargar las bodegas del traslado.", "transfer_warehouse_not_found", 404)
        return origin, destination

    async def get_transfer(self, company_id: uuid.UUID, transfer_id: uuid.UUID) -> dict[str, Any] | None:
        transfer = await self._session.scalar(
            select(InventoryTransferModel).where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
        )
        if transfer is None:
            return None
        return await self._transfer_payload(transfer)

    async def list_transfers(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        branch_ids: list[uuid.UUID] | None = None,
        status_filter: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> list[dict[str, Any]]:
        origin_warehouse = aliased(Warehouse)
        destination_warehouse = aliased(Warehouse)
        stmt = (
            select(InventoryTransferModel)
            .join(
                origin_warehouse,
                (origin_warehouse.company_id == InventoryTransferModel.company_id)
                & (origin_warehouse.id == InventoryTransferModel.origin_warehouse_id),
            )
            .join(
                destination_warehouse,
                (destination_warehouse.company_id == InventoryTransferModel.company_id)
                & (destination_warehouse.id == InventoryTransferModel.destination_warehouse_id),
            )
            .where(InventoryTransferModel.company_id == company_id)
        )
        if branch_id is not None:
            stmt = stmt.where(destination_warehouse.branch_id == branch_id)
        if branch_ids is not None:
            if not branch_ids:
                return []
            stmt = stmt.where(
                or_(
                    origin_warehouse.branch_id.in_(branch_ids),
                    destination_warehouse.branch_id.in_(branch_ids),
                )
            )
        if status_filter:
            stmt = stmt.where(InventoryTransferModel.status == status_filter)
        records = list(
            (
                await self._session.scalars(
                    stmt.order_by(InventoryTransferModel.created_at.desc(), InventoryTransferModel.id)
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).all()
        )
        output = []
        for record in records:
            payload = await self._transfer_payload(record)
            # Keep listing lightweight while retaining product names and demand context.
            output.append(payload)
        return output

    async def list_demand(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        product_id: int | None = None,
        search: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return each eligible request line once with its transfer progress."""
        stmt = (
            select(
                PurchaseRequestDetailModel,
                PurchaseRequestModel.code.label("request_code"),
                PurchaseRequestModel.branch_id,
                PurchaseRequestModel.request_date,
                PurchaseRequestModel.required_date,
                PurchaseRequestModel.status.label("request_status"),
                Branch.name.label("branch_name"),
                ProductModel.name.label("product_name"),
                ProductModel.sku.label("sku"),
                CompanyUnitModel.alias.label("unit_alias"),
                UnitModel.name.label("unit_name"),
                UnitModel.symbol.label("unit_symbol"),
                InventoryItemModel.id.label("inventory_item_id"),
            )
            .join(
                PurchaseRequestModel,
                (PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id)
                & (PurchaseRequestModel.id == PurchaseRequestDetailModel.purchase_request_id),
            )
            .join(
                Branch,
                (Branch.company_id == PurchaseRequestModel.company_id)
                & (Branch.id == PurchaseRequestModel.branch_id),
            )
            .join(
                ProductModel,
                (ProductModel.company_id == PurchaseRequestDetailModel.company_id)
                & (ProductModel.id_product == PurchaseRequestDetailModel.product_id),
            )
            .join(
                CompanyUnitModel,
                (CompanyUnitModel.company_id == PurchaseRequestDetailModel.company_id)
                & (CompanyUnitModel.unit_id == PurchaseRequestDetailModel.unit_id),
            )
            .join(UnitModel, UnitModel.id_unit == CompanyUnitModel.unit_id)
            .outerjoin(
                InventoryItemModel,
                (InventoryItemModel.company_id == PurchaseRequestDetailModel.company_id)
                & (InventoryItemModel.product_id == PurchaseRequestDetailModel.product_id)
                & (InventoryItemModel.base_unit_id == PurchaseRequestDetailModel.unit_id)
                & InventoryItemModel.is_active.is_(True),
            )
            .where(
                PurchaseRequestDetailModel.company_id == company_id,
                PurchaseRequestModel.status.in_(_TRANSFERABLE_REQUEST_STATUSES),
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
                Branch.deleted_at.is_(None),
            )
        )
        if branch_id is not None:
            stmt = stmt.where(PurchaseRequestModel.branch_id == branch_id)
        if product_id is not None:
            stmt = stmt.where(PurchaseRequestDetailModel.product_id == product_id)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    PurchaseRequestModel.code.ilike(pattern),
                    ProductModel.name.ilike(pattern),
                    ProductModel.sku.ilike(pattern),
                )
            )
        rows = (
            await self._session.execute(
                stmt.order_by(
                    PurchaseRequestModel.required_date.asc().nulls_last(),
                    PurchaseRequestModel.request_date,
                    PurchaseRequestModel.code,
                    PurchaseRequestDetailModel.id,
                ).limit(limit)
            )
        ).all()

        detail_ids = [row[0].id for row in rows]
        progress: dict[uuid.UUID, tuple[Decimal, Decimal, Decimal, Decimal]] = {}
        if detail_ids:
            progress_rows = (
                await self._session.execute(
                    select(
                        InventoryTransferDemandAllocationModel.purchase_request_detail_id,
                        func.coalesce(func.sum(InventoryTransferDemandAllocationModel.allocated_quantity), 0),
                        func.coalesce(func.sum(InventoryTransferDemandAllocationModel.quantity_dispatched), 0),
                        func.coalesce(func.sum(InventoryTransferDemandAllocationModel.quantity_received), 0),
                        func.coalesce(func.sum(InventoryTransferDemandAllocationModel.quantity_adjusted_out), 0),
                    )
                    .join(
                        InventoryTransferDetailModel,
                        (InventoryTransferDetailModel.company_id == InventoryTransferDemandAllocationModel.company_id)
                        & (InventoryTransferDetailModel.id == InventoryTransferDemandAllocationModel.transfer_detail_id),
                    )
                    .join(
                        InventoryTransferModel,
                        (InventoryTransferModel.company_id == InventoryTransferDetailModel.company_id)
                        & (InventoryTransferModel.id == InventoryTransferDetailModel.transfer_id),
                    )
                    .where(
                        InventoryTransferDemandAllocationModel.company_id == company_id,
                        InventoryTransferDemandAllocationModel.purchase_request_detail_id.in_(detail_ids),
                        InventoryTransferModel.status != "cancelled",
                    )
                    .group_by(InventoryTransferDemandAllocationModel.purchase_request_detail_id)
                )
            ).all()
            progress = {
                row[0]: (Decimal(row[1]), Decimal(row[2]), Decimal(row[3]), Decimal(row[4]))
                for row in progress_rows
            }

        output = []
        for row in rows:
            detail = row[0]
            assigned, dispatched, received, adjusted = progress.get(
                detail.id, (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
            )
            requested = Decimal(detail.quantity)
            output.append(
                {
                    "purchase_request_detail_id": detail.id,
                    "purchase_request_id": detail.purchase_request_id,
                    "request_code": row.request_code,
                    "request_status": row.request_status,
                    "branch_id": row.branch_id,
                    "branch_name": row.branch_name,
                    "request_date": row.request_date,
                    "required_date": row.required_date,
                    "product_id": detail.product_id,
                    "inventory_item_id": row.inventory_item_id,
                    "product_name": row.product_name,
                    "sku": row.sku,
                    "unit_id": detail.unit_id,
                    "unit_name": row.unit_alias or row.unit_name,
                    "unit_symbol": row.unit_symbol,
                    "quantity_requested": requested,
                    "quantity_assigned": assigned,
                    "quantity_dispatched": dispatched,
                    "quantity_in_transit": max(Decimal("0"), dispatched - received - adjusted),
                    "quantity_received": received,
                    "quantity_adjusted_out": adjusted,
                    "quantity_pending": max(Decimal("0"), requested - assigned),
                }
            )
        return output

    async def _transit_warehouse(self, company_id: uuid.UUID) -> Warehouse:
        warehouse = await self._session.scalar(
            select(Warehouse).where(
                Warehouse.company_id == company_id,
                Warehouse.is_transit.is_(True),
                Warehouse.deleted_at.is_(None),
            )
        )
        if warehouse is None:
            self._raise(
                "La empresa no tiene bodega técnica de tránsito; revise la matriz y aplique la migración.",
                "transit_warehouse_not_configured",
            )
        return warehouse

    async def create_vehicle(
        self,
        *,
        company_id: uuid.UUID,
        code: str,
        name: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        normalized_code = re.sub(r"\s+", "-", code.strip().upper())
        if not normalized_code or len(normalized_code) > MAX_VEHICLE_CODE_LENGTH:
            self._raise("El código de vehículo debe tener entre 1 y 32 caracteres.", "vehicle_code_invalid", 422)
        warehouse = await self._transit_warehouse(company_id)
        existing = await self._session.scalar(
            select(InventoryVehicleModel.id).where(
                InventoryVehicleModel.company_id == company_id,
                func.lower(InventoryVehicleModel.code) == normalized_code.lower(),
            )
        )
        if existing is not None:
            self._raise("Ya existe un vehículo con ese código en la empresa.", "vehicle_code_conflict", 409)
        location_id = uuid.uuid4()
        location_code = f"VEH-{normalized_code}"
        location = Location(
            id=location_id,
            warehouse_id=warehouse.id,
            code=location_code,
            area="Tránsito",
            aisle="VEHÍCULO",
            rack=normalized_code,
            level="ÚNICO",
            position="01",
            capacity_profile="transit",
            capacity_enforcement_mode="disabled",
            storage_eligible=False,
            location_type="vehicle",
            lifecycle_status="active",
            code_source="generated",
            is_active=True,
        )
        self._session.add(location)
        await self._session.flush()
        vehicle = InventoryVehicleModel(
            company_id=company_id,
            transit_warehouse_id=warehouse.id,
            transit_location_id=location.id,
            code=normalized_code,
            name=name.strip(),
            status="active",
            created_by_id=actor_id,
        )
        self._session.add(vehicle)
        await self._session.flush()
        return self._vehicle_payload(vehicle, warehouse.name)

    @staticmethod
    def _vehicle_payload(vehicle: InventoryVehicleModel, warehouse_name: str) -> dict[str, Any]:
        return {
            "id": vehicle.id,
            "company_id": vehicle.company_id,
            "code": vehicle.code,
            "name": vehicle.name,
            "status": vehicle.status,
            "transit_warehouse_id": vehicle.transit_warehouse_id,
            "transit_warehouse_name": warehouse_name,
            "transit_location_id": vehicle.transit_location_id,
            "created_at": vehicle.created_at,
        }

    async def list_vehicles(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(InventoryVehicleModel, Warehouse.name)
                .join(
                    Warehouse,
                    (Warehouse.company_id == InventoryVehicleModel.company_id)
                    & (Warehouse.id == InventoryVehicleModel.transit_warehouse_id),
                )
                .where(InventoryVehicleModel.company_id == company_id)
                .order_by(InventoryVehicleModel.code)
            )
        ).all()
        return [self._vehicle_payload(vehicle, warehouse_name) for vehicle, warehouse_name in rows]

    async def set_vehicle_status(
        self,
        *,
        company_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        status: str,
    ) -> dict[str, Any]:
        vehicle = await self._session.scalar(
            select(InventoryVehicleModel)
            .where(
                InventoryVehicleModel.company_id == company_id,
                InventoryVehicleModel.id == vehicle_id,
            )
            .with_for_update()
        )
        if vehicle is None:
            self._raise("Vehículo no encontrado.", "vehicle_not_found", 404)
        if status == "inactive":
            has_balance = await self._session.scalar(
                select(InventoryBalanceModel.id).where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.location_id == vehicle.transit_location_id,
                    InventoryBalanceModel.stock_status == "in_transit",
                    InventoryBalanceModel.quantity_base > 0,
                ).limit(1)
            )
            if has_balance is not None:
                self._raise("No puede desactivar el vehículo mientras tenga inventario en tránsito.", "vehicle_has_transit_inventory")
        vehicle.status = status
        await self._session.flush()
        warehouse = await self._session.get(Warehouse, vehicle.transit_warehouse_id)
        return self._vehicle_payload(vehicle, warehouse.name if warehouse else "Tránsito")


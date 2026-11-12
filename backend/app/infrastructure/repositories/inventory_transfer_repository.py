"""PostgreSQL adapter for company-scoped, auditable inventory transfers."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, NamedTuple, NoReturn

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.application.inventory import InventoryUseCases
from app.application.inventory_transfers.settings import policy_from
from app.domain.entities.inventory_transfer import (
    TransferDomainError,
    TransferPolicy,
    TransferRoute,
    TransferStatus,
    WarehouseFacts,
    approval_required,
    classify_route,
    require_cancellable,
    require_current_round,
    require_dispatchable,
    require_independent_approver,
    require_pending_approval,
    require_preparation,
    require_receivable,
    require_submittable,
    route_disabled_error,
    validate_dispatch_quantity,
    validate_receipt_quantity,
)
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import DriverModel, FleetVehicleModel
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
    InventoryTransferSettingsModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.purchase_request import (
    PurchaseRequestDetailModel,
    PurchaseRequestModel,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

_TRANSFERABLE_REQUEST_STATUSES = {
    "approved",
    "partially_quoted",
    "quoted",
    "partially_ordered",
    "completed",
}
MAX_VEHICLE_CODE_LENGTH = 32
#: Transfers that hold their handling units while they wait to be dispatched.
_COMMITTING_STATUSES = (TransferStatus.PENDING_APPROVAL, TransferStatus.APPROVED)


class _Pair(NamedTuple):
    origin: Warehouse
    destination: Warehouse
    route: TransferRoute
    policy: TransferPolicy


class SqlAlchemyInventoryTransferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _raise(message: str, code: str, status_code: int = 409) -> NoReturn:
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
        digest = hashlib.blake2b(f"{company_id}:{action}:{key}".encode(), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="big", signed=True)

    async def _lock_idempotency(self, company_id: uuid.UUID, action: str, key: str) -> None:
        await self._session.execute(
            select(func.pg_advisory_xact_lock(self._advisory_key(company_id, action, key)))
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
            self._raise(
                "El traslado de la operación repetida no existe.", "transfer_not_found", 404
            )
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
            return {
                str(key): SqlAlchemyInventoryTransferRepository._json_value(item)
                for key, item in value.items()
            }
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
            self._raise(
                "No se pudo recuperar el traslado después de la operación.",
                "transfer_not_found",
                404,
            )
        command.result = {
            **(command.result or {}),
            "response": self._json_value(response),
        }
        await self._session.flush()
        return response

    async def _policy(self, company_id: uuid.UUID, *, lock_share: bool = False) -> TransferPolicy:
        """The company's rules; ``lock_share`` keeps them from changing until commit."""
        statement = (
            select(InventoryTransferSettingsModel)
            .where(InventoryTransferSettingsModel.company_id == company_id)
            .execution_options(populate_existing=True)
        )
        if lock_share:
            statement = statement.with_for_update(read=True)
        return policy_from(await self._session.scalar(statement))

    async def get_policy(self, company_id: uuid.UUID) -> TransferPolicy:
        return await self._policy(company_id)

    @staticmethod
    def _facts(warehouse: Warehouse, branches: dict[uuid.UUID, Branch]) -> WarehouseFacts:
        branch = branches.get(warehouse.branch_id) if warehouse.branch_id is not None else None
        return WarehouseFacts(
            id=warehouse.id,
            branch_id=warehouse.branch_id,
            is_central=warehouse.is_central,
            is_transit=warehouse.is_transit,
            is_active=warehouse.is_active,
            operational_status=warehouse.operational_status,
            storage_eligible=warehouse.storage_eligible,
            branch_active=branch is not None
            and branch.is_active
            and branch.operational_status == "active",
            branch_is_headquarters=branch is not None and branch.is_headquarters,
        )

    async def _branches_by_id(
        self, company_id: uuid.UUID, branch_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Branch]:
        rows = await self._session.scalars(
            select(Branch).where(
                Branch.company_id == company_id,
                Branch.id.in_(branch_ids),
                Branch.deleted_at.is_(None),
            )
        )
        return {branch.id: branch for branch in rows.all()}

    async def _warehouse_pair(
        self,
        *,
        company_id: uuid.UUID,
        origin_id: uuid.UUID,
        destination_id: uuid.UUID,
        saved_route: str | None = None,
    ) -> _Pair:
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
            self._raise(
                "No se encontraron las bodegas en la empresa seleccionada.",
                "transfer_warehouse_not_found",
                404,
            )
        # The rules are read after the warehouses are locked and stay locked until commit.
        policy = await self._policy(company_id, lock_share=True)
        branches = await self._branches_by_id(
            company_id, [b for b in {origin.branch_id, destination.branch_id} if b is not None]
        )
        try:
            route = classify_route(
                self._facts(origin, branches), self._facts(destination, branches), policy
            )
        except TransferDomainError as exc:
            if (
                saved_route is not None
                and saved_route != TransferRoute.CENTRAL_DISTRIBUTION
                and exc.code == "transfer_origin_not_central"
            ):
                # A saved branch transfer whose routes were all turned off is not "not central".
                raise route_disabled_error(saved_route) from exc
            raise
        return _Pair(origin, destination, route, policy)

    async def _validate_lines(
        self,
        *,
        company_id: uuid.UUID,
        origin: Warehouse,
        destination: Warehouse,
        lines: list[dict[str, Any]],
        route: TransferRoute = TransferRoute.CENTRAL_DISTRIBUTION,
        exclude_transfer_id: uuid.UUID | None = None,
    ) -> None:
        if route != TransferRoute.CENTRAL_DISTRIBUTION and any(
            line.get("demand_allocations") for line in lines
        ):
            self._raise(
                "Los traslados entre sucursales o de retorno no se vinculan a solicitudes de compra.",
                "transfer_demand_not_allowed_for_route",
                422,
            )
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
                route=route,
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
        request_details: dict[
            uuid.UUID, tuple[PurchaseRequestDetailModel, PurchaseRequestModel]
        ] = {}
        if request_detail_ids:
            demand_rows = (
                await self._session.execute(
                    select(PurchaseRequestDetailModel, PurchaseRequestModel)
                    .join(
                        PurchaseRequestModel,
                        (PurchaseRequestModel.id == PurchaseRequestDetailModel.purchase_request_id)
                        & (
                            PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id
                        ),
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
            self._raise(
                "La unidad logística no existe o ya está cerrada.",
                "transfer_handling_unit_not_found",
                404,
            )
        if (
            unit.warehouse_id != origin.id
            or unit.stock_status != "available"
            or unit.location_id is None
        ):
            self._raise(
                "La unidad debe estar disponible en la bodega de origen.",
                "transfer_handling_unit_unavailable",
            )
        if quantity > unit.quantity_base:
            self._raise(
                "La cantidad planeada supera la existencia de la unidad.", "transfer_over_dispatch"
            )
        item = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == unit.inventory_item_id,
            )
        )
        if item is None:
            self._raise(
                "La identidad del producto no existe en esta empresa.",
                "transfer_item_not_found",
                404,
            )
        declared_lot_detail = line.get("inventory_lot_detail_id")
        if declared_lot_detail is not None and declared_lot_detail != unit.inventory_lot_detail_id:
            self._raise(
                "El lote del traslado no coincide con el origen de la unidad.",
                "transfer_lot_mismatch",
                422,
            )
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
        route: TransferRoute = TransferRoute.CENTRAL_DISTRIBUTION,
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
                "Documente el motivo de la cantidad enviada sin una solicitud vinculada."
                if route == TransferRoute.CENTRAL_DISTRIBUTION
                else "Indica el motivo del traslado en cada línea.",
                "transfer_excess_reason_required",
                422,
            )
        for allocation in allocations:
            linked = request_details.get(allocation["purchase_request_detail_id"])
            if linked is None:
                self._raise(
                    "La línea de solicitud no pertenece a esta empresa.",
                    "transfer_request_detail_not_found",
                    404,
                )
            request_detail, request = linked
            if (
                request.branch_id != destination.branch_id
                or request.status not in _TRANSFERABLE_REQUEST_STATUSES
                or item.product_id is None
                or request_detail.product_id != item.product_id
            ):
                self._raise(
                    "La solicitud no corresponde al producto o sucursal destino.",
                    "transfer_request_scope_mismatch",
                    422,
                )
            if request_detail.unit_id != item.base_unit_id:
                self._raise(
                    "La unidad solicitada no coincide con la unidad base; documente una conversión antes de asignar demanda.",
                    "transfer_request_unit_mismatch",
                    422,
                )
            if Decimal(allocation["allocated_quantity"]) > request_detail.quantity:
                self._raise(
                    "La asignación supera la cantidad solicitada.",
                    "transfer_request_allocation_exceeds_requested",
                )

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
                    func.coalesce(
                        func.sum(InventoryTransferDemandAllocationModel.allocated_quantity), 0
                    ),
                )
                .join(
                    InventoryTransferDetailModel,
                    (
                        InventoryTransferDetailModel.company_id
                        == InventoryTransferDemandAllocationModel.company_id
                    )
                    & (
                        InventoryTransferDetailModel.id
                        == InventoryTransferDemandAllocationModel.transfer_detail_id
                    ),
                )
                .join(
                    InventoryTransferModel,
                    (InventoryTransferModel.company_id == InventoryTransferDetailModel.company_id)
                    & (InventoryTransferModel.id == InventoryTransferDetailModel.transfer_id),
                )
                .where(
                    InventoryTransferDemandAllocationModel.company_id == company_id,
                    InventoryTransferDemandAllocationModel.purchase_request_detail_id.in_(
                        request_detail_ids
                    ),
                    InventoryTransferModel.status != "cancelled",
                )
                .group_by(InventoryTransferDemandAllocationModel.purchase_request_detail_id)
            )
            if exclude_transfer_id is not None:
                sums_stmt = sums_stmt.where(InventoryTransferModel.id != exclude_transfer_id)
            already_allocated = {
                row[0]: row[1] for row in (await self._session.execute(sums_stmt)).all()
            }
            requested_in_this_transfer: dict[uuid.UUID, Decimal] = {}
            for line in lines:
                for allocation in line.get("demand_allocations", []):
                    detail_id = allocation["purchase_request_detail_id"]
                    requested_in_this_transfer[detail_id] = requested_in_this_transfer.get(
                        detail_id, Decimal("0")
                    ) + Decimal(allocation["allocated_quantity"])
            for detail_id, planned in requested_in_this_transfer.items():
                requested_detail, _request = request_details[detail_id]
                if (
                    Decimal(already_allocated.get(detail_id, 0)) + planned
                    > requested_detail.quantity
                ):
                    self._raise(
                        "La demanda ya fue asignada a otro traslado.",
                        "transfer_request_already_allocated",
                    )

    async def _validate_vehicle(self, company_id: uuid.UUID, vehicle_id: uuid.UUID | None) -> None:
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
            self._raise(
                "Seleccione un vehículo activo de esta empresa.",
                "transfer_vehicle_unavailable",
                422,
            )

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
                excess_reason=(
                    str(line["excess_reason"]).strip() if line.get("excess_reason") else None
                ),
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
        origin, destination, route, policy = await self._warehouse_pair(
            company_id=company_id,
            origin_id=origin_warehouse_id,
            destination_id=destination_warehouse_id,
        )
        await self._validate_lines(
            company_id=company_id,
            origin=origin,
            destination=destination,
            lines=clean_lines,
            route=route,
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
            route_type=route.value,
            requires_approval=approval_required(route, policy),
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
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

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
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        require_preparation(transfer.status)
        origin_id = origin_warehouse_id or transfer.origin_warehouse_id
        destination_id = destination_warehouse_id or transfer.destination_warehouse_id
        origin, destination, route, policy = await self._warehouse_pair(
            company_id=company_id, origin_id=origin_id, destination_id=destination_id
        )
        clean_lines = [dict(line) for line in lines]
        await self._validate_lines(
            company_id=company_id,
            origin=origin,
            destination=destination,
            lines=clean_lines,
            route=route,
            exclude_transfer_id=transfer.id,
        )
        await self._validate_vehicle(company_id, vehicle_id)
        transfer.origin_warehouse_id = origin.id
        transfer.destination_warehouse_id = destination.id
        transfer.route_type = route.value
        transfer.requires_approval = approval_required(route, policy)
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
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

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
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        require_cancellable(transfer.status, transfer.route_type)
        transfer.status = "cancelled"
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="cancel",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

    async def _lock_transfer(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> InventoryTransferModel:
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        return transfer

    async def _lock_details(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> list[InventoryTransferDetailModel]:
        return list(
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

    async def _lines_from_details(
        self, company_id: uuid.UUID, details: list[InventoryTransferDetailModel]
    ) -> list[dict[str, Any]]:
        """Rebuild the lines of a saved transfer so they can be validated again."""
        allocations: dict[uuid.UUID, list[dict[str, Any]]] = {}
        if details:
            rows = await self._session.scalars(
                select(InventoryTransferDemandAllocationModel)
                .where(
                    InventoryTransferDemandAllocationModel.company_id == company_id,
                    InventoryTransferDemandAllocationModel.transfer_detail_id.in_(
                        [detail.id for detail in details]
                    ),
                )
                .order_by(InventoryTransferDemandAllocationModel.id)
            )
            for allocation in rows.all():
                allocations.setdefault(allocation.transfer_detail_id, []).append(
                    {
                        "purchase_request_detail_id": allocation.purchase_request_detail_id,
                        "allocated_quantity": allocation.allocated_quantity,
                    }
                )
        return [
            {
                "handling_unit_id": detail.source_handling_unit_id,
                "quantity_base": Decimal(detail.quantity_planned),
                "inventory_lot_detail_id": detail.inventory_lot_detail_id,
                "excess_reason": detail.excess_reason,
                "notes": detail.notes,
                "demand_allocations": allocations.get(detail.id, []),
            }
            for detail in details
        ]

    async def _ensure_units_not_committed(
        self,
        company_id: uuid.UUID,
        unit_ids: list[uuid.UUID],
        transfer_id: uuid.UUID,
    ) -> None:
        """Lock the handling units and refuse any already promised to another transfer.

        Drafts in preparation promise nothing; only transfers waiting for approval
        or already approved hold their units until they leave or are called off.
        """
        if not unit_ids:
            return
        ordered = sorted(set(unit_ids), key=str)
        await self._session.scalars(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id.in_(ordered),
            )
            .order_by(InventoryHandlingUnitModel.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        clash = (
            await self._session.execute(
                select(InventoryHandlingUnitModel.code, InventoryTransferModel.code)
                .select_from(InventoryTransferDetailModel)
                .join(
                    InventoryTransferModel,
                    (InventoryTransferModel.company_id == InventoryTransferDetailModel.company_id)
                    & (InventoryTransferModel.id == InventoryTransferDetailModel.transfer_id),
                )
                .join(
                    InventoryHandlingUnitModel,
                    (
                        InventoryHandlingUnitModel.company_id
                        == InventoryTransferDetailModel.company_id
                    )
                    & (
                        InventoryHandlingUnitModel.id
                        == InventoryTransferDetailModel.source_handling_unit_id
                    ),
                )
                .where(
                    InventoryTransferDetailModel.company_id == company_id,
                    InventoryTransferDetailModel.source_handling_unit_id.in_(ordered),
                    InventoryTransferModel.id != transfer_id,
                    InventoryTransferModel.status.in_([s.value for s in _COMMITTING_STATUSES]),
                )
                .order_by(InventoryTransferModel.code)
                .limit(1)
            )
        ).first()
        if clash is not None:
            self._raise(
                f"La unidad {clash[0]} ya está comprometida en el traslado {clash[1]} "
                "pendiente de despacho.",
                "transfer_handling_unit_committed",
            )

    async def submit_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint("submit", {"transfer_id": transfer_id})
        replay = await self._replay_command(
            company_id=company_id, action="submit", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._lock_transfer(company_id, transfer_id)
        details = await self._lock_details(company_id, transfer_id)
        pair = await self._warehouse_pair(
            company_id=company_id,
            origin_id=transfer.origin_warehouse_id,
            destination_id=transfer.destination_warehouse_id,
            saved_route=transfer.route_type,
        )
        require_submittable(transfer.status, pair.route, approval_required(pair.route, pair.policy))
        if not details:
            self._raise(
                "Agregue al menos una unidad logística al traslado.",
                "transfer_lines_required",
                422,
            )
        await self._revalidate(transfer=transfer, details=details, pair=pair)
        transfer.route_type = pair.route.value
        transfer.requires_approval = True
        transfer.status = TransferStatus.PENDING_APPROVAL.value
        transfer.submitted_by_id = actor_id
        transfer.submitted_at = datetime.now(UTC)
        transfer.approval_round = transfer.approval_round + 1
        transfer.rejected_by_id = None
        transfer.rejected_at = None
        transfer.rejection_reason = None
        transfer.approved_by_id = None
        transfer.approved_at = None
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="submit",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

    async def _revalidate(
        self,
        *,
        transfer: InventoryTransferModel,
        details: list[InventoryTransferDetailModel],
        pair: _Pair,
    ) -> None:
        """Check a saved transfer against the current stock and the units promised elsewhere."""
        # The units are locked first so the stock read below cannot go stale.
        await self._ensure_units_not_committed(
            transfer.company_id, [detail.source_handling_unit_id for detail in details], transfer.id
        )
        lines = await self._lines_from_details(transfer.company_id, details)
        await self._validate_lines(
            company_id=transfer.company_id,
            origin=pair.origin,
            destination=pair.destination,
            lines=lines,
            route=pair.route,
            exclude_transfer_id=transfer.id,
        )

    async def withdraw_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint("withdraw", {"transfer_id": transfer_id})
        replay = await self._replay_command(
            company_id=company_id, action="withdraw", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._lock_transfer(company_id, transfer_id)
        require_pending_approval(transfer.status)
        transfer.status = TransferStatus.PREPARATION.value
        transfer.submitted_by_id = None
        transfer.submitted_at = None
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="withdraw",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

    async def approve_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        expected_round: int,
        allow_self_approval: bool = False,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(
            "approve", {"transfer_id": transfer_id, "expected_round": expected_round}
        )
        replay = await self._replay_command(
            company_id=company_id, action="approve", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._lock_transfer(company_id, transfer_id)
        require_pending_approval(transfer.status)
        require_current_round(expected_round, transfer.approval_round)
        require_independent_approver(
            actor_id=actor_id,
            created_by_id=transfer.created_by_id,
            submitted_by_id=transfer.submitted_by_id,
            allow_self_approval=allow_self_approval,
        )
        details = await self._lock_details(company_id, transfer_id)
        pair = await self._warehouse_pair(
            company_id=company_id,
            origin_id=transfer.origin_warehouse_id,
            destination_id=transfer.destination_warehouse_id,
            saved_route=transfer.route_type,
        )
        await self._revalidate(transfer=transfer, details=details, pair=pair)
        transfer.status = TransferStatus.APPROVED.value
        transfer.approved_by_id = actor_id
        transfer.approved_at = datetime.now(UTC)
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="approve",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

    async def reject_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        expected_round: int,
        reason: str,
        allow_self_approval: bool = False,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(
            "reject",
            {"transfer_id": transfer_id, "expected_round": expected_round, "reason": reason},
        )
        replay = await self._replay_command(
            company_id=company_id, action="reject", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._lock_transfer(company_id, transfer_id)
        require_pending_approval(transfer.status)
        require_current_round(expected_round, transfer.approval_round)
        require_independent_approver(
            actor_id=actor_id,
            created_by_id=transfer.created_by_id,
            submitted_by_id=transfer.submitted_by_id,
            allow_self_approval=allow_self_approval,
        )
        transfer.status = TransferStatus.PREPARATION.value
        transfer.rejected_by_id = actor_id
        transfer.rejected_at = datetime.now(UTC)
        transfer.rejection_reason = reason
        transfer.submitted_by_id = None
        transfer.submitted_at = None
        command = await self._record_command(
            company_id=company_id,
            transfer_id=transfer.id,
            action="reject",
            key=idempotency_key,
            fingerprint=fingerprint,
            actor_id=actor_id,
        )
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

    async def dispatch_transfer(
        self,
        *,
        company_id: uuid.UUID,
        transfer_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
        driver_id: uuid.UUID | None = None,
        compliance_override_reason: str | None = None,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(
            "dispatch",
            {"transfer_id": transfer_id, "vehicle_id": vehicle_id, "driver_id": driver_id},
        )
        replay = await self._replay_command(
            company_id=company_id, action="dispatch", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
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
        # A state that can never be dispatched is reported before touching anything else.
        require_dispatchable(transfer.status, len(details), transfer.route_type, False)
        _, _, route, policy = await self._warehouse_pair(
            company_id=company_id,
            origin_id=transfer.origin_warehouse_id,
            destination_id=transfer.destination_warehouse_id,
            saved_route=transfer.route_type,
        )
        require_dispatchable(transfer.status, len(details), route, approval_required(route, policy))
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
            self._raise(
                "Seleccione un vehículo activo de esta empresa.",
                "transfer_vehicle_unavailable",
                422,
            )
        if transfer.vehicle_id is not None and transfer.vehicle_id != vehicle.id:
            self._raise(
                "El vehículo no coincide con el asignado a la preparación.",
                "transfer_vehicle_mismatch",
                422,
            )
        await self._ensure_units_not_committed(
            company_id, [detail.source_handling_unit_id for detail in details], transfer.id
        )
        lines: list[dict[str, Any]] = []
        for detail in details:
            unit = await self._session.scalar(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == detail.source_handling_unit_id,
                )
            )
            if unit is None:
                self._raise(
                    "No se encuentra una unidad logística del traslado.",
                    "transfer_handling_unit_not_found",
                    404,
                )
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
        movement = await InventoryUseCases(
            SqlAlchemyInventoryRepository(self._session)
        ).post_movement(
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
        transfer.driver_id = driver_id
        transfer.compliance_override_by = actor_id if compliance_override_reason else None
        transfer.compliance_override_reason = compliance_override_reason
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
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

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
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
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
            self._raise(
                "Una línea de recepción no pertenece a este traslado.",
                "transfer_detail_not_found",
                404,
            )
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
            remaining = (
                Decimal(detail.quantity_dispatched)
                - Decimal(detail.quantity_received)
                - Decimal(detail.quantity_returned)
                - Decimal(detail.quantity_adjusted_out)
            )
            quantity = Decimal(line["quantity_base"])
            validate_receipt_quantity(requested=quantity, remaining=remaining)
            if detail.transit_handling_unit_id is None:
                self._raise(
                    "La unidad logística pendiente no está asociada al tránsito.",
                    "transfer_transit_unit_missing",
                )
            unit = await self._session.scalar(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == detail.transit_handling_unit_id,
                )
            )
            if (
                unit is None
                or unit.warehouse_id
                != (
                    await self._session.scalar(
                        select(InventoryVehicleModel.transit_warehouse_id).where(
                            InventoryVehicleModel.company_id == company_id,
                            InventoryVehicleModel.id == transfer.vehicle_id,
                        )
                    )
                )
                or unit.stock_status != "in_transit"
                or unit.location_id is None
            ):
                self._raise(
                    "La unidad no se encuentra en el vehículo asociado al traslado.",
                    "transfer_transit_unit_mismatch",
                )
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
                self._raise(
                    "El destino debe ser una ubicación receptora activa de la bodega destino.",
                    "transfer_receipt_location_invalid",
                    422,
                )
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

        movement = await InventoryUseCases(
            SqlAlchemyInventoryRepository(self._session)
        ).post_movement(
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
            if Decimal(detail.quantity_received) + Decimal(detail.quantity_returned) + Decimal(
                detail.quantity_adjusted_out
            ) >= Decimal(detail.quantity_dispatched):
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
            Decimal(item.quantity_received)
            + Decimal(item.quantity_returned)
            + Decimal(item.quantity_adjusted_out)
            >= Decimal(item.quantity_dispatched)
            for item in all_details
        ):
            transfer.status = "received"
            transfer.received_by_id = actor_id
            transfer.received_at = now
        await self._session.flush()
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

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
            "incident",
            {
                "transfer_id": transfer_id,
                "reason": reason,
                "evidence_reference": evidence_reference,
            },
        )
        replay = await self._replay_command(
            company_id=company_id, action="incident", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        if transfer.status != "in_transit":
            self._raise(
                "Solo puede abrir una incidencia de un traslado en tránsito.",
                "transfer_incident_not_allowed",
            )
        incident = await self._session.scalar(
            select(InventoryTransferIncidentModel).where(
                InventoryTransferIncidentModel.company_id == company_id,
                InventoryTransferIncidentModel.transfer_id == transfer.id,
                InventoryTransferIncidentModel.status == "open",
            )
        )
        if incident is not None:
            self._raise(
                "El traslado ya tiene una incidencia abierta.", "transfer_incident_already_open"
            )
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
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

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
            "resolve",
            {
                "transfer_id": transfer_id,
                "resolution": resolution,
                "resolution_notes": resolution_notes,
            },
        )
        replay = await self._replay_command(
            company_id=company_id, action="resolve", key=idempotency_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
            .with_for_update()
        )
        if transfer is None:
            self._raise("Traslado no encontrado.", "transfer_not_found", 404)
        if transfer.status != "incident":
            self._raise(
                "El traslado no tiene una incidencia pendiente.", "transfer_incident_not_open"
            )
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
            > Decimal(detail.quantity_received)
            + Decimal(detail.quantity_returned)
            + Decimal(detail.quantity_adjusted_out)
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
            await self._validate_pending_transit(company_id, pending)
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
        return await self._finish_command(command, company_id=company_id, transfer_id=transfer.id)

    async def _transfer_payload(  # noqa: C901 - assembles the normalized transfer read projection
        self, transfer: InventoryTransferModel, policy: TransferPolicy | None = None
    ) -> dict[str, Any]:
        origin, destination = await self._warehouse_pair_for_read(
            transfer.company_id, transfer.origin_warehouse_id, transfer.destination_warehouse_id
        )
        branch_names = {
            row[0]: row[1]
            for row in (
                await self._session.execute(
                    select(Branch.id, Branch.name).where(
                        Branch.company_id == transfer.company_id,
                        Branch.id.in_([origin.branch_id, destination.branch_id]),
                    )
                )
            ).all()
        }
        actor_ids = {
            actor
            for actor in (
                transfer.submitted_by_id,
                transfer.approved_by_id,
                transfer.rejected_by_id,
            )
            if actor is not None
        }
        actor_names: dict[uuid.UUID, str] = {}
        if actor_ids:
            actor_names = {
                row[0]: row[1]
                for row in (
                    await self._session.execute(
                        select(User.id, User.username).where(User.id.in_(actor_ids))
                    )
                ).all()
            }
        requires_approval = transfer.requires_approval
        if transfer.status == TransferStatus.PREPARATION:
            # A draft follows the rules in force today; later states keep what was decided.
            live_policy = policy or await self._policy(transfer.company_id)
            requires_approval = approval_required(transfer.route_type, live_policy)
        vehicle = None
        if transfer.vehicle_id is not None:
            record = await self._session.scalar(
                select(InventoryVehicleModel).where(
                    InventoryVehicleModel.company_id == transfer.company_id,
                    InventoryVehicleModel.id == transfer.vehicle_id,
                )
            )
            if record is not None:
                fleet = (
                    await self._session.execute(
                        select(FleetVehicleModel.id, FleetVehicleModel.plate).where(
                            FleetVehicleModel.company_id == transfer.company_id,
                            FleetVehicleModel.inventory_vehicle_id == record.id,
                        )
                    )
                ).first()
                vehicle = {
                    "id": record.id,
                    "code": record.code,
                    "name": record.name,
                    "status": record.status,
                    "transit_warehouse_id": record.transit_warehouse_id,
                    "fleet_vehicle_id": fleet[0] if fleet else None,
                    "plate": fleet[1] if fleet else None,
                }
        driver = None
        if transfer.driver_id is not None:
            driver_row = (
                await self._session.execute(
                    select(
                        DriverModel.id,
                        Employee.first_name,
                        Employee.last_name,
                        Employee.employee_code,
                    )
                    .join(Employee, Employee.id == DriverModel.employee_id)
                    .where(
                        DriverModel.company_id == transfer.company_id,
                        DriverModel.id == transfer.driver_id,
                    )
                    .execution_options(include_deleted=True)
                )
            ).first()
            if driver_row is not None:
                driver = {
                    "id": driver_row[0],
                    "name": f"{driver_row[1]} {driver_row[2]}".strip(),
                    "employee_code": driver_row[3],
                }
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
                            func.coalesce(
                                ProductVariantModel.name_override, ProductModel.name
                            ).label("product_name"),
                            func.coalesce(CompanyUnitModel.alias, UnitModel.name).label(
                                "base_unit_name"
                            ),
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
        hu_ids.update(
            detail.transit_handling_unit_id for detail in details if detail.transit_handling_unit_id
        )
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
        lot_ids = {
            detail.inventory_lot_detail_id for detail in details if detail.inventory_lot_detail_id
        }
        lot_codes: dict[uuid.UUID, str] = {}
        if lot_ids:
            lot_codes = {
                row[0]: row[1]
                for row in (
                    await self._session.execute(
                        select(InventoryLotDetailModel.id, InventoryLotDetailModel.code).where(
                            InventoryLotDetailModel.company_id == transfer.company_id,
                            InventoryLotDetailModel.id.in_(lot_ids),
                        )
                    )
                ).all()
            }
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
                        (
                            PurchaseRequestDetailModel.company_id
                            == InventoryTransferDemandAllocationModel.company_id
                        )
                        & (
                            PurchaseRequestDetailModel.id
                            == InventoryTransferDemandAllocationModel.purchase_request_detail_id
                        ),
                    )
                    .join(
                        PurchaseRequestModel,
                        (PurchaseRequestModel.company_id == PurchaseRequestDetailModel.company_id)
                        & (
                            PurchaseRequestModel.id
                            == PurchaseRequestDetailModel.purchase_request_id
                        ),
                    )
                    .join(Branch, Branch.id == PurchaseRequestModel.branch_id)
                    .where(
                        InventoryTransferDemandAllocationModel.company_id == transfer.company_id,
                        InventoryTransferDemandAllocationModel.transfer_detail_id.in_(
                            [d.id for d in details]
                        ),
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
            (
                await self._session.execute(
                    select(InventoryTransferReceiptModel)
                    .where(
                        InventoryTransferReceiptModel.company_id == transfer.company_id,
                        InventoryTransferReceiptModel.transfer_id == transfer.id,
                    )
                    .order_by(
                        InventoryTransferReceiptModel.received_at, InventoryTransferReceiptModel.id
                    )
                )
            )
            .scalars()
            .all()
        )
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
            (
                await self._session.execute(
                    select(InventoryTransferIncidentModel)
                    .where(
                        InventoryTransferIncidentModel.company_id == transfer.company_id,
                        InventoryTransferIncidentModel.transfer_id == transfer.id,
                    )
                    .order_by(
                        InventoryTransferIncidentModel.opened_at, InventoryTransferIncidentModel.id
                    )
                )
            )
            .scalars()
            .all()
        )
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
            transit_hu = (
                units_by_id.get(detail.transit_handling_unit_id)
                if detail.transit_handling_unit_id
                else None
            )
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
                    "inventory_lot_detail_code": lot_codes.get(detail.inventory_lot_detail_id)
                    if detail.inventory_lot_detail_id is not None
                    else None,
                    "source_handling_unit_id": detail.source_handling_unit_id,
                    "source_handling_unit_code": source_hu.code if source_hu else None,
                    "transit_handling_unit_id": detail.transit_handling_unit_id,
                    "transit_handling_unit_code": transit_hu.code if transit_hu else None,
                    "quantity_planned": detail.quantity_planned,
                    "quantity_dispatched": detail.quantity_dispatched,
                    "quantity_received": detail.quantity_received,
                    "quantity_in_transit": Decimal(detail.quantity_dispatched)
                    - Decimal(detail.quantity_received)
                    - Decimal(detail.quantity_returned)
                    - Decimal(detail.quantity_adjusted_out),
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
            "origin_branch_name": branch_names.get(origin.branch_id),
            "origin_is_central": origin.is_central,
            "destination_warehouse_id": transfer.destination_warehouse_id,
            "destination_warehouse_name": destination.name,
            "destination_branch_id": destination.branch_id,
            "destination_branch_name": branch_names.get(destination.branch_id),
            "destination_is_central": destination.is_central,
            "vehicle": vehicle,
            "driver": driver,
            "compliance_override_reason": transfer.compliance_override_reason,
            "status": transfer.status,
            "route_type": transfer.route_type,
            "requires_approval": requires_approval,
            "approval_round": transfer.approval_round,
            "submitted_by_id": transfer.submitted_by_id,
            "submitted_by_name": actor_names.get(transfer.submitted_by_id)
            if transfer.submitted_by_id
            else None,
            "submitted_at": transfer.submitted_at,
            "approved_by_id": transfer.approved_by_id,
            "approved_by_name": actor_names.get(transfer.approved_by_id)
            if transfer.approved_by_id
            else None,
            "approved_at": transfer.approved_at,
            "rejected_by_id": transfer.rejected_by_id,
            "rejected_by_name": actor_names.get(transfer.rejected_by_id)
            if transfer.rejected_by_id
            else None,
            "rejected_at": transfer.rejected_at,
            "rejection_reason": transfer.rejection_reason,
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
            self._raise(
                "No se pudieron cargar las bodegas del traslado.",
                "transfer_warehouse_not_found",
                404,
            )
        return origin, destination

    async def get_transfer(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> dict[str, Any] | None:
        transfer = await self._session.scalar(
            select(InventoryTransferModel).where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.id == transfer_id,
            )
        )
        if transfer is None:
            return None
        return await self._transfer_payload(transfer)

    @staticmethod
    def _awaiting_approval_filters(
        *,
        origin_warehouse: Any,
        actor_id: uuid.UUID,
        allow_self_approval: bool,
        approver_branch_ids: list[uuid.UUID] | None,
    ) -> list[Any]:
        """The transfers this actor could decide on: waiting, from a branch they cover."""
        filters: list[Any] = [InventoryTransferModel.status == TransferStatus.PENDING_APPROVAL]
        if approver_branch_ids is not None:
            filters.append(origin_warehouse.branch_id.in_(approver_branch_ids))
        if not allow_self_approval:
            filters.append(InventoryTransferModel.created_by_id != actor_id)
            filters.append(
                or_(
                    InventoryTransferModel.submitted_by_id.is_(None),
                    InventoryTransferModel.submitted_by_id != actor_id,
                )
            )
        return filters

    async def list_transfers(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        branch_ids: list[uuid.UUID] | None = None,
        status_filter: str | None = None,
        route_type: str | None = None,
        side: str | None = None,
        awaiting_approval_by: uuid.UUID | None = None,
        allow_self_approval: bool = False,
        approver_branch_ids: list[uuid.UUID] | None = None,
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
        scope_ids = [branch_id] if branch_id is not None else branch_ids
        if scope_ids is not None:
            if not scope_ids:
                return []
            on_origin = origin_warehouse.branch_id.in_(scope_ids)
            on_destination = destination_warehouse.branch_id.in_(scope_ids)
            stmt = stmt.where(
                on_origin
                if side == "origin"
                else on_destination
                if side == "destination"
                else or_(on_origin, on_destination)
            )
        if status_filter:
            stmt = stmt.where(InventoryTransferModel.status == status_filter)
        if route_type:
            stmt = stmt.where(InventoryTransferModel.route_type == route_type)
        if awaiting_approval_by is not None:
            if approver_branch_ids is not None and not approver_branch_ids:
                return []
            stmt = stmt.where(
                *self._awaiting_approval_filters(
                    origin_warehouse=origin_warehouse,
                    actor_id=awaiting_approval_by,
                    allow_self_approval=allow_self_approval,
                    approver_branch_ids=approver_branch_ids,
                )
            )
        records = list(
            (
                await self._session.scalars(
                    stmt.order_by(
                        InventoryTransferModel.created_at.desc(), InventoryTransferModel.id
                    )
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).all()
        )
        policy = await self._policy(company_id)
        return [await self._transfer_payload(record, policy) for record in records]

    async def pending_approval_count(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        allow_self_approval: bool = False,
        approver_branch_ids: list[uuid.UUID] | None = None,
    ) -> int:
        """How many waiting transfers this actor could decide on (the inbox badge)."""
        if approver_branch_ids is not None and not approver_branch_ids:
            return 0
        origin_warehouse = aliased(Warehouse)
        count = await self._session.scalar(
            select(func.count(InventoryTransferModel.id))
            .join(
                origin_warehouse,
                (origin_warehouse.company_id == InventoryTransferModel.company_id)
                & (origin_warehouse.id == InventoryTransferModel.origin_warehouse_id),
            )
            .where(
                InventoryTransferModel.company_id == company_id,
                *self._awaiting_approval_filters(
                    origin_warehouse=origin_warehouse,
                    actor_id=actor_id,
                    allow_self_approval=allow_self_approval,
                    approver_branch_ids=approver_branch_ids,
                ),
            )
        )
        return int(count or 0)

    @staticmethod
    def _option(warehouse: Warehouse, branch: Branch) -> dict[str, Any]:
        return {
            "id": warehouse.id,
            "code": warehouse.code,
            "name": warehouse.name,
            "branch_id": branch.id,
            "branch_name": branch.name,
            "is_central": warehouse.is_central,
        }

    async def route_options(
        self,
        *,
        company_id: uuid.UUID,
        can_move: bool,
        branch_ids: list[uuid.UUID] | None = None,
        warehouse_ids: list[uuid.UUID] | None = None,
        origin_warehouse_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Where a user may ship from and, once an origin is chosen, where it may go.

        ``branch_ids`` and ``warehouse_ids`` are the user's scope (``None`` means all).
        """
        policy = await self._policy(company_id)
        rows = (
            await self._session.execute(
                select(Warehouse, Branch)
                .join(
                    Branch,
                    (Branch.company_id == Warehouse.company_id)
                    & (Branch.id == Warehouse.branch_id),
                )
                .where(
                    Warehouse.company_id == company_id,
                    Warehouse.deleted_at.is_(None),
                    Warehouse.is_transit.is_(False),
                    Branch.deleted_at.is_(None),
                )
                .order_by(Branch.name, Warehouse.name, Warehouse.id)
            )
        ).all()
        branches = {branch.id: branch for _, branch in rows}
        facts = {warehouse.id: self._facts(warehouse, branches) for warehouse, _ in rows}
        branch_routes_on = policy.allow_branch_to_branch or policy.allow_branch_to_central
        origins: list[dict[str, Any]] = []
        if can_move:
            for warehouse, branch in rows:
                fact = facts[warehouse.id]
                if (
                    not fact.operable
                    or not fact.branch_active
                    or (branch_ids is not None and branch.id not in branch_ids)
                    or (warehouse_ids is not None and warehouse.id not in warehouse_ids)
                ):
                    continue
                if warehouse.is_central:
                    eligible = fact.branch_is_headquarters
                else:
                    eligible = warehouse.storage_eligible and branch_routes_on
                if eligible:
                    origins.append(self._option(warehouse, branch))
        destinations: list[dict[str, Any]] = []
        if origin_warehouse_id is not None:
            if origin_warehouse_id not in {origin["id"] for origin in origins}:
                self._raise(
                    "No tienes acceso a esta bodega de origen.", "transfer_origin_forbidden", 403
                )
            for warehouse, branch in rows:
                try:
                    route = classify_route(facts[origin_warehouse_id], facts[warehouse.id], policy)
                except TransferDomainError:
                    continue
                destinations.append({**self._option(warehouse, branch), "route_type": route.value})
        return {
            "policy": {
                "allow_branch_to_branch": policy.allow_branch_to_branch,
                "allow_branch_to_central": policy.allow_branch_to_central,
                "require_approval": policy.require_approval,
            },
            "origins": origins,
            "destinations": destinations,
        }

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
                        func.coalesce(
                            func.sum(InventoryTransferDemandAllocationModel.allocated_quantity), 0
                        ),
                        func.coalesce(
                            func.sum(InventoryTransferDemandAllocationModel.quantity_dispatched), 0
                        ),
                        func.coalesce(
                            func.sum(InventoryTransferDemandAllocationModel.quantity_received), 0
                        ),
                        func.coalesce(
                            func.sum(InventoryTransferDemandAllocationModel.quantity_adjusted_out),
                            0,
                        ),
                    )
                    .join(
                        InventoryTransferDetailModel,
                        (
                            InventoryTransferDetailModel.company_id
                            == InventoryTransferDemandAllocationModel.company_id
                        )
                        & (
                            InventoryTransferDetailModel.id
                            == InventoryTransferDemandAllocationModel.transfer_detail_id
                        ),
                    )
                    .join(
                        InventoryTransferModel,
                        (
                            InventoryTransferModel.company_id
                            == InventoryTransferDetailModel.company_id
                        )
                        & (InventoryTransferModel.id == InventoryTransferDetailModel.transfer_id),
                    )
                    .where(
                        InventoryTransferDemandAllocationModel.company_id == company_id,
                        InventoryTransferDemandAllocationModel.purchase_request_detail_id.in_(
                            detail_ids
                        ),
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

    async def _find_transit_warehouse(self, company_id: uuid.UUID) -> Warehouse | None:
        warehouse: Warehouse | None = await self._session.scalar(
            select(Warehouse).where(
                Warehouse.company_id == company_id,
                Warehouse.is_transit.is_(True),
                Warehouse.deleted_at.is_(None),
            )
        )
        return warehouse

    async def _provision_transit_warehouse(self, company_id: uuid.UUID) -> None:
        """Create the technical transit warehouse in the headquarters branch.

        Migration 0086 only provisioned companies that existed at that time.
        Companies configured later get it on first use, with the same rules:
        it requires an active headquarters with an active central warehouse.
        """
        params = {"company_id": company_id}
        await self._session.execute(
            text(
                """
                INSERT INTO warehouse_categories (id, company_id, name, description, is_active,
                  created_at, updated_at)
                SELECT gen_random_uuid(), :company_id, 'Tránsito interno',
                  'Categoría técnica para ubicaciones móviles de vehículos.', true, now(), now()
                WHERE NOT EXISTS (
                  SELECT 1 FROM warehouse_categories
                  WHERE company_id = :company_id AND lower(name) = lower('Tránsito interno')
                    AND deleted_at IS NULL)
                """
            ),
            params,
        )
        await self._session.execute(
            text(
                """
                INSERT INTO warehouses (id, company_id, branch_id, warehouse_category_id, name,
                  code, warehouse_type, is_central, is_transit, operational_status,
                  capacity_profile, capacity_enforcement_mode, storage_eligible, created_at,
                  updated_at, is_active)
                SELECT gen_random_uuid(), central.company_id, headquarters.id, category.id,
                  'Tránsito de vehículos',
                  'TRN-' || upper(substr(replace(central.company_id::text, '-', ''), 1, 8)),
                  'transit', false, true, 'active', 'transit', 'disabled', false, now(), now(),
                  true
                FROM warehouses AS central
                JOIN branches AS headquarters ON headquarters.id = central.branch_id
                  AND headquarters.company_id = central.company_id
                JOIN warehouse_categories AS category ON category.company_id = central.company_id
                  AND lower(category.name) = lower('Tránsito interno')
                  AND category.deleted_at IS NULL
                WHERE central.company_id = :company_id
                  AND central.is_central IS TRUE AND central.is_active IS TRUE
                  AND central.operational_status = 'active' AND central.deleted_at IS NULL
                  AND headquarters.is_headquarters IS TRUE AND headquarters.is_active IS TRUE
                  AND headquarters.operational_status = 'active'
                  AND headquarters.deleted_at IS NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM warehouses AS transit
                    WHERE transit.company_id = central.company_id
                      AND transit.is_transit IS TRUE AND transit.deleted_at IS NULL)
                LIMIT 1
                """
            ),
            params,
        )
        await self._session.flush()

    async def _transit_warehouse(self, company_id: uuid.UUID) -> Warehouse:
        warehouse = await self._find_transit_warehouse(company_id)
        if warehouse is None:
            await self._provision_transit_warehouse(company_id)
            warehouse = await self._find_transit_warehouse(company_id)
        if warehouse is None:
            self._raise(
                "La empresa necesita una sucursal matriz activa con bodega central activa "
                "para habilitar los vehículos de traslado.",
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
            self._raise(
                "El código de vehículo debe tener entre 1 y 32 caracteres.",
                "vehicle_code_invalid",
                422,
            )
        warehouse = await self._transit_warehouse(company_id)
        existing = await self._session.scalar(
            select(InventoryVehicleModel.id).where(
                InventoryVehicleModel.company_id == company_id,
                func.lower(InventoryVehicleModel.code) == normalized_code.lower(),
            )
        )
        if existing is not None:
            self._raise(
                "Ya existe un vehículo con ese código en la empresa.", "vehicle_code_conflict", 409
            )
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

    async def list_vehicles(
        self, company_id: uuid.UUID, branch_ids: list[uuid.UUID] | None = None
    ) -> list[dict[str, Any]]:
        """Transit vehicles with their Fleet record; ``branch_ids`` limits to those branches."""
        statement = (
            select(InventoryVehicleModel, Warehouse.name, FleetVehicleModel, Branch.name)
            .join(
                Warehouse,
                (Warehouse.company_id == InventoryVehicleModel.company_id)
                & (Warehouse.id == InventoryVehicleModel.transit_warehouse_id),
            )
            .outerjoin(
                FleetVehicleModel,
                (FleetVehicleModel.company_id == InventoryVehicleModel.company_id)
                & (FleetVehicleModel.inventory_vehicle_id == InventoryVehicleModel.id),
            )
            .outerjoin(Branch, Branch.id == FleetVehicleModel.branch_id)
            .where(InventoryVehicleModel.company_id == company_id)
            .order_by(InventoryVehicleModel.code)
        )
        if branch_ids is not None:
            statement = statement.where(FleetVehicleModel.branch_id.in_(branch_ids))
        rows = (await self._session.execute(statement)).all()
        payloads = []
        for vehicle, warehouse_name, fleet, branch_name in rows:
            payload = self._vehicle_payload(vehicle, warehouse_name)
            if fleet is not None:
                payload.update(
                    fleet_vehicle_id=fleet.id,
                    plate=fleet.plate,
                    kind=fleet.kind,
                    branch_id=fleet.branch_id,
                    branch_name=branch_name,
                )
            payloads.append(payload)
        return payloads

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
                select(InventoryBalanceModel.id)
                .where(
                    InventoryBalanceModel.company_id == company_id,
                    InventoryBalanceModel.location_id == vehicle.transit_location_id,
                    InventoryBalanceModel.stock_status == "in_transit",
                    InventoryBalanceModel.quantity_base > 0,
                )
                .limit(1)
            )
            if has_balance is not None:
                self._raise(
                    "No puede desactivar el vehículo mientras tenga inventario en tránsito.",
                    "vehicle_has_transit_inventory",
                )
        vehicle.status = status
        await self._session.flush()
        warehouse = await self._session.get(Warehouse, vehicle.transit_warehouse_id)
        return self._vehicle_payload(vehicle, warehouse.name if warehouse else "Tránsito")

    async def _validate_pending_transit(
        self, company_id: uuid.UUID, pending: list[InventoryTransferDetailModel]
    ) -> None:
        if not pending:
            self._raise(
                "No queda mercancía en tránsito; cierre la incidencia como recibida.",
                "transfer_no_pending_transit",
            )
        for detail in pending:
            unit = await self._session.scalar(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == detail.transit_handling_unit_id,
                )
            )
            remaining = (
                Decimal(detail.quantity_dispatched)
                - Decimal(detail.quantity_received)
                - Decimal(detail.quantity_returned)
                - Decimal(detail.quantity_adjusted_out)
            )
            if (
                unit is None
                or unit.stock_status != "in_transit"
                or Decimal(unit.quantity_base) < remaining
            ):
                self._raise(
                    "Confirme la cantidad realmente presente en el vehículo; la diferencia requiere un ajuste autorizado.",
                    "transfer_incident_quantity_unresolved",
                )

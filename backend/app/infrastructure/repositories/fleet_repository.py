"""Read/write access for fleet vehicles, drivers and their operational records.

Every query is bound to ``company_id`` and, for listings, to the branch ids the
caller may see (``None`` = whole company). Callers enforce the branch scope of
single rows with :class:`app.api.v1.fleet_scope.FleetScope`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.application.fleet.compliance import RequiredCategory
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_record import DocumentCategoryModel, DocumentRecordModel
from app.infrastructure.models.employee import Employee, EmployeeBranchAssignment
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleCouplingModel,
    FleetVehicleModel,
    FleetVehiclePhotoModel,
    FleetVehicleTypeModel,
    MaintenanceOrderModel,
    MaintenancePlanModel,
    VehicleDriverAssignmentModel,
)
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.repositories.fleet_driver_queries import DriverQueries

ACTIVE_TRANSFER_STATUSES = ("in_transit", "incident")


def initials(first_name: str, last_name: str) -> str:
    return (first_name.strip()[:1] + last_name.strip()[:1]).upper() or "?"


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class FleetRepository(DriverQueries):
    def __init__(self, session: Any) -> None:
        self._session = session

    # -------------------------------------------------------- vehicle types

    async def vehicle_types(
        self, company_id: uuid.UUID, *, include_inactive: bool = True
    ) -> list[FleetVehicleTypeModel]:
        statement = select(FleetVehicleTypeModel).where(
            FleetVehicleTypeModel.company_id == company_id
        )
        if not include_inactive:
            statement = statement.where(FleetVehicleTypeModel.is_active.is_(True))
        rows = await self._session.scalars(
            statement.order_by(FleetVehicleTypeModel.sort_order, FleetVehicleTypeModel.name)
        )
        return list(rows)

    async def vehicle_type(self, company_id: uuid.UUID, code: str) -> FleetVehicleTypeModel | None:
        vehicle_type: FleetVehicleTypeModel | None = await self._session.scalar(
            select(FleetVehicleTypeModel).where(
                FleetVehicleTypeModel.company_id == company_id, FleetVehicleTypeModel.code == code
            )
        )
        return vehicle_type

    async def license_rules(self, company_id: uuid.UUID) -> dict[str, frozenset[str]]:
        rows = await self._session.execute(
            select(FleetVehicleTypeModel.code, FleetVehicleTypeModel.license_classes).where(
                FleetVehicleTypeModel.company_id == company_id
            )
        )
        return {row.code: frozenset(row.license_classes) for row in rows}

    async def vehicle_type_usage(self, company_id: uuid.UUID) -> dict[str, int]:
        rows = await self._session.execute(
            select(FleetVehicleModel.kind, func.count())
            .where(FleetVehicleModel.company_id == company_id)
            .group_by(FleetVehicleModel.kind)
        )
        return {row[0]: row[1] for row in rows.all()}

    # ------------------------------------------------------------ couplings

    async def open_coupling(self, vehicle_id: uuid.UUID) -> FleetVehicleCouplingModel | None:
        coupling: FleetVehicleCouplingModel | None = await self._session.scalar(
            select(FleetVehicleCouplingModel).where(
                or_(
                    FleetVehicleCouplingModel.tractor_id == vehicle_id,
                    FleetVehicleCouplingModel.trailer_id == vehicle_id,
                ),
                FleetVehicleCouplingModel.ended_at.is_(None),
            )
        )
        return coupling

    async def open_couplings_for_vehicles(
        self, company_id: uuid.UUID, vehicle_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, Any]]:
        """The unit each vehicle is hitched to, seen from either end."""
        if not vehicle_ids:
            return {}
        rows = await self._session.scalars(
            select(FleetVehicleCouplingModel).where(
                FleetVehicleCouplingModel.company_id == company_id,
                FleetVehicleCouplingModel.ended_at.is_(None),
                or_(
                    FleetVehicleCouplingModel.tractor_id.in_(list(vehicle_ids)),
                    FleetVehicleCouplingModel.trailer_id.in_(list(vehicle_ids)),
                ),
            )
        )
        couplings = list(rows)
        partner_ids = {item.tractor_id for item in couplings} | {
            item.trailer_id for item in couplings
        }
        partners = {
            row.id: row
            for row in await self._session.execute(
                select(FleetVehicleModel.id, FleetVehicleModel.code, FleetVehicleModel.plate).where(
                    FleetVehicleModel.id.in_(partner_ids)
                )
            )
        }
        result: dict[uuid.UUID, dict[str, Any]] = {}
        for item in couplings:
            for own, other, role in (
                (item.tractor_id, item.trailer_id, "tractor"),
                (item.trailer_id, item.tractor_id, "trailer"),
            ):
                partner = partners[other]
                result[own] = {
                    "coupling_id": item.id,
                    "role": role,
                    "vehicle_id": other,
                    "code": partner.code,
                    "plate": partner.plate,
                    "since": item.started_at,
                }
        return result

    # ------------------------------------------------------------- vehicles

    async def get_vehicle(
        self, company_id: uuid.UUID, vehicle_id: uuid.UUID, *, lock: bool = False
    ) -> FleetVehicleModel | None:
        statement = select(FleetVehicleModel).where(
            FleetVehicleModel.company_id == company_id, FleetVehicleModel.id == vehicle_id
        )
        if lock:
            statement = statement.with_for_update()
        vehicle: FleetVehicleModel | None = await self._session.scalar(statement)
        return vehicle

    def _vehicle_filter(
        self,
        company_id: uuid.UUID,
        branch_ids: list[uuid.UUID] | None,
        *,
        status: str | None = None,
        kind: str | None = None,
        search: str | None = None,
        include_retired: bool = True,
    ) -> list[Any]:
        conditions: list[Any] = [FleetVehicleModel.company_id == company_id]
        if branch_ids is not None:
            conditions.append(FleetVehicleModel.branch_id.in_(branch_ids))
        if status:
            conditions.append(FleetVehicleModel.status == status)
        elif not include_retired:
            conditions.append(FleetVehicleModel.status != "retired")
        if kind:
            conditions.append(FleetVehicleModel.kind == kind)
        if search and search.strip():
            pattern = _like(search.strip())
            conditions.append(
                or_(
                    FleetVehicleModel.code.ilike(pattern, escape="\\"),
                    FleetVehicleModel.plate.ilike(pattern, escape="\\"),
                    FleetVehicleModel.brand.ilike(pattern, escape="\\"),
                    FleetVehicleModel.model.ilike(pattern, escape="\\"),
                )
            )
        return conditions

    async def list_vehicles(
        self,
        company_id: uuid.UUID,
        branch_ids: list[uuid.UUID] | None,
        *,
        status: str | None,
        kind: str | None,
        search: str | None,
        include_retired: bool,
        page: int,
        size: int,
    ) -> tuple[list[FleetVehicleModel], int]:
        conditions = self._vehicle_filter(
            company_id,
            branch_ids,
            status=status,
            kind=kind,
            search=search,
            include_retired=include_retired,
        )
        total = int(
            await self._session.scalar(select(func.count(FleetVehicleModel.id)).where(*conditions))
            or 0
        )
        rows = await self._session.scalars(
            select(FleetVehicleModel)
            .where(*conditions)
            .order_by(FleetVehicleModel.code)
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(rows), total

    async def all_vehicles(
        self,
        company_id: uuid.UUID,
        branch_ids: list[uuid.UUID] | None,
        *,
        include_retired: bool = False,
    ) -> list[FleetVehicleModel]:
        rows = await self._session.scalars(
            select(FleetVehicleModel)
            .where(*self._vehicle_filter(company_id, branch_ids, include_retired=include_retired))
            .order_by(FleetVehicleModel.code)
        )
        return list(rows)

    async def conflicting_vehicle(
        self,
        company_id: uuid.UUID,
        *,
        code: str | None = None,
        plate: str | None = None,
        vin: str | None = None,
        exclude_id: uuid.UUID | None = None,
    ) -> str | None:
        """Return which visible field collides with another vehicle of the company."""
        checks = (
            ("code", code, func.lower(FleetVehicleModel.code), (code or "").lower()),
            ("plate", plate, func.upper(FleetVehicleModel.plate), (plate or "").upper()),
            ("vin", vin, func.upper(FleetVehicleModel.vin), (vin or "").upper()),
        )
        for field, value, column, normalized in checks:
            if not value:
                continue
            statement = select(FleetVehicleModel.id).where(
                FleetVehicleModel.company_id == company_id, column == normalized
            )
            if exclude_id is not None:
                statement = statement.where(FleetVehicleModel.id != exclude_id)
            if await self._session.scalar(statement.limit(1)) is not None:
                return field
        return None

    async def branch(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> Branch | None:
        branch: Branch | None = await self._session.scalar(
            select(Branch).where(
                Branch.company_id == company_id,
                Branch.id == branch_id,
                Branch.deleted_at.is_(None),
            )
        )
        return branch

    async def supplier_names(self, company_id: uuid.UUID, ids: Iterable[int]) -> dict[int, str]:
        wanted = list(set(ids))
        if not wanted:
            return {}
        # Un proveedor en papelera sigue siendo el dueño o taller de lo ya registrado.
        rows = await self._session.execute(
            select(SupplierModel.id_supplier, SupplierModel.name)
            .where(SupplierModel.company_id == company_id, SupplierModel.id_supplier.in_(wanted))
            .execution_options(include_deleted=True)
        )
        return {row[0]: row[1] for row in rows.all()}

    async def branch_names(
        self, company_id: uuid.UUID, ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        wanted = list(set(ids))
        if not wanted:
            return {}
        rows = await self._session.execute(
            select(Branch.id, Branch.name).where(
                Branch.company_id == company_id, Branch.id.in_(wanted)
            )
        )
        return {row.id: row.name for row in rows}

    # ------------------------------------------------------------- documents

    async def required_categories(
        self, company_id: uuid.UUID, module: str, *, codes: frozenset[str] | None = None
    ) -> list[RequiredCategory]:
        statement = select(DocumentCategoryModel.id, DocumentCategoryModel.name).where(
            DocumentCategoryModel.company_id == company_id,
            DocumentCategoryModel.module == module,
            DocumentCategoryModel.is_active.is_(True),
            DocumentCategoryModel.compliance_required.is_(True),
        )
        if codes is not None:
            statement = statement.where(DocumentCategoryModel.code.in_(sorted(codes)))
        rows = await self._session.execute(statement.order_by(DocumentCategoryModel.sort_order))
        return [RequiredCategory(id=row.id, name=row.name) for row in rows]

    async def document_expiries(
        self,
        company_id: uuid.UUID,
        *,
        module: str,
        owner_type: str,
        owner_ids: Sequence[uuid.UUID],
        category_ids: Sequence[uuid.UUID],
    ) -> dict[uuid.UUID, dict[uuid.UUID, date | None]]:
        """Latest expiry of each owner's current, clean documents per category.

        A document counts only when its file passed the malware scan
        (``active``) and was not sent to the trash.
        """
        if not owner_ids or not category_ids:
            return {}
        rows = await self._session.execute(
            select(
                DocumentRecordModel.owner_id,
                DocumentRecordModel.category_id,
                DocumentRecordModel.expires_on,
            )
            .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .where(
                DocumentRecordModel.company_id == company_id,
                DocumentRecordModel.module == module,
                DocumentRecordModel.owner_type == owner_type,
                DocumentRecordModel.owner_id.in_(list(owner_ids)),
                DocumentRecordModel.category_id.in_(list(category_ids)),
                DocumentRecordModel.is_current.is_(True),
                DocumentAssetModel.status == "active",
                DocumentAssetModel.deleted_at.is_(None),
            )
        )
        result: dict[uuid.UUID, dict[uuid.UUID, date | None]] = {}
        for owner_id, category_id, expires_on in rows:
            per_owner = result.setdefault(owner_id, {})
            if category_id not in per_owner:
                per_owner[category_id] = expires_on
                continue
            previous = per_owner[category_id]
            # Un documento sin vencimiento cuenta como vigente; si no, vale el más lejano.
            if previous is not None and (expires_on is None or expires_on > previous):
                per_owner[category_id] = expires_on
        return result

    # ------------------------------------------------------------- assignments

    async def open_assignments_for_vehicles(
        self, vehicle_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, Any]]:
        if not vehicle_ids:
            return {}
        rows = await self._session.execute(
            select(
                VehicleDriverAssignmentModel.id,
                VehicleDriverAssignmentModel.vehicle_id,
                VehicleDriverAssignmentModel.starts_at,
                DriverModel.id.label("driver_id"),
                DriverModel.license_class,
                DriverModel.status.label("driver_status"),
                Employee.first_name,
                Employee.last_name,
                Employee.photo_url,
            )
            .join(DriverModel, DriverModel.id == VehicleDriverAssignmentModel.driver_id)
            .join(
                Employee,
                and_(
                    Employee.id == DriverModel.employee_id,
                    Employee.company_id == DriverModel.company_id,
                ),
            )
            .where(
                VehicleDriverAssignmentModel.vehicle_id.in_(list(vehicle_ids)),
                VehicleDriverAssignmentModel.ends_at.is_(None),
            )
        )
        return {
            row.vehicle_id: {
                "assignment_id": row.id,
                "driver_id": row.driver_id,
                "name": f"{row.first_name} {row.last_name}".strip(),
                "initials": initials(row.first_name, row.last_name),
                "photo_url": row.photo_url,
                "license_class": row.license_class,
                "status": row.driver_status,
                "since": row.starts_at,
            }
            for row in rows
        }

    async def open_assignment_for_driver(
        self, driver_id: uuid.UUID
    ) -> VehicleDriverAssignmentModel | None:
        assignment: VehicleDriverAssignmentModel | None = await self._session.scalar(
            select(VehicleDriverAssignmentModel).where(
                VehicleDriverAssignmentModel.driver_id == driver_id,
                VehicleDriverAssignmentModel.ends_at.is_(None),
            )
        )
        return assignment

    async def open_assignment_for_vehicle(
        self, vehicle_id: uuid.UUID, *, lock: bool = False
    ) -> VehicleDriverAssignmentModel | None:
        statement = select(VehicleDriverAssignmentModel).where(
            VehicleDriverAssignmentModel.vehicle_id == vehicle_id,
            VehicleDriverAssignmentModel.ends_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        assignment: VehicleDriverAssignmentModel | None = await self._session.scalar(statement)
        return assignment

    # ------------------------------------------------------------- transfers

    async def active_transfers(
        self, company_id: uuid.UUID, inventory_vehicle_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, Any]]:
        """Transfers currently on the road, keyed by inventory vehicle id."""
        if not inventory_vehicle_ids:
            return {}
        destination = (
            select(Warehouse.id, Branch.name)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .subquery()
        )
        rows = await self._session.execute(
            select(
                InventoryTransferModel.id,
                InventoryTransferModel.code,
                InventoryTransferModel.vehicle_id,
                InventoryTransferModel.status,
                InventoryTransferModel.dispatched_at,
                destination.c.name.label("destination_branch"),
            )
            .join(destination, destination.c.id == InventoryTransferModel.destination_warehouse_id)
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.vehicle_id.in_(list(inventory_vehicle_ids)),
                InventoryTransferModel.status.in_(ACTIVE_TRANSFER_STATUSES),
            )
            .order_by(InventoryTransferModel.dispatched_at.desc().nulls_last())
        )
        result: dict[uuid.UUID, dict[str, Any]] = {}
        for row in rows:
            result.setdefault(
                row.vehicle_id,
                {
                    "id": row.id,
                    "code": row.code,
                    "status": row.status,
                    "dispatched_at": row.dispatched_at,
                    "destination_branch": row.destination_branch,
                },
            )
        return result

    # ------------------------------------------------------------- maintenance

    async def maintenance_state(
        self, vehicle_ids: Sequence[uuid.UUID]
    ) -> tuple[dict[uuid.UUID, list[MaintenancePlanModel]], set[uuid.UUID]]:
        """Active plans per vehicle and the vehicles with an order in progress."""
        if not vehicle_ids:
            return {}, set()
        plans = await self._session.scalars(
            select(MaintenancePlanModel).where(
                MaintenancePlanModel.vehicle_id.in_(list(vehicle_ids)),
                MaintenancePlanModel.is_active.is_(True),
            )
        )
        by_vehicle: dict[uuid.UUID, list[MaintenancePlanModel]] = {}
        for plan in plans:
            by_vehicle.setdefault(plan.vehicle_id, []).append(plan)
        in_progress = set(
            await self._session.scalars(
                select(MaintenanceOrderModel.vehicle_id).where(
                    MaintenanceOrderModel.vehicle_id.in_(list(vehicle_ids)),
                    MaintenanceOrderModel.status == "in_progress",
                )
            )
        )
        return by_vehicle, in_progress

    # ------------------------------------------------------------- photos

    async def photos(self, vehicle_id: uuid.UUID) -> list[FleetVehiclePhotoModel]:
        rows = await self._session.scalars(
            select(FleetVehiclePhotoModel)
            .where(FleetVehiclePhotoModel.vehicle_id == vehicle_id)
            .order_by(FleetVehiclePhotoModel.position, FleetVehiclePhotoModel.created_at)
        )
        return list(rows)

    # ------------------------------------------------------------- drivers

    async def employee_has_branch_assignment(
        self, employee_id: uuid.UUID, branch_id: uuid.UUID
    ) -> bool:
        found = await self._session.scalar(
            select(EmployeeBranchAssignment.id)
            .where(
                EmployeeBranchAssignment.employee_id == employee_id,
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
                or_(
                    EmployeeBranchAssignment.assigned_until.is_(None),
                    EmployeeBranchAssignment.assigned_until >= func.current_date(),
                ),
            )
            .limit(1)
        )
        return found is not None

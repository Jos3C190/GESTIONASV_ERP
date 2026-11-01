"""Driver read queries for :class:`FleetRepository` (kept apart for readability)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, func, or_, select

from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_record import DocumentRecordModel
from app.infrastructure.models.employee import Employee, EmployeeBranchAssignment
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleModel,
    VehicleDriverAssignmentModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch, Warehouse


def like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _active_assignment() -> list[Any]:
    return [
        EmployeeBranchAssignment.is_active.is_(True),
        or_(
            EmployeeBranchAssignment.assigned_until.is_(None),
            EmployeeBranchAssignment.assigned_until >= func.current_date(),
        ),
    ]


class DriverQueries:
    _session: Any

    def driver_query(self) -> Select[Any]:
        return select(DriverModel, Employee).join(
            Employee,
            and_(
                Employee.id == DriverModel.employee_id,
                Employee.company_id == DriverModel.company_id,
            ),
        )

    async def get_driver(
        self, company_id: uuid.UUID, driver_id: uuid.UUID, *, lock: bool = False
    ) -> DriverModel | None:
        statement = select(DriverModel).where(
            DriverModel.company_id == company_id, DriverModel.id == driver_id
        )
        if lock:
            statement = statement.with_for_update()
        driver: DriverModel | None = await self._session.scalar(statement)
        return driver

    async def driver_with_employee(
        self, company_id: uuid.UUID, driver_id: uuid.UUID
    ) -> tuple[DriverModel, Employee] | None:
        row = (
            await self._session.execute(
                self.driver_query().where(
                    DriverModel.company_id == company_id, DriverModel.id == driver_id
                )
            )
        ).first()
        return (row[0], row[1]) if row is not None else None

    async def list_drivers(
        self,
        company_id: uuid.UUID,
        branch_ids: list[uuid.UUID] | None,
        *,
        status: str | None,
        search: str | None,
        page: int,
        size: int,
    ) -> tuple[list[tuple[DriverModel, Employee]], int]:
        conditions: list[Any] = [DriverModel.company_id == company_id]
        if branch_ids is not None:
            conditions.append(DriverModel.branch_id.in_(branch_ids))
        if status:
            conditions.append(DriverModel.status == status)
        if search and search.strip():
            pattern = like(search.strip())
            conditions.append(
                or_(
                    Employee.first_name.ilike(pattern, escape="\\"),
                    Employee.last_name.ilike(pattern, escape="\\"),
                    Employee.employee_code.ilike(pattern, escape="\\"),
                    Employee.document_id.ilike(pattern, escape="\\"),
                )
            )
        base = self.driver_query().where(*conditions)
        total = int(
            await self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        )
        rows = await self._session.execute(
            base.order_by(Employee.first_name, Employee.last_name)
            .offset((page - 1) * size)
            .limit(size)
        )
        return [(row[0], row[1]) for row in rows.all()], total

    async def license_records(
        self,
        company_id: uuid.UUID,
        employee_ids: Sequence[uuid.UUID],
        category_ids: Sequence[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, Any]]:
        """Most relevant current driving license per employee (latest expiry)."""
        if not employee_ids or not category_ids:
            return {}
        rows = await self._session.execute(
            select(
                DocumentRecordModel.id,
                DocumentRecordModel.owner_id,
                DocumentRecordModel.reference_code,
                DocumentRecordModel.expires_on,
            )
            .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .where(
                DocumentRecordModel.company_id == company_id,
                DocumentRecordModel.module == "employees",
                DocumentRecordModel.owner_type == "employee",
                DocumentRecordModel.owner_id.in_(list(employee_ids)),
                DocumentRecordModel.category_id.in_(list(category_ids)),
                DocumentRecordModel.is_current.is_(True),
                DocumentAssetModel.status == "active",
                DocumentAssetModel.deleted_at.is_(None),
            )
            .order_by(DocumentRecordModel.expires_on.desc().nulls_first())
        )
        result: dict[uuid.UUID, dict[str, Any]] = {}
        for row in rows:
            result.setdefault(
                row.owner_id,
                {
                    "document_id": row.id,
                    "number": row.reference_code,
                    "expires_on": row.expires_on,
                },
            )
        return result

    async def open_vehicles_for_drivers(
        self, driver_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, Any]]:
        if not driver_ids:
            return {}
        rows = await self._session.execute(
            select(
                VehicleDriverAssignmentModel.id,
                VehicleDriverAssignmentModel.driver_id,
                VehicleDriverAssignmentModel.starts_at,
                FleetVehicleModel.id.label("vehicle_id"),
                FleetVehicleModel.code,
                FleetVehicleModel.plate,
                FleetVehicleModel.kind,
            )
            .join(
                FleetVehicleModel, FleetVehicleModel.id == VehicleDriverAssignmentModel.vehicle_id
            )
            .where(
                VehicleDriverAssignmentModel.driver_id.in_(list(driver_ids)),
                VehicleDriverAssignmentModel.ends_at.is_(None),
            )
        )
        return {
            row.driver_id: {
                "assignment_id": row.id,
                "vehicle_id": row.vehicle_id,
                "code": row.code,
                "plate": row.plate,
                "kind": row.kind,
                "since": row.starts_at,
            }
            for row in rows
        }

    async def employees_with_assignment(
        self, employee_ids: Sequence[uuid.UUID], branch_ids: Sequence[uuid.UUID]
    ) -> set[tuple[uuid.UUID, uuid.UUID]]:
        if not employee_ids or not branch_ids:
            return set()
        rows = await self._session.execute(
            select(EmployeeBranchAssignment.employee_id, EmployeeBranchAssignment.branch_id).where(
                EmployeeBranchAssignment.employee_id.in_(list(employee_ids)),
                EmployeeBranchAssignment.branch_id.in_(list(branch_ids)),
                *_active_assignment(),
            )
        )
        return {(row.employee_id, row.branch_id) for row in rows}

    async def driver_candidates(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, search: str | None
    ) -> list[Employee]:
        """Active employees assigned to the branch who are not drivers yet."""
        existing = select(DriverModel.employee_id).where(
            DriverModel.company_id == company_id, DriverModel.deleted_at.is_(None)
        )
        statement = (
            select(Employee)
            .join(EmployeeBranchAssignment, EmployeeBranchAssignment.employee_id == Employee.id)
            .where(
                Employee.company_id == company_id,
                Employee.status == "activo",
                EmployeeBranchAssignment.branch_id == branch_id,
                *_active_assignment(),
                Employee.id.not_in(existing),
            )
            .distinct()
            .order_by(Employee.first_name, Employee.last_name)
            .limit(50)
        )
        if search and search.strip():
            pattern = like(search.strip())
            statement = statement.where(
                or_(
                    Employee.first_name.ilike(pattern, escape="\\"),
                    Employee.last_name.ilike(pattern, escape="\\"),
                    Employee.employee_code.ilike(pattern, escape="\\"),
                )
            )
        return list(await self._session.scalars(statement))

    async def assignment_history(
        self, *, vehicle_id: uuid.UUID | None = None, driver_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        conditions: list[Any] = []
        if vehicle_id is not None:
            conditions.append(VehicleDriverAssignmentModel.vehicle_id == vehicle_id)
        if driver_id is not None:
            conditions.append(VehicleDriverAssignmentModel.driver_id == driver_id)
        rows = await self._session.execute(
            select(
                VehicleDriverAssignmentModel,
                FleetVehicleModel.code,
                FleetVehicleModel.plate,
                Employee.first_name,
                Employee.last_name,
            )
            .join(
                FleetVehicleModel, FleetVehicleModel.id == VehicleDriverAssignmentModel.vehicle_id
            )
            .join(DriverModel, DriverModel.id == VehicleDriverAssignmentModel.driver_id)
            .join(
                Employee,
                and_(
                    Employee.id == DriverModel.employee_id,
                    Employee.company_id == DriverModel.company_id,
                ),
            )
            .where(*conditions)
            .execution_options(include_deleted=True)
            .order_by(VehicleDriverAssignmentModel.starts_at.desc())
            .limit(100)
        )
        return [
            {
                "id": assignment.id,
                "vehicle_id": assignment.vehicle_id,
                "vehicle_code": code,
                "vehicle_plate": plate,
                "driver_id": assignment.driver_id,
                "driver_name": f"{first} {last}".strip(),
                "starts_at": assignment.starts_at,
                "ends_at": assignment.ends_at,
                "end_reason": assignment.end_reason,
            }
            for assignment, code, plate, first, last in rows.all()
        ]

    async def driver_trips(
        self, company_id: uuid.UUID, driver_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        origin = (
            select(Warehouse.id, Branch.name)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .subquery()
        )
        destination = (
            select(Warehouse.id, Branch.name)
            .join(Branch, Branch.id == Warehouse.branch_id)
            .subquery()
        )
        rows = await self._session.execute(
            select(
                InventoryTransferModel.id,
                InventoryTransferModel.code,
                InventoryTransferModel.status,
                InventoryTransferModel.dispatched_at,
                InventoryTransferModel.received_at,
                InventoryVehicleModel.code.label("vehicle_code"),
                origin.c.name.label("origin_branch"),
                destination.c.name.label("destination_branch"),
            )
            .join(origin, origin.c.id == InventoryTransferModel.origin_warehouse_id)
            .join(destination, destination.c.id == InventoryTransferModel.destination_warehouse_id)
            .outerjoin(
                InventoryVehicleModel, InventoryVehicleModel.id == InventoryTransferModel.vehicle_id
            )
            .where(
                InventoryTransferModel.company_id == company_id,
                InventoryTransferModel.driver_id == driver_id,
            )
            .order_by(InventoryTransferModel.dispatched_at.desc().nulls_last())
            .limit(50)
        )
        return [
            {
                "transfer_id": row.id,
                "code": row.code,
                "status": row.status,
                "vehicle_code": row.vehicle_code,
                "origin_branch": row.origin_branch,
                "destination_branch": row.destination_branch,
                "dispatched_at": row.dispatched_at,
                "received_at": row.received_at,
            }
            for row in rows
        ]

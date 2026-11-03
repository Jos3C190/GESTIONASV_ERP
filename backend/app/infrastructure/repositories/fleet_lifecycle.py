"""Trash rules for fleet vehicles and driver profiles.

A vehicle or driver can only go to the trash once it no longer takes part in
operations (open assignment, transfer on the road, open workshop order, GPS
link), and can only come back while its branch and employee still exist.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import (
    DriverModel,
    FleetVehicleModel,
    MaintenanceOrderModel,
    VehicleDriverAssignmentModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferModel,
    InventoryVehicleModel,
)
from app.infrastructure.models.organization import Branch

FLEET_RESOURCES = frozenset({"fleet_vehicles", "drivers"})
ON_ROAD_STATUSES = ("in_transit", "incident")


async def _exists(session: AsyncSession, model: type[Any], *conditions: Any) -> bool:
    return (await session.scalar(select(model).where(*conditions).limit(1))) is not None


async def fleet_deletion_blockers(session: AsyncSession, resource: str, record: Any) -> list[str]:
    blockers: list[str] = []
    if resource == "fleet_vehicles":
        if await _exists(
            session,
            VehicleDriverAssignmentModel,
            VehicleDriverAssignmentModel.vehicle_id == record.id,
            VehicleDriverAssignmentModel.ends_at.is_(None),
        ):
            blockers.append("un conductor asignado")
        if record.inventory_vehicle_id is not None and await _exists(
            session,
            InventoryTransferModel,
            InventoryTransferModel.vehicle_id == record.inventory_vehicle_id,
            InventoryTransferModel.status.in_(ON_ROAD_STATUSES),
        ):
            blockers.append("un traslado en ruta")
        if await _exists(
            session,
            MaintenanceOrderModel,
            MaintenanceOrderModel.vehicle_id == record.id,
            MaintenanceOrderModel.status.in_(("scheduled", "in_progress")),
        ):
            blockers.append("órdenes de mantenimiento abiertas")
        if record.traccar_device_id is not None:
            blockers.append("un GPS vinculado")
    elif resource == "drivers":
        if await _exists(
            session,
            VehicleDriverAssignmentModel,
            VehicleDriverAssignmentModel.driver_id == record.id,
            VehicleDriverAssignmentModel.ends_at.is_(None),
        ):
            blockers.append("un vehículo asignado")
        if await _exists(
            session,
            InventoryTransferModel,
            InventoryTransferModel.driver_id == record.id,
            InventoryTransferModel.status.in_(ON_ROAD_STATUSES),
        ):
            blockers.append("un traslado en ruta")
    return blockers


async def employee_driver_blocker(session: AsyncSession, employee_id: Any) -> str | None:
    if await _exists(session, DriverModel, DriverModel.employee_id == employee_id):
        return "un perfil de conductor"
    return None


async def fleet_restore_blockers(session: AsyncSession, resource: str, record: Any) -> list[str]:
    blockers: list[str] = []
    if not await _exists(session, Branch, Branch.id == record.branch_id):
        blockers.append("la sucursal base está eliminada")
    if resource == "drivers":
        employee = await session.scalar(select(Employee).where(Employee.id == record.employee_id))
        if employee is None:
            blockers.append("el empleado está eliminado")
        elif employee.status != "activo":
            blockers.append("el empleado no está activo")
    elif resource == "fleet_vehicles":
        blockers.extend(await _identity_conflicts(session, record))
    return blockers


async def _identity_conflicts(session: AsyncSession, record: FleetVehicleModel) -> list[str]:
    """Another vehicle may have taken its code, plate or VIN while it was in the trash."""
    conflicts: list[str] = []
    for label, column, value in (
        ("el código", FleetVehicleModel.code, record.code),
        ("la placa", FleetVehicleModel.plate, record.plate),
        ("el VIN", FleetVehicleModel.vin, record.vin),
    ):
        if value is not None and await _exists(
            session,
            FleetVehicleModel,
            FleetVehicleModel.company_id == record.company_id,
            FleetVehicleModel.id != record.id,
            FleetVehicleModel.deleted_at.is_(None),
            column == value,
        ):
            conflicts.append(f"{label} {value} ya lo usa otro vehículo")
    return conflicts


async def on_fleet_deleted(session: AsyncSession, resource: str, record: Any) -> None:
    """A vehicle in the trash cannot be selected for transfers."""
    if resource == "fleet_vehicles" and record.inventory_vehicle_id is not None:
        vehicle = await session.get(InventoryVehicleModel, record.inventory_vehicle_id)
        if vehicle is not None:
            vehicle.status = "inactive"


async def on_fleet_restored(session: AsyncSession, resource: str, record: Any) -> None:
    if resource == "fleet_vehicles" and record.inventory_vehicle_id is not None:
        vehicle = await session.get(InventoryVehicleModel, record.inventory_vehicle_id)
        # En mantenimiento sigue activo para Inventario, igual que fuera de la papelera.
        if vehicle is not None and record.status in {"active", "maintenance"}:
            vehicle.status = "active"


async def reload_label(session: AsyncSession, resource: str, record: Any) -> None:
    """The driver's name is computed in SQL and expires on flush; load it again."""
    if resource == "drivers":
        await session.refresh(record, ["display_name"])


__all__ = [
    "FLEET_RESOURCES",
    "employee_driver_blocker",
    "fleet_deletion_blockers",
    "fleet_restore_blockers",
    "on_fleet_deleted",
    "on_fleet_restored",
    "reload_label",
]

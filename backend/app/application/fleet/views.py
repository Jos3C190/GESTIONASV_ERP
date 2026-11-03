"""Read models for fleet vehicles: fitness, current driver, trip and maintenance."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.application.fleet.compliance import (
    Issue,
    document_issues,
    state_of,
    vehicle_issues,
)

#: Remaining distance/time that turns a maintenance plan into a "due soon" warning.
MAINTENANCE_WARNING_KM = 500
MAINTENANCE_WARNING_DAYS = 7


def plan_due(plan: Any, odometer_km: Decimal, today: date) -> dict[str, Any]:
    """Next service of a maintenance plan and how close it is."""
    due_km = (
        Decimal(plan.last_service_km) + plan.interval_km
        if plan.interval_km is not None and plan.last_service_km is not None
        else None
    )
    due_on = (
        plan.last_service_on + timedelta(days=plan.interval_days)
        if plan.interval_days is not None and plan.last_service_on is not None
        else None
    )
    overdue = (due_km is not None and odometer_km >= due_km) or (
        due_on is not None and today >= due_on
    )
    soon = not overdue and (
        (due_km is not None and due_km - odometer_km <= MAINTENANCE_WARNING_KM)
        or (due_on is not None and (due_on - today).days <= MAINTENANCE_WARNING_DAYS)
    )
    never = plan.last_service_km is None and plan.last_service_on is None
    return {
        "due_km": due_km,
        "due_on": due_on,
        "state": "overdue" if overdue else "soon" if soon else "unknown" if never else "ok",
    }


def maintenance_issues(plans: Sequence[Any], odometer_km: Decimal, today: date) -> list[Issue]:
    issues: list[Issue] = []
    for plan in plans:
        state = plan_due(plan, odometer_km, today)["state"]
        if state == "overdue":
            issues.append(
                Issue("maintenance_overdue", "warning", f"Mantenimiento vencido: {plan.name}.")
            )
        elif state == "soon":
            issues.append(
                Issue("maintenance_due_soon", "warning", f"Mantenimiento próximo: {plan.name}.")
            )
    return issues


def vehicle_type_view(item: Any) -> dict[str, Any]:
    return {
        "code": item.code,
        "name": item.name,
        "plural": item.plural,
        "license_classes": list(item.license_classes),
        "base_image": item.base_image,
        "requires_plate": item.requires_plate,
        "requires_capacity": item.requires_capacity,
        "meter_unit": item.meter_unit,
        "fuel_applicable": item.fuel_applicable,
        "can_tow": item.can_tow,
        "is_towable": item.is_towable,
        "is_system": item.is_system,
        "is_active": item.is_active,
    }


async def build_vehicle_views(
    repo: Any,
    company_id: uuid.UUID,
    vehicles: Sequence[Any],
    *,
    today: date,
) -> list[dict[str, Any]]:
    if not vehicles:
        return []
    vehicle_ids = [vehicle.id for vehicle in vehicles]
    required = await repo.required_categories(company_id, "fleet")
    expiries = await repo.document_expiries(
        company_id,
        module="fleet",
        owner_type="vehicle",
        owner_ids=vehicle_ids,
        category_ids=[category.id for category in required],
    )
    drivers = await repo.open_assignments_for_vehicles(vehicle_ids)
    transfers = await repo.active_transfers(
        company_id, [v.inventory_vehicle_id for v in vehicles if v.inventory_vehicle_id]
    )
    plans, in_progress = await repo.maintenance_state(vehicle_ids)
    branches = await repo.branch_names(company_id, [vehicle.branch_id for vehicle in vehicles])
    types = {item.code: item for item in await repo.vehicle_types(company_id)}
    couplings = await repo.open_couplings_for_vehicles(company_id, vehicle_ids)
    views: list[dict[str, Any]] = []
    for vehicle in vehicles:
        odometer = Decimal(vehicle.odometer_km)
        vehicle_type = types[vehicle.kind]
        # Sin placa no circula por la vía pública: no aplican los documentos de circulación.
        documents = (
            document_issues(required, expiries.get(vehicle.id, {}), today=today)
            if vehicle_type.requires_plate
            else []
        )
        issues = vehicle_issues(
            status=vehicle.status,
            documents=documents,
            maintenance=maintenance_issues(plans.get(vehicle.id, []), odometer, today),
        )
        if vehicle.inventory_vehicle_id is None and vehicle.status != "retired":
            issues.append(
                Issue(
                    "transfers_not_enabled",
                    "warning",
                    "Aún no puede usarse en traslados: la empresa necesita una sucursal matriz "
                    "con bodega central activa.",
                )
            )
        trip = transfers.get(vehicle.inventory_vehicle_id) if vehicle.inventory_vehicle_id else None
        operational = (
            "in_route"
            if trip is not None and vehicle.status == "active"
            else ("available" if vehicle.status == "active" else vehicle.status)
        )
        views.append(
            {
                "id": vehicle.id,
                "code": vehicle.code,
                "plate": vehicle.plate,
                "vin": vehicle.vin,
                "kind": vehicle.kind,
                "type": vehicle_type_view(vehicle_type),
                "coupling": couplings.get(vehicle.id),
                "brand": vehicle.brand,
                "model": vehicle.model,
                "year": vehicle.year,
                "color": vehicle.color,
                "capacity_kg": vehicle.capacity_kg,
                "tank_liters": vehicle.tank_liters,
                "fuel_type": vehicle.fuel_type,
                "odometer_km": odometer,
                "status": vehicle.status,
                "operational_status": operational,
                "branch_id": vehicle.branch_id,
                "branch_name": branches.get(vehicle.branch_id, ""),
                "driver": drivers.get(vehicle.id),
                "current_transfer": trip,
                "maintenance_in_progress": vehicle.id in in_progress,
                "gps_linked": vehicle.traccar_device_id is not None,
                "gps_device_unique_id": vehicle.gps_device_unique_id,
                "inventory_vehicle_id": vehicle.inventory_vehicle_id,
                "notes": vehicle.notes,
                "compliance": {
                    "state": state_of(issues),
                    "issues": [
                        {"code": issue.code, "severity": issue.severity, "message": issue.message}
                        for issue in issues
                    ],
                },
                "created_at": vehicle.created_at,
                "updated_at": vehicle.updated_at,
            }
        )
    return views


def summarize(views: Sequence[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(views),
        "available": 0,
        "in_route": 0,
        "maintenance": 0,
        "out_of_service": 0,
        "blocked": 0,
        "with_warnings": 0,
    }
    for view in views:
        operational = view["operational_status"]
        if operational in summary:
            summary[operational] += 1
        state = view["compliance"]["state"]
        if state == "blocked":
            summary["blocked"] += 1
        elif state == "warning":
            summary["with_warnings"] += 1
    return summary

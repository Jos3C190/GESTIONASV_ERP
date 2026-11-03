"""Read models and fitness for drivers (employees with a driving profile)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from app.application.fleet.compliance import (
    Issue,
    document_issues,
    driver_issues,
    license_issue,
    state_of,
)
from app.infrastructure.document_categories import DRIVER_CATEGORY_CODES


def _initials(first_name: str, last_name: str) -> str:
    return (first_name.strip()[:1] + last_name.strip()[:1]).upper() or "?"


def issues_out(issues: Sequence[Issue]) -> dict[str, Any]:
    return {
        "state": state_of(issues),
        "issues": [
            {"code": issue.code, "severity": issue.severity, "message": issue.message}
            for issue in issues
        ],
    }


async def driver_fitness(
    repo: Any,
    company_id: uuid.UUID,
    rows: Sequence[tuple[Any, Any]],
    *,
    today: date,
    vehicle_kinds: dict[uuid.UUID, str] | None = None,
) -> dict[uuid.UUID, tuple[list[Issue], dict[str, Any] | None]]:
    """Issues and current license of each driver.

    ``vehicle_kinds`` optionally maps a driver id to the kind of a vehicle the
    driver is about to drive, to also check the license class.
    """
    required = await repo.required_categories(company_id, "employees", codes=DRIVER_CATEGORY_CODES)
    employee_ids = [employee.id for _, employee in rows]
    expiries = await repo.document_expiries(
        company_id,
        module="employees",
        owner_type="employee",
        owner_ids=employee_ids,
        category_ids=[category.id for category in required],
    )
    licenses = await repo.license_records(
        company_id, employee_ids, [category.id for category in required]
    )
    assigned = await repo.employees_with_assignment(
        employee_ids, list({driver.branch_id for driver, _ in rows})
    )
    rules = await repo.license_rules(company_id) if vehicle_kinds else {}
    settings = await repo.fleet_settings(company_id)
    result: dict[uuid.UUID, tuple[list[Issue], dict[str, Any] | None]] = {}
    for driver, employee in rows:
        issues = driver_issues(
            driver_status=driver.status,
            employee_status=employee.status,
            has_home_branch_assignment=(employee.id, driver.branch_id) in assigned,
            documents=document_issues(
                required,
                expiries.get(employee.id, {}),
                today=today,
                warning_days=settings.document_warning_days,
            ),
        )
        kind = (vehicle_kinds or {}).get(driver.id)
        if kind is not None:
            mismatch = license_issue(driver.license_class, kind, rules)
            if mismatch is not None:
                issues.append(mismatch)
        result[driver.id] = (issues, licenses.get(employee.id))
    return result


async def build_driver_views(
    repo: Any,
    company_id: uuid.UUID,
    rows: Sequence[tuple[Any, Any]],
    *,
    today: date,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    vehicles = await repo.open_vehicles_for_drivers([driver.id for driver, _ in rows])
    fitness = await driver_fitness(
        repo,
        company_id,
        rows,
        today=today,
        vehicle_kinds={driver_id: info["kind"] for driver_id, info in vehicles.items()},
    )
    branches = await repo.branch_names(company_id, [driver.branch_id for driver, _ in rows])
    views: list[dict[str, Any]] = []
    for driver, employee in rows:
        issues, license_record = fitness[driver.id]
        views.append(
            {
                "id": driver.id,
                "employee": {
                    "id": employee.id,
                    "code": employee.employee_code,
                    "name": f"{employee.first_name} {employee.last_name}".strip(),
                    "initials": _initials(employee.first_name, employee.last_name),
                    "document_id": employee.document_id,
                    "phone": employee.phone,
                    "photo_url": employee.photo_url,
                    "position": employee.position,
                    "status": employee.status,
                },
                "branch_id": driver.branch_id,
                "branch_name": branches.get(driver.branch_id, ""),
                "license": {
                    "license_class": driver.license_class,
                    "number": (license_record or {}).get("number"),
                    "expires_on": (license_record or {}).get("expires_on"),
                    "document_id": (license_record or {}).get("document_id"),
                },
                "status": driver.status,
                "status_reason": driver.status_reason,
                "notes": driver.notes,
                "vehicle": vehicles.get(driver.id),
                "compliance": issues_out(issues),
                "created_at": driver.created_at,
                "updated_at": driver.updated_at,
            }
        )
    return views

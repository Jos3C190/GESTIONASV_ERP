"""Operational fitness of vehicles and drivers.

One place decides whether a vehicle may be assigned or dispatched and whether
a driver may drive it. Everything here is pure so the rules are easy to test
and identical for the fleet screen, the drivers screen and transfer dispatch.

Severity:

* ``blocking`` — the operation is refused unless a user with
  ``fleet:compliance_override`` authorises it with a reason.
* ``warning`` — shown to the user, never blocks.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

Severity = Literal["blocking", "warning"]
ComplianceState = Literal["ok", "warning", "blocked"]

#: Documents expiring within this window raise a warning.
EXPIRY_WARNING_DAYS = 30

#: License classes allowed to drive each vehicle kind (El Salvador classes).
_LIGHT = frozenset({"liviana", "pesada", "pesada_t"})
_HEAVY = frozenset({"pesada", "pesada_t"})
_ARTICULATED = frozenset({"pesada_t"})
LICENSE_CLASSES_BY_KIND: Mapping[str, frozenset[str]] = {
    "pickup": _LIGHT | {"particular"},
    "compact_van": _LIGHT,
    "cargo_van": _LIGHT,
    "refrigerated": _HEAVY,
    "dry_box": _HEAVY,
    "flatbed": _HEAVY,
    "curtain_side": _HEAVY,
    "semi_trailer": _ARTICULATED,
    "tanker": _ARTICULATED,
}

LICENSE_CLASS_LABELS: Mapping[str, str] = {
    "particular": "Particular",
    "liviana": "Liviana",
    "pesada": "Pesada",
    "pesada_t": "Pesada T",
    "motocicleta": "Motocicleta",
}

VEHICLE_STATUS_LABELS: Mapping[str, str] = {
    "active": "Activo",
    "maintenance": "En mantenimiento",
    "out_of_service": "Fuera de servicio",
    "retired": "Dado de baja",
}


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    severity: Severity
    message: str


@dataclass(frozen=True, slots=True)
class RequiredCategory:
    id: uuid.UUID
    name: str


def state_of(issues: Iterable[Issue]) -> ComplianceState:
    items = list(issues)
    if any(issue.severity == "blocking" for issue in items):
        return "blocked"
    return "warning" if items else "ok"


def _format(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def document_issues(
    required: Iterable[RequiredCategory],
    expiries: Mapping[uuid.UUID, date | None],
    *,
    today: date,
    subject: str = "",
) -> list[Issue]:
    """Issues for mandatory documents.

    ``expiries`` maps a category id to the latest expiry among the owner's
    current, active documents of that category (``None`` = no expiry). A
    category missing from the mapping means there is no valid document.
    """
    issues: list[Issue] = []
    suffix = f" {subject}" if subject else ""
    for category in required:
        if category.id not in expiries:
            issues.append(Issue("document_missing", "blocking", f"Falta {category.name}{suffix}."))
            continue
        expires_on = expiries[category.id]
        if expires_on is None:
            continue
        if expires_on < today:
            issues.append(
                Issue(
                    "document_expired",
                    "blocking",
                    f"{category.name}{suffix} vencida desde el {_format(expires_on)}.",
                )
            )
        elif (expires_on - today).days <= EXPIRY_WARNING_DAYS:
            days = (expires_on - today).days
            when = "hoy" if days == 0 else f"en {days} días"
            issues.append(
                Issue(
                    "document_expiring",
                    "warning",
                    f"{category.name}{suffix} vence {when} ({_format(expires_on)}).",
                )
            )
    return issues


def vehicle_issues(
    *,
    status: str,
    documents: Iterable[Issue],
    maintenance: Iterable[Issue] = (),
) -> list[Issue]:
    issues: list[Issue] = []
    if status != "active":
        label = VEHICLE_STATUS_LABELS.get(status, status)
        issues.append(Issue("vehicle_not_active", "blocking", f"El vehículo está {label.lower()}."))
    issues.extend(documents)
    issues.extend(maintenance)
    return issues


def driver_issues(
    *,
    driver_status: str,
    employee_status: str,
    has_home_branch_assignment: bool,
    documents: Iterable[Issue],
) -> list[Issue]:
    issues: list[Issue] = []
    if driver_status != "active":
        label = "suspendido" if driver_status == "suspended" else "inactivo"
        issues.append(Issue("driver_not_active", "blocking", f"El conductor está {label}."))
    if employee_status != "activo":
        issues.append(
            Issue("employee_not_active", "blocking", "El empleado no está activo en la empresa.")
        )
    if not has_home_branch_assignment:
        issues.append(
            Issue(
                "driver_branch_unassigned",
                "blocking",
                "El empleado ya no tiene asignación activa en la sucursal base del conductor.",
            )
        )
    issues.extend(documents)
    return issues


def license_issue(license_class: str, vehicle_kind: str) -> Issue | None:
    allowed = LICENSE_CLASSES_BY_KIND.get(vehicle_kind, frozenset())
    if license_class in allowed:
        return None
    needed = " o ".join(
        sorted(LICENSE_CLASS_LABELS[item] for item in allowed if item in LICENSE_CLASS_LABELS)
    )
    current = LICENSE_CLASS_LABELS.get(license_class, license_class)
    return Issue(
        "license_class_incompatible",
        "blocking",
        f"La licencia {current} no permite conducir este tipo de vehículo (requiere {needed}).",
    )

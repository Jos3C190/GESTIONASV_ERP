"""Fitness gate for dispatching a transfer: which vehicle and driver may leave.

A transfer leaves its origin branch with a fleet vehicle and a driver, both
based at that branch. Structural problems (another branch, vehicle in the
workshop, suspended driver) always stop the dispatch; compliance problems
(expired documents, wrong license class) stop it unless an authorized user
records an exception.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.application.fleet.compliance import Issue
from app.application.fleet.driver_views import driver_fitness
from app.application.fleet.views import build_vehicle_views

#: Problems no exception can waive.
HARD_BLOCKS = frozenset(
    {
        "vehicle_not_active",
        "vehicle_not_drivable",
        "vehicle_in_maintenance",
        "vehicle_on_road",
        "vehicle_branch_mismatch",
        "driver_required",
        "driver_branch_mismatch",
        "driver_not_active",
        "employee_not_active",
    }
)
#: Informative only at dispatch time.
IGNORED_AT_DISPATCH = frozenset({"transfers_not_enabled"})


@dataclass(slots=True)
class DispatchEvaluation:
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None
    vehicle_issues: list[Issue] = field(default_factory=list)
    driver_issues: list[Issue] = field(default_factory=list)

    @property
    def issues(self) -> list[Issue]:
        return [*self.vehicle_issues, *self.driver_issues]

    @property
    def blocking(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "blocking"]

    @property
    def hard_blocked(self) -> bool:
        return any(issue.code in HARD_BLOCKS for issue in self.blocking)

    def summary(self) -> str:
        return " ".join(issue.message for issue in self.blocking)


def _issue(raw: dict[str, Any]) -> Issue:
    return Issue(raw["code"], raw["severity"], raw["message"])


async def _trailer_issues(
    repo: Any, company_id: uuid.UUID, trailer_id: uuid.UUID, *, today: date
) -> list[Issue]:
    """The trailer travels too: its documents and status stop the dispatch just the same."""
    trailer = await repo.get_vehicle(company_id, trailer_id)
    view = (await build_vehicle_views(repo, company_id, [trailer], today=today))[0]
    return [
        Issue(raw["code"], raw["severity"], f"Remolque {view['code']}: {raw['message']}")
        for raw in view["compliance"]["issues"]
        if raw["code"] not in IGNORED_AT_DISPATCH
    ]


async def evaluate_dispatch(
    repo: Any,
    company_id: uuid.UUID,
    *,
    origin_branch_id: uuid.UUID,
    vehicle: Any,
    driver_id: uuid.UUID | None,
    transfer_id: uuid.UUID | None,
    today: date,
) -> DispatchEvaluation:
    """Evaluate ``vehicle`` and ``driver_id`` (default: the assigned driver)."""
    view = (await build_vehicle_views(repo, company_id, [vehicle], today=today))[0]
    evaluation = DispatchEvaluation(vehicle_id=vehicle.id, driver_id=driver_id)
    if vehicle.branch_id != origin_branch_id:
        evaluation.vehicle_issues.append(
            Issue(
                "vehicle_branch_mismatch",
                "blocking",
                "El vehículo no pertenece a la sucursal de origen del traslado.",
            )
        )
    if view["maintenance_in_progress"]:
        evaluation.vehicle_issues.append(
            Issue("vehicle_in_maintenance", "blocking", "El vehículo está en el taller.")
        )
    trip = view["current_transfer"]
    if trip is not None and trip["id"] != transfer_id:
        evaluation.vehicle_issues.append(
            Issue("vehicle_on_road", "blocking", f"El vehículo está en el traslado {trip['code']}.")
        )
    evaluation.vehicle_issues.extend(
        _issue(raw)
        for raw in view["compliance"]["issues"]
        if raw["code"] not in IGNORED_AT_DISPATCH
    )
    if view["type"]["is_towable"]:
        evaluation.vehicle_issues.append(
            Issue(
                "vehicle_not_drivable",
                "blocking",
                "Un remolque no sale solo; despache el cabezal al que está enganchado.",
            )
        )
    coupling = view["coupling"]
    if coupling is not None and coupling["role"] == "tractor":
        evaluation.vehicle_issues.extend(
            await _trailer_issues(repo, company_id, coupling["vehicle_id"], today=today)
        )

    if evaluation.driver_id is None and view["driver"] is not None:
        evaluation.driver_id = view["driver"]["driver_id"]
    if evaluation.driver_id is None:
        evaluation.driver_issues.append(
            Issue(
                "driver_required",
                "blocking",
                "Seleccione un conductor; el vehículo no tiene conductor asignado.",
            )
        )
        return evaluation
    row = await repo.driver_with_employee(company_id, evaluation.driver_id)
    if row is None:
        evaluation.driver_issues.append(
            Issue("driver_required", "blocking", "El conductor seleccionado no existe.")
        )
        return evaluation
    driver, employee = row
    if driver.branch_id != origin_branch_id:
        evaluation.driver_issues.append(
            Issue(
                "driver_branch_mismatch",
                "blocking",
                "El conductor no pertenece a la sucursal de origen del traslado.",
            )
        )
    issues, _ = (
        await driver_fitness(
            repo,
            company_id,
            [(driver, employee)],
            today=today,
            vehicle_kinds={driver.id: vehicle.kind},
        )
    )[driver.id]
    evaluation.driver_issues.extend(issues)
    return evaluation

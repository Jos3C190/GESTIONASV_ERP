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
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.application.fleet.compliance import Issue
from app.application.fleet.costs import BUSINESS_TZ
from app.application.fleet.driver_views import driver_fitness
from app.application.fleet.views import build_vehicle_views

#: How far ahead a reservation warns whoever is dispatching the vehicle.
RESERVATION_NOTICE_HOURS = 12

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
        "driver_on_road",
    }
)
#: Informative only at dispatch time.
IGNORED_AT_DISPATCH = frozenset({"transfers_not_enabled"})
#: When a transfer is only being planned, these are the only problems that stop it.
PLANNING_BLOCKS = frozenset(
    {
        "vehicle_not_active",
        "vehicle_not_drivable",
        "vehicle_branch_mismatch",
        "driver_required",
        "driver_branch_mismatch",
        "driver_not_active",
        "employee_not_active",
        "transfer_vehicle_not_in_fleet",
    }
)
#: Blocks at planning only when the company turned the rule on (it is a warning otherwise).
PLANNING_CONDITIONAL_BLOCKS = frozenset({"vehicle_overweight"})
#: What depends on the moment of departure: while planning it is only a heads-up.
PLANNING_TIMING_CODES = frozenset(
    {
        "inspection_required",
        "vehicle_on_road",
        "driver_on_road",
        "vehicle_in_maintenance",
        "vehicle_reserved",
    }
)
WHEN_DISPATCHING_PREFIX = "Al despachar: "


@dataclass(slots=True)
class DispatchEvaluation:
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None
    vehicle_issues: list[Issue] = field(default_factory=list)
    driver_issues: list[Issue] = field(default_factory=list)
    stage: str = "dispatch"

    @property
    def issues(self) -> list[Issue]:
        return [*self.vehicle_issues, *self.driver_issues]

    @property
    def planning_blocked(self) -> bool:
        """The transport cannot even be planned (as opposed to departing right now)."""
        return any(
            issue.severity == "blocking"
            and (issue.code in PLANNING_BLOCKS or issue.code in PLANNING_CONDITIONAL_BLOCKS)
            for issue in self.issues
        )

    def relax_for_planning(self) -> None:
        """Planning keeps the structural blocks and turns the rest into warnings."""
        self.vehicle_issues = [_planning_issue(issue) for issue in self.vehicle_issues]
        self.driver_issues = [_planning_issue(issue) for issue in self.driver_issues]

    @property
    def blocking(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "blocking"]

    @property
    def hard_blocked(self) -> bool:
        return any(issue.code in HARD_BLOCKS for issue in self.blocking)

    def summary(self) -> str:
        return " ".join(issue.message for issue in self.blocking)


def _planning_issue(issue: Issue) -> Issue:
    if issue.code in PLANNING_TIMING_CODES:
        return Issue(issue.code, "warning", WHEN_DISPATCHING_PREFIX + issue.message)
    if (
        issue.severity == "blocking"
        and issue.code not in PLANNING_BLOCKS
        # Over capacity is only "blocking" when the company's rule is on and the load is known.
        and issue.code not in PLANNING_CONDITIONAL_BLOCKS
    ):
        return Issue(issue.code, "warning", issue.message)
    return issue


def weight_issues(
    load_kg: Decimal, missing: int, capacity_kg: Decimal | None, *, block: bool
) -> list[Issue]:
    """Over capacity warns, and stops the dispatch only if the company turned that rule on.

    Products without weight only matter under the rule: many lack it, and it would be noise.
    """
    issues: list[Issue] = []
    if block and missing:
        issues.append(
            Issue(
                "load_weight_unknown",
                "warning",
                "No se pudo calcular todo el peso de la carga: "
                f"{missing} {'producto no tiene' if missing == 1 else 'productos no tienen'} peso.",
            )
        )
    if capacity_kg is not None and load_kg > capacity_kg:
        issues.append(
            Issue(
                "vehicle_overweight",
                "blocking" if block else "warning",
                f"La carga pesa {load_kg:.0f} kg y la capacidad es de {capacity_kg:.0f} kg.",
            )
        )
    return issues


async def _operation_issues(
    repo: Any,
    company_id: uuid.UUID,
    vehicle: Any,
    transfer_id: uuid.UUID | None,
    capacity: Any,
    load: tuple[Decimal, int] | None = None,
) -> list[Issue]:
    """What depends on this dispatch and not on the vehicle's standing."""
    now = datetime.now(UTC)
    issues: list[Issue] = []
    settings = await repo.fleet_settings(company_id)
    if settings.require_inspection:
        last = await repo.latest_inspection_at(vehicle.id)
        if last is None or now - last > timedelta(hours=settings.inspection_valid_hours):
            issues.append(
                Issue(
                    "inspection_required",
                    "blocking",
                    "Falta la inspección antes de salir "
                    f"(vale {settings.inspection_valid_hours} horas).",
                )
            )
    # Un viaje que sale justo antes de una reserva también la pisa.
    reservation = await repo.next_reservation(
        vehicle.id, now, now + timedelta(hours=RESERVATION_NOTICE_HOURS)
    )
    if reservation is not None:
        starts = reservation["starts_at"].astimezone(BUSINESS_TZ)
        ends = reservation["ends_at"].astimezone(BUSINESS_TZ)
        issues.append(
            Issue(
                "vehicle_reserved",
                "warning",
                f"Reservado del {starts.strftime('%d/%m/%Y %H:%M')} al "
                f"{ends.strftime('%d/%m/%Y %H:%M')} ({reservation['reason']}).",
            )
        )
    if load is None and transfer_id is not None:
        load = await repo.transfer_load(company_id, transfer_id)
    if load is not None:
        load_kg, missing = load
        issues.extend(weight_issues(load_kg, missing, capacity, block=settings.block_overweight))
    return issues


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
    stage: str = "dispatch",
    load: tuple[Decimal, int] | None = None,
) -> DispatchEvaluation:
    """Evaluate ``vehicle`` and ``driver_id`` (default: the assigned driver).

    ``stage="planning"`` judges a transport chosen ahead of time: what depends on
    the moment of departure becomes a warning. ``load`` (kilograms and products
    without weight) replaces the weight of the saved transfer, for a draft.
    """
    view = (await build_vehicle_views(repo, company_id, [vehicle], today=today))[0]
    evaluation = DispatchEvaluation(vehicle_id=vehicle.id, driver_id=driver_id, stage=stage)
    # Prestado, trabaja para la sucursal que lo tiene, no para la suya.
    loan = view["loan"]
    working_branch = loan["to_branch_id"] if loan is not None else vehicle.branch_id
    if working_branch != origin_branch_id:
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
    capacity = vehicle.capacity_kg
    if coupling is not None and coupling["role"] == "tractor":
        evaluation.vehicle_issues.extend(
            await _trailer_issues(repo, company_id, coupling["vehicle_id"], today=today)
        )
        # La carga va en el remolque.
        trailer = await repo.get_vehicle(company_id, coupling["vehicle_id"])
        capacity = trailer.capacity_kg if trailer.capacity_kg is not None else capacity
    evaluation.vehicle_issues.extend(
        await _operation_issues(repo, company_id, vehicle, transfer_id, capacity, load)
    )
    if evaluation.driver_id is None and view["driver"] is not None:
        evaluation.driver_id = view["driver"]["driver_id"]
    await _evaluate_driver(
        repo, company_id, evaluation, vehicle, origin_branch_id, transfer_id, today
    )
    if stage == "planning":
        evaluation.relax_for_planning()
    return evaluation


async def _evaluate_driver(
    repo: Any,
    company_id: uuid.UUID,
    evaluation: DispatchEvaluation,
    vehicle: Any,
    origin_branch_id: uuid.UUID,
    transfer_id: uuid.UUID | None,
    today: date,
) -> None:
    if evaluation.driver_id is None:
        evaluation.driver_issues.append(
            Issue(
                "driver_required",
                "blocking",
                "Seleccione un conductor; el vehículo no tiene conductor asignado.",
            )
        )
        return
    row = await repo.driver_with_employee(company_id, evaluation.driver_id)
    if row is None:
        evaluation.driver_issues.append(
            Issue("driver_required", "blocking", "El conductor seleccionado no existe.")
        )
        return
    driver, employee = row
    other_trip = await repo.driver_active_transfer(company_id, driver.id, transfer_id)
    if other_trip is not None:
        evaluation.driver_issues.append(
            Issue(
                "driver_on_road",
                "blocking",
                f"El conductor está en el traslado {other_trip}.",
            )
        )
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

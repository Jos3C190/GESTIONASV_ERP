"""Pure rules for partial reception, discrepancies, transport substitution and planning."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.application.fleet.compliance import Issue
from app.application.fleet.dispatch import (
    PLANNING_BLOCKS,
    WHEN_DISPATCHING_PREFIX,
    DispatchEvaluation,
)
from app.domain.entities.inventory_transfer import (
    FINAL_STATUSES,
    ON_ROAD_STATUSES,
    TRIP_FINISHED_STATUSES,
    DiscrepancyKind,
    TransferDomainError,
    TransferStatus,
    require_assignment_for_submission,
    require_discrepancy_kind,
    require_discrepancy_open,
    require_incident_openable,
    require_receivable,
    require_reception_closable,
    require_substitution,
    settle_transfer_status,
    validate_receipt_line,
)

D = Decimal


def settle(**overrides: object) -> TransferStatus:
    values: dict[str, object] = {
        "current_status": "in_transit",
        "uncovered_pending": D("0"),
        "has_open_discrepancies": False,
        "had_discrepancy": False,
        "had_loss": False,
        "received_any": True,
        "incident_open": False,
    }
    values.update(overrides)
    return settle_transfer_status(**values)  # type: ignore[arg-type]


def error_code(call, *args: object, **kwargs: object) -> str:
    with pytest.raises(TransferDomainError) as raised:
        call(*args, **kwargs)
    return raised.value.code


def test_status_groups_come_from_the_domain() -> None:
    assert set(ON_ROAD_STATUSES) == {"in_transit", "partially_received", "incident"}
    assert set(TRIP_FINISHED_STATUSES) == {"discrepancy", "received", "closed_with_adjustment"}
    assert set(FINAL_STATUSES) == {"received", "closed_with_adjustment", "cancelled"}
    # A trip that finished is never still on the road.
    assert not set(ON_ROAD_STATUSES) & set(TRIP_FINISHED_STATUSES)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        # An open incident wins over everything.
        (
            {"incident_open": True, "uncovered_pending": D("3"), "has_open_discrepancies": True},
            TransferStatus.INCIDENT,
        ),
        # Something still on the way: partial once anything arrived, in transit before.
        ({"uncovered_pending": D("2")}, TransferStatus.PARTIALLY_RECEIVED),
        ({"uncovered_pending": D("2"), "received_any": False}, TransferStatus.IN_TRANSIT),
        # Nothing waiting, but differences to resolve.
        (
            {"has_open_discrepancies": True, "had_discrepancy": True},
            TransferStatus.DISCREPANCY,
        ),
        # A pending quantity still beats an open discrepancy.
        (
            {"uncovered_pending": D("1"), "has_open_discrepancies": True},
            TransferStatus.PARTIALLY_RECEIVED,
        ),
        # Everything resolved, but there was a difference or a loss.
        ({"had_discrepancy": True}, TransferStatus.CLOSED_WITH_ADJUSTMENT),
        ({"had_loss": True}, TransferStatus.CLOSED_WITH_ADJUSTMENT),
        # A clean reception.
        ({}, TransferStatus.RECEIVED),
    ],
)
def test_settle_follows_the_rules_in_order(overrides: dict[str, object], expected: str) -> None:
    assert settle(**overrides) == expected


@pytest.mark.parametrize("final", ["received", "closed_with_adjustment", "cancelled"])
def test_settle_never_reopens_a_final_state(final: str) -> None:
    assert (
        settle(current_status=final, uncovered_pending=D("5"), has_open_discrepancies=True) == final
    )


def test_settle_can_leave_discrepancy_when_a_shortage_turns_up() -> None:
    # The shortage was cancelled ("it arrived"): what it covered is waiting again.
    assert (
        settle(current_status="discrepancy", uncovered_pending=D("4"))
        == TransferStatus.PARTIALLY_RECEIVED
    )


def test_receivable_and_incident_openable_accept_partial_reception() -> None:
    for status in ("in_transit", "partially_received"):
        require_receivable(status)
        require_incident_openable(status)
    for status in ("preparation", "approved", "incident", "discrepancy", "received"):
        assert error_code(require_receivable, status) == "transfer_not_receivable"
        assert error_code(require_incident_openable, status) == "transfer_incident_not_allowed"


def test_reception_can_only_be_closed_after_something_arrived() -> None:
    require_reception_closable("partially_received", received_any=True)
    assert (
        error_code(require_reception_closable, "in_transit", received_any=False)
        == "transfer_reception_close_requires_receipt"
    )
    assert (
        error_code(require_reception_closable, "discrepancy", received_any=True)
        == "transfer_reception_close_not_allowed"
    )
    with pytest.raises(TransferDomainError) as raised:
        require_reception_closable("in_transit", received_any=False)
    assert raised.value.message == "Si no llegó nada, reporta una incidencia del traslado."


def line(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {"good": D("4"), "pending": D("10")}
    values.update(overrides)
    return values


def test_a_receipt_line_accepts_good_damaged_and_surplus_together() -> None:
    validate_receipt_line(
        **line(good=D("6"), damaged=D("4"), damage_type="broken", damage_notes="Caja rota")
    )  # type: ignore[arg-type]
    validate_receipt_line(**line())  # type: ignore[arg-type]
    validate_receipt_line(  # type: ignore[arg-type]
        **line(good=D("10"), surplus=D("2"), surplus_notes="Llegaron dos cajas de más")
    )
    # Everything that arrived is damaged.
    validate_receipt_line(  # type: ignore[arg-type]
        **line(good=D("0"), damaged=D("10"), damage_type="wet", damage_notes="Mojado por lluvia")
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"good": D("0")}, "transfer_receipt_empty"),
        ({"good": D("-1")}, "transfer_quantity_invalid"),
        ({"good": D("11")}, "transfer_over_receipt"),
        (
            {
                "good": D("6"),
                "damaged": D("5"),
                "damage_type": "broken",
                "damage_notes": "Caja rota",
            },
            "transfer_over_receipt",
        ),
        (
            {"good": D("4"), "surplus": D("1"), "surplus_notes": "Una caja extra"},
            "transfer_surplus_requires_full_receipt",
        ),
        (
            {"good": D("4"), "damaged": D("1"), "damage_notes": "Caja rota"},
            "transfer_damage_details_required",
        ),
        (
            {"good": D("4"), "damaged": D("1"), "damage_type": "broken", "damage_notes": "no"},
            "transfer_damage_details_required",
        ),
        (
            {"good": D("10"), "surplus": D("1"), "surplus_notes": "  "},
            "transfer_surplus_notes_required",
        ),
    ],
)
def test_receipt_line_refusals(overrides: dict[str, object], code: str) -> None:
    assert error_code(validate_receipt_line, **line(**overrides)) == code  # type: ignore[arg-type]


def test_surplus_message_is_explicit() -> None:
    with pytest.raises(TransferDomainError) as raised:
        validate_receipt_line(
            good=D("4"), surplus=D("1"), surplus_notes="Una caja extra", pending=D("10")
        )
    assert (
        raised.value.message
        == "Declara sobrante solo cuando registras todo lo pendiente de la línea."
    )


def test_submission_needs_vehicle_and_driver() -> None:
    vehicle, driver = uuid.uuid4(), uuid.uuid4()
    require_assignment_for_submission(vehicle, driver)
    for args in ((None, driver), (vehicle, None), (None, None)):
        with pytest.raises(TransferDomainError) as raised:
            require_assignment_for_submission(*args)
        assert raised.value.code == "transfer_assignment_required"
        assert (
            raised.value.message
            == "Elige vehículo y conductor antes de enviar el traslado a aprobación."
        )


def test_substitution_needs_a_known_code_and_a_reason_of_ten_characters() -> None:
    assert require_substitution(code="vehicle_unfit", reason="  El camión no arrancó hoy ") == (
        "vehicle_unfit",
        "El camión no arrancó hoy",
    )
    for code in ("vehicle_unfit", "vehicle_unavailable", "driver_unfit", "driver_unavailable"):
        assert require_substitution(code=code, reason="Motivo suficiente")[0] == code
    assert require_substitution(code="load_change", reason="Carga mayor a la prevista")[0]
    assert require_substitution(code="other", reason="Otra razón documentada")[0] == "other"
    assert (
        error_code(require_substitution, code="other", reason="corto")
        == "transfer_substitution_reason_required"
    )
    assert (
        error_code(require_substitution, code="other", reason=None)
        == "transfer_substitution_reason_required"
    )
    assert (
        error_code(require_substitution, code="nope", reason="Motivo suficiente")
        == "transfer_substitution_code_invalid"
    )
    assert (
        error_code(require_substitution, code=None, reason="Motivo suficiente")
        == "transfer_substitution_code_invalid"
    )


def test_discrepancy_guards() -> None:
    require_discrepancy_open("open")
    require_discrepancy_open("in_claim", allow_claim=True)
    for status in ("in_claim", "resolved", "cancelled"):
        assert error_code(require_discrepancy_open, status) == "transfer_discrepancy_not_open"
    assert (
        error_code(require_discrepancy_open, "resolved", allow_claim=True)
        == "transfer_discrepancy_not_open"
    )
    require_discrepancy_kind("damage", DiscrepancyKind.DAMAGE)
    require_discrepancy_kind("shortage", DiscrepancyKind.SHORTAGE, DiscrepancyKind.SURPLUS)
    assert (
        error_code(require_discrepancy_kind, "surplus", DiscrepancyKind.DAMAGE)
        == "transfer_discrepancy_action_invalid"
    )


# --------------------------------------------------------------------------- planning mode


def planning_evaluation(vehicle: list[Issue], driver: list[Issue]) -> DispatchEvaluation:
    evaluation = DispatchEvaluation(
        vehicle_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        vehicle_issues=vehicle,
        driver_issues=driver,
        stage="planning",
    )
    evaluation.relax_for_planning()
    return evaluation


def test_planning_turns_timing_problems_into_prefixed_warnings() -> None:
    timing = [
        Issue("inspection_required", "blocking", "Falta la inspección antes de salir."),
        Issue("vehicle_on_road", "blocking", "El vehículo está en el traslado TR-1."),
        Issue("vehicle_in_maintenance", "blocking", "El vehículo está en el taller."),
        Issue("vehicle_reserved", "warning", "Reservado mañana."),
    ]
    driver = [Issue("driver_on_road", "blocking", "El conductor está en el traslado TR-2.")]
    evaluation = planning_evaluation(timing, driver)
    assert not evaluation.planning_blocked
    assert evaluation.blocking == []
    assert all(issue.severity == "warning" for issue in evaluation.issues)
    assert all(issue.message.startswith(WHEN_DISPATCHING_PREFIX) for issue in evaluation.issues)
    assert evaluation.vehicle_issues[0].message == (
        "Al despachar: Falta la inspección antes de salir."
    )


@pytest.mark.parametrize("code", sorted(PLANNING_BLOCKS))
def test_planning_blocks_stay_blocking(code: str) -> None:
    evaluation = planning_evaluation([Issue(code, "blocking", "No apto.")], [])
    assert evaluation.planning_blocked
    assert [issue.code for issue in evaluation.blocking] == [code]
    assert evaluation.vehicle_issues[0].message == "No apto."


def test_planning_keeps_expired_documents_as_warnings_for_the_approver() -> None:
    evaluation = planning_evaluation(
        [Issue("document_expired", "blocking", "La tarjeta de circulación venció.")],
        [Issue("license_expired", "blocking", "La licencia venció.")],
    )
    assert not evaluation.planning_blocked
    assert [issue.severity for issue in evaluation.issues] == ["warning", "warning"]
    # They are not timing problems, so the text is unchanged.
    assert evaluation.vehicle_issues[0].message == "La tarjeta de circulación venció."


def test_dispatch_stage_is_not_relaxed() -> None:
    evaluation = DispatchEvaluation(
        vehicle_id=uuid.uuid4(),
        driver_id=None,
        vehicle_issues=[Issue("vehicle_on_road", "blocking", "En ruta.")],
    )
    assert evaluation.stage == "dispatch"
    assert [issue.code for issue in evaluation.blocking] == ["vehicle_on_road"]
    assert not evaluation.planning_blocked


def test_overweight_blocks_planning_only_when_the_company_rule_made_it_blocking() -> None:
    # Rule on: the dispatch evaluation produced a blocking issue, and planning keeps it.
    blocking = planning_evaluation(
        [Issue("vehicle_overweight", "blocking", "La carga pesa 900 kg y la capacidad es 500 kg.")],
        [],
    )
    assert blocking.planning_blocked
    assert blocking.vehicle_issues[0].severity == "blocking"
    # Rule off: it was only a warning, and stays one.
    warning = planning_evaluation(
        [Issue("vehicle_overweight", "warning", "La carga pesa 900 kg y la capacidad es 500 kg.")],
        [],
    )
    assert not warning.planning_blocked
    assert warning.vehicle_issues[0].severity == "warning"

"""Pure rules for transfer routes, approval and dispatch eligibility."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from app.domain.entities.inventory_transfer import (
    TransferDomainError,
    TransferPolicy,
    TransferRoute,
    WarehouseFacts,
    approval_required,
    classify_route,
    require_cancellable,
    require_current_round,
    require_dispatchable,
    require_independent_approver,
    require_pending_approval,
    require_submittable,
    validate_rejection_reason,
)

HQ = uuid.uuid4()
BRANCH_A = uuid.uuid4()
BRANCH_B = uuid.uuid4()

ALL_OFF = TransferPolicy()
BRANCH_TO_BRANCH_ONLY = TransferPolicy(allow_branch_to_branch=True)
BRANCH_TO_CENTRAL_ONLY = TransferPolicy(allow_branch_to_central=True)
ALL_ON = TransferPolicy(allow_branch_to_branch=True, allow_branch_to_central=True)


def warehouse(branch_id: uuid.UUID, **overrides: object) -> WarehouseFacts:
    base = WarehouseFacts(
        id=uuid.uuid4(),
        branch_id=branch_id,
        is_central=False,
        is_transit=False,
        is_active=True,
        operational_status="active",
        storage_eligible=True,
        branch_active=True,
        branch_is_headquarters=branch_id == HQ,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def central(**overrides: object) -> WarehouseFacts:
    return warehouse(HQ, is_central=True, **overrides)


def expect_error(
    origin: WarehouseFacts, destination: WarehouseFacts, policy: TransferPolicy
) -> TransferDomainError:
    with pytest.raises(TransferDomainError) as raised:
        classify_route(origin, destination, policy)
    return raised.value


def test_policy_defaults_keep_branch_routes_off_and_approval_on() -> None:
    policy = TransferPolicy()
    assert policy.allow_branch_to_branch is False
    assert policy.allow_branch_to_central is False
    assert policy.require_approval is True
    assert policy.route_enabled(TransferRoute.CENTRAL_DISTRIBUTION) is True
    assert policy.route_enabled(TransferRoute.BRANCH_TO_BRANCH) is False
    assert policy.route_enabled(TransferRoute.BRANCH_TO_CENTRAL) is False


@pytest.mark.parametrize("policy", [ALL_OFF, BRANCH_TO_BRANCH_ONLY, ALL_ON])
def test_distribution_from_the_central_warehouse_is_always_available(
    policy: TransferPolicy,
) -> None:
    route = classify_route(central(), warehouse(BRANCH_A), policy)
    assert route == TransferRoute.CENTRAL_DISTRIBUTION


def test_central_to_a_second_warehouse_of_headquarters_is_still_distribution() -> None:
    destination = warehouse(HQ)
    assert classify_route(central(), destination, ALL_OFF) == TransferRoute.CENTRAL_DISTRIBUTION


@pytest.mark.parametrize(
    ("origin", "destination", "code", "status"),
    [
        (central(), central(), "transfer_destination_invalid", 422),
        (central(), warehouse(BRANCH_A, is_transit=True), "transfer_destination_invalid", 422),
        (central(), warehouse(BRANCH_A, is_active=False), "transfer_destination_invalid", 422),
        (
            central(),
            warehouse(BRANCH_A, operational_status="suspended"),
            "transfer_destination_invalid",
            422,
        ),
        (central(), warehouse(BRANCH_A, branch_active=False), "transfer_branch_invalid", 409),
        (
            warehouse(BRANCH_A, is_central=True, branch_is_headquarters=False),
            warehouse(BRANCH_B),
            "transfer_branch_invalid",
            409,
        ),
        (central(is_transit=True), warehouse(BRANCH_A), "transfer_origin_invalid", 409),
        (central(is_active=False), warehouse(BRANCH_A), "transfer_origin_invalid", 409),
    ],
)
def test_central_origin_keeps_its_original_errors(
    origin: WarehouseFacts, destination: WarehouseFacts, code: str, status: int
) -> None:
    error = expect_error(origin, destination, ALL_ON)
    assert (error.code, error.status_code) == (code, status)


def test_central_origin_error_order_reports_the_destination_before_the_branch() -> None:
    destination = warehouse(BRANCH_A, is_transit=True, branch_active=False)
    assert expect_error(central(), destination, ALL_OFF).code == "transfer_destination_invalid"


def test_same_warehouse_is_rejected_first() -> None:
    origin = warehouse(BRANCH_A)
    error = expect_error(origin, origin, ALL_ON)
    assert (error.code, error.status_code) == ("transfer_same_warehouse", 422)


def test_branch_origin_with_both_branch_routes_off_gets_the_original_answer() -> None:
    error = expect_error(warehouse(BRANCH_A), warehouse(BRANCH_B), ALL_OFF)
    assert (error.code, error.status_code) == ("transfer_origin_not_central", 422)
    assert error.message == "El traslado a sucursal debe salir de la bodega central."
    assert expect_error(warehouse(BRANCH_A), central(), ALL_OFF).code == (
        "transfer_origin_not_central"
    )


@pytest.mark.parametrize(
    ("policy", "destination", "expected"),
    [
        (BRANCH_TO_BRANCH_ONLY, warehouse(BRANCH_B), TransferRoute.BRANCH_TO_BRANCH),
        (ALL_ON, warehouse(BRANCH_B), TransferRoute.BRANCH_TO_BRANCH),
        (BRANCH_TO_CENTRAL_ONLY, central(), TransferRoute.BRANCH_TO_CENTRAL),
        (ALL_ON, central(), TransferRoute.BRANCH_TO_CENTRAL),
        # A second warehouse of headquarters is a branch, not "the central warehouse".
        (ALL_ON, warehouse(HQ), TransferRoute.BRANCH_TO_BRANCH),
    ],
)
def test_branch_origin_is_classified_by_its_destination(
    policy: TransferPolicy, destination: WarehouseFacts, expected: TransferRoute
) -> None:
    assert classify_route(warehouse(BRANCH_A), destination, policy) == expected


def test_a_route_that_is_off_says_which_one() -> None:
    to_branch = expect_error(warehouse(BRANCH_A), warehouse(BRANCH_B), BRANCH_TO_CENTRAL_ONLY)
    assert (to_branch.code, to_branch.status_code) == ("transfer_route_disabled", 409)
    assert (
        to_branch.message == "Los traslados entre sucursales no están habilitados en esta empresa."
    )
    to_central = expect_error(warehouse(BRANCH_A), central(), BRANCH_TO_BRANCH_ONLY)
    assert (to_central.code, to_central.status_code) == ("transfer_route_disabled", 409)
    assert (
        to_central.message
        == "Los retornos a la bodega central no están habilitados en esta empresa."
    )


def test_both_warehouses_of_one_branch_are_not_a_transfer_between_branches() -> None:
    error = expect_error(warehouse(BRANCH_A), warehouse(BRANCH_A), ALL_ON)
    assert (error.code, error.status_code) == ("transfer_same_branch", 422)
    assert error.message == (
        "Ambas bodegas pertenecen a la misma sucursal; este flujo es para traslados entre sucursales."
    )


@pytest.mark.parametrize(
    ("origin", "destination", "code"),
    [
        (
            warehouse(BRANCH_A, storage_eligible=False),
            warehouse(BRANCH_B),
            "transfer_origin_invalid",
        ),
        (warehouse(BRANCH_A, is_active=False), warehouse(BRANCH_B), "transfer_origin_invalid"),
        (warehouse(BRANCH_A, is_transit=True), warehouse(BRANCH_B), "transfer_origin_invalid"),
        (
            warehouse(BRANCH_A),
            warehouse(BRANCH_B, storage_eligible=False),
            "transfer_destination_invalid",
        ),
        (warehouse(BRANCH_A), warehouse(BRANCH_B, is_active=False), "transfer_destination_invalid"),
        (warehouse(BRANCH_A), warehouse(BRANCH_B, is_transit=True), "transfer_destination_invalid"),
        (warehouse(BRANCH_A, branch_active=False), warehouse(BRANCH_B), "transfer_branch_invalid"),
        (warehouse(BRANCH_A), warehouse(BRANCH_B, branch_active=False), "transfer_branch_invalid"),
        (
            warehouse(BRANCH_A),
            warehouse(BRANCH_B, is_central=True, branch_is_headquarters=False),
            "transfer_branch_invalid",
        ),
    ],
)
def test_branch_routes_need_active_storage_warehouses_on_both_sides(
    origin: WarehouseFacts, destination: WarehouseFacts, code: str
) -> None:
    assert expect_error(origin, destination, ALL_ON).code == code


@pytest.mark.parametrize(
    ("route", "policy", "expected"),
    [
        (TransferRoute.CENTRAL_DISTRIBUTION, TransferPolicy(), False),
        (TransferRoute.CENTRAL_DISTRIBUTION, TransferPolicy(require_approval=False), False),
        (TransferRoute.BRANCH_TO_BRANCH, TransferPolicy(), True),
        (TransferRoute.BRANCH_TO_CENTRAL, TransferPolicy(), True),
        (TransferRoute.BRANCH_TO_BRANCH, TransferPolicy(require_approval=False), False),
        ("branch_to_central", TransferPolicy(require_approval=False), False),
    ],
)
def test_approval_is_only_asked_of_branch_routes(
    route: TransferRoute | str, policy: TransferPolicy, expected: bool
) -> None:
    assert approval_required(route, policy) is expected


CENTRAL = TransferRoute.CENTRAL_DISTRIBUTION
BRANCH = TransferRoute.BRANCH_TO_BRANCH


@pytest.mark.parametrize(
    ("status", "route", "needs_approval", "outcome"),
    [
        ("preparation", CENTRAL, False, None),
        ("pending_approval", CENTRAL, False, "transfer_not_dispatchable"),
        ("approved", CENTRAL, False, "transfer_not_dispatchable"),
        ("in_transit", CENTRAL, False, "transfer_not_dispatchable"),
        ("cancelled", CENTRAL, False, "transfer_not_dispatchable"),
        ("preparation", BRANCH, True, "transfer_approval_required"),
        ("preparation", BRANCH, False, None),
        ("pending_approval", BRANCH, True, "transfer_approval_required"),
        ("pending_approval", BRANCH, False, "transfer_approval_required"),
        ("approved", BRANCH, True, None),
        ("approved", BRANCH, False, None),
        ("in_transit", BRANCH, False, "transfer_not_dispatchable"),
        ("received", BRANCH, False, "transfer_not_dispatchable"),
        ("incident", BRANCH, False, "transfer_not_dispatchable"),
        ("cancelled", BRANCH, False, "transfer_not_dispatchable"),
        ("preparation", "branch_to_central", True, "transfer_approval_required"),
    ],
)
def test_dispatch_eligibility_table(
    status: str, route: TransferRoute | str, needs_approval: bool, outcome: str | None
) -> None:
    if outcome is None:
        require_dispatchable(status, 1, route, needs_approval)
        return
    with pytest.raises(TransferDomainError) as raised:
        require_dispatchable(status, 1, route, needs_approval)
    assert raised.value.code == outcome
    assert raised.value.status_code == 409


def test_dispatch_without_route_arguments_behaves_as_before() -> None:
    require_dispatchable("preparation", 1)
    with pytest.raises(TransferDomainError, match="ya no está en preparación") as raised:
        require_dispatchable("in_transit", 1)
    assert raised.value.code == "transfer_not_dispatchable"


@pytest.mark.parametrize("route", [CENTRAL, BRANCH])
def test_dispatch_needs_at_least_one_line(route: TransferRoute) -> None:
    status = "preparation" if route == CENTRAL else "approved"
    with pytest.raises(TransferDomainError) as raised:
        require_dispatchable(status, 0, route, False)
    assert (raised.value.code, raised.value.status_code) == ("transfer_lines_required", 422)


def test_approval_needed_message_is_in_spanish_with_tuteo() -> None:
    with pytest.raises(TransferDomainError) as raised:
        require_dispatchable("preparation", 1, BRANCH, True)
    assert raised.value.message == "Este traslado necesita aprobación antes de despacharse."


@pytest.mark.parametrize(
    ("status", "route", "needs_approval", "outcome", "http_status"),
    [
        ("preparation", BRANCH, True, None, 0),
        ("preparation", CENTRAL, False, "transfer_approval_not_applicable", 422),
        ("preparation", CENTRAL, True, "transfer_approval_not_applicable", 422),
        ("preparation", BRANCH, False, "transfer_approval_not_applicable", 422),
        ("pending_approval", BRANCH, True, "transfer_not_in_preparation", 409),
        ("approved", BRANCH, True, "transfer_not_in_preparation", 409),
        ("in_transit", BRANCH, True, "transfer_not_in_preparation", 409),
    ],
)
def test_submit_eligibility_table(
    status: str, route: TransferRoute, needs_approval: bool, outcome: str | None, http_status: int
) -> None:
    if outcome is None:
        require_submittable(status, route, needs_approval)
        return
    with pytest.raises(TransferDomainError) as raised:
        require_submittable(status, route, needs_approval)
    assert (raised.value.code, raised.value.status_code) == (outcome, http_status)


def test_submit_messages_explain_why_there_is_nothing_to_approve() -> None:
    with pytest.raises(TransferDomainError) as central_error:
        require_submittable("preparation", CENTRAL, False)
    assert central_error.value.message == (
        "Los traslados desde la bodega central no requieren aprobación."
    )
    with pytest.raises(TransferDomainError) as optional_error:
        require_submittable("preparation", BRANCH, False)
    assert optional_error.value.message == (
        "Esta empresa no exige aprobación para esta ruta; puedes despachar directamente."
    )


@pytest.mark.parametrize("status", ["preparation", "pending_approval", "approved"])
@pytest.mark.parametrize("route", [CENTRAL, BRANCH])
def test_a_transfer_that_has_not_left_can_be_cancelled(status: str, route: TransferRoute) -> None:
    require_cancellable(status, route)


@pytest.mark.parametrize("status", ["in_transit", "received", "incident", "cancelled"])
def test_a_transfer_that_left_cannot_be_cancelled(status: str) -> None:
    with pytest.raises(TransferDomainError) as branch_error:
        require_cancellable(status, BRANCH)
    assert (branch_error.value.code, branch_error.value.status_code) == (
        "transfer_not_cancellable",
        409,
    )
    assert branch_error.value.message == "Solo se cancelan traslados que aún no se despachan."
    # The central route keeps the error code it always had.
    with pytest.raises(TransferDomainError) as central_error:
        require_cancellable(status, CENTRAL)
    assert central_error.value.code == "transfer_not_in_preparation"


def test_only_a_waiting_transfer_can_be_decided_on() -> None:
    require_pending_approval("pending_approval")
    for status in ("preparation", "approved", "in_transit", "cancelled"):
        with pytest.raises(TransferDomainError) as raised:
            require_pending_approval(status)
        assert raised.value.code == "transfer_not_pending_approval"
        assert raised.value.message == "El traslado ya no está esperando aprobación."


def test_a_decision_on_an_old_round_is_stale() -> None:
    require_current_round(2, 2)
    with pytest.raises(TransferDomainError) as raised:
        require_current_round(1, 2)
    assert (raised.value.code, raised.value.status_code) == ("transfer_approval_stale", 409)


def test_nobody_approves_what_they_prepared_or_sent_unless_allowed() -> None:
    creator, submitter, approver = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    require_independent_approver(
        actor_id=approver,
        created_by_id=creator,
        submitted_by_id=submitter,
        allow_self_approval=False,
    )
    for actor in (creator, submitter):
        with pytest.raises(TransferDomainError) as raised:
            require_independent_approver(
                actor_id=actor,
                created_by_id=creator,
                submitted_by_id=submitter,
                allow_self_approval=False,
            )
        assert (raised.value.code, raised.value.status_code) == (
            "transfer_approval_self_forbidden",
            403,
        )
        require_independent_approver(
            actor_id=actor,
            created_by_id=creator,
            submitted_by_id=submitter,
            allow_self_approval=True,
        )


def test_rejection_reason_is_trimmed_and_bounded() -> None:
    assert validate_rejection_reason("  Falta la firma del jefe  ") == "Falta la firma del jefe"
    assert validate_rejection_reason("x" * 1000) == "x" * 1000
    for reason in ("", "    ", "abcd", "  abcd  ", "x" * 1001):
        with pytest.raises(TransferDomainError) as raised:
            validate_rejection_reason(reason)
        assert (raised.value.code, raised.value.status_code) == (
            "transfer_rejection_reason_required",
            422,
        )

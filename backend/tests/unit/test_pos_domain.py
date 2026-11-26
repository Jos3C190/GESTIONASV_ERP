"""V6a: reglas puras de caja, turno, arqueo, depósito y PIN de supervisor."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.exceptions import AppError
from app.domain.entities.pos import (
    CashMovementKind,
    DenominationCount,
    DenominationForm,
    ShiftStatus,
    ShiftTotals,
    count_total,
    decide_closing,
    deposit_amount,
    require_countable,
    require_open,
    require_other_person,
    require_reviewable,
    validate_count,
    validate_deposit,
    validate_movement,
    validate_opening,
    validate_pin,
    validate_reason,
    validate_register,
)

D = Decimal
BILL, COIN = DenominationForm.BILL, DenominationForm.COIN


def _code(error: pytest.ExceptionInfo[AppError]) -> str:
    return error.value.code


def test_count_totals_and_rejects_bad_denominations() -> None:
    lines = validate_count(
        [
            DenominationCount(BILL, D("20"), 2),
            DenominationCount(BILL, D("1"), 3),
            DenominationCount(COIN, D("1"), 1),
            DenominationCount(COIN, D("0.25"), 3),
            DenominationCount(COIN, D("0.01"), 0),
        ]
    )
    assert count_total(lines) == D("44.75")
    assert all(line.quantity for line in lines)  # las cantidades en cero no se guardan
    with pytest.raises(AppError) as error:
        validate_count([DenominationCount(BILL, D("3"), 1)])
    assert _code(error) == "pos_denomination_invalid"
    with pytest.raises(AppError) as error:
        validate_count([DenominationCount(COIN, D("2"), 1)])
    assert _code(error) == "pos_denomination_invalid"
    with pytest.raises(AppError) as error:
        validate_count([DenominationCount(BILL, D("5"), 1), DenominationCount(BILL, D("5.00"), 2)])
    assert _code(error) == "pos_denomination_repeated"
    with pytest.raises(AppError) as error:
        validate_count([DenominationCount(BILL, D("5"), -1)])
    assert _code(error) == "pos_denomination_quantity"


def test_expected_amounts_include_every_source() -> None:
    totals = ShiftTotals(
        opening_float=D("50.00"),
        cash_in=D("10.00"),
        cash_out=D("5.00"),
        safe_drops=D("100.00"),
        cash_sales=D("230.40"),
        cash_refunds=D("12.40"),
        card_sales=D("80.00"),
        card_refunds=D("8.00"),
        transfer_sales=D("15.00"),
    )
    assert totals.expected_cash == D("173.00")
    assert totals.expected_card == D("72.00")
    assert totals.expected_transfer == D("15.00")


def test_register_validation() -> None:
    validate_register(
        code="CAJA-01",
        name="Caja 1",
        opening_float=D("50"),
        cash_out_approval_threshold=D("20"),
        cash_drawer_limit=D("500"),
    )
    cases = [
        ({"code": "caja"}, "pos_register_code_invalid"),
        ({"name": " "}, "pos_register_name_required"),
        ({"opening_float": D("-1")}, "pos_register_float_invalid"),
        ({"cash_out_approval_threshold": D("-1")}, "pos_register_threshold_invalid"),
        ({"cash_drawer_limit": D("50")}, "pos_register_drawer_limit_invalid"),
    ]
    for change, code in cases:
        values = {
            "code": "CAJA-01",
            "name": "Caja 1",
            "opening_float": D("50"),
            "cash_out_approval_threshold": D("20"),
            "cash_drawer_limit": None,
            **change,
        }
        with pytest.raises(AppError) as error:
            validate_register(**values)
        assert _code(error) == code


def test_shift_transitions() -> None:
    require_open(ShiftStatus.OPEN)
    for status in (ShiftStatus.COUNTED, ShiftStatus.RECOUNT, ShiftStatus.CLOSED):
        with pytest.raises(AppError) as error:
            require_open(status)
        assert _code(error) == "pos_shift_not_open"
    require_countable(ShiftStatus.OPEN)
    require_countable(ShiftStatus.RECOUNT)
    for status in (ShiftStatus.COUNTED, ShiftStatus.CLOSED):
        with pytest.raises(AppError):
            require_countable(status)
    require_reviewable(ShiftStatus.COUNTED)
    for status in (ShiftStatus.OPEN, ShiftStatus.RECOUNT, ShiftStatus.CLOSED):
        with pytest.raises(AppError):
            require_reviewable(status)
    person = uuid.uuid4()
    require_other_person(person, uuid.uuid4())
    with pytest.raises(AppError) as error:
        require_other_person(person, person)
    assert _code(error) == "pos_self_authorization"


def test_opening_and_reason() -> None:
    assert validate_opening(D("50")) == D("50.00")
    with pytest.raises(AppError):
        validate_opening(D("10000.01"))
    assert validate_reason("  Compra   de  bolsas ") == "Compra de bolsas"
    with pytest.raises(AppError):
        validate_reason("abc")


def test_movements() -> None:
    def move(kind: CashMovementKind, amount: str, *, authorized: bool = False) -> None:
        validate_movement(
            kind=kind,
            amount=D(amount),
            available_cash=D("60.00"),
            approval_threshold=D("20.00"),
            authorized=authorized,
        )

    move(CashMovementKind.CASH_IN, "500.00")  # una entrada no depende de lo que hay
    move(CashMovementKind.CASH_OUT, "20.00")
    move(CashMovementKind.CASH_OUT, "25.00", authorized=True)
    move(CashMovementKind.SAFE_DROP, "60.00")  # el retiro no pide supervisor
    for kind, amount, code in (
        (CashMovementKind.CASH_OUT, "25.00", "pos_movement_requires_supervisor"),
        (CashMovementKind.CASH_OUT, "60.01", "pos_movement_exceeds_cash"),
        (CashMovementKind.SAFE_DROP, "61.00", "pos_movement_exceeds_cash"),
        (CashMovementKind.CASH_IN, "0", "pos_movement_amount_invalid"),
        (CashMovementKind.CASH_IN, "1.005", "pos_movement_amount_invalid"),
    ):
        with pytest.raises(AppError) as error:
            move(kind, amount)
        assert _code(error) == code


def test_closing_decision() -> None:
    exact = decide_closing(
        expected_cash=D("150.00"), counted_cash=D("150.00"), retained_float=D("50"), notes=None
    )
    assert (exact.cash_difference, exact.cash_to_deposit) == (D("0.00"), D("100.00"))
    short = decide_closing(
        expected_cash=D("150.00"),
        counted_cash=D("148.50"),
        retained_float=D("50"),
        notes="Vuelto mal dado",
    )
    assert short.cash_difference == D("-1.50")
    with pytest.raises(AppError) as error:
        decide_closing(
            expected_cash=D("150"), counted_cash=D("151"), retained_float=D("50"), notes="  "
        )
    assert _code(error) == "pos_difference_requires_notes"
    with pytest.raises(AppError) as error:
        decide_closing(
            expected_cash=D("10"), counted_cash=D("10"), retained_float=D("11"), notes=None
        )
    assert _code(error) == "pos_retained_float_invalid"


def test_deposit() -> None:
    assert deposit_amount(D("100.00"), D("200.00")) == D("300.00")
    assert validate_deposit(expected=D("300"), deposited=D("300.00"), notes=None) == D("0.00")
    assert validate_deposit(expected=D("300"), deposited=D("299.00"), notes="Billete falso") == D(
        "-1.00"
    )
    for kwargs, code in (
        ({"expected": D("0"), "deposited": D("1"), "notes": None}, "pos_deposit_empty"),
        ({"expected": D("5"), "deposited": D("0"), "notes": None}, "pos_deposit_amount_invalid"),
        (
            {"expected": D("5"), "deposited": D("4"), "notes": None},
            "pos_deposit_difference_requires_notes",
        ),
    ):
        with pytest.raises(AppError) as error:
            validate_deposit(**kwargs)
        assert _code(error) == code


@pytest.mark.parametrize("pin", ["482915", "907153"])
def test_pin_accepts_strong(pin: str) -> None:
    assert validate_pin(pin) == pin


@pytest.mark.parametrize(
    ("pin", "code"),
    [
        ("12345", "pos_pin_invalid"),
        ("12a456", "pos_pin_invalid"),
        ("111111", "pos_pin_weak"),
        ("123456", "pos_pin_weak"),
        ("987654", "pos_pin_weak"),
    ],
)
def test_pin_rejects_weak(pin: str, code: str) -> None:
    with pytest.raises(AppError) as error:
        validate_pin(pin)
    assert _code(error) == code

from __future__ import annotations

from datetime import date

import pytest
from app.application.fleet.license_rules import (
    EmployeeIdentity,
    LicenseFields,
    check_license,
    dui_check_digit_ok,
    parse_expiry,
    parse_license_class,
    parse_printed_date,
)

TODAY = date(2026, 11, 1)
EMPLOYEE = EmployeeIdentity(
    first_name="José Alberto",
    last_name="Peña Núñez",
    document_id="12345678-4",
    birth_date=date(1990, 5, 20),
)
VALID = LicenseFields(
    license_class="D LIVIANA",
    expires="02-2028",
    number="0101-010101-101-1",
    surnames="PEÑA NUÑEZ",
    given_names="JOSE ALBERTO",
    dui="12345678-4",
    issued="25.02.2023",
    birth="20.05.1990",
    control_number="LD-000000001",
)


def _with(**changes: str | None) -> LicenseFields:
    values = {name: getattr(VALID, name) for name in VALID.__slots__}
    return LicenseFields(**{**values, **changes})


def _codes(fields: LicenseFields, employee: EmployeeIdentity = EMPLOYEE) -> set[str]:
    return {issue.code for issue in check_license(fields, employee, today=TODAY).issues}


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("D LIVIANA", "liviana"),
        ("LIVIANA", "liviana"),
        ("liviana", "liviana"),
        ("Particular", "particular"),
        ("E PESADA", "pesada"),
        ("PESADA T", "pesada_t"),
        ("PESADA-T", "pesada_t"),
        ("T PESADA", "pesada"),
        ("MOTOCICLETA", "motocicleta"),
        ("D", None),
        ("", None),
        (None, None),
    ],
)
def test_class_comes_from_the_word_not_the_letter(
    printed: str | None, expected: str | None
) -> None:
    assert parse_license_class(printed) == expected


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("10-2021", date(2021, 10, 31)),
        ("02-2028", date(2028, 2, 29)),
        ("02-2027", date(2027, 2, 28)),
        ("12-2030", date(2030, 12, 31)),
        (" 04-2029 ", date(2029, 4, 30)),
        ("13-2028", None),
        ("00-2028", None),
        ("2-2028", None),
        ("2028-02", None),
        ("15-02-2028", None),
        ("", None),
        (None, None),
    ],
)
def test_expiry_is_the_last_day_of_the_printed_month(
    printed: str | None, expected: date | None
) -> None:
    assert parse_expiry(printed) == expected


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("27.02.2000", date(2000, 2, 27)),
        ("29.02.2024", date(2024, 2, 29)),
        ("29.02.2023", None),
        ("31.04.2024", None),
        ("2000-02-27", None),
        ("27/02/2000", None),
        (None, None),
    ],
)
def test_printed_dates(printed: str | None, expected: date | None) -> None:
    assert parse_printed_date(printed) == expected


@pytest.mark.parametrize(
    ("dui", "expected"),
    [
        ("04795633-1", True),
        ("12345678-4", True),
        ("20000001-0", True),
        ("98765432-1", False),
        ("12345678-5", False),
    ],
)
def test_dui_check_digit(dui: str, expected: bool) -> None:
    assert dui_check_digit_ok(dui) is expected


def test_valid_license_has_no_issues_and_returns_parsed_values() -> None:
    result = check_license(VALID, EMPLOYEE, today=TODAY)

    assert result.issues == ()
    assert result.license_class == "liviana"
    assert result.expires_on == date(2028, 2, 29)
    assert result.issued_on == date(2023, 2, 25)
    assert not result.has_errors
    assert not result.has_mismatches


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"license_class": "D"}, "class_invalid"),
        ({"expires": "2028"}, "expiry_invalid"),
        ({"expires": None}, "expiry_invalid"),
        ({"number": " "}, "number_missing"),
        ({"issued": "25.02.2029"}, "issued_after_expiry"),
        ({"surnames": None, "given_names": None}, "name_missing"),
    ],
)
def test_missing_or_invalid_required_values_block(
    changes: dict[str, str | None], code: str
) -> None:
    result = check_license(_with(**changes), EMPLOYEE, today=TODAY)

    assert code in {issue.code for issue in result.issues}
    assert result.has_errors


def test_name_ignores_accents_case_and_order() -> None:
    fields = _with(surnames="josé alberto", given_names="PEÑA NUÑEZ")

    assert "name_mismatch" not in _codes(fields)
    assert "name_partial" not in _codes(fields)


def test_name_ignores_particles() -> None:
    employee = EmployeeIdentity(first_name="Ana", last_name="de la Cruz")
    fields = _with(surnames="CRUZ", given_names="ANA", dui=None)

    assert "name_mismatch" not in _codes(fields, employee)


def test_name_missing_second_names_only_warns() -> None:
    employee = EmployeeIdentity(first_name="José", last_name="Peña", document_id="12345678-4")

    result = check_license(VALID, employee, today=TODAY)

    assert "name_partial" in result.warning_codes
    assert not result.has_mismatches


def test_different_person_requires_override() -> None:
    fields = _with(surnames="PEREZ GOMEZ", given_names="MARIA")

    result = check_license(fields, EMPLOYEE, today=TODAY)

    assert result.has_mismatches
    assert not result.has_errors


def test_a_single_shared_token_is_not_a_partial_match() -> None:
    employee = EmployeeIdentity(first_name="José", last_name="Pérez")
    fields = _with(surnames="JOSE", given_names=None)

    assert "name_mismatch" in _codes(fields, employee)


def test_dui_mismatch_requires_override_even_if_it_is_well_formed() -> None:
    result = check_license(_with(dui="20000001-0"), EMPLOYEE, today=TODAY)

    assert {issue.code for issue in result.issues} == {"dui_mismatch"}
    assert result.has_mismatches


def test_employee_dui_is_compared_by_digits() -> None:
    employee = EmployeeIdentity(
        first_name="José Alberto",
        last_name="Peña Núñez",
        document_id="123456784",
        birth_date=date(1990, 5, 20),
    )

    assert _codes(VALID, employee) == set()


@pytest.mark.parametrize("document_id", [None, "", "A-12"])
def test_employee_without_comparable_dui_only_warns(document_id: str | None) -> None:
    employee = EmployeeIdentity(
        first_name="José Alberto",
        last_name="Peña Núñez",
        document_id=document_id,
        birth_date=date(1990, 5, 20),
    )

    result = check_license(VALID, employee, today=TODAY)

    assert result.warning_codes == {"dui_not_registered"}
    assert not result.has_mismatches


def test_bad_check_digit_warns_without_blocking() -> None:
    result = check_license(_with(dui="98765432-1"), EMPLOYEE, today=TODAY)

    assert "dui_check_digit" in result.warning_codes
    assert not result.has_errors


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"dui": None}, "dui_missing"),
        ({"dui": "123456784"}, "dui_format"),
        ({"number": "12345"}, "number_format"),
        ({"issued": "2023-02-25"}, "issued_invalid"),
        ({"birth": "1990"}, "birth_invalid"),
        ({"birth": "21.05.1990"}, "birth_mismatch"),
        ({"control_number": "X-1"}, "control_format"),
        ({"expires": "10-2021", "issued": "25.02.2016"}, "license_expired"),
    ],
)
def test_soft_problems_only_warn(changes: dict[str, str | None], code: str) -> None:
    result = check_license(_with(**changes), EMPLOYEE, today=TODAY)

    assert code in result.warning_codes
    assert not result.has_errors
    assert not result.has_mismatches


def test_license_expiring_this_month_is_not_expired_yet() -> None:
    fields = _with(expires="11-2026", issued="25.02.2023")

    assert "license_expired" not in _codes(fields)


def test_values_are_never_corrected() -> None:
    result = check_license(_with(dui=" 123456784 "), EMPLOYEE, today=TODAY)

    assert "dui_format" in result.warning_codes

"""What a circulation card may confirm: the plate is decisive, the rest only warns."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from app.application.document_capture.profiles import CIRCULATION_CARD, DRIVER_LICENSE
from app.application.fleet.circulation_capture import fields_from_extracted
from app.application.fleet.circulation_rules import (
    CirculationFields,
    RegisteredVehicle,
    check_circulation_card,
    parse_issued,
    plate_matches,
    sides_look_swapped,
    tidy_extracted,
)
from app.infrastructure.vlm.client import clean_values

TODAY = date(2026, 11, 3)
CARD = CirculationFields(
    plate="PFAK3420-2007",
    expires="05-2029",
    issued="05-25-2026",
    year="2017",
    brand="MITSUBISHI",
    model="LANCER",
    color="NEGRO",
    chassis="CHS7X9A42QK881",
    engine="MTRZP49931FAKE",
    vin="1FAKE9X7K0M123456",
)
VEHICLE = RegisteredVehicle(
    plate="PFAK3420",
    year=2017,
    brand="Mitsubishi",
    model="Lancer EX",
    color="Negro",
    vin="1FAKE9X7K0M123456",
)


def _codes(fields: CirculationFields, vehicle: RegisteredVehicle = VEHICLE) -> dict[str, str]:
    check = check_circulation_card(fields, vehicle, today=TODAY)
    return {issue.code: issue.severity for issue in check.issues}


@pytest.mark.parametrize(
    ("printed", "registered"),
    [
        ("PFAK3420-2007", "PFAK3420"),
        ("PFAK3420-2007", "PFAK3420-2007"),
        ("pfak 3420", "PFAK-3420"),
        ("P 123-456", "P123456"),
    ],
)
def test_plate_matches_ignoring_format_and_the_card_suffix(printed: str, registered: str) -> None:
    assert plate_matches(printed, registered)


@pytest.mark.parametrize(
    ("printed", "registered"),
    [
        ("P123-9999", "P123-4567"),
        ("PFAK3421-2007", "PFAK3420"),
        ("PFAK3420-07", "PFAK3420"),
        ("", "PFAK3420"),
        ("PFAK3420", None),
    ],
)
def test_plate_does_not_match(printed: str, registered: str | None) -> None:
    assert not plate_matches(printed, registered)


def test_matching_card_has_no_issues() -> None:
    check = check_circulation_card(CARD, VEHICLE, today=TODAY)

    assert check.issues == ()
    assert check.expires_on == date(2029, 5, 31)
    assert check.issued_on == date(2026, 5, 25)


def test_other_plate_is_an_error_not_a_warning() -> None:
    check = check_circulation_card(replace(CARD, plate="P999-2007"), VEHICLE, today=TODAY)

    assert check.has_errors
    assert check.plate_differs


def test_owner_is_not_a_field_of_the_rules() -> None:
    names = set(CirculationFields.__dataclass_fields__)

    assert not names & {"owner", "name", "dui", "address"}


def test_missing_plate_and_expiry_are_errors() -> None:
    codes = _codes(replace(CARD, plate=None, expires="2029"))

    assert codes["plate_missing"] == "error"
    assert codes["expiry_invalid"] == "error"


def test_expired_card_only_warns() -> None:
    assert _codes(replace(CARD, expires="10-2026", issued="05-25-2025")) == {
        "card_expired": "warning"
    }


def test_issue_must_precede_expiry() -> None:
    assert _codes(replace(CARD, issued="06-01-2029"))["issued_after_expiry"] == "error"


@pytest.mark.parametrize("value", ["25-05-2026", "2026-05-25", "13-01-2026"])
def test_issue_date_in_another_order_only_warns(value: str) -> None:
    assert parse_issued(value) is None
    assert _codes(replace(CARD, issued=value)) == {"issued_invalid": "warning"}


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"year": "2018"}, "year_mismatch"),
        ({"year": "20I7"}, "year_invalid"),
        ({"brand": "TOYOTA"}, "brand_mismatch"),
        ({"model": "COROLLA"}, "model_mismatch"),
        ({"color": "BLANCO"}, "color_mismatch"),
        ({"vin": "1FAKE9X7K0M999999"}, "vin_mismatch"),
    ],
)
def test_differences_with_the_vehicle_only_warn(changes: dict[str, str], code: str) -> None:
    assert _codes(replace(CARD, **changes)) == {code: "warning"}


def test_differences_show_both_values() -> None:
    check = check_circulation_card(replace(CARD, brand="TOYOTA"), VEHICLE, today=TODAY)

    assert "TOYOTA" in check.issues[0].message
    assert "Mitsubishi" in check.issues[0].message


def test_empty_vehicle_data_has_nothing_to_differ_from() -> None:
    bare = RegisteredVehicle(plate="PFAK3420")

    assert _codes(CARD, bare) == {}


def test_unusual_vin_warns_and_a_misread_length_blocks() -> None:
    assert _codes(replace(CARD, vin="ABC"), RegisteredVehicle(plate="PFAK3420")) == {
        "vin_format": "warning"
    }
    assert _codes(replace(CARD, chassis="X" * 33))["chassis_too_long"] == "error"


def test_sides_swapped_are_recognized_from_what_the_model_read_on_each() -> None:
    assert not sides_look_swapped(CARD)
    assert sides_look_swapped(replace(CARD, year="05-25-2026"))
    assert sides_look_swapped(replace(CARD, expires="1FAKE9X7K0M123456"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("VTO 05-2029", "05-2029"),
        ("EMISIÓN 05-25-2026", "05-25-2026"),
        ("1FAKE9X7K0M123456,", "1FAKE9X7K0M123456"),
        ("  NEGRO ", "NEGRO"),
        ("", None),
        (None, None),
    ],
)
def test_tidy_drops_what_the_model_copies_around_a_value(
    raw: str | None, expected: str | None
) -> None:
    assert tidy_extracted(raw) == expected


def test_extracted_values_map_to_fields() -> None:
    fields = fields_from_extracted(
        {
            "front": {"values": {"placa": "PFAK3420-2007", "vto": "VTO 05-2029", "emision": None}},
            "back": {"values": {"anio": "2017", "vin": "1FAKE9X7K0M123456,"}},
        }
    )

    assert fields.plate == "PFAK3420-2007"
    assert fields.expires == "05-2029"
    assert fields.issued is None
    assert fields.year == "2017"
    assert fields.vin == "1FAKE9X7K0M123456"


def test_the_word_null_counts_as_unread() -> None:
    assert clean_values(
        '{"color": "null", "motor": "NULL", "vin": "X"}', ("color", "motor", "vin")
    ) == {
        "color": None,
        "motor": None,
        "vin": "X",
    }


def test_profile_never_asks_for_the_owner() -> None:
    asked = {key for side in CIRCULATION_CARD.sides.values() for key in side.fields}

    assert asked == {
        "placa",
        "vto",
        "emision",
        "anio",
        "marca",
        "modelo",
        "color",
        "chasis",
        "motor",
        "vin",
    }
    assert "tarjeta de circulación" in CIRCULATION_CARD.sides["front"].prompt()


def test_license_prompt_stays_exactly_the_same() -> None:
    assert DRIVER_LICENSE.sides["back"].prompt() == (
        "Extrae de esta licencia estos campos y devuelve JSON. Copia exactamente lo impreso, "
        "sin corregir nada. Usa null si un campo no se puede leer. Campos: "
        "expedicion: fecha bajo Expedición/Issue; nacimiento: fecha bajo Nacimiento/Birth; "
        "numero_control: código bajo No CONTROL"
    )

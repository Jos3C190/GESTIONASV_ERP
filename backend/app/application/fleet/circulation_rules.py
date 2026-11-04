"""Deterministic checks for the fields printed on a Salvadoran circulation card.

The vision model only proposes values; these rules decide what may be confirmed.
Who owns the vehicle is not checked: companies lease, rent and borrow vehicles.
The plate is what ties the card to the vehicle, so it has no exception: a card with
another plate belongs to another vehicle and would let this one pass compliance.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from app.application.fleet.license_rules import LicenseIssue, parse_expiry

_PLATE_SUFFIX = re.compile(r"-\d{4}$")
_ISSUED_PATTERN = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
_YEAR_PATTERN = re.compile(r"\d{4}")
_DATE_LIKE = re.compile(r"\d{2}-\d{2,4}")
_VIN_PATTERN = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
_LONG_CODE = re.compile(r"[A-Z0-9]{10,}")
_LEADING_LABEL = re.compile(r"^(VTO|EMISI[OÓ]N)\b[\s:.]*", re.IGNORECASE)

_MAX_CODE_LENGTH = 32
_MAX_COLOR_LENGTH = 40


@dataclass(frozen=True, slots=True)
class CirculationFields:
    """Values as printed on the card, either extracted or typed by the user."""

    plate: str | None = None
    expires: str | None = None
    issued: str | None = None
    year: str | None = None
    brand: str | None = None
    model: str | None = None
    color: str | None = None
    chassis: str | None = None
    engine: str | None = None
    vin: str | None = None


@dataclass(frozen=True, slots=True)
class RegisteredVehicle:
    plate: str | None
    year: int | None = None
    brand: str | None = None
    model: str | None = None
    color: str | None = None
    vin: str | None = None


@dataclass(frozen=True, slots=True)
class CirculationCheck:
    expires_on: date | None
    issued_on: date | None
    issues: tuple[LicenseIssue, ...]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def plate_differs(self) -> bool:
        return any(issue.code == "plate_mismatch" for issue in self.issues)

    @property
    def warning_codes(self) -> frozenset[str]:
        return frozenset(issue.code for issue in self.issues if issue.severity == "warning")


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


def tidy_extracted(value: str | None) -> str | None:
    """Drop what the model sometimes copies around a value: its label and stray punctuation."""
    text = _LEADING_LABEL.sub("", _clean(value)).rstrip(",.;: ")
    return text or None


def _code_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _text_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", plain)


def plate_matches(printed: str | None, registered: str | None) -> bool:
    """Compare ignoring case, spaces and hyphens, and the card's ``-AAAA`` suffix.

    The suffix comes off the card only: ``P123-4567`` must not match ``P123-9999``.
    """
    card = _clean(printed)
    expected = _code_key(_clean(registered))
    if not card or not expected:
        return False
    return expected in {_code_key(card), _code_key(_PLATE_SUFFIX.sub("", card))}


def parse_issued(value: str | None) -> date | None:
    """The card prints the issue date as ``MM-DD-AAAA``, unlike the license."""
    match = _ISSUED_PATTERN.fullmatch(_clean(value))
    if match is None:
        return None
    try:
        return date(int(match[3]), int(match[1]), int(match[2]))
    except ValueError:
        return None


def _differs(field: str, label: str, printed: str, registered: str) -> LicenseIssue:
    return LicenseIssue(
        f"{field}_mismatch",
        "warning",
        field,
        f"{label}: la tarjeta dice {printed}; el vehículo tiene {registered}.",
    )


def _check_plate(fields: CirculationFields, vehicle: RegisteredVehicle) -> list[LicenseIssue]:
    printed = _clean(fields.plate)
    if not printed:
        return [LicenseIssue("plate_missing", "error", "plate", "Indica la placa.")]
    if plate_matches(printed, vehicle.plate):
        return []
    return [
        LicenseIssue(
            "plate_mismatch",
            "error",
            "plate",
            f"La placa no coincide con {vehicle.plate}. Corrígela si se leyó mal; si la registrada está mal, "
            "corrígela en la ficha. Si no, esta tarjeta es de otro vehículo.",
        )
    ]


def _check_dates(
    fields: CirculationFields, expires_on: date | None, issued_on: date | None, today: date
) -> list[LicenseIssue]:
    issues: list[LicenseIssue] = []
    if expires_on is None:
        issues.append(
            LicenseIssue(
                "expiry_invalid", "error", "expires", "Indica el vencimiento como MM-AAAA."
            )
        )
    elif expires_on < today:
        issues.append(
            LicenseIssue("card_expired", "warning", "expires", "Esta tarjeta ya está vencida.")
        )
    if _clean(fields.issued) and issued_on is None:
        issues.append(
            LicenseIssue(
                "issued_invalid", "warning", "issued", "La emisión no es una fecha MM-DD-AAAA."
            )
        )
    if issued_on is not None and expires_on is not None and issued_on >= expires_on:
        issues.append(
            LicenseIssue(
                "issued_after_expiry",
                "error",
                "issued",
                "La emisión debe ser anterior al vencimiento.",
            )
        )
    return issues


def _check_year(fields: CirculationFields, vehicle: RegisteredVehicle) -> list[LicenseIssue]:
    printed = _clean(fields.year)
    if not printed:
        return []
    if _YEAR_PATTERN.fullmatch(printed) is None:
        return [LicenseIssue("year_invalid", "warning", "year", "El año no tiene cuatro dígitos.")]
    if vehicle.year is not None and int(printed) != vehicle.year:
        return [_differs("year", "Año", printed, str(vehicle.year))]
    return []


def _check_texts(fields: CirculationFields, vehicle: RegisteredVehicle) -> list[LicenseIssue]:
    """An ERP model of ``Lancer EX`` and a printed ``LANCER`` are the same vehicle."""
    issues: list[LicenseIssue] = []
    compared = (
        ("brand", "Marca", fields.brand, vehicle.brand),
        ("model", "Modelo", fields.model, vehicle.model),
        ("color", "Color", fields.color, vehicle.color),
    )
    for field, label, printed, registered in compared:
        card, erp = _text_key(_clean(printed)), _text_key(_clean(registered))
        if card and erp and card not in erp and erp not in card:
            issues.append(_differs(field, label, _clean(printed), _clean(registered)))
    return issues


def _check_vin(fields: CirculationFields, vehicle: RegisteredVehicle) -> list[LicenseIssue]:
    printed = _clean(fields.vin)
    if not printed:
        return []
    issues: list[LicenseIssue] = []
    if _VIN_PATTERN.fullmatch(printed.upper()) is None:
        issues.append(
            LicenseIssue("vin_format", "warning", "vin", "El VIN no tiene el formato habitual.")
        )
    registered = _clean(vehicle.vin)
    if registered and _code_key(printed) != _code_key(registered):
        issues.append(_differs("vin", "VIN", printed, registered))
    return issues


def _check_lengths(fields: CirculationFields) -> list[LicenseIssue]:
    """What is stored must fit its column; a value this long is almost surely a misread."""
    limits = (
        ("chassis", fields.chassis, _MAX_CODE_LENGTH),
        ("engine", fields.engine, _MAX_CODE_LENGTH),
        ("vin", fields.vin, _MAX_CODE_LENGTH),
        ("color", fields.color, _MAX_COLOR_LENGTH),
    )
    return [
        LicenseIssue(f"{field}_too_long", "error", field, "Este dato es demasiado largo.")
        for field, value, limit in limits
        if len(_clean(value)) > limit
    ]


def sides_look_swapped(fields: CirculationFields) -> bool:
    """Read from the wrong side, the year holds a date or the expiry holds a long code."""
    year_is_date = _DATE_LIKE.search(_clean(fields.year)) is not None
    expiry_is_code = _LONG_CODE.fullmatch(_clean(fields.expires).upper()) is not None
    return year_is_date or expiry_is_code


def check_circulation_card(
    fields: CirculationFields, vehicle: RegisteredVehicle, *, today: date
) -> CirculationCheck:
    expires_on = parse_expiry(fields.expires)
    issued_on = parse_issued(fields.issued)
    issues = (
        *_check_plate(fields, vehicle),
        *_check_dates(fields, expires_on, issued_on, today),
        *_check_year(fields, vehicle),
        *_check_texts(fields, vehicle),
        *_check_vin(fields, vehicle),
        *_check_lengths(fields),
    )
    return CirculationCheck(expires_on, issued_on, issues)

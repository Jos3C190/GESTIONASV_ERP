"""Deterministic checks for the fields printed on a Salvadoran driver's license.

These rules decide what a capture may confirm; the vision model only proposes
values. They never correct a value, so what the user sees is what gets checked,
and they prove coherence, not that the document is authentic.

Severity:

* ``error`` — the capture cannot be confirmed until the value is fixed.
* ``mismatch`` — differs from the employee; only a user with
  ``drivers:license_override`` may confirm, with a reason.
* ``warning`` — shown to the user, who must acknowledge it before confirming.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Literal

Severity = Literal["error", "mismatch", "warning"]

_EXPIRY_PATTERN = re.compile(r"(0[1-9]|1[0-2])-(\d{4})")
_PRINTED_DATE_PATTERN = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_NUMBER_PATTERN = re.compile(r"\d{4}-\d{6}-\d{3}-\d")
_DUI_PATTERN = re.compile(r"\d{8}-\d")
_CONTROL_PATTERN = re.compile(r"LD-\d+")

_DUI_BODY_LENGTH = 8
_DUI_LENGTH = _DUI_BODY_LENGTH + 1
_MIN_SHARED_NAME_TOKENS = 2
_NAME_PARTICLES = frozenset({"de", "del", "la", "las", "los", "y"})


@dataclass(frozen=True, slots=True)
class LicenseIssue:
    code: str
    severity: Severity
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class LicenseFields:
    """Values as printed on the card, either extracted or typed by the user."""

    license_class: str | None = None
    expires: str | None = None
    number: str | None = None
    surnames: str | None = None
    given_names: str | None = None
    dui: str | None = None
    issued: str | None = None
    birth: str | None = None
    control_number: str | None = None


@dataclass(frozen=True, slots=True)
class EmployeeIdentity:
    first_name: str
    last_name: str
    document_id: str | None = None
    birth_date: date | None = None


@dataclass(frozen=True, slots=True)
class LicenseCheck:
    license_class: str | None
    expires_on: date | None
    issued_on: date | None
    issues: tuple[LicenseIssue, ...]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_mismatches(self) -> bool:
        return any(issue.severity == "mismatch" for issue in self.issues)

    @property
    def warning_codes(self) -> frozenset[str]:
        return frozenset(issue.code for issue in self.issues if issue.severity == "warning")


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


def _name_tokens(value: str) -> Counter[str]:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = re.findall(r"[a-z0-9]+", plain)
    return Counter(token for token in tokens if token not in _NAME_PARTICLES)


def parse_license_class(value: str | None) -> str | None:
    """Map ``D LIVIANA`` or ``LIVIANA`` to a class code; the word decides, not the letter."""
    tokens = list(_name_tokens(_clean(value)).elements())
    if "pesada" in tokens:
        after = tokens[tokens.index("pesada") + 1 :]
        return "pesada_t" if "t" in after else "pesada"
    for code in ("particular", "liviana", "motocicleta"):
        if code in tokens:
            return code
    return None


def parse_expiry(value: str | None) -> date | None:
    """The card prints ``MM-AAAA``; it stays valid through the last day of that month."""
    match = _EXPIRY_PATTERN.fullmatch(_clean(value))
    if match is None:
        return None
    month, year = int(match[1]), int(match[2])
    if year < 1:
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


def parse_printed_date(value: str | None) -> date | None:
    """The back of the card prints dates as ``DD.MM.AAAA``."""
    match = _PRINTED_DATE_PATTERN.fullmatch(_clean(value))
    if match is None:
        return None
    try:
        return date(int(match[3]), int(match[2]), int(match[1]))
    except ValueError:
        return None


def dui_check_digit_ok(value: str) -> bool:
    """Check a ``NNNNNNNN-N`` DUI: weights 9..2 over the body, then ten's complement."""
    digits = value.replace("-", "")
    body = [int(digit) for digit in digits[:_DUI_BODY_LENGTH]]
    total = sum(digit * weight for digit, weight in zip(body, range(9, 1, -1), strict=True))
    return (10 - total % 10) % 10 == int(digits[_DUI_BODY_LENGTH])


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _check_required(
    fields: LicenseFields,
    license_class: str | None,
    expires_on: date | None,
) -> list[LicenseIssue]:
    issues: list[LicenseIssue] = []
    if license_class is None:
        issues.append(
            LicenseIssue("class_invalid", "error", "license_class", "Indica una clase válida.")
        )
    if expires_on is None:
        issues.append(
            LicenseIssue(
                "expiry_invalid", "error", "expires", "Indica el vencimiento como MM-AAAA."
            )
        )
    number = _clean(fields.number)
    if not number:
        issues.append(LicenseIssue("number_missing", "error", "number", "Indica el número."))
    elif _NUMBER_PATTERN.fullmatch(number) is None:
        issues.append(
            LicenseIssue(
                "number_format", "warning", "number", "El número no tiene el formato habitual."
            )
        )
    return issues


def _check_name(fields: LicenseFields, employee: EmployeeIdentity) -> list[LicenseIssue]:
    printed = _name_tokens(f"{_clean(fields.surnames)} {_clean(fields.given_names)}")
    if not printed:
        return [LicenseIssue("name_missing", "error", "surnames", "Indica el nombre.")]
    registered = _name_tokens(f"{employee.first_name} {employee.last_name}")
    if printed == registered:
        return []
    shared = sum((printed & registered).values())
    is_subset = shared in (sum(printed.values()), sum(registered.values()))
    if is_subset and shared >= _MIN_SHARED_NAME_TOKENS:
        return [
            LicenseIssue(
                "name_partial",
                "warning",
                "surnames",
                "El nombre coincide solo en parte con el del empleado.",
            )
        ]
    return [
        LicenseIssue(
            "name_mismatch", "mismatch", "surnames", "El nombre no coincide con el del empleado."
        )
    ]


def _check_dui(fields: LicenseFields, employee: EmployeeIdentity) -> list[LicenseIssue]:
    dui = _clean(fields.dui)
    if not dui:
        return [LicenseIssue("dui_missing", "warning", "dui", "No se indicó el DUI.")]
    if _DUI_PATTERN.fullmatch(dui) is None:
        return [
            LicenseIssue("dui_format", "warning", "dui", "El DUI no tiene el formato ########-#.")
        ]
    issues: list[LicenseIssue] = []
    if not dui_check_digit_ok(dui):
        issues.append(
            LicenseIssue(
                "dui_check_digit", "warning", "dui", "El dígito verificador del DUI no cuadra."
            )
        )
    registered = _digits(employee.document_id)
    if len(registered) != _DUI_LENGTH:
        issues.append(
            LicenseIssue(
                "dui_not_registered",
                "warning",
                "dui",
                "El empleado no tiene un DUI registrado para comparar.",
            )
        )
    elif registered != _digits(dui):
        issues.append(
            LicenseIssue(
                "dui_mismatch", "mismatch", "dui", "El DUI no coincide con el del empleado."
            )
        )
    return issues


def _check_back(
    fields: LicenseFields,
    employee: EmployeeIdentity,
    expires_on: date | None,
    issued_on: date | None,
) -> list[LicenseIssue]:
    issues: list[LicenseIssue] = []
    if _clean(fields.issued) and issued_on is None:
        issues.append(
            LicenseIssue(
                "issued_invalid", "warning", "issued", "La expedición no es una fecha válida."
            )
        )
    if issued_on is not None and expires_on is not None and issued_on >= expires_on:
        issues.append(
            LicenseIssue(
                "issued_after_expiry",
                "error",
                "issued",
                "La expedición debe ser anterior al vencimiento.",
            )
        )
    birth = parse_printed_date(fields.birth)
    if _clean(fields.birth) and birth is None:
        issues.append(
            LicenseIssue(
                "birth_invalid", "warning", "birth", "El nacimiento no es una fecha válida."
            )
        )
    if birth is not None and employee.birth_date is not None and birth != employee.birth_date:
        issues.append(
            LicenseIssue(
                "birth_mismatch",
                "warning",
                "birth",
                "La fecha de nacimiento no coincide con la del empleado.",
            )
        )
    control = _clean(fields.control_number)
    if control and _CONTROL_PATTERN.fullmatch(control) is None:
        issues.append(
            LicenseIssue(
                "control_format",
                "warning",
                "control_number",
                "El número de control no tiene el formato habitual.",
            )
        )
    return issues


def sides_look_swapped(fields: LicenseFields) -> bool:
    """Each side's codes have distinct formats, so finding one on the other side gives it away."""
    control_on_front = _CONTROL_PATTERN.fullmatch(_clean(fields.number)) is not None
    number_on_back = _NUMBER_PATTERN.fullmatch(_clean(fields.control_number)) is not None
    return control_on_front or number_on_back


def check_license(
    fields: LicenseFields,
    employee: EmployeeIdentity,
    *,
    today: date,
) -> LicenseCheck:
    license_class = parse_license_class(fields.license_class)
    expires_on = parse_expiry(fields.expires)
    issued_on = parse_printed_date(fields.issued)
    issues = [
        *_check_required(fields, license_class, expires_on),
        *_check_name(fields, employee),
        *_check_dui(fields, employee),
        *_check_back(fields, employee, expires_on, issued_on),
    ]
    if expires_on is not None and expires_on < today:
        issues.append(
            LicenseIssue("license_expired", "warning", "expires", "Esta licencia ya está vencida.")
        )
    return LicenseCheck(license_class, expires_on, issued_on, tuple(issues))

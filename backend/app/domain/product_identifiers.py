"""Shared validation and normalization rules for product identifiers."""

from __future__ import annotations

from typing import Literal

IdentifierType = Literal["ean", "upc", "gtin", "isbn", "manufacturer", "internal", "other"]
ISBN10_LENGTH = 10
ISBN13_LENGTH = 13


def normalize_identifier(value: str) -> str:
    """Return the company-wide comparison value for an identifier."""

    return "".join(character for character in value if character.isalnum()).upper()


def _valid_gtin_check_digit(value: str) -> bool:
    digits = [int(character) for character in value]
    check = digits.pop()
    total = sum(digit * (3 if (len(digits) - index) % 2 else 1) for index, digit in enumerate(digits))
    return (10 - total % 10) % 10 == check


def _valid_isbn10(value: str) -> bool:
    if len(value) != ISBN10_LENGTH or not value[:9].isdigit() or not (value[-1].isdigit() or value[-1] == "X"):
        return False
    total = sum((10 - index) * int(character) for index, character in enumerate(value[:9]))
    total += 10 if value[-1] == "X" else int(value[-1])
    return total % 11 == 0


def validate_identifier_value(identifier_type: str, value: str) -> str:
    """Normalize and validate an identifier, returning its stored comparison value."""

    normalized = normalize_identifier(value)
    if not normalized:
        raise ValueError("El identificador no puede estar vacío.")

    if identifier_type in {"ean", "upc", "gtin"}:
        lengths = {"ean": {8, 13, 14}, "upc": {12}, "gtin": {8, 12, 13, 14}}
        if not normalized.isdigit() or len(normalized) not in lengths[identifier_type]:
            raise ValueError(f"El identificador {identifier_type.upper()} debe tener una longitud válida.")
        if not _valid_gtin_check_digit(normalized):
            raise ValueError("El dígito de control del identificador no es válido.")
    elif identifier_type == "isbn":
        if len(normalized) == ISBN10_LENGTH:
            if not _valid_isbn10(normalized):
                raise ValueError("El ISBN-10 no es válido.")
        elif len(normalized) == ISBN13_LENGTH and normalized.isdigit():
            if not _valid_gtin_check_digit(normalized):
                raise ValueError("El dígito de control del ISBN-13 no es válido.")
        else:
            raise ValueError("El ISBN debe tener 10 o 13 caracteres válidos.")

    return normalized

"""How a vehicle's identifying numbers are stored, wherever they come from."""

from __future__ import annotations

import re


def normalize_vin(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{11,17}", normalized):
        raise ValueError("El VIN debe tener entre 11 y 17 caracteres válidos.")
    return normalized


def normalize_serial(value: str | None) -> str | None:
    """Chassis and engine numbers have no common format, unlike the VIN."""
    if value is None or not value.strip():
        return None
    return value.strip().upper()

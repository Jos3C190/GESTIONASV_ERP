"""Business rules for printing and reprinting inventory labels."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.core.exceptions import ConflictError

LabelPrintReason = Literal["initial", "reprint"]
LabelContent = Literal["full", "qr", "barcode"]
MIN_LABEL_WIDTH_MM = 25
MIN_LABEL_HEIGHT_MM = 20
MAX_LABEL_SIZE_MM = 200
FULL_LABEL_MIN_MM = 80
BARCODE_MIN_WIDTH_MM = 50
BARCODE_MIN_HEIGHT_MM = 50
QR_MIN_WIDTH_MM = 50
QR_MIN_HEIGHT_MM = 60
PRINTABLE_ASCII_MIN = 32
PRINTABLE_ASCII_MAX = 126
MAX_LABEL_NOTES_LENGTH = 160


def normalize_label_notes(notes: str | None) -> str | None:
    value = (notes or "").strip()
    if len(value) > MAX_LABEL_NOTES_LENGTH:
        raise ValueError("Las observaciones admiten hasta 160 caracteres.")
    return value or None


@dataclass(frozen=True, slots=True)
class LabelPrintLayout:
    content: LabelContent
    width_mm: int
    height_mm: int

    def __post_init__(self) -> None:
        if self.content not in {"full", "qr", "barcode"}:
            raise ValueError("Seleccione etiqueta completa, QR o Code 128.")
        if not MIN_LABEL_WIDTH_MM <= self.width_mm <= MAX_LABEL_SIZE_MM:
            raise ValueError("El ancho debe estar entre 25 y 200 mm.")
        if not MIN_LABEL_HEIGHT_MM <= self.height_mm <= MAX_LABEL_SIZE_MM:
            raise ValueError("El alto debe estar entre 20 y 200 mm.")
        if self.content == "full" and min(self.width_mm, self.height_mm) < FULL_LABEL_MIN_MM:
            raise ValueError("La etiqueta completa requiere al menos 80 x 80 mm.")
        if self.content == "qr" and (
            self.width_mm < QR_MIN_WIDTH_MM or self.height_mm < QR_MIN_HEIGHT_MM
        ):
            raise ValueError("La viñeta QR con producto, lote y fechas requiere 50 x 60 mm.")
        if self.content == "barcode" and (
            self.width_mm < BARCODE_MIN_WIDTH_MM or self.height_mm < BARCODE_MIN_HEIGHT_MM
        ):
            raise ValueError("La viñeta Code 128 con producto, lote y fechas requiere 50 x 50 mm.")

    def validate_product_code(self, code: str) -> None:
        if self.content == "qr":
            return
        if not code or any(
            not PRINTABLE_ASCII_MIN <= ord(character) <= PRINTABLE_ASCII_MAX for character in code
        ):
            raise ValueError(
                "Code 128 requiere un código interno con caracteres ASCII imprimibles."
            )
        # CODE128B: start + data + checksum, stop and ten quiet modules per side.
        required_width = math.ceil((11 * (len(code) + 2) + 13 + 20) * 0.25 + 4)
        if self.width_mm < required_width:
            raise ValueError(
                f"Este código Code 128 requiere al menos {required_width} mm de ancho. "
                "Elija un tamaño mayor o una viñeta QR."
            )

    def to_dict(self) -> dict[str, str | int]:
        return {"content": self.content, "width_mm": self.width_mm, "height_mm": self.height_mm}


def validate_print_reason(reason: LabelPrintReason, print_count: int) -> None:
    """Require one initial print before any reprint, and allow initial only once."""
    if print_count < 0:
        raise ValueError("El conteo de impresiones no puede ser negativo.")
    if reason == "initial" and print_count > 0:
        raise ConflictError(
            "La etiqueta ya tuvo una impresión inicial; registra la siguiente como reimpresión.",
            code="inventory_label_initial_already_printed",
        )
    if reason == "reprint" and print_count == 0:
        raise ConflictError(
            "Antes de reimprimir debe existir una tirada inicial registrada.",
            code="inventory_label_initial_required",
        )


def print_fingerprint(payload: dict[str, object]) -> str:
    """Stable fingerprint to make a retry idempotent and reject key reuse."""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "LabelPrintLayout",
    "LabelPrintReason",
    "normalize_label_notes",
    "print_fingerprint",
    "validate_print_reason",
]

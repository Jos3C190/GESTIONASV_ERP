"""Nota de remisión (04) que ampara un traslado entre bodegas de la misma empresa (bloque V4d).

El traslado no es una venta: la nota acompaña la circulación de los bienes (Código Tributario,
art. 109, inciso 4) y no transfiere la propiedad ni causa IVA. Este módulo arma, sin tocar la base,
lo que se le pide al servicio DTE en ``POST /api/dte/v2/nota-remision``:

- el receptor es la misma empresa, con la dirección del establecimiento de destino;
- el título de los bienes es CAT-025 04 «Traslado»;
- cada línea es lo despachado, valorado al costo promedio del kardex al despachar, como gravada
  (el IVA del resumen es informativo);
- el transporte (vehículo, placa y conductor) va en ``observaciones``, porque el esquema
  ``fe-nr-v4`` no tiene campos de transporte.

Recepción parcial, averías, sobrantes y faltantes no cambian la nota: ampara lo que salió.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import (
    DEFAULT_UNIT,
    IssuerSnapshot,
    ReceiverAddress,
)
from app.domain.entities.sales_tax import cent_round

REMISSION = "04"
#: CAT-025: 04 = Traslado.
TRANSFER_TITLE = "04"
#: CAT-022: 36 = NIT.
_NIT = "36"
VAT_RATE = Decimal("0.13")
ZERO = Decimal("0")
_PRICE_STEP = Decimal("0.00000001")
_CODE_LENGTH = 25
_DESCRIPTION_LENGTH = 1000
_OBSERVATIONS_LENGTH = 3000
_MIN_PHONE = 8
_MIN_EMAIL = 6


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


@dataclass(frozen=True, slots=True)
class RemissionLine:
    """Una línea despachada del traslado, en su unidad base."""

    sku: str
    description: str
    quantity: Decimal
    unit_code: str | None
    """CAT-014 de la unidad base del producto; sin él se informa 59 (Unidad)."""
    unit_cost: Decimal
    """Costo promedio del kardex al despachar (sin IVA)."""


@dataclass(frozen=True, slots=True)
class CompanyReceiver:
    """La empresa como receptora de sus propios bienes, en el establecimiento de destino."""

    name: str
    commercial_name: str | None
    nit: str | None
    nrc: str | None
    activity_code: str | None
    activity_description: str | None
    address: ReceiverAddress | None
    phone: str | None
    email: str | None


@dataclass(frozen=True, slots=True)
class TransferTransport:
    transfer_code: str
    origin: str
    destination: str
    vehicle_plate: str | None
    vehicle_name: str | None
    driver_name: str | None


def _number(value: Decimal) -> float | int:
    return int(value) if value == value.to_integral_value() else float(value)


def line_amount(line: RemissionLine) -> Decimal:
    return cent_round(line.quantity * line.unit_cost)


def build_items(lines: list[RemissionLine] | tuple[RemissionLine, ...]) -> list[dict[str, Any]]:
    if not lines:
        raise _rule(
            "El traslado no tiene líneas despachadas para la nota de remisión.",
            "transfer_remission_lines_missing",
        )
    items: list[dict[str, Any]] = []
    for line in lines:
        price = line.unit_cost.quantize(_PRICE_STEP, rounding=ROUND_HALF_UP)
        items.append(
            {
                "tipoItem": 1,
                "codigo": line.sku[:_CODE_LENGTH] or None,
                "uniMedida": int(line.unit_code or DEFAULT_UNIT),
                "descripcion": line.description[:_DESCRIPTION_LENGTH],
                "cantidad": _number(line.quantity),
                "precioUni": _number(price),
                "montoDescu": 0,
                "ventaNoSuj": 0,
                "ventaExenta": 0,
                "ventaGravada": _number(line_amount(line)),
            }
        )
    return items


def remission_total(lines: list[RemissionLine] | tuple[RemissionLine, ...]) -> Decimal:
    """Monto total de la operación: gravado más el IVA informativo, como lo calcula el servicio."""

    taxed = sum((line_amount(line) for line in lines), ZERO)
    return cent_round(taxed + cent_round(taxed * VAT_RATE))


def build_receiver(receiver: CompanyReceiver) -> dict[str, Any]:
    missing: list[str] = []
    if not receiver.nit:
        missing.append("NIT de la empresa")
    if not (receiver.activity_code and receiver.activity_description):
        missing.append("actividad económica principal")
    if receiver.address is None:
        missing.append("dirección del establecimiento de destino")
    if missing:
        raise _rule(
            "No se puede emitir la nota de remisión del traslado: falta "
            + "; ".join(missing)
            + ".",
            "transfer_remission_receiver_incomplete",
        )
    assert receiver.address is not None
    return {
        "tipoDocumento": _NIT,
        "numDocumento": receiver.nit,
        "nrc": receiver.nrc or None,
        "nombre": receiver.name[:250],
        "codActividad": receiver.activity_code,
        "descActividad": (receiver.activity_description or "")[:150],
        "nombreComercial": (receiver.commercial_name or "")[:150] or None,
        "direccion": {
            "departamento": receiver.address.department_code,
            "municipio": receiver.address.municipality_code,
            "distrito": receiver.address.district_code,
            "complemento": receiver.address.complement[:200],
        },
        "telefono": receiver.phone
        if receiver.phone and len(receiver.phone) >= _MIN_PHONE
        else None,
        "correo": receiver.email if receiver.email and len(receiver.email) >= _MIN_EMAIL else None,
    }


def observations(transport: TransferTransport) -> str:
    parts = [f"Traslado {transport.transfer_code} de {transport.origin} a {transport.destination}."]
    if transport.vehicle_plate or transport.vehicle_name:
        name, plate = transport.vehicle_name, transport.vehicle_plate
        # Hay vehículos cuyo nombre ya lleva la placa: no se repite.
        vehicle = (
            name if name and plate and plate in name else " ".join(p for p in (name, plate) if p)
        )
        parts.append(f"Vehículo: {vehicle}.")
    if transport.driver_name:
        parts.append(f"Conductor: {transport.driver_name}.")
    return " ".join(parts)[:_OBSERVATIONS_LENGTH]


def build_request(
    issuer: IssuerSnapshot,
    receiver: dict[str, Any],
    lines: list[RemissionLine] | tuple[RemissionLine, ...],
    transport: TransferTransport,
) -> dict[str, Any]:
    """Cuerpo de ``POST /api/dte/v2/nota-remision``."""

    return {
        "emisor": issuer.to_service(),
        "receptor": receiver,
        "bienTitulo": TRANSFER_TITLE,
        "items": build_items(lines),
        "observaciones": observations(transport),
    }


def _cents(value: Any) -> Decimal:
    return cent_round(Decimal(str(value if value is not None else 0)))


def dte_differences(dte: dict[str, Any], total: Decimal) -> list[str]:
    """La nota que devolvió el servicio debe sumar lo que guardó el ERP."""

    summary = dte.get("resumen") or {}
    sent = _cents(summary.get("montoTotalOperacion"))
    return [] if sent == total else [f"montoTotalOperacion: {sent} frente a {total}"]

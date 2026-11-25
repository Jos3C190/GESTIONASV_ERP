"""Evento de retorno sobre una factura (bloque V4d2).

Normativa DTE 2.0, regla 13.3, y Manual Funcional V2.0, sección X: el evento de retorno (tipo 18 de
CAT-002) documenta los bienes que el cliente devuelve de una factura (01) sellada. Reduce la venta y
el débito fiscal del emisor y no da crédito fiscal al receptor. No es un descuento: se devuelve por
cantidad, sin pasar de lo vendido, y los bienes se individualizan (las líneas de la factura).

Este módulo decide, sin tocar la base:

- el plazo: tres meses desde la fecha de generación de la factura (la Normativa los cuenta desde el
  sello y el Manual desde la generación; se toma la más estricta) y dos años si el emisor tiene una
  de las actividades de medicamentos que nombra el Manual (01282, 21001, 46484 y 47721; concuerda
  con la Ley de IVA, art. 62, numeral 1, literal a);
- el saldo de cada línea de la factura después de los retornos vigentes (las líneas de la factura
  se leen como las del CCF de las notas: venta neta del descuento global);
- las líneas del retorno: la cantidad devuelta al precio neto con el que se vendió, IVA incluido;
  las últimas unidades toman el saldo exacto;
- los totales (IVA contenido y retención espejo si la factura retuvo), la solicitud del servicio
  DTE y la conciliación de su respuesta.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import INVOICE, FiscalDocumentStatus
from app.domain.entities.sales_fiscal_notes import (
    CcfLine,
    LineBalance,
    Nature,
    NoteLineKind,
    PriorNoteLine,
    ccf_lines,
    line_balances,
    note_deadline,
)
from app.domain.entities.sales_tax import cent_round

RETURN_EVENT = "18"
#: Manual Funcional V2.0, sección X: con estas actividades el plazo es de dos años.
MEDICINE_ACTIVITIES = frozenset({"01282", "21001", "46484", "47721"})
MEDICINE_YEARS = 2
VAT_RATE = Decimal("0.13")
WITHHOLDING_RATE = Decimal("0.01")
MIN_REASON = 5
MAX_REASON = 300
ZERO = Decimal("0")
_QUANTITY = Decimal("0.000001")
RETURNABLE_STATUSES = (FiscalDocumentStatus.ISSUED, FiscalDocumentStatus.SIMULATED)


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class ReturnStatus(StrEnum):
    PENDING = "pending"
    ISSUED = "issued"
    """Con sello de Hacienda."""
    SIMULATED = "simulated"
    REJECTED = "rejected"
    FAILED = "failed"
    INVALIDATED = "invalidated"


#: Cuentan para el saldo de la factura y le impiden anularse.
VIGENT_STATUSES = (ReturnStatus.PENDING, ReturnStatus.ISSUED, ReturnStatus.SIMULATED)


class AnnulStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


# --- plazo ---


def return_deadline(invoice_date: date, activity_code: str | None) -> date:
    """Último día para el retorno: 3 meses desde la factura, o 2 años con medicamentos."""

    if activity_code in MEDICINE_ACTIVITIES:
        year = invoice_date.year + MEDICINE_YEARS
        return date(
            year,
            invoice_date.month,
            min(invoice_date.day, calendar.monthrange(year, invoice_date.month)[1]),
        )
    return note_deadline(invoice_date)


def require_return_in_time(invoice_date: date, activity_code: str | None, today: date) -> None:
    deadline = return_deadline(invoice_date, activity_code)
    if today > deadline:
        raise _rule(
            f"El plazo para registrar retornos de esta factura venció el {deadline:%d/%m/%Y} "
            "(Normativa DTE 2.0, regla 13.3).",
            "sales_return_deadline_passed",
        )


def require_returnable(
    document_type: str, status: FiscalDocumentStatus, *, superseded: bool
) -> None:
    if document_type != INVOICE:
        raise _rule(
            "El evento de retorno se registra sobre una factura. Para un crédito fiscal usa una nota "
            "de crédito.",
            "sales_return_document_invalid",
        )
    if status not in RETURNABLE_STATUSES or superseded:
        raise _rule(
            "Solo una factura vigente con sello admite retornos.",
            "sales_return_document_not_issued",
        )


def require_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if not MIN_REASON <= len(text) <= MAX_REASON:
        raise _rule(
            f"Escribe el motivo del retorno (de {MIN_REASON} a {MAX_REASON} caracteres).",
            "sales_return_reason_required",
        )
    return text


# --- saldo ---


def invoice_lines(dte_json: dict[str, Any]) -> tuple[CcfLine, ...]:
    """Líneas de la factura sellada con su venta neta del descuento global (IVA incluido)."""

    return ccf_lines(dte_json)


def invoice_withholding(dte_json: dict[str, Any]) -> bool:
    summary = dte_json.get("resumen") or {}
    value = summary.get("ivaRete1", summary.get("ivaRete"))
    return Decimal(str(value or 0)) > 0


@dataclass(frozen=True, slots=True)
class PriorReturnLine:
    invoice_line_number: int
    quantity: Decimal
    amount: Decimal


def return_balances(
    lines: tuple[CcfLine, ...], prior: list[PriorReturnLine] | tuple[PriorReturnLine, ...]
) -> tuple[LineBalance, ...]:
    return line_balances(
        lines,
        [
            PriorNoteLine(
                ccf_line_number=item.invoice_line_number,
                kind=NoteLineKind.RETURN,
                quantity=item.quantity,
                amount=item.amount,
            )
            for item in prior
        ],
    )


# --- plan del retorno ---


@dataclass(frozen=True, slots=True)
class ReturnLineRequest:
    invoice_line_number: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class ReturnLine:
    line_number: int
    invoice_line_number: int
    nature: Nature
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    amount: Decimal
    """Monto devuelto de la línea, IVA incluido."""
    vat: Decimal
    """IVA contenido en el monto (13/113 de lo gravado)."""


def line_vat(nature: Nature, amount: Decimal) -> Decimal:
    return cent_round(amount * VAT_RATE / (1 + VAT_RATE)) if nature == Nature.TAXED else ZERO


def plan_return(
    balances: tuple[LineBalance, ...], requests: list[ReturnLineRequest]
) -> tuple[ReturnLine, ...]:
    if not requests:
        raise _rule("Elige al menos una línea de la factura.", "sales_return_lines_required")
    numbers = [r.invoice_line_number for r in requests]
    if len(numbers) != len(set(numbers)):
        raise _rule(
            "Cada línea de la factura se devuelve una sola vez en el retorno.",
            "sales_return_line_repeated",
        )
    planned: list[ReturnLine] = []
    for position, request in enumerate(requests, start=1):
        balance = next((b for b in balances if b.line.number == request.invoice_line_number), None)
        if balance is None:
            raise _rule(
                f"La factura no tiene la línea {request.invoice_line_number}.",
                "sales_return_line_invalid",
            )
        line = balance.line
        quantity = request.quantity.quantize(_QUANTITY)
        if quantity <= 0 or quantity > balance.remaining_quantity:
            raise _rule(
                f"Línea {line.number}: la cantidad devuelta debe ser mayor que cero y no pasar de lo "
                f"que queda por devolver ({balance.remaining_quantity.normalize()}).",
                "sales_return_quantity_exceeded",
            )
        if quantity == balance.remaining_quantity:
            amount = balance.remaining_amount
        else:
            amount = cent_round(balance.remaining_amount * quantity / balance.remaining_quantity)
        if amount <= 0:
            raise _rule(
                f"Línea {line.number}: ya se devolvió todo su monto.",
                "sales_return_amount_exceeded",
            )
        unit_price = line.unit_price
        gross = cent_round(quantity * unit_price)
        if gross < amount:
            unit_price = (amount / quantity).quantize(_QUANTITY)
            gross = cent_round(quantity * unit_price)
        planned.append(
            ReturnLine(
                line_number=position,
                invoice_line_number=line.number,
                nature=line.nature,
                description=line.description,
                quantity=quantity,
                unit_price=unit_price,
                discount=max(gross - amount, ZERO),
                amount=amount,
                vat=line_vat(line.nature, amount),
            )
        )
    return tuple(planned)


@dataclass(frozen=True, slots=True)
class ReturnTotals:
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat: Decimal
    withheld: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.not_subject + self.exempt + self.taxed

    @property
    def total(self) -> Decimal:
        return self.subtotal - self.withheld


class _ReturnAmount(Protocol):
    @property
    def nature(self) -> Nature: ...

    @property
    def amount(self) -> Decimal: ...

    @property
    def vat(self) -> Decimal: ...


def return_totals(lines: Sequence[_ReturnAmount], *, withholding: bool) -> ReturnTotals:
    """Totales del retorno con sus líneas planeadas o guardadas."""

    def total(nature: Nature) -> Decimal:
        return sum((ln.amount for ln in lines if ln.nature == nature), ZERO)

    taxed = total(Nature.TAXED)
    base = cent_round(taxed / (1 + VAT_RATE))
    return ReturnTotals(
        not_subject=total(Nature.NOT_SUBJECT),
        exempt=total(Nature.EXEMPT),
        taxed=taxed,
        vat=sum((ln.vat for ln in lines), ZERO),
        withheld=cent_round(base * WITHHOLDING_RATE) if withholding else ZERO,
    )


def _number(value: Decimal) -> float | int:
    return int(value) if value == value.to_integral_value() else float(value)


def build_return_request(lines: tuple[ReturnLine, ...]) -> dict[str, Any]:
    """Cuerpo de ``POST /api/dte/{factura}/retorno``: líneas de la factura y lo devuelto."""

    items: list[dict[str, Any]] = []
    for line in lines:
        sale: dict[str, float | int] = {"ventaNoSuj": 0, "ventaExenta": 0, "ventaGravada": 0}
        field = {Nature.TAXED: "ventaGravada", Nature.EXEMPT: "ventaExenta"}.get(
            line.nature, "ventaNoSuj"
        )
        sale[field] = _number(line.amount)
        items.append(
            {
                "numItem": line.invoice_line_number,
                "cantidad": _number(line.quantity),
                "montoDescu": _number(line.discount),
                **sale,
                "ivaItem": _number(line.vat),
            }
        )
    return {"items": items}


def _cents(value: Any) -> Decimal:
    return cent_round(Decimal(str(value if value is not None else 0)))


def return_dte_differences(dte: dict[str, Any], totals: ReturnTotals) -> list[str]:
    """Diferencias entre el resumen del evento que devolvió el servicio y lo que guardó el ERP."""

    summary = dte.get("resumen") or {}
    pairs = [
        ("totalNoSuj", _cents(summary.get("totalNoSuj")), totals.not_subject),
        ("totalExenta", _cents(summary.get("totalExenta")), totals.exempt),
        ("totalGravada", _cents(summary.get("totalGravada")), totals.taxed),
        ("totalIva", _cents(summary.get("totalIva")), totals.vat),
        ("ivaRete", _cents(summary.get("ivaRete")), totals.withheld),
        ("totalPagar", _cents(summary.get("totalPagar")), totals.total),
    ]
    return [f"{name}: {sent} frente a {stored}" for name, sent, stored in pairs if sent != stored]

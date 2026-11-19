"""Notas de crédito y de débito sobre un comprobante de crédito fiscal (bloque V4c).

Código Tributario, art. 110: la nota de crédito documenta lo que rebaja el valor y el impuesto de
un CCF (devoluciones, descuentos, correcciones de precio) y la nota de débito lo que lo aumenta
(ajustes de precio al alza, intereses, cargos). Las dos relacionan el CCF que ajustan.

Este módulo decide, sin tocar la base:

- las líneas del CCF tal como quedaron selladas, con su venta neta: la venta de la línea menos su
  parte del descuento global, repartida en centavos exactos (Manual Funcional V2.0, ejemplo
  «Ajuste con NCE a CCFE con Descuento Global y Retención»);
- el saldo de cada línea (cantidad y monto) después de las notas de crédito vigentes;
- la nota de crédito pedida: devolución por cantidad o rebaja por monto, dentro del saldo;
- la nota de débito pedida: cargos que parten de una línea del CCF o son libres;
- la retención y la percepción, que repiten las del CCF con el 1 % del gravado de la nota;
- el plazo de tres meses de la nota de crédito (CT art. 111; Normativa 2.0, anexo IV, campo 17);
- la solicitud del servicio DTE y la conciliación de su respuesta.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import (
    TAX_CREDIT,
    FiscalDocumentStatus,
)
from app.domain.entities.sales_tax import cent_round

CREDIT_NOTE = "05"
DEBIT_NOTE = "06"
NOTE_TYPES = (CREDIT_NOTE, DEBIT_NOTE)
NOTE_NAMES = {CREDIT_NOTE: "nota de crédito", DEBIT_NOTE: "nota de débito"}

#: CT art. 111: los ajustes que rebajan el débito fiscal se hacen dentro de tres meses.
CREDIT_NOTE_MONTHS = 3
VAT_RATE = Decimal("0.13")
#: Retención y percepción del IVA (CT arts. 162 y 163): la nota repite la tasa del CCF.
WITHHOLDING_RATE = Decimal("0.01")
#: CAT-007: el CCF electrónico se relaciona por su código de generación.
ELECTRONIC_GENERATION = 2
MIN_REASON = 5
MAX_REASON = 300
MAX_DESCRIPTION = 1000
MIN_CHARGE_DESCRIPTION = 3
ZERO = Decimal("0")
_QUANTITY = Decimal("0.000001")

#: Estados de una nota que cuentan para el saldo del CCF y que bloquean invalidarlo.
VIGENT_STATUSES = (
    FiscalDocumentStatus.PENDING,
    FiscalDocumentStatus.CONTINGENCY,
    FiscalDocumentStatus.ISSUED,
    FiscalDocumentStatus.SIMULATED,
)
#: Estados del CCF sobre los que se emite una nota: sellado o simulado.
NOTEABLE_STATUSES = (FiscalDocumentStatus.ISSUED, FiscalDocumentStatus.SIMULATED)


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class NoteLineKind(StrEnum):
    RETURN = "return"
    """Devolución: cantidad devuelta de una línea del CCF."""
    DISCOUNT = "discount"
    """Rebaja: monto descontado de una línea del CCF (descuento o corrección de precio)."""
    CHARGE = "charge"
    """Cargo de una nota de débito."""


class Nature(StrEnum):
    TAXED = "taxed"
    EXEMPT = "exempt"
    NOT_SUBJECT = "not_subject"


_SALE_FIELD = {
    Nature.TAXED: "ventaGravada",
    Nature.EXEMPT: "ventaExenta",
    Nature.NOT_SUBJECT: "ventaNoSuj",
}
_GLOBAL_FIELD = {
    Nature.TAXED: "descuGravada",
    Nature.EXEMPT: "descuExenta",
    Nature.NOT_SUBJECT: "descuNoSuj",
}


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _number(value: Decimal) -> float | int:
    return int(value) if value == value.to_integral_value() else float(value)


# --- plazo ---


def credit_note_deadline(ccf_date: date) -> date:
    """Último día para emitir una nota de crédito: tres meses después de la fecha del CCF."""

    month = ccf_date.month - 1 + CREDIT_NOTE_MONTHS
    year = ccf_date.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(ccf_date.day, calendar.monthrange(year, month)[1]))


def require_credit_note_in_time(ccf_date: date, today: date) -> None:
    deadline = credit_note_deadline(ccf_date)
    if today > deadline:
        raise _rule(
            f"El plazo de la nota de crédito venció el {deadline:%d/%m/%Y}: los ajustes que rebajan "
            "un crédito fiscal se emiten dentro de tres meses desde su fecha (CT art. 111).",
            "sales_note_deadline_passed",
        )


def require_noteable(
    document_type: str,
    status: FiscalDocumentStatus,
    *,
    superseded: bool,
    invalidation_pending: bool,
) -> None:
    if document_type != TAX_CREDIT:
        raise _rule(
            "Las notas de crédito y de débito se emiten sobre un comprobante de crédito fiscal.",
            "sales_note_requires_ccf",
        )
    if status not in NOTEABLE_STATUSES or superseded:
        raise _rule(
            "Solo se ajusta un crédito fiscal sellado y vigente.",
            "sales_note_ccf_not_sealed",
        )
    if invalidation_pending:
        raise _rule(
            "El crédito fiscal tiene una invalidación en curso.",
            "sales_note_ccf_invalidation_pending",
        )


def require_reason(reason: str) -> str:
    text = reason.strip()
    if not MIN_REASON <= len(text) <= MAX_REASON:
        raise _rule(
            f"Explica el motivo de la nota ({MIN_REASON} a {MAX_REASON} caracteres).",
            "sales_note_reason_required",
        )
    return text


# --- líneas del CCF ---


@dataclass(frozen=True, slots=True)
class CcfLine:
    number: int
    code: str | None
    description: str
    item_type: int
    unit: int
    quantity: Decimal
    unit_price: Decimal
    nature: Nature
    sale: Decimal
    """Venta de la línea: cantidad por precio, menos el descuento de la línea."""
    net: Decimal
    """Venta menos su parte del descuento global: lo que se acredita como máximo."""


def _share_cents(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Reparte ``total`` en centavos según los pesos (resto mayor, como ``prorratearCentavos``)."""

    cents = int((total * 100).to_integral_value(ROUND_HALF_UP))
    weight_total = sum((max(w, ZERO) for w in weights), ZERO)
    if cents <= 0 or weight_total <= 0:
        return [ZERO for _ in weights]
    exact = [Decimal(cents) * max(w, ZERO) / weight_total for w in weights]
    assigned = [int(value) for value in exact]
    rest = cents - sum(assigned)
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - assigned[i]), i))
    for i in range(rest):
        assigned[order[i % len(order)]] += 1
    return [Decimal(value) / 100 for value in assigned]


def ccf_lines(dte_json: dict[str, Any]) -> tuple[CcfLine, ...]:
    """Líneas del CCF sellado, con su venta neta del descuento global del resumen."""

    body = dte_json.get("cuerpoDocumento") or []
    summary = dte_json.get("resumen") or {}
    natures: list[Nature] = []
    sales: list[Decimal] = []
    for item in body:
        nature = next((n for n in Nature if _decimal(item.get(_SALE_FIELD[n])) > 0), Nature.TAXED)
        natures.append(nature)
        sales.append(cent_round(_decimal(item.get(_SALE_FIELD[nature]))))
    discounts = [ZERO for _ in body]
    for nature in Nature:
        weights = [sale if n == nature else ZERO for n, sale in zip(natures, sales, strict=True)]
        for index, share in enumerate(
            _share_cents(_decimal(summary.get(_GLOBAL_FIELD[nature])), weights)
        ):
            discounts[index] += share
    return tuple(
        CcfLine(
            number=int(item.get("numItem") or index + 1),
            code=item.get("codigo"),
            description=str(item.get("descripcion") or ""),
            item_type=int(item.get("tipoItem") or 1),
            unit=int(item.get("uniMedida") or 59),
            quantity=_decimal(item.get("cantidad")),
            unit_price=_decimal(item.get("precioUni")),
            nature=natures[index],
            sale=sales[index],
            net=sales[index] - discounts[index],
        )
        for index, item in enumerate(body)
    )


def ccf_adjustments(dte_json: dict[str, Any]) -> tuple[bool, bool]:
    """Si el CCF retuvo y si percibió IVA: la nota repite la misma regla."""

    summary = dte_json.get("resumen") or {}
    return _decimal(summary.get("ivaRete")) > 0, _decimal(summary.get("ivaPerci")) > 0


# --- saldo ---


@dataclass(frozen=True, slots=True)
class PriorNoteLine:
    """Una línea de una nota de crédito vigente del mismo CCF."""

    ccf_line_number: int
    kind: NoteLineKind
    quantity: Decimal | None
    amount: Decimal


@dataclass(frozen=True, slots=True)
class LineBalance:
    line: CcfLine
    returned: Decimal
    credited: Decimal

    @property
    def remaining_quantity(self) -> Decimal:
        return max(self.line.quantity - self.returned, ZERO)

    @property
    def remaining_amount(self) -> Decimal:
        return max(self.line.net - self.credited, ZERO)


def line_balances(
    lines: tuple[CcfLine, ...], prior: list[PriorNoteLine] | tuple[PriorNoteLine, ...]
) -> tuple[LineBalance, ...]:
    balances: list[LineBalance] = []
    for line in lines:
        mine = [p for p in prior if p.ccf_line_number == line.number]
        balances.append(
            LineBalance(
                line=line,
                returned=sum(
                    (p.quantity or ZERO for p in mine if p.kind == NoteLineKind.RETURN), ZERO
                ),
                credited=sum((p.amount for p in mine), ZERO),
            )
        )
    return tuple(balances)


# --- plan de la nota ---


@dataclass(frozen=True, slots=True)
class NoteLine:
    line_number: int
    ccf_line_number: int | None
    kind: NoteLineKind
    nature: Nature
    description: str
    code: str | None
    item_type: int
    unit: int
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    amount: Decimal
    """Venta neta de la línea de la nota, sin IVA."""
    returned_quantity: Decimal | None = None
    """En una devolución, la cantidad devuelta que cuenta para el saldo."""


@dataclass(frozen=True, slots=True)
class NoteTotals:
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat: Decimal
    withheld: Decimal
    perceived: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.not_subject + self.exempt + self.taxed

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.vat + self.perceived - self.withheld


def note_totals(lines: tuple[NoteLine, ...], *, withholding: bool, perception: bool) -> NoteTotals:
    def total(nature: Nature) -> Decimal:
        return sum((ln.amount for ln in lines if ln.nature == nature), ZERO)

    taxed = total(Nature.TAXED)
    return NoteTotals(
        not_subject=total(Nature.NOT_SUBJECT),
        exempt=total(Nature.EXEMPT),
        taxed=taxed,
        vat=cent_round(taxed * VAT_RATE),
        withheld=cent_round(taxed * WITHHOLDING_RATE) if withholding else ZERO,
        perceived=cent_round(taxed * WITHHOLDING_RATE) if perception else ZERO,
    )


@dataclass(frozen=True, slots=True)
class CreditLineRequest:
    ccf_line_number: int
    kind: NoteLineKind
    quantity: Decimal | None = None
    amount: Decimal | None = None


def _balance(balances: tuple[LineBalance, ...], number: int) -> LineBalance:
    found = next((b for b in balances if b.line.number == number), None)
    if found is None:
        raise _rule(f"El crédito fiscal no tiene la línea {number}.", "sales_note_line_invalid")
    return found


def _unique_lines(numbers: list[int]) -> None:
    if len(numbers) != len(set(numbers)):
        raise _rule(
            "Cada línea del crédito fiscal se ajusta una sola vez en la nota.",
            "sales_note_line_repeated",
        )


def plan_credit_note(
    balances: tuple[LineBalance, ...], requests: list[CreditLineRequest]
) -> tuple[NoteLine, ...]:
    """Líneas de la nota de crédito, dentro del saldo de cada línea del CCF."""

    if not requests:
        raise _rule("Elige al menos una línea del crédito fiscal.", "sales_note_lines_required")
    _unique_lines([r.ccf_line_number for r in requests])
    planned: list[NoteLine] = []
    for position, request in enumerate(requests, start=1):
        balance = _balance(balances, request.ccf_line_number)
        line = balance.line
        if request.kind == NoteLineKind.RETURN:
            quantity = (request.quantity or ZERO).quantize(_QUANTITY)
            if quantity <= 0 or quantity > balance.remaining_quantity:
                raise _rule(
                    f"Línea {line.number}: la cantidad devuelta debe ser mayor que cero y no pasar "
                    f"de lo que queda por devolver ({balance.remaining_quantity.normalize()}).",
                    "sales_note_quantity_exceeded",
                )
            if quantity == balance.remaining_quantity:
                amount = balance.remaining_amount
            else:
                amount = cent_round(
                    balance.remaining_amount * quantity / balance.remaining_quantity
                )
            if amount <= 0:
                raise _rule(
                    f"Línea {line.number}: ya se acreditó todo su monto.",
                    "sales_note_amount_exceeded",
                )
            gross = cent_round(quantity * line.unit_price)
            unit_price = line.unit_price
            if gross < amount:
                unit_price = (amount / quantity).quantize(_QUANTITY)
                gross = cent_round(quantity * unit_price)
            planned.append(
                NoteLine(
                    line_number=position,
                    ccf_line_number=line.number,
                    kind=NoteLineKind.RETURN,
                    nature=line.nature,
                    description=line.description,
                    code=line.code,
                    item_type=line.item_type,
                    unit=line.unit,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount=max(gross - amount, ZERO),
                    amount=amount,
                    returned_quantity=quantity,
                )
            )
        elif request.kind == NoteLineKind.DISCOUNT:
            amount = cent_round(request.amount or ZERO)
            if amount <= 0 or amount > balance.remaining_amount:
                raise _rule(
                    f"Línea {line.number}: la rebaja debe ser mayor que cero y no pasar del saldo "
                    f"de la línea (${balance.remaining_amount:,.2f}).",
                    "sales_note_amount_exceeded",
                )
            planned.append(
                NoteLine(
                    line_number=position,
                    ccf_line_number=line.number,
                    kind=NoteLineKind.DISCOUNT,
                    nature=line.nature,
                    description=f"Rebaja: {line.description}"[:MAX_DESCRIPTION],
                    code=line.code,
                    item_type=line.item_type,
                    unit=line.unit,
                    quantity=Decimal(1),
                    unit_price=amount,
                    discount=ZERO,
                    amount=amount,
                )
            )
        else:
            raise _rule(
                "Una línea de nota de crédito es una devolución o una rebaja.",
                "sales_note_line_invalid",
            )
    return tuple(planned)


@dataclass(frozen=True, slots=True)
class DebitChargeRequest:
    description: str
    quantity: Decimal
    unit_price: Decimal
    nature: Nature | None = None
    """Sin línea del CCF es obligatorio; con línea, por defecto el de la línea."""
    ccf_line_number: int | None = None


def plan_debit_note(
    lines: tuple[CcfLine, ...], requests: list[DebitChargeRequest]
) -> tuple[NoteLine, ...]:
    """Cargos de la nota de débito: libres o sobre una línea del CCF, sin tope."""

    if not requests:
        raise _rule("Agrega al menos un cargo.", "sales_note_lines_required")
    _unique_lines([r.ccf_line_number for r in requests if r.ccf_line_number is not None])
    planned: list[NoteLine] = []
    for position, request in enumerate(requests, start=1):
        line = None
        if request.ccf_line_number is not None:
            line = next((ln for ln in lines if ln.number == request.ccf_line_number), None)
            if line is None:
                raise _rule(
                    f"El crédito fiscal no tiene la línea {request.ccf_line_number}.",
                    "sales_note_line_invalid",
                )
        description = request.description.strip()
        if len(description) < MIN_CHARGE_DESCRIPTION:
            raise _rule(f"Cargo {position}: describe el cargo.", "sales_note_charge_invalid")
        nature = request.nature or (line.nature if line else None)
        if nature is None:
            raise _rule(
                f"Cargo {position}: indica si es gravado, exento o no sujeto.",
                "sales_note_charge_invalid",
            )
        quantity = request.quantity.quantize(_QUANTITY)
        amount = cent_round(quantity * request.unit_price)
        if quantity <= 0 or request.unit_price < 0 or amount <= 0:
            raise _rule(
                f"Cargo {position}: la cantidad y el precio deben dar un monto mayor que cero.",
                "sales_note_charge_invalid",
            )
        planned.append(
            NoteLine(
                line_number=position,
                ccf_line_number=line.number if line else None,
                kind=NoteLineKind.CHARGE,
                nature=nature,
                description=description[:MAX_DESCRIPTION],
                code=line.code if line else None,
                item_type=line.item_type if line else 2,
                unit=line.unit if line else 99,
                quantity=quantity,
                unit_price=request.unit_price,
                discount=ZERO,
                amount=amount,
            )
        )
    return tuple(planned)


# --- solicitud y conciliación ---


def note_receiver(ccf_dte: dict[str, Any]) -> dict[str, Any]:
    """El receptor del CCF, identificado con NIT (tipo 36) como pide la nota."""

    receiver = dict(ccf_dte.get("receptor") or {})
    nit = receiver.pop("nit", None)
    return {"tipoDocumento": "36", "numDocumento": nit, **receiver}


def build_note_request(
    issuer: dict[str, Any],
    ccf_dte: dict[str, Any],
    ccf_generation_code: str,
    ccf_date: date,
    lines: tuple[NoteLine, ...],
    reason: str,
) -> dict[str, Any]:
    """Cuerpo de ``POST /api/dte/v2/nota-credito`` o ``/v2/nota-debito``."""

    withholding, perception = ccf_adjustments(ccf_dte)
    code = ccf_generation_code.upper()
    items = []
    for line in lines:
        item: dict[str, Any] = {
            "tipoItem": line.item_type,
            "numeroDocumento": code,
            "codigo": line.code,
            "uniMedida": line.unit,
            "descripcion": line.description,
            "cantidad": _number(line.quantity),
            "precioUni": _number(line.unit_price),
            "montoDescu": _number(line.discount),
            "ventaNoSuj": 0,
            "ventaExenta": 0,
            "ventaGravada": 0,
        }
        item[_SALE_FIELD[line.nature]] = _number(line.amount)
        items.append(item)
    return {
        "emisor": issuer,
        "receptor": note_receiver(ccf_dte),
        "documentosRelacionados": [
            {
                "tipoDocumento": TAX_CREDIT,
                "tipoGeneracion": ELECTRONIC_GENERATION,
                "numeroDocumento": code,
                "fechaEmision": ccf_date.isoformat(),
            }
        ],
        "items": items,
        "observaciones": reason,
        "ajustes": {"retencionIva": withholding, "percepcionIva": perception},
    }


def note_dte_differences(dte: dict[str, Any], totals: NoteTotals) -> list[str]:
    """Diferencias entre el resumen que devolvió el servicio y lo que calculó el ERP."""

    summary = dte.get("resumen") or {}
    pairs = [
        ("totalNoSuj", summary.get("totalNoSuj"), totals.not_subject),
        ("totalExenta", summary.get("totalExenta"), totals.exempt),
        ("totalGravada", summary.get("totalGravada"), totals.taxed),
        ("totalIva", summary.get("totalIva"), totals.vat),
        ("ivaRete", summary.get("ivaRete"), totals.withheld),
        ("ivaPerci", summary.get("ivaPerci"), totals.perceived),
        ("totalPagar", summary.get("totalPagar"), totals.total),
    ]
    return [
        f"{name}: {cent_round(_decimal(sent))} frente a {stored}"
        for name, sent, stored in pairs
        if cent_round(_decimal(sent)) != stored
    ]

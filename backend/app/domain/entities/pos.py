"""Punto de venta: caja, turno, efectivo y arqueo (bloque V6a).

- Un turno es de un cajero en una caja. Mientras está ``open`` vende y mueve efectivo. Al contar pasa
  a ``counted`` y deja de vender; el supervisor aprueba (``closed``, inmutable) o pide recontar
  (``recount``). Quien aprueba nunca es el cajero.
- El cierre es ciego: el cajero declara lo que contó sin ver lo esperado. El esperado lo calcula el
  servidor con todas sus fuentes: fondo inicial, entradas, salidas, retiros a caja fuerte, ventas en
  efectivo (ya sin el vuelto) y reintegros en efectivo.
- Lo contado se reparte en el fondo que queda para el siguiente turno y lo que se deposita; el
  depósito de un turno es eso más sus retiros a caja fuerte.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from app.core.exceptions import BusinessRuleError, ConflictError

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
MIN_REASON = 5
MAX_REASON = 200
MAX_NOTES = 300
MAX_OPENING_FLOAT = Decimal("10000.00")
MAX_MOVEMENT = Decimal("100000.00")
MAX_DENOMINATION_QUANTITY = 100000
PIN_LENGTH = 6
MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15
REGISTER_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")


def _rule(code: str, message: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


class ShiftStatus(StrEnum):
    OPEN = "open"
    COUNTED = "counted"
    RECOUNT = "recount"
    CLOSED = "closed"


class CashMovementKind(StrEnum):
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"
    SAFE_DROP = "safe_drop"


class CountKind(StrEnum):
    OPENING = "opening"
    CLOSING = "closing"


class DenominationForm(StrEnum):
    COIN = "coin"
    BILL = "bill"


DENOMINATIONS: dict[DenominationForm, tuple[Decimal, ...]] = {
    DenominationForm.COIN: tuple(
        Decimal(value) for value in ("0.01", "0.05", "0.10", "0.25", "0.50", "1.00")
    ),
    DenominationForm.BILL: tuple(
        Decimal(value) for value in ("1.00", "2.00", "5.00", "10.00", "20.00", "50.00", "100.00")
    ),
}


@dataclass(frozen=True)
class DenominationCount:
    form: DenominationForm
    denomination: Decimal
    quantity: int

    @property
    def amount(self) -> Decimal:
        return money(self.denomination * self.quantity)


def validate_count(lines: Iterable[DenominationCount]) -> tuple[DenominationCount, ...]:
    """Valida un conteo por denominación: denominaciones USD válidas, sin repetir, cantidades sanas."""
    seen: set[tuple[DenominationForm, Decimal]] = set()
    result: list[DenominationCount] = []
    for line in lines:
        denomination = money(line.denomination)
        if denomination not in DENOMINATIONS[line.form]:
            raise _rule(
                "pos_denomination_invalid",
                f"{denomination} no es una denominación válida de {_form_label(line.form)}.",
            )
        key = (line.form, denomination)
        if key in seen:
            raise _rule(
                "pos_denomination_repeated",
                f"La denominación de ${denomination} aparece dos veces en el conteo.",
            )
        if not 0 <= line.quantity <= MAX_DENOMINATION_QUANTITY:
            raise _rule("pos_denomination_quantity", "La cantidad contada no es válida.")
        seen.add(key)
        if line.quantity:
            result.append(DenominationCount(line.form, denomination, line.quantity))
    return tuple(result)


def count_total(lines: Iterable[DenominationCount]) -> Decimal:
    return money(sum((line.amount for line in lines), ZERO))


def _form_label(form: DenominationForm) -> str:
    return "moneda" if form is DenominationForm.COIN else "billete"


@dataclass(frozen=True)
class ShiftTotals:
    """Todo lo que mueve dinero en un turno; las ventas y reintegros llegan con V6c y V6e."""

    opening_float: Decimal
    cash_in: Decimal = ZERO
    cash_out: Decimal = ZERO
    safe_drops: Decimal = ZERO
    cash_sales: Decimal = ZERO
    cash_refunds: Decimal = ZERO
    card_sales: Decimal = ZERO
    card_refunds: Decimal = ZERO
    transfer_sales: Decimal = ZERO
    transfer_refunds: Decimal = ZERO

    @property
    def expected_cash(self) -> Decimal:
        return money(
            self.opening_float
            + self.cash_in
            - self.cash_out
            - self.safe_drops
            + self.cash_sales
            - self.cash_refunds
        )

    @property
    def expected_card(self) -> Decimal:
        return money(self.card_sales - self.card_refunds)

    @property
    def expected_transfer(self) -> Decimal:
        return money(self.transfer_sales - self.transfer_refunds)


# --- caja ------------------------------------------------------------------------------------------


def validate_register(
    *,
    code: str,
    name: str,
    opening_float: Decimal,
    cash_out_approval_threshold: Decimal,
    cash_drawer_limit: Decimal | None,
) -> None:
    if not REGISTER_CODE.match(code):
        raise _rule(
            "pos_register_code_invalid",
            "El código de la caja usa de 2 a 20 letras mayúsculas, números o guiones.",
        )
    if len(name.strip()) < 2:  # noqa: PLR2004
        raise _rule("pos_register_name_required", "Escribe el nombre de la caja.")
    if not ZERO <= opening_float <= MAX_OPENING_FLOAT:
        raise _rule(
            "pos_register_float_invalid", "El fondo sugerido debe estar entre $0.00 y $10,000.00."
        )
    if cash_out_approval_threshold < ZERO:
        raise _rule("pos_register_threshold_invalid", "El tope de salidas no puede ser negativo.")
    if cash_drawer_limit is not None and cash_drawer_limit <= opening_float:
        raise _rule(
            "pos_register_drawer_limit_invalid",
            "El límite de efectivo en gaveta debe ser mayor que el fondo sugerido.",
        )


# --- turno -----------------------------------------------------------------------------------------


def require_open(status: ShiftStatus) -> None:
    if status is not ShiftStatus.OPEN:
        raise ConflictError(
            "El turno ya se contó; no admite ventas ni movimientos de efectivo.",
            code="pos_shift_not_open",
        )


def validate_opening(opening_float: Decimal) -> Decimal:
    if not ZERO <= opening_float <= MAX_OPENING_FLOAT:
        raise _rule(
            "pos_opening_float_invalid", "El fondo inicial debe estar entre $0.00 y $10,000.00."
        )
    return money(opening_float)


def validate_reason(reason: str, *, code: str = "pos_reason_required") -> str:
    text = " ".join(reason.split())
    if not MIN_REASON <= len(text) <= MAX_REASON:
        raise _rule(code, "Explica el motivo con al menos 5 caracteres.")
    return text


def validate_movement(
    *,
    kind: CashMovementKind,
    amount: Decimal,
    available_cash: Decimal,
    approval_threshold: Decimal,
    authorized: bool,
) -> None:
    """Entrada, salida o retiro: monto positivo; lo que sale nunca supera lo que hay en gaveta."""
    if amount <= ZERO or amount > MAX_MOVEMENT or money(amount) != amount:
        raise _rule(
            "pos_movement_amount_invalid", "El monto debe ser mayor que $0.00, con centavos."
        )
    if kind is CashMovementKind.CASH_IN:
        return
    if amount > available_cash:
        raise _rule(
            "pos_movement_exceeds_cash",
            "No hay suficiente efectivo en la gaveta para ese monto.",
        )
    if kind is CashMovementKind.CASH_OUT and amount > approval_threshold and not authorized:
        raise _rule(
            "pos_movement_requires_supervisor",
            f"Una salida mayor que ${approval_threshold:,.2f} necesita la autorización de un supervisor.",
        )


def require_countable(status: ShiftStatus) -> None:
    if status not in (ShiftStatus.OPEN, ShiftStatus.RECOUNT):
        raise ConflictError(
            "El turno ya está contado y espera la revisión del supervisor.",
            code="pos_shift_not_countable",
        )


def require_reviewable(status: ShiftStatus) -> None:
    if status is not ShiftStatus.COUNTED:
        raise ConflictError(
            "Solo se revisa un turno que el cajero ya contó.", code="pos_shift_not_counted"
        )


def require_other_person(cashier_id: object, supervisor_id: object) -> None:
    if cashier_id == supervisor_id:
        raise _rule(
            "pos_self_authorization",
            "Otra persona debe autorizar: el cajero no aprueba su propio turno.",
        )


@dataclass(frozen=True)
class ClosingDecision:
    expected_cash: Decimal
    counted_cash: Decimal
    cash_difference: Decimal
    retained_float: Decimal
    cash_to_deposit: Decimal


def decide_closing(
    *,
    expected_cash: Decimal,
    counted_cash: Decimal,
    retained_float: Decimal,
    notes: str | None,
) -> ClosingDecision:
    """Aprobación: el fondo que se queda sale de lo contado; una diferencia exige explicación."""
    retained = money(retained_float)
    if not ZERO <= retained <= counted_cash:
        raise _rule(
            "pos_retained_float_invalid",
            "El fondo que se queda debe estar entre $0.00 y lo contado.",
        )
    difference = money(counted_cash - expected_cash)
    if difference != ZERO and len(" ".join((notes or "").split())) < MIN_REASON:
        raise _rule(
            "pos_difference_requires_notes",
            "Explica el faltante o el sobrante antes de aprobar el cierre.",
        )
    return ClosingDecision(
        expected_cash=money(expected_cash),
        counted_cash=money(counted_cash),
        cash_difference=difference,
        retained_float=retained,
        cash_to_deposit=money(counted_cash - retained),
    )


def deposit_amount(cash_to_deposit: Decimal, safe_drops: Decimal) -> Decimal:
    """Lo que un turno cerrado aporta al depósito: lo contado que no queda de fondo y sus retiros."""
    return money(cash_to_deposit + safe_drops)


def validate_deposit(*, expected: Decimal, deposited: Decimal, notes: str | None) -> Decimal:
    if expected <= ZERO:
        raise _rule("pos_deposit_empty", "Elige al menos un turno con efectivo por depositar.")
    if deposited <= ZERO or money(deposited) != deposited:
        raise _rule("pos_deposit_amount_invalid", "El monto depositado debe ser mayor que $0.00.")
    difference = money(deposited - expected)
    if difference != ZERO and len(" ".join((notes or "").split())) < MIN_REASON:
        raise _rule(
            "pos_deposit_difference_requires_notes",
            "El depósito no cuadra con lo esperado: explica la diferencia.",
        )
    return difference


# --- PIN de supervisor -----------------------------------------------------------------------------


def validate_pin(pin: str) -> str:
    """Seis dígitos; no se aceptan repetidos ni consecutivos (111111, 123456, 654321)."""
    if len(pin) != PIN_LENGTH or not pin.isdigit():
        raise _rule("pos_pin_invalid", "El PIN debe tener exactamente 6 dígitos.")
    digits = [int(char) for char in pin]
    steps = {b - a for a, b in pairwise(digits)}
    if steps in ({0}, {1}, {-1}):
        raise _rule(
            "pos_pin_weak", "Elige un PIN difícil de adivinar: sin dígitos repetidos ni seguidos."
        )
    return pin


def shift_code(number: int) -> str:
    return f"TUR-{number:06d}"


def deposit_code(number: int) -> str:
    return f"DEP-{number:06d}"

"""Cuentas por cobrar y recibos de cobro (bloque V5a).

- El saldo de un documento no se guarda: es su ``totalPagar`` (que ya descuenta la retención del
  1 %), menos las notas de crédito y los eventos de retorno vigentes y lo aplicado por recibos
  vigentes. Un documento invalidado no se cobra: lo aplicado vuelve al saldo a favor del cliente.
- Un recibo no es un DTE. Se anula con motivo, nunca se edita, y lo no aplicado es saldo a favor.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError

ZERO = Decimal("0")
CENT = Decimal("0.01")
MIN_REASON = 5
MAX_PAYMENTS = 10
MAX_APPLICATIONS = 50
RECEIVABLE_TYPES = ("01", "03", "06")


def _error(code: str, message: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CHECK = "check"
    OTHER = "other"


class ReceiptStatus(StrEnum):
    ISSUED = "issued"
    ANNULLED = "annulled"


class AgingBucket(StrEnum):
    CURRENT = "current"
    DAYS_1_30 = "1_30"
    DAYS_31_60 = "31_60"
    DAYS_61_90 = "61_90"
    OVER_90 = "over_90"


def due_date(issued_on: date, credit_days: int) -> date:
    return issued_on + timedelta(days=max(credit_days, 0))


def aging_bucket(due_on: date, today: date) -> AgingBucket:
    late = (today - due_on).days
    if late <= 0:
        return AgingBucket.CURRENT
    if late <= 30:  # noqa: PLR2004 - tramos de la antigüedad de saldos
        return AgingBucket.DAYS_1_30
    if late <= 60:  # noqa: PLR2004
        return AgingBucket.DAYS_31_60
    if late <= 90:  # noqa: PLR2004
        return AgingBucket.DAYS_61_90
    return AgingBucket.OVER_90


@dataclass(frozen=True)
class ReceivableDocument:
    """Un documento por cobrar con lo que lo reduce."""

    id: object
    document_type: str
    control_number: str
    issued_on: date
    due_on: date
    payable: Decimal
    credited: Decimal
    applied: Decimal
    invalidated: bool = False

    @property
    def balance(self) -> Decimal:
        if self.invalidated:
            return ZERO
        return max(self.payable - self.credited - self.applied, ZERO)

    def bucket(self, today: date) -> AgingBucket:
        return aging_bucket(self.due_on, today)

    def overdue(self, today: date) -> bool:
        return self.balance > ZERO and self.due_on < today


def aging(documents: Iterable[ReceivableDocument], today: date) -> dict[AgingBucket, Decimal]:
    totals = dict.fromkeys(AgingBucket, ZERO)
    for document in documents:
        if document.balance > ZERO:
            totals[document.bucket(today)] += document.balance
    return totals


@dataclass(frozen=True)
class PaymentLine:
    method: PaymentMethod
    amount: Decimal
    reference: str | None = None


@dataclass(frozen=True)
class ApplicationRequest:
    document_id: object
    amount: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def validate_payments(payments: Sequence[PaymentLine]) -> tuple[list[PaymentLine], Decimal]:
    if not payments:
        raise _error("sales_receipt_payments_required", "Indica al menos una forma de pago.")
    if len(payments) > MAX_PAYMENTS:
        raise _error("sales_receipt_payments_too_many", "Un recibo admite hasta 10 formas de pago.")
    clean = []
    for payment in payments:
        if payment.amount <= ZERO or _money(payment.amount) != payment.amount:
            raise _error(
                "sales_receipt_amount_invalid",
                "Cada pago debe ser mayor que cero y con dos decimales como máximo.",
            )
        reference = (payment.reference or "").strip() or None
        if payment.method is not PaymentMethod.CASH and reference is None:
            raise _error(
                "sales_receipt_reference_required",
                "Indica la referencia del pago: número de autorización, transferencia o cheque.",
            )
        clean.append(PaymentLine(payment.method, payment.amount, reference))
    return clean, sum((payment.amount for payment in clean), ZERO)


def validate_applications(
    applications: Sequence[ApplicationRequest],
    balances: dict[object, Decimal],
    available: Decimal,
) -> list[ApplicationRequest]:
    """Cada aplicación va a un documento del cliente, sin pasar de su saldo ni de lo disponible."""

    if len(applications) > MAX_APPLICATIONS:
        raise _error(
            "sales_receipt_applications_too_many", "Un recibo se aplica a hasta 50 documentos."
        )
    seen: set[object] = set()
    total = ZERO
    for item in applications:
        if item.document_id in seen:
            raise _error(
                "sales_receipt_document_repeated", "Cada documento se aplica una sola vez."
            )
        seen.add(item.document_id)
        if item.document_id not in balances:
            raise _error(
                "sales_receipt_document_invalid",
                "El documento no es una cuenta por cobrar vigente de este cliente.",
            )
        if item.amount <= ZERO or _money(item.amount) != item.amount:
            raise _error(
                "sales_receipt_amount_invalid",
                "Cada aplicación debe ser mayor que cero y con dos decimales como máximo.",
            )
        if item.amount > balances[item.document_id]:
            raise _error(
                "sales_receipt_exceeds_balance",
                "Una aplicación no puede pasar del saldo del documento; el excedente queda como "
                "saldo a favor.",
            )
        total += item.amount
    if total > available:
        raise _error(
            "sales_receipt_exceeds_available",
            "Lo aplicado no puede pasar de lo cobrado o del saldo a favor disponible.",
        )
    return list(applications)


def require_annul_reason(reason: str) -> str:
    clean = " ".join(reason.split())
    if len(clean) < MIN_REASON:
        raise _error(
            "sales_receipt_annul_reason_required",
            "Indica por qué se anula el recibo (mínimo 5 caracteres).",
        )
    return clean


def receipt_code(number: int) -> str:
    return f"RC-{number:06d}"

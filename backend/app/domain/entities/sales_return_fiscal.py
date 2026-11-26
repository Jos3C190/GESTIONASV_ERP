"""Efecto fiscal y financiero de las devoluciones (bloque V8a).

- La devolución (B08) se acepta en unidad base; el documento fiscal usa la línea del pedido en su
  unidad de venta. La cantidad fiscal es proporcional y no pasa del saldo de la línea del documento.
- Cuando una nota de crédito o un retorno dejan un documento pagado de más, el excedente vuelve a
  los recibos que lo pagaron, del más reciente al más antiguo, como saldo a favor del cliente.
- Un reintegro devuelve dinero desde el saldo a favor de un recibo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_receivables import PaymentMethod

ZERO = Decimal("0")
QUANTITY = Decimal("0.000001")
CENT = Decimal("0.01")
MIN_REASON = 5


def fiscal_quantity(
    accepted_base: Decimal, line_quantity: Decimal, line_quantity_base: Decimal
) -> Decimal:
    """Cantidad en la unidad de venta del pedido para lo aceptado en unidad base."""

    if line_quantity_base <= ZERO:
        return ZERO
    return (accepted_base * line_quantity / line_quantity_base).quantize(
        QUANTITY, rounding=ROUND_HALF_UP
    )


@dataclass(frozen=True)
class DocumentDue:
    document_id: object
    payable: Decimal
    credited: Decimal


@dataclass(frozen=True)
class AppliedAmount:
    receipt_id: object
    document_id: object
    amount: Decimal
    created_at: datetime


def released_by_receipt(
    documents: Iterable[DocumentDue], applications: Sequence[AppliedAmount]
) -> dict[object, Decimal]:
    """Excedente que vuelve a cada recibo cuando una nota o un retorno rebajan un documento pagado."""

    released: dict[object, Decimal] = {}
    by_document: dict[object, list[AppliedAmount]] = {}
    for item in applications:
        by_document.setdefault(item.document_id, []).append(item)
    for document in documents:
        items = by_document.get(document.document_id, [])
        applied = sum((item.amount for item in items), ZERO)
        excess = applied - max(document.payable - document.credited, ZERO)
        for item in sorted(items, key=lambda value: value.created_at, reverse=True):
            if excess <= ZERO:
                break
            take = min(item.amount, excess)
            released[item.receipt_id] = released.get(item.receipt_id, ZERO) + take
            excess -= take
    return released


def validate_refund(
    *,
    amount: Decimal,
    available: Decimal,
    method: PaymentMethod,
    reference: str | None,
    reason: str,
    refunded_on: date,
    today: date,
) -> tuple[str | None, str]:
    """Devuelve (referencia, motivo) normalizados o el error de negocio."""

    if amount <= ZERO or amount.quantize(CENT) != amount:
        raise BusinessRuleError(
            "El reintegro debe ser mayor que cero y con dos decimales como máximo.",
            code="sales_refund_amount_invalid",
        )
    if amount > available:
        raise BusinessRuleError(
            "El reintegro no puede pasar del saldo a favor del recibo.",
            code="sales_refund_exceeds_credit",
        )
    clean_reference = (reference or "").strip() or None
    if method is not PaymentMethod.CASH and clean_reference is None:
        raise BusinessRuleError(
            "Indica la referencia del reintegro: transferencia, cheque o reversión de tarjeta.",
            code="sales_refund_reference_required",
        )
    clean_reason = " ".join(reason.split())
    if len(clean_reason) < MIN_REASON:
        raise BusinessRuleError(
            "Indica el motivo del reintegro (mínimo 5 caracteres).",
            code="sales_refund_reason_required",
        )
    if refunded_on > today:
        raise BusinessRuleError(
            "La fecha del reintegro no puede ser futura.", code="sales_refund_date_invalid"
        )
    return clean_reference, clean_reason


def refund_code(number: int) -> str:
    return f"RI-{number:06d}"

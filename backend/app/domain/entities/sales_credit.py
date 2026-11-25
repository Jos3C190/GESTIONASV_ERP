"""Control de crédito de los pedidos (bloque V5b).

Un pedido **a crédito** pide autorización cuando:
- la exposición del cliente pasa su límite de crédito: saldo abierto de sus documentos + pedidos a
  crédito confirmados sin facturar + este pedido (sin límite configurado no se evalúa el cupo);
- tiene saldo vencido con más días de los de gracia de la empresa;
- su crédito está bloqueado a mano.

El contado no se evalúa. Los motivos se suman a los de descuento y se guardan en el pedido.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_margin import AuthorizationReason
from app.domain.entities.sales_order import PaymentTerms

ZERO = Decimal("0")
MIN_REASON = 5
CREDIT_REASONS = frozenset(
    {
        AuthorizationReason.CREDIT_LIMIT_EXCEEDED,
        AuthorizationReason.CUSTOMER_OVERDUE,
        AuthorizationReason.CUSTOMER_BLOCKED,
    }
)


@dataclass(frozen=True)
class CreditSnapshot:
    """Situación de crédito del cliente sin contar el pedido que se evalúa."""

    credit_limit: Decimal | None
    blocked: bool
    open_balance: Decimal
    pending_orders: Decimal
    overdue_beyond_grace: Decimal
    grace_days: int = 0

    def exposure_with(self, order_total: Decimal) -> Decimal:
        return self.open_balance + self.pending_orders + order_total

    def available(self) -> Decimal | None:
        if self.credit_limit is None:
            return None
        return self.credit_limit - self.open_balance - self.pending_orders


def evaluate_credit(
    snapshot: CreditSnapshot, payment_terms: PaymentTerms, order_total: Decimal
) -> list[AuthorizationReason]:
    if payment_terms is not PaymentTerms.CREDIT:
        return []
    reasons = []
    if snapshot.blocked:
        reasons.append(AuthorizationReason.CUSTOMER_BLOCKED)
    if snapshot.overdue_beyond_grace > ZERO:
        reasons.append(AuthorizationReason.CUSTOMER_OVERDUE)
    if (
        snapshot.credit_limit is not None
        and snapshot.exposure_with(order_total) > snapshot.credit_limit
    ):
        reasons.append(AuthorizationReason.CREDIT_LIMIT_EXCEEDED)
    return reasons


def credit_reasons(reasons: tuple[str, ...] | list[str]) -> list[str]:
    return [reason for reason in reasons if reason in {item.value for item in CREDIT_REASONS}]


def has_credit_authorization(reasons: tuple[str, ...], authorized: bool) -> bool:
    """El pedido se autorizó con motivos de crédito: facturarlo no vuelve a pedir autorización."""

    return authorized and bool(credit_reasons(reasons))


def require_credit_note(note: str | None) -> str:
    text = " ".join((note or "").split())
    if len(text) < MIN_REASON:
        raise BusinessRuleError(
            "Explica por qué se autoriza el crédito (mínimo 5 caracteres).",
            code="sales_credit_note_required",
        )
    return text


def require_block_reason(reason: str) -> str:
    text = " ".join(reason.split())
    if len(text) < MIN_REASON:
        raise BusinessRuleError(
            "Indica por qué se bloquea el crédito del cliente (mínimo 5 caracteres).",
            code="sales_credit_block_reason_required",
        )
    return text

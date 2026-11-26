"""V5b: evaluación de crédito de un pedido."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_credit import (
    CreditSnapshot,
    credit_reasons,
    evaluate_credit,
    has_credit_authorization,
    require_block_reason,
    require_credit_note,
)
from app.domain.entities.sales_margin import AuthorizationReason as R
from app.domain.entities.sales_order import PaymentTerms

D = Decimal
BASE = CreditSnapshot(
    credit_limit=D("500.00"),
    blocked=False,
    open_balance=D("300.00"),
    pending_orders=D("100.00"),
    overdue_beyond_grace=D("0"),
)


def test_within_limit_and_cash_are_not_evaluated() -> None:
    assert evaluate_credit(BASE, PaymentTerms.CREDIT, D("100.00")) == []
    assert BASE.available() == D("100.00")
    blocked = replace(BASE, blocked=True, overdue_beyond_grace=D("1"))
    assert evaluate_credit(blocked, PaymentTerms.CASH, D("9999")) == []


def test_reasons_add_up() -> None:
    assert evaluate_credit(BASE, PaymentTerms.CREDIT, D("100.01")) == [R.CREDIT_LIMIT_EXCEEDED]
    worst = replace(BASE, blocked=True, overdue_beyond_grace=D("20"))
    assert evaluate_credit(worst, PaymentTerms.CREDIT, D("500")) == [
        R.CUSTOMER_BLOCKED,
        R.CUSTOMER_OVERDUE,
        R.CREDIT_LIMIT_EXCEEDED,
    ]
    no_limit = replace(BASE, credit_limit=None)
    assert evaluate_credit(no_limit, PaymentTerms.CREDIT, D("100000")) == []
    assert no_limit.available() is None


def test_credit_authorization_helpers() -> None:
    reasons = ("discount_above_limit", "customer_overdue")
    assert credit_reasons(reasons) == ["customer_overdue"]
    assert has_credit_authorization(reasons, authorized=True)
    assert not has_credit_authorization(reasons, authorized=False)
    assert not has_credit_authorization(("discount_above_limit",), authorized=True)
    assert require_credit_note("  cliente  de confianza ") == "cliente de confianza"
    for check in (require_credit_note, require_block_reason):
        with pytest.raises(BusinessRuleError):
            check("ok")

"""V8a: cantidad fiscal, saldo a favor por sobrepago y validación del reintegro."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_receivables import PaymentMethod
from app.domain.entities.sales_return_fiscal import (
    AppliedAmount,
    DocumentDue,
    fiscal_quantity,
    refund_code,
    released_by_receipt,
    validate_refund,
)

D = Decimal
NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)


def test_fiscal_quantity_converts_base_units() -> None:
    # 24 unidades base aceptadas de una línea de 2 cajas de 24.
    assert fiscal_quantity(D("24"), D("2"), D("48")) == D("1.000000")
    assert fiscal_quantity(D("1"), D("3"), D("3")) == D("1.000000")
    assert fiscal_quantity(D("5"), D("2"), D("0")) == 0


def test_excess_returns_to_latest_receipts_first() -> None:
    documents = [
        DocumentDue("ccf", payable=D("113.00"), credited=D("50.00")),
        DocumentDue("fe", payable=D("10.00"), credited=D("0")),
    ]
    applications = [
        AppliedAmount("r1", "ccf", D("80.00"), NOW - timedelta(days=2)),
        AppliedAmount("r2", "ccf", D("33.00"), NOW),
        AppliedAmount("r2", "fe", D("10.00"), NOW),
    ]
    # Quedan 63.00 por pagar del CCF y se aplicaron 113.00: vuelven 50.00, primero del recibo más reciente.
    assert released_by_receipt(documents, applications) == {"r2": D("33.00"), "r1": D("17.00")}
    assert released_by_receipt([DocumentDue("fe", D("10"), D("0"))], applications) == {}


def test_refund_rules() -> None:
    reference, reason = validate_refund(
        amount=D("20.00"),
        available=D("37.00"),
        method=PaymentMethod.TRANSFER,
        reference=" TRF-9 ",
        reason="  Devolución  de bolsas ",
        refunded_on=date(2026, 11, 25),
        today=date(2026, 11, 25),
    )
    assert (reference, reason) == ("TRF-9", "Devolución de bolsas")
    base = {
        "amount": D("20.00"),
        "available": D("37.00"),
        "method": PaymentMethod.CASH,
        "reference": None,
        "reason": "Devolución de bolsas",
        "refunded_on": date(2026, 11, 25),
        "today": date(2026, 11, 25),
    }
    for change, code in (
        ({"amount": D("40")}, "sales_refund_exceeds_credit"),
        ({"amount": D("0")}, "sales_refund_amount_invalid"),
        ({"method": PaymentMethod.CHECK}, "sales_refund_reference_required"),
        ({"reason": "no"}, "sales_refund_reason_required"),
        ({"refunded_on": date(2026, 11, 26)}, "sales_refund_date_invalid"),
    ):
        with pytest.raises(BusinessRuleError) as error:
            validate_refund(**{**base, **change})  # type: ignore[arg-type]
        assert error.value.code == code
    assert refund_code(3) == "RI-000003"

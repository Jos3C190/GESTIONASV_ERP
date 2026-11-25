"""V5a: saldo, vencimiento, antigüedad y validación de recibos de cobro."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_receivables import (
    AgingBucket,
    ApplicationRequest,
    PaymentLine,
    PaymentMethod,
    ReceivableDocument,
    aging,
    due_date,
    receipt_code,
    require_annul_reason,
    validate_applications,
    validate_payments,
)

D = Decimal
TODAY = date(2026, 11, 25)


def _document(**changes: object) -> ReceivableDocument:
    values: dict[str, object] = {
        "id": "a",
        "document_type": "03",
        "control_number": "DTE-03-M001P001-000000000000001",
        "issued_on": date(2026, 10, 1),
        "due_on": date(2026, 10, 31),
        "payable": D("113.00"),
        "credited": D("11.30"),
        "applied": D("50.00"),
    }
    values.update(changes)
    return ReceivableDocument(**values)  # type: ignore[arg-type]


def test_balance_due_and_aging() -> None:
    assert due_date(date(2026, 11, 1), 30) == date(2026, 12, 1)
    assert due_date(date(2026, 11, 1), 0) == date(2026, 11, 1)
    document = _document()
    assert document.balance == D("51.70")
    assert document.bucket(TODAY) is AgingBucket.DAYS_1_30
    assert document.overdue(TODAY)
    assert _document(invalidated=True).balance == 0
    assert _document(applied=D("200")).balance == 0
    totals = aging(
        [
            document,
            _document(id="b", due_on=date(2026, 12, 1)),
            _document(id="c", due_on=date(2026, 7, 1)),
            _document(id="d", applied=D("101.70")),
        ],
        TODAY,
    )
    assert totals[AgingBucket.DAYS_1_30] == D("51.70")
    assert totals[AgingBucket.CURRENT] == D("51.70")
    assert totals[AgingBucket.OVER_90] == D("51.70")
    assert totals[AgingBucket.DAYS_61_90] == 0


def test_payments_need_reference_except_cash() -> None:
    lines, total = validate_payments(
        [
            PaymentLine(PaymentMethod.CASH, D("20.00")),
            PaymentLine(PaymentMethod.CARD, D("30.50"), " AUT-123 "),
        ]
    )
    assert total == D("50.50")
    assert lines[1].reference == "AUT-123"
    for payments, code in (
        ([], "sales_receipt_payments_required"),
        ([PaymentLine(PaymentMethod.TRANSFER, D("5"))], "sales_receipt_reference_required"),
        ([PaymentLine(PaymentMethod.CASH, D("0"))], "sales_receipt_amount_invalid"),
        ([PaymentLine(PaymentMethod.CASH, D("1.005"))], "sales_receipt_amount_invalid"),
    ):
        with pytest.raises(BusinessRuleError) as error:
            validate_payments(payments)
        assert error.value.code == code


def test_applications_respect_balance_and_available() -> None:
    balances: dict[object, Decimal] = {"a": D("51.70"), "b": D("10.00")}
    ok = validate_applications(
        [ApplicationRequest("a", D("51.70")), ApplicationRequest("b", D("5.00"))],
        balances,
        D("60.00"),
    )
    assert len(ok) == 2
    for applications, code in (
        ([ApplicationRequest("a", D("52"))], "sales_receipt_exceeds_balance"),
        ([ApplicationRequest("x", D("1"))], "sales_receipt_document_invalid"),
        (
            [ApplicationRequest("a", D("1")), ApplicationRequest("a", D("1"))],
            "sales_receipt_document_repeated",
        ),
        (
            [ApplicationRequest("a", D("51.70")), ApplicationRequest("b", D("10"))],
            "sales_receipt_exceeds_available",
        ),
    ):
        with pytest.raises(BusinessRuleError) as error:
            validate_applications(applications, balances, D("60.00"))
        assert error.value.code == code


def test_annul_reason_and_code() -> None:
    assert require_annul_reason("  Cheque   rechazado ") == "Cheque rechazado"
    with pytest.raises(BusinessRuleError):
        require_annul_reason("no")
    assert receipt_code(7) == "RC-000007"

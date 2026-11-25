"""V4d2: el evento de retorno sobre una factura."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import FiscalDocumentStatus
from app.domain.entities.sales_fiscal_returns import (
    PriorReturnLine,
    ReturnLineRequest,
    build_return_request,
    invoice_lines,
    invoice_withholding,
    plan_return,
    require_return_in_time,
    require_returnable,
    return_balances,
    return_deadline,
    return_dte_differences,
    return_totals,
)

D = Decimal

#: Factura de 4 harinas a $22.60 y 2 azúcares a $11.30 (IVA incluido), con $11.30 de descuento global.
FACTURA = {
    "cuerpoDocumento": [
        {
            "numItem": 1,
            "tipoItem": 1,
            "cantidad": 4,
            "codigo": "PRD-HAR-001",
            "uniMedida": 59,
            "descripcion": "Harina 50 lb",
            "precioUni": 22.6,
            "montoDescu": 0,
            "ventaNoSuj": 0,
            "ventaExenta": 0,
            "ventaGravada": 90.4,
            "ivaItem": 10.4,
        },
        {
            "numItem": 2,
            "tipoItem": 1,
            "cantidad": 2,
            "codigo": "PRD-AZU-004",
            "uniMedida": 59,
            "descripcion": "Azúcar 10 kg",
            "precioUni": 11.3,
            "montoDescu": 0,
            "ventaNoSuj": 0,
            "ventaExenta": 0,
            "ventaGravada": 22.6,
            "ivaItem": 2.6,
        },
    ],
    "resumen": {"descuGravada": 11.3, "descuExenta": 0, "descuNoSuj": 0, "ivaRete1": 0},
}


def test_deadline_three_months_or_two_years_for_medicines() -> None:
    assert return_deadline(date(2026, 11, 30), "10712") == date(2027, 2, 28)
    assert return_deadline(date(2026, 11, 30), "47721") == date(2028, 11, 30)
    assert return_deadline(date(2024, 2, 29), "21001") == date(2026, 2, 28)
    require_return_in_time(date(2026, 11, 30), None, date(2027, 2, 28))
    with pytest.raises(BusinessRuleError) as raised:
        require_return_in_time(date(2026, 11, 30), None, date(2027, 3, 1))
    assert raised.value.code == "sales_return_deadline_passed"


def test_only_a_vigent_sealed_invoice() -> None:
    require_returnable("01", FiscalDocumentStatus.SIMULATED, superseded=False)
    for document_type, status, superseded, code in (
        ("03", FiscalDocumentStatus.ISSUED, False, "sales_return_document_invalid"),
        ("01", FiscalDocumentStatus.PENDING, False, "sales_return_document_not_issued"),
        ("01", FiscalDocumentStatus.ISSUED, True, "sales_return_document_not_issued"),
    ):
        with pytest.raises(BusinessRuleError) as raised:
            require_returnable(document_type, status, superseded=superseded)
        assert raised.value.code == code


def test_return_at_net_price_with_vat_included_and_balance() -> None:
    lines = invoice_lines(FACTURA)
    # El descuento global de $11.30 se reparte 9.04 / 2.26 por venta.
    assert [line.net for line in lines] == [D("81.36"), D("20.34")]
    balances = return_balances(lines, [])
    planned = plan_return(balances, [ReturnLineRequest(1, D("1"))])
    [line] = planned
    assert line.amount == D("20.34")
    assert line.vat == D("2.34")
    assert line.discount == D("2.26")
    assert line.unit_price == D("22.6")
    totals = return_totals(planned, withholding=False)
    assert totals.total == D("20.34")
    request = build_return_request(planned)
    assert request == {
        "items": [
            {
                "numItem": 1,
                "cantidad": 1,
                "montoDescu": 2.26,
                "ventaNoSuj": 0,
                "ventaExenta": 0,
                "ventaGravada": 20.34,
                "ivaItem": 2.34,
            }
        ]
    }
    # Con una harina ya devuelta, las 3 últimas toman el saldo exacto.
    after = return_balances(lines, [PriorReturnLine(1, D("1"), D("20.34"))])
    [rest] = plan_return(after, [ReturnLineRequest(1, D("3"))])
    assert rest.amount == D("61.02")
    with pytest.raises(BusinessRuleError) as raised:
        plan_return(after, [ReturnLineRequest(1, D("4"))])
    assert raised.value.code == "sales_return_quantity_exceeded"


def test_plan_rules() -> None:
    balances = return_balances(invoice_lines(FACTURA), [])
    for requests, code in (
        ([], "sales_return_lines_required"),
        (
            [ReturnLineRequest(1, D("1")), ReturnLineRequest(1, D("1"))],
            "sales_return_line_repeated",
        ),
        ([ReturnLineRequest(9, D("1"))], "sales_return_line_invalid"),
        ([ReturnLineRequest(2, D("0"))], "sales_return_quantity_exceeded"),
    ):
        with pytest.raises(BusinessRuleError) as raised:
            plan_return(balances, requests)
        assert raised.value.code == code


def test_withholding_mirrors_the_invoice_and_reconciliation() -> None:
    retained = {**FACTURA, "resumen": {**FACTURA["resumen"], "ivaRete1": 0.8}}
    assert invoice_withholding(retained) is True
    assert invoice_withholding(FACTURA) is False
    planned = plan_return(
        return_balances(invoice_lines(retained), []), [ReturnLineRequest(1, D("4"))]
    )
    totals = return_totals(planned, withholding=True)
    # 81.36 con IVA -> 72.00 sin IVA -> 0.72 de retención.
    assert totals.withheld == D("0.72")
    assert totals.total == D("80.64")
    dte = {
        "resumen": {
            "totalNoSuj": 0,
            "totalExenta": 0,
            "totalGravada": 81.36,
            "totalIva": 9.36,
            "ivaRete": 0.72,
            "totalPagar": 80.64,
        }
    }
    assert return_dte_differences(dte, totals) == []
    assert return_dte_differences({"resumen": {**dte["resumen"], "totalPagar": 81.36}}, totals) == [
        "totalPagar: 81.36 frente a 80.64"
    ]

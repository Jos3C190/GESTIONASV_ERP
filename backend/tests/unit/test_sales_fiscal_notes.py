"""Notas de crédito y de débito sobre un crédito fiscal (V4c)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import FiscalDocumentStatus
from app.domain.entities.sales_fiscal_notes import (
    CreditLineRequest,
    DebitChargeRequest,
    Nature,
    NoteLineKind,
    PriorNoteLine,
    build_note_request,
    ccf_adjustments,
    ccf_lines,
    credit_note_deadline,
    line_balances,
    note_dte_differences,
    note_totals,
    plan_credit_note,
    plan_debit_note,
    require_credit_note_in_time,
    require_noteable,
    require_reason,
)

D = Decimal
CODE = "0a1b2c3d-4e5f-4061-8728-394a5b6c7d8e"

# CCF con descuento global de $10 sobre $200 gravados (5 %) y retención del 1 %.
CCF = {
    "receptor": {
        "nit": "06141804941099",
        "nrc": "7654321",
        "nombre": "Cliente Empresa S.A.",
        "codActividad": "62010",
        "descActividad": "Programación informática",
        "nombreComercial": None,
        "direccion": {
            "departamento": "06",
            "municipio": "20",
            "distrito": "01",
            "complemento": "Otra dirección",
        },
        "telefono": "22223333",
        "correo": "cliente@example.test",
    },
    "cuerpoDocumento": [
        {
            "numItem": 1,
            "tipoItem": 1,
            "codigo": "CAM-1",
            "uniMedida": 59,
            "descripcion": "Camiseta",
            "cantidad": 4,
            "precioUni": 30,
            "montoDescu": 0,
            "ventaNoSuj": 0,
            "ventaExenta": 0,
            "ventaGravada": 120,
        },
        {
            "numItem": 2,
            "tipoItem": 1,
            "codigo": "TAZ-1",
            "uniMedida": 59,
            "descripcion": "Taza",
            "cantidad": 8,
            "precioUni": 10,
            "montoDescu": 0,
            "ventaNoSuj": 0,
            "ventaExenta": 0,
            "ventaGravada": 80,
        },
        {
            "numItem": 3,
            "tipoItem": 2,
            "codigo": None,
            "uniMedida": 99,
            "descripcion": "Capacitación",
            "cantidad": 1,
            "precioUni": 50,
            "montoDescu": 0,
            "ventaNoSuj": 0,
            "ventaExenta": 50,
            "ventaGravada": 0,
        },
    ],
    "resumen": {
        "descuGravada": 10,
        "descuExenta": 0,
        "descuNoSuj": 0,
        "ivaRete": 1.9,
        "ivaPerci": 0,
    },
}


def test_ccf_lines_prorate_the_global_discount_per_nature() -> None:
    lines = ccf_lines(CCF)
    assert [ln.net for ln in lines] == [D("114.00"), D("76.00"), D("50.00")]
    assert [ln.nature for ln in lines] == [Nature.TAXED, Nature.TAXED, Nature.EXEMPT]
    assert ccf_adjustments(CCF) == (True, False)


def test_credit_note_returns_and_discounts_within_the_balance() -> None:
    balances = line_balances(ccf_lines(CCF), [])
    planned = plan_credit_note(
        balances,
        [
            CreditLineRequest(1, NoteLineKind.RETURN, quantity=D("1")),
            CreditLineRequest(2, NoteLineKind.DISCOUNT, amount=D("5")),
        ],
    )
    returned, discount = planned
    # Una camiseta al precio neto: 114 / 4 = 28.50; el descuento lleva la parte del global.
    assert (returned.quantity, returned.unit_price, returned.discount, returned.amount) == (
        D("1.000000"),
        D("30"),
        D("1.50"),
        D("28.50"),
    )
    assert discount.description == "Rebaja: Taza"
    assert (discount.quantity, discount.unit_price, discount.amount) == (D(1), D("5.00"), D("5.00"))

    totals = note_totals(planned, withholding=True, perception=False)
    assert (totals.taxed, totals.vat, totals.withheld, totals.total) == (
        D("33.50"),
        D("4.36"),
        D("0.34"),
        D("37.52"),
    )


def test_the_last_units_take_the_exact_remaining_amount() -> None:
    lines = ccf_lines(CCF)
    prior = [
        PriorNoteLine(1, NoteLineKind.RETURN, D("1"), D("28.50")),
        PriorNoteLine(1, NoteLineKind.DISCOUNT, None, D("10.01")),
    ]
    balance = line_balances(lines, prior)[0]
    assert (balance.remaining_quantity, balance.remaining_amount) == (D("3"), D("75.49"))
    planned = plan_credit_note(
        line_balances(lines, prior), [CreditLineRequest(1, NoteLineKind.RETURN, quantity=D("3"))]
    )
    assert planned[0].amount == D("75.49")
    with pytest.raises(BusinessRuleError) as raised:
        plan_credit_note(
            line_balances(
                lines, [*prior, PriorNoteLine(1, NoteLineKind.RETURN, D("3"), D("75.49"))]
            ),
            [CreditLineRequest(1, NoteLineKind.RETURN, quantity=D("1"))],
        )
    assert raised.value.code == "sales_note_quantity_exceeded"


@pytest.mark.parametrize(
    ("requests", "code"),
    [
        ([], "sales_note_lines_required"),
        ([CreditLineRequest(9, NoteLineKind.RETURN, quantity=D("1"))], "sales_note_line_invalid"),
        (
            [CreditLineRequest(1, NoteLineKind.RETURN, quantity=D("5"))],
            "sales_note_quantity_exceeded",
        ),
        (
            [CreditLineRequest(1, NoteLineKind.RETURN, quantity=D("0"))],
            "sales_note_quantity_exceeded",
        ),
        (
            [CreditLineRequest(2, NoteLineKind.DISCOUNT, amount=D("76.01"))],
            "sales_note_amount_exceeded",
        ),
        ([CreditLineRequest(2, NoteLineKind.CHARGE, amount=D("1"))], "sales_note_line_invalid"),
        (
            [
                CreditLineRequest(1, NoteLineKind.DISCOUNT, amount=D("1")),
                CreditLineRequest(1, NoteLineKind.RETURN, quantity=D("1")),
            ],
            "sales_note_line_repeated",
        ),
    ],
)
def test_credit_note_rejections(requests: list[CreditLineRequest], code: str) -> None:
    with pytest.raises(BusinessRuleError) as raised:
        plan_credit_note(line_balances(ccf_lines(CCF), []), requests)
    assert raised.value.code == code


def test_debit_note_charges_from_a_line_or_free() -> None:
    planned = plan_debit_note(
        ccf_lines(CCF),
        [
            DebitChargeRequest("Ajuste de precio de la taza", D("8"), D("0.50"), ccf_line_number=2),
            DebitChargeRequest("Intereses por mora", D("1"), D("12.34"), nature=Nature.TAXED),
            DebitChargeRequest("Flete exento", D("1"), D("5"), nature=Nature.EXEMPT),
        ],
    )
    assert [(ln.ccf_line_number, ln.nature, ln.amount, ln.code) for ln in planned] == [
        (2, Nature.TAXED, D("4.00"), "TAZ-1"),
        (None, Nature.TAXED, D("12.34"), None),
        (None, Nature.EXEMPT, D("5.00"), None),
    ]
    totals = note_totals(planned, withholding=False, perception=True)
    assert (totals.vat, totals.perceived, totals.total) == (D("2.12"), D("0.16"), D("23.62"))
    for request, code in (
        (DebitChargeRequest("Sin naturaleza", D("1"), D("1")), "sales_note_charge_invalid"),
        (
            DebitChargeRequest("Cero", D("1"), D("0"), nature=Nature.TAXED),
            "sales_note_charge_invalid",
        ),
        (DebitChargeRequest("x", D("1"), D("1"), nature=Nature.TAXED), "sales_note_charge_invalid"),
        (DebitChargeRequest("Línea", D("1"), D("1"), ccf_line_number=7), "sales_note_line_invalid"),
    ):
        with pytest.raises(BusinessRuleError) as raised:
            plan_debit_note(ccf_lines(CCF), [request])
        assert raised.value.code == code


def test_request_relates_the_ccf_and_repeats_its_withholding() -> None:
    planned = plan_credit_note(
        line_balances(ccf_lines(CCF), []),
        [CreditLineRequest(3, NoteLineKind.RETURN, quantity=D("1"))],
    )
    body = build_note_request({"nit": "x"}, CCF, CODE, date(2026, 11, 2), planned, "Devolución")
    assert body["documentosRelacionados"] == [
        {
            "tipoDocumento": "03",
            "tipoGeneracion": 2,
            "numeroDocumento": CODE.upper(),
            "fechaEmision": "2026-11-02",
        }
    ]
    assert body["receptor"]["tipoDocumento"] == "36"
    assert body["receptor"]["numDocumento"] == "06141804941099"
    assert "nit" not in body["receptor"]
    item = body["items"][0]
    assert (item["ventaExenta"], item["ventaGravada"], item["numeroDocumento"]) == (
        50,
        0,
        CODE.upper(),
    )
    assert body["ajustes"] == {"retencionIva": True, "percepcionIva": False}
    assert body["observaciones"] == "Devolución"


def test_reconciliation_of_the_service_summary() -> None:
    planned = plan_credit_note(
        line_balances(ccf_lines(CCF), []),
        [CreditLineRequest(2, NoteLineKind.DISCOUNT, amount=D("10"))],
    )
    totals = note_totals(planned, withholding=True, perception=False)
    good = {
        "resumen": {
            "totalNoSuj": 0,
            "totalExenta": 0,
            "totalGravada": 10,
            "totalIva": 1.3,
            "ivaRete": 0.1,
            "ivaPerci": 0,
            "totalPagar": 11.2,
        }
    }
    assert note_dte_differences(good, totals) == []
    bad = {"resumen": {**good["resumen"], "ivaRete": 0}}
    assert note_dte_differences(bad, totals) == ["ivaRete: 0.00 frente a 0.10"]


def test_deadline_is_three_months_from_the_ccf() -> None:
    assert credit_note_deadline(date(2026, 11, 30)) == date(2027, 2, 28)
    assert credit_note_deadline(date(2026, 8, 15)) == date(2026, 11, 15)
    require_credit_note_in_time(date(2026, 8, 15), date(2026, 11, 15))
    with pytest.raises(BusinessRuleError) as raised:
        require_credit_note_in_time(date(2026, 8, 15), date(2026, 11, 16))
    assert raised.value.code == "sales_note_deadline_passed"
    assert "15/11/2026" in raised.value.message


def test_only_a_sealed_vigent_ccf_takes_notes() -> None:
    require_noteable(
        "03", FiscalDocumentStatus.SIMULATED, superseded=False, invalidation_pending=False
    )
    for args, code in (
        (("01", FiscalDocumentStatus.ISSUED, False, False), "sales_note_requires_ccf"),
        (("03", FiscalDocumentStatus.PENDING, False, False), "sales_note_ccf_not_sealed"),
        (("03", FiscalDocumentStatus.INVALIDATED, False, False), "sales_note_ccf_not_sealed"),
        (("03", FiscalDocumentStatus.ISSUED, True, False), "sales_note_ccf_not_sealed"),
        (("03", FiscalDocumentStatus.ISSUED, False, True), "sales_note_ccf_invalidation_pending"),
    ):
        document_type, status, superseded, pending = args
        with pytest.raises(BusinessRuleError) as raised:
            require_noteable(
                document_type, status, superseded=superseded, invalidation_pending=pending
            )
        assert raised.value.code == code
    assert require_reason("  Devolución  ") == "Devolución"
    with pytest.raises(BusinessRuleError):
        require_reason("abc")

"""V3b: del pedido a la solicitud del servicio DTE (snapshot, receptor, líneas y conciliación)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import OperatingMode
from app.domain.entities.sales_fiscal_document import (
    FiscalDocumentStatus,
    FiscalLine,
    FiscalMode,
    IssuerAddress,
    IssuerFacts,
    IssuerSnapshot,
    OrderFiscalTotals,
    ReceiverAddress,
    ReceiverFacts,
    build_receiver,
    build_request,
    dte_differences,
    fiscal_mode,
    issuer_snapshot,
    require_invoiceable,
    require_retryable,
    service_status,
)

D = Decimal
ADDRESS = IssuerAddress(
    "06",
    "San Salvador",
    "23",
    "San Salvador Centro",
    "14",
    "San Salvador",
    "Col. Escalón, calle «El Mirador» #5",
    "1.1",
)
ISSUER = IssuerSnapshot(
    legal_name="Panadería Lorena, S.A. de C.V.",
    trade_name="Lorena",
    nit="06142803901121",
    nrc="1234567",
    activity_code="10711",
    activity_description="Elaboración de productos de panadería",
    activity_catalog_version="1.1",
    address=ADDRESS,
    phone="22223333",
    email="dte@lorena.com.sv",
    establishment_type="02",
    establishment_code="M001",
    point_of_sale_code="P001",
)
#: Calculado con ``issuerContractV2.js`` del servicio sobre el mismo emisor.
SERVICE_HASH = "7c50fb814380eea33efd008f15c758124f85bd6a60826eb8555e339361e2ae3a"

TAXPAYER = ReceiverFacts(
    name="Distribuidora El Sol, S.A.",
    commercial_name="El Sol",
    is_generic=False,
    is_taxpayer=True,
    document_type="36",
    document_number="06141804941099",
    nrc="7654321",
    activity_code="46900",
    activity_description="Venta al por mayor de otros productos",
    address=ReceiverAddress("06", "20", "01", "Av. Olímpica 123"),
    phone="22224444",
    email="compras@elsol.com.sv",
)


def _line(**values: object) -> FiscalLine:
    base: dict[str, object] = {
        "sku": "PAN-001",
        "description": "Pan dulce",
        "item_type": "1",
        "unit_code": None,
        "quantity": D("2"),
        "unit_price": D("56.5"),
        "discount": D("0"),
        "not_subject": D("0"),
        "exempt": D("0"),
        "taxed": D("113"),
    }
    return FiscalLine(**{**base, **values})  # type: ignore[arg-type]


def _invoice_totals(**values: object) -> OrderFiscalTotals:
    # Dos líneas de $113 con IVA y 10 % de descuento global.
    base: dict[str, object] = {
        "document_type": "01",
        "global_discount_percent": D("10"),
        "total_not_subject": D("0.00"),
        "total_exempt": D("0.00"),
        "total_taxed": D("226.00"),
        "subtotal_sales": D("226.00"),
        "total_discount": D("22.60"),
        "subtotal": D("203.40"),
        "vat": D("23.40"),
        "vat_perceived": D("0.00"),
        "vat_withheld": D("0.00"),
        "total": D("203.40"),
        "on_credit": False,
        "credit_days": 0,
    }
    return OrderFiscalTotals(**{**base, **values})  # type: ignore[arg-type]


def _ccf_totals(**values: object) -> OrderFiscalTotals:
    # $200 sin IVA a crédito, con retención del 1 %.
    base: dict[str, object] = {
        "document_type": "03",
        "global_discount_percent": D("0"),
        "total_not_subject": D("0.00"),
        "total_exempt": D("0.00"),
        "total_taxed": D("200.00"),
        "subtotal_sales": D("200.00"),
        "total_discount": D("0.00"),
        "subtotal": D("200.00"),
        "vat": D("26.00"),
        "vat_perceived": D("0.00"),
        "vat_withheld": D("2.00"),
        "total": D("224.00"),
        "on_credit": True,
        "credit_days": 30,
    }
    return OrderFiscalTotals(**{**base, **values})  # type: ignore[arg-type]


def test_issuer_hash_matches_the_service() -> None:
    assert ISSUER.sha256() == SERVICE_HASH
    emisor = ISSUER.to_service()
    assert emisor["snapshotSha256"] == SERVICE_HASH
    assert emisor["codEstablecimientoMH"] == "001"
    assert emisor["codPuntoVentaMH"] == "001"
    assert emisor["codEstable"] == "M001"
    assert ISSUER.record()["snapshotSha256"] == SERVICE_HASH
    # Cualquier cambio del emisor cambia el hash.
    assert replace(ISSUER, point_of_sale_code="P002").sha256() != SERVICE_HASH


def test_issuer_snapshot_reports_everything_missing() -> None:
    facts = IssuerFacts(
        legal_name="Lorena",
        trade_name=None,
        nit=None,
        nrc="1234567",
        activity_code=None,
        activity_description=None,
        activity_catalog_version="1.1",
        address=None,
        phone="2222",
        email=None,
        establishment_type="02",
        establishment_code="M001",
        point_of_sale_code="P001",
    )
    with pytest.raises(BusinessRuleError) as raised:
        issuer_snapshot(facts)
    assert raised.value.code == "sales_invoice_issuer_incomplete"
    for fragment in ("NIT", "actividad", "dirección", "teléfono", "correo"):
        assert fragment in raised.value.message
    complete = replace(
        facts,
        nit="06142803901121",
        activity_code="10711",
        activity_description="Panadería",
        address=ADDRESS,
        phone="22223333",
        email="dte@lorena.com.sv",
    )
    assert issuer_snapshot(complete).nit == "06142803901121"


def test_receivers_by_document() -> None:
    ccf = build_receiver("03", TAXPAYER)
    assert ccf is not None
    assert ccf["nit"] == "06141804941099"
    assert ccf["direccion"]["complemento"] == "Av. Olímpica 123"
    assert "tipoDocumento" not in ccf

    generic = replace(TAXPAYER, is_generic=True, is_taxpayer=False)
    assert build_receiver("01", generic) is None

    person = replace(
        TAXPAYER,
        is_taxpayer=False,
        document_type="13",
        document_number="012345678",
        nrc=None,
        activity_code=None,
        activity_description=None,
        address=None,
        phone="123",
    )
    invoice = build_receiver("01", person)
    assert invoice is not None
    assert invoice["numDocumento"] == "01234567-8"
    assert invoice["nrc"] is None
    assert invoice["telefono"] is None
    assert invoice["direccion"] is None

    with pytest.raises(BusinessRuleError) as raised:
        build_receiver("03", person)
    assert raised.value.code == "sales_invoice_receiver_incomplete"
    assert "NRC" in raised.value.message


def test_invoice_request_carries_the_global_discount_in_the_summary() -> None:
    lines = [
        _line(),
        _line(sku="PAS-001", description="Pastel", quantity=D("1"), unit_price=D("113")),
    ]
    request = build_request(ISSUER, None, lines, _invoice_totals())
    assert request["emisor"]["snapshotSha256"] == SERVICE_HASH
    assert request["receptor"] is None
    assert request["descuentoGlobal"] == {"gravada": 22.6, "exenta": 0, "noSuj": 0}
    assert request["ajustes"] == {
        "condicionOperacion": 1,
        "descuentoGlobalEnResumen": True,
        "ivaRete": 0,
    }
    assert request["pago"]["codigo"] == "01"
    assert request["pago"]["montoPago"] == 203.4
    first = request["items"][0]
    assert first["uniMedida"] == 59
    assert first["precioUni"] == 56.5
    assert first["ventaGravada"] == 113


def test_ccf_request_on_credit_with_withholding() -> None:
    lines = [_line(unit_price=D("100"), taxed=D("200"))]
    request = build_request(ISSUER, build_receiver("03", TAXPAYER), lines, _ccf_totals())
    assert "descuentoGlobal" not in request
    assert request["ajustes"] == {
        "condicionOperacion": 2,
        "descuentoGlobalEnResumen": True,
        "ivaRete": 2,
        "plazoDias": 30,
        "ivaPerci": 0,
    }
    assert request["pago"] == {
        "codigo": "99",
        "montoPago": 224,
        "referencia": None,
        "numPagoElectronico": None,
    }


def test_services_use_unit_99_and_company_units_their_code() -> None:
    lines = [
        _line(item_type="2", unit_code="58"),
        _line(sku="X" * 40, unit_code="36"),
    ]
    items = build_request(
        ISSUER,
        None,
        lines,
        _invoice_totals(
            global_discount_percent=D("0"),
            total_discount=D("0.00"),
            subtotal=D("226.00"),
            vat=D("26.00"),
            total=D("226.00"),
        ),
    )["items"]
    assert [item["uniMedida"] for item in items] == [99, 36]
    assert items[0]["tipoItem"] == 2
    assert len(items[1]["codigo"]) == 25


def test_request_is_not_sent_when_totals_do_not_reconcile() -> None:
    lines = [_line(), _line(sku="PAS-001", quantity=D("1"), unit_price=D("113"))]
    with pytest.raises(BusinessRuleError) as raised:
        build_request(ISSUER, None, lines, _invoice_totals(total=D("203.41")))
    assert raised.value.code == "sales_invoice_totals_mismatch"
    assert "total" in raised.value.message
    with pytest.raises(BusinessRuleError):
        build_request(ISSUER, None, lines[:1], _invoice_totals())
    with pytest.raises(BusinessRuleError) as credit:
        build_request(
            ISSUER,
            build_receiver("03", TAXPAYER),
            [_line(unit_price=D("100"), taxed=D("200"))],
            _ccf_totals(credit_days=0),
        )
    assert "plazo" in credit.value.message
    with pytest.raises(BusinessRuleError) as unsupported:
        build_request(ISSUER, None, lines, _invoice_totals(document_type="11"))
    assert unsupported.value.code == "sales_invoice_document_unsupported"


def test_dte_differences_compare_the_service_summary() -> None:
    totals = _ccf_totals()
    dte = {
        "resumen": {
            "totalNoSuj": 0,
            "totalExenta": 0,
            "totalGravada": 200,
            "totalDescu": 0,
            "subTotal": 200,
            "tributos": [{"codigo": "20", "valor": 26}],
            "ivaRete": 2,
            "ivaPerci": 0,
            "totalPagar": 224,
        }
    }
    assert dte_differences(dte, totals) == []
    dte["resumen"]["totalPagar"] = 226
    assert dte_differences(dte, totals) == ["totalPagar: 226.00 frente a 224.00"]
    invoice = {
        "resumen": {
            "totalGravada": 226,
            "totalDescu": 22.6,
            "subTotal": 203.4,
            "totalIva": 23.4,
            "totalPagar": 203.4,
        }
    }
    assert dte_differences(invoice, _invoice_totals()) == []


def test_order_rules_and_states() -> None:
    require_invoiceable("confirmed", "01", True, False)
    cases = [
        (("draft", "01", True, False), "sales_invoice_order_not_confirmed"),
        (("confirmed", "01", True, True), "sales_invoice_already_issued"),
        (("confirmed", "11", True, False), "sales_invoice_document_unsupported"),
        (("confirmed", "03", False, False), "sales_invoice_document_disabled"),
    ]
    for args, code in cases:
        with pytest.raises(BusinessRuleError) as raised:
            require_invoiceable(*args)
        assert raised.value.code == code
    require_retryable(FiscalDocumentStatus.FAILED)
    with pytest.raises(BusinessRuleError):
        require_retryable(FiscalDocumentStatus.SIMULATED)
    assert fiscal_mode(OperatingMode.TEST) is FiscalMode.TEST
    assert service_status("SIMULADO") is FiscalDocumentStatus.SIMULATED
    assert service_status("TRANSMITIDO") is FiscalDocumentStatus.ISSUED
    assert service_status("RECHAZADO") is FiscalDocumentStatus.REJECTED
    assert service_status("FIRMADO") is None

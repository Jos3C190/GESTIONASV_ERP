"""V4d: la nota de remisión que ampara un traslado."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import ReceiverAddress
from app.domain.entities.transfer_remission import (
    CompanyReceiver,
    RemissionLine,
    TransferTransport,
    build_items,
    build_receiver,
    build_request,
    dte_differences,
    observations,
    remission_total,
)

from tests.unit.test_sales_fiscal_document import ISSUER

D = Decimal
LINES = (
    RemissionLine("PRD-HAR-001", "Harina de trigo 50 lb", D("10"), "59", D("18.5")),
    RemissionLine("PRD-AZU-004", "Azúcar glass", D("3.5"), None, D("1.234567")),
)
RECEIVER = CompanyReceiver(
    name="Grupo Lorena, S.A. de C.V.",
    commercial_name="Lorena",
    nit="06142803901121",
    nrc="1234567",
    activity_code="10711",
    activity_description="Panadería",
    address=ReceiverAddress("11", "24", "01", "Sucursal Usulután, 4a calle"),
    phone="22223333",
    email="dte@lorena.com.sv",
)
TRANSPORT = TransferTransport(
    transfer_code="TR-0001",
    origin="Bodega Central",
    destination="Bodega de tienda Usulután",
    vehicle_plate="P123-456",
    vehicle_name="Camión Isuzu",
    driver_name="Ana Pérez",
)


def test_lines_at_kardex_cost_as_taxed_with_informative_vat() -> None:
    items = build_items(LINES)
    assert items[0] == {
        "tipoItem": 1,
        "codigo": "PRD-HAR-001",
        "uniMedida": 59,
        "descripcion": "Harina de trigo 50 lb",
        "cantidad": 10,
        "precioUni": 18.5,
        "montoDescu": 0,
        "ventaNoSuj": 0,
        "ventaExenta": 0,
        "ventaGravada": 185,
    }
    # 3.5 × 1.234567 = 4.3209845 → 4.32; sin unidad CAT-014 se informa 59.
    assert items[1]["ventaGravada"] == 4.32
    assert items[1]["uniMedida"] == 59
    # 189.32 gravado + 24.61 de IVA informativo.
    assert remission_total(LINES) == D("213.93")


def test_without_lines_there_is_no_note() -> None:
    with pytest.raises(BusinessRuleError) as raised:
        build_items(())
    assert raised.value.code == "transfer_remission_lines_missing"


def test_receiver_is_the_company_at_the_destination() -> None:
    receiver = build_receiver(RECEIVER)
    assert receiver["tipoDocumento"] == "36"
    assert receiver["numDocumento"] == "06142803901121"
    assert receiver["direccion"]["complemento"] == "Sucursal Usulután, 4a calle"
    incomplete = replace(RECEIVER, nit=None, address=None, activity_code=None)
    with pytest.raises(BusinessRuleError) as raised:
        build_receiver(incomplete)
    assert raised.value.code == "transfer_remission_receiver_incomplete"
    for fragment in ("NIT", "actividad", "destino"):
        assert fragment in raised.value.message


def test_transport_goes_in_the_observations() -> None:
    assert observations(TRANSPORT) == (
        "Traslado TR-0001 de Bodega Central a Bodega de tienda Usulután. "
        "Vehículo: Camión Isuzu P123-456. Conductor: Ana Pérez."
    )
    bare = replace(TRANSPORT, vehicle_plate=None, vehicle_name=None, driver_name=None)
    assert observations(bare) == "Traslado TR-0001 de Bodega Central a Bodega de tienda Usulután."


def test_request_and_reconciliation() -> None:
    body = build_request(ISSUER, build_receiver(RECEIVER), LINES, TRANSPORT)
    assert body["bienTitulo"] == "04"
    assert body["emisor"]["codEstable"] == "M001"
    assert len(body["items"]) == 2
    total = remission_total(LINES)
    assert dte_differences({"resumen": {"montoTotalOperacion": 213.93}}, total) == []
    assert dte_differences({"resumen": {"montoTotalOperacion": 189.32}}, total) == [
        "montoTotalOperacion: 189.32 frente a 213.93"
    ]

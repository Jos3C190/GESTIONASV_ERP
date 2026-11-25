"""Libros de IVA y anexos del F-07: filas, reglas entre meses y formato del CSV."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from app.domain.entities.fiscal_books import (
    Party,
    Period,
    PurchaseDocument,
    ReturnEvent,
    SaleDocument,
    annex_csv,
    annex_file_name,
    build_month,
)

NOV = Period(2026, 11)
D = Decimal


def _sale(kind: str, day: date, number: int, **changes: object) -> SaleDocument:
    base = SaleDocument(
        document_type=kind,
        issued_on=day,
        control_number=f"DTE-{kind}-M001P001-{number:015d}",
        generation_code=f"6C7EF177-8C52-41EF-B073-{number:012d}",
        seal=f"SEAL{number:036d}",
        receiver=Party("Cafetería El Trigal, S.A. de C.V.", nit="0614-010101-101-1", nrc="1234-5"),
        exempt=D("0"),
        not_subject=D("0"),
        taxed=D("100"),
        vat=D("13") if kind != "01" else D("11.50"),
        renta_operation=1,
        renta_income=3,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _purchase(**changes: object) -> PurchaseDocument:
    base = PurchaseDocument(
        purchase_code="CMP-1",
        issued_on=date(2026, 11, 3),
        document_class=4,
        document_type="03",
        number="A1B2C3D4-0000-1111-2222-333344445555",
        supplier=Party("Molinos de El Salvador, S.A. de C.V.", nit="06142410901022"),
        exempt=D("3.34"),
        taxed=D("124.23"),
        vat=D("16.15"),
        renta_operation=1,
        renta_classification=1,
        renta_sector=2,
        renta_cost_type=5,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_period_parsing_and_file_names() -> None:
    assert Period.parse("2026-11") == NOV
    assert NOV.label == "noviembre de 2026"
    with pytest.raises(ValueError, match="fiscal_book_period_invalid"):
        Period.parse("2026-13")
    name = annex_file_name("anulados", NOV, "production")
    assert name == "F07_anulados_2026-11.csv"
    assert len(name) <= 25
    assert annex_file_name("anexo1", NOV, "simulated") == "F07_anexo1_2026-11_SIMULADO.csv"


def test_contributor_rows_with_notes_and_invalidated_ccf() -> None:
    ccf = _sale("03", date(2026, 11, 5), 1, perception=D("1"))
    note = _sale("05", date(2026, 11, 6), 1, taxed=D("10"), vat=D("1.30"))
    debit = _sale("06", date(2026, 11, 7), 1, exempt=D("3"), taxed=D("2"), vat=D("0.26"))
    # Invalidado el 10/12, dentro del plazo: sale de noviembre y va a sus anulados.
    gone = _sale("03", date(2026, 11, 20), 2, invalidated_on=date(2026, 12, 10))
    month = build_month(NOV, "production", [gone, debit, note, ccf], [], [])

    assert [row.document.document_type for row in month.contributors] == ["03", "05", "06"]
    assert month.contributors[0].cells() == [
        "05/11/2026",
        "4",
        "03",
        "DTE03M001P001000000000000001",
        f"SEAL{1:036d}",
        "6C7EF1778C5241EFB073000000000001",
        "",
        "06140101011011",
        "Cafetería El Trigal, S.A. de C.V.",
        "0.00",
        "0.00",
        "100.00",
        "13.00",
        "0.00",
        "0.00",
        "113.00",
        "",
        "1",
        "3",
        "1",
    ]
    # La nota de crédito va en positivo en el anexo y resta en el libro.
    assert month.contributors[1].cells()[11] == "10.00"
    book = month.contributor_book
    assert [line.total for line in book] == [D("114.00"), D("-11.30"), D("5.26")]
    assert [row.document.control_number for row in month.annulled] == [gone.control_number]
    assert month.annulled[0].cells()[4:6] == ["03", "D"]
    assert [row.cells()[7] for row in month.perceptions] == ["1.00"]
    assert month.perceptions[0].cells()[-1] == "9"


def test_consumer_rows_group_by_day_with_negative_rows() -> None:
    first = _sale("01", date(2026, 11, 2), 1, taxed=D("11.30"), vat=D("1.30"))
    second = _sale(
        "01", date(2026, 11, 2), 2, taxed=D("22.60"), vat=D("2.60"), not_subject=D("3.50")
    )
    # Invalidada el mismo mes: no cuenta y va a anulados.
    same_month = _sale("01", date(2026, 11, 4), 3, invalidated_on=date(2026, 11, 8))
    # De octubre, invalidada en noviembre: fila negativa con su fecha original.
    october = _sale("01", date(2026, 10, 28), 4, taxed=D("5"), invalidated_on=date(2026, 11, 3))
    # Invalidada en diciembre: noviembre la cuenta.
    later = _sale("01", date(2026, 11, 30), 5, taxed=D("8"), invalidated_on=date(2026, 12, 2))
    returned = ReturnEvent(
        invoice=first,
        returned_on=date(2026, 11, 9),
        generation_code="RET",
        seal="SEAL",
        exempt=D("0"),
        not_subject=D("0"),
        taxed=D("2.26"),
    )
    month = build_month(
        NOV, "production", [later, october, same_month, second, first], [returned], []
    )

    rows = month.consumers
    assert [(row.day, row.documents, row.taxed) for row in rows] == [
        (date(2026, 11, 2), 2, D("33.90")),
        (date(2026, 11, 30), 1, D("8")),
        (date(2026, 10, 28), 1, D("-5")),
        (date(2026, 11, 2), 1, D("-2.26")),
    ]
    cells = rows[0].cells()
    assert cells[:9] == [
        "02/11/2026",
        "4",
        "01",
        "N/A",
        "N/A",
        "N/A",
        "N/A",
        "6C7EF1778C5241EFB073000000000001",
        "6C7EF1778C5241EFB073000000000002",
    ]
    assert cells[12:14] == ["3.50", "33.90"]
    assert cells[19:] == ["37.40", "1", "3", "2"]
    assert rows[2].cells()[19] == "-5.00"
    assert rows[3].note.startswith("Evento de retorno")
    annulled = {row.document.control_number for row in month.annulled}
    assert annulled == {same_month.control_number, october.control_number}

    book = month.consumer_book
    assert book[0].first_control == first.control_number
    assert book[0].point_of_sale == "M001P001"
    assert book[-1].note.startswith("Evento de retorno")
    summary = month.summary()
    assert summary.consumer_taxed_with_vat == D("34.64")
    assert summary.consumer_vat == D("3.99")


def test_purchase_rows_and_book() -> None:
    month = build_month(
        NOV,
        "production",
        [],
        [],
        [
            _purchase(),
            _purchase(
                purchase_code="CMP-2",
                document_class=1,
                number="145501",
                supplier=Party("Ferretería Juan Pérez", dui="05702891-8"),
                exempt=D("0"),
                taxed=D("20"),
                vat=D("2.60"),
            ),
            _purchase(purchase_code="CMP-3", issued_on=date(2026, 10, 30)),
        ],
    )
    assert len(month.purchases) == 2
    dte = next(row for row in month.purchases if row.document.purchase_code == "CMP-1")
    assert dte.cells() == [
        "03/11/2026",
        "4",
        "03",
        "A1B2C3D400001111222233334444555" + "5",
        "06142410901022",
        "Molinos de El Salvador, S.A. de C.V.",
        "3.34",
        "0.00",
        "0.00",
        "124.23",
        "0.00",
        "0.00",
        "0.00",
        "16.15",
        "127.57",
        "",
        "1",
        "1",
        "2",
        "5",
        "3",
    ]
    paper = next(row for row in month.purchases if row.document.purchase_code == "CMP-2")
    assert paper.cells()[3:5] == ["145501", ""]
    assert paper.cells()[15] == "057028918"
    book = month.purchase_book
    assert sum((line.vat for line in book), D("0")) == D("18.75")
    summary = month.summary()
    assert summary.credit == D("18.75")
    assert summary.balance == D("-18.75")


def test_csv_is_semicolon_separated_windows_1252_without_header() -> None:
    month = build_month(NOV, "production", [_sale("03", date(2026, 11, 5), 1)], [], [])
    content = annex_csv(month.contributors)
    text = content.decode("cp1252")
    assert text.endswith("\r\n")
    assert text.count("\r\n") == 1
    assert "Cafetería" in text
    assert content != text.encode("utf-8")
    assert len(text.strip().split(";")) == 20


def test_unclassified_documents_warn_and_use_zero() -> None:
    month = build_month(
        NOV,
        "simulated",
        [_sale("03", date(2026, 11, 5), 1, renta_operation=None, renta_income=None)],
        [],
        [],
    )
    assert month.simulated
    assert month.contributors[0].cells()[17:19] == ["0", "0"]
    assert month.warnings
    assert "sin clasificación de renta" in month.warnings[0]

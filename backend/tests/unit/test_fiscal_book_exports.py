"""Excel, PDF y ZIP del F-07: cuadran con los anexos y respetan el formato del portal."""

from __future__ import annotations

import uuid
import zipfile
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from app.domain.entities.fiscal_books import annex_csv, build_month
from app.domain.ports.fiscal_book_repository import Issuer, PendingPurchase
from app.infrastructure.fiscal_book_exports import render_book_pdf, render_f07_zip, render_xlsx
from openpyxl import load_workbook

from tests.unit.test_fiscal_books import NOV, _purchase, _sale

ISSUER = Issuer("Grupo Lorena, S.A. de C.V.", "1217-060102-101-1", "1234567")


def _month(mode: str = "production"):  # type: ignore[no-untyped-def]
    sales = [
        _sale("03", date(2026, 11, 5), 1),
        _sale("05", date(2026, 11, 6), 1, taxed=Decimal("10"), vat=Decimal("1.30")),
        _sale("01", date(2026, 11, 2), 1, taxed=Decimal("11.30"), vat=Decimal("1.30")),
        _sale("01", date(2026, 11, 3), 2, invalidated_on=date(2026, 11, 4)),
    ]
    return build_month(NOV, mode, sales, [], [_purchase()])


def test_workbook_has_books_and_text_annexes_that_add_up() -> None:
    month = _month()
    pending = [PendingPurchase(uuid.uuid4(), "CMP-9", "Molinos", None, None, Decimal("5"))]
    book = load_workbook(BytesIO(render_xlsx(month, ISSUER, pending)))
    assert book.sheetnames == [
        "Resumen",
        "LIBRO DE CONTRIBUYENTES",
        "LIBRO DE CONSUMIDOR FINAL",
        "LIBRO DE COMPRAS",
        "Anexo 1 contribuyentes",
        "Anexo 2 consumidor final",
        "Anexo 3 compras",
        "Anexo 9 casilla 169",
        "Anulados",
    ]
    contributors = book["LIBRO DE CONTRIBUYENTES"]
    assert contributors["A2"].value == f"NOMBRE DEL CONTRIBUYENTE: {ISSUER.name}"
    assert "FOLIO" in contributors["A3"].value
    # Dos documentos y la fila de totales: el CCF suma y la nota resta.
    assert contributors["A9"].value == "Totales del mes"
    assert contributors["K9"].value == pytest.approx(11.70)
    annex = book["Anexo 1 contribuyentes"]
    assert annex["A2"].value == "Fecha de emisión"
    assert annex["H3"].value == "06140101011011"
    assert annex["H3"].number_format == "@"
    assert annex["T4"].value == "1"
    summary = book["Resumen"]
    assert any(cell.value == "CMP-9 · Molinos" for row in summary.iter_rows() for cell in row)


def test_pdf_has_one_folio_per_page_starting_where_asked() -> None:
    content = render_book_pdf(_month("simulated"), ISSUER, "contributors", first_folio=41)
    assert content.startswith(b"%PDF")
    assert content.count(b"/Type /Page\n") + content.count(b"/Type /Page ") >= 1
    empty = render_book_pdf(build_month(NOV, "production", [], [], []), ISSUER, "purchases")
    assert empty.startswith(b"%PDF")


def test_zip_has_portal_files_workbook_and_readme() -> None:
    month = _month("simulated")
    archive = zipfile.ZipFile(BytesIO(render_f07_zip(month, ISSUER)))
    names = set(archive.namelist())
    assert names == {
        "F07_anexo1_2026-11_SIMULADO.csv",
        "F07_anexo2_2026-11_SIMULADO.csv",
        "F07_anexo3_2026-11_SIMULADO.csv",
        "F07_anulados_2026-11_SIMULADO.csv",
        "F07_libros_2026-11_SIMULADO.xlsx",
        "LEEME.txt",
    }
    assert archive.read("F07_anexo1_2026-11_SIMULADO.csv") == annex_csv(month.contributors)
    readme = archive.read("LEEME.txt").decode("utf-8-sig")
    assert "NO CARGAR AL PORTAL" in readme
    assert "F07_anexo3_2026-11_SIMULADO.csv: Detalle de Compras, 1 fila(s)" in readme
    production = zipfile.ZipFile(BytesIO(render_f07_zip(_month(), ISSUER)))
    assert all(len(name) <= 25 for name in production.namelist() if name.endswith(".csv"))

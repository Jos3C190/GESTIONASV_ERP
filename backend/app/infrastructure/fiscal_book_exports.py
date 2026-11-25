"""Excel, PDF y ZIP del F-07 a partir de un mes ya calculado.

- Excel: resumen, los tres libros con el encabezado de la plantilla (nombre, mes, año, folio, NIT y
  NRC) y totales, y los anexos con el encabezado del manual y todas las celdas en formato Texto
  (así no se pierden los ceros del NIT ni se convierten las fechas).
- PDF de cada libro: carta horizontal, folio correlativo desde el que se indique, totales del mes
  y espacio para la firma del contador (CT art. 141; reglamento arts. 82 y 88).
- ZIP: los CSV de carga del portal, el Excel y un LEEME.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from app.domain.entities.fiscal_books import (
    ANNEX_FILES,
    DOCUMENT_TYPE_LABELS,
    ZERO,
    FiscalMonth,
    MonthSummary,
    annex_csv,
    annex_file_name,
)
from app.domain.ports.fiscal_book_repository import Issuer, PendingPurchase

_TZ = ZoneInfo("America/El_Salvador")
MONEY_FORMAT = "#,##0.00;[Red]-#,##0.00"
HEADER_FILL = PatternFill("solid", fgColor="18181B")
GRID = colors.HexColor("#d4d4d8")
SHADE = colors.HexColor("#f4f4f5")
NOT_FOR_PORTAL = (
    "NO CARGAR AL PORTAL: documentos simulados o de pruebas, sin validez fiscal. Los archivos "
    "llevan el modo en el nombre y el portal los rechaza."
)

BOOKS = {
    "contributors": "LIBRO DE VENTAS A CONTRIBUYENTES",
    "consumers": "LIBRO DE VENTAS A CONSUMIDORES",
    "purchases": "LIBRO DE COMPRAS",
}


@dataclass(frozen=True)
class Column:
    title: str
    value: Callable[[Any], object]
    money: bool = False
    width: int = 14


def _day(value: Any) -> str:
    return str(value.strftime("%d/%m/%Y"))


def _type(code: str) -> str:
    return f"{code} {DOCUMENT_TYPE_LABELS.get(code, '')}".strip()


CONTRIBUTOR_COLUMNS = (
    Column("N°", lambda line: line.number, width=6),
    Column("Fecha de emisión", lambda line: _day(line.issued_on), width=15),
    Column("Tipo", lambda line: _type(line.document_type), width=14),
    Column("Código de generación", lambda line: line.generation_code, width=38),
    Column("Número de control", lambda line: line.control_number, width=32),
    Column("Nombre del cliente", lambda line: line.customer, width=32),
    Column("NRC del cliente", lambda line: line.registry, width=15),
    Column("Ventas exentas", lambda line: line.exempt, money=True),
    Column("Ventas no sujetas", lambda line: line.not_subject, money=True),
    Column("Ventas internas gravadas", lambda line: line.taxed, money=True),
    Column("Débito fiscal", lambda line: line.vat, money=True),
    Column("Ventas a cuenta de terceros", lambda line: ZERO, money=True),
    Column("Débito fiscal por cuenta de terceros", lambda line: ZERO, money=True),
    Column("IVA percibido", lambda line: line.perception, money=True),
    Column("Total", lambda line: line.total, money=True),
)
CONSUMER_COLUMNS = (
    Column("Día", lambda line: _day(line.day), width=15),
    Column("Documento emitido (del)", lambda line: line.first_control, width=32),
    Column("Documento emitido (al)", lambda line: line.last_control, width=32),
    Column("N° de caja o sistema", lambda line: line.point_of_sale, width=12),
    Column("Ventas exentas", lambda line: line.exempt, money=True),
    Column("Ventas no sujetas", lambda line: line.not_subject, money=True),
    Column("Ventas internas gravadas (IVA incluido)", lambda line: line.taxed, money=True),
    Column("Exportaciones", lambda line: line.exports, money=True),
    Column("Total de ventas diarias propias", lambda line: line.total, money=True),
    Column("Ventas a cuenta de terceros", lambda line: line.third_parties, money=True),
    Column("Observación", lambda line: line.note, width=34),
)
PURCHASE_COLUMNS = (
    Column("N°", lambda line: line.number, width=6),
    Column("Fecha de emisión", lambda line: _day(line.issued_on), width=15),
    Column("Tipo", lambda line: _type(line.document_type), width=14),
    Column("Número de documento", lambda line: line.document_number, width=34),
    Column("NRC del proveedor", lambda line: line.registry, width=15),
    Column("NIT o DUI del sujeto excluido", lambda line: line.excluded_subject_id, width=14),
    Column("Nombre del proveedor", lambda line: line.supplier, width=32),
    Column("Compras internas exentas", lambda line: line.internal_exempt, money=True),
    Column("Importaciones e internaciones exentas", lambda line: line.import_exempt, money=True),
    Column("Compras internas gravadas", lambda line: line.internal_taxed, money=True),
    Column("Importaciones e internaciones gravadas", lambda line: line.import_taxed, money=True),
    Column("Crédito fiscal", lambda line: line.vat, money=True),
    Column("Anticipo a cuenta IVA percibido", lambda line: line.perception, money=True),
    Column("Total de compras", lambda line: line.total, money=True),
    Column("Retención a terceros", lambda line: line.third_party_withholding, money=True),
    Column("Compras a sujetos excluidos", lambda line: line.excluded_subjects, money=True),
)
BOOK_COLUMNS: dict[str, Sequence[Column]] = {
    "contributors": CONTRIBUTOR_COLUMNS,
    "consumers": CONSUMER_COLUMNS,
    "purchases": PURCHASE_COLUMNS,
}

# Encabezados de los anexos, en el orden del manual F-07 V14 (letra y nombre).
ANNEX_HEADERS = {
    "anexo1": (
        "Fecha de emisión", "Clase de documento", "Tipo de documento", "Número de resolución",
        "Serie del documento", "Número de documento", "Número de control interno",
        "NIT o NRC del cliente", "Nombre, razón social o denominación", "Ventas exentas",
        "Ventas no sujetas", "Ventas gravadas locales", "Débito fiscal",
        "Ventas a cuenta de terceros no domiciliados",
        "Débito fiscal por ventas a cuenta de terceros", "Total de ventas", "DUI del cliente",
        "Tipo de operación (renta)", "Tipo de ingreso (renta)", "Número del anexo",
    ),
    "anexo2": (
        "Fecha de emisión", "Clase de documento", "Tipo de documento", "Número de resolución",
        "Serie del documento", "Control interno (del)", "Control interno (al)",
        "Número de documento (del)", "Número de documento (al)", "Máquina registradora",
        "Ventas exentas", "Ventas internas exentas no sujetas a proporcionalidad",
        "Ventas no sujetas", "Ventas gravadas locales", "Exportaciones dentro de Centroamérica",
        "Exportaciones fuera de Centroamérica", "Exportaciones de servicio",
        "Ventas a zonas francas y DPA (tasa cero)", "Ventas a cuenta de terceros no domiciliados",
        "Total de ventas", "Tipo de operación (renta)", "Tipo de ingreso (renta)",
        "Número del anexo",
    ),
    "anexo3": (
        "Fecha de emisión", "Clase de documento", "Tipo de documento", "Número de documento",
        "NIT o NRC del proveedor", "Nombre del proveedor", "Compras internas exentas",
        "Internaciones exentas y/o no sujetas", "Importaciones exentas y/o no sujetas",
        "Compras internas gravadas", "Internaciones gravadas de bienes",
        "Importaciones gravadas de bienes", "Importaciones gravadas de servicios",
        "Crédito fiscal", "Total de compras", "DUI del proveedor", "Tipo de operación (renta)",
        "Clasificación (renta)", "Sector (renta)", "Tipo de costo/gasto (renta)",
        "Número del anexo",
    ),
    "anexo9": (
        "NIT sujeto", "Fecha de emisión", "Tipo de documento", "Número de resolución",
        "Serie del documento", "Número de documento", "Monto sujeto",
        "Monto de la percepción 1% de IVA", "DUI sujeto", "Número del anexo",
    ),
    "anulados": (
        "Número de resolución", "Clase de documento", "Desde (preimpreso)", "Hasta (preimpreso)",
        "Tipo de documento", "Tipo de detalle", "Serie", "Desde", "Hasta",
        "Código de generación",
    ),
}  # fmt: skip

ANNEX_SHEETS = {
    "anexo1": "Anexo 1 contribuyentes",
    "anexo2": "Anexo 2 consumidor final",
    "anexo3": "Anexo 3 compras",
    "anexo9": "Anexo 9 casilla 169",
    "anulados": "Anulados",
}


def _lines(month: FiscalMonth, book: str) -> list[Any]:
    if book == "contributors":
        return list(month.contributor_book)
    if book == "consumers":
        return list(month.consumer_book)
    return list(month.purchase_book)


def _totals(columns: Sequence[Column], lines: Sequence[Any]) -> list[object]:
    values: list[object] = []
    for index, column in enumerate(columns):
        if column.money:
            values.append(sum((Decimal(str(column.value(line))) for line in lines), ZERO))
        else:
            values.append("Totales del mes" if index == 0 else "")
    return values


def _mode_label(month: FiscalMonth) -> str:
    return {"production": "Producción", "test": "Pruebas", "simulated": "Simulado"}[month.mode]


def _summary_rows(summary: MonthSummary) -> list[tuple[str, Decimal]]:
    return [
        ("Ventas gravadas a contribuyentes (sin IVA)", summary.contributor_taxed),
        ("Débito fiscal de contribuyentes", summary.contributor_vat),
        ("Ventas gravadas a consumidor final (IVA incluido)", summary.consumer_taxed_with_vat),
        ("Débito fiscal de consumidor final (13/113)", summary.consumer_vat),
        ("Ventas exentas", summary.exempt_sales),
        ("Ventas no sujetas", summary.not_subject_sales),
        ("Débito fiscal del mes", summary.debit),
        ("Compras gravadas", summary.purchase_taxed),
        ("Crédito fiscal del mes", summary.credit),
        ("Percepción del 1 % cobrada (casilla 169)", summary.perception_collected),
        ("Impuesto del mes antes de remanentes y retenciones", summary.balance),
    ]


# --- Excel --------------------------------------------------------------------------------------


def _header_row(sheet: Worksheet, row: int, titles: Sequence[str]) -> None:
    for column, title in enumerate(titles, start=1):
        cell = sheet.cell(row=row, column=column, value=title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    sheet.row_dimensions[row].height = 45


def _book_sheet(
    workbook: Workbook, title: str, book: str, month: FiscalMonth, issuer: Issuer
) -> None:
    sheet = workbook.create_sheet(title[:31])
    columns = BOOK_COLUMNS[book]
    sheet["A1"] = BOOKS[book]
    sheet["A1"].font = Font(bold=True, size=13)
    sheet["A2"] = f"NOMBRE DEL CONTRIBUYENTE: {issuer.name}"
    sheet["A3"] = (
        f"MES: {month.period.label.split(' de ')[0].upper()}   AÑO: {month.period.year}   FOLIO N°:"
    )
    sheet["A4"] = f"NIT: {issuer.nit or 'No informado'}   NRC: {issuer.nrc or 'No informado'}"
    if month.simulated:
        sheet["A5"] = NOT_FOR_PORTAL
        sheet["A5"].font = Font(bold=True, color="B91C1C")
    _header_row(sheet, 6, [column.title for column in columns])
    lines = _lines(month, book)
    for row_index, line in enumerate(lines, start=7):
        for col_index, column in enumerate(columns, start=1):
            value = column.value(line)
            cell = sheet.cell(row=row_index, column=col_index, value=value)
            if column.money:
                cell.number_format = MONEY_FORMAT
    total_row = 7 + len(lines)
    for col_index, value in enumerate(_totals(columns, lines), start=1):
        cell = sheet.cell(row=total_row, column=col_index, value=value)
        cell.font = Font(bold=True)
        if columns[col_index - 1].money:
            cell.number_format = MONEY_FORMAT
    sheet.cell(row=total_row + 3, column=2, value="Nombre y firma del contador")
    for col_index, column in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(col_index)].width = column.width
    sheet.freeze_panes = "A7"
    if lines:
        sheet.auto_filter.ref = f"A6:{get_column_letter(len(columns))}{6 + len(lines)}"


def _annex_sheet(workbook: Workbook, key: str, month: FiscalMonth) -> None:
    sheet = workbook.create_sheet(ANNEX_SHEETS[key])
    sheet["A1"] = (
        f"{ANNEX_FILES[key][0]} · {annex_file_name(key, month.period, month.mode)} · "
        "datos desde la fila 3, celdas en formato Texto"
    )
    if month.simulated:
        sheet["A1"] = f"{sheet['A1'].value} · {NOT_FOR_PORTAL}"
    headers = ANNEX_HEADERS[key]
    _header_row(sheet, 2, headers)
    for row_index, row in enumerate(getattr(month, ANNEX_FILES[key][1]), start=3):
        for col_index, value in enumerate(row.cells(), start=1):
            cell = sheet.cell(row=row_index, column=col_index, value=value)
            cell.number_format = "@"
    for col_index in range(1, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(col_index)].width = 16


def render_xlsx(
    month: FiscalMonth, issuer: Issuer, pending: Sequence[PendingPurchase] = ()
) -> bytes:
    workbook = Workbook()
    summary_sheet = workbook.active
    assert summary_sheet is not None
    summary_sheet.title = "Resumen"
    summary_sheet["A1"] = f"Libros de IVA y anexos del F-07 · {month.period.label}"
    summary_sheet["A1"].font = Font(bold=True, size=13)
    summary_sheet["A2"] = f"{issuer.name} · NIT {issuer.nit or '—'} · NRC {issuer.nrc or '—'}"
    summary_sheet["A3"] = f"Modo: {_mode_label(month)}"
    if month.simulated:
        summary_sheet["A4"] = NOT_FOR_PORTAL
        summary_sheet["A4"].font = Font(bold=True, color="B91C1C")
    row = 6
    for label, value in _summary_rows(month.summary()):
        summary_sheet.cell(row=row, column=1, value=label)
        cell = summary_sheet.cell(row=row, column=2, value=value)
        cell.number_format = MONEY_FORMAT
        row += 1
    row += 1
    for warning in month.warnings:
        summary_sheet.cell(row=row, column=1, value=f"Aviso: {warning}")
        row += 1
    if pending:
        row += 1
        summary_sheet.cell(row=row, column=1, value="Compras sin documento del proveedor")
        summary_sheet.cell(row=row, column=1).font = Font(bold=True)
        for item in pending:
            row += 1
            summary_sheet.cell(row=row, column=1, value=f"{item.code} · {item.supplier}")
            summary_sheet.cell(row=row, column=2, value=item.total).number_format = MONEY_FORMAT
    summary_sheet.column_dimensions["A"].width = 60
    summary_sheet.column_dimensions["B"].width = 16

    _book_sheet(workbook, "LIBRO DE CONTRIBUYENTES", "contributors", month, issuer)
    _book_sheet(workbook, "LIBRO DE CONSUMIDOR FINAL", "consumers", month, issuer)
    _book_sheet(workbook, "LIBRO DE COMPRAS", "purchases", month, issuer)
    for key in ANNEX_FILES:
        _annex_sheet(workbook, key, month)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


# --- PDF ----------------------------------------------------------------------------------------


def _pdf_cell(value: object, style: ParagraphStyle) -> Paragraph:
    text = f"{value:,.2f}" if isinstance(value, Decimal) else str(value)
    return Paragraph(escape(text), style)


def render_book_pdf(month: FiscalMonth, issuer: Issuer, book: str, first_folio: int = 1) -> bytes:
    columns = BOOK_COLUMNS[book]
    lines = _lines(month, book)
    output = BytesIO()
    page = landscape(LETTER)
    document = SimpleDocTemplate(
        output,
        pagesize=page,
        leftMargin=24,
        rightMargin=24,
        topMargin=84,
        bottomMargin=40,
        title=f"{BOOKS[book].title()} · {month.period.label}",
        author=issuer.name,
    )
    text = ParagraphStyle("Cell", fontName="Helvetica", fontSize=6.3, leading=7.6)
    number = ParagraphStyle("Number", parent=text, alignment=2)
    head = ParagraphStyle("Head", parent=text, fontName="Helvetica-Bold", textColor=colors.white)
    widths = [column.width for column in columns]
    scale = (page[0] - 48) / sum(widths)
    data: list[list[Paragraph]] = [[_pdf_cell(column.title, head) for column in columns]]
    for line in lines:
        data.append(
            [_pdf_cell(column.value(line), number if column.money else text) for column in columns]
        )
    totals = _totals(columns, lines)
    bold = ParagraphStyle("Bold", parent=number, fontName="Helvetica-Bold")
    data.append(
        [
            _pdf_cell(value, bold if columns[index].money else text)
            for index, value in enumerate(totals)
        ]
    )
    table = LongTable(data, colWidths=[width * scale for width in widths], repeatRows=1)
    label_span = next(index for index, column in enumerate(columns) if column.money) - 1
    table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, -1), (label_span, -1)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18181b")),
                ("GRID", (0, 0), (-1, -1), 0.3, GRID),
                ("BACKGROUND", (0, -1), (-1, -1), SHADE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    signature = ParagraphStyle("Signature", fontName="Helvetica", fontSize=8, leading=10)
    story = [
        table,
        Spacer(1, 48),
        Paragraph("______________________________________", signature),
        Paragraph("Nombre y firma del contador", signature),
    ]
    if not lines:
        story.insert(0, Paragraph("Sin operaciones en el mes.", signature))
    month_name = month.period.label.split(" de ")[0].upper()

    def header(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        width, height = page
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(24, height - 30, BOOKS[book])
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(24, height - 44, f"NOMBRE DEL CONTRIBUYENTE: {issuer.name}")
        canvas.drawString(
            24,
            height - 56,
            f"NIT: {issuer.nit or 'No informado'}     NRC: {issuer.nrc or 'No informado'}     "
            f"MES: {month_name}     AÑO: {month.period.year}",
        )
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(width - 24, height - 30, f"FOLIO N° {first_folio + doc.page - 1}")
        if month.simulated:
            canvas.setFillColor(colors.HexColor("#b91c1c"))
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(24, height - 68, NOT_FOR_PORTAL)
        canvas.setFillColor(colors.HexColor("#52525b"))
        canvas.setFont("Helvetica", 7)
        generated = datetime.now(_TZ).strftime("%d/%m/%Y %H:%M")
        canvas.drawString(24, 20, f"Generado el {generated} · GestionaSV")
        canvas.restoreState()

    document.build(story, onFirstPage=header, onLaterPages=header)
    return output.getvalue()


# --- ZIP del F-07 -------------------------------------------------------------------------------


def _readme(month: FiscalMonth, issuer: Issuer) -> str:
    lines = [
        f"ANEXOS DE LA DECLARACIÓN DE IVA (F-07) - {month.period.label.upper()} - {issuer.name}",
        "",
    ]
    if month.simulated:
        lines += [f"*** {NOT_FOR_PORTAL} ***", ""]
    lines += [
        "Formato del manual de carga de anexos F-07 V14 (DGII, enero 2025): CSV separado por punto",
        "y coma, sin encabezados, montos con dos decimales, en Windows-1252 como lo guarda Excel.",
        "No abra los CSV con doble clic para editarlos: Excel quita los ceros del NIT y del DUI.",
        "Para revisar o corregir use el Excel del mes, que trae las celdas en formato Texto.",
        "",
        "ARCHIVOS Y DÓNDE SE CARGAN (Declaración de IVA > Subir Detalle de Ventas y Compras)",
    ]
    for key, (title, attribute) in ANNEX_FILES.items():
        rows = getattr(month, attribute)
        if rows:
            lines.append(
                f"  {annex_file_name(key, month.period, month.mode)}: {title}, {len(rows)} fila(s)"
            )
    lines += [
        "",
        "REGLAS",
        "  - Las notas de crédito van en el anexo 1 con su tipo (05) y en positivo: el portal las resta.",
        "  - Una factura invalidada en un mes posterior al de su emisión se resta en el anexo 2 del mes",
        "    de la invalidación, con su fecha original; igual un evento de retorno.",
        "  - Un crédito fiscal o una nota invalidados salen del anexo 1 de su mes y van a anulados.",
    ]
    if month.warnings:
        lines += ["", "AVISOS"] + [f"  - {warning}" for warning in month.warnings]
    return "\r\n".join(lines) + "\r\n"


def render_f07_zip(
    month: FiscalMonth, issuer: Issuer, pending: Sequence[PendingPurchase] = ()
) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, (_title, attribute) in ANNEX_FILES.items():
            rows = getattr(month, attribute)
            if rows:
                archive.writestr(annex_file_name(key, month.period, month.mode), annex_csv(rows))
        suffix = "" if month.mode == "production" else f"_{_mode_label(month).upper()}"
        archive.writestr(
            f"F07_libros_{month.period.key}{suffix}.xlsx", render_xlsx(month, issuer, pending)
        )
        archive.writestr("LEEME.txt", _readme(month, issuer).encode("utf-8-sig"))
    return output.getvalue()

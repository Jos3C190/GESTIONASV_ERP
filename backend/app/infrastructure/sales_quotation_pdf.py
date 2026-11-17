"""Versión imprimible de la cotización de venta (bloque V2d).

Muestra lo que el cliente necesita para decidir: precios, descuentos, impuestos, total y
vigencia. Nunca muestra el costo ni el margen.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.application.sales_quotations.use_cases import DocumentHeader, QuotationView

DOCUMENT_NAMES = {"01": "Factura", "03": "Comprobante de crédito fiscal"}
ID_NAMES = {"36": "NIT", "13": "DUI", "02": "Carné de residente", "03": "Pasaporte", "37": "Doc."}
GRID = colors.HexColor("#d4d4d8")
MUTED = colors.HexColor("#52525b")
SHADE = colors.HexColor("#f4f4f5")


def money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01')):,.2f}"


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _number(value: Decimal) -> str:
    text = f"{value.normalize():f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _clean(value: object) -> str:
    return escape(re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(value))).replace("\n", "<br/>")


def render_quotation_pdf(view: QuotationView, header: DocumentHeader) -> bytes:
    quotation = view.quotation
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=LETTER,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"Cotización {quotation.code}",
        author=header.commercial_name or header.company_name,
    )
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=8.5, leading=11)
    small = ParagraphStyle("Small", parent=body, fontSize=7.5, textColor=MUTED)
    right = ParagraphStyle("Right", parent=body, alignment=TA_RIGHT)
    strong = ParagraphStyle("Strong", parent=body, fontName="Helvetica-Bold")
    strong_right = ParagraphStyle("StrongRight", parent=strong, alignment=TA_RIGHT)
    title = ParagraphStyle("Title", parent=body, fontName="Helvetica-Bold", fontSize=15, leading=19)

    def p(value: object, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(_clean(value), style)

    issuer = [
        p(header.commercial_name or header.company_name, title),
        p(header.company_name, small) if header.commercial_name else Spacer(1, 0),
        p(
            " · ".join(
                part
                for part in (
                    f"NIT {header.nit}" if header.nit else "",
                    f"NRC {header.nrc}" if header.nrc else "",
                    header.branch_name or "",
                )
                if part
            ),
            small,
        ),
        p(" · ".join(part for part in (header.phone, header.email) if part), small),
    ]
    document = [
        p("COTIZACIÓN", strong_right),
        p(quotation.code, right),
        p(f"Fecha: {_day(quotation.quotation_date)}", right),
        p(f"Válida hasta: {_day(quotation.valid_until)}", right),
    ]
    top = Table([[issuer, document]], colWidths=[doc.width * 0.62, doc.width * 0.38])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    customer = view.customer
    draft = customer.draft
    ids = " · ".join(
        part
        for part in (
            f"{ID_NAMES.get(draft.document_type.value, '') if draft.document_type else ''} "
            f"{draft.document_number or ''}".strip(),
            f"NRC {draft.nrc}" if draft.nrc else "",
        )
        if part
    )
    client = Table(
        [
            [p("Cliente", small), p("Documento a emitir", small)],
            [
                [p(f"{customer.code} — {draft.name}", strong), p(ids, small)],
                p(DOCUMENT_NAMES.get(quotation.document_type, quotation.document_type)),
            ],
        ],
        colWidths=[doc.width * 0.62, doc.width * 0.38],
    )
    client.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), SHADE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    rows: list[list[object]] = [
        [
            p("#", strong),
            p("Producto", strong),
            p("Cantidad", strong_right),
            p("Precio", strong_right),
            p("Desc.", strong_right),
            p("Total", strong_right),
        ]
    ]
    for number, line in enumerate(quotation.lines, start=1):
        treatment = {"exempt": " (exento)", "not_subject": " (no sujeto)"}.get(
            line.tax_treatment, ""
        )
        rows.append(
            [
                p(number),
                [
                    p(f"{line.identity.product_name}{treatment}"),
                    p(line.identity.product_sku, small),
                ],
                p(f"{_number(line.quantity)} {line.identity.unit_name}", right),
                p(money(line.document_unit_price), right),
                p(f"{line.discount_percent:.2f} %" if line.discount_percent else "—", right),
                p(money(line.line_total), right),
            ]
        )
    widths = [0.05, 0.43, 0.15, 0.12, 0.10, 0.15]
    items = LongTable(rows, colWidths=[doc.width * w for w in widths], repeatRows=1)
    items.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, MUTED),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    totals = quotation.totals
    summary: list[tuple[str, Decimal]] = [("Ventas gravadas", totals.total_taxed)]
    if totals.total_exempt:
        summary.append(("Ventas exentas", totals.total_exempt))
    if totals.total_not_subject:
        summary.append(("Ventas no sujetas", totals.total_not_subject))
    if totals.total_discount:
        summary.append(("Descuentos aplicados", totals.total_discount))
    if quotation.document_type == "03":
        summary.append(("Subtotal", totals.subtotal))
        summary.append(("IVA 13 %", totals.vat))
    else:
        summary.append(("IVA incluido", totals.vat))
    if totals.vat_perceived:
        summary.append(("IVA percibido 1 %", totals.vat_perceived))
    if totals.vat_withheld:
        summary.append(("IVA retenido 1 %", -totals.vat_withheld))
    figures = [[p(label, right), p(money(value), right)] for label, value in summary]
    figures.append([p("Total", strong_right), p(money(totals.total), strong_right)])
    resume = Table(figures, colWidths=[doc.width * 0.25, doc.width * 0.15], hAlign="RIGHT")
    resume.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.75, MUTED)]))

    content: list[object] = [
        top,
        Spacer(1, 12),
        client,
        Spacer(1, 12),
        items,
        Spacer(1, 8),
        resume,
        Spacer(1, 6),
        p(f"Son: {totals.total_in_words}", small),
    ]
    if quotation.notes:
        content += [Spacer(1, 10), p("Observaciones", strong), p(quotation.notes)]
    content += [
        Spacer(1, 14),
        p(
            f"Precios en dólares de los Estados Unidos. Esta cotización es válida hasta el "
            f"{_day(quotation.valid_until)} y no es un documento tributario.",
            small,
        ),
    ]
    doc.build(content)
    return output.getvalue()

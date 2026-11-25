"""Recibo de cobro imprimible (bloque V5a). No es un documento tributario."""

from __future__ import annotations

from decimal import Decimal
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.domain.entities.sales_receivables import ReceiptStatus, receipt_code
from app.domain.ports.sales_receivable_repository import CustomerRef, Issuer, Receipt

METHODS = {
    "cash": "Efectivo",
    "card": "Tarjeta",
    "transfer": "Transferencia",
    "check": "Cheque",
    "other": "Otro",
}
GRID = colors.HexColor("#d4d4d8")
SHADE = colors.HexColor("#f4f4f5")


def _money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01')):,.2f}"


def render_receipt_pdf(receipt: Receipt, customer: CustomerRef, issuer: Issuer) -> bytes:
    output = BytesIO()
    code = receipt_code(receipt.number)
    document = SimpleDocTemplate(
        output,
        pagesize=LETTER,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
        title=f"Recibo de cobro {code}",
        author=issuer.name,
    )
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor=colors.HexColor("#52525b"))
    title = ParagraphStyle("Title", parent=body, fontName="Helvetica-Bold", fontSize=14, leading=18)
    right = ParagraphStyle("Right", parent=body, alignment=TA_RIGHT)

    def p(text: str, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(text), style)

    def table(rows: list[list[Paragraph]], widths: list[float]) -> Table:
        built = Table(rows, colWidths=widths)
        built.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), SHADE),
                    ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return built

    story = [
        p(issuer.name, title),
        p(f"NIT {issuer.nit or 'No informado'} · NRC {issuer.nrc or 'No informado'}", small),
        Spacer(1, 12),
        p(f"RECIBO DE COBRO {code}", title),
        p(f"Fecha: {receipt.received_on:%d/%m/%Y}"),
        p(f"Cliente: {customer.name} ({customer.code})"),
    ]
    if receipt.status is ReceiptStatus.ANNULLED:
        story.append(
            Paragraph(
                f"<font color='#b91c1c'><b>ANULADO</b>: {escape(receipt.annul_reason or '')}</font>",
                body,
            )
        )
    story += [
        Spacer(1, 10),
        p("Formas de pago", ParagraphStyle("H", parent=body, fontName="Helvetica-Bold")),
        table(
            [[p("Forma"), p("Referencia"), p("Monto", right)]]
            + [
                [
                    p(METHODS[line.method.value]),
                    p(line.reference or "—"),
                    p(_money(line.amount), right),
                ]
                for line in receipt.payments
            ]
            + [[p(""), p("Total cobrado"), p(_money(receipt.total), right)]],
            [140, 230, 160],
        ),
        Spacer(1, 10),
        p("Aplicado a", ParagraphStyle("H2", parent=body, fontName="Helvetica-Bold")),
    ]
    if receipt.applications:
        story.append(
            table(
                [[p("Documento"), p("Fecha"), p("Monto", right)]]
                + [
                    [
                        p(
                            item.control_number
                            + (" (invalidado)" if item.document_invalidated else "")
                        ),
                        p(f"{item.applied_on:%d/%m/%Y}"),
                        p(_money(item.amount), right),
                    ]
                    for item in receipt.applications
                ],
                [270, 100, 160],
            )
        )
    else:
        story.append(p("Sin aplicar a documentos."))
    story += [
        Spacer(1, 8),
        p(f"Saldo a favor del cliente: {_money(receipt.unapplied)}"),
    ]
    if receipt.notes:
        story.append(p(f"Notas: {receipt.notes}"))
    story += [
        Spacer(1, 40),
        Table(
            [
                [p("______________________________"), p("______________________________")],
                [p("Recibido por", small), p("Cliente", small)],
            ],
            colWidths=[265, 265],
        ),
        Spacer(1, 12),
        p(
            "Este recibo respalda un cobro y no es un documento tributario: el IVA se documentó "
            "en la factura o el crédito fiscal que se paga.",
            small,
        ),
    ]

    def footer(canvas: Canvas, _doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#52525b"))
        canvas.drawString(40, 24, f"{code} · GestionaSV")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

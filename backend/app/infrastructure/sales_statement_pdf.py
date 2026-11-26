"""Estado de cuenta del cliente en PDF, para imprimir o enviar por correo (bloque V5b)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.application.sales_receivables.use_cases import Account
from app.domain.entities.sales_receivables import ZERO
from app.domain.ports.sales_receivable_repository import Issuer

DOCUMENTS = {"01": "Factura", "03": "Crédito fiscal", "06": "Nota de débito"}
GRID = colors.HexColor("#d4d4d8")
SHADE = colors.HexColor("#f4f4f5")


def _money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01')):,.2f}"


def render_statement_pdf(account: Account, issuer: Issuer, today: date) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=LETTER,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"Estado de cuenta {account.customer.name}",
        author=issuer.name,
    )
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=8.5, leading=11)
    small = ParagraphStyle("Small", parent=body, fontSize=7.5, textColor=colors.HexColor("#52525b"))
    title = ParagraphStyle("Title", parent=body, fontName="Helvetica-Bold", fontSize=14, leading=18)
    right = ParagraphStyle("Right", parent=body, alignment=TA_RIGHT)
    bold = ParagraphStyle("Bold", parent=right, fontName="Helvetica-Bold")

    def p(text: str, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(text), style)

    open_documents = [item for item in account.documents if item.receivable.balance > ZERO]
    rows = [
        [
            p("Documento"),
            p("Emisión"),
            p("Vence"),
            p("Total", right),
            p("Pagado", right),
            p("Saldo", right),
        ]
    ]
    for item in open_documents:
        receivable = item.receivable
        rows.append(
            [
                p(
                    f"{DOCUMENTS.get(receivable.document_type, receivable.document_type)} "
                    f"{receivable.control_number}"
                ),
                p(f"{receivable.issued_on:%d/%m/%Y}"),
                p(
                    f"{receivable.due_on:%d/%m/%Y}"
                    + (" (vencido)" if receivable.overdue(today) else "")
                ),
                p(_money(receivable.payable - receivable.credited), right),
                p(_money(receivable.applied), right),
                p(_money(receivable.balance), right),
            ]
        )
    rows.append([p(""), p(""), p(""), p(""), p("Saldo", bold), p(_money(account.balance), bold)])
    table = Table(rows, colWidths=[200, 60, 85, 65, 65, 65], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SHADE),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story = [
        p(issuer.name, title),
        p(f"NIT {issuer.nit or 'No informado'} · NRC {issuer.nrc or 'No informado'}", small),
        Spacer(1, 10),
        p("ESTADO DE CUENTA", title),
        p(f"Cliente: {account.customer.name} ({account.customer.code})"),
        p(f"Fecha: {today:%d/%m/%Y} · Crédito a {account.customer.credit_days} días"),
        Spacer(1, 8),
        p(
            f"Saldo: {_money(account.balance)} · Vencido: {_money(account.overdue)} · "
            f"Saldo a favor: {_money(account.credit)}"
        ),
        Spacer(1, 8),
        table if open_documents else p("No tiene documentos pendientes de pago."),
        Spacer(1, 14),
        p(
            "Si ya realizó el pago, por favor ignore este estado de cuenta o envíenos el "
            "comprobante para aplicarlo.",
            small,
        ),
    ]
    document.build(story)
    return output.getvalue()

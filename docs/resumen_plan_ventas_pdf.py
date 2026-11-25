"""Resumen del plan del área de Ventas y Facturación electrónica de GestionaSV.

Versión breve del plan detallado (``plan_area_ventas_pdf.py``), pensada para presentar al docente:
qué módulos y funciones se agregan al ERP, qué ya está hecho y qué falta, con diagramas de la
arquitectura, del flujo, del ciclo de vida del documento fiscal y del modelo de datos.

Uso:  py -3 docs/resumen_plan_ventas_pdf.py  →  docs/resumen-plan-ventas.pdf
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Body", F + "calibri.ttf"))
pdfmetrics.registerFont(TTFont("Body-B", F + "calibrib.ttf"))
pdfmetrics.registerFont(TTFont("Body-I", F + "calibrii.ttf"))
pdfmetrics.registerFont(TTFont("Body-BI", F + "calibriz.ttf"))
pdfmetrics.registerFontFamily(
    "Body", normal="Body", bold="Body-B", italic="Body-I", boldItalic="Body-BI"
)
pdfmetrics.registerFont(TTFont("Head", F + "georgia.ttf"))
pdfmetrics.registerFont(TTFont("Head-B", F + "georgiab.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "consola.ttf"))

NAVY = colors.HexColor("#17324D")
ACCENT = colors.HexColor("#A8672A")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#5B6770")
LINE = colors.HexColor("#C9D1D9")
SOFT = colors.HexColor("#F2F5F8")
WHITE = colors.white
DONE = colors.HexColor("#2F7D4F")
DONE_BG = colors.HexColor("#E6F2EA")
DOING = colors.HexColor("#A8672A")
DOING_BG = colors.HexColor("#FBF0E2")
TODO = colors.HexColor("#5B6770")
TODO_BG = colors.HexColor("#EEF1F4")
BAD = colors.HexColor("#B4443A")
BAD_BG = colors.HexColor("#F8E7E5")
BLUE = colors.HexColor("#2D6A9F")
BLUE_BG = colors.HexColor("#E5EEF7")

FECHA = "24/11/2026"
WIDTH = letter[0] - 4 * cm

S = {
    "title": ParagraphStyle("title", fontName="Head-B", fontSize=21, leading=26, textColor=NAVY),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=11.5, leading=15, textColor=MUTED),
    "h1": ParagraphStyle(
        "h1", fontName="Head-B", fontSize=14, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=5
    ),
    "h2": ParagraphStyle(
        "h2", fontName="Body-B", fontSize=11.2, leading=14, textColor=NAVY, spaceBefore=7, spaceAfter=2
    ),
    "body": ParagraphStyle("body", fontName="Body", fontSize=10.5, leading=14.2, textColor=INK, spaceAfter=5),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=9.3, leading=12, textColor=INK),
    "head": ParagraphStyle("head", fontName="Body-B", fontSize=9.3, leading=12, textColor=WHITE),
    "bullet": ParagraphStyle(
        "bullet", fontName="Body", fontSize=10.2, leading=13.4, textColor=INK, leftIndent=12,
        bulletIndent=2, spaceAfter=1.5,
    ),
    "caption": ParagraphStyle(
        "caption", fontName="Body-I", fontSize=8.8, leading=11, textColor=MUTED, alignment=TA_CENTER,
        spaceBefore=3, spaceAfter=6,
    ),
    "note": ParagraphStyle("note", fontName="Body-I", fontSize=9, leading=12, textColor=MUTED),
    "badge": ParagraphStyle("badge", fontName="Body-B", fontSize=8.6, leading=10.5, alignment=TA_CENTER),
    "done_label": ParagraphStyle(
        "done_label", fontName="Body-B", fontSize=9.6, leading=12.5, textColor=DONE, spaceAfter=1
    ),
    "todo_label": ParagraphStyle(
        "todo_label", fontName="Body-B", fontSize=9.6, leading=12.5, textColor=MUTED, spaceAfter=1
    ),
}

ESTADOS = {
    "hecho": ("Hecho", DONE, DONE_BG),
    "parcial": ("En curso", DOING, DOING_BG),
    "pendiente": ("Por hacer", TODO, TODO_BG),
}


# --- utilidades de texto -------------------------------------------------------------------------


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(item, S["bullet"], bulletText="•") for item in items]


def badge(estado: str) -> Paragraph:
    label, fg, _bg = ESTADOS[estado]
    return Paragraph(f'<font color="{fg.hexval()}">{label}</font>', S["badge"])


def table(headers: list[str], rows: list[list], widths: list[float], estados: list[str] | None = None) -> Table:
    data = [[P(h, "head") for h in headers]]
    for row in rows:
        data.append([cell if isinstance(cell, Flowable) else P(cell, "cell") for cell in row])
    t = Table(data, colWidths=[w * WIDTH for w in widths], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    if estados:
        for i, estado in enumerate(estados, start=1):
            style.append(("BACKGROUND", (-1, i), (-1, i), ESTADOS[estado][2]))
            style.append(("VALIGN", (-1, i), (-1, i), "MIDDLE"))
    t.setStyle(TableStyle(style))
    return t


def caption(text: str) -> Paragraph:
    return P(text, "caption")


# --- dibujo ---------------------------------------------------------------------------------------


class Diagram(Flowable):
    """Lienzo del ancho del texto; ``paint`` dibuja con el origen abajo a la izquierda."""

    def __init__(self, height: float, paint: Callable[[Diagram], None]) -> None:
        super().__init__()
        self.width = WIDTH
        self.height = height
        self._paint = paint

    def wrap(self, *_args: object) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        self._paint(self)

    # primitivas
    def box(
        self, x: float, y: float, w: float, h: float, title: str, sub: str = "",
        fg: colors.Color = NAVY, bg: colors.Color = BLUE_BG, size: float = 8.8,
    ) -> tuple[float, float, float, float]:
        c = self.canv
        c.setFillColor(bg)
        c.setStrokeColor(fg)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        lines = [(t, "Body-B", size) for t in title.split("\n")]
        lines += [(t, "Body", size - 1.3) for t in sub.split("\n") if sub]
        total = sum(s + 2 for _t, _f, s in lines)
        cy = y + h / 2 + total / 2 - size + 1
        for text, font, fsize in lines:
            c.setFillColor(INK if font == "Body-B" else MUTED)
            c.setFont(font, fsize)
            c.drawCentredString(x + w / 2, cy, text)
            cy -= fsize + 2
        return (x, y, w, h)

    def arrow(
        self, x1: float, y1: float, x2: float, y2: float, label: str = "", color: colors.Color = MUTED,
        dashed: bool = False, label_dx: float = 0, label_dy: float = 3,
    ) -> None:
        c = self.canv
        c.setStrokeColor(color)
        c.setFillColor(color)
        c.setLineWidth(0.9)
        if dashed:
            c.setDash(2.5, 2)
        c.line(x1, y1, x2, y2)
        c.setDash()
        ang = math.atan2(y2 - y1, x2 - x1)
        size = 4.2
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2 - size * math.cos(ang - 0.42), y2 - size * math.sin(ang - 0.42))
        p.lineTo(x2 - size * math.cos(ang + 0.42), y2 - size * math.sin(ang + 0.42))
        p.close()
        c.drawPath(p, stroke=0, fill=1)
        if label:
            c.setFont("Body-I", 7.4)
            c.setFillColor(MUTED)
            c.drawCentredString((x1 + x2) / 2 + label_dx, (y1 + y2) / 2 + label_dy, label)


def legend(d: Diagram, x: float, y: float, items: list[tuple[str, colors.Color, colors.Color]]) -> None:
    c = d.canv
    c.setFont("Body", 8.2)
    for label, fg, bg in items:
        c.setFillColor(bg)
        c.setStrokeColor(fg)
        c.rect(x, y, 9, 9, stroke=1, fill=1)
        c.setFillColor(INK)
        c.drawString(x + 13, y + 1, label)
        x += 13 + pdfmetrics.stringWidth(label, "Body", 8.2) + 16


# 1. Franja de avance de los ocho bloques
BLOQUES = [
    ("V1", "Base\nfiscal", "hecho"),
    ("V2", "Precios e\nimpuestos", "hecho"),
    ("V3", "Factura\nelectrónica", "hecho"),
    ("V4", "Robustez\ndel DTE", "parcial"),
    ("V5", "Pedidos\ny cobros", "pendiente"),
    ("V7", "Documentos\nde proveedor", "pendiente"),
    ("V8", "Libros de\nIVA y F-07", "pendiente"),
    ("V9", "Análisis y\naceptación", "pendiente"),
]


def paint_avance(d: Diagram) -> None:
    c = d.canv
    n = len(BLOQUES)
    gap = 4
    w = (d.width - gap * (n - 1)) / n
    h = 1.55 * cm
    y = d.height - h
    for i, (code, name, estado) in enumerate(BLOQUES):
        _label, fg, bg = ESTADOS[estado]
        x = i * (w + gap)
        c.setFillColor(bg)
        c.setStrokeColor(fg)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 4, stroke=1, fill=1)
        c.setFillColor(fg)
        c.setFont("Body-B", 10.5)
        c.drawCentredString(x + w / 2, y + h - 12, code)
        c.setFillColor(INK)
        c.setFont("Body", 7.6)
        for j, line in enumerate(name.split("\n")):
            c.drawCentredString(x + w / 2, y + h - 23 - j * 9, line)
    legend(d, 0, 2, [ESTADOS[e] for e in ("hecho", "parcial", "pendiente")])


# 2. Arquitectura
def paint_arquitectura(d: Diagram) -> None:
    cols = 5
    gap = 12
    w = (d.width - gap * (cols - 1)) / cols
    h = 1.5 * cm
    xs = [i * (w + gap) for i in range(cols)]
    r1, r2, r3 = d.height - h, d.height - 2 * h - 22, d.height - 3 * h - 44

    nav = d.box(xs[0], r1, w, h, "Navegador", "interfaz SvelteKit", NAVY, BLUE_BG)
    api = d.box(xs[1], r1, w, h, "API FastAPI", "reglas, permisos\ny auditoría", NAVY, BLUE_BG)
    cola = d.box(xs[2], r1, w, h, "Cola Redis", "tareas en segundo\nplano", NAVY, BLUE_BG)
    wrk = d.box(xs[3], r1, w, h, "Trabajador DTE", "emite, reintenta\ny concilia", NAVY, BLUE_BG)
    mail = d.box(xs[4], r1, w, h, "Correo SMTP", "de cada empresa,\nal cliente", NAVY, SOFT)

    pg = d.box(xs[1], r2, w, h, "PostgreSQL", "datos aislados\npor empresa", NAVY, SOFT)
    sto = d.box(xs[2], r2, w, h, "Almacenamiento", "JSON y PDF de\ncada documento", NAVY, SOFT)
    svc = d.box(xs[3], r2, w, h, "Servicio DTE", "Node.js, multiemisor,\nnumeración y PDF", ACCENT, DOING_BG)
    fir = d.box(xs[4], r2, w, h, "Firmador oficial", "certificado de\ncada empresa", ACCENT, DOING_BG)

    mh = d.box(xs[3], r3, w, h, "Ministerio de\nHacienda", "recepción y sello", BAD, BAD_BG)
    d.box(
        xs[0], r3, xs[2] + w - xs[0], h,
        "Todo corre en contenedores Docker",
        "Cada empresa tiene su propio emisor: datos fiscales, credenciales y certificado cifrados.",
        MUTED, SOFT,
    )

    def mid_r(b):  # borde derecho
        return b[0] + b[2], b[1] + b[3] / 2

    def mid_l(b):
        return b[0], b[1] + b[3] / 2

    def mid_b(b):
        return b[0] + b[2] / 2, b[1]

    def mid_t(b):
        return b[0] + b[2] / 2, b[1] + b[3]

    d.arrow(*mid_r(nav), *mid_l(api))
    d.arrow(*mid_r(api), *mid_l(cola))
    d.arrow(*mid_r(cola), *mid_l(wrk))
    d.arrow(*mid_r(wrk), *mid_l(mail))
    d.arrow(*mid_b(api), *mid_t(pg))
    d.arrow(*mid_b(wrk), *mid_t(svc))
    d.arrow(wrk[0] + 8, wrk[1], sto[0] + sto[2] - 8, sto[1] + sto[3])
    d.arrow(*mid_r(svc), *mid_l(fir))
    d.arrow(*mid_b(svc), *mid_t(mh), "JSON firmado", label_dx=30)


# 3. Flujo de venta y correcciones
def paint_flujo(d: Diagram) -> None:
    main = [
        ("Cliente y\nlista de precios", "hecho"),
        ("Cotización", "hecho"),
        ("Pedido", "hecho"),
        ("Facturar\n(DTE)", "hecho"),
        ("Sello de\nHacienda", "hecho"),
        ("PDF y correo\nal cliente", "hecho"),
        ("Libros de\nIVA y F-07", "pendiente"),
    ]
    n = len(main)
    gap = 12
    w = (d.width - gap * (n - 1)) / n
    h = 1.05 * cm
    y = d.height - h
    for i, (text, estado) in enumerate(main):
        _l, fg, bg = ESTADOS[estado]
        x = i * (w + gap)
        d.box(x, y, w, h, text, "", fg, bg, 8.3)
        if i < n - 1:
            d.arrow(x + w, y + h / 2, x + w + gap, y + h / 2)
    fixes = [
        ("Contingencia", "hecho"),
        ("Invalidación\ny corrección", "hecho"),
        ("Notas de crédito\ny de débito", "hecho"),
        ("Evento de\nretorno", "pendiente"),
        ("Nota de remisión\n(traslados)", "pendiente"),
    ]
    fw = (d.width - gap * (len(fixes) - 1)) / len(fixes)
    fy = 0.15 * cm
    fh = 1.05 * cm
    anchor_x = 4 * (w + gap) + w / 2
    c = d.canv
    c.setStrokeColor(MUTED)
    c.setDash(2, 2)
    mid_y = fy + fh + 0.55 * cm
    c.line(anchor_x, y, anchor_x, mid_y)
    c.line(fw / 2, mid_y, (len(fixes) - 1) * (fw + gap) + fw / 2, mid_y)
    for i in range(len(fixes)):
        cx = i * (fw + gap) + fw / 2
        c.line(cx, mid_y, cx, fy + fh)
    c.setDash()
    for i, (text, estado) in enumerate(fixes):
        _l, fg, bg = ESTADOS[estado]
        d.box(i * (fw + gap), fy, fw, fh, text, "", fg, bg, 8.3)


# 4. Ciclo de vida del documento fiscal
def paint_estados(d: Diagram) -> None:
    w = 3.3 * cm
    h = 1.15 * cm
    x0, x1, x2 = 0, d.width / 2 - w / 2, d.width - w
    step = (d.height - h - 4) / 3
    ys = [d.height - h - 2 - i * step for i in range(4)]
    pend = d.box(x0, (ys[1] + ys[2]) / 2, w, h, "Pendiente", "en cola del trabajador", NAVY, BLUE_BG)
    emit = d.box(x1, ys[0], w, h, "Emitido / Simulado", "con sello (o simulado)", DONE, DONE_BG)
    cont = d.box(x1, ys[1], w, h, "En contingencia", "sin conexión; PDF ya válido", DOING, DOING_BG)
    rech = d.box(x1, ys[2], w, h, "Rechazado", "se corrige y se factura\nde nuevo", BAD, BAD_BG)
    fall = d.box(x1, ys[3], w, h, "Falló", "no llegó a emitirse", BAD, BAD_BG)
    inval = d.box(x2, ys[0], w, h, "Invalidado", "anulado ante Hacienda", TODO, TODO_BG)
    nota = d.box(x2, ys[2] + 6, w, h * 1.5, "Ajustado", "nota de crédito o débito\n(CCF) o evento de retorno\n(factura)", ACCENT, DOING_BG)

    px, py = pend[0] + pend[2], pend[1] + pend[3] / 2
    for b in (emit, cont, rech, fall):
        d.arrow(px, py, b[0], b[1] + b[3] / 2)
    d.arrow(cont[0] + cont[2] / 2, cont[1] + cont[3], emit[0] + emit[2] / 2, emit[1], "evento de contingencia", label_dx=58, label_dy=-2)
    d.arrow(emit[0] + emit[2], emit[1] + emit[3] / 2, inval[0], inval[1] + inval[3] / 2, "anular o corregir")
    d.arrow(emit[0] + emit[2], emit[1] + 6, nota[0], nota[1] + nota[3] - 6, "ajuste posterior", label_dx=4, label_dy=-10)
    d.arrow(fall[0], fall[1] + 8, pend[0] + pend[2] / 2, pend[1], "reintentar", dashed=True, label_dx=-18, label_dy=-6)


# 5. Modelo de datos
ENTIDADES = {
    # columna 0: comercial
    "sales_customers": (0, ["tipo, NIT/DUI, NRC", "actividad, dirección", "crédito y consentimiento"]),
    "sales_price_lists": (0, ["vigencia, sucursal", "IVA incluido o no", "+ items y márgenes"]),
    "sales_quotations": (0, ["estado y vigencia", "descuentos y autorización", "+ líneas"]),
    "sales (pedido)": (0, ["cliente, sucursal", "tipo 01 o 03, totales", "reserva y entrega", "+ sales_lines"]),
    "sales_deliveries": (0, ["unidades entregadas", "+ devoluciones (B08)"]),
    # columna 1: documentos fiscales
    "sales_fiscal_documents": (1, [
        "tipo 01, 03, 05 o 06", "estado y modo", "código de generación", "número de control y sello",
        "JSON y PDF", "renta (F-07)", "related_document_id",
    ]),
    "sales_fiscal_note_lines": (1, ["línea del CCF", "devolución, rebaja o cargo", "monto neto"]),
    "sales_fiscal_invalidations": (1, ["tipo 1 o 2, motivo", "solicitante y responsable", "evento y sello"]),
    "sales_fiscal_document_emails": (1, ["destinatarios", "automático o manual", "estado del envío"]),
    # columna 2: configuración fiscal
    "company_fiscal_profiles": (2, ["modo: simulado, pruebas", "o producción", "correo y teléfono DTE"]),
    "company_economic_activities": (2, ["código CAT-019", "renta sugerida"]),
    "fiscal_establishments": (2, ["sucursal", "código M001"]),
    "fiscal_points_of_sale": (2, ["caja, código P001"]),
    "company_dte_document_types": (2, ["tipos habilitados"]),
    "company_hacienda_credentials": (2, ["usuario y certificado", "cifrados"]),
}
GRUPOS = [
    ("Comercial · V1 y V2", NAVY, BLUE_BG),
    ("Documentos fiscales · V3 y V4", ACCENT, DOING_BG),
    ("Configuración fiscal · V1 y V3", DONE, DONE_BG),
]


def paint_modelo(d: Diagram) -> None:
    c = d.canv
    gap = 26
    cw = (d.width - 2 * gap) / 3
    pad = 7
    title_h = 18
    rects: dict[str, tuple[float, float, float, float]] = {}
    for col, (title, fg, bg) in enumerate(GRUPOS):
        x = col * (cw + gap)
        c.setFillColor(bg)
        c.setStrokeColor(fg)
        c.setLineWidth(0.8)
        c.roundRect(x, 0, cw, d.height, 6, stroke=1, fill=1)
        c.setFillColor(fg)
        c.setFont("Body-B", 9.2)
        c.drawString(x + pad, d.height - 13, title)
        y = d.height - title_h - 4
        for name, (ecol, fields) in ENTIDADES.items():
            if ecol != col:
                continue
            h = 13 + 9.2 * len(fields) + 4
            y -= h
            c.setFillColor(WHITE)
            c.setStrokeColor(fg)
            c.roundRect(x + pad, y, cw - 2 * pad, h, 3, stroke=1, fill=1)
            c.setFillColor(fg)
            c.rect(x + pad, y + h - 13, cw - 2 * pad, 13, stroke=0, fill=1)
            c.setFillColor(WHITE)
            c.setFont("Mono", 7.6)
            c.drawString(x + pad + 4, y + h - 9.8, name)
            c.setFillColor(INK)
            c.setFont("Body", 7.8)
            for j, field in enumerate(fields):
                c.drawString(x + pad + 5, y + h - 23 - j * 9.2, field)
            rects[name] = (x + pad, y, cw - 2 * pad, h)
            y -= 16

    def conn(a: str, b: str, label: str = "", vertical: bool = False) -> None:
        ra, rb = rects[a], rects[b]
        if vertical:
            x = ra[0] + ra[2] / 2
            d.arrow(x, ra[1], x, rb[1] + rb[3], label, color=NAVY, label_dx=8 + len(label) * 1.9, label_dy=-3)
            return
        if ra[0] < rb[0]:
            x1, x2 = ra[0] + ra[2], rb[0]
        else:
            x1, x2 = ra[0], rb[0] + rb[2]
        y1 = ra[1] + ra[3] / 2
        y2 = max(rb[1] + 8, min(rb[1] + rb[3] - 8, y1))
        d.arrow(x1, y1, x2, y2, label, color=NAVY)

    conn("sales_customers", "sales_price_lists", vertical=True)
    conn("sales_price_lists", "sales_quotations", vertical=True)
    conn("sales_quotations", "sales (pedido)", "se convierte en", vertical=True)
    conn("sales (pedido)", "sales_deliveries", "se entrega", vertical=True)
    conn("sales (pedido)", "sales_fiscal_documents", "«Facturar»")
    conn("fiscal_points_of_sale", "sales_fiscal_documents", "emite")
    conn("sales_fiscal_documents", "sales_fiscal_note_lines", "notas", vertical=True)
    conn("sales_fiscal_note_lines", "sales_fiscal_invalidations", vertical=True)
    conn("sales_fiscal_invalidations", "sales_fiscal_document_emails", vertical=True)
    conn("fiscal_establishments", "fiscal_points_of_sale", vertical=True)


def footer(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Body", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "GestionaSV · Resumen del plan de Ventas y Facturación electrónica")
    canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(2 * cm, 1.5 * cm, letter[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


# --- contenido ------------------------------------------------------------------------------------

MODULOS = [
    ("Clientes",
     "Maestro de clientes del área de Ventas. Distingue consumidor final y contribuyente, valida NIT, DUI y "
     "NRC, y guarda la actividad económica y la dirección con departamento, municipio y distrito del "
     "catálogo de Hacienda. Registra condiciones de crédito, direcciones de entrega, los documentos que el "
     "cliente puede recibir y su consentimiento para el uso de datos personales. De la ficha sale el "
     "receptor de cada factura.",
     "V1", "hecho"),
    ("Precios, impuestos y promociones",
     "Decide el precio, el descuento y el impuesto de cada línea con reglas auditables. Hecho: listas de "
     "precios con vigencia y precio por sucursal, precio sugerido por margen sobre el costo, descuento del "
     "cliente y por volumen, topes de descuento por rol, autorización para vender bajo costo y un motor "
     "único de IVA, retención y percepción. Falta: promociones por sucursal; las promociones de "
     "mostrador (2×1, combos) se guardan para el futuro con el punto de venta.",
     "V2", "parcial"),
    ("Cotizaciones y pedidos",
     "Separa la oferta del compromiso. La cotización calcula totales fiscales, pide autorización solo si "
     "el descuento pasa el tope del vendedor, tiene vigencia y PDF. El pedido nace de una cotización "
     "aceptada o directo, aparta existencias al confirmarse y guarda la fecha comprometida y si se retira o "
     "se entrega. Falta: venta directa de mostrador sin pedido y encargos con anticipo.",
     "V2 · V5", "parcial"),
    ("Facturación electrónica (DTE)",
     "Emite el documento tributario electrónico de cada venta. Hecho: configuración fiscal por empresa "
     "(emisor, establecimientos, puntos de venta, documentos habilitados), servicio DTE multiemisor, "
     "factura y crédito fiscal con sello, PDF con QR, envío por correo, ambiente de pruebas con "
     "credenciales cifradas, contingencia, invalidación y corrección. Falta: nota de remisión, evento de "
     "retorno y el lote de certificación que Hacienda pide antes de producción.",
     "V1 · V3 · V4", "parcial"),
    ("Devoluciones, notas de crédito y débito",
     "Da efecto fiscal a lo que cambia después de facturar. Hecho: notas de crédito (devolución o rebaja) "
     "y de débito (cargos) sobre un crédito fiscal, con saldo por línea, retención espejo y plazo de tres "
     "meses. Falta: el evento de retorno para facturas de consumidor final y enlazar la devolución física "
     "(que hoy solo mueve inventario) con su nota o evento.",
     "V4 · V8", "parcial"),
    ("Entregas y despacho",
     "Hace que la mercadería salga amparada por un documento y llegue con constancia de recibido. Las "
     "entregas por unidades logísticas ya existían. Se agregan la nota de remisión cuando algo sale sin "
     "factura (traslados en V4d; entregas de venta después), la hoja de ruta por vehículo y conductor y el "
     "comprobante de entrega con quién recibió.",
     "V4 · posterior", "pendiente"),
    ("Cuentas por cobrar y cobros",
     "Controla las ventas a crédito desde que se facturan hasta que se cobran: estado de cuenta por "
     "cliente con cada documento y su vencimiento, cobros parciales con recibo, formas de pago, "
     "retenciones que aplican los clientes grandes y bloqueo de nuevas ventas por crédito vencido o "
     "excedido.",
     "V5", "pendiente"),
    ("Documentos de proveedor y gastos",
     "Registro único del documento de cada proveedor, enlazado con compras, retaceo, combustible y "
     "mantenimiento de flota, más los gastos generales. Aplica las reglas de crédito fiscal deducible, "
     "emite la factura de sujeto excluido y recibe los DTE de proveedores. Alimenta el libro de compras.",
     "V7", "pendiente"),
    ("Fiscal: libros de IVA y F-07",
     "Genera sin trabajo manual lo que cada empresa declara al mes: libros de ventas a contribuyentes, a "
     "consumidor final y de compras, y los anexos y casillas del F-07, con cierre de período. Hecho: la "
     "clasificación de renta (tipo de operación e ingreso) que se elige en cada documento al facturar.",
     "V4 · V8", "parcial"),
    ("Análisis comercial",
     "Tablero para gerencia y cada tienda: ventas por día, hora, sucursal, cajero, cliente, categoría y "
     "producto, con márgenes y comparación entre periodos.",
     "V9", "pendiente"),
]

# (bloque, introducción, [(entrega, texto)])
HECHO = [
    ("V1 · Base fiscal",
     "Antes de vender hay que saber quién vende, a quién y qué. Este bloque deja a cada empresa configurada "
     "como emisor ante Hacienda y a los clientes y productos con sus datos fiscales.",
     [
         ("V1a · Emisor de DTE (PR #38)",
          "Perfil fiscal por empresa (categoría de contribuyente y modo: simulado, pruebas o producción), "
          "actividades económicas, un establecimiento por sucursal con su código (M001), puntos de venta por "
          "caja (P001), tipos de documento que la empresa habilita y los catálogos oficiales de Hacienda "
          "cargados y versionados en el sistema."),
         ("V1b · Clientes con datos fiscales (PR #39)",
          "El cliente distingue consumidor final y contribuyente. Se validan NIT, DUI y NRC; la dirección "
          "usa departamento, municipio y distrito del catálogo; se registran actividad, condiciones de "
          "crédito, direcciones de entrega y los documentos que puede recibir."),
         ("V1c · Clasificación fiscal de productos (PR #40)",
          "Cada producto indica si su venta es gravada, exenta o no sujeta, si es bien o servicio y su unidad "
          "de medida de Hacienda. Así el cálculo del impuesto sale del producto y no de lo que escriba el "
          "vendedor."),
         ("V1d · Datos personales (PR #41)",
          "Aviso de privacidad vigente, consentimiento del cliente y registro de solicitudes de titulares "
          "(acceso, corrección, eliminación) con sus plazos, como pide la ley de protección de datos."),
     ]),
    ("V2 · Precios, impuestos, cotización y pedido",
     "El precio, el descuento y el impuesto de cada línea los calcula el sistema con reglas auditables, y "
     "la venta se separa en oferta (cotización) y compromiso (pedido).",
     [
         ("V2a · Motor único de cálculo fiscal (PR #42)",
          "Un solo motor para cotización, pedido y factura: IVA del 13 % incluido en la factura y separado "
          "en el crédito fiscal, retención y percepción del 1 % desde $100, redondeo a centavos y total en "
          "letras. Garantiza que el documento cuadre con lo que Hacienda valida."),
         ("V2b · Listas de precios (PR #43)",
          "Listas por empresa con vigencia, precio por sucursal e indicador de IVA incluido; una lista "
          "predeterminada y otras para mayoreo o clientes institucionales."),
         ("V2c · Margen y descuentos (PR #45)",
          "Precio sugerido a partir del costo promedio y un margen objetivo; descuento fijo del cliente, "
          "escalas por volumen y topes de descuento por rol. Vender por debajo del costo exige autorización."),
         ("V2d · Cotización rediseñada (PR #46)",
          "Estados Borrador → Por autorizar → Emitida → Aceptada o Rechazada, con vigencia y PDF. Pasa por "
          "autorización solo cuando el descuento supera el tope del vendedor."),
         ("V2e · Pedido de venta (PR #47)",
          "El pedido nace de una cotización aceptada o directo. Al confirmarse aparta las existencias "
          "(reserva comercial), guarda la fecha comprometida y si se retira en sucursal o se entrega."),
     ]),
    ("V3 · Factura electrónica",
     "El corazón del proyecto: emitir el documento tributario electrónico que exige Hacienda, firmado, "
     "sellado y entregado al cliente.",
     [
         ("V3a · Servicio DTE multiemisor (PR #48)",
          "Se incorporó al sistema un servicio en Node.js que arma el JSON según los esquemas oficiales, lleva "
          "la numeración por establecimiento y punto de venta, genera el PDF con QR y transmite. Se adaptó "
          "para atender a varias empresas a la vez y tiene un modo simulado para practicar sin Hacienda."),
         ("V3b · Facturar el pedido (PR #49)",
          "Botón «Facturar» en el pedido confirmado: el sistema elige factura o crédito fiscal, concilia los "
          "totales al centavo y deja el documento en cola; un trabajador lo emite y reintenta si falla. "
          "Bandeja de documentos fiscales con su estado, JSON y PDF."),
         ("V3c · Envío por correo (PR #50)",
          "Al emitirse, el documento se envía solo al correo del cliente con el PDF y el JSON, desde el "
          "correo propio de cada empresa. También se puede reenviar a mano y queda el historial."),
         ("V3d · Ambiente de pruebas de Hacienda (PR #51)",
          "Credenciales y certificado de firma por empresa, guardados cifrados, con «Probar conexión»; el "
          "firmador oficial de Hacienda se compila dentro del sistema. Una empresa pasa a pruebas solo con "
          "credenciales verificadas."),
     ]),
    ("V4 · Robustez del DTE (tres de cinco partes)",
     "Lo que pasa cuando algo sale mal o cambia después de facturar: sin conexión, errores y ajustes.",
     [
         ("V4a · Contingencia (PR #53)",
          "Si Hacienda no responde, el establecimiento entra en contingencia: los documentos se generan y "
          "entregan al cliente con validez, y al restablecerse se informa el evento de contingencia y se "
          "transmiten. Cada empresa registra a su responsable fiscal."),
         ("V4b · Invalidación y corrección (PR #55)",
          "Un documento sellado no se borra: se anula ante Hacienda (rescindir la operación) o se corrige "
          "emitiendo uno nuevo que lo reemplaza. Respeta los plazos legales, avisa al cliente y permite "
          "cancelar un pedido ya facturado. Un documento rechazado se corrige y se factura de nuevo."),
         ("V4b2 · Clasificación de renta (PR #56)",
          "Cada documento guarda el tipo de operación y de ingreso que piden los anexos del F-07; se sugiere "
          "según la actividad económica y se elige al facturar."),
         ("V4c · Notas de crédito y de débito (PR #57)",
          "Sobre un crédito fiscal sellado: la nota de crédito registra devoluciones o rebajas sin pasar del "
          "saldo de cada línea; la de débito, cargos como intereses o ajustes de precio. Repiten la "
          "retención del crédito fiscal, se emiten dentro de tres meses y bloquean anularlo mientras estén "
          "vigentes."),
     ]),
]

# (bloque, objetivo, [qué se hará], terminado cuando)
FALTA = [
    ("V4d · Nota de remisión y evento de retorno",
     "Que ninguna mercadería circule sin documento y que las devoluciones sobre facturas tengan su efecto "
     "fiscal.",
     [
         "<b>Nota de remisión</b> al despachar un traslado entre sucursales: título «Traslado», emisor la "
         "sucursal de origen y receptor la misma empresa con la dirección de destino. El despacho no se "
         "confirma sin ella; la recepción parcial no la cambia y un error se corrige invalidándola.",
         "<b>Evento de retorno</b> sobre una factura de consumidor final: se elige la cantidad devuelta de "
         "cada línea, sin pasar de lo vendido, dentro de tres meses desde el sello.",
         "Plantillas PDF de ambos documentos.",
     ],
     "un traslado viaja con su nota de remisión y una devolución sobre factura queda documentada."),
    ("V4e · Lote de certificación",
     "Hacienda exige emitir un lote de documentos de prueba de cada tipo antes de autorizar producción.",
     [
         "Pantalla por empresa con cuántos documentos pide Hacienda por tipo, cuántos van aceptados y cuáles "
         "fueron rechazados con su motivo.",
         "Generación del lote con datos de prueba y su transmisión con avance; probado primero contra un "
         "simulador.",
     ],
     "el lote se completa en el simulador y queda listo para correrse con credenciales reales."),
    ("V5 · Pedidos y cobros",
     "Controlar la venta a crédito desde que se factura hasta que se cobra.",
     [
         "Venta directa sin cotización y encargos con anticipo (el anticipo también se documenta).",
         "Formas de pago, cuentas por cobrar con estado de cuenta por cliente, cobros parciales y recibos.",
         "Retenciones que hacen los clientes grandes y bloqueo de ventas por crédito vencido o excedido.",
     ],
     "una venta a crédito facturada, cobrada en partes y con el saldo correcto."),
    ("V7 · Documentos de proveedor y gastos",
     "Que cada compra y gasto entre al libro de compras con su crédito fiscal correcto.",
     [
         "Registro único del documento del proveedor, enlazado a compras, retaceo, combustible y "
         "mantenimiento de flota.",
         "Gastos generales, reglas de crédito fiscal deducible, factura de sujeto excluido y recepción de DTE "
         "de proveedores.",
     ],
     "una compra, una carga de combustible y un recibo de energía aparecen en el libro de compras."),
    ("V8 · Libros de IVA y F-07",
     "Generar sin trabajo manual lo que la empresa declara cada mes.",
     [
         "Devoluciones con efecto fiscal: la devolución física genera su nota de crédito o evento de retorno.",
         "Libros de ventas a contribuyentes, a consumidor final y de compras, y todos los anexos del F-07.",
         "Cierre de período: lo declarado ya no se modifica.",
     ],
     "el Excel de un mes coincide hoja por hoja con la plantilla estándar llenada a mano."),
    ("V9 · Análisis y aceptación",
     "Cerrar el proyecto con información útil para gerencia y una prueba integral.",
     [
         "Tablero comercial: ventas por día, sucursal, cajero, producto y cliente, con márgenes.",
         "Datos de demostración, manuales de usuario y recorrido completo en local y en el servidor.",
     ],
     "el recorrido completo funciona en local y en gestionasv.lat."),
]


def build(path: str) -> None:
    story: list[Flowable] = []
    add = story.append

    # portada
    add(P("GestionaSV · ERP multiempresa", "subtitle"))
    add(Spacer(1, 2))
    add(P("Área de Ventas y Facturación electrónica", "title"))
    add(Spacer(1, 3))
    add(P(f"Resumen del plan: qué se agrega al sistema, qué ya está hecho y qué falta · {FECHA}", "subtitle"))
    add(Spacer(1, 10))

    add(P("1. Propósito", "h1"))
    add(P(
        "GestionaSV ya resolvía compras, inventario, traslados entre sucursales y flota. El proyecto agrega el "
        "<b>área de Ventas</b>: desde el cliente y el precio hasta la factura electrónica (DTE) que exige el "
        "Ministerio de Hacienda de El Salvador, sus correcciones y, al final, los libros de IVA y la "
        "declaración mensual (F-07). Cada empresa del grupo es un emisor independiente, con sus propios datos "
        "fiscales, numeración, credenciales y documentos habilitados. La empresa de demostración es Grupo "
        "Lorena."
    ))

    add(P("2. Avance general", "h1"))
    add(P(
        "El trabajo se divide en ocho bloques (el punto de venta, antes V6, se pospuso). Cada bloque se entrega en partes pequeñas, con pruebas "
        "automáticas y revisión, y se integra al sistema cuando todo pasa. A la fecha van <b>17 entregas de "
        "funcionalidad integradas</b> (PR #38 a #57): los bloques V1 a V3 están completos y V4 va en tres de "
        "sus cinco partes."
    ))
    add(Diagram(2.2 * cm, paint_avance))
    add(caption("Figura 1. Avance de los bloques del área de Ventas."))

    add(KeepTogether([
        P("3. Arquitectura", "h1"),
        P(
            "La interfaz habla con la API, que guarda todo en PostgreSQL. La emisión de documentos no detiene "
            "al usuario: va a una cola y un trabajador la procesa con el servicio DTE, que firma con el "
            "certificado de la empresa y transmite a Hacienda. El JSON y el PDF se guardan y se envían al "
            "cliente por correo."
        ),
        Diagram(6.6 * cm, paint_arquitectura),
        caption("Figura 2. Componentes del sistema que intervienen en la venta y la facturación."),
    ]))

    add(PageBreak())
    add(P("4. Flujo de venta y facturación", "h1"))
    add(P(
        "La línea superior es el camino normal de una venta; la inferior, los documentos y eventos que la "
        "corrigen cuando algo cambia después de emitida la factura."
    ))
    add(Diagram(4.3 * cm, paint_flujo))
    add(caption("Figura 3. Flujo de la venta y documentos que la corrigen (verde: hecho; gris: por hacer)."))

    add(KeepTogether([
        P("5. Ciclo de vida del documento fiscal", "h1"),
        P(
            "Cada factura, crédito fiscal o nota pasa por estos estados. Un documento sellado nunca se borra "
            "ni se edita: se anula, se reemplaza o se ajusta con otro documento."
        ),
        Diagram(7.4 * cm, paint_estados),
        caption("Figura 4. Estados del documento fiscal y transiciones."),
    ]))

    add(PageBreak())
    add(P("6. Modelo de datos del área", "h1"))
    add(P(
        "Tablas principales que se agregan a la base de datos, agrupadas por función. Todas llevan la empresa "
        "(<font face='Mono'>company_id</font>) para aislar los datos de cada emisor, y toda escritura queda en "
        "la bitácora de auditoría."
    ))
    add(Diagram(11.6 * cm, paint_modelo))
    add(caption(
        "Figura 5. Modelo de datos simplificado. Las flechas muestran de dónde nace cada registro; "
        "related_document_id une una nota con su crédito fiscal."
    ))

    add(P("7. Módulos que se agregan al ERP", "h1"))
    add(table(
        ["Módulo", "Qué hace", "Bloque", "Estado"],
        [[f"<b>{m}</b>", d, b, badge(e)] for m, d, b, e in MODULOS],
        [0.22, 0.56, 0.11, 0.11],
        [e for *_rest, e in MODULOS],
    ))

    add(PageBreak())
    add(P("8. Lo ya realizado", "h1"))
    for bloque, intro, entregas in HECHO:
        (titulo0, texto0), *resto = entregas
        add(KeepTogether([P(bloque, "h2"), P(intro), P(titulo0, "done_label"), P(texto0)]))
        for titulo, texto in resto:
            add(KeepTogether([P(titulo, "done_label"), P(texto)]))

    add(PageBreak())
    add(P("9. Lo que falta", "h1"))
    add(P(
        "Cada bloque tiene un objetivo, una lista de funciones y un resultado verificable que indica cuándo "
        "se da por terminado."
    ))
    for bloque, objetivo, items, terminado in FALTA:
        add(KeepTogether([
            P(bloque, "h2"),
            P(f"<b>Objetivo:</b> {objetivo}"),
            *bullets(items),
            P(f"<i>Se da por terminado cuando</i> {terminado}", "note"),
            Spacer(1, 4),
        ]))

    add(KeepTogether([
        P("10. Para el futuro: punto de venta y caja", "h1"),
        P('El ingeniero de la materia pidió un alcance más simple, así que el <b>punto de venta y caja</b> (antes bloque V6) queda fuera del alcance actual. No se descarta: queda guardado para una etapa posterior, con este contenido.'),
        *bullets(['Pantalla de venta rápida de mostrador con lector de código de barras, cobro con varios medios y tiquete de 80 mm.', 'Turnos por cajero, arqueo por denominación, depósito del día y cierre que no se modifica una vez aprobado.', 'Existencia de vitrina que se descuenta por pieza y operación en contingencia con enlace de respaldo por tienda.', 'Promociones de mostrador como 2×1, combos o precio por horario.']),
    ]))

    add(KeepTogether([
        P("11. Cómo se trabaja", "h1"),
        *bullets([
            "<b>Tecnología:</b> FastAPI y PostgreSQL en el servidor, SvelteKit en la interfaz, servicio DTE en "
            "Node.js y firmador oficial de Hacienda, todo en contenedores Docker.",
            "<b>Calidad:</b> cada entrega incluye pruebas automáticas (unitarias, de integración y de extremo a "
            "extremo); la batería completa supera las 3,700 pruebas y debe pasar antes de integrar.",
            "<b>Normativa:</b> Código Tributario, Ley del IVA, Normativa de Cumplimiento DTE 2.0, Manual "
            "Funcional V2.0 y esquemas JSON oficiales de Hacienda.",
            "<b>Seguridad:</b> permisos por rol en cada acción, bitácora de auditoría y credenciales cifradas.",
        ]),
        Spacer(1, 6),
        P(
            "Este documento resume el plan detallado «Plan del área de Ventas — El Salvador» "
            "(docs/plan-area-ventas-el-salvador.pdf).", "note"
        ),
    ]))

    doc = SimpleDocTemplate(
        path, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
        bottomMargin=2 * cm, title="Resumen del plan de Ventas y Facturación electrónica",
        author="GestionaSV",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resumen-plan-ventas.pdf")
    build(out)
    print(out)

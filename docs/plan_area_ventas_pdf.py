# -*- coding: utf-8 -*-
"""Genera docs/plan-area-ventas-el-salvador.pdf.

Uso (desde la raíz del repositorio):
    py -3 docs/plan_area_ventas_pdf.py [salida.pdf]

Requiere reportlab y las fuentes Calibri y Georgia de Windows. El contenido del
plan vive en este archivo: para cambiar el documento se edita aquí y se vuelve
a generar el PDF.
"""
import os
import sys
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import Flowable
from reportlab.platypus.tableofcontents import TableOfContents

F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Body", F + "calibri.ttf"))
pdfmetrics.registerFont(TTFont("Body-B", F + "calibrib.ttf"))
pdfmetrics.registerFont(TTFont("Body-I", F + "calibrii.ttf"))
pdfmetrics.registerFont(TTFont("Body-BI", F + "calibriz.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-B", italic="Body-I", boldItalic="Body-BI")
pdfmetrics.registerFont(TTFont("Head", F + "georgia.ttf"))
pdfmetrics.registerFont(TTFont("Head-B", F + "georgiab.ttf"))

NAVY = colors.HexColor("#17324D")
ACCENT = colors.HexColor("#A8672A")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#5B6770")
LINE = colors.HexColor("#C9D1D9")
SOFT = colors.HexColor("#F2F5F8")
NOTE = colors.HexColor("#FBF4EA")

W, H = letter
ML, MR, MT, MB = 2.4 * cm, 2.4 * cm, 2.5 * cm, 2.3 * cm
CW = W - ML - MR

S = {
    "body": ParagraphStyle("body", fontName="Body", fontSize=10.5, leading=15, textColor=INK,
                           alignment=TA_JUSTIFY, spaceAfter=7),
    "bul": ParagraphStyle("bul", fontName="Body", fontSize=10.5, leading=14.5, textColor=INK,
                          leftIndent=16, bulletIndent=4, spaceAfter=3.5, alignment=TA_LEFT),
    "h1": ParagraphStyle("h1", fontName="Head-B", fontSize=17, leading=22, textColor=NAVY,
                         spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Head-B", fontSize=12.5, leading=16, textColor=NAVY,
                         spaceBefore=12, spaceAfter=6, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-B", fontSize=11, leading=14, textColor=ACCENT,
                         spaceBefore=8, spaceAfter=4, keepWithNext=1),
    "part": ParagraphStyle("part", fontName="Body-B", fontSize=10, leading=13, textColor=ACCENT,
                           spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=9.2, leading=12, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Body-B", fontSize=9.2, leading=12, textColor=INK),
    "th": ParagraphStyle("th", fontName="Body-B", fontSize=9.2, leading=12, textColor=colors.white),
    "note": ParagraphStyle("note", fontName="Body", fontSize=9.8, leading=13.5, textColor=INK),
    "cap": ParagraphStyle("cap", fontName="Body-I", fontSize=9, leading=12, textColor=MUTED,
                          alignment=TA_CENTER, spaceBefore=4, spaceAfter=10),
    "toc1": ParagraphStyle("toc1", fontName="Body-B", fontSize=10.5, leading=16, textColor=NAVY,
                           spaceBefore=6),
    "toc2": ParagraphStyle("toc2", fontName="Body", fontSize=10, leading=14, textColor=INK,
                           leftIndent=16),
}


class Doc(BaseDocTemplate):
    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph):
            n = fl.style.name
            if n == "h1":
                self.notify("TOCEntry", (0, fl.getPlainText(), self.page))
            elif n == "h2":
                self.notify("TOCEntry", (1, fl.getPlainText(), self.page))


def page_deco(c, doc):
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(ML, H - 1.7 * cm, W - MR, H - 1.7 * cm)
    c.setFont("Body", 8.5)
    c.setFillColor(MUTED)
    c.drawString(ML, H - 1.45 * cm, "GestionaSV ERP · Ventas y facturación fiscal")
    c.drawRightString(W - MR, H - 1.45 * cm, "Investigación y plan de implementación")
    c.line(ML, 1.6 * cm, W - MR, 1.6 * cm)
    c.drawString(ML, 1.15 * cm, "Plan multiempresa · Noviembre de 2026")
    c.drawRightString(W - MR, 1.15 * cm, "Página %d" % doc.page)
    c.restoreState()


def cover(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, H - 9.2 * cm, W, 9.2 * cm, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(ML, H - 9.2 * cm - 0.18 * cm, 4.2 * cm, 0.18 * cm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Body-B", 11)
    c.drawString(ML, H - 3.0 * cm, "GESTIONASV ERP  ·  PLAN MULTIEMPRESA")
    c.setFont("Head-B", 27)
    c.drawString(ML, H - 5.3 * cm, "Ventas y facturación fiscal")
    c.setFont("Head", 15)
    c.drawString(ML, H - 6.5 * cm, "Investigación del marco salvadoreño")
    c.drawString(ML, H - 7.3 * cm, "y plan de implementación")
    c.setFillColor(INK)
    c.setFont("Body", 11.5)
    y = H - 11.6 * cm
    for a, b in [("Tipo de documento", "Estudio técnico-normativo y plan de trabajo"),
                 ("Alcance", "Clientes, precios, pedidos, punto de venta, facturación electrónica"),
                 ("", "multiemisor (DTE), entregas, devoluciones, cobros, datos fiscales de"),
                 ("", "compras, libros de IVA y anexos del F-07"),
                 ("Empresa piloto", "Grupo Lorena, cadena de panaderías"),
                 ("País de aplicación", "República de El Salvador"),
                 ("Fecha", "15 de noviembre de 2026"),
                 ("Versión", "2.3 — para revisión del equipo")]:
        c.setFont("Body-B", 10.5)
        c.setFillColor(MUTED)
        c.drawString(ML, y, a)
        c.setFont("Body", 11)
        c.setFillColor(INK)
        c.drawString(ML + 4.4 * cm, y, b)
        y -= 0.72 * cm
    c.setStrokeColor(LINE)
    c.line(ML, 3.6 * cm, W - MR, 3.6 * cm)
    c.setFont("Body-I", 9.5)
    c.setFillColor(MUTED)
    c.drawString(ML, 3.0 * cm, "Este documento resume normativa tributaria con fines de diseño de software. No sustituye la")
    c.drawString(ML, 2.55 * cm, "asesoría de un contador público o del Ministerio de Hacienda; los datos se verificaron en su fuente oficial (Parte VIII).")
    c.restoreState()


def P(t):
    return Paragraph(t, S["body"])


def B(items):
    return [Paragraph(i, S["bul"], bulletText="•") for i in items]


def T(head, rows, widths, zebra=True):
    data = [[Paragraph(h, S["th"]) for h in head]]
    for r in rows:
        data.append([Paragraph(str(x), S["cellb"] if i == 0 else S["cell"]) for i, x in enumerate(r)])
    t = Table(data, colWidths=[w * CW for w in widths], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    if zebra:
        for i in range(2, len(data), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(st))
    return t


def NOTEBOX(title, text):
    t = Table([[Paragraph("<b>%s</b> %s" % (title, text), S["note"])]], colWidths=[CW])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NOTE), ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 8)])


class Flow(Flowable):
    """Fila(s) de cajas unidas por flechas."""

    def __init__(self, rows, box_h=1.25 * cm, gap=0.45 * cm, vgap=0.75 * cm):
        super().__init__()
        self.rows, self.bh, self.gap, self.vgap = rows, box_h, gap, vgap
        self.width = CW
        self.keepWithNext = 1
        self.height = len(rows) * box_h + (len(rows) - 1) * vgap + 4

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        y = self.height - self.bh - 2
        for ri, row in enumerate(self.rows):
            n = len(row)
            bw = (self.width - (n - 1) * self.gap) / n
            for i, (label, kind) in enumerate(row):
                x = i * (bw + self.gap)
                fill = {"n": colors.white, "a": NOTE, "d": NAVY}[kind]
                c.setFillColor(fill)
                c.setStrokeColor(NAVY if kind != "a" else ACCENT)
                c.setLineWidth(0.9)
                c.roundRect(x, y, bw, self.bh, 4, stroke=1, fill=1)
                c.setFillColor(colors.white if kind == "d" else INK)
                lines = label.split("\n")
                c.setFont("Body-B", 8.6)
                ty = y + self.bh / 2 + (len(lines) - 1) * 5 - 3
                for ln in lines:
                    c.drawCentredString(x + bw / 2, ty, ln)
                    ty -= 10
                if i < n - 1:
                    ax = x + bw
                    c.setStrokeColor(MUTED)
                    c.setFillColor(MUTED)
                    c.line(ax + 2, y + self.bh / 2, ax + self.gap - 4, y + self.bh / 2)
                    p = c.beginPath()
                    p.moveTo(ax + self.gap - 1, y + self.bh / 2)
                    p.lineTo(ax + self.gap - 6, y + self.bh / 2 + 3)
                    p.lineTo(ax + self.gap - 6, y + self.bh / 2 - 3)
                    p.close()
                    c.drawPath(p, stroke=0, fill=1)
            if ri < len(self.rows) - 1:
                c.setStrokeColor(MUTED)
                c.setDash(2, 2)
                xr = self.width - bw / 2
                c.line(xr, y, xr, y - self.vgap / 2)
                c.line(xr, y - self.vgap / 2, bw / 2, y - self.vgap / 2)
                c.line(bw / 2, y - self.vgap / 2, bw / 2, y - self.vgap + 2)
                c.setDash()
            y -= self.bh + self.vgap


story = []


def part(num, title):
    story.append(PageBreak())
    story.append(Paragraph("PARTE %s" % num, S["part"]))
    story.append(Paragraph(title, S["h1"]))


def h2(t):
    story.append(Paragraph(t, S["h2"]))


def h3(t):
    story.append(Paragraph(t, S["h3"]))


def add(*x):
    for i in x:
        if isinstance(i, list):
            story.extend(i)
        else:
            story.append(i)


# ---------------- Portada e índice ----------------
story.append(NextPageTemplate("normal"))
story.append(PageBreak())
story.append(Paragraph("Contenido", S["h1"].clone("toc_title")))
toc = TableOfContents()
toc.levelStyles = [S["toc1"], S["toc2"]]
story.append(toc)

# ---------------- PARTE I ----------------
part("I", "Presentación y resumen ejecutivo")
h2("1.1 Objetivo del documento")
add(P("Este documento reúne la investigación necesaria para construir correctamente el área de Ventas del ERP "
      "GestionaSV, tal como debe operar una empresa salvadoreña, y propone un plan de implementación por bloques. "
      "Responde tres preguntas: qué exige la ley y la práctica comercial en El Salvador, qué módulos componen el "
      "área y qué lleva cada uno, y en qué orden conviene construirlos sobre lo que el ERP ya tiene."))
add(P("GestionaSV es un ERP multiempresa y multisucursal, así que el diseño no se fija para una sola empresa. "
      "Grupo Lorena, una cadena de panaderías, es la empresa piloto y la fuente de los ejemplos. El alcance "
      "rebasa las ventas en un punto: la declaración mensual de IVA también depende de las compras, por lo que "
      "el plan incluye los documentos de proveedor de todos los gastos: mercadería, flota y gastos generales."))
h2("1.2 Cómo se elaboró")
add(B(["<b>Revisión del ERP actual.</b> Se examinaron los modelos de datos, las rutas de la API, las pantallas y los "
       "manuales de los bloques B06 (ventas base), B07 (entregas) y B08 (devoluciones).",
       "<b>Fuentes oficiales.</b> Guía de integración de factura electrónica de la Dirección General de Impuestos "
       "Internos (DGII), formularios y boletines del Ministerio de Hacienda, y material de la Defensoría del Consumidor.",
       "<b>Fuentes secundarias.</b> Alertas de firmas de auditoría, proveedores de facturación electrónica y prensa "
       "económica salvadoreña, usadas para los cambios de 2024 a 2026.",
       "<b>Implementación de referencia.</b> Se revisó, solo en lectura, el sistema de facturación electrónica "
       "de un proyecto de referencia del mismo equipo. Fue construido leyendo directamente los manuales técnico y "
       "funcional de Hacienda en su versión 2.0, por lo que sirvió para corregir varios datos operativos.",
       "<b>Verificación.</b> Los plazos, montos y direcciones se comprobaron leyendo directamente la Normativa "
       "de Cumplimiento 2.0, los manuales técnico y funcional, el catálogo oficial y el Código Tributario; la "
       "Parte VIII indica la fuente de cada dato y el alcance de la verificación."]))
h2("1.3 Resumen ejecutivo")
add(P("El ERP tiene hoy un primer intento de ventas: cliente, cotización, venta, entrega y devolución. Este "
      "documento <b>no lo toma como base válida</b>. Se diseñó primero cómo debe funcionar el área según la ley y "
      "la práctica salvadoreña, y después se evaluó lo existente contra ese diseño. La conclusión es que el módulo "
      "actual es un prototipo que debe rediseñarse; solo la infraestructura común del ERP se reutiliza. Sus "
      "carencias de fondo son:"))
add(B(["<b>No existe facturación.</b> Ninguna venta genera un Documento Tributario Electrónico (DTE). En El Salvador "
       "la factura electrónica es el único comprobante con validez fiscal para los emisores incorporados, y debe "
       "transmitirse al Ministerio de Hacienda para obtener un sello de recepción.",
       "<b>No hay impuestos.</b> Los totales no contemplan IVA (13 %), ni retención o percepción del 1 %, ni "
       "operaciones exentas o no sujetas.",
       "<b>El cliente no tiene identidad fiscal.</b> Faltan NIT, NRC, actividad económica, dirección y la "
       "clasificación de contribuyente, que deciden qué documento se emite.",
       "<b>No hay precios, descuentos ni cobros.</b> El precio se teclea en cada línea, no existen listas de precios, "
       "formas de pago, caja ni cuentas por cobrar.",
       "<b>No hay venta de mostrador.</b> Toda venta exige una cotización previa; una panadería vende la mayor parte "
       "en caja, en segundos y a consumidor final.",
       "<b>El flujo está mal planteado.</b> Confunde pedido con factura, no reserva existencias, y la devolución "
       "no tiene efecto fiscal ni financiero."]))
add(P("La propuesta organiza el área en <b>diez módulos</b> y los construye en <b>nueve bloques</b>. El orden "
      "prioriza primero la base fiscal (emisor, cliente, impuestos, precios), después el documento legal (DTE) y "
      "por último la velocidad de operación (punto de venta) y el control fiscal (compras, libros de IVA y F-07). "
      "Cuatro decisiones de diseño atraviesan todo el plan:"))
add(B(["<b>Facturación multiemisor.</b> Cada empresa es un emisor aislado, con sus credenciales, numeración y "
       "ambiente; elige qué documentos emite; y cada sucursal y caja tiene sus propios códigos ante Hacienda "
       "(sección 6.5).",
       "<b>Se parte de una base existente.</b> El servicio DTE de un proyecto de referencia del equipo ya genera, "
       "firma y transmite documentos, con modo simulado, de pruebas y de producción. Se adapta a varias empresas "
       "en lugar de escribirse desde cero; aún no se ha certificado ante Hacienda (sección 2.5).",
       "<b>F-07 y libros completos.</b> El ERP genera los tres libros de IVA y todos los anexos de la "
       "declaración con las columnas oficiales. Como la mitad sale de las compras, se agrega un bloque para sus "
       "documentos de proveedor y gastos, incluidos los de flota (módulo 9 y bloque V7).",
       "<b>Datos verificados.</b> Los plazos, montos, catálogos y formatos se leyeron en la Normativa de "
       "Cumplimiento 2.0, los manuales de Hacienda, el Código Tributario y su reglamento (Parte VIII)."]))
add(NOTEBOX("Fecha crítica.", "Hacienda publicó la Normativa de Cumplimiento de los DTE versión 2.0, que sustituye a "
            "la 1.2 y está vigente desde el 25 de mayo de 2026. Según el comunicado de Hacienda de esa fecha, quienes usan el Sistema de Transmisión deben tener sus sistemas "
            "adaptados el <b>1 de diciembre de 2026</b>. El módulo de facturación debe construirse directamente "
            "contra los esquemas de la versión 2.0, no contra la versión anterior."))

# ---------------- PARTE II ----------------
part("II", "Evaluación crítica del módulo de ventas actual")
h2("2.1 Criterio de evaluación")
add(P("Que una función exista en el ERP no significa que sea correcta. Cada pieza del módulo actual se contrastó "
      "con tres preguntas: ¿cumple lo que exige la normativa salvadoreña?, ¿refleja cómo vende realmente una cadena "
      "de panaderías?, y ¿su modelo de datos admite lo que falta sin rehacerse? El veredicto de cada pieza es uno "
      "de tres: <b>conservar</b>, <b>rehacer</b> o <b>descartar</b>."))
h2("2.2 Veredicto por componente")
add(T(["Componente", "Cómo está hoy", "Problema de fondo", "Veredicto"],
      [["Clientes", "Código, nombre, teléfono y correo. Aparece dentro del menú de Compras.",
        "Sin identidad fiscal, sin tipo de contribuyente, sin dirección ni condiciones de crédito. Está ubicado "
        "en el área equivocada.", "Rehacer"],
       ["Cotizaciones", "Borrador, confirmación, vigencia y cancelación. Precio tecleado en cada línea.",
        "Sin impuestos ni descuentos; el precio no sale de una lista; no verifica existencias ni margen.",
        "Rehacer el modelo; conservar el ciclo de estados"],
       ["Ventas", "Solo pueden nacer de una cotización confirmada. Estados: borrador, confirmada, cancelada.",
        "La cotización obligatoria es un error de diseño. El documento mezcla pedido y factura, no tiene estado "
        "de facturación ni de cobro, no reserva existencias y sus totales carecen de impuestos.", "Rehacer"],
       ["Entregas", "Asignan unidades logísticas completas y descuentan inventario al costo promedio.",
        "Correcto para mayoreo, inservible para mostrador. No emite nota de remisión, no tiene ruta ni "
        "comprobante de recibido, y entrega sin que exista factura.", "Conservar el motor; rehacer el flujo"],
       ["Devoluciones", "Documento con eventos y reingreso a inventario.",
        "No corrige el impuesto, no emite nota de crédito, no reintegra dinero ni ajusta saldo. Una devolución "
        "sin efecto fiscal deja mal declarado el IVA.", "Rehacer"],
       ["Totales", "Subtotal igual a total, en dólares.",
        "Un total sin IVA no es el precio que paga el cliente ni el que se declara.", "Descartar el cálculo"],
       ["Permisos", "Lectura y gestión de ventas, sin separación de funciones.",
        "Quien vende puede también cancelar; no hay roles de cajero, supervisor, facturación ni cobros.",
        "Rehacer"]],
      [0.15, 0.25, 0.40, 0.20]))
h2("2.3 Errores de planteamiento, no solo faltantes")
add(B(["<b>Se construyó el documento antes que la regla fiscal.</b> El modelo de líneas no tiene dónde guardar "
       "naturaleza de la venta, tributos ni descuentos; agregarlos después obliga a migrar todas las tablas.",
       "<b>Una sola entidad «venta» hace de pedido y de factura.</b> En la práctica son documentos distintos, con "
       "numeración, estados y efectos distintos.",
       "<b>El flujo solo imagina la venta corporativa.</b> Cotizar, confirmar, convertir y entregar son cuatro "
       "pasos para algo que en una panadería ocurre en un solo acto.",
       "<b>La confirmación no compromete inventario.</b> Dos vendedores pueden vender la misma existencia.",
       "<b>Los propios manuales lo reconocen.</b> La documentación del bloque de ventas indica que el total «no "
       "debe presentarse como documento fiscal» y que facturación, pagos y devoluciones quedaron fuera."]))
h2("2.4 Qué sí se reutiliza")
add(P("Lo que se conserva no es del módulo de ventas, sino infraestructura común del ERP que ya está probada:"))
add(B(["El motor de inventario, con kardex, lotes, costo promedio y libro inmutable.",
       "El mecanismo de comandos idempotentes, que evita duplicados por doble clic o reconexión.",
       "La bitácora de auditoría y el control de alcance por empresa y sucursal.",
       "El repositorio de documentos, la cola de tareas en segundo plano y la generación de PDF y Excel.",
       "Flota y rastreo, para el reparto."]))
add(NOTEBOX("Consecuencia para el plan.", "Los datos de ventas que hoy existen son de demostración, por lo que no "
            "hay historial real que proteger. Conviene rediseñar el modelo de ventas desde su base en lugar de "
            "parchar el actual; hacerlo ahora es mucho más barato que después de emitir documentos fiscales reales."))

h2("2.5 Base disponible fuera del ERP: el servicio DTE del proyecto de referencia")
add(P("El equipo cuenta con otro proyecto propio, llamado aquí proyecto de referencia, que ya tiene una implementación "
      "amplia de facturación electrónica. Se evaluó con el mismo criterio que el módulo actual: qué se reutiliza, "
      "qué se reescribe y qué le falta para una cadena de panaderías."))
add(T(["Pieza", "Qué contiene", "Decisión"],
      [["Servicio DTE (Node.js, independiente)",
        "Generación de los 11 tipos de documento validada contra los esquemas oficiales, 33 catálogos, numeración "
        "atómica, firma con el firmador de Hacienda, transmisión con la política oficial de reintentos, "
        "contingencia, invalidación, versión legible en PDF con QR y control de duplicados.",
        "Reutilizar: se incorpora al ERP como un servicio más y se adapta."],
       ["Tres modos de operación",
        "Simulado (sin salida de red y con marca «sin validez fiscal»), ambiente de pruebas de Hacienda y "
        "producción, con candados que impiden mezclar ambientes.",
        "Reutilizar tal cual."],
       ["Lógica de negocio del lado de la tienda",
        "Cola de trabajos, emisor con revisiones, notas de crédito, libros de IVA y anexos del F-07. Está escrita "
        "en otro lenguaje y atada a pedidos de comercio electrónico.",
        "Reescribir en el ERP, tomando su diseño y sus reglas como referencia."],
       ["Panel de administración", "Pantallas de documentos, contingencia, invalidación y conexión con Hacienda.",
        "Solo referencia de flujo; la interfaz del ERP es otra."],
       ["Documentación", "Auditoría contra la normativa, guía de anexos F-07, plan de retención del 1 % y manual "
        "de operación.", "Reutilizar como base de los manuales."]],
      [0.22, 0.50, 0.28]))
h3("Lo que esa base no resuelve")
add(B(["<b>No se ha probado contra Hacienda.</b> Por falta de credenciales, todo está validado contra los esquemas "
       "y en modo simulado. La propia auditoría de ese proyecto advierte que cumplir el esquema no garantiza la "
       "aceptación: Hacienda valida además cálculos, fechas y coherencia entre campos.",
       "<b>Solo tres documentos están ejercitados de extremo a extremo</b>: factura, comprobante de crédito fiscal "
       "y nota de crédito. La nota de remisión, la nota de débito y el comprobante de retención tienen generador, "
       "pero no el mismo nivel de prueba.",
       "<b>Es de un solo emisor.</b> El NIT, las credenciales, el certificado, los tipos de documento habilitados "
       "y el modo de operación se fijan al desplegar el servicio, para una única empresa. Indicar el "
       "establecimiento y el punto de venta en cada solicitud solo está disponible para factura, crédito fiscal "
       "y nota de crédito, y la ventana de contingencia es única para todo el servicio. El ERP es multiempresa y "
       "multisucursal, así que esto debe rehacerse (sección 6.5).",
       "<b>Decisiones de negocio ajenas.</b> El proyecto de referencia trata todos sus productos como gravados y solo "
       "emite factura, crédito fiscal y nota de crédito. El ERP no puede heredar esas decisiones: cada empresa "
       "elige qué documentos emite y cómo clasifica sus productos.",
       "<b>Volumen de mostrador sin medir.</b> Transmite documento por documento; debe medirse contra las ventas "
       "diarias de las tiendas y, si hace falta, usar el envío por lotes.",
       "<b>Evento de retorno pendiente.</b> Incluye el esquema oficial, pero no su generador.",
       "<b>Datos en un archivo local.</b> Guarda numeración y documentos en una base propia; el ERP debe conservar "
       "su copia de cada documento y respaldar esa base."]))
add(NOTEBOX("Efecto en el plan.", "La facturación electrónica deja de ser un desarrollo desde cero: los bloques V3 "
            "y V4 pasan a consistir en adaptar ese servicio, conectarlo al ERP y certificarlo. El resto del área "
            "(clientes, precios, pedidos, caja, cobros) no cambia, porque esa base no lo cubre."))

# ---------------- PARTE III ----------------
part("III", "Marco legal y fiscal de El Salvador")
h2("3.1 Normas que gobiernan una venta")
add(T(["Norma", "Qué regula en relación con ventas"],
      [["Ley de Impuesto a la Transferencia de Bienes Muebles y a la Prestación de Servicios (Ley de IVA)",
        "Hecho generador, tasa del 13 %, momento en que se causa el impuesto, operaciones exentas, exportaciones "
        "con tasa 0 %, débito fiscal y ajustes por devoluciones y descuentos."],
       ["Código Tributario", "Documentos que deben emitirse (art. 107 y siguientes), requisitos (art. 114), "
        "documentos electrónicos (art. 119-A y siguientes), libros de IVA (art. 141), retención y percepción de "
        "IVA (arts. 162 y 163), pago a cuenta (art. 151) y sanciones."],
       ["Decreto Legislativo 487 (2022) y reformas de 2024", "Incorporan los Documentos Tributarios Electrónicos al "
        "Código Tributario y ajustan los datos del receptor en facturas de consumidor final."],
       ["Normativa de Cumplimiento de los DTE y Manual Funcional (Hacienda)", "Reglas operativas: tipos de "
        "documento, estructura, plazos de transmisión, contingencia, invalidación y entrega al receptor."],
       ["Ley de Firma Electrónica", "Validez del certificado con que se firma cada DTE."],
       ["Ley de Protección al Consumidor y su reglamento", "Información de precios, garantías, devoluciones, "
        "ventas a plazos, comercio electrónico y reversión de pagos."],
       ["Ley de Impuesto sobre la Renta", "Los ingresos por ventas son la base del pago a cuenta mensual."]],
      [0.36, 0.64]))

h2("3.2 El IVA en la venta")
add(B(["<b>Tasa general: 13 %</b> sobre el precio de venta. Las exportaciones se gravan con tasa 0 %.",
       "<b>Tres naturalezas de venta</b> que el sistema debe distinguir línea por línea: <i>gravada</i>, "
       "<i>exenta</i> y <i>no sujeta</i>. Cada producto necesita su clasificación.",
       "<b>Dos formas de expresar el precio</b>, según el documento: en la factura a consumidor final el precio "
       "<b>incluye</b> el IVA; en el comprobante de crédito fiscal el precio va <b>sin</b> IVA y el impuesto se "
       "muestra por separado.",
       "<b>Débito fiscal.</b> El IVA de las ventas del mes se declara en el formulario F-07, junto con sus anexos "
       "de detalle de ventas."]))
add(T(["Concepto", "Factura (consumidor final)", "Comprobante de crédito fiscal"],
      [["Precio de lista", "$1.13 (IVA incluido)", "$1.00 (sin IVA)"],
       ["Venta gravada", "$1.13", "$1.00"],
       ["IVA", "$0.13, contenido en el precio; se informa en el resumen", "$0.13, sumado aparte"],
       ["Total a pagar", "$1.13", "$1.13"],
       ["Cálculo del IVA", "precio ÷ 1.13 × 0.13", "precio × 0.13"]],
      [0.26, 0.37, 0.37]))
add(Paragraph("Cuadro 1. El mismo producto en los dos documentos más frecuentes.", S["cap"]))

h2("3.3 Retención, percepción y pago a cuenta")
add(T(["Figura", "Cuándo aparece en una venta", "Efecto en el documento"],
      [["Retención de IVA 1 % (art. 162 C.T.)", "El comprador es gran contribuyente (o agente designado) y el "
        "vendedor no lo es. Se aplica sobre el precio sin IVA, en operaciones iguales o superiores a $100.",
        "El cliente paga el total menos el 1 %. El vendedor recibe un comprobante de retención y lo acredita."],
       ["Percepción de IVA 1 % (art. 163 C.T.)", "El vendedor es gran contribuyente y vende bienes a un "
        "contribuyente que no lo es, para su inventario. Operaciones iguales o superiores a $100, sobre el precio "
        "sin IVA.",
        "Se suma el 1 % al total del comprobante de crédito fiscal."],
       ["Pago a cuenta 1.75 % (art. 151 C.T.)", "Todos los meses, sobre los ingresos brutos.",
        "No aparece en el documento; se calcula del total de ventas y se declara en el F-14."]],
      [0.27, 0.40, 0.33]))
add(NOTEBOX("Dato de configuración de cada empresa:", "la categoría de contribuyente (grande, "
            "mediano u otro). De ella depende si el sistema debe calcular percepción en las ventas o esperar "
            "retenciones de sus clientes. El diseño contempla ambas, activables por configuración."))

h2("3.4 Los Documentos Tributarios Electrónicos")
add(P("El DTE es un archivo JSON con firma electrónica que el emisor genera, transmite al Ministerio de Hacienda y "
      "entrega al cliente junto con una versión legible. Hacienda lo valida y devuelve un <b>sello de recepción</b>, "
      "que es lo que le da validez jurídica. Existen once tipos; el área de ventas usa principalmente seis."))
add(T(["Cód.", "Documento", "Uso en ventas", "Prioridad"],
      [["01", "Factura", "Venta a consumidor final. Precios con IVA incluido.", "Alta"],
       ["03", "Comprobante de crédito fiscal", "Venta a otro contribuyente de IVA. Exige NIT y NRC del cliente.", "Alta"],
       ["05", "Nota de crédito", "Devolución, descuento o anulación parcial posterior sobre un crédito fiscal.", "Alta"],
       ["06", "Nota de débito", "Cargo adicional posterior sobre un crédito fiscal.", "Media"],
       ["04", "Nota de remisión", "Traslado de bienes sin factura inmediata: entregas previas a facturar, "
        "consignación, traslados entre sucursales.", "Media"],
       ["11", "Factura de exportación", "Ventas al exterior, tasa 0 %.", "Baja"],
       ["07", "Comprobante de retención", "Lo emite quien retiene. Ventas lo <i>recibe</i> y lo registra.", "Recepción"],
       ["14", "Factura de sujeto excluido", "La emite la empresa al comprar a personas no inscritas en IVA. "
        "Alimenta la casilla 66 del F-07.", "Habilitable"],
       ["08, 09, 15", "Liquidación, documento contable de liquidación y donación", "Casos especiales; la "
        "liquidación alimenta la casilla 108.", "Habilitable"]],
      [0.09, 0.26, 0.47, 0.18]))
add(Paragraph("Cuadro 2. Tipos de DTE según el catálogo de Hacienda y su papel en el área de ventas.", S["cap"]))

h3("Elementos de identificación de todo DTE")
add(T(["Elemento", "Descripción", "Quién lo genera"],
      [["Código de generación", "Identificador UUID versión 4 (36 caracteres, 8-4-4-4-12). Es el número de "
        "trazabilidad en todo el ecosistema.", "El ERP"],
       ["Número de control", "Correlativo por tipo de documento, establecimiento y punto de venta. Formato "
        "habitual: DTE-01-M001P001-000000000000001. Se reinicia cada año.", "El ERP"],
       ["Firma electrónica", "Estándar JSON Web Signature (JWS) con el certificado del contribuyente.", "El ERP, con el firmador"],
       ["Sello de recepción", "Código alfanumérico que Hacienda asigna al aceptar el documento.", "Hacienda"],
       ["Versión legible con código QR", "Representación gráfica (PDF o tiquete). El QR lleva a la consulta "
        "pública del documento en Hacienda.", "El ERP"]],
      [0.24, 0.54, 0.22]))

h3("Ciclo de vida de un DTE")
add(Flow([[("Generar JSON\nsegún esquema", "n"), ("Firmar\n(JWS)", "n"), ("Transmitir\na Hacienda", "n"),
           ("Sello de\nrecepción", "d"), ("Entregar JSON\ny versión legible", "n")],
          [("Rechazado:\ncorregir y reenviar", "a"), ("Sin respuesta:\nconsultar y reintentar", "a"),
           ("Sin conexión:\ncontingencia", "a"), ("Error posterior:\ninvalidación", "a"),
           ("Ajuste posterior:\nnota de crédito/débito", "a")]]))
add(Paragraph("Figura 1. Camino normal de un DTE (arriba) y los cinco desvíos que el módulo debe manejar (abajo).",
              S["cap"]))

h3("Reglas operativas que condicionan el diseño")
add(B(["<b>Transmisión.</b> Hacienda ofrece un servicio uno a uno (síncrono) y otro por lotes (asíncrono). Hay un "
       "ambiente de pruebas y uno de producción, con direcciones distintas, y la autenticación devuelve un token "
       "válido por 24 horas en producción y 48 en pruebas.",
       "<b>Reintentos.</b> El manual técnico pide: si no hay respuesta en 8 segundos, consultar primero el estado "
       "del documento y reenviar como máximo dos veces; si aun así falla, pasar a contingencia.",
       "<b>Contingencia.</b> Ante caída del sistema, de internet o de energía, el documento se genera con tipo de "
       "transmisión «contingencia», se entrega al cliente su versión legible y, al volver el servicio, se envía "
       "primero un <i>evento de contingencia</i> y luego los documentos. El evento debe enviarse dentro de las 24 "
       "horas siguientes al fin de la falla y admite hasta 1,000 documentos; estos se transmiten dentro de las 72 "
       "horas siguientes al sello del evento. El envío por lotes admite hasta 100 documentos por lote y, para "
       "facturación cíclica, se recibe de 10:00 p. m. a 5:00 a. m.; los lotes de contingencia se reciben a "
       "cualquier hora.",
       "<b>Invalidación.</b> Un DTE no se borra: se invalida con un evento firmado. La factura, la factura de "
       "exportación y la de sujeto excluido pueden invalidarse hasta tres meses después de su sello de recepción. "
       "El comprobante de crédito fiscal, las notas de crédito y débito, la nota de remisión y el comprobante de "
       "retención, hasta el décimo día hábil del mes siguiente al período en que obtuvieron el sello. Hacienda no "
       "sella un evento de invalidación fuera de plazo. "
       "Si el error es de datos, primero se emite el documento correcto y luego se invalida el anterior, "
       "vinculándolos.",
       "<b>Corrección de facturas a consumidor final.</b> La nota de crédito se relaciona con comprobantes de "
       "crédito fiscal. Una devolución sobre una factura se resuelve con invalidación o, en la versión 2.0, con el "
       "nuevo <i>evento de retorno</i>, pensado para reembolsos y devolución de envases. Se aplica a facturas ya "
       "selladas dentro de los tres meses siguientes, puede cubrir hasta 50 documentos del mismo tipo y admite "
       "varios eventos sobre una factura mientras su suma no supere el valor de esta. Una factura con un evento "
       "de retorno vigente no puede invalidarse sin invalidar antes el evento.",
       "<b>Datos del consumidor final.</b> El Decreto Legislativo 94 de 2024 reformó los artículos 114 y 119-G "
       "del Código Tributario: no se debe exigir nombre ni documento a una persona natural en compras inferiores "
       "a $25,000, salvo que necesite la factura para deducir el gasto. Sobre ese monto la identificación es "
       "obligatoria, y las personas jurídicas siempre indican su razón social. Exigirla sin corresponder se "
       "sanciona (art. 239-A).",
       "<b>Sin tiquetes.</b> Desde el 1 de enero de 2025 un emisor de DTE no puede usar tiquetes: toda venta a "
       "consumidor final se documenta con factura electrónica. El tiquete de 80 mm del punto de venta es solo la "
       "versión impresa de esa factura.",
       "<b>Rechazos frecuentes.</b> Códigos de establecimiento o punto de venta no registrados en Hacienda, campos "
       "que no siguen el esquema vigente y certificados de firma vencidos.",
       "<b>Conservación.</b> Diez años desde su generación (art. 147 del Código Tributario), con la misma "
       "información, estructura y formato con que se firmaron y transmitieron. La versión legible se conserva en "
       "el mismo formato en que se entregó."]))

h2("3.5 Libros de IVA y declaraciones")
add(B(["<b>Libro de ventas a contribuyentes</b>: un renglón por cada comprobante de crédito fiscal, nota de crédito "
       "y nota de débito, con fecha, número, cliente, NRC, ventas exentas, no sujetas y gravadas, débito fiscal, "
       "percepción y total.",
       "<b>Libro de ventas a consumidor final</b>: resumen diario por establecimiento y punto de venta, con el "
       "rango de documentos del día y las ventas exentas, no sujetas, gravadas y de exportación.",
       "<b>Libro de compras</b>: un renglón por documento de proveedor, con compras exentas y gravadas, "
       "importaciones e internaciones, crédito fiscal, percepción y compras a sujetos excluidos.",
       "<b>Anexos del F-07</b>: ventas a contribuyentes, ventas a consumidor final, compras, documentos anulados "
       "o extraviados y nueve anexos por casilla (66, 108, 161, 162, 163, 169, 170, 171 y 172) con retenciones, "
       "percepciones, anticipos y operaciones por cuenta de terceros. Se cargan a Hacienda en archivos con "
       "formato definido.",
       "<b>F-14</b>: pago a cuenta del 1.75 % sobre ingresos brutos, más retenciones.",
       "<b>Plazo</b>: ambas declaraciones se presentan dentro de los primeros diez días hábiles del mes siguiente."]))

h2("3.6 Protección al consumidor")
add(B(["El precio exhibido al público debe ser el <b>precio total</b> que pagará el consumidor, impuestos incluidos.",
       "Las <b>garantías</b> deben constar por escrito y el proveedor debe llevar un registro de ellas (arts. 33 y "
       "33-A).",
       "En <b>ventas a plazos</b>, el contrato debe detallar intereses, comisiones y condiciones antes de firmarse.",
       "En <b>comercio electrónico</b>, el consumidor tiene derecho de retracto y a la reversión del pago en los "
       "casos del art. 13-D.",
       "Las <b>promociones y ofertas</b> obligan en los términos anunciados: vigencia, condiciones y existencias."]))
add(P("Para una panadería, lo anterior se traduce en precios de mostrador con IVA incluido, vigencia explícita "
      "en las promociones y un procedimiento claro de cambios y devoluciones de producto."))

h2("3.7 Protección de datos personales")
add(P("La Ley para la Protección de Datos Personales (Decreto Legislativo 144 de 2024, reformada por el Decreto "
      "659 de septiembre de 2026) aplica a toda empresa que trate datos de personas naturales, y la supervisa la "
      "Agencia de Ciberseguridad del Estado (ACE). El área de Ventas guardará nombres, NIT, DUI, direcciones, "
      "teléfonos y correos de clientes, así que cada empresa que use el ERP es <i>responsable</i> del tratamiento y "
      "el proveedor del ERP actúa como <i>encargado</i>."))
add(T(["Qué exige la ley", "Qué hace el ERP"],
      [["Informar antes de recolectar, con un aviso de privacidad que diga qué datos se tratan, con qué "
        "fundamento y finalidad, y cómo ejercer los derechos (art. 24).",
        "Aviso de privacidad por empresa, con plantilla editable, enlazado en el registro del cliente, en el "
        "correo del documento y visible en caja."],
       ["Consentimiento expreso y demostrable. No se requiere cuando los datos derivan de una relación "
        "contractual y son necesarios para cumplirla (arts. 26 a 28).",
        "Los datos fiscales para facturar no piden consentimiento. Todo otro uso, como promociones, sí: se "
        "registra por cliente, con fecha, medio y finalidad."],
       ["Tratar solo los datos directamente relacionados con el servicio (art. 32).",
        "Campos mínimos por tipo de cliente. En ventas a consumidor final bajo $25,000 no se pide identificación, "
        "lo que coincide con el Código Tributario."],
       ["Derechos de acceso, rectificación, cancelación, oposición, portabilidad, olvido y limitación, con "
        "respuesta en 20 días hábiles, prorrogables otros 20 (arts. 6 a 14 y 20).",
        "Bandeja de solicitudes de titulares con plazo y responsable, exportación de los datos de un cliente y "
        "registro de cada respuesta."],
       ["Revocar el consentimiento en 5 días hábiles (art. 30).",
        "Baja del consentimiento con fecha; el cliente deja de recibir comunicaciones."],
       ["La supresión no procede si contraviene una obligación legal; en ese caso los datos se bloquean "
        "(arts. 10 y 11).",
        "Los documentos fiscales se conservan diez años por ley. El cliente se anonimiza en el maestro y sus "
        "datos quedan bloqueados dentro de los documentos ya emitidos."],
       ["Medidas de seguridad que garanticen integridad, disponibilidad y confidencialidad (art. 36).",
        "Cifrado, permisos por rol y bitácora de consulta y cambio de datos de clientes, que el ERP ya tiene."],
       ["Notificar toda vulneración a la ACE, a la Fiscalía y a los afectados en 72 horas, y documentarla "
        "(art. 25).", "Registro de incidentes con fecha, datos comprometidos, medidas y constancia de las "
        "notificaciones."],
       ["Transferir datos a otro país solo si este ofrece protección equivalente, con consentimiento del "
        "titular (art. 44).", "La ubicación del servidor es una decisión de cada empresa y se declara en el "
        "aviso de privacidad (sección 7.5)."]],
      [0.50, 0.50]))
add(B(["<b>Sanciones.</b> Multas de 1 a 40 salarios mínimos mensuales del sector comercio, según la gravedad "
       "(art. 57).",
       "<b>Delegado de protección de datos.</b> La reforma de 2026 derogó la obligación de nombrarlo; las "
       "solicitudes las atiende la empresa directamente.",
       "<b>Infraestructura.</b> El Manual Técnico de Hacienda (sección 6.4) restringe además el alojamiento a "
       "países con tratados de extradición y asistencia legal con El Salvador."]))

# ---------------- PARTE IV ----------------
part("IV", "Lógica del proceso de venta")
h2("4.1 El ciclo completo: del pedido al cobro")
add(Flow([[("Cliente y\ncondiciones", "n"), ("Cotización\n(opcional)", "n"), ("Pedido o venta\nconfirmada", "n"),
           ("Entrega y\nsalida de inventario", "n"), ("DTE\nsellado", "d")],
          [("Cobro o cuenta\npor cobrar", "n"), ("Devolución\ny nota de crédito", "a"), ("Cierre de caja\ny depósito", "n"),
           ("Libros de IVA\ny declaración", "n"), ("Contabilidad", "n")]]))
add(Paragraph("Figura 2. Ciclo «del pedido al cobro» que debe cubrir el área de ventas.", S["cap"]))
add(P("Cada documento del ciclo responde una pregunta distinta, y el sistema no debe mezclarlas:"))
add(T(["Documento", "Pregunta que responde", "Afecta"],
      [["Cotización", "¿A qué precio y con qué condiciones ofrezco?", "Nada; es una oferta con vigencia."],
       ["Pedido o venta", "¿Qué me comprometí a entregar?", "Reserva de existencias y demanda."],
       ["Entrega", "¿Qué salió físicamente y cuánto me costó?", "Inventario y costo de ventas."],
       ["DTE", "¿Qué facturé ante Hacienda?", "Ingresos, IVA débito y cuenta por cobrar."],
       ["Cobro", "¿Qué dinero entró y por qué medio?", "Caja, bancos y saldo del cliente."]],
      [0.2, 0.45, 0.35]))

h2("4.2 Los tres canales de venta de la empresa piloto")
add(T(["", "Mostrador", "Pedido o encargo", "Mayoreo y distribución"],
      [["Cliente típico", "Consumidor final, anónimo", "Consumidor final identificado", "Negocios: tiendas, cafeterías, empresas"],
       ["Documento", "Factura", "Factura", "Comprobante de crédito fiscal"],
       ["Precio", "Con IVA incluido", "Con IVA incluido", "Sin IVA; lista de mayoreo"],
       ["Pago", "Inmediato: efectivo, tarjeta, transferencia", "Anticipo y saldo a la entrega", "Crédito a 8, 15 o 30 días"],
       ["Entrega", "En el acto", "Fecha y hora pactadas", "Ruta con vehículo de reparto"],
       ["Velocidad exigida", "Segundos por venta", "Minutos", "No crítica"],
       ["Inventario", "Unidad suelta de vitrina", "Producto reservado o por producir", "Cajas o bandejas completas"]],
      [0.19, 0.25, 0.26, 0.30]))
add(Paragraph("Cuadro 3. Diferencias que obligan a tratar cada canal con un flujo propio.", S["cap"]))

h2("4.3 Cómo se decide qué documento emitir")
add(B(["Si el cliente es contribuyente de IVA y pide crédito fiscal → <b>comprobante de crédito fiscal</b>. Requiere "
       "NIT, NRC, nombre o razón social, actividad económica y dirección.",
       "Si el cliente es consumidor final → <b>factura</b>. Sin datos de identificación por debajo de $25,000, "
       "salvo que el cliente los solicite.",
       "Si la mercadería sale antes de facturarse o no hay venta → <b>nota de remisión</b>.",
       "Si el cliente está en el exterior → <b>factura de exportación</b>."]))
add(P("Esta decisión debe tomarla el sistema a partir del tipo de cliente y permitir al cajero cambiarla solo "
      "entre opciones válidas. Un crédito fiscal emitido a quien no tiene NRC es rechazado por Hacienda."))

h2("4.4 Momento en que se causa el impuesto")
add(P("En la venta de bienes, el IVA se causa cuando ocurre lo primero entre: emitir el documento, entregar el bien "
      "o recibir el pago. Dos consecuencias prácticas para el diseño:"))
add(B(["Un <b>anticipo</b> por un encargo obliga a documentar esa parte en el momento en que se recibe.",
       "Una <b>entrega sin factura</b> debe ir amparada por una nota de remisión y facturarse dentro del mismo "
       "período tributario."]))

h2("4.5 Reglas de cálculo que el sistema debe garantizar")
add(B(["Los montos por línea se calculan con el número de decimales que admite el esquema del DTE y los totales "
       "se redondean a dos decimales. La suma de las líneas debe coincidir con el resumen; de lo contrario Hacienda "
       "rechaza el documento.",
       "El descuento puede ser por línea o global, y debe distinguirse si afecta ventas gravadas, exentas o no "
       "sujetas.",
       "El total en letras es un campo obligatorio.",
       "La condición de la operación (contado, crédito u otra) y la forma de pago, con su plazo si es crédito, "
       "forman parte del documento.",
       "El servidor es la única fuente de verdad de los cálculos, como ya ocurre en cotizaciones."]))

# ---------------- PARTE V ----------------
part("V", "Módulos propuestos y contenido de cada uno")
add(P("Se proponen diez módulos. Para cada uno se indica su propósito, la información que maneja, sus reglas "
      "principales y cómo se conecta con el resto del ERP."))
add(T(["N.º", "Módulo", "Propósito en una línea"],
      [["1", "Clientes", "Saber a quién se vende y qué documento le corresponde."],
       ["2", "Precios, impuestos y promociones", "Que el precio y el impuesto salgan del sistema, no del vendedor."],
       ["3", "Cotizaciones y pedidos", "Registrar ofertas y compromisos de entrega."],
       ["4", "Punto de venta y caja", "Vender en mostrador en segundos y cuadrar el dinero."],
       ["5", "Facturación electrónica (DTE)", "Emitir el documento legal y obtener el sello de Hacienda."],
       ["6", "Entregas y despacho", "Sacar la mercadería y llevarla al cliente."],
       ["7", "Devoluciones, notas de crédito y débito", "Corregir una venta con efecto fiscal e inventario."],
       ["8", "Cuentas por cobrar y cobros", "Controlar el crédito y registrar los pagos."],
       ["9", "Fiscal: libros de IVA y F-07 completo", "Generar los tres libros y todos los anexos de la declaración."],
       ["10", "Análisis comercial", "Medir ventas, márgenes y desempeño."]],
      [0.08, 0.34, 0.58]))


def modulo(n, nombre, proposito, lleva, reglas, integra):
    h2("5.%s %s" % (n, nombre))
    add(P("<b>Propósito.</b> " + proposito))
    h3("Qué lleva")
    add(B(lleva))
    h3("Reglas principales")
    add(B(reglas))
    add(P("<b>Integración.</b> " + integra))


modulo(1, "Clientes",
       "Construir un maestro de clientes con identidad fiscal y condiciones comerciales, ubicado en el área de Ventas.",
       ["Tipo de cliente: consumidor final, contribuyente de IVA, gran contribuyente, exportación, gobierno.",
        "Identificación: tipo y número de documento (DUI, NIT, pasaporte, carné de residente), NRC, nombre o razón "
        "social y nombre comercial.",
        "Actividad económica según el catálogo de Hacienda, y dirección con departamento, distrito y municipio "
        "según los catálogos territoriales vigentes.",
        "Contactos y correo para recibir los DTE.",
        "Condiciones comerciales: lista de precios, plazo de crédito, límite de crédito, vendedor y ruta asignados.",
        "Direcciones de entrega, con coordenadas para el módulo de rastreo.",
        "Un cliente genérico «Consumidor final» por sucursal para la venta de mostrador."],
       ["NIT y NRC se validan en formato y no se repiten dentro de la empresa.",
        "Un cliente solo puede recibir crédito fiscal si tiene NRC, actividad económica y dirección completas.",
        "Los datos fiscales se copian a cada documento al emitirlo; cambiar el cliente después no altera documentos "
        "ya emitidos.",
        "Desactivar un cliente conserva su historial y bloquea nuevas ventas."],
       "Alimenta cotizaciones, punto de venta, DTE y cuentas por cobrar. Reutiliza el patrón de maestro ya usado en "
       "proveedores.")

modulo(2, "Precios, impuestos y promociones",
       "Que el precio, el descuento y el impuesto de cada línea los determine el sistema con reglas auditables.",
       ["Listas de precios con vigencia: mostrador, mayoreo, institucional y las que la empresa defina; por "
        "sucursal cuando el precio cambie entre tiendas.",
        "Precio por producto y unidad de venta, indicando si incluye IVA.",
        "Clasificación fiscal de cada producto: gravado, exento o no sujeto, y su código de tributo.",
        "Descuentos por línea, por cliente y por volumen, con tope según el rol.",
        "Promociones con fecha de inicio y fin, sucursales y condiciones (2×1, combos, precio especial por horario).",
        "Configuración fiscal de la empresa: categoría de contribuyente, percepción y retención activas, montos "
        "mínimos."],
       ["El precio de lista se propone automáticamente; cambiarlo exige permiso y deja rastro.",
        "No se vende por debajo del costo promedio sin autorización explícita.",
        "Un cambio de precio nunca modifica documentos confirmados.",
        "El motor de cálculo es único y lo comparten cotización, pedido, punto de venta y DTE."],
       "Toma el costo promedio del módulo de valoración para mostrar el margen. Los precios de mostrador se publican "
       "con IVA incluido, como exige la protección al consumidor.")

modulo(3, "Cotizaciones y pedidos",
       "Rediseñar el tramo entre ofrecer y entregar, separando la oferta, el compromiso y la factura.",
       ["Cotización rediseñada: precios de lista, impuestos, descuentos, vigencia y margen visible para quien autoriza.",
        "Pedido de venta: compromiso con fecha y lugar de entrega, que puede nacer de una cotización o directamente.",
        "Encargos de mostrador (por ejemplo, pasteles): descripción, fecha de retiro, anticipo y saldo.",
        "Reserva de existencias al confirmar el pedido.",
        "Versión imprimible y envío por correo de la cotización."],
       ["La cotización deja de ser obligatoria: una venta puede crearse sin ella.",
        "Un pedido a crédito se confirma solo si el cliente tiene cupo disponible y no tiene saldos vencidos, o con "
        "autorización.",
        "El anticipo de un encargo genera su documento fiscal al recibirse.",
        "El pedido es un documento distinto de la factura: tiene su propia numeración y sus estados de entrega, "
        "facturación y cobro.",
        "Toda cancelación exige motivo y libera las reservas."],
       "El pedido confirmado alimenta la demanda por sucursal que ya usa Compras y, más adelante, la planificación de "
       "producción.")

modulo(4, "Punto de venta y caja",
       "Vender en mostrador con rapidez, cobrar por varios medios y cuadrar el efectivo de cada turno.",
       ["Pantalla de venta rápida: búsqueda por nombre o código, lector de código de barras, botones de productos "
        "frecuentes y teclado numérico. Pensada para pantalla táctil.",
        "Cobro con uno o varios medios en la misma venta: efectivo con cálculo de vuelto, tarjeta, transferencia, "
        "billetera electrónica y vales.",
        "Emisión inmediata de la factura electrónica e impresión del tiquete con código QR.",
        "Caja y turnos: apertura con fondo inicial, entradas y salidas de efectivo, retiros parciales, corte "
        "parcial y cierre con arqueo por denominación.",
        "Registro de sobrantes y faltantes, y del depósito bancario del día.",
        "Punto de venta registrado ante Hacienda: cada caja tiene su código de establecimiento y de punto de venta."],
       ["No se vende sin un turno de caja abierto a nombre del cajero.",
        "La venta de mostrador descuenta inventario al cobrarse, desde la existencia de vitrina de la sucursal.",
        "Si Hacienda no responde, la caja sigue vendiendo en contingencia. Si la tienda pierde su conexión, "
        "opera con el enlace de respaldo o con su nodo local (sección 6.9).",
        "Anular una venta ya cobrada exige autorización de supervisor y sigue las reglas de invalidación.",
        "El cierre de caja no se puede modificar una vez aprobado."],
       "Es el módulo que más exige al inventario. Hoy la entrega asigna unidades logísticas completas; el mostrador "
       "necesita una «existencia de vitrina» que se alimenta abriendo una unidad logística y se descuenta por pieza. "
       "Esta decisión se detalla en la Parte VI.")

modulo(5, "Facturación electrónica (DTE)",
       "Emitir, firmar, transmitir y conservar los documentos tributarios conforme a la normativa de Hacienda.",
       ["Perfil de emisor por empresa: datos fiscales, actividad económica, ambiente (simulado, pruebas o "
        "producción), credenciales y certificado de firma, aislados de las demás empresas.",
        "Establecimientos por sucursal y puntos de venta por caja, cada uno con el tipo y los códigos que "
        "Hacienda le asignó.",
        "Tipos de documento habilitados por empresa: cada una activa solo los que emite, y el sistema no ofrece "
        "los demás.",
        "Generación del JSON por tipo de documento según el esquema vigente (versión 2.0), con sus catálogos.",
        "Numeración: código de generación y número de control por tipo, establecimiento, punto de venta y año.",
        "Firma, transmisión, consulta de estado y reintentos automáticos.",
        "Contingencia: emisión sin conexión, evento de contingencia y envío posterior por lotes.",
        "Invalidación y, en la versión 2.0, evento de retorno.",
        "Versión legible en PDF carta y en tiquete de 80 mm, con código QR.",
        "Envío al cliente del JSON y el PDF por correo, y descarga desde el sistema.",
        "Bandeja de documentos con su estado: pendiente, sellado, rechazado, en contingencia o invalidado.",
        "Catálogos de Hacienda versionados dentro del sistema."],
       ["Un documento sellado es inmutable; cualquier corrección es otro documento o un evento.",
        "Un DTE rechazado nunca se entrega al cliente; se corrige y se reenvía con el mismo código de generación.",
        "El número de control jamás se reutiliza ni deja huecos sin explicación.",
        "El certificado y las credenciales se guardan cifrados y nunca se muestran en pantalla ni en registros.",
        "El sistema avisa antes del vencimiento del certificado y de las credenciales.",
        "Se guarda el JSON firmado y la respuesta de Hacienda por al menos diez años."],
       "Se alimenta de ventas, punto de venta y devoluciones. La transmisión corre en la cola de tareas que el ERP "
       "ya tiene, para no bloquear al cajero. Su núcleo técnico parte del servicio DTE del proyecto de referencia (sección 2.5), "
       "adaptado a varias sucursales y puntos de venta.")

modulo(6, "Entregas y despacho",
       "Rehacer el flujo de entrega para que salga amparado por un documento fiscal y llegue con constancia de "
       "recibido, reutilizando el motor de inventario.",
       ["Preparación del pedido con asignación de unidades logísticas, lote y vencimiento, sobre el motor de inventario.",
        "Nota de remisión electrónica cuando la mercadería sale antes de facturarse.",
        "Hoja de ruta de reparto: pedidos del día por vehículo y conductor, usando Flota y rastreo.",
        "Comprobante de entrega: quién recibió, firma o fotografía, y diferencias anotadas."],
       ["Primero vence, primero sale, para producto perecedero.",
        "Nada sale de la bodega sin factura o nota de remisión que lo ampare, incluidos los traslados entre "
        "sucursales (sección 6.8).",
        "Una entrega confirmada no se edita; se corrige con devolución.",
        "El despacho revalida la aptitud del vehículo y del conductor, como en traslados."],
       "Reutiliza el motor de traslados y de flota. La salida sigue registrándose en el kardex como «Venta».")

modulo(7, "Devoluciones, notas de crédito y débito",
       "Dar efecto fiscal y financiero a la devolución que hoy solo mueve inventario.",
       ["Devolución rediseñada: siempre parte del documento fiscal de origen y de sus líneas.",
        "Nota de crédito electrónica para devoluciones, descuentos posteriores y anulaciones parciales sobre "
        "comprobantes de crédito fiscal.",
        "Nota de débito electrónica para cargos posteriores.",
        "Para facturas a consumidor final: invalidación dentro del plazo o evento de retorno.",
        "Destino del producto devuelto: vuelve a la venta, cuarentena o baja por merma.",
        "Forma de reintegro: efectivo, reversión a tarjeta, saldo a favor o cambio de producto."],
       ["No se devuelve más de lo facturado ni se acredita más que el saldo del documento.",
        "La nota de crédito debe emitirse dentro del plazo que la ley permite para ajustar el débito fiscal.",
        "El producto perecedero devuelto no regresa a la venta sin inspección.",
        "Todo reintegro de efectivo pasa por un turno de caja abierto."],
       "Reingresa inventario con el costo de la salida original, ajusta la cuenta por cobrar y alimenta el libro de "
       "ventas.")

modulo(8, "Cuentas por cobrar y cobros",
       "Controlar las ventas a crédito desde que se facturan hasta que se cobran.",
       ["Estado de cuenta por cliente, con cada documento, su vencimiento y su saldo.",
        "Recibo de cobro aplicable a uno o varios documentos, con pagos parciales.",
        "Registro de retenciones de IVA recibidas, con el número del comprobante de retención del cliente.",
        "Anticipos y saldos a favor.",
        "Antigüedad de saldos: por vencer, 1 a 30, 31 a 60, 61 a 90 y más de 90 días.",
        "Gestión de cobro: recordatorios, notas de seguimiento y bloqueo por mora."],
       ["El límite de crédito se evalúa al confirmar el pedido y al facturar.",
        "Un cobro nunca excede el saldo del documento; el excedente pasa a saldo a favor.",
        "La retención del 1 % reduce el saldo sin ser un ingreso de dinero.",
        "Anular un cobro exige motivo y restituye el saldo."],
       "Recibe los documentos a crédito de facturación y los cobros del punto de venta. Es la base de una futura "
       "conciliación bancaria y de la contabilidad.")

modulo(9, "Fiscal: libros de IVA y F-07 completo",
       "Generar, sin trabajo manual, los tres libros de IVA y todos los anexos de la declaración mensual, para "
       "cada empresa.",
       ["Libro de ventas a contribuyentes, libro de ventas a consumidores y libro de compras, por empresa y período.",
        "Anexos de ventas a contribuyentes, de ventas a consumidor final y de compras.",
        "Anexos por casilla: 66, 108, 161, 162, 163, 169, 170, 171 y 172.",
        "Detalle de documentos anulados, invalidados o extraviados.",
        "Listado de contribuyentes: clientes y proveedores con NRC o NIT.",
        "Clasificación de renta que los anexos exigen desde 2025: tipo de operación, tipo de ingreso, "
        "clasificación, sector y tipo de costo o gasto.",
        "Salida en un libro de Excel con las mismas hojas, columnas y orden de la plantilla estándar, y en los "
        "archivos de carga de Hacienda.",
        "Resumen mensual con débito y crédito fiscal, retenciones, percepciones y base del pago a cuenta.",
        "Conciliación entre documentos sellados, ventas y compras registradas."],
       ["Cada documento se anota en su libro dentro de los diez días hábiles siguientes a su emisión o recibo. "
        "Los emitidos en contingencia se anotan aunque aún no tengan sello (art. 141 del Código Tributario); a "
        "los anexos del F-07 van con su sello.",
        "Cada empresa activa las hojas que le aplican; las demás no se muestran ni se generan.",
        "Un período cerrado no admite documentos nuevos con esa fecha.",
        "Los reportes se generan de los documentos fiscales, no de las ventas ni de las compras internas.",
        "Los anexos no admiten montos negativos: la nota de crédito va con su tipo (05) y montos positivos, y es "
        "el portal de Hacienda quien la resta. La única excepción son los documentos anulados en el anexo de "
        "consumidor final.",
        "Lo que el contador corrija se registra en el ERP, no en el Excel, para que el siguiente mes salga bien."],
       "Lee de ventas, compras y cobros, por lo que deja de ser exclusivo de Ventas. Depende del módulo 5 y de "
       "del registro único de documentos de proveedor, que hoy no existe.")
h3("Hojas de la plantilla y origen de cada dato")
add(P("La referencia es la plantilla «Plantillas IVA F-07», versión 11.7.4, que es la que usan los contadores. El "
      "ERP debe producir cada hoja con sus mismas columnas:"))
add(T(["Hoja", "Contenido", "Origen en el ERP"],
      [["Anexo contribuyentes", "Créditos fiscales y notas emitidos, uno por renglón.", "Documentos fiscales emitidos."],
       ["Anexo consumidor final", "Facturas emitidas, resumidas por día y rango.", "Documentos fiscales emitidos."],
       ["Anexo de compras", "Documentos de proveedores con crédito fiscal.", "Documentos de proveedor de compras, flota y gastos generales."],
       ["Casilla 66", "Compras a sujetos excluidos.", "Facturas de sujeto excluido emitidas al comprar."],
       ["Casilla 108", "Ventas gravadas por cuenta de terceros.", "Comprobantes de liquidación."],
       ["Casilla 161", "Anticipo del 2 % que le aplicaron a la empresa.", "Liquidaciones de cobros con tarjeta."],
       ["Casilla 162", "Retención del 1 % que le hicieron sus clientes.", "Comprobantes de retención recibidos, en cobros."],
       ["Casilla 163", "Percepción del 1 % que le cobraron sus proveedores.", "Compras a grandes contribuyentes."],
       ["Casilla 169", "Percepción del 1 % que la empresa cobró.", "Créditos fiscales emitidos con percepción."],
       ["Casilla 170", "Retención del 1 % que la empresa hizo.", "Comprobantes de retención emitidos."],
       ["Casilla 171", "Anticipo del 2 % que la empresa aplicó.", "Solo emisores o administradores de tarjetas."],
       ["Casilla 172", "Retención del 13 % a terceros.", "Comprobantes de retención emitidos."],
       ["Detalle de documentos", "Anulados, invalidados o extraviados.", "Eventos de invalidación."],
       ["Libro de contribuyentes", "Libro legal de ventas a contribuyentes.", "Igual que su anexo."],
       ["Libro de consumidor final", "Libro legal de ventas a consumidores.", "Igual que su anexo."],
       ["Libro de compras", "Libro legal de compras.", "Igual que el anexo de compras y la casilla 66."],
       ["Contribuyentes", "Catálogo de NRC o NIT y nombre.", "Clientes y proveedores."]],
      [0.22, 0.40, 0.38]))
h3("Contraste con el manual oficial de Hacienda")
add(P("Las columnas de la plantilla se compararon con el «Manual de usuario para carga de archivo de los anexos "
      "de la declaración del IVA», F-07 versión 14 (enero de 2025), de la DGII. Resultado:"))
add(B(["<b>Las columnas coinciden.</b> Los doce anexos de carga y el de documentos anulados tienen en la "
       "plantilla el mismo número de columnas y el mismo orden que en el manual: 20 en contribuyentes, 23 en "
       "consumidor final, 21 en compras, 15 en la casilla 108, 13 en la 66, 8 en la 161, 9 en la 162, la 163 y la "
       "171, y 10 en la 169, la 170, la 172 y en anulados.",
       "<b>Los libros no están en el manual.</b> El manual solo regula los anexos. Los tres libros de IVA se "
       "rigen por el artículo 141 del Código Tributario y los artículos 82 a 88 de su reglamento, que se "
       "contrastan más abajo.",
       "<b>El manual trae cinco anexos que la plantilla omite</b>, todos de sectores específicos: tres de "
       "combustibles (tasas diferenciadas, descuento por precio máximo y anexo 17 de importadores) y dos del "
       "Decreto 357 (ventas internas exentas no sujetas a proporcionalidad y compras internas exentas). Quedan "
       "fuera del alcance, como hojas que una empresa podría habilitar más adelante."]))
add(T(["Regla del manual", "Qué implica para el ERP"],
      [["Archivo CSV separado por punto y coma, sin encabezados ni celdas combinadas, con nombre de hasta 25 "
        "caracteres y todo en formato de texto.", "El generador produce los archivos de carga además del Excel."],
       ["Montos con dos decimales; 0.00 cuando no hay operación, nunca vacíos ni negativos.",
        "Validación antes de generar; el archivo se rechaza si falta un monto."],
       ["La última columna de cada línea lleva el número del anexo.", "Se fija por hoja, no lo teclea el usuario."],
       ["DTE en anexos de detalle: clase 4; número de resolución = número de control sin guiones; serie = sello "
        "de recepción; número de documento = código de generación sin guiones.",
        "Salen del documento fiscal sellado, sin captura manual."],
       ["Consumidor final con DTE: una línea por día, con el código de generación del primer y del último "
        "documento; resolución, serie y control interno llevan «N/A».", "Agrupación diaria automática."],
       ["Anulados con DTE: tipo de detalle «D», rangos en cero y código de generación de 36 caracteres.",
        "Sale de los eventos de invalidación."],
       ["Columnas de renta: obligatorias desde enero de 2025 en ventas y desde febrero de 2024 en compras; «0» "
        "en períodos anteriores.", "La clasificación de renta se configura por empresa, producto y proveedor."],
       ["Compras con DTE: clase 4 para crédito fiscal, notas y exportación; las importaciones toman el valor de "
        "la declaración de mercancías.", "Compras debe guardar el tipo de documento y el origen de la compra."],
       ["Los documentos emitidos ya no se cargan: el portal los arma con los anexos de ventas y de las casillas "
        "169 a 172.", "Solo se genera el archivo de anulados y extraviados."]],
      [0.55, 0.45]))
h3("Formato legal de los libros de IVA")
add(P("Las columnas de los tres libros se compararon con el artículo 141 del Código Tributario y con los artículos "
      "82 a 88 de su Reglamento de Aplicación (Decreto Ejecutivo 117 de 2001), que fijan las columnas y su orden."))
add(T(["Libro", "Qué exige la norma", "Resultado frente a la plantilla"],
      [["Ventas a consumidores (art. 83)", "Fecha; primer y último documento del día; número de caja o sistema; "
        "ventas exentas; gravadas locales; exportaciones; total diario; ventas por cuenta de terceros. Al cierre, "
        "resumen del débito fiscal.", "Las ocho columnas coinciden. El ERP añade lo que el artículo 141 pide "
        "para DTE: código de generación inicial y final, rango de número de control y establecimiento."],
       ["Ventas a contribuyentes (art. 85)", "Correlativo; fecha y número del documento; número de formulario "
        "único; nombre y NRC del cliente; ventas exentas; gravadas; débito fiscal; ventas y débito por cuenta de "
        "terceros; impuesto percibido; total. Al cierre, resumen de ventas y débito.",
        "Coincide. El ERP añade para DTE el código de generación, el número de control y el NIT del cliente."],
       ["Compras (art. 86)", "Correlativo; fecha y número del documento; NRC del proveedor; NIT o DUI del sujeto "
        "excluido; nombre; compras exentas y gravadas, separando locales, importaciones e internaciones; crédito "
        "fiscal; total; retención a terceros; compras a sujetos excluidos.",
        "La plantilla omite el NIT o DUI del sujeto excluido y la retención a terceros, y en su lugar trae el "
        "anticipo percibido. El ERP incluye las tres columnas."],
       ["Detalle de exportaciones (art. 84)", "Correlativo, fecha, número de factura, cliente del exterior, "
        "declaración de mercancías y valor.", "La plantilla no lo trae. Se genera solo para empresas que exportan."]],
      [0.20, 0.44, 0.36]))
add(B(["<b>Requisitos de forma</b> (arts. 82 y 88 del reglamento y 141 del Código): cada folio lleva el nombre y "
       "el NRC del contribuyente y un número correlativo; el libro se totaliza al cierre de cada mes con el "
       "nombre y la firma del contador; y las hojas deben estar autorizadas, numeradas y selladas por un "
       "contador público. El ERP imprime sobre esas hojas foliadas o genera el PDF con el folio que corresponda.",
       "<b>Documentos anulados</b> (art. 87): un ajuste que disminuye o anula una factura se anota en el libro "
       "de ventas a consumidores del mes en que ocurre, restando su valor.",
       "<b>Orden y atraso</b>: las anotaciones son diarias y cronológicas, con un atraso máximo de diez días "
       "hábiles."]))
h3("Documentos de proveedor: todo gasto entra al libro")
add(P("El libro de compras no es solo de mercadería: incluye todo documento de proveedor que traslade crédito "
      "fiscal. Hoy el ERP registra gastos en seis lugares y en ninguno guarda el documento fiscal; el comprobante "
      "es solo un archivo adjunto, así que el sistema sabe cuánto se gastó pero no puede separar el IVA."))
add(T(["Dónde se registra el gasto", "Qué guarda hoy", "Qué le falta"],
      [["Compras de mercadería", "Número y fecha de la factura del proveedor y un monto de impuesto.",
        "Clase y tipo de documento, separación de montos y clasificación de renta."],
       ["Gastos de órdenes de compra", "Tipo de gasto, monto, referencia y adjuntos.", "Proveedor y documento."],
       ["Costos de retaceo (fletes, aduana, seguros)", "Clasificación, monto y adjuntos.", "Proveedor y documento."],
       ["Cargas de combustible (Flota)", "Litros, monto total, estación, proveedor opcional y recibo.",
        "Documento, IVA separado, FOVIAL y COTRANS."],
       ["Órdenes de mantenimiento (Flota)", "Taller, proveedor opcional, costo y recibo.", "Documento e IVA."],
       ["Costos de flota", "Categoría, monto, proveedor opcional y adjunto.", "Documento e IVA."],
       ["Gastos generales (alquiler, energía, teléfono, honorarios)", "No tienen dónde registrarse.",
        "Una pantalla propia."]],
      [0.32, 0.38, 0.30]))
add(P("La solución es un registro único de <b>documento recibido de proveedor</b>. Cada módulo se enlaza a ese "
      "registro en lugar de guardar su propia copia, y los libros y anexos leen de un solo lugar, de modo que "
      "un documento nunca se cuenta dos veces."))
add(B(["<b>Qué guarda.</b> Clase y tipo de documento, número o código de generación y sello, proveedor con NRC o "
       "NIT, fecha, montos gravados, exentos y no sujetos, IVA, percepción, retención practicada, otros tributos, "
       "forma de pago y clasificación de renta.",
       "<b>Captura.</b> Al recibir el DTE del proveedor (JSON y sello) los datos se toman sin teclearlos; para "
       "documentos en papel se capturan a mano.",
       "<b>Enlace.</b> Un documento puede cubrir varias cargas de combustible o varios gastos, y un gasto no se "
       "aprueba como deducible sin documento.",
       "<b>Combustible.</b> La factura lleva FOVIAL ($0.20 por galón) y COTRANS ($0.10 por galón) como tributos "
       "aparte, que no son crédito fiscal. El registro los separa para que el IVA salga exacto.",
       "<b>Importaciones.</b> El documento es la declaración de mercancías y el IVA es el pagado en aduana."]))
h3("Cuándo el crédito fiscal es deducible")
add(P("Que un gasto tenga IVA no significa que se pueda deducir. Los artículos 65 y 65-A de la Ley de IVA fijan "
      "las condiciones, y el ERP las aplica al registrar el documento:"))
add(T(["Regla de la ley", "Qué hace el ERP"],
      [["Solo es deducible el IVA de un comprobante de crédito fiscal a nombre de la empresa, con el impuesto "
        "separado del precio y anotado en el libro de compras (art. 65).",
        "Una factura de consumidor final entra como gasto, pero sin crédito fiscal."],
       ["El gasto debe ser indispensable para el giro del negocio (art. 65).",
        "Cada tipo de gasto lleva una marca de deducible, parcial o no deducible, que define el contador."],
       ["La compra de mercadería debe estar además en el registro de control de inventarios (art. 65).",
        "Ya se cumple: la recepción de compras alimenta el kardex con referencia al documento."],
       ["Vehículos: el IVA de su compra, mantenimiento, combustible, repuestos y seguros no es deducible si el "
        "vehículo no es indispensable para el giro, y lo es al 50 % si se usa también en actividades ajenas "
        "(art. 65-A).",
        "Cada vehículo de Flota tiene un uso fiscal: 100 %, 50 % o no deducible. Sus gastos heredan ese "
        "porcentaje."],
       ["No son deducibles alimentos, hoteles, boletos aéreos, prendas y bebidas ajenos al giro, ni gastos "
        "personales (art. 65-A).", "Tipos de gasto marcados como no deducibles por defecto."],
       ["Desde 58 salarios mínimos, el pago debe hacerse con cheque, transferencia o tarjeta (art. 65-A).",
        "El documento guarda la forma de pago y avisa cuando el monto exige un medio bancario."],
       ["El emisor debe estar inscrito como contribuyente (art. 65-A).",
        "El proveedor debe tener NRC registrado para que su documento genere crédito."],
       ["El IVA no deducible forma parte del costo del bien o del gasto (art. 65).",
        "El costo de flota y el retaceo toman el monto con IVA cuando no es deducible, y sin IVA cuando sí."]],
      [0.52, 0.48]))
add(P("Una panadería que vende solo productos gravados deduce todo su crédito deducible. Si una empresa tiene "
      "además ventas exentas o no sujetas, el artículo 66 obliga a deducirlo en proporción; el resumen mensual "
      "calcula esa proporción."))
h3("Dónde se decide la deducibilidad")
add(P("La decisión es del contador, pero se toma dentro del ERP, sin tocar código:"))
add(B(["<b>Uso fiscal del vehículo.</b> Es un campo de la ficha del vehículo en Flota, con tres opciones: "
       "indispensable para el giro (100 %), uso mixto (50 %) o ajeno al giro (no deducible). Sus cargas de "
       "combustible, mantenimientos, repuestos y seguros heredan ese porcentaje al registrarse.",
       "<b>Marca por tipo de gasto.</b> El catálogo de tipos de gasto, que ya existe, recibe una marca por tipo: "
       "deducible, parcial o no deducible. Los casos que la ley excluye vienen como no deducibles por defecto y "
       "cada empresa puede ajustarlos.",
       "<b>Excepción por documento.</b> Al registrar un documento concreto, quien tenga el permiso puede "
       "corregir la marca heredada dejando el motivo. Cubre el caso atípico sin cambiar la configuración.",
       "<b>Permiso propio.</b> Cambiar estas marcas mueve el IVA que se declara. Solo pueden hacerlo los roles "
       "Contador y Administrador fiscal.",
       "<b>Bitácora.</b> Cada cambio queda registrado con usuario, fecha, motivo y valor anterior.",
       "<b>Sin efecto hacia atrás.</b> Un cambio aplica a los gastos nuevos. Los ya anotados en un período "
       "cerrado no se recalculan; corregirlos exige reabrir el período con autorización."]))

modulo(10, "Análisis comercial",
       "Dar a gerencia y a cada tienda una lectura clara del desempeño.",
       ["Ventas por día, hora, sucursal, cajero, canal, cliente, categoría y producto.",
        "Margen bruto por producto y sucursal: precio de venta contra costo promedio de salida.",
        "Tiquete promedio, número de transacciones y productos más y menos vendidos.",
        "Mermas y devoluciones como porcentaje de la venta.",
        "Cumplimiento de metas por sucursal."],
       ["Las cifras de ingresos se muestran sin IVA.",
        "El costo solo lo ven los roles autorizados, como hoy.",
        "Cada usuario ve únicamente las sucursales de su alcance."],
       "Se integra al tablero existente. No requiere datos nuevos: aprovecha lo que registran los demás módulos.")

# ---------------- PARTE VI ----------------
part("VI", "Lineamientos de diseño técnico")
h2("6.1 Principios")
add(B(["<b>Separar lo comercial de lo fiscal.</b> La venta es un documento interno; el DTE es un documento legal "
       "con su propio ciclo. Una venta puede tener varios DTE (factura, nota de crédito) y un DTE puede fallar sin "
       "perder la venta.",
       "<b>Inmutabilidad.</b> Un DTE sellado, un cobro aplicado y un cierre de caja no se editan; se corrigen con "
       "documentos nuevos. El ERP ya aplica este criterio al libro de inventario.",
       "<b>Copia de datos al emitir.</b> El documento guarda los datos del cliente, del producto y del precio tal "
       "como eran en ese momento.",
       "<b>Idempotencia.</b> Cobrar, facturar y transmitir usan claves de comando, como ya hacen ventas y "
       "entregas, para que un doble clic o una reconexión no dupliquen nada.",
       "<b>Configuración antes que código.</b> Tasas, montos mínimos, plazos y catálogos viven en tablas "
       "versionadas, porque la normativa cambia varias veces al año.",
       "<b>Multiemisor desde el diseño.</b> Nada de la facturación se fija para una empresa. Cada empresa es un "
       "emisor independiente, con sus datos, credenciales, documentos habilitados y numeración aislados de las "
       "demás, y cada sucursal y caja tiene sus propios códigos ante Hacienda."]))

h2("6.2 Entidades nuevas principales")
add(T(["Grupo", "Entidades", "Notas"],
      [["Clientes", "Datos fiscales del cliente, direcciones, contactos, condiciones de crédito",
        "Sustituye a la tabla actual de clientes."],
       ["Precios", "Listas de precios, precios por producto y unidad, reglas de descuento, promociones",
        "Con vigencias; nunca se sobrescribe un precio histórico."],
       ["Fiscal", "Perfil de emisor por empresa, establecimientos, puntos de venta, tipos de documento "
        "habilitados, catálogos de Hacienda, clasificación fiscal del producto",
        "Establecimiento por sucursal y punto de venta por caja; todo con alcance de empresa."],
       ["Documentos fiscales", "Documento fiscal, líneas, tributos, documentos relacionados, eventos "
        "(transmisión, contingencia, invalidación), secuencias de número de control",
        "Guarda el JSON firmado y la respuesta de Hacienda."],
       ["Caja", "Cajas, turnos, movimientos de efectivo, arqueos, depósitos", "Un turno pertenece a un cajero y a una caja."],
       ["Cobros", "Formas de pago, pagos de venta, recibos, aplicaciones a documentos, retenciones recibidas, "
        "anticipos de tarjeta", "Base de la cuenta por cobrar y de las casillas 161 y 162."],
       ["Documentos de proveedor", "Documento recibido, sus tributos, percepciones, retenciones practicadas, enlaces "
        "a compras, gastos y flota, uso fiscal del vehículo, marca de deducible por tipo de gasto, "
        "clasificación de renta, DTE recibidos", "Extiende las compras actuales; base del libro y del anexo de "
        "compras."],
       ["Períodos fiscales", "Período por empresa, hojas habilitadas, cierre y archivos generados",
        "Un período cerrado conserva el Excel que se entregó."],
       ["Pedidos", "Cotización, pedido de venta, líneas con tributos y descuentos, reservas de existencia, anticipos",
        "Sustituyen a las tablas actuales de cotización y venta."]],
      [0.18, 0.47, 0.35]))

h2("6.3 Estados del documento fiscal")
add(Flow([[("Borrador", "n"), ("Firmado", "n"), ("Transmitido", "n"), ("Sellado", "d"), ("Entregado\nal cliente", "n")],
          [("Rechazado", "a"), ("En contingencia", "a"), ("Invalidado", "a"), ("Ajustado por\nnota o retorno", "a"),
           ("Archivado\n(10 años)", "n")]]))
add(Paragraph("Figura 3. Estados propuestos para el documento fiscal.", S["cap"]))

h2("6.4 Arquitectura de la integración con Hacienda")
add(P("La integración se apoya en el servicio DTE del proyecto de referencia (sección 2.5), desplegado como un contenedor más "
      "junto al backend. El ERP no habla con Hacienda directamente: le pide los documentos a ese servicio."))
add(Flow([[("ERP\ndocumento fiscal", "n"), ("Cola de\ntareas", "n"), ("Servicio\nDTE", "d"), ("Firmador\nde Hacienda", "n"),
           ("Hacienda", "n")]]))
add(Paragraph("Figura 4. Recorrido de un documento desde el ERP hasta Hacienda.", S["cap"]))
add(B(["<b>ERP</b>: es dueño de la venta, del cálculo fiscal y del registro del documento. Guarda su propia copia "
       "del JSON firmado, el sello y el PDF en el repositorio de documentos, con retención de diez años.",
       "<b>Cola de tareas</b>: envía cada documento al servicio DTE con una clave que impide duplicados, consulta "
       "su estado y reintenta sin bloquear al cajero.",
       "<b>Servicio DTE</b>: arma el JSON del esquema oficial, lo valida, asigna código de generación y número de "
       "control, lo firma, lo transmite y aplica la política de reintentos, contingencia e invalidación.",
       "<b>Firmador</b>: servicio de firma que publica Hacienda, en la red interna y sin salida a internet.",
       "<b>Tres modos</b>: simulado, para desarrollo, demostraciones y capacitación sin tocar a Hacienda; ambiente "
       "de pruebas de Hacienda, para la certificación; y producción. El modo es un dato de cada empresa, no del "
       "despliegue: una puede estar certificándose mientras otra ya emite en producción. Cada documento queda "
       "marcado con el modo en que se emitió, de forma que uno simulado nunca pasa por fiscal."]))
add(NOTEBOX("Proceso de incorporación.", "Antes de emitir en producción, cada empresa debe solicitar su "
            "incorporación como emisor, obtener el certificado de firma y superar las pruebas de cada tipo de "
            "documento que vaya a emitir en el ambiente de pruebas de Hacienda. Conviene iniciar ese trámite en "
            "paralelo al desarrollo, porque no depende del equipo técnico."))

h2("6.5 Facturación multiemisor")
add(P("GestionaSV es un ERP multiempresa y multisucursal. La facturación electrónica sigue esa misma forma: nada "
      "se configura para «la empresa», sino para cada una, y dentro de cada una para cada sucursal y cada caja."))
h3("Tres niveles de configuración")
add(Flow([[("Empresa\nemisor", "d"), ("Sucursal\nestablecimiento", "n"), ("Caja\npunto de venta", "n"),
           ("Documento\nemitido", "n")]]))
add(Paragraph("Figura 5. Niveles de los que un documento toma sus datos de emisor.", S["cap"]))
add(T(["Nivel", "Qué se configura", "Notas"],
      [["Empresa (emisor)", "NIT, NRC, razón social, nombre comercial, actividades económicas, categoría de "
        "contribuyente, ambiente, credenciales de Hacienda, certificado de firma, tipos de documento habilitados "
        "y marca de las plantillas.", "Es la unidad de aislamiento: una empresa nunca ve ni usa datos de otra."],
       ["Sucursal (establecimiento)", "Tipo de establecimiento (casa matriz, sucursal, bodega o patio), código "
        "asignado por Hacienda, código interno, dirección, teléfono y correo.",
        "El documento lleva la dirección del establecimiento donde se hizo la operación, no la de la casa matriz "
        "(Normativa 2.0, anexo II, campos 26 a 29)."],
       ["Caja (punto de venta)", "Código de punto de venta asignado por Hacienda y código interno.",
        "Forma parte del número de control: DTE-01-S002P003-…"],
       ["Documento", "Copia de los tres niveles tal como estaban al emitir.",
        "Cambiar la configuración después no altera lo ya emitido."]],
      [0.22, 0.48, 0.30]))
add(P("La actividad económica también se elige por documento: la Normativa pide el código «que corresponda a "
      "la operación» (anexo II, campo 23), así que una empresa con varias actividades registra todas y cada "
      "establecimiento o tipo de venta usa la suya."))
h3("Documentos que emite cada empresa")
add(B(["Cada empresa activa los tipos de documento que usa. Una panadería puede necesitar factura, crédito "
       "fiscal, notas de crédito y débito y nota de remisión; otra empresa puede sumar factura de exportación, "
       "comprobante de retención o factura de sujeto excluido.",
       "Un tipo se habilita cuando la empresa aprobó sus pruebas ante Hacienda; el sistema lleva ese estado por "
       "tipo, ambiente y empresa.",
       "Las pantallas solo ofrecen los documentos habilitados, y el servicio rechaza cualquier otro.",
       "La clasificación fiscal es por producto (gravado, exento o no sujeto) y por empresa. Ninguna regla asume "
       "que todo es gravado."]))
h3("Aislamiento entre empresas")
add(T(["Elemento", "Cómo se aísla"],
      [["Credenciales y certificado", "Se guardan cifrados por empresa. El firmador de Hacienda recibe el NIT en "
        "cada solicitud y usa el certificado de ese NIT, por lo que uno solo sirve a todas."],
       ["Sesión con Hacienda", "Un token por empresa y ambiente; nunca se comparte."],
       ["Numeración", "Correlativo por empresa, ambiente, tipo de documento, año, establecimiento y punto de venta."],
       ["Contingencia", "Ventana por empresa y, dentro de ella, por establecimiento o punto de venta: la caída de "
        "internet en una tienda no pone en contingencia a las demás."],
       ["Documentos y eventos", "Toda consulta filtra por empresa; el servicio comprueba que la empresa de la "
        "solicitud sea la dueña del documento."],
       ["Acceso al servicio", "El ERP se identifica con su llave y declara la empresa en cada solicitud; el "
        "servicio valida que esa empresa esté registrada y activa."],
       ["Límites de uso", "Por empresa, para que el volumen de una no frene a otra."]],
      [0.26, 0.74]))
h3("Adaptaciones que requiere el servicio de referencia")
add(T(["Hoy", "Debe quedar"],
      [["Un emisor definido al desplegar, con sus claves en la configuración del servidor.",
        "Registro de emisores administrado desde el ERP, con credenciales cifradas."],
       ["Un token de Hacienda en memoria.", "Un token por empresa y ambiente."],
       ["Tipos de documento habilitados en una lista global.", "Lista por empresa, con su estado de certificación."],
       ["Modo único para todo el servicio.", "Modo por empresa."],
       ["Establecimiento y punto de venta por solicitud solo en tres documentos.", "En todos los documentos y eventos."],
       ["Numeración sin distinguir empresa.", "Empresa y ambiente dentro de la llave del correlativo."],
       ["Una ventana de contingencia global.", "Ventanas por empresa y establecimiento."],
       ["Sin evento de retorno ni tiquete.", "Evento de retorno y tiquete de 80 mm."],
       ["Volumen de tienda en línea.", "Medido con volumen de mostrador; envío por lotes si hace falta."],
       ["Numeración solo en la base del servicio.", "Conciliada al arrancar con la copia del ERP, para que nunca "
        "retroceda."]],
      [0.46, 0.54]))
h3("Plantillas de la versión legible")
add(P("El Manual Funcional de Hacienda (sección XXII) trae un modelo sugerido de versión legible para cada "
      "documento y evento. El servicio de referencia ya tiene plantillas en PDF que siguen esos modelos, con "
      "logo por emisor, código QR y marca de documento simulado. Se reutilizan y se completan así:"))
add(T(["Plantilla", "Estado en el proyecto de referencia", "Acción"],
      [["Factura, comprobante de crédito fiscal y nota de crédito", "En uso y revisadas.", "Reutilizar."],
       ["Evento de invalidación", "En uso y revisada.", "Reutilizar."],
       ["Nota de remisión, nota de débito y factura de exportación", "Comparten la plantilla de venta; sin uso real.",
        "Revisar contra el modelo de Hacienda al habilitarlas."],
       ["Comprobante de retención, de liquidación, documento contable de liquidación, sujeto excluido y donación",
        "Tienen columnas propias y pruebas automáticas; sin uso real.", "Revisar contra el modelo al habilitarlas."],
       ["Evento de retorno y evento de operaciones especiales", "No existen.", "Crear según el modelo de Hacienda."],
       ["Tiquete de 80 mm", "No existe.", "Crear: es la factura en formato de rollo para el punto de venta."]],
      [0.42, 0.30, 0.28]))
add(P("Las plantillas toman el logo y los datos del emisor de cada empresa, de modo que dos empresas nunca "
      "comparten encabezado. Las que faltan se crean cuando una empresa habilita ese documento, no antes."))
h2("6.6 Inventario de mostrador")
add(P("El inventario actual se controla por unidad logística etiquetada (caja, bandeja, saco), con lote y "
      "ubicación. Eso es correcto para bodega y mayoreo, pero no para vender una pieza de pan. Se propone:"))
add(B(["Una <b>ubicación de vitrina</b> por sucursal, a granel, sin etiqueta por pieza.",
       "Una operación «pasar a vitrina» que abre una unidad logística y suma sus piezas a la vitrina.",
       "La venta de mostrador descuenta de la vitrina por cantidad, al costo promedio, y registra el movimiento "
       "«Venta» en el kardex.",
       "Un <b>conteo de cierre</b> diario de vitrina, que revela la merma del día y la registra como ajuste.",
       "El mayoreo y los pedidos siguen usando la entrega actual por unidad logística."]))
add(P("Esta es la decisión de diseño más delicada del área, porque toca el motor de inventario. Debe validarse con "
      "la operación real de las tiendas antes de construir el punto de venta."))

h2("6.7 Permisos y auditoría")
add(T(["Rol", "Puede", "No puede"],
      [["Cajero", "Vender, cobrar, abrir y cerrar su turno, reimprimir.", "Cambiar precios, anular ventas cobradas, ver costos."],
       ["Supervisor de tienda", "Autorizar descuentos, anulaciones y devoluciones; aprobar cierres de caja.",
        "Modificar listas de precios o configuración fiscal."],
       ["Vendedor de mayoreo", "Cotizar, tomar pedidos, consultar el estado de cuenta de sus clientes.",
        "Facturar por encima del cupo de crédito sin autorización."],
       ["Facturación", "Emitir e invalidar DTE, emitir notas, gestionar contingencias.", "Alterar cobros."],
       ["Créditos y cobros", "Registrar cobros, aprobar cupos, bloquear clientes.", "Emitir documentos fiscales."],
       ["Contador", "Consultar libros, generar anexos, cerrar períodos; definir el uso fiscal de los vehículos y "
        "qué tipos de gasto son deducibles.", "Operar ventas."],
       ["Administrador fiscal", "Configurar emisor, certificado, establecimientos, catálogos y marcas de "
        "deducibilidad.", "—"]],
      [0.22, 0.42, 0.36]))
add(P("Toda acción sensible —cambio de precio, descuento fuera de tope, invalidación, anulación de cobro, cierre "
      "con faltante, cambio de una marca de deducibilidad— queda en la bitácora de auditoría con usuario, fecha, motivo y valores anterior y nuevo."))

h2("6.8 Nota de remisión en traslados entre sucursales")
add(P("El artículo 109 del Código Tributario obliga a emitir nota de remisión en los envíos en consignación y en "
      "los «traslados que no constituyan transferencias». Mover mercadería entre sucursales de la misma empresa "
      "es ese caso: no hay venta, pero la carga debe circular amparada. El módulo de Traslados ya existe y hoy "
      "despacha sin documento fiscal."))
add(B(["<b>Cuándo se emite.</b> Al despachar el traslado, antes de que el vehículo salga. El despacho no se "
       "confirma si la nota no se pudo generar.",
       "<b>Qué lleva.</b> Documento tipo 04, con «bienes remitidos a título de» igual a 04, Traslado (catálogo "
       "CAT-025). El emisor es el establecimiento de origen y el receptor es la misma empresa, con la dirección "
       "del establecimiento de destino. Las líneas salen de las unidades despachadas.",
       "<b>Vehículo y conductor.</b> El esquema de la nota no tiene sección de transporte; la placa y el "
       "conductor van en observaciones y en el apéndice.",
       "<b>Lo que acompaña la carga.</b> La versión impresa de la nota, con su código QR.",
       "<b>Contingencia.</b> La nota de remisión puede emitirse en contingencia, igual que una factura.",
       "<b>Correcciones.</b> Un despacho cancelado o corregido invalida la nota, dentro del décimo día hábil del "
       "mes siguiente. La recepción parcial y las discrepancias no cambian la nota: se resuelven en el traslado.",
       "<b>Quién la habilita.</b> Toda empresa con más de un establecimiento debe tener habilitada y certificada "
       "la nota de remisión."]))

h2("6.9 Caja sin conexión")
add(P("La norma no permite dejar de documentar la venta cuando falla la conexión. En contingencia el orden es "
      "generar, firmar y entregar el documento al cliente en ese momento, y transmitirlo después (Normativa 2.0, "
      "regla 6.3). El Manual Funcional añade que el contribuyente sigue operando «con su sistema de respaldo para "
      "operar fuera de línea». De ahí salen tres condiciones para el diseño:"))
add(B(["<b>El documento se firma en el momento de la venta.</b> Capturar la venta y facturarla al volver la "
       "conexión no cumple: la factura debe generarse cuando ocurre la venta.",
       "<b>La llave de firma no puede vivir en el navegador de la caja.</b> La Normativa hace al contribuyente "
       "responsable exclusivo de sus claves de firma (regla 9). Por eso una pantalla que solo guarda ventas en "
       "el navegador no puede producir un documento válido sin conexión.",
       "<b>La numeración ya lo permite.</b> El número de control es por punto de venta, así que una tienda puede "
       "numerar por su cuenta sin chocar con las demás."]))
add(T(["Opción", "Cómo funciona", "Cumple", "Costo"],
      [["A. Caja en línea con enlace de respaldo", "La caja usa el ERP central. Cada tienda tiene un segundo "
        "enlace, por ejemplo celular. La contingencia cubre las caídas de Hacienda y del propio servicio.",
        "Sí, mientras alguno de los dos enlaces funcione.", "Bajo: un módem por tienda."],
       ["B. Nodo de tienda", "Un equipo pequeño en la tienda corre el servicio DTE y el firmador, con una copia "
        "de respaldo de las ventas del día. Sin internet emite en contingencia y sincroniza al volver.",
        "Sí, también sin internet. Con batería de respaldo cubre cortes de energía.",
        "Medio: equipo, instalación y custodia del certificado en cada tienda."],
       ["C. Solo cola en el navegador", "La caja guarda la venta localmente y factura al reconectar.",
        "No: no firma ni entrega el documento en el momento.", "Bajo, pero no es válido."]],
      [0.20, 0.40, 0.24, 0.16]))
add(NOTEBOX("Decisión.", "El punto de venta sale con la opción A, que no exige equipo en tienda y cubre la falla "
            "más común. La opción B queda como bloque opcional, activable por sucursal para las tiendas con "
            "conexión inestable; es viable porque el servicio DTE ya es un contenedor independiente y la "
            "numeración es por punto de venta. La opción C se descarta."))
add(B(["Con la opción A, si los dos enlaces fallan la tienda no puede facturar. Ese riesgo se acepta por "
       "tienda o se cubre con la opción B.",
       "El nodo de tienda guarda una copia del certificado de firma de la empresa. Requiere disco cifrado, "
       "acceso físico restringido y poder revocar el certificado si el equipo se pierde.",
       "Los plazos no cambian: evento de contingencia en 24 horas desde que vuelve el servicio y documentos en "
       "72 horas desde el sello del evento."]))

# ---------------- PARTE VII ----------------
part("VII", "Plan de implementación")
h2("7.1 Bloques de trabajo")
add(P("Se proponen nueve bloques. Cada uno entrega algo utilizable y verificable, y sigue la forma de trabajo que el "
      "proyecto ya usa: rama propia desde <i>develop</i>, migración, dominio, repositorios, API, interfaz, pruebas "
      "y manual."))
add(T(["Bloque", "Contenido", "Resultado verificable", "Depende de"],
      [["V1 · Base fiscal", "Datos fiscales del cliente, catálogos de Hacienda, clasificación fiscal de "
        "productos, perfil de emisor por empresa, establecimientos por sucursal, puntos de venta por caja, "
        "tipos de documento habilitados por empresa, aviso de privacidad, consentimientos y solicitudes de "
        "titulares de datos.",
        "Dos empresas configuradas como emisores distintos, sin datos compartidos.", "—"],
       ["V2 · Precios e impuestos", "Listas de precios, descuentos, motor único de cálculo con IVA, retención y "
        "percepción. Nuevo modelo de cotización y pedido, que sustituye al actual.", "Una cotización y un pedido con "
        "totales fiscales correctos en ambos tipos de documento.", "V1"],
       ["V3 · DTE esencial", "Incorporar el servicio DTE del proyecto de referencia, convertirlo en multiemisor y conectarlo "
        "al ERP. Factura y comprobante de crédito fiscal con sello, PDF con QR y envío por correo, primero en "
        "modo simulado y luego en el ambiente de pruebas.", "Dos empresas emiten en simulado desde el ERP con "
        "numeración, credenciales y plantillas separadas; con credenciales, sellan en el ambiente de pruebas.",
        "V2"],
       ["V4 · Robustez del DTE", "Contingencia por empresa y establecimiento, invalidación, nota de crédito, nota "
        "de débito, nota de remisión emitida al despachar traslados, evento de retorno, plantillas faltantes y "
        "certificación ante Hacienda.", "Los cinco desvíos de la Figura 1 probados de extremo a extremo y el lote "
        "de certificación aprobado.", "V3"],
       ["V5 · Pedidos y cobros", "Venta sin cotización, pedidos, encargos con anticipo, formas de pago, cuentas "
        "por cobrar, recibos y retenciones recibidas.", "Una venta a crédito facturada, cobrada parcialmente y con "
        "saldo correcto.", "V3"],
       ["V6 · Punto de venta y caja", "Inventario de vitrina, pantalla de venta rápida, cobro mixto, tiquete, "
        "turnos, arqueo y cierre, con enlace de respaldo por tienda. Nodo de tienda como bloque opcional.",
        "Un día completo de tienda: apertura, ventas, cierre cuadrado y una caída de enlace simulada.", "V4 y V5"],
       ["V7 · Documentos de proveedor y gastos", "Registro único del documento de proveedor y su enlace con "
        "compras, gastos de órdenes, retaceo, combustible, mantenimiento y costos de flota. Gastos generales, "
        "reglas de crédito deducible, factura de sujeto excluido y recepción de DTE de proveedores.",
        "Una compra, una carga de combustible y un recibo de energía aparecen en el libro de compras con su "
        "crédito fiscal correcto.", "V1 y V4"],
       ["V8 · Fiscal: libros y F-07", "Devoluciones con efecto fiscal, los tres libros de IVA, todos los anexos "
        "y casillas del F-07, hojas habilitadas por empresa y cierre de período.",
        "El Excel de un mes coincide, hoja por hoja, con la plantilla estándar llenada a mano.", "V5 y V7"],
       ["V9 · Análisis y aceptación", "Tablero comercial, márgenes, datos de demostración, manuales y prueba "
        "integral.", "Recorrido completo en local y en gestionasv.lat.", "Todos"]],
      [0.17, 0.37, 0.30, 0.16]))

h2("7.2 Orden y justificación")
add(Flow([[("V1\nBase fiscal", "n"), ("V2\nPrecios e\nimpuestos", "n"), ("V3\nDTE\nesencial", "d"),
           ("V4\nRobustez\ndel DTE", "n")],
          [("V5\nPedidos\ny cobros", "n"), ("V6\nPunto de venta\ny caja", "d"), ("V7\nDocumentos\nde proveedor", "n"),
           ("V8\nLibros\ny F-07", "n"), ("V9\nAnálisis y\naceptación", "n")]], box_h=1.5 * cm))
add(Paragraph("Figura 6. Secuencia propuesta de los nueve bloques.", S["cap"]))
add(B(["<b>El rediseño ocurre en V1 y V2</b>: ahí se sustituyen clientes, cotización y venta actuales, y se retiran "
       "las pantallas y tablas que ya no aplican, antes de que nada dependa de ellas.",
       "<b>La base fiscal va primero</b> porque todos los demás módulos dependen de saber quién es el cliente y "
       "cuánto impuesto lleva cada producto.",
       "<b>El DTE va antes que el punto de venta</b> porque un punto de venta que no factura no puede usarse en "
       "una tienda real, mientras que la facturación desde una venta ordinaria ya es útil para el mayoreo.",
       "<b>V3 y V4 parten de una base existente</b>: el servicio DTE del proyecto de referencia reduce el trabajo de esos "
       "bloques a adaptar, integrar y certificar, y permite avanzar en modo simulado mientras llegan las "
       "credenciales de Hacienda.",
       "<b>La robustez del DTE es un bloque propio</b> porque contingencia e invalidación son las partes con más "
       "reglas y las que más rechazos generan.",
       "<b>El punto de venta llega cuando ya existen cobros y contingencia</b>, que son sus dos dependencias duras.",
       "<b>Los documentos de proveedor van antes que los libros</b> porque la mitad del F-07 sale de ellos. Ese "
       "bloque toca Compras y Flota, fuera del área de Ventas, y puede avanzar en paralelo a V5 y V6."]))

h2("7.3 Pruebas y criterios de aceptación")
add(B(["<b>Cálculo</b>: casos de prueba con valores exactos para cada combinación de documento, naturaleza de "
       "venta, descuento, retención y percepción, incluidos los de redondeo.",
       "<b>Esquema</b>: cada tipo de DTE se valida contra el esquema oficial antes de transmitirse.",
       "<b>Hacienda</b>: emisión real en el ambiente de pruebas de cada tipo de documento y de cada evento.",
       "<b>Resiliencia</b>: caída de conexión simulada a mitad de una venta, respuesta perdida y doble envío.",
       "<b>Concurrencia</b>: dos cajas emitiendo al mismo tiempo sin repetir ni saltar números de control.",
       "<b>Conciliación</b>: ventas, documentos sellados, inventario, caja y libros deben cuadrar entre sí al "
       "cierre de un día y de un mes de datos de demostración.",
       "<b>F-07</b>: el Excel generado se compara, hoja por hoja y columna por columna, con la plantilla "
       "estándar llenada a mano para el mismo mes, y los libros deben dar los mismos totales que los anexos.",
       "<b>Permisos</b>: cada acción sensible probada con un rol que puede y con uno que no."]))

h2("7.4 Riesgos")
add(T(["Riesgo", "Efecto", "Mitigación"],
      [["Cambio de normativa (versión 2.0)", "Rechazo de documentos.", "Construir contra la versión 2.0, "
        "catálogos y esquemas versionados, y revisar el portal de Hacienda al iniciar cada bloque."],
       ["Trámite de incorporación como emisor", "No poder probar contra Hacienda.", "Iniciarlo desde el bloque "
        "V1; mientras tanto, trabajar en modo simulado y validar contra los esquemas oficiales."],
       ["Base DTE sin certificar", "Rechazos al conectar con Hacienda por reglas que el esquema no cubre.",
        "Reservar tiempo en V4 para la certificación completa y no dar por buena ninguna regla hasta verla "
        "aceptada en el ambiente de pruebas."],
       ["Servicio DTE en otra tecnología", "Dos lenguajes que mantener.", "Tratarlo como servicio cerrado con "
        "contrato estable; el equipo ya lo conoce porque es suyo."],
       ["Mezcla de datos entre empresas", "Un documento emitido con el NIT, el certificado o la numeración de "
        "otra empresa.", "Empresa obligatoria en cada solicitud y en cada llave; pruebas automáticas con dos "
        "empresas desde V1."],
       ["Inventario de vitrina", "Descuadre entre existencias y ventas.", "Validar el diseño con una tienda y "
        "comenzar por una sucursal piloto."],
       ["Rendimiento en caja", "Filas en horas pico.", "Transmisión en segundo plano; el cajero no espera a Hacienda."],
       ["Custodia del certificado", "Emisión fraudulenta.", "Cifrado, acceso restringido y firmador en red interna."],
       ["Caída de internet en tienda", "Tienda sin poder facturar.", "Enlace de respaldo en cada tienda desde "
        "el primer día y nodo de tienda donde la conexión sea inestable (sección 6.9)."],
       ["Fuga de datos de clientes", "Multa y notificación obligatoria en 72 horas.", "Datos mínimos, cifrado, "
        "bitácora de accesos y procedimiento de incidentes (sección 3.7)."],
       ["Rehacer lo existente", "Pruebas y pantallas actuales dejan de servir.", "Aceptarlo de forma explícita: son "
        "datos de demostración y el costo de rehacer hoy es bajo."],
       ["Alcance", "El área es grande y puede no terminarse.", "Cada bloque es entregable por sí mismo; V1 a V4 "
        "ya dan una facturación completa."]],
      [0.26, 0.26, 0.48]))

h2("7.5 Decisiones que se necesitan de cada empresa")
add(B(["Categoría de contribuyente de la empresa y si ya está incorporada como emisora de DTE.",
       "Qué sucursales son establecimientos registrados ante Hacienda y cuántas cajas tiene cada una.",
       "Qué tipos de documento emitirá cada empresa, para habilitar y certificar solo esos.",
       "Qué anexos y casillas del F-07 aplican a cada empresa, confirmados por su contador.",
       "Dónde se alojan los datos: en el país o fuera, por la ley de datos personales y por la restricción de "
       "infraestructura de Hacienda.",
       "Qué tiendas tienen conexión inestable y necesitan nodo local, y cuáles operan solo con enlace de respaldo.",
       "Quién atiende en la empresa las solicitudes de titulares de datos y los incidentes de seguridad.",
       "El uso fiscal de cada vehículo (indispensable, mixto o ajeno al giro) y qué tipos de gasto son "
       "deducibles, definidos por el contador.",
       "Si el mayoreo y los encargos entran en la primera versión o después del mostrador.",
       "Política de crédito: plazos, cupos y quién autoriza excepciones.",
       "Formas de pago aceptadas y si se integrará alguna terminal de tarjetas.",
       "Política de cambios y devoluciones de producto perecedero.",
       "Cómo se maneja hoy la merma diaria de vitrina y quién la registra.",
       "Si la producción propia (panadería) se modelará como módulo o los productos terminados seguirán "
       "entrando por compras y traslados."]))

# ---------------- PARTE VIII ----------------
part("VIII", "Verificación de datos y fuentes")
h2("8.1 Datos verificados en su fuente oficial")
add(P("Los datos que en versiones anteriores de este documento figuraban como pendientes se verificaron leyendo "
      "directamente la fuente oficial. La columna de la derecha indica dónde está cada regla."))
add(T(["Dato", "Regla", "Fuente oficial"],
      [["Vigencia de la Normativa 2.0", "Vigente desde su publicación, el 25 de mayo de 2026.",
        "Normativa de Cumplimiento 2.0, regla 20."],
       ["Invalidación de factura, exportación y sujeto excluido", "Hasta tres meses desde el sello de recepción.",
        "Manual Funcional 2.0, sección VII."],
       ["Invalidación de crédito fiscal, notas, remisión, retención y eventos",
        "Hasta el décimo día hábil del mes siguiente al período en que se obtuvo el sello.",
        "Manual Funcional 2.0, sección VII."],
       ["Evento de contingencia", "Dentro de las 24 horas siguientes al cese de la falla; de 1 a 1,000 documentos.",
        "Manual Funcional 2.0, sección VIII."],
       ["Documentos en contingencia", "Dentro de las 72 horas siguientes al sello del evento.",
        "Manual Funcional 2.0, sección VIII."],
       ["Evento de retorno", "Facturas ya selladas, dentro de tres meses; hasta 50 documentos por evento.",
        "Manual Funcional 2.0, sección X."],
       ["Número de control", "31 caracteres, DTE-01-M001P025-000000000000001; no se repite en el año calendario.",
        "Manual Funcional 2.0, sección XI."],
       ["Reintentos", "Sin respuesta en 8 segundos: consultar el estado y reenviar como máximo 2 veces.",
        "Manual Técnico 2.0, sección 3.3."],
       ["Envío por lotes", "Hasta 100 documentos por lote y 400 lotes; de 10:00 p. m. a 5:00 a. m. para "
        "facturación cíclica.", "Manual Técnico 2.0, secciones 3.2 y 3.4."],
       ["Direcciones del servicio", "apitest.dtes.mh.gob.sv (pruebas) y api.dtes.mh.gob.sv (producción), sin "
        "barra final.", "Manual Técnico 2.0, secciones 4 y 6.2."],
       ["Códigos de documento", "01, 03, 04, 05, 06, 07, 08, 09, 11, 14 y 15; eventos 17 (operaciones "
        "especiales) y 18 (retorno).", "Catálogo CAT-002, edición del 1 de julio de 2026."],
       ["Retención y percepción del 1 %", "Operaciones con precio sin IVA igual o superior a $100.",
        "Código Tributario, arts. 162 y 163."],
       ["Identificación del consumidor final", "No se exige bajo $25,000, salvo que el cliente deduzca el gasto.",
        "Decreto Legislativo 94 de 2024 (D. O. 178, tomo 444); aviso de la DGII del 5 de septiembre de 2024."],
       ["Conservación", "Diez años desde la generación, en su formato original.",
        "Código Tributario, art. 147; Normativa 2.0, regla 12."],
       ["Tiquetes", "Prohibidos para emisores de DTE desde el 1 de enero de 2025.", "Normativa 2.0, regla 15."],
       ["Dirección y actividad del emisor", "La del establecimiento donde se hizo la operación; el código de "
        "actividad es el que corresponde a la operación.", "Normativa 2.0, anexo II, campos 23 y 26 a 29."],
       ["Libros de IVA", "Tres libros con columnas y orden fijos, foliados, totalizados por mes y autorizados por "
        "contador público; anotación en diez días hábiles.", "Código Tributario, art. 141; Reglamento de "
        "Aplicación, arts. 82 a 88."],
       ["Anexos del F-07", "Doce anexos de carga y uno de anulados, en CSV con punto y coma; versión vigente del "
        "formulario y del manual: 14.", "Manual de carga de anexos F-07 V14 (enero de 2025); formulario F-07 V14."],
       ["Plazo para dejar la versión 1.2", "Hasta el 1 de diciembre de 2026 para quienes usan el Sistema de "
        "Transmisión.", "Comunicado oficial del Ministerio de Hacienda del 25 de mayo de 2026; Normativa 2.0, "
        "regla 18."],
       ["Reformas recientes al Código Tributario", "Después de septiembre de 2024 solo hay una, de abril de 2026, "
        "sobre el artículo 158 (retención a inversiones bursátiles); no toca los artículos usados aquí.",
        "Asamblea Legislativa, Decreto 544 de 2026 y listado de decretos."],
       ["Datos personales", "Aviso de privacidad, consentimiento, derechos del titular con respuesta en 20 días "
        "hábiles, notificación de vulneraciones en 72 horas y límites a la transferencia internacional.",
        "Ley para la Protección de Datos Personales, D. L. 144 de 2024, reformada por D. L. 659 de 2026."],
       ["Nota de remisión en traslados", "Obligatoria en traslados que no son transferencias; documento 04 con "
        "título 04, Traslado.", "Código Tributario, art. 109; catálogo CAT-025; esquema de la nota de remisión."],
       ["Venta en contingencia", "Generar, firmar y entregar en el momento; transmitir después. Las claves de "
        "firma las custodia el contribuyente.", "Normativa 2.0, reglas 6.3, 9 y 11.2; Código Tributario, "
        "art. 119-F; Manual Funcional, sección VIII."],
       ["Crédito fiscal deducible", "Solo con comprobante de crédito fiscal, gasto indispensable y anotado en el "
        "libro; vehículos y su combustible al 100 %, 50 % o nada según su uso.", "Ley de IVA, arts. 65, 65-A y 66."],
       ["Combustible", "FOVIAL y COTRANS son tributos aparte del IVA (códigos D1 y C8).",
        "Manual Funcional 2.0, sección sobre tributos."]],
      [0.26, 0.42, 0.32]))
h3("Lo que queda fuera de la investigación")
add(P("No quedan datos normativos por confirmar. Lo que resta no se puede investigar, porque depende de la empresa:"))
add(B(["<b>Datos propios de cada empresa.</b> Su categoría de contribuyente, si ya fue notificada como emisora, "
       "sus actividades económicas y los códigos de establecimiento y punto de venta que Hacienda le asigne. Los "
       "entrega la empresa (sección 7.5)."]))
h3("Alcance de la verificación")
add(B(["El comunicado del 25 de mayo de 2026 se leyó en la reproducción de un proveedor de facturación; no se "
       "localizó en el portal de Hacienda. La fecha coincide en todas las fuentes y no afecta al ERP, que se "
       "construye sobre la versión 2.0.",
       "El reglamento se leyó en el texto del Decreto Ejecutivo 117 de 2001 publicado por el Centro de "
       "Documentación Judicial. No se encontraron reformas a sus artículos 82 a 88.",
       "No se halló una versión del manual de anexos posterior a la 14; la página de Hacienda y el formulario "
       "vigente siguen citando esa versión.",
       "La normativa cambia varias veces al año. Al iniciar cada bloque conviene revisar factura.gob.sv y la "
       "página de anexos de Hacienda, como ya indica la tabla de riesgos."]))

h2("8.2 Fuentes consultadas")
src = [
    ("Ministerio de Hacienda, DGII — Guía de integración de factura electrónica (versión 8.0)",
     "factura.gob.sv/wp-content/uploads/2021/11/FESVDGIIMH_GuiaIntegracionFacturaElectronicasSV.pdf"),
    ("Ministerio de Hacienda — Formulario F-07 versión 14", "mh.gob.sv/wp-content/uploads/2025/08/F07_V14_COMPLE.pdf"),
    ("Ministerio de Hacienda — Formulario F-14 versión 17", "mh.gob.sv/wp-content/uploads/2026/06/F14-V17.pdf"),
    ("Ministerio de Hacienda — Boletín para nuevos contribuyentes (2025)",
     "mh.gob.sv/wp-content/uploads/2025/03/BOLETIN-PARA-NUEVOS-CONTRIBUYENTES-05032025.pdf"),
    ("Ministerio de Hacienda — Calendario tributario 2026", "mh.gob.sv/wp-content/uploads/2025/12/Calendario-Tributario-2026.pdf"),
    ("Ministerio de Hacienda — Marco normativo de la administración tributaria",
     "transparencia.mh.gob.sv (sección Administración Tributaria)"),
    ("Defensoría del Consumidor — Ley de Protección al Consumidor y su reglamento", "defensoria.gob.sv/images/ley_reglamento.pdf"),
    ("EDICOM — Factura electrónica en El Salvador y novedades de la versión 2.0",
     "edicomgroup.com/es/blog/como-es-la-factura-electronica-en-el-salvador"),
    ("elsalvador.com — Nuevo plazo de invalidación de facturas electrónicas (febrero de 2026)",
     "elsalvador.com/dinero-y-negocios/entorno-economico/el-salvador-facturacion-electronica-nuevo-plazo/1262295/2026/"),
    ("elsalvador.com — Identificación no indispensable en compras menores de $25,000 (2024)",
     "elsalvador.com/noticias/nacional/identificacion-no-sera-indispensable-para-compras-menores-de-25-000/1169434/2024/"),
    ("EY — Reformas al Código Tributario para implementar los DTE",
     "ey.com/es_ce/technical/tax/tax-alerts/el-salvador-se-aprueban-reformas-al-codigo-tributario-para-implementar"),
    ("EY — Reforma a los artículos 114 y 119-G del Código Tributario",
     "ey.com/es_ce/technical/tax/tax-alerts/el-salvador-asamblea-legislativa-aprueba-reforma-codigo-tributario"),
    ("PwC — Cambios en los formularios F-07 y F-14 (2024)",
     "pwc.com/ia/es/publicaciones/Noticias-Tax-Legal/Tax-and-Legal-2024/Cambios-F07-F14.pdf"),
    ("Sovos — Facturación electrónica en El Salvador", "sovos.com/es/iva/reglas-fiscales/factura-electrnica-en-el-salvador/"),
    ("ERP Software Blog — How DTE validation really works (septiembre de 2026)",
     "erpsoftwareblog.com/2026/09/business-central-el-salvador-how-dte-validation-really-works/"),
    ("BAC Credomatic — Manual de documentos tributarios para comercios afiliados",
     "baccredomatic.com/sites/default/files/2024-07/SV-Manual-Documentos-Tributarios-Comercios-Afiliados-v2.pdf"),
    ("Ministerio de Hacienda, DGII — Normativa de Cumplimiento de los Documentos Tributarios Electrónicos, "
     "versión 2.0 (25 de mayo de 2026)", "factura.gob.sv, sección de información técnica y funcional; leída directamente"),
    ("Ministerio de Hacienda — Manual Funcional del Sistema de Transmisión, versión 2.0",
     "Documento oficial entregado por la empresa; leído directamente"),
    ("Ministerio de Hacienda — Manual Técnico para la Integración Tecnológica del Sistema de Transmisión, "
     "versión 2.0", "Documento oficial entregado por la empresa; leído directamente"),
    ("Ministerio de Hacienda — Catálogos de facturación electrónica (1 de julio de 2026), esquemas JSON y firmador",
     "Documentos oficiales entregados por la empresa"),
    ("Ley de Impuesto a la Transferencia de Bienes Muebles y a la Prestación de Servicios (arts. 65, 65-A y 66), "
     "con reformas hasta julio de 2024",
     "asamblea.gob.sv/sites/default/files/documents/decretos/C710DA02-4727-485E-B8F4-B9CBF64152A6.pdf"),
    ("Reglamento de Aplicación del Código Tributario, Decreto Ejecutivo 117 de 2001 (arts. 82 a 88)",
     "jurisprudencia.gob.sv/DocumentosBoveda/D/2/2000-2009/2001/12/89024.PDF"),
    ("Asamblea Legislativa — Ley para la Protección de Datos Personales, Decreto Legislativo 144 de 2024",
     "asamblea.gob.sv/sites/default/files/documents/decretos/17458CF0-AB9B-482A-85A1-03834D5D89B7.pdf"),
    ("Asamblea Legislativa — Reformas a la Ley para la Protección de Datos Personales, Decreto 659 de 2026",
     "asamblea.gob.sv/sites/default/files/documents/decretos/048D810E-C262-4D9E-8839-B3D26A2F4378.pdf"),
    ("Asamblea Legislativa — Decretos emitidos en 2026 y Decreto 544 (reforma al art. 158 del Código Tributario)",
     "asamblea.gob.sv/leyes-y-decretos/decretos-por-anios/2026/0"),
    ("Ministerio de Hacienda — Comunicado oficial sobre la Normativa DTE 2.0 (25 de mayo de 2026)",
     "Reproducido en hixtechnologies.com/en/dte2/"),
    ("Código Tributario, texto consolidado a septiembre de 2024 (arts. 114, 119-G, 141, 147, 162 y 163)",
     "reddecontadores.com/wp-content/uploads/2025/05/Codigo-Tributario-sept2024.pdf"),
    ("Asamblea Legislativa — Decreto Legislativo 94, del 17 de septiembre de 2024",
     "asamblea.gob.sv/sites/default/files/documents/decretos/CC6E4183-4D6F-4BC8-9A88-C0BC2BFAF13E.pdf"),
    ("DGII — Aviso sobre identificación en ventas a consumidor final (5 de septiembre de 2024)",
     "factura.gob.sv, sección de normativa"),
    ("Proyecto de referencia — servicio DTE y su documentación (auditoría contra Hacienda, anexos F-07, retención "
     "de IVA y manual de operación)", "Repositorio interno del equipo; revisado solo en lectura"),
    ("Ministerio de Hacienda, DGII — Manual de usuario para carga de archivo de los anexos de la declaración "
     "del IVA, F-07 versión 14 (enero de 2025)",
     "iscpelsalvador.org/wp-content/uploads/700-DGII-MN-2021-26031-1.pdf (copia del documento 700-DGII-MN-2021-26031)"),
    ("Contaportable — «Plantillas IVA F-07», versión 11.7.4 (libros de IVA y anexos del F-07)",
     "contaportable.com; plantilla entregada por la empresa, leída hoja por hoja"),
    ("Documentación interna del ERP", "docs/ers-v1/manual-ventas-base.md, manual-entregas.md y modelos de datos de ventas"),
]
add(T(["Fuente", "Ubicación"], [[a, "<font size=8>%s</font>" % b] for a, b in src], [0.48, 0.52]))

h2("8.3 Glosario")
add(T(["Término", "Significado"],
      [["DTE", "Documento Tributario Electrónico."],
       ["DGII", "Dirección General de Impuestos Internos, del Ministerio de Hacienda."],
       ["NIT", "Número de Identificación Tributaria."],
       ["NRC", "Número de Registro de Contribuyente de IVA."],
       ["CCF", "Comprobante de crédito fiscal."],
       ["Sello de recepción", "Código que Hacienda asigna al aceptar un DTE; le da validez jurídica."],
       ["Contingencia", "Modalidad para emitir sin conexión y transmitir después."],
       ["Invalidación", "Evento que deja sin efecto un DTE ya sellado."],
       ["Débito fiscal", "IVA generado por las ventas."],
       ["F-07 / F-14", "Declaraciones mensuales de IVA y de pago a cuenta y retenciones."],
       ["Unidad logística", "Caja, bandeja o saco etiquetado con que el ERP controla el inventario en bodega."]],
      [0.24, 0.76]))

# ---------------- build ----------------
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "plan-area-ventas-el-salvador.pdf")
doc = Doc(out, pagesize=letter, leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
          title="Ventas y facturación fiscal — Investigación y plan de implementación",
          author="GestionaSV ERP", subject="Ventas, DTE multiemisor, libros de IVA y F-07 en El Salvador")
frame = Frame(ML, MB, CW, H - MT - MB, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
doc.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=cover),
                      PageTemplate(id="normal", frames=[frame], onPage=page_deco)])
doc.multiBuild(story)
print("ok")

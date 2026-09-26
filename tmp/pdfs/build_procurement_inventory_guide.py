from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path.cwd()
MD_PATH = ROOT / "docs" / "flujo-compras-inventario-retaceo.md"
PDF_PATH = ROOT / "output" / "pdf" / "guia-flujo-compras-inventario-retaceo.pdf"

pages = [
    {
        "title": "Guía funcional: compras, recepción, retaceo e inventario",
        "subtitle": "Documento preliminar para alinear al equipo y capacitar usuarios",
        "blocks": [
            {"type": "p", "text": "Fecha de revisión: 26 de septiembre de 2026. Esta guía describe el flujo que se encontró en el repositorio del ERP y separa el comportamiento implementado de las propuestas todavía pendientes de decisión."},
            {"type": "callout", "label": "Lectura importante", "text": "No se propone rehacer todo el ERP. El flujo de compras existe. Inventario también tiene backend y algunas pantallas; lo que falta conectar es, principalmente, la recepción de compras con los movimientos de stock y el efecto del retaceo sobre el costo inventariable."},
            {"type": "flow", "text": "Necesidad de sucursal -> Solicitud de compra SCR -> Aprobación -> Solicitud de precio COT -> Respuesta del proveedor -> Evaluación y selección -> Orden de compra OC -> Recepción física -> Retaceo -> Inventario y Kardex"},
            {"type": "h2", "text": "Tres términos para no confundir"},
            {"type": "table", "headers": ["Término", "Significado práctico"], "rows": [
                ["Solicitud de compra SCR", "Necesidad interna de una sucursal o área. Todavía no es una compra ni aumenta el stock."],
                ["Solicitud de cotización COT", "Pedido de precio preparado para un proveedor. En el sistema, el mismo registro COT recibe después la respuesta del proveedor."],
                ["Oferta del proveedor", "Precio, moneda, impuestos, entrega y condiciones que el equipo registra cuando el proveedor responde al COT."]
            ]},
            {"type": "callout", "label": "Estado actual", "text": "La respuesta del proveedor se registra manualmente en la pantalla de la cotización. En el flujo revisado no aparece una bandeja que lea correos ni un campo para adjuntar el PDF de la oferta."},
        ],
    },
    {
        "title": "1. Solicitud interna y aprobación",
        "subtitle": "La solicitud expresa qué necesita la operación y para cuándo.",
        "blocks": [
            {"type": "p", "text": "El solicitante registra sucursal, almacén, fecha requerida, justificación y líneas de producto con unidad y cantidad. Al enviar el borrador, pasa a la cola de aprobación. Aprobar autoriza a continuar con el sondeo a proveedores; no crea una orden de compra ni registra existencias."},
            {"type": "table", "headers": ["Estado actual", "Qué significa", "Siguiente paso"], "rows": [
                ["Borrador (draft)", "Editable por quien gestiona la solicitud.", "Completar y enviar a aprobación, o cancelar."],
                ["Enviada (submitted)", "Pendiente de revisión y decisión.", "Aprobar o rechazar con permiso de aprobación."],
                ["Aprobada (approved)", "Autorizada para iniciar cotizaciones.", "Crear uno o más COT para proveedores."],
                ["Rechazada (rejected)", "No autorizada; estado terminal en el flujo actual.", "Aclarar motivo y crear una nueva solicitud si corresponde."],
                ["Parcialmente cotizada (partially_quoted)", "Hay respuestas para parte de las cantidades solicitadas.", "Continuar con ofertas o evaluar lo recibido."],
                ["Cotizada (quoted)", "La cobertura de cotización registrada alcanza las cantidades solicitadas.", "Comparar ofertas y preparar una orden."],
                ["Parcialmente ordenada (partially_ordered)", "Solo parte de lo cotizado se convirtió en orden.", "Completar la necesidad o cerrar según la operación."],
                ["Completada (completed)", "La necesidad llegó al cierre de compras.", "Consulta histórica."],
                ["Cancelada (cancelled)", "La solicitud se anuló antes de completar el flujo.", "Consulta histórica."]
            ]},
            {"type": "callout", "label": "Control de aprobación", "text": "La decisión debe seguir protegida por purchase_requests:approve. La tarjeta o el dashboard facilita encontrar y revisar solicitudes, pero no debe aprobar por sí solo. Conviene confirmar si la persona solicitante puede aprobar su propia solicitud; esa regla no se observa aplicada en el flujo actual."},
            {"type": "p", "text": "En el listado actual existe un filtro por estado, pero no una cola con conteo ni acciones de aprobación en la fila. La aprobación ocurre desde el detalle. Una mejora útil es mostrar una tarjeta de pendientes y un acceso directo a revisar cada SCR."},
        ],
    },
    {
        "title": "2. Cotizaciones a proveedores",
        "subtitle": "El COT une la solicitud enviada y la respuesta registrada.",
        "blocks": [
            {"type": "p", "text": "El comprador selecciona proveedor y moneda, agrega notas, vincula solicitudes aprobadas o con cotizaciones previas y marca las líneas y cantidades que pedirá cotizar. El formulario actual permite solicitudes aprobadas, parcialmente cotizadas y cotizadas. El borrador se crea para un proveedor. Para comparar varios proveedores, normalmente se prepara un COT por proveedor y se comparan sus respuestas para el mismo SCR."},
            {"type": "table", "headers": ["Estado COT", "Qué significa", "Acción siguiente"], "rows": [
                ["Borrador (draft)", "Se armó el pedido de precio; aún no se ha marcado como enviado.", "Revisar datos y enviar al proveedor."],
                ["Solicitada (requested)", "La solicitud de precio se envió; se espera respuesta.", "Registrar la oferta recibida o marcar vencimiento/cancelación."],
                ["Recibida (received)", "El equipo capturó manualmente los precios y condiciones.", "Evaluar la oferta."],
                ["En evaluación (under_evaluation)", "Se está comparando la respuesta.", "Seleccionar, rechazar o marcar vencida."],
                ["Seleccionada (selected)", "Oferta elegida para generar una orden.", "Crear la orden de compra."],
                ["Rechazada (rejected)", "Oferta no elegida.", "Consulta histórica."],
                ["Vencida (expired)", "La vigencia terminó sin selección.", "Solicitar una oferta vigente si aplica."],
                ["Cancelada (cancelled)", "Se canceló el pedido al proveedor.", "Consulta histórica."]
            ]},
            {"type": "callout", "label": "Por qué no ves el SCR en la lista COT", "text": "La lista de Cotizaciones muestra registros COT, no solicitudes SCR. Una solicitud aprobada aparece en el selector de Nueva cotización hasta que se crea el COT. La lista tampoco muestra hoy el código SCR asociado, por lo que conviene agregarlo como referencia visible."},
            {"type": "p", "text": "El formulario conserva proveedor, moneda, notas y líneas. Un acceso desde la tarjeta de solicitudes aprobadas podría abrir ese mismo formulario con el SCR ya seleccionado, evitando buscarlo de nuevo sin crear un flujo paralelo."},
        ],
    },
    {
        "title": "3. Orden de compra y recepción",
        "subtitle": "La orden compromete una compra; la recepción documenta lo que llegó.",
        "blocks": [
            {"type": "p", "text": "La orden se prepara a partir de una oferta seleccionada. Su aprobación y envío al proveedor son pasos distintos. La recepción solo puede originarse desde una orden enviada o parcialmente recibida, y permite registrar entregas parciales sin superar lo pendiente."},
            {"type": "table", "headers": ["Estado OC", "Significado operativo"], "rows": [
                ["Borrador (draft)", "Orden editable."],
                ["Pendiente de aprobación (pending_approval)", "En revisión de autorización."],
                ["Aprobada (approved)", "Autorizada para enviar."],
                ["Enviada (sent)", "Transmitida al proveedor; se puede recibir."],
                ["Parcialmente recibida (partially_received)", "Llegó parte de lo ordenado; queda cantidad pendiente."],
                ["Recibida (received)", "Se recibió toda la cantidad de la orden."],
                ["Cerrada (closed)", "Orden finalizada."],
                ["Cancelada (cancelled)", "Orden anulada."]
            ]},
            {"type": "table", "headers": ["Estado de recepción", "Significado operativo"], "rows": [
                ["Borrador (draft)", "Preparar cantidades reales recibidas por línea."],
                ["Recibida (received)", "Recepción confirmada; falta verificación."],
                ["Verificada (verified)", "La recepción pasó revisión."],
                ["Cerrada (closed)", "Recepción finalizada."],
                ["Cancelada (cancelled)", "Se anuló el borrador."]
            ]},
            {"type": "callout", "label": "No confundir", "text": "La cantidad de la orden es una cantidad esperada. La cantidad de una recepción es lo que físicamente llegó. Ninguna solicitud aprobada, cotización u orden debería sumarse al stock antes de una recepción física confirmada."},
        ],
    },
    {
        "title": "4. Retaceo e inventario",
        "subtitle": "El retaceo distribuye costo; Inventario controla cantidades y movimientos.",
        "blocks": [
            {"type": "p", "text": "El retaceo se crea desde una compra o recepción elegible, no directamente desde una orden. Distribuye flete, gastos y DAI entre líneas proporcionalmente al FOB. El IVA de importación se conserva por separado y no forma parte del costo total calculado por el retaceo."},
            {"type": "table", "headers": ["Estado del retaceo", "Significado"], "rows": [
                ["Borrador (draft)", "Captura editable de costos de importación."],
                ["Calculado (calculated)", "Distribución calculada y congelada para revisar."],
                ["Verificado (verified)", "Cálculo revisado."],
                ["Cerrado (closed)", "Retaceo finalizado."],
                ["Cancelado (cancelled)", "Retaceo anulado antes del cierre."]
            ]},
            {"type": "h2", "text": "Qué hay hoy en Inventario"},
            {"type": "p", "text": "En este repositorio Inventario no está vacío: hay backend para identidad de artículos, presentaciones, movimientos, saldos, consultas de stock, unidades logísticas, reservas y capacidad. También hay componentes y algunas pantallas frontend. Sin embargo, no aparece completa la pantalla operativa de movimientos conectada a compras, y el código revisado no enlaza automáticamente la recepción con un movimiento de inventario."},
            {"type": "callout", "label": "Brecha confirmada", "text": "La documentación técnica indica que el retaceo actual no genera movimientos de Inventario ni Kardex. Por tanto, el enlace pendiente es integración y experiencia operativa, no reconstruir todo el módulo desde cero."},
            {"type": "bullets", "items": [
                "Stock: cantidad física registrada por artículo, almacén/ubicación y estado. No es la cantidad pedida ni la cantidad de una orden.",
                "Capacidad: espacio físico disponible por peso o volumen. No equivale al stock que existe.",
                "Recepción: evidencia de llegada física y cantidades aceptadas.",
                "Retaceo: cálculo del costo importado por línea; no debe sumar unidades otra vez."
            ]},
        ],
    },
    {
        "title": "5. Recomendación de UX, permisos y plan seguro",
        "subtitle": "Cambios graduales para simplificar el trabajo sin rehacer el proceso completo.",
        "blocks": [
            {"type": "h2", "text": "Tarjetas útiles por etapa"},
            {"type": "bullets", "items": [
                "Solicitudes de compra: pendientes de aprobación y aprobadas listas para pedir precio.",
                "Cotizaciones: COT pendientes de respuesta del proveedor y ofertas recibidas por evaluar.",
                "Órdenes: pendientes de aprobación y parcialmente recibidas.",
                "Compras e Inventario: recepciones por verificar y artículos recibidos pendientes de ubicación."
            ]},
            {"type": "p", "text": "Las tarjetas deben mostrar conteos y llevar a una lista filtrada. Desde SCR aprobado se puede abrir el formulario COT existente con esa solicitud preseleccionada. La lista COT debe mostrar sus SCR relacionados. Mantener aprobación y selección protegidas por permiso y revisar el documento antes de cualquier acción."},
            {"type": "table", "headers": ["Acción", "Permiso que gobierna el acceso"], "rows": [
                ["Crear, ver y enviar SCR", "purchase_requests:read + purchase_requests:manage"],
                ["Revisar, aprobar o rechazar SCR", "purchase_requests:read + purchase_requests:approve"],
                ["Crear COT desde una solicitud", "purchase_requests:read + purchase_quotations:manage + suppliers:read"],
                ["Registrar respuesta y evaluar COT", "purchase_quotations:read + purchase_quotations:manage"],
                ["Seleccionar oferta ganadora", "purchase_quotations:read + purchase_quotations:select"],
                ["Crear o editar OC", "purchase_orders:read + purchase_orders:manage"],
                ["Aprobar y enviar OC", "purchase_orders:approve + purchase_orders:send"],
                ["Preparar, recibir y verificar mercancía", "purchases:read + purchases:manage + purchases:receive + purchases:verify"],
                ["Crear, calcular y verificar retaceo", "retaceos:read + retaceos:manage + retaceos:calculate + retaceos:verify"],
                ["Consultar y registrar movimientos de stock", "inventory:read + inventory:receive o inventory:move"]
            ]},
            {"type": "callout", "label": "Los cargos no conceden permisos por el nombre", "text": "Super Admin recibe todos los permisos en el catálogo base. El rol base ADMINISTRADOR no incluye automáticamente purchase_requests:approve; ese permiso debe asignarse al rol que la empresa defina como aprobador. Hallazgo técnico: la lista de solicitudes y el formulario COT no envían la sucursal seleccionada a la API; un usuario limitado a sucursales podría recibir 403. Corregir y validar ese alcance antes de confiar en los conteos del dashboard."},
            {"type": "h2", "text": "Orden recomendado de trabajo"},
            {"type": "numbered", "items": [
                "Acordar este vocabulario, quién aprueba por sucursal y qué significa una respuesta recibida del proveedor.",
                "Proteger los cambios locales y trabajar aislados; corregir primero el alcance de sucursal y confirmar la matriz de permisos.",
                "Implementar un primer dashboard de solo lectura con conteos, filtros y enlaces a los formularios existentes.",
                "Diseñar por separado la integración de recepción verificada -> movimiento de entrada de stock y retaceo cerrado -> actualización del costo, con trazabilidad e idempotencia.",
                "Probar recepción parcial, reintentos, permisos y sucursales antes de habilitar el nuevo flujo al personal."
            ]},
            {"type": "callout", "label": "Decisión de negocio pendiente", "text": "Propuesta para validar: aumentar cantidades de stock una sola vez al verificar la recepción física; al cerrar el retaceo, actualizar el costo unitario aterrizado sin volver a sumar cantidades. También debe decidirse si el stock queda disponible antes de cerrar el retaceo o en un estado de costo pendiente."},
            {"type": "p", "text": "Base revisada: docs/api.md, docs/database-schema.md, estados de solicitud, cotización, orden, compra y retaceo del dominio, y router backend de Inventario. El alcance funcional aquí descrito requiere validación del equipo antes de convertirse en reglas definitivas."},
        ],
    },
]

def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |")
    return "\n".join(lines)

md_parts = [
    "# " + pages[0]["title"],
    "",
    "**" + pages[0]["subtitle"] + "**",
    "",
]
for block in pages[0]["blocks"]:
    if block["type"] == "p":
        md_parts += [block["text"], ""]
    elif block["type"] == "callout":
        md_parts += ["> **" + block["label"] + ".** " + block["text"], ""]
    elif block["type"] == "flow":
        md_parts += ["**Flujo de extremo a extremo**", "", block["text"], ""]
    elif block["type"] == "h2":
        md_parts += ["## " + block["text"], ""]
    elif block["type"] == "table":
        md_parts += [md_table(block["headers"], block["rows"]), ""]
for page in pages[1:]:
    md_parts += ["## " + page["title"], "", "**" + page["subtitle"] + "**", ""]
    for block in page["blocks"]:
        kind = block["type"]
        if kind == "p":
            md_parts += [block["text"], ""]
        elif kind == "callout":
            md_parts += ["> **" + block["label"] + ".** " + block["text"], ""]
        elif kind == "h2":
            md_parts += ["### " + block["text"], ""]
        elif kind == "table":
            md_parts += [md_table(block["headers"], block["rows"]), ""]
        elif kind in ("bullets", "numbered"):
            for index, item in enumerate(block["items"], start=1):
                prefix = "- " if kind == "bullets" else str(index) + ". "
                md_parts.append(prefix + item)
            md_parts.append("")
MD_PATH.write_text("\n".join(md_parts).strip() + "\n", encoding="utf-8")

navy = colors.HexColor("#14263D")
blue = colors.HexColor("#0B83C6")
teal = colors.HexColor("#0C7A77")
ink = colors.HexColor("#202B38")
muted = colors.HexColor("#526273")
pale_blue = colors.HexColor("#EAF4FA")
pale_teal = colors.HexColor("#E9F5F3")
row_alt = colors.HexColor("#F5F8FA")
border = colors.HexColor("#D3DCE4")
white = colors.white

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="DocTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=22, leading=26, textColor=navy, alignment=TA_LEFT,
    spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="PageTitle", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=16, leading=19, textColor=navy, spaceBefore=0, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="PageSubtitle", parent=styles["Normal"], fontName="Helvetica",
    fontSize=9, leading=12, textColor=muted, spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=11, leading=14, textColor=blue, spaceBefore=7, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="BodyTextCustom", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.6, leading=11.2, textColor=ink, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="SmallTextCustom", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.7, leading=9.8, textColor=muted, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="CalloutText", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.3, leading=10.8, textColor=ink, spaceAfter=0,
))
styles.add(ParagraphStyle(
    name="TableHeaderCustom", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=7.8, leading=9.4, textColor=white,
))
styles.add(ParagraphStyle(
    name="TableCellCustom", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=7.4, leading=9.1, textColor=ink,
))
styles.add(ParagraphStyle(
    name="BulletCustom", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.3, leading=10.6, leftIndent=10, firstLineIndent=-8,
    textColor=ink, spaceAfter=3,
))

body_width = A4[0] - 36 * mm

def P(text, style="BodyTextCustom"):
    return Paragraph(escape(text), styles[style])

def make_table(headers, rows):
    count = len(headers)
    if count == 2:
        widths = [body_width * 0.29, body_width * 0.71]
    elif count == 3:
        widths = [body_width * 0.25, body_width * 0.38, body_width * 0.37]
    else:
        widths = [body_width / count] * count
    data = [[Paragraph(escape(str(value)), styles["TableHeaderCustom"]) for value in headers]]
    for row in rows:
        data.append([Paragraph(escape(str(value)), styles["TableCellCustom"]) for value in row])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), row_alt))
    table.setStyle(TableStyle(commands))
    return table

def make_callout(label, text):
    content = Paragraph(
        "<b>" + escape(label) + ":</b> " + escape(text),
        styles["CalloutText"],
    )
    table = Table([[content]], colWidths=[body_width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pale_teal),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B6DCD6")),
        ("LINEBEFORE", (0, 0), (0, 0), 3, teal),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table

def draw_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(navy)
    canvas.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(18 * mm, height - 8 * mm, "GESTIONASV  |  GUIA FUNCIONAL PRELIMINAR")
    canvas.setStrokeColor(border)
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.setFillColor(muted)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18 * mm, 9 * mm, "Compras, recepción, retaceo e inventario  |  26-09-2026")
    canvas.drawRightString(width - 18 * mm, 9 * mm, "Página " + str(doc.page))
    canvas.restoreState()

story = []
for page_index, page in enumerate(pages):
    if page_index:
        story.append(PageBreak())
    if page_index == 0:
        story.append(Spacer(1, 4 * mm))
        story.append(P(page["title"], "DocTitle"))
        story.append(P(page["subtitle"], "PageSubtitle"))
        story.append(Spacer(1, 2 * mm))
    else:
        story.append(P(page["title"], "PageTitle"))
        story.append(P(page["subtitle"], "PageSubtitle"))
    for block in page["blocks"]:
        kind = block["type"]
        if kind == "p":
            story.append(P(block["text"]))
        elif kind == "callout":
            story.append(make_callout(block["label"], block["text"]))
            story.append(Spacer(1, 5))
        elif kind == "flow":
            story.append(P("Flujo de extremo a extremo", "SectionTitle"))
            story.append(make_callout("Ruta general", block["text"]))
            story.append(Spacer(1, 4))
        elif kind == "h2":
            story.append(P(block["text"], "SectionTitle"))
        elif kind == "table":
            story.append(make_table(block["headers"], block["rows"]))
            story.append(Spacer(1, 6))
        elif kind in ("bullets", "numbered"):
            for index, item in enumerate(block["items"], start=1):
                prefix = "- " if kind == "bullets" else str(index) + ". "
                story.append(P(prefix + item, "BulletCustom"))
            story.append(Spacer(1, 3))

doc = SimpleDocTemplate(
    str(PDF_PATH),
    pagesize=A4,
    leftMargin=18 * mm,
    rightMargin=18 * mm,
    topMargin=18 * mm,
    bottomMargin=19 * mm,
    title="Guía funcional: compras, recepción, retaceo e inventario",
    author="GestionaSV",
    subject="Flujo de compras e integración con inventario",
)
doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
print(f"Markdown: {MD_PATH}")
print(f"PDF: {PDF_PATH}")

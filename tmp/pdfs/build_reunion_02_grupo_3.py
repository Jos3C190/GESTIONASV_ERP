from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable

OUT = Path("output/pdf/reunion-02-grupo-3-apuntes.pdf")
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-Bold")

NAVY = colors.HexColor("#142B45")
BLUE = colors.HexColor("#1468A8")
CYAN = colors.HexColor("#00A6C8")
INK = colors.HexColor("#182230")
MUTED = colors.HexColor("#5E6B78")
LINE = colors.HexColor("#D7E0E8")
PALE = colors.HexColor("#F2F7FA")
PALE_BLUE = colors.HexColor("#EAF4FB")
PALE_AMBER = colors.HexColor("#FFF6E5")
PALE_GREEN = colors.HexColor("#EAF6F1")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyX", fontName="Arial", fontSize=9, leading=12, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name="SmallX", fontName="Arial", fontSize=8, leading=10.5, textColor=MUTED, spaceAfter=3))
styles.add(ParagraphStyle(name="TitleX", fontName="Arial-Bold", fontSize=22, leading=25, textColor=NAVY, spaceAfter=4))
styles.add(ParagraphStyle(name="SubtitleX", fontName="Arial", fontSize=10, leading=13, textColor=MUTED, spaceAfter=8))
styles.add(ParagraphStyle(name="SectionX", fontName="Arial-Bold", fontSize=13, leading=16, textColor=NAVY, spaceBefore=5, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="MetaX", fontName="Arial-Bold", fontSize=8, leading=10, textColor=NAVY))
styles.add(ParagraphStyle(name="LabelX", fontName="Arial-Bold", fontSize=7.3, leading=9, textColor=NAVY))
styles.add(ParagraphStyle(name="CalloutX", fontName="Arial", fontSize=8.2, leading=11, textColor=INK))

ACCENTS = {
    "APUNTES DE REVISION": "APUNTES DE REVISIÓN",
    "REUNION": "REUNIÓN", "Reunion": "Reunión", "Numero": "Número", "numero": "número", "Pagina": "Página",
    "Vinculo": "Vínculo", "Navegacion": "Navegación", "Evaluacion": "Evaluación",
    "Comparacion": "Comparación", "Recepcion": "Recepción", "Inspeccion": "Inspección",
    "Ubicacion": "Ubicación", "Exportacion": "Exportación",
    "revision": "revisión", "Revision": "Revisión", "especificacion": "especificación",
    "distribucion": "distribución", "asignacion": "asignación", "menciono": "mencionó",
    "quedo": "quedó", "lineas": "líneas", "linea": "línea", "despues": "después",
    "envio": "envío", "cotizacion": "cotización", "comparacion": "comparación",
    "evaluacion": "evaluación", "mercaderia": "mercadería", "busqueda": "búsqueda",
    "segun": "según", "Segun": "Según", "explicacion": "explicación",
    "aprobacion": "aprobación", "reporto": "reportó", "aun": "aún",
    "modulos": "módulos", "modulo": "módulo", "limite": "límite",
    "informacion": "información", "decision": "decisión", "adjudicacion": "adjudicación",
    "ordenes": "órdenes", "fisico": "físico", "fisica": "física", "logistico": "logístico",
    "recepcion": "recepción", "automaticamente": "automáticamente",
    "inspeccion": "inspección", "estan": "están", "codigo": "código",
    "resalto": "resaltó", "ubicacion": "ubicación", "exhibicion": "exhibición",
    "operacion": "operación", "quien": "quién", "multiples": "múltiples",
    "implementarian": "implementarían", "catalogo": "catálogo",
    "ferreteria": "ferretería", "tambien": "también", "Tambien": "También",
}

def normalize_spanish(text):
    for source, target in ACCENTS.items():
        text = re.sub(r"\b" + re.escape(source) + r"\b", target, text)
    return text

def para(text, style="BodyX"):
    return Paragraph(normalize_spanish(text), styles[style])

def point(label, detail):
    return para(f'<font color="#00A6C8">-</font> <b>{label}</b> {detail}')

def heading(text):
    return [para(text, "SectionX"), HRFlowable(width="100%", thickness=0.8, color=LINE, spaceAfter=5)]

def callout(label, detail, shade=PALE_BLUE):
    t = Table([[para(label.upper(), "LabelX"), para(detail, "CalloutX")]], colWidths=[24*mm, 145*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), shade), ("BOX", (0,0), (-1,-1), 0.6, LINE),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    return t

def draw_page(canvas, doc):
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, h-10*mm, w, 10*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Arial-Bold", 8)
    canvas.drawString(16*mm, h-6.7*mm, "GESTIONASV ERP  |  APUNTES DE REVISIÓN")
    canvas.setStrokeColor(LINE)
    canvas.line(16*mm, 13*mm, w-16*mm, 13*mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Arial", 7.2)
    canvas.drawString(16*mm, 8.3*mm, "Reunión 2 - Grupo 3  |  29/09/2026")
    canvas.drawRightString(w-16*mm, 8.3*mm, f"Página {doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(
    str(OUT), pagesize=letter, leftMargin=16*mm, rightMargin=16*mm,
    topMargin=16*mm, bottomMargin=18*mm,
    title="Reunión 2 - Grupo 3 - Compras, cotizaciones y bodega",
    author="Apuntes de revisión - GESTIONASV ERP",
    subject="Apuntes consolidados del grupo 3",
)
story = []

# Pagina 1: roles y solicitud de oferta
story += [para("REUNION 2  /  GRUPO 3", "MetaX"), Spacer(1, 2*mm)]
story += [para("Compras, cotizaciones y<br/>flujo de bodega", "TitleX")]
story += [para("Apuntes de las sesiones y explicaciones compartidas durante la revision del sistema.", "SubtitleX")]
meta = Table([
    [para("REUNION", "MetaX"), para("GRUPO", "MetaX"), para("PREPARADO", "MetaX"), para("ESTADO", "MetaX")],
    [para("Numero 2"), para("3"), para("29/09/2026"), para("Notas consolidadas; pendientes por validar")],
], colWidths=[35*mm, 25*mm, 38*mm, 71*mm])
meta.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), PALE), ("BOX", (0,0), (-1,-1), 0.6, LINE),
    ("INNERGRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story += [meta, Spacer(1, 3*mm)]
story += [callout("Alcance", "Se separan los puntos atribuidos al flujo presentado, las ideas personales y las preguntas pendientes. Este documento recoge apuntes de revision; no es una especificacion aprobada.", PALE)]
story += [Spacer(1, 2*mm)]
story += heading("1. Roles y alcance de Compras")
story += [
    point("Las sucursales informan necesidades.", "Segun la explicacion, no realizan la compra al proveedor. El gerente o solicitante de cada sucursal comunica lo que necesita."),
    point("Compra centralizada.", "La compra se realiza desde la bodega general, principal, de distribucion o casa matriz, segun el nombre usado por la empresa. Desde ese punto se puede abastecer a las sucursales."),
    point("Compras puede iniciar por cuenta propia.", "El departamento puede pedir precios a proveedores sin esperar una solicitud previa de sucursal, por ejemplo para anticipar abastecimiento de la bodega central."),
    point("Vinculo del comprador por definir.", "Se menciono que el departamento de Compras está asociado a la bodega de distribucion. No quedo claro si esto representa una asignacion organizativa, el destino de las compras o el alcance de inventario."),
]
story += [callout("Nota personal", "El empleado o gerente prepara y revisa un borrador de solicitud; si tiene permiso, puede aprobarlo y enviarlo a Compras. Si no tiene ese permiso, lo remite para aprobación de una persona autorizada. Confirmar este paso y sus permisos con el grupo.", PALE_AMBER), Spacer(1, 2*mm)]
story += heading("2. Consolidado y envio a proveedores")
story += [
    point("Consolidar y luego separar.", "Compras puede reunir productos y cantidades de varias solicitudes, agregar necesidades propias de la bodega central y despues dividir el listado por proveedor o linea de producto."),
    point("Ejemplos de ferreteria.", "Las tejas pueden agruparse para proveedores de tejas y los tornillos para proveedores de tornillos. Un mismo listado de una linea se puede enviar a varios proveedores para recibir alternativas."),
    point("PDF para solicitar oferta.", "Antes de capturar la respuesta, generar un documento por proveedor con productos y cantidades solicitadas. El envio a varios proveedores crea la base para comparar sus respuestas."),
]
story += [callout("PDFs", "El PDF enviado al proveedor contiene lo que Compras solicita. El reporte PDF o Excel de comparacion, propuesto para uso interno, resume lo que contestaron los proveedores.", PALE_GREEN)]

story.append(PageBreak())
# Pagina 2: ofertas, comparacion y pantallas
story += heading("3. Registro de cotizaciones y comparacion de ofertas")
story += [
    point("Una respuesta por proveedor.", "Al recibir las ofertas, registrar cada una como cotizacion separada y vinculada al mismo listado enviado. No volver a buscar o escribir los productos si ya vienen de ese consolidado."),
    point("Respuestas parciales.", "Un proveedor puede cubrir toda la lista o solo una parte. Conservar cantidad solicitada, cantidad que ofrece o tiene disponible, precio, descuento o promocion, impuestos, condiciones, vigencia y tiempo o fecha de entrega."),
    point("Varias ofertas abiertas.", "Se reporto una dificultad para agregar o consultar otra cotizacion despues de guardar una como borrador. El flujo debe permitir registrar varias respuestas de proveedores para una misma solicitud de cotizacion o consolidado."),
    point("Comparacion lado a lado.", "La referencia muestra proveedores como columnas y productos como filas, con cantidad solicitada, cotizada y disponible; precio, descuento, impuesto, entrega, condiciones, vigencia, gastos y total de la oferta."),
    point("Decide el comprador.", "El sistema conserva y presenta los datos para comparar. La persona de Compras decide; puede adjudicar productos o cantidades a distintos proveedores y dejar sin adjudicar otras ofertas."),
    point("Ordenes por proveedor adjudicado.", "Una comparacion puede terminar en varias ordenes de compra, una por cada proveedor seleccionado y por las cantidades que se le asignen. Las ofertas no seleccionadas se conservan como historial."),
]
story += [callout("Pendiente", "En la explicacion se plantea comparar tres cotizaciones. Confirmar si tres es un limite fijo o solo un ejemplo de uso habitual.", PALE_AMBER), Spacer(1, 2*mm)]
story += [
    point("Adjunto opcional (idea tuya).", "Permitir anexar el archivo original que envio el proveedor, como PDF, Word o Excel, y agregar una nota. La oferta tambien debe quedar registrada en campos consultables."),
    point("Reporte interno (idea tuya).", "Poder descargar la comparacion como PDF o Excel, con informacion por producto y proveedor para revisar condiciones, precios y entrega, similar a una tabla comparativa de opciones."),
]
story += heading("4. Listados y modulos observados")
story += [
    point("Listado de cotizaciones.", "Se sugirieron filtros por estado, proveedor y fecha. Tambien se propuso consultar cotizaciones individuales o una vista agrupada por consolidado; el modo predeterminado queda por decidir."),
    point("Evaluacion de proveedores.", "El Grupo 3 muestra un acceso a evaluacion de proveedores. Se propuso agregar ese apartado al sistema propio, donde aun no existe. No se definieron criterios ni puntajes."),
    point("Recepciones de mercaderia.", "La referencia presenta busqueda por orden, factura o proveedor, filtro por estado y columnas de proveedor, factura, estado y total. En el sistema propio ya existe recepcion; revisar si su pantalla cubre esas consultas."),
    point("Navegacion de compras.", "La referencia agrupa cotizaciones y comparacion de ofertas; y bajo ordenes de compra muestra ordenes, recepciones, retaceo y tipos de gasto."),
]
story += [callout("Agrupar", "Al agrupar respuestas, conservar el total de cada cotizacion por proveedor: las ofertas son alternativas entre si y sus importes no deben sumarse como si fueran una sola compra.", PALE)]

story.append(PageBreak())
# Pagina 3: recepcion fisica y puntos pendientes
story += heading("5. Recepcion y proceso fisico de inventario - futuro")
story += [callout("Futuro", "La explicacion de viñeteado, ubicacion y seguimiento logistico se conserva como idea futura. La recepcion registrada no debe marcar por si sola el producto como disponible ni saltar el trabajo fisico del personal.", PALE_AMBER), Spacer(1, 2*mm)]
story += [
    point("Trazabilidad de embarques (futuro).", "Para cargas internacionales se mencionaron contenedores, capacidad y contenido, cantidades, origen, exportador, transportista, barco, flete, ruta, paradas y fechas entre puntos. Es un proceso complejo para evaluar en otra etapa."),
    point("Descarga y conteo.", "Registrar la llegada de transporte, el traslado hacia la bodega matriz y las cantidades que se descargan. La recepcion documenta el conteo real y las diferencias frente a lo pedido."),
    point("Inspeccion de estado.", "Verificar las unidades recibidas y registrar si estan buenas, dañadas o presentan fallas, antes de tratarlas como disponibles."),
    point("Viñeteado unitario.", "Tras verificar, colocar a cada producto su etiqueta con codigo de barras o QR interno. Se resalto que etiquetar grandes cantidades manualmente es un trabajo pesado."),
    point("Ubicacion y alta de stock.", "El personal de bodega escanea la etiqueta del producto y el codigo de su ubicacion al almacenarlo. La recepcion, el conteo y el etiquetado no reemplazan el registro de ubicacion; el sistema debe mostrar el avance y no asumir el paso como terminado."),
    point("Capacidad de ubicacion (por validar).", "Si no existe una ubicacion compatible con capacidad suficiente para una linea, mostrar un aviso y permitir que el personal elija manualmente otro destino. Confirmar si nuestros productos requieren esta validacion fisica."),
    point("Traslados y exhibicion.", "El envio desde bodega matriz a una sucursal y los movimientos de bodega interna a estante o exhibicion deben registrarse como pasos separados. El personal decide si repone exhibicion o conserva el articulo en bodega."),
]
story += [callout("Principio", "El sistema coordina el trabajo manual: organiza tareas, cantidades, etiquetas, verificaciones, ubicaciones y pendientes. No elimina el trabajo del bodeguero ni registra automaticamente una operacion fisica no realizada.", PALE_GREEN), Spacer(1, 2*mm)]
story += heading("6. Pendientes antes de convertirlo en requerimientos")
story += [
    point("Roles y aprobacion.", "Definir quién puede crear, aprobar y enviar solicitudes, y qué significa que el comprador esté asociado a la bodega de distribución."),
    point("Consolidado y cotizacion.", "Definir cómo se agrupan las solicitudes, cómo se asocian múltiples proveedores a un mismo envío y si la comparación admite un número fijo de ofertas."),
    point("Vistas y exportacion.", "Decidir la vista predeterminada del listado, el contenido del PDF para proveedores y el formato del informe de comparación para uso interno."),
    point("Evaluacion de proveedores.", "Acordar criterios de evaluación antes de diseñar reglas, puntajes o historial."),
    point("Alcance de bodega.", "Confirmar si el seguimiento de contenedores y la capacidad física por ubicación se necesitan para los productos del sistema y en qué fase se implementarían."),
]
story += [Spacer(1, 2*mm), para("Nota: los ejemplos de tejas, tornillos, refrigeradoras y contenedores ilustran el flujo y no definen el catalogo real de productos.", "SmallX")]

doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
print(OUT.resolve())

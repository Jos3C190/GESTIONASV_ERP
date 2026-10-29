from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, KeepTogether

OUT = Path("output/pdf/apuntes-equipo-nexora-erp.pdf")
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
styles.add(ParagraphStyle(name="BodyN", fontName="Arial", fontSize=9, leading=12.2, textColor=INK, spaceAfter=5))
styles.add(ParagraphStyle(name="SmallN", fontName="Arial", fontSize=7.9, leading=10.2, textColor=MUTED, spaceAfter=3))
styles.add(ParagraphStyle(name="TitleN", fontName="Arial-Bold", fontSize=23, leading=27, textColor=NAVY, spaceAfter=5))
styles.add(ParagraphStyle(name="SubtitleN", fontName="Arial", fontSize=10, leading=13.4, textColor=MUTED, spaceAfter=9))
styles.add(ParagraphStyle(name="SectionN", fontName="Arial-Bold", fontSize=13.2, leading=16, textColor=NAVY, spaceBefore=5, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="SubsectionN", fontName="Arial-Bold", fontSize=10.1, leading=13, textColor=BLUE, spaceBefore=4, spaceAfter=3, keepWithNext=True))
styles.add(ParagraphStyle(name="MetaN", fontName="Arial-Bold", fontSize=7.8, leading=10, textColor=NAVY))
styles.add(ParagraphStyle(name="LabelN", fontName="Arial-Bold", fontSize=7.3, leading=9, textColor=NAVY))
styles.add(ParagraphStyle(name="CalloutN", fontName="Arial", fontSize=8.4, leading=11.2, textColor=INK))
styles.add(ParagraphStyle(name="StepN", fontName="Arial", fontSize=8.6, leading=11.2, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle(name="TableN", fontName="Arial", fontSize=7.9, leading=10.1, textColor=INK))

def p(text, style="BodyN"):
    return Paragraph(text, styles[style])

def bullet(label, detail):
    return p(f'<font color="#00A6C8">-</font> <b>{label}</b> {detail}', "BodyN")

def step(n, title, detail):
    return p(f'<font color="#1468A8"><b>{n}.</b></font> <b>{title}</b> {detail}', "StepN")

def heading(text):
    return [p(text, "SectionN"), HRFlowable(width="100%", thickness=0.8, color=LINE, spaceAfter=6)]

def subheading(text):
    return p(text, "SubsectionN")

def callout(label, detail, shade=PALE_BLUE):
    t = Table([[p(label.upper(), "LabelN"), p(detail, "CalloutN")]], colWidths=[27*mm, 149*mm])
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
    canvas.drawString(16*mm, h-6.7*mm, "GESTIONASV ERP  |  APUNTES DE REFERENCIA")
    canvas.setStrokeColor(LINE)
    canvas.line(16*mm, 13*mm, w-16*mm, 13*mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Arial", 7.2)
    canvas.drawString(16*mm, 8.3*mm, "Equipo Nexora ERP / nombre por confirmar")
    canvas.drawRightString(w-16*mm, 8.3*mm, f"Página {doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(
    str(OUT), pagesize=letter, leftMargin=16*mm, rightMargin=16*mm,
    topMargin=16*mm, bottomMargin=18*mm,
    title="Apuntes del equipo Nexora ERP",
    author="Apuntes de revisión - GESTIONASV ERP",
    subject="Consolidación de compras, cotizaciones, comparación, órdenes y retaceo",
)
story = []

# Página 1 - portada y mapa
story += [p("APUNTES DE REFERENCIA", "MetaN"), Spacer(1, 2*mm)]
story += [p("Equipo Nexora ERP", "TitleN")]
story += [p("Consolidación de compras, solicitudes de cotización, respuestas de proveedores, comparación, órdenes de compra y retaceo.", "SubtitleN")]
meta = Table([
    [p("NOMBRE DEL EQUIPO", "MetaN"), p("NÚMERO", "MetaN"), p("FUENTE", "MetaN"), p("ESTADO DE ESTOS APUNTES", "MetaN")],
    [p("Nexora ERP (denominación por confirmar)", "TableN"), p("No identificado", "TableN"), p("Capturas y explicación verbal", "TableN"), p("Consolidados; varios puntos por validar", "TableN")],
], colWidths=[52*mm, 26*mm, 42*mm, 56*mm])
meta.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), PALE), ("BOX", (0,0), (-1,-1), 0.6, LINE),
    ("INNERGRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
]))
story += [meta, Spacer(1, 3*mm)]
story += [callout("Propósito", "Dejar reunidas las observaciones del equipo de referencia para leerlas y compararlas con GESTIONASV ERP. El nombre se recuerda como Nexora ERP / Nexus ERP; no se confirmó el número del equipo.", PALE)]
story += [Spacer(1, 3*mm)]
story += heading("Resumen del flujo de compras observado")
story += [
    step("1", "Consolidar", "las solicitudes y necesidades de compra en un listado maestro; el comprador puede revisar y ajustar cantidades."),
    step("2", "Separar por proveedor", "los productos que cada proveedor distribuye y preparar una solicitud de cotización distinta para cada uno."),
    step("3", "Enviar el PDF", "con las líneas y cantidades propuestas; conservar la relación entre cada PDF y el consolidado de origen."),
    step("4", "Registrar respuestas", "del proveedor usando el listado enviado como base, precargando productos y cantidades para editarlos."),
    step("5", "Comparar y adjudicar", "las ofertas manualmente, incluso por línea y en cantidades parciales."),
    step("6", "Crear órdenes", "por proveedor seleccionado; registrar gastos definitivos en la orden y llevarlos al retaceo."),
    step("7", "Recibir y costear", "la compra con cantidades reales y distribuir los costos de importación para obtener el costo final."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Distinción", "Se separan funciones que se observaron en la referencia, propuestas personales para GESTIONASV ERP y aspectos cuya regla todavía necesita confirmación.", PALE_BLUE)]

# Página 2 - consolidado y PDF RFQ
story += [PageBreak()]
story += [p("01  /  LISTADO MAESTRO Y SOLICITUDES A PROVEEDORES", "MetaN")]
story += heading("El consolidado es la base")
story += [
    p("El departamento de compras trabaja desde un listado de compra consolidado. Ese listado puede reunir productos y cantidades que provienen de solicitudes internas y puede organizarse para pedirlos a uno o más proveedores."),
    bullet("Revisión del comprador:", "puede revisar las necesidades antes de cotizar y ajustar la cantidad que enviará a cada proveedor."),
    bullet("Agrupación por proveedor:", "los productos se separan según quién los distribuye; por ejemplo, lácteos para proveedores de lácteos y bebidas para proveedores de bebidas."),
    bullet("Más de un proveedor:", "el mismo producto puede enviarse a varios proveedores para recibir alternativas. Cada proveedor recibe solo las líneas que se le están consultando."),
    bullet("Trazabilidad:", "cada solicitud enviada debe conservar el vínculo con el consolidado, las líneas, las cantidades y el proveedor destinatario."),
]
story += [subheading("PDF de solicitud de cotización")]
story += [
    p("Antes de registrar la respuesta del proveedor, el sistema debe permitir preparar e imprimir un PDF con lo que se desea cotizar. Debe producir archivos separados por proveedor a partir del consolidado maestro."),
    bullet("Contenido mínimo propuesto:", "empresa compradora, fecha, proveedor destinatario, líneas de producto, unidad y cantidad solicitada, además de espacio para datos de contacto o respuesta si aplica."),
    bullet("Salida:", "un PDF por proveedor; no un único documento mezclando productos de distribuidores distintos."),
    bullet("Uso:", "el equipo envía el PDF al proveedor y, cuando recibe su respuesta, registra las condiciones ofrecidas en el sistema."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Idea de adaptación", "El comprador debería poder revisar el consolidado, quitar líneas, cambiar cantidades y agregar productos o cantidades propias antes de generar los documentos para proveedores. Esta capacidad se planteó como criterio funcional; verificar qué parte ya existe en nuestro sistema.", PALE_AMBER)]
story += [Spacer(1, 3*mm)]
story += heading("No confundir los dos documentos")
tbl = Table([
    [p("DOCUMENTO", "MetaN"), p("QUIÉN LO GENERA", "MetaN"), p("QUÉ REPRESENTA", "MetaN")],
    [p("Solicitud de cotización (PDF)", "TableN"), p("Departamento de compras", "TableN"), p("Lo que la empresa solicita que el proveedor cotice.", "TableN")],
    [p("Cotización / respuesta del proveedor", "TableN"), p("Proveedor; luego se registra", "TableN"), p("Lo que el proveedor ofrece: cantidades, precios, entrega y condiciones.", "TableN")],
], colWidths=[50*mm, 48*mm, 78*mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), PALE), ("BOX", (0,0), (-1,-1), 0.6, LINE),
    ("INNERGRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
]))
story += [tbl]

# Página 3 - respuesta y comparación
story += [PageBreak()]
story += [p("02  /  RESPUESTA DEL PROVEEDOR Y COMPARACIÓN", "MetaN")]
story += heading("Precargar la respuesta desde el PDF enviado")
story += [
    p("Al registrar la cotización recibida, el usuario debería seleccionar la solicitud de cotización enviada a ese proveedor. El sistema recuperaría del registro guardado los productos y cantidades solicitadas, para que no tenga que volver a buscarlos y escribirlos desde cero."),
    bullet("Precarga:", "cargar automáticamente las líneas, productos, unidades, cantidades solicitadas, proveedor y referencia del documento enviado."),
    bullet("Edición:", "permitir cambiar la cantidad ofrecida, reducirla o quitar una línea si el proveedor no la cotiza; mantener visible la cantidad originalmente solicitada."),
    bullet("Datos de oferta:", "registrar disponibilidad, precio unitario, descuento, impuestos, días de entrega, vigencia, condiciones de pago, notas y gastos estimados cuando correspondan."),
    bullet("Respuesta parcial:", "aceptar que el proveedor cotice solo una parte de las líneas o cantidades."),
    bullet("Adjuntos opcionales:", "idea del usuario: permitir subir la respuesta recibida en PDF, Word o Excel, además de registrar notas. No se planteó que el sistema tenga que leer automáticamente ese archivo."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Alcance acotado", "La precarga debe partir de los datos del PDF que el sistema generó y guardó, no depender del reconocimiento automático del documento que devuelve el proveedor.", PALE_GREEN)]
story += [Spacer(1, 3*mm)]
story += heading("Comparar varias ofertas")
story += [
    p("El comprador necesita consultar las respuestas de varios proveedores para el mismo consolidado o solicitud enviada. La comparación debe presentar los datos de forma paralela, por proveedor y por producto."),
    bullet("Por producto:", "cantidad solicitada, cantidad ofrecida/disponible, precio, descuento, impuesto y total."),
    bullet("Por proveedor:", "plazo o fecha de entrega, vigencia, condiciones de pago, gastos y observaciones."),
    bullet("Motivos comerciales:", "registrar si el precio se explica por descuento, promoción, liquidación u otra condición, cuando el proveedor lo informe."),
    bullet("Decisión humana:", "el sistema muestra y conserva los datos; el comprador decide a quién comprar. No se debe escoger automáticamente al más barato."),
    bullet("Adjudicación parcial:", "permitir asignar productos o cantidades a proveedores distintos y dejar sin adjudicar líneas que no se comprarán."),
    bullet("Exportación interna:", "idea del usuario: descargar la comparación en PDF o Excel para revisar precios, cantidades, entregas y condiciones."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Cantidad de ofertas", "En la conversación se usaron tres cotizaciones como ejemplo habitual. No quedó confirmado si tres sería un límite del sistema o solo una referencia.", PALE_AMBER)]

# Página 4 - órdenes y gastos
story += [PageBreak()]
story += [p("03  /  ÓRDENES DE COMPRA Y GASTOS", "MetaN")]
story += heading("De la adjudicación a las órdenes")
story += [
    p("La adjudicación de las líneas determina qué se le comprará a cada proveedor. Una adjudicación puede producir varias órdenes de compra, una por proveedor seleccionado, con sus líneas y cantidades correspondientes."),
    bullet("Origen trazable:", "mantener el vínculo entre consolidado, PDF enviado, respuesta del proveedor, decisión de compra y orden generada."),
    bullet("No copiar toda la oferta:", "la orden debe llevar únicamente las líneas y cantidades que el comprador adjudicó a ese proveedor."),
    bullet("Ofertas sin adjudicar:", "conservar las respuestas para consulta histórica y comparación; no convertirlas todas en órdenes."),
]
story += [Spacer(1, 2*mm)]
story += heading("Gastos de cotización frente a gastos de orden")
expenses = Table([
    [p("ETAPA", "MetaN"), p("NATURALEZA", "MetaN"), p("USO", "MetaN")],
    [p("Cotización", "TableN"), p("Estimados o provisionales", "TableN"), p("Dar una perspectiva del costo esperado para comparar ofertas.", "TableN")],
    [p("Orden de compra", "TableN"), p("Definitivos o reales", "TableN"), p("Registrar los gastos efectivamente asociados a la compra y usarlos en el retaceo.", "TableN")],
], colWidths=[37*mm, 51*mm, 88*mm])
expenses.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), PALE), ("BOX", (0,0), (-1,-1), 0.6, LINE),
    ("INNERGRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
]))
story += [expenses, Spacer(1, 2*mm)]
story += [
    p("La referencia mostró en el detalle de una orden una sección de gastos adicionales con acción para agregar gastos. El usuario pidió que las líneas puedan agregarse, editarse y eliminarse y que tengan documentos de respaldo."),
    bullet("Campos observados/propuestos:", "tipo de gasto, descripción, importe, indicador costeable y documentos adjuntos."),
    bullet("Tipos de gasto:", "administrar opciones como flete, aduana y otros conceptos, según las necesidades de la empresa."),
    bullet("Respaldo:", "adjuntar archivos que expliquen o justifiquen el cargo o un cambio de precio."),
    bullet("Uso posterior:", "copiar al retaceo los gastos definitivos de la orden, evitando volver a digitarlos; el retaceo también puede registrar costos adicionales."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Por definir", "Aclarar qué significa exactamente el indicador “Costeable” en la orden y cómo se relaciona con “capitalizable” en el retaceo.", PALE_AMBER)]

# Página 5 - retaceo
story += [PageBreak()]
story += [p("04  /  RETACEO Y COSTO DE IMPORTACIÓN", "MetaN")]
story += heading("Datos de cabecera y gastos")
story += [
    bullet("País de origen:", "agregarlo o verificar que exista en nuestro retaceo. En la referencia aparece como dato de cabecera."),
    bullet("Factura y póliza de importación:", "la referencia muestra esos campos; el usuario cree que ya existe una póliza en nuestro sistema y no pidió ampliar ese alcance ahora."),
    bullet("Gastos de la orden:", "reunir en el retaceo los gastos definitivos de la orden de compra y permitir costos adicionales cuando surjan."),
    bullet("Datos de cada costo:", "tipo, descripción, moneda, importe, tipo y fecha de cambio, categoría, método de distribución y tratamiento."),
    bullet("Comprobante adjunto:", "cada gasto debe permitir adjuntar el archivo que lo respalda; no basta escribir el nombre o número del documento. La observación pide aceptar PDF u otros formatos, y dejar claro cuáles admite el sistema."),
]
story += [subheading("Categorías y reglas de distribución mencionadas")]
methods = Table([
    [p("CATEGORÍAS", "MetaN"), p("MÉTODOS", "MetaN"), p("TRATAMIENTO", "MetaN")],
    [p("IVA, DAI/arancel, flete, seguro, IVA de importación y otros impuestos o gastos.", "TableN"),
     p("Valor FOB, cantidad, peso, volumen, valor CIF, partes iguales y distribución manual.", "TableN"),
     p("Capitalizable, impuesto recuperable y componente CIF, según aplique.", "TableN")],
], colWidths=[62*mm, 62*mm, 52*mm])
methods.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), PALE), ("BOX", (0,0), (-1,-1), 0.6, LINE),
    ("INNERGRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
]))
story += [methods, Spacer(1, 2*mm)]
story += heading("Cálculo, distribución y verificación")
story += [
    bullet("Costos capitalizables:", "se distribuyen entre las líneas y modifican el costo unitario de los productos."),
    bullet("Costos no capitalizables:", "deben mostrarse, pero no sumarse al costo unitario inventariable, conforme a la regla contable que se defina."),
    bullet("Cálculo:", "al calcular, congelar las bases de distribución utilizadas y dejar visible cómo se asignó cada gasto a cada línea."),
    bullet("Resultado visible:", "FOB original, gastos por categoría, asignación por producto, costo unitario final, costo total por línea y total del retaceo."),
    bullet("Validación independiente:", "comprobar fórmulas y resultados con una hoja de cálculo de control; probar compras grandes, varios productos y cantidades altas."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Punto crítico", "El usuario indicó que las fórmulas y sus bases son esenciales. No se debe asumir el origen del FOB: confirmar si se toma de la factura, de la compra recibida u otro dato antes de validar el cálculo.", PALE_AMBER)]
story += [Spacer(1, 2*mm)]
story += [p("Los ejemplos del sistema de referencia usan importes y cantidades pequeños. Las reglas deben funcionar también con compras internacionales de alto valor y grandes volúmenes.", "SmallN")]

# Página 6 - revisión y atribuciones
story += [PageBreak()]
story += [p("05  /  LISTA DE REVISIÓN Y PUNTOS ABIERTOS", "MetaN")]
story += heading("Qué revisar en GESTIONASV ERP")
review_items = [
    ("PDF a proveedores", "generación separada por proveedor desde un consolidado y vínculo persistente con las líneas enviadas."),
    ("Registro de respuesta", "selección del PDF/solicitud enviada y precarga de productos y cantidades; edición de respuesta parcial."),
    ("Comparación", "varias respuestas visibles a la vez, datos por línea y proveedor, adjudicación parcial y exportación PDF/Excel."),
    ("Órdenes", "órdenes por proveedor con solo las líneas adjudicadas y vínculos de trazabilidad."),
    ("Gastos", "gastos definitivos con tipo, importe, indicador costeable, documentos y acciones de agregar/editar/eliminar."),
    ("Retaceo", "país de origen, consolidación de gastos definitivos, comprobante adjunto por gasto, costos adicionales, métodos de distribución y fórmulas."),
]
for label, detail in review_items:
    story.append(bullet(label + ":", detail))
story += [Spacer(1, 2*mm)]
story += heading("Aspectos que quedaron sin confirmar")
story += [
    bullet("Identidad:", "confirmar si el nombre oficial es Nexora ERP o Nexus ERP y cuál es el número del equipo."),
    bullet("Límite de comparación:", "confirmar si el ejemplo de tres ofertas es un límite o una práctica habitual."),
    bullet("Reglas contables:", "definir FOB, CIF, capitalizable, costeable e impuesto recuperable, así como las bases y fórmulas aplicables."),
    bullet("Auditoría de módulos:", "no quedó comprobado de punta a punta que los cinco módulos mencionados estén completos. Revisar integración, datos, adjuntos y acciones; la lista exacta de esos cinco módulos no quedó identificada en estas notas."),
    bullet("Catálogo de proveedores:", "asociar nombres/códigos de proveedor con productos equivalentes sería complejo. Se dejó fuera del alcance inmediato; por ahora el comprador puede relacionar manualmente la línea ofrecida con el producto interno."),
    bullet("Evaluación de proveedores:", "aparece como módulo/enlace en una captura, pero no se definieron criterios ni funcionamiento en estas observaciones."),
]
story += [Spacer(1, 2*mm)]
story += [callout("Nota de atribución", "La explicación detallada sobre descarga física, viñeteado con Code 128/QR y ubicación en bodega quedó en un apunte separado atribuido al grupo R. No se incorpora como requisito propio de Nexora sin confirmar que pertenezca a este equipo.", PALE_AMBER)]
story += [Spacer(1, 3*mm)]
story += [p("Documento de trabajo para lectura y revisión. Las observaciones no implican que todas las funciones estén aprobadas o implementadas en GESTIONASV ERP.", "SmallN")]

doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
print(OUT.resolve())

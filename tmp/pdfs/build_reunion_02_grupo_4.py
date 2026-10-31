from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable

OUT = Path("output/pdf/reunion-02-grupo-4-apuntes.pdf")
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
styles.add(ParagraphStyle(name="BodyG4", fontName="Arial", fontSize=8.9, leading=11.8, textColor=INK, spaceAfter=3.7))
styles.add(ParagraphStyle(name="SmallG4", fontName="Arial", fontSize=7.8, leading=10.2, textColor=MUTED, spaceAfter=3))
styles.add(ParagraphStyle(name="TitleG4", fontName="Arial-Bold", fontSize=22, leading=25, textColor=NAVY, spaceAfter=4))
styles.add(ParagraphStyle(name="SubtitleG4", fontName="Arial", fontSize=10, leading=13, textColor=MUTED, spaceAfter=8))
styles.add(ParagraphStyle(name="SectionG4", fontName="Arial-Bold", fontSize=13, leading=16, textColor=NAVY, spaceBefore=5, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="MetaG4", fontName="Arial-Bold", fontSize=8, leading=10, textColor=NAVY))
styles.add(ParagraphStyle(name="LabelG4", fontName="Arial-Bold", fontSize=7.3, leading=9, textColor=NAVY))
styles.add(ParagraphStyle(name="CalloutG4", fontName="Arial", fontSize=8.1, leading=10.8, textColor=INK))

def para(text, style="BodyG4"):
    return Paragraph(text, styles[style])

def point(label, detail):
    return para(f'<font color="#00A6C8">-</font> <b>{label}</b> {detail}')

def heading(text):
    return [para(text, "SectionG4"), HRFlowable(width="100%", thickness=0.8, color=LINE, spaceAfter=5)]

def callout(label, detail, shade=PALE_BLUE):
    table = Table([[para(label.upper(), "LabelG4"), para(detail, "CalloutG4")]], colWidths=[24*mm, 145*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), shade), ("BOX", (0,0), (-1,-1), 0.6, LINE),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    return table

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
    canvas.drawString(16*mm, 8.3*mm, "Reunión 2 - Grupo 4  |  30/09/2026")
    canvas.drawRightString(w-16*mm, 8.3*mm, f"Página {doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(
    str(OUT), pagesize=letter, leftMargin=16*mm, rightMargin=16*mm,
    topMargin=16*mm, bottomMargin=18*mm,
    title="Reunión 2 - Grupo 4 - Abastecimiento, análisis y recepción",
    author="Apuntes de revisión - GESTIONASV ERP",
    subject="Apuntes consolidados del grupo 4",
)
story = []

# Página 1: abastecimiento central y consolidado
story += [para("REUNIÓN 2  /  GRUPO 4", "MetaG4"), Spacer(1, 2*mm)]
story += [para("Abastecimiento, demanda y<br/>flujo de inventario", "TitleG4")]
story += [para("Apuntes consolidados de las observaciones y ejemplos compartidos por el grupo.", "SubtitleG4")]
meta = Table([
    [para("REUNIÓN", "MetaG4"), para("GRUPO", "MetaG4"), para("PREPARADO", "MetaG4"), para("ESTADO", "MetaG4")],
    [para("Número 2"), para("4"), para("30/09/2026"), para("Notas consolidadas; pendientes por validar")],
], colWidths=[35*mm, 25*mm, 38*mm, 71*mm])
meta.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), PALE), ("BOX", (0,0), (-1,-1), 0.6, LINE),
    ("INNERGRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story += [meta, Spacer(1, 3*mm)]
story += [callout("Alcance", "Se recogen los puntos del grupo 4 y se identifican los aspectos todavía por aclarar. Los ejemplos ilustran el flujo y no constituyen reglas aprobadas.", PALE)]
story += [Spacer(1, 2*mm)]
story += heading("1. Compra centralizada y papel de las sucursales")
story += [
    point("Las sucursales comunican su necesidad.", "No compran directamente al proveedor. Sus solicitudes sirven a Compras para conocer qué productos se están agotando y en qué ubicaciones."),
    point("La compra llega a la bodega general.", "Las compras se reciben en la bodega principal o de distribución. Después se envían a las bodegas internas de las sucursales mediante traslados registrados."),
    point("La bodega central también se abastece.", "El departamento puede comprar para cubrir solicitudes de sucursales y agregar productos o cantidades que considere necesarios para el inventario central."),
]
story += [callout("Ejemplo", "En 15 días, una sucursal solicita 40 unidades de frijoles y otra 60. Compras ve una demanda reportada de 100, pero puede elegir comprar más, menos o nada según lo que ya tenga pedido o abastecido en la bodega central.", PALE_BLUE)]
story += [Spacer(1, 2*mm)]
story += heading("2. Resumen de compra editable")
story += [
    point("Agrupar solicitudes.", "El resumen reúne productos iguales y cantidades solicitadas por diferentes sucursales, conservando el origen de cada necesidad."),
    point("Revisar existencias y pedidos previos.", "Antes de cotizar, Compras puede excluir una línea si el producto ya está abastecido o viene en camino. Las sucursales pueden no conocer esas compras centralizadas."),
    point("Agregar abastecimiento propio.", "Compras puede añadir productos o cantidades para la bodega central aunque ninguna sucursal los haya solicitado."),
    point("El comprador define la lista final.", "El resumen es una base editable: puede aceptar, reducir o descartar necesidades de sucursales y sumar necesidades de abastecimiento antes de enviarlo a proveedores."),
]
story += [callout("Origen", "Aunque se ajuste la cantidad que se comprará, conviene conservar cuánto pidió cada sucursal y cuánto se agregó, quitó o adjudicó desde Compras.", PALE_GREEN)]

story.append(PageBreak())
# Página 2: comparación, órdenes y análisis
story += heading("3. Comparación y adjudicación por proveedor")
story += [
    point("Comparar por producto.", "Compras necesita ver precios, disponibilidad, descuentos y tiempos de entrega de cada proveedor para cada línea del resumen."),
    point("Decisión humana.", "El precio no es el único criterio: el comprador puede preferir una oferta más cara si llega antes, o repartir cantidades entre proveedores según convenga."),
    point("Adjudicación parcial.", "Ejemplo: asignar 15 unidades al proveedor A y 5 al proveedor B. La decisión debe guardar proveedor, producto y cantidad elegida, además de las ofertas comparadas."),
    point("Una orden por proveedor.", "Cada adjudicación genera una orden de compra separada con las líneas y cantidades correspondientes. La orden mantiene el vínculo con la cotización y la decisión que la originó."),
]
story += [callout("Decisión humana", "El sistema presenta las alternativas y registra la decisión del comprador. No determina por sí solo cuál proveedor es el mejor.", PALE_AMBER), Spacer(1, 2*mm)]
story += heading("4. Estado de las solicitudes de sucursal")
story += [
    point("Al crear el resumen.", "Se propuso cambiar a Aprobada el estado de las solicitudes incluidas en el resumen, para que los gerentes sepan que Compras aceptó atender esa necesidad."),
    point("No confundir aprobación con tránsito.", "Aprobada puede significar que Compras incorporó o aceptó la necesidad. El producto no necesariamente ya fue ordenado o enviado por el proveedor."),
]
story += [callout("Pendiente", "Definir si la aprobación aplica a toda la solicitud o puede ser parcial por línea. Si se quiere informar que el producto va en camino, considerar un estado posterior cuando la orden se envíe o el proveedor confirme el despacho.", PALE_AMBER), Spacer(1, 2*mm)]
story += heading("5. Análisis histórico de demanda")
story += [
    point("Mini panel de análisis (idea tuya).", "Agregar desde el dashboard de Compras un acceso a gráficas de demanda por sucursal, región, producto y temporada."),
    point("Guardar fechas e historial.", "Conservar las fechas de solicitudes, ventas y movimientos para observar patrones a lo largo del tiempo y comparar zonas o temporadas."),
    point("Filtros temporales sugeridos.", "7 días, 15 días, mes, trimestre, semestre, año y rango personalizado."),
    point("Señales de demanda.", "Las solicitudes repetidas pueden indicar desabastecimiento o interés por una marca en una sucursal. El análisis permitiría revisar esas tendencias; la decisión de compra sigue siendo del equipo."),
]
story += [callout("Datos", "Las solicitudes muestran necesidades reportadas. Para afirmar cuántas unidades se vendieron, se necesitan los registros reales de ventas. Definir si las gráficas usarán solicitudes, ventas o ambas.", PALE_BLUE)]

story.append(PageBreak())
# Página 3: recepción, etiqueta, ubicación y retaceo
story += heading("6. Recepción física de la compra")
story += [
    point("Conteo al descargar.", "Registrar los productos que llegan del camión o contenedor y compararlos con las cantidades de la orden. Puede haber faltantes o excedentes."),
    point("Condición y espacio.", "Anotar daños o condiciones del producto y, si es necesario, sus medidas o el espacio que ocupa para decidir una ubicación compatible."),
    point("La recepción no equivale a stock disponible.", "La recepción deja constancia de lo descargado y verificado. Todavía siguen el viñeteado y la ubicación física en la bodega."),
]
story += [Spacer(1, 2*mm)]
story += heading("7. Viñeteado, ubicación y distribución")
story += [
    point("Identificación interna.", "Después de verificar los productos, generar e imprimir una etiqueta con el código interno para colocarla en cada unidad."),
    point("Información de trazabilidad.", "Se mencionó mostrar en la etiqueta la fecha de recepción y el número de la orden de compra, para identificar de qué compra procede el producto."),
    point("Formatos de código propuestos.", "Se propuso considerar código de barras Code 128 y QR. El QR puede servir cuando se necesite asociar más información; falta definir qué datos se codifican y qué formato se usa para productos y ubicaciones."),
    point("Escaneo de producto y rack.", "El bodeguero escanea la etiqueta del producto y el código de la ubicación o rack. El sistema relaciona el artículo con su ubicación física y registra el avance de la tarea."),
    point("De bodega central a sucursales.", "Una vez recibidos y ubicados en la bodega de distribución, los productos se despachan a las bodegas de las sucursales mediante movimientos separados."),
]
story += [callout("Código", "Se indicó que unidades del mismo producto pueden compartir el código interno, mientras la fecha y la orden ayudan a distinguir su procedencia. Confirmar si basta con identificar producto y lote/cantidad, o si ciertos artículos requieren un código único por unidad.", PALE_AMBER), Spacer(1, 2*mm)]
story += heading("8. Retaceo y validación integral")
story += [
    point("Costo final.", "El retaceo puede avanzar a la par de la recepción y determina el costo asociado a los productos con las cantidades reales recibidas. Ese costo debe quedar relacionado con la línea de inventario, la recepción y la orden de compra que le corresponden."),
    point("Cantidad y costo son datos distintos.", "El conteo y la ubicación reflejan las unidades físicamente recibidas; el retaceo completa el costo final. Confirmar si el stock queda disponible antes de terminar el retaceo o mantiene un estado de costo pendiente."),
    point("Validar toda la cadena.", "Revisar la consistencia y las relaciones entre solicitud, resumen consolidado, cotizaciones por proveedor, comparación, órdenes adjudicadas, recepción real, retaceo, etiquetas, ubicación y traslado a sucursales."),
]
story += [callout("Criterio operativo", "El sistema debe coordinar las tareas que realiza el personal de bodega y registrar lo que ocurrió físicamente. No debe asumir que la descarga, el viñeteado o la ubicación se completaron solo porque existe una orden o una recepción.", PALE_GREEN)]

doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
print(OUT.resolve())

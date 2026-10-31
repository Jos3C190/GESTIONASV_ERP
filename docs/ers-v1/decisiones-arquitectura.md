# Decisiones de arquitectura para ERS 1.0

Fecha: 19/10/2026. Versión: 1.0. Estado: ADR-01–05 implementados en B01–B05; el alcance comercial de ADR-06/07 implementado en B06. La entrega y devolución restantes se reservan para B07–B08; revisión completa y aceptación integrada reservadas para B08.

El usuario confirmó la asociación de bodega central a una matriz administrativa y el trabajo por bloques con documentación. Las decisiones técnicas siguientes son la arquitectura recomendada para ejecutar ese encargo. Cualquier cambio posterior se registra con razón, impacto y pruebas; no se transforma una diferencia con la ERS en cumplimiento declarado sin evidencia.

## ADR-01. Matriz y bodega central

Usar la entidad Branch existente. Identificar la sede matriz de forma explícita; si no hay un campo equivalente, añadir is_headquarters con unicidad por empresa entre sedes activas. La sede no necesita convertirse en punto de venta. Mantener Warehouse.is_central como función del almacén, pero exigir branch_id de la matriz de la misma empresa.

Migrar las referencias actuales conservando las bodegas. Reutilizar una sede matriz inequívoca o crear «Casa matriz» con datos mínimos válidos. Evitar crear otra empresa, otra bodega física o copiar existencias. Revisar todos los consumidores que deducen centralidad por branch_id nulo, incluyendo permisos, compras, consolidaciones, catálogos y semillas.

Los documentos históricos confirmados conservan sus datos; su lectura puede resolver la relación organizacional por la bodega. No reescribir documentos históricos para rellenar un nuevo campo de presentación.

## ADR-02. Lote de producto sobre la estructura existente

Conservar inventory_lots como cabecera de recepción. Dar a cada inventory_lot_details una identidad/código único por empresa, correspondiente al producto y detalle real de recepción. Esta es la identidad canónica del lote de producto. Si un mismo producto aparece en dos detalles reales, conservar dos orígenes distinguibles.

La etiqueta nueva, Kardex, consulta por ubicación y traslado usan esa identidad. El código de cabecera anterior queda como alias de recepción y puede resolver varios lotes de producto; se muestra esa pluralidad. El lote del fabricante sigue siendo otro dato. No modificar snapshots de impresiones ni movimientos históricos. Las etiquetas anteriores y QR mantienen resolución por su identidad/alias original; cambiar el esquema no simula una reimpresión ni invalida silenciosamente su confirmación.

Ofrecer una proyección compatible con inventory_location_details por lote canónico y ubicación, con desglose de estado. Reutilizar HUs activas y relaciones de origen; no copiar saldos en una segunda tabla editable. El saldo agregado existente por fabricante no sustituye esa proyección. Su suma debe conciliar con HUs, movimientos y total de empresa.

Para el mapeo docente, el «lote» funcional corresponde al detalle canónico y la cabecera es un agrupador adicional. Documentar esta equivalencia y sus límites; la aceptación literal de nombres físicos de tablas no está confirmada por los documentos.

## ADR-03. Documentos de traslado y ubicación móvil

Crear cabecera/detalles de traslado con identificadores estables, empresa, origen/destino, vehículo, lotes, HUs/asignaciones, cantidades despachadas/recibidas, documentos de solicitud enlazados, actor y fechas. Usar FK compuestas por empresa donde corresponda. Los movimientos enlazan el documento real; evitar interpretar texto libre como única fuente de relación.

Estados: PREPARACIÓN, EN TRÁNSITO, RECIBIDO, INCIDENCIA y CANCELADO antes de despacho. Una recepción parcial mantiene EN TRÁNSITO con progreso recibido; una discrepancia declarada abre INCIDENCIA. Una resolución conserva su historial y puede volver a tránsito o cerrar recibido cuando no queda cantidad sin resolver. Toda pérdida/merma necesita el ajuste autorizado que la explica; cambiar estado no destruye stock.

Preparación no altera stock físico. El despacho valida y bloquea la disponibilidad actual. La recepción parcial conserva el remanente en tránsito. Reintentos y concurrencia no duplican despacho o recepción.

Para cumplir la ubicación de vehículo manteniendo locations.warehouse_id, usar un almacén técnico de tránsito por empresa, adscrito a la matriz, con ubicaciones de tipo vehicle vinculadas a vehículos de esa empresa. Es un contenedor lógico del stock que viaja; no duplica la bodega física ni la mercancía. Distinguirlo de las bodegas seleccionables para recepción comercial, venta y almacenamiento normal. Excluirlo de la ocupación física de estantes de la bodega central; incluirlo en existencia/valor global y conciliación.

Así el despacho registra central → vehículo y la recepción vehículo → sucursal. Permisos de recepción se autorizan por documento y destino; no conceder acceso global de empresa para leer la ubicación de tránsito necesaria. Un vehículo no puede desactivarse ni perder su ubicación con stock en tránsito.

Alcance mínimo de vehículo: código/identificación, empresa, estado y ubicación móvil; conductor opcional si se aprovecha el catálogo de empleados. No se requiere GPS ni mantenimiento de flota para este alcance.

Para tránsitos históricos, conservar movimientos. Reconstruir documentos solo con evidencia inequívoca; marcar lo no reconstruible como legado y conservar una vía de recepción acotada a esos registros. No inventar vehículo, despacho o aceptación anterior. Los nuevos comandos pasan por el documento y sus reglas, incluso cuando se invocan desde Almacenes.

## ADR-04. Costos, unidades y retaceo

Conservar la política autorizada: promedio compartido por empresa/artículo, costo provisional de recepción en cuarentena y aplicación del retaceo verificado antes de liberar cuando sea exigible. El estado provisional debe ser visible y el costo final de la demo debe incluir el retaceo. Se mantiene documentada la diferencia de secuencia respecto a la narrativa de la ERS; no está confirmada su equivalencia literal por el docente.

No reemplazar el motor de valoración por un promedio por almacén o por el costo histórico de cada lote en las salidas. El lote identifica procedencia; la salida usa el promedio vigente. La devolución de cliente usa el costo efectivo de la salida original. La política ya aprobada de devolución a proveedor separa costo retirado y crédito/diferencia; no cambiarla.

Las variantes mantienen la identidad inventariable existente. Documentar su equivalencia a artículo; la aceptación inicial utiliza productos base. El código de barras exigido se deriva del código interno del producto; la HU y el QR son identificadores adicionales.

No introducir redondeos que eliminen remanentes. Fraccionar sigue siendo una operación explícita. Una regla de incremento mínimo por unidad/producto requerirá su propia configuración y migración; no inferirla del nombre «Caja» ni del múltiplo de compra.

## ADR-05. Ajustes y evidencia

Documento de ajuste con líneas, empresa, ubicación, lote/HU, signo, cantidad, motivo, evidencia, autor y aprobador. Estados BORRADOR, APROBADO, APLICADO y CANCELADO antes de aplicación. El mismo usuario puede aprobar/aplicar si posee permisos; no imponer una separación de cargos que no se pidió.

Para aprobar un ajuste nuevo: motivo, referencia documental y al menos un adjunto activo válido de la misma empresa. Reutilizar almacenamiento, validación y acceso a documentos existentes. La carga del archivo puede ser previa y fuera de la transacción de inventario; el enlace/versionado de la evidencia aprobada queda fijo en el documento. No permitir que su borrado o reemplazo silencioso quite el soporte histórico.

La aplicación invoca movimientos existentes y valoración. Positivo usa costo documentado cuando se identifica; si no, promedio vigente. Sin promedio previo requiere costo documentado. Negativo usa promedio vigente. Corrección de un aplicado: nuevo documento enlazado y movimiento compensatorio cuya cantidad/costo correspondan al origen; no un cambio del registro anterior. Las incidencias de tránsito pueden enlazar un ajuste, con autorización específica del documento de traslado y sin bypass genérico.

## ADR-06. Venta, entrega y devolución

La venta es el documento comercial; la entrega es el evento físico. Precio, descuentos y moneda quedan como snapshot independiente del costo. Una venta confirmada sin entrega no reduce stock. Las cotizaciones no reservan ni descuentan stock; su conversión a venta es trazable e idempotente.

Crear solo los prerrequisitos comerciales necesarios: cliente básico por empresa y captura explícita de precio de venta. No inferir precio del promedio ni inventar políticas fiscales. DTE, cobros, crédito y libro contable completo quedan fuera de estos encargos; requerirían especificación propia. La cotización/venta de esta etapa sirve para demostrar la integración de inventario, no acredita esos módulos fiscales.

La confirmación comercial congela las líneas. El avance de entrega es una proyección independiente: PENDIENTE, PARCIAL, COMPLETA. Cada entrega identifica la sucursal/ubicación real y la asignación por lote/HU. Solo consume disponible y no supera el pendiente de venta. Cancelar antes de entregar no mueve inventario; después de una entrega, cualquier retorno/corrección física sigue el documento compensatorio correspondiente. Una cancelación no demuestra que la mercancía haya vuelto.

La devolución referencia líneas de entrega/salida original. Estados operativos: BORRADOR, RECIBIDA/PENDIENTE DE REVISIÓN y resultado final ACEPTADA, RECHAZADA o MIXTA; admitir resultado parcial por línea y mantener la revisión abierta mientras queden cantidades sin decidir. La recepción documental no incrementa automáticamente inventario. La aceptación aplica la cantidad apta autorizada, con movimiento y costo original, sin superar lo entregado menos devoluciones ya aceptadas. Rechazo o daño se registra aparte y no se libera a disponible. Si la mercancía aceptada requiere nueva revisión física, entra a cuarentena y usa el flujo de liberación existente.

La devolución no reduce el historial de cantidad entregada ni provoca un nuevo envío automático del pedido. Registrar entregado, devuelto y neto como magnitudes distintas.

## ADR-07. Transacciones, permisos y documentación

Toda operación de negocio y sus movimientos se guardan en una unidad de trabajo atómica, incluso si falla una validación tardía. La sesión actual confirma AppError; proteger explícitamente la operación con savepoint/rollback. Mantener las particularidades de otros módulos y probar que la auditoría de éxito tampoco queda confirmada en una operación fallida.

Usar permisos específicos siguiendo el catálogo actual: operación logística/comercial, aprobación de ajuste y lectura de costos separados. El detalle visible al usuario identifica producto, presentación/unidad, cantidad, origen/destino y siguiente paso. El código HU nunca es el único nombre del producto.

Cada bloque actualiza su informe y la matriz común con resultados reales. Los contratos dependientes se registran aquí si cambian. Ningún bloque se cierra por un número alto de pruebas si falta un criterio o la base habitual no está actualizada.

## Implementación B03 (19/10/2026)

La decisión ADR-03 quedó implementada en la revisión 0086. Cada empresa recibe una bodega técnica de tránsito; cada vehículo tiene una ubicación móvil dentro de ella. Los movimientos del documento transfieren las mismas unidades/HUs entre ubicaciones por medio del motor existente y mantienen intacto el promedio global. La recepción parcial termina en cuarentena. El API de B03 expone contratos para que B04 agregue operación visual sin definir de nuevo los estados.

El motor registra las cantidades devueltas en el esquema para no perder capacidad de conciliación, pero B03 no expone un comando de retorno. Hasta una etapa autorizada que modele ese flujo, solo se cierra un traslado al recibir la cantidad despachada; una diferencia requiere incidencia y, si corresponde pérdida, el ajuste autorizado de B05. No se reconstruyen documentos o vehículos para los movimientos legados sin evidencia inequívoca.

## Implementación B05 (19/10/2026)

ADR-05 y la preparación del bloque quedaron implementadas en la revisión 0087. El documento de ajuste registra empresa, bodega, fechas operativa/contable, motivo, referencia, líneas, actores, evidencia con checksum, eventos, versión de aprobación e idempotencia. Borrador, aprobación y cancelación no mueven existencias. Aplicar invoca el motor de movimientos y valoración actual, conserva nuevas entradas en cuarentena y no deja otro camino público de ajustes en el endpoint genérico.

La pérdida en tránsito se registra como ajuste negativo enlazado a traslado, incidencia, detalle y HU en tránsito. `quantity_adjusted_out` se mantiene separado de `quantity_received` y participa en la ecuación despachado = recibido + en tránsito + devuelto + ajustado de salida. Al resolver la última cantidad pendiente, el traslado cierra como `closed_with_adjustment`; no se genera una recepción ficticia ni un despacho/reposición automática. Movimiento, costo, cantidad ajustada, resolución de incidencia e historial se confirman en una sola operación.

La corrección disponible cubre el total de un ajuste ordinario aplicado de una sola línea negativa cuando puede identificarse exactamente el costo original y no hay movimientos físicos o valorizados posteriores del artículo. Crea un nuevo ajuste positivo enlazado y en cuarentena por el valor original. Otras formas de corrección, incluidas pérdidas de traslado ya cerradas, líneas múltiples/parciales y movimientos posteriores, se rechazan para evitar una compensación de valor no justificable.

La verificación técnica se registra en [entrega B05](entrega-bloque-05.md) y `tmp/ers-v1/bloque-05/evidencia-2026-10-19.md`. La aceptación de navegador, la matriz exhaustiva de perfiles API y las pruebas de concurrencia permanecen pendientes de la revisión integrada de B08. B05 no habilita retornos ni inicia B06.

## Implementación B06 (19/10/2026)

La revisión 0088 implementa los prerrequisitos comerciales de ADR-06: cliente
básico por empresa, cotización con precio explícito y conversión completa a
una venta en borrador. La confirmación comercial congela la revisión, pero no
reserva ni descuenta existencias. La venta informa cero entregado y toda la
cantidad base pendiente como una proyección de solo lectura; B07 deberá
reemplazarla por el agregado de entregas reales. El precio y sus totales son
independientes del promedio de costo; no se añadieron impuestos, descuentos,
DTE, cobros, crédito ni contabilidad.

Las líneas guardan snapshot de producto/variante, artículo inventariable,
SKU/nombre, unidades, conversión y versión de empaque, cantidad comercial/base
y precio. El servidor redondea cada línea a centavos con Decimal y
`ROUND_HALF_UP`, y suma las líneas redondeadas. USD es la única moneda de esta
demostración. Unicidad por empresa/origen evita convertir de nuevo una
cotización incluso después de cancelar su venta.

Se aplicaron los límites de ADR-07 con savepoints alrededor de las operaciones
comerciales: una falla en la segunda línea o en la auditoría tardía no deja
venta, clave de idempotencia ni evento de conversión parciales. La evidencia
incluye API por perfiles, alcance por compañía/sucursal, reintentos,
concurrencia y huellas de inventario sin cambios. El contrato y los casos
pendientes de aceptación están en [entrega B06](entrega-bloque-06.md). B06 no
implementa la entrega física y no inicia B07; ese era el corte al cerrar B06 y quedó superado por el resultado B07.

## Implementación B07 (19/10/2026)

B07 mantiene la entrega como documento físico separado de la venta. La
preparación solo asigna HUs completas y no reserva ni mueve stock; la
confirmación vuelve a validar empresa, sucursal, venta, pendiente, HU, ubicación,
lote y etiqueta antes de registrar el envío y la valoración. Las líneas y
asignaciones preservan las conversiones congeladas de B06 aunque cambie una
definición de empaque posteriormente. La entrega parcial es una selección de
HUs completas; no fracciona mercancía automáticamente.

Las confirmaciones se serializan por venta y por el motor global de valoración.
La carrera por la última HU se responde como conflicto recargable y no como
recurso desaparecido. El documento, la salida física, la entrada de valoración,
los vínculos por asignación, el comando idempotente y la auditoría de éxito se
confirman en el mismo savepoint. La salida usa el promedio vigente compartido
por empresa/artículo, sin usar el precio comercial ni cambiar el promedio por
la sucursal. Se conserva por asignación el costo realmente aplicado y el enlace
a su entrada de valoración para que B08 determine el costo original; la API
comercial no devuelve importes de costo. Cancelar una venta con una entrega
confirmada queda bloqueado. B07 no implementa devoluciones.

La comprobación, el respaldo/migración y los casos pendientes de aceptación
integrada se registran en [entrega B07](entrega-bloque-07.md) y en su evidencia.

## Actualización: retaceo previo al ingreso (23/10/2026)

Para compras creadas con la revisión 0092, `retaceo_before_inventory` sustituye
el orden provisional de ADR-04: el documento comercial recibido no crea stock;
se captura FOB/importación y gastos manualmente, se calcula/verifica/cierra el
retaceo y después se verifica la recepción física. Esa recepción crea lote,
cuarentena y asiento al costo final en una misma transacción. El promedio es
calculado por empresa/artículo y la consulta posterior usa los asientos
inmutables vinculados al retaceo.

Las compras ya existentes conservan `receipt_before_retaceo`, sin importar su
estado al migrar. No se reordenan movimientos ni se alteran costos históricos.
El bodeguero usa una proyección operativa sin precios y autorización explícita
de bodega, independiente del nombre de su rol. Detalles, alcance y limitaciones:
[entrega del 23/10](retaceo-recepcion-bodega-2026-10-23.md).

# Sesión 23: impacto en el plan de GestionaSV

**Fecha:** 13 de octubre de 2026.  
**Fuente:** [Apuntes de la sesión 23](C:/Users/rodri/Downloads/Apuntes_Sesion_23_Inventario_y_compras.pdf), 15 páginas, leídas completas y revisadas visualmente.  
**Comparación:** [revisión estática del sistema del 12 de octubre](C:/Developer/GESTIONASV_ERP/output/reviews/cumplimiento-inventario-gestionaSV-2026-10-12.md). Esta comparación utiliza esa revisión como base; no constituye una nueva prueba integral del ERP.

## 1. Conclusión

El documento confirma que debemos comenzar por conectar recepción y retaceo con el inventario valorado. Agrega precisiones que conviene incorporar antes de diseñar las siguientes etapas:

1. El lote interno corresponde a una recepción y puede agrupar varios productos.
2. La colocación se realiza escaneando ubicación y producto e indicando la cantidad del grupo; admite reparto entre destinos.
3. El método de costo promedio se configura por empresa, pero el alcance del saldo de valoración entre almacenes sigue pendiente.
4. Recibir, imprimir, ubicar y habilitar disponibilidad son hechos distintos; cada cantidad debe incorporarse una sola vez.
5. El avance debe poder expresarse por producto y cantidad, porque una recepción puede estar parcialmente terminada.

El primer bloque del plan se mantiene: costo final confiable y procedencia de cada entrada. Ahora debe incluir desde el diseño la relación **recepción → detalle de producto → retaceo → lote de recepción → unidades logísticas**.

## 2. Qué autoridad tiene este documento

Las páginas 1 y 15 explican que son apuntes elaborados desde una transcripción de 247 líneas. No se revisó el audio ni el diagrama original en su elaboración. El documento distingue:

- **CLASE:** explicación atribuida a la sesión.
- **PROPUESTA:** diseño o validación agregados al preparar los apuntes.
- **POR DEFINIR:** decisión aún no resuelta.

Esta distinción debe conservarse en el plan. Los nombres de estados, las tablas propuestas, los roles y los criterios de aceptación no equivalen automáticamente a una especificación aprobada por el docente. Las referencias a líneas del TXT no fueron verificadas contra ese archivo en esta revisión.

La sesión desarrolla especialmente la continuidad hacia Inventario. Según la página 2, no redefine la adjudicación ni las reglas completas de solicitudes, cotizaciones o consolidados. Las mejoras previamente solicitadas por el usuario conservan su propio alcance.

## 3. Precisiones frente a nuestro análisis anterior

### A. Lote interno de recepción con varios productos — páginas 3 y 5

La aclaración es explícita: televisores de tres modelos pueden compartir `LOTE-R001`, conservando un código de producto distinto para cada modelo. Una segunda recepción debe conservar su identidad aunque incluya los mismos productos.

**Ajuste a mi recomendación anterior:** la expresión «lote por recepción/producto» debe descomponerse en una cabecera de lote de recepción y sus detalles por producto/línea. No debemos imponer un código de lote interno distinto para cada producto recibido junto.

Propuesta de correspondencia con GestionaSV:

| Identidad | Qué representa |
|---|---|
| Código de producto | El artículo del catálogo |
| Lote interno de recepción | El conjunto recibido en una operación concreta |
| Detalle del lote | Producto, línea de origen, cantidad, unidad y costo de esa recepción |
| Código HU | La unidad logística física que se mide, ubica o fracciona |
| Lote de fabricante | Identidad de producción, si aplica al artículo |

Las HU existentes pueden conservarse. Su genealogía y la identidad del lote interno resuelven necesidades diferentes. El fraccionamiento o traslado debería conservar el vínculo con la recepción de origen; un despacho interno no equivale a una nueva compra.

La propuesta de cabecera y detalles también permite resolver la diferencia con el esquema simplificado de las imágenes anteriores, que mostraba el producto directamente dentro de `inventory_lots`.

### B. Escaneo por grupo y ubicación parcial — página 6

La operación descrita es: seleccionar el trabajo de recepción/lote, escanear una ubicación, escanear el producto e indicar la cantidad colocada. La selección previa del lote es una propuesta técnica del documento para resolver la ambigüedad del barcode de producto.

Ejemplo: colocar 12 unidades en A y 8 en B debe dejar 20 ubicadas y cero pendientes. No requiere veinte escaneos individuales.

Esto encaja con la intención del usuario de trabajar por grupos. Conviene distinguir dos operaciones:

- **Ubicar un grupo:** confirmar varias unidades del mismo producto y lote en un destino.
- **Recibir varias compras juntas:** ejecutar acciones agrupadas conservando por separado sus recepciones, documentos y lotes.

La página 6 especifica la primera; no define una recepción masiva que fusione compras distintas. La función de recepción agrupada solicitada anteriormente necesita su propia regla de ejecución y manejo de errores.

En la revisión previa encontramos separación de HU durante la verificación y ubicación final al liberar. También encontramos restricciones para fraccionar una HU ya creada. Por tanto, el caso general de ubicar 12 y después 8 necesita integración específica; no debe darse por cubierto solo porque existen traslados parciales.

### C. Promedio por empresa: todavía hay una decisión — páginas 7, 10 y 14

El documento afirma que la política de valoración es costo promedio ponderado configurado globalmente por empresa. A la vez, deja pendiente si cada producto comparte un único promedio entre todos los almacenes o tiene promedios separados.

**Corrección a mi recomendación anterior:** promedio por producto y bodega era una propuesta de diseño, no un requisito demostrado. Debe permanecer provisional hasta resolver este punto.

| Alternativa | Consecuencia |
|---|---|
| Un promedio por empresa y producto | Los traslados internos conservan la cantidad y el valor globales; las ubicaciones muestran la distribución física |
| Un promedio por empresa, producto y almacén | Hay que definir el costo de salida, tránsito y combinación del valor recibido con las existencias del destino |

Esta decisión afecta las claves de los saldos, el cálculo y el Kardex. Debe resolverse antes de construir el motor de valoración. No hace falta rehacer la distribución física por bodega para elegir cualquiera de las dos políticas.

### D. Momento de disponibilidad y momento de valoración — páginas 3, 4 y 13

El flujo operativo exige retaceo finalizado, identificación, ubicación válida y confirmación antes de dar la mercancía por disponible. Sin embargo, los apuntes dejan pendiente el evento técnico exacto que incorpora el valor, especialmente con ubicaciones parciales.

Según la revisión anterior, GestionaSV ya registra las cantidades aceptadas en cuarentena al verificar la compra. Debemos conservar esa realidad física y evitar una segunda entrada de compra al imprimir o liberar las mismas unidades.

Propuesta: definir expresamente, antes de programar, qué evento registra cada hecho:

1. Recepción: cantidad física aceptada y su procedencia.
2. Retaceo finalizado: costo de origen definitivo o versión de costo aplicable.
3. Impresión: historial de etiquetas; no cambia cantidades de inventario.
4. Colocación: cantidad y ubicación confirmadas.
5. Incorporación de valor y habilitación: cantidad elegible según la política acordada, registrada una sola vez.

Estos hechos pueden resolverse mediante operaciones coordinadas. No es obligatorio convertirlos en cinco menús ni sumar existencias en cada uno. El historial físico y el Kardex valorado deben explicar sus diferencias de estado.

### E. Etiqueta de producto y QR de trazabilidad — página 5

El código de barras representa el código interno del producto; lote y fecha de recepción deben quedar visibles. El documento exige registrar cantidades y fechas de impresión. Distinguir reimpresión, usuario y motivo aparece como control propuesto.

El QR por HU existente puede complementar esa etiqueta. La sesión no fija una simbología obligatoria, una marca de lector ni acceso público sin autenticación.

Imprimir una etiqueta no acredita por sí solo que se colocó físicamente. Es necesario acordar si el flujo llevará confirmación explícita de viñeteado y qué cantidad se confirma.

## 4. Comparación con la base revisada de GestionaSV

Los estados siguientes provienen de la revisión del 12 de octubre, no del hecho de que el PDF enumere una tarea.

| Tema de los apuntes | Base encontrada | Trabajo que queda |
|---|---|---|
| Recepción con origen y cantidades | Compra, orden, verificación y cuarentena implementadas | Conectar progreso por cantidades hasta disponibilidad |
| Costo final de la entrada | Retaceo con cálculo y estados | Distribución acordada, gastos entre recepciones parciales y vínculo exacto con cantidades valoradas |
| Lote interno por recepción | HU y lote opcional | Identidad de recepción con detalles de varios productos |
| Viñeteado | QR e impresión por HU | Barcode de producto, lote, fecha e historial de impresión |
| Ubicación por grupo | Ubicaciones, capacidad y liberación de HU | Captura por escaneo y reparto parcial general con saldo pendiente |
| Promedio ponderado | Sin motor de valoración encontrado | Alcance, saldos monetarios, actualización y costo de salidas |
| Kardex | Historial físico existente; menú pendiente | Consulta con entradas, salidas, saldo y costos históricos |
| Traslados | Despacho, tránsito, recepción contada y cuarentena | Vincular valoración sin duplicar cantidad ni valor global |

Los controles físicos de capacidad y tránsito de GestionaSV ya desarrollan aspectos que la sesión deja abiertos. Se pueden reutilizar, sujetos a que sus reglas respondan al negocio.

## 5. Costos y ejemplo numérico

Las páginas 4, 7 y 8 mantienen tres conceptos separados:

- **Costo de origen:** resultado del retaceo de una recepción concreta.
- **Costo promedio vigente:** valor de las existencias remanentes dividido entre su cantidad, incorporando las nuevas entradas según la política.
- **Precio de venta:** decisión comercial.

El ejemplo de la página 8 es aritméticamente consistente:

| Operación | Cantidad | Valor |
|---|---:|---:|
| Primera entrada, 10 a $10 | 10 | $100 |
| Segunda entrada, 8 a $12 | 8 | $96 |
| Saldo antes de salir | 18 | $196 |
| Salida de 12 a promedio | 12 | $130.666666… |
| Saldo restante | 6 | $65.333333… |

El promedio es $196 / 18 = $10.888888…; salida más saldo conservan $196. Con PEPS, la salida sería $124 y el remanente $72. Esto ilustra dos valoraciones diferentes del mismo movimiento físico.

La rotación física por antigüedad puede coexistir con costo promedio. La sesión no establece como entrega adicional un motor de valoración PEPS.

## 6. Plan actualizado de trabajo

### Bloque 1. Recepción, retaceo y procedencia

Comenzar aquí, como acordamos. Corregir y concretar la distribución de gastos y el costo unitario; evitar cargar el mismo gasto completo en varias recepciones parciales. Definir los vínculos exactos con el detalle recibido y el lote interno de recepción. Acordar qué estado del retaceo significa costo final utilizable.

**Resultado revisable:** cada cantidad aceptada tiene origen y costo explicables; los gastos repartidos reconcilian con el importe real. El tratamiento de gastos compartidos viene del análisis anterior y debe conservarse como requisito propio, pues esta sesión no lo desarrolla.

### Bloque 2. Lotes, etiquetas y colocación

Completar lote con varios productos, etiquetas e historial. Construir la operación de ubicación por grupo con cantidades colocadas y pendientes, varios destinos y contexto de lote. Aprovechar las HU y las validaciones de almacén existentes.

**Resultado revisable:** una recepción de 20 permite ubicar 12 y 8, preservando lote y origen; imprimir o repetir una confirmación no crea mercancía adicional.

### Bloque 3. Valoración y Kardex integrados

Con el alcance y evento de valoración ya definidos, implementar promedio, valor del saldo y costos históricos. Integrarlos con las confirmaciones del bloque anterior. El control físico de los bloques anteriores no implica que ya exista disponibilidad valorada completa.

**Resultado revisable:** el ejemplo de 18 unidades y $196 reconcilia antes y después de una salida. El Kardex se consulta y sus correcciones se realizan por operaciones justificadas, no editando filas antiguas.

### Bloque 4. Continuidad operativa

Completar conservación del costo en traslados y después salidas de ventas. Incorporar recepción agrupada y navegación guiada entre los pasos ya definidos. Conservar las referencias a solicitudes, adjudicaciones, órdenes y compras.

Este orden ajusta el plan anterior para definir la identidad del lote y el trabajo de colocación antes de dar por cerrado el Kardex y la disponibilidad. El diseño de valoración debe acordarse desde el comienzo aunque su implementación llegue después.

## 7. Decisiones identificadas en la revisión original

Esta lista registra lo que estaba pendiente al analizar el PDF. Las decisiones posteriores de la conversación prevalecen; la política de devoluciones acordada se documenta en la sección 8.

1. Promedio compartido por producto y empresa o separado por almacén.
2. Evento exacto que incorpora valor, y tratamiento de cantidades aún en cuarentena o pendientes de ubicar.
3. Estado concreto del retaceo que habilita el siguiente paso: calculado, verificado o cerrado.
4. Confirmación de viñeteado y unidad que representa cada etiqueta: caja, paquete o unidad base.
5. Costos de devoluciones, ajustes, correcciones y fechas retroactivas.
6. Valoración inicial documentada del inventario que ya existe.

Estos puntos son decisiones de diseño o negocio. Los apuntes no los resuelven por completo. La revisión de este PDF actualiza el plan; no aplica cambios al sistema ni registra operaciones reales.

## 8. Política de devoluciones acordada el 13 de octubre

El usuario aceptó la recomendación sobre devoluciones y correcciones. Se adopta como política funcional para implementar en GestionaSV; su registro aquí no significa que el motor de valoración ya esté implementado.

### Devolución normal a proveedor

Para artículos intercambiables valorados por promedio:

1. Registrar la cantidad que realmente sale y vincular proveedor, compra, recepción, lote y HU de origen.
2. Valorar la salida al promedio vigente de la empresa y producto, conservando el costo aplicado en el movimiento. El valor original de la compra permanece como antecedente.
3. Registrar separadamente el importe neto reconocido por el proveedor y el documento que lo respalda. Separar los impuestos y los gastos que no sean recuperables del proveedor; no comparar un crédito bruto con un costo neto.
4. Registrar la diferencia entre recuperación neta y valor de salida como ajuste de costo por devolución, vinculado a ambos documentos. Su clasificación contable debe configurarse expresamente; no absorberla silenciosamente en el saldo de unidades que ya no existen.
5. Si el proveedor aún no ha confirmado el crédito, distinguir salida física, recuperación pendiente y liquidación posterior. La recepción de la nota de crédito no vuelve a descontar mercancía.

Ejemplo sin impuestos, deterioro ni gastos adicionales: después de comprar 10 unidades a $10 y 10 a $20 y vender 15 a promedio de $15, quedan 5 unidades valoradas en $75. Al devolverlas, salen 5 unidades y $75. Si el proveedor reconoce $100, quedan cero unidades y cero valor de inventario; la diferencia favorable de $25 queda como ajuste separado de costo por devolución.

Cuando se devuelve la totalidad del saldo, se retira exactamente su valor pendiente, evitando residuos causados por usar el promedio redondeado de pantalla. Si existe deterioro previamente registrado, se debe incluir su baja proporcional en la conciliación para no conservar una corrección valorativa de mercancía que ya salió.

### Devolución de cliente

La propuesta es reincorporar la cantidad aceptada al costo registrado en la salida original, considerando los ajustes de costo posteriormente vinculados a ella. El importe que se devuelve al cliente pertenece a la operación comercial y se registra por separado.

Conservar la referencia a la venta y enviar la mercancía a revisión física. Su disponibilidad posterior depende de condición y controles de liberación. El deterioro se registra explícitamente; una devolución no convierte automáticamente mercancía dañada en disponible.

### Correcciones y retaceo tardío

- Una devolución comercial normal y una anulación por error son operaciones distintas. La corrección debe enlazar el movimiento original, la reversión o ajuste y, cuando corresponda, el reemplazo.
- Antes de revertir una entrada con operaciones posteriores, resolver su efecto en salidas y valoración. No basta insertar un negativo del costo original si eso deja saldos incoherentes.
- El retaceo posterior modifica valor una sola vez y conserva su relación con recepción, inventario remanente y salidas afectadas. La distribución debe seguir el historial de valoración cuando se mezclan entradas bajo promedio.
- Distinguir información nueva que actualiza una estimación de un error por información disponible mal utilizada u omitida. No clasificar automáticamente cualquier factura o retaceo tardío como error de períodos anteriores.
- Conservar fecha del hecho, fecha de registro y fecha de efecto contable. El bloqueo de un período es un control operativo; no sustituye el tratamiento de un error material de períodos anteriores.

### Fundamento y alcance

[IAS 2](https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/) admite promedio ponderado para artículos intercambiables y regula costo y valor neto realizable. La mecánica de devolución al promedio con conciliación separada se adopta aquí como decisión de diseño del ERP; no se presenta como una instrucción literal de esa página ni como validación completa de cumplimiento normativo.

[IAS 8](https://www.ifrs.org/issued-standards/list-of-standards/ias-8-basis-of-preparation-of-financial-statements/) distingue cambios de estimaciones y correcciones de errores; establece corrección retrospectiva de errores materiales de períodos anteriores, salvo impracticabilidad. La aprobación contable y la configuración de cuentas deben reflejar el marco aplicable a la empresa antes de emitir asientos reales.

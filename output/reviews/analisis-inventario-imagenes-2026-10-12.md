# Análisis de las ocho imágenes: módulo de inventario

**Fecha:** 12 de octubre de 2026.  
**Alcance:** interpretación funcional, revisión del ejemplo numérico y análisis del modelo de datos mostrado. No se inspeccionó ni se modificó la implementación de inventario para este análisis.

Complementa el [análisis del PDF y del Excel](C:/Developer/GESTIONASV_ERP/output/reviews/analisis-ers-retaceo-2026-10-12.md).

## 1. Conclusión principal

Las imágenes desarrollan el tramo que el PDF anterior dejaba como integración posterior: transformar una recepción con costos determinados en inventario identificado, ubicado y disponible.

Establecen cinco reglas centrales:

1. Para el flujo representado, el retaceo finalizado antecede a la creación de lotes, al etiquetado y a la disponibilidad.
2. Se conservan lotes asociados al origen de compra.
3. La ubicación física y su confirmación forman parte del ingreso a inventario.
4. Se utiliza costo promedio ponderado, configurado como método por empresa.
5. El Kardex consulta movimientos registrados; el precio de venta se define en el proceso comercial.

Las imágenes son una especificación conceptual. Los textos «ya implementado» describen lo que afirma el material; no constituyen evidencia de que una función concreta del ERP esté terminada o probada.

## 2. Lectura de cada imagen

| Imagen | Qué aporta | Qué necesita precisarse |
|---|---|---|
| 1. Diagrama de flujo | Recepción → retaceo finalizado → lotes → etiquetas → ubicación válida → confirmación → existencias disponibles | Qué estado significa «retaceo finalizado» y cuándo se registra la mercancía física pendiente |
| 2. Encabezado | Trazabilidad, lotes, ubicaciones, costo promedio y Kardex como pilares | Son objetivos; se necesitan reglas y pruebas para demostrar cada uno |
| 3. Proceso general | Sitúa etiquetado y ubicación entre retaceo e ingreso disponible | La flecha de retorno no debe interpretarse como volver a crear una compra por cada movimiento |
| 4. Etiqueta y ubicación | Barcode del producto; lote y fecha impresos; reparto de 20 unidades en ubicaciones de 12 y 8 | Identificación única de lote/unidad logística y registro del saldo por ubicación |
| 5. Valoración | Costo promedio = valor del inventario / cantidad; primera entrada establece el promedio inicial | Alcance del promedio y diferencia entre existencia valorizada y cantidad disponible para despacho |
| 6. Comparativa y Kardex | PEPS como referencia; promedio vigente en salidas; historial consultable de movimientos | Distinguir valoración de selección física de lotes; mostrar costos de las entradas del ejemplo |
| 7. Tablas | Lotes, movimientos, capas, promedios y registro de impresiones | Completar ubicaciones, estados físicos, restricciones y reglas de conciliación |
| 8. Reglas | Cada recepción genera lote; promedio cambia con entradas valorizadas; Ventas define precio | Granularidad del lote, traslados, devoluciones, correcciones y costos tardíos |

## 3. Flujo operativo que proponen

Para las compras sometidas a retaceo, la secuencia es:

**Recibir y verificar → finalizar retaceo → identificar lotes → generar/colocar etiquetas → asignar ubicación → validar → confirmar colocación → dejar disponible.**

### Recepción física, valoración y disponibilidad

Conviene separar tres hechos:

- **Recepción física:** se sabe qué llegó, cuánto se contó y qué se aceptó o rechazó.
- **Valoración:** se conoce el costo aplicable a lo aceptado, incluyendo el retaceo correspondiente.
- **Disponibilidad:** la mercancía está identificada, ubicada y habilitada para su uso o despacho.

Si el retaceo aún está pendiente, la mercancía recibida debe seguir siendo visible como pendiente de costeo/ubicación o en el estado operativo que se defina. No debería desaparecer de la consulta de recepción por no estar disponible todavía.

La implementación puede registrar existencia física restringida antes de liberar disponibilidad, o diferir el asiento definitivo de inventario. Debe escogerse una política explícita. En ambos casos, **la misma recepción no puede convertirse en varias entradas por crear el lote, imprimir, ubicar y liberar**.

### Puntos abiertos

- «Finalizado» debe corresponder a una transición precisa: calculado, verificado o cerrado no significan lo mismo.
- Se necesita decidir cómo se tratan compras locales o compras sin gastos adicionales; el gráfico no define una excepción al retaceo.
- Debe permitirse identificar las cantidades listas y las pendientes en una colocación parcial.
- Una ubicación válida necesita capacidad, estado activo, pertenencia al almacén y compatibilidad con el producto, según las reglas adoptadas.
- Hay que prever correcciones de ubicación y de costos después del ingreso, conservando el historial.

**Propuesta de continuidad de pantalla:** al finalizar el retaceo, ofrecer «Gestionar ingreso a inventario», con pasos visibles de lotes/etiquetas, ubicación y confirmación. Esto se deriva del flujo, pero el material no prescribe un botón o una redirección concreta.

## 4. Producto, lote y unidad logística son identificaciones diferentes

La imagen 4 dice expresamente que el código de barras identifica el producto por su código interno. El lote y la fecha aparecen en texto.

| Identificación | Ejemplo | Qué permite conocer |
|---|---|---|
| Producto / SKU | PRD-000125 | Qué artículo es |
| Lote de recepción | LOT-20261012-001 | A qué ingreso o agrupación trazable pertenece |
| Unidad logística | HU-… | Qué caja, saco, pallet o agrupación física concreta se está moviendo |

Dos lotes del mismo producto pueden tener el mismo barcode de producto. Por tanto, escanear PRD-000125 permite buscar ese producto, pero no determina por sí solo cuál de sus lotes o cajas se tiene delante.

Para la consulta directa de origen y movimientos que has pedido, puede conservarse el barcode del producto y añadirse un QR o identificador único de lote/unidad logística. Si solo se escanea el producto, el sistema necesitará contexto adicional o selección del lote.

El QR de una unidad logística y el código de producto cumplen funciones compatibles. La elección entre código 1D y 2D no resuelve por sí sola la identidad: lo decisivo es el dato codificado y la ficha a la que corresponde.

### Impresión y reimpresión

Una reimpresión produce otra etiqueta del mismo objeto; no crea mercancía, un nuevo lote ni otra entrada. El registro de impresiones debería conservar objeto etiquetado, cantidad de etiquetas, fecha, usuario y motivo de reimpresión.

«Cantidad impresa» tampoco equivale necesariamente a cantidad recibida: puede imprimirse una etiqueta por unidad, por caja o por pallet. Esa unidad de etiquetado debe definirse. La muestra de la imagen 4 no expone claramente la cantidad, aunque la regla de la imagen 8 menciona su registro.

## 5. Qué significa «cada recepción genera un lote»

La regla necesita granularidad. Una recepción puede contener varios productos y un mismo producto puede llegar con varios lotes del fabricante.

Una solución coherente es conservar:

- Compra/recepción y su línea de origen.
- Producto y unidad de medida.
- Lote interno de recepción.
- Lote del fabricante y vencimiento cuando correspondan.
- Unidades logísticas y cantidades físicas que pertenecen a ese lote.

No basta un único lote para toda una recepción con productos diferentes. Tampoco conviene reemplazar el lote del fabricante con un código interno que borre su procedencia.

Si una mercancía se divide entre sucursales, las partes deben conservar la relación con su origen. Puede generarse una unidad logística hija o un registro de recepción destino vinculado, pero un traslado no debe simular una nueva compra ni perder la identidad del lote de origen.

## 6. Ubicaciones: el ejemplo 12 + 8 exige una relación adicional

La imagen 4 reparte 20 unidades en:

- Estante A, nivel 2: 12.
- Estante B, nivel 1: 8.

Esto implica que un lote puede ocupar varias ubicaciones. La tabla de lotes mostrada en la imagen 7 contiene almacén, pero no muestra una asignación de cantidades por ubicación.

Hace falta una relación equivalente a:

| Lote o unidad logística | Ubicación | Estado físico | Cantidad |
|---|---|---|---:|
| Lote L1 / unidad H1 | A, nivel 2 | Disponible | 12 |
| Lote L1 / unidad H2 | B, nivel 1 | Disponible | 8 |

El nombre de la tabla puede variar. Lo necesario es que existan esas relaciones y que sus cantidades concilien con el lote. La aparición de `locations` como tabla relacionada en el gráfico no demuestra que ese detalle esté resuelto.

Mover 5 unidades de A a B dejaría 7 y 13. El total seguiría siendo 20 y el movimiento conservaría su origen, destino, fecha y usuario. Un cambio de ubicación dentro del mismo conjunto de valoración no modifica el valor total ni el costo promedio.

## 7. Costo promedio ponderado: la regla financiera del material

La combinación de las imágenes 5 y 8 describe un promedio que se actualiza con las entradas valorizadas, es decir, un promedio móvil:

```text
Valor nuevo = valor anterior + cantidad de entrada × costo unitario de entrada
Cantidad nueva = cantidad anterior + cantidad de entrada
Promedio nuevo = valor nuevo / cantidad nueva
```

Se aplica al mismo producto, con cantidades expresadas en una unidad compatible y valores en una moneda compatible. No se promedian juntos productos distintos ni se mezclan cajas y unidades sin conversión.

### Comprobación del Kardex mostrado

La tabla de la imagen 6 es matemáticamente coherente si ambas compras del ejemplo ingresan a $15 por unidad:

| Paso | Cantidad en existencia | Valor en existencia | Costo promedio |
|---|---:|---:|---:|
| Inicial: 10 a $10 | 10 | $100.00 | $10.00 |
| Entrada: 10 a $15 | 20 | $250.00 | $12.50 |
| Salida: 6 al promedio vigente | 14 | $175.00 | $12.50 |
| Entrada: 5 a $15 | 19 | $250.00 | $13.157894… |

La última celda puede mostrarse como **$13.16**. La imagen no muestra el costo unitario de las entradas; $15 es la hipótesis usada para comprobar un escenario compatible, no un dato explícito de esa tabla.

La salida de 6 unidades cuesta $75 y no cambia el promedio de $12.50. Su precio de venta puede ser otro; es una decisión comercial.

### Precisiones necesarias

1. **Método por empresa no significa necesariamente un solo promedio empresarial.** La tabla `inventory_cost_averages` incluye producto y almacén, lo que sugiere promedios por producto/almacén. Debe confirmarse si ese es el alcance o si la valoración se agrupa por empresa.
2. **Disponible para despacho no siempre equivale a existencia valorizada.** Reservar o poner una unidad en cuarentena no debería recalcular el promedio como si hubiera ocurrido una compra o venta. Hay que definir qué estados forman parte de cantidad y valor contables.
3. **Costo de adquisición del lote y costo promedio vigente son datos distintos.** El retaceo conserva el costo del ingreso; el promedio determina el costo de las salidas según el método elegido.
4. **Los traslados internos conservan el costo transferido.** Con promedios por almacén, origen descarga a su costo aplicable y destino incorpora ese valor al recibir. Con un promedio común por empresa, mover entre almacenes no debe aparentar una adquisición externa ni duplicar el valor.
5. **El stock en tránsito debe mantener su trazabilidad y valor.** No puede perderse entre la salida del origen y la recepción del destino.
6. **Devoluciones, ajustes, gastos tardíos y movimientos retroactivos necesitan reglas específicas.** El gráfico no establece cómo valorarlos o corregir el promedio histórico.
7. **La precisión interna debe superar la presentación cuando sea necesario.** Mostrar $13.16 no obliga a reemplazar toda la valoración por 19 × $13.16 = $250.04.

## 8. PEPS, lotes y selección física

El material elige costo promedio ponderado y deja PEPS como referencia. Eso fija cómo se calcula el costo de salida.

Mantener lotes sigue siendo útil para origen, vencimiento y retiro de mercancía. Que el proyecto exija lotes es una regla de trazabilidad; el costo promedio, como operación matemática, no exige por sí mismo lotes.

La selección física de mercancía puede priorizar el lote más antiguo o el que vence primero, mientras su salida se valora al promedio. Son decisiones diferentes que deben representarse con claridad.

La tabla `inventory_cost_layers` no contradice automáticamente el uso de promedio: puede conservar historia de entradas. Pero no debería introducir una valoración PEPS de las salidas si la política seleccionada es promedio.

Ejemplo del riesgo: con 10 unidades a $10 y 10 a $15, el promedio es $12.50. Después de sacar 6, la valoración por promedio queda en $175. Si se conservan físicamente 4 del primer lote y 10 del segundo, sumar sus costos originales da $190. Ese segundo importe es una suma histórica por capas, no la valoración de saldo bajo promedio que se acaba de aplicar. Debe definirse qué representa cada campo para evitar dos valores contradictorios del mismo saldo.

## 9. Kardex y modelo de datos

El Kardex debe derivarse de movimientos y consultarse. Una corrección debe producir el movimiento de ajuste o reversión autorizado que corresponda, preservando el origen del cambio.

El listado de la imagen 6 incluye compras, ventas, devoluciones, ajustes, traslados y cambios de ubicación. Para la operación real también hay que distinguir los cambios de estado, como cuarentena a disponible, de entradas o salidas físicas.

### Evaluación de las tablas mostradas

| Tabla | Utilidad | Aspectos por completar |
|---|---|---|
| `inventory_lots` | Origen por producto y detalle de compra, cantidades y costo | Código de lote visible, lote fabricante, vencimiento cuando aplique y relaciones de genealogía |
| `inventory_movements` | Historial con cantidades, costo, usuario y documento de referencia | Ubicación origen/destino, relación de las dos partes de un traslado y prevención de registros repetidos |
| `inventory_cost_layers` | Historia de cantidades y costos de entrada | Función exacta bajo promedio; no usar inadvertidamente costo PEPS |
| `inventory_cost_averages` | Saldo de cantidad, valor y promedio por agrupación | Clave única del conjunto de valoración y actualización coherente con movimientos |
| `inventory_label_prints` | Historial de etiquetas | Usuario, objeto exacto, formato y motivo; reimpresión sin impacto en stock |

El esquema está rotulado como simplificado. La ausencia de un campo en el dibujo se trata como un punto por especificar, no como prueba de que falte en la base de datos real.

### Controles que se desprenden del proceso

- No disponer más cantidad de la recibida y aceptada.
- No repetir el ingreso de una misma línea al confirmar dos veces.
- No mezclar productos, unidades o empresas en una asignación.
- Mantener la suma por ubicaciones y estados conciliada con el lote.
- Registrar saldo, costo y movimiento de forma consistente ante operaciones simultáneas.
- Conservar vínculos con compra, retaceo, traslado y responsables.
- Restringir operaciones a los almacenes y sucursales autorizados para el usuario.
- Reimprimir sin alterar existencias ni costos.

## 10. Relación con la revisión anterior

Las imágenes aclaran decisiones que el PDF anterior no completaba:

- Orden de etiquetado, ubicación y disponibilidad.
- Creación de lotes de recepción.
- Costo promedio ponderado como método elegido.
- Salidas al promedio vigente.
- Kardex como consulta de movimientos.
- Separación entre costo y precio comercial.

No resuelven la omisión de seguro ni la fórmula de costo unitario del Excel. Un costo de entrada incorrecto pasa al promedio y afecta las salidas posteriores. Primero debe conciliarse el costo de adquisición.

Tampoco especifican el reparto de mercancía central entre sucursales, ni el promedio ante traslados en tránsito, recepción parcial o cuarentena. Esos cruces necesitan una extensión de las reglas.

## 11. Qué verificar después en el sistema

Este análisis deja una lista concreta para una revisión de implementación posterior:

1. Si cada recepción aceptada conserva lote y detalle de compra de origen.
2. Si las etiquetas distinguen producto de lote/unidad logística.
3. Si se puede repartir un lote entre ubicaciones con cantidades conciliadas.
4. Si finalizar el ingreso habilita disponibilidad una sola vez.
5. Si la primera entrada y las siguientes calculan el promedio correctamente.
6. Si salidas, traslados y cambios de ubicación utilizan la regla de costo adecuada.
7. Si el Kardex explica documento, cantidad, saldo y valoración sin edición directa.
8. Si reimpresiones, reservas y cambios de estado no crean stock adicional.
9. Si el precio comercial se mantiene separado del costo promedio.

**Conclusión:** las imágenes describen una ampliación coherente del proceso de compras hacia inventario. Para convertirla en una especificación implementable faltan, sobre todo, identidad de lotes/unidades, saldos por ubicación, alcance del promedio y reglas de traslado/corrección. No es posible afirmar qué parte ya cumple el ERP basándose solo en estas ilustraciones.

## Fuentes visuales

1. [Flujo de ingreso](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-c1d3e3de-f334-4d9f-aa4d-1967fd0a5b63.png).
2. [Objetivos del módulo](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-e58c4c1b-ebcd-4cfb-a4dd-c5350c4bc5d2.png).
3. [Proceso general](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-6c96cd6e-5eca-4810-8eb4-01973124f0bb.png).
4. [Etiqueta y asignación de ubicación](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-a0a435c6-9e6d-45c0-ba2d-09b5f3c2c5be.png).
5. [Costo promedio](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-c3c1a0f6-6887-4b7f-b46b-d8dc60d2acb6.png).
6. [Comparativa de métodos y Kardex](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-6ea2c91a-6761-4d53-ac1f-ebececf34c00.png).
7. [Modelo de datos simplificado](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-a846e88d-e7ee-4915-b31f-def690dc63f1.png).
8. [Reglas de negocio](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-1a499933-0ca2-411b-9531-27e2bf0d2b3d.png).

# Guion breve para la exposición de Grupo Lorena

Actualizado: 29/10/2026. Recorrido validado mediante API y PostgreSQL de pruebas;
los ejemplos numéricos siguientes no se insertaron en tus compras de demostración.

## La historia que vas a contar

«Voy a seguir un producto desde que se solicita hasta que queda ubicado y puedo
consultar su cantidad y su costo histórico. Compras registra los documentos y
costos; el bodeguero confirma la operación física; el administrador consulta
la valoración y el Kardex.»

Usa el mismo producto y conserva a mano los códigos de solicitud, orden, compra,
retaceo, lote y unidad. Abre previamente las pantallas necesarias. Los módulos
adicionales quedan como apoyo para preguntas; no hace falta recorrer todo el menú.

## Recorrido principal

| Paso | Qué mostrar | Qué explicar en una frase |
|---|---|---|
| 1. Solicitud y consolidado | Necesidades de sucursales y cantidades agrupadas | «Reunimos lo que se necesita comprar y conservamos de dónde viene cada cantidad.» |
| 2. Cotización y orden | RFQ del proveedor con varios productos, respuesta, comparación y orden aprobada | «Comparamos las ofertas y dejamos documentada la decisión de compra.» |
| 3. Recepción | Factura, fecha y cantidades recibidas, pendientes o rechazadas | «Confirmar lo recibido permite continuar con su revisión y costo; todavía falta completar el ingreso a inventario.» |
| 4. Retaceo | FOB, flete, DAI y otros gastos desglosados; cálculo y cierre | «Calculamos cuánto costó traer la mercancía y el costo unitario de esta entrada.» |
| 5. Bodega con Rodrigo | Lote, etiqueta, medidas, lectura de unidad y ubicación, cantidad y confirmación | «La etiqueta identifica; al confirmar la colocación se registra el ingreso final y queda disponible.» |
| 6. Inventario y Kardex con administrador | Existencia, lote, movimientos, promedio y respaldo | «Cada movimiento conserva su historia; el saldo y el costo vigente reflejan las entradas y salidas registradas.» |

En el flujo nuevo, antes del ingreso definitivo el promedio mostrado en retaceo
es una proyección. Al confirmar la colocación se publican cantidad y valor de
forma coherente. Imprimir etiquetas o repetir una consulta no aumenta existencias.

## Seis ideas para recordar

1. **Consolidado:** agrupa necesidades; la RFQ reúne lo que se pide a cada proveedor.
2. **FOB del formulario:** valor documentado de la mercancía de cada línea, sin
   volver a sumar flete ni DAI. El descuento debe poder explicarse.
3. **Retaceo:** costo de la entrada = mercancía + flete + DAI + otros gastos que
   correspondan al costo. El IVA de importación se registra separado en este flujo.
4. **Lote:** distingue recepciones y permite rastrear el producto hasta su compra.
5. **Promedio:** combina el valor restante anterior y el costo de la nueva entrada,
   dividido entre las cantidades correspondientes. Con existencia y valor anteriores
   agotados, toma el costo de la entrada nueva.
6. **Kardex:** historial de movimientos y saldos. Una corrección posterior se
   documenta; no sustituye silenciosamente un movimiento anterior.

Ejemplo académico para practicar la explicación, sin modificar compras históricas:

| Entrada | Cantidad de entrada | Valor de entrada | Cantidad acumulada | Valor acumulado | Promedio |
|---|---:|---:|---:|---:|---:|
| Primera, a $10 | 5 | $50 | 5 | $50 | $10 |
| Segunda, a $15 | 10 | $150 | 15 | $200 | $13.333333 |
| Tercera, a $20 | 15 | $300 | 30 | $500 | $16.666667 |

## Qué corresponde a cada persona

- **Compras/administración:** proveedor, cotización, aprobación, gastos y retaceo.
- **Bodeguero operativo:** recepción física, medidas, etiquetas, ubicación,
  existencias y consulta de los movimientos físicos de su bodega.
- **Administrador autorizado:** costos, promedio, Kardex valorado, conciliación,
  reportes y revisión global.

Consultar los movimientos físicos ayuda al bodeguero a saber qué entró, qué salió
y dónde se colocó. Consultar costos es una autorización distinta. Para explicar
la valoración, cambia a la cuenta administrativa.

## Dónde continuar después de cerrar el retaceo

1. Entra como **Rodrigo**, abre **Inventario** (`/inventory`) y confirma que estés
   en **Bodega Matriz Grupo Lorena**. En **Recepciones**, busca el código de la
   compra que acabas de trabajar y pulsa **Verificar recepción**. Confirma las
   cantidades físicas; esto prepara las unidades, todavía no las publica como stock.
2. En **Preparar y ubicar**, elige esa unidad. Completa las medidas, revisa/imprime
   la etiqueta y confirma su colocación. Enseña lote y fecha de recepción visibles;
   el vencimiento se muestra cuando corresponde. Reimprimir repite la etiqueta.
3. Escribe o escanea el **código de unidad o producto**, indica la cantidad y lee
   el **código de ubicación** del estante. Son dos datos diferentes. Pulsa
   **Confirmar ubicación e ingresar**. Para repartir en dos espacios, separa la
   cantidad en la preparación y completa ambas colocaciones.
4. Abre **Existencias** y busca ese mismo producto/lote. Muestra su ubicación y
   cantidad. En **Movimientos**, usa el rango de fechas de la operación y pulsa
   **Consultar**: aparecen ingreso, responsable y referencia, sin costos para Rodrigo.
5. Cambia a administrador y abre **Kardex** (`/inventory/kardex`). Selecciona el
   mismo producto y la bodega, ajusta fechas y consulta **Movimientos físicos**.
   Después abre **Valoración** para enseñar cantidad, valor y promedio de cada
   entrada. Esa valoración es global por empresa/producto, aunque el físico se
   consulte por bodega.
6. Abre **Conciliación** con el mismo contexto de producto/fecha: explica cantidad
   física, valorada y diferencia. Descarga PDF o Excel de la consulta que estés
   mostrando. Una diferencia cero comprueba cantidades; no valida por sí sola
   que el precio capturado de la factura fuera correcto.

## Preguntas que puede hacer el ingeniero

| Pregunta | Respuesta breve |
|---|---|
| ¿Dónde ingresas FOB, flete y DAI? | «Manualmente en retaceo. Los ceros son explícitos cuando no aplican; los otros gastos tienen su desglose.» |
| ¿Qué pasa con los gastos previstos? | «Son presupuesto. Los reales se registran aparte y se relacionan con el retaceo; no se suman dos veces.» |
| ¿Se puede agregar otro gasto después de cerrar? | «El cierre bloquea nuevos gastos reales de la orden y conserva el cálculo cerrado.» |
| ¿Es obligatorio adjuntar un PDF a cada gasto? | «Es opcional. Si inicié una carga, debo terminarla o quitarla; los montos y su distribución sí se validan.» |
| ¿Ya entró al inventario por recibir o imprimir? | «Todavía no. En el flujo nuevo, cantidad y valor se registran al confirmar la ubicación.» |
| ¿Por qué el promedio de retaceo dice proyección? | «Anticipa el ingreso usando el saldo actual. El promedio definitivo se calcula junto con la colocación, porque pueden ocurrir otros movimientos mientras tanto.» |
| ¿El costo del lote es igual al promedio? | «El lote conserva su costo de entrada. El promedio combina el valor restante anterior con la entrada nueva.» |
| ¿Y si ya no queda producto? | «Con cantidad y valor agotados, la nueva entrada toma su propio costo. El historial anterior sigue visible.» |
| ¿Qué significa lote o existencia histórica sin origen atribuible? | «Son registros anteriores sin vínculo suficiente con una recepción. Se conservan como historial; no se inventa una compra de origen.» |
| ¿Por qué aparece una recepción antigua pendiente? | «Falta completar su verificación o colocación registrada. No se borra ni se recibe otra vez para limpiar la pantalla. La demostración sigue su propia compra.» |
| ¿Puede Rodrigo ver costos? | «Puede ver tareas, existencias y movimientos físicos de su bodega. La valoración requiere permisos administrativos distintos.» |
| ¿Cambiaste los movimientos viejos? | «No. Cada ingreso o salida guarda su costo histórico. Una operación posterior no reemplaza silenciosamente esos registros.» |

## Comprobación antes de exponer

- Apunta los códigos reales de tu ejemplo: solicitud, RFQ, orden, compra, retaceo,
  lote y unidad. No uses los números del ejercicio académico como si fueran tus
  compras reales; si preparas el ejercicio, usa un producto nuevo para no mezclar saldos.
- Abre las cuentas administrativa y de bodega en sesiones distintas. Comprueba
  el acceso y deja las pantallas listas. No necesitas enseñar todos los menús.
- Revisa producto, unidad, descuento, importe FOB y fechas. Los importes son
  valores documentados; el sistema no puede adivinar una captura equivocada.
- Conserva el archivo original del proveedor y un reporte final del ejemplo.
  El PDF general del consolidado es interno; la RFQ del proveedor puede incluir
  varios productos seleccionados de ese consolidado.
- Para la defensa del promedio, enseña las tres entradas del cuadro y explica
  una sola fórmula: **(valor restante + costo de entrada) ÷ cantidad resultante**.

La aceptación y sus límites quedan en
[el informe del bloque 6](bloque-06-aceptacion-final-2026-10-29.md).
La matriz global de comparación de proveedores, la revisión ampliada de Gerencia
y el abastecimiento automático por mínimos siguen como mejoras posteriores.
No forman parte del recorrido principal que debes explicar ahora.

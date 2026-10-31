# Plan maestro: compras e inventario de Grupo Lorena

Creación: 27/10/2026. Actualización: 29/10/2026. Implementación de los bloques 1–5
y aceptación integrada del bloque 6; evidencia y límites en los informes enlazados.
Este plan integra las observaciones del propio
grupo, Apex y los demás grupos compartidos por Rodrigo. Sustituye la separación
anterior que dejaba mejoras de otros grupos fuera del alcance sin priorizarlas.

**Prioridad aclarada por Rodrigo:** solicitud, cotización y orden de compra son
la base ya avanzada. La entrega que ahora se debe completar empieza en recepción
y termina en inventario, costo promedio, Kardex y reportes conciliados. Incluye
todos los aportes útiles de las exposiciones, ejemplos, pantallas y apuntes,
además de las correcciones que verbalizó el ingeniero. El hecho de que Rodrigo
no alcanzara a exponer su Kardex no lo excluye de la entrega final.

## 1. Criterio de trabajo y fuentes

Rodrigo confirmó que también deben incorporarse las observaciones de los otros
grupos. Apex es una referencia funcional evaluada en clase. Su catálogo y su
apariencia no definen el catálogo ni la identidad de Grupo Lorena.

Las transcripciones mezclan voces del docente y estudiantes. No se atribuye cada
frase a una persona cuando no se puede distinguir. Las pantallas y explicaciones
de los compañeros también aportan requisitos de referencia: no se reduce el plan
a una lista de frases del docente. Se conserva su procedencia para adaptar la
solución a Grupo Lorena y distinguir referencias actuales de ideas para una etapa
posterior. Ninguna función se presenta como implementada por estar anotada.

Fuentes de alcance:

- Revisión del propio grupo y lista personal: retaceo/FOB, gastos reales,
  costo promedio, etiquetas, ingreso después de ubicación y bodeguero móvil.
- Apex: RFQ por proveedor con varios productos, respuesta documentada,
  comparación y elección, revisión de Gerencia, seguimiento, gastos detallados,
  inventario consultable, saldo inicial, lotes, Kardex, exportación y permisos.
- Segundo grupo y demás notas: componentes fijos del retaceo, factura protegida,
  recepción parcial, promedio con existencias anteriores, secuencia de viñeteado
  y ubicación, cantidades repartidas y distinción de lotes.
- MiniERP.png: relaciones y flujo del esquema aportado. La compatibilidad de
  modelos y migraciones se revisa antes de modificar persistencia.

El diagnóstico local y la matriz de observaciones propias se mantienen en
[el documento de detalle](plan-correcciones-observaciones-propias-2026-10-27.md).
La cobertura del recorrido de cotizaciones está en
[la revisión de compras](revision-compras-cotizaciones-2026-10-27.md).

## 2. Recorrido común que debe quedar completo

Solicitud/consolidado → RFQ con todos los productos elegidos para cada proveedor
→ respuesta manual con archivo original → comparación/adjudicación → orden
revisada y aprobada → registro de envío → recepción documental y conteo físico
→ retaceo cerrado y costo calculado → viñeteado → ubicación confirmada por
bodeguero → ingreso final → existencias, lotes, Kardex y conciliación.

Durante la espera de la compra se registran los gastos reales conocidos. Recibir
o contar no habilita por sí solo venta, traslado, viñeteado ni duplicación de
existencias. El costo y el promedio mostrados antes del ingreso deben identificar
si son proyección o asiento efectivo. Cantidad y valor se publican de forma
coherente en la confirmación del ingreso, con protección contra reintentos.

Aclaración de Rodrigo del 27/10/2026: los archivos adjuntos de los gastos del
retaceo son opcionales. Su ausencia no bloquea calcular ni verificar. El desglose,
los importes y la distribución conservan sus validaciones; un archivo cuya carga
ya se inició debe completarse o quitarse antes de continuar sin adjuntos.

Abastecimiento toma las existencias disponibles completas, antiguas y nuevas,
después de ese ingreso. No se limita a repartir la última recepción.

### Aportes agrupados para el tramo que falta cerrar

| Aporte de las exposiciones y capturas | Cómo se incorpora a Grupo Lorena | Evidencia al presentar |
| --- | --- | --- |
| Recepción de 8 unidades sobre 10 ordenadas, con fecha, factura y observación | Conservar recibido, aceptado, rechazado, faltante y pendiente; una recepción parcial tiene su propia identidad | Mostrar las cantidades y el documento de esa recepción sin crear stock disponible antes de completar el proceso |
| Factura y fecha copiadas a retaceo | Usar el documento confirmado como fuente y proteger sus datos; cambios posteriores quedan documentados | Ir de orden a compra y retaceo conservando número y fecha |
| Gastos acumulados durante espera, desglosados por tipo | Bitácora con fecha, categoría, descripción, monto, comprobante y relación con presupuesto | Abrir cada gasto y explicar de dónde sale la suma de otros gastos |
| FOB, flete y DAI visibles; guardar cálculo y cerrar después | Captura/revisión explícita de componentes, desglose por producto y cierre protegido | Mostrar costo por renglón y suma total; guardar borrador no habilita etiquetado |
| Costo de lote y costo promedio diferenciados | Mostrar existencia/valor anteriores, entrada y promedio global resultante desde retaceo, consistente al ingresar | Tres ingresos del mismo producto; comparar el costo de cada lote con el promedio vigente |
| Planillas de viñetas repetidas según cantidad recibida | Impresión por unidad/caja definida, selección de cantidad, vista previa, registro y reimpresión | Imprimir QR y Code 128 legibles sin cortar etiquetas ni crear otro lote |
| Fecha y lote a simple vista debajo o encima del código | Nombre/código de producto, recepción, lote y vencimiento cuando aplique; observaciones opcionales | Distinguir visualmente dos recepciones del mismo azúcar sin escanear |
| Lotes separados y trazabilidad hacia atrás | Lote interno identificable y lote de fabricante separado, con vínculo a recepción, orden, compra y proveedor | Abrir un lote y llegar a sus documentos, ubicaciones, movimientos y etiquetas |
| Listas de pendientes de viñetear, pendientes de ubicar y lotes disponibles | Cola por etapa con cantidades pendientes y siguiente acción, reutilizable por el bodeguero | Ver cómo una recepción avanza sin saltarse pasos ni desaparecer prematuramente de pendientes |
| Bodeguero con escáner y ubicación parcial | Vista móvil: leer unidad/lote, leer ubicación, cantidad y confirmar; 50 se pueden repartir 30 y 20 | Acceder con Rodrigo, completar ambos espacios y verificar el pendiente restante |
| Inventario de Apex con varias consultas conectadas | Existencias, mapa/ubicaciones, lotes, movimientos, Kardex, costo promedio y conciliación con contexto compartido | Consultar un producto desde existencia hasta ubicación, lote y movimiento |
| Detalle de un espacio y reubicación | Pasillo, estante, nivel, posición, contenido y capacidad; reubicar exige motivo | Mover entre espacios y mostrar que no cambia la existencia global |
| Saldo inicial de un producto sin movimientos | Formulario de cantidad/costo/ubicación/respaldo; bloqueo por historial, no solo por saldo actual | 80 a 6.80 = 544 y primer movimiento identificable en Kardex |
| Kardex con referencias legibles, filtros y detalle desplegable | Código de compra/recepción/retaceo/traslado/venta, lote, usuario y vínculo a documento; no mostrar solo UUID técnico | Filtrar y abrir el respaldo de una entrada y una salida |
| Cabecera de empresa/producto y descargas XLSX/PDF | Usar datos de Grupo Lorena y las mismas cantidades, filtros y alcance de la consulta | Descargar el reporte y cotejarlo con pantalla; el formato fiscal específico requiere su propia verificación |
| Valoración y conciliación del inventario | Cantidad física, cantidad valorada, diferencia, promedio y valor total al corte | Diferencia cero y costo actual explicado sin modificar movimientos históricos |
| Costos ocultos según permisos | Protección en consulta, API y archivos, además de la pantalla móvil | Contrastar cuenta autorizada y bodeguero sin filtrar importes |
| Vehículos como bodega móvil, documento y abastecimiento posterior | Mantener su conexión con inventario disponible antiguo y nuevo, en su etapa propia | Comprobar las funciones existentes después de cerrar el núcleo, sin usar distribución como atajo antes de ubicación |

Este inventario de aportes es parte del alcance de presentación. Se debe revisar
contra las capturas y recorridos existentes al implementar cada bloque, no solo
contra las frases de la revisión propia.

## 3. Matriz única de requisitos

Estados: **base** = hay código relacionado; **parcial** = falta parte del
comportamiento; **pendiente** = no se localizó el recorrido completo. Ninguno de
estos estados sustituye la aceptación integrada con datos de demostración.

| ID | Requisito integrado | Base revisada / brecha | Orden |
| --- | --- | --- | --- |
| C01 | RFQ por proveedor con varios productos y cantidades consolidadas | Base: editor multiselección, versiones, documento imprimible y cantidades de origen; demostrar varios productos en una RFQ | Base / mejora posterior |
| C02 | Registrar oferta manual, disponibilidad, precio, descuento, impuesto, vigencia, pago y adjunto original | Base; aclarar descuento monetario/porcentaje ligado al error FOB; cargos adicionales y revisión de condiciones se conservan como mejora posterior | 1 / base |
| C03 | Comparación comparable por producto y matriz de proveedores; recomendación aplicable y elección manual justificada | Matriz global de respuestas recibidas del consolidado implementada el 29/10: productos × proveedores, versiones/monedas/condiciones y acceso a adjudicación manual. Recomendación automática excluida por indicación de Rodrigo | Matriz manual / mejora posterior |
| C04 | Revisión de orden, devolución con observaciones e historial de versión aprobada | Parcial: aprobación/envío existentes; devolución y revisión aprobada equivalente pendientes | Base / mejora posterior |
| C05 | Seguimiento y accesos directos que reduzcan saltos entre documentos | Base de enlaces y atajos; reunir contexto, estado y siguiente acción reutilizando pantallas | Base / mejora posterior |
| R01 | Resolver el FOB cero sin inventar importes ni borrar historial | Confirmado: descuento 5%=100 y FOB 1900. Regularización manual documentada implementada y probada con rollback; aplicación real pendiente de cargos/comprobantes | 1 |
| R02 | Separar gastos previstos y reales; bitácora durante espera de la orden | Implementado: bitácora desde aprobación, aislada del presupuesto; cierre bloquea gastos posteriores, incluida una orden parcialmente recibida | 1/6 |
| R03 | FOB, flete y DAI explícitos; IVA/impuestos diferenciados; otros gastos detallados | Implementado/probado: captura vacía, cero explícito, componentes separados y reparto exacto | 1 |
| R04 | Desglose de otros gastos con categoría, descripción, fecha, monto y respaldo | Implementado/probado: categorías/fecha/documentos y saldo compartido entre recepciones parciales | 1 |
| R05 | Recepción parcial, faltantes, rechazos y documentos protegidos | Base de recepción/verificación; preservar factura confirmada y documentar correcciones, sin volver a editarla como si fuera nueva | 1 |
| I01 | Bloquear viñeteado antes del retaceo y alta final antes de ubicación | Implementado en 3 y aceptado en 6: cierre de retaceo, verificación y preparación no publican stock; la colocación confirma cantidad y valor una sola vez | 1–3/6 |
| I02 | Lotes distinguibles por recepción, con trazabilidad hacia compra/orden/proveedor | Implementado en 2/4; tres compras reales de prueba mantienen identidades distintas y referencias COM legibles en Kardex | 2/4/6 |
| I03 | QR y Code 128 con nombre/código, lote y recepción visibles, vencimiento cuando aplique | Implementado/probado en 2: vista previa/papel, identidad, fechas y observaciones opcionales; imprimir no mueve existencias | 2/6 |
| I04 | Pantalla propia y móvil del bodeguero: pendiente, escaneo de unidad/lote y ubicación, cantidad, confirmar | Implementado en 3: /inventory, cola por etapa, medidas/etiquetas, escaneo y colocación; movimientos físicos de su bodega sin valoración | 3/6 |
| I05 | Ubicación parcial, capacidad, estante/nivel/posición y reubicación con motivo | Implementado en 3/4: colocación parcial, consultas por espacio y reubicación de unidad disponible completa con motivo; conserva cantidad y valor | 3/4 |
| I06 | Inventario como punto de consulta: existencias, ubicaciones/mapa, lotes, movimientos, Kardex y promedio autorizado | Implementado en 4/5: Por ubicación, Unidades, Lotes y Mapa, accesos a movimientos, valoración y reportes según permisos | 4/5 |
| I07 | Mapa de bodega legible con selección de pasillo/estante/nivel/posición y contenido/capacidad | Implementado/probado en 4: esquema por pasillo, selección de espacio, contenido, capacidad y acceso desde una existencia; no representa distancias reales | 4 |
| V01 | Promedio ponderado global por empresa/producto usando solo existencia anterior restante y costo de la entrada | Aceptado en 6 por API: solicitud → orden → recepción → retaceo manual → ubicación, tres entradas 5/10/15, valores 50/150/300; promedios 10/13.333333/16.666667 | 1/3/5/6 |
| V02 | Al agotarse la existencia, la entrada nueva usa su costo; historia anterior inmutable | Aceptado en 6: entrega de las 30 unidades deja cantidad/valor cero; recepción posterior de 4 con valor 100 resulta en promedio 25, sin reescribir las tres entradas anteriores | 3/5/6 |
| V03 | Saldo inicial por producto sin movimientos: almacén, ubicación, cantidad, costo, motivo/respaldo y fecha | Implementado/probado en 4: apertura física y valorada individual, historial por empresa/producto, auditoría, idempotencia y concurrencia; requiere corte de valoración previo | 4 |
| K01 | Kardex histórico: entradas, salidas, saldo, costo aplicado/promedio, lote, usuario y documento legible | Implementado/probado en 5: referencias legibles, responsable, costo aplicado y promedio persistido con hasta seis decimales | 5 |
| K02 | Filtros por producto, sucursal, almacén, lote, movimiento, referencia y fechas | Implementado/probado en 5: filtros físicos y totales consistentes; asignación de bodega y alcance financiero global protegidos | 5 |
| K03 | Reporte identificable de empresa/producto con NIT/NRC y exportación XLSX/PDF | Implementado/probado en 5: físico/valorado/conciliación, todas las filas filtradas, límite explícito y datos fiscales disponibles. Reporte interno, sin certificación de plantilla fiscal | 5 |
| K04 | Existencia física frente a valorada, diferencia y valor total/fecha de corte | Implementado/probado en 5: diferencia cero y reconstrucción por fecha de registro local desde base aprobada; antes de ella no se inventan saldos | 5 |
| P01 | Costos solo para permisos autorizados, también en API, archivos y etiquetas | Vías nuevas de 5 probadas: costos requieren permiso y alcance global; Kardex físico/archivos limitados a bodegas asignadas | Transversal |
| A01 | Abastecimiento desde stock completo, solicitudes y mínimos; prioridad en su contexto | Base de vistas de demanda/traslados; completar análisis de mínimos y selección de stock previo en etapa posterior | Continuidad |
| A02 | Tránsito como bodega móvil, recepción en destino y documento imprimible de traslado | Continuidad comprobada en 6: despacho concurrente, tránsito, recepción parcial y reintentos; alcance por sucursal/empresa y respaldo existente | Continuidad / 6 |
| A03 | Venta, entrega, devolución y ajuste documentado | Regresión aprobada en 6: venta sin descuento físico, entrega, devolución a costo original, ajustes autorizados/rollback y permisos de comprobantes | Continuidad / 6 |

El mapa, las consultas de inventario y el Kardex están en el cierre actual. Las
recomendaciones de compras y las versiones de Gerencia permanecen
registradas como mejoras de la base anterior a recepción. No se intercalan como
bloque que retrase el ingreso, la valoración o la presentación del Kardex.

## 4. Reglas que deben mantenerse coherentes

### Compra y retaceo

- La respuesta del proveedor se transcribe y se conserva su archivo original.
  Marcar enviada una RFQ/orden registra un estado; no promete envío de correo.
- Comparar el mismo producto, unidad/equivalencia, cantidad disponible y moneda.
  Si faltan costos o condiciones, mostrar comparación parcial. Una recomendación
  no reemplaza la decisión de Compras ni compromete stock del proveedor.
- Captura manual de costos no autoriza alterar una factura confirmada. FOB
  por renglón, bruto, descuento y neto deben resultar explicables y documentados.
- Gastos previstos son presupuesto. Solo cargos reales revisados ingresan en el
  cálculo, una vez. Flete/DAI fijos no vuelven a sumarse como otros gastos.
- La clasificación de impuestos debe señalar cuáles forman costo y cuáles se
  registran separados según la política aprobada. No generalizar una regla
  tributaria a todos los impuestos por una captura del ejemplo.
- Compra local e importación deben distinguirse. Los campos no aplicables
  requieren revisión explícita; el sistema no inventa aranceles por categoría.

### Promedio, saldo inicial e historial

- Promedio de entrada = (valor anterior restante + costo total entrante) /
  (cantidad anterior restante + cantidad entrante). Usar precisión decimal y
  resolver redondeo residual para que la suma del detalle coincida con el total.
- Si cantidad y valor anteriores están agotados, el costo vigente toma el costo
  unitario de la nueva entrada. El historial de compras antiguas no se promedia
  otra vez como si siguiera existiendo físicamente.
- La apertura individual es por empresa/producto sin movimientos, aunque su
  stock actual sea cero. Haber vendido todo no habilita otro saldo inicial.
  Consultar historial, no solo saldo; impedir carreras y aperturas repetidas.
- La aprobación del corte inicial de valoración existente sirve para documentar
  el valor de stock ya registrado. No se presenta como equivalente al alta de
  cantidad, ubicación y costo de un producto que empieza sin movimientos.
- Conservar movimientos y costos históricos. Las correcciones posteriores usan
  documentos/asientos de regularización; nunca sustituyen silenciosamente los
  números de un Kardex ya emitido.
- Incluir un movimiento de saldo inicial reconocible. Reubicación y liberación
  dentro de la misma bodega conservan la cantidad total de la empresa.

### Adaptación específica a Grupo Lorena

- Usar productos, unidades, proveedores, sucursales y almacenes de Grupo Lorena.
  No reutilizar catálogos, datos fiscales ni nombres de la ferretería de ejemplo.
- Mantener unidad base y equivalencias: una etiqueta representa la unidad/caja
  física definida, no necesariamente un kilogramo ni una sola pieza comercial.
- Lote, recepción y vencimiento cuando aplique deben ser visibles. Conservar
  lote de fabricante separado del lote interno de recepción cuando exista.
- Para perecederos, mostrar alertas de vencimiento y facilitar selección por
  vencimiento más próximo entre existencias elegibles; si no hay vencimiento,
  usar antigüedad de recepción. Es adaptación del proyecto, no cita atribuida
  al ingeniero. No confundir orden físico de salida con método de valoración.
- Identificar claramente producto, lote, unidad logística y ubicación. Un código
  común del producto no distingue dos lotes; el recorrido debe resolver ese
  contexto antes de ubicar o retirar cantidades.
- El bodeguero Rodrigo opera en matriz con sus permisos, sin recibir costos ni
  opciones administrativas. La consulta autorizada de valoración es global por
  empresa/producto, aunque el detalle físico se filtre por almacén/sucursal.

## 5. Entregas incrementales

La base solicitud → cotización → orden se reutiliza. Solo se corrigen allí los
problemas que afecten el tramo actual, como el descuento que origina FOB cero.

1. **Recepción, gastos y retaceo:** R01–R05, claridad de descuento de C02 y
   comparación de promedio V01. Recibido/aceptado/faltante, factura protegida,
   bitácora de gastos, cálculo por producto, borrador y cierre. La regularización
   histórica COM-00024 necesita el descuento correcto; el resto puede avanzar.
2. **Lotes y viñeteado:** I01–I03. Cola por etapa, origen trazable, QR/Code 128,
   fecha/lote visibles, recepción/vencimiento, cantidad de etiquetas y reimpresión.
3. **Bodeguero, colocación e ingreso:** I01, I04/I05 y V01/V02. Escaneo de
   unidad/lote y ubicación, distribución parcial y entrada única; cantidades,
   costo vigente y registro histórico consistentes al confirmar.
4. **Inventario completo:** I05–I07 y V03. Existencias, ubicaciones/mapa,
   lotes, movimientos, reubicación y saldo inicial individual, conectados a las
   consultas existentes con permisos de P01.
5. **Kardex, promedio, conciliación y reportes:** K01–K04, V01/V02 y P01.
   Histórico con referencias y costos de cada movimiento, filtros, valor vigente,
   diferencia cero y exportaciones coherentes. Este bloque forma parte de la
   entrega final y no depende de rediseñar compras.
6. **Demostración completa y continuidad:** ejecutar el guion de la sección 6,
   guardar evidencia y revisar A01–A03 para que cambios de ingreso no rompan las
   salidas, devoluciones, ajustes o traslados existentes. Las ampliaciones de
   compras y abastecimiento conservadas en la matriz se ordenan después.

**Condición de cierre:** ninguna entrega que termine solo en retaceo o etiquetas
se marca como cierre del trabajo actual. Deben poder mostrarse el producto ya
ubicado, su existencia, el promedio vigente, los movimientos históricos del
Kardex y la conciliación correspondiente, con sus reportes y permisos. Esto es
el objetivo de presentación acordado; no una garantía de una nota específica.

## 6. Evidencia de aceptación prevista

| Caso | Resultado que debe demostrarse |
| --- | --- |
| Una RFQ con varios productos a un proveedor | Documento único, cantidades consolidadas y respuesta con archivo conservado |
| Dos o tres ofertas del mismo producto | Comparación de unidades/costos completos; recomendación explicable y selección manual auditada |
| Gerencia devuelve y luego aprueba | Motivo, versión corregida y versión aprobada conservadas; envío registrado sobre la versión correcta |
| Gasto real durante espera | Aparece en bitácora y participa una sola vez en el retaceo |
| Recepción de 8 de 10 | Pendientes/faltantes y costo sobre lo recibido documentados, sin consumir dos veces gastos comunes |
| Costo/ubicación incompletos | Operación siguiente bloqueada; ningún doble ingreso al reintentar |
| Tres ingresos del mismo producto con cantidades distintas | 5 a 10 → 10 a 15 → 15 a 20: saldos 5/15/30, valores 50/200/500 y promedios 10/13.333333/16.666667, con tres movimientos históricos |
| Agotar existencia y recibir nuevamente | Promedio del nuevo lote; costos anteriores conservados |
| Apertura de producto nuevo | 80 a 6.80: 80 unidades, valor 544 y promedio 6.80; repetir o usar producto con historia se rechaza |
| Colocar 50 en dos espacios | 30 en A + 20 en B; pendientes y capacidad correctos; suma física/valorada consistente |
| Reimpresión y escaneo | Mismo lote, fechas visibles y cantidad sin cambios; unidad y ubicación identificadas |
| Consulta/exportación Kardex | Filtros y referencias consistentes, identificación de empresa/producto y mismos totales en pantalla/XLSX/PDF |
| Bodeguero frente a administrador | Tareas móviles y bodega permitida; costos protegidos en respuesta API y archivos, no solo columnas ocultas |
| Abastecer con stock antiguo y nuevo | No se limita a la última recepción; usa solicitudes/mínimos y existencias disponibles |
| Tránsito y destino | Cantidad sale de origen, permanece en vehículo y entra a destino solo al confirmar su recepción |

### Guion de cierre del tramo recepción → Kardex

1. Usar una orden ya creada para concentrar la exposición en el tramo mejorado.
2. Mostrar recepción y un faltante/parcial, gastos con sus comprobantes y costo
   del retaceo; distinguir costo de lote y promedio del producto.
3. Cerrar retaceo, generar lote y enseñar ambas etiquetas con fecha/lote legibles.
4. Con Rodrigo, ubicar parte en un espacio y el resto en otro; comprobar el alta
   final y los pendientes. Abrir mapa/espacio y contenido del lote en inventario.
5. Repetir el ingreso del mismo producto en tres ocasiones y comparar cantidad,
   valor y promedio calculados. Incluir el caso de existencia agotada y el de
   apertura de un producto nuevo, en datos separados para no mezclar historias.
6. Mostrar Kardex cronológico y filtros; abrir respaldo de recepción/retaceo y de
   una salida existente. Mostrar costo histórico y costo vigente sin reescritura.
7. Cerrar con conciliación física/valorada, diferencia cero y reporte XLSX/PDF;
   contrastar permisos de administrador y bodeguero.

Los ejemplos se ejecutan en `erp_db_test`; no se han registrado automáticamente en la
base de demostración `erp_db`. Las cifras comerciales de una compra histórica no se sustituyen por estos
valores de demostración.

## 7. Estado y límites de esta actualización

Cierre del bloque 6, 29/10/2026: recorrido comercial integrado y regresiones
de continuidad verificados en base aislada. Incluye tres entradas, agotamiento,
recepción parcial posterior, historia inmutable, permisos y exportación. Evidencia
en [aceptación final](bloque-06-aceptacion-final-2026-10-29.md) y recorrido práctico en
[guion de exposición](guion-exposicion-corto-grupo-lorena.md).
La preparación de los datos que Rodrigo elija mostrar y su ensayo con las dos
cuentas se hacen en la aplicación; esta aceptación no modifica sus compras reales.
Después del bloque 6, Rodrigo autorizó únicamente la matriz de proveedores de C03,
sin recomendación automática ni otras ampliaciones. Detalle en
[matriz manual](matriz-proveedores-manual-2026-10-29.md). C04/A01 siguen posteriores.

Actualización del bloque 4, 28/10/2026: implementadas las consultas conectadas,
el mapa esquemático, la reubicación con motivo y el saldo inicial individual.
Los pendientes del flujo anterior se conservan en consultas plegadas; no se
eliminaron ni se recibieron de nuevo para limpiar la vista. Implementación,
validaciones y guion en [bloque 4](bloque-04-inventario-conectado-2026-10-28.md).
El bloque 5 se implementó y probó el 29/10/2026; detalle y límites en
[Kardex y reportes](bloque-05-kardex-reportes-2026-10-29.md). La demostración
integrada y las regresiones del recorrido completo se cerraron en el bloque 6.

Actualización del 28/10/2026: el bloque 3 está implementado y verificado, con
alta física/valorada al confirmar ubicación, pantalla móvil del bodeguero y
conservación de los movimientos existentes. Alcance, pruebas, migración y
guion de revisión en [bloque 3](bloque-03-bodeguero-ingreso-2026-10-28.md).
Ese avance por sí solo no cierra la presentación completa del Kardex.

Actualización de implementación del bloque 1:
[captura manual y gastos reales](bloque-1-retaceo-manual-2026-10-27.md).
El bloque 2 se documentó en [lotes y etiquetas](bloque-02-lotes-etiquetas-2026-10-28.md).
Los párrafos siguientes describen la consolidación documental inicial; no sustituyen
los informes de implementación de los bloques 1–5 ni la aceptación integrada
del bloque 6.

Se consolidó el alcance y se revisó código de apertura de valoración, filtros de
Kardex y compras. En ese diagnóstico inicial, el corte tomaba un snapshot de
existencias y sus costos sin ofrecer el alta física individual descrita en V03;
esa apertura individual se implementó después en el bloque 4. En el recorrido Kardex
revisado no se localizaron exportación XLSX/PDF ni cabecera NIT/NRC equivalentes.
Estas brechas no se declaran resueltas por esta actualización documental.

Durante esa consolidación documental inicial no se modificaron compras, gastos,
inventario, credenciales ni valoración, ni se ejecutaron casos de aceptación.
Las implementaciones posteriores y sus pruebas se documentan en los bloques enlazados.

Las menciones al Código Tributario, Hacienda, plazos y formatos en las notas se
conservan como contexto de clase. Para declarar compatibilidad con un formato
fiscal concreto se debe identificar y comprobar la plantilla oficial vigente;
un PDF/XLSX de uso interno no recibe esa certificación automáticamente.

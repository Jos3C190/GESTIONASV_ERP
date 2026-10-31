# Manual de pruebas y demostración ERS B01–B08

**Versión:** 1.1 · **Fecha:** 19/10/2026  
**Estado vigente:** guía de demostración; aceptación B01–B08 **PARCIAL** por V01/V02/V03-02/03/05 y V04-04, además de la demostración manual del usuario. Ver [revisión vigente](revision-completa-2026-10-19.md).  
**Datos:** usar un artículo ficticio nuevo, distinto del café histórico y del corte inicial aprobado. Identificar todos los documentos con una nota como `ERS-DEMO-20261019`.

## Actualización vigente — 21/10/2026

### Continuación más reciente — 21/10/2026

La conciliación de solo lectura confirma que los cuatro SKU protegidos permanecen iguales y que V04-01/02/03 siguen persistidos. Se encontraron tres pares de alias de recepción en la clon para seleccionar en la demostración; las consultas visuales de esos alias siguen pendientes. El navegador rechazó `localhost:5174/inventory/trace` por su política de URL y se detuvo esa parte. No se cambió código de producto. La lista exacta de casos pendientes y siguiente acción está en el [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md).

RustFS real pasó un round-trip ficticio con hash idéntico y limpieza del objeto. El API de documentos no se probó porque el login de test devolvió 401; no se probó otra contraseña. Esto no cierra los adjuntos por módulo.

La ejecución final de cuatro verificaciones se hizo en una clon aislada. V04-01/02/03 aprobaron con persistencia; no repitas esos documentos. V01 permisos/documentos, V02 exportación de capturas, V03 recepción repetida/alias/privacidad y V04-04 pérdida de respuesta postcommit desde UI siguen abiertos. El estado de cada caso y la conciliación de los cuatro SKU protegidos están en el [informe final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md), [registro](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md) y [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md). Este manual sigue siendo una guía de demostración; no se declara ejecutado completo por el usuario.

## Actualización de aceptación — 20/10/2026

El manual sigue siendo una guía de demostración y **no se ejecutó de principio a fin con clics**. La última continuación agregó evidencia E2E de documentos de ajustes, corrección compensatoria, traslado parcial/final y devolución parcial multi-asignación/rollback; también corrigió la presentación de lote en la ficha HU. Los pasos, resultados y límites están en [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md). La aceptación manual continúa parcial: faltan PNG exportados de los siete recorridos, matriz E13, recepción visual con SKU repetido/consulta UI de códigos aplicables, devolución mixta desde formulario y recuperación desde navegador tras descartar controladamente la respuesta. No repetir los documentos ya aplicados ni usar los SKU protegidos para escrituras.

## Antes de empezar

En las recepciones, **Guardar borrador** prepara el documento y abre ahora su detalle; **Confirmar recepción** actualiza el pendiente de la orden y **Verificar recepción** registra la mercancía aceptada en inventario. Si ya hay un borrador de esa orden, continuar ese documento. Una orden totalmente recibida muestra **Recepción completada** y no admite otra recepción mientras esté completa. El [diagnóstico de OC-00019](diagnostico-oc-00019-recepciones-y-cierre-2026-10-21.md) documenta la corrección y sus pruebas; el COM-00021 real no fue confirmado por el agente.

1. Ingresar con un usuario autorizado de la empresa y elegir la sucursal correcta. Confirmar que la bodega central original está asociada a la sucursal matriz y que las sucursales de destino aparecen activas.
2. Seleccionar un artículo base con unidad/conversión conocida. Registrar SKU, unidad base, lote y vencimiento si aplica. No usar HUs ni lotes históricos para los casos de costo.
3. Usar las pantallas y movimientos normales del sistema; no editar la base ni ejecutar semillas que borren datos. Guardar los códigos de solicitudes, compras, recepción, retaceo, traslado, venta, entrega, devolución y ajuste.
4. Para costo de apertura se permite un ajuste positivo ficticio, documentado y aprobado. La impresora y el lector físicos no se necesitan: basta revisar la vista software de la etiqueta/QR.
5. Anotar cantidades en unidad base y valores con la precisión completa que presenta la valoración. No calcular saldos redondeando primero el costo promedio.

## Caso calculable principal

| Paso | Pantalla/acción | Datos y resultado esperado |
| --- | --- | --- |
| 1. Saldo inicial | Inventario → Ajustes. Crear/aprobar ajuste positivo con motivo y documento de demostración. | 5 unidades base a USD 10 = **5 unidades / USD 50**. Confirmar en valoración y Kardex. |
| 2. Solicitud de compra | Compras → Solicitudes. Crear y aprobar la solicitud del artículo de demostración. | Cantidad pedida suficiente para la recepción de 10 unidades. Registrar sucursal solicitante y requerida. |
| 3. Consolidar y cotizar | Consolidar solicitudes aprobadas, crear cotización y orden de compra por los pasos de compras. | La solicitud queda como origen del consolidado; verificar que el borrador no duplica ni altera la cantidad solicitada. |
| 4. Recibir y retacear | Compras → Recepción. Recibir 10 unidades. Para simular importación, usar costo base total USD 100 y gasto aplicable USD 50; verificar y aplicar el retaceo una vez. | La recepción vale USD 150. Junto con el saldo previo: **15 unidades / USD 200**, promedio exacto `200/15` (USD 13.333333… por unidad). Si no se usa retaceo, recibir las 10 a USD 15 y documentar por qué el gasto no aplica. |
| 5. Lote, ubicación y etiqueta | Abrir recepción/lote; generar vista de etiqueta; asignar ubicación, revisar producto/unidad, confirmar etiqueta software y liberar solo tras terminar las verificaciones. | El lote mantiene el detalle de recepción. La etiqueta identifica nombre, SKU/código, lote y fecha. Buscar su código en Kardex. Abrir/cerrar/reimprimir no altera cantidad. Dividir es opcional y solo crea movimientos al confirmar expresamente. |
| 6. Traslado a sucursal | Inventario → Traslados o acción desde Almacenes. Elegir la sucursal que solicita el artículo, vehículo y unidades. Preparar 10; despachar y recibir 8, luego 2. | Preparación: total empresa **15/USD 200**. Despacho: central 5, tránsito 10. Primera recepción: central 5, sucursal 8, tránsito 2. Recepción final: central 5, sucursal 10, tránsito 0. El total global permanece **15/USD 200**. |
| 7. Cotización y venta | Ventas → Clientes, Cotizaciones y Ventas. Crear cliente ficticio, cotización y venta de 3 unidades para la sucursal destino. | El precio comercial se diferencia del costo. Antes de entregar, el inventario sigue en **15/USD 200**. Venta/cotización no son salida física. |
| 8. Entrega | En la venta, preparar y confirmar la entrega de 3 unidades elegibles. | La sucursal baja de 10 a **7**; empresa queda en **12 unidades / USD 160**. El costo de salida esperado es USD 40 con el costo medio exacto `200/15`; revisar con el valor guardado por el motor. Recargar y consultar Kardex/conciliación. |
| 9. Registrar devolución | Desde Ventas/Devoluciones, crear retorno de 1 unidad ligado a la asignación de esa entrega y registrar recepción. | La recepción documental **no** incrementa stock ni valor. No exceder la unidad efectivamente entregada pendiente de devolución. |
| 10. Revisar y aceptar | Inspeccionar la línea; aceptar 1 unidad apta. Si corresponde, mantenerla primero en cuarentena y terminar sus verificaciones antes de liberarla. | La aceptación repone al costo efectivo original de la asignación (aprox. USD 13.333333…), no al precio de venta. Empresa: **13 unidades / aprox. USD 173.333333**; sucursal: 8. Liberar de cuarentena no debe crear una segunda entrada. |
| 11. Ajuste final | Crear/aprobar/aplicar ajuste negativo documentado de 1 unidad disponible al costo medio vigente. | Empresa: **12 unidades / aprox. USD 160**. Confirmar que venta, entrega, devolución y movimientos originales siguen visibles; conciliación por ubicación/estado debe cuadrar. |

Las cifras orientan la revisión. Si la aplicación usa una precisión decimal documentada distinta, comparar con el valor de servidor y explicar el redondeo de presentación; no aprobar una discrepancia calculada desde valores redondeados en pantalla.

## Casos negativos que se deben probar

- Intentar recibir/devolver más de lo entregado pendiente, aceptar más de lo recibido o resolver más de la cantidad pendiente: el servidor debe rechazar sin cambios parciales.
- Probar stock en tránsito, cuarentena, ubicación incompatible, HU cerrada, saldo insuficiente, sucursal ajena y empresa ajena: ninguna debe quedar disponible o contabilizada por error.
- Repetir con la misma clave una recepción, entrega, aceptación o ajuste; no se duplica. Repetir la clave con otro cuerpo debe dar conflicto.
- Abrir/cerrar/cancelar formulario de división y revisar/reimprimir etiqueta: no modifica la cantidad. Confirmar una división explícita: la suma de nueva unidad + remanente conserva el saldo.
- Provocar una operación con una segunda línea inválida: documento, saldo, valoración y auditoría de éxito deben revertirse juntos.
- Una entrega confirmada no se edita; una devolución no reabre el pendiente de venta; corregir con documento compensatorio autorizado.
- Probar lector sin permiso de costos, operador de sucursal y perfil autorizado de empresa distinta. No se deben exponer costos globales, datos de otra empresa ni adjuntos ajenos.

## Revisión de interfaz

Repetir las pantallas clave en ambos temas y un ancho móvil: resumen de almacén, recepción/lote/etiqueta, traslados, ajustes, cliente/cotización/venta, entregas, Devoluciones y Kardex. Comprobar estados de carga/error/vacío/permisos, textos con nombre de producto y unidad y que una falla de consulta no aparezca como cero real. En **Devoluciones**, abrir el detalle desde una venta entregada, recargar y comprobar los eventos y cantidades guardadas.

## Registro de resultado

Por cada paso, anotar fecha/hora, perfil, empresa/sucursal, código de documento, SKU/lote/HU, cantidad base, valor, resultado esperado/real y captura sin credenciales. Si algo difiere, no repetir una operación de escritura a ciegas; revisar primero el documento y Kardex, guardar el error y detener la secuencia en ese punto.

La ejecución completa por clics de este manual sigue **pendiente**. La [evidencia actual](revision-completa-2026-10-19.md) distingue el recorrido real por API, consulta visual y pruebas aisladas; no confundir esas modalidades de comprobación.

## Demostración ya guardada para inspeccionar

Empresa **Grupo Lorena**, operador autorizado `superadmin`, artículo **ERS-REVIEW-DD6BBF85**, nombre «Artículo demostración integral ERS-REVIEW-DD6BBF85», unidad base `u`. No se incluyen contraseñas. No se necesita reconstruir documentos ni tocar el café histórico para consultar estos resultados.

| Documento o punto | Código / resultado |
| --- | --- |
| Solicitud de El Tránsito | SCR-00037 |
| Consolidado | CD-00007 |
| Ajuste positivo inicial aplicado | AJ-20261019-000001, 5 unidades/USD 50, con adjunto |
| Compra recibida en Bodega Madre Grupo Lorena | COM-00018, 10 unidades a USD 15, caso local sin retaceo |
| Lote del detalle | LOT-COM-00018-D5D319E0D778A4021B149F692E766083D |
| Traslado al almacén El Tránsito | TR-20261020-1454CFC3, 10 despachadas con vehículo, recibidas 8 y después 2; total empresa 15/USD 200 |
| Cotización comercial | CV-20261019-320C7EBB |
| Venta | VTA-20261019-81DD0543, 3 a precio 25, total comercial USD 75 |
| Entrega | ENT-20261020-7D62A6E4, salida de 3, costo USD 40 |
| Devolución | DEV-20261020-87D20EC3, aceptada 1; después se revisó/liberó y un ajuste negativo documentado retiró esa unidad |
| Ajuste negativo final aplicado | AJ-20261019-000002, salida de 1, con adjunto |
| Conciliación final del artículo | Central 5 + El Tránsito 7 = físico 12 = valorado 12; diferencia 0; valor USD 160 |

Para revisar la venta: Ventas → buscar **VTA-20261019-81DD0543** → comprobar «Entregada», entrega confirmada e historial de devolución aceptada. «Aceptada · ingresó en cuarentena» describe el evento original, no su disponibilidad actual. El límite pendiente de devolución es 2; no lo uses para repetir la prueba sobre el caso ya conciliado.

En Kardex → Conciliación, buscar el artículo y comprobar 12/12/diferencia 0/USD 160. En movimientos físicos seleccionar la bodega y el artículo; el código del lote mostrado arriba también debe filtrar su historial. El flujo de almacén termina en **«Revisión terminada · disponible para uso»**; dividir nuevamente es opcional, no el siguiente paso obligatorio.

En compras consolidadas, el orden operativo es RFQ/respuestas → evaluación → **adjudicación del consolidado** → orden de compra. No intentar seleccionar directamente una respuesta RFQ consolidada como si fuera una cotización individual. Para una nueva demostración, usar otro SKU y conservar el resultado existente.

### Otros casos ya guardados (20/10/2026)

- **Incidencia y pérdida autorizada:** SKU ERS-INC-EE8FE228, traslado TR-20261020-3BF90713, despachado 3, recibido 2 y faltante 1. En pantalla se registraron/resolvieron incidencias y se creó, adjuntó, aprobó y aplicó AJ-20261020-000002. Final: Cerrado con ajuste; conciliación 4/4, diferencia 0, USD 40. Consultar el historial; no volver a aplicar ni registrar otra pérdida.
- **Rechazo sin inventario:** en VTA-20261019-81DD0543, DEV-20261020-8A63F2BF quedó rechazada por 1 dañada, sin entrada ni reserva. Se conserva el ejemplo principal en 12/USD 160.
- **Retaceo tardío:** SKU ERS-LATE-B1B55D6D, COM-00019, RET-00016. Entraron 10 a 10 y se entregaron 6; quedaban 4/USD 40. En el formulario se agregó flete 20, se adjuntó ACTA-RETACEO-DEMO.txt, se calculó/verificó sin efecto en stock y se aplicó/cerró: 4/USD 48. Ocho del gasto quedaron en inventario y doce en las salidas.
- **Devolución después del retaceo:** VTA-20261020-EC35E6B7, DEV-20261020-ACB68F5E. Recepción documental mantiene 4/48; aceptar 1 desde pantalla deja 5/60. Después se verificó HU-RET-222B0730708C466E (0.1 kg/0.001 m³), se registró por API una impresión digital simulada y se confirmó/liberó desde pantalla. Ya muestra «Revisión terminada · disponible para uso»; conserva 5/60 y no requiere repetir aceptación, división ni liberación.
- **Flujo comercial por pantalla y entregas parciales:** cliente/SKU ERS-UI-F767BABC, CV-20261020-2BFF8493 → VTA-20261020-C99E3B6F, 4 a precio comercial 20. Cliente, cotización y venta no consumen las 4 unidades/USD 40. ENT-20261020-60E9E1AB entrega 2 y deja 2/USD 20; ENT-20261020-0E0F9F4C entrega las otras 2 y deja 0/USD 0. La venta muestra 4 entregadas, cero pendientes y conserva ambas salidas. No repetir entregas sobre este caso terminado.

Son documentos ficticios persistidos para consultar. Los detalles de evidencia y límites de cobertura están en el informe actual; estos casos no sustituyen la matriz completa de perfiles y pantallas.

## Casos finales de clon — 21/10/2026

Estos documentos se crearon solo en la clon aislada para la aceptación V01–V04. No repetir escrituras sobre ellos y no confundirlos con los casos históricos de `erp_db`:

| Flujo | Referencia | Resultado persistido |
| --- | --- | --- |
| Corrección de ajuste | `AJ-20261020-000005` → `AJ-20261020-000006` | Ambos aplicados; el segundo enlaza al original y genera movimiento compensatorio. |
| Traslado parcial/final | `TR-20261021-60344005`, `SCR-00009` | 10 despachadas; recibidas 8+2; estado recibido; valor global neutro. |
| Venta con dos entregas | `VTA-20261020-63B217FB`; `ENT-20261021-C8347B11` + `ENT-20261021-AA22CD2A` | Dos HUs de 4 unidades; venta completa. |
| Devolución mixta | `DEV-20261021-530AF39F` | 3 de la primera entrega: 2 aptas aceptadas a cuarentena; 1 dañada rechazada; pendiente 0. |
| QR/división cancelada | `HU-8D63FE508BF14124`, `HU-8FEE57267CC84449` | Consulta QR pública sin costo; cancelar división conservó 2.25 cj en ambas unidades. |

La [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y el [log de solo lectura](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log) confirman los cuatro SKU protegidos contra el baseline en demo y clon. La aceptación global sigue parcial: V01 permisos/documentos, V02 PNG, V03 recepción repetida/alias y V04 pérdida de respuesta postcommit quedan pendientes. Para las instrucciones de seguimiento, ver el [cierre integrado](cierre-visual-y-permisos-b01-b08.md).
 
## Estado de aceptación y conciliación — 20/10/2026

No repitas escrituras de los artículos y documentos ya cerrados. El snapshot final de solo lectura está en [protected-skus-after-continuation.log](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/protected-skus-after-continuation.log): ERS-INC-EE8FE228 = 4/4, USD 40; ERS-LATE-B1B55D6D = 5/5, USD 60; ERS-REVIEW-DD6BBF85 = 12/12, USD 160; ERS-UI-F767BABC = 0/0, USD 0. En todos, físico y valorado coinciden.

La unidad duplicada en presentación quedó corregida. Devoluciones distingue Aceptada/Rechazada y anuncia el conteo del filtro; la segunda revisión independiente aprobó esa pantalla con 8.56/10. El corte anterior también comprobó móvil y teclado. Esta continuación corrigió la ficha HU para separar lote fabricante/detalle/cabecera y actualizó los requisitos de permiso de descarga documental.

En esta continuación pasaron 47 Vitest focalizadas, Svelte-check con 0 errores, ESLint enfocado y build. En el corte previo backend unitario pasó 753 con extras dev+ocr. No se repitieron suites completas. Ver el informe [cierre visual y permisos](cierre-visual-y-permisos-b01-b08.md) y [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md) para resultados y límites.

La aceptación integral sigue **PARCIAL** por E13 no exhaustiva, PNG P02 no exportado, recepción visual repetida y consultas UI P03, más devolución mixta/recuperación desde interfaz P04. No vuelvas a liberar la HU devuelta ni aplicar el retaceo cerrado.

# Revisión integral ERS B01–B08

## Estado vigente — cuatro puntos finales, 21/10/2026

La aceptación integrada sigue **PARCIAL**. V04-01/02/03 aprobaron en UI con persistencia y conciliación en clon; V01, V02, V03 y V04-04 conservan casos abiertos concretos. No hay defectos funcionales reproducidos que requieran otro cambio de código en esta pasada. Los cuatro SKU protegidos concilian igual en la base habitual y el clon. Consultar el [informe fechado](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md), el [registro de casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md), la [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y el [cierre vigente E01–E15](cierre-visual-y-permisos-b01-b08.md).

## Actualización vigente — continuación final 20/10/2026

El resultado actual y la evidencia detallada están en [cierre visual y permisos](cierre-visual-y-permisos-b01-b08.md), [cierre de pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md) y [recorrido visual adicional](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/mobile-ui-run.md). La suite backend unitaria completa aprobó 753 con extras dev+ocr, por lo que la mención posterior a una suite bloqueada por `pikepdf` quedó reemplazada. Devoluciones también se probó a 390×844, en claro/oscuro y con teclado. Traslados se corrigió tras la evaluación crítica móvil y pasó la regresión focalizada, check, lint y build.

La continuación agregó una prueba de autorización documental de ajustes y corrigió la descripción API/RBAC; comprobó también corrección de ajuste, traslado parcial/final y devolución parcial/multi-asignación en API/PostgreSQL. La ficha de la HU `HU-8D63FE508BF14124` ahora muestra producto, detalle canónico y cabecera de recepción sin alterar datos. Los detalles y límites están en [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

La aceptación continúa **PARCIAL**: E13 no tiene matriz completa; no se pudo guardar PNG con la capacidad CUA disponible; P03 aún requiere una recepción visual de varias líneas repetidas y consultas UI de los códigos realmente aplicables; P04 aún requiere devolución mixta en interfaz y recuperación de respuesta descartada desde navegador. Los dos E2E repetidos del corte previo siguen siendo regresiones y no casos nuevos. No se escribieron los SKU protegidos ni se requiere hardware físico.

## Actualización vigente — revisión y correcciones del 19/10/2026

El [informe actual](revision-completa-2026-10-19.md) amplía y sustituye el estado de aceptación de este primer corte. Ya existe una demostración persistida, creada por API autenticada: solicitud/consolidado/compra → traslado parcial 8 + 2 → venta/entrega → devolución → ajuste; conciliación final **12 unidades/USD 160, diferencia 0**. Se comprobó la lectura de la venta y devolución en navegador. La aceptación integral sigue parcial por los controles visuales y perfiles que el nuevo informe identifica; ya no está impedida por ausencia de ventas.

Los apartados siguientes se conservan como **primer corte histórico**, anterior a esa demostración. Sus referencias a base vacía, 483 pruebas y casos no ejecutados no representan el último resultado.

## Primer corte histórico

**Fecha:** 19/10/2026  
**Resultado:** **PARCIAL**. Las implementaciones y las pruebas técnicas focalizadas están presentes; la aceptación integrada con transacciones persistidas en navegador no se puede afirmar todavía.  
**Base:** `erp_db`, Alembic `0090 (head)`.  
**Evidencia reunida:** [registro de esta revisión](../../tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md), [entregas B01–B08](.) y [checklist](prompt-luna-bloque-09-aceptacion.md).

## Hallazgo que limita el cierre

La base de demostración tiene cero clientes, cotizaciones, ventas, entregas y devoluciones. El navegador autenticado confirmó que `/sales/returns` resuelve y presenta el estado vacío real; no hay venta entregada desde la que crear una devolución. Por eso no se completó en la demo la secuencia de compra → recepción/retaceo → traslado → venta → entrega → devolución → ajuste. No se usó una respuesta simulada como sustituto ni se marcaron esos recorridos como aceptados.

La tabla distingue **verificación técnica previa o actual** de **aceptación integrada**. La primera puede estar aprobada en API/PostgreSQL; la segunda requiere ejecutar el caso persistido en el entorno indicado.

## Estado E01–E15

| ID | Verificación técnica disponible | Estado de aceptación integrada | Pendiente concreto |
| --- | --- | --- | --- |
| E01 Matriz y bodega central | Migración/pruebas de B01 y comparación de datos; la bodega central conserva identidad e historial. | **Parcial** | Verificar visualmente asociación y permisos en la ficha de bodega y sucursal matriz. |
| E02 Lote por detalle de recepción | API/E2E B02 cubre lote asociado a producto y recepción, incluida parcialidad. | **Parcial** | Crear una recepción de demostración y comprobar código/origen visible en lote y producto. |
| E03 Saldo por ubicación | Pruebas API/E2E previas concilian saldos atribuibles y legado. | **Parcial** | Recorrer recepción, ubicación y conciliación por ubicación en pantalla. |
| E04 Etiqueta y reimpresión | Preview/API B02; generación y confirmación son software. Impresora física excluida. | **Parcial** | Comprobar nombre del producto, SKU/lote/fecha, historial y reimpresión sin cambio de cantidades. |
| E05 Código de etiqueta en Kardex | E2E B02 comprueba resolución por código canónico y código de cabecera. | **Parcial** | Leer el código mostrado en pantalla y confirmar que filtra sus movimientos en Kardex. |
| E06 Vehículo, tránsito y estados | Integración B03/B04 cubre estados y vehículo. | **Parcial** | Navegar demanda por sucursal, preparación, despacho, recepción y estados con un traslado real. |
| E07 Parcialidad y costo neutro de traslado | PostgreSQL B03 cubre despachos/recepciones parciales y neutralidad del valor. | **Parcial** | Ejecutar 10 unidades: salida 10, recepción 8 + 2 y comprobar cada saldo. |
| E08 Ajustes documentados | B05 verifica motivo, autorización, evidencia, aplicación idempotente, reverso y rollback. | **Parcial** | Hacer ajuste de inicio y uno negativo con adjunto, autorización y comprobación de Kardex. |
| E09 Cotización y venta sin salida física | E2E B06 comprueba conversión e invariantes de inventario/valoración. | **Parcial** | Crear cliente/cotización/venta, recargar y comprobar que no cambia stock hasta la entrega. |
| E10 Entrega desde sucursal y costo | E2E B07 cubre entrega parcial/final, sucursal, HU, promedio, concurrencia y rollback. | **Parcial** | Entrega persistida en navegador, recarga, respuesta perdida, Kardex y conciliación. |
| E11 Devolución limitada a entrega | E2E B08 cubre origen, límites, resolución, costo original e idempotencia. | **Parcial** | Crear y resolver una devolución desde una entrega visible en la demo. |
| E12 Promedio global y movimientos | Pruebas B02–B08 cubren valoración por empresa/producto, salida, devolución y traslado. | **Parcial** | Conciliar el flujo completo y probar el retaceo tardío afectando inventario remanente y costo de venta. |
| E13 Permisos, alcance y rollback | Hay pruebas seleccionadas por bloque; B08 incluye 403 sin permiso. No hay matriz exhaustiva integrada. | **Parcial** | Probar lector/operador/administrador, otra sucursal y otra empresa; verificar replay y protección de costos. |
| E14 Cuarentena, retaceo y disponibilidad | Pruebas cubren precondiciones de liberación, cuarentena y ajustes; el retaceo tardío no se recorrió integrado. | **Parcial** | Recibir, etiquetar, inspeccionar, aplicar retaceo, liberar y comprobar que no se duplica existencia. |
| E15 Migración y conciliación | 0090 en demo; respaldo verificado y comparación de 30 tablas con ensayo, cero diferencias antes/después salvo el esquema esperado. | **Parcial** | Completar conciliación tras el recorrido de extremo a extremo; conservar evidencia de IDs y saldos finales. |

## Regresiones y salud técnica

- La suite frontend completa pasó: **108 archivos / 483 pruebas**. La regresión histórica de fraccionamiento estaba acoplada al texto anterior “Preparar fracción”; la acción operativa ahora se llama “Dividir unidad”. La prueba de integración usa el nombre visible vigente y las pruebas de `HandlingUnitsPanel` verifican abrir/cerrar/cancelar sin invocar la mutación y división explícita.
- `pnpm check`: **0 errores**, 8 avisos CSS en `TransferOperationsPage.svelte` (`@apply` ya existentes). Build de producción exitoso; quedan avisos no bloqueantes de `jsbarcode` y `adapter-auto`.
- La E2E B08 pasa: **1 passed** en 210.93 s. Prueba transacción/rollback en la base de prueba, no crea ventas en la demo.
- ESLint focalizado de la nueva bandeja, navegación y API cliente pasa.
- El recorrido de navegador de Devoluciones valida solo la ruta y el estado vacío. No equivale a aceptación de devolución funcional.
- No se probaron impresora ni lector físicos; no son requisito según lo indicado por el usuario.

## Conclusión y criterio de cierre

B08 está **implementado y verificado técnicamente**. El cierre de aceptación B01–B08 permanece **parcial** hasta que se ejecute el manual con documentos de demostración persistidos, se verifique la conciliación final y se completen los perfiles/contextos indicados. No hace falta otro bloque B09: ese checklist ya forma parte del cierre de B08.

Siguiente acción: usar [manual de pruebas y demostración](manual-pruebas-y-demostracion.md) en una base de demo con datos ficticios; documentar el resultado y los IDs creados. La pantalla vacía actual no permite continuar una devolución sin primero completar ventas y entregas.
 
## Corte intermedio — 20/10/2026 (superado por la continuación final)

El texto de este apartado conserva el estado anterior a P01–P04. Para el estado vigente, usa la actualización que aparece al inicio y su [registro de casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

Consultar [cierre visual y permisos B01–B08](cierre-visual-y-permisos-b01-b08.md) para el estado vigente E01–E15. Unidad duplicada y distinción/feedback de filtros de Devoluciones quedaron corregidos; su segunda revisión independiente aprobó 8.56/10. Frontend 513/513, backend focalizado 25, E2E seleccionadas 33; tipos 0 errores/8 avisos CSS, lint focalizado y build aprobados. La suite completa tests/unit está bloqueada al recolectar por pikepdf ausente.

La conciliación de demo se hizo en solo lectura. E13 sigue parcial por no tener la matriz exhaustiva de roles, acciones, alcances y documentos. Devoluciones móvil, recepción con líneas repetidas y alias históricos quedan pendientes. No se declara aceptada toda la revisión B01–B08.

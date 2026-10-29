# Entrega ERS-B08 — devoluciones de clientes y cierre integrado

## Estado vigente — cuatro verificaciones finales, 21/10/2026

### Continuación ejecutada — 21/10/2026

La continuación verificó conciliación `READ ONLY` en clon y demo y consultó los alias de recepción que sí existen en la clon; no realizó escrituras de inventario ni cambios al producto. La lectura de UI en `localhost:5174` fue rechazada por la política de seguridad del navegador, de modo que V01/V02/V03-02/03/05 y V04-04 permanecen abiertos. El scorecard estático no alcanzó el umbral de 8.5/10 ni constituye aceptación visual. Evidencia detallada: [informe](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md).

V01 adicional: RustFS aceptó y devolvió un archivo ficticio idéntico por su adaptador; la operación documental API quedó detenida en login 401 antes de crear un documento. No se intentaron más credenciales.

V04-01/02/03 aprobaron desde UI con persistencia y conciliación. V01 permisos/documentos, V02 evidencia PNG, V03 recepción repetida/alias/privacidad y V04-04 recuperación tras pérdida de respuesta siguen **ABIERTO**; por tanto, la aceptación total de B01–B08 permanece **PARCIAL**. La conciliación por SKU, documentos, movimientos y resultados está en [conciliación final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y [registro V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md). No se requieren lector ni impresora físicos.

## Estado vigente — continuación final del 20/10/2026

La continuación queda documentada en [cierre visual y permisos](cierre-visual-y-permisos-b01-b08.md), [cierre de pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md) y [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md). Se agregó cobertura de documentos de ajustes (redacción, denegación/permiso, sucursal/empresa, retiro y revocación); API/PostgreSQL valida corrección de ajuste, traslado parcial/final y devolución parcial con varias asignaciones/rollback. La ficha HU ahora muestra el origen de recepción sin mutación. Vitest enfocado pasó 47, Svelte-check 0 errores, ESLint enfocado y build aprobaron. La matriz E13, los PNG P02, la recepción repetida/consulta UI P03 y la devolución mixta/recuperación UI P04 siguen pendientes; la aceptación permanece **PARCIAL**.

## Actualización de revisión y correcciones

Ver [revisión actual B01–B08](revision-completa-2026-10-19.md): el flujo persistido por API ya terminó con conciliación física/valorada 12/USD 160. Se verificaron aceptación concurrente limitada, aislamiento entre sucursales/empresas, ocultación de costos y costo efectivo de salida después de retaceo tardío en PostgreSQL. Se corrigieron motivos vacíos, lecturas desactualizadas bajo bloqueo y recuperación/formularios comerciales. El [manual](manual-pruebas-y-demostracion.md) incluye los códigos reales de esta demo. La aceptación visual completa sigue parcial según E01–E15; el estado vacío descrito abajo es el primer corte histórico, conservado para trazabilidad.

## Entrega inicial e historial

**Evidencia de operaciones en pantalla del corte anterior, 20/10:** se completaron incidencia → resolución → ajuste con adjunto/aprobación/aplicación; rechazo de devolución sin entrada; retaceo tardío y devolución posterior a costo efectivo; y venta con dos entregas parciales/finales. La nueva continuación agregó casos técnicos persistidos de autorización documental, ajuste correctivo, traslado parcial/final y devolución parcial/multi-asignación; su detalle vigente está en [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md). La matriz visual y de perfiles continúa parcial.

**Fecha:** 19/10/2026  
**Estado:** devoluciones implementadas y verificadas técnicamente; aceptación integrada B01–B08 **parcial**.  
**Base de demostración:** `erp_db`, Alembic `0090` (head).  
**Código revisado:** HEAD `242c709` más cambios locales de B01–B08; el árbol de trabajo conserva cambios sin commit.

## Alcance y decisiones

La devolución de cliente se vincula a las asignaciones de una entrega confirmada de B07. El flujo mantiene recepción documental separada de la aceptación de inventario; permite resolución parcial, aceptación o rechazo por línea, conserva el costo efectivo de origen y aplica la entrada mediante el motor existente. La repetición idempotente no vuelve a crear efectos y la aceptación aplicada no modifica la entrega original. La evidencia adjunta se conserva con el documento. No se implementaron reembolso, nota de crédito fiscal, cobro ni contabilidad general.

Se agregó la bandeja global **Devoluciones** en `/sales/returns`, con filtros y acceso a la devolución desde la venta. Durante el recorrido visual la bandeja muestra correctamente el estado vacío. En `erp_db` no hay ventas ni entregas; por ello no se pudo recorrer una devolución persistida desde el navegador.

## Cambios revisados

- Migración `0090_sales_returns.py`; tablas de cabecera, líneas, eventos, comandos idempotentes y documentos.
- Aplicación `backend/app/application/sales/returns.py`, esquemas, modelos, router de ventas y catálogo RBAC.
- Permisos específicos de lectura, administración, recepción, resolución y cancelación; la autorización se comprueba también en los comandos.
- API documentada en [docs/api.md](../api.md), esquema en [docs/database-schema.md](../database-schema.md) y permisos en [docs/rbac-model.md](../rbac-model.md).
- Bandeja y navegación en `frontend/src/routes/(app)/sales/returns/`, `frontend/src/lib/api/sales.ts` y `frontend/src/lib/navigation.ts`.

## Comprobaciones B08

| Criterio | Comprobación y evidencia | Resultado |
| --- | --- | --- |
| B08-A1 Recepción sin entrada; aceptación parcial crea una sola entrada | E2E FastAPI/PostgreSQL de ventas y devoluciones; [log](../../tmp/ers-v1/bloque-08/pytest-sales-deliveries.log) | **Aprobado técnicamente** |
| B08-A2 Costo original aun con promedio posterior distinto | E2E cambia el promedio después de la salida y verifica la asignación de costo original. No se probó retaceo tardío en el flujo de devolución. | **Parcial** |
| B08-A3 Límite, parcialidad, idempotencia y cuerpo distinto | E2E verifica cantidad devuelta, aceptación/rechazo parcial, reintento y conflicto de clave con cuerpo diferente. No hay evidencia de dos aceptaciones concurrentes del mismo límite. | **Parcial** |
| B08-A4 Rollback de una falla de segunda línea e inmutabilidad de la entrega | E2E fuerza el fallo tardío y verifica que no queden efectos parciales; prueba límites contra el origen. | **Aprobado técnicamente** |
| B08-A5 HU/costo/origen y cuarentena/liberación | E2E verifica vínculo de HU y valoración; la secuencia visual etiqueta/QR/Kardex/cuarentena/liberación no se recorrió con una devolución real. | **Parcial** |
| B08-A6 Empresa, sucursal, permiso y ocultamiento de costos | La E2E comprueba rechazo 403 sin permiso y que el movimiento genérico no pueda saltarse el flujo. Falta matriz completa de perfiles, empresa ajena y lector sin permiso de costo. | **Parcial** |
| B08-A7 Venta → devolución recibida → resolución → Kardex en navegador | Navegador autenticado abre `/sales/returns`, muestra `0 de 0` y acceso a Ventas; la base no contiene ventas ni devoluciones. No existe una transacción de devolución que persistir/recargar. | **Parcial; aceptación manual pendiente** |

La E2E focalizada terminó con **1 passed en 210.93 s**. La evidencia funcional está en `backend/tests/e2e/test_sales_deliveries.py` y el log enlazado. Esto verifica reglas de servidor sobre la base aislada de pruebas, no el recorrido persistido en la demo.

## Migración y conservación de datos

Se verificó Alembic `0090 (head)` en `erp_db`. Antes de migrar existe el respaldo `tmp/ers-v1/bloque-08/erp_db_b08_before_0090_20261019.dump`, SHA-256 `678092952A350BE3402E69DA07FA1475C21BBB0CB8D32C5A7E9022EE631891AD`. La migración se ensayó en `erp_db_b08_rehearsal_20261019`; la comparación posterior registra 60 filas de comparación (30 tablas por base) y **cero diferencias** en conteos y huellas MD5 entre demo y ensayo migrado. Las nuevas tablas de devoluciones tienen cero filas en ambas.

La demo conserva, entre otros, 12 productos, 1 lote y detalle de lote, 25 HUs, 65 movimientos y 6 entradas de valoración. Las tablas de clientes, ventas, entregas y devoluciones están vacías. No se limpiaron ni sembraron transacciones comerciales.

Para recuperar el esquema anterior, restaurar el respaldo en una base aislada y verificarla antes de considerar cualquier reemplazo de demo. No aplicar una restauración directamente sobre la base habitual sin decisión y validación operativa. El corte inicial aprobado no se reabrió ni editó.

## Revisión integral B01–B08

La demo, migración y evidencia técnica previa fueron comparadas con E01–E15. La suite actual de frontend terminó con **108 archivos / 483 pruebas aprobadas**; `pnpm check` terminó con **0 errores y 8 avisos CSS ya existentes** en `TransferOperationsPage.svelte`. ESLint focalizado de los archivos de la bandeja pasa. El build de producción termina; emite un aviso no bloqueante por importación sin uso de `jsbarcode` en `HandlingUnitLabelDialog.svelte` y el mensaje informativo de `adapter-auto` sobre el destino de despliegue.

Se revisó la regresión histórica de `WarehouseHandlingUnitsIntegration.test.ts:192`: el control visible vigente se llama **“Dividir unidad”**, así que el selector antiguo “Preparar fracción” no reflejaba la interfaz. El test de integración ahora afirma disponibilidad según permiso y aptitud; `HandlingUnitsPanel.test.ts` conserva cobertura de abrir/cerrar/cancelar sin mutación y de la división explícita. La suite completa pasó. La causa queda clasificada como **expectativa de etiqueta desactualizada**, no como eliminación de la capacidad.

La bandeja de Devoluciones fue abierta en navegador autenticado; la vista vacía y su acceso a Ventas son visibles. La aceptación visual completa B01–B08 y el recorrido con documentos reales de demo siguen **parciales**: no se recorrieron con transacciones las rutas de lotes/etiqueta, traslado parcial, ajuste, venta, entrega, devolución ni conciliación; tampoco la matriz completa de roles/empresas, ambos temas y móvil. Ver el detalle por criterio en [revisión integral](revision-integral-bloques-01-08.md).

## Próximo paso del usuario

Ejecutar el [manual de pruebas y demostración](manual-pruebas-y-demostracion.md) con un artículo ficticio nuevo y registrar los códigos de los documentos. El manual define los saldos esperados y las condiciones para detenerse ante una diferencia. Impresora y lector físicos no se necesitan; basta la vista de etiqueta/QR del sistema.
 
## Actualización de cierre — 20/10/2026

El estado de B08 y sus límites actuales están en [cierre visual y permisos B01–B08](cierre-visual-y-permisos-b01-b08.md). Se corrigió la duplicación visual de unidad y se diferenciaron los estados de Devoluciones; el filtro anuncia su conteo. Segunda revisión independiente de esa pantalla: 8.56/10, aprobada. Claro/oscuro comprobados en escritorio; oscuro restaurado.

La continuación final actualizó API/RBAC para documentar que descargar evidencia de ajuste requiere permiso de valoración, alcance vigente y vínculo activo; los servicios de documentos entregan URL firmadas temporales. No hubo migración. Vitest focalizado aprobó 47, Svelte-check tuvo 0 errores, ESLint enfocado y build aprobaron. El backend unitario previo con extras dev+ocr pasó 753.

La aceptación B01–B08 sigue **PARCIAL** por E13, PNG de P02, recepción repetida/consulta UI P03 y recuperación/devolución mixta desde UI P04. No se necesitan lector ni impresora físicos.

## Addendum de aceptación final — 21/10/2026

En la clon de prueba, V04-01 (ajuste correctivo), V04-02 (traslado 10 recibido en 8+2) y V04-03 (devolución mixta, 2 aceptadas/1 rechazada desde una venta con dos entregas) pasaron con lectura persistida posterior. V03 comprobó QR público, origen producto/lote y cancelar división sin crear otra HU. Los identificadores están en el [registro V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md); los balances y vínculos de movimientos, en la [conciliación final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y sus [logs de lectura](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log).

V01 sigue abierto por la matriz exhaustiva de permisos/documentos; V02 por falta de PNG archivados; V03 por recepción repetida/alias y privacidad UI; V04-04 por pérdida postcommit no ejecutada desde el navegador. La causa técnica de V04-04 y la siguiente acción están en [informe final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md). No se declara cerrada la aceptación integral. La base `erp_db` y los cuatro SKU protegidos se mantuvieron sin cambios; las pruebas persistidas nuevas quedaron en `erp_db_ers_final4p_20261020`.

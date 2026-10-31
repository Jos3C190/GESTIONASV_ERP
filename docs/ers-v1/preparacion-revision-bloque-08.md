# Preparación de la revisión integral B01–B08

## Estado vigente — 21/10/2026

La revisión se ejecutó parcialmente en la clon aislada. V04-01/02/03 aprobaron con UI + persistencia y están conciliados; V01, V02, V03 y V04-04 mantienen pendientes concretos. La demostración habitual y los cuatro SKU protegidos no se alteraron. Para el detalle vigente, consulta el [cierre B01–B08](cierre-visual-y-permisos-b01-b08.md), el [registro de cuatro puntos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md) y la [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md). No se inicia otro bloque funcional; B09 sigue integrado en B08.

**Continuación 21/10/2026:** se confirmó por segunda vez la conciliación protegida, se descubrieron los alias de recepción con datos vigentes y se documentó que no hay candidatos de movimiento con FK ausente/literal divergente según el predicado consultado. El navegador rechazó la URL de prueba por política; los recorridos UI, capturas y recuperación postcommit no avanzaron. Véase [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md). El estado permanece parcial.

El adaptador real de RustFS sí pasó una prueba de bytes ficticios con limpieza. El API de documentos no se alcanzó por login de prueba 401; por tanto, V01 permanece abierto.

## Estado vigente — 20/10/2026

Este documento empezó como una preparación anterior a B08; la tabla y el orden de trabajo de abajo son históricos y no describen el estado actual. B08 ya se implementó y la revisión integrada se ejecutó parcialmente. Consulta el [cierre B01–B08](cierre-visual-y-permisos-b01-b08.md), la [última pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md) y los [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md): P01 ya cubre documentos de ajustes con pruebas de autorización por alcance; P03 corrigió la ficha de identidad de lote; P04 añadió operaciones parciales/rollback en API/PostgreSQL. Aún están pendientes matriz E13 exhaustiva, PNG P02, recepción visual repetida/consultas UI P03 y devolución mixta/recuperación de respuesta desde UI P04. No se requieren dispositivos físicos. B09 sigue siendo checklist integrado, no un bloque adicional.

Preparado el 19/10/2026 y actualizado al cerrar B07 el mismo día. **B07 está implementado, verificado técnicamente y migrado en `erp_db` a 0089; este documento no acredita aceptación integrada.** B08 implementará devoluciones y después ejecutará la revisión completa.

Referencias: [encargo B07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-07-entregas.md), [encargo B08](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-08-devoluciones.md), [checklist integrado incorporado a B08](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-09-aceptacion.md) y [matriz E01–E15](C:/Developer/GESTIONASV_ERP/docs/ers-v1/matriz-y-seguimiento.md).

## Pendientes que deben conservarse

| Origen | Trabajo de revisión en B08 | Estado al preparar este documento |
| --- | --- | --- |
| B01–B04 | Recorridos autenticados pendientes de matriz, lotes, etiquetas y traslados; demanda por sucursal, vehículos, recepción parcial e incidencias. Recuperar el detalle de cada entrega y la matriz. | Pendiente de aceptación integrada; esta lista no sustituye sus criterios. |
| B05 | Matriz API por perfiles/empresa, soporte y reintentos; concurrencia y variante sin promedio previo; recorrido autenticado de ajustes y compensaciones. | Pendientes conservados de la matriz. |
| B06 | Cliente → cotización → conversión → venta, recarga, cambios de empresa/sucursal, permisos y errores en navegador. Revisar móvil y ambos temas. | B06-A6 parcial; pruebas técnicas no equivalen a recorrido autenticado. |
| B07 | Venta → entrega parcial → entrega final → Kardex/conciliación, costos protegidos, cancelación y reintento de respuesta perdida, sin división automática. | Implementado y verificado técnicamente en revisión 0089. Recorrido autenticado de navegador, recarga, Kardex/conciliación y respuesta de confirmación perdida aún pendientes de aceptación integrada. |
| B08 | Devolución recibida/revisada/aceptada o rechazada, cantidad apta parcial, costo original, cuarentena/liberación y límites concurrentes. | No iniciado. |
| Global | E01–E15, integración compras/retaceo/inventario/traslados/ventas/devoluciones/ajustes, aislamiento de empresa/sucursal, historial y datos previos. | Ejecutar checklist completo al final B08. |

## Evidencia B07 disponible para B08

- [Entrega B07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-07.md), [manual operativo](C:/Developer/GESTIONASV_ERP/docs/ers-v1/manual-entregas.md) y [evidencia técnica y migratoria](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-07/evidencia-2026-10-19.md) contienen los resultados y comandos. `erp_db` está en 0089. El respaldo previo es `tmp/ers-v1/bloque-07/erp_db-before-0089-20261019.dump`; hash SHA-256 `064258FBB1E5D0D68ECA6FCDC5BF495E86BF3462C48D4D1F21F55B93D9DCCA4C`. La copia restaurada de ensayo es `erp_db_b07_rehearsal_20261019`.
- API de venta/entrega: `/api/v1/sales`, `/api/v1/sales/{sale_id}/delivery-stock`, `/api/v1/sales/{sale_id}/deliveries` y `/api/v1/sales/deliveries/{delivery_id}` con operaciones de preparación, edición, confirmación y cancelación. Permisos: `sales_deliveries:read`, `:manage`, `:confirm`, `:cancel`; `SUPER_ADMIN` los recibe por 0089. El caso E2E se ejecuta como ese perfil; pruebas exhaustivas de otros perfiles y alcance para otras empresas/sucursales siguen pendientes en B08.
- La E2E usa datos ficticios aislados en `erp_db_test`: inventario inicial del artículo 13 unidades base por USD 130, promedio USD 10; una venta equivalente a 5 unidades con precio comercial USD 20 por unidad; una entrega de 3 y otra de 2 deja 8 unidades y USD 80. Se enlazan asignaciones, HUs, movimientos y entradas de valoración, y la respuesta comercial no expone costos. Dos ventas de otra sucursal compiten por la última HU de 7: solo una confirma; la cantidad/valor global pasa de 8/USD 80 a 1/USD 10. Los fixtures no dejan esos datos en la demo.
- `sales_delivery_allocations` guarda `movement_line_id`, `valuation_entry_id`, `applied_total_cost` y `applied_unit_cost` por asignación. Este snapshot y la referencia permiten a B08 volver al costo de salida original, identificar ajustes posteriores por la valoración enlazada, limitar el retorno a lo entregado y mantener devoluciones separadas del pendiente comercial. El contrato de tablas está en `docs/database-schema.md`.
- El recorrido visual autenticado de venta → parcial → final → Kardex/conciliación, cambio de empresa/sucursal, móvil/temas, recuperación de respuesta perdida y matriz completa de permisos aún no se ejecutó. No se requieren lector ni impresora físicos.
- La suite frontend completa terminó con 473 pruebas aprobadas y una falla en `tests/unit/WarehouseHandlingUnitsIntegration.test.ts:192`, que no pertenece a B07; las 3 pruebas focalizadas de `SalesDeliveryPanel` pasan. `svelte-check` reportó 0 errores y 8 avisos CSS existentes en traslados. El estado del lint global/preexistente debe revisarse al cerrar, sin atribuirlo a B07.

## Orden de cierre B08

1. Leer entregas y matriz completas; verificar entorno y migraciones antes de tocar datos.
2. Implementar devoluciones según su encargo y comprobar sus reglas técnicas.
3. Ejecutar el checklist integrado E01–E15 y los recorridos pendientes con navegador autenticado/API real, incluyendo roles, contexto, móvil y temas. Corregir defectos dentro del alcance y repetir las comprobaciones afectadas.
4. Entregar `revision-integral-bloques-01-08.md`, `manual-pruebas-y-demostracion.md` y evidencia fechada. Registrar por separado implementación, comprobación técnica y aceptación integrada; si falta evidencia, mantener el criterio pendiente.

No se requieren impresora ni lector físico. Sí se verifican generación, consulta, confirmación y reimpresión como software. DTE, cobros y contabilidad general permanecen fuera de este alcance.

## Resultado del primer corte B08 (19/10/2026, histórico)

Este documento se conserva como traspaso histórico previo al cierre. El resultado posterior está en [entrega B08](entrega-bloque-08.md) y [revisión integral](revision-integral-bloques-01-08.md): B08 quedó implementado y verificado técnicamente; la aceptación integrada B01–B08 es **parcial**. `erp_db` está en 0090 y la bandeja `/sales/returns` se abrió autenticada. La demo no contiene clientes, ventas ni entregas, así que no se pudo persistir ni recargar una devolución desde el flujo completo. No se reemplaza esta limitación con una prueba simulada.

La suite frontend actual pasa 483 pruebas; `pnpm check` tiene 0 errores y 8 avisos CSS preexistentes; la E2E B08 pasa 1 caso. El respaldo y comparación de migración están descritos en `tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md`. Los pendientes manuales, incluidos retaceo tardío, concurrencia, roles/contextos, ambos temas y móvil, siguen en el manual de demostración; no requieren un bloque B09 separado.

## Continuidad después de la revisión y correcciones

El [informe actual](revision-completa-2026-10-19.md) registra la demostración persistida del flujo completo por API, su lectura en navegador y conciliación final 12/USD 160; también la repetición de pruebas de concurrencia, aislamiento y retaceo tardío del motor. La base ya contiene cliente, venta, entrega y devolución del artículo `ERS-REVIEW-DD6BBF85`. Retomar los pendientes concretos E01–E15 del informe actual, conservando la evidencia y sin volver a crear el corte inicial ni repetir escrituras ya aplicadas. B09 continúa integrado en B08.
 
## Estado de cierre actualizado — 20/10/2026

El estado vigente está resumido al inicio y en [cierre visual y permisos B01–B08](cierre-visual-y-permisos-b01-b08.md). La continuación final agregó un E2E de autorización de documentos de ajuste, corrigió API/RBAC, probó corrección/traslado/devolución parcial con persistencia y corrigió la presentación del lote de una HU real. Véase [registro P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

El estado integrado continúa parcial por matriz E13 incompleta, PNG P02 no archivados, recepción de SKU repetido/consultas UI P03 y devolución mixta/recuperación de respuesta desde UI P04. El corte anterior completó 753 pruebas unitarias backend con extras dev+ocr; no se repitió suite completa. No hubo escrituras sobre erp_db ni sobre los cuatro SKU protegidos.

No iniciar un nuevo bloque funcional: B09 continúa integrado en el cierre B08.

## Resultado de verificación final — 21/10/2026

La ejecución final ya se realizó en `tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/`. V04-01/02/03 aprobaron con persistencia; V01/V02/V03 y V04-04 conservan pendientes concretos. B09 sigue integrado en B08; no se requiere otra implementación por bloques. La matriz y captura pendientes no se registran como aprobadas. Ver [informe final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md).

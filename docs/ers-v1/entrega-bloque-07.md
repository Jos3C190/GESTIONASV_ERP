# Entrega ERS-B07 — entregas de ventas

**Fecha:** 19/10/2026  
**Estado:** Implementado y verificado técnicamente. No equivale a aceptación integrada; el recorrido autenticado queda para B08.  
**Base habitual:** `erp_db`, Alembic `0089`. B08 no se inició.

## Alcance terminado

B07 conecta ventas confirmadas con una entrega física. Preparar una entrega asigna unidades logísticas completas y no reserva ni descuenta inventario. Confirmarla valida de nuevo la venta y su pendiente, empresa/sucursal, artículo, HU abierta, estado disponible, ubicación, lote, vencimiento y etiqueta; registra salida, valoración promedio, referencias por asignación e historial de auditoría atómicamente. Las HUs de cuarentena, tránsito, cerradas, vencidas o de otra sucursal no son seleccionables. Una venta con entrega confirmada no puede cancelarse.

Las cantidades entregadas y pendientes se calculan desde líneas confirmadas, en unidad base y precisión de seis decimales. El precio comercial permanece independiente. La salida usa el promedio vigente compartido por empresa/artículo, sin cambiarlo por almacén. El servidor guarda el costo aplicado por asignación para el retorno B08 y no incluye importes de costo en respuestas comerciales. La conversión de empaque se conserva en snapshots y la entrega parcial se realiza asignando HUs completas; no hay división automática.

No se añadieron devoluciones, facturación, cobros, impuestos, reservas ni impresión/lectura de hardware. La aceptación visual autenticada de B01–B07 se conserva pendiente para el cierre B08.

## Decisiones y contratos

- **Documento:** cabecera de entrega, líneas enlazadas a líneas de venta, asignaciones enlazadas a HU/lote/ubicación y comando idempotente. Borrador, confirmada y cancelada; versión esperada protege ediciones.
- **Salida:** movimiento `shipment` del motor de inventario y entrada `issue` del motor de promedio; no se calcula un segundo saldo. Auditoría de éxito, movimiento, valoración y entrega comparten savepoint.
- **Concurrencia:** bloquea la venta al confirmar para serializar su pendiente y sincroniza la salida con los recursos del motor de inventario. Una HU consumida entre validación y bloqueo se presenta como conflicto recargable `409`, no como recurso inexistente `404`.
- **Idempotencia:** creación y confirmación usan claves por empresa/acción y huella de contenido. Igual contenido recupera el documento; contenido diferente devuelve conflicto.
- **Costo para B08:** cada asignación conserva `movement_line_id`, `valuation_entry_id`, `applied_total_cost` y `applied_unit_cost`. El enlace a la valoración permite revisar modificaciones posteriores al promedio, mientras el snapshot conserva el importe original de esa salida. El retorno no debe superar la cantidad entregada menos devoluciones aceptadas y no debe reabrir el pendiente comercial.
- **Permisos:** `sales_deliveries:read`, `sales_deliveries:manage`, `sales_deliveries:confirm`, `sales_deliveries:cancel`; 0089 los asigna al rol de sistema `SUPER_ADMIN`. Otros roles requieren asignación explícita. El API no expone importes de costo ni requiere `inventory:valuation` para la entrega.

Rutas bajo `/api/v1`:

| Método | Ruta | Permiso |
| --- | --- | --- |
| GET | `/sales/{sale_id}/delivery-stock` | `sales_deliveries:manage` |
| GET / POST | `/sales/{sale_id}/deliveries` | `read` / `manage` |
| GET / PUT | `/sales/deliveries/{delivery_id}` | `read` / `manage` |
| POST | `/sales/deliveries/{delivery_id}/confirm` | `sales_deliveries:confirm` |
| POST | `/sales/deliveries/{delivery_id}/cancel` | `sales_deliveries:cancel` |

Archivos centrales: `backend/app/application/sales/deliveries.py`, `backend/app/application/sales/service.py`, `backend/app/api/v1/routers/sales.py`, `backend/app/infrastructure/models/sales_delivery.py`, `backend/alembic/versions/0089_sales_deliveries.py`, `frontend/src/lib/features/sales/components/SalesDeliveryPanel.svelte`, `frontend/src/lib/features/sales/components/SaleDetail.svelte` y sus tipos/API. Los contratos completos están en [API](C:/Developer/GESTIONASV_ERP/docs/api.md), [esquema](C:/Developer/GESTIONASV_ERP/docs/database-schema.md) y [RBAC](C:/Developer/GESTIONASV_ERP/docs/rbac-model.md).

La cadena que comprueba la E2E, por asignación, es `sales.id → sales_lines.id → sales_deliveries.id → sales_delivery_lines.id → sales_delivery_allocations.id → inventory_handling_units.id / inventory_lot_details.id (si tiene lote) → inventory_movements.id → inventory_movement_lines.id → inventory_valuation_entries.id`. Los IDs se generan en cada ejecución aislada; la prueba verifica los enlaces y el total por HU. La asignación guarda la cantidad base y snapshot de empaque/lote, sin duplicar movimientos ni crear registros históricos para otras ventas.

## Migración y conservación de datos

La migración `0089` agrega una FK compuesta para la identidad de línea de venta, cuatro tablas (`sales_deliveries`, `sales_delivery_lines`, `sales_delivery_allocations`, `sales_delivery_commands`), restricciones/índices/triggers de inmutabilidad y los cuatro permisos. No crea entregas históricas ni modifica existencias anteriores.

Antes de actualizar se creó y verificó `tmp/ers-v1/bloque-07/erp_db-before-0089-20261019.dump` (994000 bytes; SHA-256 `064258FBB1E5D0D68ECA6FCDC5BF495E86BF3462C48D4D1F21F55B93D9DCCA4C`) y se restauró a `erp_db_b07_rehearsal_20261019`. La copia aplicó 0089. Antes y después se compararon filas ordenadas convertidas a JSON y su MD5 para 22 tablas de empresa, sucursales/bodegas/ubicaciones, inventario, traslados y ventas. Las 22 huellas y cantidades coincidieron entre la copia anterior y `erp_db` posterior.

Conteos de la base habitual tras aplicar 0089: empresas 1, sucursales 8, bodegas 9, ubicaciones 23, artículos inventariables 12, lotes 1, detalles de lote 1, HUs 25, saldos 27, movimientos 65, líneas de movimiento 71, promedios 6 y entradas de valoración 6. Ventas y líneas comerciales previas: 0. Las cuatro tablas B07 quedaron vacías (0 documentos, líneas, asignaciones y comandos) y se verificaron cuatro permisos con cuatro concesiones al `SUPER_ADMIN` de sistema. La copia restaurada y la demo permanecen coherentes.

El respaldo se puede volver a restaurar en una base separada para recuperación o inspección; no se hizo downgrade destructivo. El ensayo de restauración sí se completó sobre la base separada indicada. No se ejecutaron fixtures ni semillas de prueba sobre `erp_db`.

## Comprobaciones de aceptación B07

| Criterio | Resultado | Evidencia/alcance |
| --- | --- | --- |
| B07-A1 parcial y final | Aprobado técnicamente | E2E PostgreSQL entrega 3 y después 2 unidades base de una venta de 5; cantidades entregadas/pendientes y valor del inventario se consultan después de cada estado. |
| B07-A2 sucursal, cuarentena y saldo | Parcial | E2E excluye stock de otra sucursal y cuarentena, y valida conflictos por una HU consumida. Falta un caso independiente para tránsito, HU cerrada, ubicación incompatible y falta de saldo; llevar esos recorridos al checklist B08. |
| B07-A3 promedio vs precio | Aprobado técnicamente | La venta usa USD 20 por unidad y la salida USD 10 promedio; 5 unidades rebajan USD 50, no USD 100. Se valida el antes/después con `Decimal`. |
| B07-A4 reintentos, competencia y rollback | Aprobado técnicamente | E2E cubre claves repetidas/conflictivas, confirmaciones concurrentes, error de negocio en la segunda línea, excepción inesperada en segunda línea, auditoría tardía y reintento posterior sin efectos parciales. |
| B07-A5 trazabilidad y permisos | Parcial | Se verifican venta/línea → entrega/asignación → movimiento/línea → valoración/HU y ausencia de importes privados en DTOs. E2E usa `SUPER_ADMIN`; falta matriz exhaustiva de otros perfiles, otras empresas/sucursales y permisos en replay. |
| B07-A6 panel y operación | Parcial | Tres pruebas Vitest cubren abrir/cerrar sin mutación, crear borrador sin confirmar y confirmar con clave estable/refresco. Tipos, lint y build pasan. Navegador autenticado, cambio de contexto, respuesta perdida y Kardex/conciliación visual quedan para B08. No se requieren hardware ni pruebas físicas. |
| B07-A7 cancelación/entrega | Parcial | E2E compite confirmación contra cancelación de venta y cancela el borrador perdedor sin movimiento. No ejecuta un caso separado que intente preparar una venta ya cancelada ni mutar una entrega confirmada; agregar esos casos al cierre B08. |
| B07-A8 snapshots y última HU | Aprobado técnicamente | Dos líneas del mismo artículo y una conversión de empaque congelada sobreviven un cambio posterior. Dos ventas de sucursales compiten por una HU de 7; solo una confirma, el saldo queda 1/USD 10 y un vínculo conserva USD 70 de costo original. |
| B07-A9 migración | Aprobado técnicamente | Respaldo verificable, restauración de ensayo, comparación de 22 huellas de datos, actualización real a 0089 y verificación de tablas nuevas vacías. Sin backfill de ventas. |

## Pruebas ejecutadas

- `pytest -q tests/e2e/test_sales_deliveries.py --tb=line`: **1 passed** (187.65 s) en `erp_db_test`. Incluye la regresión que convierte a 409 la carrera de consumo de la última HU.
- `pytest -q tests/e2e/test_sales_base.py --tb=line`: **1 passed** (187.62 s), regresión de B06.
- `pnpm exec vitest run src/lib/features/sales/components/SalesDeliveryPanel.test.ts --reporter=dot`: **3 passed**.
- Suite frontend completa: **473 passed, 1 failed** (`tests/unit/WarehouseHandlingUnitsIntegration.test.ts:192`, no encuentra el botón “Preparar fracción”). Está fuera de B07; no se diagnosticó su causa ni se corrigió dentro de este bloque y se registra para revisar en B08.
- `pnpm check`: 0 errores y 8 avisos CSS preexistentes en `TransferOperationsPage.svelte`.
- `pnpm exec eslint src/lib/features/sales`: pasa. `pnpm build`: pasa; conserva avisos de `jsbarcode` y de `adapter-auto` ya presentes.
- `ruff check app/application/sales/deliveries.py app/application/sales/service.py app/api/v1/routers/sales.py tests/e2e/test_sales_deliveries.py`: pasa.

Comandos, resultados de base y hash del respaldo: [evidencia B07](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-07/evidencia-2026-10-19.md). El log de la suite frontend completa está en `tmp/ers-v1/bloque-07/vitest-full.log`.

## Instrucciones y trabajo que continúa

Consulta el [manual de entregas](C:/Developer/GESTIONASV_ERP/docs/ers-v1/manual-entregas.md) para el flujo desde una venta confirmada. La [preparación B08](C:/Developer/GESTIONASV_ERP/docs/ers-v1/preparacion-revision-bloque-08.md) mantiene explícitamente los pendientes de B01–B06 y añade rutas, roles, datos y casos B07.

Pendiente: los criterios parciales A2/A5/A6/A7, aceptación visual autenticada y recorridos integrados de B01–B07, completar B08 (devoluciones) y ejecutar después el checklist E01–E15. No iniciar la aceptación integral antes de terminar B08 ni declarar aceptado todo el ERP con esta entrega.

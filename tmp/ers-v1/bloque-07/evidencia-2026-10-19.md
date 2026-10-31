# Evidencia técnica ERS-B07 — 19/10/2026

## Entorno y aislamiento

- Docker Compose local en ejecución: `gestionasv_erp-backend-1`, `gestionasv_erp-db-1`, `gestionasv_erp-frontend-1`.
- PostgreSQL habitual dentro de Docker: host `db`, puerto interno `5432`, base `erp_db`. Integración/E2E usa exclusivamente la fixture `erp_db_test`; no se ejecutó ninguna fixture/seed sobre la base habitual.
- Base de ensayo de migración: `erp_db_b07_rehearsal_20261019`, restaurada desde el backup y actualizada de 0088 a 0089. La UI del navegador no se usó para aceptación autenticada en este bloque.

## Respaldo y migración

- Respaldo anterior a 0089: `erp_db-before-0089-20261019.dump`, 994000 bytes.
- SHA-256: `064258FBB1E5D0D68ECA6FCDC5BF495E86BF3462C48D4D1F21F55B93D9DCCA4C`. La lista del dump fue verificada y el respaldo se restauró en la base de ensayo.
- Cabeza previa habitual: `0088`. Cabeza de la copia restaurada tras el ensayo: `0089`. Se identificó el destino de Alembic sin imprimir la URL ni credenciales: host `db`, base `erp_db`.
- Comando aplicado a la base habitual: `docker exec gestionasv_erp-backend-1 alembic upgrade head`. Resultado: `Running upgrade 0088 -> 0089`.
- Verificación posterior: `erp_db` está en `0089`; `sales_deliveries`, `sales_delivery_lines`, `sales_delivery_allocations` y `sales_delivery_commands` tienen 0 filas; existen 4 permisos `sales_deliveries:*` y 4 concesiones para el `SUPER_ADMIN` de sistema.
- No se hizo downgrade. Restauración ensayada en base separada; no se borraron documentos ni se sobrescribieron datos de demostración.

### Comparación de datos

Antes de actualizar la habitual, se compararon 22 tablas entre la copia restaurada/migrada y `erp_db` después de 0089. El comando consultó por tabla cantidad de filas y `md5(string_agg(to_jsonb(row)::text, chr(10) ORDER BY to_jsonb(row)::text))`. Coincidieron todas las cantidades y huellas:

`companies` 1; `branches` 8; `warehouses` 9; `locations` 23; `inventory_items` 12; `inventory_lots` 1; `inventory_lot_details` 1; `inventory_packaging_definitions` 6; `inventory_handling_units` 25; `inventory_balances` 27; `inventory_movements` 65; `inventory_movement_lines` 71; `inventory_cost_averages` 6; `inventory_valuation_entries` 6; `inventory_valuation_settings` 1; `inventory_transfer_details` 0; `inventory_transfers` 0; `sales_customers` 0; `sales_quotations` 0; `sales_quotation_lines` 0; `sales` 0; `sales_lines` 0.

El snapshot anterior a migración mostraba en `erp_db`: 65 movimientos, 71 líneas de movimiento, 25 HUs, 27 saldos, 6 promedios y 6 entradas de valoración. La revisión 0089 no generó entregas históricas.

| Tabla | Filas | MD5 antes = después |
| --- | ---: | --- |
| `companies` | 1 | `e60631c4711367014ee572534be9823b` |
| `branches` | 8 | `f37d80b7e85d2bef5ff4e1db5de44061` |
| `warehouses` | 9 | `3c155b759d68938cb6b9c15f4c8e5e54` |
| `locations` | 23 | `a44d612713969d8639590d5277f856eb` |
| `inventory_items` | 12 | `650d1853d6c2c1966e9e6ff31d3fa836` |
| `inventory_lots` | 1 | `618bea20e991f86878df38c43029a10f` |
| `inventory_lot_details` | 1 | `497925ae585d01e935b207b5a5b319da` |
| `inventory_packaging_definitions` | 6 | `d5f3f1c0da4b2cdab9ecd480400ef892` |
| `inventory_handling_units` | 25 | `735c5303ad16df3fa77453dfe4cca631` |
| `inventory_balances` | 27 | `4089e7f72c71f334d53460c8063d212d` |
| `inventory_movements` | 65 | `6ea1f4ae6e70e7224405c406bb5e958d` |
| `inventory_movement_lines` | 71 | `fcc304d6f8883c6983695991c5085629` |
| `inventory_cost_averages` | 6 | `618a129491630498274b55d9694c2cc6` |
| `inventory_valuation_entries` | 6 | `4294e867a0c628a3c1d7da4f85c5fb3e` |
| `inventory_valuation_settings` | 1 | `37a9b3ab3a7d772ca620a7a469871a12` |
| `inventory_transfer_details` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `inventory_transfers` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `sales_customers` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `sales_quotations` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `sales_quotation_lines` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `sales` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `sales_lines` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |

## Pruebas de backend

| Comando | Resultado |
| --- | --- |
| `docker exec gestionasv_erp-backend-1 pytest -q tests/e2e/test_sales_deliveries.py --tb=line` | 1 passed, 187.65 s; corre sobre la base de pruebas aislada. |
| `docker exec gestionasv_erp-backend-1 pytest -q tests/e2e/test_sales_base.py --tb=line` | 1 passed, 187.62 s; regresión B06. |
| `docker exec gestionasv_erp-backend-1 ruff check app/application/sales/deliveries.py app/application/sales/service.py app/api/v1/routers/sales.py tests/e2e/test_sales_deliveries.py` | All checks passed. |

La E2E B07 emplea costo inicial promedio USD 10 para 13 unidades base. La venta ficticia equivale a 5 unidades (3 en unidad base y 1 empaque congelado a factor 2), a precio comercial USD 20/unidad. Las entregas de 3 y 2 dejan 8 unidades base y valor USD 80; el valor descargado es USD 50, conservando promedio USD 10. Dos ventas ficticias de una segunda sucursal compiten por su última HU de 7 unidades: solo una confirma, el estado global queda en 1 unidad/USD 10 y su asignación conserva USD 70 de costo aplicado. Las pruebas comprueban `Decimal`, IDs de movimiento/línea/valoración, idempotencia, rollback por error de negocio, excepción inesperada y auditoría tardía, cancelación concurrente, doble confirmación y serialización por la última HU.

La carrera de la última HU identificó el hallazgo `ERS-B07-R01`: después de validar la HU, otra confirmación podía consumirla y el motor devolvía 404 `handling_unit_not_available`; para el operador era una selección obsoleta, no un recurso inexistente. El servicio B07 lo convierte ahora a `409 sales_delivery_unit_unavailable`, indicando recargar y preparar de nuevo. La E2E repetida tras la corrección pasó.

## Pruebas de frontend

| Comando | Resultado |
| --- | --- |
| `docker exec gestionasv_erp-frontend-1 pnpm exec vitest run src/lib/features/sales/components/SalesDeliveryPanel.test.ts --reporter=dot` | 1 archivo, 3 pruebas aprobadas. |
| `docker exec gestionasv_erp-frontend-1 pnpm exec vitest run --reporter=dot` | 106 archivos: 105 aprobados y 1 con falla; 473 pruebas aprobadas y 1 fallida. El fallo único es `tests/unit/WarehouseHandlingUnitsIntegration.test.ts:192`, que espera el botón `Preparar fracción`. Está fuera de los archivos de B07; no se diagnosticó ni corrigió su causa en este bloque. Salida íntegra: `vitest-full.log`. |
| `docker exec gestionasv_erp-frontend-1 pnpm check` | 0 errores; 8 avisos CSS `@apply` preexistentes en `src/lib/features/inventory/components/TransferOperationsPage.svelte`. |
| `docker exec gestionasv_erp-frontend-1 pnpm exec eslint src/lib/features/sales` | Pasa sin reportes. |
| `docker exec gestionasv_erp-frontend-1 pnpm build` | Pasa. Conserva avisos de import `jsbarcode` y de `adapter-auto` sin plataforma de despliegue configurada. |

## Alcance que no se ejecutó

- No se realizó recorrido autenticado manual de B07 en el navegador: detalle venta → borrador → confirmación parcial/final → Kardex/conciliación, recarga o recuperación de respuesta perdida.
- La E2E utiliza `SUPER_ADMIN`; no completa una matriz de lectura, preparación, confirmación y cancelación para perfiles distintos, otras empresas o todos los alcances de sucursal/replay.
- No se probó en un caso separado el rechazo de una entrega para una venta ya cancelada ni las mutaciones de una entrega confirmada; agregarlas a la revisión B08.
- A2 no tiene casos separados para toda condición no elegible (tránsito, HU cerrada, ubicación incompatible y saldo insuficiente). A5 y A6 se consideran parciales hasta la aceptación integrada.
- No se probaron impresora ni lector físicos; no son necesarios para la demostración.
- B08, devoluciones y la revisión completa E01–E15 no se iniciaron.

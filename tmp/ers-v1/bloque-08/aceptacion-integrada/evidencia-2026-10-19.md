# Evidencia de cierre B08 e integración B01–B08

Fecha de corte: 19/10/2026. Captura del estado visible en esta fecha; no implica que el recorrido manual esté aceptado.

## Código y servicios

- Rama local: `codex/block-2-stabilization-2026-09-30`; HEAD `242c709`. El árbol compartido contiene cambios locales de los bloques, por lo que el identificador HEAD no representa por sí solo todos los archivos descritos.
- `backend`, `frontend` y `db` reportaron estado healthy al verificar; frontend en `http://localhost:5173`. El contenedor `tempo` reportaba unhealthy, ajeno al flujo B08.
- `docker compose exec -T backend alembic current` → `0090 (head)`.

## Migración, respaldo y datos

- Respaldo anterior a 0090: [`erp_db_b08_before_0090_20261019.dump`](../erp_db_b08_before_0090_20261019.dump), SHA-256 `678092952A350BE3402E69DA07FA1475C21BBB0CB8D32C5A7E9022EE631891AD`.
- La revisión 0090 se ensayó en `erp_db_b08_rehearsal_20261019` y después se aplicó a `erp_db`.
- [`erp_db-vs-rehearsal-after-demo-0090.csv`](../erp_db-vs-rehearsal-after-demo-0090.csv) contiene 60 renglones de comparación (30 tablas por base). Conteos y MD5 coinciden entre demo y ensayo migrado; las cinco tablas nuevas de devoluciones están vacías en ambas.
- La demo conserva 12 artículos, un lote/detalle de lote, 25 HUs, 65 movimientos y 6 entradas de valoración. `sales_customers`, `sales_quotations`, `sales`, `sales_deliveries` y `sales_returns` tienen cero filas tanto en demo como ensayo.
- No se ejecutó seed destructivo ni se cambió el saldo del corte aprobado.

## Comprobaciones automatizadas y estáticas

| Comprobación | Evidencia y resultado |
| --- | --- |
| E2E backend B08 | [`pytest-sales-deliveries.log`](../pytest-sales-deliveries.log): `1 passed in 210.93s`. Valida costo de origen tras cambiar el promedio, aceptación/rechazo parcial, límite, idempotencia/conflicto, rollback tardío, enlace HU/valoración y 403 sin permiso. No cubre retaceo tardío ni dos aceptaciones concurrentes del mismo límite. |
| Suite frontend completa | `docker compose exec -T frontend pnpm exec vitest run --reporter=dot` → [log](../frontend-vitest-2026-10-19.log), 108 archivos aprobados / **483 pruebas aprobadas** en 35.16 s. |
| `pnpm check` | **0 errores**, 8 avisos CSS `@apply` existentes en `TransferOperationsPage.svelte`, líneas 1322–1329. |
| ESLint focalizado | Sin errores en la ruta Devoluciones, su prueba, cliente `salesApi` y navegación. |
| Build frontend | Completado. Aviso no bloqueante de importación `jsbarcode` sin uso en `HandlingUnitLabelDialog.svelte`; mensaje informativo de `adapter-auto` al no detectar destino de despliegue. |
| Regresión de almacén | La prueba previa esperaba “Preparar fracción”; la acción actual se llama “Dividir unidad”. La integración prueba el nombre/permisos vigentes y `HandlingUnitsPanel.test.ts` cubre abrir/cerrar/cancelar sin mutación y división explícita. La suite completa pasó. |

El intento de repetir Vitest desde el host se detuvo antes de ejecutar pruebas porque pnpm pidió reinstalar dependencias sin TTY; no modificó `node_modules`. La ejecución en el contenedor frontend evitó la reinstalación y pasó. Los 483 tests no sustituyen aceptación visual integrada.

## Recorrido autenticado en navegador

- Con sesión autenticada se abrió `http://localhost:5173/sales/returns` en una pestaña temporal. La página mostró filtros, el estado vacío real “Todavía no hay devoluciones” y acceso a Ventas.
- Al abrir Ventas, el contador mostró 0. La comparación de base confirma que no hay clientes, cotizaciones, ventas ni entregas; por tanto, no se pudo continuar a una devolución persistida.
- El recorrido visual cubrió la ruta y el estado vacío de la bandeja. No se crearon operaciones persistentes solo para producir una captura.
- No se requiere probar lector/impresora físicos; la demostración usa vista previa y registro de etiqueta por software.

## Límites de aceptación

1. Falta el caso persistido de navegador compra → recepción/retaceo → lote/etiqueta → traslado parcial → venta → entrega → devolución → ajuste y conciliación.
2. Faltan la prueba de retaceo aplicado después de vender parte del lote y el reparto del ajuste entre saldo remanente y costo de venta.
3. Faltan dos aceptaciones concurrentes de devolución, matriz completa de perfiles, cruce de empresa ajena, lector sin permiso de costos y reintento con cambio de contexto en navegador.
4. Faltan pruebas visuales integradas de ambos temas y móvil en pantallas pendientes de B01–B08.

El estado final se registra como **aceptación integrada parcial**. El manual define saldos y pasos reproducibles para una demo con transacciones ficticias.

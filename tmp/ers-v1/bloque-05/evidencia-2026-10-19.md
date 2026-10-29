# Evidencia técnica ERS-B05 — 19/10/2026

Esta evidencia recoge las comprobaciones focalizadas de ajustes y la migración 0087. La aceptación autenticada y la revisión integrada se reservan para B08. Los tests de PostgreSQL se ejecutaron en serie y usan `erp_db_test`, de acuerdo con `backend/tests/conftest.py`; no reconstruyen la demo `erp_db`.

## Repositorio y herramientas

| Comprobación | Resultado |
| --- | --- |
| `docker compose exec -T backend pytest tests/unit/test_inventory_adjustments.py -q --tb=short` | 4 passed (9.35 s). |
| `docker compose exec -T backend pytest tests/integration/test_inventory_adjustment_repository.py -q --tb=short` | 4 passed (18.48 s), PostgreSQL. Incluye soporte, aprobación, idempotencia, saldo insuficiente, rollback tardío, promedio, corrección y pérdida en tránsito. |
| Vitest directo con el Node local: `vitest.mjs run tests/unit/InventoryAdjustmentsApi.test.ts tests/unit/InventoryKardexContext.test.ts src/lib/features/inventory/kardex.test.ts` | 3 archivos, 9 tests aprobados (24.41 s). |
| ESLint directo de los archivos del cliente, editor Svelte, lista/detalle, Kardex y traslados B05 | Aprobado, salida 0. |
| `svelte-check` | 0 errores; 8 avisos CSS `@apply` en `TransferOperationsPage.svelte`, fuera del editor/listado de ajustes. |
| Ruff focalizado sobre router/modelo/caso de uso/repositorio y tests B05 | `All checks passed!` |
| `docker compose exec -T backend python -m compileall -q app` | Aprobado, salida 0. |
| Build Vite directo con Node local: `node frontend/node_modules/vite/bin/vite.js build` | Aprobado, salida 0; compiló 493 módulos SSR y 744 módulos cliente. Avisó que `jsbarcode` se importa sin uso en `HandlingUnitLabelDialog.svelte` y que `adapter-auto` no detecta destino productivo configurado. |

Se evitó ejecutar `pnpm exec` para Vitest/ESLint porque pnpm intentó reconciliar `node_modules` y abortó al no haber terminal interactiva. Las herramientas locales existentes se invocaron con el runtime de Node ya instalado; no se reinstalaron ni eliminaron dependencias.

## Escenarios PostgreSQL cubiertos

- No aprobar sin evidencia; aceptar soporte activo; impedir por trigger que el estado del archivo enlazado cambie después de aprobar.
- Aplicar una entrada con costo documentado y otra sin costo que usa el promedio vigente; verificar cantidad y valor global.
- Rechazar disminución mayor que el saldo de la HU; un reintento de aplicación con la misma clave conserva un solo efecto.
- Forzar fallo tardío y confirmar rollback del ajuste, movimiento, valoración y HU: queda aprobado sin aplicación parcial.
- Corregir por compensación un ajuste ordinario negativo completo de una línea: el documento y movimiento originales no cambian, y el saldo/valor retornan al importe justificable.
- Pérdida de traslado: 10 despachadas, 8 recibidas y 2 ajustadas; `quantity_received=8`, tránsito cero, pérdida dos, estado `closed_with_adjustment` y valor reducido. No se informa falsamente una recepción de diez.

La primera ejecución de integración detectó que al ingresar un aumento el adaptador omitía `length_m`, `width_m` y `height_m` al construir las medidas opcionales de HU. Se pasaron explícitamente como `None`; las cuatro pruebas de integración finales pasaron. La prueba de corrección se ajustó para ubicar la nueva HU positiva en cuarentena, porque el motor no debe reutilizar la HU negativa original.

## Migración de demo y conservación

- Cabeza de Alembic previa: **0086**. Cabeza tras la actualización: **0087 (head)**.
- Respaldo previo: `C:\Users\rodri\AppData\Local\Temp\GESTIONASV_erp_db_pre_0087_20261019.dump`, 916,929 bytes. `pg_restore --list` pudo leer 1,187 entradas del catálogo.
- Ensayo de recuperación: se restauró ese dump en la base temporal nueva `b05_recovery_20261019`, se confirmó cabeza 0086, y se aplicó allí la migración 0087. Se retiraron la base temporal y la copia del dump dentro del contenedor después de validar los conteos; el archivo original del host se conservó.
- Conteos observados después de la migración de `erp_db`: `inventory_lot_details=1`, `inventory_handling_units=25`, `inventory_movements=65`, `inventory_cost_averages=6`, `inventory_transfers=0`, `inventory_transfer_details=0`, `inventory_adjustments=0`, suma de `quantity_adjusted_out=0`.
- La misma verificación en la restauración temporal tras 0087 dio `inventory_lot_details=1`, `inventory_handling_units=25`, `inventory_movements=65`, `inventory_cost_averages=6`, `inventory_transfers=0`, `inventory_transfer_details=0`, `inventory_adjustments=0`; las sumas de `quantity_adjusted_out` en detalles y asignaciones fueron cero. Las tres restricciones ampliadas de cantidades/estado quedaron creadas.
- Los conteos de lotes, HUs, movimientos y promedios se preservaron; los dos conteos de traslado eran cero antes y siguen cero. La columna nueva inicia en cero y no se reescribieron movimientos ni promedios.
- El respaldo permanece disponible para recuperar en una base separada; la restauración y la actualización se comprobaron sin modificar `erp_db`.

## Revisión de los criterios y pendientes

| Criterio | Evidencia | Estado de esta revisión |
| --- | --- | --- |
| A1 | Pruebas de soporte obligatorio, soporte activo y protección posterior a aprobar. | Técnica parcial; faltan carga/descarga API real y matriz de ámbito/perfiles. |
| A2 | Entrada documentada, fallback al promedio vigente y salida por promedio. | Técnica parcial; falta el caso sin promedio previo ni costo y la conciliación comercial B06–B08. |
| A3 | Exceso de saldo rechazado e idempotencia de replay. | Técnica parcial; falta concurrencia de aplicación, recepción simultánea y dos operadores. |
| A4 | Fallo tardío revierte los efectos físicos y valorizados. | Focal aprobado; falta inyección sistemática por efecto y auditoría API completa. |
| A5 | Corrección total negativa ordinaria preserva el original y restaura el valor justificable. | Focal aprobado; falta matriz de concurrencia y rechazos por API. |
| A6 | 10/8/2, cierre con ajuste y valor/cantidades correctos. | Integración PostgreSQL aprobada; aceptación de pantalla pendiente. |
| A7 | Protección del endpoint genérico, alcance y redacción de costo inspeccionados; Ruff aprobado. | Parcial; falta matriz API con roles, otras empresas/sucursales, soporte y replay. |
| A8 | Migración 0087 y conteos históricos; Vitest, ESLint, Svelte-check y build. | Parcial; falta recorrido autenticado, móvil, temas y regresión completa B01–B08. |

No se afirma una aceptación manual ni se inicia B06. La revisión integrada de B01–B08 se mantiene para el final de B08.

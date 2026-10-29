# Cierre de pasada — pendientes B01–B08

**Fecha:** 20/10/2026, America/El_Salvador. Esta pasada continúa el cierre integrado B08; no inicia B09 ni otro bloque funcional.

## Entorno protegido

- Frontend 5173, API 8000 y PostgreSQL reportan estado healthy; `alembic current` en backend reporta `0090 (head)`.
- La demo que usa la API es `erp_db`. Las E2E corren en serie con la guarda de `backend/tests/conftest.py`, exclusivamente contra `erp_db_test`.
- `erp_db` solo se consultó en transacciones `READ ONLY`; no se aplicaron migraciones, escrituras ni semillas. Los SKU guardados siguen conciliados: `ERS-INC-EE8FE228` 4/4 USD40; `ERS-LATE-B1B55D6D` 5/5 USD60; `ERS-REVIEW-DD6BBF85` 12/12 USD160; `ERS-UI-F767BABC` 0/0 USD0.
- No se limpió, reseteó ni restauró el árbol de trabajo compartido. El navegador se devolvió a `/sales/returns`, tema oscuro, 1280×720.

## Pruebas nuevas o repetidas en esta pasada

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Backend `tests/unit` con extras `dev,ocr` bloqueados por el lock del proyecto | 753 aprobadas, 35.18 s; `pikepdf` estaba presente en el entorno efímero de prueba. | `backend-unit-dev-ocr-final.log` |
| Regresiones backend de unidad/migración | 3 aprobadas en 11.20 s. | `backend-unit-regressions.log` |
| Regresión E2E de migración 0082→0083 | 1 aprobada, 26.18 s, en `erp_db_test`. | `e2e-migration-regression.log` |
| Regresión E2E de ventas base | 1 aprobada, 204.07 s, en `erp_db_test`. | `e2e-sales-base-regression.log` |
| `TransferDemandQuantity.test.ts` | 2 aprobadas. | salida de Vitest de esta pasada; detalle en `mobile-ui-run.md` |
| `pnpm check` | 0 errores; 8 avisos CSS existentes `@apply`. | salida de `pnpm check` de esta pasada |
| ESLint focalizado en componentes de Traslados y regresión | Exit code 0. | salida focalizada de esta pasada |
| Build frontend producción | Exit code 0 en 1m16s. Avisos no bloqueantes: jsbarcode sin uso en HandlingUnitLabelDialog y adapter-auto sin entorno productivo configurado. | salida de `pnpm build` de esta pasada |
| Inspección de interfaz móvil | Sin desbordamiento exterior en las rutas y medidas descritas; incidencias corregidas de Traslados confirmadas. | [recorrido visual](mobile-ui-run.md) |
| P01 documentos de ajustes | 1 E2E PostgreSQL; redacción, 403/404/200, sucursal/empresa, retiro y revocación verificados. | [comando/log reproducible](p01-adjustment-document-permission-rerun.log), [casos P01–P04](p01-p04-casos-y-evidencia.md) |
| P04 corrección de ajuste | 1 prueba de integración PostgreSQL; original conservado y corrección enlazada; rollback/idempotencia comprobados. | [comando/log](p04-adjustment-transfer-focused-rerun.log) |
| P04 traslado parcial/final | 1 prueba de integración PostgreSQL y un caso E2E del receptor de sucursal; preparar/cancelar sin movimiento, 10/8/2, replay y validaciones de exceso/ubicación. | [comando/log integración](p04-adjustment-transfer-focused-rerun.log), [autorización destino](p04-transfer-partial-final-api.log) |
| P04 devoluciones parciales y multi-asignación | 1 E2E PostgreSQL; costos, rechazo sin stock, aceptación controlada, rollback al fallar segunda línea y replay idempotente. | [comando/log](p04-sales-delivery-returns-focused-rerun.log) |
| P03 HU/lote UI y frontend enfocado | HU real consultada sin escritura; seis archivos/47 Vitest, Svelte-check 0 errores, ESLint P03 y build aprobados. | [casos P01–P04](p01-p04-casos-y-evidencia.md), [lectura UI](p03-trace-lot-ui-readonly.md), logs enlazados allí |

Las dos E2E son repeticiones de regresión de casos ya incluidos en la selección previa; no aumentan el número de casos E2E únicos comunicado anteriormente (33). Las pruebas full unit sí añaden evidencia de ejecución integral: el antiguo impedimento de recolección por `pikepdf` queda resuelto en el entorno `dev+ocr` adecuado; no se modificó la dependencia global ni el contenedor habitual para lograrlo.

## Qué sigue parcial — corte final P01–P04

1. **P01/E13 — parcial:** la prueba documental de ajustes cubre acceso directo, vínculo, costos redactados, sucursal/empresa, retiro y revalidación. No completa la matriz de todos los módulos. Siguiente acción: inventariar routers/acciones restantes y añadir pruebas solo a celdas de alto riesgo que hoy no tienen aserción. La descarga utiliza URL temporal simulada; bytes/almacenamiento/expiración no se probaron.
2. **P02 — pendiente:** no hay PNG archivados. La sesión CUA solo permitió inspección in situ y no ofrece exportación local a la carpeta. Siguiente acción: usar sesión de navegador con captura exportable y guardar ruta/tema/tamaño/perfil/estado para las siete familias; una vista observada no sustituye ese artefacto.
3. **P03 — parcial:** la ficha `HU-8D63FE508BF14124` ya muestra el producto y separa código de recepción cabecera/detalle; la lectura fue de solo consulta. Falta una recepción visual con varias líneas del mismo SKU y consulta por UI de cada código para el que exista dato aplicable. Siguiente acción: preparar caso nuevo aislado y repetir lectura tras recarga sin volver a recibir.
4. **P04 — parcial:** API/PostgreSQL verifica corrección de ajuste, tránsito parcial/final, devolución parcial/multi-asignación e idempotencia/rollback. Falta operación desde UI de devolución mixta/varias HUs y pérdida de respuesta para ajuste y venta/devolución. Siguiente acción: preparar documentos y SKU nuevos en entorno aislado, descartar la respuesta después de persistir, consultar y reintentar con la misma clave; comprobar un efecto tras recargar.
5. La matriz finita por acción/perfil/empresa/sucursal no se infiere de superadmin ni de una suite. Los casos aprobados y límites están en [matriz de permisos](../matriz-permisos.md) y [registro P01–P04](p01-p04-casos-y-evidencia.md).

El lector HS200 y una impresora física siguen excluidos por el usuario. Ninguno de los pendientes anteriores depende de hardware real.

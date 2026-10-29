# Evidencia — cierre visual y permisos B01–B08

## Actualización vigente — 21/10/2026

El corte anterior fechado 20/10 se conserva como histórico. Para la verificación final de cuatro puntos, usa el [informe](../2026-10-21/verificacion-cuatro-puntos/informe-final.md), el [registro de casos](../2026-10-21/verificacion-cuatro-puntos/registro-casos.md), la [matriz de permisos](../2026-10-21/verificacion-cuatro-puntos/matriz-permisos.md) y la [conciliación de solo lectura](../2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log). V04-01/02/03 aprobaron con UI + persistencia; V01/V02/V03 y V04-04 siguen abiertos con impedimentos documentados. La demostración habitual y los cuatro SKU protegidos no se alteraron.

**Fecha local:** 20/10/2026. No se incluyen credenciales, tokens ni enlaces firmados.

## Continuación final P01–P04 — 20/10/2026

Esta es la evidencia vigente para el cierre al 20/10; el P06 con comandos/nodos está en [comandos y resultados](comandos-y-resultados.md) y la cobertura por caso en [P01–P04](pasada-final/p01-p04-casos-y-evidencia.md).

- P01: el test de documento de ajuste pasó (1); cubre costo redactado, 403/404/200 por permiso y alcance, retiro y revocación. Comando/salida: [log P01](pasada-final/p01-adjustment-document-permission-rerun.log).
- P04: integración de ajuste compensatorio y traslado parcial/final pasaron (2); E2E de venta/entrega/devolución parcial pasó (1). Comandos/salidas: [ajuste/traslado](pasada-final/p04-adjustment-transfer-focused-rerun.log), [venta/devolución](pasada-final/p04-sales-delivery-returns-focused-rerun.log).
- P03: corrección comprobada en ficha HU autenticada y de solo lectura; separa lote de fabricante, detalle canónico y cabecera. No se pudo archivar PNG desde CUA.
- La aceptación permanece **PARCIAL** por matriz E13 incompleta, P02 PNG sin exportación, recepción visual con líneas repetidas/consultas de alias en UI y devolución mixta/recuperación de respuesta desde UI P04.
- Los cuatro SKU protegidos permanecen como en [snapshot final](pasada-final/protected-skus-after-continuation.log). Las pruebas de integración/E2E nuevas usaron erp_db_test, no la demo. No se requieren dispositivos físicos.

## Corte previo de continuación — 20/10/2026

Este corte previo describe la suite/recorrido móvil anteriores a la continuación P01–P04. El [registro de pasada](pasada-final/cierre-de-pasada.md) y el [recorrido visual](pasada-final/mobile-ui-run.md) conservan su alcance original.

- Suite unitaria backend con extras `dev+ocr`: **753 aprobadas**, 35.18 s; salida íntegra en `pasada-final/backend-unit-dev-ocr-final.log`. `pikepdf` se instaló en el entorno efímero bloqueado por el lock para esta ejecución; no se alteró la imagen habitual del servicio.
- E2E repetidas de migración y ventas base: **1 + 1 aprobadas**, en `erp_db_test`. Son regresiones repetidas de la selección existente, no dos casos nuevos.
- Regresión Vitest de Traslados: **2 aprobadas**. `pnpm check`: 0 errores y 8 avisos CSS conocidos. ESLint focalizado y build de producción aprobados; detalles exactos en `pasada-final/cierre-de-pasada.md`.
- `/transfers`, `/sales/returns`, una bodega y `/inventory/kardex` observados a 390×844. No se detectó desbordamiento exterior; detalles y límites por pantalla en `pasada-final/mobile-ui-run.md`.
- El crítico había rechazado la versión móvil previa de Traslados por pestañas envueltas, densidad y blancos táctiles. Tras la corrección y reinicio exclusivo del frontend para invalidar caché de Vite, se observan pestañas en una fila, acciones de 44 px y solicitudes con sucursal/código SCR visibles.
- La API de navegador disponible no ofrece operación documentada para guardar PNG en el repositorio. Por tanto el requisito de archivo de capturas de P02 sigue abierto; las capturas de la sesión no se presentan como archivos guardados.
- Los cuatro SKU preservados fueron consultados en solo lectura y concilian: `ERS-INC-EE8FE228` 4/4 USD40; `ERS-LATE-B1B55D6D` 5/5 USD60; `ERS-REVIEW-DD6BBF85` 12/12 USD160; `ERS-UI-F767BABC` 0/0 USD0. No hubo escrituras ni migraciones sobre `erp_db`.
- La lista finita de códigos del Kardex/label, con pruebas y pendientes por tipo, está en [alias-trazabilidad.md](pasada-final/alias-trazabilidad.md).

## Entorno

- Frontend 5173 y API 8000 healthy.
- La API usa erp_db; Alembic reporta 0090 (head).
- backend/tests/conftest.py valida que la suite E2E opere únicamente sobre erp_db_test y reconstruye su esquema por prueba.
- Inspección autenticada de /sales/returns con datos persistidos; ninguna escritura en erp_db.
- Se verificó temporalmente el tema claro y luego se restauró el oscuro.

## Resultado visual — corte inicial, histórico

Vista /sales/returns a 1280×720, tema claro y oscuro: Aceptada en verde, Rechazada en rojo, el texto aparece como «Unidad (u)» una sola vez y el contador de resultados cambia al filtrar. Se observó el foco visible en el campo de búsqueda. La pantalla muestra tres documentos ficticios ya existentes.

La segunda revisión independiente aprobó esta pantalla con 8.56/10. No es revisión móvil ni certificación del resto de GestionaSV. No se guardó una captura nueva en este directorio; las capturas previas de otros recorridos están bajo tmp/ers-v1/revision-2026-10-19/.

## Pruebas — corte inicial, histórico

- Frontend Vitest: 116 archivos / 513 aprobadas.
- svelte-check: 0 errores / 8 avisos CSS conocidos en TransferOperationsPage.svelte.
- ESLint focalizado: aprobado; [registro](eslint-focused.log).
- Build producción: aprobado en 1m 13s; avisos no bloqueantes de jsbarcode y adapter-auto.
- Backend focalizado de ventas: 25 aprobadas.
- E2E anteriores: 11 + 12 aprobadas en los grupos descritos en el informe de cierre.
- E2E adicionales de permisos: 10 aprobadas en 96.23s. Registro completo en e13-permission-tests.log.
- suite tests/unit completa: bloqueada en recolección por pikepdf ausente para prueba OCR.
- git diff --check: sin errores; avisos de conversión CRLF/LF de archivos compartidos.
- [Comandos y resultados detallados](comandos-y-resultados.md).

## Conciliación de solo lectura

| SKU | Físico | Valorado | Valor USD | Promedio USD |
| --- | ---: | ---: | ---: | ---: |
| ERS-INC-EE8FE228 | 4 | 4 | 40 | 10 |
| ERS-LATE-B1B55D6D | 5 | 5 | 60 | 12 |
| ERS-REVIEW-DD6BBF85 | 12 | 12 | 160 | 13.333333 |
| ERS-UI-F767BABC | 0 | 0 | 0 | 0 |

Los cuatro saldos coinciden con el manual. No se ejecutaron escrituras ni migraciones en erp_db.

## Pendiente remanente — corte vigente

E13 sigue parcial: falta la matriz exhaustiva por acción/rol/empresa/sucursal y documentos directos. Devoluciones ya se revisó a 390×844, pero faltan sus operaciones, perfiles y diálogo completos. P02 todavía no tiene PNG archivados de todos los recorridos. También faltan recepción visual con varias líneas repetidas, consulta desde UI de los códigos aplicables y casos P04 de devolución mixta, múltiples HUs/asignaciones y recuperación ante respuesta perdida. Ver [informe](../../../../docs/ers-v1/cierre-visual-y-permisos-b01-b08.md), [matriz muestreada](matriz-permisos.md) y [alias-trazabilidad](pasada-final/alias-trazabilidad.md).

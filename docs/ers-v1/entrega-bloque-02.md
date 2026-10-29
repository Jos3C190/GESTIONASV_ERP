# Entrega ERS-B02 — Identidad de lote por detalle, etiqueta y Kardex

**Fecha:** 18/10/2026  
**Estado:** **Parcial con impedimento documentado.** Implementación y migración 0085 aplicadas; pruebas automatizadas aprobadas. Falta recorrido visual autenticado y aceptación manual en la demo.  
**Dependencia:** B01, migraciones 0084–0085.

## 1. Alcance entregado

Cada producto aceptado en una recepción conserva una identidad canónica propia
en `inventory_lot_details`. La cabecera `inventory_lots` sigue agrupando la
recepción. Una línea distinta o una recepción parcial tiene un detalle/código
distinto, aunque sea el mismo producto. El código de cabecera anterior continúa
como alias de búsqueda; el lote del fabricante se mantiene separado.

La identidad se muestra en consulta de lotes, preview de etiqueta, trazabilidad
y Kardex. Los movimientos nuevos guardan la FK directa al detalle. Los
movimientos históricos append-only no se editan: se resuelven por la relación
exacta con su HU cuando existe evidencia suficiente. Si no hay origen confiable,
el movimiento permanece como legado no atribuible.

No se creó un segundo saldo editable. Las existencias físicas siguen usando
HUs, ubicaciones, movimientos y la valoración actuales. La migración no cambia
costos ni genera impresiones o confirmaciones. El lector HS200 y la impresión
física están excluidos por el alcance autorizado; se validan la etiqueta y su
registro por software. B02 usa los permisos existentes; no cambia el catálogo
RBAC ni amplía el acceso a costos.

## 2. Migración, respaldo y datos

La revisión de la demo al iniciar B02 era `erp_db / 0084`. Se creó el respaldo
externo a Docker
`backups/ers_b02_erp_db_pre_0085_20261018.dump` (877,534 bytes, SHA-256
`42357323E3FD7BCAE43CF7A5F88534E705F11FFA85C2DA503B6576A61210B7AF`). El hash
calculado fuera y dentro del contenedor coincidió. Se restauró el respaldo a
`erp_ers_b02_rehearsal_20261018`, se migró esa copia a 0085 y se compararon los
fingerprints de las tablas de negocio con `erp_db`. La copia temporal se elimina
al cerrar esta entrega; el respaldo se conserva.

La migración `0085_receipt_detail_lot_identity.py` crea el código estable
`<código-cabecera>-D<UUID-del-detalle-sin-guiones-en-mayúsculas>`, una unicidad
por empresa, y el FK opcional del movimiento al detalle. PostgreSQL valida
unicidad y empresa. El backfill se limita a `inventory_lot_details`; no hace
`UPDATE` sobre `inventory_movement_lines`, cuya inmutabilidad está protegida
por trigger.

| Dato | Antes de 0085 / restauración | Después de 0085 en demo y ensayo |
| --- | ---: | ---: |
| Revisión Alembic | 0084 | 0085 |
| Detalles de recepción | 1; cantidad aceptada 9 | 1; misma cantidad, 1 con código único |
| Líneas de movimiento | 71 | 71; ninguna línea histórica editada |
| Historial resoluble por HU exacta | 18 | 18 |
| Historial legado no atribuible | 53 | 53; queda explícitamente sin lote inventado |
| Impresiones existentes | 8 | 8 |
| Promedios / valor | 6 / USD 47.50 | 6 / USD 47.50 |
| Entradas de valoración / valor fuente | 6 / USD 47.50 | 6 / USD 47.50 |
| Saldos físicos | 27 | 27 |
| Aplicaciones de retaceo en la demo | 0 | 0 |

La prueba aislada de R03 incorpora registros sintéticos no vacíos de valoración y
retaceo para comprobar su conservación; no representa datos encontrados en la
demo. La suma de cantidades en unidades base de distintos productos no se usa
como una unidad física común.

## 3. Aceptación B02

| Criterio | Comprobación y resultado | Estado |
| --- | --- | --- |
| B02-A1 | E2E de dos recepciones parciales del mismo producto: dos cabeceras/detalles distintos, cantidad y `purchase_detail_id` originales, códigos canónicos únicos y estables. También pasa la regresión de dos detalles de compra del mismo producto. | Aprobado en automatización |
| B02-A2 | E2E busca el código canónico en Kardex y en etiqueta; regresión de cabecera anterior resuelve todos sus detalles asociados. Los filtros de lote/producto/fecha permanecen combinables. | Aprobado en automatización |
| B02-A3 | Pruebas de colocación agrupada, ubicación, división, traslado y conciliación conservan el origen y cantidades. | Aprobado en automatización |
| B02-A4 | Ensayo restaurado y prueba 0084→0085 comparan datos; movimiento histórico, trigger, HUs, cantidades, impresiones y valoración permanecen. No se generan impresiones/confirmaciones por migración. | Aprobado en automatización y base de ensayo |
| B02-A5 | Preview/API de etiqueta conserva producto, código interno para barras, detalle de recepción, fecha y lote de fabricante. | Aprobado por software; vista manual pendiente |
| B02-A6 | Pruebas de aislamiento de empresa y valoración activa; el preview real no detecta código duplicado y los valores/fingerprints de empresa permanecen iguales. | Aprobado en automatización y preflight |
| B02-A7 | Pruebas de idempotencia, fallo, concurrencia y rollback de movimientos/divisiones; la migración de PostgreSQL es transaccional. | Aprobado en automatización |
| B02-A8 | Pruebas de componentes, API de revisión/confirmación de etiqueta y división impiden efectos repetidos; no se exige redividir. | Aprobado en automatización; recorrido visual pendiente |

## 4. Validaciones ejecutadas

- Cierre R02/R03 B01: **7 pruebas aprobadas** en 50.69 s.
- Unidad e integración de inventario/aislamiento/valoración: **82 aprobadas** en 22.72 s.
- E2E de integración B01/B02 y cierre de almacén: **17 aprobadas** en 169.23 s; una advertencia deprecada de Starlette sobre el nombre de estado HTTP 422, sin fallos.
- Pruebas nuevas de migración y recepciones parciales: **2 aprobadas** en 31.59 s.
- Vitest focalizado de interfaz: **44 pruebas aprobadas en 4 archivos**. `npm run check`: **0 errores y 0 advertencias**.
- Ruff de backend afectado: **All checks passed**. `git diff --check`: código de salida 0; Git mostró avisos de conversión CRLF/LF ya observados en pruebas de compras.
- `alembic current` en la demo: **0085 (head)**. Los preflight B01/B02 son de solo lectura y reportan `validation_errors: []`.

La evidencia de comandos, respaldos, preflight, fingerprints, chequeos posteriores
y resultados está en [`tmp/ers-v1/bloque-02/evidencia-2026-10-18.md`](../../tmp/ers-v1/bloque-02/evidencia-2026-10-18.md).

## 5. Límites y siguiente paso

No se hizo recorrido visual autenticado desde esta sesión. Por eso el bloque no
se marca aceptado aunque la migración y pruebas automatizadas estén completas.
Pendiente: recorrer en el navegador real una recepción con dos productos,
consultar etiqueta/código nuevo y código de cabecera en Kardex, revisar el
detalle de una HU y confirmar que abrir/cerrar no divide stock. El usuario puede
hacer estas comprobaciones manuales sobre `erp_db / 0085`.

Los 53 movimientos sin HU/detalle exacto siguen visibles como historia legacy
no atribuible y requieren revisión del negocio si se necesita asociarlos. No
fueron asignados automáticamente a un lote. No se inicia B03 con esta entrega.

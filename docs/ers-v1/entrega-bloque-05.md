# Entrega ERS-B05 — Ajustes autorizados

Fecha: 19/10/2026  
Estado: **Implementado; comprobaciones técnicas focalizadas aprobadas.** La aceptación autenticada, la matriz completa de perfiles y la revisión integrada de B01–B08 quedan pendientes para B08, según la decisión del usuario. B06 no se inicia con este cierre.

## 1. Alcance y resultado

Se implementó el ciclo de ajustes de inventario sobre el motor de movimientos y valoración existente: borrador, soporte documental, aprobación versionada, aplicación explícita, cancelación previa y consulta desde Kardex. Se añadieron los faltantes justificados de traslados y correcciones compensatorias acotadas. La migración 0087 se aplicó a la demo desde 0086.

El ajuste no crea compras ni recepciones ficticias. Los aumentos ingresan en cuarentena, sujetos a revisión de la HU y su etiqueta. Los descensos usan el promedio vigente y no pueden dejar saldo negativo. La pérdida en tránsito se separa de lo recibido y puede cerrar el traslado como **Cerrado con ajuste**. La apertura, edición, aprobación, cancelación o consulta de un borrador no registra movimientos.

## 2. Reglas y límites implementados

- El documento y cada línea pertenecen a una empresa; el código del ajuste es único por empresa. Se registran bodega, fechas operativa/contable, motivo, referencia, notas, líneas, actores y eventos.
- Cada línea usa el artículo y unidad base que devuelve el servidor, una cantidad positiva de hasta seis decimales, dirección, ubicación y estado físico. No se infieren conversiones desde el nombre del producto.
- El aumento admite costo unitario o costo total documentado; si no se proporciona costo, aplica el promedio vigente. Si no existe promedio, el motor exige un costo documentado. El descenso consume al promedio vigente y exige una HU y saldo válidos.
- Aprobar requiere motivo, referencia y evidencia cargada, completa, activa y de la misma empresa. La aprobación queda vinculada a la versión actual. Aplicar vuelve a validar versión, evidencia, alcance y existencias.
- La clave de idempotencia evita que un reintento de creación/aplicación duplique el resultado. La escritura de documento, movimientos, HUs, cantidades, promedio y resolución de incidencia usa una unidad transaccional protegida contra errores tardíos.
- El endpoint genérico de movimientos rechaza `adjustment_in` y `adjustment_out` sin el flujo autorizado.
- La corrección automática se limita a la cantidad completa de un ajuste ordinario negativo de una línea, cuando se puede justificar el valor original y no hay operaciones físicas o valorizadas posteriores que hagan ambigua su compensación. El original y su movimiento no se editan. Una corrección es otro borrador con soporte, aprobación y aplicación propios.
- No se implementa corrección monetaria aislada, corrección parcial/multilínea ni reversión automática de pérdida de tránsito después de operaciones posteriores. El motor devuelve un error explícito para esos casos.

## 3. Contratos, permisos y archivos

Rutas bajo `/api/v1/inventory/adjustments`: opciones/listado, crear/leer/actualizar borrador, iniciar y completar carga documental, descargar con URL temporal autorizada, aprobar, cancelar, aplicar y solicitar corrección. Los detalles de entradas/salidas están en [API](../api.md#ers-b05-authorized-inventory-adjustments-revision-0087).

La puerta del módulo exige `inventory:read`; escritura valida además `inventory:adjust` o `inventory:adjust_approve` según la acción y el alcance de empresa/bodega. `inventory:valuation` sigue separado: sin ese permiso, el servidor oculta los costos. El mismo usuario puede crear, aprobar y aplicar si tiene ambos permisos; no se impone separación de funciones. Los ajustes de tránsito comprueban además traslado, incidencia, línea, HU y acceso logístico al origen o destino. La bodega técnica de tránsito no queda disponible para ajustes libres. Véase [RBAC](../rbac-model.md#10-inventory-adjustment-authorization-ers-b05--revision-0087).

Componentes principales del cambio:

- Backend: `inventory_adjustments.py`, `inventory_adjustment.py`, `use_cases.py`, `inventory_adjustment_repository.py`, esquema y puertos del ajuste; protección del movimiento genérico en `inventory.py`.
- Base de datos: migración `backend/alembic/versions/0087_inventory_adjustments.py`, con cabeceras, líneas, soporte, eventos, cantidades de salida ajustadas y el estado terminal de traslado.
- Interfaz: rutas de lista, creación y detalle de ajustes; cliente tipado `frontend/src/lib/features/inventory/adjustments.ts`; filtro de origen en Kardex; enlace desde incidencia de traslado.
- Pruebas: `backend/tests/unit/test_inventory_adjustments.py`, `backend/tests/integration/test_inventory_adjustment_repository.py` y pruebas Vitest del cliente y contexto Kardex.
- Documentación: API, esquema, RBAC, guía maestra, decisiones de arquitectura, matriz de seguimiento y [manual de traslados](manual-traslados.md).

El mapa de entrada física queda así: aplicación de ajuste autorizada → `InventoryUseCases` y repositorio de inventario existentes → movimiento y valoración existentes. La creación genérica de movimiento no sirve como vía alterna. Las pérdidas de traslado pasan por el mismo documento autorizado y la incidencia abierta; `close_received` no convierte la pérdida en recepción.

## 4. Migración y recuperación

La cabeza observada antes del cambio era **0086**; después, **0087 (head)**. La migración añade tablas/documentación de ajustes, eventos y soporte; agrega `quantity_adjusted_out` con valor inicial cero a detalles y asignaciones de traslado, amplía sus restricciones de cantidades y permite `closed_with_adjustment`. No reescribe movimientos ni promedios históricos.

Antes de migrar se guardó `C:\Users\rodri\AppData\Local\Temp\GESTIONASV_erp_db_pre_0087_20261019.dump` (916,929 bytes). La lista del archivo fue legible con `pg_restore --list` (1,187 entradas). El ensayo técnico y las pruebas de integración se ejecutaron contra la base aislada `erp_db_test`; los fixtures reconstruyen esa base y no la demo.

La comprobación de conservación en `erp_db` registró después de 0087: 1 detalle de lote, 25 unidades logísticas, 65 movimientos, 6 promedios, 0 traslados y 0 detalles de traslado. Los campos nuevos quedaron en cero y las tablas de ajustes no tenían documentos al migrar. Estos conteos corresponden a la demo; la suite de integración usó `erp_db_test`.

Recuperación: el dump se restauró en la base temporal `b05_recovery_20261019`; confirmó cabeza 0086 y los conteos previos. Se aplicó 0087 en esa copia y los conteos quedaron idénticos, con los campos nuevos en cero. La base temporal y la copia del dump dentro del contenedor se retiraron al terminar; se conservó intacto el respaldo del host. Si hay que recuperar, restaurar el dump primero en una base separada y comparar las cantidades de referencia; no ejecutar semillas destructivas ni restaurar encima de una demo con actividad posterior sin respaldar esa actividad.

## 5. Criterios B05-A1–A8 y resultado

| Criterio | Comprobación realizada | Resultado y pendiente |
| --- | --- | --- |
| A1 — Soporte y aprobación | Integración PostgreSQL comprueba que sin evidencia no se aprueba, que el soporte activo permite aprobar, y que un trigger impide cambiar su estado después de aprobar. | **Parcial aprobado técnicamente.** No se ejecutó matriz API completa de archivos, carga real, descarga y perfiles/empresa; queda para B08. |
| A2 — Aplicación y valoración | Integración cubre aumento documentado, aumento sin costo documentado con promedio vigente, descenso al promedio mediante pérdida y conciliación de cantidad/valor. Unitarias cubren reglas del documento. | **Parcial aprobado técnicamente.** Falta el caso sin promedio previo ni costo documentado y la conciliación integrada de ventas/devoluciones B06–B08. |
| A3 — Saldo e idempotencia | PostgreSQL rechaza consumir más saldo que el de la HU y acepta el replay de la misma aplicación sin repetir movimiento. | **Parcial aprobado técnicamente.** No se ejecutaron pruebas concurrentes de operadores, cambios de versión o recepción simultánea. |
| A4 — Atomicidad | Una falla tardía deja el ajuste aprobado, sin movimiento ni cambio de valor/saldo, y sin HUs parciales. | **Aprobado en el escenario focalizado.** Matriz de fallo por cada efecto y auditoría completa pendiente de B08. |
| A5 — Corrección trazable | PostgreSQL crea y aplica una corrección total de un ajuste ordinario negativo; el original y su movimiento permanecen intactos y cantidad/valor vuelven al valor justificable. | **Parcial aprobado técnicamente.** Variantes concurrentes y todos los rechazos de modalidad no soportada no se probaron por API. |
| A6 — Pérdida en traslado | Escenario 10 despachadas, 8 recibidas y 2 perdidas: quedan 8 recibidas, 0 en tránsito y 2 ajustadas; cierra `closed_with_adjustment`, el valor baja y no se reportan 10 recibidas. | **Aprobado en integración PostgreSQL.** La recepción/incidencia se probó en el repositorio, no como recorrido autenticado de navegador. |
| A7 — Permisos y ámbito | Ruff y pruebas focalizadas/código confirman que el movimiento genérico rechaza ajustes públicos y las rutas validan permisos y alcance empresa/bodega; los costos se redactan sin `inventory:valuation`. | **Parcial aprobado técnicamente.** Matriz API por roles, otra sucursal/empresa, soporte y replay autorizado queda para B08. |
| A8 — Migración e interfaz | Migración a 0087 preserva los conteos históricos; Vitest, ESLint, `svelte-check` y compilación de producción pasan. | **Parcial aprobado técnicamente.** No se hizo aceptación autenticada, móvil o por temas. El build no se considera aceptación visual. |

## 6. Comprobaciones y resultado reproducible

En la evidencia fechada [evidencia técnica B05](../../tmp/ers-v1/bloque-05/evidencia-2026-10-19.md) se guardan comandos, resultados y límites. Resumen:

- Pruebas unitarias de ajustes: **4/4**.
- Pruebas de integración PostgreSQL de ajustes: **4/4**.
- Vitest focalizado de ajustes/Kardex: **9/9 en 3 archivos**.
- Ruff: aprobado; `compileall`: aprobado; ESLint focalizado: aprobado.
- `svelte-check`: 0 errores y 8 avisos CSS `@apply` ya existentes en `TransferOperationsPage.svelte`.
- Build Vite de producción: aprobado; avisos existentes de importación `jsbarcode` sin uso y `adapter-auto` sin destino de despliegue configurado.
- Alembic en demo: `0087 (head)`; conteos de referencia conservados.

Una primera integración encontró que la creación de una HU de aumento no enviaba las medidas opcionales nulas que espera el motor físico. Se corrigió el adaptador del ajuste y se repitió la suite: los cuatro casos pasaron. También se corrigió la expectativa de una prueba de corrección; una entrada positiva crea una nueva HU en cuarentena, no reutiliza el identificador de la unidad original.

## 7. Uso y pendiente para B08

Ruta de operación: **Inventario → Ajustes**. Crear el borrador, seleccionar bodega/artículo/unidad/ubicación, especificar dirección y cantidad base, registrar fecha, motivo y referencia, completar un soporte autorizado, aprobar la versión mostrada y luego pulsar **Aplicar** explícitamente. Consultar el documento o el movimiento por referencia en Kardex. Un aumento genera una HU en cuarentena y requiere revisión física de medidas/etiqueta antes de liberarla. Una pérdida se inicia desde la incidencia de traslado.

El detalle de manejo está en [manual de ajustes](manual-ajustes.md). Para B08 queda el recorrido manual autenticado de borrador → soporte → aprobación → aplicación → Kardex y HU, el escenario de faltante y corrección, pruebas de perfiles/otra empresa, concurrencia, casos sin promedio previo, interfaz móvil/temas y regresión completa B01–B08. No se inició el bloque 6.

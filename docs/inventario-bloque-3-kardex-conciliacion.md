# Inventario, bloque 3: Kardex y conciliación

Fecha: 14/10/2026.

## Estado

> **Revisión posterior del 14/10/2026:** el Kardex y las protecciones están construidos, pero el cumplimiento de R1/R3 es parcial. Se reprodujeron la falta de acción para medir fracciones, desgloses financieros omitidos y una respuesta obsoleta al cambiar fechas. También falta completar las pruebas integradas y separar las consultas del router. Las afirmaciones de cierre de código más abajo describen la entrega anterior y quedan acotadas por la [revisión del bloque 3](C:/Developer/GESTIONASV_ERP/docs/revision-inventario-bloque-3-y-alcance-bloque-4.md). El [encargo del bloque 4](C:/Developer/GESTIONASV_ERP/docs/prompt-luna-inventario-bloque-4.md) define su corrección y aceptación.

El código de R1–R3 del bloque 2, el Kardex físico y valorado, la conciliación y las pruebas unitarias están implementados. La suite backend disponible y la suite frontend pasan. La interfaz recibió aprobación del crítico de UX/UI con promedio de 8.75/10; las tres listas tienen tarjetas para anchos menores a `xl`, controles semánticos de pestañas y navegación por flechas/Home/End. **El bloque todavía no tiene aceptación operativa completa**: Docker no tiene daemon activo, no hay PostgreSQL local disponible, el recorrido autenticado de navegador no pudo ejecutarse y no se probó hardware. No se aplicaron migraciones ni se usaron datos operativos.

No se agregó una migración para este bloque. La cabeza local de Alembic continúa en `0083`; esta revisión integra consultas sobre el modelo actual y conserva `/inventory/valuation` como pantalla de apertura y saldos.

## Recorrido y permisos

La nueva página está en **Inventario → Kardex**, ruta `/inventory/kardex`.

1. **Movimientos físicos por bodega.** El usuario busca un producto en una bodega autorizada y filtra por fechas, tipo y lote. La tabla muestra fecha de El Salvador, evento, referencia, lote/HU, recorrido, entradas, salidas y saldo del artículo en esa bodega. Los traslados muestran el efecto correspondiente de cada extremo; los cambios internos de ubicación/estado se identifican con efecto neto cero.
2. **Detalle del movimiento.** Desde una fila se abre un diálogo con cantidad base, referencia persistida, ubicaciones/estados visibles y vínculo a la ficha de unidad logística cuando el servidor la devuelve dentro del alcance. Si faltan datos históricos o el alcance no permite verlos, se muestra la limitación sin inventar un enlace.
3. **Conciliación de empresa.** Para usuarios con `inventory:valuation` y acceso global a la empresa, se comparan cantidades de balances físicos con cantidades del costo promedio, diferencia, valor y promedio por producto. Si no se ha aprobado apertura de valoración, los valores se conservan como no disponibles y se indica que no hay valoración activa.
4. **Kardex valorado.** Desde conciliación se abre el historial de costo promedio por producto y período contable, mostrando también fecha operativa, cantidad, cambio de valor, saldo y promedio registrados. Los desgloses de retaceo se consultan sin reescribir movimientos originales.

| Vista | Permiso y alcance |
| --- | --- |
| Búsqueda y movimientos físicos | `inventory:read`; el servidor valida empresa y acceso a la bodega/sucursal en cada consulta. No incluye costos globales. |
| Conciliación y Kardex valorado | `inventory:valuation` y alcance de todas las sucursales de la empresa, igual que la valoración actual. El costo promedio se comparte entre bodegas de la empresa. |
| Apertura/configuración de valoración | Enlace a la pantalla existente `/inventory/valuation`; no se duplicó su lógica en el Kardex. |

## Contratos y decisiones

- Router: `backend/app/api/v1/routers/inventory_kardex.py`, registrado en el router API existente.
- `GET /api/v1/inventory/kardex/items`: catálogo acotado a movimientos o existencia de la bodega seleccionada.
- `GET /api/v1/inventory/kardex/physical`: movimiento físico por artículo, bodega, período, tipo/lote opcionales y página limitada.
- `GET /api/v1/inventory/kardex/reconciliation`: conciliación paginada de la empresa, solo con autorización global de valoración.
- `GET /api/v1/inventory/kardex/valuation`: historial de valoración de un artículo y período, usando el ledger existente y su secuencia persistida.
- DTOs: `backend/app/api/v1/schemas/inventory_kardex.py`; cliente y tipos: `frontend/src/lib/features/inventory/kardex.ts`.
- Interfaz: `frontend/src/routes/(app)/inventory/kardex/+page.svelte`; el detalle y las listas de movimientos físicos, conciliación y valoración están separados en `KardexMovementDetails.svelte`, `PhysicalKardexList.svelte`, `KardexReconciliationList.svelte` y `ValuedKardexList.svelte`.

El Kardex físico usa `inventory_movements` y `inventory_movement_lines`, con saldos físicos, lote, HU, bodegas y ubicaciones. Los límites de fecha son inclusivos en `America/El_Salvador`; para la consulta SQL el límite final se convierte al inicio del día siguiente. Ordena por fecha y desempate persistido y pagina sin reiniciar el saldo. Los totales y saldos no dependen solo de la página visible. Sin un corte aprobado ni historial suficiente, el saldo se devuelve desconocido en lugar de cero.

El saldo inicial físico se toma del `physical_snapshot` del corte aprobado en `inventory_valuation_settings`; los movimientos posteriores ajustan la reconstrucción. El recorrido de cada fila es una proyección de un solo ámbito de bodega. Un traslado entre bodegas afecta cada historial de forma independiente y no duplica el total de la empresa.

La vista financiera reutiliza `SqlAlchemyInventoryValuationRepository.ledger` y los promedios/capas ya existentes. No calcula costos en TypeScript ni recorta el promedio por lote o bodega. Los ajustes de retaceo aparecen como entradas financieras separadas del evento físico; los ajustes de valor no fabrican una entrada o salida de cantidad. Los saldos previos a la apertura permanecen no disponibles.

Las cuatro consultas de lectura mantienen el bloqueo transaccional de valoración por empresa mientras observan balances, snapshot y ledger. De esta manera no se lee el saldo de un lado de una recepción concurrente y el historial del otro. La conciliación suma `inventory_balances` una vez por producto y no vuelve a sumar las unidades logísticas.

Las respuestas físicas no incluyen costo. Las filas de origen/destino se filtran por el alcance del usuario; si una HU está ahora en otra sucursal, el servidor elimina su identificador y código del DTO. La respuesta distingue un extremo externo real de uno omitido por privacidad; la UI no presenta una bodega oculta como si fuera un extremo externo. Si el saldo de una fila no se puede reconstruir, la interfaz lo dice explícitamente en vez de mostrar un guion. La UI solo crea el enlace a HU con un identificador autorizado. La ficha QR pública no se amplió.

La búsqueda de productos separa error y ausencia de resultados, permite repetir la búsqueda fallida con el mismo término y evita que una respuesta atrasada reemplace el resultado de otra bodega o filtro. En móvil, tarjetas muestran cantidades, saldo, origen/destino y acciones; las tablas quedan para pantallas anchas. Las vistas usan `tablist`/`tab`/`tabpanel`, selección ARIA, foco itinerante y teclas de flecha, `Home` y `End`.

## Cierre de R1–R3 del bloque 2

- **R1, fraccionamiento y etiqueta:** el movimiento genérico exige cuarentena para una división cuando hay etiqueta sujeta a confirmación. La hija no hereda confirmación; el cambio de cantidad/revisión invalida la impresión anterior del remanente. La prueba de confirmación de etiqueta verifica impresión ausente/ajena y revisión/cantidad obsoletas tras fraccionar.
- **R2, replay del grupo:** antes de devolver el grupo idempotente se valida la empresa y el alcance de las bodegas del movimiento persistido. Esa autorización se mantiene separada de la precondición física de una operación nueva; el replay no vuelve a escribir movimiento ni auditoría.
- **R3, ubicar antes de liberar:** una unidad completa puede ir a una ubicación permaneciendo en cuarentena si todavía le falta etiqueta o retaceo exigible. El helper compartido decide el estado; el panel informa qué falta y ofrece el recorrido existente. Ubicar no confirma etiquetas ni aplica costos.

Los controles transaccionales del repositorio, los bloqueos y los permisos efectivos necesitan confirmación en PostgreSQL. Las pruebas unitarias no validan interbloqueos ni rollback real.

## Validación ejecutada

| Comando / revisión | Resultado actual | Duración / límite |
| --- | --- | --- |
| `python -m pytest tests/unit -q --ignore=tests/unit/test_ocr_worker.py` con Python 3.12.15 en WSL | **692 aprobadas**, 6 advertencias preexistentes por longitud de la clave JWT de pruebas | 32.56 s. Se omitió únicamente `test_ocr_worker.py`: no está instalado `pikepdf`. |
| `node node_modules/vitest/vitest.mjs run` desde `frontend` | **417 pruebas aprobadas en 98 archivos** | 24.39 s. |
| `node node_modules/svelte-check/bin/svelte-check --tsconfig ./tsconfig.json` | 0 errores, 0 advertencias | Resultado final tras el refactor de las listas y navegación por teclado. |
| ESLint sobre la página Kardex, componentes, pruebas y navegación modificados | Aprobado, sin salida de diagnóstico | Se ejecutó con `node_modules/eslint`. |
| `node node_modules/vite/bin/vite.js build` | Build de producción aprobado | 34.60 s. Vite reportó una importación `jsbarcode` sin uso detectado en el bundle SSR; el build terminó correctamente. Adapter-auto tampoco detectó un destino de producción configurado. |
| `alembic heads` | `0083 (head)` | Consulta local, sin base. |
| `alembic upgrade 0078:0083 --sql` | Generación SQL de `0079`–`0083` aprobada | Generación offline del tramo afectado; no demuestra aplicación ni compatibilidad real con una base. |
| `python -m compileall -q` sobre router, schemas y repositorios tocados | Aprobado | Validación de sintaxis Python, no de consultas PostgreSQL. |
| `alembic upgrade head --sql` | **No completó** | La migración histórica `0014_official_sv_geography.py` requiere un resultado de base de datos y falla en modo offline; no es un fallo del bloque 3. |
| `docker compose ps` y comprobación local de PostgreSQL | No disponible | Docker Desktop no responde en su named pipe; tampoco hay `pg_isready`/servidor local. Por seguridad no se ejecutó la suite de integración/E2E, cuyo fixture reconstruye el esquema de `erp_db_test`. |
| Navegador autenticado con perfiles de prueba | No ejecutado | El navegador in-app no tenía pestañas abiertas y no había API/DB de prueba disponible. No se usaron credenciales del usuario ni datos operativos. |

Las pruebas frontend enfocadas del Kardex pasaron: 6 pruebas en `InventoryKardexPage.test.ts` y `KardexLists.test.ts`, incluyendo reintento de búsqueda, navegación por teclado, tarjetas, acceso a detalle, enlace al retaceo y saldo físico no reconstruible. También pasaron las pruebas existentes de detalle del movimiento y etiqueta. El chequeo de lint se limitó a los archivos frontend tocados. No se encontró `ruff` instalado en el entorno disponible, así que no se reporta lint Python aprobado.

## Pendiente para aceptación operativa

1. Iniciar PostgreSQL desechable, verificar host/puerto y base `erp_db_test`, y ejecutar migración `0082 → 0083` con datos ficticios; luego revisar `alembic current`. No ejecutar el fixture contra otra base.
2. Ejecutar integración PostgreSQL de reintentos/revocación de alcance, fraccionamiento 10 → 4 + 6, ubicación agrupada de líneas 20 + 30 y rollback completo del grupo.
3. Ejecutar las pruebas de dos sesiones concurrentes sobre movimiento/grupo/medición con sincronización explícita y timeout: sin deadlock, sin doble entrada y con rollback íntegro.
4. Correr el escenario del bloque 1: dos recepciones al promedio, salida de 15, devolución de 5 y crédito separado; también el retaceo tardío, que distribuye el ajuste entre existencia remanente y salidas sin cambiar cantidades ni duplicarse al aplicar de nuevo.
5. Abrir la ruta `/inventory/kardex` en el navegador de pruebas con perfiles de sucursal y global; recargar, cambiar fechas/filtros/página y verificar la máscara de datos entre sucursales.
6. Mantener pendiente la prueba física de etiqueta, impresora y escáner HS-200: `afterprint` no prueba que la etiqueta se imprimió o colocó.

No se modifica la política de valoración, no se crean saldos históricos artificiales y el bloque no da por certificado el cumplimiento contable integral.

### Estado posterior al bloque 4 — 14/10/2026

La revisión corrigió los tres defectos visuales/operativos (fracciones estimadas sin acción, desglose de valoración incompleto y respuestas de período obsoletas) y separó la lectura nueva en puerto, aplicación e infraestructura. La regresión frontend de inventario aprobó 59 pruebas; también pasaron `svelte-check`, ESLint, build y `compileall` con Python 3.12.14. No se pudieron ejecutar PostgreSQL, Alembic ni navegador autenticado. Por ello B3-04 y la aceptación integrada siguen pendientes. El detalle está en el [cierre operativo del bloque 4](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-4-cierre-operativo.md).

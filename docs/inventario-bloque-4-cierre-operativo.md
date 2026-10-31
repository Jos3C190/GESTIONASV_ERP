# Inventario — cierre operativo del bloque 4

Fecha de la entrega original: 14/10/2026. Evidencia complementaria: 15 y 16/10/2026.

## Estado

**Incidente posterior del 16/10/2026 — resuelto:** se detectó que `erp_db` estaba en 0078 y el código esperaba 0083. Se respaldó, se ensayó 0079–0083 sobre una copia restaurada y se migró la base habitual conservando los registros y saldos. Retaceo, Valoración, Traslados y Kardex se comprobaron después en el navegador autenticado. El [informe de reparación](reparacion-entorno-inventario-0078-0083.md) conserva el respaldo, los invariantes, las pruebas y el procedimiento. La aceptación previa en `erp_db_test` y su evidencia siguen siendo válidas, pero no sustituían esta comprobación del entorno habitual.

**Estado vigente al 16/10/2026: B4-01 a B4-05 y B4-R01/R02/R03 están corregidos con regresiones. Las 15 filas E y F están verificadas; la recepción con perfil sucursal se confirmó en navegador contra la API aislada. La aceptación de software del bloque 4 queda completa.** Ver la [revisión independiente](revision-inventario-bloque-4.md) y el expediente reproducible en `tmp/inventory-block4-acceptance-20261016`. El usuario excluyó expresamente el lector HS-200, la impresión física y la colocación real de los requisitos de entrega; son demostraciones opcionales, no pendientes.

**Corte histórico (15/10/2026):** R01/R02 pasaban y una sonda reprodujo R03. Esa reproducción y su estado parcial se conservan abajo como historial, ya actualizados por la sección final del 16/10.

**Primera revisión independiente del 15/10/2026:** encontró los cinco defectos B4-01 a B4-05; B4-01 y B4-02 se reprodujeron con HTTP y PostgreSQL en `erp_db_test`. Las correcciones posteriores y sus pruebas se conservan abajo como evidencia de esa entrega. La revisión posterior volvió a ejecutar **3 API/DB aprobadas (35.27 s)** y **21 frontend aprobadas (6.61 s)**, y agregó **2 sondas que fallan (4.40 s)** por B4-R01/B4-R02. Esos resultados actualizan el veredicto sin borrar los cortes anteriores.

Este cierre conserva la política de valoración aprobada en el bloque 1. No modifica el libro mayor, períodos, monedas, reglas retroactivas ni migraciones.

## Recorrido operativo implementado

1. En **Almacenes → Inventario**, las unidades en cuarentena muestran requisitos concretos para liberarse. Una persona con `inventory:receive` puede verificar medidas incompletas o estimadas por fraccionamiento. Cada parte mantiene su propio estado y exige confirmar la etiqueta correspondiente a su revisión y cantidad vigentes.
2. La liberación individual y la colocación agrupada consultan la misma política de requisitos: medición, etiqueta, vencimiento y estado/costo del retaceo aplicable. El servidor vuelve a comprobarlos al escribir. Una recepción histórica sin obligación nueva no recibe un bloqueo inventado.
3. Desde una unidad disponible de una bodega activa y apta, quien tenga `inventory:move` puede **Preparar fracción** en bodega central o de sucursal. El despacho de una unidad completa a sucursal sigue restringido a la bodega madre. La preparación solicita cantidad y ubicación válida, y presenta la consecuencia antes de confirmar. `POST /api/v1/inventory/handling-units/{id}/prepare-split` compone movimientos existentes dentro de un savepoint: primero pasa la unidad completa de disponible a cuarentena y luego registra la parte separada en cuarentena. Si falla el segundo paso, se revierten ambos movimientos. El remanente y la fracción requieren nueva medición y etiqueta antes de volver a disponible. El mismo intento idempotente devuelve el resultado guardado; si el cuerpo difiere, responde conflicto.
4. La recepción parcial conserva la excepción acotada `transfer` de `in_transit` a `quarantine`: la cantidad recibida pasa a cuarentena y el remanente continúa en tránsito. La regla general de seguridad de etiquetas sigue activa.
5. Cuando el costo/estado del retaceo impide liberar, el panel explica que una persona con `retaceos:verify` debe completarlo. Quien tenga `retaceos:read` ve el enlace a la lista de retaceos; sin permiso de lectura no se presenta un enlace inaccesible.
6. **Inventario → Kardex** presenta cantidades/eventos físicos y valores registrados. El ajuste `cost_delta` de salidas mantiene el signo; `supplier_credit` separa crédito, costo de inventario retirado y diferencia; ajustes financieros no se presentan como cantidades físicas. Los enlaces usan IDs reales y respetan permisos.
7. Si una unidad queda bloqueada por el retaceo, el panel expone la compra y el lote de recepción que originan el requisito. En móvil conserva encabezados de tabla accesibles junto con la presentación compacta.

## Cambios técnicos

- Política pura `handling_unit_release_requirements` en dominio, compartida por liberación individual y colocación agrupada, con razones tipadas y día local `America/El_Salvador`.
- Preparación de fracción disponible con idempotencia por empresa/clave/cuerpo, autorización de ambas ubicaciones, movimientos existentes, savepoint y auditoría requerida.
- La regla de división de unidades etiquetadas permite exclusivamente la recepción parcial indicada sin retirar la protección del resto de movimientos.
- Presentación financiera compartida en las vistas de Kardex; filtros/estados de solicitudes se asocian a identidad con empresa, sucursal, bodega, artículo, período, filtros y página. Cambiar el período/contexto descarta datos atrasados.
- Puerto `InventoryKardexReadRepository`, caso de uso `InventoryKardexReadUseCases` y adaptador SQLAlchemy en infraestructura. El router mantiene HTTP, DTO, dependencias y autorización. La lectura valorada delega al repositorio/motor existente.
- No se agregaron migraciones ni se alteró el ledger.

## Pruebas y validación ejecutadas

| Capa | Comando | Resultado |
| --- | --- | --- |
| Interfaz | `vitest run src/lib/features/inventory tests/unit/InventoryKardexPage.test.ts tests/unit/KardexLists.test.ts tests/unit/InventoryValuation.test.ts tests/unit/InventoryValuationOpening.test.ts` | **61 pruebas aprobadas en 12 archivos** (5.87 s). Incluye medición de fracciones estimadas, preparación de fracción, acciones/permisos y referencia del retaceo, encabezados accesibles en móvil, cambios de período, presentación de tarjetas/tablas y servicios. |
| Tipos Svelte | `svelte-check --tsconfig ./tsconfig.json` | 0 errores y 0 advertencias. |
| ESLint | ESLint directo sobre los componentes, página, pruebas y tipos de inventario modificados | Aprobado, sin diagnósticos. |
| Build | `vite build` | Aprobado (25.27 s). Vite conserva una advertencia de importación de `jsbarcode` no detectada como usada en el bundle SSR; el módulo sí contiene uso del componente de etiqueta y el build termina. Adapter-auto no detectó un destino de producción, lo cual no impide generar el build. |
| Backend unitario | `pytest -q tests/unit --ignore=tests/unit/test_ocr_worker.py` | **694 pruebas aprobadas** (29.02 s). La prueba OCR excluida no se pudo recolectar porque falta `pikepdf` en el contenedor. Tras el último refactor, las pruebas unitarias enfocadas de Inventario pasaron: **65 pruebas** (9.77 s). |
| PostgreSQL | `pytest -q tests/integration/test_inventory_kardex_repository.py tests/integration/test_inventory_split_prepare_route.py tests/integration/test_inventory_movement_idempotency.py` | **4 pruebas aprobadas** (15.98 s) en la base aislada `erp_db_test`: Kardex paginado/totales/aislamiento, preparación de fracción con replay/conflicto/rollback, liberación idempotente y recepción parcial de traslado. |
| E2E backend | `pytest -q tests/e2e/test_purchase_orders.py -k 'purchase_receiving_partial_then_complete_workflow_and_audit or retaceo_workflow_uses_purchase_details_and_audits'` | **2 recorridos aprobados** (25.50 s) en `erp_db_test`, recreada y sembrada antes de cada prueba. Cubren recepción de compra parcial/completa y el flujo de retaceo/auditoría. No equivalen a un recorrido de navegador. |
| Calidad backend | Ruff en archivos del bloque y dependencias directas; `python -m compileall -q app tests` | Ruff enfocado aprobado; compilación aprobada en Python **3.12.15**, runtime dentro del rango del proyecto. La ejecución global de Ruff sigue mostrando hallazgos en archivos fuera del alcance enfocado. |
| Alembic | `alembic heads`; `alembic current` dirigido a `erp_db_test` | Cabeza `0083`; la base de prueba está en `0083 (head)`. No se añadió una migración en el bloque 4. |
| Higiene del diff | `git diff --check` | Aprobado; Git mostró únicamente avisos de normalización CRLF/LF en dos pruebas de solicitudes de compra ya modificadas. |

La fixture E2E ahora reconstruye el esquema de `erp_db_test` antes de cada caso, en vez de borrar filas del ledger append-only en orden inseguro. Cada cliente E2E cierra su pool async al terminar para evitar reutilizar conexiones entre loops. Ninguna prueba apunta a `erp_db`.

## Límites del corte inicial (histórico)

Los pendientes descritos en esta sección y la matriz siguiente corresponden al corte anterior a la aceptación final del 16/10/2026. La evidencia posterior que los resuelve está en «Cierre operativo R03 y aceptación E/F» al final de este documento.

- **Suite OCR:** `tests/unit/test_ocr_worker.py` no se recolecta porque `pikepdf` no está instalado en el contenedor. Las demás pruebas unitarias sí pasaron; no instalé una dependencia ajena al bloque.
- **Cobertura PostgreSQL restante:** aún faltan las sesiones concurrentes, replay con permisos revocados, matriz completa de alcance por empresa/sucursal, doble asignación agrupada con rollback de segunda línea y cortes/lotes/empates de fecha. La corrida SQL aprobada cubre el subconjunto descrito arriba.
- **Recorrido de navegador autenticado:** no se hizo una sesión de extremo a extremo en navegador con perfiles global y de sucursal. Las pruebas de frontend son componentes/servicios; las pruebas backend E2E ejercitan HTTP/API y base, pero no reemplazan esa aceptación visual.
- **Hardware:** lector HS-200, impresión física y colocación no probados; `afterprint` tampoco confirma colocación real.

## Matriz de aceptación del corte inicial (histórica)

| Caso | Estado actual |
| --- | --- |
| HU estimada dividida 4 + 6 ofrece medición propia para ambas partes | UI y política local aprobadas; prueba de preparación/replay/rollback SQL aprobada. La cadena medición + etiqueta + liberación de ambas partes no está probada en E2E. |
| HU disponible: preparar 4 + 6, medir, etiquetar, despachar 4 y conservar 6 | UI/end-point implementados; preparación, idempotencia, conflicto y rollback del movimiento preparatorio pasaron en PostgreSQL. Medición, impresión/confirmación y despacho encadenados siguen pendientes en navegador. |
| Recibir 4 de 10 en tránsito | La prueba PostgreSQL de recepción parcial aprobó: 4 en cuarentena y remanente en tránsito. Falta el recorrido visual autenticado. |
| Requisito de etiqueta/retaceo y excepción histórica | Política unitaria y mensajes/acciones de interfaz cubiertos. Autorización efectiva en DB pendiente. |
| Retaceo tardío $20 repartido $8/$12 y crédito $100/costo $75/diferencia $25 | Los cálculos tienen cobertura unitaria dentro de la suite backend aprobada (excepto el módulo OCR no recolectado); el E2E de retaceo/auditoría también pasó. No se ejecutó un escenario PostgreSQL que reproduzca exactamente esos importes ni el recorrido visual. |
| Cambio de período durante consulta | Prueba frontend de respuesta atrasada aprobada. |
| Orden, páginas, empates, lotes, cortes y conciliación SQL | PostgreSQL aprobó búsqueda/paginación/totales, desconocido sin corte, conciliación e aislamiento. Empates de fecha, lotes, cortes valorados y carreras siguen pendientes. |
| Ubicación 20 + 30, rechazo de 51 y rollback de segundo movimiento | Validaciones existentes y UI se mantienen; rollback/concurrencia real pendientes. |
| Replay, alcance de sucursal/empresa y revocación de permisos | Replay idempotente/conflicto del endpoint de preparación probado en PostgreSQL. Permiso revocado y toda la matriz de alcance siguen pendientes. |
| Migración 0082 → 0083 y cabeza aplicada | `alembic heads` y `alembic current` de `erp_db_test` informan `0083 (head)`. No se probó una migración histórica con fixture de datos previa a 0083; no hay migración nueva en el bloque. |

## Cierre de bloques anteriores

- **Bloque 1 — política y motor de valoración:** código y pruebas unitarias existentes; la activación del saldo inicial real y la validación PostgreSQL permanecen pendientes. No equivale a aprobación contable.
- **Bloque 2 — lotes, etiquetas y colocación:** el código conserva identidad, revisión y alcance; la prueba física de etiqueta/QR/escáner y las transacciones PostgreSQL permanecen pendientes.
- **Bloque 3 — Kardex:** B3-01 (medir/revalidar fracciones), B3-02 (desgloses reales), B3-03 (descartar respuestas obsoletas) y B3-05 (separación por capas) están corregidos en código y cubiertos por las validaciones disponibles. B3-04 y la aceptación integrada siguen pendientes por PostgreSQL/navegador.

## Próximos pasos reproducibles

1. Completar las pruebas de autorización/revocación, alcance por sucursal/empresa, rollback de grupos y carreras concurrentes dentro de `erp_db_test`.
2. Levantar la API y frontend con datos ficticios y completar el navegador autenticado con perfiles global y de sucursal: acceso directo/recarga, cambio de contexto, filtros, preparación de fracción, medición, etiqueta, disponibilidad y traslado.
3. Probar por separado el HS-200, la etiqueta impresa y su colocación.

La entrega local no debe presentarse como aceptación completa hasta pasar PostgreSQL y navegador autenticado, según el contrato del bloque 4.

## Actualización de evidencia del cierre — 15/10/2026

Esta sección registra las ejecuciones posteriores al corte histórico de arriba. Las pruebas PostgreSQL usan exclusivamente `erp_db_test`; no se consultó ni modificó `erp_db`.

| Alcance | Comando / comprobación | Resultado actual |
| --- | --- | --- |
| Regresiones B4 por API y PostgreSQL | `pytest -q tests/e2e/test_inventory_block4_closure.py` | **3 aprobadas en 40.80 s**. Incluye que medición y listado conserven los pendientes reales y dos escenarios de ubicación agrupada: excepción histórica y recepción nueva con etiqueta pendiente. |
| Regresiones frontend B4 | `vitest run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts tests/unit/InventoryKardexPage.test.ts` | **21 aprobadas en 7.72 s**. Incluye respuesta de medición con bloqueo restante, confirmación de etiqueta con fallo/reintento y refresco del panel, preparación en sucursal sin habilitar despacho completo y reintento de la página valorada solicitada. |
| Unitarias backend relacionadas | `pytest -q tests/unit/test_inventory_capacity.py tests/unit/test_inventory_putaway_group_schema.py` | **39 aprobadas en 10.19 s**. |
| Tipos Svelte | `svelte-check --tsconfig ./tsconfig.json` | **0 errores, 0 advertencias**. |
| Lint y formato | ESLint y Prettier `--check` en los archivos frontend tocados; Ruff `check` y `format --check` en los cuatro archivos Python de esta entrega | Aprobados. Ruff: `All checks passed!`; los cuatro archivos ya están formateados. |
| Build | `vite build` | Aprobado en **1 min 11 s**. Se mantienen advertencias del bundle SSR de `jsbarcode` y de detección del adaptador; no impidieron el build. |
| Alembic en entorno de prueba | `alembic heads` y `alembic current` con destino `erp_db_test` | **0083 (head)**. No se creó una migración nueva en este cierre. |
| Higiene | `git diff --check` | Aprobado; solo avisos de conversión CRLF/LF en pruebas preexistentes fuera de este cambio. |

### Estado de B4-01 a B4-05 tras las regresiones

| Hallazgo | Resolución | Evidencia actual y límite |
| --- | --- | --- |
| B4-01 — requisitos desactualizados entre asignaciones agrupadas | Corregido: cada resultado evalúa los requisitos vigentes del remanente dentro de la transacción. | Pruebas API/DB de ubicación agrupada para recepción histórica y nueva, además de unitarias de esquema. No cubren todavía la cadena completa de medida, etiqueta, liberación y despacho, ni una valoración exacta del grupo. |
| B4-02 — respuesta de medición sin pendientes actuales | Corregido: se devuelve la HU enriquecida con los metadatos usados por el listado. | Prueba API compara medición/listado con etiqueta y retaceo pendientes; prueba de panel evita liberar mientras permanezca un requisito. |
| B4-03 — confirmar etiqueta no refresca el panel | Corregido: el diálogo notifica éxito y el panel recarga la elegibilidad sin perder filtros. | Prueba de componente cubre error/reintento y otro bloqueo persistente. No es prueba en navegador autenticado ni hardware. |
| B4-04 — preparar fracciones solo visible en matriz | Corregido: la elegibilidad de preparación se separa de la autorización de despacho completo. | Prueba de componente valida la prop de preparación sin autorización de transferencia; falta prueba integrada de página/panel con sesión real de sucursal. |
| B4-05 — reintento pierde la página consultada | Corregido: el reintento mantiene la página y período aplicados. | Prueba de página cubre fallo de página 2 y reintento; falta completar cambios de empresa/sucursal/permisos durante fallo y desmontaje si no existe otra cobertura. |

### Aceptación integral pendiente en el corte del 15/10 (histórico)

Las pruebas de esta actualización son focalizadas y **no cierran la aceptación del bloque**. Siguen pendientes las filas de la matriz E que no están cubiertas por una regresión equivalente: importes exactos de retaceo/crédito en PostgreSQL; grupo de 20 + 30, rechazo de 51 y rollback por fallo de segunda asignación; replay con permisos revocados y alcance empresa/sucursal completo; carreras concurrentes y conciliación bajo concurrencia; empates de fecha, lotes, cortes/fechas locales y una migración `0082 → 0083` con datos ficticios previos; y recorrido de navegador autenticado con perfiles global y de sucursal contra API aislada.

El navegador no se probó porque la interfaz/API disponibles están publicadas en los puertos de desarrollo (`5173` y `8000`) y la API existente apunta a la base operativa `erp_db`. Usar esa sesión para acciones de escritura violaría el aislamiento exigido; no se levantó ni se reinició un stack alterno. Los datos presentes en `erp_db_test` cubren los E2E reportados, no la matriz completa.

## Actualización final de evidencia — 15/10/2026

Se ejecutó `docs/prompt-luna-correcciones-finales-inventario-bloque-4.md`. Las secciones anteriores son cortes históricos y quedan supersedidas por esta tabla en lo que respecta a B4-R01/R02 y las corridas listadas abajo.

| Validación actual | Comando/entorno | Resultado |
| --- | --- | --- |
| Frontend | Binarios locales de `frontend/node_modules/.bin`: Vitest para `HandlingUnitsPanel`, Kardex, integración de bodega y contexto | **41 aprobadas en 4 suites / 5.17 s.** |
| Tipos/lint/formato frontend | `svelte-check`, ESLint y Prettier `--check` en los archivos cambiados | Svelte: **0 errores y 0 advertencias / 22.77 s**; ESLint aprobado en 4.51 s; Prettier en 1.15 s. |
| Backend unitario | Valoración, esquema de ubicación agrupada y Kardex | **36 aprobadas / 9.42 s.** |
| PostgreSQL | Valoración, Kardex, idempotencia, recepción parcial y preparación de fracciones | **5 aprobadas / 16.69 s.** Importes: ajuste `$8/$12`; devolución/costo `$75`, crédito `$100`, diferencia `$25`. |
| API E2E | `backend/tests/e2e/test_inventory_block4_closure.py` | **6 aprobadas en 63.18 s.** Prueba rollback si falla la segunda asignación; dos solicitudes simultáneas de misma clave/cuerpo producen un solo movimiento y un replay; prueba `0082→0083` conserva datos históricos. |
| Alembic | `alembic heads` y `alembic current` con DSN preparado por `backend/tests/conftest.py` | **0083 (head)**; host `db`, puerto `5432`, base `erp_db_test`. |
| Build | `vite build` | Aprobado en **27.70 s**. Warnings no bloqueantes: import default de `jsbarcode` no usado por SSR y `adapter-auto` sin destino de despliegue detectado. |
| Higiene | `git diff --check` | Aprobado; avisos CRLF/LF solo en dos pruebas preexistentes de Compras. |

Las pruebas con PostgreSQL se ejecutaron en serie sobre `erp_db_test`; el servicio normal que usa `erp_db` no se detuvo, reconfiguró ni usó para escritura. `pnpm` intentó reemplazar `node_modules` y se detuvo por falta de TTY (`ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`), así que se utilizaron los binarios locales. Ruff no está instalado en el runtime backend y no se agregó una dependencia; `compileall` pasó para las pruebas Python editadas.

### Matriz E–F del corte preliminar (histórica; ver cierre final abajo)

| Caso | Estado actual |
| --- | --- |
| B4-R01 confirmación tardía y B4-R02 lectura previa a medición | **Corregidos.** Regresiones permanentes cubren éxito/error/finalización tardíos, reabrir la misma unidad, otra unidad, contexto/desmontaje, impresión de B y listado anterior con demora de ubicaciones. |
| Grupo 20+30, rechazo 51, rollback segunda asignación | **Parcial.** API prueba 20+30 en dos destinos desde una misma línea/HU, rechaza 51, y un fallo inyectado en la segunda asignación revierte HU, balances, movimientos y auditoría. Falta que 20 y 30 sean dos detalles de compra distintos del mismo artículo. |
| Concurrencia/idempotencia | **Parcial.** Dos peticiones E2E concurrentes con la misma clave/cuerpo producen una escritura y un replay dentro del timeout. No hay carrera demostrada de claves distintas ni competencia simultánea de medición, retaceo o conciliación. |
| Importes de retaceo y devolución | **Aprobado en PostgreSQL** con los importes exactos, historial idempotente y sin movimiento físico de retaceo. |
| Kardex y conciliación | **Parcial.** SQL demuestra páginas/totales, desconocido distinto de cero y aislamiento de empresa; también pasa recepción parcial. Faltan empates de fecha, lotes, saldos anteriores al período, zona horaria/corte inicial y conciliación bajo escritura concurrente. |
| Acceso/replay y JSON sensible | **Parcial.** Hay aislamiento SQL por empresa y comprobaciones del panel/rutas; falta replay después de mover la HU con acceso revocado y una matriz completa de perfiles/sucursal que inspeccione los importes no autorizados. |
| Migración histórica | **Aprobada para `0082→0083` en la base desechable**, con una recepción ficticia preexistente y comprobación de nueva recepción posterior. No se reescribió historia ni se creó migración nueva. |
| Navegador con perfiles global/sucursal y API real | **Parcial.** Sobre API/frontend aislados en `8001/5174` se verificó listado de sucursal, medición, liberación y ficha QR pública en nueva pestaña con origen y movimientos. No se completó preparación/despacho 4+6, colocación de etiqueta confirmada, ciclo de recepción parcial y Kardex/conciliación en navegador. |
| HS-200, impresión y colocación física | No probado; requiere el lector/etiqueta reales y comprobación del usuario. |

En ese corte, el health check del backend comparaba contra una revisión esperada `0043`, aunque el entorno de prueba estaba en `0083`; las llamadas API utilizadas funcionaron. Ese diagnóstico quedó fuera del encargo. El estado de aceptación reflejado en esta matriz preliminar fue reemplazado por el cierre final de E–F que sigue. Los apuntes no autorizan ampliar políticas contables ni operar sobre datos de `erp_db`.
## Cierre operativo R03 y aceptación E/F — 16/10/2026

Esta sección es el estado final más reciente de esta revisión; las tablas fechadas antes siguen como historial, no como resultado vigente.

### Entorno y aislamiento

Antes de las pruebas destructivas se leyó backend/tests/conftest.py. Su fixture reconstruye el esquema y aborta si el destino no es la base dedicada. Los DSN efectivos se inspeccionaron sin mostrar secretos; destino: host db, puerto 5432, base erp_db_test. Ninguna prueba escribió en erp_db.

La comprobación real de Alembic se ejecutó con la URL modificada explícitamente a erp_db_test, sin mostrarla: alembic heads y alembic current dieron **0083 (head)**. No se reescribieron migraciones.

El navegador usó API/frontend aislados en 8001/5174. Los servicios temporales de aceptación fueron detenidos al terminar; la verificación de Docker solo muestra activo el stack ordinario gestionasv_erp en 8000/5173 y sus servicios habituales. No se detuvieron ni reiniciaron esos servicios, ni se borraron contenedores o volúmenes. El navegador operativo del usuario no se usó para escrituras.

### Resultado de código y validaciones

- R03 corregido: respuestas tardías de invalidación de enlaces ya no cambian QR, enlace, producto, mensaje ni estado ocupado de otra unidad/sesión. Regresiones permanentes con promesas controladas.
- Kardex corregido: la página carga bodegas en páginas de 100, por debajo del límite 100 de API que antes causaba HTTP 422. Tiene regresión y se confirmó la recarga en navegador.
- Backend: unitarias focalizadas 79 aprobadas; E2E de `test_inventory_block4_closure.py` 10 aprobadas, incluyendo liberación de HU bloqueada por etiqueta/retaceo y respuestas JSON restringidas. Suites PostgreSQL: Kardex 5, valoración 1, idempotencia de movimientos 2 y preparación fraccionada 1 aprobadas. La conciliación se sincronizó con recepción, traslado y aplicación de retaceo.
- Frontend: 45 pruebas en cuatro suites focalizadas aprobadas. svelte-check encontró 0 errores y 0 advertencias; ESLint para inventario aprobó; Prettier aprobó los cinco archivos revisados; build Vite aprobado. El build conserva avisos no bloqueantes por import SSR de jsbarcode y falta de destino de despliegue para adapter-auto.
- En este cierre, git diff --check se ejecutó después de actualizar la evidencia y terminó sin errores.
- Python compileall pasó para las regresiones E2E e integración modificadas. La comprobación Ruff focalizada registrada después de las refactorizaciones pasó; no se pudo repetir aquí porque el contenedor actual no tiene instalado el módulo Ruff y no se reinstalaron dependencias.

Comandos reproducibles, resultados detallados, límites de cobertura y versiones de entorno están en tmp/inventory-block4-acceptance-20261016/verification-results.md.

### Recorrido de navegador real aislado

La secuencia documentada con IDs sintéticos, importes de prueba y resultados está en tmp/inventory-block4-acceptance-20261016/browser-acceptance.md. Se utilizó COM-00004 / RET-00002, una división de HU 4+6, medición, etiqueta, confirmación de colocación simulada, disponibilidad, despacho de 4, conservación de 6, recepción contada y consulta de Kardex desde la API aislada. La ficha QR pública abrió en navegador con origen y movimientos. Se verificaron teclado y los temas disponibles. El comando de colocación y la salida de impresión fueron simulaciones de software, no impresión o lectura física.

**Verificación complementaria de perfil:** la primera pasada consumió con el perfil global el único envío disponible para esa secuencia, de modo que el perfil sucursal no tuvo un pendiente que mostrar. Se reservó una HU sintética diferente y se repitió en el navegador aislado con un perfil limitado a Jiquilisco. La bodega ITK-IT-WR-b2 mostró 1 pendiente de 4 cajas; tras confirmar desde la interfaz, la UI reportó 4 recibidas y 0 pendientes, y la consulta de solo lectura a `erp_db_test` confirmó `quantity_base=4` y `stock_status=quarantine`. El rol sintético necesitó `warehouses.view`, concedido únicamente en `erp_db_test`; la cuenta se desactivó después. El Kardex de sucursal inicialmente recibió HTTP 422 al solicitar 200 bodegas; tras paginar de 100, la vista cargó. No se encontró un defecto de producto en la recepción por perfil sucursal.

### Decisión de aceptación

R03 está cerrado. Las 15 filas E están verificadas en el alcance documentado en la matriz: E1 se respalda con evidencia complementaria navegador + API/SQL, E7 con regresiones deterministas de UI, E12 con JSON de consulta/listado/replay restringido y E14 con conciliación sincronizada con las tres escrituras. F también está verificado: la recepción desde perfil sucursal se confirmó en navegador aislado y se corroboró cuarentena en `erp_db_test`. **La aceptación de software del bloque 4 queda completa en el alcance solicitado.** Por aclaración expresa del usuario, el proyecto es una demostración de software: lectura con HS-200, impresión física y colocación real son opcionales y no requieren otro encargo. No se afirma que esas pruebas físicas se hayan ejecutado.

### Recomprobación posterior solicitada por el usuario

El 16/10/2026 se repitieron **45 pruebas frontend**, **10 E2E API** y **9 de integración PostgreSQL**. Al reunir las cuatro suites SQL se detectó contaminación entre sus datos ficticios: una prueba concurrente dejaba valoración activa en la empresa compartida. Se corrigió el montaje de esas pruebas para usar empresas propias y la ejecución conjunta pasó completa. No se cambió código de producción. El detalle, el fallo inicial y el resultado final están en la sección «Recomprobación final solicitada por el usuario» de la [revisión independiente](revision-inventario-bloque-4.md).

El recorrido manual del usuario queda como aceptación de su demostración. El hardware y las etiquetas físicas no figuran como pendientes. Al momento del corte R03, la base habitual aún no se había contrastado y el diagnóstico de revisión de esquema seguía pendiente; la actualización del 16/10/2026 que sigue resuelve esa observación.

## Reparación y comprobación del entorno habitual — 16/10/2026

Se identificó que la base habitual `erp_db` estaba en 0078 aunque el backend consultaba el esquema hasta 0083. Se respaldó la base, se restauró en una base nueva de ensayo, se aplicaron allí 0079–0083 y se compararon los invariantes. El ensayo pasó y entonces se migró `erp_db` a **0083**. No se hizo reset, downgrade, seed ni apertura de valoración.

La comparación antes/después mantuvo 16 compras, 21 detalles, 14 retaceos, 15 unidades de manejo, 28 movimientos, 34 líneas y 22 saldos físicos por 2,883 unidades. La vista de valoración sigue sin apertura y por ello no inventa costo; lotes y etiquetas nuevas permanecieron vacíos. El endpoint `/health/ready` y las páginas habituales de Retaceo, Valoración, Traslados y Kardex cargaron sin los errores de esquema de las capturas.

El health check compara ahora con las cabezas Alembic del backend. También se corrigió la presentación de error frente a resultados vacíos en el contador de Retaceo y las consultas de Traslados. Las pruebas focalizadas pasaron: 5 backend, 7 frontend y Svelte Check con 0 errores/advertencias. Se revisaron las cuatro pantallas en el navegador autenticado, en solo lectura; Kardex mostró los 9 movimientos consultados para `PRD-EMP-009`.

El detalle reproducible, hash/ruta del respaldo, base de ensayo, conservación de datos, comandos y límites están en [reparacion-entorno-inventario-0078-0083.md](reparacion-entorno-inventario-0078-0083.md). La lectura física con HS-200, impresión y colocación real siguen fuera del alcance y no se afirman como realizadas.

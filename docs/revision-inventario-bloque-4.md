# Revisión independiente del bloque 4 de Inventario

Revisión inicial: **15/10/2026**. Cierre de aceptación E–F: **16/10/2026**. Revisión iniciada el 14/10/2026.

## Veredicto

**Incidente posterior confirmado y resuelto el 16/10/2026:** la revisión detectó que `erp_db` seguía en **0078** aunque el código requería **0083**. Se respaldó la base, se restauró una copia nueva, se ensayaron las cinco migraciones y se compararon los saldos antes de actualizar `erp_db` a 0083. Retaceo, Valoración, Traslados y Kardex se volvieron a comprobar en el entorno habitual. La causa y la evidencia están en el [informe de reparación 0078–0083](reparacion-entorno-inventario-0078-0083.md); no se ejecutaron acciones operativas de inventario durante esa aceptación.

**Estado vigente al 16/10/2026: B4-01 a B4-05 y B4-R01/R02/R03 están corregidos con regresiones; las 15 filas E tienen evidencia aprobada y F se completó en navegador con un perfil de sucursal contra la API aislada. La aceptación de software del bloque 4 queda completa.** Por aclaración expresa del usuario, impresión física, colocación real y lector HS-200 son demostraciones opcionales: no son requisitos ni pendientes de esta entrega.

Las secciones fechadas antes del cierre final conservan el estado de cada revisión como historial. Para el veredicto actual, prevalecen esta síntesis, «Cierre R03 y matriz original E» y la recomprobación final solicitada por el usuario.

**Corte histórico (15/10/2026):** 41 pruebas frontend, 6 E2E API/PostgreSQL y 5 de integración PostgreSQL aprobaron; una sonda adicional reprodujo B4-R03. La sección conserva esa reproducción y veredicto anterior como historial, no como estado actual.

El alcance fue contrastado con [el encargo original](prompt-luna-inventario-bloque-4.md) y [el informe de entrega](inventario-bloque-4-cierre-operativo.md). Hay avances verificables en medición de fracciones, preparación transaccional, presentación del Kardex y separación de sus consultas por capas. Se encontraron cinco defectos; dos se reprodujeron mediante HTTP contra la aplicación real y PostgreSQL de pruebas. Los otros tres se identificaron en la integración de componentes y rutas.

**Este es el último bloque funcional del alcance de Inventario acordado y su aceptación de software ya quedó completada.** Para el proyecto teórico basta demostrar el flujo de etiquetas en software. Una comprobación futura con lector, impresora o mercancía real sería opcional y queda fuera del alcance autorizado.

La revisión no modifica código funcional ni datos operativos. Las sondas temporales se retiraron de la suite tras guardar su fuente y resultado como evidencia.

## Hallazgos

### B4-01 · P1 · Una unidad lista para ubicar falla al repartirse completamente entre dos destinos

**Lugar:** `backend/app/api/v1/routers/inventory_putaway_groups.py:653–668`; rama de requisitos precargados en el mismo archivo, líneas 66–67.

Los requisitos se calculan una sola vez antes de ejecutar las asignaciones. Si una HU sin requisitos pendientes se divide entre dos destinos, el primer movimiento modifica su remanente: ahora tiene medidas estimadas y otra revisión de etiqueta. El segundo movimiento sigue usando los requisitos anteriores. Como consume todo el remanente, intenta dejarlo disponible. El repositorio detecta las medidas estimadas, rechaza la operación y revierte el grupo.

**Reproducción ejecutada:** crear solicitud, cotización, orden y recepción de 4 mediante la API; aceptar y medir la HU; representar en la base de prueba la excepción histórica de etiqueta; confirmar que el listado devuelve requisitos vacíos; solicitar 1 en ubicación A y 3 en B. No se simularon permisos, validadores ni servicios.

- Esperado: HTTP 201, dos partes en cuarentena, pendientes de revalidación.
- Obtenido: HTTP 409: «La sucursal debe verificar las medidas del fraccionamiento antes de liberar el inventario».
- Comprobación posterior: permanece una sola HU de 4 en la ubicación original; no queda una hija persistida. La sonda no verificó todos los saldos ni todas las filas de auditoría.

**Corrección requerida:** obtener la elegibilidad vigente después de cada división, conservando la política común y los bloqueos transaccionales. La división no debe autorizar disponibilidad del remanente con metadatos anteriores. Añadir regresión con una misma HU asignada a dos destinos, tanto histórica como nueva con etiqueta vigente.

### B4-02 · P2 · Guardar medidas elimina de la respuesta requisitos que siguen pendientes

**Lugares:** `backend/app/infrastructure/repositories/inventory_repository.py:1486`; `backend/app/api/v1/schemas/inventory.py:439`; `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:744`.

La verificación de medidas devuelve `_handling_unit_dict(row)`, sin los metadatos de elegibilidad que sí agrega el listado. El DTO completa `release_requirements` con `[]`. El panel sustituye toda la HU por esa respuesta y pierde los pendientes reales de etiqueta/retaceo. En la página de almacén no se pasa un callback que recargue la lista después de medir.

**Reproducción ejecutada:** recepción nueva aceptada, sin confirmar etiqueta; verificar medidas y consultar inmediatamente la misma HU por el listado.

- Respuesta de medición: `release_requirements: []`.
- Respuesta del listado: `release_requirements: ["label_confirmation_required"]`.
- Consecuencia en el panel: desaparece el pendiente y puede habilitarse «Liberar», aunque el servidor conserva el bloqueo.

**Corrección requerida:** devolver la HU con requisitos actualizados desde el comando o recargarla antes de presentar su disponibilidad. Añadir prueba con el payload real de HTTP, cubriendo etiqueta y retaceo pendiente.

### B4-03 · P2 · Confirmar la etiqueta no actualiza el bloqueo de liberación del panel

**Lugares:** `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte:442–451`; `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:1608–1612`.

La confirmación solo cambia `labelPreview` dentro del diálogo. El panel recibe únicamente el cierre y conserva el `release_requirements` anterior. Una HU ya medida que tenga pendiente solo su etiqueta sigue mostrando el bloqueo al confirmar y cerrar; el operador debe pulsar «Actualizar» manualmente.

**Evidencia:** inspección del flujo de eventos y de `releaseBlockReasons` en el panel, líneas 271–288. No se ejecutó este caso en un navegador real.

**Corrección requerida:** notificar al padre la confirmación y refrescar la elegibilidad. Cubrir el recorrido medir → imprimir → confirmar colocación → liberar sin recarga manual. Mantener la confirmación expresa; `afterprint` no la sustituye.

### B4-04 · P2 · La interfaz restringe preparar fracciones a la bodega central

**Lugares:** `frontend/src/routes/(app)/warehouses/[id]/+page.svelte:931–934`; `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:513–514`, `:1131`.

La preparación reutiliza `canTransfer`, que la página solo activa si `warehouse.isCentral`. Un usuario con `inventory:move` no puede preparar una fracción disponible en una ubicación apta de sucursal. El endpoint permite esa operación dentro del almacén autorizado; el encargo A2 no restringe la preparación a la matriz.

**Evidencia:** inspección de autorización, props y condiciones de render. No se probó el recorrido visual de sucursal.

**Corrección requerida:** separar la capacidad de preparar fracciones de la capacidad de despachar desde matriz; exigir el permiso y la elegibilidad correspondientes. Añadir una prueba de la integración entre página y panel para un almacén no central.

### B4-05 · P2 · Reintentar una página fallida del Kardex valorado vuelve a la primera

**Lugar:** `frontend/src/routes/(app)/inventory/kardex/+page.svelte:339–344`, `:907`.

`showValued` recibe la página solicitada, pero vacía `valuationData` y no conserva esa página para reintentar. El botón invoca la función sin el tercer argumento, cuyo valor por defecto es 1. Si falla «Siguiente» al cargar la página 2, «Reintentar» consulta la página 1.

**Evidencia:** inspección del manejo de la consulta y del botón. Las pruebas existentes de esta página no cubren el error de paginación.

**Corrección requerida:** persistir la consulta aplicada con su página y reutilizarla al reintentar. Añadir la secuencia página 1 → fallo en página 2 → reintento de página 2.

## Comparación con las expectativas

| Requisito | Evaluación |
| --- | --- |
| A1: medir hija y remanente; llegar a acciones útiles; etiqueta y liberación coherentes | La medición de `split_estimate` y el enlace profundo están implementados. B4-02 y B4-03 impiden aceptar el recorrido integrado. |
| A2: preparar fracciones disponibles y recibir parcialmente | Existe comando transaccional, idempotencia y cobertura SQL previa de preparación/rollback y recepción parcial. B4-04 limita la UI; falta el recorrido completo de ambas partes hasta despacho. |
| A3: elegibilidad común y vigente al escribir | Existe política pura con razones tipadas. B4-01 muestra que la decisión del grupo reutiliza requisitos anteriores a una división. El repositorio bloquea la liberación inválida. |
| B: datos reales del Kardex | Presentación compartida de `cost_delta`, crédito/costo/diferencia y efecto físico de eventos financieros. Las regresiones frontend focalizadas pasan. Falta aceptación integrada con los importes exactos del encargo. |
| C: filtros, contexto, paginación y reintento | Hay identidad de consulta e invalidación de fechas. B4-05 incumple el reintento de la página aplicada. Faltan escenarios reactivos de empresa/sucursal/permisos y desmontaje en las pruebas de página. |
| D: lectura por capas y PostgreSQL | Puerto, caso de uso y adaptador SQL presentes. La cobertura SQL entregada prueba un subconjunto, no toda la matriz. |
| E–F: aceptación de software | Incompleta: faltan escenarios exigidos de concurrencia, revocación/permisos, lotes/cortes, migración histórica y recorrido en navegador con API real. Dos sondas nuevas fallan por defectos reproducidos. |

No se identificó en esta revisión una necesidad de modificar la política contable aprobada, añadir otro motor de costos o ampliar el alcance a módulos nuevos.

## Evidencia ejecutada en esta revisión

### API real + PostgreSQL

- Destino comprobado antes de correr: **host `db`, puerto `5432`, base `erp_db_test`**. No se usó `erp_db`.
- Se revisó `backend/tests/conftest.py`: las pruebas E2E reconstruyen exclusivamente la base de prueba y aplican migraciones/seed antes de cada caso.
- Comando de pytest: `pytest -q --tb=short --show-capture=no tests/e2e/test_inventory_block4_review_probe.py`, dentro del contenedor backend, con ambos DSN dirigidos explícitamente a `erp_db_test`.
- Resultado: **2 fallos reproducidos en 27.28 s**, correspondientes a B4-01 y B4-02. No son errores de arranque ni de preparación de fixtures: ambos alcanzan el endpoint y la aserción funcional señalada.
- Fuente archivada: `tmp/inventory-block4-audit-20261014/test_inventory_block4_review_probe.py`.
- Salida: `tmp/inventory-block4-audit-20261014/backend-probes.log`.
- Se verificó igualdad de hash entre la copia archivada y la sonda ejecutada antes de retirar la sonda de `backend/tests/e2e`.

Para repetir estas sondas, copiar temporalmente la fuente archivada al path indicado de la suite y utilizar las fixtures/DSN de `erp_db_test`. Su finalidad es demostrar los defectos actuales; deben convertirse en regresiones permanentes al corregirlos. No ejecutar contra una base operativa: las fixtures reconstruyen el esquema de prueba.

### Frontend

El crítico independiente ejecutó seis suites focalizadas con Vitest: **31/31 pruebas aprobadas en 5.13 s**. Comprenden HU, ubicación agrupada, detalle/listas de Kardex, página y cliente API. Las pruebas actuales verifican pasos separados; no cubren las transiciones defectuosas señaladas.

Comando ejecutado desde `frontend`:

```powershell
node node_modules/vitest/vitest.mjs run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts src/lib/features/inventory/components/GroupedPutawayPanel.test.ts src/lib/features/inventory/components/KardexMovementDetails.test.ts tests/unit/InventoryKardexPage.test.ts tests/unit/KardexLists.test.ts src/lib/features/inventory/kardex.test.ts
```

Resultado por suite: HU 15, ubicación agrupada 1, detalle de Kardex 3, página 4, listas 6 y cliente API 2. Código de salida 0. La salida frontend está en la herramienta de esta conversación; no se guardó en archivo.

El intento previo de usar `pnpm exec` abortó por comprobación de dependencias sin TTY. Se utilizó el binario ya instalado; no se forzó instalación.

### Límites de esta evidencia

- Los resultados de 694 unitarios backend, 65 enfocados, 4 SQL, 2 E2E API, 61 frontend, tipos/lint/build y cabeza 0083 corresponden a la entrega anterior y se conservan en su informe. No se presentan como nuevas ejecuciones de esta revisión.
- No se ejecutó el navegador autenticado contra un entorno ficticio en esta revisión. Las sondas HTTP usan ASGI y PostgreSQL reales; no sustituyen esa aceptación visual.
- No se puntuó apariencia, contraste ni comportamiento visual sin render. La revisión independiente rechaza el cierre frontend por consistencia operativa.
- No se probó lectura física del HS-200, impresión ni colocación de etiquetas.

## Qué falta para cerrar este mismo bloque

1. Corregir B4-01 a B4-05 y dejar regresiones permanentes con respuestas reales del backend.
2. Completar los casos pendientes de la matriz E, incluyendo la cadena recepción validada → retaceo exigible → ubicación → medición/etiqueta → disponibilidad → traslado/recepción parcial → Kardex/conciliación.
3. Demostrar permisos/alcance, concurrencia y rollback, cortes/empates/lotes y migración histórica en la base de prueba; registrar resultados reales por caso.
4. Recorrerlo en navegador con perfiles global y sucursal, incluidas recarga, errores/reintento, tabla/tarjetas y ambos temas. Mantener la prueba física del lector/etiqueta separada.

Cuando eso esté aprobado, se podrá cerrar el alcance de software de los cuatro bloques. La activación del inventario inicial real sigue siendo una operación del negocio con su conteo y aprobación, no otro bloque de desarrollo.

## Resolución de hallazgos y evidencia posterior — 15/10/2026

El diagnóstico anterior conserva las reproducciones y el estado que tenía antes de los arreglos. El resultado actual se distingue aquí para no confundir «corregido» con «aceptación integral aprobada».

| Hallazgo | Estado actual | Cambio y prueba permanente |
| --- | --- | --- |
| B4-01 | **Corregido; regresión API/DB aprobada.** | `backend/app/api/v1/routers/inventory_putaway_groups.py` reevalúa requisitos para cada resultado conforme cambia el remanente. `backend/tests/e2e/test_inventory_block4_closure.py::test_group_putaway_uses_split_requirements_for_each_result` cubre divisiones a dos destinos para una recepción histórica y una nueva. |
| B4-02 | **Corregido; regresión API/DB aprobada.** | `backend/app/infrastructure/repositories/inventory_repository.py` devuelve la HU con metadatos de liberación después de medir. `test_measurement_response_matches_list_with_label_and_retaceo_blockers` comprueba por HTTP igualdad con el listado y conserva etiqueta/retaceo pendientes. |
| B4-03 | **Corregido; regresión de componente aprobada.** | `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte` notifica confirmación exitosa; `HandlingUnitsPanel.svelte` recarga elegibilidad respetando filtros. El test cubre fallo/reintento y que retaceo pendiente no desaparezca. |
| B4-04 | **Corregido; comportamiento del panel aprobado.** | `frontend/src/routes/(app)/warehouses/[id]/+page.svelte` pasa elegibilidad de preparación separada de `canTransfer`; el despacho completo permanece restringido a matriz. El test de `HandlingUnitsPanel` prepara fracción sin mostrar despacho completo. Falta probar página/panel con perfil real de sucursal en navegador/API aislada. |
| B4-05 | **Corregido; regresión de página aprobada.** | `frontend/src/routes/(app)/inventory/kardex/+page.svelte` conserva la página aplicada al reintentar. `frontend/tests/unit/InventoryKardexPage.test.ts` cubre página 1 → fallo de página 2 → reintento de página 2 preservando período. |

### Ejecuciones nuevas del 15/10/2026

- API + PostgreSQL aislado: `pytest -q tests/e2e/test_inventory_block4_closure.py` — **3 aprobadas en 40.80 s**, destino `erp_db_test`.
- Interfaz focalizada: `vitest run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts tests/unit/InventoryKardexPage.test.ts` — **21 aprobadas en 7.72 s**.
- Unitarias backend enfocadas: `pytest -q tests/unit/test_inventory_capacity.py tests/unit/test_inventory_putaway_group_schema.py` — **39 aprobadas en 10.19 s**.
- `svelte-check --tsconfig ./tsconfig.json` — **0 errores, 0 advertencias**. ESLint, Prettier `--check`, Ruff `check`/`format --check`, build frontend y `git diff --check` también pasaron.
- `alembic heads` y `alembic current` de la base de prueba indican **0083 (head)**; no se agregó migración para estos cinco arreglos.

No se modificó `erp_db`. La prueba de navegador solicitada por el contrato se omitió porque la API disponible en el puerto `8000` apunta a esa base operativa, y la UI del puerto `5173` la consume. No se reutilizó esa sesión para operaciones de escritura ni se reinició el stack. La prueba de interfaz con Vitest no sustituye el recorrido autenticado.

### Decisión de cierre

Los cinco defectos reportados están corregidos y las regresiones focalizadas correspondientes pasan. **El bloque 4 no queda aceptado todavía**: falta ejecutar la matriz PostgreSQL completa (valores exactos, rollback de segunda asignación, alcance/revocación, concurrencia, reconciliación, lotes/cortes y migración histórica con datos ficticios) y el recorrido de navegador autenticado con perfiles global y de sucursal. El HS-200 y la colocación física siguen siendo comprobaciones de hardware separadas.

## Revisión de las correcciones de Luna — 15/10/2026

Se revisaron las correcciones contra `prompt-luna-cierre-inventario-bloque-4.md` y el contrato A–F original. Esta revisión modifica únicamente documentación y evidencia de pruebas; no corrige aún los dos problemas siguientes ni modifica datos operativos.

### B4-R01 · P1 · Una confirmación demorada mezcla las etiquetas de dos unidades

**Lugar:** `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte:449–460`. El cierre permitido durante confirmación está en líneas 149–167 y 511; la impresión combina la unidad seleccionada y la vista previa en líneas 292–295 y 342–368.

**Reproducción determinista en componente:** abrir la unidad A, confirmar colocación dejando pendiente la respuesta, cerrar el diálogo, abrir B y esperar sus datos, resolver entonces la confirmación de A. El QR continúa siendo de B, pero la vista previa pasa a mostrar el producto A y «Etiqueta vigente confirmada como colocada». La prueba observó `qrBelongsToB=true`, `productA=true`, `productB=false`, `confirmationShown=true`.

La operación conserva `unit` y `preview` de A antes del `await` y después sobrescribe el estado sin comprobar la sesión de diálogo vigente. Las secuencias existentes protegen las cargas de vista previa, pero no esta confirmación. Por inspección, imprimir después de esta mezcla utiliza el producto/lote de A junto con el código y QR de B; no se ejecutó impresión física.

**Corrección requerida:** asociar éxito, error y finalización a la identidad vigente de unidad/sesión/contexto. Una respuesta de A no debe modificar ni bloquear la vista de B. Notificar al padre la mutación exitosa sin trasladar datos de A al diálogo nuevo; conservar idempotencia. Convertir esta sonda en regresión permanente e incluir cierre, reapertura y fallo tardío.

### B4-R02 · P2 · Una recarga anterior sobrescribe una medición guardada

**Lugares:** `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:197–198`, `:741–749` y `:834`.

**Reproducción determinista en componente:** iniciar verificación de medidas; mientras está pendiente, pulsar «Actualizar». El listado obtiene el estado todavía pendiente, pero la carga paralela de ubicaciones demora. Finaliza la medición y se muestra el éxito; después termina la carga de ubicaciones. `loadData` vuelve a colocar el listado anterior y la unidad reaparece como «Medición pendiente». La prueba observó `verified=false`, `pending=true` al finalizar ambas respuestas.

La secuencia de lectura diferencia cargas entre sí, pero la respuesta de medición no invalida lecturas iniciadas antes de su éxito. El dato guardado en servidor no se revierte; la pantalla vuelve a presentar un requisito desactualizado y obliga a recargar o medir otra vez.

**Corrección requerida:** coordinar lecturas y mutaciones mediante identidad/secuencia o una recarga posterior coherente, de forma que una respuesta anterior no sustituya el resultado guardado. Proteger también cambios de bodega/contexto y desmontaje. Añadir la regresión permanente con promesas controladas, sin depender de tiempos arbitrarios.

### Cumplimiento del encargo después de revisar el código

| Hallazgo original | Resultado revisado | Expectativa todavía sin demostrar |
| --- | --- | --- |
| B4-01 | El reparto completo 1 + 3 funciona para recepción histórica y nueva; ambas partes quedan en cuarentena. | Conservación de valor con valoración activa, la cadena completa y caso de unidad íntegra elegible conforme a la matriz. |
| B4-02 | La respuesta HTTP de medición incluye origen y los pendientes de etiqueta/retaceo, igual que el listado. | Robustez del panel frente a lectura atrasada: B4-R02 sigue abierto. |
| B4-03 | La confirmación exitosa notifica al padre y recarga los pendientes; error/reintento cubiertos. | B4-R01 y recorrido medir → imprimir → confirmar → cerrar → liberar; preservación de filtros/selección durante la secuencia. |
| B4-04 | La página separa correctamente `canPrepareSplit` de `canTransfer`; mantiene `inventory:move` y permite sucursal apta. | La prueba existente pasa `canPrepareSplit=true` a un panel aislado. Falta montar página/panel con bodega no central, ausencia de permiso y bodega no apta, como exige el encargo. No se necesita inventar otro permiso. |
| B4-05 | La prueba demuestra consultas de páginas `[1, 2, 2]` y el mismo período tras un fallo. | Cambios de empresa/sucursal/permisos durante fallo o petición y desmontaje. La prueba de cambio de fechas existente es del Kardex físico. |

La aceptación E–F sigue pendiente: cadena integrada, importes PostgreSQL exactos, rollback de grupo en segunda asignación, alcance/revocación, concurrencia, conciliación, lotes/cortes y migración con datos históricos ficticios; además del navegador con API real aislada. No son requisitos nuevos. Que el servicio habitual use `erp_db` explica por qué no debe usarse para las pruebas, pero no demuestra un impedimento para preparar la API/frontend aislados y puertos libres que el encargo ya autoriza. La entrega anterior no documenta un intento fallido de preparar ese entorno.

### Evidencia nueva de esta revisión

| Ejecución | Resultado |
| --- | --- |
| `pytest -q --tb=short --show-capture=no tests/e2e/test_inventory_block4_closure.py` | **3 aprobadas en 35.27 s**, Python 3.12.15. Antes de recolectar se verificaron ambos DSN: host `db`, puerto `5432`, base `erp_db_test`. |
| `node node_modules/vitest/vitest.mjs run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts tests/unit/InventoryKardexPage.test.ts` | **21 aprobadas en 6.61 s**, ejecutadas por el revisor frontend independiente. |
| `node node_modules/vitest/vitest.mjs run tests/unit/InventoryBlock4ReviewProbe.test.ts` | **2 fallos funcionales reproducidos en 4.40 s**, correspondientes a B4-R01 y B4-R02. No son fallos de arranque ni de fixtures. |

Fuente de sondas y logs en `tmp/inventory-block4-corrections-review-20261015/`: `InventoryBlock4ReviewProbe.test.ts`, `frontend-probes.log` y `backend-regressions.log`. La sonda se ejecutó mediante una copia temporal en `frontend/tests/unit`; se comprobó igualdad SHA256 y se retiró esa copia para no dejar pruebas temporales recolectadas accidentalmente. Para repetir, copiar la fuente archivada a ese mismo destino y ejecutar el comando indicado.

No se repitieron build/lint/tipos en aquella revisión porque no modificó código funcional. Los resultados allí registrados son históricos. Las sondas frontend usaron respuestas de API controladas; no sustituyen navegador autenticado ni prueba física de lector/etiquetas.

## Cierre de correcciones finales — 15/10/2026

Se ejecutó `docs/prompt-luna-correcciones-finales-inventario-bloque-4.md`. Esta sección actualiza el estado de la revisión anterior; no borra sus reproducciones ni presenta sus resultados históricos como ejecuciones actuales.

### Resolución de B4-R01 y B4-R02

| Hallazgo | Corrección | Regresión permanente |
| --- | --- | --- |
| B4-R01 — confirmación tardía mezcla la etiqueta de A con el QR de B | `HandlingUnitLabelDialog.svelte` vincula confirmaciones a unidad, sesión de diálogo y contexto. Éxito, error y `finally` verifican identidad vigente; cerrar/reabrir la misma HU o cambiar contexto inicia una sesión separada. Una confirmación exitosa solo notifica al padre en el contexto que la originó. Los intentos de impresión/confirmación mantienen sus claves idempotentes y la prueba cubre impresión de B mientras A sigue pendiente. | `HandlingUnitsPanel.test.ts`: respuesta A posterior a abrir B, error tardío, cierre/reapertura de la misma unidad, cambio de contexto, desmontaje y B operando mientras A sigue pendiente. |
| B4-R02 — listado anterior sustituye una medición ya guardada | `HandlingUnitsPanel.svelte` invalida lecturas iniciadas antes de la mutación, aplica el payload enriquecido del servidor y separa el estado de operaciones por contexto/secuencia. Cambios de alcance y desmontaje no permiten que una respuesta obsoleta sustituya la sesión actual. | `HandlingUnitsPanel.test.ts`: lectura anterior con ubicaciones demoradas, contexto distinto, error de recarga tras medir y desmontaje. |

### Ejecuciones actuales

Todas las pruebas de base de datos se ejecutaron en serie contra `erp_db_test` (host `db`, puerto `5432`); nunca se ejecutó una escritura de prueba contra `erp_db`.

| Validación | Resultado |
| --- | --- |
| Frontend: `HandlingUnitsPanel.test.ts`, `InventoryKardexPage.test.ts`, `WarehouseHandlingUnitsIntegration.test.ts`, `InventoryKardexContext.test.ts` | **41 aprobadas / 4 suites en 5.17 s.** Incluye B4-R01/B4-R02 y las regresiones B4-03/04/05. |
| `svelte-check --tsconfig ./tsconfig.json` | **0 errores, 0 advertencias en 22.77 s.** |
| ESLint en los dos componentes y su suite de regresión | Aprobado en **4.51 s**. |
| Prettier `--check` en esos mismos archivos | Aprobado en **1.15 s**. |
| Backend unitario: valoración, esquema de ubicación agrupada y Kardex | **36 aprobadas en 9.42 s.** |
| PostgreSQL: valoración, Kardex, idempotencia y preparación de fracciones | **5 aprobadas en 16.69 s.** Confirma `$8` al remanente y `$12` a salidas; devolución con costo `$75`, crédito `$100` y diferencia `$25`; también páginas, valores desconocidos, alcance de empresa y recepción parcial. |
| E2E API/PostgreSQL: `test_inventory_block4_closure.py` | **6 aprobadas en 63.18 s.** Incluye medición/listado, recepción histórica/nueva, ubicación 20+30, rechazo 51, rollback al fallar la segunda asignación, una carrera concurrente de mismo cuerpo/clave con un movimiento y un replay, y migración con datos ficticios 0082→0083. |
| Migración actual | `alembic heads` y `alembic current` en la base de prueba: **0083 (head)**. El test de migración bajó a 0082 con una recepción ficticia existente, verificó datos preservados, volvió a subir a 0083 y comprobó que la recepción histórica queda exceptuada mientras las nuevas requieren confirmación de etiqueta. |
| Navegador con API/frontend aislados | Verificado antes de la reconstrucción de la base: perfil de sucursal y perfil global, listado real, medición, liberación a disponible y apertura en pestaña nueva de la ficha pública sin login, con origen de compra y movimientos. El recorrido no llegó a preparar/despachar 4+6 ni a confirmar físicamente una etiqueta. |
| Build | `vite build` aprobado en **27.70 s**. El bundler avisó que `jsbarcode` no tiene import default usado durante SSR; el adaptador automático tampoco detectó destino de despliegue. Ninguna advertencia impidió compilar. |
| `git diff --check` | Aprobado; solo avisos CRLF/LF en dos pruebas preexistentes de solicitudes de compra. |

`pnpm` intentó reemplazar `node_modules` sin terminal interactiva y se detuvo con `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`. Para no modificar las dependencias existentes, las comprobaciones frontend se ejecutaron con los binarios locales de `node_modules/.bin`. Ruff no está instalado en el runtime backend disponible; no se instaló una dependencia ajena al encargo. Python `compileall` pasó para los archivos de prueba Python editados.

### Brechas de aceptación que siguen abiertas

- La prueba 20+30 asigna dos fracciones de **una misma línea/unidad recibida** a dos destinos. No construye dos detalles de compra distintos del mismo artículo. El rollback de la segunda asignación sí se fuerza y verifica en movimientos, balance, HU y auditoría.
- La concurrencia aprobada cubre dos peticiones simultáneas con la misma clave/cuerpo. No cubre escritores con claves distintas ni medición, conciliación o retaceo compitiendo en paralelo.
- No se probó el replay después de mover una HU con acceso revocado, todos los perfiles/alcances por sucursal, ni la ausencia de importes globales en JSON para el conjunto completo de endpoints.
- El SQL cubre páginas, conteos, valores desconocidos y aislamiento de empresa; empates de fecha, lotes, movimientos anteriores al período, zona horaria/corte inicial y conciliación mientras se escriben movimientos siguen sin una regresión integral.
- El navegador real aislado no completó el flujo completo recepción → retaceo → ubicación → etiqueta confirmada → fraccionamiento → despacho → recepción parcial → Kardex/conciliación. Tampoco se probó el HS-200, impresión física ni colocación de etiqueta.
- El health check del backend conserva una expectativa de revisión 0043 aunque el esquema de prueba llega a 0083; las rutas API usadas en estas pruebas sí respondieron. Esa discrepancia de diagnóstico no se corrigió en este alcance.

**Decisión vigente:** B4-R01/B4-R02 y las seis pruebas E2E añadidas quedan corregidos/verificados, pero no se acepta el bloque 4 completo porque aún no pasan o no se han ejecutado todas las filas de la matriz E–F original. No declarar el software cerrado hasta cubrir las brechas anteriores; hardware permanece como comprobación separada.

## Revisión independiente posterior a la entrega final de Luna — 15/10/2026

### Resultado

Las correcciones de confirmación de etiqueta (B4-R01) y medición (B4-R02) cumplen los casos reproducidos. Se revisaron sus controles de identidad y las regresiones permanentes, incluyendo apertura de B mientras A confirma, reapertura de la misma HU, contexto, desmontaje y lectura anterior con ubicaciones demoradas. La integración de página/panel de sucursal y el reintento de página 2 del Kardex también tienen regresiones que pasan. **Esto no cierra el bloque completo.**

### B4-R03 · P2 · Revocar enlaces de A elimina el QR de B al llegar una respuesta tardía

**Lugar:** `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte:299–310`, función `revokePublicTraceLinks`.

**Reproducción determinista:** abrir A; pulsar «Invalidar enlaces públicos» y «Invalidar enlaces»; mantener pendiente la petición; cerrar y abrir B; esperar a que aparezcan producto y QR de B; resolver la revocación de A. La pantalla de B pierde su QR y el enlace «Abrir ficha», y muestra «Se invalidaron 2 enlace(s) QR» correspondiente a A. La petición enviada identifica correctamente A; la sonda demuestra contaminación de la interfaz, no una revocación de B en el servidor.

**Causa:** esta operación escribe `publicTraceHref`, `qrDataUrl`, mensaje, error y estado ocupado después del `await` sin comprobar unidad, sesión ni contexto. A diferencia de la confirmación ya corregida, tampoco se restablece `revokingTraceLinks` al abrir otra sesión.

**Corrección necesaria:** aplicar a la revocación la identidad de unidad/sesión/contexto vigente, protegiendo éxito, error y `finally`; permitir operar B aunque la revocación de A esté pendiente. Conservar la revocación real que ya se envió al servidor. Añadir regresiones de éxito/error tardío, B operando mientras A sigue pendiente, reapertura, cambio de contexto y desmontaje. No resolverlo ocultando el botón ni bloqueando el cambio de unidad.

Fuente y resultado de la sonda: `tmp/inventory-block4-final-review-20261015/InventoryBlock4FinalReviewProbe.test.ts` y `frontend-probe.log`. Para repetir, copiar la fuente a `frontend/tests/unit/InventoryBlock4FinalReviewProbe.test.ts` y ejecutar Vitest para ese archivo. La copia temporal se retiró tras comprobar igualdad SHA256 con el archivo conservado. No se modificó código funcional durante esta revisión.

### Aceptación pendiente contrastada con las pruebas

- **Origen de dos detalles:** `test_group_putaway_uses_split_requirements_for_each_result` crea una sola recepción/HU de 50 y la divide en 20+30. No demuestra el requisito de dos detalles de compra distintos del mismo artículo ni su trazabilidad separada. El rechazo de 51 y el rollback forzado sí tienen cobertura.
- **Concurrencia y alcance:** la carrera existente usa la misma clave y cuerpo en dos sesiones. Siguen pendientes escritores distintos, interacción con medición/movimientos/retaceo, conciliación durante escritura, replay después de mover HU y revocar acceso, y ausencia de importes globales en los JSON de perfiles restringidos.
- **Lecturas y cadena real:** la prueba SQL del Kardex usa dos entradas; no cubre conjuntamente empates, lotes, saldo anterior, corte y límites de fecha local. Sigue faltando el recorrido completo con API real y perfiles global/sucursal desde recepción y retaceo hasta etiqueta, preparación 4+6, despacho, recepción parcial y Kardex/conciliación, con los cambios de contexto y variantes visuales ya solicitados.

Estas son comprobaciones pendientes del encargo existente, no defectos funcionales nuevos demostrados ni una ampliación del alcance. La impresión, colocación física y lector HS-200 se mantienen separados de la aceptación de software.

### Ejecuciones de esta revisión

| Comando / prueba | Resultado nuevo |
| --- | --- |
| Binario local `vitest.cmd run` sobre `HandlingUnitsPanel`, `InventoryKardexPage`, `WarehouseHandlingUnitsIntegration` e `InventoryKardexContext` | **41 aprobadas, 4 suites, 5.32 s.** |
| `pytest -q --tb=short --show-capture=no tests/e2e/test_inventory_block4_closure.py` | **6 aprobadas, 68.52 s.** Una advertencia de constante HTTP 422 obsoleta. |
| `pytest -q --tb=short --show-capture=no` sobre `test_inventory_valuation_repository.py`, `test_inventory_kardex_repository.py`, `test_inventory_movement_idempotency.py` y `test_inventory_split_prepare_route.py` | **5 aprobadas, 17.95 s.** |
| Sonda de revocación tardía de A al abrir B | **1 fallo funcional, 4.39 s.** El QR de B desaparece y se muestra el mensaje de A. |
| `alembic current` con DSN de prueba; `git diff --check` | **0083 (head)**; sin errores de espacios. Avisos CRLF/LF en dos pruebas preexistentes de solicitudes. |

Antes de las pruebas se leyeron los fixtures destructivos y se verificaron ambos DSN: host `db`, puerto `5432`, base **`erp_db_test`**. Las suites de base se ejecutaron en serie. Los servicios operativos no se reiniciaron y no se usó `erp_db`. No se repitieron build/lint/tipos ni navegador en esta revisión; los resultados correspondientes de la entrega anterior siguen siendo históricos.

**Lo que debe completar Luna:** corregir B4-R03 y demostrar las filas pendientes de la matriz E–F con evidencia por requisito. No necesita rehacer R01/R02 ni abrir un nuevo bloque funcional. La aceptación queda pendiente hasta completar ambos puntos.
## Cierre R03 y matriz original E — 16/10/2026

Esta sección complementa el historial previo y registra el resultado del encargo R03. Los estados reflejan evidencia concreta; “parcial” no se cuenta como aceptación.

### B4-R03 — respuesta tardía al invalidar enlaces QR

**Resultado: corregido y verificado con regresiones permanentes.** Antes, una respuesta asíncrona de revocación de la unidad A podía escribir QR, enlace, mensaje y estado ocupado sobre el diálogo de la unidad B que ya estaba abierto. La petición seguía dirigida a A; el defecto demostrado era contaminación de la interfaz, no revocación de B en el servidor.

La corrección asocia éxito, error y finalización a la unidad, sesión y contexto actuales, y restablece la actividad al iniciar otra sesión. B puede operar mientras A sigue pendiente; la operación enviada para A conserva su efecto en el servidor, pero no modifica la vista nueva. Se conserva la confirmación explícita de etiqueta y el flujo de QR/impresión.

La regresión permanente está en frontend/src/lib/features/inventory/components/HandlingUnitsPanel.test.ts: éxito y error tardíos, operación simultánea de B, reapertura de A, cambios de contexto/permisos y desmontaje; revisa QR, enlace, producto, mensajes y estado ocupado. La suite pasó junto con las otras pruebas de interfaz del cierre.

### Correspondencia con cada fila de la matriz E original

| # | Caso de aceptación | Estado | Evidencia y límite |
| --- | --- | --- | --- |
| 1 | HU de 10 con revisión anterior; dividir 4 + 6, medir, etiquetar y liberar ambas partes | **Verificado por evidencia complementaria API/SQL + navegador** | `test_new_receipt_split_invalidates_label_on_both_grouped_results` verifica que la recepción nueva de 10 invalida la etiqueta anterior en las dos fracciones 4+6 y exige medición/etiqueta nueva; el recorrido aislado midió, imprimió y confirmó colocación simulada antes de liberar ambas. `test_prepare_split_route_replays_conflicts_and_rolls_back_atomically` activa valoración sintética y conserva 10 unidades/$100/promedio $10 a través de la preparación 4+6. El importe del recorrido navegador permanece desconocido porque esa empresa no tenía corte aprobado; la conservación monetaria se prueba en la integración SQL separada. |
| 2 | Preparar fracción, despachar 4 y conservar 6; operación idempotente, auditada y sin disponibilidad con revisión inválida | **Verificado en software** | test_prepare_split_route_replays_conflicts_and_rolls_back_atomically, las pruebas de idempotencia de grupo/movimiento y el recorrido de navegador comprobaron el despacho de 4 y la conservación de 6. F se cerró después con una recepción independiente iniciada desde el perfil de sucursal. |
| 3 | Recibir 4 de 10 en tránsito; 4 en cuarentena y 6 continúan en tránsito | **Verificado por API/SQL; recepción por navegador verificada con perfil sucursal** | `test_partial_branch_transfer_preserves_remainder_and_records_receipt_count` comprueba 4 recibidas, 6 en tránsito, origen y ausencia de doble entrada. En navegador, el perfil limitado de Jiquilisco recibió 4 cajas de una HU pendiente; la UI mostró 0 pendientes y PostgreSQL confirmó la HU en cuarentena. |
| 4 | HU completa con etiqueta/retaceo pendientes puede ubicarse en cuarentena; mostrar bloqueos, no liberar por otra ruta y conservar excepción histórica | **Verificado en API/SQL** | `test_pending_label_and_retaceo_can_only_be_put_away_in_quarantine` confirma ambos bloqueos, permite ubicación en cuarentena, intenta la liberación por movimientos y comprueba el rechazo 409 sin cambio de saldo. La excepción histórica se verifica en la migración 0082→0083. |
| 5 | Retaceo tardío: 10/$100, salida 6, gasto $20 → $8 remanente y $12 salidas, cantidad cero, sin duplicar | **Verificado en PostgreSQL** | test_postgres_late_retaceo_and_supplier_return_conserve_exact_value confirma los importes, sin movimiento físico adicional y con reintento idempotente. |
| 6 | Compra 10 a $10 + 10 a $20; salida 15, devolución 5, crédito $100 | **Verificado en PostgreSQL** | La misma prueba confirma existencia y valor cero, costo de devolución $75, crédito $100, diferencia $25 y que no se descuenta stock dos veces. |
| 7 | Cambiar fechas y empresa/sucursal durante una búsqueda; descartar respuestas viejas y reintentar sin heredar filtros/valores | **Verificado con regresiones deterministas de UI** | `InventoryKardexPage.test.ts` descarta una respuesta física al cambiar fecha, no conserva el saldo del producto anterior y reintenta la misma página valorada con el mismo período. `InventoryKardexContext.test.ts` descarta éxito y error tardíos al cambiar sucursal, empresa o permiso, y cubre desmontaje. El efecto de contexto limpia búsqueda, selección e importes antes de cargar el nuevo alcance. La prueba de carrera usa promesas controladas; el comportamiento de navegación manual está registrado aparte en la evidencia F. |
| 8 | Kardex paginado con empates, lote, movimientos previos y corte de día de El Salvador | **Verificado en PostgreSQL** | test_kardex_sql_orders_timestamp_ties_filters_lot_and_uses_local_day_cutoffs comprueba orden determinista, tres páginas, saldos continuos, totales del filtro, lote y límite local. InventoryKardexPage también prueba que la UI pagina bodegas de 100 en 100 para respetar el máximo de API. |
| 9 | Datos previos al corte y valoración inactiva: desconocido no equivale a cero | **Verificado en PostgreSQL** | test_kardex_sql_reads_pages_totals_unknown_values_and_company_scope y test_reconciliation_waits_for_atomic_receipt_and_valuation_commit mantienen cantidades físicas conocidas y valores/costos nulos cuando no hay apertura aprobada. |
| 10 | Dos detalles de compra del mismo artículo: 20 + 30, aceptar 50 y rechazar 51; rollback total si falla la segunda asignación | **Verificado en API/SQL** | test_group_putaway_preserves_two_purchase_detail_origins crea dos detalles de orden/compra distintos para el mismo SKU, conserva lote/detalle/HU/movimiento por origen, rechaza 51 y prueba replay/conflicto/permisos. test_group_putaway_rolls_back_first_allocation_when_second_fails verifica rollback de HU, balances, movimientos y auditoría de éxito. |
| 11 | Replay tras mover HU: mismo resultado autorizado, otro cuerpo conflicto, otro alcance o permiso revocado denegado | **Verificado en API/SQL** | test_group_putaway_preserves_two_purchase_detail_origins reproduce el replay con HU ya movidas, valida el cuerpo conflictivo y deniega perfil sin permiso y perfil sucursal revocado. |
| 12 | Otra empresa y perfil sucursal sin permiso de valoración; JSON y replays no exponen importes globales | **Verificado en los endpoints y replays aplicables** | `test_branch_kardex_profile_cannot_fetch_company_valuation_json` revisa recursivamente el JSON de la consulta física y el listado/detalle de HU; el perfil sin valoración recibe 403 en valoración y conciliación y otro alcance de empresa queda denegado. `test_group_putaway_preserves_two_purchase_detail_origins` comprueba el replay autorizado con perfil de sucursal sin valoración y revisa recursivamente que su respuesta no contenga campos financieros. La autorización del replay también se vuelve a validar tras revocar el acceso a la sucursal. |
| 13 | Sesiones concurrentes de grupo, movimiento, medición y retry sin deadlock/doble aplicación | **Verificado para las carreras implementadas** | test_concurrent_group_movement_and_measurement_are_serialized sincroniza grupo, movimiento y medición con barrera y timeout; test_concurrent_group_retry_applies_once_and_replays comprueba un solo movimiento, auditoría y HU bajo retry concurrente. |
| 14 | Conciliación durante recepción, traslado y aplicación de retaceo | **Verificado en PostgreSQL con barreras y timeout** | `test_reconciliation_waits_for_atomic_receipt_and_valuation_commit` prueba una recepción atómica con valor aún desconocido. Los dos casos parametrizados de `test_reconciliation_waits_for_transfer_or_landed_cost_commit` mantienen bloqueada la conciliación hasta confirmar el traslado o aplicar el retaceo: tras el commit se observa cantidad 10 una sola vez y el valor coherente ($100 después del traslado; $120 después del ajuste de $20), sin diferencia física/valorada. |
| 15 | Migración histórica 0082→0083 y cabeza real | **Verificado en base de prueba** | test_0082_to_0083_preserves_legacy_receipt_rows prueba recepción histórica y nueva; consulta real de Alembic al cierre: 0083 (head) en erp_db_test. |

La cobertura financiera está separada de la cadena de API/UI. No se aprueba inventario inicial real ni se infiere un valor cuando la valoración está inactiva.

### F — recepción desde perfil de sucursal en navegador

**Verificado el 16/10/2026 contra la API/frontend aislados en `8001/5174`.** El perfil sintético limitado a Pastelería Lorena Jiquilisco consultó `ITK-IT-WR-b2`, mostró una recepción pendiente de 4 cajas para `HU-2849B778010749BF` y confirmó la cantidad contada desde la interfaz. La UI reportó el registro de 4 cajas, mostró 0 unidades pendientes y mantuvo la instrucción de revisar/ubicar desde Inventario. PostgreSQL de `erp_db_test`, consultado en modo de solo lectura, confirmó cantidad base 4 y estado `quarantine`. El rol sintético necesitó `warehouses.view`; el permiso se concedió únicamente en `erp_db_test` y el perfil se desactivó al finalizar. Los pasos y resultados observados están en `tmp/inventory-block4-acceptance-20261016/browser-acceptance.md`.

Esto completa la aceptación de software del bloque en el alcance de E–F. El usuario confirmó después que el escáner HS-200, la impresión física y la colocación física no son requisitos del proyecto: se excluyen de los pendientes, sin presentarlos como pruebas realizadas.

## Recomprobación final solicitada por el usuario — 16/10/2026

Se contrastó el último encargo (`prompt-luna-r03-y-aceptacion-inventario-bloque-4.md`) con el código, las regresiones permanentes y el expediente de navegador. Se revisaron los controles de sesión/contexto de R03, el contexto de permisos que transmite el panel, los dos detalles de compra 20+30, rollback, autorización de replays, privacidad del JSON, concurrencia y los importes de valoración. No se reprodujo un bloqueo funcional nuevo del alcance encargado.

### Pruebas repetidas en esta revisión

| Verificación | Resultado final |
| --- | --- |
| Cuatro suites de interfaz: panel/etiqueta, Kardex, contexto y página de almacén | **45 aprobadas; 5.04 s.** |
| E2E `test_inventory_block4_closure.py` | **10 aprobadas; 106.85 s.** Aviso no bloqueante por nombre obsoleto de constante HTTP 422. |
| Ejecución conjunta de Kardex, valoración, movimientos y preparación fraccionada | **9 aprobadas; 18.68 s.**, después de corregir el aislamiento descrito abajo. |

Las pruebas de datos se ejecutaron secuencialmente contra `db:5432/erp_db_test`, después de leer las fixtures y comprobar ambos DSN. No se modificó `erp_db` ni se reiniciaron los servicios operativos. La evidencia previa de navegador fue revisada, no repetida en esta recomprobación. Tampoco se volvieron a ejecutar build, tipos ni lint de frontend, cuyo código no cambió.

### Detalle encontrado y corregido en las pruebas

Las cuatro suites SQL pasaban por separado, pero al ejecutarlas juntas las pruebas concurrentes de Kardex dejaban una apertura valorada confirmada sobre la empresa canónica del seed. La siguiente suite intentaba crear otra apertura para esa empresa y fallaba por clave duplicada; después aparecían errores derivados del bucle asíncrono. La primera ejecución conjunta dio **5 aprobadas y 4 fallidas**.

Se corrigió únicamente `backend/tests/integration/test_inventory_kardex_repository.py`: cada caso que necesita confirmar transacciones concurrentes crea su propia empresa, sucursal y producto ficticios. Mantiene las sesiones independientes, locks, barreras y comprobaciones financieras. Durante el ajuste se respetó la inscripción automática de unidades de la migración 0023, evitando insertar una unidad empresarial ya creada por su trigger. La misma ejecución conjunta terminó en **9/9**; no se cambiaron reglas de negocio ni se ocultaron fallos mediante skips.

### Decisión para la entrega

**El encargo funcional de Luna queda aceptado y no necesita otro bloque ni otro prompt para cerrarse.** Al usuario le queda su recorrido manual de aceptación: recepción/retaceo, ubicación y etiquetas simuladas, fraccionamiento/despacho/recepción de sucursal, consulta de ficha QR y Kardex. Generar/ver la etiqueta en software y simular su confirmación es suficiente para el proyecto teórico; no se exige impresora, mercancía etiquetada ni escaneo físico.

Al cierre de esa revisión permanecía la observación técnica de que el health check comparaba el esquema con `0043`; ese estado histórico quedó resuelto al reparar el entorno habitual. La aceptación de este bloque no equivale a certificar todo el ERP ni a aprobar una apertura contable real.

## Corrección posterior del entorno habitual — 16/10/2026

La revisión anterior había verificado la aceptación funcional con `erp_db_test`, pero no había contrastado la revisión Alembic de la base usada por `localhost:5173`. El nuevo encargo identificó ese desfase: `erp_db` estaba en **0078** mientras el código y `erp_db_test` estaban en **0083**. Esa diferencia explicaba los 500 de Retaceo, Valoración, Traslados y Kardex; no era un defecto de etiqueta ni evidencia de pérdida de existencias.

Se respaldó `erp_db`, se restauró el archivo en `erp_db_inventory_repair_20261016`, se ensayaron las migraciones 0079–0083 y se compararon cantidades antes/después. Con el ensayo aprobado se actualizó la base habitual a 0083. Compras (16), detalles (21), retaceos (14), HU (15), movimientos (28), líneas (34) y saldos (22 filas / 2,883 unidades) quedaron iguales. No se creó valoración inicial ni se fabricaron costos o movimientos.

El health check ahora consulta las cabezas Alembic del código; Retaceo y Traslados distinguen carga fallida de resultado vacío. En `localhost:5173` se confirmaron la lista/detalle de Retaceo, la vista de Valoración sin apertura, Traslados con datos y el Kardex con 9 movimientos de `PRD-EMP-009`. `/health/ready` terminó `ok`; no se observaron errores de esquema en logs del backend durante la revisión. Las pantallas se comprobaron sin escrituras.

**Estado actual:** la aceptación de software del bloque 4 sigue completa dentro de los límites E–F documentados y el entorno habitual también está migrado y disponible. El HS-200, impresión y colocación físicas siguen excluidos como requisitos por decisión del usuario; no se presentan como pruebas hechas. No hace falta otro prompt para Luna para este problema.

El respaldo, el ensayo restaurado, los valores de conservación, las pruebas y el procedimiento de actualización están en [reparacion-entorno-inventario-0078-0083.md](reparacion-entorno-inventario-0078-0083.md).

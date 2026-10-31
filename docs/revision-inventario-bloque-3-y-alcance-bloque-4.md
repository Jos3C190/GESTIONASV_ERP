# Revisión del bloque 3 y alcance del bloque 4 de Inventario

Fecha: 14/10/2026. Revisión del código local contra `prompt-luna-inventario-bloque-3.md`.

## Dictamen

**El bloque 3 cumple una parte importante del encargo, pero todavía no cumple su aceptación completa.** Ya existen el Kardex físico, el valorado, la conciliación, DTOs, filtros, controles de alcance y confirmación de etiquetas. Encontré defectos reproducibles en la continuación del fraccionamiento, en los desgloses financieros y en el cambio de período. Además, siguen faltando pruebas integradas exigidas por el contrato, algunas todavía sin escribir.

El siguiente bloque será **cierre operativo, coherencia del Kardex y aceptación integrada**. No conviene iniciar otro módulo hasta terminar este recorrido. Este bloque 4 pertenece a la ampliación de Inventario; es distinto de `bloque-4-retaceo-costos-reales-y-comprobantes.md` del flujo anterior de Compras.

Esta revisión produce documentación y evidencia de pruebas. No modifica código funcional, políticas de costos, migraciones ni datos de la empresa.

## Cumplimiento del encargo anterior

| Requisito | Resultado observado |
| --- | --- |
| A1: fracciones con identidad propia, etiqueta vigente y recorrido de revalidación | Parcial. Se bloqueó la división insegura y se invalida la revisión anterior, pero falta una continuación utilizable para ciertas fracciones. Ver B3-01. |
| A2: autorización del replay del grupo | Implementada en código: se comprueban las bodegas persistidas y la ubicación actual de las HU antes de devolver el resultado. Falta prueba transaccional y de revocación de alcance. |
| A3: ubicar una HU completa sin etiqueta y conservar cuarentena | El helper contempla la etiqueta pendiente. La UI todavía da un mensaje general y el enlace de continuación lleva a una ficha de consulta. No existe una única regla compartida de elegibilidad entre las rutas. |
| A4: confirmación explícita de etiqueta | Hay pruebas del método de repositorio con dobles de sesión para impresión ajena/ausente, revisión/cantidad obsoleta, replay y conflicto. No equivalen a persistencia ni concurrencia PostgreSQL. |
| B1: ruta Kardex y capas del proyecto | Ruta y DTOs implementados. La consulta nueva quedó concentrada en el router, incumpliendo la separación solicitada. Ver B3-05. |
| B2: historial físico y valorado con alcance | Existen ambas vistas y controles backend; el físico no incluye importes. El valorado omite campos reales del desglose. Ver B3-02. |
| B3: saldos, fechas, paginación, filtros y enlaces | Las consultas contienen reconstrucción desde corte y orden determinista. Falta verificar su SQL con datos reales; se reprodujo una respuesta obsoleta al cambiar fechas. Ver B3-03. |
| B4: conciliación de lectura | Suma balances una sola vez y usa el bloqueo de empresa. No se verificó con una escritura concurrente real. |
| C: aceptación integrada y navegador | Incompleta. Ver B3-04. La nota del crítico UI y los tests unitarios anteriores no sustituyen este recorrido. |

## Hallazgos

### B3-01 — P1: una fracción en cuarentena no tiene acción visible para medirla

Referencias del corte revisado:

- `backend/app/infrastructure/repositories/inventory_repository.py:2927` y `:2951`: al dividir durante ubicación, remanente e hija pueden quedar con `measurement_status="complete"` y `measurement_source="split_estimate"`.
- `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:219`: `canMeasure` solo admite `measurement_status === 'incomplete'`.
- `backend/app/infrastructure/repositories/inventory_repository.py:2733`: el servidor impide liberar una unidad cuya fuente siga siendo `split_estimate`.
- `frontend/src/lib/features/inventory/components/GroupedPutawayPanel.svelte:408`: “Revisar unidad” abre la ficha de trazabilidad, que actualmente solo consulta información.

**Reproducción:** ubicar parcialmente 4 de una HU de 10. La fracción queda en cuarentena y necesita medición propia. Con permiso para verificar, el panel no ofrece “Verificar medidas” porque su estado es `complete`. Intentar liberarla sigue siendo rechazado por el backend. La sonda de componente reprodujo la ausencia del botón.

Además, `_require_labelled_split_in_quarantine` (`inventory_repository.py:96`) rechaza cualquier fraccionamiento de una HU nueva que ya esté disponible y los traslados parciales de esas HU en tránsito. Esto protege la etiqueta, pero no completa la alternativa operativa exigida en A1. Hay que conservar la protección y ofrecer preparación/fraccionamiento trazable, incluyendo qué hacer con una recepción parcial de traslado.

**Cierre requerido:** poder medir tanto hija como remanente estimados; imprimir y confirmar sus etiquetas vigentes; liberarlos y despacharlos desde una ruta visible. Una ficha de solo lectura o un error que pide una acción inexistente no completa el recorrido. Mantener cantidad y valor y la excepción histórica documentada.

### B3-02 — P2: el Kardex descarta el desglose que realmente produce el backend

Referencias:

- `backend/app/domain/entities/inventory_valuation.py:162`: el retaceo tardío emite `cost_delta` por salida afectada.
- `backend/app/infrastructure/repositories/inventory_valuation_repository.py:175`: un crédito de proveedor emite `credit_net`, `inventory_cost` y `cost_difference`.
- `frontend/src/lib/features/inventory/components/ValuedKardexList.svelte:22`: el lector de importes busca `cost_adjustment`, `value_delta`, `inventory_delta` o `amount`; ninguno cubre esos contratos.

**Efecto:** el ajuste de $12 a salidas del ejemplo de retaceo aparece como un guion en el detalle. En un crédito de $100 con salida valorada a $75 no se muestran correctamente los tres importes $100 / $75 / $25. El evento tiene variación de inventario cero, por lo que esa columna no puede reemplazar el desglose comercial.

Las dos sondas usando los campos reales fallaron. El fixture anterior de `KardexLists.test.ts` usa `amount`, que no representa esos eventos y por eso no detectó el problema. No se demostró corrupción del motor de costos: el defecto confirmado está en su presentación.

**Cierre requerido:** un contrato tipado para cada desglose, importes separados con nombres claros y pruebas con el payload real. Diferenciar entrada y salida de cantidad; ajustes y créditos no crean una segunda salida. Condicionar los enlaces documentales al permiso correspondiente; hoy el enlace a retaceo se muestra solo por existir `retaceo_id`.

### B3-03 — P2: el cambio de período valorado admite una respuesta del filtro anterior

Referencias:

- `frontend/src/routes/(app)/inventory/kardex/+page.svelte:231`: `showValued` acepta la respuesta si sigue vigente su número de petición.
- La misma página, `:720`: las fechas de la vista valorada tienen `bind:value`, pero no invalidan la petición ni los datos. Las fechas de la vista física sí llaman a los invalidadores.
- La misma página, `:273`: cambiar empresa/sucursal limpia las consultas principales, pero no cancela el temporizador/búsqueda de artículos ni borra todas las selecciones y nombres asociados.

**Reproducción confirmada:** iniciar la consulta valorada, cambiar “Desde” mientras responde y devolver la respuesta del período original. Los saldos del período anterior se pintan bajo las fechas nuevas. La sonda encontró dos resúmenes de $999 que debían descartarse. También puede quedar una consulta física con fechas visibles cambiadas desde la otra pestaña.

La omisión de invalidación de la búsqueda al cambiar contexto se identificó por lectura de código; no se presenta como un bypass de permisos backend demostrado.

**Cierre requerido:** asociar toda respuesta a empresa, sucursal, artículo, fechas y filtros de su consulta. Invalidar resultados, selecciones y peticiones al cambiar su contexto. Si se conservan resultados anteriores mientras el usuario edita filtros, mostrar expresamente el período aplicado; no mezclarlo con el solicitado.

### B3-04 — Pendiente obligatorio: no están completos los tests transaccionales del contrato

`backend/tests/integration/test_inventory_movement_idempotency.py` contiene dos pruebas de movimientos. No encontré pruebas que ejecuten el grupo completo, sus replays autorizados/revocados, el rollback de la segunda asignación, las consultas SQL de Kardex o las sesiones concurrentes grupo/movimiento/medición. `test_inventory_kardex.py` prueba seis helpers/políticas, no los endpoints y sus consultas.

La falta de un servidor explica que una prueba no se ejecute, pero no reemplaza la escritura de esos casos. Se requieren tanto el código de las pruebas como su ejecución en PostgreSQL desechable y el recorrido autenticado de navegador. La verificación física del lector/impresora seguirá siendo una comprobación distinta del usuario.

### B3-05 — P2: las consultas nuevas no siguen las capas solicitadas

`backend/app/api/v1/routers/inventory_kardex.py` contiene unas 714 líneas: joins, ventanas, reconstrucción de saldos, conciliación y lectura financiera junto con HTTP/autorización. El encargo B1 pedía separar la consulta y reutilizar el acceso a valoración. El endpoint valorado consulta directamente modelos del ledger en vez de delegar la lectura a un puerto/repositorio.

**Cierre requerido:** mover las consultas a infraestructura detrás de un puerto de lectura y los casos de uso a aplicación. El router conserva DTOs, dependencias, contexto autorizado y traducción HTTP. No duplicar el cálculo de costos ni hacer una refactorización general del ERP. Conservar pruebas de contrato de los endpoints después de extraer el código.

## Evidencia de esta revisión

Ejecución nueva desde `frontend`:

```text
node node_modules/vitest/vitest.mjs run tests/unit/InventoryKardexPage.test.ts tests/unit/KardexLists.test.ts src/lib/features/inventory/components/HandlingUnitsPanel.test.ts src/lib/features/inventory/components/GroupedPutawayPanel.test.ts
```

Resultado: **18 pruebas existentes aprobadas, 4 archivos, 4.44 s**.

Se ejecutaron además cuatro sondas temporales sobre los componentes reales con dobles de API:

| Expectativa de la sonda | Resultado |
| --- | --- |
| HU `complete/split_estimate` en cuarentena permite verificar medidas | Falla: falta el botón. |
| Retaceo muestra `cost_delta=12` en el desglose | Falla: el importe no se representa. |
| Crédito muestra `credit_net=100`, `inventory_cost=75`, `cost_difference=25` | Falla: falta la presentación de esos importes. |
| Respuesta del período anterior se descarta después de cambiar fechas | Falla: se muestran dos saldos del período anterior. |

Las sondas terminaron por aserciones de esas expectativas, no por errores de importación. Sus archivos temporales `.test.ts` se retiraron de la suite; no se dejaron nuevas pruebas fallando ni cambios funcionales. Sus cuerpos y resultados JSON/log están en `C:\Developer\GESTIONASV_ERP\tmp\inventory-block3-audit-20261014\`. Para repetirlas, usar los fixtures de los tests existentes y convertir los casos en regresiones permanentes durante el bloque 4.

Las cifras **692 backend / 417 frontend**, build, chequeos estáticos y evaluación UI del informe anterior pertenecen a aquella entrega: no se volvieron a ejecutar completos en esta auditoría. Aquí no se aplicaron migraciones, no se ejecutó PostgreSQL, no se recorrió un navegador autenticado ni se probó hardware. El estado actual de Docker/PostgreSQL debe inspeccionarse de nuevo al iniciar el bloque 4.

## Decisión de ingeniería para el siguiente bloque

1. Corregir B3-01 a B3-03 con regresiones basadas en los contratos reales.
2. Extraer las consultas del Kardex y unificar la elegibilidad operativa sin modificar el motor de valoración.
3. Completar y ejecutar los casos PostgreSQL de recepción, ubicación, etiqueta, traslado, retaceo y conciliación; después recorrerlos en navegador con datos ficticios.
4. Actualizar los estados de los bloques 1–3 según evidencia. No volver a declarar R1–R3 totalmente cerrados solo porque existe un helper que bloquea el caso inseguro.

Se mantienen fuera de alcance libro mayor, períodos contables, retroactividad, monedas múltiples, deterioro, nuevas políticas contables y módulos completos de ventas/devoluciones.

Encargo: [Prompt para Luna — bloque 4](C:/Developer/GESTIONASV_ERP/docs/prompt-luna-inventario-bloque-4.md).

## Resultado posterior al bloque 4 — 14/10/2026

| Hallazgo | Estado de código | Evidencia disponible | Límite |
| --- | --- | --- | --- |
| B3-01: fracciones sin acción para medir/revalidar | Corregido; medición disponible para medidas incompletas/estimadas, etiqueta de revisión actual y elegibilidad común al liberar/colocar. | Pruebas de componente y política; suite de Inventario de 61 pruebas frontend. | Persistencia, movimientos y rollback PostgreSQL pendientes. |
| B3-02: el Kardex omitía `cost_delta` y datos de crédito | Corregido en tarjetas/tablas; mensajes de créditos e importes separados. | 6 pruebas de presentación `KardexLists.test.ts`, dentro de las 61. | Respuesta SQL real y permisos en navegador pendientes. |
| B3-03: respuesta de período anterior | Corregido mediante identidad/secuencia de consulta e invalidación inmediata. | `InventoryKardexPage.test.ts` incluye respuesta atrasada al cambiar fecha. | Cambios de perfil/sucursal en navegador pendientes. |
| B3-04: pruebas transaccionales PostgreSQL faltantes | **Pendiente de aceptación.** Se añadieron escenarios SQL para preparación (replay, conflicto, auditoría y rollback) y consultas de Kardex (página, totales, conciliación, desconocido sin corte e aislamiento); faltan concurrencia, permisos autenticados y más casos financieros. Nada de PostgreSQL se ejecutó. | `backend/tests/integration/test_inventory_split_prepare_route.py`, `backend/tests/integration/test_inventory_kardex_repository.py`; compileall sintáctico aprobado con Python 3.13.12, fuera del rango requerido `>=3.12,<3.13`. `pytest` no está instalado, `localhost:5432` y Docker daemon no disponibles. | Preparar Python 3.12 y ejecutar/ampliar en base descartable `erp_db_test`; no apuntar pruebas a datos del usuario. |
| B3-05: lectura SQL dentro del router | Corregido estructuralmente: puerto de lectura, caso de uso y adaptador SQLAlchemy; router solo HTTP/DTO/contexto. | `compileall` sintáctico y auditoría de imports/consultas. | Ejecución de consultas PostgreSQL pendiente. |

No se declara aceptación de software: `localhost:5173` tampoco estaba levantado, por lo que falta navegador autenticado. La validación de HS-200 e impresión física es independiente. Consulte el [cierre operativo](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-4-cierre-operativo.md).

## Actualización de ejecución — 14/10/2026

Esta sección reemplaza las observaciones anteriores de “PostgreSQL/Docker no disponibles”, que describían el estado del entorno durante la auditoría inicial. En esta continuación se ejecutaron las pruebas con Python 3.12.15 y PostgreSQL dedicado; los fixtures recrearon únicamente `erp_db_test`.

| Validación | Resultado actualizado |
| --- | --- |
| Unit tests backend | 694 aprobados al excluir `tests/unit/test_ocr_worker.py`, que no se recolecta por falta de `pikepdf`; tras el último refactor, 65 unit tests enfocados de Inventario pasaron. |
| Integración PostgreSQL | 4 aprobados: Kardex paginado/totales/aislamiento, preparación de fracción con replay/conflicto/rollback, liberación idempotente y recepción parcial de traslado. |
| E2E API/base | 2 aprobados: flujo de recepción de compra parcial/completa y retaceo con auditoría. Son pruebas HTTP de backend, no navegador. |
| Ruff y compilación | Ruff enfocado aprobado; `compileall` pasó bajo Python 3.12.15. |
| Alembic | `heads` y `current` en `erp_db_test`: `0083 (head)`. No se añadió migración. |

Quedan pendientes la aceptación del flujo completo en navegador autenticado, las pruebas SQL de permisos revocados/alcance exhaustivo/concurrencia/rollback de asignación grupal, y la verificación física del HS-200/etiqueta. No se declara aceptación integrada completa hasta cubrir esos casos. El detalle y comandos están en el [cierre operativo del bloque 4](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-4-cierre-operativo.md).

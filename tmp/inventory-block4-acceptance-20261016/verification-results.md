# Resultados reproducibles — aceptación de inventario bloque 4

Fecha de cierre: 16/10/2026.

## Destino y contenedores

Se leyó backend/tests/conftest.py antes de cualquier suite E2E/integración. La fixture reconstruye el esquema; su guardia exige el nombre erp_db_test. DSN mostrado de forma segura: host db, puerto 5432, base erp_db_test. Nunca se escribió en erp_db.

alembic heads y alembic current con DSN reescrito explícitamente a la base de prueba: **0083 (head)**. Las suites PostgreSQL se corrieron una después de otra.

Al cierre, la lista Docker contenía el stack ordinario gestionasv_erp (frontend 5173, backend 8000 y dependencias normales). No quedaron activos los contenedores temporales de aceptación. El proceso Vite temporal se detuvo con Ctrl-C. No se eliminaron contenedores ni volúmenes.

## Suites de datos registradas después de los últimos cambios de código

Se ejecutaron en el contenedor backend con Python 3.12.15. El conteo de cada suite se conserva por separado:

- Unitarias focalizadas: pytest -q tests/unit/test_inventory_capacity.py tests/unit/test_inventory_kardex.py tests/unit/test_inventory_valuation.py tests/unit/test_inventory_putaway_group_schema.py tests/unit/test_retaceo_use_cases.py — 79 aprobadas en 11.80 s.
- E2E API/PostgreSQL: pytest -q --tb=short --show-capture=no tests/e2e/test_inventory_block4_closure.py — 10 aprobadas en 101.56 s. Incluye orígenes de dos detalles para el mismo SKU, sobreasignación 51, rollback, permisos/replay, inspección recursiva de campos financieros privados en consulta/listado/replay, rechazo de liberación con etiqueta/retaceo pendientes, carreras y migración 0082→0083. Una advertencia deprecada de Starlette sobre HTTP 422 no afectó el resultado.
- PostgreSQL Kardex, corrida final unificada: `pytest -q --tb=short --show-capture=no tests/integration/test_inventory_kardex_repository.py` — 5 aprobadas en 13.08 s, incluyendo lectura SQL y las tres escrituras concurrentes de conciliación (recepción, traslado y retaceo).
- PostgreSQL valoración: pytest -q --tb=short --show-capture=no tests/integration/test_inventory_valuation_repository.py — 1 aprobada en 11.46 s.
- PostgreSQL movimientos: pytest -q --tb=short --show-capture=no tests/integration/test_inventory_movement_idempotency.py — 2 aprobadas en 11.65 s.
- PostgreSQL preparación fraccionada: pytest -q --tb=short --show-capture=no tests/integration/test_inventory_split_prepare_route.py — 1 aprobada en 16.02 s. Con valoración sintética activa, preparar el split 4+6 conserva 10 unidades, $100 y costo promedio $10; el rollback mantiene la segunda recepción y el mismo valor.

Los casos financieros confirman retaceo $8 al remanente y $12 a salidas; devolución/costo de $75, crédito $100 y diferencia $25. Los casos de Kardex comprueban páginas, empates de fecha, lote, fecha local y datos desconocidos. La conciliación sincronizada cubre recepción, traslado y aplicación de retaceo: tras cada commit la fotografía contiene cantidad 10 una vez y el valor esperado ($100 para traslado, $120 para ajuste de $20).

## Frontend y build

- Cuatro suites focalizadas: node node_modules/vitest/vitest.mjs run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts tests/unit/InventoryKardexPage.test.ts tests/unit/InventoryKardexContext.test.ts tests/unit/WarehouseHandlingUnitsIntegration.test.ts — 45 aprobadas en 5.88 s.
- Comprobación repetida en este cierre: svelte-check --tsconfig ./tsconfig.json — 0 errores y 0 advertencias.
- ESLint sobre src/lib/features/inventory — aprobado.
- Prettier --check sobre HandlingUnitLabelDialog.svelte, HandlingUnitsPanel.svelte, su test, la página de Kardex y InventoryKardexPage.test.ts — todos los archivos cumplen el formato.
- Build repetido en este cierre con vite build — aprobado en 26.13 s. Avisos no bloqueantes: import default de jsbarcode no utilizado en salida SSR y adapter-auto sin destino de despliegue configurado.
- git diff --check repetido después de actualizar los documentos — aprobado sin errores de whitespace.
- python -m compileall -q backend/tests/e2e/test_inventory_block4_closure.py backend/tests/integration/test_inventory_kardex_repository.py — aprobado con el Python local 3.13.12.
- Ruff: la comprobación focalizada que siguió a las refactorizaciones informó All checks passed en los archivos backend seleccionados. No se pudo repetir en este cierre porque el contenedor actual no tiene instalado el módulo Ruff; no se reinstalaron dependencias.

## Aceptación de software y límites físicos

Las 15 filas E y el recorrido F están verificados con evidencia combinada de API, PostgreSQL, interfaz y navegador según el caso. La evidencia complementaria de navegador confirmó la recepción con un perfil de sucursal: 4 cajas registradas, 0 pendientes y la unidad en cuarentena. La valoración de la secuencia principal del navegador era desconocida porque no había un corte aprobado, por lo que el importe no se infiere; la conservación de $100 se verificó en una integración SQL sintética separada. Hardware HS-200, impresión física y colocación física se reportan aparte y no forman parte de la aceptación de software.

## Recomprobación independiente posterior — 16/10/2026

El usuario excluyó expresamente lector, impresión y colocación físicos: son opcionales para la demostración, no requisitos pendientes.

Resultados nuevos, separados de los anteriores:

- Desde `frontend`: `node_modules/.bin/vitest.cmd run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts tests/unit/InventoryKardexPage.test.ts tests/unit/InventoryKardexContext.test.ts tests/unit/WarehouseHandlingUnitsIntegration.test.ts` — **45 aprobadas, 5.04 s**.
- En `gestionasv_erp-backend-1`: `python -m pytest -q --tb=short --show-capture=no tests/e2e/test_inventory_block4_closure.py` — **10 aprobadas, 106.85 s**; aviso de constante HTTP 422 obsoleta.
- Primera ejecución conjunta de las cuatro suites SQL siguientes: **5 aprobadas, 4 fallidas, 21.62 s**. Las pruebas concurrentes habían activado valoración en la empresa canónica, causando una apertura duplicada en la suite siguiente y errores asíncronos derivados.
- Se aislaron las empresas ficticias en los casos concurrentes de `test_inventory_kardex_repository.py`. Una ejecución intermedia detectó que el trigger de la migración 0023 ya inscribe las unidades de empresas nuevas (**5 aprobadas, 4 fallidas, 22.47 s**); se corrigió la fixture para reutilizar esa inscripción.
- Ejecución final en el contenedor: `python -m pytest -q --tb=line --show-capture=no tests/integration/test_inventory_kardex_repository.py tests/integration/test_inventory_valuation_repository.py tests/integration/test_inventory_movement_idempotency.py tests/integration/test_inventory_split_prepare_route.py` — **9 aprobadas, 18.68 s**, en una sola invocación y sin skips.

Ambos DSN se comprobaron antes de pytest: `db:5432/erp_db_test`. Las suites de datos se ejecutaron en serie. No hubo escrituras en `erp_db`. La revisión de navegador se basó en el expediente previo; no se volvió a ejecutar ni se repitió build/tipos/lint de frontend. Ruff no está disponible en el contenedor ni en los entornos locales comprobados, por lo que no se presenta como ejecutado sobre el ajuste de la fixture.

Al finalizar, `alembic heads` y `alembic current` volvieron a confirmar **0083 (head)** con ambos DSN de prueba. `python -m compileall -q tests/integration/test_inventory_kardex_repository.py` pasó con Python 3.12 del contenedor. `git diff --check` no informó errores en los cambios rastreados; mantiene dos avisos CRLF/LF preexistentes. Los archivos de este cierre continúan sin rastrear y no se creó ningún commit.

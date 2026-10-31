# Verificación: solicitudes ya incluidas en un consolidado

Fecha: 2026-10-16

## Causa confirmada

La consulta de solicitudes elegibles excluye las que ya están vinculadas a un consolidado no cancelado. La pantalla interpretaba esa ausencia como un fallo al cargar el detalle. En la base local `erp_db`, la revisión de solo lectura encontró SCR-00036 y SCR-00035 aprobadas y vinculadas al borrador CD-00005. SCR-00035 tiene varias fuentes dentro del consolidado, por lo que las referencias se deduplican por ID.

## Solución implementada

- Se añadió `GET /api/v1/purchase-consolidations/selected-requests` para resolver si cada solicitud seleccionada sigue elegible, ya está consolidada, cambió de estado o no está disponible.
- Se limita la respuesta a la empresa y ámbito autorizados. Si el usuario no puede ver el consolidado relacionado, no se devuelven su código, ID ni estado.
- La interfaz presenta el código legible, el consolidado y su estado, y permite quitar solo la selección local. Los fallos transitorios permiten reintentar y no se etiquetan como consolidados.
- Se conserva el bloqueo contra duplicados en backend. Ante un conflicto al guardar, la pantalla vuelve a consultar el estado.

## Archivos

- Backend: `backend/app/api/v1/routers/purchase_consolidations.py`, `backend/app/api/v1/schemas/purchase_consolidation.py`, `backend/app/application/purchase_consolidations/use_cases.py`, `backend/app/domain/ports/purchase_consolidation_repository.py`, `backend/app/infrastructure/repositories/purchase_consolidation_repository.py`.
- Frontend: `frontend/src/lib/features/purchase-requests/components/PurchaseConsolidationCreate.svelte`, `frontend/src/lib/api/purchase-consolidations.ts`, `frontend/src/lib/types/purchase-consolidation.ts`.
- Pruebas: `backend/tests/integration/test_purchase_request_repository.py`, `backend/tests/unit/test_purchase_consolidation_selected_request_api.py`, `frontend/tests/unit/PurchaseConsolidationCreate.test.ts`.

## Comprobaciones automáticas

- `docker compose exec -T backend pytest -q tests/integration/test_purchase_request_repository.py` — 8 pasaron.
- `docker compose exec -T backend pytest -q tests/unit/test_purchase_consolidation_selected_request_api.py` — 1 pasó.
- `frontend/node_modules/.bin/vitest.CMD run tests/unit/PurchaseConsolidationCreate.test.ts tests/unit/PurchaseConsolidationDetail.test.ts tests/unit/PurchaseConsolidationAdjudication.test.ts` — 14 pasaron.
- `frontend/node_modules/.bin/svelte-check.CMD --tsconfig ./tsconfig.json` — 0 errores, 0 advertencias.
- ESLint para los cuatro archivos de frontend modificados — pasó.
- Ruff para los archivos backend con `--ignore C901,PLR2004,RUF100` — pasó. El chequeo sin esas exclusiones sigue reportando complejidad alta, una constante mágica y directivas `noqa` sin uso en funciones existentes fuera del cambio de diagnóstico.

Las pruebas de integración usan exclusivamente `erp_db_test`; la configuración del fixture rechaza cualquier otro nombre de base. No se crearon, cancelaron, borraron ni modificaron documentos comerciales en `erp_db`.

## Aceptación en navegador y pendiente

En la pantalla real de creación con SCR-00036 y SCR-00035 seleccionadas, ambas muestran “Ya incluida en CD-00005 · Borrador”, el enlace lleva al ID real `f8697dc9-4b15-48cd-a0b0-474d92a2406c` y “Crear borrador” permanece deshabilitado.

La aceptación de navegación **no pasó**: al abrir ese enlace o cargar directamente la ruta del ID, la URL cambia pero la app sigue mostrando “Nuevo consolidado · Borrador”. Se observó el mismo comportamiento al abrir una ruta dinámica de detalle de solicitud, que mostró “Nueva solicitud de compra”. Esto apunta a un problema de resolución/navegación de rutas dinámicas en la aplicación y requiere corregirse antes de considerar completo el encargo. No se modificó el flujo ni los estados de los documentos para sortearlo.

# Comandos y resultados — 20/10/2026

## Continuación final

Esta sección es el corte vigente del 20/10; el resto del archivo conserva los comandos de la primera pasada.

- Prueba invocada: `pytest -q tests/unit`, en contenedor efímero con extras `dev+ocr` resueltos desde el lock del proyecto: **753 passed in 35.18s**. La salida íntegra está en [backend-unit-dev-ocr-final.log](pasada-final/backend-unit-dev-ocr-final.log), status 0. El wrapper exacto de Compose no se guardó en el registro original; no se inventa. No se cambió el lock ni el servicio habitual. El intento anterior sin el entorno OCR adecuado falló; no se omite ningún test.
- Regresión de unidad/migración: **3 passed in 11.20s**. Registro: [backend-unit-regressions.log](pasada-final/backend-unit-regressions.log).
- E2E `test_inventory_lot_detail_migration.py` de migración 0082→0083: **1 passed in 26.18s**; E2E `test_sales_base.py`: **1 passed in 204.07s**. Cada invocación reconstruyó únicamente `erp_db_test`; ambas se ejecutaron en serie. Registros: [migración](pasada-final/e2e-migration-regression.log), [ventas](pasada-final/e2e-sales-base-regression.log). Son repeticiones y no incrementan 33 casos E2E únicos anteriores.
- `docker compose exec -T frontend pnpm exec vitest run tests/unit/TransferDemandQuantity.test.ts`: **2 passed**.
- `docker compose exec -T frontend pnpm check`: **0 errores, 8 avisos CSS `@apply`** ya conocidos.
- ESLint focalizado en `TransferOperationsPage.svelte`, `TransferDemandOverview.svelte` y `TransferDemandQuantity.test.ts`: exit code 0.
- `docker compose exec -T frontend pnpm build`: exit code 0 en **1m16s**. Avisos no bloqueantes: jsbarcode sin uso y adapter-auto sin entorno de despliegue configurado.
- Docker frontend se reinició para limpiar un módulo transformado obsoleto de Vite; no se reiniciaron API ni DB por esta causa. Después, `/transfers` mostró la UI editada y todos los servicios principales quedaron saludables.
- Conciliación de `erp_db` se hizo con `BEGIN READ ONLY`: los cuatro SKU protegidos mantienen cantidades y valor de la sección vigente en [evidencia](evidencia.md). Alembic sigue 0090.
- Inspección visual de solo lectura y sus límites: [mobile-ui-run.md](pasada-final/mobile-ui-run.md). Capturas PNG no se guardaron porque la API de control no expone una operación de archivo; P02 sigue parcial.

Todos los E2E se ejecutaron en serie. backend/tests/conftest.py impone erp_db_test y reconstruye esa base por caso. No se ejecutaron E2E contra la demo.

## Frontend y backend focalizado

- Comando: docker compose exec -T frontend pnpm exec vitest run  
  Resultado: 116 archivos / 513 pruebas aprobadas, 44.64s. Registro: frontend-vitest.log.
- Comando: docker compose exec -T frontend pnpm check  
  Resultado: 0 errores / 8 avisos CSS en TransferOperationsPage.svelte. Registro: frontend-check.log.
- Comando: docker compose exec -T frontend pnpm exec eslint src/lib/features/sales 'src/routes/(app)/sales/returns/+page.svelte'  
  Resultado: aprobado. Registro: eslint-focused.log.
- Comando: docker compose exec -T frontend node node_modules/vite/bin/vite.js build  
  Resultado: aprobado en 1m 13s; avisos no bloqueantes de jsbarcode no usado y adapter-auto sin entorno productivo configurado.
- Comando: docker compose exec -T backend pytest -q tests/unit/test_sales_domain.py tests/unit/test_sales_return_validation.py  
  Resultado: 25 aprobadas. Registro: backend-sales-unit.log.
- Comando: docker compose exec -T backend pytest -q tests/unit  
  Resultado: no recolecta la suite completa; ModuleNotFoundError por pikepdf en tests/unit/test_ocr_worker.py.
- Comando: docker compose exec -T backend python -m alembic current  
  Resultado: 0090 (head).
- Comando: git diff --check  
  Resultado: sin errores; solo avisos CRLF/LF en archivos compartidos.

## E2E anteriores de cierre: 11 aprobadas

Comando ejecutado:

    docker compose exec -T backend pytest -q tests/e2e/test_inventory_transfers.py::test_destination_branch_receiver_can_receive_without_global_access tests/e2e/test_inventory_transfers.py::test_transfer_from_another_company_is_not_visible tests/e2e/test_sales_base.py tests/e2e/test_sales_deliveries.py tests/e2e/test_documents.py tests/e2e/test_inventory_block4_closure.py::test_branch_kardex_profile_cannot_fetch_company_valuation_json

Resultado: 11 aprobadas. Alcance: recepción por sucursal, empresa ajena, venta/conversión, entrega/devolución, documentos y valoración de Kardex.

## E2E anteriores B01–B04: 12 aprobadas

Se ejecutaron en una sola invocación de pytest:

- test_inventory_block4_closure.py: measurement_response_matches_list_with_label_and_retaceo_blockers; pending_label_and_retaceo_can_only_be_put_away_in_quarantine; group_putaway_uses_split_requirements_for_each_result; group_putaway_preserves_two_purchase_detail_origins; group_putaway_rolls_back_first_allocation_when_second_fails; concurrent_group_movement_and_measurement_are_serialized; concurrent_group_retry_applies_once_and_replays; new_receipt_split_invalidates_label_on_both_grouped_results; 0082_to_0083_preserves_legacy_receipt_rows.
- test_inventory_lot_detail_migration.py: los dos casos de lote por recepciones parciales y conservación de detalle legado.
- test_company_mother_warehouse_catalogue.py: catálogo de sucursal y bodega madre explícita.

Resultado: 12 aprobadas; 133.32s. Alcance: lotes, cuarentena, etiqueta, fraccionamiento, ubicación, atomicidad, concurrencia y bodega madre.

## E2E E13 adicionales de esta fecha: 10 aprobadas

Comando ejecutado:

    docker compose exec -T backend pytest -q tests/e2e/test_branch_isolation.py::test_restricted_user_cannot_cross_branch_boundary tests/e2e/test_purchase_orders.py::test_purchase_order_requires_rbac_permission tests/e2e/test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope tests/e2e/test_purchase_orders.py::test_purchase_receiving_requires_rbac_permission tests/e2e/test_purchase_orders.py::test_retaceo_requires_rbac_permission tests/e2e/test_purchase_orders.py::test_purchase_order_expense_documents_require_permission tests/e2e/test_purchase_quotations.py::test_purchase_quotation_requires_rbac_permission tests/e2e/test_purchase_requests.py::test_purchase_request_requires_rbac_permission tests/e2e/test_warehouse_category_isolation.py::test_categories_are_isolated_by_company_and_reject_cross_assignment tests/e2e/test_warehouse_category_isolation.py::test_user_cannot_list_categories_from_an_unassigned_company

Resultado: 10 aprobadas en 96.23s. Registro íntegro: e13-permission-tests.log. Alcance: ausencia de permiso, aislamiento de sucursal/empresa, recepción central asignada, compras, retaceo y documentos.

## Conciliación de erp_db

Se consultaron inventory_cost_averages, inventory_items, products e inventory_balances en una transacción READ ONLY. Para cada SKU se sumó la cantidad física por bodega/estado y se comparó con cantidad valorizada, valor y promedio. Resultado: ERS-INC-EE8FE228 4/4 USD 40; ERS-LATE-B1B55D6D 5/5 USD 60; ERS-REVIEW-DD6BBF85 12/12 USD 160; ERS-UI-F767BABC 0/0 USD 0. No hubo cambios en datos.

## Re-ejecuciones focalizadas P01–P04 — 20/10/2026

Los comandos de abajo se repitieron para vincular el resumen P01–P04 con nodos reales de pruebas. No se ejecutaron suites completas. Las pruebas que recolectan integración/E2E pasan por `backend/tests/conftest.py`, que obliga la base desechable `erp_db_test`; se ejecutaron en serie. No se tocó `erp_db`.

### P01 — documentos y permisos de ajustes

Comando:

    docker compose exec -T backend pytest -q tests/e2e/test_inventory_adjustment_permissions.py::test_adjustment_evidence_download_requires_valuation_permission

Resultado: **1 passed in 21.51s**. El log conserva el comando y la salida: [P01](pasada-final/p01-adjustment-document-permission-rerun.log).

### P04 — corrección compensatoria y traslado parcial

Comando:

    docker compose exec -T backend pytest -q tests/integration/test_inventory_adjustment_repository.py::test_ordinary_negative_adjustment_correction_preserves_origin_and_compensates_value tests/integration/test_inventory_transfer_repository.py::test_transfer_preparation_dispatch_partial_receipt_and_idempotent_replay

Resultado: **2 passed in 20.51s**. El log conserva el comando y la salida: [ajuste y traslado](pasada-final/p04-adjustment-transfer-focused-rerun.log).

### P04 — venta/entrega y devolución parcial

Comando:

    docker compose exec -T backend pytest -q tests/e2e/test_sales_deliveries.py::test_sales_delivery_partial_cost_idempotency_concurrency_and_rollback

Resultado: **1 passed in 207.33s**. El log conserva el comando y la salida: [venta/devolución](pasada-final/p04-sales-delivery-returns-focused-rerun.log). Este caso cubre API/persistencia e idempotencia; no prueba selección de asignaciones ni pérdida de respuesta desde navegador.

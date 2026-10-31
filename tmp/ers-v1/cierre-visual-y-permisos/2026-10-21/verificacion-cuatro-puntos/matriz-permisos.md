# Matriz E13 — resultados observados

## Actualización de verificación final — 21/10/2026

**Dictamen E13/V01: ABIERTO.** Se conserva la evidencia puntual de las filas que siguen; no se infiere permiso de una ruta a otra ni de una prueba con superadmin. El inventario estático [routes-b01-b08.tsv](routes-b01-b08.tsv) enumera 304 declaraciones de endpoint, pero el extractor no resuelve dependencias dinámicas, guardas de servicio ni reglas de alcance. Por sí solo no completa el mapa de autorización.

No se añadieron casos V01 nuevos durante el recorrido UI de 21/10: los recorridos autenticados se hicieron con superadmin para demostrar operaciones, no para aceptar autorización. V04 corrigió/aplicó ajuste, recibió traslado y resolvió devolución en la base clonada; eso no acredita ausencia de permiso ni acceso a recurso ajeno. V03 consultó la vista QR pública, pero no probó una consulta privada ajena.

Los grupos sin resultados individualizados siguen siendo los ya enumerados abajo: cambios de matriz/bodega, lotes/etiquetas/alias, operaciones e incidencias de traslado, cambios/aprobación de ajuste, clientes/cotizaciones/ventas, entregas/devoluciones y Kardex/valoración; para cada grupo faltan acciones de lectura/detalle/borrador/confirmación/aprobación/aplicación/cancelación/corrección y controles de documentos según aplique. En adjuntos faltan bytes reales en descarga y recursos documentales de módulos distintos de ajustes.

**Siguiente paso exacto:** completar una fila por ruta/acción aplicable con permiso, regla de empresa/sucursal, control de UI, perfil/alcance probado y nodo/assertion/log; ejecutar denegación UI+API y contexto propio/ajeno para los huecos. No se marca `NO APLICA` sin demostrar que el contrato carece de esa operación.

**Continuación 20/10:** se repitieron con éxito dos regresiones E2E (migración y ventas) en `erp_db_test`; se conservaron sus registros en `pasada-final/`. No se añadieron como casos nuevos. Esta nueva ejecución no amplía por sí sola las filas de autorización abajo. El frontend Vitest/chequeo/lint/build tampoco acredita permisos del servidor.

**Caso adicional P01 del 20/10:** `test_inventory_adjustment_permissions.py::test_adjustment_evidence_download_requires_valuation_permission` acredita el endpoint de descarga de adjuntos de ajustes y la redacción de costos; se dejó la invocación exacta y salida en el [log rerun](../../2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log). Véase la fila abajo y el [registro P01–P04](../../2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md). Esto no completa E13 para los otros módulos.

Corte 20/10/2026. «Aprobado» se limita al caso indicado; cualquier combinación no enumerada queda sin evidencia. La revisión con superadmin acredita presentación, nunca autorización.

| Contexto | Recurso/acción | Resultado | Evidencia |
| --- | --- | --- | --- |
| Usuario restringido a una sucursal | Leer/escribir fuera de sucursal y pedir alcance global | Servidor deniega (403) | test_branch_isolation.py::test_restricted_user_cannot_cross_branch_boundary |
| Receptor con permiso de sucursal destino | Recibir sin permiso global | Permitido en su alcance | test_inventory_transfers.py::test_destination_branch_receiver_can_receive_without_global_access |
| Usuario de otra empresa | Consultar traslado por ID | No visible | test_inventory_transfers.py::test_transfer_from_another_company_is_not_visible |
| Perfil Kardex de sucursal | Leer valoración de empresa | Denegado; JSON no contiene costos | test_inventory_block4_closure.py::test_branch_kardex_profile_cannot_fetch_company_valuation_json |
| Usuario sin permiso / permiso revocado | Replay de movimiento | Denegado; replay autorizado no filtra costos | test_inventory_block4_closure.py::test_concurrent_group_retry_applies_once_and_replays |
| Usuario sin permiso documental | Iniciar carga | HTTP 403 | test_documents.py::test_document_upload_requires_explicit_permission |
| Lector de ajuste sin `inventory:valuation` | Leer el detalle de ajuste | HTTP 200; costos documentados `null` | `test_inventory_adjustment_permissions.py::test_adjustment_evidence_download_requires_valuation_permission`; [comando/log](../../2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log) |
| Lector de ajuste sin permisos de valoración/ajuste | Iniciar, completar, retirar o descargar adjunto; lector sin `inventory:read` pide descarga directa | HTTP 403 | Mismo E2E P01 y [comando/log](../../2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log) |
| Responsable con valoración y sucursal propietaria | Descargar vínculo activo de ajuste | HTTP 200; se emite URL temporal simulada | Mismo E2E P01; prueba autorización/emisión, no bytes ni expiración |
| Responsable con valoración pero documento no vinculado | Descarga directa por ID aleatorio | HTTP 404 | Mismo E2E P01; [log](../../2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log) |
| Responsable con permiso, sucursal distinta | Descargar documento del ajuste fuera de sucursal | HTTP 403 | Mismo E2E P01 |
| Usuario de otra empresa | Descargar por ID de ajuste/documento ajeno | HTTP 404 | Mismo E2E P01 |
| Responsable; vínculo retirado o alcance revocado | Nueva petición tras cada cambio | Vínculo con `detached_at`; descarga 404 tras retiro, 403 tras revocación | Mismo E2E P01; URL emitido previamente es capacidad temporal bearer |
| Usuario sin permiso de orden | Crear orden de compra | Denegado | `test_purchase_orders.py::test_purchase_order_requires_rbac_permission` |
| Usuario de sucursal matriz explícitamente asignado | Leer recepción central nueva sin permiso global | Permitido solo dentro de sede asignada; lista global/otra sede no permitida | `test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope` |
| Usuario sin permiso de recepción | Recibir una compra | Denegado | `test_purchase_orders.py::test_purchase_receiving_requires_rbac_permission` |
| Usuario sin permiso de retaceo | Operar retaceo | Denegado | `test_purchase_orders.py::test_retaceo_requires_rbac_permission` |
| Usuario sin permiso documental de gasto de orden | Acceder al documento de gasto | Denegado | `test_purchase_orders.py::test_purchase_order_expense_documents_require_permission` |
| Usuario sin permisos de compra | Cotización y solicitud | Denegadas | test_purchase_quotations.py; test_purchase_requests.py |
| Empresa no asignada | Listar/asignar categoría de bodega ajena | Denegado por empresa | Dos casos de test_warehouse_category_isolation.py |
| Usuario de ventas | Detalle, conversión y reintento de cotización por sucursal/empresa | Se permite el alcance asignado; los ajenos se deniegan | test_sales_base.py::test_sales_quote_conversion_is_idempotent_scoped_and_inventory_neutral |
| Usuario de sucursal/sin permiso | Leer o resolver devolución ajena | Denegado en casos directos | test_sales_deliveries.py::test_sales_delivery_partial_cost_idempotency_concurrency_and_rollback |
| Sede asignada explícitamente a Casa matriz | Leer recepción central sin acceso global | Permitido solo para sede asignada; otras sedes/global denegadas | test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope |

## Combinaciones aún sin evidencia individual

No existe la matriz completa recurso × acción × perfil × contexto. El nuevo caso P01 cubre documentos de ajustes y redacción de costos; no se extrapola a documentos de otros módulos. Siguen pendientes resultados explícitos para listar, detalle, borrador, confirmar/despachar/recibir, aprobar/aplicar, resolver, cancelar/corregir y consultar evidencia en:

- Matriz/bodegas y sus cambios.
- Lotes, etiquetas, QR, impresión/reimpresión y resolución de alias.
- Traslados e incidencias, incluidos adjuntos y cambio de contexto.
- Ajustes y sus flujos de corrección/aprobación/aplicación.
- Clientes, cotizaciones y ventas con cancelación/corrección y documentos.
- Entregas y devoluciones con límites, operaciones parciales y descarga de evidencia por perfil.
- Kardex/valoración para todas las combinaciones de acceso, incluido endpoint directo.
- Documentos de todos los módulos: iniciar/subir, listar, ver/descargar, quitar y revalidar propiedad/sucursal/empresa al cambiar contexto.

No marcar estas celdas aprobadas hasta ejecutar un caso con resultado verificable. Esta matriz es intencionalmente parcial.

## Prioridad para cerrar el hueco

Crear una fila por acción realmente disponible en routers y formularios: lectura/listado, detalle, borrador, confirmación, aprobación/aplicación, cancelación/corrección y documentos. Por cada una vincular perfil y contexto real (empresa, sucursal, recurso propio/ajeno), método/ruta, resultado y prueba. Empezar por ajustes/incidencias, QR/etiquetas y adjuntos; probar tanto la guarda UI como la denegación del servidor y una nueva petición después de cambio de contexto. No extrapolar una autorización a otras acciones.

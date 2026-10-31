# Entrega ERS-B03 — Motor de traslados

**Fecha:** 19/10/2026

**Estado:** implementado y verificado técnicamente. La aceptación visual e integrada queda pendiente para el cierre B08, según la decisión vigente del usuario.

## Alcance entregado

B03 incorpora el documento de traslado, vehículos y ubicación móvil de existencias en tránsito, sobre los lotes y el motor de inventario existentes. No incluye las pantallas operativas completas; esas corresponden a B04.

- Una bodega técnica de tránsito por empresa contiene las ubicaciones móviles de sus vehículos. No se duplica inventario: el despacho y la recepción son movimientos del motor existente. La bodega técnica no es elegible como bodega comercial ni ocupa capacidad de estantes; sí participa en la existencia y valoración global.
- Los traslados mantienen cabecera, detalle, lote canónico, unidad logística, asignaciones a solicitudes, comandos idempotentes, recepciones parciales e incidencias con motivo y evidencia.
- Preparar y cancelar una preparación no mueven ni reservan existencias. El despacho mueve la cantidad a tránsito; cada recepción la lleva a cuarentena en destino. Una recepción parcial conserva el remanente en tránsito.
- Se conserva el costo promedio global por empresa y producto. Los traslados internos no cambian la cantidad ni el valor global.
- El receptor con acceso a la sucursal destino puede consultar y recibir su traslado sin acceso global a las sucursales de la empresa. Las operaciones verifican permisos también al repetir una clave idempotente.
- La operación del documento, sus movimientos, saldos, valoración y auditoría de éxito están protegidos con savepoint ante errores funcionales o inesperados.

## Contrato API para B04

El router se publica bajo `/api/v1/inventory/transfers`:

| Operación | Ruta |
| --- | --- |
| Consultar demanda disponible por producto/sucursal | `GET /demand` |
| Consultar y registrar vehículos | `GET /vehicles`, `POST /vehicles`, `PATCH /vehicles/{vehicle_id}` |
| Crear/listar documentos | `POST /`, `GET /` |
| Consultar/editar documento | `GET /{transfer_id}`, `PUT /{transfer_id}` |
| Cancelar preparación | `POST /{transfer_id}/cancel` |
| Despachar | `POST /{transfer_id}/dispatch` |
| Registrar recepción parcial o total | `POST /{transfer_id}/receive` |
| Reportar/resolver incidencia | `POST /{transfer_id}/incidents`, `POST /{transfer_id}/incidents/resolve` |

Los cuerpos, respuestas, errores, permisos y transiciones están documentados en [API](C:/Developer/GESTIONASV_ERP/docs/api.md), [modelo de datos](C:/Developer/GESTIONASV_ERP/docs/database-schema.md) y [RBAC](C:/Developer/GESTIONASV_ERP/docs/rbac-model.md). OpenAPI de la aplicación local mostró las rutas de traslado y vehículo; la demo quedó en Alembic `0086 (head)`.

**Corrección contractual incorporada en B04:** el router acepta `PUT /{transfer_id}` para editar una preparación. La mención anterior de `PATCH` en esta entrega era un error documental; no se añadió una ruta alternativa.

## Criterios B03-A1–A8

| Criterio | Evidencia ejecutada | Resultado |
| --- | --- | --- |
| A1 — Preparar, cancelar y despachar | `test_transfer_preparation_dispatch_partial_receipt_and_idempotent_replay`; `test_concurrent_dispatches_cannot_consume_the_same_handling_unit` | Preparar/cancelar deja movimientos, HU y saldos sin cambios. Un despacho mueve 10 una sola vez a tránsito y conserva promedio/valor global. Dos despachos concurrentes sobre la misma HU producen un éxito y un conflicto. |
| A2 — Recepción parcial, final e idempotencia | `test_transfer_preparation_dispatch_partial_receipt_and_idempotent_replay`; `test_destination_branch_receiver_can_receive_without_global_access` | De 10, recibir 8 deja 2 en tránsito; recibir esos 2 completa el documento. El reintento devuelve el resultado guardado, la sobre-recepción se rechaza y dos recepciones concurrentes de 6 no reciben más de las 10 despachadas. |
| A3 — Conflictos y concurrencia | Pruebas de integración/E2E anteriores | La misma clave con cuerpo distinto se rechaza; los comandos concurrentes no consumen dos veces la misma HU ni exceden el saldo en tránsito. No se inyectó un deadlock de PostgreSQL artificial; la contención real de despacho y recepción sí se ejercitó. |
| A4 — Atomicidad y rollback | `test_transfer_command_savepoint_rolls_back_partial_movement_failures` | Fuerza un fallo después de procesar parcialmente la segunda línea, tanto funcional como inesperado. El documento vuelve a preparación; no quedan movimiento, cambio de saldo/valoración ni auditoría de éxito. |
| A5 — Incidencias y seguridad del tránsito | `test_transfer_incident_never_removes_unresolved_inventory` | La incidencia conserva las 10 unidades en tránsito; no se puede cancelar tras despachar, cerrar una pérdida sin ajuste autorizado ni desactivar el vehículo mientras transporta existencias. |
| A6 — Empresa, sucursal y valoración global | `test_transfer_from_another_company_is_not_visible`; `test_destination_branch_receiver_can_receive_without_global_access`; prueba de integración de ciclo | Otra empresa recibe 404. Un receptor restringido a su sucursal puede recibir sin acceso global. La transferencia conserva el total de empresa y su promedio ponderado. |
| A7 — Lotes, historial y migración | Ensayo aislado de `0085 → 0086`; `test_0084_to_0085_keeps_immutable_movements_and_resolves_legacy_detail_lot` | La migración conserva los datos existentes y añade solo la bodega técnica. La regresión de lote resuelve históricos solo con relación exacta y mantiene los movimientos anteriores inmutables. |
| A8 — Demanda y recepción concurrente | `test_demand_allocation_cannot_exceed_planned_transfer_quantity`; `test_demand_progress_tracks_assignment_dispatch_and_partial_receipt_once`; E2E de recepción restringida | La asignación no excede la línea planeada; la demanda mantiene asignado, pendiente, en tránsito y recibido después de recepción parcial. El evento parcial se registra una sola vez bajo concurrencia. |

### Resultados reales de los comandos

Las suites se ejecutaron en serie y las fixtures apuntaron a la base de pruebas `erp_db_test`, nunca a la demo:

| Comando | Resultado |
| --- | --- |
| `docker compose exec -T backend pytest tests/integration/test_inventory_transfer_repository.py -q` | `6 passed` |
| `docker compose exec -T backend pytest tests/e2e/test_inventory_transfers.py -q` | `3 passed` |
| `docker compose exec -T backend pytest tests/e2e/test_inventory_lot_detail_migration.py::test_0084_to_0085_keeps_immutable_movements_and_resolves_legacy_detail_lot -q` | `1 passed` |
| `docker compose exec -T backend ruff check` sobre los módulos B03, router, adaptador legado y pruebas tocadas | `All checks passed!` |

Los detalles de respaldo, ensayo, comparación de datos, ruta OpenAPI y resultados están en [evidencia fechada](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-03/evidencia-2026-10-19.md).

## Decisiones y límites conocidos

- B03 no ofrece comando de retorno del traslado. El esquema conserva la cantidad retornada para una extensión posterior, pero el documento actual se completa al recibir toda la cantidad despachada. Una diferencia se registra como incidencia; una pérdida requiere el ajuste autorizado de B05.
- B03 no reconstruye traslados, vehículos o despachos históricos sin evidencia inequívoca. Los movimientos genéricos anteriores mantienen su lectura y no se recontabilizan.
- La incidencia no descuenta ni elimina mercancía. La resolución de pérdida depende del ajuste de B05.
- La API ya está disponible para B04. Falta conectar la pantalla de traslados, demanda visible por sucursal, despacho, recepción, incidencias y validación visual.
- La aceptación autenticada de B01, B02 y B03 queda acumulada para B08. No se declara aprobada por las pruebas de backend.

## Siguiente paso

Continuar únicamente con el encargo B04, [Operación de traslados](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-04-traslados-operacion.md). B04 debe consumir este contrato sin duplicar movimientos ni redefinir estados. No se inicia automáticamente en esta entrega.

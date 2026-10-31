# Evidencia técnica ERS-B03 — 19/10/2026

## Migración y recuperación

- Base demo: `erp_db`.
- Cabeza antes: Alembic `0085`.
- Respaldo: `backups/ers_b03_erp_db_pre_0086_20261019.dump` (879,279 bytes).
- SHA-256 del respaldo: `08F7480452C857CCF499800D9D874FC02F3F90F5332690D8509C1AE8681F5D2E`.
- Ensayo aislado: copia `erp_ers_b03_rehearsal_20261019`, restaurada desde el respaldo exacto y migrada mediante `tmp/ers-v1/bloque-03/upgrade-rehearsal.py`. El ensayo confirmó que el origen era `erp_db`, el origen estaba en `0085` y el destino era la copia aislada autorizada.
- Resultado del ensayo: `0085 → 0086` correcto; las cantidades, relaciones y valores de negocio previos se conservaron.
- Demo después del ensayo: `docker compose exec -T backend alembic upgrade 0086` completó `0085 → 0086`; lectura posterior: `0086 (head)`.

## Comparación antes/después

La copia aislada y la demo migrada devolvieron las mismas cantidades de filas y los mismos hashes de contenido de filas serializadas en las tablas preexistentes revisadas. La única adición organizativa es un almacén técnico de tránsito; las ocho bodegas físicas existentes permanecen intactas.

| Datos de negocio preexistentes | Demo antes | Demo después |
| --- | ---: | ---: |
| Empresas / sucursales | 1 / 8 | 1 / 8 |
| Bodegas físicas / bodega técnica de tránsito | 8 / 0 | 8 / 1 |
| Lotes / detalles canónicos | 1 / 1 | 1 / 1 |
| Detalle aceptado de lote | 9 | 9 |
| Unidades logísticas activas | 25 | 25 |
| Cantidad base en unidades logísticas | 2,892 | 2,892 |
| Saldos por ubicación/estado | 27 filas, 2,892 unidades | 27 filas, 2,892 unidades |
| Movimientos / líneas de movimiento | 65 / 71 | 65 / 71 |
| Cantidad histórica en líneas de movimiento | 11,963.2 | 11,963.2 |
| Impresiones de etiquetas | 8 | 8 |
| Promedios ponderados | 6 filas, 2,892 unidades, USD 47.50 | 6 filas, 2,892 unidades, USD 47.50 |
| Entradas de valoración | 6 filas, 2,892 unidades, delta USD 47.50 | 6 filas, 2,892 unidades, delta USD 47.50 |
| Configuraciones de valoración / aplicaciones de retaceo | 1 / 0 | 1 / 0 |
| Compras | 17 | 17 |
| Vehículos / traslados nuevos | 0 / 0 | 0 / 0 |

La comparación cubrió estas tablas: `inventory_balances`, `inventory_cost_averages`, `inventory_handling_units`, `inventory_label_prints`, `inventory_lot_details`, `inventory_lots`, `inventory_movement_lines`, `inventory_movements`, `inventory_retaceo_applications`, `inventory_valuation_entries`, `inventory_valuation_settings` y `warehouses` (esta última excluyendo el almacén técnico nuevo). No se actualizaron filas de movimientos históricos.

| Tabla | Filas comparadas | Huella de contenido |
| --- | ---: | --- |
| `inventory_balances` | 27 | `77ebeaec81136eb86d1ad04dfd287786` |
| `inventory_cost_averages` | 6 | `d663f06fef3a6f82acf65f9ed6c3d25d` |
| `inventory_handling_units` | 25 | `93e8d3b93ddfb238d3f331c494b77028` |
| `inventory_label_prints` | 8 | `400524c2021a9c8a6c14bb2e7dc42628` |
| `inventory_lot_details` | 1 | `5c4e7f19ccfb8ddd135865735c253655` |
| `inventory_lots` | 1 | `efc58fb1445b4c4f1df103e676f26e5b` |
| `inventory_movement_lines` | 71 | `b9febf6e7b8c0aeadf1123611cbb68c2` |
| `inventory_movements` | 65 | `ac1da21871c6001c7edaf260841c8b8c` |
| `inventory_retaceo_applications` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `inventory_valuation_entries` | 6 | `ca2f960fcf100b3199e20628db26f0c9` |
| `inventory_valuation_settings` | 1 | `80006d0e3e67b3a20a5c83244fb44672` |
| `warehouses` | 8 | `2910449c4e3406a970339347148db6c0` |

La aplicación de prueba quedó vacía para los nuevos objetos: 0 vehículos, 0 traslados, 0 detalles y 0 eventos de comando/recepción/incidencia. Las nuevas tablas no recibieron filas comerciales durante la migración.

## Verificación de API

`GET http://localhost:8000/openapi.json` respondió con las rutas B03 publicadas:

```text
/api/v1/inventory/transfers
/api/v1/inventory/transfers/{transfer_id}
/api/v1/inventory/transfers/{transfer_id}/cancel
/api/v1/inventory/transfers/{transfer_id}/dispatch
/api/v1/inventory/transfers/{transfer_id}/incidents
/api/v1/inventory/transfers/{transfer_id}/incidents/resolve
/api/v1/inventory/transfers/{transfer_id}/receive
/api/v1/inventory/transfers/demand
/api/v1/inventory/transfers/vehicles
/api/v1/inventory/transfers/vehicles/{vehicle_id}
```

## Verificación focalizada

Las pruebas de persistencia/E2E corrieron en la base `erp_db_test`, en serie:

| Verificación | Resultado |
| --- | --- |
| `docker compose exec -T backend pytest tests/integration/test_inventory_transfer_repository.py -q` | 6 passed en 18.04 s |
| `docker compose exec -T backend pytest tests/e2e/test_inventory_transfers.py -q` | 3 passed en 33.64 s |
| `docker compose exec -T backend pytest tests/e2e/test_inventory_lot_detail_migration.py::test_0084_to_0085_keeps_immutable_movements_and_resolves_legacy_detail_lot -q` | 1 passed en 21.76 s |
| Ruff en módulos B03, router, adaptador genérico legado y pruebas modificadas | `All checks passed!` |

Los casos focales cubren preparación sin mutación, cancelación previa, despacho único, reintento idempotente, conflicto de cuerpo, recepción parcial/total y sobre-recepción, contención concurrente, acceso de sucursal y de otra empresa, tránsito con incidente, rollback de fallo funcional e inesperado después de una primera línea y avance de demanda sin duplicación.

## Alcance de esta evidencia

La migración y los contratos del motor quedaron comprobados. B03 no implementa la experiencia visual de despacho/recepción, un comando de retorno ni el ajuste de pérdida. La revisión autenticada de las pantallas de B01–B03 se reserva para el cierre integrado B08; la evidencia técnica no equivale a aceptación visual.

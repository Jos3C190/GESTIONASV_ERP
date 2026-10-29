# Evidencia ERS-B02 — 18/10/2026

## Entorno y protección

- Destino habitual: `erp_db`; al iniciar B02 estaba en 0084 y su cabeza final es `0085`.
- Respaldo B01 previo a 0084: `backups/ers_b02_erp_db_pre_0084_20261018.dump`, SHA-256 `EA02470BDA68A6D92432E976EABCCD4789EA4A2DF8FD5673D11FFACDFF9A6C3A`.
- Respaldo B02 previo a 0085: `backups/ers_b02_erp_db_pre_0085_20261018.dump`, 877,534 bytes, SHA-256 `42357323E3FD7BCAE43CF7A5F88534E705F11FFA85C2DA503B6576A61210B7AF`. El archivo está bajo `backups/*.dump`, ignorado por Git y conservado localmente.
- El respaldo B02 se restauró en la base aislada `erp_ers_b02_rehearsal_20261018`, migró de 0084 a 0085, y sus métricas/fingerprints coincidieron con `erp_db`. El ensayo temporal se retiró después de documentar; no se eliminó otra base.
- Limpieza verificada: `docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" erp_ers_b02_rehearsal_20261018'`; una consulta posterior a `pg_database` devolvió `0` para ese nombre.
- No hubo reset ni seed de `erp_db`. Los chequeos posteriores son consultas de lectura.

## Migraciones B01/B02 y preflight

Comandos/resultados:

```text
docker compose exec -T backend alembic current
0085 (head)

docker compose exec -T backend python scripts/preview_headquarters_migration.py --expect-database erp_db
database=erp_db; schema_already_has_is_headquarters=true; validation_errors=[]
central warehouse=14e5a8bc-20e6-4184-99a1-4238000eca8a
headquarters=9ef70033-12c3-48e5-9604-53755df35342

docker compose exec -T backend python scripts/preview_inventory_lot_identity_migration.py --expect-database erp_db
database=erp_db; revision=0085; validation_errors=[]
detail=1; existing_code=proposed_code=LOT-COM-00017-DA9DBC0769F114438A8C0CF242E8344D8
movement_lines=71; resolvable_via_exact_HU=18; historical_rows_modified=false; label_print_rows=8
```

La vista previa R02 ahora comprueba lo mismo que 0084 para almacenes no
centrales sin sucursal y para dirección nula/vacía. El preflight B02 no escribe
filas y compara código propuesto/guardado.

## Fingerprints posteriores y conciliación

Los archivos SQL de este directorio permiten repetir los chequeos:

- `database-fingerprint.sql`: conteos y fingerprints de lotes, detalle,
  balances, HUs, movimientos, líneas, compras, etiquetas y valoración.
- `post-migration-check.sql`: unicidad del código, líneas históricas resolubles,
  trigger de inmutabilidad, valoración y saldos físicos.
- `database-snapshot.sql`: resumen de cantidades/valores previos a la migración.

Resultado idéntico para `erp_db` y la restauración ensayada: 1 lote, 1 detalle
con cantidad aceptada 9, 27 saldos físicos, 25 HUs, 65 movimientos, 71 líneas,
8 impresiones, 6 promedios con valor USD 47.50, 6 entradas de valoración con
valor fuente USD 47.50 y 1 ajuste de configuración. Las 71 líneas permanecen
intactas; 18 se atribuyen mediante su HU exacta y 53 siguen sin origen suficiente.
El trigger `trg_inventory_movement_lines_immutable` continúa instalado. La demo
tiene 0 aplicaciones de retaceo; R03 comprueba una aplicación sintética no vacía
en su fixture aislado.

Fingerprints idénticos entre demo y restauración ensayada para las consultas de
negocio (mismo valor en cada lado): lotes `f87e62f28ad1f83bd6a27535d31a0f82`,
balances `699b03bb6bb6d3671b4036b297f4a4e1`, movimientos
`768be12e66f88d00fe922600dc8ed69e`, compras
`82c83117758f4c618a60c116aff387f5`, almacenes
`a0e1053e829b282cbd1ef908d3f43b1f`, detalles de lote
`cc259c2d050bfa69007d224cee97a851`, impresiones
`15890262e0413bc50fa98726238209b3`, costos promedio
`5cec3996399a4d5c7b3df70e1d0aeb0f`, HUs
`1633b4797b0da36671ca80cb0f42f487`, líneas de movimiento
`eb969287d53c98e2df9e7ce6a32fb3a0`, entradas de valoración
`19d8e0060c72df785cf964963d965d46` y configuración de valoración
`ef37451e110a6d507d16b32b251456a0`. El digest vacío de aplicaciones de retaceo
es `d41d8cd98f00b204e9800998ecf8427e` en ambas bases.

La cantidad de 2,892 que aparece como suma de cantidades base es una huella de
regresión a través de varios productos/unidades; no se interpreta como una
unidad física agregada comparable.

## Pruebas

R02/R03 B01:

```text
docker compose exec -T backend python -m pytest -q tests/unit/test_preview_headquarters_migration.py tests/e2e/test_headquarters_migration_preserves_inventory.py tests/e2e/test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope
7 passed in 50.69s
```

Regresiones de unidad e integración B02 (13 módulos enfocados):

```text
docker compose exec -T backend python -m pytest tests/unit/test_branch_schema.py tests/unit/test_warehouse_schema.py tests/unit/test_document_warehouse_branch_scope.py tests/unit/test_inventory_lots_api_contract.py tests/unit/test_inventory_label_prints.py tests/unit/test_inventory_kardex.py tests/unit/test_inventory_putaway_group_schema.py tests/unit/test_inventory_trace_capability.py tests/unit/test_purchase_inventory_safety.py tests/integration/test_inventory_kardex_repository.py tests/integration/test_inventory_split_prepare_route.py tests/integration/test_inventory_movement_idempotency.py tests/integration/test_inventory_valuation_repository.py -q
82 passed in 22.72s
```

E2E enfocado (ejecutado en serie porque reconstruye `erp_db_test`):

```text
docker compose exec -T backend python -m pytest tests/e2e/test_branch_isolation.py tests/e2e/test_company_mother_warehouse_catalogue.py tests/e2e/test_headquarters_migration_preserves_inventory.py tests/e2e/test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope tests/e2e/test_inventory_block4_closure.py tests/e2e/test_inventory_lot_detail_migration.py -q
17 passed in 169.23s; 1 aviso deprecado de Starlette sobre HTTP 422
```

Al agregar una segunda prueba al archivo de migración, se repitió:

```text
docker compose exec -T backend python -m pytest tests/e2e/test_inventory_lot_detail_migration.py -q
2 passed in 31.59s
```

También se ejecutó `ruff check` sobre los módulos/pruebas afectados y pasó; en
`frontend`, `npm run check` reportó 0 errores/advertencias y el Vitest focalizado
reportó 44 aprobadas en 4 archivos. No se ejecutó aceptación visual autenticada.

## Evidencia de alcance histórico

La prueba HTTP de compra crea el documento de prueba como administrador y luego
asigna al usuario limitado permisos de recepción, verificación y lectura con
scope solo de matriz. Después deja `purchase.branch_id = NULL` en el fixture y
comprueba HTTP de detalle/listado con matriz, lectura global con administrador,
rechazo de sucursal ajena y que la respuesta siga exponiendo `branch_id = NULL`.
No se modifica la sucursal histórica para resolver su alcance.

## Limitación visible

El estado `0085` está desplegado y la base de datos supera los chequeos
automatizados. Falta que el usuario recorra manualmente el navegador habitual:
recepción → lote por detalle → etiqueta de software → búsqueda por código nuevo
y de cabecera en Kardex. El lector HS200 y la impresora física no forman parte de
la aceptación.

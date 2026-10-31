# Evidencia ERS-B01 — 18/10/2026

## Bases y protección de datos

- E2E ejecutado con el fixture aislado `erp_db_test`, que reconstruye el esquema y aplica las migraciones para cada prueba.
- Consulta de solo lectura a la base habitual: `Database=erp_db Alembic=0083`.
- La vista previa se ejecutó con destino esperado `erp_db`. Salida relevante:

```json
{
  "database": "erp_db",
  "schema_already_has_is_headquarters": false,
  "mode": "read-only preview; no rows were changed",
  "mapping_by_company": [
    {
      "company_id": "0a7303f6-64a5-428c-a829-c2b09966fefd",
      "company": "Grupo Lorena",
      "central_warehouse_ids": ["14e5a8bc-20e6-4184-99a1-4238000eca8a"],
      "headquarters": "CREAR Casa matriz (sin coordenadas inventadas)",
      "reuse_migration_marked_branch": false,
      "address_source": "domicilio registrado de la empresa"
    }
  ],
  "validation_errors": []
}
```

No se ejecutó `alembic upgrade` sobre `erp_db`, no se hizo seed/reset de esa base y no se creó respaldo en este trabajo. El resultado no contiene credenciales ni DSN.

## Pruebas

Comando final, ejecutado en serie:

```text
docker compose exec -T backend python -m pytest -q tests/unit/test_branch_schema.py tests/unit/test_warehouse_schema.py tests/unit/test_document_warehouse_branch_scope.py tests/e2e/test_branch_isolation.py tests/e2e/test_company_mother_warehouse_catalogue.py tests/e2e/test_headquarters_migration_preserves_inventory.py tests/e2e/test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope
```

Resultado: `28 passed in 59.89s`.

Casos incluidos:

- Matriz mínima sin coordenadas, sucursal/almacén válidos y rechazo de coordenadas incompletas.
- Scope de documentos legacy que conservan `branch_id = NULL`; rechazo de matriz inactiva o cruce entre sucursales.
- Catálogo de bodega: una sucursal no recibe la central por defecto, el flujo autorizado la puede incluir; usuario global ve tanto central como tienda.
- API devuelve conflicto por segunda matriz activa; rechaza una matriz de otra empresa. PostgreSQL bloquea el mismo cruce mediante FK compuesta.
- Usuario con acceso únicamente a la matriz crea/recibe/verifica y consulta una recepción central; el mismo usuario no consulta alcance global ni otra sucursal.
- Migración conserva HUs, saldos, ubicaciones, movimientos y una cadena sintética legacy de cotización, orden y recepción; repite la migración sin duplicar matriz ni central.
- Prevalidación de centrales duplicadas no cambia la cabeza. Una prueba de fallo inyectado después de insertar la matriz verifica rollback total: se mantiene 0083, no queda columna `is_headquarters`, no queda la matriz nueva y la central sigue sin asignación.

Un primer conjunto de ejecución detectó que una prueba general de aislamiento usaba un nombre fijo que chocaba con el seed. Se cambió esa prueba a un usuario sintético único y la suite final completa pasó; no se reutilizaron ni alteraron datos de `erp_db`.

## Chequeos adicionales

- Ruff sobre los archivos de backend afectados: `All checks passed!`.
- Desde `frontend`: `svelte-check --tsconfig ./tsconfig.json` → `0 errors and 0 warnings`.
- `git diff --check` → código de salida 0. Git emitió dos avisos CRLF/LF en `PurchaseRequestDraftEditor.test.ts` y `PurchaseRequestEditor.test.ts`.
- Revisión visual independiente del cambio de B01: 8.56/10, aprobada tras corregir tres observaciones de claridad de matriz/tienda y ubicación. No es un recorrido manual del navegador.

## Límite de verificación

La base habitual todavía está en 0083; por tanto, los cambios no están activados en esa demo y no se pudo confirmar el flujo allí mediante navegador. Para terminar la aceptación hace falta el respaldo previo, ejecutar 0084 sobre `erp_db` en forma controlada y repetir un recorrido autenticado sucursal → bodega matriz → recepción.

## Actualización posterior de R01–R03 — 18/10/2026

El texto anterior registra la primera revisión, cuando la demo estaba en 0083.
Después, durante el cierre técnico solicitado al inicio de B02:

- Se verificó el respaldo pre-0084 `backups/ers_b02_erp_db_pre_0084_20261018.dump` (SHA-256 `EA02470BDA68A6D92432E976EABCCD4789EA4A2DF8FD5673D11FFACDFF9A6C3A`) y su ensayo de restauración en una base aislada.
- R01 se activó en `erp_db`; luego B02 aplicó 0085, por lo que la cabeza actual es `0085`, no 0084. La vista previa de 0084 confirma el mapeo de la bodega central existente `14e5a8bc-20e6-4184-99a1-4238000eca8a` a la matriz de Grupo Lorena y no reporta errores.
- R02 se alineó con la prevalidación de 0084. La vista previa rechaza almacenes no centrales sin sucursal y direcciones nulas o vacías como lo hace la migración. Las pruebas unitarias de la vista previa pasan.
- R03 añadió comparación de filas de valoración, promedio, entradas y aplicación de retaceo con registros sintéticos no vacíos en la prueba aislada. El E2E HTTP comprueba recepción con `branch_id = NULL`, lectura/listado por matriz y administrador global, rechazo de sucursal ajena y conservación del nulo.
- En el E2E, el administrador crea el borrador; el usuario de alcance limitado a matriz recibe, verifica y lee. No se afirma que el rol limitado cree el borrador.
- Siete pruebas seleccionadas R02/R03 pasaron el 18/10/2026. La aceptación visual autenticada de sucursal → central → recepción en la demo sigue pendiente.

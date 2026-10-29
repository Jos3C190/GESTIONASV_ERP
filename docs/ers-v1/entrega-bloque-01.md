# Entrega ERS-B01 — Sucursal matriz y bodega central

> **Actualización vigente — 18/10/2026:** B01 tiene la migración 0084 aplicada
> en `erp_db`; R01–R03 cuentan con respaldo/ensayo y pruebas técnicas descritos
> en el cierre agregado al final de esta entrega y en `revision-bloque-01.md`. La demo quedó luego
> en 0085 al activar B02. El recorrido visual autenticado en la demo sigue
> pendiente; el estado global de B01 es **Parcial con impedimento documentado**,
> no aceptación completa. Las secciones de estado inicial y el procedimiento de
> activación que siguen reflejan la entrega original y quedan supersedidos por
> este cierre.

**Fecha:** 18/10/2026  
**Estado:** Implementado y probado en base aislada. La demo habitual conserva su esquema original y todavía no activa la migración 0084.  
**Referencia:** migración Alembic `0084` (`0083` → `0084`).

## 1. Alcance

Se agregó una identidad explícita de matriz administrativa por empresa y se vinculó funcionalmente la bodega central a esa matriz. La matriz representa recepción y distribución; puede carecer de coordenadas físicas y no se trata como punto de venta. La bodega central conserva su ID. La migración no copia ni vuelve a crear ubicaciones, unidades logísticas, existencias o movimientos.

Al redactarse la entrega inicial, la base aislada pasó las pruebas descritas abajo y la base habitual `erp_db` seguía en `0083`; el respaldo, migración 0084 y recorrido en esa base aún estaban pendientes. El cierre técnico posterior de R01–R03 se registra en la actualización al final de este informe.

## 2. Requisitos y decisiones

- `Branch.is_headquarters` identifica la sede matriz. Un índice parcial admite como máximo una matriz activa por empresa.
- Todo almacén debe tener sucursal. Una bodega con `is_central = true` solo puede asociarse a la matriz activa de su empresa.
- Si la empresa no tiene una matriz identificada, 0084 crea “Casa matriz” usando su domicilio y geografía registrados; deja latitud y longitud vacías. El script de vista previa diagnostica datos faltantes antes de cualquier escritura.
- La relación matriz no cambia membresías ni permisos. Una cuenta limitada a la matriz puede operar documentos asignados a la bodega central, sin recibir acceso a las sucursales comerciales.
- Los documentos centrales anteriores conservan `branch_id = NULL`. Su alcance se resuelve desde `warehouse_id`; no se reescribe su historia.
- El usuario excluyó lector y colocación física de etiquetas del alcance demostrativo; este bloque tampoco los requiere.

## 3. Cambios principales

- `backend/alembic/versions/0084_explicit_headquarters_branch.py`: migración transaccional, prevalidaciones, mapeo por empresa, integridad de matriz/central y downgrade conservador.
- `backend/scripts/preview_headquarters_migration.py`: vista previa de solo lectura con validación del nombre exacto de la base y mapa central por empresa.
- Modelos y API de organización: marca de matriz, validación de empresa/sucursal, creación mínima y prevención de matrices duplicadas.
- Autorización y repositorios de compras, órdenes, cotizaciones y retaceo: lectura de documentos históricos por su bodega original y filtrado por matriz sin modificar su `branch_id` histórico.
- Frontend: edición y detalle de bodega muestran la matriz; la tabla, el detalle y el mapa de sucursales evitan presentar la matriz administrativa como una tienda física.
- Documentación actualizada: `docs/api.md`, `docs/database-schema.md`, `docs/rbac-model.md`, esta entrega y la guía/matriz ERS.

## 4. Migración, datos y recuperación

La información que sigue en esta sección y en la entrega inicial describe el
estado observado antes del cierre posterior de R01–R03. La actualización vigente
se encuentra en el aviso al inicio del documento y en el cierre fechado al final.

### Vista previa observada en la demo

Comando de solo lectura:

```text
docker compose exec -T backend python scripts/preview_headquarters_migration.py --expect-database erp_db
```

Resultado: base `erp_db`, esquema sin `is_headquarters`, sin errores de validación. Para Grupo Lorena, la vista previa propone crear una matriz mínima y asociarle la bodega central existente `14e5a8bc-20e6-4184-99a1-4238000eca8a`. La procedencia de domicilio/geografía es el registro de la empresa; no se inventan coordenadas.

La cabeza consultada después fue `erp_db / 0083`. La ejecución no hizo cambios en esta base. La salida completa está en [evidencia fechada](../../tmp/ers-v1/bloque-01/evidencia-2026-10-18.md).

### Procedimiento para activar 0084 en la demo

1. Confirmar que el destino es `erp_db` y guardar una copia restaurable de PostgreSQL fuera del contenedor. Registrar `current_database()` y `alembic_version` antes del cambio.
2. Ejecutar nuevamente la vista previa; resolver cualquier error y validar el mapeo empresa → matriz → bodega con quien administra los datos.
3. Aplicar `alembic upgrade 0084` únicamente después de confirmar y validar el respaldo. El `upgrade` de PostgreSQL es transaccional.
4. Confirmar `alembic_version = 0084`, comparar el ID y los saldos de la bodega, y recorrer sucursal, bodega y una recepción central en el navegador.
5. Si algo falla, preferir restaurar la copia previa y dejar la aplicación en una versión compatible con ese esquema. El `downgrade 0083` conserva la fila de matriz pero devuelve la central a `branch_id = NULL`; usarlo solo si no hubo operaciones nuevas después de migrar y luego de validar la reversión.

**No se ha creado ni aplicado un respaldo o migración en la demo en esta entrega.**

## 5. Aceptación

| Criterio | Comprobación | Resultado | Evidencia |
|---|---|---|---|
| B01-A1: preservar inventario e historial | E2E migra una central legacy con ubicación, HU, saldo, movimiento y una cadena sintética de cotización/orden/recepción; compara IDs y filas antes/después. | Aprobado en `erp_db_test`. La cadena legacy se crea sintéticamente porque no se asume que el seed E2E contenga esos documentos. | `test_migration_preserves_central_warehouse_inventory_and_purchase_history` |
| B01-A2: idempotencia y ambigüedad | Repite `0083 → head`, verifica el mismo ID de matriz y una central/matriz activa; provoca centrales duplicadas y comprueba que el esquema sigue en 0083. | Aprobado en base aislada. | Prueba de migración e `test_duplicate_central_warehouses_fail_without_partial_migration` |
| B01-A3: aislamiento entre empresas y unicidad | API rechaza una bodega central cuyo `branch_id` pertenece a otra empresa; la FK compuesta rechaza la misma relación a nivel PostgreSQL; API rechaza crear una segunda matriz activa. | Aprobado en E2E aislado. | `test_branch_scoped_catalogue_includes_mother_only_when_requested` |
| B01-A4: alcance de sucursal, matriz y global | Usuario con acceso solo a matriz recibe/verifica una recepción central; se le niega lista global y sucursal ajena. Usuario global consulta la bodega central y una bodega de tienda. Se conserva la regresión de aislamiento de sucursal. | Aprobado en pruebas API/E2E aisladas. | `test_headquarters_user_can_read_new_central_receipt_without_global_scope`, prueba de catálogo y `test_restricted_user_cannot_cross_branch_boundary` |
| B01-A5: compras nuevas e históricas | Crea y verifica una recepción central nueva con `branch_id` matriz; resuelve acceso al documento histórico con sucursal nula vía bodega y mantiene sus columnas/IDs durante migración. | Aprobado en base aislada. | E2E de recepción y `test_legacy_null_branch_uses_the_central_warehouse_headquarters` |
| B01-A6: recuperación y cabeza Alembic | Inyecta fallo tras crear la matriz pero antes de asociar la central; comprueba rollback de columna, fila nueva, relación y cabeza. También prueba error de prevalidación por centrales duplicadas. Registra cabeza de la demo. | Rollback probado; demo documentada en 0083 y pendiente de aplicación. No se afirma activación en la demo. | `test_mid_mapping_failure_rolls_back_schema_headquarters_and_warehouse_link`; vista previa de solo lectura |

## 6. Validaciones ejecutadas

- Suite focalizada, ejecutada en serie sobre el fixture E2E aislado `erp_db_test`: **28 aprobadas** en 59.89 s.
- Ruff sobre módulos y pruebas afectados: **All checks passed**.
- `svelte-check --tsconfig ./tsconfig.json`: **0 errores y 0 advertencias**.
- `git diff --check`: pasó; Git reportó avisos existentes de conversión CRLF/LF en dos pruebas de compras.
- Revisión visual independiente del cambio de sucursal/bodega: aprobada con 8.56/10. Esa revisión no sustituye el recorrido autenticado en la demo pendiente.

Los comandos concretos están registrados en la evidencia fechada.

## 7. Uso visible y pendientes

Después de aplicar 0084, en el detalle/edición de la bodega central debe verse su sucursal matriz. En el selector de almacenes, la central puede incluirse en los flujos de sucursal únicamente si el usuario tiene alcance sobre la matriz o es global. La matriz aparece como sede administrativa y el navegador no le atribuye coordenadas físicas inexistentes.

Pendiente para cerrar la aceptación del bloque: respaldo restaurable de `erp_db`, aplicación controlada de 0084, confirmar la cabeza 0084 y recorrido autenticado de sucursal → bodega matriz → recepción central en el navegador. B02 no se inicia con esta entrega.

## 8. Cierre técnico R01–R03 — 18/10/2026

| Pendiente de revisión | Cierre técnico | Evidencia/resultados |
| --- | --- | --- |
| R01 — activar 0084 con recuperación | Se verificó respaldo externo, restauración y ensayo aislado. 0084 se aplicó a `erp_db` antes de B02; la cabeza actual pasó a 0085 al ejecutar B02. La bodega central existente y su ID se conservaron. | `backups/ers_b02_erp_db_pre_0084_20261018.dump`, SHA-256 `EA02470BDA68A6D92432E976EABCCD4789EA4A2DF8FD5673D11FFACDFF9A6C3A`; ver evidencia B01/B02. No hubo reset/seed. |
| R02 — reglas de vista previa | Se alinearon la dirección vacía/nula y bodegas no centrales sin sucursal con las precondiciones de 0084. El preflight real con destino esperado `erp_db` no reporta impedimentos. | `tests/unit/test_preview_headquarters_migration.py`; 7 pruebas combinadas R02/R03 aprobadas. |
| R03 — valoración y recepción histórica | La migración aislada conserva un promedio, entrada de valoración y aplicación de retaceo sintéticos no vacíos. El E2E HTTP prueba detalle/lista de recepción legacy con `branch_id = NULL`, acceso matriz/global, rechazo de sucursal ajena y conserva el `NULL`. | `test_headquarters_migration_preserves_inventory.py` y `test_headquarters_user_can_read_new_central_receipt_without_global_scope`; 7 pruebas combinadas R02/R03 aprobadas. |

En la prueba HTTP el administrador crea el borrador; el rol de matriz tiene
permiso de recepción, verificación y lectura. No se atribuye creación al rol
limitado. La API documenta `POST` para crear bodegas y `PATCH
/api/v1/warehouses/{record_id}` para editarlas.

**Pendiente de aceptación B01:** recorrido visual autenticado en el navegador
habitual, desde sucursal matriz a bodega central y recepción. B01 queda parcial
hasta ese recorrido; el hecho de estar en 0085 confirma su esquema, pero no
sustituye aceptación visual.

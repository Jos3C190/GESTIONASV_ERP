# Revisión ERS-B01 y entrada a B02

Fecha: 18/10/2026. Alcance: revisión de código, encargo, pruebas y documentación; no implementación de B02 ni modificación de la demo.

## Dictamen

La implementación base es aprovechable y la suite focalizada vuelve a pasar: **28 pruebas aprobadas en 65.64 segundos**. B01 permanece **Implementado con cierre pendiente**, no aceptado íntegramente en la demo. Las correcciones y comprobaciones siguientes quedan incorporadas al inicio del encargo B02.

Se revisaron la migración 0084, su vista previa, resolución de alcance de documentos por bodega, modelo de lotes existente, pruebas de migración y recepción central y los informes. Esta revisión no acredita por sí sola todo el ERP ni reemplaza un recorrido autenticado.

## Hallazgos y pendientes

### ERS-B01-R01 — Activación pendiente (alta, despliegue)

Se volvió a ejecutar `docker compose exec -T backend alembic current`: **0083**. La vista previa de solo lectura confirma ausencia de `branches.is_headquarters`, propone crear Casa matriz para Grupo Lorena y conserva la central `14e5a8bc-20e6-4184-99a1-4238000eca8a`. No detecta errores en los datos que comprueba.

El código nuevo consulta esa columna y exige la relación matriz/central. Por tanto, no se puede considerar lista la demo con el esquema anterior. Esto es una incompatibilidad deducida del código y esquema, no una afirmación de haber reproducido un error HTTP en navegador durante esta revisión.

Cerrar con respaldo restaurable, ensayo, migración controlada y recorrido sucursal → central → recepción antigua/nueva. No reiniciar ni resembrar la demo.

### ERS-B01-R02 — Vista previa y migración no validan exactamente lo mismo (media)

`backend/scripts/preview_headquarters_migration.py` no comprueba almacenes no centrales sin sucursal; `0084_explicit_headquarters_branch.py::_validate_before_writes` sí los rechaza. Además, la vista previa rechaza dirección vacía por falsedad, mientras la migración solo comprueba NULL. Un informe previo sin errores no equivale a haber superado todas las precondiciones del cambio.

Unificar criterios y añadir pruebas de discrepancia. Si una restricción de 0083 impide construir cierto dato inválido, demostrarlo o simularlo exclusivamente en base aislada; no alterar restricciones de la demo. No se observó este dato inválido en la demo actual.

### ERS-B01-R03 — Evidencia de aceptación incompleta (media, cobertura)

- B01-A1: `preserved_tables` en la prueba de migración conserva filas físicas y documentos, pero no incluye `inventory_valuation_settings`, `inventory_cost_averages`, `inventory_valuation_entries` ni `inventory_retaceo_applications`. Añadir escenario valorado con datos no vacíos y comparación antes/después. No hay pérdida de costos demostrada; falta acreditar esa parte del requisito.
- B01-A5: la conservación SQL del documento histórico y el test unitario del resolver son positivos, pero no prueban el recorrido HTTP completo de una recepción histórica con `branch_id = NULL`. Añadir lectura y listado bajo usuario matriz, global y sucursal ajena; revisar también enlaces a orden y retaceo cuando existan.
- La evidencia anterior dice que el usuario limitado a matriz «crea/recibe/verifica». El test crea el borrador con `admin_headers`; el usuario limitado recibe, verifica y consulta. Corregir la afirmación o ampliar explícitamente el test si crear es parte del contrato autorizado. La descripción del rol de prueba como `Read-only` tampoco refleja sus permisos de recepción/verificación.
- `docs/api.md` describe `POST/PUT /api/v1/warehouses`; cotejar y documentar la ruta real de modificación (`PATCH /api/v1/warehouses/{record_id}`).

## Verificación repetida

Ejecutada secuencialmente sobre el entorno aislado de pruebas:

```text
docker compose exec -T backend python -m pytest -q tests/unit/test_branch_schema.py tests/unit/test_warehouse_schema.py tests/unit/test_document_warehouse_branch_scope.py tests/e2e/test_branch_isolation.py tests/e2e/test_company_mother_warehouse_catalogue.py tests/e2e/test_headquarters_migration_preserves_inventory.py tests/e2e/test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope
```

Resultado: `28 passed in 65.64s (0:01:05)`.

También se repitieron `preview_headquarters_migration.py --expect-database erp_db` y `alembic current`, ambos de lectura. No se creó respaldo, migró o modificó información de la demo en esta revisión. Ruff, Svelte y la valoración visual citados en la entrega anterior no se repitieron: aquí solo se modificó documentación.

## Encargo siguiente

Ejecutar `docs/ers-v1/prompt-luna-bloque-02-lotes.md`: comienza cerrando R01–R03 y continúa con lotes por detalle, etiquetas, búsqueda en Kardex y proyección por ubicación. No rehacer B01 ni adelantar B03.

## Cierre técnico R01–R03 — actualización del 18/10/2026

Esta sección conserva el dictamen histórico anterior y registra el resultado
posterior del encargo B02. Los hallazgos quedaron cerrados técnicamente; la
aceptación visual de B01 en el navegador habitual sigue pendiente.

| Hallazgo | Resultado actual | Evidencia |
| --- | --- | --- |
| R01 — activación y recuperación | `erp_db` se respaldó fuera del contenedor, se restauró a una base temporal y se ensayó allí la migración. La demo recibió 0084 y posteriormente 0085. La consulta actual devuelve `erp_db / 0085`; el mapeo mantiene la bodega central `14e5a8bc-20e6-4184-99a1-4238000eca8a` y la matriz de la misma empresa. No hubo reset ni seed de la demo. | Evidencia B01/B02; respaldo previo a 0084: `backups/ers_b02_erp_db_pre_0084_20261018.dump`. |
| R02 — prevalidación | La vista previa valida almacenes no centrales sin sucursal y dirección nula o vacía igual que 0084. Sus pruebas unitarias pasan y la vista de solo lectura sobre `erp_db` no informa errores. | `tests/unit/test_preview_headquarters_migration.py`; vista previa `--expect-database erp_db`. |
| R03 — datos valorados y alcance histórico | La prueba de migración compara filas no vacías de valoración, promedio, entradas y aplicación de retaceo antes/después. La prueba HTTP convierte una recepción de prueba en histórica con `branch_id = NULL` y comprueba detalle/lista para matriz y global, rechazo de sucursal ajena y conservación del campo nulo. | `tests/e2e/test_headquarters_migration_preserves_inventory.py`, `tests/e2e/test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope`; siete pruebas seleccionadas de R02/R03 pasaron. |

**Corrección de alcance del usuario de prueba:** el administrador crea el borrador
de recepción; el rol de alcance limitado a matriz recibe, verifica y consulta la
recepción. No se afirma que ese usuario limitado cree el borrador. Su descripción
en la prueba indica permisos de recepción/verificación/lectura, no solo lectura.
La documentación de bodegas especifica `POST` para crear y `PATCH
/api/v1/warehouses/{record_id}` para modificar.

**Pendiente de aceptación:** abrir la demo en navegador y recorrer sucursal
matriz → bodega central → recepción, verificando selección y permisos. Las
validaciones actuales cubren API, PostgreSQL y esquema; no sustituyen ese paso.

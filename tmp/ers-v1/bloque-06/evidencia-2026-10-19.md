# Evidencia técnica ERS-B06 — 19/10/2026

## Base y migración 0088

- Base productiva/demo: `erp_db`. Cabeza inicial: `0087`; cabeza final
  verificada: `0088`.
- Respaldo pre-migración: `erp_db-before-0088-20261019.dump`, formato custom,
  953,623 bytes. SHA-256:
  `2E662D9F4FB7F86597DC733902F76F214AC524BA87EC1D399C3172363549A4F9`.
  El archivo pasó `pg_restore --list`.
- El `pg_dump` de host 15 rechazó el servidor PostgreSQL 16 antes de producir
  un respaldo. Se detuvo el intento y se generó el dump con el cliente 16 del
  contenedor de base de datos.
- Restauración en la base aislada `b06_rehearsal_20261019`, versión inicial
  `0087`; `alembic upgrade 0088` finalizó correctamente. Las huellas de tablas
  físicas/valoración coinciden antes y después.
- La huella inicial de `erp_db` coincidía con el respaldo y la copia de
  ensayo. Se aplicó `alembic upgrade 0088` y se comprobó nuevamente la versión
  y las huellas. La migración agrega tablas/constraints/permisos; no actualiza
  filas históricas de inventario.
- El E2E reconstruye únicamente `erp_db_test`. No se ejecutaron seeds
  destructivas en `erp_db`.
- Consulta final de demo: `alembic_version=0088`; están presentes las seis
  tablas B06 y los diez permisos `sales_*` definidos para esta revisión.
- La demo conserva `sales=0`, `sales_customers=0` y `sales_quotations=0`;
  no se sembraron documentos comerciales de prueba allí.

## Conciliación de inventario

Cada entrada presenta `filas | MD5 de filas serializadas` y coincide en las
capturas pre/post del ensayo y de demo (más la captura inmediata anterior a
aplicar la migración en demo):

| Tabla | Filas | Huella |
| --- | ---: | --- |
| `inventory_items` | 12 | `54b63dd25ddf03652cbcbf2ea795ec07` |
| `inventory_handling_units` | 25 | `cacb9f93b3aa207234d57ed4dc399c8d` |
| `inventory_balances` | 27 | `62cdc7f52733fb5e495d021bd87589ea` |
| `inventory_capacity_reservations` | 0 | `d41d8cd98f00b204e9800998ecf8427e` |
| `inventory_movements` | 65 | `1d71b15bb795f7269deb68a8d95cdd7d` |
| `inventory_movement_lines` | 71 | `1ffe2a02d55e6394bf45402b721181ac` |
| `inventory_cost_averages` | 6 | `e313c84c3bf49faa1736b1dd65fea0d7` |
| `inventory_valuation_entries` | 6 | `5903e33669efed00a58c0c6cde95f4a3` |

TSV reproducibles: `erp_db-inventory-before-0088.tsv`,
`erp_db-inventory-immediate-before-0088.tsv`,
`erp_db-inventory-after-0088.tsv`, `rehearsal-inventory-before-0088.tsv` y
`rehearsal-inventory-after-0088.tsv`.

## Pruebas focalizadas

- Reglas de dominio: `backend/tests/unit/test_sales_domain.py` — 4 aprobadas.
  Comando reproducible: `docker exec gestionasv_erp-backend-1 python -m pytest
  tests/unit/test_sales_domain.py -q` — `4 passed`.
- E2E: `backend/tests/e2e/test_sales_base.py` ejecutado en serie contra la
  app FastAPI y PostgreSQL. Comprueba cliente, creación/edición/confirmación
  de cotización, moneda y unidad inválidas, totales servidor, snapshots,
  vigencia, conversión paralela, replay y payload conflictivo, venta editable
  en borrador y congelada al confirmar, cancelación, inventario sin cambios,
  permisos, alcance por sucursal/empresa, carrera confirmación/edición,
  carrera cancelación/conversión, fallo de la segunda línea, fallo tardío de
  auditoría y reintento tras ambos fallos.
- Comando final serial: `docker exec gestionasv_erp-backend-1
  /opt/venv/bin/python -m pytest tests/e2e/test_sales_base.py -q` (salida
  capturada dentro del contenedor) — `1 passed in 193.18s`.
- La E2E falla intencionalmente en la segunda línea mediante un modelo
  transitorio de prueba que viola una constraint PostgreSQL; no se conserva
  ese parche fuera de la prueba. Tanto esa falla como la auditoría tardía
  dejan cero ventas, claves de idempotencia y eventos de conversión para esa
  cotización. El reintento válido después de cada rollback crea un solo
  documento completo.
- La prueba de catálogo cambia el nombre comercial después de confirmar la
  cotización; el nombre snapshoteado de la cotización y venta no cambia.
- API de perfiles reales: superusuario para comandos, lector limitado a una
  sucursal para lectura, replay bloqueado sin permiso de conversión y usuario
  sin permiso comercial (`403`). Otra compañía no obtiene el documento
  (`403/404`).
- Inventario antes/después de todos los comandos comerciales: igualdad exacta
  de conteos y huellas en las ocho tablas enumeradas arriba.
- Ruff para módulos y pruebas B06: `All checks passed!`.
- Vitest de navegación afectada: 8/8 aprobadas.
- Svelte-check: 0 errores, 8 avisos CSS preexistentes en
  `TransferOperationsPage.svelte`.
- ESLint focalizado en B06: aprobado. El lint de todo el frontend no es limpio
  por tres imports sin uso previos y ajenos a B06: `ConsolidationLine`, `Card`
  y `goto` en tres componentes de compras identificados en la entrega.
- Build frontend: aprobado.
- Aceptación autenticada/visual: no ejecutada; reservada para B08.

## Diagnósticos/correcciones encontrados durante B06

1. Un primer E2E encontró que la constraint original exigía que la metadata de
   confirmación existiera exactamente cuando el estado era `confirmed`, lo
   que impedía cancelar una venta confirmada preservando la fecha/actor. Se
   relajó la constraint para requerir metadata en `confirmed`, impedirla en
   `draft` y permitir que `cancelled` conserve la historia de confirmación.
   El caso cancelar venta confirmada pasó posteriormente.
2. Se validó que el detalle `status=expired` es una proyección de fecha local y
   no una transición persistida por tarea periódica.
3. El primer chequeo de Ruff detectó importación fuera de orden en la prueba
   E2E; se ordenó y Ruff volvió a pasar.

## Corrida final

La corrida final serial incorporó tanto la competencia confirmar/editar como
la prueba de snapshot de catálogo. Resultado: `1 passed in 193.18s`. La prueba
anterior a esos dos casos no se usa como resultado final.

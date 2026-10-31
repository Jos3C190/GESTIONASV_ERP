# Reparación del entorno habitual de Inventario — 16/10/2026

## Resultado

Se corrigió el desfase que impedía usar Retaceo, Valoración, Traslados y Kardex en el entorno habitual (`localhost:5173` → backend `localhost:8000` → `erp_db`). El código ya incluía las migraciones hasta 0083, pero la base habitual seguía en 0078. La base de pruebas estaba en 0083, por eso las pruebas anteriores no revelaron el problema del entorno que usa la demostración.

Se respaldó `erp_db`, se restauró el respaldo en una base nueva de ensayo, se ejecutaron allí las migraciones 0079–0083 y se compararon los datos. El ensayo pasó; entonces se aplicó el mismo recorrido a `erp_db`. La base habitual quedó en **0083**, igual que la cabeza actual del repositorio. No se reconstruyeron datos, no se creó una apertura de valoración y no se activaron migraciones automáticas al arrancar.

## Respaldo y ensayo

- Archivo custom de PostgreSQL, fuera del repositorio: `C:\Developer\GESTIONASV_ERP_backups\inventory-repair-20261016\erp_db-before-0079-0083-20261016.dump`.
- Tamaño: **786,198 bytes**. SHA-256: `c08dcf5b35625150b9f9f84fb884072e4f83fe812f0eee49200c32267c058d1e`.
- El respaldo se pudo listar con `pg_restore` y restaurar en la base nueva **`erp_db_inventory_repair_20261016`**. La copia se conserva para revisión; no se sobrescribió ninguna base.
- Se verificaron `DATABASE_URL` y `DATABASE_URL_SYNC` sin mostrar credenciales. Ambos apuntaron a `db:5432/erp_db` durante la migración habitual y a `db:5432/erp_db_inventory_repair_20261016` durante el ensayo.
- El ensayo 0078 → 0083 terminó correctamente. Las tablas nuevas de valoración, lotes, etiquetas y capacidades de trazabilidad permanecieron sin filas; no se generaron saldos iniciales ficticios.

## Conservación de datos

Los valores de los resúmenes de conservación fueron iguales antes y después de migrar; la copia restaurada y migrada produjo los mismos totales:

| Dato | Antes | Después |
| --- | ---: | ---: |
| Revisión Alembic | 0078 | 0083 |
| Compras | 16 | 16 |
| Detalles de compra | 21 | 21 |
| Retaceos | 14 | 14 |
| Unidades de manejo | 15 | 15 |
| Movimientos | 28 | 28 |
| Líneas de movimiento | 34 | 34 |
| Saldos físicos | 22 filas / 2,883 unidades | 22 filas / 2,883 unidades |
| HU disponibles | 14 / 2,763 unidades | 14 / 2,763 unidades |
| HU en cuarentena | 1 / 120 unidades | 1 / 120 unidades |

La comparación agrupada por empresa, artículo, bodega, ubicación y estado coincidió; SHA-256 del resumen: `68f747dfece569b0d05fdc6e1a9f979f25fd4060183fab91c936bc4094e59cf3`. Las tablas `inventory_valuation_settings`, `inventory_lots`, `inventory_lot_details`, `inventory_label_prints` e `inventory_trace_capabilities` existen, pero siguen vacías. `retaceos.applied_at` y `retaceos.applied_by` están presentes.

## Cambios de código de esta reparación

- `backend/app/api/v1/routers/health.py`: el estado de esquema ahora se compara con las cabezas Alembic incluidas con el backend, admite más de una cabeza y diferencia base inaccesible, esquema atrasado y revisión no verificable. No aplica migraciones desde el endpoint y no expone DSN ni errores SQL al cliente.
- `frontend/src/routes/(app)/transfers/+page.svelte`: los errores al cargar existencias o recepciones ya no se presentan como cero; las secciones muestran error/reintento y las operaciones que dependen de existencias quedan bloqueadas mientras falte esa lectura. Las consultas exitosas que regresan vacío siguen mostrando vacío.
- `frontend/src/lib/features/retaceos/components/RetaceoList.svelte`: el contador distingue carga/error de un total confirmado.
- Se añadieron pruebas unitarias del diagnóstico de esquema y del estado de colecciones asíncronas, además de la regresión del contador de Retaceo.

## Validación ejecutada

### Código

- Backend `tests/unit/test_health_observability.py`: **5 pruebas aprobadas**.
- Ruff y formato para los archivos backend modificados: aprobados en el contenedor disponible.
- Vitest para `async-collection-state.test.ts` y `RetaceoList.test.ts`: **7 pruebas aprobadas en 2 archivos**.
- `svelte-check --tsconfig ./tsconfig.json`: **0 errores, 0 advertencias**.
- Las pruebas fueron focalizadas a los cambios de esta reparación; no se ejecutó la suite completa del ERP ni pruebas destructivas sobre `erp_db`.

### Entorno habitual y navegador autenticado

- `GET /health/ready`: **`status: ok`**; base y esquema reportados como `ok` y los demás componentes incluidos en ese health check también reportaron `ok`.
- El backend no registró errores 500, `UndefinedColumnError`, `UndefinedTableError` ni tracebacks en los 30 minutos posteriores a la actualización.
- **Retaceo:** lista de 14 registros cargada y se abrió `RET-00014` en modo lectura.
- **Valoración:** la página cargó sin error. No hay corte de apertura aprobado; por eso informa valoración inactiva/desconocida y no inventa costos.
- **Traslados:** cargaron existencias, unidades de manejo y pendientes por sucursal. La sección de recepciones mostró cero pendientes después de recibir una respuesta exitosa; no confundió un error de lectura con saldo cero.
- **Kardex:** cargaron movimientos físicos, valoración y conciliación. La consulta física de `PRD-EMP-009` mostró 9 movimientos; la valoración permaneció desconocida donde no existe apertura aprobada.
- El navegador conservó la sesión de `superadmin`. Las consultas y aperturas fueron de solo lectura; no se registraron compras, despachos, recepciones ni ajustes nuevos durante la comprobación.

La comprobación de Docker también mostraba `tempo` como `unhealthy` desde antes de esta reparación; no pertenece a las consultas de inventario comprobadas y no se reinició ni modificó. El health check de la aplicación sí terminó en `ok`.

## Procedimiento repetible

1. Antes de migrar, confirma que `DATABASE_URL` y `DATABASE_URL_SYNC` resuelven al mismo host/puerto/base esperados. No imprimas las URLs completas ni credenciales.
2. Para obtener un respaldo custom fuera del repositorio en PowerShell 7.4 o posterior (conserva la salida binaria de Docker):

   ```powershell
   docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d erp_db' > 'C:\Developer\GESTIONASV_ERP_backups\erp_db-before-upgrade.dump'
   ```

3. Lista el respaldo con `pg_restore --list` y restaura una copia en una base nueva, nunca encima de la original. Ensaya allí `uv run alembic upgrade head` y compara los invariantes de datos.
4. Una vez aprobado el ensayo y el respaldo, el servicio definido en `compose.yaml` puede aplicar la cabeza con `docker compose run --rm migrate`. Verifica ambos DSN del servicio antes de usarlo; ejecuta la migración de forma explícita y sin escrituras concurrentes.
5. Comprueba `alembic_version`, `GET /health/ready`, los invariantes de datos y las cuatro pantallas. Mantén `RUN_MIGRATIONS_ON_STARTUP=False`.

No se hizo downgrade ni se restauró sobre la base habitual. El HS-200, impresión física y colocación real no forman parte de este encargo, según la aclaración del usuario.

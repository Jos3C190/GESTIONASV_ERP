# Matriz de seguridad y pruebas de ubicaciones

## Controles implementados

| Riesgo | Control esperado | Evidencia automatizada |
|---|---|---|
| Cruce de empresa por UUID global | El permiso fija una empresa efectiva y el recurso se compara contra su empresa persistida | `test_company_resource_authorization.py`, `test_location_router_authorization.py` |
| Enumeración entre tenants | Una discrepancia se oculta como `404`, incluso para superusuarios | `test_cross_company_resource_is_hidden_even_from_superuser_context` |
| Contexto RBAC obsoleto | Se valida existencia de empresa y membresía actual después del permiso | `test_permission_without_current_company_membership_fails_closed` |
| Códigos variables o ambiguos | NFKC, trim, mayúsculas, padding, separador prohibido y esquema versionado | `test_location_generation.py` |
| Explosión combinatoria | Cardinalidad cartesiana máxima de 50 000 antes de persistir | `test_generator_rejects_cardinality_above_configured_limit` |
| Reintentos duplicados | Clave de idempotencia + checksum canónico | pruebas unitarias y `test_real_repository_idempotency_reuses_job_and_rejects_new_payload` |
| Publicación obsoleta | Revalidación bajo bloqueo de lote y almacén | suite PostgreSQL `test_location_repository.py` |
| Reutilización de código histórico | Alias reservado por almacén | `test_historical_alias_is_reserved_from_reuse_by_another_location` |
| Exceso de capacidad | Suma/delta revalidada bajo bloqueo del almacén | `test_bulk_update_capacity_delta_is_revalidated_under_warehouse_lock` |
| Restauración conflictiva | Índices parciales + savepoint; el original permanece eliminado | `test_location_restore_conflict_keeps_original_in_trash` |

## Frontera de archivos

- Tamaño total: de 1 byte a 20 MiB.
- Filas: máximo 50 000, con corte durante el parseo.
- CSV: UTF-8/UTF-8 con BOM; delimitadores `,`, `;`, tabulación o `|`; campo
  individual limitado a 1 000 000 caracteres.
- Encabezados: deben existir las cuatro coordenadas y no puede haber dos alias
  que representen la misma columna.
- XLSX: modo `read_only`, `data_only`, sin enlaces externos y solo extensión
  `.xlsx`. Las macros `.xlsm` no se aceptan.

Las fórmulas se leen como datos y no se ejecutan en el servidor. Si en el futuro
se exportan CSV/XLSX con contenido de usuario, el exportador debe neutralizar
valores cuyo primer carácter significativo sea `=`, `+`, `-`, `@`, tabulación o
retorno de carro para evitar formula injection al abrirlos en Excel/LibreOffice.

El límite comprimido de 20 MiB no limita por sí solo el tamaño descomprimido de
un ZIP/XLSX. Antes de elevar límites o aceptar archivos no confiables de gran
volumen, agregar preflight de ZIP: suma de tamaños descomprimidos, cantidad de
entradas y ratio de compresión.

## Ejecución segura

Las pruebas `unit` no usan I/O ni base de datos. Las pruebas marcadas
`integration` solo deben ejecutarse en el proceso configurado desde el inicio con
`DATABASE_URL_TEST`/`DATABASE_URL_TEST_SYNC` apuntando a una base cuyo nombre sea
exactamente `erp_db_test`. El `conftest.py` reconstruye esa base; nunca ejecutarlas
contra `erp_db` ni contra producción.

## Pendientes de cierre

- retirar o adaptar los endpoints heredados `/locations` de `organization.py`,
  que todavía aceptan un código escrito por el cliente;
- ejecutar la suite PostgreSQL una vez aplicada la migración solo en
  `erp_db_test`;
- verificar que `uv.lock` incluya `openpyxl` junto con el cambio de
  `pyproject.toml`;
- medir el preview de 50 000 filas y evitar consultas por fila antes de declarar
  ese volumen apto para producción.

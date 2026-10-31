# Informe final — verificación de cuatro puntos B01–B08

**Corte:** 21/10/2026 · **Entorno persistido de prueba:** `erp_db_ers_final4p_20261020`, Alembic 0090 · **Estado global:** **PARCIAL**.

## Continuación ejecutada — 21/10/2026

La continuación hizo conciliación `READ ONLY` antes/después, corrigió el helper de descubrimiento de alias para consultar el modelo vigente y recibió una evaluación estática de UI. No cambió código de producto ni repitió V04-01/02/03. Los cuatro SKU protegidos y la persistencia de esos tres casos siguen iguales. El adaptador real de RustFS completó upload → HEAD → download de un PDF ficticio de 90 bytes, con SHA-256 coincidente y limpieza del objeto; el flujo API de documentos no llegó a iniciarse porque el login de prueba devolvió 401. V03 descubrió tres pares de alias de recepción y 24 HUs históricas sin lote enlazado; ningún movimiento coincidió con el criterio consultado de literal divergente/FK de detalle nula. Esto informa la selección de datos, pero no aprueba las búsquedas UI. El intento `cua.getTab` a `localhost:5174/inventory/trace` fue rechazado por la política de seguridad de URL; no se buscó otra vía de acceso a esa sesión.

El detalle y los códigos de retorno están en [informe de continuación](continuacion-pendientes/informe-continuacion.md), [comandos](continuacion-pendientes/comandos-y-resultados.md), [log de alias](continuacion-pendientes/v03-alias-discovery.log) y [conciliación posterior](continuacion-pendientes/reconciliation-after.log). La crítica estática no superó el umbral 8.5/10 y no sustituye una revisión visual; ver [scorecard](continuacion-pendientes/critico-ui-estatico.md). El estado global se conserva **PARCIAL**: V01 permisos/documentos, V02 PNG, V03-02/03/05 y V04-04 siguen abiertos.

| Punto | Dictamen | Evidencia y límite actual |
| --- | --- | --- |
| V01 Permisos y documentos | **ABIERTO** | Hay una muestra finita de pruebas existentes por permiso/alcance y el caso de descarga documental de ajuste; el adaptador real de RustFS sí descargó bytes con hash coincidente, pero no se probaron el endpoint API, el vínculo por familia ni la matriz íntegra de acciones B01–B08: el login devolvió 401 antes de crear el documento. Ver `matriz-permisos.md`, el inventario AST `routes-b01-b08.tsv` (304 declaraciones; no acredita autorización por sí solo) y `continuacion-pendientes/real-storage-adapter-roundtrip.log`. |
| V02 Evidencia visual | **ABIERTO** | Se inspeccionaron pantallas en el navegador y se reutilizan notas de AX/UI; `capturas/` no contiene PNG y no se declara aprobada ninguna familia. Ver `manifiesto-capturas.md`. |
| V03 Recepción/trazabilidad | **ABIERTO** | La identidad de producto/HU/cabecera/detalle, el QR público y abrir/cancelar división se comprobaron; no se hizo la recepción visual de varias líneas del mismo SKU ni se consultaron todos los alias UI aplicables ni una consulta privada ajena. Ver `v03-ui-trace-qr-division-cancel-2026-10-21.md`. |
| V04 Operaciones/recuperación | **ABIERTO** | Corrección de ajuste, traslado 8+2 y devolución mixta en UI con lectura persistida aprobaron; la pérdida de respuesta postcommit no se pudo simular desde navegador. Ver `v04-ui-operations-2026-10-21.md`. |

## Defectos y observaciones reproducidos

- En primer intento de corrección de `AJ-000004`, la aplicación rechazó la acción al no existir presentación física vigente para crear una unidad en cuarentena. Se conservó esa precondición y se repitió la prueba con una presentación vigente; no se modificó el código ni se emitió una corrección huérfana.
- Al inspeccionar etiqueta de la HU, se observó representación duplicada del sufijo de unidad en una etiqueta histórica; la normalización previa de presentación ya fue incorporada y sus regresiones focalizadas permanecen aprobadas. No se cambió el contrato ni se migraron snapshots.
- Abrir/cancelar división no produjo una HU nueva ni alteró la cantidad de las HUs de control. Consultar QR sí creó una capability pública adicional en el clon (7→8); quedó documentada sin token y no afectó la demo.

## Conciliación y conservación

El baseline previo está en el [snapshot 20/10](../../2026-10-20/pasada-final/protected-skus-after-continuation.log). `reconciliation-final.log` ejecutó consultas finales con transacción `READ ONLY`. El [historial V04](transaction-history-v04.log) incluye los balances previos y eventos por SKU; la conciliación legible está en [conciliacion-final.md](conciliacion-final.md). En `erp_db_ers_final4p_20261020` y `erp_db`, los cuatro SKU protegidos coinciden con el baseline:

| SKU | Físico | Valorado | Valor USD | Resultado |
| --- | ---: | ---: | ---: | --- |
| ERS-INC-EE8FE228 | 4 | 4 | 40 | Coincide |
| ERS-LATE-B1B55D6D | 5 | 5 | 60 | Coincide |
| ERS-REVIEW-DD6BBF85 | 12 | 12 | 160 | Coincide |
| ERS-UI-F767BABC | 0 | 0 | 0 | Coincide |

Se restauró CORS de RustFS del clon a `http://localhost:5173` y `http://127.0.0.1:5173`; lectura de verificación confirmó esas dos origins y ningún puerto 5174. La demostración habitual no se reinició ni recibió escrituras.

## Pendientes concretos

1. V01: derivar y cerrar filas de permisos/alcance desde cada ruta y acción de módulos; ejecutar controles UI y acceso directo, cubrir perfiles/empresa/sucursal y descarga por endpoint API de documentos vinculados. El login del API de prueba respondió 401 antes de crear documento; el round-trip del adaptador no sustituye esas comprobaciones. El inventario estático no basta.
2. V02: obtener capacidad autorizada/documentada de guardar PNG reales para las siete familias en escritorio/móvil y ambos temas; completar el manifiesto.
3. V03: completar el recibo visual de mismo SKU (o documentar no-aplica contractual más prueba equivalente de recepciones parciales), recargar y consultar códigos aplicables; probar denegación privada ajena.
4. V04-04: completar fallo de respuesta después del commit en UI para ajuste y flujo comercial, consultar estado antes del replay y verificar un efecto/auditoría.

**Decisión:** no se declara cerrado B01–B08. No hay una corrección de producto pendiente confirmada por esta pasada; quedan abiertas pruebas de aceptación con las acciones exactas anteriores. No se requieren impresora ni lector físicos.

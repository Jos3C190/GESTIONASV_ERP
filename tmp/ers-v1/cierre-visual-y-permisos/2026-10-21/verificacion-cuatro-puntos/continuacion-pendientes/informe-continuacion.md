# Continuación ejecutada — verificación pendiente B01–B08

**Fecha:** 21/10/2026 · **Dictamen:** **PARCIAL; V01–V03 y V04-04 siguen abiertos.** No se modificó código del producto ni se repitieron V04-01/02/03. Se actualizaron solo evidencia y documentación.

## Trabajo realizado

1. Se repitió la conciliación de protección en transacciones `READ ONLY` sobre `erp_db_ers_final4p_20261020` y `erp_db`; los cuatro SKU siguen en sus cantidades y valores de referencia. También se verificó en la misma lectura el ajuste correctivo, valoración y devolución mixta ya aprobados. Salidas: `reconciliation-before.log` y `reconciliation-after.log`.
2. Se corrigió la consulta de descubrimiento V03 para usar los campos reales de `inventory_movements` (`movement_type`, `source_reference`, `posted_at`). La primera variante había usado `reference_type`/`reference_id`, columnas inexistentes en el modelo vigente; esa consulta fue de solo lectura y no cambió datos. La consulta corregida terminó con código 0 y dejó `v03-alias-discovery.log`.
3. El descubrimiento de la clon encontró tres pares de alias de recepción con HUs abiertas: `LOT-COM-00017` / `LOT-COM-00017-DA9DBC0769F114438A8C0CF242E8344D8` (PRD-CAF-011); `LOT-COM-00018` / `LOT-COM-00018-D5D319E0D778A4021B149F692E766083D` (SKU de control); y `LOT-COM-00019` / `LOT-COM-00019-D88B7BDD4045D4013B47DACFD2A8B5843` (SKU de control). Encontró 24 HUs sin lote/cabecera/detalle de recepción asociados, incluida una unidad histórica de Café. No se inventó ni editó historia. La consulta de movimientos no encontró filas que cumplieran el predicado de código literal divergente o FK de detalle ausente.
4. Se intentó un ciclo documental real por API, pero el login a `localhost:8001` con el usuario de pruebas `superadmin` devolvió **401 antes de crear el documento**. No se intentaron más credenciales. En una comprobación separada, el adaptador S3 real de RustFS sí completó upload → HEAD → download de un PDF ficticio de 90 bytes: SHA-256 de subida y descarga `5ef647a977fab5ebd71b0fa2780ff1adaae695251cea54337f410f60bd57a432`; el objeto de prueba se eliminó. Esto acredita el adaptador/almacenamiento, no los permisos, el vínculo de un módulo ni el flujo API de documentos.
5. La revisión estática independiente de UI no supera el umbral de 8.5/10 y no aprueba aceptación visual; accesibilidad obtuvo 6.5/10. Está separada de la evidencia de navegador. Ver `critico-ui-estatico.md`.

## Casos que siguen abiertos

| Caso | Estado | Impedimento comprobado y siguiente acción |
| --- | --- | --- |
| V01-01…04 — permisos y documentos | **ABIERTO** | La evidencia histórica cubre casos concretos, pero no el mapa acción/ruta/perfil/ámbito completo ni bytes API descargados desde almacenamiento real en todas las familias. El adaptador de RustFS pasó su round-trip, pero el login del API devolvió 401 antes de crear un documento y la UI no se pudo abrir en esta sesión. Siguiente acción: usar un actor/sesión de prueba autorizada para completar el ciclo de documentos vinculados, descarga API real y denegaciones UI/API por familia. |
| V02-01…07 — evidencia visual | **ABIERTO** | El directorio de capturas sigue vacío. `cua.getTab` para `http://localhost:5174/inventory/trace` fue rechazado por la política de seguridad de URL del navegador. No se usó ni se probará un mecanismo alterno para extraer la misma sesión. Siguiente acción: ejecutar desde una sesión/herramienta con exportación de PNG documentada y permitida; archivar las siete familias del manifiesto. |
| V03-02 — recepción repetida | **ABIERTO** | No se pudo ejecutar la recepción por UI. El contrato y las E2E previas se mantienen, pero no sustituyen el recorrido y la recarga solicitados. Siguiente acción: recibir por el flujo normal de UI y documentar origen, líneas y cantidades. |
| V03-03 — alias | **ABIERTO** | Descubrimiento SQL de solo lectura identifica datos aplicables, pero no prueba búsquedas desde etiqueta/QR/Kardex. El filtro por código bruto histórico no tuvo un registro divergente aplicable en la consulta; las HUs sin recepción no deben convertirse en un lote ficticio. Siguiente acción: en sesión UI autorizada probar cabecera y detalle de `LOT-COM-00017`; documentar no-aplica con el log para variantes sin datos y verificar en la UI su resolución. |
| V03-05 — privacidad | **ABIERTO** | No se pudo ejecutar desde UI la consulta privada de un recurso ajeno. Siguiente acción: prueba con actor restringido ficticio y recurso ajeno, tanto UI como petición directa, cuando haya sesión/herramienta autorizada. |
| V04-04 — pérdida postcommit | **ABIERTO** | No se simuló una respuesta perdida tras persistencia. El mecanismo previo no fue ejecutado. La política bloqueó la adquisición de la página del navegador y el encargo prohíbe intentar variaciones para eludir un rechazo. Siguiente acción: usar una capacidad autorizada/documentada que descarte solo la respuesta tras el commit; consultar primero y después reintentar con la misma clave. |

## Resultado de producto

No se reprodujo un defecto nuevo; por ello no se hizo un cambio funcional ni una migración. V04-01/02/03 permanecen aprobados y no se reescribieron. La demostración habitual no recibió escrituras. Los SKU protegidos coinciden antes y después. No se declara cerrada la implementación/verificación B01–B08: la aceptación sigue parcial hasta cerrar los casos originales abiertos con evidencia.

## Referencias

- `reconciliation-before.log`, `reconciliation-after.log` — lectura de conciliación.
- `v03-alias-discovery.log` y `readonly-v03-alias-discovery.py` — aliases hallados en la clon; todo SQL usa transacción de solo lectura.
- `real-storage-adapter-roundtrip.py` / `.log` — lectura/escritura de un objeto S3 ficticio, hash coincidente y eliminación verificada por llamada sin error.
- `critico-ui-estatico.md` — revisión de código de UI, sin observación en vivo.
- `../informe-final.md` y `../registro-casos.md` — registro canónico de puntos/casos actualizado.

# Encargo para Luna — reparar el entorno habitual de Inventario

## Objetivo

Restablecer Retaceo, Valoración, Traslados y Kardex en **http://localhost:5173**, conectado al backend habitual `8000` y su base `erp_db`, conservando los datos existentes. Completar el despliegue de las migraciones que ya existen y comprobar las cuatro pantallas contra ese entorno. No basta con que funcione en `erp_db_test`.

Lee `.agents/AGENTS.md` y aplica `feature-development`. Trabaja sobre el estado actual, conservando los cambios de otros agentes. Este es un encargo de corrección y despliegue local, no otro bloque funcional ni un rediseño.

## Diagnóstico comprobado el 16/10/2026

La revisión anterior aprobó pruebas aisladas y presentó el sistema como listo para demostración. Esa conclusión omitió comprobar la versión de la base habitual. Las capturas del usuario muestran errores reales; la aceptación del entorno habitual sigue pendiente.

Se consultaron ambos esquemas en transacciones de **solo lectura**, usando la configuración efectiva del contenedor `gestionasv_erp-backend-1`, sin imprimir credenciales:

| Dato | Entorno habitual | Entorno de pruebas |
| --- | --- | --- |
| Host / puerto | `db:5432` | `db:5432` |
| Base | `erp_db` | `erp_db_test` |
| `alembic_version` | **0078** | **0083** |
| `inventory_valuation_settings` | Ausente | Presente |
| `inventory_lots` / `inventory_lot_details` | Ausentes | Presentes |
| `inventory_label_prints` | Ausente | Presente |
| `inventory_trace_capabilities` | Ausente | Presente |
| `retaceos.applied_at` / `applied_by` | Ausentes | Presentes |

Los logs del backend habitual confirman:

- `GET /api/v1/retaceos?page=1&size=20`: **500**, `UndefinedColumnError: column retaceos.applied_at does not exist`.
- `GET /api/v1/inventory/valuation`: **500**; falta `inventory_valuation_settings`.
- `GET /api/v1/inventory/warehouses/{id}/transfer-units?stock_status=in_transit`: **500**, `UndefinedTableError: relation "inventory_lots" does not exist`.
- `GET /api/v1/inventory/kardex/reconciliation?page=1&page_size=50`: **500**, falta `inventory_valuation_settings`.

**Causa principal confirmada:** el código actualizado consulta estructuras introducidas entre 0079 y 0083, pero esas migraciones no se aplicaron a `erp_db`. No es un problema del lector, del tema visual ni prueba de que se hayan perdido las existencias.

La configuración efectiva tiene `RUN_MIGRATIONS_ON_STARTUP=False`. `compose.yaml` documenta que en desarrollo las migraciones son un paso explícito y tiene un servicio `migrate`. Recargar código no garantiza ejecutar ese servicio de nuevo. No se ha demostrado el evento exacto por el que quedó pendiente la actualización; no inventes un fallo de ejecución si los logs no lo acreditan.

Hay dos observaciones adicionales:

1. `backend/app/api/v1/routers/health.py` conserva `EXPECTED_SCHEMA_REVISION = "0043"`. Actualizar el esquema sin corregir ese diagnóstico seguirá mostrando una versión equivocada.
2. Traslados muestra el error y simultáneamente «No hay existencias liberadas» y contadores 0. Un fallo de lectura no demuestra saldo cero. Revisar el estado de error de las secciones afectadas, sin ocultar datos de otras consultas que sí terminaron correctamente.

## 1. Confirmar destino y preparar actualización sin pérdida de datos

1. Revalida contenedores, configuración efectiva, ambas URLs de base —asíncrona y síncrona— y revisión real. Muestra solamente host, puerto y nombre de base. `backend/alembic/env.py` prioriza `DATABASE_URL_SYNC`; verificar una sola URL no es suficiente.
2. Lee las revisiones 0079–0083 completas. Obtén la cabeza real del repositorio; la comprobada es 0083. Si hay nuevas revisiones ajenas al encargo, examínalas antes de extender la actualización.
3. Obtén un respaldo PostgreSQL en formato custom de `erp_db`, con nombre fechado, fuera del control de versiones y sin exponer su contenido ni secretos. Verifica que sea legible y restaura una copia en una base desechable nueva, identificada expresamente para esta reparación. No sobrescribas bases existentes. Registra ruta, destino y resultado.
4. Antes de migrar, registra revisión y un resumen de conservación: número de compras, detalles, retaceos, HU, movimientos y balances; cantidades por empresa/artículo/ubicación/estado. No vuelques datos sensibles al informe.
5. Ensaya **0078 → 0083** en la copia restaurada y compara esos invariantes. Las pruebas anteriores desde un esquema vacío o desde 0082 no sustituyen esta comprobación con historia real. La copia es únicamente para migración y lecturas: no inicia OCR, mantenimiento, correos ni otros workers.
6. Con respaldo verificado y ensayo correcto, aplica el mismo recorrido mediante Alembic a la base habitual. Al ejecutar este encargo se solicita esta actualización local conservadora; no es una autorización para reconstruir datos. Usa el servicio de migración existente o el comando equivalente con los dos DSN comprobados. Comunica el comienzo de la actualización y evita escrituras concurrentes durante ese intervalo. Reinicia solo el backend si es necesario renovar conexiones; no reinicies todo el stack.
7. Comprueba versión, tablas, columnas e invariantes después de la actualización. Ante un fallo conserva el error y el respaldo; no improvises un downgrade ni una restauración sobre la base original.

**Prohibiciones:** no `drop/create schema` en `erp_db`, no `alembic stamp`, no recrear volúmenes, no reset, seed/`bootstrap(force=True)`, ni pytest contra la base habitual. No reescribas migraciones históricas para aparentar que se aplicaron. Si descubres un defecto de migración real, documenta la corrección compatible y pruébala primero en la copia. No habilites migraciones automáticas en cada hot reload.

No crees una apertura de valoración, costos estimados, lotes retroactivos ni confirmaciones físicas para hacer desaparecer errores. Si la empresa no tiene una apertura aprobada, la respuesta correcta es valoración inactiva o importe desconocido según el contrato actual. Mantén la compatibilidad de HU históricas y la política de etiquetas de 0083.

## 2. Corregir diagnóstico y estados de carga

- Haz que el diagnóstico de esquema compare con la cabeza del código desplegado, usando la infraestructura Alembic existente, en lugar de mantener otra constante obsoleta. Prueba coincidencia, esquema atrasado y error de consulta. Conserva contratos y no expongas DSN ni SQL al cliente. No apliques migraciones desde `/health`.
- Documenta un procedimiento breve y repetible para comprobar/aplicar migraciones al actualizar el código local. Una comprobación de versión debe detectar el desfase antes de declarar el entorno listo. No hace falta crear un sistema nuevo de despliegue.
- En `frontend/src/routes/(app)/transfers/+page.svelte`, distingue carga fallida de resultado vacío en las secciones afectadas. Si falla cargar existencias, muestra error/reintento y no afirmes que hay cero productos; bloquea acciones que dependan de esa lectura. No tapes fallos retornando arrays vacíos o HTTP 200 ficticios. Respeta los controles existentes de contexto y respuestas tardías.
- Revisa el contador de Retaceo durante un error: el número 0 inicial no debe presentarse como un total confirmado si falló la consulta.
- Cambios mínimos de estado y texto: conserva diseño, permisos, políticas de costos y flujos acordados.

## 3. Aceptación exigida

### Pruebas automatizadas

- Regresiones focalizadas del diagnóstico de esquema y del tratamiento de errores/resultado vacío que cambies.
- Si ejecutas integración/E2E, lee primero `backend/tests/conftest.py`: reconstruye esquemas. Verifica **ambos DSN hacia `erp_db_test`** y ejecuta suites destructivas en serie. Nunca uses esas fixtures sobre la copia con historia ni sobre `erp_db`.
- Reutiliza las pruebas existentes. Las cuatro suites SQL de Kardex/valoración/movimientos/preparación ya pueden correrse juntas: la última revisión aisló las empresas de las pruebas concurrentes. No reviertas ese cambio.
- Tipos/lint/format y build cuando corresponda a los archivos cambiados. Distingue resultados ejecutados de evidencia anterior.

### Entorno habitual y navegador

Verifica con la sesión autorizada del usuario en `localhost:5173`, sin fabricar tokens ni solicitar que comparta contraseñas. Si falta sesión, pide únicamente que inicie sesión. No registres nuevas compras, despachos ni recepciones reales para probar lecturas.

1. **Retaceo:** lista y filtros cargan; abre un registro existente sin modificarlo. No hay errores de `applied_at` ni un falso total cero por fallo.
2. **Valoración de inventario:** la API responde correctamente. Sin apertura, la pantalla explica ese estado; no muestra error 500 ni inventa valores.
3. **Traslados:** existencias disponibles y recepciones pendientes cargan. Distingue inventario real cero de consulta fallida. Conserva la selección y los alcances por sucursal/bodega autorizados.
4. **Kardex:** movimientos físicos y conciliación responden; valoración respeta apertura/permisos. Prueba recarga y reintento.
5. Revisa solicitudes y logs de este recorrido: ninguna de las cuatro pantallas debe seguir fallando por tablas o columnas ausentes. Si aparece otro error, diagnostícalo por su excepción real y resuélvelo dentro de este alcance.

**No se acepta nuevamente con solo `erp_db_test` aprobado.** Deben estar demostrados: esquema habitual actualizado, registros previos conservados, API habitual y cuatro pantallas funcionando. El lector HS-200, la impresión y la colocación físicas son opcionales y no forman parte de este encargo.

## 4. Entrega

1. Informe `docs/reparacion-entorno-inventario-0078-0083.md`: causa, respaldo, ensayo sobre copia, revisión antes/después, conservación de datos, cambios de código y resultados del navegador/API. Sin credenciales ni datos personales.
2. Actualiza `docs/revision-inventario-bloque-4.md` y `docs/inventario-bloque-4-cierre-operativo.md` para separar aceptación del código en pruebas y disponibilidad del entorno habitual. Marca este incidente resuelto solo tras verificar ambos.
3. Comandos reproducibles y limitaciones reales. No publiques, hagas commits ni elimines el respaldo o contenedores/volúmenes ajenos.
4. Resumen breve al usuario: qué causaba los errores, qué se corrigió y qué pantallas se comprobaron realmente.

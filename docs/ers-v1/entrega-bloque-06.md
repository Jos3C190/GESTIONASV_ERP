# Entrega ERS-B06 — base de ventas sin entrega

Fecha: 19/10/2026. Revisión de base: Alembic `0088`. Estado: implementado y
verificado técnicamente en el alcance B06. La aceptación integrada/autenticada
de navegador sigue diferida a B08 por decisión del usuario. B07 no se inició.

## 1. Estado y alcance terminado

Se implementaron clientes básicos por empresa, catálogo de artículos
vendibles, cotizaciones con precios explícitos y conversión idempotente a una
venta en borrador. Se puede editar la venta mientras está en borrador,
confirmarla para congelar sus términos o cancelarla con motivo. Clientes,
cotizaciones y ventas tienen listas/detalles y controles por permiso y
empresa/sucursal.

La cotización y la venta no reservan, mueven ni valoran inventario. La venta
muestra `Pendiente de entrega`, cero entregado y la cantidad base completa
pendiente como proyección de solo lectura. La salida física pertenece a B07.
No se añadieron impuestos, descuentos, DTE, cobros, crédito, contabilidad,
precios derivados del costo ni ventas directas fuera de cotización.

La revisión 0088 está aplicada a la base de demostración. La migración se
ensayó en una base restaurada e independiente antes de aplicarla. Los cambios
de implementación están en el backend, frontend, migración y documentación
enumerados abajo; no se creó una revisión B07.

## 2. Requisitos y decisiones aplicadas

- Cliente con código único sin distinguir mayúsculas/minúsculas dentro de su
  empresa, nombre y contacto opcional. La desactivación conserva el cliente y
  el acceso histórico, pero bloquea cotizaciones nuevas y conversiones cuando
  ya no está activo.
- Cada cotización pertenece a una sucursal de la empresa y tiene fecha de
  vigencia local de El Salvador, inclusiva hasta el día indicado. El estado
  `expired` se proyecta al leer y se valida en los comandos; no hay tarea
  periódica de vencimiento.
- La línea utiliza artículo/variante inventariable y unidad base o empaque
  habilitado. Guarda snapshots de SKU/nombre, unidades, factor y versión de
  empaque, cantidades comercial/base y precio.
- El usuario captura el precio; el backend ignora cualquier total enviado y
  recalcula con `Decimal`. Redondea cada línea a centavos con
  `ROUND_HALF_UP` y suma las líneas ya redondeadas. Solo se admite USD; no se
  convierte moneda. El costo promedio no participa en el precio ni se expone
  en DTOs comerciales.
- Una cotización confirmada y vigente se convierte completa a una venta en
  borrador. El origen y cada línea quedan vinculados; una clave repetida
  devuelve la misma venta, y una segunda clave tampoco crea otra. Cancelar la
  venta no libera el origen para volver a convertirlo.
- Las ventas confirmadas no se editan. B06 no puede registrar una entrega;
  B07 deberá sustituir la proyección de entrega y bloquear cancelación si ya
  existe una entrega física.
- Las operaciones compuestas usan savepoint. La E2E fuerza fallo de la
  segunda línea y de una auditoría tardía; ninguno deja venta, clave de
  conversión ni evento de conversión parcial.

La demostración no constituye factura fiscal ni evidencia de cobro. El
recorrido visual autenticado, móvil/temas y cambio de contexto se mantienen
pendientes de B08, sin declararse aceptados aquí.

## 3. Archivos, contratos, migración y permisos

Backend: `backend/app/domain/entities/sales.py`,
`backend/app/application/sales/service.py`,
`backend/app/infrastructure/models/sales.py`,
`backend/app/api/v1/schemas/sales.py`,
`backend/app/api/v1/routers/sales.py`, `backend/app/api/v1/router.py`,
`backend/app/api/v1/deps.py`, `backend/app/application/rbac/catalogue.py` y
`backend/alembic/versions/0088_sales_base.py`.

Frontend: `frontend/src/lib/api/sales.ts`, `frontend/src/lib/types/sales.ts`,
`frontend/src/lib/features/sales/`, rutas bajo `frontend/src/routes/(app)/sales/`
y `frontend/src/routes/(app)/customers/`, además de navegación y títulos de
ruta.

La API completa, sus rutas y payload ejemplo están en [docs/api.md](C:/Developer/GESTIONASV_ERP/docs/api.md).
Las seis tablas y sus relaciones están en
[docs/database-schema.md](C:/Developer/GESTIONASV_ERP/docs/database-schema.md).
Los permisos nuevos son:

- Clientes: `sales_customers:read`, `sales_customers:manage`.
- Cotizaciones: `sales_quotations:read`, `sales_quotations:manage`,
  `sales_quotations:confirm`, `sales_quotations:convert`.
- Ventas: `sales:read`, `sales:manage`, `sales:confirm`, `sales:cancel`.

La revisión 0088 crea `sales_customers`, `sales_quotations`,
`sales_quotation_lines`, `sales`, `sales_lines` y
`sales_idempotency_commands`; instala índices, constraints, triggers de líneas
de borrador y permisos. El contrato para B07 está descrito en [docs/api.md](C:/Developer/GESTIONASV_ERP/docs/api.md)
y en el encargo previsto; no se crearon rutas de entrega.

## 4. Actualización y recuperación

Antes del cambio se generó un dump custom-format de `erp_db` con `pg_dump`
16 desde el contenedor PostgreSQL 16. Archivo recuperable:
`tmp/ers-v1/bloque-06/erp_db-before-0088-20261019.dump` (953,623 bytes,
SHA-256 `2E662D9F4FB7F86597DC733902F76F214AC524BA87EC1D399C3172363549A4F9`).
El archivo fue inspeccionado con `pg_restore --list`.

El dump se restauró en `b06_rehearsal_20261019`, que estaba en 0087. Allí
`alembic upgrade 0088` terminó correctamente. Las huellas de tablas físicas y
de valoración antes/después coincidieron. Se comprobó que `erp_db` tenía la
misma huella anterior que el respaldo y el ensayo. Luego se ejecutó
`alembic upgrade 0088` en `erp_db`; la cabeza resultó `0088` y las mismas
huellas volvieron a coincidir. No se actualizaron filas de inventario.

Para recuperación, restaure el dump en una base aislada y valide aplicación,
versión Alembic y conciliación antes de cualquier sustitución de la demo. No
se ensayó downgrade. `alembic downgrade 0087` elimina documentos comerciales
y tablas B06; si ya se capturaron ventas, no lo use como rollback operativo.
Primero haga otro respaldo y decida la recuperación con el dueño de la demo.
La E2E usa solamente `erp_db_test`, cuya fixture elimina/recrea su esquema;
no apunta a `erp_db`.

## 5. Criterios, pruebas y resultados

| Criterio | Prueba | Resultado | Evidencia |
| --- | --- | --- | --- |
| B06-A1 — cliente, cotización, confirmación, conversión y reintento | E2E FastAPI/PostgreSQL: totales recalculados, conversión concurrente con claves distintas, replay/conflicto y venta vinculada | Aprobado | `tmp/ers-v1/bloque-06/evidencia-2026-10-19.md` |
| B06-A2 — ninguna operación comercial altera inventario | Huellas antes/después de los comandos en 8 tablas; huellas también alrededor de la migración | Aprobado, idénticas | Evidencia fechada y TSV de inventario |
| B06-A3 — moneda/unidad/cantidad/precio y snapshots | E2E rechaza USD no soportado y unidad inválida; prueba precio enviado/total recalculado y cambia el nombre de catálogo tras confirmar sin alterar el snapshot | Aprobado en casos ejecutados | E2E `test_sales_base.py`; unit tests de dominio |
| B06-A4 — congelación de documentos confirmados | API rechaza edición de cotización y venta confirmadas; los estados de entrega no se aceptan como entrada | Aprobado | E2E `test_sales_base.py` |
| B06-A5 — permisos, empresa/sucursal, auditoría e idempotencia | E2E con superusuario, lector de una sucursal, usuario sin permisos, otra compañía, replay sin permiso, conflicto de clave y auditoría | Aprobado en perfiles focalizados | E2E `test_sales_base.py`; aceptación integrada B08 pendiente |
| B06-A6 — experiencia cliente → cotización → venta | Navegación/Vitest, tipos, Svelte-check, ESLint focalizado y build; la E2E recorre API real | Parcial: compilación y contratos verificados; no se hizo el recorrido autenticado del navegador | Registros Vitest/check/lint/build; aceptación visual B08 pendiente |
| B06-A7 — concurrencia y rollback | E2E convierte en paralelo, enfrenta confirmación con edición, enfrenta cancelar con convertir, y fuerza falla de segunda línea y auditoría tardía; reintentos no duplican | Aprobado tras corrida final | E2E `test_sales_base.py`; evidencia fechada |
| B06-A8 — migración con respaldo/ensayo y datos anteriores intactos | Restauración 0087 → migración aislada a 0088; respaldo de demo; actualización demo y comparación de huellas | Aprobado; downgrade no probado | Dump, TSVs y evidencia fechada |

Ver resumen reproducible, tiempos y fallos corregidos en
[`tmp/ers-v1/bloque-06/evidencia-2026-10-19.md`](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-06/evidencia-2026-10-19.md).

## 6. Pasos de uso y resultados visibles

El [manual de ventas base](C:/Developer/GESTIONASV_ERP/docs/ers-v1/manual-ventas-base.md)
describe el recorrido con los menús **Compras → Clientes** y
**Ventas → Cotizaciones de venta / Ventas**. El resultado es una venta
comercial confirmada con el estado **Pendiente de entrega**. No se descuenta
inventario ni se crea una factura fiscal.

## 7. Pendientes, diagnóstico y siguiente paso

- Hacer la aceptación autenticada en navegador de alta/edición de cliente,
  creación y confirmación de cotización, conversión, confirmación de venta,
  recarga, cambio de sucursal, errores y permisos. Se acumula para B08 junto
  con B01/B02 y los recorridos anteriores.
- La revisión integral debe revisar catálogo/variantes, operación de todos
  los perfiles y cualquier advertencia de integración visual. El flujo
  frontend tiene validación de tipos/lint/build, pero no un recorrido
  Playwright autenticado en este bloque.
- `pnpm check` termina sin errores con 8 avisos CSS existentes en
  `TransferOperationsPage.svelte`. El ESLint focalizado de B06 pasa; el lint
  global conserva 3 imports sin uso en componentes de compras preexistentes
  (`PurchaseQuotationConsolidationEditor.svelte`,
  `PurchaseQuotationRequestDocument.svelte` y
  `PurchaseConsolidationDetail.svelte`), fuera de este alcance.
- B07 deberá crear las entregas físicas, recalcular entregado/pendiente desde
  eventos reales y aplicar la salida valorada usando el promedio vigente de
  empresa/artículo, compartido entre almacenes. La sucursal determina el
  origen físico de la entrega. No se inició B07 por instrucción del usuario.
- Devoluciones, impuestos, DTE, descuentos, pagos y crédito continúan fuera
  del alcance hasta su bloque/encargo correspondiente.

La evidencia y las comprobaciones técnicas de B06 no sustituyen la revisión
completa solicitada para el final de B08.

# Bloque 2 — alcance de sucursal en cotizaciones y órdenes

**Fecha:** 30 de septiembre de 2026  
**Estado:** Implementación local lista para revisión; falta aceptación manual con una sesión autenticada.  
**Rama de trabajo:** `codex/block-2-stabilization-2026-09-30`  
**Plan funcional base:** [Plan integral por bloques](planificacion-bloque-0-alcance-y-hoja-de-ruta-compras.md)  
**Diagnóstico previo:** [Auditoría del flujo actual de compras](auditoria-estado-actual-flujo-compras.md)

## Objetivo

Permitir que cotizaciones, órdenes y la cola de trabajo muestren solo información de la sucursal operativa elegida. El servidor aplica el alcance; la interfaz transmite la sucursal seleccionada y vuelve a consultar al cambiarla.

Este bloque cierra una brecha detectada en la auditoría: antes, los listados y detalles de cotizaciones y órdenes no aplicaban el ámbito de sucursal como sí lo hacían otros módulos.

## Comportamiento implementado

### Cotizaciones de compra

- El listado, detalle, comparación, creación, captura de respuesta y transiciones reciben y validan el contexto de sucursal.
- Para una persona con una sucursal asignada, una cotización es visible si todas sus solicitudes vinculadas pertenecen a esa sucursal. Una cotización consolidada entre varias sucursales queda reservada al contexto autorizado de todas las sucursales para evitar revelar cantidades y solicitudes de otras ubicaciones.
- Crear una cotización desde una sucursal valida en el backend que cada solicitud vinculada pertenezca a la sucursal elegida.
- La comparación aplica el mismo criterio de alcance que el detalle de la cotización.

### Órdenes de compra

- Los listados, detalles, cambios de borrador, transiciones y documentos de gastos validan el ámbito de la orden.
- La sucursal de la orden es su destino operativo (`purchase_orders.branch_id`). En contexto de una sucursal, la orden nueva o editada debe tener ese mismo destino.
- Una persona con alcance limitado solo puede crear la orden desde una cotización visible para esa sucursal. Para una cotización consolidada entre sucursales se requiere contexto autorizado de todas las sucursales.

### Interfaz y permisos

- Las pantallas de cotizaciones, órdenes, detalles, comparación y documentos envían la sucursal activa a la API.
- Las tarjetas de cotizaciones pendientes dentro del módulo de Cotizaciones de compra consultan conteos con el mismo alcance. Se retiró el aviso que ocultaba la cola por falta de filtro.
- El detalle de solicitud presenta las columnas Producto, Unidad, Cantidad, Descripción y Notas. Producto y unidad se resuelven a nombres legibles; los identificadores numéricos siguen en el contrato interno de datos, pero no se muestran como valores de la tabla.
- No se agregaron ni cambiaron permisos. Continúan aplicando `purchase_quotations:read`, `purchase_quotations:manage`, `purchase_quotations:select` y los permisos de órdenes existentes, según la acción.
- El selector “Todas las sucursales” solo funciona cuando el contexto operativo autoriza ese alcance. En una cuenta limitada, se debe elegir una sucursal autorizada.

## Contrato de la API

Los endpoints de cotizaciones y órdenes aceptan `branch_id`. La API valida ese valor con el contexto operativo de empresa y usuario antes de acceder al recurso. Si no se envía una sucursal, se interpreta como alcance global y se exige autorización para todas las sucursales; no se usa la ausencia del parámetro como forma de saltarse el control.

No hubo cambios de esquema, migraciones, permisos, reglas de aprobación ni datos de negocio en este bloque.

## Seguridad y límites conocidos

- Las cotizaciones enlazadas a solicitudes de varias sucursales no aparecen en la vista de una sola sucursal. La compra central debe operarse con una cuenta y contexto autorizados para todas las sucursales.
- Las órdenes se filtran por sucursal de destino, mientras que las cotizaciones se filtran por sucursal de las solicitudes fuente. La futura consolidación deberá conservar esta distinción y definir explícitamente quién puede ver un consolidado central.
- `suppliers:read` sigue siendo necesario para consultar el nombre/proveedor en los filtros y detalles cuando la pantalla así lo solicite; este bloque no amplía permisos de proveedores.
- La reproducción del caso en que al abrir COT-00013 el navegador mostró COT-00016 queda pendiente. El vínculo estático de la fila usa el ID de esa misma cotización y el detalle carga el ID de la URL; la base local también contiene IDs diferentes para COT-00013 y COT-00016. La sesión del navegador de revisión terminó redirigida a inicio de sesión, por lo que no se confirmó qué ocurre al hacer clic estando autenticado. Este cambio de alcance no se presenta como solución de ese problema de navegación.

## Validación realizada

- Revisión estática de los cambios de API, casos de uso, repositorios y pantallas afectadas.
- El OpenAPI servido por el contenedor local ya expone `branch_id` en los listados y detalles principales de cotizaciones y órdenes; se comprobó sin iniciar sesión.
- Los servicios de backend, base de datos y frontend estaban saludables al revisar `docker compose ps`. Los contenedores no se reiniciaron; backend y frontend montan sus carpetas locales.
- La revisión de sintaxis Python, Ruff y `git diff --check` fue ejecutada por el constructor y reportada sin errores. El constructor no pudo hacer la comprobación de importación de routers porque el intérprete disponible no tenía `pydantic_settings` y la ruta de entorno esperada no existía.
- No se ejecutaron pruebas automatizadas ni se verificó el flujo de clics con una sesión autenticada. La aceptación manual de una cuenta de una sucursal y otra de alcance global sigue pendiente.

## Recuperación y estado de cambios

Antes de iniciar el bloque se creó el punto de recuperación solicitado:

- Rama de recuperación: `recovery/pre-bloque-2-2026-09-30`.
- Commit de recuperación: `242c709` (`chore: save recovery checkpoint before block 2`).
- Repositorio bare separado: `C:\Developer\GESTIONASV_ERP_RECOVERY_20260930.git`.
- Bundle Git: `C:\Developer\GESTIONASV_ERP_RECOVERY_20260930.bundle`.
- Respaldo SQL local: `C:\Developer\GESTIONASV_ERP_RECOVERY_20260930_DB.sql`.

Los cambios del Bloque 2 están en la rama de trabajo indicada y no se han confirmado en un commit ni enviado al repositorio original. La rama y los respaldos de recuperación no se modificaron.

## Próximo paso

Con una sesión autenticada, revisar: (1) empleado limitado a Roosevelt ve solicitudes/cotizaciones de Roosevelt, (2) no puede leer ni cambiar recursos de otra sucursal alterando `branch_id`, (3) superadministrador autorizado a todas las sucursales ve los registros consolidados, y (4) abrir desde la lista una cotización lleva al mismo código mostrado. Después de esa aceptación se puede guardar un commit local de Bloque 2. La integración de recepción/Inventario y el consolidado de compras son bloques posteriores.

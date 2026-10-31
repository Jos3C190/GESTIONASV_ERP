# Catálogo de tipos de gasto

## Para qué sirve

El catálogo define las clases de cargos que pueden agregarse a una cotización u orden de compra. Cada registro pertenece a una empresa, así que la configuración de una compañía no afecta a otra.

## Operación

1. Abre **Compras → Tipos de gasto**.
2. Crea un tipo con nombre y, si ayuda al equipo, una descripción de cuándo usarlo.
3. En la cotización u orden, selecciona el tipo y captura el importe real correspondiente a ese documento.
4. Si una categoría deja de utilizarse, desactívala. No se elimina: los documentos anteriores conservan su referencia.

Las compañías existentes reciben tipos iniciales mediante la migración `0058`: Flete, Seguro, Agente aduanal, Manejo y descarga, Almacenamiento y Otros. En una compañía nueva, un usuario autorizado puede crear el catálogo necesario desde la pantalla.

## Historial y permisos

- `expense_types:manage`: consultar el catálogo completo, crear, editar, activar y desactivar tipos. La migración incorpora este permiso al catálogo RBAC y al rol global SUPER_ADMIN.
- `purchase_orders:read`: consultar los tipos activos utilizados en formularios de órdenes.
- No existe eliminación física desde la interfaz. Las referencias en compras y cotizaciones permanecen válidas.
- El nombre no se puede cambiar después de que el tipo se haya usado en una cotización u orden; se puede editar la descripción o desactivar el tipo. Esto evita que cambie la etiqueta de documentos históricos.

## Relación con los gastos estimados y el retaceo

Los gastos estimados de una cotización son una previsión. Los cargos de una orden son importes concretos asociados a esa orden. El retaceo registra y distribuye los costos de importación al costo de los productos recibidos. No se deben volver a capturar en la orden los mismos importes que se distribuirán en retaceo; la pantalla incluye este recordatorio para reducir duplicados.

El catálogo no calcula impuestos, flete, DAI ni costo unitario landed. Tampoco crea movimientos de inventario. Esas reglas pertenecen a las etapas de cotización, retaceo y recepción, respectivamente.

# Acceso directo al inventario desde Almacenes

Fecha: 21/10/2026.

## Solicitud y cambio

El usuario solicitó una opción **Ver inventario** en el menú de tres puntos de cada almacén, manteniendo el diseño actual.

Se añadió a la función compartida `actionsFor` de `frontend/src/routes/(app)/warehouses/+page.svelte`, después de **Ver detalle**. Abre `/warehouses/{id}?tab=inventario`, que el detalle ya reconoce para seleccionar directamente la pestaña Inventario.

La opción se aplica a cada almacén del listado, incluida la bodega matriz y las bodegas de sucursal, tanto en Cuadrícula como en Lista, que comparten menú. Se muestra a los usuarios con `inventory:read`; conserva los controles existentes de acceso a empresa y almacén del destino.

## Alcance y comprobación

Cambio de navegación; no cambia datos, inventario, estados ni el diseño de las tarjetas. Se inspeccionó la lectura de `tab=inventario` en el detalle y el uso compartido del menú en las dos vistas. No se añadieron ni ejecutaron pruebas automatizadas en este encargo. La comprobación manual pendiente consiste en abrir los tres puntos de cualquier almacén y elegir **Ver inventario**.

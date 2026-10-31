# Continuar al inventario de destino desde un traslado

Fecha: 21/10/2026.

## Solicitud

Agregar un acceso directo desde el documento de traslado al inventario de su bodega receptora,
para continuar con la ubicación, las medidas y las etiquetas de la mercancía recibida.
El ejemplo del usuario es PRD-AZU-004, Azúcar Glass Premium 10kg, recibido en San Francisco Gotera.
La implementación es común para todos los productos y destinos.

## Cambio

Archivo: `frontend/src/lib/features/inventory/components/TransferOperationsPage.svelte`.

- El detalle muestra «Siguiente paso: inventario de destino» cuando alguna línea tiene una
  cantidad recibida positiva. Se comprueba cada cantidad con la conversión decimal exacta ya
  existente; no se suman unidades diferentes.
- «Continuar en inventario de destino» abre
  `/warehouses/{destination_warehouse_id}?tab=inventario`.
- El destino se obtiene del documento seleccionado. No hay sucursal, producto ni UUID fijo.
- Funciona al consultar un documento con mercancía recibida y después de que la actualización
  de la recepción devuelva sus cantidades. Incluye recepciones parciales y cierres con ajuste
  que sí tengan mercancía recibida.
- Una preparación, un traslado sin recepción o un cierre con pérdida total sin recepción no
  muestran este siguiente paso.
- Requiere `inventory:read` y `warehouses.view`. Cuando faltan, muestra una explicación.
  Se mantienen las autorizaciones de empresa y sucursal de los servicios existentes.
- La pantalla abre el inventario completo de la bodega. No filtra ni selecciona automáticamente
  un producto o una unidad logística; el usuario puede buscarlos allí.
- Se ajustó el aviso de recepción para indicar que la mercancía **ingresó** en cuarentena.
  Un traslado recibido no prueba que sus unidades sigan en cuarentena al volver a consultarlo;
  su estado actual se revisa en inventario.
- El enlace solo navega: no registra otra recepción, no libera mercancía ni cambia cantidades,
  costos, etiquetas, datos de vehículos o SKU protegidos.

## Comprobaciones técnicas

- ESLint del archivo: salida 0, sin incidencias.
- Prettier del archivo: salida 0, formato conforme.
- `svelte-check --tsconfig ./tsconfig.json`: salida 0, 0 errores y las 8 advertencias existentes
  de `@apply` en la página de traslados. No aparecieron diagnósticos nuevos.

No se añadieron ni ejecutaron pruebas automatizadas. No se realizaron operaciones sobre datos.
La navegación y la presentación en navegador siguen pendientes de observación; no se declaran
aprobadas por las comprobaciones estáticas.

## Guía de comprobación manual

1. Abrir el traslado recibido del azúcar hacia San Francisco Gotera.
2. Comprobar el nombre de la bodega en la indicación y pulsar «Continuar en inventario de destino».
3. Confirmar que se abre esa bodega en la pestaña Inventario y buscar PRD-AZU-004.
4. Consultar un traslado con otro destino: el enlace debe cambiar a su bodega receptora.
5. Revisar un traslado con recepción parcial: el botón permite consultar las cantidades ya
   recibidas; las pendientes de llegar se siguen recibiendo desde el documento del traslado.
6. Confirmar que no aparece en preparaciones o documentos sin mercancía recibida.
7. Revisar foco de teclado, ancho móvil y el aviso de falta de permisos.

Este ajuste no cambia el estado del cierre integral B01–B08.

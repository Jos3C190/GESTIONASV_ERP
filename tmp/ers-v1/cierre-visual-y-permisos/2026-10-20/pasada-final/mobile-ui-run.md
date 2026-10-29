# Recorrido visual adicional — 20/10/2026

**Entorno:** frontend local `http://localhost:5173`, usuario de demostración ya autenticado, lectura solamente. No se enviaron formularios ni se escribieron datos en `erp_db`.

## Resultados observados

| Pantalla | Viewport y tema | Observación | Resultado |
| --- | --- | --- | --- |
| `/transfers` | 390×844, oscuro | Tres secciones de traslado en una sola fila desplazable; ancho exterior y documento 390 px; pestañas con alto 44 px; filas muestran producto, sucursal solicitante y código `SCR`; acciones primarias de al menos 44 px. | Aprobado para este viewport/caso. |
| `/transfers` | 390×844, claro | La página respondió en 390 px sin desbordamiento exterior; la captura visible mostró la misma ruta tras aplicar el tema claro. | Aprobado para ancho/tema; no se comprobó cada estado de operación. |
| `/sales/returns` | 390×844, oscuro y claro | `documentElement.scrollWidth` y `body` coinciden con 390 px. Filtro desplegable se abre con teclado; Escape lo cierra y mantiene el foco en el control; el foco visible supera 2 px. | Aprobado para la bandeja y controles ejercitados. |
| `/warehouses/d31dce4f-6078-47fb-a3e5-55e043abb6b0#inventario` | 390×844, oscuro | Sin desbordamiento exterior; tabla usa área interna desplazable. | Aprobado para presentación del caso consultado. |
| `/inventory/kardex` | 390×844, oscuro | Sin desbordamiento exterior. Las pestañas pueden ocupar dos filas; no se probaron todos los filtros ni perfiles. | Aprobado para el caso y ancho consultados. |

El recorrido es una muestra visual de solo lectura, no una certificación de todas las pantallas de la aplicación. Se comprobó previamente `/branches`, `/purchase-orders` y `/inventory/adjustments` en móvil; sus resultados históricos conservan su propia evidencia.

## Incidencia corregida en Traslados

La revisión crítica detectó pestañas que se envolvían en varias filas, tarjetas de demanda demasiado densas y acciones táctiles pequeñas. En `TransferOperationsPage.svelte` las pestañas ahora permanecen en una fila con scroll horizontal. En `TransferDemandOverview.svelte` las acciones primarias tienen alto mínimo de 44 px y el detalle secundario de despacho/tránsito/recepción queda plegado. El contenido esencial de solicitud, sucursal, cantidad pendiente y destino sigue visible. Se añadió una regresión de componente que afirma sucursal/código SCR, pendiente, detalles plegables y tamaño táctil.

Prueba focalizada: 2 pruebas aprobadas. `pnpm check`: 0 errores y 8 avisos CSS `@apply` existentes en el componente de Traslados. ESLint focalizado y build de producción aprobaron. Después del cambio, Vite seguía entregando su módulo transformado anterior desde caché en memoria; se reinició solamente el servicio frontend y se confirmó la versión nueva en navegador. Al cierre, frontend, API y base figuran saludables.

## Límite del archivo de capturas

Las capturas se mostraron en la sesión de control visual, pero la API de navegador disponible no expone una operación documentada para guardar sus PNG en el repositorio. Por eso esta nota registra dimensiones, tema y observaciones inspeccionables, pero **no afirma que exista un PNG archivado** ni satisface el requisito de P02 de conservar capturas. Para cerrar P02 debe guardarse evidencia PNG verificable por ruta para cada familia/estado pendiente.

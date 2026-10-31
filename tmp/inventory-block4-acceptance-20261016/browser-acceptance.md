# Evidencia de navegador — aceptación de inventario bloque 4

Fecha de las ejecuciones: 16/10/2026. Entorno aislado, API en puerto 8001 y frontend en 5174. No se usó la sesión de localhost 8000/5173 ni la base erp_db. El recorrido principal y la comprobación complementaria de recepción usaron perfiles sintéticos.

## Datos ficticios

- Compra sintética COM-00004.
- Retaceo RET-00002. Se usó el archivo sintético synthetic-retaceo-proof.txt, expresamente marcado como no factura ni comprobante fiscal.
- HU padre HU-F07DC15939E743BF; la división generó HU hija HU-2D9F817BAE57469E.
- Bodega de destino de sucursal BOD-ET-01.
- Comprobación complementaria: HU HU-2849B778010749BF, 4 cajas, producto PRD-LAC-002, bodega ITK-IT-WR-b2 de Pastelería Lorena Jiquilisco. Se usó un usuario sintético limitado a esa sucursal; se desactivó y se marcó eliminado después de la prueba.
- Los IDs se refieren únicamente al dataset desechable de aceptación.

## Pasos y observaciones

1. Se abrió RET-00002 desde la compra sintética, se calculó, verificó y cerró el retaceo. El costo FOB de prueba fue $125; con $5 de gasto asignado el costo aterrizado fue $130, equivalente a $13/kg.
2. Se dividió la HU padre en 6 y 4 unidades base. Se midieron las dos partes; se generó la etiqueta y se confirmó colocación desde el control de software. Tras completar requisitos, las partes quedaron disponibles. La HU padre conservó 6 en la bodega central.
3. Se preparó y despachó la parte hija de 4 a BOD-ET-01. El movimiento quedó en tránsito con origen de compra trazable.
4. Con el perfil global se contó la recepción de 4. La existencia recibida quedó en cuarentena para revisar y ubicar; no se liberó como disponible prematuramente.
5. Con el perfil de sucursal se consultó la HU en cuarentena y su historial/Kardex. La primera consulta del Kardex pidió 200 bodegas y API respondió 422 (máximo 100). Tras el cambio de paginación a 100, la recarga del Kardex cargó correctamente.
6. Se comprobó navegación con teclado, vistas de tabla/tarjetas y tema claro/oscuro. El enlace público de trazabilidad del QR abrió la ficha en una nueva pestaña del navegador con origen y movimientos.
7. En la primera pasada, el perfil global recibió el único envío preparado para esa secuencia; por eso el perfil de sucursal no tuvo una recepción pendiente que mostrar. Fue una limitación del orden de la prueba, no un fallo atribuido a la API.
8. En la comprobación complementaria se inició sesión como perfil de sucursal de Jiquilisco. El selector mostró la bodega ITK-IT-WR-b2 y una recepción pendiente de 4 cajas para HU-2849B778010749BF. Se marcó la unidad y se confirmó la recepción contada desde la interfaz. La aplicación informó que se registraron 4 cajas y que debían verificarse y ubicarse desde Inventario; el selector quedó con 0 pendientes. Una consulta de solo lectura a erp_db_test confirmó quantity_base=4 y stock_status=quarantine. El perfil sintético necesitó `warehouses.view`; se agregó solo a su rol de prueba y luego se desactivó la cuenta.

## Límite de lo probado

La aplicación validó reglas y movimientos de software sobre datos ficticios. La generación/impresión HTML y la confirmación del comando de colocación se simularon en el navegador. No se imprimió una etiqueta física, no se escaneó con el HS-200 y no se colocó físicamente el adhesivo.

La valoración de empresa estaba inactiva porque no existía un corte de apertura aprobado. Por diseño, el Kardex mostró el importe como desconocido y no como cero. Por ello no se afirma que el importe monetario total de la HU permaneció igual a través de toda la secuencia.

Para repetir, preparar otra vez la API y frontend aislados contra erp_db_test, autenticar perfiles sintéticos global y de sucursal, seguir el recorrido y reservar un traslado pendiente independiente para la recepción con perfil de sucursal. Comparar el estado en las fichas de retaceo, HU, traslados y Kardex. No reutilizar credenciales o datos de producción.

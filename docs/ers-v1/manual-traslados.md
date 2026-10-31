# Manual operativo de traslados — ERS-B04

**Actualizado:** 19/10/2026  
**Estado:** flujo conectado y comprobado técnicamente. La aceptación autenticada completa se hará junto con B01–B08 al finalizar B08.

## Recorrido de operación

1. Abra **Inventario → Traslados**. El panel **Abastecimiento** muestra el nombre del producto, SKU, unidad base, HUs y existencias liberadas de la bodega central.
2. Revise **Sucursal / solicitud** para elegir una necesidad aprobada. La tabla muestra solicitado, asignado, despachado, en tránsito, recibido y **pendiente de asignar**. Este último dato significa solicitado menos asignado; no es una cantidad pendiente de recepción.
3. Pulse **Preparar** junto a la solicitud. Se seleccionan la sucursal y la línea de solicitud. También puede usar **Envío manual** si no hay solicitud; documente el motivo de cualquier cantidad no asignada.
4. Elija una o más HUs, compruebe producto, lote y unidad, e indique la cantidad base que se enviará. Una cantidad sobre la demanda pendiente exige un motivo de excedente. El servidor vuelve a validar existencia y demanda.
5. Pulse **Guardar en preparación**. El sistema crea el documento, pero no reserva, divide ni mueve stock. Puede editarlo o cancelarlo antes del despacho; cerrar el formulario no cancela un documento guardado.
6. En **Documentos**, abra la preparación, seleccione un vehículo activo y confirme el despacho. Solo esta acción mueve la cantidad desde la central a la ubicación móvil del vehículo y cambia el estado a **En tránsito**.
7. El usuario autorizado de la sucursal destino abre el documento en **Traslados**. En cada línea escribe la cantidad que contó físicamente y elige una ubicación activa y apta para almacenamiento/cuarentena. Los campos quedan vacíos hasta que se capture el conteo.
8. Confirme la recepción. Una recepción parcial mantiene el remanente **En tránsito**; lo recibido queda en **Cuarentena**, pendiente de revisión. Desde **Almacenes**, verifique las medidas y la etiqueta y libere la HU cuando corresponda. La recepción por sí sola no libera la mercancía.
9. Para una diferencia, abra una incidencia, describa el motivo y agregue la referencia de evidencia. Si se confirma una pérdida, desde la incidencia use **Crear ajuste por faltante**, adjunte el soporte, apruebe el borrador y aplíquelo con el permiso autorizado. El sistema descuenta únicamente la cantidad aún en tránsito. Si no queda remanente sin resolver, cierra como **Cerrado con ajuste**; la cantidad recibida conserva solo el conteo físico real. Para diferencias no confirmadas, mantenga la incidencia abierta o reanude el tránsito según corresponda.

## Acceso desde Almacenes

La acción **Trasladar a sucursal** abre el mismo recorrido documental con la bodega de origen y HU seleccionadas. El destino y la solicitud se eligen en Abastecimiento. Los traslados entre bodegas no se registran desde el formulario genérico del Kardex.

**Dividir unidad** sigue disponible como operación explícita cuando haya una separación física real. Abrir, cerrar o cancelar paneles, consultar el QR o revisar/reimprimir una etiqueta no divide ni mueve unidades. Una HU ya liberada no necesita volver a dividirse para completar el flujo de traslado.

## Estados y efectos

| Estado o acción | Efecto esperado |
| --- | --- |
| En preparación | Documento editable/cancelable; no reserva ni mueve existencias. |
| Cancelar preparación | Conserva el historial y no crea un movimiento. |
| Despachar | Movimiento central → vehículo; estado En tránsito. Requiere confirmación explícita. |
| Recepción parcial | Mueve solo lo contado a cuarentena; el resto sigue en tránsito. |
| Recibido | No quedan unidades en tránsito; las recibidas esperan revisión de HU/etiqueta. |
| Con incidencia | Conserva cantidades, motivo y evidencia sin eliminar movimientos. |
| Cerrado con ajuste | Todo quedó recibido/devuelto o justificado por un ajuste aprobado; la pérdida no se cuenta como recibida. |
| Liberar HU | Se hace después de verificar medidas y etiqueta desde Almacenes. |

## Escenarios manuales para el cierre integrado de B08

Estos pasos aún no se han aceptado en el navegador; forman parte del recorrido integrado pendiente:

- Preparar una línea vinculada a una solicitud y confirmar que producto, sucursal, unidad y pendiente se entienden sin usar el código HU como nombre.
- Preparar un envío manual y otro con excedente justificado; comprobar que solo las cantidades enlazadas avanzan la solicitud.
- Guardar, editar y cancelar una preparación; comprobar antes/después que no cambió el stock ni apareció un movimiento.
- Despachar dos unidades y recibir primero una; verificar una unidad en cuarentena y una en tránsito. Recibir la segunda y revisar medidas/etiqueta antes de liberar.
- Reportar una incidencia y verificar que conserva la cantidad en tránsito; resolver solo con una acción autorizada.
- Intentar recepción con una ubicación inactiva/no apta y comprobar que no se confirma.
- Revisar alcance de emisor, receptor, usuario de otra sucursal y otra empresa; cambiar sucursal/empresa con un formulario abierto y confirmar que la selección anterior se descarta.
- Reintentar tras una respuesta incierta o doble clic y confirmar que no se duplica el despacho/recepción.
- Probar la tabla de demanda en pantalla pequeña, navegación por teclado, diálogo de confirmación y temas claro/oscuro.

No se exige lector físico ni impresora. La demostración usa datos ficticios y la generación/consulta de etiquetas del sistema.

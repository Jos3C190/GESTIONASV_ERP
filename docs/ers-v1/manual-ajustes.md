# Manual operativo — Ajustes de inventario

Este manual cubre el flujo ERS-B05 implementado en GestionaSV. La demostración utiliza datos ficticios. Las comprobaciones automatizadas están documentadas en [la entrega B05](entrega-bloque-05.md); la aceptación de navegador y los perfiles queda para B08.

## Antes de crear el ajuste

- Confirma empresa y sucursal operativa en el encabezado.
- Elige la bodega física correcta. Una bodega técnica de tránsito solo se usa desde una incidencia autorizada.
- Ten listo un motivo concreto, la referencia del documento y un archivo de soporte válido. Aprobar exige que la carga haya terminado, siga activa y pertenezca a la empresa.
- Ingresa cantidades en la unidad base y verifica artículo, ubicación, lote y HU. El código de la HU identifica una unidad logística; el sistema muestra aparte el nombre del producto y su unidad.

## Ajuste ordinario

1. Abre **Inventario → Ajustes** y selecciona **Nuevo ajuste**.
2. Selecciona bodega, fecha operativa y contable, motivo y referencia. La fecha contable no puede ser anterior a la operativa.
3. Agrega una línea por producto/ubicación/HU que corresponda. Selecciona **Aumento** o **Disminución** y escribe una cantidad positiva en unidad base, hasta seis decimales.
4. Para un aumento, captura costo unitario o costo total solo si lo respalda la evidencia; no llenes ambos. Si no se captura, el motor utiliza el promedio vigente. Sin un promedio previo se requiere costo documentado. El ingreso queda en cuarentena y no se libera automáticamente.
5. Para una disminución, selecciona la HU existente y comprueba que la cantidad no exceda su saldo. El costo de salida corresponde al promedio vigente en el momento de aplicar.
6. Guarda el borrador. Esto no mueve ni valora inventario.
7. Adjunta el comprobante y espera a que el sistema confirme que la carga se completó. Si debes reemplazar soporte mientras el documento sigue en borrador, conserva el historial y vuelve a adjuntar el archivo correcto.
8. Revisa versión, producto, dirección, cantidad y ubicación. Selecciona **Aprobar**; el servidor vuelve a validar motivo, referencia y soporte.
9. Cuando la aprobación sea correcta, selecciona **Aplicar ajuste** y confirma el resumen. Aplicar es la acción que registra el movimiento y actualiza saldo/valoración.
10. Abre el enlace a **Kardex** y verifica el movimiento por documento, artículo, ubicación, cantidad y costo. Si fue un aumento, continúa en **Almacenes** con revisión de medidas/etiqueta de la HU en cuarentena antes de liberarla.

## Cancelar o corregir

- Un borrador o aprobado puede cancelarse con motivo antes de aplicar; la cancelación conserva historial y no cambia existencias. Un ajuste aplicado no se cancela ni se edita.
- Para cambiar un ajuste aprobado antes de aplicar, revoca su aprobación con motivo, modifica el borrador y vuelve a aprobar la versión nueva.
- La corrección automática disponible crea otro documento: solo admite compensar la cantidad completa de un ajuste ordinario negativo de una línea si el costo original es justificable y no hay operaciones posteriores que vuelvan ambigua la compensación. Adjunta soporte, aprueba y aplica la corrección como un ajuste separado.
- Las correcciones parciales, multilínea, exclusivamente monetarias y de pérdidas de tránsito con operaciones posteriores no están soportadas por la compensación automática. El sistema debe rechazarlas; no crees un movimiento manual para intentar eludir esa protección.

## Pérdida de un traslado

1. En **Inventario → Traslados**, abre el documento con incidencia pendiente y confirma qué cantidad sigue en tránsito.
2. Desde la incidencia, elige **Crear ajuste por faltante**. El borrador queda vinculado al traslado, incidencia, detalle y HU. No uses un ajuste ordinario libre para la bodega técnica de tránsito.
3. Registra el motivo y referencia, adjunta evidencia completa, aprueba y aplica el ajuste con los permisos correspondientes.
4. Comprueba el detalle del traslado: `despachado = recibido + en tránsito + devuelto + ajustado de salida`. La cantidad perdida se muestra como ajustada, no como recibida. Si no queda tránsito ni cantidad por resolver, el traslado cierra **Cerrado con ajuste**.

## Permisos y resolución de errores

- La lectura del módulo requiere `inventory:read`; crear/editar/cancelar/soportar/corregir requiere `inventory:adjust`; aprobar/aplicar requiere `inventory:adjust_approve`.
- Ver costos depende además de `inventory:valuation`. Tener permiso de ajuste no revela por sí mismo los costos.
- Si falta permiso, alcance, soporte válido o saldo suficiente, detente y corrige esos datos con un usuario autorizado. No vuelvas a aplicar con una clave distinta después de una respuesta incierta; consulta primero el estado del documento.
- Si una solicitud se rechaza por operaciones posteriores, no cambies el historial original. Conserva el error y escala la compensación para revisión contable/arquitectónica.

## Casos manuales para B08

Probar con usuarios y datos ficticios: borrador sin efectos; aprobación sin soporte rechazada; aprobación con soporte activo; aplicación única y reintento; aumento en cuarentena; rechazo de exceso; Kardex por referencia; cancelación sin movimiento; corrección admitida y modalidades rechazadas; pérdida de traslado con recepción parcial; acceso de otra sucursal/empresa; descarga y protección del soporte después de aprobar. Estos casos aún no se declaran aceptados en navegador.

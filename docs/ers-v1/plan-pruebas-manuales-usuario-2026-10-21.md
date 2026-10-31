# Plan de pruebas manuales del usuario — B01–B08

Fecha: 21/10/2026, America/El_Salvador.

Estado: **PLAN PENDIENTE DE EJECUCIÓN**. Ningún paso se considera aprobado por estar escrito aquí. Complementa el [manual general](manual-pruebas-y-demostracion.md) y el [cierre integrado](cierre-visual-y-permisos-b01-b08.md).

Hallazgo del recorrido del usuario: la orden consolidada excluía incorrectamente las bodegas centrales vinculadas a matriz. Se corrigió el selector y pasaron 10 pruebas focalizadas; falta confirmar tras recargar el formulario. Ver [diagnóstico y evidencia](diagnostico-orden-consolidada-bodega-matriz-2026-10-21.md). Para los ajustes, abrir directamente la entrada **Ajustes de inventario** del menú; la entrada separada **Inventario** aún conduce a una pantalla pendiente.

Recepción y cierre del pendiente: guardar abre ahora el detalle del borrador; continuar con **Confirmar recepción** para actualizar el estado de la orden y después **Verificar recepción** para registrar la mercancía aceptada en inventario. La orden continúa el borrador existente y anuncia **Recepción completada** cuando está totalmente recibida. Ver [diagnóstico de OC-00019](diagnostico-oc-00019-recepciones-y-cierre-2026-10-21.md): COM-00021 estaba en borrador en la lectura inicial; después el usuario confirmó la recepción y la orden pasó a recibida. La verificación definitiva de inventario sigue pendiente.

Nota del recorrido con productos existentes: se configuraron las equivalencias de las dos harinas de COM-00021 y se simuló su verificación completa con rollback. La recepción sigue disponible para el paso definitivo del usuario. Ver [configuración, equivalencias y evidencia](presentaciones-harinas-demostracion-2026-10-21.md). Este recorrido con tres productos existentes tiene cantidades y costos diferentes al ejemplo DEMO-MANUAL-2110 de la tabla siguiente; no mezclar sus resultados esperados.

## Preparación desde el dashboard

- [ ] Mantener la empresa de prueba Grupo Lorena. Anotar la sucursal matriz, su bodega central y una sucursal de destino con su bodega.
- [ ] Consultar Valoración de inventario: debe indicar promedio ponderado activo. No volver a aprobar el corte inicial existente; si solicita activación, detenerse y registrar la pantalla.
- [ ] Crear un producto ficticio nuevo: **Artículo prueba manual 2110**, SKU sugerido **DEMO-MANUAL-2110**, o una variante nueva si ya existe. Unidad base **Unidad (u)**, presentación activa **Unidad**, equivalencia **1**. Usar datos físicos coherentes con la ubicación elegida, por ejemplo 0.1 kg y 0.001 m³ por unidad si los campos corresponden a cada unidad.
- [ ] Confirmar que el producto nuevo no tiene stock. Preparar un comprobante ficticio legible, por ejemplo un PDF o TXT con el texto “Demostración académica 21/10/2026”, sin datos privados.
- [ ] Anotar en todos los documentos la referencia **PRUEBA-MANUAL-20261021**. Registrar sus códigos y no reutilizar documentos ya terminados.

Conservar los SKU protegidos ERS-INC-EE8FE228, ERS-LATE-B1B55D6D, ERS-REVIEW-DD6BBF85 y ERS-UI-F767BABC y sus documentos. Este recorrido usa exclusivamente el producto nuevo.

## Recorrido principal

| Hecho | Pantalla y acción | Resultado que se debe comprobar |
| --- | --- | --- |
| [ ] 1 | **Inventario → Ajustes.** Registrar un ajuste positivo inicial ficticio de **5 unidades a $10**, con motivo y comprobante. Completar las aprobaciones/aplicación que presente la pantalla. | Empresa: **5 unidades, $50, promedio $10**. El ajuste y su documento permanecen vinculados. Si crea una HU en cuarentena, revisar medidas y etiqueta para liberarla; liberar no vuelve a sumar stock. |
| [ ] 2 | **Solicitudes de compra.** Crear una solicitud nueva de **10 unidades** para la sucursal destino elegida y aprobarla. | La solicitud identifica producto, cantidad, unidad y sucursal solicitante. Conservar su código. |
| [ ] 3 | **Solicitudes y consolidados → Cotizaciones → Órdenes de compra.** Consolidar esa solicitud; registrar RFQ/respuesta, evaluar y adjudicar el consolidado; generar la orden de **10 a $10**. | Se conserva la solicitud como origen. Una solicitud ya vinculada a un consolidado activo no puede generar otra compra duplicada. Crear solicitud, consolidado y orden conserva las **5 unidades/$50** existentes. |
| [ ] 4 | **Compras.** Guardar el borrador de **10 unidades**, abrir su detalle, **Confirmar recepción** y **Verificar recepción**, aceptando las 10 en la bodega central. Preparar una HU de 10 unidades si la pantalla permite definirla. | Guardar no cambia el saldo; confirmar actualiza el pendiente de la orden. Tras verificar las cantidades aceptadas se conserva el origen y se registra el inventario con su detalle/lote: antes del retaceo, empresa **15 unidades/$150**, promedio $10, incluso en cuarentena. Anotar compra, cabecera de recepción, detalle/lote y HU. |
| [ ] 5 | **Retaceo.** Añadir un gasto aplicable ficticio de **$30**, con comprobante, asignado a la línea recibida; calcular, verificar y aplicar/cerrar siguiendo las acciones disponibles. | Base de compra **$100**, gasto **$30**, costo de la compra **$130**. Calcular/verificar conserva el valor previo; aplicar una vez deja empresa **15 unidades/$180**, promedio **$12**. No volver a aplicar el retaceo cerrado. |
| [ ] 6 | **Almacenes → bodega central → Inventario.** Revisar las HUs del artículo, ubicación, medidas, etiqueta y QR; confirmar etiqueta vigente y liberar las unidades que correspondan. Abrir y cancelar el formulario de división dos veces, sin confirmar división. | Se ven nombre, SKU, unidad, HU y origen. QR/etiqueta abren su ficha. Debe terminar en **Disponible / Revisión terminada · disponible para uso**. Consultar, cerrar, cancelar o volver a abrir conserva el número de HUs y la suma **15**. Dividir es opcional y no es una etapa obligatoria después de liberar. |
| [ ] 7 | **Traslados.** Buscar el producto disponible en central y comprobar la demanda de la sucursal que pidió 10. Preparar **10**, elegir destino y vehículo/conductor cuando el flujo lo solicite, despachar, recibir **8** y después **2**. | En preparación no hay salida. Tras despacho: central **5**, tránsito **10**. Primer recibo: central **5**, destino **8**, tránsito **2**. Final: central **5**, destino **10**, tránsito **0**; empresa **15/$180**, promedio $12. En destino completar las verificaciones de medidas/etiqueta para las HUs pendientes. Si el formulario de traslado no muestra quién solicita y cuánto falta, registrar el problema antes de elegir destino. |
| [ ] 8 | **Clientes → Cotizaciones de venta → Ventas.** Crear cliente ficticio, cotizar/vender **3 unidades a $20** en la sucursal destino. | Subtotal comercial **$60**; revisar por separado los impuestos que correspondan. Antes de entregar, el inventario conserva **15 unidades/$180**. El precio de venta $20 se distingue del costo $12. |
| [ ] 9 | **Detalle de venta → Entregas.** Entregar **2** unidades y luego **1**, con las asignaciones válidas que exija la pantalla. | Primera entrega: sucursal **8**, empresa **13/$156**. Segunda: sucursal **7**, empresa **12/$144**; costo total de las salidas **$36**. Recargar: se conservan ambas entregas y cero pendientes de entrega. |
| [ ] 10 | **Devoluciones.** Devolver las **2 unidades de la primera entrega**, con motivo y documento de origen. Registrar recepción; inspeccionar y aceptar **1 apta** y rechazar **1 dañada**, usando las acciones de resolución que presente el formulario. | Registrar la recepción documental conserva **12/$144**. Aceptar 1 repone **$12**: empresa **13/$156**, sucursal **8**. Rechazar 1 no suma stock. La devolución queda resuelta con 1 aceptada y 1 rechazada. Si la apta entra en cuarentena, completar revisión y liberar; esa liberación no suma otra unidad. |
| [ ] 11 | **Inventario → Ajustes.** Aplicar un ajuste negativo de **1 unidad disponible** en la sucursal destino con motivo ficticio y comprobante. | Empresa **12 unidades/$144**; central **5**, sucursal **7**, promedio **$12**. El historial de compra, retaceo, traslados, entregas, devolución y ajustes se conserva. |
| [ ] 12 | **Kardex → Movimientos físicos, Valoración y Conciliación.** Consultar el producto por bodega y a nivel empresa. Buscar también los códigos de recepción/lote obtenidos y abrir la ficha desde la etiqueta/QR. | Físico **12**, valorado **12**, diferencia **0**, valor **$144**. El traslado mantiene el valor global; la etiqueta/QR conduce al producto y origen correctos. Recargar debe conservar los resultados. |

Los valores suponen moneda USD y que el precio base de compra no incluye otros gastos capitalizables. Si la pantalla agrega un impuesto al costo o los importes difieren, registrar ese dato y revisar antes de continuar; no cambiar cantidades para forzar el resultado.

## Verificaciones puntuales para los pendientes

- [ ] **Adjuntos.** En los ajustes y retaceo nuevos, subir el archivo, guardar, recargar y descargarlo. Abrir lo descargado y confirmar que el contenido y el vínculo al documento correcto se conservan. Registrar acciones que fallen o queden visibles sin funcionar.
- [ ] **Recepciones parciales y lote.** Con otro producto/orden de prueba, recibir el mismo SKU en dos momentos: **4 y 6 unidades**, sin reutilizar documentos aplicados. Cada recepción debe conservar su cabecera y detalle/origen. Si se permite repetir un SKU en distintas líneas de una misma recepción, revisar además ese caso. Si no se permite, registrar la validación; la cobertura contractual se evalúa después. Comparar consultas por cabecera, código del detalle/lote y HU cuando cada pantalla admita esos identificadores.
- [ ] **Permisos básicos.** Si ya hay un usuario restringido autorizado, abrir los documentos nuevos con él: verificar acciones disponibles, costos según sus permisos y denegación de un enlace privado de otra empresa o sucursal fuera de su alcance. Un superadmin no demuestra estas restricciones. Si no hay usuario adecuado, registrar **pendiente**. La matriz exhaustiva de rutas/acciones requiere comprobación técnica adicional.
- [ ] **Ficha pública.** Abrir el enlace público del QR en una ventana privada: comprobar que muestra únicamente la trazabilidad pública autorizada y no costos ni adjuntos privados. El enlace público del QR y el enlace privado del documento tienen alcances distintos.
- [ ] **Escritorio/móvil y temas.** Guardar PNG de siete familias: matriz/bodega; recepción/lote/etiqueta; demanda/traslados; ajustes/adjuntos; cliente/cotización/venta; entregas/devoluciones; Kardex/conciliación. Repetir en claro y oscuro, escritorio y ancho móvil 390×844. Deben verse nombres, cantidades, estados y acciones sin contenido inaccesible. No incluir contraseñas, tokens ni enlaces públicos completos en las capturas compartidas.
- [ ] **Recuperación tras respuesta perdida: pendiente técnico.** No simularlo desconectando servicios ni reenviando escrituras al azar. Requiere descartar la respuesta de forma controlada después de guardar, consultar el estado y comprobar que el reintento con la misma clave no duplica efectos. Una recarga normal o un clic repetido no acredita este caso.

No se necesitan impresora ni lector físicos. Para revisar el software, usar la vista de etiqueta/QR y la confirmación digital disponible, sin declarar una impresión física realizada.

## Cómo registrar cada resultado

Copiar una fila por comprobación y guardar la captura correspondiente. No marcar APROBADO solo porque apareció una notificación: recargar el documento y comprobar cantidades/estado persistidos.

| Paso/caso | Código de documento | Perfil y sucursal | Esperado | Observado tras recargar | PNG | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| Por completar | | | | | | PENDIENTE |

Estados: **APROBADO**, **FALLÓ** o **PENDIENTE**. Si algo falla, registrar paso, acción, mensaje y captura, y detener la secuencia dependiente. Antes de reintentar una escritura, consultar el documento, las HUs y el Kardex para comprobar si ya se guardó.

**Primera acción ahora:** consultar Valoración de inventario para comprobar que está activa y crear el producto nuevo desde Productos. Después, ejecutar el paso 1.

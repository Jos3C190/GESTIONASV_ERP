# Manual operativo — entregas de ventas (ERS-B07)

Estado: B07 implementado y verificado técnicamente en `erp_db` con revisión
0089. Este manual describe el flujo implementado; el recorrido autenticado de
navegador, incluida la conciliación visual, queda pendiente para B08. La
implementación está disponible desde el detalle de una venta confirmada.

## Preparar una entrega

1. Abre **Ventas**, entra al detalle de la venta y confirma que su estado sea
   **Confirmada**.
2. En **Entregas de la venta**, pulsa **Preparar entrega**. La disponibilidad
   muestra solo unidades logísticas abiertas y disponibles de la sucursal de
   la venta. Revisa el producto, presentación/unidad, cantidad base, bodega,
   ubicación, lote y vencimiento.
3. Selecciona las cajas o unidades completas que se entregarán. Las cantidades
   vendida, entregada y pendiente aparecen por línea. Una misma venta permite
   varias entregas hasta completar el pendiente.
4. Agrega una nota si hace falta y pulsa **Crear borrador**. El borrador no
   descuenta inventario; puedes revisar la selección, cambiarla o cancelarlo
   con motivo.
5. Pulsa **Confirmar entrega** solo cuando el despacho esté listo. El sistema
   vuelve a validar empresa, sucursal, saldo, lote, ubicación, estado de la
   unidad, etiqueta vigente, vencimiento y pendiente. Si algo cambió, recarga
   y prepara una nueva selección.
6. Después de confirmar, la venta muestra el avance real y cada asignación
   queda ligada al movimiento y a la valoración de salida. Consulta el
   movimiento desde **Kardex** usando el código de la entrega o de la unidad.

## Ejemplo parcial y final

Venta confirmada: 5 unidades base. La bodega de la sucursal tiene una caja de
3 y otra de 2 unidades.

- Primera entrega: asigna la caja de 3, crea el borrador y confírmalo. La venta
  queda **Parcialmente entregada**: 3 entregadas y 2 pendientes.
- Segunda entrega: asigna la caja de 2, crea el borrador y confírmalo. La venta
  queda **Entregada**: 5 entregadas y 0 pendientes.
- Si se pierde la respuesta al confirmar, vuelve a cargar el detalle y usa la
  misma acción. La interfaz conserva la clave de comando para recuperar la
  confirmación sin generar otra salida.

Si la entrega necesita solo una parte de una caja, separa la unidad desde el
flujo de almacén y termina allí las medidas y la revisión de la etiqueta antes
de asignar las nuevas unidades. La entrega no divide HUs ni crea fracciones al
abrir, cerrar o cancelar el formulario.

## Cancelación y errores habituales

- **Sin stock en la sucursal de la venta:** revisa la sucursal y el Kardex; una
  unidad de otra sucursal, en tránsito, en cuarentena o cerrada no puede
  asignarse. No cambies manualmente la sucursal del documento.
- **La venta cambió o ya se completó:** recarga el detalle y vuelve a revisar
  cantidades pendientes antes de preparar otro borrador.
- **Etiqueta vencida o medida no validada:** vuelve al inventario del almacén,
  completa el proceso de revisión de la HU y luego consulta disponibilidad.
- **Cancelar borrador:** escribe el motivo y pulsa **Cancelar**. No genera
  movimientos ni modifica saldo.
- **Venta con entrega confirmada:** no puede cancelarse. Las devoluciones se
  registrarán en B08 y no reabrirán automáticamente la cantidad pendiente.

El costo promedio se aplica en el servidor al confirmar, pero no se muestra en
la pantalla comercial. El precio de la venta permanece separado del costo del
inventario.

Las instrucciones y estados descritos aquí no acreditan todavía aceptación
visual autenticada, cambio de sucursal/empresa, recarga del navegador ni
reconciliación manual de Kardex; esos recorridos siguen pendientes de B08.

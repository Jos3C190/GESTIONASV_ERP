# Manual de uso — clientes, cotizaciones y ventas base

Este flujo prepara el documento comercial para una venta. En B06 no aparta ni
descuenta inventario y no genera factura fiscal. El despacho físico llegará en
B07.

## 1. Crear o revisar al cliente

1. En el menú **Compras**, abre **Clientes**.
2. Si el cliente no existe, registra un código y nombre. Teléfono y correo
   son opcionales.
3. Guarda y comprueba que aparezca activo en la lista.
4. Si desactivas un cliente, conserva las cotizaciones y ventas existentes,
   pero ya no podrás usarlo para nuevas cotizaciones o conversiones.

## 2. Preparar una cotización

1. Abre **Ventas → Cotizaciones de venta** y elige **Nueva cotización**.
2. Selecciona la sucursal, el cliente y la fecha de vencimiento. La vigencia
   es inclusiva durante ese día según la fecha de El Salvador.
3. Agrega un producto disponible en el catálogo comercial. Solo aparecen
   productos vendibles con identidad de inventario y unidad configurada.
4. Selecciona la unidad comercial permitida, cantidad y precio de venta. El
   precio se captura aquí; no se copia del costo promedio. En esta
   demostración la moneda es USD.
5. Guarda el borrador. El servidor calcula y devuelve los totales. El subtotal
   o total tecleado por el navegador nunca es la fuente de verdad.

La cotización no comprueba disponibilidad de stock, no crea reservas y no
cambia existencias. Eso se validará cuando se registre la entrega física.

## 3. Confirmar la cotización

1. Abre el detalle de la cotización y revisa sucursal, cliente, vigencia,
   productos, unidades, cantidades y precios.
2. Mientras está en borrador puedes editarla. Si cambió desde que la abriste,
   recarga para evitar guardar una revisión obsoleta.
3. Selecciona **Confirmar cotización**. Una cotización vencida o cancelada no
   se puede confirmar ni convertir.
4. Si no continuarás, escribe un motivo y usa **Cancelar cotización** antes
   de convertirla.

## 4. Convertir a una venta en borrador

1. En una cotización confirmada, selecciona **Crear venta en borrador**.
2. La venta conserva la cotización de origen y los datos de producto, unidad,
   conversión, cantidades, precio y total de cada línea.
3. Si el resultado tarda o la pantalla muestra un error de red, vuelve a abrir
   la cotización y consulta si ya aparece enlazada a una venta antes de
   repetir la acción. El servidor protege la conversión contra duplicados.
4. Desde **Ventas → Ventas**, abre el documento creado. Antes de confirmar
   puedes corregir sus datos comerciales autorizados y guardar el borrador.

## 5. Confirmar o cancelar la venta

1. Revisa los términos y selecciona **Confirmar venta**. Desde ese momento las
   líneas y condiciones quedan congeladas.
2. El estado de entrega seguirá como **Pendiente de entrega**: B06 muestra
   cero entregado y la cantidad base completa pendiente.
3. Si debes cancelar y aún no existe entrega, registra el motivo y cancela.
   La historia de confirmación se conserva; una venta cancelada no permite
   reconvertir la misma cotización.
4. Para revisar el documento después, usa el listado de Ventas y abre su
   código; el detalle también enlaza la cotización de origen.

## Qué no significa el resultado

- **Confirmada** significa aceptada comercialmente; no significa despachada,
  entregada, facturada ni cobrada.
- **Pendiente de entrega** es una proyección de B06; la cantidad solo cambiará
  cuando B07 registre entregas físicas confirmadas.
- El total no incluye impuestos o descuentos y no debe presentarse como
  documento fiscal.
- La prueba de impresora, lector físico, QR impreso, DTE, pagos y devoluciones
  no forma parte de este flujo.

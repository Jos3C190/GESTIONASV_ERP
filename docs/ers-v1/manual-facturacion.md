# Manual de uso — facturar el pedido

Facturar emite el documento tributario electrónico (DTE) del pedido completo: factura a
consumidor final o comprobante de crédito fiscal, según el documento elegido en el pedido.

## 1. Antes de facturar

La empresa necesita, en **Ventas → Configuración fiscal**:

- NIT y NRC válidos en la ficha de la empresa;
- teléfono y correo para DTE en el perfil fiscal;
- una actividad económica (la del establecimiento o la principal);
- un establecimiento activo para la sucursal del pedido, con dirección completa, y al menos un
  punto de venta (caja) activo;
- el tipo de documento habilitado.

Para el crédito fiscal, el cliente debe ser contribuyente con NIT o DUI homologado, NRC,
actividad y dirección completa.

Si falta algo, el pedido lo dice en la sección **Factura**, en la lista «Antes de facturar».

## 2. Facturar

1. Abre el pedido **confirmado**. Se puede facturar antes, durante o después de entregar.
2. En la sección **Factura**, elige la caja si la sucursal tiene varias.
3. Pulsa **Facturar**.

El documento queda **Emitiendo** y la sección se actualiza sola. Al terminar muestra el número
de control y los botones **Ver PDF** y **Descargar JSON**. Pulsar Facturar dos veces no crea dos
documentos: el pedido devuelve el que ya tiene.

Antes de enviar, el sistema comprueba que la solicitud cuadre al centavo con los totales del
pedido. Si no cuadra, no envía nada y pide editar y volver a confirmar el pedido.

## 3. Estados del documento

| Estado | Qué significa |
|---|---|
| Emitiendo | Se está enviando al servicio de facturación. |
| Simulado | Emitido en modo simulado: sin validez fiscal, no llegó a Hacienda. |
| Emitido | Hacienda lo recibió y le puso sello. |
| Rechazado | Hacienda lo rechazó; el detalle queda en el documento. |
| Falló | No se pudo emitir. Se puede reintentar. |

## 4. Si algo falla

- **Reintentar emisión** envía el mismo documento con la misma clave, así que nunca se duplica.
  Úsalo después de corregir lo que indica el mensaje (por ejemplo, habilitar el tipo de
  documento).
- Si el problema estaba en los datos del pedido o del cliente, corrígelos y pulsa **Facturar de
  nuevo**: se arma un documento nuevo con los datos actuales.
- Un pedido facturado ya no se puede cancelar. La corrección se hará con invalidación o nota de
  crédito (bloque V4).

## 5. Bandeja «Documentos fiscales»

En **Ventas → Documentos fiscales** están todos los documentos de la sucursal, con filtros por
estado y tipo y búsqueda por número de control, pedido o cliente. El detalle muestra el código
de generación, el sello, los intentos y el último error, y permite descargar el JSON y el PDF.

## 6. Permisos

| Permiso | Qué permite |
|---|---|
| `sales_invoices:read` | Ver la sección Factura, la bandeja y descargar JSON y PDF. |
| `sales_invoices:issue` | Facturar y reintentar. |

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

## 6. Envío por correo

El documento emitido se envía al cliente con el PDF y el JSON adjuntos. Sale desde el correo
propio de la empresa (**Configuración fiscal → Correo**, ver el manual de configuración fiscal)
y, si la empresa no lo configuró, desde el correo del servidor. Si el cliente responde, la
respuesta llega al correo DTE de la empresa. Al pie va el aviso de privacidad vigente.

- **Automático**: al terminar de emitirse, si la ficha del cliente tiene un correo válido, el
  documento se envía solo (una vez).
- **Manual**: en la sección **Envío por correo** del documento (o en la sección Factura del
  pedido) escribe hasta 5 correos separados por comas y pulsa **Enviar por correo**. Si dejas el
  correo del cliente, se usa ese.
- El historial muestra a quién se envió, si fue automático o quién lo pidió, y si llegó al
  servidor de correo (**Enviado**), si sigue en proceso (**Enviando**) o si falló (**No se
  envió**, con el motivo).
- Un documento **simulado** se envía con la marca «SIMULADO — sin validez fiscal» en el asunto y
  en el cuerpo.
- Si la empresa no tiene correo saliente (ni propio ni del servidor), la sección lo indica y no
  deja enviar.

En desarrollo, los correos no salen a internet: llegan al buzón de prueba Mailpit, en
<http://localhost:8025>.

## 7. Permisos

| Permiso | Qué permite |
|---|---|
| `sales_invoices:read` | Ver la sección Factura, la bandeja, el historial de envíos y descargar JSON y PDF. |
| `sales_invoices:issue` | Facturar, reintentar y enviar por correo. |

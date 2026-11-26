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
3. Revisa el **tipo de operación** y el **tipo de ingreso (renta)**. Vienen propuestos por la
   actividad económica del establecimiento; cámbialos si esta venta es distinta (por ejemplo, un
   servicio en una empresa comercial, o una venta con operaciones gravadas y exentas: «Mixta»).
   Sin ellos no se puede facturar. El documento los guarda para los anexos de ventas del F-07.
4. Pulsa **Facturar**.

El documento queda **Emitiendo** y la sección se actualiza sola. Al terminar muestra el número
de control y los botones **Ver PDF** y **Descargar JSON**. Pulsar Facturar dos veces no crea dos
documentos: el pedido devuelve el que ya tiene.

Antes de enviar, el sistema comprueba que la solicitud cuadre al centavo con los totales del
pedido. Si no cuadra, no envía nada y pide editar y volver a confirmar el pedido.

## 3. Estados del documento

| Estado | Qué significa |
|---|---|
| Emitiendo | Se está enviando al servicio de facturación. |
| En contingencia | Se generó sin comunicación con Hacienda. Tiene número de control y PDF, y se transmite al cerrar la contingencia. |
| Simulado | Emitido en modo simulado: sin validez fiscal, no llegó a Hacienda. |
| Emitido | Hacienda lo recibió y le puso sello. |
| Rechazado | Hacienda lo rechazó; el detalle queda en el documento. |
| Falló | No se pudo emitir. Se puede reintentar. |
| Invalidado | Se anuló ante Hacienda con un evento de invalidación; ya no tiene validez. |

## 4. Si algo falla

- **Reintentar emisión** envía el mismo documento con la misma clave, así que nunca se duplica.
  Úsalo después de corregir lo que indica el mensaje (por ejemplo, habilitar el tipo de
  documento).
- Si Hacienda **rechazó** el documento, la sección Factura del pedido muestra sus observaciones.
  Corrige los datos del pedido o del cliente y pulsa **Facturar**: se emite un documento nuevo y
  el rechazado queda en el historial.

## 4.1 Anular o corregir un documento emitido

Un documento con sello no se borra. En su detalle, la sección **Anulación y corrección** dice
hasta cuándo se puede (tres meses desde el sello para una factura; hasta el décimo día hábil del
mes siguiente para un crédito fiscal) y ofrece:

- **Corregir documento**: para un error en los datos. Corrige antes los datos del cliente o del
  pedido. Se emite un documento nuevo con los datos actuales y, cuando queda sellado, el
  original se invalida solo y ambos quedan vinculados. Si el reemplazo no se emite, el original
  sigue vigente.
- **Anular documento**: la operación se rescinde; pide el motivo. No se emite otro documento.

En los dos casos se indica quién lo solicita (nombre y documento). El evento lo firma el
**responsable fiscal** de la empresa, que se registra en **Ventas → Contingencia**.

Para **cancelar un pedido facturado**, usa **Cancelar pedido** en el pedido: pide el motivo y
el solicitante, anula su documento ante Hacienda y el pedido se cancela cuando Hacienda lo
acepta. Un pedido con entregas no se cancela así: se gestiona con devoluciones.

Cuando Hacienda acepta la anulación, el cliente recibe por correo un aviso con el comprobante
del evento. Si la rechaza (por ejemplo, fuera de plazo), el documento sigue vigente y el
motivo queda en el historial.

## 4.2 Notas de crédito y de débito

Las notas ajustan un **crédito fiscal** sellado (Código Tributario, art. 110). La **nota de
crédito** rebaja lo documentado; la **nota de débito** lo aumenta. Las dos son solo fiscales: no
mueven inventario ni reintegran dinero. Cuando el cliente devuelve mercadería, la nota de crédito (o el
evento de retorno de una factura) se emite sola al aceptar la devolución; ver
[manual-cobros.md §8](manual-cobros.md). La
empresa debe tener habilitados los tipos 05 y 06 en **Configuración fiscal → Documentos**.

En el detalle del crédito fiscal, la sección **Notas de crédito y de débito** muestra cada línea
con lo vendido, lo devuelto, su venta neta y el **saldo por acreditar**, y la lista de sus notas.

- **Emitir nota de crédito**: en cada línea elige **Devolución** (la cantidad devuelta; se acredita
  al precio neto con el que se vendió, descuento global incluido) o **Rebaja** (el monto que se
  descuenta, sin IVA). No pasa del saldo de la línea.
- **Emitir nota de débito**: agrega cargos sin IVA (descripción, cantidad, precio). Un cargo puede
  ajustar una línea del crédito fiscal (toma su tipo de venta) o ser libre, como intereses o flete
  (eliges si es gravado, exento o no sujeto). No consume saldo.
- Las dos se emiten hasta **tres meses** desde la fecha del crédito fiscal (Normativa de
  Cumplimiento DTE 2.0, anexo IV, regla 2c; para la nota de crédito, también CT art. 111): Hacienda
  rechaza una nota fuera de ese plazo. Vencido, la sección lo indica y no deja emitirlas.
- Las dos piden el **motivo** y muestran el total estimado: si el crédito fiscal retuvo o percibió
  el 1 % de IVA, la nota repite la misma retención o percepción sobre lo gravado.
- La nota pertenece al mismo pedido, hereda la clasificación de renta del crédito fiscal, se emite
  como cualquier documento y se envía al cliente por correo. Su detalle enlaza al crédito fiscal.

Una nota no se corrige: se **anula** (rescindir la operación) y, si hace falta, se emite otra.
Anularla devuelve el saldo y no cancela el pedido. Un crédito fiscal con notas vigentes no se
anula ni se corrige: primero se anulan sus notas.

## 4.3 Nota de remisión de los traslados

La nota de remisión (04) no se emite desde un pedido: sale sola al despachar un traslado si la empresa
la habilitó. Ver [manual-traslados.md](manual-traslados.md) («Nota de remisión al despachar»). En la
bandeja aparece con el código del traslado en lugar del pedido; su detalle no tiene cliente, correo ni
clasificación de renta. Se corrige con **Corregir documento** (reemplazo); no se anula.

## 4.4 Eventos de retorno

El **evento de retorno** registra ante Hacienda la mercadería que un consumidor devuelve sobre una
**factura** sellada (Normativa 2.0, regla 13.3). Es solo fiscal: no mueve inventario ni reintegra
dinero (las devoluciones con mercadería se gestionan aparte).

En el detalle de la factura, la sección **Eventos de retorno** muestra cada línea con lo vendido,
lo ya devuelto y el saldo, y la lista de retornos con su estado, PDF y JSON.

- **Registrar retorno**: escribe la cantidad devuelta en cada línea y el **motivo**. Los montos
  llevan el IVA incluido; la sección muestra el total estimado y el IVA. Si la factura retuvo el
  1 % de IVA, el retorno repite la retención. No pasa del saldo de cada línea.
- Se registra hasta **tres meses** desde la fecha de la factura, o hasta **dos años** si la
  empresa vende medicamentos (Ley IVA, art. 62). Vencido el plazo, la sección lo indica.
- Cuando Hacienda lo acepta, el cliente lo recibe por correo con el PDF y el JSON.
- **Anular retorno**: pide el nombre y documento del solicitante; lo firma el responsable de la
  sucursal. Anularlo devuelve el saldo a las líneas.

Una factura con retornos vigentes no se anula ni se corrige: primero se anulan sus retornos.

Los documentos emitidos, sus notas, anulaciones y retornos se reúnen cada mes en los libros de IVA y
los anexos del F-07: ver [manual-libros-iva.md](manual-libros-iva.md).

## 5. Contingencia

Cuando no hay comunicación con Hacienda se sigue facturando «en contingencia». Los documentos
quedan **En contingencia**: el cliente recibe su PDF, que dice que el sello está pendiente, y se
transmiten a Hacienda cuando la comunicación se restablece.

- **Sola**: si Hacienda no responde después de los reintentos, el establecimiento entra en
  contingencia sin que nadie haga nada y sale cuando Hacienda vuelve a responder.
- **Manual**: ante un corte de energía o de internet en la tienda, en **Ventas → Contingencia**
  pulsa **Activar contingencia**, elige el establecimiento, el tipo y, si es «Otro», el motivo.
  Al volver la comunicación, pulsa **Cerrar contingencia**.
- Al cerrarla se informa a Hacienda el **evento de contingencia**, firmado por el responsable que
  registres en esa misma pantalla (nombre y documento). Sin responsable el evento no se envía:
  regístralo y pulsa **Informar evento**.
- Plazos: el evento se informa dentro de las 24 horas siguientes al cierre y los documentos se
  transmiten dentro de las 72 horas siguientes al sello del evento. La pantalla los muestra y
  marca en rojo los vencidos.
- Mientras haya un establecimiento en contingencia, la bandeja lo avisa. Cada documento indica
  si se generó en contingencia y con qué motivo.
- En una empresa en modo simulado la contingencia se puede probar completa: el evento recibe
  un sello simulado y los documentos quedan **Simulados**.

## 6. Bandeja «Documentos fiscales»

En **Ventas → Documentos fiscales** están todos los documentos de la sucursal (facturas, créditos
fiscales, sus notas y las notas de remisión de los traslados), con filtros por estado y tipo y búsqueda por número de control, pedido, cliente o traslado. El detalle muestra el código
de generación, el sello, los intentos y el último error, y permite descargar el JSON y el PDF.

## 7. Envío por correo

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
- Un documento **en contingencia** se envía al generarse, con el aviso de que se transmitirá a
  Hacienda al restablecerse la comunicación. No se vuelve a enviar al sellarse; puedes reenviarlo
  a mano.
- Si la empresa no tiene correo saliente (ni propio ni del servidor), la sección lo indica y no
  deja enviar.

En desarrollo, los correos no salen a internet: llegan al buzón de prueba Mailpit, en
<http://localhost:8025>.

## 8. Permisos

| Permiso | Qué permite |
|---|---|
| `sales_invoices:read` | Ver la sección Factura, la bandeja, el historial de envíos y descargar JSON y PDF. |
| `sales_invoices:issue` | Facturar, reintentar y enviar por correo. |
| `sales_invoices:invalidate` | Anular y corregir documentos emitidos; con `sales:cancel`, cancelar un pedido facturado. |
| `sales_invoices:notes` | Emitir notas de crédito y de débito sobre un crédito fiscal. Ver su saldo y sus notas pide `sales_invoices:read`. |
| `sales_invoices:returns` | Registrar y anular eventos de retorno sobre una factura. Verlos pide `sales_invoices:read`. |
| `sales_invoices:contingency` | Activar y cerrar contingencias, informar el evento y registrar al responsable. Ver la pantalla Contingencia pide `sales_invoices:read`. |

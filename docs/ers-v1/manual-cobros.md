# Manual: cuentas por cobrar y recibos de cobro

En **Ventas → Cuentas por cobrar** se controla lo que deben los clientes por sus facturas, créditos
fiscales y notas de débito, y se registran los cobros con recibos.

## 1. El saldo de un documento

El saldo no se teclea: sale del documento fiscal.

- **Total a pagar** del DTE. Si el cliente es agente de retención, ya viene descontada la retención
  del 1 % de IVA.
- Menos las **notas de crédito** vigentes que ajustan el crédito fiscal y los **eventos de retorno**
  vigentes de la factura.
- Menos lo **cobrado** con recibos vigentes.

**Vencimiento**: la fecha del documento más los días de crédito del pedido. Una venta de contado
vence el mismo día: si no se registra su cobro, aparece como vencida.

Un documento invalidado deja de cobrarse; lo que ya se le había aplicado vuelve como saldo a favor
del cliente.

## 2. Cartera y estado de cuenta

- La **cartera** lista los clientes con saldo o saldo a favor: lo que deben, lo vencido, lo de más de
  90 días y la antigüedad del total (por vencer, 1 a 30, 31 a 60, 61 a 90 y más de 90 días).
- El **estado de cuenta** de un cliente muestra sus documentos (emisión, vencimiento, total, notas y
  retornos, cobrado y saldo) y sus recibos.

## 3. Registrar un cobro

Desde el estado de cuenta (**Registrar cobro**) o desde el detalle del documento fiscal (sección
**Cobro**, que ya trae el documento y su saldo):

1. Fecha del cobro (no futura) y, si trabajas con todas las sucursales, la sucursal que recibe.
2. **Formas de pago**: efectivo, tarjeta, transferencia, cheque u otro. Todas salvo el efectivo piden
   referencia (autorización, número de transferencia o de cheque). Se pueden combinar.
3. **Aplicar a documentos**: el monto de cada uno, o **Saldar**, o **Aplicar a los más antiguos**
   para repartir lo cobrado por fecha de vencimiento. Nunca se aplica más que el saldo de un
   documento.
4. Lo que no se aplica queda como **saldo a favor** del cliente y se aplica después con **Aplicar
   saldo a favor** en el recibo.

El recibo recibe un número correlativo por empresa (RC-000001) y se imprime con **PDF**. No es un
documento tributario.

## 4. Anular un recibo

Un recibo no se edita: si hubo un error (cheque rechazado, monto equivocado) se **anula** con motivo
y se registra otro. Al anularlo, los documentos recuperan su saldo. Queda en la bitácora.

## 5. Comprobante de retención

Si el documento tiene retención del 1 %, el cliente entrega su comprobante de retención. En la
sección **Cobro** del documento se registra su número (o código de generación), fecha y monto. No
cambia el saldo, porque la retención ya está descontada del total a pagar; respalda la casilla 162
del F-07.

## Permisos

| Permiso | Qué permite |
|---|---|
| `sales_receivables:read` | Ver la cartera, los estados de cuenta, los recibos y su PDF. |
| `sales_receivables:collect` | Registrar y anular recibos, aplicar saldo a favor y registrar comprobantes de retención. |

## 6. Límite de crédito y mora (V5b)

Un pedido **a crédito** pide autorización al confirmarlo cuando:

- **Pasa el límite** del cliente: lo que debe (saldo abierto) más sus pedidos a crédito confirmados
  sin facturar más este pedido supera su límite de crédito. Sin límite configurado no se evalúa.
- **Tiene mora**: saldos vencidos con más días que los de gracia de la empresa (por omisión, 0).
- **Su crédito está bloqueado.**

Los pedidos de contado no se evalúan. Estos motivos se suman a los de descuento: el pedido queda
«Espera autorización». Lo autoriza quien tiene `sales_credit:authorize`, escribiendo **por qué se
autoriza el crédito**; si además tiene descuentos fuera de tope, hace falta también el permiso de
descuentos.

Al **facturar** se vuelve a revisar: si desde que se confirmó el cliente pasó su cupo, entró en mora
o se bloqueó, la factura no se emite. Quien controla el crédito usa **Autorizar crédito para
facturar** en el pedido, con su motivo, y entonces se factura. Un pedido que ya se autorizó por
crédito se factura sin volver a preguntar.

## 7. Gestión de cobro

En el estado de cuenta, la sección **Crédito y cobranza** muestra el límite, los pedidos sin
facturar, el **disponible** y la **mora**, y permite:

- **Notas de seguimiento**: qué se habló con el cliente y la fecha de la próxima acción.
- **Estado de cuenta (PDF)** y **Enviar por correo** al cliente (o a otra dirección), con el SMTP de la
  empresa o el del servidor.
- **Bloquear o desbloquear el crédito** con motivo (permiso `sales_credit:authorize`).

Todo queda en la bitácora.

| Permiso | Qué permite |
|---|---|
| `sales_credit:authorize` | Autorizar pedidos a crédito fuera de cupo, con mora o de un cliente bloqueado, y bloquear o desbloquear clientes. |

## 8. Devoluciones: ajuste fiscal, saldo a favor y reintegro (V8a)

**Ajuste fiscal automático.** Al aceptar mercadería en la revisión de una devolución (B08) de un
pedido facturado, el sistema emite su documento sin pasos extra:

- Pedido con **crédito fiscal (03)** → **nota de crédito** por las unidades aceptadas.
- Pedido con **factura (01)** → **evento de retorno** sobre la factura.

Cada aceptación emite el suyo (una devolución puede aceptarse en varias veces) y un reintento de la
misma operación no emite otro. Si no se puede emitir, la aceptación física se guarda igual y la
devolución muestra **Sin ajuste fiscal** con el motivo: pedido sin facturar, documento aún sin sello,
plazo vencido para la nota, cantidades que ya se ajustaron… En ese caso el ajuste se hace a mano
desde el documento fiscal. El bloque **Ajuste fiscal** de la devolución enlaza la nota o la factura.

**Saldo a favor por sobrepago.** Si el documento ya estaba cobrado, la nota o el retorno lo dejan
pagado de más. Ese excedente vuelve a los recibos que lo cobraron, empezando por el más reciente, y
aparece como **saldo a favor** del recibo («Volvió al recibo $…»). Se puede aplicar a otro documento
(**Aplicar saldo a favor**) o devolver.

**Reintegro.** En el recibo con saldo a favor, **Reintegrar** registra el dinero devuelto al
cliente: fecha (no futura), monto (hasta el saldo a favor), forma (todas salvo el efectivo piden
referencia) y motivo. Recibe un número correlativo (RI-000001), no es un documento tributario y
queda en la bitácora. Si el reintegro no se concretó (transferencia rechazada, el cliente no lo
retiró), **Anular reintegro** con motivo devuelve el saldo a favor al recibo.

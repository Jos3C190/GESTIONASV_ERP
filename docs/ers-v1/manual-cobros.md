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

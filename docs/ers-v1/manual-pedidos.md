# Manual de uso — pedidos de venta

El pedido es el compromiso con el cliente: qué se le entrega, cuándo y dónde. Lleva los mismos
precios, descuentos e impuestos que la cotización. Al confirmarlo, el sistema descuenta las
existencias de la bodega y deja la salida en el kardex (ver la sección 3).

## 1. Estados

| Estado | Qué significa |
|---|---|
| Borrador | Se puede editar. Cada cambio recalcula precios, descuentos e impuestos. |
| Por autorizar | Una línea o el descuento global pasa el tope de quien confirma. |
| Confirmado | Las existencias salieron de la bodega o quedan apartadas. Desde aquí se registran entregas y devoluciones. |
| Cancelado | Se anuló con un motivo y liberó lo apartado. |

El avance de entrega (pendiente, parcial o entregado) se ve junto al estado.

## 2. Crear un pedido

Hay dos caminos:

- **Desde una cotización aceptada.** En la cotización, **Crear pedido**, con la fecha
  comprometida y el lugar de entrega. El pedido copia productos, precios, descuentos y totales
  tal como el cliente los aceptó. Mientras no lo edites, conserva la autorización de la
  cotización, así que no vuelve a pedir permiso por las mismas condiciones.
- **Directo.** En **Ventas → Pedidos → Nuevo pedido**. Funciona igual que la cotización: el
  precio sale de la lista del cliente y el descuento vacío aplica el sugerido.

Datos de entrega:

- **Fecha comprometida**: hoy o una fecha futura.
- **Entrega**: retiro en la sucursal o entrega a domicilio. Para entregar a domicilio, elige una
  de las direcciones de entrega del cliente (se agregan en su ficha).
- La **condición de pago** se toma del cliente: contado, o crédito si tiene días de crédito.

Mientras editas, cada línea muestra cuánto hay **disponible en la sucursal** sin contar este
pedido. Si no alcanza, el aviso aparece en color de advertencia.

## 3. Confirmar y apartar

1. **Confirmar y apartar.** El sistema revisa que alcance lo disponible en las bodegas de la
   sucursal, descontando lo que ya apartaron otros pedidos confirmados. Si no alcanza, dice qué
   producto falta y cuánto hay.
2. Si el pedido pasa tu tope, queda **Por autorizar**. Quien autoriza ve el costo y el margen, y
   puede autorizar (se aparta y queda confirmado) o devolverlo a borrador con lo que debe
   corregirse.
3. Nunca se confirma ni se autoriza una línea bajo el costo del kardex: el sistema usa el costo
   vigente en ese momento.
4. **Salida al confirmar.** Con la opción «Descontar existencias al confirmar el pedido» encendida
   (lo está por omisión, en **Ventas → Configuración de ventas**), al confirmar o autorizar se crea
   y confirma la entrega sola con las cajas o unidades completas que cubren lo vendido, primero
   las que vencen antes. La salida aparece en el **Kardex** con el código de la entrega y el
   pedido muestra un aviso con ese código.
5. Si para completar una línea hay que abrir una caja (por ejemplo, se venden 2 unidades y solo
   hay cajas de 6), esa parte queda apartada y el aviso lo dice: separa la unidad en bodega y
   entrégala con **Preparar entrega** (ver [manual-entregas.md](manual-entregas.md)).
6. Con la opción apagada, confirmar solo aparta y la entrega se prepara a mano.

## 4. Cancelar

**Cancelar pedido** pide un motivo y libera lo apartado. Un pedido que ya tiene entregas no se
cancela: se gestiona con devoluciones.

Un pedido **facturado** tampoco se cancela: la corrección se hará con invalidación o nota de
crédito. Para facturar, ver [manual-facturacion.md](manual-facturacion.md).

## 5. Lo que todavía no hace

- Los traslados y los ajustes de inventario aún no respetan lo apartado.
- El bloqueo por cupo de crédito y saldos vencidos llega con las cuentas por cobrar.
- La factura o el crédito fiscal del pedido llegan con el DTE.

## 6. Permisos

| Permiso | Para qué |
|---|---|
| `sales:read` | Ver pedidos. |
| `sales:manage` | Crear y editar borradores. |
| `sales:confirm` | Confirmar y apartar (y, con la opción encendida, entregar). |
| `fiscal_settings:manage` | Encender o apagar la salida al confirmar. |
| `sales:cancel` | Cancelar con motivo. |
| `sales_quotations:convert` | Crear el pedido de una cotización aceptada. |
| `sales_discounts:authorize` | Autorizar o devolver pedidos por autorizar. |
| `sales_prices:override` | Escribir un precio distinto al de lista. |

Toda acción queda en la bitácora con usuario, fecha, valores y motivo.

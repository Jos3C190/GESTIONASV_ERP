# Manual de uso — cotizaciones de venta

La cotización propone el precio de lista, aplica los descuentos permitidos, calcula los impuestos
y muestra el total en letras. Si algo pasa el tope de quien cotiza, la cotización espera la
autorización de alguien con un tope suficiente. Cotizar no reserva ni descuenta inventario.

## 1. Estados

| Estado | Qué significa |
|---|---|
| Borrador | Se puede editar. Cada cambio recalcula precios, descuentos e impuestos. |
| Por autorizar | Una línea o el descuento global pasa el tope, o un precio queda bajo el costo. |
| Emitida | Lista para el cliente. Se puede imprimir y registrar su respuesta. |
| Vencida | Emitida cuya vigencia pasó. Ya no se puede aceptar; sí rechazar o cancelar. |
| Aceptada | El cliente la aceptó. Desde aquí se crea la venta. |
| Rechazada | El cliente no la aceptó; queda el motivo. |
| Cancelada | Se anuló con un motivo. |

## 2. Preparar el borrador

1. Abre **Ventas → Cotizaciones de venta → Nueva cotización**.
2. Elige el cliente y la sucursal. El documento se propone solo: crédito fiscal si el cliente es
   contribuyente con los datos completos, si no, factura. Puedes cambiarlo entre los válidos.
3. Agrega los productos con su unidad y cantidad. El precio sale de la lista del cliente o, si no
   tiene, de la lista predeterminada.
4. Deja el **Descuento** vacío para aplicar el sugerido: el del cliente o el de volumen, el mayor.
   Si escribes otro, se compara con tu tope.
5. Si tienes permiso para cambiar precios, verás **Precio manual**. La diferencia contra el
   precio de lista cuenta como descuento ante tu tope y queda en la bitácora.
6. Mientras editas, el resumen muestra gravado, exento, descuentos, IVA, retención o percepción,
   el total y el total en letras. Si algo necesita autorización, lo verás antes de guardar.
7. **Válida hasta** vacío usa los días de vigencia de la empresa. Puedes poner otra fecha.

Un producto exento o no sujeto no lleva IVA, aunque la lista sea con IVA.

## 3. Emitir y autorizar

1. En el borrador, **Emitir cotización**. Si pasa tu tope, el botón dice **Enviar a autorización**
   y la cotización queda **Por autorizar** con los motivos a la vista.
2. Quien autoriza necesita el permiso de autorizar descuentos y un tope propio que cubra el
   descuento. Ninguna cotización se emite con precios bajo el costo del kardex, ni con
   autorización: hay que corregir el precio o el descuento.
3. Quien autoriza ve el costo y el margen de cada línea y puede:
   - **Autorizar**, con una nota opcional: la cotización queda Emitida.
   - **Devolver a borrador** con lo que debe corregirse. El vendedor lo ve en el borrador.

## 4. Respuesta del cliente

1. **Ver PDF** abre la versión imprimible: empresa, cliente, documento, productos con descuento,
   resumen fiscal, total en letras y vigencia. Nunca muestra costos ni márgenes.
2. Registra **El cliente aceptó** o **El cliente rechazó** (con el motivo).
3. Desde una Aceptada, **Crear pedido** genera el pedido en borrador con sus mismas condiciones
   (una sola vez). Ver [manual-pedidos.md](manual-pedidos.md).

## 5. Vigencia por empresa

En **Ventas → Configuración fiscal → Cotizaciones** se fijan los días de vigencia por defecto
(15 de entrada, de 1 a 365). El cambio aplica a las cotizaciones nuevas.

## 6. Permisos

| Permiso | Para qué |
|---|---|
| `sales_quotations:read` | Ver cotizaciones y su PDF. |
| `sales_quotations:manage` | Crear y editar borradores. |
| `sales_quotations:confirm` | Emitir, registrar la respuesta del cliente y cancelar. |
| `sales_quotations:convert` | Crear el pedido desde una Aceptada. |
| `sales_discounts:authorize` | Autorizar o devolver cotizaciones por autorizar. |
| `sales_prices:override` | Escribir un precio distinto al de lista. |
| `sales_costs:read` | Ver costo y margen. |

Toda acción queda en la bitácora con usuario, fecha, valores y motivo.

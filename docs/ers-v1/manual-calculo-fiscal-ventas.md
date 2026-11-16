# Manual: cálculo fiscal de las ventas

Todos los documentos de venta usan el mismo cálculo de impuestos: la cotización, el
pedido, la caja y el documento tributario electrónico (DTE). Por eso un mismo pedido da
los mismos montos en cualquier pantalla. Nadie teclea el IVA: lo calcula el sistema.

## De dónde salen los datos

| Dato | Dónde se configura |
|---|---|
| Si la empresa es gran contribuyente | **Ventas → Configuración fiscal → Emisor**, campo categoría de contribuyente. |
| Si el cliente es contribuyente, gran contribuyente o agente de retención | Ficha del cliente, **Identidad fiscal**. |
| Si el producto es gravado, exento o no sujeto, y si es bien o servicio | Ficha del producto, **Clasificación fiscal**. |
| Qué documentos emite la empresa | **Ventas → Configuración fiscal → Documentos**. |

## Factura y crédito fiscal

El mismo producto se expresa distinto en cada documento:

| Concepto | Factura (consumidor final) | Crédito fiscal (contribuyente) |
|---|---|---|
| Precio | $1.13, con IVA incluido | $1.00, sin IVA |
| IVA | $0.13, incluido en el precio | $0.13, sumado aparte |
| Total a pagar | $1.13 | $1.13 |

Si el precio se registró con IVA y el documento lo pide sin IVA, o al revés, el sistema lo
convierte (÷ 1.13 o × 1.13). Los productos exentos y no sujetos no llevan IVA en ningún
documento.

## Descuentos

- **Por línea**: se resta de precio × cantidad, por el total de la línea. Por ejemplo, 10
  unidades a $1.00 con $0.10 de descuento cada una llevan un descuento de línea de $1.00.
- **Global**: se aplica al total de cada tipo de venta (gravada, exenta o no sujeta). En el
  crédito fiscal el IVA se calcula después de restar el descuento global.

Ningún descuento puede superar el monto al que se aplica.

## Retención y percepción del 1 %

- **Retención** (Código Tributario, art. 162): el cliente retiene el 1 % cuando es gran
  contribuyente o agente de retención, la empresa no es gran contribuyente y la venta
  gravada sin IVA llega a $100. Se resta del total.
- **Percepción** (art. 163): la empresa cobra el 1 % en el crédito fiscal cuando ella es gran
  contribuyente, el cliente no lo es y la venta gravada de bienes llega a $100. Se suma al
  total. Los servicios no generan percepción.

## Redondeo

Como lo exige Hacienda (Manual Funcional, cap. XXI): las líneas se calculan con 8
decimales y los totales con 2, redondeando la mitad hacia arriba. Así, $5.665 se registra
como $5.67.

## Total en letras

Cada documento lleva su total en letras, por ejemplo «SETECIENTOS OCHENTA Y UNO 20/100
DÓLARES».

## Lo que todavía no admite

- Productos con tributos adicionales (FOVIAL, COTRANS, impuestos a bebidas o tabaco): el
  cálculo los rechaza con un mensaje, porque sus tasas no son el 13 %.
- Factura de exportación, notas de crédito y débito: llegan con la emisión de DTE.
- Promociones: llegan con la caja.

## Ejemplo verificado

El ejemplo oficial del Manual Funcional (cap. XVIII) da los mismos montos en el sistema:
crédito fiscal con $775.00 gravados y $77.50 de descuento global a un gran contribuyente.

| Concepto | Monto |
|---|---|
| Subtotal | $697.50 |
| IVA 13 % | $90.68 |
| IVA retenido | $6.98 |
| Monto total de la operación | $781.20 |

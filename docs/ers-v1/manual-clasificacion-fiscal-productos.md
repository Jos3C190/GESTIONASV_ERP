# Manual: clasificación fiscal de productos

Cada línea de un documento tributario electrónico (DTE) dice cómo se trata el producto
ante el IVA, qué tipo de ítem es y en qué unidad de medida de Hacienda se vende. Esos datos
se configuran una vez por producto y por unidad.

## En la ficha del producto

Pantalla: **Productos → (producto)**, tarjeta **Clasificación fiscal**.
Para consultarla basta el permiso `products:read`; para editarla hace falta
`products:fiscal`.

- **Tratamiento de IVA.**
  - *Gravado*: lleva IVA del 13 % y es lo habitual.
  - *Exento*: la ley lo libera del IVA y se registra como venta exenta.
  - *No sujeto*: la operación queda fuera del alcance del IVA.
  - Todo producto empieza como gravado. Cámbialo solo si la ley lo indica para ese producto.
- **Tipo de ítem en el DTE.** Se toma del tipo de producto: bien o servicio. Elige
  «Bienes y servicios» solo si el producto incluye los dos.
- **Tributos adicionales.**
  - Son tributos que el producto lleva además del IVA, por ejemplo FOVIAL y COTRANS en
    combustibles, o impuestos especiales a bebidas y tabaco.
  - Solo los admite un producto gravado.
  - El IVA no se elige aquí: lo determina el tipo de venta.
- **Unidad de venta ante Hacienda.** Muestra la unidad de medida de Hacienda que se usará
  para la unidad de venta del producto.

Si algo impide facturar el producto, la tarjeta lo indica en **Para facturar este
producto falta:**. Por ejemplo, cuando la unidad de venta no está habilitada en la
empresa.

## Unidades de medida

Pantalla: **Ventas → Configuración fiscal → Unidades**.
Para consultarla basta el permiso `fiscal_settings:read`; para cambiarla hace falta
`fiscal_settings:manage`.

Cada unidad de la empresa tiene un código de Hacienda sugerido: unidad 59, kilogramo 34,
gramo 39, libra 36, litro 23, mililitro 26, galón 22, metro 1.

Las presentaciones que Hacienda no tiene, como caja, paquete o pie, van como **99, Otra**.
Puedes elegir otro código; si vuelves a «Usar la sugerida», se aplica la sugerencia.

## Bitácora

Cada cambio queda en la bitácora con sus valores anteriores y nuevos. Los recursos son:
- `product_fiscal`
- `fiscal_unit`

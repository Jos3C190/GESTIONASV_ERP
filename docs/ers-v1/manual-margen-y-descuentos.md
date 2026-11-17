# Manual: margen, precio sugerido y descuentos

El costo de un producto (que ya incluye el retaceo) y su precio de venta son cosas distintas.
La diferencia es el margen. Estas herramientas ayudan a fijar precios que dejen ganancia y a
controlar los descuentos.

## El margen

El margen se mide sobre el precio sin IVA:

> margen % = (precio sin IVA − costo) ÷ precio sin IVA

Por ejemplo, un producto con costo de $7.00 y precio de $11.30 con IVA ($10.00 sin IVA) deja
30 % de margen.

En **Ventas → Listas de precios → (lista)**, junto a cada precio aparecen el costo actual y el
margen:

- en **verde**, si alcanza el margen objetivo;
- en **amarillo**, con «Bajo el objetivo», si no lo alcanza;
- en **rojo**, con «Bajo costo», si el precio no cubre el costo.

Solo lo ven los usuarios con el permiso `sales_costs:read`. Si el producto no tiene costo
registrado en inventario, se indica «Costo sin registrar».

## Margen objetivo y precio sugerido

Con **Cambiar margen objetivo** se define el margen que busca la lista, por ejemplo 35 % en
Mostrador y 20 % en Mayoreo. Una categoría de productos puede tener su propio margen dentro de
la lista; si no lo tiene, usa el de la lista.

Al cambiar un precio, el sistema muestra el **precio sugerido**:

> precio sugerido sin IVA = costo ÷ (1 − margen objetivo)

En una lista con IVA se le suma el IVA. Con costo de $7.00 y 30 % de margen, el sugerido es
$10.00 sin IVA, o $11.30 con IVA. **Usar** lo copia en el precio; puedes ajustarlo antes de
guardar.

## Descuento fijo del cliente

En la ficha del cliente, **Descuento fijo (%)** es el descuento que tiene siempre, por ejemplo 3 %
para un negocio frecuente. Se propone en cada línea de sus cotizaciones y pedidos.

## Descuento por volumen

En la lista de precios, **Volumen** abre las escalas del producto en esa unidad, por ejemplo:

- desde 10 cajas, 3 %;
- desde 50 cajas, 6 %.

Aplica la escala más alta que alcance la cantidad. Una escala nueva para la misma cantidad
reemplaza a la anterior desde la fecha indicada. Una programada se puede anular, y una vigente
se puede terminar hoy.

**Los descuentos no se suman**: si el cliente tiene 3 % fijo y la cantidad alcanza 6 % por
volumen, se propone 6 %.

## Topes de descuento por rol

En **Ventas → Topes de descuento** (permiso `sales_discounts:manage`) se define, para cada rol:

- el descuento máximo por línea;
- el descuento máximo sobre el total;
- si puede vender por debajo del costo.

Un usuario con varios roles toma el tope más alto. Un rol sin topes no puede dar descuento sin
autorización. El superadministrador no tiene tope.

Cuando un vendedor propone un descuento mayor que su tope, o un precio que queda bajo el costo,
el sistema marca la línea como **requiere autorización** y explica el motivo. La cotización y
el pedido usan esa marca para pedir la autorización de un supervisor.

## Datos de demostración

Grupo Lorena tiene:

- Mostrador con 35 % de margen objetivo y Mayoreo con 20 %;
- escalas en Mayoreo para las bolsas por caja (desde 10 cajas, 3 %; desde 50, 6 %);
- Cafetería El Trigal (CLI-00001) con 3 % de descuento fijo;
- topes: GERENTE DE SUCURSAL hasta 10 % por línea y 5 % global; EMPLEADO hasta 3 % por línea.

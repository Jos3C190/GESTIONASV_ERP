# Manual: listas de precios

El precio de venta sale de una lista de precios: el vendedor no lo teclea. Cada empresa
define sus listas, por ejemplo «Mostrador» para el público y «Mayoreo» para negocios.

Pantalla: **Ventas → Listas de precios**. Para consultarla hace falta el permiso
`price_lists:read`; para crear listas y cambiar precios, `price_lists:manage`.

## Las listas

Cada lista tiene un código, un nombre y una regla de IVA:

- **Incluyen IVA**: lo habitual para el mostrador y el consumidor final, porque al público
  se le muestra el precio total.
- **No incluyen IVA**: lo habitual para mayoreo y contribuyentes, que ven el IVA aparte.

El sistema convierte el precio al documento que se emita: un precio con IVA se divide entre
1.13 para el crédito fiscal, y uno sin IVA se multiplica por 1.13 para la factura.

Una lista es la **predeterminada**: la usan los clientes que no tienen lista asignada. La
primera lista que se crea queda como predeterminada. Para cambiarla, marca otra como
predeterminada.

## Los precios

Abre una lista con **Ver precios**. Aparecen los productos activos, marcados como vendibles y
con artículo de inventario, en su unidad base y en sus empaques vigentes (por ejemplo, la
unidad suelta y la caja de 25).

Para cambiar un precio, pulsa **Cambiar** (o **Fijar precio** si aún no tiene):

1. Escribe el precio. Debajo se muestra el equivalente con o sin IVA.
2. Elige desde qué día rige: hoy o una fecha futura. El historial no se reescribe hacia
   atrás.
3. Elige si aplica a todas las sucursales o solo a una.

El precio anterior no se borra: termina el día antes de que empiece el nuevo y queda en el
**Historial**. Desde el historial puedes:

- **Anular** un precio programado que todavía no empieza. El anterior vuelve a quedar
  vigente.
- **Terminar hoy** un precio vigente. Si era de una sucursal, desde mañana esa sucursal usa
  el precio general.

### Precio por sucursal

Una sucursal puede tener su propio precio dentro de la misma lista. Ese precio gana al
general solo en esa sucursal. En la pantalla, el filtro **Sucursal** muestra los precios que
rigen en ella, y la columna de precio indica **Sucursal** cuando el precio es propio.

### Precios a una fecha

El filtro **Precios al día** muestra los precios que regirán (o regían) en otra fecha.

## La lista del cliente

En la ficha del cliente, el campo **Lista de precios** define de qué lista salen sus precios.
Si queda en «La predeterminada», usa la lista predeterminada. Si la lista del cliente se
desactiva, el cliente vuelve a la predeterminada.

## Cómo se elige el precio de una venta

La cotización y el pedido piden el precio al sistema con el cliente, la sucursal y la fecha:

1. Se usa la lista del cliente, si tiene y está activa; si no, la predeterminada.
2. Dentro de la lista, el precio de la sucursal gana al general.
3. Solo cuenta un precio que rija ese día.

Si el producto no tiene precio, el sistema lo indica y no inventa uno.

## Datos de demostración

Grupo Lorena tiene:

- **Mostrador**, la predeterminada, con IVA incluido.
- **Mayoreo**, sin IVA: 10 % menos que mostrador antes de IVA, con precio por caja.
- Un precio propio del café en la sucursal Roosevelt.

Cafetería El Trigal (CLI-00001) y Distribuidora La Espiga (CLI-00002) usan Mayoreo.

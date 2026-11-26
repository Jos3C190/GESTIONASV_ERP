# Manual: análisis comercial y metas de venta

En **Ventas → Análisis** la gerencia y cada tienda leen el desempeño de las ventas. El **Dashboard** muestra,
arriba, la venta del mes, los documentos, el tiquete promedio y el avance de las metas, con un enlace al
análisis.

## Quién ve qué

| Permiso | Qué permite |
|---|---|
| `sales_analytics:read` | Ver las cifras de venta (también en el Dashboard), el análisis y las metas. Sin él, el Dashboard no muestra nada de ventas. |
| `sales_costs:read` | Ver además el costo y el margen bruto. |
| `sales_goals:manage` | Definir las metas mensuales por sucursal. |

Cada usuario ve solo las sucursales de su alcance: con «Todas las sucursales» (si las puede ver todas) o con
la sucursal operativa elegida arriba.

## De dónde salen las cifras

- **Venta sin IVA**: las facturas y los créditos fiscales **vigentes** del rango (sellados, simulados o en
  contingencia; no los fallidos, rechazados, invalidados ni reemplazados), por su fecha de emisión. En la
  factura el precio trae el IVA incluido y aquí se le quita.
- **Documentos** y **tiquete promedio**: cuántos documentos y la venta entre documentos.
- **Devoluciones**: las notas de crédito y los eventos de retorno vigentes del rango, sin IVA, y su porcentaje
  sobre la venta.
- **Margen bruto** (con permiso de costos): venta menos el **costo promedio de salida** de lo entregado (el
  mismo del kardex); si la línea aún no se entregó, el costo con el que se cotizó.

## Cortes

Venta por día y por hora de emisión, por sucursal (con su meta y avance), por categoría, clientes principales y
productos más vendidos; con más de diez productos aparecen también los menos vendidos.

## Metas

**Metas del mes** (permiso `sales_goals:manage`) abre la meta de venta sin IVA de cada sucursal para el mes de la
fecha inicial. Dejar el monto vacío quita la meta. El avance es la venta del rango entre la meta de los meses que
abarca. Los cambios quedan en la bitácora (`SET_SALES_GOALS`).

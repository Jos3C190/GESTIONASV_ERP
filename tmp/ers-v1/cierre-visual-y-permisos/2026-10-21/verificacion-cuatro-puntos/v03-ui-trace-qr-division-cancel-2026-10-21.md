# V03 — UI de trazabilidad, QR y cancelación de división

**Fecha:** 21/10/2026 · **Modalidad:** navegador autenticado/anónimo y conciliación de solo lectura · **Persistencia:** `erp_db_ers_final4p_20261020`.

## Identidad privada de la unidad

En `/warehouses/d31dce4f-6078-47fb-a3e5-55e043abb6b0#inventario`, la tabla de Unidades logísticas identifica para `HU-8D63FE508BF14124`:

- Producto: **Café Tostado y Molido 1kg** (`PRD-CAF-011`); cantidad **2.25 Caja (cj)**.
- Bodega/ubicación: `BOD-USU-01` / `SEC-02`; estado `Disponible`.
- Recepción: `COM-00017`; cabecera `LOT-COM-00017`; detalle canónico `LOT-COM-00017-DA9DBC0769F114438A8C0CF242E8344D8`.
- El fabricante no proporcionó un lote de fabricante; no se inventó un alias.

## Consulta QR pública

Se abrió el QR de `HU-8FEE57267CC84449` desde su fila de almacén y el navegador mostró `/inventory/trace` sin inicio de sesión. La vista expuso SKU/nombre, código HU, cantidad/unidad, estado, bodega/ubicación, cabecera/detalle de recepción, proveedor, orden/compra/consolidado y nueve movimientos públicos. No mostró costo, promedio, valor de inventario ni datos de empleados. El token/capability de la URL no se conserva aquí.

La operación de lectura creó una capability adicional en la **base clonada**: el recuento activo de esa HU era 7 antes y 8 después. No afecta `erp_db`; no se revocaron las capabilities históricas ni se guardó el token. Consulta SQL posterior: `reconciliation-final.log`.

## Abrir y cancelar división

Se abrió «Otras acciones» → «Dividir unidad» para `HU-8D63FE508BF14124`. El formulario mostró el nombre del producto, código HU, cantidad total y unidad `2.25 Caja (cj)`, la ubicación de la nueva unidad y la nota de que ambas unidades requerirían revisión. No se introdujo cantidad ni se confirmó. Se pulsó **Cancelar**.

El formulario se cerró. En la lectura posterior ambas HUs de control conservaron la cantidad y estado originales: `HU-8D63FE508BF14124` = 2.25, Disponible; `HU-8FEE57267CC84449` = 2.25, Disponible. No se creó una tercera HU. La consulta posterior reportó 4 y 9 líneas de movimiento vinculadas, respectivamente; no se usa ese conteo como comparación antes/después. El único incremento antes/después medido fue la capability pública de consulta del QR, no una división.

## Límite del caso

Se comprobaron lectura de la ficha, resolución pública QR y abrir/cancelar división. No se consultaron desde cada filtro de Kardex todos los alias históricos ni se ejecutó una nueva recepción visual de varias líneas del mismo SKU. `V03` por tanto sigue **ABIERTO**. La sesión CUA permitió observar la pantalla, pero no produjo un PNG archivado; eso corresponde a `V02`.

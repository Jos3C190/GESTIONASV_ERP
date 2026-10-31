# Verificación del flujo de unidades logísticas

**Fecha:** 17/10/2026  
**Bodega:** Bodega de tienda Usulután (`BOD-USU-01`)  
**Empresa:** Grupo Lorena

## Resultado

La lista de bodega ahora identifica el producto **Café Tostado y Molido 1kg**, SKU `PRD-CAF-011`, la unidad base **Caja (cj)** y el lote de recepción `LOT-COM-00017`. Buscar por producto, SKU o lote devuelve las unidades correspondientes.

Se encontró y corrigió una diferencia de trazabilidad: la tabla leía solo el lote del fabricante, que está vacío en estas HUs; la etiqueta sí mostraba el lote de recepción. Además, la lista solo cargaba el lote para unidades en cuarentena. El backend ahora incluye el lote de recepción para todos los estados y la pantalla distingue `Fabricante` de `Recepción`.

## Aceptación en navegador

Se verificó la bodega en Docker, antes y después de recargar. No se confirmó ninguna división y no cambió el inventario.

- Línea final: **5 HUs, 9 cajas** en total.
- Códigos y cantidades: `HU-DC0E5941BC324574` 2.2; `HU-5B91A504489E4080` 2.25; `HU-EB8E841FE6534526` 0.05; `HU-8D63FE508BF14124` 2.25; `HU-8FEE57267CC84449` 2.25.
- Estados finales: las primeras tres siguen en **Cuarentena**; las últimas dos siguen **Disponibles**. Todas conservan `LOT-COM-00017`.
- Abrir **Otras acciones → Dividir unidad** muestra el producto, la HU y la unidad; cantidad vacía y confirmación deshabilitada.
- Cerrar el formulario no crea unidades. Introducir `1` y pulsar **Cancelar** cierra el formulario sin crear unidades. Tras recargar, siguen los mismos 5 códigos, cantidades y estados.
- Abrir el QR de una HU disponible muestra el lote y la etiqueta vigente confirmada. Abrir **Revisar etiqueta** de `HU-5B91A504489E4080` muestra el producto y lote correctos y avisa **Sin impresión previa**. Se cerró el diálogo sin imprimir ni confirmar colocación.
- Abrir el QR crea un enlace público de trazabilidad, según el comportamiento de la pantalla. No se registraron impresiones, confirmaciones de etiqueta ni movimientos de inventario durante esta aceptación.

No se reprodujo una división automática ni una rama nueva causada por abrir o cerrar el formulario o la etiqueta. El historial muestra divisiones explícitas anteriores; dividir es opcional y una unidad **Disponible** ya terminó su revisión.

## Verificación automatizada

- `HandlingUnitsPanel.test.ts`: **32 pruebas aprobadas**.
- `test_inventory_split_prepare_route.py` y `test_inventory_handling_unit_metadata.py`: **2 pruebas aprobadas**. La prueba de ruta usa la base aislada `erp_db_test`.
- `svelte-check`: **0 errores, 0 advertencias**.
- Ruff para los archivos backend tocados: **aprobado**.

## Pendiente antes de fraccionar cantidades decimales

El sistema acepta hasta seis decimales. Por eso `2.249999` puede dejar un remanente de `0.000001`. No se envió esa división a la bodega real. En el modelo actual no hay un incremento mínimo de fraccionamiento por producto, unidad base o presentación; la conversión de empaque no define qué fracciones físicas se permiten. `minimum_order_qty` y `order_multiple` son reglas de compra a proveedor, no reglas de división de inventario.

No se debe redondear ni eliminar el remanente por defecto. Falta definir una regla de fraccionamiento por producto/unidad (por ejemplo, incrementos enteros para presentaciones contables y precisión explícita para peso o volumen) y guardarla en la configuración antes de validar esos casos.

## Siguiente paso operativo

Para terminar el proceso normal, completa las medidas faltantes de `HU-DC0E5941BC324574` y `HU-EB8E841FE6534526`; luego imprime o registra la etiqueta vigente, confirma su colocación y libera cada unidad a **Disponible** cuando corresponda. `HU-5B91A504489E4080` ya tiene medidas verificadas; aún requiere impresión y confirmación de etiqueta. No vuelvas a dividir las dos HUs disponibles a menos que vayas a separar físicamente su contenido.

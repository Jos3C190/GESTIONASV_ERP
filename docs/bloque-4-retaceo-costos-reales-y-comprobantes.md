# Bloque 4: costos reales, comprobantes y retaceo

## Objetivo

Conservar los costos reales y sus respaldos, relacionarlos con la recepción verificada y mostrar cómo se asignó cada importe a los productos aceptados. El retaceo valora líneas ya recibidas; no agrega cantidades ni produce movimientos de Inventario.

## Flujo

1. Crear un borrador desde una compra/recepción verificada o cerrada con cantidad aceptada.
2. Copiar al retaceo los gastos registrados en su orden de compra y enlazar sus comprobantes existentes. No duplicar archivos ni volver a digitarlos.
3. Revisar la clasificación de cada costo heredado. La persona autorizada puede clasificarlo como flete, otro gasto, DAI o IVA de importación; el sistema no deduce el tratamiento contable por el nombre del tipo de gasto.
4. Agregar costos reales que falten, indicar concepto, monto y descripción, y adjuntar el comprobante. Un costo nuevo debe guardarse primero para obtener su identificador y habilitar la carga segura del archivo.
5. Para flete, otros gastos y DAI, distribuir manualmente el monto entre los detalles de compra que tuvieron cantidad aceptada. Los detalles con aceptación cero no son destinos válidos. La suma debe coincidir con el importe real antes de calcular.
6. Registrar el IVA de importación como importe informativo respaldado, sin asignarlo a productos y sin sumarlo al costo aterrizado.
7. Calcular el retaceo únicamente cuando cada costo activo tenga al menos un comprobante cargado y completo, y las distribuciones no informativas estén completas. La persona autorizada verifica y cierra usando las transiciones existentes.

## Datos y trazabilidad

- `retaceo_costs` conserva concepto, clasificación explícita, importe, descripción, tipo de gasto cuando proviene de la orden, UUID del gasto origen y estado activo/histórico.
- `retaceo_cost_allocations` conserva el monto asignado a cada detalle recibido (`purchase_detail_id`), una fila por costo y línea.
- `retaceo_cost_documents` enlaza de forma segura los comprobantes. Para costos heredados apunta al mismo `document_asset`; no crea una segunda copia del archivo.
- Las referencias de orden, gasto origen, tipo de gasto, documento, producto, unidad y recepción permanecen consultables para auditoría y análisis. Un gasto retirado del borrador se conserva inactivo con asignaciones y documentos; no se borra físicamente.
- La asignación manual produce los componentes de flete, otros gastos y DAI por línea y calcula el costo total/unitario sobre la cantidad aceptada. El FOB parte del detalle de recepción y se prorratea según la cantidad aceptada cuando difiere de la recibida.
- Guardar, calcular, verificar o cerrar el retaceo no escribe `inventory_movements`, no crea unidades logísticas y no altera saldos.

## Límites contables y fiscales

La aplicación conserva la clasificación que el usuario selecciona, suma la asignación indicada y calcula costos sobre los detalles aceptados. No infiere porcentajes de DAI, tipos de cambio, bases tributarias ni qué gastos son capitalizables. El IVA de importación queda fuera del costo aterrizado en este flujo, conforme al alcance implementado; Finanzas/Contabilidad debe ratificar el tratamiento contable definitivo antes de usar estos valores para una valoración oficial del inventario. También queda por validar la base del FOB contra factura/documentación y la distribución resultante con una hoja de control.

## Migración y registros anteriores

La revisión `0060` agrega las tablas de costo, asignación manual y vínculos a documentos. No inventa comprobantes ni reconstruye desglose para retaceos anteriores. En un borrador antiguo, la pantalla puede presentar los totales previos como grupos de transición; para recalcularlo se deben respaldar y revisar antes de guardar el detalle nuevo. Los retaceos ya calculados conservan sus líneas y totales históricos.

Aplicación local de migraciones con Docker Compose:

```powershell
docker compose run --rm migrate
```

Después, el servicio `backend` debe estar actualizado/reiniciado para usar el nuevo esquema. En desarrollo, el frontend utiliza su recarga habitual.

## Recorrido manual pendiente de comprobación

- Crear retaceo desde recepción verificada con varios gastos de orden y documentos ya adjuntos; confirmar que se copian sus referencias y que se pueden descargar.
- Añadir un gasto real, guardarlo, adjuntar el comprobante y distribuir el total entre dos líneas aceptadas; confirmar que el cálculo muestra exactamente la suma por producto.
- Intentar calcular con documento incompleto, sin comprobante, asignación incompleta, distribución mayor que el monto o una línea que no pertenece a esa recepción; confirmar que el backend rechaza el cálculo/entrada inválida.
- Agregar IVA de importación con comprobante; confirmar que se ve en su total informativo y no altera el costo aterrizado.
- Retirar un costo de un borrador y volver a consultarlo; confirmar que permanece como histórico inactivo junto con su referencia documental.
- Consultar el detalle del retaceo después de cada transición y confirmar que no se agregó movimiento de inventario.

No se ejecutaron pruebas automatizadas para este bloque durante la implementación actual.

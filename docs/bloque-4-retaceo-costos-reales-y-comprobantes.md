# Bloque 4: costos reales, comprobantes y retaceo

## Objetivo

Conservar los costos reales y sus respaldos, relacionarlos con la recepción verificada y mostrar cómo se asignó cada importe a los productos aceptados. El retaceo valora líneas ya recibidas; no agrega cantidades ni produce movimientos de Inventario.

## Flujo

1. Crear un borrador desde una compra/recepción verificada o cerrada con cantidad aceptada.
2. Copiar al retaceo los gastos registrados en su orden de compra y enlazar sus comprobantes existentes. No duplicar archivos ni volver a digitarlos.
3. Revisar la clasificación de cada costo heredado. La persona autorizada puede clasificarlo como flete y seguro, otro gasto o DAI (el IVA de importación ya no es una clasificación); el sistema no deduce el tratamiento contable por el nombre del tipo de gasto.
4. Agregar costos reales que falten, indicar concepto, monto y descripción, y adjuntar el comprobante. Un costo nuevo debe guardarse primero para obtener su identificador y habilitar la carga segura del archivo.
5. Flete y seguro, DAI y otros gastos se reparten automáticamente en el servidor según el FOB de cada línea con cantidad aceptada (mayor residuo a seis decimales); ya no se asignan montos por producto. Los detalles con aceptación cero no reciben reparto. El FOB sale de la factura de compra y es fijo.
6. El IVA de importación no forma parte del retaceo (revisión 0117): no se registra ni se suma al costo aterrizado.
7. Calcular el retaceo únicamente cuando cada costo activo tenga al menos un comprobante cargado y completo, y el reparto guardado coincida con el monto de cada costo. La persona autorizada verifica y cierra usando las transiciones existentes.

## Datos y trazabilidad

- `retaceo_costs` conserva concepto, clasificación explícita, importe, descripción, tipo de gasto cuando proviene de la orden, UUID del gasto origen y estado activo/histórico.
- `retaceo_cost_allocations` conserva el monto asignado a cada detalle recibido (`purchase_detail_id`), una fila por costo y línea.
- `retaceo_cost_documents` enlaza de forma segura los comprobantes. Para costos heredados apunta al mismo `document_asset`; no crea una segunda copia del archivo.
- Las referencias de orden, gasto origen, tipo de gasto, documento, producto, unidad y recepción permanecen consultables para auditoría y análisis. Un gasto retirado del borrador se conserva inactivo con asignaciones y documentos; no se borra físicamente.
- El reparto por FOB produce los componentes de flete, otros gastos y DAI por línea y calcula el costo total/unitario sobre la cantidad aceptada. El FOB parte del detalle de recepción y se prorratea según la cantidad aceptada cuando difiere de la recibida.
- Guardar, calcular, verificar o cerrar el retaceo no escribe `inventory_movements`, no crea unidades logísticas y no altera saldos.

## Límites contables y fiscales

La aplicación conserva la clasificación que el usuario selecciona, reparte cada importe según el FOB y calcula costos sobre los detalles aceptados. No infiere porcentajes de DAI, tipos de cambio, bases tributarias ni qué gastos son capitalizables. El IVA de importación no forma parte del retaceo (revisión 0117); Finanzas/Contabilidad debe ratificar el tratamiento contable definitivo antes de usar estos valores para una valoración oficial del inventario. También queda por validar la base del FOB contra factura/documentación y la distribución resultante con una hoja de control.

## Migración y registros anteriores

La revisión `0060` agrega las tablas de costo, asignación manual y vínculos a documentos. No inventa comprobantes ni reconstruye desglose para retaceos anteriores. En un borrador antiguo, la pantalla puede presentar los totales previos como grupos de transición; para recalcularlo se deben respaldar y revisar antes de guardar el detalle nuevo. Los retaceos ya calculados conservan sus líneas y totales históricos.

Aplicación local de migraciones con Docker Compose:

```powershell
docker compose run --rm migrate
```

Después, el servicio `backend` debe estar actualizado/reiniciado para usar el nuevo esquema. En desarrollo, el frontend utiliza su recarga habitual.

## Recorrido manual pendiente de comprobación

- Crear retaceo desde recepción verificada con varios gastos de orden y documentos ya adjuntos; confirmar que se copian sus referencias y que se pueden descargar.
- Añadir un gasto real, guardarlo y adjuntar el comprobante; confirmar que el reparto entre dos líneas aceptadas sigue su FOB y que el cálculo muestra exactamente la suma por producto.
- Intentar calcular con documento incompleto, sin comprobante o con un reparto que no coincide con el monto; confirmar que el backend rechaza el cálculo/entrada inválida y que envía `422` si se intenta mandar `allocations`.
- Intentar agregar un costo con clasificación `import_vat`; confirmar que el backend responde `422` y que el retaceo no muestra IVA.
- Retirar un costo de un borrador y volver a consultarlo; confirmar que permanece como histórico inactivo junto con su referencia documental.
- Consultar el detalle del retaceo después de cada transición y confirmar que no se agregó movimiento de inventario.

No se ejecutaron pruebas automatizadas para este bloque durante la implementación actual.

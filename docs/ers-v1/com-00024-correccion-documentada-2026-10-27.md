# COM-00024: corrección documentada del FOB

Fecha local: 27/10/2026. Estado: importe confirmado por Rodrigo; **no aplicado a saldos reales**.

## Hechos revisados

- Compra: `16fe2c34-9beb-4274-a4bc-c3d234a34a52`, COM-00024.
- Origen: COT-00050 → OC-00024 → COM-00024.
- Producto: Azúcar Glass Premium 10kg, 200 cajas × USD 10 = USD 2,000.
- La captura histórica contiene USD 2,000 de descuento y deja FOB neto 0.
- Rodrigo confirmó el 27/10/2026 que el descuento correcto era **5%**, equivalente
  a **USD 100**. El FOB correcto por esta línea es **USD 1,900**.
- La recepción ya está registrada en inventario. No corresponde recibir sus 200
  cajas otra vez ni borrar el asiento original.
- No confundir con COM-00025/RET-00019: aquel caso tiene FOB USD 39,990 y no se
  modificó a partir de esta confirmación.

## Aplicación permitida por el cambio

Abrir COM-00024, crear un retaceo manual y capturar FOB de línea **1900**.
Completar **flete, DAI e IVA reales** según sus comprobantes; escribir 0 solamente
si efectivamente no aplican. No se han supuesto sus importes.

En Notas se puede usar:

> Regularización de COM-00024: se capturó por error USD 2,000 de descuento sobre
> USD 2,000. El responsable confirmó descuento de 5% (USD 100); FOB neto USD 1,900.
> Se conserva la recepción original y se corrige su valor mediante este retaceo.

Agregar otros gastos reales detallados, adjuntar respaldo si se desea, guardar, calcular,
revisar la comparación de promedio, verificar y aplicar mediante el flujo existente.
El motivo se conserva en la auditoría y el resumen de aplicación. La comparación
debe identificar **ajuste de valor, entrada de unidades 0**. Al aplicar se añade un
asiento de costo relacionado con la recepción original y se actualiza el promedio
de la empresa; los asientos originales permanecen inmutables.

Esto regulariza el costo del inventario. Los valores comerciales históricos de la
cotización, orden y compra permanecen tal como se capturaron, vinculados al motivo
de corrección; no se presenta como una reescritura de la factura original.

## Verificación realizada sin afectar los datos

En una transacción con rollback se construyó un retaceo con FOB 1900 y cargos 0
**solo como datos de prueba**. Se calculó, verificó y simuló su aplicación por los
casos de uso. La proyección coincidió con el asiento simulado; no cambió la cantidad,
no se alteró ninguna fila histórica y repetir la aplicación no la duplicó.
Al terminar se comprobó que el retaceo temporal no existe en la base.

Script de evidencia: `tmp/ers-v1/bloque-1-2026-10-27/verify_historical_correction.py`.

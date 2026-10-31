# Orden consolidada sin bodega madre seleccionable

Fecha: 21/10/2026, America/El_Salvador.

## Síntoma aportado por el usuario

Al crear una orden desde las adjudicaciones de **COT-00048**, la lista “Bodega madre de recepción” aparecía vacía y deshabilitada con el aviso de que no existía una bodega madre activa y apta. La evidencia aportada es `C:/Users/rodri/AppData/Local/Temp/codex-clipboard-69ac87b4-b9c5-48b4-9197-88a0e69c952e.png`.

## Causa y corrección

`frontend/src/lib/features/purchase-orders/components/PurchaseOrderEditor.svelte`, en `loadWarehouses`, todavía filtraba las bodegas centrales exigiendo `!warehouse.branchId`. Esa condición pertenece al modelo anterior de central sin sucursal; B01 asocia la central a la sucursal matriz.

El editor excluía la configuración vigente. El contrato del servidor en `purchase_order_repository.get_destination_reference` ya contempla la central asociada a matriz y las autorizaciones continúan validándose en el servidor.

Se cambió únicamente el filtro del modo consolidado para admitir una central con sucursal asociada, activa, apta para almacenamiento y cuyo tipo no sea tránsito. La selección conserva la preferencia de `central_warehouse_id` y envía el `branch_id` de la bodega seleccionada. No se modificaron modelos, permisos, migraciones ni datos de bodegas, documentos o inventario.

## Comprobaciones

Se actualizó la prueba existente de creación desde adjudicación con una central asociada a una matriz distinta de la sucursal inicial del formulario. Comprueba su selección automática y el envío de bodega/matriz al servicio de creación. Se añadió cobertura de exclusión de almacén normal, central inactiva, central no apta, tránsito y central sin sucursal.

- **Reproducción antes del parche:** 2 fallos y 3 aprobadas; el editor no seleccionaba la central con matriz y prefería una central sin sucursal. Evidencia: [log de reproducción](../../tmp/ers-v1/2026-10-21-orden-bodega-matriz/regresion-reproducida.log), código de salida 1.
- **Después del parche:** `PurchaseOrderEditor.test.ts` y `purchase-orders-api.test.ts`, **10 pruebas aprobadas**, código 0. Evidencia: [log corregido](../../tmp/ers-v1/2026-10-21-orden-bodega-matriz/regresion-corregida.log).
- **ESLint de componente y prueba:** aprobado, código 0; [log](../../tmp/ers-v1/2026-10-21-orden-bodega-matriz/lint.log).
- Las pruebas se ejecutaron en el contenedor frontend existente con servicios simulados; no crearon órdenes ni accedieron a inventario persistido. La preparación local inicial se interrumpió antes de ejecutar las pruebas; no cambió los archivos de dependencias/lockfile.

## Confirmación manual pendiente

Recargar el formulario de la orden, comprobar que aparece la bodega madre asociada a matriz y continuar con la fecha esperada y las adjudicaciones existentes. La creación de una orden real y su recepción deben verificarse por el usuario; no se declaran ejecutadas por las pruebas del componente. Si sigue vacío tras recargar, revisar las respuestas y el estado operativo del almacén/matriz sin crear ni desvincular bodegas como atajo.

La captura corresponde a una orden con **tres adjudicaciones**, incluida **Harina Integral de Trigo 25kg**, 100 kg a $5. Los saldos numéricos del guion `DEMO-MANUAL-2110` no se aplican a esos productos históricos.

El cierre integrado B01–B08 continúa **PARCIAL**; esta corrección no acredita los casos V01–V04 pendientes.

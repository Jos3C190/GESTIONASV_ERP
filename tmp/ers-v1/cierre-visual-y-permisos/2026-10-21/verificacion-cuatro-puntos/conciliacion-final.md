# Conciliación final — verificación de cuatro puntos B01–B08

**Fecha:** 21/10/2026 · **Bases:** `erp_db_ers_final4p_20261020` y `erp_db` · **Consulta final:** transacción `READ ONLY`.

## Cuatro SKU protegidos

El baseline previo está en el [snapshot 20/10](../../2026-10-20/pasada-final/protected-skus-after-continuation.log). La consulta final por base está en [reconciliation-final.log](reconciliation-final.log). Los cuatro conservaron físico, valorado y valor en la demo y en el clon:

| SKU | Antes: físico / valorado / USD | Después clon: físico / valorado / USD | Después `erp_db`: físico / valorado / USD | Estado |
| --- | --- | --- | --- | --- |
| `ERS-INC-EE8FE228` | 4 / 4 / 40 | 4 / 4 / 40 | 4 / 4 / 40 | Conservado |
| `ERS-LATE-B1B55D6D` | 5 / 5 / 60 | 5 / 5 / 60 | 5 / 5 / 60 | Conservado |
| `ERS-REVIEW-DD6BBF85` | 12 / 12 / 160 | 12 / 12 / 160 | 12 / 12 / 160 | Conservado |
| `ERS-UI-F767BABC` | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | Conservado |

## Artículos usados por operaciones de aceptación

No se creó un SKU de catálogo nuevo para esta verificación; V04 usó artículos ya existentes y documentos ficticios bajo `ERS-FINAL-4P`.

| SKU / operación | Antes | Operación y evidencia de movimientos | Después | Conciliación |
| --- | --- | --- | --- | --- |
| `PRD-EMP-009` · traslado `TR-20261021-60344005` | Última entrada de valoración antes del despacho: 2,214 cajas, USD 0.50, promedio USD 0.000226. | Detalle `3841cf1c-1b00-40f3-a7bf-7c5c46c8ff25`: 10 planificadas/despachadas/recibidas en 8+2. El historial registra un despacho de 10 y dos recepciones (8 y 2); no hay entrada de valoración para esos traslados. | Antes de las salidas comerciales posteriores, la valoración global siguió en 2,214 cajas y USD 0.50; la primera salida registra 2,210. | Movimiento interno neutral en valoración global; dos recepciones parciales completan el mismo detalle. |
| `PRD-EMP-009` · venta/devolución `VTA-20261020-63B217FB` / `DEV-20261021-530AF39F` | Después del traslado y antes de la venta: 2,214 cajas, USD 0.50. | Dos entregas de 4 cajas: `ENT-20261021-C8347B11` y `ENT-20261021-AA22CD2A`. La devolución se vinculó solo a la primera: 3 recibidas, 2 aceptadas y 1 rechazada. El evento aceptado tiene un movimiento y una entrada de valoración; el rechazado no tiene ninguno. | 2,208 cajas, USD 0.498646 y promedio USD 0.000226. | Salida 8, entrada aceptada 2, rechazo sin entrada; saldo neto −6. No se repitió la confirmación. |
| `PRD-JAR-012` · corrección `AJ-20261020-000005` → `AJ-20261020-000006` | 192 L, USD 2.00, promedio USD 0.010417 (última valoración anterior al par). | Original: salida de 1 L, entrada de valoración `86f01d89-49e2-40ab-8c4a-5156fd22b3c3`, saldo 191 L/USD 1.989583. Corrección: entrada compensatoria de 1 L, valoración `69125993-ae46-46c0-975d-3ef9ba0c71b2`. Movimientos `0135aa3c-ee58-449b-bac5-61086c0d1eb5` y `9026eb0f-4fac-4d2e-b550-0516cc82cf75`; corrección vinculada al original. | 192 L, USD 2.00, promedio USD 0.010417. | El par invierte la salida original una vez; saldo cuantitativo y valorizado vuelve al previo. |

## Referencias de detalle

- [V04 UI: IDs, estados y operaciones](v04-ui-operations-2026-10-21.md).
- [Registro de casos](registro-casos.md).
- [Salida SQL de solo lectura](reconciliation-final.log).
- [Historial de valoración y movimientos de V04](transaction-history-v04.log), consultado en transacción `READ ONLY`; muestra saldos anteriores, movimientos de transferencia y efectos de salida/devolución.
- Los IDs de movimiento, entrada de valoración, línea transferida y eventos de devolución están en ese log y en el informe V04. No se incluyen URLs firmadas, tokens QR ni credenciales.

## Dictamen

Los cuatro SKU protegidos concilian contra el baseline. Las operaciones V04-01/02/03 tienen documentos y efectos únicos compatibles con sus resultados. V04-04 continúa abierto: no se simuló la pérdida de respuesta postcommit; esta conciliación no acredita idempotencia UI de recuperación.

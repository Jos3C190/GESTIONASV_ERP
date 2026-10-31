# V04 — Operaciones parciales y recuperación

**Fecha:** 21/10/2026 · **UI:** clon `localhost:5174` · **API/DB:** `erp-final4p-api:8001` / `erp_db_ers_final4p_20261020`. No se escribió en la demo `erp_db`.

## V04-01 — Corrección compensatoria de ajuste: APROBADO

Desde navegador se creó y aplicó el ajuste original `AJ-20261020-000005` (`8aa214fb-38cb-436e-9149-5c3c613d3412`) para una disminución de 1 L de `PRD-JAR-012` (Jarabe de Vainilla 1L), con soporte ficticio inocuo `ERS-FINAL-4P-ajuste-soporte.txt`. Se creó la corrección `AJ-20261020-000006` (`cd275d03-7a17-41e1-92a6-1e82156798d0`) vinculada por `correction_of_id`, con motivo/documento y el mismo soporte, y se aprobó/aplicó.

La consulta posterior confirma ambos encabezados `applied`, la relación original→corrección y dos movimientos distintos: salida `0135aa3c-ee58-449b-bac5-61086c0d1eb5` y entrada `9026eb0f-4fac-4d2e-b550-0516cc82cf75`. El historial muestra 192 L/USD 2.00 antes del par, 191 L/USD 1.989583 después de la salida original y 192 L/USD 2.00 después de compensar. No se editó ni reemplazó el original. Véanse `reconciliation-final.log` y `transaction-history-v04.log`.

Un primer intento de corregir `AJ-000004` se detuvo con la validación «requiere una presentación física vigente para crear una unidad en cuarentena» porque la presentación fuente no estaba vigente; no se persistió esa corrección. Se repitió el caso con un producto que sí tenía presentación vigente y el recorrido terminó.

## V04-02 — Traslado parcial/final desde UI: APROBADO

Se trasladaron 10 cajas de `PRD-EMP-009` para `SCR-00009`, usando vehículo ficticio. Tras despacho se recibió primero 8 y luego 2. El documento `TR-20261021-60344005` (`60344005-6ce1-4b6b-b1b4-0c0e8e6817b6`) quedó `received`; detalle `3841cf1c-1b00-40f3-a7bf-7c5c46c8ff25`: planificadas/despachadas/recibidas 10, retornadas/ajustadas 0. La bodega destino recibió 8 y 2 en HUs separadas en cuarentena; se conservó el origen y el movimiento vehicular.

El historial de valoración registra 2,214 cajas, USD 0.50 y promedio USD 0.000226 antes del despacho; no hay entradas de valoración por las tres operaciones de traslado. La primera salida comercial posterior pasa a 2,210. El control `erp_db` conserva 2,214/USD 0.50. Esto acredita que el traslado fue neutral en el costo promedio global. Ver `transaction-history-v04.log` y `transfer-after.log`; la copia `erp_db` no se escribió.

## V04-03 — Devolución mixta desde UI con dos entregas: APROBADO

La venta ficticia `VTA-20261020-63B217FB` (`62d1a824-2bf8-472f-80cb-a7da8e2d315b`) de 8 cajas de `PRD-EMP-009` se entregó en dos documentos independientes de 4:

- `ENT-20261021-C8347B11` (`438ad3be-b360-4544-887c-39d6614df457`), HU `HU-0972C1B723AF4040`.
- `ENT-20261021-AA22CD2A` (`13c9b82c-fb09-4f5d-b9ec-e46b8eed06f5`), HU `HU-13D6DCFC8F8E4989`.

La devolución `DEV-20261021-530AF39F` (`18a88cae-7e44-4ad9-8acb-6e6686e141a3`) se vinculó a la primera asignación, sin inventar una devolución multi-entrega: 3 cajas recibidas documentalmente; 2 aptas aceptadas a cuarentena y 1 dañada rechazada. Estado final `mixed`, recibido 3, resuelto 3, pendiente 0. El evento aceptado creó un único movimiento y una entrada de valoración al costo de origen; el rechazo no creó movimiento ni valoración. La segunda entrega conserva su HU/asignación independiente. La valoración persistida de `PRD-EMP-009` quedó 2,208 cajas / USD 0.498646 / USD 0.000226 promedio; salida total de las dos entregas 8, devolución aceptada 2.

La UI se recargó y mostró el estado final. IDs de eventos, movimiento y valoración: `reconciliation-final.log`. No se reejecutó la operación al confirmar la persistencia.

## V04-04 — Pérdida de respuesta posterior al commit: ABIERTO

No se pudo ejecutar desde navegador. El mecanismo preparado requería detener/reiniciar el proceso Vite aislado para apuntarlo al proxy temporal; la herramienta bloqueó el intento antes de ejecutar el comando. No se inició el proxy y no se cambió la API/UI habitual. Una lectura posterior encontró el puerto 5174 escuchando y ningún listener en 8002. Las pruebas E2E idempotentes previas no sustituyen una pérdida real de respuesta UI.

Acción exacta pendiente: habilitar una sesión de navegador de prueba con interceptación documentada de respuesta o una autorización de entorno que permita reiniciar **solo** el Vite aislado; luego descartar la respuesta después del commit, consultar el documento antes de reintentar y comprobar una sola operación/efecto/auditoría para un ajuste y un flujo comercial. No reutilizar el servidor de demostración 5173/8000.

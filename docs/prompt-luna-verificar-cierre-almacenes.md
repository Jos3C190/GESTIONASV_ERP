# Luna: verificar y cerrar la corrección de almacenes

## Encargo y alcance

El usuario pide que Luna termine las pruebas para ahorrar tokens. Continúa desde los cambios existentes: verifica el flujo real de almacenes y corrige únicamente los fallos que encuentres. No rehagas el módulo. Lee las instrucciones del repositorio y conserva todos los cambios ajenos; hay numerosos archivos modificados. Las pruebas están autorizadas. No se requiere impresora ni lector físico: es una demostración.

Problema: el usuario solo veía códigos HU, sin identificar producto ni unidad, y percibía un bucle al dividir, revisar etiquetas y liberar repetidamente. El proceso normal termina en Disponible; dividir es opcional. No elimines unidades para simular finalización.

## Cambios ya implementados

- Backend en `backend/app/infrastructure/repositories/inventory_repository.py`: identidad de producto/SKU/unidad base y presentación en el listado de HUs, mediante consultas agrupadas y filtro por empresa; incluye unidades antiguas sin lote de recepción.
- Contrato en `backend/app/api/v1/schemas/inventory.py` y `frontend/src/lib/features/inventory/types.ts`.
- UI en `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte`: producto visible, SKU y código HU, unidad real, búsqueda por producto/SKU, mensaje de revisión terminada para disponibles; división dentro de Otras acciones, cantidad inicial vacía, validaciones y guardas contra doble envío. Cerrar formulario o Cancelar no debe dividir.
- Pruebas en `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.test.ts` y `backend/tests/integration/test_inventory_split_prepare_route.py`.

No asumas que todos los requisitos del prompt anterior están resueltos. `docs/prompt-luna-corregir-flujo-fraccionamiento-inventario.md` contiene además el problema de remanentes microscópicos y granularidad física. La política de granularidad NO quedó implementada en estos cambios. Diagnostica ese punto con las reglas reales de producto/unidad, sin redondear ni borrar existencias existentes silenciosamente.

## Evidencia ya obtenida el 17/10/2026

Docker está iniciado. Frontend en localhost:5173, backend en 8000. El arranque tardó y hubo errores transitorios de carga, pero finalmente abrió la pantalla real con sesión vigente.

Resultados terminados, no pendientes:

- `docker compose exec -T frontend pnpm exec vitest run src/lib/features/inventory/components/HandlingUnitsPanel.test.ts`: 32 aprobadas.
- `docker compose exec -T frontend pnpm exec svelte-check --tsconfig ./tsconfig.json`: 0 errores y 0 advertencias.
- `docker compose exec -T backend python -m pytest tests/integration/test_inventory_split_prepare_route.py -q`: 1 aprobada.

La prueba backend comprueba división, replay idempotente, conflictos/rollback, conservación y campos de identidad con aislamiento entre empresas. Antes de repetir pruebas, revisa `backend/tests/conftest.py`: deben usar la base aislada erp_db_test, nunca reconstruir la base de la demo. No repitas suites completas sin necesidad; enfócate en aceptación de navegador y regresiones de lo que cambies.

## Pantalla y línea base real

Abre o reutiliza:
`http://localhost:5173/warehouses/d31dce4f-6078-47fb-a3e5-55e043abb6b0#inventario`

Empresa Grupo Lorena, bodega de tienda Usulután. Última lectura del navegador mostró 5 HUs de Café Tostado y Molido 1kg, SKU PRD-CAF-011, unidad base Caja (cj), ubicación SEC-02:

| HU | Cantidad | Estado | Medidas |
|---|---:|---|---|
| HU-DC0E5941BC324574 | 2.2 | Cuarentena | Estimadas |
| HU-5B91A504489E4080 | 2.25 | Cuarentena | Verificadas; etiqueta pendiente |
| HU-EB8E841FE6534526 | 0.05 | Cuarentena | Estimadas |
| HU-8D63FE508BF14124 | 2.25 | Disponible | Verificadas |
| HU-8FEE57267CC84449 | 2.25 | Disponible | Verificadas |

Total: 9 cajas. Confirma la línea base actual, pues el usuario puede haber operado después. Ya se vio el nombre/SKU y Caja (cj) correctamente; las disponibles mostraban Revisión terminada · disponible para uso y Otras acciones contraído.

No se completó la secuencia final de abrir/cancelar/revisar/recargar en esta sesión. No la presentes como aprobada todavía. La existencia de varias ramas en capturas no demuestra por sí sola un bucle automático: las divisiones explícitas conservan el HU original con el remanente y crean un hijo.

## Pruebas pendientes, en orden

1. Registra IDs, cantidades, estados y total antes de operar.
2. En una HU disponible, abre Otras acciones y Dividir unidad. Verifica cantidad vacía y confirmación deshabilitada. Cierra formulario; repite con Cancelar, incluyendo introducir una cantidad válida y cancelar. No confirmes divisiones sobre las existencias del usuario para esta prueba.
3. Abre y cierra Ver QR/Revisar etiqueta sin ejecutar cambios. Recarga. Deben conservarse exactamente HUs, cantidades y estados. Identifica cualquier error de etiqueta de unidades antiguas sin lote y distingue ese caso de una HU inexistente.
4. Comprueba que buscar por nombre/SKU funciona y que el usuario entiende qué producto, unidad y presentación tiene. No inventes presentación para datos históricos que no la guardaron; distingue unidad base de empaque.
5. Para pruebas que sí cambian existencias, usa datos de prueba identificados y aislados: división explícita una vez, doble clic/reintento, conservación de cantidad y valor, revisión de las dos unidades afectadas y liberación final. Verifica que revisar/abrir/cerrar no ejecuta otra división y que Disponible es un final válido. No hace falta fraccionar otra vez.
6. Verifica el caso 2.25 dividido en 2.249999, sin mutar datos de demo. Determina si existe regla de incremento por unidad/producto. Si falta, deja claramente identificado el pendiente y una propuesta concreta; no inventes mínimos universales ni prohíbas todos los decimales. Corrige validaciones cuando la regla existente permita hacerlo con certeza.
7. Si falla algo, documenta causa y corrígelo preservando aislamiento por empresa, historial y cantidades. Prueba solo regresiones pertinentes y repite la aceptación afectada.

## Entrega

Guarda evidencia concisa en `docs/verificacion-cierre-almacenes-luna.md`: línea base y final, acciones probadas, resultados, errores y correcciones, y pendientes reales. Diferencia pruebas automatizadas de navegador y lo que no se ejecutó.

Responde brevemente al usuario con resultado y cómo terminar: verificar medidas, confirmar etiqueta vigente y liberar a Disponible; dividir solo si físicamente necesita separar contenido. No declares cierre total si la prueba real falla o queda una regla de cantidades sin resolver. No hagas commits, reinicialices la demo ni borres HUs históricas.

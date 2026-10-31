# Entrega ERS-B04 — Operación visible de traslados

**Fecha:** 19/10/2026  
**Base de partida:** ERS-B03 publicado; Alembic 0086.  
**Estado:** Implementado y verificado técnicamente. Revisión de código UI aprobada (8.5/10). La aceptación autenticada y visual integrada continúa pendiente para el cierre B08, según la decisión del usuario. B05 no se inició.

## 1. Alcance terminado

Se conectó **Inventario → Traslados** y el acceso desde **Almacenes** al mismo ciclo de documentos del API B03. El área de abastecimiento presenta producto, unidad base, existencias y solicitudes por sucursal; permite preparar envíos vinculados a una solicitud o envíos manuales con motivo de excedente. Se agregaron la lista y el detalle de preparaciones, catálogo de vehículos, confirmación explícita de despacho, captura de recepciones parciales e incidencias.

Guardar una preparación no reserva ni mueve existencias. El despacho explícito cambia la cantidad a tránsito. La recepción solo registra lo contado en una ubicación válida del destino y deja las unidades en cuarentena para revisión. La revisión/liberación posterior de la HU sigue en Almacenes. El ingreso desde Almacenes conserva contexto de origen, producto y HU y ya no usa un movimiento genérico para cruzar bodegas.

La pantalla muestra el avance de preparación, tránsito y recepción. En tarjetas responsivas distingue el importe **pendiente de asignar** del porcentaje ya asignado. Las acciones anuncian su procesamiento y respetan movimiento reducido.

## 2. Requisitos y decisiones

| Criterio | Resultado de esta entrega | Estado de aceptación |
| --- | --- | --- |
| B04-A1 Producto → sucursal → preparación → vehículo → despacho → recepción | Recorrido implementado sobre el documento B03, con nombre de producto, unidad, sucursal y vínculo de demanda. Componentes, tipos y compilación comprobados. | Pruebas de navegador autenticado aún pendientes para B08. |
| B04-A2 Pendiente de asignar, manual/excedente y cancelación | La demanda distingue asignado de pendiente; el formulario enlaza solo líneas seleccionadas y documenta excedentes. Guardar/cancelar preparación conserva la regla de no mover inventario. La integración cubre progreso de demanda y replay idempotente del documento. | Recorrido de operador y cantidades antes/después pendiente para B08. |
| B04-A3 Recepción parcial, cuarentena e incidencias | La interfaz exige captura explícita de cantidades y ubicación; muestra recepciones e incidencias del contrato. La integración focalizada cubre despacho, recepción parcial, idempotencia e inventario no resuelto por incidencia. | Confirmar visualmente 8/10 + 2/10 y revisión/liberación en B08. |
| B04-A4 Paneles, etiquetas, reintentos y contexto | La ruta de Almacenes abre el flujo documental y las operaciones usan claves idempotentes y refrescan el estado autoritativo. La integración cubre repetición de comandos; pruebas del panel de Almacenes pasan. | Navegación/QR sin mutaciones, doble clic y cambio de contexto requieren aceptación manual en B08. |
| B04-A5 Estados, filtros, totales y cantidades | UI separa carga, error, vacío y permiso; la demanda y las cantidades usan DTO del servidor, y la tabla amplia cambia a tarjetas en pantallas angostas. | Comprobar filtros, paginación y vista móvil en navegador durante B08. |
| B04-A6 Alcance de acceso, PUT y camino único | El cliente de edición usa `PUT /{transfer_id}`. Se mantienen permisos de lectura, movimiento y recepción. El backend rechaza cruces de bodega/tránsito mediante el movimiento genérico; la recepción exige ubicación activa apta para almacenamiento. | Contrato técnico y pruebas focalizadas aprobados; matriz de perfiles autenticados en navegador pendiente para B08. |
| B04-A7 Persistencia y aceptación | El flujo persiste como documentos B03 y la suite de integración de traslados aprobó 6/6. No se añadió migración. | Persistencia técnica comprobada; recorrido autenticado, recarga, teclado, temas y dispositivos queda pendiente para B08. |

No se añadieron rutas alternativas al API de B03. Se corrigió en la documentación B03 el método de edición de preparación de `PATCH` a `PUT`, que es el contrato implementado. No se cambió el esquema ni RBAC. La solución no requiere lector HS200 ni impresora física; esos equipos están fuera de la demostración ficticia.

## 3. Archivos y contratos afectados

- **Backend:** `backend/app/api/v1/routers/inventory.py` impide utilizar el movimiento genérico para traslados entre bodegas o entradas/salidas de tránsito sin documento B03. `backend/app/infrastructure/repositories/inventory_transfer_repository.py` valida que la ubicación de recepción esté activa, sea apta para almacenamiento y no sea virtual. `backend/tests/integration/test_inventory_transfer_repository.py` cubre el flujo y restricciones.
- **Frontend:** cliente tipado y lógica de cantidades/idempotencia en `frontend/src/lib/features/inventory/transfer-documents.ts` y `transfer-operations.ts`; coordinación en `components/TransferOperationsPage.svelte`; vista de demanda en `TransferDemandOverview.svelte`; lista, vehículos y progreso en `TransferDocumentList.svelte`, `TransferVehicleCatalog.svelte` y `TransferLifecycleProgress.svelte`. `HandlingUnitsPanel.svelte` abre el flujo documental conservando contexto. La página pública de la ruta de la aplicación está en `frontend/src/routes/(app)/transfers/+page.svelte`.
- **Documentación:** `docs/api.md`, corrección contractual en `docs/ers-v1/entrega-bloque-03.md`, este archivo, [manual de traslados](manual-traslados.md), [guía maestra](guia-maestra.md) y [matriz](matriz-y-seguimiento.md).

## 4. Actualización, datos y recuperación

No se creó migración ni se cambió la base demo. Las pruebas de integración se ejecutaron en la base aislada `erp_db_test`; el estado y los IDs de la demo no se modificaron. Por ello no hay procedimiento de rollback de esquema o datos para B04. Si se necesita revertir cambios de aplicación, hacerlo solo sobre los archivos propios de B04 y sin revertir modificaciones concurrentes de B01–B03 u otros módulos.

## 5. Comprobaciones y evidencia

La salida completa y fechada se conserva en [evidencia B04](../../tmp/ers-v1/bloque-04/evidencia-2026-10-19.md).

| Criterio técnico | Comprobación | Resultado |
| --- | --- | --- |
| Cliente de API y operaciones de cantidad/idempotencia | Vitest de `transfer-documents.test.ts` y `transfer-operations.test.ts` | 7/7 pruebas aprobadas. |
| Entrada contextual desde Almacenes | Vitest de `HandlingUnitsPanel.test.ts` | 32/32 pruebas aprobadas. |
| Integridad del documento, parcialidad, demanda, incidencia, puente legacy y rollback | `pytest tests/integration/test_inventory_transfer_repository.py -q` en Docker | 6/6 aprobadas en `erp_db_test`. |
| Backend tocado | Ruff sobre router, repositorio y prueba | Sin hallazgos. |
| Código frontend | ESLint de los componentes y ruta B04 | Sin hallazgos. |
| Tipos y compilación Svelte | `svelte-check` | 0 errores; 8 avisos `@apply` de la hoja de estilos de `TransferOperationsPage.svelte`. |
| Build de producción | Vite | Aprobado. Advierte un import `jsbarcode` sin uso en el diálogo de etiqueta existente y que `adapter-auto` no detecta destino de despliegue; no bloquean el build. |
| Revisión de UI por crítico de código | Rúbrica de 8 categorías, solo lectura | 8.5/10, aprobado. Es una crítica del código/UI y no sustituye la aceptación en navegador. |

## 6. Uso del flujo

El procedimiento operativo está detallado en [manual-traslados.md](manual-traslados.md): elegir producto y sucursal solicitante, guardar preparación, confirmar vehículo/despacho, capturar recepción parcial en destino, y revisar/liberar las HUs desde Almacenes. Ahí también se explica la diferencia entre pendiente de asignar y pendiente de recibir, y qué hacer con excedentes e incidencias.

## 7. Pendientes y siguiente paso

- Aceptación autenticada por los perfiles de origen/destino/global; recarga y cambio de empresa/sucursal con una acción abierta.
- Validación manual de cantidades parciales, estados, filtros/paginación, móvil, teclado, diálogos y temas claro/oscuro.
- Comprobar en el flujo integrado que consultar/reimprimir etiquetas y abrir/cerrar formularios no crea movimientos ni divisiones.
- Consolidar la revisión de B01–B08 al terminar B08. No iniciar B05 hasta que el usuario lo solicite.

No se declara aprobada la aceptación visual integrada. B04 queda implementado con pruebas técnicas focalizadas; esos pasos manuales quedan explícitamente pendientes para el cierre B08.

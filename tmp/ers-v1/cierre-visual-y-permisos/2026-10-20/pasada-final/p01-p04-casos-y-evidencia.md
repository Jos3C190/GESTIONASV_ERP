# Casos ejecutados P01–P04 — 20/10/2026

Este registro agrega únicamente comprobaciones ejecutadas durante la continuación final. Cada resultado se limita a las aserciones del caso indicado; no convierte una prueba focalizada en aprobación global del módulo ni del perfil.

## P01 — Adjunto de ajuste y autorización de costos

| Caso | Actor/contexto | Acción y resultado observado | Evidencia | Alcance/limitación |
|---|---|---|---|---|
| Detalle sin permiso de valoración | Lector con `inventory:read`, sin `inventory:valuation`, dentro de la sucursal del ajuste | HTTP 200; los costos documentados unitario y total llegan como `null` | `backend/tests/e2e/test_inventory_adjustment_permissions.py::test_adjustment_evidence_download_requires_valuation_permission`; [comando/log reproducible](p01-adjustment-document-permission-rerun.log) | Confirma redacción del costo en este detalle. |
| Descarga, carga, completar y retirar sin permiso de valoración/ajuste | Lector de la sucursal sin permisos; ruta exacta del ajuste | Descarga, iniciar carga, completar y retirar son rechazados HTTP 403; lector sin `inventory:read` tampoco obtiene descarga | Mismo caso y [comando/log](p01-adjustment-document-permission-rerun.log) | No cubre cada acción documental de todos los módulos. |
| Documento enlazado y permitido | Responsable con `inventory:read` + `inventory:valuation` y alcance de la sucursal propietaria | URL temporal emitida por el servicio simulado; un ID de documento no vinculado da 404 | Mismo caso y [comando/log](p01-adjustment-document-permission-rerun.log) | Se valida autorización y emisión; el stub no valida descarga real de bytes, almacenamiento, antivirus ni expiración. |
| Cambio de alcance | Usuario con permiso pero solo sucursal destino; usuario de otra empresa | Otra sucursal da 403; otra empresa da 404 | Mismo caso y [comando/log](p01-adjustment-document-permission-rerun.log) | Semántica de ocultación entre empresas conservada. |
| Retiro/revocación | Documento activo retirado; posteriormente se revoca el alcance de sucursal | El enlace queda con `detached_at`; nueva petición tras retiro da 404 y tras revocación da 403 | Mismo caso y [comando/log](p01-adjustment-document-permission-rerun.log) | Una URL firmada ya emitida es capacidad bearer temporal: retirar/revocar impide emitir otra, pero no invalida retroactivamente una URL ya entregada antes de su vencimiento. No se registró ni publicó la URL real. |

La matriz E13 general de todos los módulos y perfiles continúa abierta; las filas ejecutadas y las combinaciones no cubiertas se mantienen en [matriz de permisos](../matriz-permisos.md). Se corrigió la documentación normativa de descarga para que explicite `inventory:valuation`, el alcance y el vínculo activo.

## P03 — Identidad de lote en ficha de unidad logística

Se corrigió la ficha privada de unidad logística para separar el lote del fabricante (`lot_code`) del detalle canónico de recepción y su cabecera de compra. Los datos de servicio ya incluían `receipt_lot_code` y `receipt_lot_header_code`; la pantalla no los mostraba, lo que producía la impresión de que faltaba el lote.

| Registro consultado | Resultado visible | Comprobación |
|---|---|---|
| `HU-8D63FE508BF14124` | `Café Tostado y Molido 1kg` (`PRD-CAF-011`); recepción `COM-00017`; cabecera `LOT-COM-00017`; detalle canónico `LOT-COM-00017-DA9DBC0769F114438A8C0CF242E8344D8`; cantidad 2.25 cj; estado disponible en `SEC-02` | Apertura/lectura de la ficha autenticada tras reiniciar solo el frontend; la región accesible mostró producto, identidades diferenciadas, origen, cantidad, ubicación, estado e historial. La consulta no realizó mutaciones. |

La prueba unitaria `HandlingUnitLotIdentity.test.ts` cubre la separación/rotulado de ambos códigos; `services.test.ts` cubre la conservación de campos al mapear la respuesta. Los resultados de Vitest y los chequeos UI quedan en [Vitest enfocado](p03-p04-focused-vitest.log), [ESLint](p03-trace-lot-ui-eslint.log), [Svelte-check](p03-p04-svelte-check-final.log) y [build](p03-p04-focused-build.log).

No se pudo archivar un PNG a disco desde la sesión CUA disponible: permite observar estado/captura dentro de la sesión, pero no exportar una captura a la carpeta de evidencia. Por ello esta observación no cierra P02. Tampoco se demuestra una recepción visual con dos líneas del mismo SKU; el caso E2E de dos detalles distintos no es equivalente. El identificador del registro fue localizado en lectura de solo consulta; no se dividió, liberó ni trasladó durante esta comprobación.

## P04 — Reversión, traslado parcial/final y devoluciones

| Operación reproducida | Resultado | Evidencia | Límite |
|---|---|---|---|
| Corrección de ajuste ya aplicado | Conserva documento/movimiento original; crea borrador compensatorio vinculado; rollback/idempotencia según el contrato | `backend/tests/integration/test_inventory_adjustment_repository.py::test_ordinary_negative_adjustment_correction_preserves_origin_and_compensates_value`; [comando/log](p04-adjustment-transfer-focused-rerun.log) | Integración PostgreSQL; no se recorrió en UI en esta continuación. |
| Traslado: preparación, cancelación, despacho, recepción parcial/final | Preparar no mueve ni reserva; cancelar no genera movimiento; despacho de 10, recepción de 8 y cierre con 2 resuelven tránsito; replay idempotente; coste medio de empresa neutro; exceso/ubicación incorrecta rechazados | `backend/tests/integration/test_inventory_transfer_repository.py::test_transfer_preparation_dispatch_partial_receipt_and_idempotent_replay`; [comando/log](p04-adjustment-transfer-focused-rerun.log). La autorización del receptor también se probó en [E2E](p04-transfer-partial-final-api.log). | Integración/PostgreSQL y E2E de sucursal; la recepción física parcial desde interfaz no quedó demostrada por una captura archivada. |
| Venta asignada a varias HUs y devolución parcial | PostgreSQL recorre asignaciones, costo efectivo original, recepción documental/rechazo sin sumar stock, aceptación controlada, fallo inyectado de la segunda línea con rollback, reintento y replay idempotente | `backend/tests/e2e/test_sales_deliveries.py::test_sales_delivery_partial_cost_idempotency_concurrency_and_rollback`; [comando/log reproducible](p04-sales-delivery-returns-focused-rerun.log) | E2E/API; no es demostración de los selectores UI ni de pérdida real de respuesta HTTP en navegador. |
| Componentes UI involucrados | Se conservan regresiones de ajustes/navegación y formas de incidencia; 47 pruebas en seis archivos focalizados | [Vitest P03–P04](p03-p04-focused-vitest.log) y [Vitest recuperación](p04-recovery-vitest-final.log) | Pruebas de componente simuladas; no sustituyen operaciones persistidas en UI real. |

La recuperación real de la respuesta perdida desde navegador para ajuste y venta, más la devolución mixta operada mediante formularios, quedan abiertas. No se afirma que la prueba de replay API pruebe la pérdida de respuesta en UI. La siguiente acción es levantar una sesión de navegador autenticada contra una base aislada preparada con documentos/SKU nuevos, activar el stub de red solo para descartar la respuesta después de persistir el comando, consultar estado, reintentar con la misma clave y verificar tras recarga un único efecto; sin ese entorno no se toca `erp_db`.

## Validaciones focalizadas y preservación

- Frontend: seis archivos / 47 pruebas Vitest aprobadas; [log](p03-p04-focused-vitest.log).
- `svelte-check`: cero errores, ocho avisos `@apply` ya conocidos; [log](p03-p04-svelte-check-final.log).
- ESLint de los componentes de identidad P03: código 0; [log](p03-trace-lot-ui-eslint.log).
- Build de producción frontend: aprobado; avisos no bloqueantes `jsbarcode` / `adapter-auto`; [log](p03-p04-focused-build.log).
- Los cuatro SKU protegidos fueron consultados de nuevo sin escritura: [snapshot final](protected-skus-after-continuation.log). Físico/valor/valor USD permanecen 4/4/40, 5/5/60, 12/12/160 y 0/0/0, respectivamente.
- No se necesitó impresora ni lector físico. No se repitieron suites completas en esta continuación.

## Estado al cierre

P01 avanzó con una prueba E2E nueva de autorización documental de ajuste y actualización normativa, pero la matriz completa E13 sigue parcial. P03 corrigió y comprobó la identidad visual del lote para una HU real, pero faltan PNG archivado, recepción de SKU repetido en pantalla y UI para los tipos de alias aplicables. P04 añade evidencia de persistencia/rollback y movimientos parciales, pero falta cerrar recuperación de respuesta y la interfaz de devolución mixta. P02 sigue abierto por ausencia de PNG guardable mediante la capacidad disponible; véase la siguiente acción registrada arriba. El estado integrado no se declara completo.

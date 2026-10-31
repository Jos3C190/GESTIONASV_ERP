# Revisión de expectativas: valoración e integración de inventario

Fecha: 14/10/2026. Actualizado tras implementar el cierre del bloque 2 y ejecutar regresiones. No se modificaron datos operativos.

> **Seguimiento del bloque 3:** desde este corte se corrigieron en código los hallazgos R1–R3 de la revisión estática posterior del bloque 2 y se implementaron Kardex/conciliación. Las cifras de prueba incluidas más abajo pertenecen al corte histórico de esta revisión; las ejecuciones actuales están en [inventario-bloque-3-kardex-conciliacion.md](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-3-kardex-conciliacion.md). La aceptación PostgreSQL y el recorrido visual autenticado siguen pendientes.

## Dictamen

El bloque 2 quedó corregido en código y las regresiones relevantes pasan: 85 pruebas backend unitarias y 406 pruebas frontend. `svelte-check`, build, ESLint, Prettier y Ruff también pasaron. La revisión inicial halló cuatro incompatibilidades y una brecha; sus soluciones están anotadas abajo.

La aceptación operativa sigue pendiente. No se aplicaron migraciones ni se ejecutaron transacciones/concurrencia sobre PostgreSQL: no hay servidor local ni daemon Docker disponible, y WSL falló con `Wsl/Service/E_UNEXPECTED`. Tampoco se probó impresora o lector físico. No se afirma que el bloque esté habilitado para operación real.

## Comparación con las seis decisiones autorizadas

| Expectativa                                                                 | Evidencia en código                                                                                                                                                                                        | Evaluación                                                                                                                                   |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Promedio por empresa y producto, compartido entre almacenes                 | `InventoryCostAverageModel` usa empresa y artículo de inventario como clave; el historial se proyecta por esas claves. Los movimientos entre ubicaciones no agregan valor a la empresa.                    | Implementado en el núcleo. Falta validar aislamiento y concurrencia sobre PostgreSQL.                                                        |
| Cantidad y valor provisional al verificar recepción; retaceo posterior      | `purchase_inventory_gateway.py` incorpora cantidades aceptadas a cuarentena y distribuye el FOB aceptado entre unidades; `post_physical_line` registra el valor cuando la empresa tiene valoración activa. | Implementado para el flujo de compras. La recepción física y el valor deben probarse en la misma transacción.                                |
| Calcular como vista previa; verificar, aplicar una vez y cerrar             | `RetaceoUseCases.apply_retaceo` exige estado verificado. La aplicación usa claves idempotentes y un registro único por recepción; el cierre exige aplicación con valoración activa.                        | Implementado. El ajuste tardío recalcula efectos y conserva eventos originales; falta prueba integrada.                                      |
| Confirmar el viñeteado y representar unidades físicas con equivalencia base | Se agregó confirmación explícita, auditable e idempotente ligada a revisión, cantidad y registro de impresión vigentes; la etiqueta muestra presentación y equivalencia base. | Implementado en código y cubierto por pruebas unitarias/frontend; falta validarlo con una transacción PostgreSQL y colocación física. |
| Devoluciones, ajustes y correcciones trazables                              | El motor aplica promedio a salidas y devolución a proveedor; crédito y diferencia separados; devolución de cliente ligada a su salida.                                                                     | Núcleo implementado. Formularios operativos completos, reversión general y períodos contables siguen diferidos según el alcance documentado. |
| Corte inicial documentado y aprobado                                        | Se conserva una instantánea física, moneda, costos por artículo, referencias y actor; se rechaza aprobar un conteo desactualizado.                                                                         | Implementación inicial. Las referencias son texto: no equivalen a adjuntos documentales ni a un módulo avanzado de conteo/conciliación.      |

Referencias principales: [motor de promedio](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/inventory_valuation.py), [balances por empresa y artículo](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory_valuation.py:47), [apertura](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_valuation_repository.py:231), [movimientos físicos y valor](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_valuation_repository.py:335), [aplicación del retaceo](C:/Developer/GESTIONASV_ERP/backend/app/application/retaceos/use_cases.py:217).

## Hallazgos de la revisión inicial y estado del cierre

### H1 — Alta: las etiquetas exigen una aplicación que no existe para recepciones anteriores a la valoración

En [inventory_label_repository.py](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_label_repository.py:401), `_ensure_retaceo_final` rechaza `applied_at is None` antes de comprobar si la empresa tiene valoración activa. Un retaceo antiguo cerrado mediante el flujo admitido por el bloque 1 mantiene ese campo vacío. Ese caso queda bloqueado para etiquetas y también para emitir QR, porque la emisión reutiliza la vista previa de etiquetas.

La consulta incluye además retaceos cancelados: deben distinguirse de la versión vigente para no bloquear una recepción por un intento descartado. Hay que conservar la exigencia de aplicación para recepciones nuevas valoradas y tratar explícitamente las recepciones anteriores al corte. No se deben inventar aplicaciones históricas.

Aceptación: recepción antigua con retaceo final y valoración desactivada; recepción anterior al corte con empresa ya activada; recepción nueva valorada sin aplicación; nueva aplicada; intento cancelado más retaceo vigente. Cada caso debe tener resultado definido y probado.

**Estado del cierre:** corregido en el repositorio de etiquetas. Se distingue recepción anterior al corte de recepción que requiere aplicación; se ignoran intentos cancelados al encontrar el retaceo vigente. Hay regresiones unitarias para estos escenarios. Aún no se validó la consulta en PostgreSQL.

### H2 — Alta: la ubicación agrupada compara el total del producto contra un solo detalle

[inventory_lots.py](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_lots.py:132) agrupa varios detalles de recepción por artículo. Sin embargo, [inventory_putaway_groups.py](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_putaway_groups.py:208) carga un único detalle mediante `scalar` y, en la [validación de cantidad](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_putaway_groups.py:399), compara todas las unidades activas del producto con la cantidad de ese detalle.

Las órdenes desde adjudicaciones pueden contener varias líneas del mismo producto; los detalles de lote son únicos por línea de compra, no por producto. Por ejemplo, dos líneas aceptadas de 20 y 30 unidades pueden mostrar 50 pendientes, pero la confirmación compara 50 con 20 o con 30 y rechaza un grupo válido.

Aceptación: sumar todos los detalles pertinentes de empresa, lote y artículo, conservar el origen por línea y comprobar que 20 + 30 permite distribuir 50, mientras exceder la cantidad aceptada sigue rechazado.

**Estado del cierre:** el grupo agrega cantidades por detalle aceptado, mantiene `inventory_lot_detail_id` en cada unidad y rechaza cantidades por encima del total. Pasan las pruebas de agregación y exceso; la transacción completa requiere PostgreSQL.

### H3 — Alta: existe una inversión en el orden de bloqueos

[La ubicación agrupada](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_putaway_groups.py:242) bloquea unidades de manejo antes de llamar a `post_movement`. El [movimiento ordinario](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_repository.py:2439) obtiene primero el bloqueo de valoración de empresa, después los ámbitos físicos y después la unidad.

Una transacción de grupo puede tener la unidad y esperar a la empresa, mientras otro movimiento tiene la empresa y espera a esa unidad. También debe revisarse el orden frente a la verificación de medidas, que bloquea el ámbito físico antes que la unidad. Es un riesgo deducido de los caminos de bloqueo; no se reprodujo un bloqueo mutuo en PostgreSQL durante esta revisión.

Aceptación: unificar el orden de adquisición de bloqueos en los caminos afectados y probar dos transacciones concurrentes con sincronización controlada, verificando conservación de cantidades y rollback. Agregar reintentos sin corregir el orden no resuelve la causa.

**Estado del cierre:** los tres caminos ahora solicitan primero el bloqueo de valoración de empresa, luego los ámbitos físicos y finalmente las unidades. La prueba concurrente solicitada no se pudo ejecutar sin PostgreSQL; H3 no se considera aceptado hasta correrla.

### H4 — Media: etiquetas y emisión de QR exigen acceso a todas las sucursales

Los auxiliares `_company` de [inventory_labels.py](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_labels.py:31) e [inventory_trace.py](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_trace.py:39) llaman a `require_company_wide_scope`. Un operador con permiso de recepción y acceso solo a su sucursal puede consultar su lote mediante el alcance por bodega, pero no imprimir etiquetas de sus unidades.

Aceptación: autorizar estas operaciones según la bodega de la unidad o detalle elegido y los permisos correspondientes; rechazar otra sucursal o empresa. La consulta y aprobación de valoración global deben conservar el alcance de toda la empresa.

**Estado del cierre:** las rutas obtienen el alcance desde la relación persistida unidad→bodega→sucursal (o detalle→compra→bodega) y conservan la valoración global por empresa. La validación efectiva con usuarios de dos sucursales/empresas queda pendiente en base de integración.

### H5 — Brecha de requisito: impresión preparada no equivale a etiqueta colocada

[HandlingUnitLabelDialog.svelte](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte:307) registra la impresión antes de llamar a `window.print()`. Cancelar el diálogo de impresión deja el registro existente. El navegador no aporta una confirmación fiable de impresión física ni de colocación.

Además, [confirm_putaway_group](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory_putaway_groups.py:459) puede pasar una unidad medida a disponible sin comprobar viñeteado confirmado. Falta la confirmación explícita autorizada en la política, con actor, fecha, unidad y etiqueta vigente, comprobada también desde los otros caminos de liberación.

Aceptación: distinguir preparación/impresión de confirmación de viñeteado; impedir liberación de las recepciones sujetas al nuevo flujo hasta confirmar. Reimpresiones y copias no crean existencias ni unidades nuevas. La etiqueta debe explicar qué unidad física representa y su equivalencia base cuando corresponda. No marcar históricos como confirmados de manera automática.

**Estado del cierre:** se agregó `POST /inventory/labels/confirmations`, con registro idempotente/auditado ligado a la revisión, cantidad, código y última impresión de la unidad. La liberación individual y agrupada queda bloqueada sin esa confirmación para lotes nuevos. Un fraccionamiento cambia la revisión de la unidad original y la unidad hija requiere confirmación propia. Los lotes históricos no se autoconfirman.

## Evidencia y límites de la revisión

- Backend con Python 3.12.15: 85 pruebas unitarias aprobadas en 11 módulos relacionados con inventario, lotes, etiquetas/QR, compras y retaceo.
- Frontend: 406 pruebas aprobadas en 94 archivos; `svelte-check` informó cero errores y advertencias; build de producción correcto; ESLint y Prettier pasaron.
- Ruff pasó en los archivos backend modificados. Las pruebas y el análisis estático no sustituyen transacciones reales.
- Alembic reportó `0083` como cabeza. No se obtuvo `current`, ni se aplicó migración; la generación offline no finalizó al fallar WSL. Docker no tenía daemon y no hay PostgreSQL local instalado.
- Concurrencia, rollback, permisos efectivos de sucursal/empresa y flujo físico de impresora/escáner requieren entorno PostgreSQL de prueba y hardware.
- Para activar solo la valoración, usar la revisión `0079` en una base desechable verificada. Para probar el bloque completo, aplicar `head` (`0083`) en la base dedicada `erp_db_test`; nunca en la base operativa.

El alcance de los bloques 1 y 2 no incluye libro mayor, períodos contables, conversión monetaria ni toda la experiencia de devoluciones; esas tareas conservan su lugar en la hoja de ruta.

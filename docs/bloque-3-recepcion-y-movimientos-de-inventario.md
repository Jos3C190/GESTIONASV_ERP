# Bloque 3: recepción verificada e inventario

## Objetivo

Registrar en el inventario únicamente las cantidades aceptadas durante la verificación física de una recepción. La recepción, el movimiento de inventario, el estado de la orden y la bitácora se confirman juntos: si falla una validación o una escritura, no queda una entrada parcial.

## Flujo implementado

1. **Registrar lo contado.** La recepción conserva `quantity_received` por línea. Confirmar que llegó mercancía todavía no aumenta existencias.
2. **Verificar cada línea.** La persona autorizada informa `quantity_accepted`, entre cero y lo contado. La diferencia queda como cantidad rechazada.
3. **Asignar destino.** Cada línea con cantidad aceptada requiere una ubicación activa del mismo almacén de la orden y de la empresa. Las líneas aceptadas en cero no requieren ubicación.
4. **Validar y convertir la unidad.** El producto debe tener una identidad inventariable activa. Si la unidad recibida coincide con la unidad base, se conserva la cantidad tal cual. Si difiere, se requiere una presentación vigente que enlace la unidad recibida con la unidad base y defina la cantidad exacta. La equivalencia se valida en backend, debe ser única y el resultado debe caber en seis decimales; el sistema no infiere conversiones por el nombre del producto o del empaque.
5. **Registrar una entrada en cuarentena.** Una sola operación `receipt` registra las cantidades aceptadas ya expresadas en unidad base y conserva la presentación usada en la unidad logística. Se usa una clave idempotente y una referencia estable basadas en el UUID de la recepción (`purchase-receipt:<purchase UUID>`). La compra conserva el UUID del movimiento resultante.
6. **Terminar la verificación.** Compra, cantidades aceptadas, movimiento, estado recalculado de la orden y auditoría se guardan en la misma transacción. Si todas las líneas se rechazan, la recepción se verifica sin crear un movimiento y las cantidades vuelven a quedar pendientes en la orden.
7. **Costear lo aceptado.** El retaceo solo se habilita para recepciones verificadas o cerradas. Distribuye FOB sobre la cantidad aceptada y no incluye las líneas con aceptación cero.

Las cantidades aceptadas se reciben inicialmente en **cuarentena**, por lo que no cuentan como disponibilidad normal. El registro de medidas físicas existente permite verificar manualmente la unidad logística. Después, una persona con `inventory:move` debe ejecutar explícitamente **Liberar a disponible**; el sistema no libera mercancía de forma automática. La acción conserva la misma unidad logística, cantidad base y lote. Usa la ubicación actual si es apta para almacenamiento normal; si no, permite elegir otra ubicación activa y apta del mismo almacén. Registra un movimiento `putaway` idempotente con una clave reutilizable en los reintentos y la referencia `quarantine-release:<UUID de unidad logística>`. Si las medidas siguen incompletas o el lote está vencido, el backend rechaza la liberación. El permiso de consulta del panel sigue siendo `inventory:read`.

## Protección contra duplicados y datos cruzados

- La clave idempotente es única por recepción y el movimiento también queda referenciado desde `purchases.inventory_movement_id`.
- Movimiento, aceptación y estado de compra se guardan atómicamente. Un reintento no suma existencias por segunda vez.
- El servidor vuelve a validar la empresa, el almacén y la ubicación; el UUID enviado por el navegador no se considera suficiente.
- Toda cantidad se registra en unidad base. Una conversión explícita debe tener una sola equivalencia vigente por producto y unidad recibida. La FK limita la unidad a las habilitadas en la empresa; un índice único evita conversiones ambiguas.
- Cada detalle se verifica una sola vez y la solicitud debe incluir exactamente todas las líneas de esa recepción.
- Lo contado que se rechaza deja de reservar cantidad en la orden; se puede recibir posteriormente la cantidad faltante.

## Correcciones y reversiones

- Los movimientos publicados son inmutables: no se editan ni se eliminan para corregir un error. La tabla ya reserva `reversal_of_id`, pero todavía no existe una operación de reversa; el endpoint genérico rechaza el tipo `reversal` intencionalmente.
- No se debe corregir una recepción modificando directamente el saldo, la unidad logística o la fila histórica. Eso rompería la trazabilidad entre recepción, cuarentena, liberación, orden y análisis posterior.
- Antes de habilitar reversiones debe acordarse cómo se corrigen también la cantidad aceptada de la compra y, cuando aplique, su retaceo. Revertir solo el movimiento de inventario dejaría esos documentos con cantidades distintas.
- Propuesta segura para una primera versión: agregar un comando de compensación auditado, con motivo obligatorio, usuario, fecha, clave idempotente propia y `reversal_of_id`; conservar tanto el movimiento original como la compensación. Para revertir una recepción, permitirlo únicamente si las unidades logísticas afectadas siguen en cuarentena, en su ubicación original, sin movimientos posteriores y sin estar cerradas. Si ya se liberaron o trasladaron, exigir deshacer esos movimientos posteriores en orden inverso antes de compensar la recepción. No admitir reversas parciales de una unidad logística en esa primera versión.
- La compensación y los cambios relacionados en compra, inventario y auditoría deben persistirse juntos en una transacción. Hasta que ese flujo exista, una recepción incorrecta se escala para corrección autorizada; no se vuelve a enviar un movimiento con otra clave para intentar neutralizarla.
- Esta propuesta define una salvaguarda técnica, pero la política operativa —quién autoriza, qué documentos se reabren y cómo se conserva el costeo— sigue pendiente de confirmación antes de programar el comando.

## Conservación del historial para análisis

- Cada recepción aceptada y cada liberación/traslado se conserva como encabezado en `inventory_movements` y como una o más líneas en `inventory_movement_lines`. El cambio de cuarentena a disponible no reemplaza ni borra el evento de recepción: queda un segundo evento relacionado con la misma unidad logística.
- El registro conserva empresa, usuario, fecha, tipo, referencia, producto y variante, cantidad en unidad base, unidad logística, origen/destino, estados de existencia, lote, vencimiento, mediciones y fotografía de la presentación aplicada. Las medidas verificadas también dejan auditoría asociada a la unidad.
- La tarjeta **Operaciones → Historial de movimientos** y `GET /inventory/warehouses/{warehouse_id}/movements` muestran hasta 100 líneas recientes por consulta. Ese límite solo afecta la vista; no elimina ni limita los datos persistidos. El endpoint requiere `inventory:read` y respeta la empresa y el alcance de sucursal del usuario. Cada fila presenta la referencia comercial disponible y el botón **Ver detalles** abre el recorrido, cantidades, lote, mediciones y datos técnicos de trazabilidad; los UUID quedan fuera del resumen para facilitar la lectura.
- Los saldos actuales sirven para conocer existencias; el libro de movimientos es la fuente histórica para analizar entradas, salidas, traslados y cambios de estado. No reconstruir el historial a partir del saldo actual ni generar eventos retroactivos para registros anteriores sin evidencia.

## Permisos para verificar

El usuario que verifica una recepción necesita estos tres permisos:

- `purchases:verify`
- `inventory:receive`
- `locations.view`

Los permisos de registrar la recepción siguen siendo los existentes en Compras. Ver unidades requiere `inventory:read`; verificar sus medidas requiere `inventory:receive`; liberarlas manualmente requiere `inventory:move`.

## Datos anteriores y migración

La revisión `0057` agrega la cantidad aceptada, el UUID de ubicación y la referencia al movimiento. Los registros históricos quedan con cantidad aceptada y ubicación nulas: la migración **no inventa aceptación, ubicación ni movimientos retroactivos**. El fallback de retaceo conserva las cantidades históricas cuando un registro verificado antiguo no tiene aceptación registrada.

Con Docker Compose, aplicar la migración con:

```powershell
docker compose run --rm migrate
```

Después, el servicio `backend` debe estar iniciado o reiniciarse para usar el código actualizado. En desarrollo el frontend se actualiza con su recarga normal.

## Preparación necesaria antes de probar

- El producto debe tener una identidad activa en Inventario, con una unidad base apropiada (por ejemplo, `Unidad`).
- Si la orden usa otra unidad (por ejemplo, `Caja`), registre en el producto una presentación vigente con su unidad de compra y la cantidad exacta en unidad base (por ejemplo, `1 Caja = 20 Unidad`, únicamente cuando ese empaque realmente contenga 20 unidades).
- La orden debe apuntar a un almacén operativo con al menos una ubicación activa.
- El usuario debe tener los tres permisos de verificación.

Si falta uno de esos datos, la verificación falla completa y muestra la causa; no registra una parte de la entrada.

## Recorrido manual de aceptación

La verificación visual local se completó el 3 de octubre de 2026 con sesión autenticada de `superadmin`, empresa Grupo Lorena y la Bodega de tienda El Tránsito. En **Operaciones**, el historial cargó cuatro movimientos (dos recepciones y dos liberaciones/acomodos) sin reproducir el error anterior. **Ver detalles** abrió el movimiento de liberación y mostró su compra/orden de origen (`COM-00011` / `OC-00009`), recorrido de cuarentena en `REC-01` a disponible en `SEC-02`, cantidad, unidad logística y medidas. Esto confirma la consulta y el detalle para esta cuenta y almacén; no valida todavía otros ámbitos de sucursal ni permisos.

1. Crear una orden de compra y registrar una recepción con una línea.
2. Confirmar la recepción y verificar que aún no se haya creado movimiento.
3. Abrir la verificación, aceptar una cantidad menor o igual a lo contado y elegir ubicación.
4. Confirmar que el detalle muestre contado, aceptado y rechazado, y que el inventario muestre una sola entrada en cuarentena con la referencia de esa recepción.
5. Si hace falta, verificar las medidas; seleccionar un destino apto y ejecutar **Liberar a disponible**. Confirmar que conserva cantidad y lote, cambia el estado, y registra un solo movimiento de bodega.
6. Reintentar la liberación con la misma clave: debe permanecer un solo movimiento y no duplicarse la existencia.
7. Verificar otra recepción rechazando toda la cantidad: no debe crear movimiento y la cantidad debe seguir pendiente en la orden.
8. Intentar una unidad sin equivalencia o una ubicación de otro almacén: la operación debe rechazarse sin cambiar compra ni inventario.

## Resultado de la comprobación de los tres casos pendientes

El 3 de octubre de 2026 se comprobaron los puntos 6–8 con **41 pruebas unitarias, 2 pruebas E2E de la API y 1 prueba de integración con PostgreSQL; todas aprobadas**. Las pruebas con base de datos usan exclusivamente `erp_db_test`.

- **Reintento de liberación:** la prueba PostgreSQL registra recepción y liberación, repite la liberación desde una instancia nueva del repositorio y confirma que devuelve el mismo UUID, queda un solo movimiento y el saldo es 1 disponible / 0 en cuarentena. Los datos sintéticos se revierten al terminar porque el libro real es inmutable.
- **Rechazo total:** la prueba E2E verifica por la API que una recepción con cantidad aceptada cero produce `inventory_movement_id = null`, deja la orden enviada, conserva pendiente la cantidad completa y no registra un movimiento.
- **Ubicación o conversión inválida:** la prueba E2E intenta verificar una recepción en otra bodega y confirma el rechazo, la compra aún recibida, la orden sin cambios y ningún movimiento. La prueba unitaria complementaria confirma que una unidad sin equivalencia vigente también se detiene antes de publicar movimiento o escribir filas.

La prueba de liberación valida el recorrido en PostgreSQL dentro de una transacción que se revierte; no prueba dos solicitudes concurrentes. La inspección visual local del historial fue de solo lectura; no se agregaron ni alteraron movimientos de inventario de desarrollo.

La migración `0059` agrega la unidad de compra asociada a una presentación como campo nullable; las presentaciones antiguas conservan su historial y no se les asigna una equivalencia inventada. La liberación manual no requiere una migración adicional.

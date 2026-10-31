# Revisión de MiniERP ERS v1.0 frente a GestionaSV

Fecha: 17/10/2026.

## Alcance y conclusión

Se comparó el texto de las 103 páginas de la versión 0.9 con las páginas correspondientes de la versión 1.0, se leyó completa la nueva sección 6.9 de Inventario y se revisaron visualmente sus páginas principales y las tres capturas entregadas. También se contrastaron los requisitos con el código actual del repositorio.

La implementación de recepciones, etiquetas, almacenamiento, valoración y Kardex aporta una base reutilizable. El cumplimiento completo de la ERS 1.0 sigue pendiente: hay diferencias concretas en la pertenencia de la bodega madre, la identidad y consulta de lotes, el traslado con vehículo y la integración comercial de ventas y devoluciones. Los ajustes tienen soporte en el motor, pero falta cerrar su experiencia operativa y documental.

Esta revisión es documental y estática. No se ejecutaron nuevas pruebas, no se confirmó ninguna operación de inventario ni se modificó el código del sistema. Las pruebas de entregas anteriores no equivalen a una aceptación de los nuevos criterios.

## 1. Fuentes y cambios efectivos

- [ERS 1.0, 115 páginas](<C:/Users/rodri/Downloads/MiniERP ERS v1.0.pdf>).
- [ERS 0.9 comparada, 103 páginas](<C:/Users/rodri/Downloads/MiniERP ERS v0.9 (2).pdf>).
- [Captura del esquema ER](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-b971fae2-5872-4307-9fb6-a694cfdeadff.png).
- [Infografía del flujo](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-c042eca7-e843-485c-96e2-820152847e8a.png).
- [Competencias y resultados de la sesión](C:/Users/rodri/AppData/Local/Temp/codex-clipboard-acb2947e-98d2-4746-9267-b7b04c7d8c30.png).

La comparación textual encontró cambios en las páginas 1, 8 y 9 de la parte compartida. Las páginas 10 a 103 conservan el contenido de la versión 0.9, incluida la sección de Compras. La página 104 es una separación sin contenido sustantivo y las páginas 105 a 115 incorporan Inventario.

Los cambios generales son:

1. **RN-009:** el ingreso procede de una recepción confirmada y de movimientos que validan recepción y costo aplicable.
2. **RN-016:** el historial confirmado es inmutable; las correcciones se hacen mediante reversión o ajuste autorizado.
3. **RN-018 y RN-019:** la salida corresponde a la venta confirmada y entregada desde la ubicación de la sucursal que entrega. Una cotización o carrito no descuenta existencia física.
4. **Sección 6.9:** especifica lotes, saldos por ubicación, movimientos, promedio por empresa y producto, etiquetas, traslados, integraciones, permisos y aceptación.

La portada todavía dice «Versión 0.6», mientras el control de versiones registra 1.0. Es una inconsistencia editorial; el contenido nuevo de Inventario sí está presente.

## 2. Qué aportan las capturas

La infografía presenta el ciclo **recepción → lote → etiquetado → ubicación → traslado → venta y entrega**, con devoluciones y ajustes que generan movimientos nuevos. El cuadro de la sesión pone el énfasis docente en viñeteado, trazabilidad, promedio ponderado y Kardex. La ERS añade criterios expresos de venta y devolución; no se puede deducir de la captura de la clase que esos criterios hayan quedado excluidos de la evaluación.

El esquema ER muestra `inventory_transfers` e `inventory_transfer_details`, con origen, destino, ubicación del vehículo, fechas de despacho/recepción, estado y cantidades despachadas/recibidas. Es información adicional útil, porque el PDF describe ese flujo sin desarrollar las tablas de traslado con el mismo detalle que las de inventario.

La captura ER es parcial: no permite concluir que falten tablas fuera del área visible. El PDF sí describe `inventory_location_details`.

## 3. Matriz frente al código actual

«Implementado» en esta tabla significa evidencia en código; no representa una nueva certificación de funcionamiento en navegador o base de datos.

| Requisito | Situación observada | Resultado |
| --- | --- | --- |
| Recepción real vinculada al detalle recibido | El adaptador de compras genera lote, detalles, HUs y movimiento desde la recepción verificada; conserva `purchase_detail_id`. | Implementado; conservar. |
| Promedio por empresa y producto, compartido entre almacenes | `inventory_cost_averages` se identifica por empresa e identidad inventariable, sin almacén. Para productos base existe unicidad empresa/producto. | Alineado para productos base. |
| Traslados sin aumentar cantidad ni valor global | El motor de valoración omite una nueva entrada/salida valorada cuando el movimiento tiene ubicación origen y destino. | Base implementada. |
| Etiqueta con código interno, lote y fecha; historial de reimpresión | Hay generación de código de barras, datos de recepción, historial y confirmación de etiqueta. | Implementado; revisar coherencia de identidad de lote. |
| Movimientos históricos inmutables y Kardex derivado | Existen tablas de movimientos y líneas, consultas de Kardex y restricciones PostgreSQL contra UPDATE/DELETE del historial. | Implementado. |
| Actualización conjunta de cantidades y valor | El registro físico invoca valoración dentro de la misma sesión; hay bloqueo y límites transaccionales. | Base implementada; exigir regresiones en las nuevas integraciones. |
| Bodega central perteneciente a sucursal matriz | El modelo actual exige `branch_id = NULL` cuando `is_central = true`. | Diferencia explícita con páginas 105 y 115. |
| Un lote por producto y recepción | Actualmente existe una cabecera por recepción y detalles por producto/línea recibida. | Trazabilidad presente, estructura e identificación distintas. |
| Saldo y consulta por lote de recepción y ubicación | HUs conservan lote y detalle; el saldo agregado y el filtro del Kardex usan otro campo `lot_code`. | Equivalencia incompleta; homologar las consultas. |
| Traslado con vehículo y estados de preparación, tránsito, recibido e incidencia | Existen despacho, tránsito y recepción mediante movimientos; no aparece una entidad de traslado con ese ciclo ni ubicación vinculada a vehículo. | Parcial. |
| Venta entregada descuenta la sucursal correcta | Ventas y cotizaciones de venta siguen enlazadas a páginas provisionales; no hay módulo comercial en la agregación de rutas API. | Pendiente de integración operativa. |
| Devolución aceptada con referencia a venta y salida originales | El motor de costos contempla devoluciones y costo de la salida original; el módulo comercial de devoluciones sigue provisional. | Motor disponible; flujo comercial pendiente. |
| Ajuste autorizado con motivo, origen e historial | Existen tipos de movimiento y valoración de ajustes, pero no se encontró una pantalla completa para capturarlos y autorizarlos. | Parcial. |

## 4. Diferencias que requieren trabajo

### A. Pertenencia de la bodega madre

La ERS dice que el almacén de distribución pertenece a la sucursal principal mediante la relación existente `warehouses.id_branch`. El modelo de GestionaSV contiene la restricción contraria: una bodega central debe estar sin sucursal.

Evidencia: [Warehouse y restricciones](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/organization.py:231), especialmente `ck_warehouses_central_must_be_unassigned`.

Recomendación: conservar los IDs de bodegas, ubicaciones, HUs e historial; asociar la bodega central a la sucursal matriz correcta y ajustar validaciones, filtros y alcance de permisos. La migración debe incluir un mapeo explícito por empresa. No basta cambiar el texto «Casa matriz» en la interfaz.

### B. Traslados con documento y vehículo

Hoy el traslado llama al endpoint genérico de movimientos. Mueve la HU desde origen a una ubicación de destino con estado `in_transit`; la recepción cambia esa existencia a cuarentena. Esto impide considerarla disponible, pero la ubica en destino antes de recibirla físicamente.

Evidencia: [servicios de traslado](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/services.ts:493), [tipos de ubicación](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/location.py:26). Entre los tipos permitidos no existe `vehicle`. Flota y conductores también aparece como módulo provisional.

La página 115 exige una ubicación de tipo vehículo vinculada al vehículo asignado y los estados EN PREPARACIÓN, EN TRÁNSITO, RECIBIDO e INCIDENCIA. La formulación más general de la página 112 admite estado o ubicación de tránsito; para cumplir toda la sección se debe contemplar la precisión de la página 115.

Recomendación: introducir documento de traslado y detalles enlazados al motor existente. Al despachar, trasladar a la ubicación del vehículo; al recibir, trasladar desde vehículo a recepción/cuarentena de destino. El faltante queda en tránsito o en una incidencia documentada, sin hacerlo desaparecer. Definir con consistencia la pertenencia de esa ubicación móvil al modelo organizacional.

Conservar selección por solicitudes, cantidades pendientes, envíos adicionales justificados, recepción parcial y elección manual. Una nueva pantalla no debe eliminar esas capacidades.

### C. Identidad y consulta del lote

La ERS pide que cada lote identifique un producto y el detalle real de recepción. GestionaSV tiene una cabecera `inventory_lots` por compra/recepción y `inventory_lot_details` por línea/producto. Los enlaces de origen existen, pero varios productos pueden compartir el código visible de la cabecera.

Evidencia: [cabecera y detalles de lote](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory_lot.py:27).

Además, el filtro por lote del Kardex compara `InventoryMovementLineModel.lot_code`, mientras la etiqueta muestra `receipt_lot_code` de la cabecera. El filtro no enlaza ese campo con `InventoryLotModel.code`. Una consulta con un código visible como `LOT-COM-00017` no tiene garantizado encontrar sus movimientos si ese código no coincide con `lot_code`.

Evidencia: [filtro del Kardex](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_kardex_read_repository.py:239), [lote de la etiqueta](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_label_repository.py:155), [saldos agregados](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory.py:528).

Recomendación: dar una identidad consultable inequívoca a producto + recepción y usarla en etiqueta, Kardex, saldo por ubicación y traslado. Puede conservarse la cabecera actual y explicitar sus detalles como lotes por producto, con una proyección compatible con la ERS. La equivalencia debe demostrarse; renombrar tablas por sí solo no la resuelve. Conservar los códigos históricos y distinguir lote del fabricante de lote interno de recepción.

### D. Ventas, devoluciones y ajustes

Evidencia: [navegación y módulos provisionales](C:/Developer/GESTIONASV_ERP/frontend/src/lib/navigation.ts), [rutas disponibles](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/router.py), [motor de valoración](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/inventory_valuation.py).

La salida genérica y la devolución valorada no constituyen por sí solas un proceso comercial completo. Para la aceptación de las páginas 112 a 114 faltan:

- Venta y entrega enlazadas a sucursal, ubicación, producto y cantidad disponible, con documento y salida registrados en la misma transacción.
- Cotización y venta sin entrega sin reducción de stock físico.
- Devolución vinculada a venta/salida; entrada solo de la cantidad recibida y aceptada.
- Corrección posterior mediante movimiento compensatorio; historial original conservado.
- Captura y autorización operativa de ajustes con motivo y documento de soporte. El contrato genérico de movimientos permite `source_reference` opcional, por lo que las nuevas operaciones deben exigir y validar su origen.

## 5. Criterios que conviene alinear antes de implementar

**Costo provisional y retaceo.** La política autorizada anteriormente registra la recepción en cuarentena con costo provisional y aplica después el retaceo, antes de liberar cuando corresponde. El código confirma ese comportamiento en [el ingreso de compras](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/purchase_inventory_gateway.py:260) y [la valoración física](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_valuation_repository.py:335). La ERS describe la entrada con costo final aplicable y un flujo que finaliza el retaceo antes del ingreso. Esa extensión debe explicarse y evaluarse expresamente; no se puede declarar equivalencia literal sin resolver el momento de reconocimiento que se espera demostrar. Esta revisión no cambia la política autorizada.

**Activación del promedio.** El sistema admite una etapa previa al corte de apertura. La demostración de la ERS debe hacerse con la valoración activada, pues la página 114 exige consistencia entre movimientos, saldos y valoración.

**Producto y variante.** El promedio actual puede separarse por identidad de variante. Para artículos simples coincide con empresa/producto. Si la evaluación incluye variantes, documentar si cada variante es un artículo inventariable distinto y cómo se presenta su valoración.

**Código de barras.** El flujo habitual usa código interno. Existe respaldo al SKU si falta el código interno y se utiliza SKU para variantes. Para demostrar literalmente RN-INV-016, usar productos con `internal_code` válido y revisar esa regla al incluir variantes.

**Fraccionamiento.** La nueva infografía no exige dividir una unidad repetidamente. Dividir continúa siendo una operación opcional cuando realmente se separa contenido. Disponible continúa siendo el cierre de la preparación de esa HU. No equivale a que el producto ya haya pasado por venta y devolución.

**Esquemas.** Los UUID, las líneas de movimiento y las HUs pueden conservarse. Cada adaptación debe acreditar identidad del lote, integridad, saldos y transacciones. Se recomienda documentar el mapeo con el esquema docente; la documentación recibida no prueba que cualquier estructura alternativa sea aceptada automáticamente.

**Hardware.** El usuario excluyó previamente lector e impresión física de su demostración. Se conserva ese alcance de trabajo. La generación de etiquetas y su historial sí forman parte de la especificación; no se atribuye al docente una exención que sus documentos no indican.

## 6. Orden propuesto para la adaptación

1. **Organización y lotes:** resolver bodega madre/sucursal matriz e identidad de lote por producto; homologar las consultas por lote. Preparar migraciones conservando registros históricos.
2. **Traslados:** documento, detalles, vehículo, ubicación de tránsito, estados e incidencias. Reutilizar movimientos, valoración y solicitudes existentes.
3. **Ajustes:** completar la captura autorizada y la evidencia de origen sobre el motor disponible.
4. **Ventas y devoluciones:** integrar documentos y entrega/aceptación con inventario, respetando permisos y transacciones.
5. **Aceptación del nuevo alcance:** recorrido documentado con casos normales, parciales y fallos. Confirmar antes cómo se demostrará el costo provisional frente a la redacción de la ERS.

Las pantallas provisionales de Clientes y Asignación de precios pueden requerir alcance propio al desarrollar ventas. La sección 6.9 aclara que el precio de venta es independiente del costo promedio; no exige recalcularlo automáticamente cada vez que cambia el promedio.

## 7. Casos mínimos de aceptación propuestos

Estos casos están definidos para una siguiente ejecución; no se ejecutaron en este análisis.

| Caso | Evidencia esperada |
| --- | --- |
| Dos productos recibidos en una compra y otra recepción parcial | Cada producto/recepción tiene identidad inequívoca y referencia al detalle recibido. |
| Buscar el lote visible en etiqueta en Kardex | Recupera sus movimientos y ubicaciones; diferencia lote interno y del fabricante. |
| Bodega madre asignada a matriz | Conserva existencias e historial y respeta permisos de empresa/sucursal. |
| Trasladar 10 unidades y recibir 8 | Origen disminuye 10; destino recibe 8; las otras 2 siguen en vehículo/tránsito o incidencia. El total y el valor global se conservan. |
| Recibir posteriormente las 2 restantes | Documento queda recibido sin duplicar movimientos ni valor. |
| Promedio del ejemplo ERS | 5 a USD 10 más 10 a USD 15 producen 15 unidades, USD 200 de valor y promedio 13.333333 a seis decimales. |
| Venta creada sin entrega | No cambia la cantidad física. |
| Venta entregada | Descuenta solo la ubicación de la sucursal que entrega y valora al promedio vigente. |
| Venta superior al disponible | Rechaza sin confirmar venta ni dejar movimiento parcial. |
| Devolución recibida y aceptada | Reintegra únicamente la cantidad aceptada, enlazada a salida original; conserva historial. |
| Ajuste y corrección autorizados | Motivo, documento, actor y nuevo movimiento; ninguna edición del histórico confirmado. |
| Error o reintento durante operación | Rollback completo ante fallo; repetición del mismo intento no duplica saldos ni movimientos. |

## Cierre del análisis

El recorrido ya trabajado termina en mercancía revisada y disponible en la bodega destino. La ERS 1.0 extiende la aceptación hasta entrega de ventas, devoluciones y ajustes, y precisa la organización y el transporte. El siguiente trabajo debe cerrar esas diferencias conservando la base implementada y su historial.

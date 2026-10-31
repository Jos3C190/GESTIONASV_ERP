# Retaceo manual, ingreso posterior y operación de bodega

Fecha local: 23/10/2026. Referencia: `MiniERP.png` aportado por el usuario.

## Alcance y resultado

Se implementó el flujo para compras nuevas: documento de compra recibido →
retaceo manual calculado, verificado y cerrado → verificación física de bodega →
ingreso con costo final y cuarentena → medidas, etiqueta, ubicación y liberación.
La confirmación comercial previa no crea existencias. El promedio se calcula
con el historial de la empresa y el costo de la entrada; no se captura a mano.

Las compras existentes conservan `receipt_before_retaceo`, incluso si estaban
pendientes al migrar. Las creadas con esta versión usan
`retaceo_before_inventory`. No se convierte una recepción histórica ni se
revalora un Kardex anterior para imponer el nuevo orden de pasos.

## Recorrido para presentar la funcionalidad

1. Crear una compra nueva desde su orden y confirmar su documento recibido.
2. Desde esa compra, abrir **Crear retaceo**. Capturar el FOB total de cada
   renglón; la compra solo aparece como referencia. Registrar origen, factura y
   póliza con sus fechas cuando correspondan.
3. Agregar gastos reales: flete, otros gastos, DAI e IVA de importación.
   Guardar el borrador, adjuntar comprobantes y distribuir los costos entre
   los productos. Guardar conserva el editor abierto. **Revisar y calcular**
   abre el detalle con las acciones de cálculo y verificación.
4. Consultar gastos previstos de la orden frente a los reales de esta compra.
   La comparación advierte que el presupuesto pertenece a toda la orden;
   no asigna automáticamente importes a una recepción parcial.
5. Calcular, verificar y cerrar el retaceo. La comparación del promedio muestra
   cantidad y valor anteriores, entrada y saldo proyectado. Puede cambiar si
   se registran otros movimientos antes de la recepción.
6. Entrar como bodeguero a **Inventario → Recepciones pendientes**. Verificar
   cantidades y seleccionar destino. Solo un retaceo cerrado habilita el nuevo
   ingreso. Lo rechazado no se incorpora a existencias.
7. Completar medidas, revisión de etiqueta y ubicación. Seleccionar pasillo,
   rack, nivel y posición y liberar la unidad cuando corresponda.
8. En retaceo y Kardex consultar el costo realmente contabilizado. La
   comparación posterior usa asientos históricos de esa recepción, aunque
   haya compras posteriores. Una recepción sin unidades aceptadas no genera
   una entrada física.

La política existente mantiene el IVA de importación como dato informativo,
separado del costo aterrizado. Esta entrega no cambia esa política contable.

## Bodeguero principal creado

- Empleado: Rodrigo Molina, código `BOD-MATRIZ-001`.
- Usuario: `rodrigo.molina.bodega`, activo y sin condición de superusuario.
- Empresa: Grupo Lorena. Bodega autorizada: `BM-001`, Bodega Matriz Grupo Lorena.
- Rol: `BODEGUERO PRINCIPAL`. Alcance explícito por empresa, sucursal y bodega.
- Permisos: consulta de empresa/sucursal/bodega, lectura/recepción/movimiento/
  capacidad de inventario, cola operativa de recepciones, consulta/creación/
  actualización/etiquetas de ubicaciones.
- Sin permisos de compras financieras, retaceo, valoración, usuarios o roles.
- El perfil usa navegación operativa reducida y se dirige a `/inventory`.
  La restricción de bodega se comprueba también en el servidor.
- La contraseña generada no se encuentra en el repositorio. Archivo privado:
  `C:/Users/rodri/AppData/Local/Temp/gestionasv-rodrigo-molina-bodega-20261023.txt`.
- Creación auditada mediante `backend/scripts/provision_warehouse_operator.py`.
  El comando rechaza identidades existentes y no restablece sus contraseñas.

## Etiquetas y Code 128

`INT-009` es el código interno del producto; corresponde al SKU `PRD-EMP-009`,
Caja de Cartón para Pastel 12 pulgadas. Code 128 representa ese identificador,
no una fecha ni un impuesto. Las etiquetas incluyen debajo del código la fecha
de recepción y, si está registrado, el vencimiento, también al imprimir solo
el código de barras.

Se corrigieron el contraste de barras/fondo, margen de lectura, respuestas
asíncronas antiguas y recuperación del renderizador tras un error. Se informa
claramente cuando el identificador contiene caracteres incompatibles con
Code 128. El error original de asignación mencionado por el usuario no contó
con mensaje ni reproducción: si persiste, requiere esa evidencia.

## Correspondencia con el diagrama

| Referencia del diagrama | Implementación usada |
| --- | --- |
| Retaceo antes de crear lotes | Política versionada en `purchases.inventory_workflow`; gateway exige retaceo cerrado antes de crear lote y movimiento |
| FOB/documentos/importación | Renglones `retaceo_details`, gastos/documentos normalizados y cinco campos de importación de `retaceos` |
| Gastos previstos | `purchase_order_expenses`, según el diagrama; consulta comparativa en edición y detalle de retaceo |
| Lotes/viñetas | `inventory_lots`, detalles, unidades logísticas y registros de impresión existentes |
| Pasillo/rack/nivel/posición | Catálogo `locations` y selector de cuadrícula existente |
| Kardex/promedio | `inventory_valuation_entries` inmutable y proyección `inventory_cost_averages` por empresa/artículo |
| Usuarios/roles/permisos | `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, más asignaciones de sucursal y bodega |

No se creó una tabla de gastos previstos en solicitudes: el usuario indicó
“creo” al ubicar ese paso y el diagrama sitúa los gastos en la orden. Los gastos
reales nuevos se capturan manualmente y no se copian desde ese presupuesto.

## Historial, respaldo y migraciones

- Respaldo previo: `tmp/ers-v1/retaceo-reorden-2026-10-23/before-retaceo-workflow-20261023.dump`.
- Revisiones aplicadas: `0092`, `0093`, `0094`. Revisión actual comprobada: `0094`.
- La recepción nueva registra el costo final una sola vez, vincula el retaceo
  en el asiento inicial y conserva una aplicación con modo `initial_receipt`.
- El Kardex anterior no se reescribe. El promedio actual es una proyección que
  cambia con entradas/salidas; los asientos y su promedio histórico permanecen.
- Las entradas genéricas de compra por `/inventory/movements` se rechazan;
  se utiliza el documento de compra y su verificación autorizada.
- No se crearon compras ni movimientos de inventario para probar esta entrega.

## COM-00025: pendiente de aclaración

Consulta de solo lectura: compra cerrada, 2,000 × USD 20 = USD 40,000,
descuento monetario USD 10, FOB de `RET-00019` USD 39,990. El gasto real
“flete int” de USD 10 deja costo total USD 40,000. La operación y su movimiento
siguen intactos. El usuario aún no indicó el importe correcto ni el mensaje de
error. No hay evidencia suficiente para reemplazar ese FOB histórico.

El balance de azúcar observado ahora es 1,390, con un ingreso histórico posterior
de 200 unidades a valor provisional cero (asiento 32). No debe compararse con
la captura anterior de 1,190 como si fuera el mismo instante. No se modificó ese
ingreso ni se creó por esta entrega. Su costo depende del flujo histórico y
retaceo correspondiente; no se corrigió inventando un valor.

## Comprobaciones y límites

Ruff y ESLint sin errores en los archivos revisados. `svelte-check`: cero errores,
ocho avisos existentes de `@apply` en `TransferOperationsPage.svelte`.
Inspección SQL con transacción `READ ONLY`: revisión, COM-00025/RET-00019,
permisos y alcance de Rodrigo y saldo/historial de azúcar. Evidencia:
`tmp/ers-v1/retaceo-reorden-2026-10-23/final-readonly.jsonl`.

No se añadieron ni ejecutaron tests automatizados ni una aceptación integrada
de compra/recepción con el nuevo usuario. Queda pendiente comprobar el recorrido
renderizado en ambos temas, impresión física/lectura del código y recepción real
de una compra nueva. La inspección estática no sustituye esas comprobaciones.

## Revisión independiente de interfaz

El skill `frontend-quality-studio` limita la revisión a tres rondas. Inventario
obtuvo 7.9/10 y retaceo 8.25/10 en su última revisión estática: ambos rechazados
frente al umbral 8.5. Después se corrigieron los hallazgos concretos descritos
abajo, sin una cuarta ronda ni aprobación visual inferida.

| Categoría | Inventario | Retaceo | Evidencia y alcance |
| --- | ---: | ---: | --- |
| Distinción visual | 7.5 | 8.0 | Flujo y destinos claros; tarjetas todavía convencionales |
| Tipografía/contenido | 8.5 | 8.5 | Geist y cifras; se corrigió la indicación de ubicaciones, etapas y estados documentales |
| Layout/responsive | 8.0 | 8.0 | Fichas móviles; resumen FOB/costo/IVA movido antes de los bloques extensos |
| Motion/interacción | 8.1 | 8.3 | Foco al revisar/confirmar; se añadió retorno al cancelar y guardar sin abandonar el editor |
| Sistema de diseño | 8.5 | 8.8 | Tokens compartidos; persisten pequeñas diferencias de radios/densidad |
| Accesibilidad | 6.5 | 7.8 | Se añadió borde de control con contraste y anillos opacos, también para adjuntos; sin inspección renderizada posterior |
| Código | 8.0 | 8.4 | Consultas protegidas; se invalidó selección URL al elegir manualmente y se limpia la selección antigua |
| Estados/límites | 7.8 | 8.2 | Cola/páginas/errores; revisión se cierra al refrescar y se distingue ausencia de retaceo de carga |

Entre rondas se incorporaron selector paginado, contexto compacto, comparativa
de gastos, tarjetas móviles, verificación condicionada por cierre y correcciones
de contraste/foco. Se entrega el mejor resultado alcanzado sin declarar que se
superó el estándar visual ni que se resolvió el FOB desconocido de COM-00025.

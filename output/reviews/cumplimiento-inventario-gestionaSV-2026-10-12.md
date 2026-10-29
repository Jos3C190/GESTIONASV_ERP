# GestionaSV frente a las imágenes de inventario

**Fecha:** 12 de octubre de 2026.  
**Método:** revisión estática del código local: modelos, reglas de dominio, casos de uso, API, servicios y pantallas. No se ejecutaron nuevas pruebas integrales ni operaciones sobre inventario real. «Implementado» significa que se encontró una ruta funcional en el código, no que se haya certificado su funcionamiento en producción.

## Resultado

GestionaSV tiene una base operativa de inventario implementada: recepción verificada, cuarentena, unidades logísticas, cantidades por ubicación, capacidades, traslados y trazabilidad. Para cumplir todo el material faltan principalmente valoración por costo promedio, Kardex valorizado, formalización de lotes y etiquetado, y conexión del cierre de retaceo con la disponibilidad.

## Matriz de cumplimiento

| Requisito | Estado observado | Alcance real |
|---|---|---|
| Recepción desde orden y verificación | Implementado | Cantidades recibidas, aceptadas y rechazadas; relación con la orden; ingreso de lo aceptado a cuarentena |
| Retaceo de la compra | Implementado con diferencia respecto a la ERS | Estados borrador/calculado/verificado/cerrado, gastos, documentos y costo unitario; el flujo de gastos detallados distribuye manualmente |
| Existencias por almacén y ubicación | Implementado | Saldos por artículo, ubicación, estado, lote opcional y vencimiento |
| Validar ubicación y capacidad | Implementado | Ubicación activa y apta; controles de peso, volumen y límites superiores |
| Confirmar ubicación y liberar disponibilidad | Implementado para el control físico | Exige condiciones físicas y ubicación; no vincula la liberación con el cierre del retaceo o una confirmación de etiquetado |
| Unidades logísticas y trazabilidad | Implementado | Identificador HU, genealogía de fraccionamientos, origen de compra, proveedor, orden, consolidado/solicitudes vinculadas e historial de movimientos |
| Traslados y recepción en sucursal | Implementado | Cantidades parciales, saldo en tránsito, recepción contada en cuarentena y liberación posterior |
| Conversión de unidad recibida a unidad base | Implementado | Presentación vigente por producto; rechazo si falta conversión o es ambigua |
| Lote automático por recepción | Parcial | Hay `lot_code` y vencimiento opcionales. El ingreso desde compras genera HU, pero no proporciona ni exige código de lote |
| Etiquetas | Parcial | QR e impresión por HU. El formato revisado no imprime la etiqueta de producto + barcode + lote + fecha del material |
| Historial de impresiones/reimpresiones | Pendiente en el flujo revisado | La impresión se ejecuta en el navegador, sin registro de cantidad, usuario y motivo de reimpresión en backend |
| Costo promedio ponderado | Pendiente | No se encontró cálculo, saldo valorizado ni configuración del método por empresa |
| Salidas al costo promedio vigente | Pendiente | Los movimientos revisados registran cantidades y medidas físicas, sin costo monetario de salida |
| Kardex completo y valorizado | Parcial en su base, pendiente como módulo | Existe historial de movimientos, pero la entrada del menú Kardex apunta a una pantalla pendiente; faltan saldos y valoración del Kardex del ejemplo |
| Asignación de precios de venta | Pendiente como módulo | El menú marca la función como no implementada |

## Evidencia de lo implementado

### Recepción y conversión

En [verificación de compra](C:/Developer/GESTIONASV_ERP/backend/app/application/purchases/use_cases.py:243), las cantidades aceptadas se envían al movimiento de inventario y se conserva su referencia en la compra. Se mantienen separadas las unidades físicas ingresadas por el operador.

El [adaptador de recepción](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/purchase_inventory_gateway.py:23) convierte cantidades a la unidad base mediante presentaciones activas y verifica el almacén/ubicación. Su entrada usa estado `quarantine` y una clave estable por compra para evitar registrar dos veces el mismo ingreso.

### Ubicaciones, cantidades y capacidad

[InventoryBalanceModel](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory.py:510) guarda cantidades por almacén, ubicación, producto, estado, lote y vencimiento. Por tanto, existe una estructura para saldos distribuidos entre ubicaciones aunque no se use el mismo nombre de tabla de las imágenes.

La [validación de destino](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_repository.py:1091) exige ubicación apta cuando el destino es disponible. El movimiento comprueba capacidad antes de confirmar. La [liberación desde cuarentena](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_repository.py:2630) valida medidas y vencimiento.

La separación de cantidades al verificar la compra existe, pero la pantalla exige una ubicación inicial común para las unidades separadas del producto. Después se elige ubicación final al liberar cada HU. Fraccionar una HU ya creada tiene restricciones; no debe darse por hecho que todo reparto posterior entre estantes esté cubierto por una pantalla dedicada.

### Traslados y trazabilidad

Los [servicios de traslados](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/services.ts:415) envían cantidades parciales a tránsito y reciben cantidades contadas en cuarentena. La [pantalla de traslados](C:/Developer/GESTIONASV_ERP/frontend/src/routes/(app)/transfers/+page.svelte:1280) ofrece consulta de pendientes por bodega o todas las autorizadas.

La [consulta de trazabilidad](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_repository.py:1482) recorre la unidad original y sus movimientos, y consulta los documentos de origen. Su [endpoint](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory.py:751) requiere usuario y autorización de almacén. La ficha existe; acceso público sin iniciar sesión no queda demostrado ni habilitado por esta ruta.

El [registro de movimientos](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_repository.py:2407) incorpora protección contra repetición mediante clave y huella del contenido. Las migraciones también contienen restricciones de inmutabilidad del historial.

## Brechas confirmadas

### 1. Valoración y Kardex

Los modelos de movimientos, líneas y saldos contienen cantidades, peso y volumen; no contienen valor del inventario o costo promedio. La búsqueda del motor de promedio ponderado y sus estructuras en backend, frontend y migraciones no encontró una implementación.

El menú declara explícitamente:

- [Kardex: `implemented: false`](C:/Developer/GESTIONASV_ERP/frontend/src/lib/navigation.ts:297).
- [Asignación de precios: `implemented: false`](C:/Developer/GESTIONASV_ERP/frontend/src/lib/navigation.ts:212).

El historial operativo existente sirve de base para el Kardex, pero no equivale al Kardex valorizado de las imágenes. Tampoco basta tener un costo de referencia en un producto o el costo de un retaceo para disponer de un promedio actualizado con entradas y salidas.

### 2. Lotes y viñetas

La [unidad logística](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory.py:197) tiene un código HU obligatorio, mientras `lot_code` es opcional. La [entrada desde compra](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/purchase_inventory_gateway.py:143) no suministra un lote ni un vencimiento.

La [impresión de etiqueta](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:126) genera HTML con QR, código HU y texto para consultar movimientos. No incluye producto, barcode del SKU, lote, fecha o cantidad, ni llama a una operación para registrar la impresión.

Esto cubre identificación y consulta de la HU, pero deja parcial el requisito de etiquetado del material. No es obligatorio reproducir los nombres de sus tablas; sí hace falta cubrir sus datos y comportamiento.

### 3. Retaceo finalizado como condición de disponibilidad

Actualmente:

1. Verificar la compra crea existencia en cuarentena.
2. El retaceo se crea sobre una recepción verificada o cerrada.
3. La liberación de cuarentena valida medidas, vencimiento y ubicación/capacidad.

No se encontró una comprobación del estado del retaceo en la liberación. Tampoco una confirmación obligatoria de etiqueta colocada. Por ello, no se cumple todavía el orden obligatorio completo que presentan las imágenes.

El [cierre de retaceo](C:/Developer/GESTIONASV_ERP/backend/app/application/retaceos/use_cases.py:235) cambia su estado. No actualiza un promedio de inventario. La [pantalla de liberación](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte:317) tampoco consulta ese cierre.

### 4. Distribución proporcional del retaceo

Existe un algoritmo proporcional al FOB, pero el [caso de uso](C:/Developer/GESTIONASV_ERP/backend/app/application/retaceos/use_cases.py:296) elige distribución manual cuando maneja gastos detallados. La [instrucción del editor](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/retaceos/components/RetaceoDraftEditor.svelte:522) lo expresa así. Es una diferencia respecto al PDF analizado, adicional a lo mostrado en las imágenes.

## Orden razonable para completar el material

1. Acordar el alcance del promedio (producto/almacén o producto/empresa), sus unidades y el momento de incorporación del costo.
2. Conectar el costo final del retaceo con la valoración de la entrada, contemplando recepciones parciales.
3. Implementar actualización del promedio y costo de salidas/traslados; construir el Kardex sobre esos movimientos.
4. Formalizar lote por recepción y etiqueta completa con auditoría de reimpresiones.
5. Unificar el flujo de retaceo finalizado, etiquetado y disponibilidad según la política acordada.
6. Completar asignación de precios cuando corresponda al alcance comercial.

**Conclusión:** se cumple una parte sustancial del control físico y de la trazabilidad. La valoración monetaria y el Kardex del material están pendientes; los lotes, etiquetas y la secuencia estricta de disponibilidad están parciales. No corresponde afirmar cumplimiento total del módulo de inventario de esas imágenes.

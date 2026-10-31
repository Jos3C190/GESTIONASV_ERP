# Plan consolidado: observaciones directas de Grupo Lorena

Fecha local: 27/10/2026. Fuente principal: transcripción y capturas de la revisión
del propio grupo, entregadas por Rodrigo, y resumen personal adjunto. Este
documento conserva el diagnóstico y el detalle de esas observaciones. El alcance
integrado de **todos los grupos**, confirmado después por Rodrigo, se encuentra
en el [plan maestro](plan-maestro-compras-inventario-grupo-lorena-2026-10-27.md).
La prioridad vigente toma solicitud/cotización/orden como base avanzada y cierra
recepción → retaceo → viñeteado → ubicación → inventario → promedio/Kardex y
reportes. Incluye aportes de las exposiciones, no solo las frases del docente.
Este documento distingue implementación existente, hallazgos y trabajo por hacer;
no declara terminadas las correcciones.

## 1. Alcance confirmado de la próxima demostración

Recorrer compra y recepción → gastos reales/retaceo → costo de adquisición y
promedio → viñeteado → ubicación física → ingreso a inventario → consulta de
Kardex e historial. La operación de ubicación debe poder realizarla un bodeguero
con una pantalla simple, permisos limitados y uso en dispositivo móvil.

Las prioridades manuales del consolidado pueden permanecer como dato adicional.
La explicación las sitúa principalmente en abastecimiento/reabastecimiento.
No se requiere rehacer el consolidado por este comentario ni convertir su
clasificación manual en un sistema de alertas completo para esta entrega.

## 2. Evidencia nueva del error FOB

La captura muestra **COM-00024**, no COM-00025. Una consulta de solo lectura al
entorno local confirmó esta cadena:

| Documento | Cantidad | Precio | Subtotal | Descuento monetario | Neto antes de impuesto |
| --- | ---: | ---: | ---: | ---: | ---: |
| COT-00050 | 200 | 10 | 2,000 | 2,000 | 0 |
| OC-00024 | 200 | 10 | 2,000 | 2,000 | 0 |
| COM-00024 | 200 | 10 | 2,000 | 2,000 | 0 |

COM-00024 está cerrada, tiene 200 unidades aceptadas y movimiento físico;
no tiene retaceo. La validación de FOB positivo falla porque el cálculo de
origen queda en cero. La cotización también registra impuesto 5%, con base
neta cero. La transcripción habla de un descuento del 5%, pero eso no coincide
con estos campos persistidos. No se infiere cuál era el descuento correcto.

Acciones del primer bloque:

- Aclarar en los formularios si descuento es importe total o porcentaje y
  mostrar bruto, descuento, neto e impuesto antes de confirmar.
- Comunicar por qué el FOB resulta cero, identificando el documento/renglón.
- Revisar si la captura o transformación pudo producir el descuento completo.
- Confirmar el importe correcto mediante el documento original antes de
  regularizar la operación cerrada. Mantener movimientos y auditoría históricos;
  no efectuar actualizaciones SQL para sustituir costos confirmados.
- COM-00025/RET-00019 es un caso diferente: en la inspección anterior tenía
  subtotal 40,000, descuento 10, FOB 39,990 y costo final 40,000. No confundir
  los dos documentos al corregir el caso presentado en clase.

La base está en revisión 0094. Las consultas no cambiaron compras, gastos,
inventario ni valoración. Scripts de evidencia en
`tmp/ers-v1/retaceo-reorden-2026-10-23/inspect_purchase_24*.py`.

## 3. Matriz de trabajo

| Requisito propio | Situación verificada | Trabajo concreto |
| --- | --- | --- |
| Una RFQ reúne varios productos del mismo proveedor | El editor permite seleccionar varias líneas y genera snapshot por proveedor | Demostrar tres productos en un solo documento; no confundir selección individual usada en clase con limitación del sistema |
| Adjuntar respuesta original y transcribirla | Hay adjuntos y editor manual | Comprobar archivos admitidos, conservación al guardar y lectura posterior |
| Comparar proveedores del mismo producto | Adjudicación manual y cantidades divididas implementadas | Demostrar dos o tres ofertas comparables, motivo y creación de orden. Matriz y recomendación del ejemplo Apex se incorporan en la entrega de compras del plan maestro |
| Gastos previstos frente a reales | Hay previstos en orden y comparativa con retaceo | Separar presupuesto y gasto real; relacionarlos sin sumar dos veces un mismo cargo |
| Registrar gastos durante la espera | El retaceo nuevo se crea desde compra recibida y los gastos de orden son de su borrador | Permitir bitácora de gastos reales vinculada a la orden aprobada/enviada, aun antes de recibir, con permisos y comprobantes |
| FOB/flete/DAI manuales y visibles | FOB manual para compras nuevas; flete y DAI son actualmente clases de costos junto con gastos | Darles sección propia y revisión explícita; cero confirmado y vacío deben distinguirse. Otros gastos salen del desglose, sin duplicar los componentes fijos |
| Factura conservada | Compra guarda número/fecha; importación puede volver a capturarlos | Reutilizar la misma factura cuando corresponda y proteger sus datos confirmados; documentos diferentes mantienen su identidad |
| Promedio global calculado con retaceo | Hay cálculo proyectado y lectura histórica; el costo se aplica hoy en verificación de recepción | Integrar cálculo de retaceo con confirmación del ingreso, preservando consistencia entre cantidad, valor y promedio; Kardex registra cada resultado histórico |
| No viñetear sin costo final | El flujo nuevo exige retaceo cerrado para verificar/crear unidades | Mantener el bloqueo hasta completar retaceo y costo. Separar preparación física de la entrada final |
| Ingreso después de ubicación | Hoy el gateway crea stock en cuarentena al verificar, antes de terminar etiqueta y ubicación | Reordenar el flujo para que la colocación confirmada sea el punto de alta final; evitar doble ingreso y conservar rechazos/parciales |
| Etiquetas QR y Code 128 legibles | Impresión incluye recepción/vencimiento; el renderizador de barras fue corregido | Unificar vista previa e impresión: producto, lote y fecha visibles en ambos formatos; vencimiento cuando aplique, observaciones opcionales |
| Vista propia de bodeguero | Existe /inventory, navegación reducida y usuario Rodrigo limitado a matriz | Completar cola de unidades viñeteadas, lectura de unidad/lote y ubicación, cantidad, confirmación y pendientes; proteger costos en UI/API/exportación |
| Ubicar parcialmente | Hay fraccionamiento/unidades y colocación existentes | Permitir un recorrido simple 50 recibidas → 30 en A + 20 en B, con validación y sin repetir movimientos |
| Kardex histórico y costo actual | Hay asientos inmutables y proyección por empresa/artículo | Comprobar que una entrada nueva cambia el costo vigente y no los asientos anteriores; referencias legibles y permisos |

## 4. Decisión técnica que debe quedar explícita

Recibir físicamente o registrar el documento no equivale a dejar stock
disponible. El flujo debe representar mercancía pendiente de costear/etiquetar/
ubicar sin crear dos entradas por esos mismos bienes.

Antes del viñeteado debe poder mostrarse el costo del retaceo y su comparación
con existencia anterior. La confirmación final debe mantener unidos cantidad,
valor, promedio vigente y asiento histórico, con bloqueo frente a concurrencia
e idempotencia. Una proyección no puede presentarse como costo ya contabilizado.
El ajuste fino del momento de aplicación requiere resolver esto en el diseño
del flujo; no basta cambiar el texto de un botón.

El promedio vigente pertenece a la empresa y artículo. Precio de venta es un
concepto aparte. No se debe sustituir el precio de venta al actualizar costos.

## 5. Orden de implementación

El orden vigente es el del plan maestro, que continúa hasta Kardex y reportes:

1. **Recepción, gastos y retaceo:** diagnóstico FOB, documento de origen,
   parciales, bitácora, componentes fijos y cierre con comparación de costo.
2. **Lotes y etiquetas:** QR/Code 128, fecha/lote visibles, cantidades y reimpresión.
3. **Bodeguero, ubicación e ingreso:** recorrido móvil, colocación parcial y
   entrada final única, con valoración consistente e historial conservado.
4. **Inventario:** existencias, lotes, mapa/ubicaciones, movimientos y saldo inicial.
5. **Kardex y reportes:** promedio, referencias, filtros, conciliación y XLSX/PDF.
6. **Aceptación y exposición:** recorrido completo y regresiones de funciones existentes.

Reutilizar las pantallas de compras. Las funciones de recomendación, matriz,
devolución de Gerencia por versión, consulta espacial y mínimos quedan incluidas
y ordenadas en el plan maestro. No es requisito reproducir el aspecto 3D de un
mapa: debe permitir consultar ubicaciones y su contenido. Abastecimiento/traslados
usan existencias disponibles del inventario completo, incluyendo lotes viejos,
en su fase propia.

## 6. Casos de aceptación propuestos, todavía no ejecutados

- RFQ de un proveedor con tres productos y orígenes de varias sucursales.
- Respuesta con documento adjunto, precios y descuento explícito; comparación
  del mismo producto entre dos o tres proveedores y motivo de adjudicación.
- Gasto real registrado antes de recepción; luego retaceo que lo incorpora una
  sola vez. Flete/DAI cero revisados frente a datos omitidos.
- Recepción parcial y rechazo; etiqueta/ingreso bloqueados hasta costo final.
- Primera entrada 10 × 10 = 100; segunda 10 × 15 = 150 → saldo 20, valor 250,
  promedio 12.50; tercera 10 × 20 = 200 → saldo 30, valor 450, promedio 15.
- Agotar existencia y recibir nuevamente: el promedio toma costo de nueva entrada;
  los movimientos anteriores conservan sus valores.
- Bodeguero ubica 30 y 20 de un pendiente de 50; reintento de confirmación no duplica.
- QR y Code 128 impresos/escaneados con fecha y lote legibles; reimpresión conserva
  lote y cantidades. Escanear solo el código común del producto no distingue sus
  lotes: usar identificador de unidad o el contexto explícito del lote.
- Kardex, existencias y valoración concilian; el bodeguero no recibe costos.

Los requisitos normativos mencionados en la clase no se dan por verificados:
un eventual formato fiscal necesita su plantilla oficial vigente y revisión
correspondiente. El objetivo inmediato es la demostración funcional solicitada.

## 7. Estado de esta entrega de planificación

Se consolidaron observaciones y se inspeccionó código/BD en lectura. No se
implementaron los bloques anteriores ni se ejecutaron los casos de aceptación.
Las mejoras previas de 0092–0094 y los atajos del 27/10 siguen siendo avances
parciales; no se declaran como cumplimiento completo de este plan.

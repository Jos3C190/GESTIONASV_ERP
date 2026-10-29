# Revisión del recorrido de cotización y orden

Fecha local: 27/10/2026. Referencia: capturas y transcripción de la exposición
aportadas por el usuario. Se compararon funcionalidades del código actual;
las frases del material no se trataron como autorización para reproducir toda
la interfaz ni para afirmar cumplimiento fiscal o funcional.

Actualización de alcance: Rodrigo confirmó incorporar también las observaciones
de Apex y los demás grupos. Las brechas de esta revisión forman parte del
[plan maestro de Grupo Lorena](plan-maestro-compras-inventario-grupo-lorena-2026-10-27.md),
con entregas incrementales. Este informe mantiene los resultados de la revisión
original y sus límites de comprobación.

## Lo encontrado

| Función del ejemplo | Estado en nuestro código |
| --- | --- |
| Consultar varios proveedores desde un consolidado | Implementado: RFQ separada por proveedor, versiones y cantidades de origen congeladas |
| Documento para cada proveedor | Vista imprimible de la RFQ con posibilidad de guardar PDF desde el navegador; no es una descarga PDF binaria directa |
| Registrar disponibilidad y precios | Implementado en el editor de respuesta, con cantidades ofrecidas/disponibles, precio, descuento, impuesto y entrega |
| Pago y vigencia | Campos implementados; no se encontraron las confirmaciones de revisión del ejemplo ni un mínimo de compra estructurado en el editor de respuesta |
| Cargos adicionales de la oferta | Soporte en la API; el editor de respuesta envía `expenses: []` y no ofrece capturarlos en ese paso |
| Comparar proveedores y elegir por producto | Implementado en adjudicación del consolidado; puede dividir cantidades entre ofertas y exige motivo |
| Recomendación automática y aplicarla | No implementada en adjudicación consolidada. La comparación individual de solicitudes ordena cotizaciones por total, entrega y código; no equivale a recomendar una cesta de productos comparables |
| Matriz global producto × proveedor | No existe con la presentación del ejemplo; hay comparación rápida por producto y fichas de ofertas |
| Generar órdenes para proveedores elegidos | Implementado por cotización adjudicada y cantidades pendientes. La UI crea borradores por separado; no es un comando único de creación múltiple y envío a Gerencia |
| Solicitar aprobación, aprobar y registrar envío | Implementado con permisos separados y estados de orden |
| Devolver con observaciones y aprobar una versión | No se encontró esa transición de devolución ni un modelo de revisión aprobada equivalente. En pendiente de aprobación están aprobar/cancelar; cancelar no equivale a devolver para corregir |
| Esperar y registrar recepción | Implementado desde la orden enviada o parcialmente recibida |

## Evidencia principal

- `frontend/src/lib/features/purchase-quotations/components/PurchaseConsolidationRfqs.svelte`:
  proveedores/RFQ del consolidado.
- `PurchaseQuotationRequestDocument.svelte`: usa `window.print()` sobre la
  solicitud con snapshots de origen.
- `PurchaseQuotationResponseEditor.svelte`: captura respuesta, pago, vigencia
  y líneas; su envío actual contiene `expenses: []`.
- `frontend/src/lib/features/purchase-requests/components/PurchaseConsolidationAdjudication.svelte`:
  adjudicación manual, decisiones y enlaces para crear órdenes por cotización.
- `PurchaseConsolidationAwardLine.svelte`: comparación rápida por producto.
- `backend/app/application/purchase_quotations/use_cases.py`, `compare_offers`:
  excluye RFQ de consolidado del ranking individual y ordena totales de ofertas
  filtradas; no implementa una recomendación global de compra.
- `backend/app/domain/entities/purchase_order.py`: estados y transiciones.
  `pending_approval` admite `approved` o `cancelled`, no devolución.
- `frontend/src/lib/features/purchase-orders/components/PurchaseOrderWorkflowActions.svelte`:
  acciones disponibles según permisos y estado.

## Simplificación puntual aplicada

Se conservan las pantallas y el proceso existentes. En la lista de RFQ del
consolidado se agregaron:

1. **Imprimir solicitud**, enlazando al documento existente.
2. **Registrar oferta**, solo para una RFQ enviada, consolidado activo y los
   permisos necesarios del flujo existente.
3. **Comparar ofertas**, enlace a la sección de adjudicación cuando ya hay
   respuestas y el usuario puede consultar solicitudes.
4. **Ver detalle**, para mantener disponible la consulta completa.

En la orden se cambió la instrucción técnica por texto operativo y el botón
**Enviar al proveedor** por **Marcar enviada al proveedor**. La acción registra
la transición existente; el texto no promete que se haya enviado un correo.

No se agregó una nueva interfaz, recomendación automática, nueva transición de
Gerencia, migración ni cambio del cálculo comercial. No se ejecutaron operaciones
de compra ni se alteraron datos para hacer esta revisión.

## Comprobación y límites

- Ambos componentes modificados se compilaron con el compilador de Svelte
  instalado localmente: sin errores ni advertencias.
- Docker Desktop no tenía disponible su motor Linux. No se pudo comprobar el
  recorrido integrado con la aplicación y base de datos en funcionamiento.
- Vitest/ESLint y el plugin de Prettier para Svelte no estaban resolubles en
  las dependencias locales; no se ejecutaron sus suites ni se instaló un entorno
  nuevo. La compilación estática no certifica el comportamiento completo.

La conclusión es cobertura parcial del ejemplo, con atajos de navegación
aplicados. Los pendientes funcionales requieren su propio trabajo: cargos de
oferta, revisión de condiciones, recomendación comparable y devolución de
Gerencia con historial de versiones.

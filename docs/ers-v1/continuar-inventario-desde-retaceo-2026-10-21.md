# Continuar a inventario desde un retaceo cerrado

Fecha: 21/10/2026.

## Solicitud

Facilitar el siguiente paso después de cerrar el retaceo. Referencia visual del usuario:
RET-00018, compra COM-00023. Estos códigos son ejemplos; la navegación se calcula para cada compra.

## Implementación

- En el detalle de un retaceo `closed` aparece «Siguiente paso: ubicación y etiquetas».
- «Continuar en inventario» abre `/warehouses/{warehouse_id}?tab=inventario`.
  `warehouse_id` procede de la compra vinculada al retaceo; no se fija la bodega matriz.
- El botón aparece al actualizar el estado tras cerrar y al consultar un retaceo ya cerrado.
  El usuario conserva el aviso de costo aplicado y decide cuándo continuar mediante el botón.
- La indicación menciona el código de la compra y las revisiones de ubicación, medidas y etiquetas.
  La pantalla de destino conserva las recepciones y unidades de toda esa bodega; el enlace no
  preselecciona ni filtra una recepción.
- Se requieren `inventory:read` y `warehouses.view`, conforme a los accesos existentes de destino.
  Si faltan, se explica que debe continuar un usuario autorizado.
- Si no se puede cargar la compra o identificar su bodega, se muestra un aviso con «Volver a cargar».
  No se ofrece un destino supuesto.
- Se verifica que la compra corresponda al ID y empresa del retaceo. La carga se reinicia al cambiar
  empresa o sucursal y descarta respuestas de cargas anteriores o de un componente desmontado.

Archivo modificado: `frontend/src/lib/features/retaceos/components/RetaceoDetail.svelte`.
No se modifican movimientos, cantidades, costos, permisos del backend ni SKU protegidos.

## Evidencia técnica

- Prettier del archivo: salida 0, sin cambios de formato pendientes.
- ESLint del archivo: salida 0, sin incidencias.
- `git diff --check` del archivo: salida 0.
- `svelte-check --tsconfig ./tsconfig.json`: salida 0; 0 errores y 8 advertencias existentes
  por `@apply` en `TransferOperationsPage.svelte`. Sin diagnósticos en el archivo modificado.

No se ejecutaron suites de pruebas ni operaciones sobre datos. No se verificó el clic en navegador.

## Comprobación manual pendiente

1. Recargar RET-00018 y comprobar que el botón aparece debajo del aviso de costo aplicado.
2. Pulsar «Continuar en inventario»: debe abrir la bodega receptora de COM-00023 en la pestaña Inventario.
3. Localizar la recepción o sus unidades; continuar únicamente las revisiones pendientes.
4. En otro retaceo, completar el cierre y comprobar que aparece la misma acción sin recargar.
5. Confirmar que un borrador o un retaceo cancelado no muestran la acción.
6. Verificar teclado y presentación en móvil, y los mensajes de falta de permisos o fallo al cargar
   la compra. Estos casos no se declaran aprobados sin observación.

Este ajuste no modifica el estado del cierre integral B01–B08.

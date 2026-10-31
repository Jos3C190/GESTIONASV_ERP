# Traslados: dashboard de abastecimiento y preparación visible

Fecha: 21/10/2026. Estado: implementación y revisión estática; aceptación interactiva pendiente.

## Solicitud y diagnóstico

El usuario reportó que **Preparar traslado** y **Envío manual** parecían no responder y pidió una organización similar a un dashboard, conservando la cabecera, las pestañas y el selector de origen mostrados en sus capturas.

La inspección encontró que ambos botones cambiaban el estado del formulario situado **después del catálogo completo**, sin llevarlo a la vista ni darle foco. El producto del formulario se buscaba además dentro de una lista filtrada por la búsqueda: cambiar el filtro podía hacer desaparecer su selección. Esta causa se identificó por lectura del código; no se registró una reproducción nueva mediante clicks.

## Investigación y diseño

**Usuario:** encargado de la bodega matriz que prepara abastecimiento para sucursales. La tarea principal es identificar producto, cantidad disponible y solicitud antes de elegir qué enviar. Se usan exclusivamente existencias, unidades y solicitudes reales devueltas por los servicios existentes. No se suman cajas con kilos ni cantidades de productos distintos.

**Dirección visual:** mantener Geist y los tokens de la aplicación. Superficies claras `#FFFFFF`, texto `#111111`, borde `#E9E9E9`, acento `#0070F3`; en oscuro, superficies `#000000`/`#0A0A0A`, texto `#FAFAFA`, borde `#1A1A1A`, acento `#00A8F3`. Los avisos conservan borde/fondo semánticos y texto principal para evitar el contraste insuficiente encontrado en la revisión.

La composición utiliza conteos operativos y un panel de producto/demanda, sin gráficos inventados ni una tarjeta grande por cada solicitud en toda la página:

```text
Cabecera de Traslados + pestañas existentes
Planificar abastecimiento                  Bodega de origen
Productos disponibles | Unidades logísticas | Solicitudes | Sucursales
Buscar producto, SKU, sucursal o solicitud        Filtros
Lista compacta de productos | Producto elegido y disponibilidad
                           | Solicitudes por sucursal y cantidades
                           | Preparar traslado / Envío manual
                            -> Diálogo de preparación
```

En móvil los paneles se apilan. Elegir un producto lleva foco al detalle y ofrece volver a la lista. Las cantidades usan tipografía monoespaciada; carga, consulta parcial, falta de existencia y ausencia de resultados tienen estados distintos.

## Cambios implementados

- `TransferDemandOverview.svelte`: resumen real de productos disponibles, HUs, solicitudes pendientes y sucursales; búsqueda y filtros; lista compacta y detalle por producto. Se conserva el avance de asignación y el detalle de despacho, tránsito y recepción.
- `TransferPreparationDialog.svelte`: diálogo nativo con título y descripción, foco inicial, scroll propio y cierre bloqueado mientras se guarda. Los controles se montan únicamente cuando se abre. La apertura no crea documentos ni unidades logísticas.
- `TransferOperationsPage.svelte`: catálogo seleccionado independiente de los filtros; estado explícito del diálogo; preparación manual y por solicitud conectadas a ese mismo editor. El enlace desde una HU prioriza ese producto y su unidad al preparar; un enlace obsoleto muestra un aviso.
- El origen queda fijo dentro del formulario. Para una solicitud, los destinos se filtran a la sucursal correspondiente; se permite elegir entre sus bodegas elegibles y se informa cuando no existe ninguna.
- Edición de documentos: consulta nuevamente la bodega de origen y obtiene el límite de las HUs desde la existencia vigente, en vez de usar la cantidad planeada anterior como saldo. Durante carga/error no permite guardar con una existencia desconocida.
- Las asignaciones de solicitudes son editables al modificar cantidades. Se rechazan valores negativos, exponentes, vacíos o más de seis decimales con mensaje asociado al campo. Cero significa explícitamente no asignar esa cantidad; cualquier envío sin asignación requiere motivo. El backend conserva sus validaciones autoritativas.
- La carga del origen lleva secuencia: solamente la consulta más reciente del contexto y bodega actuales puede aplicar resultados. Protege actualizaciones simultáneas y cambios A → B → A.
- **Actualizar saldos** permite consultar existencias/demanda desde el diálogo conservando cantidades y motivos. Los límites se reconcilian con las HUs vigentes; no se presenta un saldo desconocido como cero.
- Después de guardar, se muestra confirmación en Documentos y se lleva foco al documento resultante. Guardar conserva el comportamiento existente de crear/actualizar preparación; el despacho sigue siendo una confirmación aparte.
- La demanda parcial muestra conteos `≥` y textos limitados a las sucursales consultadas, evitando afirmar ausencia absoluta de solicitudes.

No se modificaron endpoints, permisos, migraciones o motores de movimientos. No se ejecutaron escrituras a la base de datos ni operaciones sobre los cuatro SKU protegidos durante este encargo. Abrir/cerrar o seleccionar productos no divide inventario.

## Comprobaciones técnicas

Evidencia: `tmp/ers-v1/2026-10-21-dashboard-traslados/`. El subdirectorio `before/` conserva los dos componentes originales como referencia del cambio; parte del diff del contenedor corresponde al formato Prettier.

| Comprobación | Evidencia | Alcance |
| --- | --- | --- |
| ESLint de los tres componentes | `eslint.log` y `.exit`, salida 0 | Aprobado, análisis estático |
| Svelte/TypeScript del proyecto | `svelte-check.log` y `.exit`, salida 0 | 0 errores y 8 advertencias heredadas de `@apply` en el contenedor |
| Prettier de los tres componentes | `prettier-check.log` y `.exit`, salida 0 | Aprobado, formato |
| Espacios del diff del archivo de pruebas previamente existente | `diff-check.log` y `.exit` | Higiene de cambios; no ejecuta pruebas |

No se añadieron ni ejecutaron casos/suites de prueba. Se ajustaron las expectativas de presentación de los dos casos existentes en `TransferDemandQuantity.test.ts`: una representación por solicitud en lugar de duplicados ocultos para móvil/escritorio, resumen de cantidad y pluralización. Estos casos **no se ejecutaron** en este encargo.

## Crítico independiente

Se realizaron tres revisiones de solo lectura, con contexto nuevo, según `frontend-quality-studio`. No hubo navegador, capturas nuevas o comprobación de teclado. **El gate no quedó aprobado por el crítico:** las tres revisiones rechazaron las versiones evaluadas; se aplicaron las correcciones encontradas. Tras la tercera se hizo revisión propia y se repitieron comprobaciones estáticas; no se inventa una cuarta aprobación.

| Ronda | Resultado del crítico | Correcciones aplicadas después |
| --- | --- | --- |
| 1 | Rechazado, 7,4/10 | Recarga del origen al editar, contraste de pestañas, mensajes parciales, ajuste de columnas de edición |
| 2 | Rechazado, 8,1/10 | Asignaciones editables, rechazo explícito de entradas inválidas, límite desde existencia vigente y recuperación de consulta |
| 3 | Rechazado, 8,0/10 | Secuencia de consultas, actualización de saldos dentro del modal y foco/confirmación al documento guardado |

Scorecard de la **versión evaluada en la tercera ronda**, anterior a las últimas correcciones:

| Categoría | Nota | Evidencia señalada |
| --- | --- | --- |
| Distinción | 8 | Organización específica de productos, demandas y sucursales |
| Contenido | 8,5 | Vocabulario operativo y cifras monoespaciadas |
| Layout | 8,5 | Dos paneles desde `lg`, lista móvil y modal `90dvh`; render pendiente |
| Interacción | 8 | Selección, progreso y carga; faltaba completar transición de guardado |
| Consistencia | 8,5 | Tokens y Button compartido |
| Accesibilidad | 7,5 | Diálogo y formularios nombrados; faltaba foco final al guardar |
| Código | 7,5 | Componentes separados y cantidades con bigint; faltaba proteger respuestas fuera de orden |
| Estados | 7,5 | Estados diferenciados; faltaba recarga del formulario ante un conflicto |

La revisión propia posterior confirma por código las tres correcciones finales: el resultado de origen exige secuencia vigente, existe el botón de recarga en el pie del diálogo y el guardado anuncia el documento/focaliza `detail-heading` tras actualizar el DOM. Esto no acredita ejecución ni acabado visual.

## Aceptación manual pendiente

Usar productos de demostración propios del usuario o un producto nuevo; conservar los SKU protegidos. Los siguientes son criterios propuestos, **sin resultado ejecutado**:

1. **Manual:** seleccionar harina, pulsar Envío manual, comprobar diálogo visible y nombre/SKU; elegir destino y cantidades; cerrar sin guardar. No debe haber movimiento ni nueva HU.
2. **Por solicitud:** abrir una solicitud de una sucursal, pulsar Preparar traslado; verificar sucursal, solicitud, pendiente y destinos restringidos correctamente.
3. **Búsqueda/selección:** filtrar, elegir otro producto, abrir/cerrar preparación y volver a filtrar; el borrador no debe perder su identidad por la búsqueda.
4. **Teclado:** abrir con Enter, recorrer campos, cerrar con Escape y comprobar foco de retorno; guardar y comprobar foco/confirmación en el documento creado. Escape/cerrar no deben cancelar una solicitud de guardado ya en curso.
5. **Edición parcial:** reducir una línea planeada/asignada de 10 a 8 y ajustar su asignación a 8. Verificar que la existencia utilizada sea la actual del origen del documento.
6. **Validación:** probar asignación negativa, exponente, más de seis decimales, vacía y cero. Las inválidas no deben llegar al payload; cero sin asignar exige motivo para la cantidad enviada.
7. **Recuperación:** provocar conflicto o error de consulta, usar Actualizar saldos y comprobar que cantidades/motivos se conservan y que no se permite exceder el saldo actualizado.
8. **Concurrencia:** actualizar dos veces y alternar A → B → A con respuestas lentas; solo la última consulta debe modificar la existencia visible.
9. **Estados parciales:** fallar una consulta de sucursal y comprobar `≥`, mensajes limitados a lo consultado y ausencia de ceros falsos.
10. **Visual:** revisar tema claro/oscuro en móvil (~375 px), tablet (~768 px) y escritorio (1280 px+), textos largos, altura del diálogo, scroll y acciones del pie.

No hay aprobación de render, clicks, accesibilidad interactiva o demostración completa. No se declara cerrado B01–B08 a partir de este cambio.

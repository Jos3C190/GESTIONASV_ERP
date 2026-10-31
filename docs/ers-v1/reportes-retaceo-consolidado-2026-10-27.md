# Reportes de retaceo y consolidado general

Fecha local: 27/10/2026. Cambio adicional al bloque 1 de Grupo Lorena.

## Cómo usarlos

- Abrir un retaceo: junto a sus acciones aparecen **Descargar PDF** y
  **Descargar Excel**. Los dos reportes muestran el cálculo guardado, incluso
  después del cierre. El estado identifica borradores y documentos cancelados.
- Abrir un consolidado general: **Descargar PDF** muestra demanda por producto,
  cantidades de sucursales, demanda central y solicitudes de origen. Si hay
  cambios locales sin guardar se avisa que se exportará la versión guardada.
- Las solicitudes de cotización y su impresión por proveedor continúan disponibles.
  El consolidado general es un reporte interno; cada RFQ contiene los productos
  que se consultan a su proveedor.

El Excel contiene las hojas Información, Costos por producto, Resumen del
retaceo y Gastos reales y respaldo. Los importes son numéricos; el costo unitario
mantiene seis decimales. Las filas superiores permanecen visibles al desplazarse
y las tablas tienen filtros. Los archivos de evidencia se enumeran; no se
incrustan dentro del reporte.

FOB, flete, DAI, otros gastos y costo aterrizado proceden del cálculo persistido.
El IVA se muestra por separado. El costo de esta entrada y el promedio global
son distintos: el reporte no vuelve a calcular el historial ni reemplaza el costo
guardado por una proyección actual. Descargar o editar una copia del Excel no
modifica el documento en el sistema. Los comprobantes adjuntos siguen opcionales.

## Qué significa la matriz de proveedores

Es una presentación de las ofertas con productos en filas y proveedores en
columnas. Se compara el mismo producto, unidad y cantidad, junto con descuentos,
impuestos, gastos, moneda y disponibilidad. Una línea no cotizada no equivale a
precio cero. La selección puede adjudicarse a proveedores distintos por producto
y debe conservar su justificación.

Este cambio agrega reportes; no reemplaza la comparación por producto existente
ni incorpora una nueva pantalla matricial.

## Validación

- 31 pruebas dirigidas de backend y 24 de frontend correctas en la ejecución de
  aceptación. Cubren valores persistidos, IVA separado, textos no ejecutables en
  Excel, paginación PDF, visibilidad de empresa/bodega/sucursales, descargas sin
  autenticación, formato elegido, nombre de archivo, reintento, sesión renovada,
  doble clic, cambio de documento/contexto y desmontaje.
- Ruff y ESLint sin incidencias. Svelte-check sin errores; ocho avisos previos de
  `@apply` en TransferOperationsPage, ajenos a esta entrega.
- Prueba real de solo lectura: RET-00021 conserva USD 37; CD-00010 conserva tres
  productos. Se generaron copias de QA y se inspeccionaron las páginas renderizadas.
  Los documentos cortos caben en una página horizontal; las tablas extensas
  continúan con encabezados repetidos. No se alteraron registros de negocio.
- Comprobación HTTP autenticada contra el servidor activo: retaceo PDF, retaceo
  XLSX y consolidado PDF respondieron 200 con el tipo de archivo correcto y
  `Cache-Control: no-store`. El Excel descargado mantiene USD 37 como costo
  aterrizado. Las credenciales de prueba se mantuvieron solo en memoria.
- Control probado visualmente a 375, 768 y 1280 px, con temas claro/oscuro y
  mensaje de error. Sin desbordamiento horizontal en esas capturas.
- Dependencia de producción añadida: ReportLab, con `uv.lock` actualizado. La
  instalación activa se sincronizó. No se necesita migración de base de datos.

## Crítica independiente de UI

Veredicto del agente de solo lectura: **aprobado**, promedio **8.63/10**. Alcance:
control de descargas dentro de las vistas existentes; capturas del componente con
estilos reales. La integración se revisó por código, sin afirmar una revisión
visual completa de ambas pantallas.

| Categoría | Nota | Evidencia |
|---|---:|---|
| Distinción visual | 8 | Acciones discretas y elección explícita de formatos |
| Tipografía y contenido | 9 | Ayuda sobre datos guardados y éxito dirigido a descargas |
| Layout y responsive | 8.5 | Controles de 44 px y ajuste en móvil sin recortes |
| Motion e interacción | 8 | Preparación y bloqueo inmediato; después se estabilizó el ancho |
| Consistencia | 9.5 | Button y tokens compartidos de ambos temas |
| Accesibilidad | 9 | Grupo con nombre, estado anunciado, alerta y foco visible |
| Código | 8.5 | Reutilización y descarte de respuestas de otro contexto |
| Estados y bordes | 8.5 | Preparación, éxito, error, reintento y cambios sin guardar |

Se atendieron las observaciones menores: ancho fijo mínimo al preparar,
mensaje que incluye sucursal, y pruebas de respuesta tardía por contexto y
desmontaje. El resto del plan de lotes, ubicación, inventario y Kardex continúa
con su alcance previamente acordado.

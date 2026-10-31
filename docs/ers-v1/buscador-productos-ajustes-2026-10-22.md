# Buscador de productos en ajustes — 22/10/2026

## Alcance y diseño

El operador necesita encontrar un artículo entre miles de productos al preparar
un ajuste. Se sustituyó el select nativo de **Artículo** por un diálogo de
búsqueda, sin rediseñar el resto del formulario. Nombre, SKU y unidad se muestran
por separado. Se conservan los tokens Geist y los temas existentes; controles y
resultados tienen foco visible y al menos 44 px de altura. El diálogo adapta el
ancho a móvil y limita su altura para mantener accesibles búsqueda y navegación.

El catálogo inicial se ordena por nombre. No se presenta como una lista de
recientes ni como disponibilidad física: los productos de la empresa pueden
utilizarse para entradas; una salida exige además escoger una HU de la bodega.

## Uso

1. Seleccionar la bodega del ajuste.
2. Pulsar **Buscar producto** en la línea.
3. Escribir parte del nombre o SKU, por ejemplo `azucar`, `glass premium` o
   `PRD-AZU-004`. La consulta no distingue mayúsculas ni tildes españolas.
4. Seleccionar un resultado o navegar con Anterior/Siguiente, 20 por página.
   Nombre, SKU y unidad permanecen visibles tras seleccionar.
5. Para el ejemplo de Gotera, escoger **Salida negativa** y la HU devuelta
   que contiene 1 cj; continuar con borrador, soporte, aprobación y aplicación.

Tab recorre los controles; flecha abajo desde el buscador enfoca resultados;
flechas arriba/abajo recorren la página; Enter selecciona un resultado enfocado;
Escape cierra el diálogo. Enter en el buscador selecciona únicamente si hay un
solo resultado en la página.

## Contrato y arquitectura

`GET /inventory/adjustments/options` conserva `inventory:read` y la autorización
de empresa/bodega/sucursal que se ejecuta antes de consultar. Parámetros nuevos:

| Parámetro | Predeterminado | Uso |
| --- | --- | --- |
| `q` | vacío | Hasta 120 caracteres; palabras combinadas de nombre/SKU |
| `limit` | sin límite, por compatibilidad | 1–50; el nuevo selector solicita 20 |
| `offset` | 0 | Página por desplazamiento, orden estable nombre/ID |
| `include_items` | true | false carga ubicaciones sin descargar catálogo |
| `include_locations` | true | false evita repetir ubicaciones en la búsqueda |

Respuesta compatible: `items`, `locations`, más `items_total` nullable.
El formulario nuevo solicita solo ubicaciones al cargar. La búsqueda y
paginación se realizan en PostgreSQL; se renderizan hasta 20 resultados.
No se midió rendimiento con 2,000 productos.

La lectura de opciones se trasladó del router al repositorio mediante el puerto
y caso de uso de ajustes. Las palabras de consulta usan parámetros SQL y
escapado literal para `%` y `_`; el tratamiento de tildes no exige extensiones
de PostgreSQL. El catálogo sigue limitado a artículos activos de la empresa.
No se añaden migraciones ni comandos de inventario.

## Robustez revisada en código

- Secuencias de consulta descartan respuestas anteriores al cambiar consulta,
  página, bodega, empresa/sucursal o cerrar/destruir el selector.
- Las líneas tienen claves estables; quitar una línea no reutiliza el diálogo
  ni el producto seleccionado de otra.
- La selección conserva sus propios metadatos; no depende de la página del
  catálogo que esté cargada.
- Cambiar producto limpia cantidad, unidad logística, ubicación, costo y
  medidas del producto anterior. Cambiar dirección conserva la identidad y
  exige una nueva selección física cuando corresponda.
- Las consultas de HUs tienen secuencia por línea y descartan líneas quitadas
  y contextos obsoletos.
- Carga con skeleton; error con reintento; vacío con explicación y retorno al
  catálogo; resultado seleccionado identificado. Los errores técnicos de
  conexión no se muestran literalmente en el selector.
- El nuevo diálogo no envía el formulario al pulsar Enter en la búsqueda.

## Comprobaciones y límites

No se añadieron ni ejecutaron pruebas automatizadas. No se realizaron clics de
aceptación ni escrituras de inventario por el agente. La inspección de teclado,
responsive y estados es estática; el recorrido de usuario queda pendiente.

- ESLint focalizado de los tres archivos frontend: exit 0.
- Prettier focalizado: exit 0.
- Svelte-check: 0 errores; 8 avisos `@apply` existentes de Traslados.
- Ruff inicial: dos hallazgos previos en `validate_direction_fields` del DTO
  (`C901`, `SIM102`); esa validación no se modificó. Se eliminó un import `date`
  sin uso en el puerto de ajustes.
- Ruff final de router, caso de uso, puerto y repositorio: exit 0. Los dos
  hallazgos anteriores del DTO quedan registrados; no se cambió esa validación.

## Alcance de la demostración del usuario

La venta `VTA-20261022-61FFF076` y entrega `ENT-20261022-7372C13E` muestran salida
de 10 cj del azúcar; devolución `DEV-20261022-5BF897BB` aceptada por 1 cj y
liberada en Gotera. Las capturas muestran 1,190 + 1 = 1,191 cj disponibles.
Queda aplicar el ajuste negativo ficticio de 1 cj con soporte y verificar 1,190;
también demostrar dos ingresos a costos distintos para el promedio ponderado.
La aceptación integrada B01–B08 sigue parcial según la guía maestra. Revisar
las mediciones ficticias antes de exponer (0.5 kg para la caja devuelta y 1 kg
para 1,190 cajas en las capturas).

## Revisión independiente

Ronda 1: **8.38/10, rechazada**. Se corrigieron dos hallazgos: elegir otra vez
el producto actual ahora cierra sin borrar campos; un error al cargar HUs tiene
su propio mensaje/reintento y no se presenta como ausencia real de unidades.

Ronda 2: **8.56/10, aprobada en revisión estática**, sin categorías menores de 7.

| Categoría | Nota | Evidencia del crítico |
| --- | ---: | --- |
| Distinción visual | 8 | Filas funcionales con nombre, SKU y unidad |
| Tipografía y contenido | 9 | Jerarquía clara y ejemplos reales de búsqueda |
| Layout y responsive | 8 | Ancho limitado, márgenes y controles adaptables |
| Interacción | 8.5 | Debounce, flechas, Escape y selección que conserva datos |
| Consistencia | 8 | Tokens compartidos; controles propios del picker |
| Accesibilidad | 9 | Diálogo nativo, labels, anuncios y foco explícito |
| Código | 9 | Páginas de 20, contexto autorizado y respuestas descartables |
| Estados | 9 | Carga, vacío, error, reintento y selección diferenciados |

Después de la segunda revisión se añadió separación superior al bloque de
búsqueda, una observación menor de espaciado. Compartir más estilos entre
controles queda como mejora de consistencia; no se cambió globalmente `Button`.
La revisión estática no equivale a aprobación visual en navegador.

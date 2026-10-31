# Selector de productos del Kardex y acceso desde inventario

Fecha: 21/10/2026.

## Objetivo y diseño

Usuario: personal que continúa una recepción o un traslado y necesita consultar sus movimientos
sin recordar un SKU. Ejemplo real aportado: Azúcar Glass Premium 10kg, PRD-AZU-004, en San Francisco
Gotera. Se conserva la consulta por bodega y el alcance autorizado de empresa y sucursal.

La interfaz se organiza así:

1. Bodega y selector de producto, con el nombre y el SKU visibles.
2. Período, accesos Hoy / 7 días / 30 días y acción de consulta.
3. Tipo, lote y referencia de documento dentro de «Más filtros», con contador de filtros activos.

El selector abre un diálogo nativo con búsqueda, una lista desplazable y cierre por Escape o botón.
Cada fila muestra nombre (14 px), SKU y unidad (12 px), y fecha del último movimiento (12 px).
Se reutilizan los tokens `surface`, `foreground`, `foreground-muted`, `border` y `primary` del ERP,
sin introducir otra paleta. La selección de período utiliza el contraste foreground/surface.
Los nombres largos se envuelven; los resultados tienen al menos 80 px de alto y los controles
principales al menos 44 px. No se añadieron animaciones.

## Comportamiento implementado

- Abrir «Seleccionar producto» carga hasta 20 productos de la bodega, ordenados por la fecha real
  de su movimiento más reciente. Los artículos con saldo pero sin movimiento registrado quedan
  después, con una indicación explícita. No se simulan recientes ni se guarda historial personal.
- Permite buscar por nombre, SKU, código interno y código original, hasta 120 caracteres.
  La búsqueda conserva el alcance de bodega y empresa y el límite de 20 resultados.
- Nombre y SKU aparecen por separado en cada resultado. La búsqueda no depende del `datalist`
  ni de las sugerencias del navegador.
- Elegir un producto inicia su consulta de movimientos con el período y filtros actuales.
- «Más filtros» conserva los filtros adicionales; su contador permite detectar filtros activos
  incluso al cerrar el desplegable. Se pueden limpiar juntos.
- En cada unidad logística del inventario aparece «Ver Kardex». El enlace lleva el ID de bodega
  y de artículo. La pantalla verifica el artículo mediante una búsqueda exacta por UUID dentro
  de esa bodega y realiza la consulta; no depende de un texto de nombre o SKU truncado.
- Un enlace a una bodega fuera de las opciones autorizadas muestra un error y permite volver
  a elegir otra bodega. No se consulta silenciosamente otra bodega como sustitución.
- El selector conserva el producto actual al cancelar. Gestiona carga, error con reintento y
  vacío; permite Tab, Escape y flechas entre resultados. Las respuestas anteriores se descartan
  al cerrar, cambiar búsqueda o desmontar el componente por cambio de empresa, sucursal o bodega.
- Las fechas se validan antes de consultar: ambas deben existir, ser fechas reales y estar en orden.
  Los errores se asocian a los campos y bloquean también las solicitudes iniciadas por código.
- La página física se confirma con la respuesta del servidor. Al cargar otra página se retiran
  los datos anteriores; un fallo conserva el número solicitado para reintentar sin saltar páginas.
- Reintentar una búsqueda devuelve el foco al campo de búsqueda antes de retirar el botón.
  Una región de estado persistente anuncia carga y número de resultados.

## Archivos

- `frontend/src/lib/features/inventory/components/KardexProductPicker.svelte`
- `frontend/src/routes/(app)/inventory/kardex/+page.svelte`
- `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte`
- `frontend/src/lib/features/inventory/kardex.ts`
- `backend/app/api/v1/routers/inventory_kardex.py`
- `backend/app/api/v1/schemas/inventory_kardex.py`
- `backend/app/infrastructure/repositories/inventory_kardex_read_repository.py`

No hay migraciones ni cambios de existencias, costos, movimientos o SKU protegidos.

## Evidencia y límites

Comprobaciones estáticas de los archivos afectados:

- ESLint: salida 0. Se eliminó una variable sin uso detectada en la primera pasada.
- Prettier: salida 0, archivos conformes.
- Ruff: salida 0.
- `git diff --check`: salida 0 para los archivos seguidos indicados en el encargo.
- Svelte-check después del ajuste final: salida 0, 0 errores y las 8 advertencias heredadas
  de `@apply` en `TransferOperationsPage.svelte`, sin diagnósticos nuevos.

### Revisión independiente, primera ronda

Revisión estática, **rechazada: 8.0/10**. Sin evidencia de navegador.

| Categoría | Nota |
|---|---:|
| Distinción visual | 8 |
| Tipografía y contenido | 8.5 |
| Layout y responsive | 8.5 |
| Interacciones | 8 |
| Consistencia | 9 |
| Accesibilidad | 7.5 |
| Arquitectura | 8 |
| Estados y límites | 6.5 |

Se corrigieron en código los tres defectos señalados: página y datos incoherentes después de
un error de paginación; fechas vacías enviadas a la API; pérdida de foco al reintentar y ausencia
de anuncio de resultados. También se simplificó el rótulo del encabezado y se reforzó el contraste
de la pestaña activa. La segunda revisión se registra a continuación.

### Revisión independiente, segunda ronda

Revisión estática, **rechazada: 8.25/10**. Sin evidencia de navegador.

| Categoría | Nota |
|---|---:|
| Distinción visual | 8.5 |
| Tipografía y contenido | 9 |
| Layout y responsive | 8.5 |
| Interacciones | 8 |
| Consistencia | 8.5 |
| Accesibilidad | 7 |
| Arquitectura | 8.5 |
| Estados y límites | 8 |

Se añadió un encabezado de resultados persistente y enfocable: paginación y reintentos mueven
el foco antes de retirar el control utilizado. Se conservó el mismo criterio al paginar o
reintentar valoración y conciliación, y al limpiar filtros. Los botones dentro del Kardex,
incluidos los de componentes importados, tienen una altura mínima de 44 px y un contorno
de foco sólido de 2 px en foreground, limitado a esta pantalla; no se cambió Button global.
El vacío distingue ausencia de movimientos en las fechas de ausencia de coincidencias con
filtros adicionales y ofrece quitarlos. La tercera revisión se registra a continuación.

### Revisión independiente, tercera ronda

Revisión estática, **rechazada: 8.40/10**. Sin evidencia de navegador.

| Categoría | Evidencia y nota |
|---|---|
| Distinción visual | Lista específica de producto/SKU/fecha sin tarjetas decorativas: 8.2 |
| Tipografía y contenido | Nombre, SKU y metadatos legibles; error técnico de conexión pendiente en esa versión: 8.4 |
| Layout y responsive | Proporción 1:2 y diálogo adaptable en código: 8.7 |
| Interacciones | Debounce, teclado, Escape y carga con skeleton: 8.8 |
| Consistencia | Tokens compartidos; bordes de campos demasiado tenues en esa versión: 8.3 |
| Accesibilidad | Foco y labels presentes; delimitación del campo inferior a 3:1 en esa versión: 7.5 |
| Arquitectura | Selector separado, contratos tipados, secuencias y alcance del backend: 8.7 |
| Estados y límites | Vacío y recuperación resueltos; mensaje técnico de red pendiente en esa versión: 8.6 |

Correcciones posteriores a esa revisión:

- Los campos de producto/búsqueda, los filtros y el acceso desde inventario usan borde
  `foreground/50`. Sobre las superficies base de los tokens actuales, el contraste teórico
  estimado del borde es 3.54:1 en claro y 5.10:1 en oscuro. Es un cálculo de los tokens,
  no una medición del renderizado en navegador.
- `kardexErrorMessage` convierte el error de red en una indicación de conexión y reintento,
  sin mostrar el proveedor técnico. Otros errores HTTP conservan su mensaje funcional;
  errores desconocidos usan el texto de recuperación del contexto.

`frontend-quality-studio` limita la revisión a tres rondas. Se alcanzó ese límite sin aprobación:
la versión actual tiene estos últimos ajustes, pero no una cuarta nota ni aprobación inventada.
Quedan pendientes la observación visual y la confirmación de los recorridos indicados abajo.

No se añadieron ni ejecutaron pruebas automatizadas ni se operó sobre datos.
La navegación real, el renderizado en claro/oscuro y los anchos móvil/tablet/escritorio requieren
observación en navegador; no se declaran aprobados por una inspección de código.

## Recorrido manual pendiente

1. Desde el inventario de Gotera, abrir «Ver Kardex» del azúcar: comprobar bodega, producto y consulta.
2. Abrir el selector sin escribir: comprobar que los productos se ordenen por sus movimientos reales.
3. Buscar por nombre, SKU y códigos; elegir producto y comprobar que su consulta se inicia.
4. Buscar algo inexistente y volver a recientes; simular una carga fallida y usar Reintentar.
5. Cambiar de bodega o empresa durante una búsqueda; comprobar que no aparecen resultados antiguos.
6. Revisar Escape, cancelación, retorno del foco, Tab y flechas; revisar móvil y ambos temas.
7. Cambiar períodos, desplegar filtros, limpiar filtros y comprobar los parámetros de la consulta.
8. Abrir un enlace fuera del alcance o con un artículo no presente en la bodega: comprobar el aviso.

El cierre integral B01–B08 conserva su estado anterior.

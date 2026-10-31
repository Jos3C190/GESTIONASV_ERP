# Bloque 2 — Lotes y etiquetas de Grupo Lorena

Fecha: 28/10/2026. Continúa el plan maestro de compras e inventario.

## Resultado

- QR, Code 128 y etiqueta completa comparten el generador de vista previa y
  papel. Todos muestran nombre/código del producto, lote de recepción, fecha de
  recepción, vencimiento si existe y unidad logística. La completa añade cantidad,
  lote del fabricante y presentación. No se inventa vencimiento cuando no existe.
- `INT-004` es un código interno de producto válido. Code 128B representa ese
  código; el lote visible distingue recepciones y el QR consulta la unidad.
  No se sustituyeron SKU, códigos internos ni identidades de lotes existentes.
- Observaciones opcionales de hasta 160 caracteres. Cada solicitud conserva
  sus observaciones en el snapshot y auditoría; los reintentos incluyen la nota
  normalizada en su identidad. El texto se escapa antes de imprimir.
- Medidas ofrecidas: QR 50×70, 60×80 y 80×80 mm; barras 80×50, 50×50 y 80×80 mm;
  completa 80×80, 100×125 y 100×150 mm. Medidas personalizadas conservan controles
  de ancho de barras/QR y desbordamiento antes de registrar una impresión.
- Copias 1–100, con validación asociada al campo. Las copias repiten la misma
  etiqueta y no crean lotes, fracciones ni movimientos. Un registro de impresión
  tampoco acredita colocación física: permanece la confirmación explícita.
- Diálogo en dos columnas en escritorio, controles con borde de contraste,
  acciones visibles al desplazar y apertura de vista a tamaño real sin registrar
  otra impresión. En móvil se usa una columna.
- Almacenes permite filtrar las unidades con etiqueta pendiente de imprimir o
  confirmar; al confirmar y recargar deja de aparecer la unidad en ese filtro.
- Para compras del flujo `retaceo_before_inventory`, la vista previa y las
  impresiones exigen retaceo cerrado. Se preserva el tratamiento histórico del
  flujo anterior. Continúan RBAC, empresa, sucursal y asignación de bodega.

## Verificación

- Backend: 34 pruebas unitarias de etiquetas/lotes aprobadas. Nueva prueba con
  PostgreSQL desechable y API real: recepción → retaceo manual → calcular/verificar/
  cerrar → verificación física → imprimir/repetir/reimprimir. Comprueba fecha/lote
  persistidos, existencias y número de movimientos sin cambios, rechazo entre
  empresas, falta de permiso y bloqueo con un cálculo verificado pero no cerrado.
- Regresión de backend: 71 unitarias aprobadas al incluir capacidad y seguridad
  de recepción, además de la prueba del flujo completo con PostgreSQL.
- Frontend: 44 pruebas aprobadas en generador, diálogo y panel de unidades.
  Se actualizaron pruebas antiguas al visor actual, manteniendo comprobaciones
  de respuestas tardías, revocación, contexto, confirmación e idempotencia.
- Svelte-check: cero errores; ocho avisos previos de `@apply` en
  `TransferOperationsPage.svelte`. Ruff y ESLint de archivos afectados aprobados.
- Chromium/Edge: las tres variantes en 375, 768 y 1280 px, temas claro/oscuro;
  sin desbordamiento horizontal ni errores de ejecución. Diez documentos de papel
  (incluye dos copias) sin recortes en los datos de prueba, verificación de copias
  inválidas, retaceo pendiente y apertura del papel a tamaño real.
- Evidencia local: `tmp/ers-v1/lotes-etiquetas-2026-10-28/qa-results.json`, PNG y PDF
  correspondientes. Son datos ficticios; no se alteraron recepciones reales.

## Límites y continuidad

- No requiere migración. Los registros históricos se conservan; no se regeneran
  lotes al imprimir ni reimprimir. El formato para una impresora real requiere
  seleccionar su papel y escala al 100 %.
- La evidencia visual corresponde a navegador y papel virtual. Falta comprobar
  la impresora física y el lector del usuario; no se certifica su funcionamiento.
- No representa el cierre del proyecto. El bloque 3 debe separar la preparación
  del producto del alta final: actualmente verificar recepción aún registra
  existencias en cuarentena antes de terminar la ubicación. Quedan la pantalla
  simplificada del bodeguero, ingreso al colocar, inventario, Kardex/conciliación
  y la demostración de tres entradas con costos distintos.

## Revisión visual

La primera revisión independiente detectó contraste insuficiente en campos,
recuperación equivocada para copias inválidas y poco espacio de revisión. La
segunda detectó asociación de errores de medidas y foco en invalidación de QR.
Se corrigieron los controles, la validación local, el foco y el diálogo con vista
ampliable. La tercera revisión independiente aprobó con **8,56/10**:

| Categoría | Nota | Evidencia |
| --- | --- | --- |
| Distinción visual | 8,3 | Papel monocromo y jerarquía de producto/código/lote |
| Tipografía y contenido | 8,4 | Datos de trazabilidad completos en los tres formatos |
| Layout y responsive | 8,3 | Dos columnas en escritorio y nueve combinaciones sin desbordamiento |
| Interacción | 9,0 | Foco en Cancelar y retorno al disparador con Escape |
| Consistencia | 8,8 | Tokens, controles de 44 px y papel en milímetros |
| Accesibilidad | 9,0 | Campos/errores asociados; contraste de control 3,95:1 |
| Código | 8,5 | Generación compartida, escape y protección de respuestas obsoletas |
| Estados y límites | 8,2 | Bloqueos por copias, medidas, retaceo y ajuste físico |

La observación no bloqueante sobre mensajes de medidas se corrigió centralizando
los mínimos por formato: campo, atributos HTML y validación general usan la
misma función/constantes. La oportunidad de reducir desplazamiento en tablet se
conserva como mejora de diseño futura. La ruta temporal de QA se retira antes
de entregar; las evidencias permanecen en la carpeta documentada.

## Corrección posterior — producto eliminado con existencias

La unidad `HU-F204E71DDD3E4597` conserva dos unidades de un producto de
demostración eliminado del catálogo el 22/10/2026. El filtro global de borrado
lógico ocultaba el producto en la consulta de etiquetas y provocaba un 404
incorrecto, aunque la unidad, el lote y la compra COM-00018 existen.

Las consultas por unidad y por detalle de lote ahora leen los datos históricos
del catálogo mediante sus relaciones persistidas. Se mantienen el alcance de
empresa, los permisos, el estado de existencias y la validación de retaceo. No
se restauraron productos, no se modificaron cantidades ni movimientos y no se
generó ninguna impresión real durante el diagnóstico.

Verificación: 34 unitarias y dos escenarios completos con PostgreSQL aprobados
(producto visible y producto eliminado). Ambos comprueban vista previa por
unidad/detalle, impresión, reintento, reimpresión, aislamiento de empresa y
permisos. El producto eliminado permanece eliminado y la cantidad no cambia.
La consulta de solo lectura sobre la unidad reportada devolvió correctamente
su nombre, código, lote y fecha de recepción.

## Retoque visual puntual — QR y Code 128

A petición del usuario se centraron los datos de trazabilidad de las dos viñetas,
se separó el lote en su propia línea y se equilibró el título y el espaciado. Un
separador fino distingue el código del bloque de lote/fechas/unidad. La etiqueta
completa conserva su diseño. Se mantienen el papel en milímetros, las dimensiones
de los símbolos, sus márgenes de lectura y todos los datos de trazabilidad.

Se revisaron 14 documentos de papel en Edge, incluidos los tamaños existentes,
dos copias y el nombre/lote largos de las capturas, con y sin observaciones.
Todos caben sin recortes. Pasaron las 44 pruebas de generador/diálogo/panel y
ESLint. Evidencias en `tmp/ers-v1/etiquetas-retoque-2026-10-28/`.

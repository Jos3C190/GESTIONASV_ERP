# Formatos y medidas de etiquetas de inventario

Fecha: 21/10/2026. Alcance: impresión de una unidad logística desde Almacenes.

> Actualización del 28/10/2026: este documento conserva la entrega original.
> Las viñetas QR y Code 128 ahora incorporan producto, lote, recepción y
> vencimiento cuando corresponde; sus medidas mínimas cambiaron para conservar
> esos datos legibles. Véase [el cierre del bloque 2](bloque-02-lotes-etiquetas-2026-10-28.md).

## Resultado implementado

En el diálogo de etiqueta, la sección **Configuración de impresión** reúne contenido, tamaño y copias. Se mantiene el formato inicial de 100 × 125 mm. La vista previa muestra solamente el contenido seleccionado, dentro de un papel con la proporción elegida.

| Contenido | Incluye | Medidas predefinidas, ancho × alto |
| --- | --- | --- |
| Viñeta QR | Solo el QR de trazabilidad de la unidad | 25 × 35, 35 × 35, 50 × 50, 80 × 80 mm |
| Viñeta Code 128 | Código de barras y código interno legible del producto | 50 × 25, 50 × 50, 80 × 40, 80 × 80 mm |
| Etiqueta completa | Producto, HU, código interno, QR, lotes, recepción, cantidad, presentación y vencimiento cuando existen | 80 × 80, 100 × 125, 100 × 150 mm |

También hay **Medidas personalizadas**: ancho entre 25 y 200 mm y alto entre 20 y 200 mm, en enteros. La etiqueta completa requiere al menos 80 × 80 mm; el QR, 25 mm de alto como mínimo; Code 128, al menos 35 mm de ancho y espacio suficiente para el código concreto. Son límites del producto, no una certificación de lectura en cualquier impresora.

Las copias siguen limitadas a 1–100. Cambiar el tamaño no cambia la cantidad de inventario. La impresión no libera la unidad ni confirma automáticamente que se haya colocado su etiqueta.

## Cómo usarlo

1. Almacenes → Ver inventario → Ver QR o Revisar etiqueta.
2. Elegir **Contenido**.
3. Elegir **Tamaño** o introducir ancho y alto personalizados.
4. Comprobar la vista previa y corregir cualquier aviso de espacio.
5. Indicar copias y pulsar Imprimir etiqueta o Reimprimir etiqueta.
6. En la ventana de impresión, seleccionar el papel correspondiente, escala **100 % / tamaño real**, sin encabezados ni pies del navegador. El controlador debe ofrecer el tamaño seleccionado; la aplicación no puede cambiar por sí sola la configuración física de la impresora.
7. Confirmar la colocación únicamente después de colocar la etiqueta. Cerrar o cancelar la ventana de impresión no confirma colocación ni elimina la solicitud ya registrada.

Code 128 identifica el **producto** mediante su código interno. El QR consulta el origen y los movimientos de la **unidad logística**. La ayuda de cámara, lector USB y acceso por red se muestra como información secundaria cuando el formato contiene QR.

## Implementación y controles

- Un generador compartido construye el documento de vista previa y el de impresión. `@page` y cada etiqueta reciben el ancho y alto seleccionados en **mm**, con una etiqueta por página. La adaptación de la vista a la pantalla no modifica el tamaño del papel.
- Antes de registrar la impresión se esperan fuentes e imágenes y se comprueba el desbordamiento. No se comprime automáticamente el texto para hacerlo caber. Si no cabe, se pide un papel mayor o menos contenido.
- QR mantiene cuatro módulos de margen. Se aplica un umbral preventivo de 0,30 mm por módulo, incluyendo el espacio previsto para el símbolo; si el enlace requiere más espacio se propone una viñeta mayor.
- Code 128B utiliza caracteres ASCII imprimibles, diez módulos de margen a cada lado y un cálculo preventivo de ancho con módulo mínimo de 0,25 mm. El backend vuelve a validar el código y el papel. Estos controles no sustituyen una comprobación de escaneo con el equipo final.
- El documento final utiliza los datos de `label_snapshot` devueltos por el servidor. Las respuestas de otra unidad, sesión o contexto no abren una impresión posterior. La invalidación de QR y la impresión se bloquean mutuamente mientras se procesan.
- Las solicitudes incluyen `layout: { content, width_mm, height_mm }`. El historial y la auditoría guardan `label_snapshot.print_layout`; la clave idempotente incluye contenido y medidas, además del destino, copias, fecha y motivo. Los reintentos de una solicitud sin respuesta conservan su clave mientras el diálogo sigue montado.
- `layout` es opcional para conservar la compatibilidad con clientes anteriores. Las solicitudes que lo omiten conservan su fingerprint previo. No se necesita migración: el formato se añade al snapshot JSON existente.
- Se mantienen permisos, aislamiento por empresa/sucursal, revisión vigente y confirmación de colocación. No se ejecutaron operaciones de inventario ni cambios de SKU durante este encargo.

## Comprobaciones y evidencia

Evidencia local: `tmp/ers-v1/2026-10-21-formatos-etiquetas/`.

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Ruff sobre los cuatro archivos Python afectados | Aprobado, sin incidencias finales | `ruff-check.log`, `ruff-check.exit` |
| ESLint sobre componentes, generador, tipos y servicio | Aprobado, salida 0 | `eslint.log`, `eslint.exit` |
| Formato Prettier sobre los siete archivos frontend afectados | Aprobado | `prettier-check.log`, `prettier-check.exit` |
| Svelte/TypeScript del proyecto | 0 errores, 8 advertencias existentes en 1 archivo | `svelte-check.log`, `svelte-check.exit` |
| Espacios del diff en archivos previamente versionados afectados | Aprobado | `diff-check.log`, `diff-check.exit` |
| Crítico UI independiente, segunda revisión | Aprobado **solo para revisión estática**, 8,56/10 | `critico-final.md` |

La primera revisión detectó contraste insuficiente en avisos y exceso de ayuda de QR en modo Code 128. Se corrigió usando texto principal sobre fondos de aviso y ayuda contextual desplegable. La segunda revisión no encontró un defecto funcional bloqueante demostrable por lectura del código.

**No se añadieron ni ejecutaron suites de pruebas en este encargo.** No hay evidencia nueva de navegador, PDF impreso, impresora o lector. Por ello, el resultado visual renderizado y el tamaño/lectura físicos quedan pendientes de comprobación. Este cambio no declara cerrado el conjunto B01–B08.

## Comprobación manual pendiente

Estos casos son instrucciones de aceptación, **no resultados ejecutados**. No requieren impresora ni lector físicos: puede revisarse la salida a PDF desde el navegador.

| Caso | Acción | Resultado esperado |
| --- | --- | --- |
| F01 | Seleccionar QR 25 × 35, 50 × 50 y 80 × 80 | Solo el QR; proporción y medidas coincidentes. Si el enlace excede la densidad permitida, aviso para elegir un tamaño mayor y ninguna solicitud registrada |
| F02 | Elegir Code 128 50 × 25 con código corto, por ejemplo INT-003 | Barras y código legible; sin QR ni instrucciones de cámara. Un código más largo puede requerir 80 mm u otra medida |
| F03 | Etiqueta completa 100 × 125 y 80 × 80 | Datos completos según snapshot. Si el contenido no cabe, aviso y bloqueo antes de registrar |
| F04 | Medida personalizada, cerrar y reabrir el diálogo para otra unidad | Tamaño conservado correctamente identificado como personalizado; datos de la nueva unidad |
| F05 | Pedir dos copias y revisar las páginas de salida | Dos etiquetas, una por página, en el papel elegido; verificar propiedades del PDF y que no haya página vacía extra |
| F06 | Introducir ancho 24/201, alto 19/201, copias 0/101 o fracciones | Aviso y ninguna impresión registrada con valores inválidos |
| F07 | Cancelar la impresión y volver a imprimir | Se distingue solicitud registrada de impresión física; reimpresión disponible; no se confirma colocación automáticamente |
| F08 | Reimprimir una unidad con etiqueta ya confirmada | Se registra el nuevo formato; no se reinicia su revisión ni se modifica su disponibilidad o existencia |
| F09 | Consultar con usuario sin permiso de recepción | Puede consultar el QR si tiene lectura; no obtiene controles para registrar impresiones |
| F10 | Bloquear ventana emergente o cambiar de contexto durante la preparación | Mensaje recuperable o cancelación de la operación visual; no se imprime una unidad/contexto diferente |

Registrar captura, formato seleccionado, identificación de unidad, resultado y fecha por caso antes de marcarlo aprobado.

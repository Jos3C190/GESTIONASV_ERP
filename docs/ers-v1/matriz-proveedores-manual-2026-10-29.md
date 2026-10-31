# Matriz de proveedores del consolidado — elección manual

29/10/2026. Ampliación solicitada por Rodrigo después del bloque 6: únicamente
la matriz global de proveedores. No incluye recomendación, ordenación por mejor
precio, selección automática, cambios de Gerencia ni abastecimiento.

## Uso y alcance

Abre un consolidado en **Consolidados de compra**, ve a **Comparar y adjudicar por
producto** y pulsa **Matriz de proveedores** junto a **Por producto**.

- Filas: todos los productos/unidades del consolidado; búsqueda por nombre o código.
- Columnas: proveedores que tienen alguna respuesta recibida en la comparación.
  Un proveedor que todavía no respondió a ningún producto sigue en el seguimiento
  de RFQ, no se presenta como una oferta recibida.
- En teléfonos se elige qué proveedor consultar y se conserva la columna del
  producto al lado. En pantallas desde 640 px se muestran todas las columnas con
  desplazamiento horizontal dentro de la tabla.
- Cada cruce muestra las ofertas de ese proveedor para ese producto, conservando
  todas las cotizaciones/versiones disponibles y sus estados. Si no hay respuesta
  para el cruce, aparece **Sin oferta recibida**.
- Cada oferta conserva precio y moneda original, cantidad ofrecida, disponibilidad,
  plazo y total de esa cantidad cotizada. El desplegable muestra descuento,
  impuesto, vigencia, pago, notas y cargos compartidos de cotización.
- Los totales de líneas con cantidades o monedas distintas no se suman ni se
  clasifican. Los cargos compartidos se identifican por separado y no se reparten
  de forma ficticia entre productos. Cantidad ofrecida cero se presenta como
  **Sin cantidad ofrecida**, no como una oferta gratuita.
- **Ver oferta** vuelve a la ficha correspondiente, enfoca y desplaza al proveedor
  elegido. La cantidad y el motivo que se estaban escribiendo, la búsqueda de
  producto y el proveedor consultado permanecen al cambiar entre las dos vistas.
  La adjudicación sigue usando el formulario y
  endpoint existentes, con decisión explícita y permisos vigentes.

La matriz es global **dentro del consolidado consultado**; no mezcla compras,
empresas ni catálogos de proveedores ajenos a esa gestión.

## Diseño y verificación

Vista adicional en la sección existente. Cabecera y columna del producto fijas,
desplazamiento limitado a la tabla, controles táctiles de 44 px y foco visible.
Se reutilizan los tokens `surface`, `surface-muted`, `foreground`,
`foreground-muted`, `border` y `primary` de ambos temas del ERP. Se conserva el
estado de carga/error/reintento del contenedor; la matriz tiene vacío sin ofertas
y búsqueda sin resultados con acción para limpiar. El vacío permite actualizar
las ofertas; un fallo de carga presenta un único mensaje y botón de reintento.
Los campos usan `control-border`, con contraste medido de al menos 3:1 frente a
su fondo en ambos temas. En teléfonos se reduce la introducción para priorizar
la consulta de ofertas.

Implementación dividida en `PurchaseConsolidationSupplierMatrix.svelte` y
`PurchaseConsolidationMatrixOffer.svelte`, reutilizando el tablero ya autorizado.
No cambian API, migraciones, cálculos financieros, permisos ni datos comerciales.

- 18 pruebas Vitest aprobadas: 11 de adjudicación (6 nuevas para la matriz) y
  7 del detalle de consolidado. Cubren varias versiones, huecos por proveedor,
  monedas distintas, conservación del borrador y foco, consultas sin permiso
  de adjudicar, consolidado cerrado, error/reintento, búsqueda y cantidad cero.
- ESLint sobre los archivos de la ampliación: sin errores.
- `svelte-check`: 0 errores; 8 avisos CSS preexistentes en TransferOperationsPage.
- La región desplazable recibe foco para permitir desplazamiento por teclado;
  la excepción puntual a la advertencia de Svelte se comenta en su marcado.
- Recorrido en navegador a 1440, 768 y 375 px, con temas claro y oscuro:
  cero errores JavaScript y cero escrituras comerciales. Se comprobó el
  desplazamiento por teclado, la columna móvil completa, el foco y la
  conservación tanto del borrador manual como de los filtros de la matriz.
- Contraste medido: controles 3.95:1 en claro y 5.32:1 en oscuro; distintivo de
  decisión manual 16.48:1 y 17.05:1, respectivamente.

Evidencias visuales y veredicto independiente se conservan en
`tmp/supplier-matrix-review/`. El recorrido de revisión monta el componente real
con un tablero de prueba identificado como fixture; no adjudica ni crea órdenes
en la base de demostración. El backend de adjudicación existente no se modifica.

## Revisión independiente final

Tres rondas de revisión. Se corrigieron columnas cortadas en teléfonos, contraste
de controles y distintivos, vacío sin acción de actualización, mensajes duplicados
de error y pérdida de filtros al volver desde una oferta.

| Categoría | Puntaje | Evidencia del crítico |
|---|---:|---|
| Distinción visual | 8.4 | Demanda fija, proveedores en columnas e importes destacados, sin recomendaciones visuales |
| Tipografía y contenido | 8.6 | Jerarquía de importes y distinción explícita de cantidad, moneda y disponibilidad |
| Layout y responsive | 8.2 | Comparación simultánea en escritorio, contexto fijo en tablet y columna completa en teléfono |
| Interacción | 8.6 | Búsqueda, condiciones desplegables y retorno con foco, borrador y filtros conservados |
| Sistema de diseño | 9.0 | Tokens y escalas consistentes entre temas y estados |
| Accesibilidad | 8.8 | Tabla semántica, etiquetas, teclado, foco y contraste medido |
| Código y arquitectura | 8.7 | Responsabilidades separadas, tipos y formateadores reutilizados, pruebas pertinentes |
| Estados y casos límite | 8.9 | Vacíos, error/reintento, carga, éxito y datos no informados explícitos |

**Promedio: 8.65/10. Aprobado; ninguna categoría inferior a 7.**

Límites visuales no bloqueantes: en teléfonos la introducción aún requiere
desplazamiento y la columna de producto de 112 px reparte nombres largos en varias
líneas. Se conserva este diseño para mostrar producto y proveedor a la vez sin
cortar importes. La auditoría no certifica el resto del ERP ni un recorrido de
adjudicación contra datos reales: ese recorrido se revisó con fixtures.

## Para la exposición

«Aquí veo los productos de este consolidado frente a las respuestas de los
proveedores. Reviso cantidades, monedas y condiciones; abro la oferta elegida y
registro manualmente cuánto comprar y por qué.»

El resto de la preparación sigue siendo elegir los documentos de demostración
y ensayar el guion de solicitud → compra → retaceo → ubicación → inventario →
Kardex. La regularización histórica de COM-00024 conserva los límites documentados
en el bloque 6 y no se aplica como parte de esta matriz.

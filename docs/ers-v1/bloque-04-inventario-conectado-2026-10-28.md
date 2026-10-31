# Bloque 4: inventario conectado de Grupo Lorena

Fecha local: 28/10/2026. Alcance: consultas de inventario, ubicación, lotes,
reubicación y apertura individual. El Kardex ampliado y sus exportaciones
continúan en el bloque 5; la aceptación de tres ingresos sigue en el bloque 6.
Validación final del bloque: 29/10/2026.

## Diseño y usuarios

El bodeguero conserva sus cuatro tareas principales. Dentro de Existencias puede
consultar Por ubicación, Unidades, Lotes y Mapa de bodega. No necesita recorrer
las cuatro consultas para completar una recepción. Una cuenta con permisos de
valoración y recepción puede registrar un saldo inicial individual.

Se reutilizan los tokens, Button y los componentes existentes. La lista de
existencias resalta producto, cantidad/unidad y ubicación; en tablet usa columnas
compactas y en teléfono reparte las acciones en dos columnas. El esquema de
espacios es navegable con teclado, por pasillo, estante, nivel y posición. No
representa distancias reales. Su detalle contiene capacidad y existencias reales.

## Comportamiento

- **Existencias** lee inventory_balances positivos, con filtros y paginación en
  servidor. No suma HU a esos saldos ni mezcla cantidades de diferentes unidades.
  Incluye registros antiguos sin lote de recepción. Las unidades en preparación
  del flujo nuevo permanecen en su cola propia, sin incorporarse al saldo antes
  de confirmar ubicación.
- **Lotes** consulta la recepción, fecha local, compra, productos y unidades
  abiertas de esa bodega. La búsqueda de producto, compra o lote se aplica antes
  de paginar. Enlaces a compras solo se presentan a quien tiene su permiso.
- **Mapa** conecta cada código con contenido y capacidad. Se puede entrar desde
  una existencia, incluso si su espacio no está en la primera página. Seleccionar
  un espacio dirige el foco a su encabezado. No presume capacidades ni interpreta
  una medida pendiente como cero.
- **Reubicar**, dentro de Unidades → Otras acciones, permite mover una unidad
  disponible completa a otro espacio de la misma bodega. Exige motivo, conserva
  cantidad/lote/costo y reutiliza las validaciones de capacidad, permisos e
  idempotencia del motor. El movimiento guarda el motivo en su referencia.
- **Históricos**: COM-00020 y COM-00021 se conservan detrás de un control explícito
  por página. LOT-COM-00022 y otros pendientes de ubicación del flujo antiguo
  quedan dentro de un desplegable en Unidades. Su resumen de existencias sin
  recepción vinculada también queda plegado y explicado con términos operativos.
  No se canceló, completó, reasignó ni borró ninguno para vaciar la pantalla.

## Saldo inicial individual

Es distinto del corte inicial de valoración de la empresa. Requiere que este
último esté configurado y que el producto tenga identidad/unidad base inventariable.

El formulario recoge producto, ubicación activa, cantidad base, costo unitario,
medidas físicas totales, fecha, referencia del acta, motivo y lote/vencimiento
cuando apliquen. Una revisión previa separa la captura de la confirmación.
Esa revisión reúne producto, bodega/espacio, cantidad, costo, valor total,
fecha, medidas y respaldo. El foco pasa al resumen y regresa al selector de
producto si se vuelve a editar, conservando la captura.

La confirmación crea un movimiento físico `opening` y un asiento valorado
`opening` en la misma transacción. Actualiza cantidad, valor y promedio, con
auditoría obligatoria de los datos y referencia `SI:<documento>`. El conteo
inicial verificado ingresa disponible con medidas documentadas; no simula una
compra ni exige un retaceo de importación para existencias anteriores.

El bloqueo es por empresa/producto: revisa movimientos físicos, valoración,
unidades incluso en preparación y saldos. Llegar a existencia cero no habilita
otra apertura. El bloqueo de empresa usado por los movimientos físicos y
valorados serializa aperturas concurrentes. Repetir la misma solicitud devuelve
el mismo movimiento; cambiar el contenido con su clave se rechaza.

Fecha operativa entre el corte y hoy en El Salvador. La comprobación de ingreso
de una unidad que vence hoy también usa el día local, no el día UTC adelantado.

El endpoint exige `inventory:valuation` y `inventory:receive`, más alcance real
de empresa/sucursal/bodega. Rodrigo no recibe esos permisos ni el botón de apertura.
Las consultas de existencias, lotes y espacios no exponen importes.

## Persistencia y entorno

Migración `0097`: amplía el tipo del registro físico para aceptar `opening`.
No actualiza registros comerciales ni movimientos existentes. El downgrade se
rechaza si ya hay aperturas; no las renombra ni elimina para permitirlo.

Respaldo previo local: `tmp/gestionasv-before-0097.dump` (formato pg_dump custom).
Se aplicó `alembic upgrade head`; el entorno está en 0097.
Los casos que crean o mueven inventario usan exclusivamente erp_db_test.

## Validación

- Prueba E2E: 80 × 6.80 = 544, una sola entrada física/valorada; reintento sin
  duplicación, cambio de contenido rechazado, bodega incorrecta rechazada,
  bodeguero sin apertura, respuesta de stock sin costos, búsqueda literal `%`,
  reubicación sin variar valor/cantidad, agotamiento sin permitir nueva apertura
  y dos aperturas simultáneas con un único éxito. Incluye vencimiento en el día
  local de ingreso.
- Regresión de preparación, movimientos y cálculos de Kardex.
- Backend: 11 pruebas dirigidas aprobadas. Después de añadir la exigencia de
  referencia a la reubicación, la prueba E2E de apertura y reubicación volvió a
  aprobar, incluyendo carrera entre aperturas, vencimiento local e idempotencia.
- Frontend: filtros enviados al servidor, errores/vacíos/reintentos, localización
  de un espacio fuera de página, foco y capacidad, revisión de apertura y clave
  estable ante fallo de red, reubicación y ausencia de destinos elegibles.
- Frontend: 60 pruebas aprobadas en cinco archivos; ESLint dirigido y Ruff sin
  errores. Incluye foco de la confirmación, vuelta a editar y resumen 80 × 6.80.
- `svelte-check`: cero errores; ocho avisos CSS preexistentes de TransferOperationsPage.
- Navegador Edge con Rodrigo: consultas reales en 1280, 768 y 375 px; HTTP 200,
  cero errores JavaScript y cero escrituras de inventario. Evidencia en
  `tmp/block4-review/result.json` y capturas de esa carpeta.
- Las dos capturas administrativas de apertura son fixtures de visibilidad de
  permisos en el cliente, expresamente identificadas en su nombre y JSON. No se
  modificaron permisos del servidor y el POST de apertura fue bloqueado en ese
  navegador. La autorización y la confirmación real administrativa se probaron
  mediante la aplicación real en la base E2E aislada.

## Guion para Rodrigo

1. En Existencias, buscar un producto y mostrar cantidad, estado y ubicación.
2. Pulsar su ubicación para abrir espacio, contenido y capacidad.
3. Abrir Lotes para mostrar la compra de origen y las unidades actuales.
4. En Unidades, enseñar etiqueta y, si se necesita mover físicamente una unidad,
   Reubicar con su motivo. Consultar el cambio en Movimientos.
5. Con cuenta administrativa y un producto sin historial, revisar y confirmar
   un saldo inicial; comparar su cantidad y valor en Kardex/valoración.

Los filtros y consultas no son pasos obligatorios adicionales de recepción.
Los históricos no se vuelven a recibir para que dejen de aparecer en pantalla.

## Revisión visual

Primera revisión independiente: 8.21/10, rechazada por densidad en tablet,
continuidad de foco y vacíos de ubicaciones. Se ajustaron esas observaciones.
Segunda revisión: 8.25/10; solicitó mostrar antes el primer registro en móvil y
reunir los datos de apertura en un resumen con continuidad de foco. Se compactaron
cabecera, navegación y filtros; el recorrido en navegador comprueba que el primer
registro completo cabe en 960 px de alto. El resumen sustituye el formulario al
revisar y conserva los datos al volver.

Tercera revisión independiente: **aprobado, 8.5625/10**, sin categoría inferior
a 7. Comparación con la claridad operativa de Linear, Vercel y Stripe:

| Categoría | Nota | Evidencia de la revisión |
| --- | --- | --- |
| Distinción visual | 8 | Filas, cantidades y esquema de pasillos propios del trabajo de bodega; dirección sobria |
| Tipografía y contenido | 9 | Producto, cantidad, ubicación y resumen 80 × 6.80 = 544 legibles |
| Layout y responsive | 8 | Tres columnas en tablet y primer registro completo antes de 810 px en móvil; navegación principal horizontal |
| Motion e interacción | 8.5 | Diálogo nativo, revisión previa, foco de destino y vuelta a editar |
| Sistema de diseño | 9 | Tokens, controles, radios y estados compartidos |
| Accesibilidad | 8.5 | Labels, anuncios, foco y movimiento reducido; contraste secundario claro 5.74:1 y oscuro 7.37:1 |
| Código | 8.5 | Responsabilidades separadas, paginación, protección de solicitudes e idempotencia |
| Estados y límites | 9 | Carga/vacío/error/éxito; explicación sin destinos y captura conservada al reintentar |

Reserva de la evaluación resuelta en la validación del 29/10: la lista de espacios
debe terminar de sustituir su skeleton antes de dirigir foco y desplazamiento al
encabezado seleccionado. Se añadió esa condición y el recorrido real de Edge
comprueba tanto `activeElement` como que el encabezado queda dentro del viewport
móvil. El recorrido completo volvió a terminar con HTTP 200, sin errores JS y sin
escrituras de inventario; la regresión dirigida de nueve consultas también aprobó.
La pestaña Movimientos puede requerir deslizar la navegación principal en móvil.

# Historial de movimientos para el bodeguero

## Alcance y diseño

Rodrigo consulta lo ocurrido en la bodega asignada desde la pestaña
**Movimientos** de Inventario. No cambia existencias, costos ni registros
históricos. Se reutilizan el permiso `inventory:read`, el alcance de bodega y
el historial existente; no se amplía el rol ni se agregan migraciones.

La vista mantiene los tokens del ERP para fondo, texto, bordes, foco y estados.
Jerarquía: bodega seleccionada → tarea → producto/período → filtros adicionales
→ resultados. Texto de 14 px y metadatos de 12 px; controles de al menos 44 px.
En escritorio los registros se alinean en columnas; en móvil se apilan dentro
de cada movimiento. Las tareas de bodega forman una grilla de dos columnas en
móvil. No se cambia la consola del administrador.

## Consulta

- Período inicial: últimos 30 días del calendario de El Salvador.
- Desde/Hasta, Hoy, 7 días y 30 días; limpiar permite revisar todo el historial.
- Búsqueda por nombre de producto, SKU o unidad logística.
- Tipo de movimiento; sentido entrada/salida/interno; lote de recepción o
  fabricante; referencia de origen del movimiento.
- Fecha y responsable, producto, recorrido, cantidad y detalle de trazabilidad.
- Páginas de 25 registros; se solicita uno adicional para detectar otra página.
- Carga, vacío recuperable, error y reintento; cancelación de consultas y descarte
  de respuestas de un contexto anterior.

Los filtros se aplican en PostgreSQL antes de paginar. Las fechas incluyen el
día completo en `America/El_Salvador`. Los caracteres `%` y `_` de una búsqueda
se interpretan literalmente. Una reubicación dentro de la bodega se presenta
como interna, no como una entrada de mercancía nueva.

El endpoint existente conserva el contrato de lista y sus valores por defecto.
Los parámetros nuevos son opcionales. Los datos físicos no incluyen costos.
Se conserva la validación de empresa, sucursal y bodega asignada en el servidor.

## Verificación

- 23 pruebas frontend de servicio, fechas locales, sentido, filtros, error,
  paginación, detalle y descarte de respuestas antiguas, incluida regresión del detalle de Kardex.
- Una prueba E2E sobre PostgreSQL aislado: límites de medianoche, filtros
  combinados, caracteres literales, paginación, contrato anterior y rechazo de
  otra bodega/empresa y del Kardex valorado.
- 13 pruebas backend de regresión de Kardex, lotes y metadatos.
- Svelte: cero errores y ocho advertencias CSS preexistentes en Traslados.
- Ruff y ESLint de los archivos de esta funcionalidad aprobados.

Las pruebas automatizadas de escritura de fixtures usan exclusivamente la base
aislada de tests. La comprobación de la cuenta real solo consulta información.

## Revisión de uso y presentación

Las primeras revisiones detectaron filas demasiado largas en tablet, filtros
avanzados que podían quedar ocultos y una diferencia de zona horaria entre el
listado y el detalle. Se compactaron las filas, se agruparon cantidad y acción,
se dejaron chips de filtros aplicados y se centralizó la fecha en el formateador
de El Salvador. Los lotes largos tienen corte seguro en el detalle.

Los badges azul/ámbar/rojo de texto pequeño usan ahora tinta de primer plano sobre
el fondo teñido: las combinaciones anteriores no llegaban a 4.5:1 en tema claro.
Se conserva el color de fondo para distinguir los tipos y la etiqueta textual
para no depender del color.

La comprobación de navegador usa la cuenta real de Rodrigo y una zona horaria
Asia/Tokyo para verificar explícitamente la hora salvadoreña. Incluye 375, 768 y
1280 px, filtros, teclado, detalle, vacío, fallo 503 simulado y recuperación.
La evidencia se guarda sin credenciales en `tmp/warehouse-movements/`.

Durante la actualización se limpió la caché de Vite y se retiró la precarga
especulativa de rutas SSR del servidor de desarrollo. SvelteKit inicializa esas
rutas cuando se necesitan; no se modificó la configuración de producción.

## Resultado de navegador y revisión independiente

Cuenta real: `rodrigo.molina.bodega`, Bodega Matriz Grupo Lorena. El recorrido
final terminó sin errores JavaScript: consulta filtrada 200, detalle con fecha
SV desde navegador en Tokyo, vacío 200, fallo 503 simulado y recuperación 200.
Se verificó ausencia de desbordamiento en 375, 768 y 1280 px y detalle móvil.
Contraste medido de ocho tipos en ambos temas: mínimo **5.28:1 claro** y
**7.11:1 oscuro**. El registro de resultados y capturas no contiene credenciales.

El juez independiente rechazó las dos primeras rondas (8.19 y 8.25) por densidad,
visibilidad de filtros y contraste. Tras corregirlas, la tercera revisión quedó
**aprobada: 8.56/10**, sin categoría inferior a 7.

| Categoría | Nota | Evidencia |
|---|---:|---|
| Distinción visual | 8 | Recorrido, cantidades con signo y lotes responden a la operación |
| Tipografía y contenido | 8.5 | Nombre destacado, SKU monoespaciado y copy claro |
| Layout y responsive | 8.5 | Cinco columnas escritorio, dos tablet y lectura apilada móvil |
| Interacción | 8 | Filtros, disclosures, carga y respuesta funcional sin animación gratuita |
| Consistencia | 9 | Tokens, controles y superficies comunes en ambos temas |
| Accesibilidad | 8.5 | Labels, foco, teclado y contraste AA medido en las ocho variantes |
| Código | 9 | Componentes separados, cancelación y consultas acotadas |
| Estados y límites | 9 | Vacío, validación, paginación y recuperación 503→200 |

Mejoras menores futuras: reemplazar el snapshot técnico desplegable de empaque
por etiquetas de lectura y compactar más el detalle móvil. No bloquean esta
consulta de movimientos.

# Bloque 5 — Kardex, promedio, conciliación y reportes

Implementación del 29/10/2026. Corresponde a K01–K04, la presentación de V01/V02
y la protección de P01 del plan maestro. El bloque 6 conserva la demostración
integrada del recorrido completo y sus regresiones.

## Qué puede consultar cada persona

- **Bodeguero:** movimientos físicos de sus bodegas asignadas, documentos,
  lotes, responsable, entradas/salidas y saldos reconstruibles; PDF/Excel sin
  costos. No basta compartir sucursal para consultar otra bodega. Los extremos
  y unidades de bodegas fuera de su asignación se ocultan también en el detalle.
- **Usuario con `inventory:valuation` y alcance de toda la empresa:** Kardex
  valorado y conciliación global. Una cuenta restringida por bodega no obtiene
  esos reportes globales, aunque intente llamar directamente a la API.

La pantalla del bodeguero conserva su consulta de movimientos dentro de
Inventario; estas consultas y descargas no agregan tareas obligatorias al ingreso.

## Las tres vistas

1. **Movimientos físicos:** producto, bodega/sucursal autorizada, fechas, tipo,
   lote y referencia. La búsqueda acepta códigos de compra/entrega y referencias
   de ajustes, traslados o devoluciones. Las entradas y salidas del resumen usan
   el mismo filtro de documento que las filas. Los saldos conservan la secuencia
   completa; filtrar una recepción no convierte su cantidad en el saldo total.
2. **Valoración:** fechas contables, documento legible, lote disponible,
   responsable, cantidad, costo unitario aplicado, cambio de valor y saldo de
   cantidad/valor/promedio guardado después de cada movimiento. El promedio y
   el costo unitario muestran hasta seis decimales. Una fila antigua no se
   sustituye por el promedio actual. Los ajustes solo de valor no inventan
   unidades ni un costo unitario físico.
3. **Conciliación:** cantidad física frente a valorada, diferencia, promedio y
   valor por producto. Admite fecha de corte por registro, nombre/SKU y filtro
   de diferencias o falta de base. Los indicadores abarcan el resultado filtrado
   completo, no solo la página. Un vacío permite quitar producto/estado sin
   perder la fecha. Los productos sin valoración verificable se señalan y no
   se interpretan como importes conocidos.

La conciliación histórica parte del corte físico aprobado y suma las entradas y
salidas externas registradas hasta el final del día en El Salvador. Para el valor
usa el último evento persistido por producto hasta esa hora. Reubicaciones y
traslados dentro de la empresa no aumentan el total global. Un corte anterior a
la base disponible muestra saldos desconocidos; no inventa ceros.

**Fecha de registro y fecha contable son distintas:** esta conciliación por fecha
de registro no recalcula un cierre contable retroactivo. El Kardex valorado
mantiene su filtro por fecha contable y explica el alcance correspondiente.

## PDF y Excel

Las tres vistas ofrecen los dos formatos desde una consulta terminada:

- Empresa, NIT/NRC disponibles, producto/código, unidad, alcance, período o corte,
  moneda cuando corresponda, filtros y notas de interpretación.
- Todas las filas filtradas, independientemente de la página visible. Límite de
  5,000 filas por archivo; si se supera, se pide reducir el período/aplicar filtros
  en lugar de entregar un archivo truncado.
- Excel con cantidades/importes numéricos, precisión decimal y texto de usuario
  tratado como texto; PDF tabulado con encabezados repetidos y paginación.
- Descargas sin caché, comprobación del contexto de empresa/sucursal y rechazo
  de respuestas obsoletas. Un error de consulta no deja descargar un resultado
  anterior como si fuera el nuevo.

Son reportes internos identificables. No se afirma compatibilidad con una
plantilla fiscal específica de Hacienda sin cotejar esa plantilla vigente.

## API

Se mantienen `GET /inventory/kardex/{physical,valuation,reconciliation}`.

- Conciliación agrega `as_of=YYYY-MM-DD`, `q` y `difference_only`, además de
  resumen global y fecha de generación. Omitir `as_of` conserva la lectura actual.
- Los tres endpoints agregan `GET .../export?format=pdf|xlsx`, con los mismos
  filtros y autorizaciones de la consulta. Paginación no limita el archivo.
- Las respuestas agregan contexto de identificación y referencias legibles sin
  reemplazar los identificadores técnicos originales.

No requiere migración ni modifica datos comerciales/históricos existentes.

## Evidencia automatizada y visual

- **48 pruebas backend**: políticas de valoración, informes, paginación de
  exportaciones, SQL de Kardex/conciliación y conservación de valor.
- **1 recorrido E2E adicional** en `erp_db_test`: tres ingresos 5 × USD 10,
  10 × USD 15 y 15 × USD 20; saldos 5/15/30, valores 50/200/500 y promedios
  10/13.333333/16.666667. Comprueba costo aplicado, historia intacta después de
  consultar/exportar, diferencia cero, seis archivos PDF/XLSX, filtros, fecha
  futura rechazada, desconocidos anteriores al corte y permisos 401/403/404.
- La prueba SQL de corte con base no vacía verifica 10/12/20 unidades y
  68/88/248 de valor, incluyendo la separación exacta de medianoche local y
  el ocultamiento de otra bodega de la misma sucursal.
- **32 pruebas frontend**: filtros/rutas, contexto obsoleto, errores/reintentos,
  precisión histórica, limpieza de filtros y descargas. `svelte-check`: cero
  errores; ocho advertencias CSS preexistentes en `TransferOperationsPage`.
- Edge: recorrido real de Rodrigo y descarga física, cero escrituras de inventario
  y cero errores JavaScript. Las vistas financieras se revisan con una fixture
  visual declarada en la app real, en 1440/768/375 px y ambos temas; su autorización
  y exportaciones financieras sí están probadas contra la API con PostgreSQL en E2E.
- PDF renderizado e inspeccionado; Excel leído con openpyxl para comprobar tipos,
  valores y cantidad de filas. Artefactos en `tmp/block5-exports` y `tmp/block5-review`.

## Qué explicar al ingeniero

1. «Al confirmar la ubicación se registra una sola entrada física y valorada.
   El Kardex consulta esos movimientos; no calcula otra compra ni altera el stock».
2. En Valoración, comparar **costo aplicado a la entrada** y **promedio histórico**:
   segunda entrada a 15, promedio resultante 13.333333; tercera a 20, promedio
   16.666667. La primera fila sigue a 10.
3. «El promedio es global por empresa/producto. Cambiar de bodega no cambia el
   costo global; el movimiento físico sí se consulta por la bodega autorizada».
4. Mostrar documento/lote/responsable, aplicar un filtro y descargar PDF o Excel.
   Explicar que el archivo incluye todas las filas que cumplen esos filtros.
5. En Conciliación mostrar cantidad física = valorada y diferencia cero.
   Distinguir una base histórica desconocida de una diferencia real de cantidades.
6. Cambiar a Rodrigo para mostrar movimientos operativos y confirmar que no tiene
   columnas, vistas ni archivos de costos.

## Revisión independiente

Primera ronda: 8.13/10, rechazada por contraste del mensaje de error, saldos
posteriores a exportaciones en móvil y vacío poco contextual. Se corrigieron:
texto de error con `foreground`, resúmenes antes de identificación/descargas,
controles de período adaptados a tablet y vacío con limpieza de filtros.
Segunda revisión independiente: **aprobado, 8.60/10**, sin categoría inferior a 7.

| Categoría | Nota | Evidencia de la evaluación |
| --- | --- | --- |
| Distinción visual | 8.3 | Resúmenes contables y trazabilidad determinan la composición |
| Tipografía/contenido | 8.7 | Distingue costo aplicado y promedio histórico sin perder 13.333333 |
| Layout/responsive | 8.6 | Tablas en escritorio y fichas en tablet/móvil sin recortes |
| Interacción | 8.3 | Preparación, bloqueo de duplicados, paginación y reintento |
| Sistema de diseño | 8.8 | Controles compartidos y tokens coherentes entre temas |
| Accesibilidad | 9.0 | Teclado, labels/captions y anuncios; contraste secundario claro 5.74:1 |
| Código | 8.1 | Responsabilidades separadas y respuestas obsoletas descartadas |
| Estados/límites | 9.0 | Carga, vacío, error, sin valoración, sin base y descarga exitosa |

Mejoras no bloqueantes conservadas para mantenimiento: compactar identificación
y exportación en móvil, simplificar el sufijo de títulos PDF, contextualizar el
rótulo general de productos en búsquedas y extraer coordinación de la ruta extensa.
La revisión visual no sustituye la validación financiera real de servidor descrita
en las pruebas E2E/SQL.

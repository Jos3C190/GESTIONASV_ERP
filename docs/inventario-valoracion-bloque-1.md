# Valoración de inventario: primer bloque implementado

Fecha: 14/10/2026.

## Estado de entrega

Implementación en código y pruebas unitarias terminadas. En el cierre del bloque 2 se volvieron a ejecutar 85 pruebas backend pertinentes y pasaron. **No está activada ni validada de extremo a extremo sobre PostgreSQL.** La migración `0079` no se aplicó a una base de datos ni se aprobó un saldo inicial real.

### Actualización después del bloque 3

El código actual agrega Kardex físico/valorado y conciliación por empresa, reutilizando el corte y el promedio de este bloque. En la última validación disponible, la suite unitaria backend aprobó 692 pruebas (se excluyó el módulo OCR porque falta `pikepdf`); la suite frontend aprobó 417 pruebas en 98 archivos, `svelte-check` informó cero errores y advertencias, ESLint pasó sobre los archivos modificados y el build de producción terminó. La interfaz recibió aprobación UX/UI con promedio de 8.75/10. El informe del [bloque 3](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-3-kardex-conciliacion.md) detalla comandos y límites. **La aprobación y operación real continúan pendientes**: no hubo PostgreSQL de prueba disponible, recorrido autenticado de navegador ni aprobación de un corte inicial real.

Este documento describe el primer bloque de la política autorizada. No equivale a dar por terminados todos los cambios de inventario, contabilidad y viñeteado de la hoja de ruta.

La [revisión de integración del 14/10/2026](C:/Developer/GESTIONASV_ERP/docs/revision-inventario-bloques-1-2-2026-10-14.md) registra las correcciones del bloque 2 y las validaciones de PostgreSQL aún pendientes.

## Qué incorpora

- Promedio móvil ponderado por empresa legal y producto de inventario/variante en unidad base. Los almacenes de una empresa comparten el promedio; las empresas mantienen balances separados.
- Corte inicial explícito con existencias físicas actuales, moneda, costo total documentado por producto, fuente del costo, documento de aprobación y usuario. Incluye cuarentena y tránsito. No deduce costos históricos ni altera las cantidades físicas.
- Recepciones nuevas valoradas al verificar la compra: FOB aceptado neto de descuento, distribuido entre las unidades logísticas recibidas. Cambios de ubicación, estado y traslados internos conservan el valor de la empresa.
- Aplicación explícita del retaceo verificado, una sola vez por recepción. El cálculo es una vista previa. Aplicar registra ajustes de valor con fecha y actor; cerrar conserva ese registro.
- Ajustes de retaceo tardío distribuidos entre existencia remanente y salidas afectadas mediante recálculo del promedio cronológico. Los eventos originales permanecen inmutables y el ajuste conserva su desglose.
- Salidas al promedio vigente; devolución de cliente al costo efectivo de la salida original; devolución a proveedor al promedio, con crédito del proveedor y diferencia registrados por separado. El registro del crédito está disponible mediante API, aún sin formulario propio.
- Historial inmutable, claves de idempotencia, bloqueo transaccional por empresa y permiso `inventory:valuation`. El permiso se concede inicialmente al rol global de sistema `SUPER_ADMIN`.

## Pantallas y recorrido

1. Entrar en **Inventario → Valoración de inventario**, ruta `/inventory/valuation`, con acceso a todas las sucursales de la empresa.
2. Finalizar los retaceos anteriores al corte y conciliar sus valores con el saldo inicial. El sistema impide abrir la valoración mientras existan retaceos en proceso.
3. Revisar el conteo, documentar costos y aprobar el saldo inicial. Si las existencias cambiaron, actualizar el conteo: se conservan valores de productos cuya cantidad no cambió, se limpian los afectados y se exige nueva confirmación.
4. Verificar las próximas recepciones de compra. Se incorporan cantidad y costo provisional al registro de valoración.
5. En retaceo: **Calcular → Verificar → Aplicar costo al inventario → Cerrar**. Con valoración activa no se permite cerrar sin aplicar. La liberación a disponible de unidades procedentes de estas compras requiere el retaceo aplicado.
6. Consultar los saldos compartidos entre almacenes y abrir el historial por producto. Los desgloses permiten saltar al movimiento valorado de origen.

Antes de aprobar el corte, los retaceos conservan su cierre anterior sin registrar ajustes de valoración. La interfaz lo indica. Después del corte, no se permite crear un retaceo para una recepción antigua sin registro provisional: sus costos pertenecen a la conciliación inicial y requieren regularización documentada.

## Activación pendiente

1. Recuperar el servicio de PostgreSQL/Docker y confirmar la base de destino.
2. Aplicar y comprobar `0079` primero en la base de prueba dedicada, tras revisar `alembic current` y `alembic heads`. El árbol ahora llega a `0083`; `upgrade head` aplicaría también las revisiones del bloque 2. Nunca ejecutar estas pruebas contra la base operativa.
3. Probar en esa base apertura, recepción, retaceo, aplicación repetida, cierre, devolución, traslados y restricciones entre empresas. Verificar rollback ante errores y concurrencia de movimientos.
4. Reiniciar el backend y actualizar sesión/permisos de la interfaz según el entorno.
5. Aprobar el saldo inicial real únicamente con cantidades y costos conciliados. La aprobación de la implementación no sustituye esa aprobación operativa.

La migración agrega cuatro tablas de valoración y los campos de aplicación del retaceo; no convierte el histórico ni rellena importes. Su reversión destructiva se bloquea intencionalmente para conservar el historial financiero.

## Verificación realizada

- En el cierre del bloque 2 se reejecutaron **85 pruebas backend aprobadas** en 11 módulos de unidad, incluyendo promedio, retaceo, recepción de compra, etiquetas, trazabilidad QR y validación agrupada.
- **30 pruebas frontend enfocadas aprobadas en 6 archivos**: valoración, apertura del saldo, verificación de recepción y acciones, detalle y creación de retaceos.
- Ruff: archivos nuevos de valoración sin errores.
- Alembic: generación SQL PostgreSQL de `0078:0079 --sql` correcta. Esto valida la generación, no su ejecución sobre una base de datos.
- `svelte-check` global: **0 errores y 0 advertencias**.
- **406 pruebas frontend aprobadas en 94 archivos**, `svelte-check` con cero errores/advertencias y build de producción completado.
- Ruff, ESLint y Prettier pasaron sobre los archivos afectados.
- La generación offline de la migración y el estado de `alembic current` se documentan en la revisión de integración; no se aplicó ninguna migración a una base activa.
- Revisión de interfaz estática realizada; comprobación visual con dispositivos e integración real de PostgreSQL pendiente.

## Límites y siguientes bloques de la política

- No se implementó en esta entrega el nuevo flujo completo de viñeteado, confirmación de etiquetas, lotes por recepción ni captura avanzada del inventario físico inicial.
- No hay libro mayor contable, períodos abiertos/cerrados, autorizaciones de retroactividad ni reversión general de movimientos financieros. Las fechas operativa y contable se registran separadas, usando la fecha actual de El Salvador; no se acepta fecha retroactiva arbitraria.
- No incluye conversión monetaria: la recepción y el retaceo deben usar la moneda aprobada de valoración.
- No hay recálculo automático del inventario anterior al corte, tratamiento de deterioro ni regularización contable de diferencias antiguas.
- La base de devolución/ajuste está en el motor y API; queda integrar la experiencia completa con los documentos y pantallas operativas de devoluciones y correcciones.
- El cálculo recorre el historial del producto. Su rendimiento con grandes volúmenes históricos y su concurrencia deben medirse en PostgreSQL antes de ampliar el uso.

Estos límites deben conservarse en la planificación; no presentar este bloque como certificación de cumplimiento contable integral.

### Estado posterior al bloque 4 — 14/10/2026

La lectura del Kardex y las acciones de retaceo aparecen ahora vinculadas a los permisos existentes; la autorización de liberación sigue comprobando el costo aplicado cuando corresponde. No cambia el promedio por empresa ni el tratamiento autorizado del crédito del proveedor. Se ejecutaron 59 pruebas frontend de inventario, `svelte-check`, ESLint, build y compilación sintáctica Python 3.12.14. La suite backend y PostgreSQL no se ejecutaron por ausencia de dependencias backend y servidor disponible. La activación/conciliación del saldo inicial real continúa pendiente; véase el [cierre operativo del bloque 4](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-4-cierre-operativo.md).

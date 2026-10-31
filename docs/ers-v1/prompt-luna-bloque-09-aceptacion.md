# Checklist de cierre B08 — aceptación integrada (antes ERS-B09)

Decisión del usuario del 18/10/2026: ejecutar este checklist como fase final de B08, después de las devoluciones. Se conserva el nombre de archivo por compatibilidad con enlaces históricos; no constituye un noveno encargo. Los pendientes visuales de bloques anteriores se revisan aquí sin darlos por aprobados de antemano.

Verifica la adaptación completa B01–B08 contra la ERS 1.0. Lee [guía](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [decisiones](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md), [matriz](C:/Developer/GESTIONASV_ERP/docs/ers-v1/matriz-y-seguimiento.md) y entregas anteriores. No estás solo en el repositorio; conserva cambios e informes existentes. Este bloque incluye corregir defectos de integración dentro del alcance y documentar su causa y comprobación.

## Entorno y evidencia

Identifica las versiones de código, cabeza real de migraciones, base que usa la API y puerto del frontend de demostración. No asumir que pasar tests deja migrada la base habitual. Ensaya migraciones con datos previos en copia aislada; documenta respaldo, recuperación y conservación de IDs/saldos/historial antes de actualizar la demo. No limpiar ni reemplazar sus datos mediante semillas destructivas.

Antes de recolectar integración/E2E, revisa las fixtures y confirma que los DSN de prueba apuntan únicamente a erp_db_test. Las suites reconstruyen el esquema: ejecútalas en serie y nunca mientras la aceptación de navegador dependa de la misma base. Después prepara un entorno de demostración estable con datos ficticios identificados, usando API autenticada y un navegador real. No mostrar credenciales.

Reutiliza casos y evidencias pertinentes de B01–B08, indicando su fecha y versión; vuelve a ejecutar los que dependan de cambios posteriores y el recorrido integrado actual. No volver a auditar todo el ERP ni aumentar cobertura de módulos ajenos. Distingue pruebas con respuestas simuladas de la comprobación real de persistencia.

## Recorrido controlado con resultado calculable

Usa un artículo base nuevo de prueba, unidad/conversión identificadas y cantidades decimales del motor. No editar el corte inicial ya aprobado de la empresa ni mezclar el caso con el café histórico. Puedes generar la existencia de partida mediante ajuste positivo documentado B05. Todo documento de prueba debe distinguirse como demostración.

1. Verificar matriz administrativa, bodega central original asociada y permisos. Conservar IDs/historial previos. Preparar 5 unidades con costo documentado de 10 USD: cantidad 5, valor 50.
2. Completar solicitud → consolidado → cotización de compra → orden → recepción de 10 unidades. Si hay retaceo, usar costo base total 100 y gasto aplicable 50, de forma que el costo final de esa recepción sea 150. Si la compra local no requiere retaceo, probarlo en otro caso y recibir estas 10 a 15. El total final del artículo será 15 unidades, valor 200 y promedio 200/15. No sumar dos veces el gasto.
3. Comprobar lote de producto, etiqueta con código interno/lote/fecha, QR/ficha, ubicación y liberación. Consultar movimientos por código de etiqueta en Kardex. Abrir/cerrar una división o reimprimir no modifica cantidades; una división confirmada conserva la suma y exige solo las verificaciones pertinentes.
4. Desde la demanda del producto, elegir la sucursal solicitante y preparar traslado de 10, con vehículo y documento. Preparación conserva 15/200. Despachar deja 5 en central y 10 en vehículo. Recibir 8 deja central 5, destino 8 y tránsito 2; completar las 2 deja central 5 y destino 10. El total de empresa permanece 15/200 en cada paso.
5. Crear cliente/cotización de venta y confirmar venta de 3 unidades para esa sucursal. Precio comercial distinto del costo. Estos documentos no cambian 15/200. Confirmar la entrega de 3 deja sucursal 7, empresa 12 y valor 160; el costo de la salida es 40, sujeto a la precisión documentada del motor.
6. Registrar devolución de 1 de esa entrega. La recepción documental no cambia inventario. Aceptarla a su costo original deja sucursal 8, empresa 13 y valor aproximado 173.333333. Si entra a cuarentena, distinguir stock total de disponible y completar su liberación sin volver a contabilizarla.
7. Aplicar ajuste negativo documentado de 1 unidad disponible al promedio vigente: empresa 12 y valor aproximado 160. Conservar entrega, devolución, adjuntos y movimientos originales. Comprobar conciliación por producto y suma por ubicación/estado.

Calcula las expectativas con Decimal y la precisión real del contrato; explica diferencias de presentación a dos decimales frente al almacenamiento. No dar por correcto un saldo calculado a partir de valores redondeados de la pantalla.

## Casos de control obligatorios

- Insuficiencia, cantidad superior al pendiente, devolución superior a lo entregado, stock en tránsito/cuarentena, empresa o sucursal ajena: rechazo sin cambios parciales.
- Idempotencia de despacho, recepción parcial, entrega, aceptación y ajuste; clave repetida con otro cuerpo; dos usuarios contra el mismo saldo o límite.
- Falla de segunda línea y AppError tardío: documento, cantidades, valoración y auditoría de éxito se revierten juntos.
- Incidencia de traslado con cantidad aún en vehículo; resolución parcial y ajuste autorizado de pérdida, sin borrar stock por un cambio de estado. Este es un caso separado del recorrido numérico anterior.
- Reimpresiones, etiquetas antiguas y alias de recepción conservan resolución e historial. Producto/presentación visibles, división opcional, ninguna operación física al abrir/cancelar formularios.
- Demanda por sucursal visible desde producto/HU; destinos preseleccionados, extra con motivo, envío manual y errores de carga distinguibles de ausencia de demanda.
- Usuario de sucursal puede operar según su rol sin recibir costos globales ni otros documentos/adjuntos no autorizados. No basta ocultar controles en pantalla.
- Existencias históricas sin origen reconstruible se muestran como legado; no inventar lote, vehículo o entrega para completar el caso.

## Entregables y cierre

1. Crear revision-integral-bloques-01-08.md y enlazarlo desde entrega-bloque-08.md, con matriz E01–E15 → evidencia → resultado, entorno/migraciones, defectos encontrados y corregidos, comandos/resultados reales y límites.
2. Crear manual-pruebas-y-demostracion.md en esta carpeta: pasos desde solicitud hasta entrega/devolución/ajuste, nombres de acciones reales, cuentas/roles sin contraseñas, datos ficticios usados, saldos esperados y dónde comprobarlos. Incluir el punto de fin del flujo de almacén: «Revisión terminada · disponible para uso»; ventas/devoluciones son etapas posteriores cuando correspondan.
3. Actualizar matriz-y-seguimiento.md con el estado real y conservar revisiones anteriores; actualizar documentación API, esquema y RBAC si hubo cambios. Evidencias fechadas en tmp/ers-v1/bloque-08/aceptacion-integrada.
4. Explicar las extensiones documentadas: cabecera de recepción + lote canónico por detalle, costo provisional antes de retaceo, variantes y almacén técnico de tránsito. Verificación funcional no equivale a aprobación literal del modelo físico por el docente.

La ausencia de impresora o lector físico no impide aceptar esta demostración: el usuario los excluyó. Las funciones de generación, consulta, confirmación y reimpresión sí se comprueban como software. DTE/cobros/contabilidad general permanecen fuera del alcance.

Con todos los criterios demostrados, marcar la implementación VERIFICADA y entregar el manual para revisión de arquitectura. Si falta alguno, registrar cuál y su evidencia/impedimento; no declarar todo completo por compilación, capturas aisladas o un número de tests.

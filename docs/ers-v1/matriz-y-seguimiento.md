# Matriz de requisitos y seguimiento ERS 1.0

Fecha inicial: 17/10/2026. Última actualización: 21/10/2026. Estado vigente: `erp_db` en 0090; flujo B01–B08 persistido y aceptación integrada **PARCIAL**. La actualización vigente de cuatro puntos está al inicio de este documento; las filas e informes históricos que siguen conservan la fecha/alcance originales.

## Estado vigente — verificación final del 21/10/2026

V04-01/02/03 aprobaron desde UI con persistencia en clon: ajuste compensatorio, traslado 8+2 y devolución mixta 2 aceptadas/1 rechazada. Los cuatro SKU protegidos concilian contra el baseline en `erp_db` y la clon. V01 permisos/documentos, V02 PNG archivados, V03 recepción repetida/alias y V04-04 pérdida postcommit desde UI siguen **ABIERTO**. No se corrigió código de producto en esta pasada. Ver [cierre E01–E15](cierre-visual-y-permisos-b01-b08.md), [registro V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md) y [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md).

**Continuación ejecutada el mismo día:** la segunda lectura `READ ONLY` volvió a confirmar los cuatro saldos; se localizaron tres pares de alias de recepción y 24 HUs sin lote enlazado en la clon. La lectura UI fue rechazada por política de URL y se detuvo. No equivale a aceptación visual. V01/V02/V03-02/03/05/V04-04 siguen abiertos; detalle en [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md).

El adaptador real de RustFS transfirió un archivo ficticio con igualdad de hash y lo eliminó; la autenticación del API documental devolvió 401 antes de crear un documento. V01 queda abierto; no se registró descarga API ni permiso por módulo.

**Actualización final 20/10/2026:** la continuación agregó un E2E de documento de ajuste con denegaciones/alcance/revocación, y pruebas persistidas de corrección compensatoria, traslado parcial/final y devolución parcial con varias asignaciones/rollback. Se corrigió la ficha HU para diferenciar lote fabricante, detalle canónico y cabecera. Vitest focalizado pasó 47, Svelte-check 0 errores, ESLint enfocado y build aprobaron. La aceptación sigue parcial por matriz E13 no exhaustiva, PNG P02 no exportables desde la sesión disponible, recepción repetida/alias en UI P03 y devolución mixta/recuperación de respuesta desde UI P04. Ver [cierre vigente](cierre-visual-y-permisos-b01-b08.md), [cierre de pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md) y [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

## Estado por bloque

**Siguiente encargo de aceptación:** [verificación final de cuatro puntos B01–B08](prompt-luna-verificacion-final-cuatro-puntos-b01-b08.md). Reúne permisos, evidencia visual, recepción/trazabilidad y operaciones/recuperación; mantiene el alcance de B08 y no altera el estado parcial hasta su ejecución.

| Bloque | Estado | Informe de entrega | Revisión independiente |
| --- | --- | --- | --- |
| ERS-B01 Matriz | Implementado/verificado técnicamente; aceptación visual integrada parcial por perfiles/tamaños restantes | [entrega-bloque-01.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-01.md) | [Revisión B01](C:/Developer/GESTIONASV_ERP/docs/ers-v1/revision-bloque-01.md) y E01 del [cierre vigente](cierre-visual-y-permisos-b01-b08.md) |
| ERS-B02 Lotes | Implementado/verificado técnicamente; aceptación visual parcial: varias líneas del mismo SKU y consulta UI de códigos aplicables | [entrega-bloque-02.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-02.md) | [Evidencia B02](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-02/evidencia-2026-10-18.md), E02/E04/E05 y [lista de códigos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/alias-trazabilidad.md) |
| ERS-B03 Motor de traslados | Implementado/verificado técnicamente; parcial en aceptación integrada de estados y contextos visuales | [entrega-bloque-03.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-03.md) | Evidencia técnica fechada en `tmp/ers-v1/bloque-03/`; E03/E06/E07 actuales |
| ERS-B04 Operación de traslados | Flujos principales operados y verificados; pasada móvil adicional confirma pestañas/demanda; matriz visual completa sigue parcial | [entrega-bloque-04.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-04.md) | Corrección y comprobación actual en [recorrido móvil](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/mobile-ui-run.md); E06/E07 |
| ERS-B05 Ajustes | Flujos documentados y operados; aceptación sigue parcial por perfiles, documentos directos y variantes de corrección UI | [entrega-bloque-05.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-05.md) | [Evidencia técnica](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-05/evidencia-2026-10-19.md), E08/E13 vigentes |
| ERS-B06 Base comercial | Flujo cliente/cotización/venta y neutralidad comprobados; permisos, estados y recuperación no cubren todos los perfiles | [entrega-bloque-06.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-06.md) | Evidencia API/UI y E09/E13 del [cierre vigente](cierre-visual-y-permisos-b01-b08.md) |
| ERS-B07 Entregas | Entrega parcial y final por UI más evidencia API; aceptación completa de perfiles/recuperación sigue parcial | [entrega-bloque-07.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-07.md) | E10/E13 del [cierre vigente](cierre-visual-y-permisos-b01-b08.md) |
| ERS-B08 Devoluciones | Implementado y operado para aceptación/rechazo; aceptación integrada parcial por devolución mixta/UI, permisos/adjuntos y estados restantes | [entrega-bloque-08.md](entrega-bloque-08.md) | E11 y [revisión de interfaz móvil](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/mobile-ui-run.md) |
| Checklist antes B09 | Ejecutado parcialmente como cierre B08; no es bloque independiente | [revision-integral-bloques-01-08.md](revision-integral-bloques-01-08.md) | E01–E15 y pendientes P01–P04 en el [cierre vigente](cierre-visual-y-permisos-b01-b08.md) |

Los informes se guardarán en C:\Developer\GESTIONASV_ERP\docs\ers-v1. Estados permitidos: Pendiente, En curso, Implementado, Verificado, Revisado, Parcial con impedimento documentado. Al actualizar una fila, indicar fecha, evidencia y revisión; no sustituir el historial de resultados anteriores.

## Trazabilidad de requisitos

| ID de seguimiento | Fuente ERS | Comprobación requerida | Bloque responsable |
| --- | --- | --- | --- |
| E01 | 6.9.1 y 6.9.19, pp. 105/115 | Central adscrita a matriz; IDs, saldos e historial conservados | B01 |
| E02 | RN-INV-002/003, 6.9.5 | Producto/lote vinculados a detalle de recepción real y parcial | B02 |
| E03 | RN-INV-004/005, 6.9.6 | Lote distribuido en ubicaciones con saldo reconciliable | B02 |
| E04 | RN-INV-016/017 | Código interno, lote y fecha en etiqueta; historial de impresión y motivo de reimpresión | B02, regresión al cierre B08 |
| E05 | 6.9.16, 6.9.18 | Código de etiqueta consultable en Kardex y trazabilidad | B02 |
| E06 | 6.9.13/19, p. 115 | Vehículo, tránsito y estados de traslado exigidos | B03, B04 |
| E07 | RN-INV-008/009/015 | Origen, tránsito y destino conservan cantidades y valor; recepción parcial | B03, B04 |
| E08 | RN-INV-001/006/007/018 | Ajuste autorizado, motivo, soporte y compensación sin edición histórica | B05 |
| E09 | RN-020 y RN-INV-011 | Cotización convierte a venta; ni cotización ni venta sin entrega descuentan stock | B06 |
| E10 | RN-018/019 y RN-INV-010 | Entrega transaccional desde la sucursal correcta, rechazo por insuficiencia | B07 |
| E11 | RN-021/022 y RN-INV-012 | Devolución recibida/aceptada; límite por salida original | B08 |
| E12 | RN-INV-013/014/015 y 6.9.15 | Promedio global, salidas/devoluciones valoradas, traslados neutros | B02–B08, cierre B08 |
| E13 | 6.9.17/19 y reglas de auditoría | Permisos, empresa/sucursal, actor, documento y rollback completo | Cada bloque, cierre B08 |
| E14 | 6.9.12 y política ya autorizada | Cuarentena, costo provisional identificado, retaceo aplicado y disponibilidad final | B02, cierre B08 |
| E15 | 6.9.18/19 | Base habitual migrada, recorrido integrado y conciliación | Cierre B08 |

Para cada ID añadir las pruebas concretas y su resultado en el informe del bloque. La aceptación integrada sigue pendiente y se ejecutará al finalizar B08. El estado puntual de los requisitos tocados por B01/B02 al 18/10/2026 es:

| ID | Resultado técnico actual | Pendiente |
| --- | --- | --- |
| E01 | Aprobada en migración/prueba: 0084 vinculó la bodega central existente a la matriz y conservó IDs, saldos e historial. | Recorrido visual de B01 en la demo. |
| E02 | Aprobado en pruebas: cada detalle y recepción parcial del mismo producto conserva código/origen distinto. | Revisión manual de pantallas. |
| E03 | Aprobado en API/E2E: colocación agrupada conserva origen por detalle y conciliación; saldo legacy no atribuible se identifica aparte. | Revisión manual de pantallas. |
| E04 | Aprobado por preview/API: etiqueta de software muestra producto, código interno y origen; impresión/confirmación queda registrada. | No aplica impresora física; confirmación visual manual pendiente. |
| E05 | Aprobado en E2E: Kardex filtra por código canónico; el código previo de cabecera resuelve los detalles asociados. | Recorrido manual etiqueta → Kardex. |
| E12 | 0085 no altera promedio ni valoración; las regresiones seleccionadas de valoración/concurrencia pasan. | Reglas completas de salidas, devoluciones y traslados continúan en B03–B08 y revisión final. |
| E13 | Aprobado en pruebas seleccionadas de empresa/sucursal, permisos y rollback. | Aceptación integrada de roles y recorrido manual al cierre B08. |
| E14 | Regresión automatizada cubre cuarentena, verificación de etiqueta y precondiciones de liberación. | Recorrido manual provisional → retaceo aplicado → disponible. |

**Resultado técnico ERS-B03 (19/10/2026):** migración 0086 aplicada después de respaldo y ensayo aislado. Vehículos, traslados, asignaciones de demanda, comandos idempotentes, recepciones e incidencias se registran mediante documentos y movimientos del motor existente. Las pruebas de integración/E2E focalizadas cubren parcialidad, valor neutro, concurrencia, autorización de sucursal destino, aislamiento de empresa, movimiento genérico legado y rollback. La base demo conserva las huellas previas de lotes, HUs, saldos, movimientos, etiquetas y valoración; solo se agrega una bodega técnica por empresa. B04 debe conectar las pantallas; no se ha hecho aceptación visual. Ver entrega y evidencia B03.

**Resultado técnico ERS-B04 (19/10/2026):** la ruta `/transfers` y el acceso desde Almacenes usan el mismo flujo documental B03. Se muestran solicitudes relacionadas por sucursal; la preparación no mueve ni reserva stock; despacho requiere confirmación explícita; recepción captura cantidades parciales en ubicaciones válidas y deja HUs en cuarentena; incidencias conservan motivo/evidencia y solo permiten las resoluciones del API. El puente genérico impide usar movimientos sin documento para cruzar bodegas o entrar/salir de tránsito. No se añadió migración ni se alteraron datos demo. Las comprobaciones focalizadas pasan; la aceptación autenticada e integrada sigue diferida a B08. Ver [entrega B04](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-04.md) y [evidencia](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-04/evidencia-2026-10-19.md).

| ID | Resultado técnico actual | Pendiente |
| --- | --- | --- |
| E06 | B03 implementa vehículos, ubicación técnica de tránsito y estados; B04 conecta demanda, preparación, despacho, recepción e incidencias a los documentos del motor. | Recorrido autenticado de emisor, receptor y usuario global al cierre B08. |
| E07 | B03 y su integración focalizada prueban despacho/recepción parcial con movimientos reales, concurrencia y neutralidad de valor; B04 deja vacías las cantidades y exige captura explícita. | Recorrido visual completo e integración con entrega/devolución al cierre B08. |
| E12 | Neutralidad de traslado validada contra el motor de valoración; B05 integra ajustes en el promedio existente y prueba la pérdida valorizada. | Validación integral de salidas, ventas, entregas y devoluciones en B06–B08. |
| E13 | B03 cubre alcance empresa/sucursal, idempotencia y rollback; B04 invalida respuestas/estado al cambiar contexto y mantiene separados permisos de movimiento y recepción. | Aceptación integrada de permisos en navegador al cierre B08. |

| ID | Resultado técnico actual | Pendiente |
| --- | --- | --- |
| E06 | B04 conecta la pantalla con el API B03 de vehículos, tránsito, estados y detalle de traslado. | Aceptación autenticada por los perfiles definidos al cierre B08. |
| E07 | La ubicación de recepción se filtra por bodega destino, activa y elegible; integración B03 conserva parcialidad, cuarentena y valor global. | Confirmar recorrido de usuario y conciliación visual al cierre B08. |
| E13 | Cliente separa `inventory:move` y `inventory:receive`, limpia el contexto anterior al cambiar empresa/sucursal y no expone costo global para recepcionar. | Aceptación de alcance/permisos en navegador y regresión integral al cierre B08. |

**Resultado técnico ERS-B05 (19/10/2026):** se respaldó `erp_db` y se restauró el dump en una base temporal separada; esa copia partió de 0086 y aplicó 0087 conservando 1 detalle de lote, 25 HUs, 65 movimientos, 6 promedios y cero traslados/detalles. Luego se migró la demo a 0087; sus conteos coinciden y no se reescribieron movimientos ni promedios. Se probaron promedio positivo, reintento idempotente, soporte requerido/protegido, saldo insuficiente, rollback tardío, corrección compensatoria y pérdida de traslado (10 despachadas, 8 recibidas, 2 ajustadas, 0 en tránsito). 4 pruebas unitarias, 4 integración PostgreSQL, 9 frontend, Ruff, compileall, ESLint, Svelte-check y build pasan. No se ejecutó aceptación visual autenticada ni matriz API exhaustiva de perfiles. Ver [entrega B05](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-05.md) y [evidencia](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-05/evidencia-2026-10-19.md).

| ID | Resultado técnico actual | Pendiente |
| --- | --- | --- |
| E08 | B05 añade motivo, referencia, soporte activo, autorización, movimientos compensatorios, historial e inmutabilidad. PostgreSQL cubre falta de soporte, soporte activo protegido tras aprobar, aplicación idempotente, rollback tardío y corrección negativa ordinaria. | Matriz API completa por perfil/empresa, concurrencia, variante sin promedio previo y aceptación autenticada al cierre B08. |
| E12 | Positivos con costo documentado y promedio vigente actualizan la valoración global; el faltante reduce cantidad/valor sin alterar lo recibido. | Recorrido integrado de ventas, entregas y devoluciones al cierre B08. |
| E13 | Rutas de ajuste comprueban `inventory:adjust`, `inventory:adjust_approve`, alcance de empresa/bodega y `inventory:valuation` para exponer costos; el movimiento genérico rechaza ajustes públicos. | Pruebas API por perfiles de sucursal/otra empresa, acceso a soporte y replay; aceptación integrada al cierre B08. |

| ID | Resultado técnico actual ERS-B06 | Pendiente |
| --- | --- | --- |
| E09 | E2E real confirma cotización vigente → una venta en borrador, con origen y snapshots, totales del servidor, mismo resultado al reintentar y cero cambios físicos/de valoración. | Aceptación autenticada y visual del proceso comercial al cierre B08; venta no representa entrega ni factura fiscal. |
| E12 | Todos los comandos comerciales B06 conservan sin cambio la huella de 8 tablas físicas y de valoración. | La salida con promedio vigente se valida en B07; conciliación integrada de ventas, entregas y devoluciones en B08. |
| E13 | E2E cubre compañía/sucursal, usuario lector sin permiso de conversión (incluido replay), usuario sin permisos, auditoría, carrera confirmar/editar y rollback de segunda línea/falla tardía. | Matriz integrada de perfiles y recorrido de navegador al cierre B08. |

**Resultado técnico ERS-B06 (19/10/2026):** la revisión 0088 se ensayó desde un respaldo restaurado en una base aislada y luego se aplicó a `erp_db` después de respaldar la demo. Las huellas de inventario antes/después son idénticas. Unit tests, E2E FastAPI/PostgreSQL, pruebas Vitest de navegación, Ruff y build pasan; `svelte-check` termina con 0 errores y 8 avisos CSS preexistentes en traslados. ESLint focalizado de B06 pasa; el lint global conserva tres imports sin uso en pantallas de compras no modificadas por B06. No se hizo aceptación autenticada de navegador. Ver [entrega B06](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-06.md) y [evidencia](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-06/evidencia-2026-10-19.md).

**Resultado inicial B01 (18/10/2026):** la primera revisión encontró la demo en 0083 y dejó R01–R03 pendientes. El cierre técnico posterior se registra en la entrega/revisión B01 y en la evidencia B02; la demo está ahora en 0085. B01 se mantiene parcial solo por el recorrido visual pendiente, no por falta de migración.

## Extensiones y límites que deben seguir visibles

- La cabecera de recepción y sus lotes por detalle son un mapeo del modelo docente; verificar equivalencia funcional y registrar la diferencia física de tablas.
- El costo provisional antes del retaceo conserva una política autorizada anteriormente. La conformidad literal de esa secuencia con la redacción docente permanece sin confirmar; el cierre debe mostrar el costo final aplicado y declarar la extensión.
- Las variantes conservan su identidad; la demostración inicial usa productos base.
- Hardware físico excluido por el usuario; generación y confirmación de etiquetas se prueban como software.
- DTE, cobros y contabilidad general no están incluidos en estos ocho bloques y su revisión integrada.
- El stock histórico sin origen reconstruible no se asigna a un lote/vehículo inventado. Registrar cualquier caso y su vía de regularización, sin ocultarlo con una migración.

## Registro de decisiones y hallazgos

| Fecha | Registro | Resultado |
| --- | --- | --- |
| 17/10/2026 | Creación de guía, decisiones y nueve encargos | Documentación preparada; ejecución pendiente |
| 18/10/2026 | Implementación y comprobación aislada de ERS-B01 | Migración 0084, permisos y recepción central pasan los casos focalizados. La base `erp_db` sigue en 0083; aplicación a demo y recorrido visual pendientes. Ver entrega B01 y evidencia fechada en `tmp/ers-v1/bloque-01/`. |
| 18/10/2026 | Revisión B01 y preparación del encargo B02 | 28 pruebas repetidas: 65.64 s. R01 activación, R02 coherencia de prevalidación y R03 cobertura/evidencia se incorporan como fase inicial obligatoria del prompt B02. Solo se modificó documentación durante la revisión. |
| 18/10/2026 | Cierre técnico R01–R03 y B02 | 0084/0085 activos en `erp_db`, ensayo de restauración completado y pruebas focalizadas aprobadas. Queda aceptación visual/manual de la demo. No se inició B03. |

Al detectar un defecto, añadir identificador ERS-BNN-RNN, reproducción, impacto, causa comprobada o hipótesis, corrección y prueba. Un número de tests aprobados no cierra un hallazgo sin evidencia específica.

| 18/10/2026 | Decisión del usuario: continuar B03 y revisar todo al finalizar B08 | Prompt B03 actualizado sobre 0085. Aceptación originalmente B09 integrada en B08; pruebas técnicas por bloque se mantienen. Pendientes visuales B01/B02 diferidos, no aprobados. |
| 19/10/2026 | Implementación y verificación técnica ERS-B03 | Migración 0086 ensayada en copia y aplicada a `erp_db` con respaldo recuperable; datos previos conservados. Integración y E2E de traslados aprobadas. Las pantallas de B04 y la aceptación visual siguen pendientes. Ver `entrega-bloque-03.md` y `tmp/ers-v1/bloque-03/evidencia-2026-10-19.md`. |
| 19/10/2026 | Implementación y verificación técnica ERS-B04 | Cliente tipado, pantallas de demanda/documentos/vehículos, entrada contextual desde Almacenes y protección contra traslados genéricos entre bodegas. Vitest 39/39, ESLint, Svelte-check (0 errores), build, integración B04 (6/6) y Ruff pasan. La primera crítica UI (7.75/10) se atendió con mejoras de jerarquía, avance y estado accesible; la revisión final aprobó 8.5/10. Aceptación autenticada e integrada diferida a B08; B05 no iniciado. Ver `entrega-bloque-04.md` y `tmp/ers-v1/bloque-04/evidencia-2026-10-19.md`. |
| 19/10/2026 | Implementación y comprobaciones técnicas focalizadas ERS-B05 | Migración 0087 aplicada a `erp_db` después de respaldo; pruebas unitarias 4/4, PostgreSQL 4/4, Vitest 9/9, Ruff, compileall, ESLint y build pasan; Svelte-check sin errores y con 8 avisos CSS existentes. Aceptación autenticada, matriz API/perfiles y concurrencia quedan para B08; B06 no iniciado. Ver `entrega-bloque-05.md` y `tmp/ers-v1/bloque-05/evidencia-2026-10-19.md`. |
| 19/10/2026 | Implementación y comprobaciones técnicas focalizadas ERS-B06 | Migración 0088 respaldada, ensayada sobre copia restaurada y aplicada a `erp_db`; inventario y valoración conservan huellas. Cliente, cotización, venta en borrador/confirmada/cancelada, permisos y pantallas implementados; E2E API/PostgreSQL, unit, Vitest, Ruff y build pasan. Al corte de B06, B07 todavía no iniciado; aceptación visual/autenticada y revisión completa reservadas a B08. Ver `entrega-bloque-06.md` y `tmp/ers-v1/bloque-06/evidencia-2026-10-19.md`. |
| 19/10/2026 | Implementación y verificación técnica focalizada ERS-B07 | Revisión 0089 ensayada sobre copia restaurada y aplicada a `erp_db` con respaldo. E2E FastAPI/PostgreSQL cubre parcial/final, promedio frente a precio, rollback, idempotencia, carreras y trazabilidad; B06 E2E de regresión pasa. Vitest focalizado, Ruff, ESLint focalizado, Svelte-check y build pasan. Suite frontend completa: 473 aprobadas y 1 fallo legado de almacenes, registrado sin ampliar B07. Aceptación autenticada, otras combinaciones de perfiles/sucursal y revisión integrada permanecen pendientes de B08. Ver entrega B07 y `tmp/ers-v1/bloque-07/evidencia-2026-10-19.md`. |

## Resultado técnico ERS-B07 y estado de E10–E15 (19/10/2026)

La E2E focalizada crea una base ficticia aislada, fija promedio de USD 10 y confirma una venta a precio comercial distinto; dos entregas consumen 3 y luego 2 unidades base y rebajan USD 50, dejando 8/USD 80. Prueba los vínculos de costo/movimiento por HU, el snapshot de empaque, otra sucursal, cuarentena, idempotencia, errores tardíos, dos ventas compitiendo por la última unidad, el límite del pendiente y la carrera cancelación/entrega. La carrera por la última HU encontró que el motor reportaba como 404 una unidad que se acababa de consumir; B07 traduce ese caso validado previamente como conflicto recargable 409. La repetición completa pasa. La migración no inventó entregas históricas. E10, E12 y E15 tienen evidencia técnica; E13 y el criterio A7 siguen parciales hasta probar más perfiles, ventas canceladas y mutaciones posteriores de entregas confirmadas.

| ID | Resultado técnico de B07 | Pendiente conservado para B08 |
| --- | --- | --- |
| E10 | Aprobado en E2E PostgreSQL: parcial/final, sucursal correcta, stock no elegible excluido y sobreconsumo concurrente rechazado sin cambiar el promedio global por bodega. | Recorrido autenticado de la venta, recarga, error de disponibilidad y confirmación en navegador. |
| E12 | Aprobado en E2E: issue por promedio global USD 10 aunque venta comercial sea USD 20; cantidad/valor antes y después se verifican con Decimal. El resultado de traslado no se altera. | Revisión integrada con traslados, ajustes, cambios de costo y devoluciones. |
| E13 | B07 agrega permisos específicos y valida alcance en endpoints; E2E automatizada usa `SUPER_ADMIN`, no es una matriz exhaustiva de roles ni de otra empresa. | Probar perfiles de lectura/operación, compañía y sucursal, incluidas respuestas idempotentes, en API/navegador. |
| E15 | 0089 aplicada con respaldo verificado y ensayo de restauración. Las huellas ordenadas de 22 tablas de empresa, ventas e inventario coinciden entre `erp_db` actualizado y la copia previa restaurada/migrada; las cuatro tablas B07 están vacías y no hay backfill. | Verificación de integración en navegador y conciliación durante revisión completa. |

Frontend B07: tres pruebas focalizadas del panel pasan; el svelte-check tiene cero errores y ocho avisos CSS existentes de `TransferOperationsPage.svelte`; ESLint focalizado de `src/lib/features/sales` y build pasan. La suite completa finaliza con 473 aprobadas y un fallo en `tests/unit/WarehouseHandlingUnitsIntegration.test.ts:192` (botón de fracción, fuera de B07; causa no diagnosticada en este bloque). No se declara aceptada la suite completa. La revisión integrada permanece pendiente.

## Resultado del cierre B08 e integración B01–B08 (19/10/2026)

**Estado actual:** B08 implementado y verificado técnicamente; revisión integrada **parcial**, no aceptada por completo. `erp_db` está en 0090. La tabla E01–E15 conserva los resultados por bloque documentados arriba; el cierre más reciente está en [revision-integral-bloques-01-08.md](revision-integral-bloques-01-08.md). La [entrega B08](entrega-bloque-08.md), el [manual](manual-pruebas-y-demostracion.md) y [evidencia fechada](../../tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md) son la referencia vigente.

| ID | Evidencia técnica más reciente | Estado de aceptación integrada |
| --- | --- | --- |
| E01–E05 | Migraciones y E2E B01/B02; preservación de datos verificada | Parcial: falta recorrido visual real de matriz, lote, etiqueta y Kardex |
| E06–E08 | Integración B03–B05 y verificaciones de motor, traslado y ajuste | Parcial: falta flujo persistido, perfiles/contextos y evidencia en pantalla |
| E09–E10 | E2E API/PostgreSQL B06/B07; invariantes de venta/entrega y costo probadas | Parcial: la demo no tiene ventas/entregas que recorrer y conciliar |
| E11–E12 | E2E B08 prueba costo original, límites, parcialidad e idempotencia | Parcial: retaceo tardío y concurrencia de aceptación requieren evidencia adicional |
| E13 | Pruebas RBAC seleccionadas por bloque; 403 sin permiso en B08 | Parcial: matriz completa de usuario, empresa, sucursal y costos no recorrida |
| E14 | Pruebas de cuarentena/liberación y migración | Parcial: falta recepción y retaceo integrado hasta disponibilidad |
| E15 | Respaldo previo a 0090 y comparación de 30 tablas con ensayo, cero diferencias | Parcial: falta conciliación tras ejecutar la demostración completa |

Suite frontend de cierre: 108 archivos / 483 aprobadas. `pnpm check`: cero errores y ocho avisos CSS existentes en Traslados. La regresión histórica de almacenes esperaba el texto “Preparar fracción”; la acción vigente es “Dividir unidad” y el componente conserva cobertura de cancelación sin mutación. El navegador autenticado validó la bandeja Devoluciones en estado vacío; la demo tiene cero clientes/ventas/entregas/devoluciones. No se requiere lector ni impresora físicos. La [evidencia](../../tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md) registra el alcance exacto.
 
## Estado final E01–E15 / P01–P04 — 20/10/2026

El estado vigente está en [cierre visual y permisos B01–B08](cierre-visual-y-permisos-b01-b08.md). La [matriz E13](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/matriz-permisos.md) incluye nuevos casos de descarga/adjuntos de ajustes, pero las acciones restantes de módulos no se infieren de esa prueba. Los casos de ajuste compensatorio, traslado parcial/final y devolución parcial multi-asignación están descritos en [registro P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

La ficha HU ahora muestra por separado el producto, el lote de fabricante, el detalle canónico y la cabecera de recepción. Vitest focalizado aprobó 47; Svelte-check 0 errores, ESLint enfocado y build aprobaron. El backend unitario completo pasó 753 con extras dev+ocr en el corte previo. Los cuatro SKU se reconsultaron de solo lectura.

La aceptación integral permanece **PARCIAL** por la matriz E13 no exhaustiva, PNG P02 no exportados, recepción visual repetida y filtros UI P03, además de devolución mixta y recuperación de respuesta desde UI P04.

## Actualización de verificación — 21/10/2026

La nueva ejecución cierra V04-01, V04-02 y V04-03 con UI + persistencia aislada; V03 ahora incluye QR público y abrir/cancelar división sin mutación. No se cuentan como aprobadas la matriz de permisos, los PNG, la recepción repetida en navegador ni la pérdida postcommit. Dictamen E01–E15 continúa **PARCIAL**; tabla vigente y pendientes exactos en [cierre B01–B08](cierre-visual-y-permisos-b01-b08.md) e [informe final V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md). Conciliación `READ ONLY`: cuatro SKU protegidos iguales en `erp_db` y clon.

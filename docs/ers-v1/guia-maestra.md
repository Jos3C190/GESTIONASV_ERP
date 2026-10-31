# Guía oficial de adaptación de GestionaSV a la ERS 1.0

Versión de la guía: 1.3. Fecha de actualización: 21/10/2026. Estado vigente: B01–B08 implementados y revisados con correcciones; aceptación integrada **PARCIAL**. V04-01/02/03 ya están probados desde UI con persistencia en una clon; V01, V02, V03 y V04-04 conservan pruebas de aceptación abiertas. No se requiere impresora ni lector físicos. Los resultados e impedimentos exactos están en el [cierre actual](cierre-visual-y-permisos-b01-b08.md), [informe V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md) y [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md). Los informes anteriores conservan su fecha y alcance.

**Continuación 21/10/2026:** la última lectura no alteró los SKU protegidos. La consulta de aliases identificó datos de cabecera/detalle para las pruebas UI; la sesión de navegador fue rechazada por política de seguridad de URL y no se eludió. RustFS real pasó una prueba de hash de subida/descarga; la ruta API de documentos se detuvo en login 401. La aceptación sigue parcial por V01/V02/V03-02/03/05 y V04-04. Ver [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md).

**Actualización de cierre del 20/10/2026:** Devoluciones también se inspeccionó en móvil 390×844, claro/oscuro y teclado; Traslados recibió una corrección móvil revisada. En la continuación final se comprobó el control documental de ajustes por alcance/permisos y se validaron operaciones parciales/corrección en PostgreSQL; la ficha de una HU real ya separa origen de recepción y detalle de lote. El cierre integrado sigue **PARCIAL** por la matriz E13, falta de PNG archivados, recepción visual de líneas repetidas y acciones UI de devolución mixta/recuperación. Ver [cierre vigente](cierre-visual-y-permisos-b01-b08.md) y [evidencia P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

## Objetivo y acuerdos

Completar el alcance de Inventario descrito en las páginas 105–115 de la ERS 1.0 conservando el sistema existente. El usuario encargó la arquitectura y documentación a este chat, y la construcción por bloques a Luna.

La sucursal matriz será una sede administrativa de recepción y distribución. La bodega central existente seguirá operando con su mismo identificador, ubicaciones, productos, existencias e historial. Se asociará a esa sucursal; no se duplicará la bodega ni su inventario. La matriz puede no operar como tienda. Debe ser un registro válido de sucursal, aunque se capture solo la información mínima exigida por el sistema.

El usuario incluyó ventas, devoluciones y ajustes documentados en el alcance cuando sean necesarios para cumplir la ERS. Para los ajustes se habilitará adjuntar evidencia. Se mantiene la demostración con datos ficticios y sin exigir lector ni impresión física.

Fuentes: [ERS 1.0](<C:/Users/rodri/Downloads/MiniERP ERS v1.0.pdf>) y [análisis con diferencias y evidencia de código](C:/Developer/GESTIONASV_ERP/docs/analisis-ers-v1-inventario-2026-10-17.md). Esta guía es una decisión de ingeniería del proyecto; no representa aprobación académica del docente.

## Ocho bloques y revisión integrada al cierre

Decisión del usuario del 18/10/2026: continuar con B03 y hacer la revisión completa al finalizar B08. Son ocho bloques de construcción; B08 incluye además la aceptación integrada que originalmente se llamó B09. Se conserva su archivo como checklist, sin encargo independiente. Cada bloque mantiene sus comprobaciones técnicas y documentación. Los recorridos visuales pendientes de B01/B02 se acumulan para ese cierre y no bloquean B03; siguen pendientes, no aprobados.

| Bloque | Resultado visible o técnico | Depende de | Encargo |
| --- | --- | --- | --- |
| ERS-B01 | Sucursal matriz y bodega central asociada, con permisos e historial conservados | Base actual | [Matriz](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-01-matriz.md) · [Entrega](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-01.md) |
| ERS-B02 | Lote por producto/recepción identificable en etiqueta, saldos y Kardex | B01 | [Lotes](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-02-lotes.md) |
| ERS-B03 | Documento de traslado, vehículo, ubicación de tránsito y transiciones en API | B01, B02 | [Motor de traslados](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-03-traslados-motor.md) |
| ERS-B04 | Despacho y recepción desde pantallas, demanda por sucursal e incidencias | B03 | [Operación de traslados](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-04-traslados-operacion.md) |
| ERS-B05 | Ajustes autorizados, documentos adjuntos y correcciones trazables | B02, B04 | [Ajustes](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-05-ajustes.md) · [Entrega](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-05.md) |
| ERS-B06 | Clientes mínimos, cotización de venta y venta confirmada sin entrega | B01, B05 | [Base comercial](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-06-ventas-base.md) |
| ERS-B07 | Entregas completas/parciales que descuentan inventario y costo de la sucursal correcta | B02, B06 | [Entregas](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-07-entregas.md) |
| ERS-B08 | Devoluciones vinculadas a entrega y revisión completa de B01–B08 al finalizar | B01–B07 | [Devoluciones y cierre](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-08-devoluciones.md) |
| Checklist antes B09 | Integrado en el cierre de B08; sin ejecución independiente | B01–B08 implementados | [Aceptación](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-09-aceptacion.md) |

Orden vigente: B01 → B02 → B03 → B04 → B05 → B06 → B07 → B08 (devoluciones y después revisión completa). No se fija una duración sin observar el avance. Si un bloque requiere subdivisión interna, conservar su número y criterios; documentar el motivo y la dependencia, sin añadir funcionalidades ajenas.

## Forma de trabajo entre arquitectura y Luna

1. El usuario entrega a Luna la ruta del encargo. Luna ejecuta únicamente ese bloque y las correcciones de dependencias que sean necesarias para cumplirlo.
2. Luna lee esta guía, [decisiones de arquitectura](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md), la fila vigente de [seguimiento](C:/Developer/GESTIONASV_ERP/docs/ers-v1/matriz-y-seguimiento.md) y su encargo. Lee el código relacionado; no necesita repetir la lectura de todo el historial ni de las 115 páginas para cada cambio.
3. La implementación mantiene las capas de dominio, aplicación, infraestructura y API; el frontend usa Svelte 5 y componentes del sistema. Aplican [reglas del proyecto](C:/Developer/GESTIONASV_ERP/.agents/AGENTS.md) y [skill de desarrollo](C:/Developer/GESTIONASV_ERP/.agents/skills/feature-development/SKILL.md). Los cambios de interfaz siguen el skill frontend-quality-studio aplicable a la sesión.
4. Luna registra qué cambió, por qué, qué comprobó y qué permanece pendiente. Puede resolver detalles rutinarios de implementación dentro del alcance. Cambios de política de costos, permisos entre empresas, significado de los estados o pérdida de historia se elevan como decisión explícita con alternativas y evidencia.
5. Este chat revisa el bloque contra sus criterios cuando el usuario lo solicite. Se revisan los cambios y casos relevantes; no se reaudita todo el ERP. No se envían mensajes a otros chats ni se inician otros modelos automáticamente por leer estos documentos.
6. Un bloque con solo código escrito permanece IMPLEMENTADO. VERIFICADO requiere pruebas y recorrido equivalentes al alcance; REVISADO añade la revisión independiente. Un impedimento se registra con el requisito afectado y la evidencia disponible.

## Contratos obligatorios compartidos

- Conservar IDs, códigos históricos, saldos, etiquetas ya registradas, solicitudes, consolidaciones y trazabilidad. Los archivos modificados por otros trabajos son parte del estado inicial; no hacer reset/clean ni revertirlos.
- El motor actual sigue siendo la fuente de movimientos y valoración. Los documentos nuevos lo invocan; no mantienen otro inventario ni calculan otro promedio en el frontend.
- Todo importe y cantidad se valida en servidor con precisión decimal y unidades base/conversiones existentes. El precio de venta se registra aparte del costo de inventario.
- Cada comando nuevo con efecto físico tiene documento de origen válido, actor, empresa, sucursal y ubicaciones autorizadas. Aplicar autorización también al reintentar una operación previamente registrada.
- Idempotencia por empresa, acción y clave; mismo cuerpo devuelve resultado, otro cuerpo da conflicto. Bloquear recursos compartidos en orden determinista y comprobar cantidades actuales dentro de la transacción.
- Documento, movimiento, HUs, saldos, valoración y auditoría de éxito se confirman juntos. Hay una particularidad real: [la sesión actual](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/db/session.py:81) hace commit al capturar AppError. Cada nuevo comando debe proteger su unidad de trabajo con rollback/savepoint ante errores de negocio y fallos inesperados. No cambiar globalmente ese comportamiento sin analizar autenticación y otros consumidores.
- Los historiales confirmados son inmutables. Las correcciones generan documentos/eventos nuevos enlazados. No actualizar o borrar movimientos históricos para que un reporte cuadre.
- La mercancía en cuarentena, tránsito o dañada no se ofrece como disponible. Abrir, cerrar o cancelar un formulario no crea movimientos ni divisiones. Dividir una HU es opcional y explícito.
- Los permisos de operación y de consulta de costo son distintos. Un usuario de sucursal no recibe importes globales o datos de otras sucursales solo porque la interfaz los oculte.
- El estado de carga, error o permiso insuficiente nunca se presenta como cantidad cero o ausencia real de solicitudes.

## Datos, migraciones y entorno

Usar migraciones nuevas desde la cabeza real de Alembic; 0083 es el antecedente observado, no un número que deba asumirse en el futuro. Registrar cabeza antes/después. Ensayar el esquema y la migración de datos con registros existentes en una copia o base aislada, y demostrar conservación de saldos y referencias antes de aplicarla a la demo habitual.

El usuario autorizó asociar la bodega central a la matriz. La selección se realiza por empresa e identidad verificada; nunca por el primer UUID o el primer nombre que coincida. Se permite crear la sucursal mínima si falta. Para la demo ficticia pueden reutilizarse datos válidos de domicilio/geografía de la empresa, indicando su procedencia. No inventar coordenadas si las validaciones las exigen y no se cuenta con una fuente identificada; resolver ese dato mediante configuración o captura explícita, conservando el resto del trabajo.

No ejecutar semillas que limpien o reemplacen datos de la demo para aplicar estos cambios. Un script de adaptación debe ser idempotente, mostrar una simulación, registrar los IDs afectados y tener plan de recuperación. Hacer respaldo antes de alterar los datos existentes; no publicar credenciales ni DSN completos.

Las suites de integración/E2E reconstruyen el esquema. Antes de recolectarlas, leer [fixtures](C:/Developer/GESTIONASV_ERP/backend/tests/conftest.py) y verificar ambos DSN: solo erp_db_test. Ejecutarlas en serie; nunca mientras el navegador de aceptación utiliza esa misma base. Comprobar la API y frontend concretos que usa el usuario: una prueba aislada no demuestra que la base habitual tenga sus migraciones.

Buscar runtimes/dependencias ya disponibles, incluidos los contenedores, antes de declarar un bloqueo o reinstalar paquetes. Registrar únicamente procesos propios y sus puertos; preservar servicios ajenos.

## Pruebas y condición de entrega de cada bloque

Para cambios con persistencia: prueba unitaria de reglas, integración PostgreSQL de invariantes/rollback/concurrencia pertinente y contrato API con perfiles global, sucursal y otra empresa. Para interfaz: pruebas de comportamiento con Vitest, tipos Svelte, lint de archivos tocados, build cuando el cambio lo requiera y registro del recorrido autenticado pendiente de las pantallas modificadas para la revisión completa al cierre B08, según la decisión vigente del usuario. Las simulaciones deben identificarse como tales.

No perseguir un número arbitrario de tests. Cada criterio tiene una comprobación equivalente que puede reutilizarse. Después de pasar los casos pertinentes, repetirlos solo si hay cambios, fallos o dudas nuevas. Ningún resultado de una entrega anterior cuenta como ejecución actual.

Registrar por bloque: migraciones, rutas/contratos, permisos, ejemplo operativo, prueba de datos antiguos, casos nuevos, comando y resultado reales, destino no secreto, alcance del navegador y cualquier límite. Si una herramienta falta, dejar el criterio pendiente y completar lo independiente; no declarar la entrega verificada basándose únicamente en compilación.

## Documentación por entrega

Cada bloque crea o actualiza su archivo entrega-bloque-NN.md dentro de C:\Developer\GESTIONASV_ERP\docs\ers-v1, con esta estructura:

1. Estado y alcance terminado; fecha y versión/cambios de referencia.
2. Requisitos y decisiones aplicadas, más cualquier divergencia de la ERS.
3. Archivos/contratos/migraciones/permisos afectados.
4. Procedimiento de actualización y recuperación; datos previos y posteriores.
5. Tabla criterio → prueba → resultado → evidencia; diferenciar no ejecutado de aprobado.
6. Pasos de uso y resultados visibles en lenguaje de usuario.
7. Pendientes concretos, diagnóstico y siguiente paso.

Actualizar también la matriz central, API, esquema de base de datos y RBAC cuando cambien. Conservar los informes previos; añadir las nuevas revisiones sin borrar fallos históricos. Guardar evidencia reproducible con fecha en tmp/ers-v1/bloque-NN; no exponer secretos ni archivos personales.

## Corte histórico después de B03

B03 se implementó y verificó técnicamente el 19/10/2026; sus contratos y evidencia están en [entrega B03](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-03.md) y `tmp/ers-v1/bloque-03/`. No se inició B04. El siguiente bloque de la secuencia es [operación de traslados B04](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-04-traslados-operacion.md), que agregará las pantallas sobre el API ya publicado. La revisión visual de B01–B03 permanece pendiente para el cierre integrado de B08.

## Estado después de B04

B04 conectó **Traslados** y la acción desde **Almacenes** al mismo flujo documental B03. La demanda por sucursal, preparación, vehículos, despacho explícito, recepción parcial, cuarentena e incidencias están disponibles en la interfaz. Las comprobaciones técnicas focalizadas pasan y la revisión final de código UI obtuvo 8.5/10; esto no equivale a aceptación visual en el navegador. El detalle está en [entrega B04](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-04.md) y su evidencia fechada en `tmp/ers-v1/bloque-04/evidencia-2026-10-19.md`.

El endpoint genérico de movimientos sigue disponible para operaciones legítimas dentro de la bodega; ahora rechaza movimientos de traslado entre bodegas o hacia/desde tránsito sin documento B03. No se cambió el esquema en B04. La revisión autenticada integral, roles en navegador, recorrido móvil y aceptación visual se ejecutarán al finalizar B08.

## Estado después de B05

B05 implementa el documento de ajuste con soporte versionado, aprobación y aplicación explícitas sobre el motor vigente. La migración 0087 añade historial de ajustes y la cantidad ajustada fuera del tránsito; el faltante solo se cierra después de una incidencia y aprobación, sin registrarlo como recibido. Kardex permite consultar por referencia de ajuste y conservar el contexto. Las pruebas unitarias, de integración PostgreSQL y frontend focalizadas pasan; el respaldo y la conciliación de la demo están registrados en [entrega B05](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-05.md) y [evidencia fechada](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-05/evidencia-2026-10-19.md). La aceptación autenticada/visual, la matriz completa de perfiles API y los casos de concurrencia no se declaran aceptados aquí; se consolidarán con la revisión B08. La referencia a B06 como siguiente bloque corresponde al corte previo al encargo de ventas y queda reemplazada por el estado posterior documentado abajo.

## Estado después de B06

B06 añade el catálogo básico de clientes, cotizaciones de venta y ventas originadas por cotización. La migración 0088 está aplicada a la demo con respaldo y ensayo aislado; su operación comercial no reserva ni modifica inventario. Las pruebas focalizadas cubren API/PostgreSQL, permisos y alcance, idempotencia, concurrencia, rollback de una segunda línea y auditoría tardía, y huellas físicas/de valoración sin cambios. El resultado detallado, los contratos para B07 y los casos pendientes están en [entrega B06](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-06.md), [manual operativo](C:/Developer/GESTIONASV_ERP/docs/ers-v1/manual-ventas-base.md) y [evidencia técnica](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-06/evidencia-2026-10-19.md).

La aceptación visual autenticada de clientes → cotización → venta, móvil, temas, cambio de contexto y recorrido manual sigue pendiente para B08. B06 no incluye entregas, devoluciones, facturación, impuestos, cobros, reservas ni precios derivados del costo. En el corte de B06 el siguiente bloque era B07; ese estado quedó superado por el cierre técnico descrito a continuación.

## Estado después de B07

B07 implementa entregas parciales o completas desde ventas confirmadas. La migración `0089` agrega documentos, líneas, asignaciones y comandos idempotentes enlazados a ventas, HUs, movimientos y valoración. Solo se consumen HUs completas disponibles en la sucursal de la venta; confirmar descuenta stock y aplica el promedio ponderado vigente de empresa/artículo en la misma transacción. El pendiente comercial se deriva de entregas confirmadas y el costo aplicado queda guardado para el flujo de devoluciones B08, sin exponerse en los DTOs comerciales.

La entrega y evidencia fechada están en [B07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-07.md) y [su evidencia técnica](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-07/evidencia-2026-10-19.md); los pasos operativos están en [manual de entregas](C:/Developer/GESTIONASV_ERP/docs/ers-v1/manual-entregas.md). La validación automatizada focalizada no sustituye los recorridos autenticados de navegador: venta → entrega parcial/final → Kardex/conciliación, permisos/contexto y recuperación de una confirmación cuya respuesta se perdió permanecen para B08 junto a los pendientes B01–B06. No se implementaron devoluciones. El siguiente bloque es B08; no se declara aceptación integral antes de terminarlo.

## Estado de cierre B08 (19/10/2026)

B08 incorpora devoluciones de cliente enlazadas a las asignaciones de entrega originales, recepción/revisión parcial, aceptación o rechazo, costo de origen, eventos idempotentes, permisos, evidencia documental y navegación global **Devoluciones** en `/sales/returns`. La migración 0090 está aplicada en la demo. La E2E de devoluciones pasa y la suite de frontend reporta 483/483; los detalles, límites y avisos están en [entrega B08](entrega-bloque-08.md) y [evidencia](../../tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md).

La aceptación integral queda **PARCIAL**, no cerrada como aceptada. El navegador autenticado confirmó que la bandeja de Devoluciones se abre y presenta el estado vacío correctamente, pero la demo muestra cero clientes, ventas, entregas y devoluciones. Por ello no existe una transacción real en la demo para recorrer y conciliar desde compra hasta devolución. También falta demostrar en esa ruta el retaceo tardío, concurrencia de aceptaciones y la matriz completa de perfiles/empresas. Los pasos reproducibles y saldos esperados están en [manual de pruebas y demostración](manual-pruebas-y-demostracion.md). Para completar la aceptación, crear los documentos ficticios por las pantallas normales según el manual; no limpiar datos ni usar una semilla destructiva.
 
## Cierre visual y permisos B01–B08 — corte vigente 20/10/2026

El estado más reciente está en [cierre visual y permisos](cierre-visual-y-permisos-b01-b08.md). La continuación final agregó pruebas de permisos/documentos de ajustes y operaciones parciales/correcciones persistidas; también corrigió la presentación del lote en una HU real. El detalle se enlaza desde [revisión B01–B08](revision-completa-2026-10-19.md) y [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

El corte previo ya verificó Devoluciones en móvil 390×844 y claro/oscuro, y pasó backend unitario 753 con extras dev+ocr. En esta última continuación pasaron 47 Vitest focalizadas, Svelte-check sin errores, ESLint enfocado y build. Los cuatro SKU protegidos se reconsultaron sin escritura.

La aceptación integral sigue **PARCIAL** por la matriz E13 no exhaustiva, falta de PNG exportados, recepción visual con líneas repetidas y algunos recorridos UI de devolución mixta/recuperación. No existe un bloque funcional B09 ni se requieren dispositivos físicos.

## Estado final de verificación — 21/10/2026

V04-01, V04-02 y V04-03 se probaron desde UI en el clon y conciliaron; V03 añade consulta QR pública y cancelación de división sin mutación. V01 permanece abierto por permisos/documentos; V02 por PNG no archivados; V03 por recepción repetida y consultas restantes; V04-04 por respuesta perdida postcommit no simulada en navegador. No se recomienda otro bloque de implementación funcional; el cierre de aceptación depende de ejecutar estas cuatro acciones exactas. Ver [cierre vigente](cierre-visual-y-permisos-b01-b08.md) y [registro de casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md).

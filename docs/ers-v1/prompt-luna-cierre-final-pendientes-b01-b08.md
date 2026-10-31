# Encargo para Luna — cerrar pendientes verificables B01–B08

Preparado el 20/10/2026, America/El_Salvador, después de revisar tu informe de cierre visual/permisos.

## Objetivo y autorización

Ejecuta los pendientes de aceptación que quedaron en el cierre B08, corrige los defectos que reproduzcas y documenta resultados verificables. Este encargo continúa el anterior; B09 es su checklist histórico. No implementes otro bloque funcional ni entregues otro prompt como sustituto del trabajo.

El informe anterior es parcial y sus pruebas aprobadas siguen siendo evidencia útil. El trabajo ahora consiste en resolver los huecos concretos P01–P06. No amplíes el alcance a fiscalidad, cobros, dispositivos o una reescritura ORM/puertos. No se necesitan impresora, lector HS200 ni colocación física de etiquetas.

No estás solo en el repositorio. Conserva cambios ajenos, documentos y evidencia; no hagas reset/clean, semillas destructivas ni cambios de permisos a usuarios reales. La autorización cubre pruebas y correcciones necesarias en este alcance; no pidas confirmaciones rutinarias.

## Lectura y conservación

Trabaja en C:/Developer/GESTIONASV_ERP/. Lee:

1. .agents/AGENTS.md y los skills aplicables. Aplica frontend-quality-studio al corregir una UI; la revisión independiente debe identificar la pantalla y versión realmente evaluadas.
2. docs/ers-v1/revision-astra-informe-luna-cierre-2026-10-20.md.
3. docs/ers-v1/cierre-visual-y-permisos-b01-b08.md y la evidencia de tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/.
4. docs/ers-v1/prompt-luna-cierre-visual-y-permisos-b01-b08.md, revision-completa-2026-10-19.md y manual-pruebas-y-demostracion.md. Conserva los pendientes originales que una adenda no haya demostrado.
5. API/RBAC/esquema, decisiones de arquitectura y contratos/pruebas actuales de los módulos que revises.

Registra Git, servicios, base real de la API y Alembic antes de ejecutar. La referencia anterior era erp_db, 0090, frontend 5173/API 8000; comprueba el estado actual.

| SKU preservado | Físico = valorado | Valor USD |
| --- | ---: | ---: |
| ERS-REVIEW-DD6BBF85 | 12 | 160 |
| ERS-INC-EE8FE228 | 4 | 40 |
| ERS-LATE-B1B55D6D | 5 | 60 |
| ERS-UI-F767BABC | 0 | 0 |

Consulta esos cuatro casos antes/después. No repitas sus escrituras ni reabras el corte inicial. Para escrituras usa otros SKUs/documentos ficticios con prefijo identificable y conserva sus IDs. Usa actores ficticios controlados o un entorno estable aislado para UI/perfiles; explica dónde opera cada prueba. No cambies la conexión de la app habitual mientras se usa.

Antes de recolectar integración/E2E, comprueba las fixtures y la guarda de nombre de base: solo erp_db_test. Se reconstruye por caso; ejecuta estas pruebas en serie y separadas de cualquier navegador que dependa de esa misma base. No expongas credenciales ni URLs firmadas. Si un cambio exige migración/datos de demo, respalda y ensaya en copia aislada antes; no es necesario repetir migraciones/restauraciones sin cambios que lo justifiquen.

## P01 — Matriz finita de autorización y documentos

Primero inventaría las acciones que realmente implementan los routers/contratos B01–B08: matriz/bodegas, lotes/etiquetas, traslados/incidencias, ajustes, clientes/cotizaciones/ventas, entregas/devoluciones, Kardex/valoración y adjuntos enlazados. Guarda una fila por endpoint/acción aplicable con permiso requerido y regla de empresa/sucursal/origen.

Para cada fila registra: caso, perfil, contexto, método/ruta, acción, esperado, observado, prueba/aserción, log/captura y resultado. Cubre usuario sin permiso, lector sin costos, operador autorizado de sucursal y responsable con alcance de empresa; además permiso presente con otra sucursal u otra empresa cuando ese ámbito aplique. Marca no aplica solo con razón concreta del contrato. No inventes acciones ni roles nuevos ni exijas un producto cartesiano de combinaciones sin sentido.

Mapea las pruebas existentes a sus aserciones. Las 33 E2E reportadas incluyen flujos funcionales; no son 33 pruebas exclusivamente de E13. En las cinco pruebas seleccionadas de purchase_orders hay cuatro denegaciones por permiso y una autorización de lectura central con alcance limitado: descríbelas individualmente. Reutiliza registros válidos y ejecuta los huecos de mayor riesgo primero, especialmente ajustes/incidencias, etiquetas y documentos.

Adjuntos: iniciar/subir/completar, listar, ver/obtener enlace/descargar y quitar cuando exista; comprobar origen, propiedad, validación, empresa/sucursal y acceso directo a ID ajeno. Tras cambiar contexto o retirar acceso, una nueva petición de autorización/descarga debe respetar la política real. No uses caducidad de URL como prueba de permiso; documenta la semántica de las capacidades firmadas sin publicarlas. Revisa adjuntos de costos con un lector sin valoración.

Comprueba las guardias UI y el rechazo del servidor. Prueba replays tras perder permiso/alcance; ninguna respuesta debe filtrar costos globales. Una denegación o fallo tardío no debe dejar cantidad, valoración o auditoría de éxito parciales.

## P02 — UI pendiente con evidencia guardada

Convierte el informe en un checklist finito por estas siete familias: (1) matriz/bodega, (2) recepción/lotes/medidas/etiqueta, (3) demanda/traslados/incidencias, (4) ajustes/correcciones/adjuntos, (5) clientes/cotización/venta, (6) entregas/devoluciones y (7) Kardex/conciliación. Identifica las pantallas y operaciones aún sin evidencia; consulta las ya terminadas.

Verifica escritorio y móvil real 390×844, claro/oscuro, foco visible y Tab/Escape/apertura/cierre/devolución de foco de diálogos aplicables. Guarda PNG con ruta, tema, tamaño, perfil y caso. Captura antes/después de cada defecto; no basta una captura de otra versión. En tablas puede existir scroll interno usable; no debe haber desbordamiento exterior ni acciones cortadas.

Devoluciones tiene aprobación independiente de escritorio 8.56/10 y claro/oscuro observado, pero no captura archivada actual ni prueba móvil. Completa esos huecos y teclado. Conserva unidad sin sufijo repetido, colores semánticos y anuncio del filtro. No vuelvas a rediseñar la bandeja por no tener puntuación de otras pantallas.

Comprueba carga, vacío, error con reintento, validación, permiso insuficiente, operación en curso y éxito tras recargar en los casos aplicables. Para estados forzados mediante una interrupción o respuesta simulada, indícalo expresamente; registra aparte la operación con API/persistencia real. Si una capacidad de herramienta no permite tamaño/captura, explica el impedimento y continúa los casos independientes; no declares móvil usando una captura de escritorio.

## P03 — Recepción, origen y alias históricos

Consulta o prepara un caso nuevo con varias líneas de compra del mismo producto y las recepciones parciales pertinentes. Desde la pantalla verifica cabecera de recepción, detalle/lote canónico, cantidad y origen de cada línea; conservar identidades aunque se agrupe la presentación. Repite lectura/recarga sin generar lotes ni existencias adicionales.

Obtén del contrato/código la lista finita de alias históricos realmente soportados. Para cada tipo existente prueba lote/etiqueta/QR/Kardex con un registro real apropiado y guarda el resultado. No adivines combinaciones de códigos. Un registro legado sin origen reconstruible debe seguir identificado como legado; no inventes recepción o lote. Revisa la política pública del QR y el rechazo de información privada ajena.

Abrir/cerrar/cancelar división, ver QR y revisar/reimprimir no cambian cantidad ni crean ramas. Solo una división confirmada lo hace y conserva la suma. Mantén demanda por producto con sucursal solicitante, pendiente y destino preseleccionado; envío adicional requiere motivo. El flujo termina en «Revisión terminada · disponible para uso» sin otra división obligatoria.

## P04 — Operaciones y recuperación que no deben perderse del encargo original

Revisa primero los casos ya acreditados y completa únicamente la evidencia faltante:

- Corrección de ajuste desde su UI: guarda motivo/origen/evidencia, conserva el original y comprueba la reversión/enlace que permita el contrato. No edites movimientos aplicados.
- Recepción parcial y final de traslado desde pantalla, con cantidades pendiente/recibida/tránsito e impacto global neutro; conserva el origen y el vehículo cuando aplique.
- Devolución con revisión mixta/parcial desde pantalla: aceptar una parte, rechazar otra y resolver el resto, respetando costo efectivo de entrega y cuarentena. La recepción documental y el rechazo no suman stock. Usa un caso nuevo calculable; por ejemplo partida 6/USD 60, entrega 3 a costo 10 → saldo 3/USD 30; devolución documental de 3 mantiene 3/30; aceptar 1 → 4/40; rechazar 1 mantiene 4/40; aceptar la última → 5/50. Adapta el ejemplo al contrato y documenta cualquier redondeo real.
- Selección de varias HUs/asignaciones y una venta con más de una entrega. Si cada devolución se vincula a una sola entrega, comprueba el selector y sus asignaciones sin añadir una devolución multi-entrega no soportada.
- Recuperación por pantalla de una confirmación/aplicación cuya respuesta se perdió: usa datos nuevos e interrupción controlada; consulta si el servidor aplicó el comando antes de reintentar y reutiliza la clave idempotente. Verifica una sola operación, un solo efecto físico/valorado y estado persistido al recargar. Cubrir un flujo de ajuste y uno comercial si sus mecanismos son distintos; reutiliza evidencia válida del componente compartido.

Un caso fallido debe tener causa, corrección, regresión útil y repetición del mismo caso en navegador. No declares una corrección nueva solo porque una prueba pendiente pase.

## P05 — Entorno OCR y regresiones necesarias

pikepdf ya figura en el extra opcional ocr de backend/pyproject.toml. backend/Dockerfile separa la etapa OCR de la API. El error de recolección del backend base no demuestra un defecto de inventario ni justifica añadir OCR a dependencias globales.

Identifica el entorno oficial de pruebas. Ejecuta la suite completa en un entorno reproducible con Python compatible y extras dev+ocr usando el lock del proyecto, o particiona explícitamente base/OCR y comprueba ambas en sus entornos adecuados. Guarda comando y resultado. No uses skip/importorskip, elimines pruebas o hagas pip install manual en el contenedor habitual para declarar éxito. Si aparece un fallo real, diagnostícalo y corrígelo dentro del alcance; no actualices dependencias ajenas sin necesidad.

Para los cambios ejecuta regresiones pertinentes, tipos, lint focalizado y build. La referencia previa era frontend 116/513, backend focalizado 25, tipos 0 errores/8 avisos CSS y build aprobado. No repitas toda la batería al inicio ni varias veces sin cambios/fallos nuevos. Los avisos conocidos @apply, jsbarcode y adapter-auto no son defectos funcionales por sí solos ni requieren desplegar el proyecto.

## P06 — Evidencia y cierre coherente

Actualiza docs/ers-v1/cierre-visual-y-permisos-b01-b08.md y su matriz. Guarda esta nueva pasada bajo tmp/ers-v1/cierre-visual-y-permisos/AAAA-MM-DD/pasada-final/ para conservar lo anterior. Registra comando, versión/archivos relevantes, fecha, base aislada, resultado y enlace al log/captura. Los registros anteriores de 23 E2E deben mapearse a nodos/resultados verificables; si falta evidencia recuperable, ejecuta solo esa selección una vez y guárdala. No sumes repeticiones como casos nuevos ni presentes un resumen manual como salida cruda.

En E01–E15 indica cumplido en el alcance definido, pendiente concreto o no aplica con razón. La ausencia de una repetición de migración/restauración no es por sí sola un pendiente si se mantiene la misma migración y el ensayo anterior válido. Conserva la evidencia y repite únicamente cuando haya cambios que la invaliden.

Actualiza revisión actual, entrega B08, matriz de seguimiento, preparación, guía y manual. Coloca al inicio un enlace al estado vigente y marca los cortes superados como históricos; evita otra cadena de adendas contradictorias. Actualiza API/esquema/RBAC solo si cambian contratos, esquema o permisos. Documenta cada defecto corregido y los pasos manuales de la demostración.

Conciliación final de los cuatro casos preservados y cada SKU nuevo: esperado/real, físico, valorado, valor, documentos e historial sin duplicación. Restaura tamaños/tema temporales y deja los servicios de demostración operativos.

## Criterio de entrega

Cierra P01–P06 con evidencia y corrige los defectos reproducidos dentro de su alcance. No exijas nuevas variantes ilimitadas para dar por terminado un caso finito ya demostrado. Si un impedimento real deja un caso abierto, consérvalo como parcial e identifica ID, último estado, lo intentado y siguiente acción exacta; la falta de hardware no es impedimento.

La respuesta final debe explicar qué quedó comprobado, qué se corrigió, qué sigue abierto si lo hay, conciliación final y enlaces a informe/manual/evidencia. El usuario realizará después su demostración manual; no declares aprobación del docente ni aceptación total sin evidencia.

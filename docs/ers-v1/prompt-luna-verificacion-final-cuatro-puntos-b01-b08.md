# Encargo para Luna — verificación final de cuatro puntos B01–B08

Preparado el 20/10/2026, America/El_Salvador.

## Objetivo y límite de cierre

Ejecuta y documenta los cuatro pendientes concretos del cierre B01–B08: permisos, evidencia de pantallas, recepción/trazabilidad y operaciones/recuperación. Corrige los defectos que reproduzcas y repite el caso que falló. Entrega el resultado ejecutado; no otro prompt.

Este es un único encargo de aceptación final dentro de B08. B09 es el checklist histórico integrado. No agregues módulos, políticas contables nuevas, fiscalidad, cobros ni integración de dispositivos. No se requieren impresora, lector HS200 ni colocación física de etiquetas.

Si los cuatro puntos quedan aprobados y la conciliación final es correcta, declara cerrada la implementación y verificación del alcance B01–B08, dejando al usuario su demostración manual y la evaluación del docente. No prometas aprobación académica. No amplíes los criterios con variantes ilimitadas; un caso finito ya demostrado se conserva.

## Lectura y estado de partida

Trabaja en C:/Developer/GESTIONASV_ERP/. Lee:

1. .agents/AGENTS.md y los skills aplicables. Usa feature-development para correcciones y frontend-quality-studio cuando realmente modifiques o audites una UI.
2. docs/ers-v1/cierre-visual-y-permisos-b01-b08.md, especialmente “Pendientes exactos de aceptación”.
3. docs/ers-v1/revision-astra-informe-luna-cierre-2026-10-20.md.
4. tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/matriz-permisos.md.
5. tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md, alias-trazabilidad.md y p03-trace-lot-ui-readonly.md.
6. tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/comandos-y-resultados.md, los contratos/pruebas del caso revisado y docs/ers-v1/manual-pruebas-y-demostracion.md.

La referencia anterior era frontend 5173, API 8000, erp_db y Alembic 0090; comprueba el entorno actual. Conserva los cambios ajenos y todos los logs anteriores. No hagas reset/clean ni semillas destructivas.

Ya hay evidencia aprobada de permisos documentales de ajustes, corrección compensatoria, traslado parcial/final y entrega/devolución parcial mediante API/PostgreSQL. También hay 47 pruebas frontend focalizadas, Svelte-check sin errores, lint y build aprobados. Backend unitario pasó 753 con extras dev+ocr. No repitas suites completas sin cambio o fallo que lo justifique.

Los nodos reales de referencia son:

- tests/e2e/test_inventory_adjustment_permissions.py::test_adjustment_evidence_download_requires_valuation_permission.
- tests/integration/test_inventory_adjustment_repository.py::test_ordinary_negative_adjustment_correction_preserves_origin_and_compensates_value.
- tests/integration/test_inventory_transfer_repository.py::test_transfer_preparation_dispatch_partial_receipt_and_idempotent_replay.
- tests/e2e/test_sales_deliveries.py::test_sales_delivery_partial_cost_idempotency_concurrency_and_rollback.

Sus últimas re-ejecuciones tienen comando y salida en pasada-final/p01-adjustment-document-permission-rerun.log, p04-adjustment-transfer-focused-rerun.log y p04-sales-delivery-returns-focused-rerun.log. No cuentes repeticiones como casos nuevos ni atribuyas resultados a nodos inexistentes.

## Conservación y entorno de ejecución

Consulta antes y después, en solo lectura, estos cuatro SKU:

| SKU protegido | Físico = valorado | Valor USD |
| --- | ---: | ---: |
| ERS-REVIEW-DD6BBF85 | 12 | 160 |
| ERS-INC-EE8FE228 | 4 | 40 |
| ERS-LATE-B1B55D6D | 5 | 60 |
| ERS-UI-F767BABC | 0 | 0 |

No repitas sus escrituras, no reabras el corte inicial y no alteres permisos de usuarios reales. Usa actores y datos ficticios nuevos con prefijo ERS-FINAL-4P y guarda sus IDs.

Para pruebas con PostgreSQL verifica primero backend/tests/conftest.py y su guarda de erp_db_test. Ejecútalas en serie. Las E2E reconstruyen la base: no mantengas un recorrido de navegador contra esa base mientras pytest la reconstruye. Para UI con persistencia prepara un entorno aislado y estable con API/frontend propios, registra sus direcciones/base y no cambies la conexión de la app habitual. Si se necesita una migración por una corrección, respalda y ensaya en copia antes de aplicarla.

## Orden de trabajo

Ejecuta V01 → V04 → V03 → V02. Reutiliza los mismos recorridos UI y datos nuevos para obtener evidencia visual de V02, sin duplicar operaciones para tomar capturas.

Antes de ejecutar crea un registro finito con ID, acción/ruta, actor/alcance, esperado, evidencia previa reutilizable y prueba pendiente. Extrae las acciones del código real. No marques un criterio por inferencia desde superadmin ni por el número total de pruebas.

## V01 — Permisos y documentos restantes (P01/E13)

Completa un inventario por método/ruta/acción de las capacidades implementadas en B01–B08: matriz/bodegas; lotes/etiquetas/QR; traslados/incidencias; ajustes; clientes/cotizaciones/ventas; entregas/devoluciones; Kardex/valoración; y adjuntos enlazados.

Por fila registra permiso, regla de empresa/sucursal/origen, perfil, resultado esperado/observado, nodo/aserción y log. Vincula la evidencia existente. Agrupa casos solo cuando compartan exactamente la misma guarda y regla de alcance, indicando las rutas representadas; una prueba de un módulo no acredita otro.

Cubre, donde aplique al contrato: falta de permiso; lector sin costos; operador de sucursal autorizado; responsable de empresa; permiso presente con recurso de otra sucursal/empresa; y nueva petición o replay tras perder acceso. La UI debe ocultar o bloquear la acción y el servidor rechazar el acceso directo.

Para documentos de los módulos pendientes prueba las operaciones que existan: iniciar/subir/completar, listar/ver, obtener enlace/descargar y retirar. Verifica vínculo al origen, empresa/sucursal, documento ajeno, vínculo retirado y nueva autorización tras cambio de contexto. Usa un archivo ficticio inocuo y comprueba bytes descargados en un flujo real permitido si el almacenamiento de prueba está configurado. No declares descarga real usando solo un stub de URL.

Conserva la política actual: una URL firmada ya emitida es una capacidad temporal; retirar permisos debe impedir nuevas emisiones, no se exige revocar retroactivamente esa URL antes del vencimiento. No guardes URLs firmadas ni secretos en evidencia.

Aceptación V01: cada acción aplicable inventariada tiene evidencia válida o un “no aplica” con razón del contrato. No quedan celdas genéricas “todos los demás módulos” sin resolver. Si falta infraestructura documental, identifica servicio/configuración exacta, fallo observado y acción necesaria; no lo presentes como defecto de permisos.

## V04 — Operaciones parciales y recuperación desde interfaz (P04)

Ejecuta desde navegador autenticado con persistencia real los casos que todavía no tienen esa modalidad de evidencia:

1. Corrección de ajuste: crear la corrección desde el original aplicado, comprobar vínculo/motivo/origen/evidencia, aprobar/aplicar según el contrato y conservar el documento/movimiento original.
2. Traslado parcial/final: preparar y despachar 10 unidades nuevas; recibir 8 y después 2 desde la pantalla. Comprobar pendiente, recibido, tránsito, ubicación destino y valor global neutro; conservar lote/origen y vehículo cuando aplique.
3. Devolución mixta/parcial: seleccionar asignaciones reales de una venta con más de una entrega y varias HUs. Cada devolución debe vincularse a la entrega permitida por el contrato. No inventes una devolución multi-entrega. Partida calculable sugerida: 6 unidades/USD 60 → entregar 3 a costo 10 deja 3/USD 30 → recepción documental de devolución de 3 mantiene 3/30 → aceptar 1 deja 4/40 → rechazar 1 mantiene 4/40 → aceptar la restante deja 5/50. Respetar cuarentena, costo efectivo original y precisión completa. Registrar la decisión mixta y el saldo pendiente conforme al contrato.
4. Respuesta perdida: un flujo de ajuste y uno comercial si sus mecanismos son diferentes. Descartar controladamente la respuesta después de que el servidor reciba y persista el comando. Consultar el estado antes de reintentar; reutilizar la clave idempotente. Comprobar tras recargar una sola operación, un solo efecto físico/valorado y auditoría coherente. Registrar cómo se provocó la pérdida y cómo se confirmó la persistencia. Un error simulado antes de enviar no acredita este caso.

Aceptación V04: UI y lectura persistida concuerdan con los saldos/estados esperados; original conservado, sin duplicación ni éxito parcial. Pruebas de componentes con mocks siguen siendo regresiones útiles, pero no sustituyen este recorrido.

## V03 — Recepción e identidad de origen (P03)

Comprueba en pantalla una compra/recepción con varias líneas del mismo producto y las recepciones parciales aplicables. Verifica producto y unidad/presentación, cabecera, detalle canónico, cantidad y origen de cada línea. Reabrir/recargar debe conservar identidades y cantidades.

Primero comprueba el contrato: si prohíbe duplicar un SKU en la misma compra, no elimines esa validación solo para satisfacer la prueba. Cita la restricción y demuestra el caso legítimo equivalente de varias recepciones parciales del mismo producto, con aprobación del criterio documentada por esa razón técnica y conservando origen por detalle/recepción.

Usa la lista finita de alias-trazabilidad.md. Para cada tipo con registro aplicable verifica la consulta desde la UI de lote/etiqueta/QR/Kardex donde el contrato lo admita: cabecera de recepción, detalle canónico, literal histórico de movimiento y resolución histórica sin FK directa. Una HU legítima sin lote debe conservar esa condición; no fabriques origen ni alias.

La ficha HU ya fue corregida para separar lote de fabricante, detalle y cabecera; conserva ese arreglo. Abrir/cerrar/cancelar división, consultar QR o revisar etiqueta no debe crear ramas ni cambiar stock. Solo dividir con confirmación explícita cambia las HUs y conserva la suma. La disponibilidad termina en “Revisión terminada · disponible para uso”; no requiere dividir ni reimprimir de nuevo.

Mantén nombre/SKU/presentación del producto visibles, demanda por sucursal y destino contextual; exceso de envío exige motivo. Comprueba que el QR público exponga únicamente la política autorizada y que el acceso privado ajeno sea denegado.

Aceptación V03: identidades/cantidades persistidas y visibles, consultas aplicables demostradas y recargas sin duplicación. Para un alias histórico no existente en la demo usa una fixture histórica aislada si es viable; “sin dato aplicable” exige consulta registrada y motivo. No se crea un requisito de migración histórica nueva.

## V02 — Evidencia visual finita de las pantallas pendientes (P02)

Completa esta muestra de siete familias utilizando las operaciones V01/V04/V03 ya realizadas:

| Familia | Vista/operación representativa |
| --- | --- |
| Matriz/bodega | Identidad de Casa matriz y bodega asociada. |
| Recepción/lotes/medidas/etiqueta | Origen de líneas, nombre/SKU/unidad, revisión de etiqueta y disponibilidad. |
| Demanda/traslados/incidencias | Sucursal solicitante, pendiente/destino, recepción parcial e incidencia aplicable. |
| Ajustes/correcciones/adjuntos | Original/corrección, estados y acceso al soporte. |
| Clientes/cotización/venta | Detalle comercial y acciones disponibles para el perfil. |
| Entregas/devoluciones | Asignaciones y devolución mixta/parcial del caso nuevo. |
| Kardex/conciliación | Movimientos del caso, saldo y costos según permiso. |

Por familia guarda una vista representativa en escritorio y móvil 390×844, claro y oscuro: hasta 28 capturas base, reutilizando evidencia actual válida de esa misma versión/ruta/estado si ya existe. Guarda además antes/después de defectos corregidos y estados que una captura base no muestre. No exijas cuatro temas/tamaños para cada combinación de roles y endpoints.

Comprueba foco visible, Tab/Escape y retorno de foco en los diálogos que existan; sin desbordamiento exterior ni acciones inaccesibles. El scroll interno de tablas puede ser válido. Mapea carga, vacío, error/reintento, validación, permiso insuficiente, operación en curso y éxito con recarga a los casos aplicables; distingue estados simulados de operaciones reales.

El recorrido móvil de Devoluciones ya fue observado; falta el archivo de captura. No lo declares pendiente otra vez como si no se hubiera realizado ni rediseñes una bandeja aprobada sin defecto nuevo.

Antes de repetir la limitación anterior de exportación PNG, inspecciona las herramientas documentadas disponibles. Usa una capacidad permitida de captura/exportación o un entorno de navegador de pruebas autorizado si existe. No inventes una API, ni presentes HTML o un resumen accesible como PNG. Si la herramienta solo permite observación en sesión, registra el intento exacto y la capacidad que falta; continúa los casos independientes y deja abierto únicamente ese artefacto.

Aceptación V02: imágenes reales de la versión revisada y un manifiesto con caso, archivo, ruta, tema, tamaño, perfil, estado y fecha. Capturas sin contexto o de una versión previa no acreditan una corrección.

## Evidencia, documentación y entrega

Guarda esta ejecución en tmp/ers-v1/cierre-visual-y-permisos/AAAA-MM-DD/verificacion-cuatro-puntos/, sin sobrescribir las pasadas anteriores:

- registro-casos.md: filas V01–V04, esperado/observado, IDs, modalidad UI/API/integración y resultado.
- matriz-permisos.md: inventario finito de acciones y evidencia correspondiente.
- capturas/ y manifiesto-capturas.md: archivos visuales y metadatos.
- Logs con comando exacto/nodo existente, salida y código de retorno.
- conciliacion-final.md: cada SKU nuevo y los cuatro protegidos, antes/después, físico, valorado, valor, documentos y movimientos sin duplicación.
- informe-final.md: defectos encontrados, causa, corrección, comprobación posterior y dictamen por V01–V04.

Actualiza el cierre principal E01–E15, matriz de permisos, revisión actual, entrega B08, seguimiento, preparación, guía y manual. Mantén un estado vigente al inicio y marca cortes anteriores como históricos. Cambia API/RBAC/esquema solo cuando la corrección o una imprecisión real lo requiera.

Ejecuta regresiones apropiadas a los cambios; tipos/lint/build si modificas frontend. Reutiliza suites aprobadas salvo cambios o fallos que invaliden su evidencia. No sumes re-ejecuciones como cobertura nueva. Restaura tema/tamaño temporal y deja operativa la demostración.

El dictamen final por cada punto debe ser APROBADO, NO APLICA justificado o ABIERTO. Un punto abierto debe señalar caso/ID, impedimento concreto, último resultado, intentos realizados y siguiente acción exacta. No conviertas “faltó tiempo” o “falta revisar” en una causa externa.

Si V01–V04 y la conciliación quedan aprobados, declara: “Alcance B01–B08 cerrado para implementación y verificación; pendiente únicamente demostración del usuario y evaluación académica”. Si queda una falla o evidencia obligatoria abierta, conserva el cierre parcial y enumera solo esos casos. No entregues otro bloque ni otro prompt como sustituto de completar este encargo.

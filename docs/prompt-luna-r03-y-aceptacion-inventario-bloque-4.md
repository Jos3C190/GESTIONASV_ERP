# Encargo para Luna — B4-R03 y aceptación pendiente de Inventario

Repositorio: `C:\Developer\GESTIONASV_ERP`. Fecha: 15/10/2026.

Completa las correcciones y la aceptación del bloque 4. El usuario autorizó este trabajo y sus pruebas. La última revisión independiente verificó B4-R01/R02 y encontró **B4-R03**, un fallo residual al invalidar enlaces QR. Además, siguen pendientes comprobaciones del encargo anterior. Trabaja hasta completar ambas partes; corregir únicamente el QR no termina este encargo.

## 1. Punto de partida y alcance

Lee, en este orden:

1. `.agents/AGENTS.md` y las instrucciones/skills aplicables.
2. La última sección de `docs/revision-inventario-bloque-4.md`: **«Revisión independiente posterior a la entrega final de Luna — 15/10/2026»**.
3. `tmp/inventory-block4-final-review-20261015/InventoryBlock4FinalReviewProbe.test.ts` y `frontend-probe.log`.
4. La matriz **E** y los requisitos **F** de `docs/prompt-luna-inventario-bloque-4.md`.
5. Secciones 5–7 de `docs/prompt-luna-correcciones-finales-inventario-bloque-4.md` y el estado actual de `docs/inventario-bloque-4-cierre-operativo.md`.

Los resultados independientes más recientes son **41 frontend aprobadas**, **6 E2E API/PostgreSQL aprobadas**, **5 de integración PostgreSQL aprobadas** y **1 sonda fallida por B4-R03**. La base de prueba estaba en `0083 (head)`. Son antecedentes; identifica por separado tus ejecuciones nuevas.

Conserva B4-01 a B4-05 y B4-R01/R02. Reutiliza pruebas que demuestren realmente el requisito y completa las brechas. Evita repetir una auditoría de todo el ERP o suites completas sin cambios que lo justifiquen. No amplíes políticas contables, permisos, diseño visual, libro mayor ni módulos de ventas/devoluciones. No necesitas rehacer lo ya verificado.

El repositorio contiene numerosos cambios ajenos y archivos sin seguimiento: consérvalos. No hagas reset/clean, commits, publicaciones ni borrados de contenedores o volúmenes.

## 2. Corregir B4-R03: revocación tardía de enlaces

Archivo: `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte`, función `revokePublicTraceLinks` (líneas 294–311 en la revisión).

### Reproducción comprobada

1. Abrir el QR de la unidad A.
2. Pulsar «Invalidar enlaces públicos» y confirmar «Invalidar enlaces»; dejar la petición pendiente.
3. Cerrar el diálogo y abrir B. Esperar a que aparezcan su producto, QR y «Abrir ficha».
4. Resolver la revocación de A.
5. Actualmente desaparecen el QR y «Abrir ficha» de B, y aparece el mensaje de revocación correspondiente a A.

La petición identifica correctamente A. El fallo demostrado está en la interfaz; no afirmar que el servidor revoca B.

### Corrección esperada

- Captura unidad, sesión y contexto al comenzar. Aplica éxito, error y `finally` únicamente a la operación vigente.
- Reutiliza las secuencias existentes de diálogo/contexto, con una identidad de operación si hace falta. Evita una biblioteca o gestor global nuevo.
- Cerrar, reabrir la misma HU, cambiar HU/contexto/permisos o desmontar invalida los efectos de la operación anterior sobre la vista.
- Restablece el estado de actividad de la sesión nueva: B debe poder invalidar sus propios enlaces mientras A sigue pendiente. El `finally` de A no puede quitar el indicador ocupado de B.
- La revocación ya enviada puede terminar en el servidor. Conserva su efecto real sin trasladar mensajes ni datos al diálogo de otra unidad.
- Conserva los permisos y el comportamiento de QR, impresión y confirmación explícita de etiqueta. No ocultes el botón ni bloquees la navegación como sustituto de proteger respuestas tardías.

Integra la sonda en la suite permanente correspondiente, con promesas controladas. Cubre éxito y error tardíos de A tras abrir B; operación simultánea de B; reapertura de A; cambio de contexto y permisos; desmontaje. Comprueba QR, enlace, producto y estado ocupado, además de los mensajes. No debilites expectativas para aceptar el fallo. Si copias temporalmente la sonda a `frontend/tests/unit`, retira únicamente esa copia al integrar la regresión y conserva la evidencia archivada.

## 3. Completar la aceptación ya solicitada

Primero crea una correspondencia entre **cada fila de la matriz E original** y su prueba/evidencia, usando estados «verificado», «parcial» o «pendiente». Una prueba parecida no basta si evita el caso requerido. Completa estas brechas identificadas:

### A. Dos detalles de compra reales del mismo artículo

La prueba actual `test_group_putaway_uses_split_requirements_for_each_result` recibe **una sola HU de 50** y la divide en 20+30. No demuestra dos detalles de origen diferentes.

- Construye dos detalles de compra distintos, del mismo artículo, con cantidades 20 y 30, dentro del agrupamiento que admite el contrato existente.
- Ubica 50 y rechaza 51. Comprueba que lotes/detalles, HU resultantes y movimientos conservan cada origen; no basta sumar cantidades.
- Fuerza el fallo de la segunda asignación y verifica rollback de movimientos, balances, HU y auditoría de éxito. Adapta/reutiliza la prueba existente cuando corresponda.
- Replay autorizado después de mover la HU: devuelve el resultado guardado sin duplicar. Mismo identificador idempotente con otro cuerpo: conflicto. Otro alcance o acceso revocado: denegación, incluso en replay.

### B. Concurrencia, aislamiento y conciliación

La carrera actual con dos peticiones de igual clave/cuerpo ya prueba un caso de idempotencia. Completa los casos originales con sesiones/transacciones reales, barreras/eventos y timeout:

- Escritores distintos sobre recursos compartidos: grupo, movimiento y medición; verifica cantidades, estados, aplicación única y ausencia de deadlock. Usa conflictos concretos y resultados esperados; no hace falta probar todas las permutaciones.
- Conciliación mientras se registra recepción, traslado o ajuste de retaceo: debe mostrar una fotografía coherente, sin mezclar versiones ni contar dos veces cantidades o valores.
- Otra empresa y perfil de sucursal sin acceso a valoración: comprueba respuestas JSON de consultas, detalles y replays pertinentes. Los importes globales no autorizados no deben llegar al cliente; ocultarlos visualmente no es suficiente.
- Mantén autorizaciones vigentes de las bodegas de origen, destino y ubicación actual de la HU en los replays.

### C. Kardex y corte

Completa la cobertura SQL con varias páginas, fechas empatadas, filtro por lote, movimientos anteriores al período y límites de día en `America/El_Salvador`. Comprueba orden determinista, continuidad de saldos y totales de todo el filtro. Incluye el corte de apertura y valoración inactiva: «desconocido» debe seguir siendo distinto de cero. Reutiliza los casos frontend de contexto/reintento ya aprobados.

### D. Cadena operativa y navegador real

Con datos ficticios, encadena recepción validada → retaceo exigible → ubicación → medición y etiqueta → disponibilidad → preparación de 4+6 → despacho de 4 y conservación de 6 → recepción parcial → Kardex/conciliación. Comprueba origen, cantidades y valor, idempotencia y ausencia de disponibilidad prematura. Incluye una HU íntegra elegible y los bloqueos de etiqueta/retaceo por rutas alternativas.

Conserva también la prueba independiente de recibir 4 de un traslado de 10, dejando 6 en tránsito: tiene cantidades distintas del escenario de despacho anterior y no debe confundirse con él.

Recorre la interfaz contra una API real aislada, con perfiles ficticios global y de sucursal: acceso directo/recarga, medición, etiqueta, preparación y despacho, recepción, contexto y reintento; comprueba teclado, tabla/tarjetas y temas claro/oscuro. Los mocks de Vitest no sustituyen este recorrido.

En este entorno ficticio se puede probar el comando de confirmación de colocación y el HTML/documento de impresión, identificándolos como simulación de software. La impresión física, colocación real y lector HS-200 requieren comprobación del usuario y se reportan aparte; no los uses como bloqueo para ejecutar la aceptación de software.

### E. Conservar la cobertura que ya pasa

Mantén, sin cambiar la política aprobada:

- Retaceo tardío: entrada 10/$100, salida 6, gasto $20 → $8 al remanente y $12 a salidas, sin movimiento físico adicional y sin duplicar al reintentar.
- Entradas 10 a $10 y 10 a $20, salida 15, devolución de 5 y crédito $100 → stock/valor 0, costo retirado $75, diferencia $25.
- Migración histórica y nuevas recepciones, rollback y replay ya cubiertos. La evidencia de repositorio financiero debe distinguirse de la cadena API/UI.

Las brechas anteriores son validaciones pendientes, no prueba automática de otros defectos. Si alguna demuestra un fallo, corrige la causa dentro del alcance y deja su regresión.

## 4. Entorno y ejecución segura

- Antes de recolectar integración/E2E, lee `backend/tests/conftest.py`: reconstruye el esquema. Verifica **ambos DSN**, mostrando solo host, puerto y base. Único destino autorizado para estas pruebas: PostgreSQL dedicado **`erp_db_test`**. Nunca `erp_db` ni inventario operativo.
- Comprueba contenedores y runtimes actuales. La revisión usó Python 3.12 en `gestionasv_erp-backend-1`, directorio `/app`, y binarios locales del frontend. No asumas que el entorno permanece igual.
- Ejecuta en serie las suites que reconstruyen la base. Prepara después los datos del navegador y no ejecutes pytest destructivo mientras ese recorrido usa la misma base.
- Prepara API/frontend aislados en puertos libres con autenticación normal. Los servicios temporales 8001/5174 anteriores fueron detenidos y sus credenciales temporales retiradas; no los des por disponibles. Conserva el stack operativo 8000/5173 y cualquier servicio ajeno.
- Registra y administra únicamente los procesos/servicios temporales que inicies. Al terminar, informa cuáles quedan activos o detenidos. No expongas tokens, contraseñas ni DSN completos en logs/documentos.
- Evita reinstalar dependencias sin necesidad. El `pnpm` anterior intentó reemplazar `node_modules` y abortó sin TTY; funcionaron los ejecutables locales `frontend/node_modules/.bin/*.cmd`. Comprueba herramientas realmente disponibles antes de declarar un bloqueo.
- Verifica la cabeza real de Alembic. No reescribas migraciones existentes; cualquier prueba de migración destructiva debe limitarse a la base de prueba y restaurar su cabeza al terminar.

## 5. Validación y entrega

Ejecuta primero la sonda R03 y su corrección; luego las regresiones permanentes, las pruebas SQL/API pendientes y el navegador. Termina con tipos Svelte, lint/formato de archivos modificados, build frontend, `git diff --check` y revisión de Alembic de la base de prueba. Evita repetir suites sin cambios ni hipótesis nueva.

Suites existentes de referencia:

- Frontend: `HandlingUnitsPanel.test.ts`, `InventoryKardexPage.test.ts`, `WarehouseHandlingUnitsIntegration.test.ts`, `InventoryKardexContext.test.ts`.
- API: `backend/tests/e2e/test_inventory_block4_closure.py`.
- PostgreSQL: `test_inventory_valuation_repository.py`, `test_inventory_kardex_repository.py`, `test_inventory_movement_idempotency.py`, `test_inventory_split_prepare_route.py`, en `backend/tests/integration/`.

Actualiza:

1. `docs/revision-inventario-bloque-4.md`: resolución de R03, prueba antes/después y estado de cada fila E. Conserva las revisiones históricas.
2. `docs/inventario-bloque-4-cierre-operativo.md`: estado inicial y evidencia final coherentes, comandos, resultados, duración, destino no secreto, migraciones y recorrido real.
3. Evidencia reproducible de navegador y pruebas nuevas en una carpeta identificada; evita archivos temporales recolectados accidentalmente.

**Condición de cierre:** R03 corregido con regresiones; matriz E cubierta con evidencia equivalente real; recorrido F realizado contra la API aislada. Las 52 pruebas anteriores aprobadas no sustituyen las filas faltantes. No marques bloques 1–3 nuevamente aceptados ni inventario inicial real aprobado basándote en esta revisión.

Ante un impedimento externo real, registra intento, error, diagnóstico y requisito afectado; completa lo independiente y conserva el estado pendiente. No detenerse por no haber preparado todavía el entorno aislado. En la respuesta final indica brevemente qué corregiste, qué comprobaste y si queda algún requisito concreto abierto; informa hardware por separado.

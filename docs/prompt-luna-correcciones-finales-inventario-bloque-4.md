# Encargo para Luna — respuestas tardías y aceptación del bloque 4

Fecha: 15/10/2026. Repositorio: `C:\Developer\GESTIONASV_ERP`.

Completa el cierre del bloque 4 de Inventario. Corrige **B4-R01 y B4-R02**, deja regresiones permanentes y termina la aceptación que ya estaba pendiente. El usuario autorizó las correcciones y sus pruebas. Conserva los arreglos B4-01 a B4-05; este encargo continúa ese trabajo.

## 1. Contexto y límites

Lee en este orden:

1. `.agents/AGENTS.md`, instrucciones aplicables y los skills correspondientes.
2. `docs/revision-inventario-bloque-4.md`, empezando por **«Revisión de las correcciones de Luna — 15/10/2026»**. Las secciones anteriores son evidencia histórica.
3. `tmp/inventory-block4-corrections-review-20261015/InventoryBlock4ReviewProbe.test.ts` y `frontend-probes.log`: contienen las dos reproducciones deterministas.
4. `docs/prompt-luna-cierre-inventario-bloque-4.md`, secciones 2–5; y la matriz E–F de `docs/prompt-luna-inventario-bloque-4.md`.
5. `docs/inventario-bloque-4-cierre-operativo.md`, para actualizar la evidencia al terminar.

No repitas una auditoría general del ERP. Revisa el código necesario para estos casos, trabaja en etapas y reutiliza pruebas existentes cuando demuestren realmente el requisito. Conserva cambios ajenos y archivos sin seguimiento; no hagas reset/clean, commits ni publicación. No amplíes políticas contables, permisos, módulos o diseño visual.

La última revisión ejecutó **3 pruebas API/PostgreSQL aprobadas**, **21 frontend aprobadas** y **2 sondas frontend fallidas**. Son resultados anteriores: registra por separado tus nuevas ejecuciones.

## 2. B4-R01 — impedir que una confirmación tardía mezcle dos etiquetas

Archivo principal: `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte`. Revisa `confirmLabelPlacement`, cierre nativo/manual, apertura de otra unidad, impresión y el callback del padre.

### Fallo demostrado

1. Abrir A e iniciar «Confirmar etiqueta colocada» dejando su respuesta pendiente.
2. Cerrar el diálogo y abrir B; cargar la vista previa de B.
3. Resolver la confirmación de A.
4. El QR sigue siendo de B, pero aparecen el producto A y el mensaje de etiqueta confirmada.

`confirmLabelPlacement` captura A antes del `await` y después sobrescribe el estado sin comprobar la sesión vigente. La impresión puede tomar el producto/lote de esa vista previa A y el código/QR de la unidad B. La sonda reprodujo la mezcla en el componente; no se imprimió físicamente.

### Resultado exigido

- Vincula cada operación a la unidad, sesión de diálogo y contexto que la originaron. Comprueba esa identidad antes de aplicar **éxito, error y finalización**, incluyendo indicadores de actividad.
- Cerrar/reabrir la misma unidad también inicia una sesión nueva. Una respuesta anterior no puede sobrescribir esa sesión ni otra unidad.
- La confirmación ya enviada puede terminar en el servidor. Su resultado debe notificarse/refrescarse en el padre solo dentro del contexto válido, sin presentar datos de A en B ni perder la actualización real de A.
- La nueva sesión debe poder operar aunque A todavía tenga una respuesta pendiente. El `finally` de A tampoco debe quitar el estado ocupado de una operación nueva de B.
- Antes de imprimir, garantiza que la vista previa, unidad seleccionada, código y QR pertenecen a la misma unidad/sesión. Si falta coherencia, recupera la vista correcta; nunca produzcas una etiqueta mezclada.
- Conserva confirmación expresa, controles de permiso e idempotencia de reintentos. `afterprint` no confirma colocación. Cancelar una petición no sustituye las comprobaciones de identidad.
- Usa una solución pequeña y coherente con las secuencias existentes; no introduzcas un gestor global nuevo ni una biblioteca para resolverlo.

## 3. B4-R02 — preservar una medición exitosa frente a lecturas anteriores

Archivo principal: `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte`. Revisa `loadData`, `requestLoad`, `verifyMeasurement` y los cambios de contexto.

### Fallo demostrado

1. Iniciar verificación de medidas y dejarla pendiente.
2. Pulsar «Actualizar»: el listado devuelve la HU todavía pendiente; la carga paralela de ubicaciones demora.
3. Termina la medición y se muestra el éxito.
4. Termina la carga de ubicaciones y `loadData` repone el listado anterior: vuelve «Medición pendiente».

La escritura no se revierte en el servidor. La interfaz aplica una fotografía anterior a la mutación porque la secuencia actual solo diferencia cargas entre sí.

### Resultado exigido

- Coordina lecturas y mutaciones para que una lectura anterior al éxito no sustituya el resultado guardado. Puedes invalidar esa lectura y hacer una recarga vigente, o aplicar una estrategia equivalente de versión/contexto.
- Conserva el payload enriquecido del servidor: después de medir deben permanecer los pendientes reales de etiqueta/retaceo; no los recalcules ni los vacíes en frontend.
- Protege éxito, error, callbacks y `finally` frente a cambio de bodega, empresa/sucursal, permisos y desmontaje. La respuesta de una operación anterior no debe cerrar un formulario nuevo ni mostrar éxito en otro contexto.
- Si descartas una carga, resuelve correctamente su estado de actividad. No dejes el panel bloqueado en «Actualizando…», pierdas las ubicaciones válidas ni ocultes un error de la recarga vigente.
- Conserva filtros/selección dentro del mismo contexto y limpia datos privados al cambiar de contexto. Deshabilitar un botón por sí solo no cubre las cargas ya iniciadas.

## 4. Regresiones permanentes y expectativas frontend pendientes

Integra las dos sondas archivadas en las suites permanentes apropiadas. No modifiques sus expectativas para aceptar el estado incorrecto y no dejes otra copia temporal recolectada. Usa promesas controladas; evita pruebas basadas en esperas arbitrarias.

| Caso | Resultado comprobable |
| --- | --- |
| Confirmación de A resuelve después de abrir B | B conserva su producto, lote, código, QR y estado de confirmación. |
| Confirmación de A falla después de abrir B | El error de A no aparece en B. |
| Cerrar/reabrir A; desmontar; cambiar contexto | La operación anterior no contamina la sesión vigente ni dispara callbacks de otro contexto. |
| B confirma mientras A sigue pendiente | A no bloquea B ni su finalización altera los indicadores de B. |
| Impresión tras cambio de unidad | El contenido preparado pertenece íntegramente a la unidad seleccionada; no equivale a validar una impresora física. |
| Medición + listado anterior con ubicaciones demoradas | Al terminar, sigue la medición verificada y sus otros requisitos reales. |
| Medición/recarga fallida y cambio de bodega/contexto | Recuperación utilizable, sin datos anteriores, éxito ajeno ni carga permanente. |
| B4-03: medir → imprimir → confirmar → cerrar → liberar | Se puede continuar sin actualización manual, conservando filtros/selección. Si queda retaceo pendiente, liberar sigue bloqueado. |
| B4-04: integración página/panel en sucursal | Montar la página real con panel; bodega no central activa/apta y `inventory:move` permite preparar. Sin permiso o bodega no apta no permite. El despacho completo conserva su restricción a matriz. |
| B4-05: Kardex valorado página 1 → fallo página 2 → reintento | Mantiene página 2 y filtros; cambios de empresa/sucursal/permisos/fechas invalidan la consulta, también durante error o petición y tras desmontaje. |

Para B4-04 se mantiene **el mismo permiso `inventory:move`** para preparación. No inventes permisos distintos ni presentes un panel aislado con `canPrepareSplit=true` como prueba de la página.

## 5. Completar la aceptación integrada ya solicitada

Mantén una correspondencia entre cada fila de la matriz E original y su prueba/evidencia. Reutiliza cobertura equivalente; completa las brechas reales:

- Cadena recepción validada → retaceo exigible → ubicación → medición/etiqueta → disponibilidad → preparación 4 + 6 → despacho de 4 y conservación de 6 → recepción parcial → Kardex/conciliación. Verifica origen, cantidades y valor sin duplicación; incluye una HU íntegra elegible.
- PostgreSQL con importes exactos: entrada 10/$100, salida 6 y retaceo $20 producen **$8 al remanente y $12 a salidas**, idempotentes y sin movimiento físico. Entradas 10 a $10 y 10 a $20, salida 15, devolución de 5 y crédito $100 producen **stock/valor 0, costo retirado $75 y diferencia $25**.
- Grupo de dos detalles del mismo artículo 20 + 30: admite 50 y rechaza 51, conserva origen; fallo en segunda asignación revierte movimientos, balances, HU y auditoría de éxito. Replay tras mover HU, cuerpo distinto y acceso revocado.
- Aislamiento de empresa/sucursal y JSON sin importes globales no autorizados. Concurrencia real entre sesiones con barreras/eventos y timeout, sin deadlock ni doble aplicación; conciliación consistente.
- Lecturas con páginas, empates, lotes, movimientos anteriores, fechas locales y corte de apertura; desconocido distinto de cero. Migración histórica `0082 → 0083` con datos ficticios conservados, adaptada a la cabeza real sin reescribir revisiones.
- Navegador contra API real aislada, perfiles global y sucursal: acceso directo/recarga, fraccionamiento, medición, etiqueta, liberación, cambios de contexto/reintentos, teclado, tablas/tarjetas y temas claro/oscuro.

## 6. Entorno y ejecución

- Lee `backend/tests/conftest.py` antes de integración/E2E: reconstruye el esquema. Verifica **ambos DSN** y muestra solo host, puerto y base. Destino permitido: PostgreSQL dedicado **`erp_db_test`**. Nunca uses `erp_db` ni inventario operativo.
- Usa Python `>=3.12,<3.13` y dependencias existentes. Comprueba los contenedores/runtimes actuales. La revisión usó los contenedores `gestionasv_erp-backend-1` y `gestionasv_erp-frontend-1`, con directorio `/app`; confirma que siguen disponibles.
- Ejecuta en serie las pruebas que reconstruyen la base. Prepara después los datos ficticios para el navegador: no ejecutes pytest que borra el esquema mientras el recorrido de navegador usa esa misma base.
- **Prepara realmente una API y frontend aislados en puertos libres** dirigidos a `erp_db_test`, con autenticación normal de perfiles ficticios. Verifica el destino antes de escribir. El servicio habitual en `8000`/`5173` puede seguir usando `erp_db`; eso no impide por sí solo levantar el entorno alterno autorizado.
- Conserva los servicios del usuario y no borres contenedores/volúmenes. Registra puertos y procesos temporales que tú inicies; administra únicamente esos procesos. Evita instalaciones o cambios de infraestructura sin necesidad concreta.
- Primero reproduce las sondas y corrige; después ejecuta regresiones permanentes, matriz PostgreSQL y navegador. Termina con tipos Svelte, lint/formato de cambios, build, `git diff --check` y comprobación de Alembic en la base de prueba. No repitas suites enteras sin cambios o dudas que lo justifiquen.
- Si existe un bloqueo externo real, documenta comando intentado, error, diagnóstico y qué validación impide. Completa el trabajo independiente y deja preparados los escenarios que no puedan ejecutarse. No declares aprobada una prueba omitida ni llames bloqueo a no haber preparado todavía el entorno aislado.

## 7. Entrega y condición de cierre

1. Código corregido, regresiones permanentes y evidencia reproducible de la matriz.
2. Actualiza `docs/revision-inventario-bloque-4.md`: resolución individual de B4-R01/B4-R02, archivos/pruebas y estado exacto de cada expectativa. Conserva la revisión histórica.
3. Actualiza `docs/inventario-bloque-4-cierre-operativo.md` y sus estados iniciales: comandos, duración, resultados actuales, destino, versión de migración y pendientes concretos. Los resultados de otra entrega siguen identificados como históricos.
4. No marques los bloques 1–3 aceptados usando pruebas que no hayas verificado. El inventario inicial real conserva su conteo y aprobación de negocio.
5. Responde brevemente qué se corrigió, qué pasó y qué queda. **Cierra el software solo si pasan las regresiones, la matriz PostgreSQL y el recorrido de navegador.** HS-200, impresión y colocación física se informan por separado y requieren comprobación real del usuario.

Completa el trabajo autorizado. Dos sondas verdes y documentación actualizada no sustituyen la aceptación integral pendiente del mismo bloque.

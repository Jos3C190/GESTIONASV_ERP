# Prompt para Luna — Inventario, bloque 4

## Encargo y punto de partida

Trabaja en `C:\Developer\GESTIONASV_ERP`. Implementa el **bloque 4 de la ampliación de Inventario: cierre operativo, coherencia del Kardex y aceptación integrada**. Entrega código, pruebas y evidencia de ejecución. Este bloque es distinto del antiguo bloque 4 de Compras/Retaceo.

El bloque 3 construyó Kardex físico, valorado y conciliación, pero su revisión encontró tres defectos funcionales y brechas de arquitectura/pruebas. No lo trates como aceptado solo por las suites anteriores. El usuario mantiene autorizada la política de valoración; este encargo la conserva.

Lee primero, en este orden:

1. `C:\Developer\GESTIONASV_ERP\.agents\AGENTS.md` y las instrucciones aplicables por directorio.
2. `C:\Developer\GESTIONASV_ERP\.agents\skills\feature-development\SKILL.md`.
3. `C:\Developer\GESTIONASV_ERP\docs\revision-inventario-bloque-3-y-alcance-bloque-4.md`.
4. `C:\Developer\GESTIONASV_ERP\docs\prompt-luna-inventario-bloque-3.md`, como contrato aún pendiente de aceptación.
5. `C:\Developer\GESTIONASV_ERP\docs\inventario-bloque-3-kardex-conciliacion.md`, distinguiendo evidencia anterior y revisión posterior.

Consulta `inventario-valoracion-bloque-1.md` y `inventario-bloque-2-lotes-etiquetas-colocacion.md` para sus políticas de origen, histórico, etiqueta y valoración. Lee después solo los archivos de código relacionados con cada paso. No repitas una auditoría general de todo el ERP. Usa el skill frontend aplicable al modificar la interfaz, aprovechando sus componentes actuales.

El repositorio tiene muchos cambios y archivos sin seguimiento: consérvalos. No hagas reset/clean, commits, publicación ni movimientos de datos operativos. No envíes mensajes a otros chats. Primero añade regresiones para los fallos observados; después corrige y valida.

## Decisiones que debes conservar

- Promedio por empresa legal y artículo, compartido entre bodegas. Una ubicación, fraccionamiento, etiqueta o traslado interno conserva cantidad y valor de empresa.
- Recepción validada incorpora cantidad y valor conocido/provisional. Cuarentena bloquea disponibilidad, no elimina la existencia valorada.
- Retaceo calculado es vista previa; verificado autoriza aplicación idempotente; cerrado bloquea cambios. Un retaceo tardío reparte el ajuste entre existencia remanente y salidas sin reescribir el historial.
- Crédito de proveedor, costo de la salida y diferencia son importes separados. No restes nuevamente el crédito del inventario.
- Cada fracción tiene identidad y etiqueta propias; la revisión/cantidad anterior no confirma la nueva. Respeta `label_confirmation_required` y la excepción de recepciones históricas.
- No abras políticas nuevas de contabilidad, períodos cerrados, retroactividad ni monedas múltiples para resolver estos defectos.

## A. Completar el recorrido físico — B3-01

Archivos iniciales: `inventory_repository.py`, `inventory_putaway_groups.py`, `inventory_label_repository.py`, `HandlingUnitsPanel.svelte`, `GroupedPutawayPanel.svelte` y la ficha autenticada de HU. Sus rutas completas y líneas están en la revisión.

### A1. Medir y liberar las partes

Una división de ubicación produce actualmente `measurement_status=complete` con `measurement_source=split_estimate`. El backend exige verificarla para liberar, pero `canMeasure` solo admite `incomplete`.

- Ofrece verificación a unidades abiertas en cuarentena con medidas incompletas **o estimadas por fraccionamiento**, cuando el usuario tenga permiso. Cubre hija y remanente.
- Conserva el control backend y actualiza peso/volumen mediante la operación existente, con su auditoría y consistencia de capacidad. No marques las medidas como verificadas al fraccionar.
- Después de medir, permite imprimir/reimprimir y confirmar la etiqueta de la revisión actual y finalmente liberar a una ubicación apta. Una confirmación de 10 no sirve para una parte de 4 o de 6.
- “Revisar unidad” debe llegar a acciones utilizables, con la unidad seleccionada. Reutiliza el panel/formulario existente mediante un enlace profundo a la bodega o un componente compartido en la ficha autenticada; no dupliques el formulario ni agregues escritura a la ficha QR pública.
- Reemplaza el aviso genérico por pendientes concretos: medición, etiqueta o retaceo exigible, y su acción autorizada. El usuario sin permiso recibe una explicación clara.

### A2. Fraccionamiento después de disponibilidad y recepción parcial

El bloqueo actual acepta divisiones de lotes nuevos solo como `putaway`, de cuarentena a cuarentena. No basta retirar ese bloqueo: volvería el fallo de etiquetas.

Implementa una **preparación explícita y trazable de fracciones** para una HU disponible. Reutiliza el servicio de movimientos: bajo una transacción/idempotencia, pasa la HU completa de origen a cuarentena de forma coherente con los balances, crea la fracción y deja hija y remanente sujetos a revalidación. Presenta esa consecuencia antes de confirmar. Puede ser un comando de aplicación pequeño que componga movimientos existentes; evita escrituras directas a estado/saldos y un segundo motor de inventario. Si falla la división, también debe revertirse el paso previo a cuarentena.

El recorrido observable debe permitir: HU disponible de 10 → preparar 4 y 6 → medir ambas → confirmar etiquetas vigentes → despachar 4 → conservar 6 en la matriz. La acción puede operar en ubicaciones de almacenamiento válidas; no obligues a una HU ya almacenada a aparecer artificialmente como una nueva recepción de compra.

Conserva también la recepción contada parcial de traslado. Si están en tránsito 10 y llegan 4, esas 4 deben poder ingresar a cuarentena con origen/identidad trazables y las otras 6 seguir en tránsito. Las fracciones estimadas no pasan a disponible automáticamente. Resuelve la excepción con validación explícita de los extremos/estado del comando, no desactivando globalmente la regla de etiqueta. Misma clave/cuerpo repite el resultado; otro cuerpo genera conflicto.

### A3. Una regla de elegibilidad

Coloca la política pura de disponibilidad en dominio/aplicación, con las dependencias de lectura detrás de puertos. Consulta medición, revisión de etiqueta, vencimiento y condición del retaceo cuando corresponda; grupo y liberación individual deben usarla. Devuelve razones tipadas para la interfaz y vuelve a validarlas dentro de la transacción de escritura.

Reutiliza la política existente de `inventory_label_repository._ensure_retaceo_final`: una compra sin retaceo exigible o un histórico no debe bloquearse por inventar un requisito nuevo. No conviertas el retaceo tardío autorizado en una prohibición general de operar inventario. Usa el día de `America/El_Salvador` en las comprobaciones de vencimiento tocadas por este flujo.

## B. Mostrar los datos reales del Kardex — B3-02

Trabaja sobre `frontend/src/lib/features/inventory/components/ValuedKardexList.svelte`, sus tipos/cliente y los DTOs necesarios, sin recalcular costos en el navegador.

1. Tipar y mostrar `cost_delta` para los efectos del retaceo sobre salidas. Conservar su signo y referencia persistida. Diferenciar el ajuste al inventario remanente de los efectos sobre salidas.
2. Para `supplier_credit`, mostrar **crédito del proveedor**, **costo de inventario retirado** y **diferencia**, usando `credit_net`, `inventory_cost` y `cost_difference`. Si no hay dato histórico, decirlo; no sustituirlo por cero.
3. Presentar entrada/salida de cantidad de forma inequívoca a partir del evento persistido. Ajustes de costo y créditos tienen efecto físico cero. No mostrar una salida positiva bajo una columna que parezca entrada ni modificar el ledger para resolver presentación.
4. Mantener fechas, secuencia, moneda, saldo y promedio registrados. Usar el formato monetario del proyecto con dos decimales; preservar decimales de cálculo en backend.
5. Aplicar estas reglas a tarjetas y tablas mediante presentación compartida. Enlaces a retaceo/recepción/HU usan identificadores reales y permisos del destino. No extraer UUIDs de `source_reference` para inventar relaciones.

Las pruebas usarán payloads iguales a los del backend. El fixture ficticio con `amount` no prueba un evento que en realidad contiene `cost_delta`.

## C. Coherencia de filtros y contexto — B3-03

En `frontend/src/routes/(app)/inventory/kardex/+page.svelte` y helpers relacionados:

- Al cambiar las fechas de cualquiera de las vistas, invalida las consultas que dependan de esas fechas. No apliques una respuesta solicitada antes del cambio aunque el usuario todavía no haya pulsado “Actualizar período”.
- Asocia cada carga con una identidad de consulta que incluya empresa, sucursal/alcance, bodega, artículo, fechas, tipo/lote y página según corresponda. Compara esa identidad al aceptar la respuesta; cancelar la petición es complementario.
- Al cambiar empresa/sucursal o perder permisos, cancela temporizadores y descarta búsqueda de artículos, opciones, selección/nombre de producto, detalle abierto y valores del contexto anterior. Cubre el período de carga de las nuevas bodegas y el desmontaje de la página.
- Evita que al volver a la pestaña física queden saldos de fechas anteriores debajo de filtros nuevos. La paginación y los reintentos conservan el filtro aplicado de manera explícita.
- Mantén carga/vacío/error, reintento y navegación accesible; no rehagas visualmente toda la pantalla.

## D. Separación de lectura y cobertura SQL — B3-04 / B3-05

Extrae las consultas nuevas de `backend/app/api/v1/routers/inventory_kardex.py`:

- Puerto de lectura en dominio, por ejemplo `InventoryKardexReadRepository`.
- Casos de uso en aplicación para búsqueda, físico, valorado y conciliación.
- SQLAlchemy async y modelos exclusivamente en la implementación de infraestructura de esas consultas.
- Router con HTTP, validación DTO, dependencias y contexto autorizado; aplicación/infraestructura no importan helpers HTTP para resolver autorización.

Conserva el contrato HTTP salvo campos aditivos justificados. Reutiliza/extiende la lectura del repositorio de valoración existente; no copies su motor ni reconstruyas costos con textos. Mantén el orden de bloqueos vigente para obtener una fotografía consistente. No retires el bloqueo de empresa sin una alternativa de consistencia probada. No refactorices todos los routers antiguos como parte de este paso.

Escribe pruebas contra PostgreSQL de las consultas y comandos reales, además de los helpers. Deben verificar valores, páginas, conteos, aislamiento, permisos y rollback. Si el entorno está caído, aun así deja escritos los escenarios y ejecuta las comprobaciones independientes; especifica cuáles no se pudieron correr.

## E. Matriz mínima de aceptación

| Caso | Resultado exigido |
| --- | --- |
| HU nueva de 10, etiqueta de revisión anterior; dividir 4 + 6 | Ambas partes conservan lote/detalle, no heredan confirmación y ofrecen medición. Tras medir, imprimir y confirmar, se liberan. Total físico/valor no cambia. |
| HU disponible: preparar fracción, despachar 4, conservar 6 | Recorrido UI/API utilizable, idempotente y auditado; ningún remanente sigue disponible con revisión inválida. |
| Recepción de 4 de las 10 unidades de un traslado | 4 en cuarentena y 6 en tránsito; sin doble entrada, sin disponibilidad prematura, con origen conservado. |
| HU completa sin etiqueta y retaceo exigible | Puede ubicarse en cuarentena; muestra cada requisito pendiente; no se libera por una ruta alternativa. Histórico conserva su excepción. |
| Retaceo tardío: entrada 10/$100, salida 6, gasto $20 | $8 al remanente y $12 a salidas; cantidad cero en el ajuste; detalle muestra $12; repetición no duplica. |
| Entradas 10 a $10 + 10 a $20; salida 15; devolución de 5; crédito $100 | Stock 0, valor 0; salida de devolución a $75; crédito $100 y diferencia $25 visibles, sin descontar stock otra vez. |
| Cambiar fechas durante petición y cambiar empresa/sucursal durante búsqueda | Respuestas antiguas descartadas, ninguna selección/importe heredado del contexto previo; reintento funciona. |
| Kardex con más de una página, empate de fecha, lote y movimientos anteriores al período | Orden determinista, saldos continuos, totales de todo el filtro, límites diarios de El Salvador y alcance correcto. |
| Datos anteriores al corte; valoración inactiva | No se inventan saldos/costos. Se distingue dato desconocido de cero. |
| Dos líneas de compra del mismo artículo: 20 + 30 | Se ubican 50 conservando detalle de origen; 51 se rechaza. Fallo de segunda asignación revierte movimientos, balances, HU y auditoría de éxito. |
| Replay del grupo después de mover la HU | Usuario autorizado obtiene el mismo resultado; otra sucursal/acceso revocado se deniega; otro cuerpo con misma clave da conflicto. |
| Otra empresa; perfil sucursal sin valoración | Consultas, detalles y replays no filtran datos privados ni importes globales en JSON. Enlaces respetan permisos de destino. |
| Dos sesiones concurrentes: grupo/movimiento/medición/retry | Finalizan dentro de timeout, sin deadlock ni doble aplicación; rollback completo. Usar barreras/eventos, no solo `sleep`. |
| Conciliación durante recepción/traslado/aplicación de retaceo | Fotografía consistente: balances contados una vez, traslado conserva cantidad/valor, retaceo conserva cantidad. |
| Migración histórica `0082 → 0083` y cabeza real | Datos ficticios históricos preservados, recepciones nuevas sujetas a confirmación; `alembic current` demuestra aplicación. |

Para los casos financieros usa los comandos y motor existentes. No hace falta construir pantallas completas de ventas/devoluciones. La prueba de extremo a extremo debe encadenar recepción validada → retaceo exigible → ubicación → medición/etiqueta → disponibilidad → traslado/recepción parcial → Kardex/conciliación, dentro de una empresa de pruebas.

## F. Entorno, pruebas y evidencia

- Inspecciona disponibilidad real de PostgreSQL/Docker/WSL. La entrega anterior reportó Docker sin daemon; no asumas que sigue igual. No reinicies servicios del usuario ni borres contenedores/volúmenes existentes para resolverlo.
- Backend: Python `>=3.12,<3.13` con dependencias del proyecto. **Solo servidor PostgreSQL desechable y base `erp_db_test` dedicada.** Antes de recoger integración/E2E revisa `backend/tests/conftest.py`: reconstruye el esquema. Verifica destino/host/puerto/nombre sin mostrar credenciales; no uses una base operativa ni una base de trabajo del usuario.
- Comprueba `alembic heads`; la última cabeza documentada es `0083`. Si cambia el esquema, crea revisión nueva desde la cabeza real. No reescribas revisiones ya entregadas ni hagas downgrade de historia financiera. SQL offline no prueba migración real.
- Primero reproduce B3-01/02/03 y deja regresiones permanentes; después ejecuta suites relacionadas, integración SQL, `svelte-check`, lint de cambios y build. Las sondas previas están en `tmp/inventory-block3-audit-20261014`; son evidencia, no sustituyen tus tests.
- Prueba en navegador con API y datos ficticios: perfil global y sucursal, acceso directo/recarga, unidad fraccionada, reintentos, fechas, tablas/tarjetas y tema claro/oscuro. Dobles de API no cuentan como integración real.
- No declares lectura física del HS-200, impresión o colocación real sin comprobación del usuario. `afterprint` sigue sin confirmar colocación.
- Registra comandos, resultados, duración, destino de prueba no secreto, revisiones aplicadas y errores/omisiones reales. Mantén separados unitarios, PostgreSQL, navegador y hardware. Si algo no puede ejecutarse, deja pasos reproducibles y estado pendiente; no lo presentes como aprobado.

## Entrega

1. Código funcional y regresiones permanentes de A–E, sin archivos temporales de prueba incluidos accidentalmente en las suites.
2. `C:\Developer\GESTIONASV_ERP\docs\inventario-bloque-4-cierre-operativo.md`: qué cambió, recorrido del operador, contratos/permisos, migraciones, matriz de pruebas y evidencia.
3. Actualizar los estados de bloques 1–3 y marcar cada hallazgo de la revisión como corregido/verificado o pendiente, conservando la evidencia histórica.
4. Resumen breve: qué se usa y dónde, pruebas realmente ejecutadas y límites restantes. Solo declarar aceptación completa de software cuando pasen las regresiones, PostgreSQL y el recorrido de navegador; informar hardware por separado.

No amplíes el bloque a libro mayor, períodos contables, retroactividad, conversión de monedas, deterioro, rediseño global, módulos completos de ventas/devoluciones ni nuevas políticas contables. El objetivo es completar el flujo ya acordado y demostrarlo.

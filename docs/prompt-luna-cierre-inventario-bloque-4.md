# Encargo para Luna — correcciones y aceptación final del bloque 4

Fecha: 15/10/2026.

Trabaja en `C:\Developer\GESTIONASV_ERP`. Completa el **cierre del bloque 4 de la ampliación de Inventario**: corrige los cinco hallazgos B4-01 a B4-05 y termina las pruebas de aceptación pendientes. El usuario autoriza esta implementación y sus pruebas. Entrega código, regresiones permanentes y evidencia. Este encargo continúa el bloque existente.

## 1. Contexto mínimo y alcance

Lee primero:

1. `.agents/AGENTS.md`, instrucciones aplicables y `.agents/skills/feature-development/SKILL.md`.
2. `docs/revision-inventario-bloque-4.md`: diagnóstico principal, reproducciones, archivos y límites de la revisión.
3. `docs/prompt-luna-inventario-bloque-4.md`: conserva su contrato; las secciones E y F contienen la matriz y condiciones de aceptación.
4. `docs/inventario-bloque-4-cierre-operativo.md`: evidencia previa y pendientes.

Aplica los skills correspondientes al trabajo que realices. Consulta después únicamente el código necesario para cada corrección. Trabaja en dos etapas: primero las cinco regresiones y sus arreglos; después la aceptación integrada. Evita repetir la auditoría general del ERP y las lecturas de documentos ya resumidos. Agrupa consultas independientes y utiliza pruebas focalizadas durante los cambios; ejecuta la validación conjunta al terminar.

El repositorio contiene muchos cambios y archivos sin seguimiento de trabajos anteriores: consérvalos. No hagas reset/clean, commits, publicación ni cambios a inventario operativo. El alcance excluye módulos nuevos, rediseño global, otro motor de costos y cambios de política contable.

### Reglas que permanecen vigentes

- Promedio por empresa legal y artículo, compartido entre almacenes. Fraccionar, etiquetar y trasladar internamente conserva cantidad y valor de empresa.
- Cuarentena mantiene la existencia y su valor, pero bloquea venta/despacho.
- Aplicación idempotente del retaceo; ajustes tardíos repartidos entre remanente y salidas. Crédito de proveedor separado del costo retirado y su diferencia.
- Cada fracción conserva origen y tiene revisión/etiqueta propias. Conserva la excepción histórica de `label_confirmation_required` y la política existente de retaceo exigible.
- Las comprobaciones del servidor, autorización por empresa/sucursal, auditoría y bloqueos transaccionales siguen siendo obligatorias. Las fechas tocadas usan `America/El_Salvador`.

## 2. Correcciones obligatorias

### B4-01 · Elegibilidad vigente durante la ubicación agrupada

En `backend/app/api/v1/routers/inventory_putaway_groups.py`, los requisitos se cargan antes de todas las asignaciones. La primera división modifica el remanente, pero la siguiente asignación utiliza los requisitos anteriores e intenta liberarlo. El repositorio responde 409 y revierte el grupo.

- Evalúa la elegibilidad de cada resultado con el estado vigente después de las divisiones, dentro de la transacción y utilizando la política común.
- Una HU de 10 repartida en 4 y 6 debe dejar ambas partes en cuarentena para revalidación. Conserva también el caso de una HU íntegra que sí cumple todos los requisitos y puede quedar disponible.
- Mantén idempotencia, autorización, revisión de etiqueta y rollback. No elimines el bloqueo backend de medidas estimadas.
- Añade regresiones de dos destinos para una misma HU: recepción histórica sin confirmación exigible y recepción nueva con etiqueta vigente. Comprueba cantidades, identidad/origen, revisiones, estados y conservación de valor cuando la valoración esté activa.

La sonda real ya reproduce una HU de 4 repartida en 1 y 3. Está archivada en `tmp/inventory-block4-audit-20261014/test_inventory_block4_review_probe.py`; el resultado está en `backend-probes.log` de esa carpeta. Conviértela en una regresión permanente dentro de la suite correspondiente y amplía sus aserciones; no dejes una copia temporal recolectada accidentalmente.

### B4-02 · La respuesta de medición debe conservar los pendientes reales

En `backend/app/infrastructure/repositories/inventory_repository.py`, la medición devuelve `_handling_unit_dict(row)` sin los metadatos que agrega el listado. `HandlingUnitOut` completa `release_requirements` con `[]`; `HandlingUnitsPanel.svelte` reemplaza la HU por esa respuesta.

- Reutiliza el enriquecimiento existente para devolver elegibilidad actualizada después de medir, manteniendo el contrato HTTP. Evita duplicar la política en frontend.
- Asegura que la HU mostrada conserve datos de origen y requisitos de etiqueta/retaceo todavía vigentes. Si necesitas recargar en el panel, protege la respuesta frente a cambio de unidad, bodega o contexto.
- Prueba por HTTP que medición y listado coinciden en los requisitos actuales; cubre etiqueta pendiente y retaceo pendiente.
- Añade la regresión del componente usando el payload real. Después de medir, «Liberar» sigue bloqueado mientras exista otro requisito.

La segunda sonda archivada reproduce exactamente `[]` en medición frente a `["label_confirmation_required"]` en listado.

### B4-03 · Confirmar colocación debe actualizar el panel

`HandlingUnitLabelDialog.svelte` solo cambia su vista previa al confirmar. El padre, `HandlingUnitsPanel.svelte`, conserva el requisito anterior.

- Notifica al panel cuando la confirmación termine correctamente y actualiza los requisitos de la HU afectada.
- Preserva filtros y selección; el operador debe continuar sin pulsar «Actualizar» ni recargar toda la página.
- Mantén confirmación expresa e idempotencia. `afterprint` no confirma colocación.
- Prueba medir → imprimir → confirmar → cerrar diálogo → liberar. Incluye confirmación fallida/reintento y una HU que todavía tenga otro requisito: confirmar etiqueta no debe borrar ese bloqueo.

### B4-04 · Preparar fracciones en almacenes autorizados de sucursal

En `frontend/src/routes/(app)/warehouses/[id]/+page.svelte`, `canTransfer` exige `warehouse.isCentral`; el panel reutiliza esa condición para «Preparar fracción».

- Separa la elegibilidad de preparar fracciones de la autorización de despachar desde matriz.
- Ofrece preparación a quien tenga `inventory:move` dentro de su alcance, con HU disponible y almacén/ubicación válidos, tanto central como sucursal.
- Conserva las restricciones existentes del despacho y todas las comprobaciones del endpoint.
- Prueba la integración real página/panel en una bodega no central, además de ausencia de permiso y almacén no apto. No basta pasar `canTransfer=true` a un panel aislado.

### B4-05 · Reintentar la página solicitada del Kardex

En `frontend/src/routes/(app)/inventory/kardex/+page.svelte`, `showValued` vacía los resultados y «Reintentar» omite la página, volviendo a 1.

- Conserva la identidad de la consulta aplicada, incluida la página, y úsala para reintentar.
- Al cambiar fechas, empresa, sucursal o permisos, invalida esa consulta y descarta respuestas anteriores. Un reintento no puede recuperar datos de un contexto descartado.
- Prueba página 1 → error al solicitar página 2 → reintentar página 2, conservando filtros. Añade cambio de contexto durante el fallo/petición y desmontaje donde falte cobertura.

## 3. Aceptación pendiente del contrato original

Los cinco arreglos necesitan pruebas nuevas, y además sigue pendiente la matriz E del encargo original. Reutiliza cobertura existente cuando compruebe realmente el caso; deja una correspondencia entre cada fila de la matriz y sus pruebas/evidencia. Completa al menos estas brechas identificadas:

1. **Cadena integrada:** recepción validada → retaceo exigible → ubicación → medición/etiqueta → disponibilidad → preparación de 4 y 6 → despacho de 4 conservando 6 → recepción parcial de traslado → Kardex/conciliación. Comprueba que cantidades y valor no se duplican y que cada fracción conserva su origen.
2. **Importes exactos en PostgreSQL:** retaceo tardío con entrada 10/$100, salida 6 y gasto $20: $8 al remanente y $12 a salidas, sin efecto físico ni duplicación al repetir. Entradas 10 a $10 y 10 a $20, salida 15, devolución de 5 y crédito $100: stock/valor finales 0, costo retirado $75 y diferencia $25. Usa los comandos existentes.
3. **Grupos y rollback:** dos detalles del mismo artículo, 20 + 30; 50 aceptados y 51 rechazados, preservando detalle de origen. Fallo en la segunda asignación revierte movimientos, balances, HU y auditoría de éxito. Replay tras mover la HU, conflicto por otro cuerpo y acceso revocado.
4. **Aislamiento y concurrencia:** empresa distinta, perfil sucursal sin valoración y acceso directo a detalles/replays; no filtrar importes globales en JSON. Dos sesiones con barreras/eventos y timeout, sin doble aplicación ni deadlock. Conciliación consistente durante recepción, traslado y retaceo.
5. **Lecturas y migración:** páginas, empates de fecha, lote, movimientos anteriores al período, límites diarios locales y corte de apertura. Valoración inactiva distingue desconocido de cero. Migración histórica `0082 → 0083` con datos ficticios preservados y evidencia de cabeza aplicada; adaptar si la cabeza real cambió, sin reescribir revisiones existentes.
6. **Navegador con API real:** perfiles global y sucursal, acceso directo/recarga, fraccionamiento, medidas, etiqueta, liberación, reintentos y cambios de contexto. Revisar tabla/tarjetas, teclado y temas claro/oscuro. Un componente con API simulada no sustituye este recorrido.

## 4. Entorno y orden de validación

- Antes de integración/E2E, lee `backend/tests/conftest.py`: reconstruye el esquema. Verifica ambos DSN y muestra únicamente host, puerto y nombre de base, sin credenciales. **Solo PostgreSQL desechable y base dedicada `erp_db_test`; nunca `erp_db`.**
- Usa Python `>=3.12,<3.13` y dependencias del proyecto. Comprueba Docker y servicios actuales sin asumir el estado de sesiones anteriores. No reinicies servicios del usuario ni borres contenedores/volúmenes para preparar pruebas.
- Para navegador, usa API/frontend aislados con datos ficticios y puertos libres. Comprueba qué base utiliza esa API antes de escribir. La sesión operativa del usuario no es un entorno de pruebas.
- Primero reproduce las cinco regresiones; luego corrige; ejecuta suites relacionadas, PostgreSQL y navegador. Termina con tipos Svelte, lint de cambios, build, `git diff --check` y comprobación de Alembic en la base de prueba.
- Conserva los servicios, repositorios y componentes existentes. Evita instalar dependencias o ampliar refactors sin necesidad concreta de estos arreglos.
- Las cifras de pruebas del informe anterior son evidencia histórica. Registra lo que ejecutes ahora con comando, resultado, duración y destino. Si una limitación externa impide una validación, documenta la causa exacta, lo intentado y pasos reproducibles; no declares esa validación aprobada.
- HS-200, impresión y colocación física requieren comprobación real del usuario y se informan por separado. No los declares probados por emitir un QR o simular `afterprint`.

## 5. Entrega y condición de cierre

1. Código corregido y regresiones permanentes B4-01 a B4-05; pruebas faltantes del contrato original.
2. Actualizar `docs/inventario-bloque-4-cierre-operativo.md` con recorrido utilizable, comandos/resultados y matriz completa de aceptación.
3. Añadir a `docs/revision-inventario-bloque-4.md` una sección de resolución por hallazgo, enlazando código/pruebas/evidencia. Preservar el diagnóstico histórico y distinguir «corregido» de «verificado».
4. Actualizar los estados de aceptación relacionados de los bloques 1–3 solo con evidencia real. La activación del inventario inicial operativo conserva su conteo/aprobación de negocio.
5. Resumen final breve: qué quedó corregido, qué pruebas pasaron y cualquier pendiente concreto. **Aceptar el software únicamente cuando pasen las regresiones, la matriz PostgreSQL y el recorrido de navegador.**

Completa este encargo dentro del alcance autorizado. No lo des por terminado solo porque pase una suite unitaria ni por haber redactado un plan de pruebas.

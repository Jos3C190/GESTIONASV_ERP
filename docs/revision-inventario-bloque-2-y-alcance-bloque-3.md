# Revisión del bloque 2 y alcance del bloque 3 de Inventario

Fecha: 14/10/2026. Revisión de arquitectura y código; sin cambios al código de producción ni a datos operativos.

> **Actualización posterior:** este documento conserva los hallazgos en el estado en que se hizo la revisión estática. El encargo del bloque 3 corrigió R1–R3 en el código actual y agregó regresiones unitarias. Los hallazgos no se consideran aceptación operativa: no se dispuso de PostgreSQL ni de un navegador autenticado con datos de prueba. Ver [evidencia del bloque 3](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-3-kardex-conciliacion.md).

## Dictamen

**El bloque 2 cubre la mayor parte del alcance, pero aún no cumple todos sus criterios de aceptación.** Tiene lotes por recepción, origen por línea, registro de impresión, confirmación explícita de etiqueta, ubicación agrupada y QR público revocable. Encontré dos defectos de control y una inconsistencia del recorrido que deben corregirse antes de considerarlo cerrado.

Esta revisión es estática. Los escenarios que siguen se deducen de rutas alcanzables del código; todavía deben reproducirse con pruebas de regresión y PostgreSQL. Las 85 pruebas backend y 406 frontend pertenecen a la entrega anterior: no se volvieron a ejecutar para redactar este informe y no sustituyen las pruebas faltantes.

## Lo que sí responde a las expectativas

| Requisito | Evidencia actual | Límite de aceptación |
| --- | --- | --- |
| Mantener origen de la recepción | La integración de compra asigna `inventory_lot_detail_id`; el fraccionamiento conserva ese origen. | Falta comprobar persistencia y rollback sobre PostgreSQL. |
| Agrupar líneas del mismo producto | `_validate_lot_detail_totals` agrega detalles y valida cantidades por origen; hay casos 20 + 30 y exceso. | Son pruebas de validación; falta recorrer grupo, movimientos y saldos juntos. |
| Confirmar físicamente las etiquetas | Existe `inventory_label_confirmations`, con revisión/cantidad/impresión, idempotencia y acción explícita de UI. | El control de disponibilidad aún tiene la excepción descrita en R1. |
| Respetar datos históricos | `0083` mantiene lotes existentes sin el requisito nuevo; los nuevos lo exigen. Se distingue retaceo histórico y posterior al corte. | La migración no se ha validado en una base real. |
| Acceso local a etiquetas y QR | Las rutas autorizan contra la bodega persistida de la unidad. | El reintento del grupo tiene un defecto separado, R2. |
| Conservar el motor de costos | Se reutiliza el bloqueo de empresa y la valoración del bloque 1; ubicar no crea otra compra. | No hay prueba concurrente real que cierre H3. |

## Hallazgos que deben corregirse

### R1 — Alta: una fracción puede quedar disponible sin su propia etiqueta confirmada

Referencias: `backend/app/infrastructure/repositories/inventory_repository.py:2622`, `:2668`, `:2713`, `:2888`, `:2902`; entrada pública en `backend/app/api/v1/routers/inventory.py:517`.

El movimiento genérico admite un `transfer` parcial con destino `available`. La comprobación de medidas estimadas revisa la unidad **antes** de fraccionarla. Si el origen está en cuarentena, la comprobación de etiqueta también usa el código, revisión y cantidad de la unidad original. Después se crea una hija con `measurement_source=split_estimate` y se le asigna el `to_status` pedido, aunque nunca se haya confirmado su etiqueta.

Ejemplo a reproducir: unidad nueva de 10, medidas verificadas, retaceo aplicado y etiqueta confirmada; solicitar traslado parcial de 4 desde cuarentena a una ubicación válida con estado disponible. La hija no puede quedar disponible usando la confirmación de la unidad de 10. El grupo evita este caso usando cuarentena, pero el endpoint genérico no tiene esa misma protección.

Además, el remanente cambia de cantidad y revisión. Si el origen ya estaba disponible, mantiene ese estado pese a que su confirmación anterior dejó de representar la cantidad actual. Debe definirse y probarse su bloqueo operativo hasta revalidar medidas/etiqueta, sin desajustar saldos físicos.

**Cierre requerido:** controlar la elegibilidad de la unidad resultante, impedir la disponibilidad de la fracción estimada/no confirmada y conservar la invalidez de la etiqueta del remanente. Cubrir el endpoint genérico, no solo el panel agrupado. Aplicar el requisito nuevo a los lotes sujetos a él, preservando la excepción histórica documentada.

### R2 — Alta: el replay del grupo omite la autorización de sucursal

Referencias: `backend/app/api/v1/routers/inventory_putaway_groups.py:75`, `:331`, `:482`.

`confirm_putaway_group` ejecuta `_replay_if_present` y devuelve la respuesta guardada antes de `_validate_group`. La autorización mediante `resolve_branch_scope` se encuentra en la validación posterior de ubicaciones. Un usuario con los permisos generales de inventario y la clave/cuerpo originales puede recuperar la respuesta de una bodega a la que ya no tiene acceso. No vuelve a mover stock, pero revela los datos del grupo saltándose el alcance vigente.

**Cierre requerido:** autorizar la empresa y la sucursal de origen/destino persistidas antes de devolver un replay. Separar autorización de validación de estado: un replay válido debe seguir funcionando aunque la unidad ya no esté en recepción. Probar usuario de otra sucursal y usuario cuyo acceso fue retirado; ninguno debe recibir la respuesta histórica.

### R3 — Media: ubicar primero y etiquetar después falla para unidades completas

Referencias: `backend/app/api/v1/routers/inventory_putaway_groups.py:503` y `backend/app/infrastructure/repositories/inventory_repository.py:2748`.

Una unidad completa, medida y vigente recibe destino `available` en el grupo. No se consulta si le falta la confirmación de etiqueta. En una recepción nueva sin confirmar, el movimiento se rechaza; para una fracción, en cambio, el mismo grupo conserva cuarentena y permite continuar. El recorrido documentado presenta ubicación, impresión y confirmación en ese orden, pero no funciona de manera uniforme.

**Cierre requerido:** permitir ubicación completa en cuarentena cuando todavía falte un requisito de disponibilidad. Mostrar qué falta y cómo completarlo. La ubicación no debe aplicar retaceo ni confirmar etiquetas automáticamente. Seguir rechazando cantidades, capacidad, destinos y permisos inválidos.

## Pruebas y evidencia pendientes

- `test_inventory_label_prints.py` prueba el esquema de confirmación, pero no ejecuta `confirm_handling_unit_label` para verificar persistencia, revisión obsoleta, replay y conflicto de contenido.
- `test_inventory_putaway_group_schema.py` prueba contratos/cantidades, pero no el recorrido transaccional del grupo.
- `test_inventory_movement_idempotency.py` contiene dos pruebas PostgreSQL de movimientos; no cubre la concurrencia grupo/movimiento/medición ni R1–R3.
- Faltan migración real, transacciones concurrentes, rollback, permisos de sucursal y lectura física de etiqueta. El equipo físico requiere una comprobación del usuario; no se simula su aprobación.
- Había una contradicción documental: una sección decía que no se pudo generar SQL offline hasta `head` y otra afirmaba que sí. Se corrige para no atribuir evidencia inexistente. La generación histórica `0078:0079 --sql` del bloque 1 es un resultado distinto.

## Siguiente bloque recomendado

**Bloque 3 de esta ampliación: Kardex operativo y valorado, conciliación y cierre de integración.** No se trata del antiguo bloque 3 del flujo de Compras documentado en `bloque-3-recepcion-y-movimientos-de-inventario.md`.

Motivos:

1. Los apuntes requieren poder consultar entradas, salidas, saldos, costo y documento de origen.
2. El motor de valoración y los movimientos físicos ya existen; reutilizarlos evita crear otro cálculo de costo.
3. La navegación todavía dirige Kardex a `/placeholder?module=Kardex` (`frontend/src/lib/navigation.ts:306`). La pantalla de valoración permite consultar su registro financiero, pero no reemplaza el Kardex físico por bodega.

Orden del encargo: corregir R1–R3 y agregar regresiones → conectar consultas reales del Kardex → conciliar cantidades/valor → validar PostgreSQL y recorrido de usuario. La aceptación de lo nuevo no debe ocultar pendientes del bloque 2.

Quedan fuera: libro mayor, períodos contables, monedas múltiples, deterioro, captura avanzada del corte inicial, módulo completo de ventas/devoluciones y reversión financiera general. Son ampliaciones posteriores; no se consideran implementadas por mostrar sus eventos existentes en el Kardex.

Encargo listo para construcción: [Prompt para Luna — bloque 3](C:/Developer/GESTIONASV_ERP/docs/prompt-luna-inventario-bloque-3.md).

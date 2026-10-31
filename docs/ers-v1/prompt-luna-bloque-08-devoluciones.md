# Encargo Luna — ERS-B08: devoluciones de clientes y cierre integral B01–B08

Preparado para ejecución el 19/10/2026. Este archivo encarga implementar B08, realizar sus comprobaciones técnicas y después ejecutar la aceptación integrada. La preparación del prompt no inicia el bloque ni acredita resultados.

Implementa el proceso operativo de devolución sobre las entregas de B07. Lee [guía](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-04/05/06/07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md) e informes B05/B07. No estás solo en el repositorio; conserva otros cambios. La política de devolución a proveedor existente sigue vigente; este encargo desarrolla la devolución de cliente exigida por la integración de ventas.

## Responsabilidad

**Decisión del usuario, 18/10/2026:** este es el último bloque de ejecución. Después de implementar y comprobar las devoluciones, realiza la revisión completa B01–B08 siguiendo [el checklist de aceptación originalmente B09](C:/Developer/GESTIONASV_ERP/docs/ers-v1/prompt-luna-bloque-09-aceptacion.md). Incluye los recorridos visuales pendientes de B01/B02 y los acumulados de los demás bloques. No requiere un nuevo encargo B09; tampoco se considera cumplida esa revisión por haber terminado únicamente las devoluciones.

Responsable de documentos de devolución y sus líneas, recepción/revisión, aceptación o rechazo, integración con inventario/valoración, permisos y pantallas. Reutiliza el movimiento customer_return y sus reglas de costo original; no implementar otro cálculo de promedio en paralelo.

## Inicio y secuencia de ejecución

1. Lee `.agents/AGENTS.md`, la guía, las decisiones, `matriz-y-seguimiento.md`, `entrega-bloque-07.md` y `preparacion-revision-bloque-08.md`. Consulta las entregas B01–B06 para recuperar cada criterio pendiente y el checklist `prompt-luna-bloque-09-aceptacion.md` antes de planificar el cierre. Ese nombre histórico no crea un bloque adicional.
2. Registra el estado inicial de archivos, servicios, base de la API y migraciones. El cierre documentado de B07 sitúa la demo en 0089; comprueba la cabeza real, no la supongas. Conserva todos los cambios existentes. Antes de cualquier migración sobre la demo, crea respaldo, ensaya en una copia y comprueba conservación de datos. No vuelvas a aprobar ni edites el corte inicial histórico.
3. Inspecciona las asignaciones de entrega B07: `movement_line_id`, `valuation_entry_id`, `applied_total_cost`, `applied_unit_cost`, cantidad base y snapshots de lote/empaque. Diseña el enlace de devolución a esas asignaciones, incluyendo líneas atendidas por varias HUs o entregas. El límite y el costo se comprueban contra el origen preciso, no solo contra el total del producto.
4. Implementa documentos, reglas, permisos e interfaz; comprueba B08-A1–A7 y documenta el resultado. Después ejecuta la revisión completa E01–E15 y corrige los defectos relacionados con el alcance. Completar devoluciones no es motivo para detenerse antes de la aceptación integrada.
5. Mantén una lista de avance persistente en `entrega-bloque-08.md`: implementado, comprobado, pendiente y siguiente acción. Si la sesión se interrumpe, reanuda desde la evidencia registrada, conservando los pendientes anteriores. No inicies un B09 independiente.

Para la ejecución aplica los skills de desarrollo y calidad frontend que correspondan. Este encargo autoriza las comprobaciones técnicas y los recorridos de navegador necesarios. Antes de recolectar integración/E2E, inspecciona las fixtures y verifica que sus conexiones apunten únicamente a `erp_db_test`; esas suites reconstruyen el esquema y deben ejecutarse en serie. El navegador de aceptación debe usar una base estable que ninguna suite esté reconstruyendo. Conserva credenciales fuera de documentos y salidas.

## Flujo y reglas

1. BORRADOR: seleccionar venta y líneas de entrega originales, cantidad, motivo y condición declarada. Conservar cliente, empresa, sucursal y documento de origen. Permitir adjuntar evidencia con el servicio existente y validar su pertenencia/acceso. La obligación de adjunto de ADR-05 se refiere a ajustes; no exigirlo en toda devolución sin una regla documentada que lo justifique.
2. RECIBIDA/PENDIENTE DE REVISIÓN: registrar recepción documental y actor; todavía no aumentar inventario disponible ni valor. Mostrar la mercancía pendiente de decisión por separado para que esa custodia no se confunda con stock reconocido.
3. Registrar revisión por línea: cantidad apta aceptada, rechazada o pendiente, con motivo/condición. Admitir aceptación parcial sin perder lo aún pendiente. La suma de resultados no supera lo recibido; la recepción propuesta no supera la cantidad entregada aún susceptible de devolución. Al aceptar, volver a comprobar bajo bloqueo el límite acumulado entregado menos devoluciones ya aceptadas, incluyendo otros documentos concurrentes.
4. Aceptar solo cantidad apta autorizada. Crear movimiento vinculado a la entrega/salida original y reincorporar a su costo efectivo de origen mediante el motor, incluyendo el tratamiento existente de ajustes de costo/retaceo tardíos. No usar automáticamente el promedio actual ni el precio de venta. Si el motor no conserva suficiente trazabilidad, completarla con evidencia y prueba; no sustituirla por una estimación silenciosa.
5. La entrada identifica producto, unidad, lote canónico, ubicación autorizada y HU nueva o reutilización segura según el motor. No reabrir ciegamente una HU agotada ni sobrescribir su historial. Conservar la cadena de procedencia. Si requiere etiqueta/medidas/revisión, entra a cuarentena y luego sigue la liberación existente; no declararla disponible antes.
6. Lo rechazado o dañado no se libera ni se valora automáticamente como mercancía apta. Registrar su resolución documental. Si requiere un tratamiento distinto de inventario, enlazar el ajuste autorizado B05 con su evidencia; no usar cambios de estado para destruir o crear existencias.
7. Cada aceptación tiene identidad idempotente; el documento puede tener varios eventos parciales. Documento, stock, costo, trazabilidad y auditoría de éxito se confirman juntos. Una falla tardía o concurrencia no puede dejar retorno parcial no autorizado. Aplicar la protección ante AppError de ADR-07.
8. La aceptación aplicada es inmutable. Una corrección usa compensación autorizada y enlazada; no edita la venta, entrega o movimiento original. Devolver no reduce la cantidad histórica entregada ni dispara un nuevo despacho del pedido.

Para la cabecera, derivar ACEPTADA/RECHAZADA/MIXTA cuando todas las cantidades recibidas tengan resolución; mantener «En revisión» mientras existan pendientes. Distinguir esos resultados del estado físico disponible/cuarentena. Documentar esta precisión del contrato compartido.

## Pantallas

Permitir abrir devolución desde una venta entregada y desde Devoluciones. Mostrar producto y unidad, entregado, devuelto aceptado, máximo restante, motivo y documento de origen. Separar «Registrar recepción» de «Aceptar mercancía» y «Rechazar». Mostrar resultados por línea, evidencia y movimientos. No simular reembolsos, notas de crédito fiscales ni cobros; esa integración requiere especificación propia.

## Aceptación

- B08-A1: registrar y recibir una devolución no incrementa stock. Aceptar una parte apta genera una sola entrada por esa cantidad; lo rechazado y pendiente permanece distinguible y fuera de disponible.
- B08-A2: con promedio actual diferente al de la salida original, la aceptación usa el costo efectivo original y recalcula el saldo mediante el motor. Incluir un caso con ajuste tardío del costo de origen si el sistema admite ese flujo.
- B08-A3: devoluciones parciales en varios documentos y dos aceptaciones concurrentes no superan lo efectivamente entregado menos lo ya aceptado. El mismo evento repetido no duplica y una clave con cuerpo distinto produce conflicto.
- B08-A4: una falla en segunda línea revierte todos los efectos de esa aceptación, incluidos valor y auditoría de éxito. No modifica entregas históricas ni crea un nuevo pendiente de venta.
- B08-A5: entrada en cuarentena conserva origen y requiere la liberación aplicable. Etiqueta/QR/Kardex resuelven correctamente su lote y entrega de origen; rechazar no crea HU disponible.
- B08-A6: perfiles autorizados de empresa/sucursal pueden ejecutar el flujo; otra empresa no puede consultar origen, adjuntos ni aceptar. Usuarios sin lectura de costos no reciben costos ocultos en la respuesta.
- B08-A7: flujo autenticado con API real desde venta → devolución recibida → revisión parcial → resolución → Kardex, incluyendo recarga y consulta de evidencia.

Crea entrega-bloque-08.md, actualiza decisiones de estados si se precisaron, API/esquema/RBAC y E11/E12/E13. Documenta cualquier tratamiento de mercancía dañada que aún requiera decisión. No declarar un módulo fiscal de devoluciones terminado.

## Fase final: revisión completa y demostración

Antes de ejecutar la revisión, incorpora el traspaso de B07 y los pendientes conservados en [preparacion-revision-bloque-08.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/preparacion-revision-bloque-08.md). Ese documento prepara casos y evidencia; no acredita que hayan sido ejecutados. Recupera también los criterios completos de la matriz y entregas previas.

Incluye expresamente estos pendientes, sin reducir el resto del checklist:

- B01–B04: matriz/bodega original, lotes y etiquetas, demanda visible por sucursal, selección del destino, excedentes con motivo, vehículos, tránsito, recepción parcial e incidencias. Mostrar nombre del producto y unidad; abrir/cerrar formularios o revisar etiquetas no divide ni mueve existencias. «Revisión terminada · disponible para uso» es el final de la revisión de almacén; dividir continúa siendo opcional.
- B05: perfiles y aislamiento de empresa/sucursal en API, evidencia adjunta y sus accesos, reintentos, concurrencia, costo sin promedio previo y recorrido de ajustes/compensaciones.
- B06: cliente → cotización → venta con API real, recarga, cambio de contexto, permisos, errores, móvil y ambos temas.
- B07-A2: rechazo de stock en tránsito, HU cerrada, ubicación incompatible y saldo insuficiente, además de cuarentena y sucursal ajena. B07-A5: otros roles, otras empresas/sucursales y autorización también en replay. B07-A6: entrega parcial/final → Kardex/conciliación, recarga y recuperación de respuesta perdida. B07-A7: intentar preparar una entrega de venta ya cancelada y modificar una entrega confirmada; comprobar rechazo sin efectos.
- Regresión de almacenes documentada en B07: `frontend/tests/unit/WarehouseHandlingUnitsIntegration.test.ts:192` esperaba «Preparar fracción»; la suite registró 473 aprobadas y 1 fallida. Diagnostica si es un contrato de prueba desactualizado o un defecto funcional. Corrige la causa y conserva cobertura de abrir/cancelar sin mutación y división explícita; no elimines la aserción solo para conseguir verde. Revisa también el estado vigente de tipos, lint y avisos, distinguiendo lo previo de lo introducido.

Utiliza el artículo ficticio nuevo y los saldos calculables del checklist integrado, sin mezclar el caso con el café histórico ni alterar su corte aprobado. Verifica los valores con la precisión decimal del motor. Reutiliza evidencia previa pertinente identificando fecha/versión, pero ejecuta el recorrido integrado sobre el estado actual y repite los casos afectados por cambios o fallos. Las pruebas simuladas y las capturas aisladas no sustituyen el flujo autenticado persistido.

Ejecuta el checklist enlazado, corrige defectos dentro del alcance y registra evidencia real de E01–E15. Entrega revision-integral-bloques-01-08.md, manual-pruebas-y-demostracion.md y evidencia fechada en tmp/ers-v1/bloque-08/aceptacion-integrada. En entrega-bloque-08.md distingue implementación de devoluciones, verificación técnica y aceptación integrada. No marques el cierre completo si quedan criterios sin comprobar; identifica sus impedimentos. Impresora y lector físicos continúan fuera del requisito de demostración.

Actualiza también `guia-maestra.md`, `matriz-y-seguimiento.md` y `preparacion-revision-bloque-08.md` con el estado final real, conservando los cortes históricos. Incluye en los informes una tabla por criterio con resultado, evidencia, defecto/corrección y pendiente; documenta migraciones, recuperación y los pasos de uso de devoluciones. El manual final debe permitir al usuario repetir la demostración desde solicitud de compra hasta entrega, devolución y ajuste, con acciones reales y resultados esperados.

La respuesta final debe indicar qué quedó implementado, qué se comprobó realmente, si la aceptación integrada terminó o qué criterios concretos faltan, y enlaces a los informes y al manual. El cierre técnico no equivale a una revisión independiente de arquitectura ni a aprobación académica. DTE, reembolsos, cobros y contabilidad general siguen fuera del encargo.

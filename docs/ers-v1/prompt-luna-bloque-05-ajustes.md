# Encargo Luna — ERS-B05: ajustes autorizados, evidencia y faltantes de traslado

Construye el flujo operativo de ajustes sobre el motor actual: borrador, soporte adjunto, aprobación, aplicación y consulta en Kardex. Integra pérdidas documentadas de traslados y correcciones trazables de ajustes aplicados.

## Decisión vigente — 19/10/2026

Ejecuta únicamente B05 y las correcciones de dependencias necesarias. La revisión completa de B01–B08 y la aceptación visual autenticada se harán al finalizar B08. Realiza ahora comprobaciones técnicas focalizadas y documenta los recorridos manuales pendientes. No inicies B06.

B04 está implementado y verificado técnicamente: 39 pruebas frontend, 6 de integración, lint y build aprobados; crítica estática de UI 8.5/10. Son antecedentes, no ejecuciones B05 ni aceptación manual. B04 no añadió migración; la última revisión documentada es 0086. Comprueba la cabeza efectiva antes de crear una sucesora.

Lee la guía-maestra.md, decisiones-arquitectura.md (ADR-04/05/07 y preparación B05), matriz-y-seguimiento.md, entrega-bloque-04.md y manual-traslados.md de C:/Developer/GESTIONASV_ERP/docs/ers-v1. Aplica .agents/AGENTS.md y las skills pertinentes. La postergación de aceptación manual a B08 es una decisión expresa del usuario.

## Responsabilidad y código a reutilizar

Responsable de documento/líneas de ajuste, permisos, adjuntos, aprobación, aplicación, compensación, interfaz y enlaces a Kardex/traslados. No estás solo en el repositorio: conserva cambios ajenos; no uses reset/clean ni descartes trabajo previo.

Inspecciona estos archivos bajo C:/Developer/GESTIONASV_ERP:

- backend/app/application/inventory/use_cases.py: reconoce adjustment_in/adjustment_out y rechaza reversal directo.
- backend/app/infrastructure/repositories/inventory_valuation_repository.py: valoración y eventos de origen. No crees otro promedio.
- backend/app/api/v1/routers/inventory.py: movimientos genéricos y protección B04.
- backend/app/infrastructure/repositories/inventory_transfer_repository.py, router y esquemas de traslados: recepción, incidencias, bloqueo e idempotencia.
- backend/app/api/v1/routers/documents.py y sus servicios/modelos; patrón de comprobantes en backend/app/infrastructure/models/purchase_order.py.
- Catálogo RBAC, navegación, componentes documentales y frontend/src/lib/features/inventory/components/TransferOperationsPage.svelte.

Presenta un plan corto y concreta contratos antes de implementar. Respeta las capas del backend y Svelte 5 Runes; divide componentes por responsabilidad.

## 1. Documento y estados

Crear cabecera con código único por empresa, bodega/sucursal, fechas operativa/contable, motivo, referencia documental, notas y actores. Cada línea identifica artículo/variante, unidad base, ubicación, lote canónico/HU cuando corresponda, dirección positiva/negativa y cantidad positiva con hasta seis decimales. Obtén producto/unidad del servidor; no infieras conversiones del nombre comercial ni incrementos por llamarse «Caja».

Estados: draft → approved → applied; cancelled solo antes de aplicar. Crear/editar/adjuntar/aprobar/cancelar no altera existencias ni valor. Para modificar un aprobado, revoca la aprobación con motivo e historial y vuelve a borrador; exige nueva aprobación del contenido actual. Usa revisión/versionado o bloqueo equivalente para impedir aprobar una versión y aplicar otra. Autor/aprobador/aplicador provienen de la sesión autenticada.

El mismo usuario puede aprobar/aplicar si tiene permisos. No impongas separación de cargos adicional. Define o reutiliza permisos explícitos de ajuste y aprobación, con catálogo, asignaciones y documentación. inventory:move no debe permitir eludir aprobación. Mantén lectura de costos y alcance empresa/sucursal separados.

## 2. Adjuntos y soporte histórico

Aprobar exige motivo, referencia documental y al menos un adjunto válido, activo y de la misma empresa. Reutiliza carga, escaneo, límites de tamaño/tipo, almacenamiento y descarga autorizada. Pendiente de validación, rechazado, eliminado o inaccesible no sirve como soporte.

Relaciona por ID y versión/checksum real; nombre o URL libre no sustituyen un adjunto. Congela el soporte aprobado y consérvalo al aplicar. Borrar/reemplazar desde el módulo documental también debe respetar el vínculo histórico; no basta ocultar botones en ajustes. Revalida al aplicar y protege carreras con borrado/reemplazo. Un soporte nuevo conserva el anterior y su historial.

Algunos documentos generales exigen alcance empresarial completo. Si el operador de sucursal necesita cargar/consultar evidencia, implementa autorización acotada al ajuste y su bodega usando la infraestructura actual. No le concedas biblioteca global ni acceso al archivo solo por conocer su ID.

## 3. Aplicación física y valoración

Aplicar invoca movimientos existentes en una unidad de trabajo: documento, líneas, HUs, saldos, movimiento, valoración, enlace a incidencia y auditoría de éxito. La sesión puede confirmar AppError: usa savepoint/rollback explícito y prueba fallos tardíos.

- Positivo: costo documentado cuando se conoce; si falta, promedio vigente. Sin promedio válido previo exige costo documentado. Distingue costo unitario de costo total en UI/DTO y deriva el otro en servidor. Cero explícito no equivale a costo ausente y debe cumplir las reglas del motor.
- Negativo: promedio vigente al aplicar. No permite saldo negativo ni consumir otro artículo/lote/HU/ubicación/empresa. Si cambian existencia o condiciones después de aprobar, rechaza sin efectos parciales.
- Los positivos conservan origen documental como ajuste; no inventes compras/recepciones ni alteres lotes históricos. Valida la identidad de cualquier lote existente. Una HU nueva sigue cuarentena/revisión: no confirmes etiquetas ni liberes automáticamente.
- No ajustes stock reservado/bloqueado por otra operación ni tránsito mediante un ajuste libre. El tránsito requiere la incidencia autorizada del apartado siguiente.

Usa claves idempotentes por empresa/acción/cuerpo, autorización también en replay y bloqueos en orden determinista. Doble clic/reintento no duplica aplicación. Conserva clave ante respuesta incierta y consulta estado actual tras éxito. Cambiar empresa/sucursal invalida respuestas y formularios anteriores.

## 4. Un solo camino autorizado

Revisa consumidores de adjustment_in/adjustment_out en el endpoint genérico y demás accesos. Los nuevos ajustes operativos exigen documento aprobado válido en servidor; reference_type/UUID arbitrarios no son autorización.

Preserva operaciones internas legítimas e historial y documenta el mapa de consumidores. No rompas recepción, traslado, retaceo o liberación para cerrar este acceso. No habilites reversal público para sortear el rechazo actual.

## 5. Faltantes de traslado

B03 permite resume_transit y close_received. Extiende el contrato para justificar una pérdida mediante ajuste negativo aprobado, sin presentarla como recepción.

Desde la incidencia, crea un borrador enlazado al traslado, incidencia, línea y HU/ubicación de tránsito reales. Solo ajusta el remanente no recibido/no resuelto. Exige permiso de ajuste/aprobación y alcance logístico del documento; no concedas acceso general a la bodega técnica. Revalida dentro de la transacción frente a una recepción simultánea.

Registra por línea quantity_adjusted_out separada de recibida/devuelta, con vínculos a ajustes aplicados. Conserva la ecuación:
**despachado = recibido + en tránsito + devuelto + ajustado de salida**.

Si no queda tránsito y existe pérdida ajustada, usa estado terminal closed_with_adjustment («Cerrado con ajuste»), distinto de received. Si queda tránsito, conserva incidencia o reanúdalo mediante acción autorizada; pérdida parcial no cierra lo restante. El cierre puede ocurrir al aplicar si cumple todas las condiciones, de forma atómica y auditada. close_received nunca convierte pérdidas en recibido.

Actualiza DTOs, enums/constraints, proyecciones, filtros, detalle y cliente B04 para nuevo estado/cantidad. Documentos anteriores conservan su estado y cantidad ajustada cero. Demanda muestra recibido real y faltante justificado. No reasignes, crees reposiciones ni despaches automáticamente: conserva asignación histórica y explica la diferencia. No implementes retornos en B05.

## 6. Correcciones trazables

El original aplicado permanece inmutable. Corregir crea documento enlazado con motivo/evidencia, aprobación y compensación del motor; no modifica/borra el movimiento original ni reutiliza su clave.

Inspecciona las compensaciones admitidas para restaurar cantidad y valor del origen. No asumas que un positivo al promedio actual revierte un negativo histórico. Implementa al menos la corrección de cantidad de un ajuste aplicado ordinario con compensación justificable y enlazada. Rechaza saldo insuficiente, cantidades superiores a lo corregible o una compensación que invalide operaciones posteriores. Dos correcciones concurrentes no compensan dos veces el origen.

Para modalidades no soportadas (p. ej. corrección exclusivamente monetaria o reversión de pérdida de tránsito con operaciones posteriores), devuelve error de negocio explícito y documenta límites concretos. No muestres éxito ficticio ni extiendas reversión a movimientos arbitrarios. Conserva fechas operativa/contable y controles de períodos existentes; no construyas contabilidad general.

## 7. Interfaz

Entrega lista/formulario/detalle con filtros de estado/bodega/fecha y acceso desde Inventario. Nombre de producto, SKU, unidad y ubicación son principales; HU/lote complementan. Incluye adjuntar/abrir soporte, aprobar, cancelar, aplicar explícitamente, historial y enlace al Kardex por documento real.

Distingue Guardar borrador, Aprobar y Aplicar ajuste. Antes de aplicar resume ubicación, producto, dirección y cantidad; muestra costos solo a autorizados. Indica Aplicado y siguiente paso de revisión de HU si corresponde. Abrir/cerrar, navegar, adjuntar o consultar Kardex no aplica ni divide unidades. Implementa estados carga/error/vacío/sin permiso, foco/teclado, móvil y temas. Registra aceptación manual pendiente B08.

## 8. Migración y pruebas focalizadas

Si necesitas esquema, crea sucesora desde cabeza real. Ensaya con registros existentes en copia/base aislada, prueba conservación de saldos/valor/etiquetas/movimientos y respalda antes de aplicar a demo. Registra cabeza antes/después y recuperación. No ejecutes semillas destructivas ni reabras el saldo inicial.

Antes de recolectar integración/E2E, inspecciona fixtures y ambos DSN: solo erp_db_test; ejecuta suites en serie. Prueba reglas unitarias, integración PostgreSQL de invariantes/rollback/concurrencia y API por perfiles. Frontend: Vitest de comportamiento afectado, tipos Svelte, lint y build. Identifica mocks como simulación. No repitas suites ajenas sin cambio/fallo que lo justifique.

| Criterio | Comprobación requerida |
| --- | --- |
| B05-A1 | Adjuntar → aprobar; rechaza falta de motivo/referencia, archivo ajeno/pendiente/rechazado/eliminado y permiso insuficiente. Descarga/borrado posterior respetan soporte y ámbito. |
| B05-A2 | Positivo con costo, fallback a promedio y ausencia de costo/promedio; negativo al promedio de aplicación. Cantidad/valor/Kardex/HU concilian. Borrador/aprobación no mueven stock. |
| B05-A3 | Saldo insuficiente, doble aplicación, edición concurrente con aprobación, recepción concurrente con pérdida y dos operadores ajustando la misma HU no duplican ni consumen de más. |
| B05-A4 | Fallo tardío revierte documento/movimiento/HUs/saldos/valoración/incidencia/auditoría de éxito. Archivo cargado previamente puede persistir sin ajuste aplicado. |
| B05-A5 | Corrección ordinaria conserva original y compensa cantidad/valor justificables del origen; impide doble compensación y rechaza modalidades no soportadas. |
| B05-A6 | Despachar 10, recibir 8, justificar 2 perdidas: 8 recibidas, 0 tránsito, 2 ajustadas, Cerrado con ajuste y valor reducido correctamente. Nunca 10 recibidas. |
| B05-A7 | API genérica, replay y archivos no eluden aprobación/ámbito. Otro usuario/sucursal/empresa no ajusta tránsito ajeno ni recibe costo global. |
| B05-A8 | Migración conserva datos existentes; API persiste documentos/enlaces. Recorrido autenticado completo, móvil, temas y aceptación integrada pendientes B08. |

## 9. Documentación y cierre

Crea docs/ers-v1/entrega-bloque-05.md, docs/ers-v1/manual-ajustes.md y evidencia fechada en tmp/ers-v1/bloque-05/. Incluye contratos/permisos, migración/recuperación, mapa de consumidores, compensaciones admitidas, criterios A1–A8 y resultados reales. Registra causas/correcciones de fallos; no presentes resultados anteriores como pruebas actuales.

Actualiza E08/E12/E13, guía y API/esquema/RBAC cuando cambien. Actualiza manual de traslados con faltantes y cierre con ajuste. Conserva evidencia histórica y pendientes manuales B08. Un build aprobado no acredita recorrido autenticado.

Termina con lo implementado, comprobado y pendiente de aceptación B08. **No inicies B06.**

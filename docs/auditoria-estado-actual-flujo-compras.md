# Auditoría de solo lectura: compras, cotizaciones, recepción, retaceo e inventario

**Fecha:** 30 de septiembre de 2026  
**Estado:** diagnóstico del código y del árbol de trabajo; no es una autorización para implementar cambios.  
**Plan relacionado:** docs/planificacion-bloque-0-alcance-y-hoja-de-ruta-compras.md

## 1. Alcance y método

Se contrastaron los siete apuntes PDF de las reuniones 1 y 2, la guía funcional existente, la arquitectura documentada y el código actual de los cinco módulos de compra, más el módulo de inventario. La revisión cubrió routers, permisos, casos de uso, entidades, persistencia y cambios locales de frontend.

El estado observado corresponde a la rama codex/inventory-workflow-dashboard, commit a9bc45e, más el árbol de trabajo compartido que ya tenía modificaciones locales. No se descartó ni se revirtió ningún archivo. Los hallazgos distinguen la implementación confirmada del trabajo local aún no validado.

La auditoría fue de solo lectura respecto al código funcional. No se consultó la base de datos activa ni se inició el ERP en Docker; tampoco se ejecutaron pruebas. Este informe y el plan relacionado son documentación, no cambios funcionales.

## 2. Conclusión ejecutiva

El flujo actual cubre operaciones básicas, pero todavía representa una compra directa desde una solicitud aprobada hacia una cotización por proveedor. No implementa todavía el proceso de abastecimiento consolidado que describen los apuntes.

Hay capacidades existentes que se pueden reutilizar:

- Una solicitud puede ser aprobada por un usuario con el permiso purchase_requests:approve. La aplicación no exige que esa persona tenga un cargo específico ni comprueba una relación de supervisor.
- Una cotización puede vincular varias solicitudes en estado aprobado, parcialmente cotizado o cotizado; suma las líneas que tengan el mismo producto y unidad y conserva enlaces de procedencia hacia las solicitudes.
- La respuesta del proveedor se captura manualmente y acepta una cantidad disponible menor que la cantidad pedida, pero exige que la respuesta mencione todos los productos y unidades incluidos en la solicitud enviada.
- Una orden puede tomar una parte de las líneas de una cotización y limita la cantidad a la disponibilidad pendiente de esa oferta.
- El inventario tiene movimientos de entrada, acomodo y traslado. Sin embargo, recibir/verificar una compra o cerrar un retaceo no publica un movimiento de inventario.

Las brechas principales son el consolidado como entidad editable e independiente, la separación clara entre solicitud de precio enviada y oferta recibida, la comparación y adjudicación por línea, el alcance seguro por sucursal en cotizaciones y órdenes, y la falta de integración entre recepción física e Inventario. Esta última brecha queda confirmada como prioridad del proyecto, no como trabajo diferido.

**La causa de que una cola no aparezca no se puede atribuir solo a permisos.** En las cotizaciones, el endpoint no acepta filtro de sucursal. La interfaz local en progreso oculta los conteos de cotización para usuarios en una sucursal específica porque no puede filtrar con seguridad. El listado de cotizaciones y el de órdenes tampoco reciben ese filtro desde el backend. Por tanto, el permiso puede habilitar lectura, pero no resuelve el alcance de datos.

## 3. Flujo que ejecuta el sistema hoy

1. **Solicitud de compra:** se crea como borrador con sucursal, almacén, fecha requerida, justificación y líneas. Se envía para revisión y luego se aprueba o rechaza con permisos.
2. **Solicitud de cotización:** un usuario con permiso de gestión crea un borrador para un proveedor, moneda y una o más solicitudes elegibles (aprobadas, parcialmente cotizadas o cotizadas). La solicitud de precio se marca como enviada al proveedor mediante un cambio de estado.
3. **Oferta recibida:** el equipo captura manualmente los precios, descuentos, impuestos, gastos y condiciones reportados por el proveedor. No se encontró una bandeja de correo ni un vínculo específico de adjunto PDF en la entidad de cotización.
4. **Evaluación:** las ofertas comparables se consultan para una solicitud de compra y moneda. La proyección de comparación contiene proveedor, moneda, total, entrega, vigencia y estado. No entrega una matriz de precios por producto.
5. **Selección:** se selecciona la cotización completa como ganadora; no existe una adjudicación persistida por producto y cantidad. Una oferta seleccionada puede originar una orden.
6. **Orden de compra:** cada orden está ligada a una sola cotización/proveedor. Puede contener una selección de sus líneas y cantidades no mayores a la cantidad todavía disponible.
7. **Compra/recepción:** se registra la recepción contra una orden; puede recibirse menos de lo ordenado y la orden avanza según lo recibido. La compra puede pasar por recibida, verificada y cerrada.
8. **Retaceo:** se crea a partir de una compra recibida, verificada o cerrada. Se introducen flete, gastos, DAI e IVA de importación; el costo distribuido se calcula por participación FOB. En el modelo, el costo total agrega FOB, flete, gastos y DAI; el IVA de importación se guarda aparte.
9. **Inventario:** no hay llamada desde la recepción o el retaceo hacia InventoryUseCases.post_movement. El inventario sigue siendo un módulo aparte y no se incrementa automáticamente por este flujo.

### Dónde se vuelve confuso

La misma cotización representa dos momentos distintos: el documento que el equipo prepara para pedir precio y la respuesta económica que registra después. Además, “seleccionar oferta” significa seleccionar una cotización completa, aunque la necesidad real podría terminar repartida entre varios proveedores y cantidades. La pantalla obliga al usuario a navegar solicitud → nueva cotización → proveedor → solicitud a cotizar, sin una bandeja de trabajo que conecte claramente lo pendiente.

## 4. Matriz de brechas frente a los siete apuntes

| Capacidad | Situación verificada | Brecha / consecuencia |
|---|---|---|
| Solicitudes por sucursal | El listado de solicitudes acepta estado y branch_id; la ruta valida el alcance de sucursal. | No se encontraron filtros de período que materialicen los horizontes de consolidación indicados en los apuntes. |
| Agrupar demanda repetida | Al crear una cotización se pueden vincular varias solicitudes y se suman producto + unidad en sus líneas. Las relaciones guardan las líneas fuente. | Es agrupación dentro de una cotización para un proveedor, no un consolidado compartido, editable y filtrable por fechas, sucursal o disponibilidad. No mantiene por separado cantidad aceptada, rechazada, añadida por Compras y su motivo. |
| Compra planificada para casa matriz | La creación de cotización requiere al menos una solicitud vinculada. | No permite originar una línea planificada por Compras cuando ninguna sucursal la solicitó. |
| RFQ enviada a cada proveedor | Cada cotización tiene un proveedor, guarda sus líneas/enlaces de cobertura y el repositorio protege la cobertura original al registrar la respuesta. | No existe una entidad de consolidado que emita varias RFQ a partir de una misma demanda; tampoco se encontró control de revisiones ni un artefacto descargable que pruebe qué archivo exacto recibió el proveedor. |
| Respuesta parcial del proveedor | Puede guardarse available_quantity menor que la cantidad solicitada; la orden usa esa cantidad disponible como límite. | La respuesta debe incluir todas las líneas/producto-unidad de la RFQ y registrar el mismo quantity solicitado. No representa con claridad una oferta que excluya líneas o cubra solo una parte de la cantidad pedida. |
| PDF/correo de proveedor | El estado de envío cambia en el sistema y la respuesta se registra manualmente. | No se encontró envío por correo, bandeja, archivo adjunto ni evidencia del documento exacto que se remitió o recibió. |
| Comparar ofertas | Endpoint por solicitud; incluye total, moneda, entrega, vigencia y estado; rechaza comparación sin conversión si hay monedas distintas. | No muestra precios/condiciones alineados por línea, cargos comparables ni adjudicación por producto/cantidad. Las monedas requieren una regla y tipo de cambio aprobados. |
| Adjudicar una parte a distintos proveedores | Una cotización completa cambia a seleccionada. Una orden se crea desde una sola cotización. | No hay registro único de adjudicación por línea, cantidad, proveedor, usuario y razón; el resultado parcial entre proveedores queda sin una trazabilidad consolidada. |
| Orden consolidada | La orden conserva proveedor, sucursal, almacén y referencia a una cotización. | Una orden corresponde a una cotización/proveedor; las órdenes divididas no quedan unidas a una adjudicación que explique el total consolidado. |
| Recepción física | Hay cantidades recibidas parciales contra la orden y transiciones de estado. | El detalle registra quantity_received, pero no modela de forma explícita inspección física, cantidad aceptada/rechazada, daño, evidencia o acomodo. |
| Retaceo y costo aterrizado | Asigna FOB, flete, gastos y DAI por proporción FOB; el IVA queda separado. | No actualiza el costo del catálogo ni el inventario. La aplicación guarda importes ingresados; no clasifica arancel ni determina por sí misma la tasa DAI. |
| Stock y Kardex | Inventario tiene movimientos idempotentes y tipos receipt, putaway, transfer, pick, shipment y ajustes. | No hay integración desde Compras o Retaceo que publique el movimiento al completar recepción/acomodo. |
| Historial de precios por proveedor | Producto-proveedor puede guardar unit_cost, moneda, MOQ, múltiplo y plazo. Compras guarda los precios de sus líneas. | No se encontró una vista histórica comparativa de precios pagados por producto/proveedor. El vínculo producto-proveedor es un registro maestro único por par, no un historial de versiones de cada precio. |
| Prioridad/demanda | Se guardan solicitudes y compras históricas. | Una solicitud expresa necesidad, no venta ni consumo. Pronóstico y prioridad necesitan datos confiables de ventas y movimientos; deben ser posteriores y no activar compras automáticas. |

## 5. Permisos y alcance de datos

Los endpoints separan permisos por módulo:

- Solicitudes: purchase_requests:read, purchase_requests:manage, purchase_requests:approve.
- Cotizaciones: purchase_quotations:read, purchase_quotations:manage, purchase_quotations:select.
- Órdenes: purchase_orders:read, purchase_orders:manage, purchase_orders:approve, purchase_orders:send.
- Compras/recepciones: purchases:read, purchases:manage, purchases:receive, purchases:verify.
- Retaceo: retaceos:read, retaceos:manage, retaceos:calculate, retaceos:verify.

La autorización del aprobador de solicitudes se implementa por permiso; el código inspeccionado no resuelve “quién es el supervisor de esta persona” ni aplica niveles jerárquicos. El responsable del proyecto confirmó que basta el permiso asignado y que una persona puede aprobar su propia solicitud si también posee ese permiso. El sistema actual ya permite la acción por permiso; cualquier autoaprobación debe conservar auditoría de autor y decisión.

Hay una diferencia importante de alcance:

- Solicitudes, compras y retaceos reciben branch_id y validan alcance en el router.
- El endpoint de cotizaciones lista por estado/proveedor/paginación y el de órdenes por estado/proveedor/paginación; ninguno acepta branch_id ni valida el alcance de sucursal en esos listados.
- Los detalles de cotizaciones y órdenes consultados por ID tampoco muestran esa validación de sucursal en el router revisado.

Esto explica por qué dar purchase_quotations:read no garantiza una cola contextual por sucursal. También hace necesario definir si cotizaciones y órdenes son siempre datos de Compras a nivel empresa, o si ciertos perfiles de sucursal podrán ver solo las vinculadas a sus solicitudes. La decisión debe implementarse en backend y probarse allí; ocultar tarjetas en frontend no constituye un control de acceso.

## 6. Arquitectura recomendada

Conservar el monolito modular y los límites Clean/Hexagonal que ya documenta el repositorio. No hace falta iniciar microservicios ni reemplazar los cinco módulos.

### Responsabilidades propuestas

1. **Solicitudes:** fuente de la necesidad de sucursal y su aprobación. No altera inventario.
2. **Consolidación/abastecimiento:** nueva capacidad de aplicación que agrupa líneas elegibles por período y producto, conserva procedencia por solicitud/sucursal y separa la demanda añadida para la bodega central. Debe consultar stock, reservas y tránsito mediante contratos de Inventario; no copiar sus tablas ni tratar una solicitud como stock.
3. **RFQ por proveedor:** prepara una copia/versionado inmutable del conjunto de productos y cantidades enviado a cada proveedor. La RFQ guarda a qué líneas del consolidado responde.
4. **Oferta recibida:** registra la respuesta del proveedor en una versión separada, incluyendo líneas omitidas o parcialmente atendidas, moneda, precio, descuento, impuesto declarado, cargos, disponibilidad, plazo, vigencia, términos y evidencia/documento.
5. **Comparación y adjudicación:** una decisión humana registra proveedor y cantidad elegida por línea, usuario, fecha y justificación. Impide adjudicar más que la demanda consolidada o la oferta disponible y conserva las alternativas descartadas.
6. **Órdenes:** generar una o más órdenes por proveedor a partir de la adjudicación, reutilizando PurchaseOrderUseCases y manteniendo la trazabilidad al consolidado, RFQ, oferta y solicitudes.
7. **Recepción e inventario:** conservar Purchase como documento de recepción e integrar como prioridad el conteo/inspección, cantidades aceptadas/rechazadas y ubicación con un movimiento idempotente hacia Inventory. No duplicar inventario; acordar la semántica de disponibilidad y el contrato antes de publicar cantidades.
8. **Retaceo y valoración:** conservarlo como registro de costos aterrizados basados en documentos reales. Como parte de la integración prioritaria, asociar el costo aprobado a las mismas líneas/lotes recibidos sin crear otro movimiento de cantidad. Mantener DAI e IVA bajo reglas contables/aduanales aprobadas; no convertir enlaces informativos en calculadora legal.

El tablero operativo que el usuario pidió debe vivir dentro de Cotizaciones de compra o del flujo existente de Compras, con enlaces directos a cada pendiente. No implica crear un dashboard general ni un módulo de Ventas. Si la consolidación se aprueba como requisito, su pantalla es una bandeja de trabajo del proceso de compra, no un dashboard separado por departamento.

### Esquema de integración a alto nivel

- Mantener los agregados existentes y sumar un agregado de abastecimiento/consolidación.
- Trazabilidad explícita de línea a solicitud y sucursal; demanda de casa matriz identificada como planificada por Compras.
- RFQ congelada por proveedor y versión; respuesta comercial mutable solo creando una nueva versión.
- Adjudicación independiente de respuesta y orden.
- Comunicación entre módulos por casos de uso/puertos y transacciones de aplicación, no por importar modelos ORM ajenos.
- Para la integración prioritaria con Inventario, usar referencia de origen e idempotencia ya disponibles en sus movimientos para impedir entradas dobles. Confirmar si recepción física y acomodo son un único paso o pasos separados.

## 7. Qué está modificado localmente y debe tratarse como trabajo en progreso

El árbol de trabajo ya contiene cambios locales previos en listas/detalles de solicitudes, cotizaciones, órdenes, compras y retaceos, más componentes y pruebas nuevas. No se modificaron durante esta auditoría.

A alto nivel, esos cambios locales:

- agregan una cola con tarjetas al listado de Cotizaciones de compra;
- pasan branch_id en consultas de solicitudes, compras y retaceos y muestran el contexto de sucursal;
- ocultan los conteos de cotizaciones en la cola cuando el usuario está limitado a una sucursal, porque el endpoint no permite filtrar;
- permiten abrir la creación de cotización desde una solicitud concreta y muestran el nombre del producto junto a su ID;
- agregan una caja informativa de consulta DAI con enlaces externos, sin calcular aranceles;
- mejoran estados de carga, filtros y navegación visual.

El comportamiento de “ocultar conteos” es prudente para evitar presentar totales de otra sucursal, pero no resuelve la falta de filtro de cotizaciones. El listado de cotizaciones continúa usando un endpoint sin branch_id. Las órdenes tienen el mismo hueco de alcance. La solución debe centralizar la autorización en API/backend antes de dar ese acceso a usuarios limitados por sucursal.

Las pruebas unitarias que aparecen en el árbol de trabajo no se ejecutaron. Por eso no se confirma compilación ni comportamiento operativo de estos cambios. La consulta de nombres de producto hace solicitudes individuales por producto; es aceptable para una pantalla pequeña, pero convendría un endpoint por lote/caché si el volumen de líneas crece.

## 8. Secuencia recomendada después de este diagnóstico

1. Preservar los cambios locales actuales; aislar trabajo nuevo y dejar una recuperación de código/base de desarrollo.
2. Cerrar permisos, alcance por sucursal y navegación/detalle del flujo actual sin ampliar todos los módulos a la vez.
3. Implementar y verificar una ruta vertical pequeña de OC existente → conteo/inspección → movimiento idempotente en Inventory.
4. Vincular el retaceo con las líneas recibidas usando una regla de costos aprobada, sin alterar cantidades.
5. Crear el consolidado con procedencia y consulta de stock/reservas/tránsito mediante el contrato de Inventario.
6. Separar RFQ y oferta recibida; después persistir comparación y adjudicación humana por producto/cantidad.
7. Generar las OCs desde las adjudicaciones y conectarlas a la ruta de recepción ya probada.
8. Completar la cola de trabajo dentro de Cotizaciones de compra y sumar historial/analítica cuando los datos sean suficientes.

## 9. Criterios funcionales confirmados después de la auditoría

El 30 de septiembre de 2026, el responsable revisó las decisiones funcionales del plan. Estas respuestas actualizan los criterios con los que se deben interpretar las brechas; no cambian la implementación observada en la rama/commit auditados.

- Fecha requerida de solicitud: opcional. Sucursal, almacén, justificación y al menos una línea: requeridos.
- Autoaprobación: permitida si la persona tiene el permiso de aprobación. El flujo actual autoriza por permiso y no exige un supervisor.
- Filtros de 7, 15, 30, 90 días y rango personalizado; 30 días iniciales. Paginación inicial 20 con opciones 10, 20, 25, 30 y personalizada.
- Aprobación de sucursal precede a la elegibilidad para consolidar. La decisión puede ser completa, por línea o por cantidad parcial; solicitudes ya aprobadas pueden añadirse a un consolidado que todavía no fue enviado al proveedor.
- Se conserva separado el origen de demanda de sucursales y el volumen adicional que Compras propone para la bodega central.
- La comparación muestra detalle por producto/línea y resumen por proveedor/grupo. Puede haber cualquier cantidad de ofertas guardadas, pero una matriz muestra hasta tres proveedores; la selección de ofertas y adjudicación es humana.
- PDF por proveedor, archivo original de oferta recibida y reporte de comparación PDF/Excel quedan dentro del alcance aprobado. El correo automático no se considera decidido.
- Las acciones se asignan por permisos, no por el nombre del rol. La autorización y ámbito se deben proteger en backend.

### Contraste de decisiones con el estado auditado

| Criterio objetivo | Estado comprobado en la auditoría | Consecuencia para el trabajo |
|---|---|---|
| Fecha requerida opcional; filtros 7/15/30/90 días y rango; 30 días iniciales | El listado de solicitudes acepta estado y sucursal, pero no se encontraron filtros por período. La obligatoriedad actual de fecha no se da por confirmada en esta inspección. | Incorporar filtros y validar el formulario/caso de uso para permitir fecha vacía sin romper registros existentes. |
| Paginación inicial 20; nombres de producto/unidad legibles | La auditoría de flujo no verificó exhaustivamente el tamaño predeterminado de cada listado ni cada celda de detalle. | Verificar esos dos puntos de UI/API durante el diseño de la mejora, sin presentarlos como hechos ya implementados. |
| Autoaprobación solo cuando se posee `purchase_requests:approve` | El caso de uso revisado aplica autorización por permiso y no exige jerarquía de supervisor. | Es compatible con la decisión funcional; confirmar que la bitácora guarda actor/fecha/resultado al usar la ruta. No hace falta introducir un rol fijo. |
| Aprobar primero; aceptación total, por línea o por cantidad parcial | El flujo actual permite aprobar/rechazar la solicitud, pero la aceptación parcial del consolidado por cantidad aún no existe. | Mantener cantidad original y diseñar decisiones separadas por línea/cantidad con estado derivado; añadirla al consolidado, no alterar el documento fuente. |
| Consolidado abierto, editable y congelado al enviar RFQ | No existe un agregado de consolidado independiente. Hoy varias solicitudes se agrupan dentro de una cotización para un proveedor. | Brecha estructural principal: diseñar procedencia, cambios y copia/versionado inmutable por proveedor antes de modificar las cotizaciones existentes. |
| Demanda de sucursal separada de volumen que Compras añade para casa matriz | La cotización actual exige solicitud vinculada; no se encontró origen central sin solicitud ni objetivo separado. | Incorporar un origen explícito para demanda central sin falsificar o modificar solicitudes de sucursal. |
| Todas las ofertas almacenadas; hasta tres proveedores en una matriz, comparación por línea y resumen general | Comparación actual es un resumen por solicitud con total, moneda, entrega, vigencia y estado; no presenta matriz por línea ni adjudicación. | Guardar respuestas independientemente; limitar la selección de cada vista comparativa a tres, no la cantidad de ofertas persistidas. Mantener selección humana. |
| RFQ PDF, documento original de proveedor y exportación comparativa PDF/Excel | El envío solo cambia estado y la oferta se captura manualmente; no se encontró adjunto/evidencia del documento remitido o recibido ni reporte de comparación. | Diseñar registro/documentación y acceso al archivo como brechas nuevas; no inferir correo automático. |
| Adjudicación total/parcial por línea y OC por proveedor | Hoy se selecciona una cotización completa; cada OC nace de una sola cotización, aunque puede usar algunas de sus líneas. No hay registro de adjudicación fraccionada por línea/cantidad. | Agregar trazabilidad explícita a adjudicación; sumar solo cantidades elegidas al generar órdenes. |
| Recepción inspeccionada y disponibilidad tras putaway; costo/retaceo separado | Compras/recepción no publica movimiento de Inventario. Inventory ya tiene movimientos y conceptos de receipt/putaway; la semántica y el vínculo con Compras requieren auditoría de contrato. Retaceo actual distribuye FOB, flete, gastos y DAI por participación FOB y mantiene IVA separado. | Implementar una ruta idempotente recepción↔Inventario solo después de mapear producto/unidad/almacén y estados. Mantener la política de costo sujeta a Contabilidad. |
| Permisos por acción y alcance de empresa/sucursal | Las solicitudes, compras y retaceos validan `branch_id`; listados/detalles de cotizaciones y órdenes revisados no validan el mismo ámbito. | El permiso de lectura no basta para habilitar una cola segura. Completar filtrado/autorización en backend antes de mostrar datos a usuarios limitados por sucursal. |

## 10. Recomendaciones registradas y preguntas que siguen abiertas

Estas recomendaciones permiten continuar la arquitectura documental, pero no deben convertirse en cálculos financieros/contables automáticos sin validar las dependencias.

- **Estados para sucursal (recomendación):** distinguir `Borrador`, `En aprobación`, `Aprobada/Parcialmente aprobada/Rechazada`, `En consolidado`, `En cotización`, `Adjudicada total/parcial`, `Ordenada`, `Recibida parcial/total` y `Ubicada/Disponible`. Presentarlos en cronología; estar en RFQ no significa que ya haya orden o mercancía.
- **Inventario (contrato abierto):** Inventario es fuente de saldos. Falta confirmar en el módulo existente el significado de utilizable, reservado, inspección y tránsito, cómo se evita contar dos veces reservas/órdenes y cómo se identifica entrada en tránsito no comprometida. La recomendación matemática queda documentada en el plan; no se automatiza hasta validar esos términos.
- **Recepción (recomendación):** contar e inspeccionar en recepción; aceptar/rechazar cantidades; publicar disponibilidad después de ubicar lo aceptado. Mantener estado de costeo separado y pendiente hasta revisión contable, salvo política que requiera costo final antes de disponibilidad.
- **Monedas:** no ordenar ofertas por total convertido sin fuente, fecha y reglas de tipo de cambio acordadas.
- **Finanzas/Contabilidad (bloquea retaceo automático):** decidir gastos capitalizables, distribución, IVA, moneda/tipo de cambio y momento de cierre. No se definen tasas DAI ni tratamiento fiscal en esta auditoría.
- **Aprobación de inversión (recomendación):** mostrar total/moneda y aplicar aprobación por permiso. El significado habitual puede incluir escalamiento por umbral presupuestario, pero no existe un importe ni fuente presupuestaria acordada. No inventar límites; documentar fuente, período, moneda y aprobador si se incorpora.
- **Compras locales vs centralizadas:** reutilizar entidades compartidas y distinguir modalidad/destino cuando el comportamiento existente lo permita. El alcance inmediato prioriza la consolidación y la compra centralizada; las excepciones locales requieren definición antes de ampliarse.
- **Identificación física:** mantener SKU estable; lote si el producto requiere trazabilidad/caducidad y serie por unidad para equipo serializado. Code 128/QR queda configurable por Bodega; la necesidad de etiquetado/escaneo avanzado se valida en su proceso.

### Pendientes técnicos y de negocio

1. Auditar el contrato real de Inventory para disponibilidad, reservas, tránsito, ubicación, publicación idempotente y reversa de entradas.
2. Confirmar con Finanzas/Contabilidad la clasificación de costos, tratamiento del IVA, distribución del retaceo y evidencia aceptada.
3. Si se implementan umbrales de aprobación de OC, definir presupuesto/fuente, moneda, período y límites por usuario/permisos.
4. Definir campos obligatorios finales de oferta y cualquier política de evaluación de proveedores.
5. Verificar qué estados y movimientos existentes representan recepción, inspección y acomodo antes de cambiar la disponibilidad.
6. Precisar excepciones de compra local por sucursal frente al flujo centralizado.

## 11. Actualización de alcance acordada por el responsable del proyecto

El 30 de septiembre de 2026 se corrigió el criterio previo que trataba la integración con Inventario como futura o dependiente de otro compañero. La conexión con el Inventario existente y el flujo mínimo de recepción física son ahora prioridad del proyecto. Se reutiliza el módulo y sus casos de uso; no se reconstruyen saldos, almacenes ni traslados. La revisión con el compañero queda para el período 3 y funciona como validación, no como condición para planificar o avanzar.

La auditoría sigue siendo un diagnóstico de solo lectura y no implica que la integración ya esté implementada. Los hechos técnicos descritos arriba siguen representando el estado inspeccionado.

## 12. Fuentes inspeccionadas

Apuntes de reuniones:
- reunion-01-parte-1-solicitudes-y-consolidacion.pdf
- reunion-01-parte-2-cotizaciones-y-ordenes.pdf
- reunion-01-parte-3-gastos-recepcion-y-inventario-futuro.pdf
- reunion-02-grupo-1-apuntes.pdf
- reunion-02-grupo-2-apuntes.pdf
- reunion-02-grupo-3-apuntes.pdf
- reunion-02-grupo-4-apuntes.pdf

Código y documentación:
- docs/architecture.md
- docs/flujo-compras-inventario-retaceo.md
- backend/app/api/v1/routers/purchase_requests.py
- backend/app/api/v1/routers/purchase_quotations.py
- backend/app/api/v1/routers/purchase_orders.py
- backend/app/api/v1/routers/purchases.py
- backend/app/api/v1/routers/retaceos.py
- backend/app/application/purchase_quotations/use_cases.py
- backend/app/application/purchase_orders/use_cases.py
- backend/app/application/purchases/use_cases.py
- backend/app/application/retaceos/use_cases.py
- backend/app/application/inventory/use_cases.py
- backend/app/domain/entities/purchase_quotation.py
- backend/app/domain/entities/retaceo.py
- backend/app/infrastructure/models/product_master.py
- frontend/src/lib/features/purchase-quotations/components/ProcurementWorkQueue.svelte


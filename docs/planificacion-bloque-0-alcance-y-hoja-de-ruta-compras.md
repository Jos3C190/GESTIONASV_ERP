# Plan integral por bloques: flujo de compras y crecimiento del ERP

**Versión:** 5 — decisiones funcionales incorporadas y pendientes acotados  
**Fecha:** 30 de septiembre de 2026  
**Estado:** Bloque 0 actualizado con decisiones del responsable; quedan recomendaciones por validar y contratos técnicos por auditar.  
**Alcance de este documento:** incorporar decisiones tomadas sobre los siete apuntes, especificar recomendaciones restantes, arquitectura y bloques implementables. Esta fase es documental; no modifica código, módulos, datos ni permisos.

## 1. Propósito

Usar los apuntes de los siete PDF para preparar una implementación incremental del proceso de compras. Primero se acuerda el mapa funcional y arquitectónico; después se audita el estado real del repositorio y se contrasta con este plan; solo entonces se decide qué brechas se implementan.

La conexión con Inventario y la recepción física son parte prioritaria del trabajo actual. Se reutilizarán las capacidades existentes de Inventario; no se reconstruirá ese módulo ni se duplicarán saldos, almacenes, sucursales o traslados. La revisión del compañero en el período 3 será una revisión del trabajo, no un requisito para empezar ni una transferencia de responsabilidad.

## 2. Fuentes y nivel de certeza

Se tomaron como fuente los apuntes de las reuniones 1 y 2:

- `reunion-01-parte-1-solicitudes-y-consolidacion.pdf`
- `reunion-01-parte-2-cotizaciones-y-ordenes.pdf`
- `reunion-01-parte-3-gastos-recepcion-y-inventario-futuro.pdf`
- `reunion-02-grupo-1-apuntes.pdf`
- `reunion-02-grupo-2-apuntes.pdf`
- `reunion-02-grupo-3-apuntes.pdf`
- `reunion-02-grupo-4-apuntes.pdf`

Los apuntes se contrastaron con las decisiones del responsable del proyecto registradas el 30 de septiembre de 2026. Una decisión confirmada aquí define el comportamiento objetivo; no afirma que el código ya lo implemente. Las brechas verificadas en la auditoría de solo lectura del Bloque 1 siguen separadas en el informe de auditoría.

### Clasificación usada

- **Recurrente en los apuntes:** aparece de forma consistente en varias exposiciones; se propone como requisito base para confirmar.
- **Pendiente de decisión:** los apuntes son ambiguos o contienen versiones distintas.
- **Idea atribuida a quien expone:** sugerencia personal, no regla acordada.
- **Futuro explícito:** los apuntes indican que no debe implementarse en el trabajo inmediato. Esto aplica a capacidades avanzadas de inventario y logística; no excluye conectar las compras con el Inventario existente ni registrar la recepción física aceptada.
- **Hecho del sistema:** solo se etiqueta así después de verificarlo en el repositorio; este documento no constituye esa auditoría.

### Precedencia cuando los apuntes y la decisión actual difieren

Algunos apuntes de la Reunión 1 Parte 3 y de los Grupos 3 y 4 etiquetan como futuro el ingreso físico detallado a Inventario. La decisión más reciente del responsable del proyecto es conectar Compras con el Inventario existente y completar la recepción física básica como prioridad actual. Por eso este plan incluye conteo, inspección, cantidad aceptada y movimiento de Inventario después de la verificación. El etiquetado unitario, el escaneo de cada caja/ubicación, seguimiento de contenedores, rutas y capacidad avanzada siguen como ampliaciones futuras. Esta resolución refleja la decisión actual del responsable; no se atribuye como aprobación del ingeniero.

### Síntesis trazable de los siete apuntes

| Necesidad o propuesta | Fuentes donde aparece | Tratamiento para el plan |
|---|---|---|
| Solicitudes de sucursales con aprobación, estado claro, búsqueda por fecha y nombres legibles | R1-P1, R2-G1, R2-G2, R2-G4 | Requisito base; definir quién aprueba y si acepta parcialmente. |
| Consolidar productos/unidades compatibles entre sucursales, conservando solicitud, sucursal y cantidad de origen | R1-P1, R2-G1, R2-G2, R2-G3, R2-G4 | Requisito central; grupo editable, trazable y con período configurable. |
| Consultar existencias y compras en camino; agregar necesidad separada para bodega matriz | R1-P1, R2-G1, R2-G2, R2-G3, R2-G4 | Requisito para evitar duplicados y distinguir demanda de sucursal de abastecimiento central. |
| Enviar lista versionada a uno o varios proveedores y recibir ofertas parciales | R1-P2, R2-G1, R2-G2, R2-G3 | Requisito; el proveedor responde sobre lo que recibió, sin reescribir las líneas. |
| Comparar condiciones y adjudicar manualmente cantidades por producto; generar OC por proveedor | R1-P2, R2-G1, R2-G2, R2-G3, R2-G4 | Requisito; guardar decisión, usuario, cantidad y motivo; no seleccionar automáticamente. |
| Separar gastos estimados de los reales, documentar cantidades recibidas y retacear con datos reales | R1-P3, R2-G3, R2-G4 | Requisito; resolver fórmula/costos con responsable contable; no sumar cantidad desde retaceo. |
| Mostrar una cola de pendientes de compras dentro del flujo existente | R2-G1, R2-G3 | Mejora de navegación, después de que API, estados y permisos definan conteos correctos. |
| PDF de solicitud por proveedor | R1-P2, R2-G1, R2-G2, R2-G3 | Requisito de salida a validar; envío automático por correo aún no está definido. |
| Adjuntar oferta original, exportar comparación y evaluar proveedores | R2-G3 | Propuestas opcionales; priorizar solo tras acordar formatos y criterios. |
| Analizar demanda por región/temporada y desempeño | R1-P1, R2-G2, R2-G4 | Futuro; distinguir solicitudes de sucursal de ventas/consumo real. No automatizar compras. |
| Etiquetas, QR/códigos, escaneo, contenedores y seguimiento de rutas | R1-P3, R2-G3, R2-G4 | Futuro avanzado, aparte de la integración mínima de recepción decidida como prioridad actual. |

**Claves de fuente:** R1-P1/P2/P3 = Reunión 1, partes 1/2/3; R2-G1/G2/G3/G4 = Reunión 2, grupos 1/2/3/4. Los ejemplos de cantidades, productos, zonas y número de proveedores ilustran los apuntes; no se convierten automáticamente en reglas del sistema.

## 3. Alcance funcional propuesto

### 3.1 Flujo principal que se planificará

1. Las sucursales comunican una necesidad interna a Compras; no compran directamente al proveedor.
2. Compras reúne necesidades elegibles en un **consolidado de compra** durante un período definido, manteniendo el origen de cada línea.
3. Compras consulta stock, reservas y pedidos en camino mediante el módulo existente de Inventario, ajusta lo que planea atender y puede agregar una necesidad separada para la bodega central.
4. El consolidado se divide en solicitudes de precio dirigidas a uno o varios proveedores, según los productos que cada uno ofrece.
5. Se registra una respuesta estructurada por proveedor contra la lista y versión que recibió. La respuesta puede ofrecer toda, parte o ninguna de la cantidad pedida.
6. Compras compara las respuestas y decide manualmente qué proveedor cubrirá cada producto y cantidad.
7. Se crea una orden por proveedor seleccionado, únicamente con las cantidades adjudicadas.
8. Se registran los gastos reales acordados para la orden y se inicia la recepción de lo entregado.
9. La bodega cuenta e inspecciona, registra cantidades aceptadas/rechazadas y ubicación, y verifica la recepción.
10. El sistema publica una sola vez la cantidad aceptada al módulo existente de Inventario; la disponibilidad depende de la etapa física acordada.
11. El retaceo distribuye costos reales sobre las cantidades recibidas, según una regla validada, y se asocia a esas mismas líneas sin generar cantidades nuevas.

### 3.2 Vocabulario del proceso

| Término | Significado propuesto | No significa |
|---|---|---|
| Solicitud de compra de sucursal | Necesidad interna con sucursal, bodega, justificación y una o más líneas de producto/unidad/cantidad; fecha requerida opcional. | Compra al proveedor ni entrada de stock. |
| Consolidado | Reunión editable de líneas de solicitudes y, por separado, necesidades planificadas para la bodega central. | Borrar, sobrescribir o atribuir a las sucursales las cantidades agregadas por Compras. |
| Solicitud de cotización a proveedor / RFQ | Lista y cantidades que Compras prepara y envía a un proveedor para solicitar precio. | La respuesta del proveedor. |
| Oferta o cotización recibida | Respuesta del proveedor a una RFQ, con cantidades ofrecidas, precio y condiciones. | Una compra ya autorizada. |
| Adjudicación | Decisión humana de asignar proveedor y cantidad por producto/línea. | Selección automática o conversión total obligatoria de una oferta en orden. |
| Orden de compra | Compromiso autorizado que se envía al proveedor con las líneas adjudicadas. | Mercancía recibida o stock disponible. |
| Recepción | Registro de lo que llegó, fue contado e inspeccionado; incluye cantidades aceptadas/rechazadas y ubicación. | Que toda cantidad ordenada pase automáticamente a stock disponible. |
| Retaceo | Cálculo documentado de costos reales para las líneas recibidas. | Un movimiento adicional de cantidades. |

## 4. Flujo objetivo y trazabilidad

```text
Solicitud SCR de sucursal ─┐
                           ├─> Consolidado maestro editable ─> RFQ por proveedor/version
Necesidad central ─────────┘                                  └─> Ofertas recibidas
                                                                  ↓
                                    Comparación humana y adjudicación por producto/cantidad
                                                                  ↓
                                               Una OC por cada proveedor adjudicado
                                                                  ↓
                                            Gastos reales → recepción física e inspección
                                                                  ↓
                                         Entrada/acomodo en Inventario existente
                                                                  ↓
                                               Retaceo asociado a lo recibido
```

Cada línea debe conservar su procedencia: solicitud y sucursal, cantidad original, cantidad aceptada o excluida, cambio realizado por Compras y motivo; las líneas de abastecimiento central se registran como tales. El historial también conserva las cantidades solicitadas a cada proveedor, la respuesta que dio, cuánto se adjudicó y cuánto quedó sin adjudicar.

Las listas enviadas a proveedores deben conservar una **versión o copia inmutable** con productos y cantidades entregados a cada uno. Si el consolidado cambia después del envío, se genera una nueva versión; no se altera retrospectivamente lo que recibió el proveedor.

Los importes de cotizaciones alternativas no se suman entre sí. La comparación presenta alternativas; solo las líneas adjudicadas forman órdenes y montos comprometidos.

## 5. Arquitectura propuesta para evaluar

### 5.1 Forma general

Mantener el monolito modular y la arquitectura documentada del repositorio. No proponer microservicios ni una reconstrucción. Reutilizar las capacidades actuales y confirmar en la auditoría si la consolidación requiere un nuevo agregado dentro del dominio de Compras o una extensión segura de los modelos existentes.

```text
Frontend SvelteKit
  Solicitudes | Consolidado | RFQ/ofertas | Comparación | Órdenes | Recepción/retaceo
                          │ contratos REST existentes o revisados
API FastAPI
  validación DTO + autorización por acción + ámbito empresa/sucursal
                          │
Application / casos de uso
  consolidar | preparar RFQ | registrar oferta | adjudicar | ordenar | recibir | retacear
                          │ puertos
Dominio de Compras ─── Repositorios/PostgreSQL
        │
        └── puerto/caso de uso explícito hacia Inventario existente para consulta y recepción
```

La estructura concreta de directorios, tablas, estados, endpoints y migraciones se define **después de resolver las decisiones de negocio**, basándose en lo que ya exista. No se crean tablas o módulos solo porque el diagrama conceptual use esos nombres.

### 5.2 Límites de responsabilidad

- **Solicitudes:** conservan la necesidad original y su proceso de decisión.
- **Consolidado:** registra el ciclo de abastecimiento, sus líneas, las fuentes de demanda, adiciones centrales y cambios con autor y motivo.
- **RFQ por proveedor:** fija la lista y cantidad exactas enviadas a ese proveedor.
- **Oferta del proveedor:** registra la respuesta y sus valores por línea, sin reescribir la necesidad original.
- **Adjudicación:** guarda proveedor, producto/línea, cantidad elegida y persona que decidió; permite dividir cantidades y dejar ofertas sin adjudicar.
- **Orden:** se genera desde la adjudicación, agrupando por proveedor y sin exceder lo adjudicado.
- **Recepción:** registra cantidades físicas aceptadas, parciales, dañadas/rechazadas y diferencias respecto de la orden; identifica almacén y ubicación antes de publicar la cantidad aceptada.
- **Retaceo:** referencia la compra/recepción real y asocia los costos aterrizados a las mismas líneas recibidas, sin volver a aumentar unidades. La valoración de inventario se actualiza solo con una regla contable aprobada.
- **Inventario:** conserva su propio dominio de movimientos, saldos y ubicaciones. Compras consulta ese módulo para planificar y lo invoca para registrar la recepción aceptada; nunca mantiene una segunda versión del stock.

### 5.3 Correspondencia con el diagrama Mini ERP

El SVG es un **modelo de datos y relaciones**, no un diagrama del proceso ni de capas de software. Se conserva su cadena y sus claves foráneas; la arquitectura de aplicación sigue siendo el monolito modular Clean/Hexagonal del repositorio.

| Concepto del proceso | Entidades/tablas representadas en el diagrama | Regla de evolución |
|---|---|---|
| Necesidad de sucursal | `purchase_requests` → `purchase_request_details` | Mantener la solicitud original como fuente auditable, con su sucursal, bodega y líneas. |
| Solicitud de precio y respuesta | `purchase_quotations`, `purchase_quotation_details`, `purchase_quotation_requests`, `purchase_quotation_request_details`, gastos | Conservar los vínculos a las solicitudes. Separar claramente RFQ enviada y oferta recibida; extender estados/versiones o agregar entidades solo si las tablas actuales no pueden guardar ambos momentos sin ambigüedad. |
| Compra adjudicada | `purchase_orders`, `purchase_order_details`, gastos y documentos | Reutilizar órdenes existentes y agregar trazabilidad a la adjudicación por línea cuando falte. |
| Documento de compra/recepción | `purchases` → `purchase_details` | Mantener la relación a la orden, producto y cantidad recibida. Aún debe decidirse si se amplía el detalle o se representa cada entrega física con una recepción separada. |
| Costo aterrizado | `retaceos` → `retaceo_details` → `purchase_details` | Conservar `id_purchase_detail` como origen de las asignaciones FOB, flete, gastos, DAI y costo unitario. El retaceo nunca vuelve a crear cantidades. |
| Existencias y Kardex | No se ve una entidad explícita de movimientos de Inventario en el SVG de referencia. El ERP actual sí tiene un módulo de Inventario. | Integrar mediante sus casos de uso/API de aplicación y relacionar cada movimiento con la línea de recepción por referencia de origen e idempotencia. No agregar una tabla de stock dentro de Compras. |

Las tablas candidatas nuevas se limitan a conceptos que el proceso requiere y que el modelo existente no represente: consolidado y procedencia de sus líneas, adjudicación por producto/cantidad y, solo si se requieren varias entregas físicas por orden y el modelo actual no puede expresarlas, cabecera/detalles de recepción. Antes de cada migración se confirma la ausencia de una entidad equivalente y se preservan registros históricos.

### 5.4 Reglas transversales de escalabilidad y seguridad

- Mantener aislamiento por empresa y controles de acceso por sucursal en API y consultas.
- Aplicar permisos por acción; el nombre del rol no concede por sí solo aprobación.
- Auditar cambios de estado, cantidades, adjudicaciones, gastos y recepciones.
- Guardar moneda, unidad y conversiones explícitas para evitar comparaciones incompatibles.
- Usar transacciones para adjudicación/creación de órdenes y proteger de duplicados y reintentos.
- Guardar todas las ofertas recibidas; limitar a tres las ofertas mostradas simultáneamente en una comparación, con posibilidad de elegir otro grupo para comparar.
- Mantener paginación y filtros en servidor al crecer el volumen.
- Introducir cambios de API y base de datos retrocompatibles, con migraciones revisables y preservación de historial.
- Mantener decisiones humanas para aprobación, comparación, adjudicación y registro físico.

## 6. Requisitos y mejoras recogidos en los apuntes

### 6.1 Solicitudes

- **Confirmado:** sucursal, almacén, justificación y al menos una línea son requisitos. La fecha requerida y las notas son opcionales.
- **Confirmado:** una persona puede aprobar su propia solicitud si tiene el permiso de aprobación correspondiente. La acción queda auditada con usuario, fecha, decisión y motivo cuando aplique; no depende del nombre del rol.
- **Confirmado:** filtro por últimos 7, 15, 30 o 90 días y rango personalizado; valor inicial: últimos 30 días. Este filtro de consulta no fija la duración de un consolidado.
- **Confirmado:** paginación con opciones 10, 20, 25, 30 y cantidad personalizada; valor inicial: 20.
- **Confirmado:** mostrar nombre del producto y unidad legibles, además del código cuando ayude a identificarlo; no exponer IDs técnicos como dato principal.

### 6.2 Consolidado

- **Confirmado:** una solicitud de sucursal debe aprobarse antes de ser elegible para consolidación. Una solicitud ya aprobada puede agregarse a un consolidado que siga abierto y aún no haya sido enviado a proveedores.
- **Confirmado:** la decisión puede abarcar la solicitud completa, líneas específicas o una cantidad parcial por línea. Debe persistir el desglose aceptado, reducido o excluido y su motivo; nunca se cambia la cantidad original.
- **Confirmado:** consolidar productos solo cuando producto, unidad y presentación sean compatibles; conservar sucursal, solicitud, fecha y cantidad de origen.
- **Confirmado:** distinguir demanda de sucursales de cantidad adicional que Compras planifica para bodega central. La compra central puede proponerse sin una solicitud de sucursal.
- **Recomendación de flujo:** el consolidado se mantiene editable mientras está abierto. Enviar una RFQ congela una copia por proveedor y versión. Necesidades aprobadas que lleguen después se agregan a otro consolidado o versión sin alterar lo que ya se envió.
- **Confirmado:** mostrar filtros de 7, 15, 30 y 90 días y rango personalizado; 30 días por defecto. El comprador selecciona explícitamente cuándo cerrar el lote de consolidación; no se infiere el cierre solo por el filtro.
- **Recomendación de cálculo por almacén destino:** `compra sugerida = max(0, demanda de sucursales aprobada + objetivo central − (existencia utilizable − reservas) − entradas confirmadas en tránsito no comprometidas)`. Solo se incluyen líneas aceptadas; no contar borradores de órdenes como suministro ni descontar dos veces reservas. La existencia de otras sucursales solo cuenta si hay una transferencia aprobada hacia el almacén destino. No usar solicitudes como ventas/consumo real ni activar stock de seguridad sin política/datos. Mostrar cada componente para revisión humana; no generar compras automáticamente.

### 6.3 Solicitudes a proveedores y ofertas

- **Confirmado:** preparar solicitudes de precio por proveedor, permitiendo pedir la misma línea a varios proveedores; generar un documento PDF por proveedor y conservar el archivo original de la respuesta.
- **Confirmado:** registrar cantidad solicitada, ofrecida y disponible, precio unitario, moneda, descuentos, impuestos declarados, condiciones, vigencia, plazo/fecha de entrega y gastos estimados informados por proveedor. Mantener respuestas parciales o líneas no ofrecidas sin borrar la solicitud enviada.
- **Recomendación:** comparar importes en la misma moneda. Si son distintas, no declarar un ganador hasta aplicar una fuente y fecha de tipo de cambio acordadas; mostrar moneda original y conversión por separado.
- **Confirmado:** comparar por producto/línea y mostrar también resumen por grupo/proveedor (total, moneda, entrega, vigencia y condiciones). Guardar todas las ofertas recibidas; cada matriz incluye como máximo tres proveedores, seleccionados por Compras. Se puede comparar otro conjunto en una matriz aparte.
- **Confirmado:** generar un reporte interno PDF/Excel de las ofertas y decisiones comparadas. El envío automático por correo no forma parte del alcance hasta definir integración y remitente.
- **Pendiente:** criterios y datos para evaluar/rankear proveedores. No diseñar puntuaciones ni selección automática antes de que Compras defina una política.

### 6.4 Adjudicación y órdenes

- **Confirmado:** adjudicación por decisión humana, por solicitud y por línea/cantidad, completa o parcial, considerando precio, moneda, disponibilidad, entrega, condiciones y descuentos. Una línea puede repartirse entre proveedores.
- **Confirmado:** emitir una orden por proveedor adjudicado y solo por cantidades adjudicadas; conservar alternativas no elegidas y la justificación de la decisión.
- **Recomendación de responsabilidad:** los permisos determinan quién consolida, registra ofertas, adjudica, aprueba y envía; no se codifica un cargo fijo. Mantener aprobar OC y enviar OC como acciones separadas cuando la política lo requiera.
- **Regla:** una RFQ enviada pide precio; no es una orden autorizada ni un compromiso de compra.

### 6.5 Gastos, recepción y retaceo

- **Confirmado:** separar estimados de la oferta de costos reales documentados. Si se requiere una estimación presupuestaria interna antes de recibir ofertas, guardarla con etiqueta y fuente distintas; no presentarla como costo ofrecido por proveedor.
- **Recomendación de captura:** el proveedor informa cargos estimados en su oferta; Compras registra cargos reales respaldados por factura/documento en la orden o recepción. Flete internacional, cargos aduaneros/DAI y otros gastos directamente atribuibles se proponen como componentes de costo aterrizado. IVA se conserva separado hasta que Contabilidad defina su tratamiento. Mano de obra y gastos internos posteriores a la llegada se registran aparte salvo política contable aprobada.
- **Pendiente técnico/contable:** revisar `is_costable`, documentos y regla actual antes de reutilizarlos. Finanzas/Contabilidad confirma qué costos capitalizan, la distribución, moneda/tipo de cambio y el momento de cierre; no se infieren tasas DAI ni tratamiento fiscal.
- **Recomendación de disponibilidad:** recibir en una ubicación de recepción/inspección no disponible; contar y verificar cantidades aceptadas, dañadas o rechazadas; después ubicar la cantidad aceptada en una ubicación válida de Inventario. La disponibilidad física depende de recepción verificada y acomodo, no de cerrar el retaceo. Mantener el costo pendiente hasta aprobación contable sin bloquear disponibilidad física, salvo política expresa.
- **Confirmado como trazabilidad requerida:** fecha, factura, proveedor, orden, almacén, cantidades ordenadas/recibidas/aceptadas/rechazadas y diferencias.
- **Pendiente operativo:** confirmar si el sistema representa separadamente recepción, inspección y acomodo y cuál movimiento de Inventario corresponde a cada paso; usar el contrato existente, sin duplicar saldos.

### 6.6 Responsabilidades funcionales y acceso

Los nombres de rol no conceden acceso por sí solos. **Confirmado:** las acciones corresponden a los permisos asignados y el backend valida el alcance de empresa/sucursal. La matriz describe responsabilidades funcionales, no una asignación ya aplicada.

| Perfil funcional propuesto | Puede realizar | Separación que se debe conservar |
|---|---|---|
| Solicitante de sucursal | Crear/editar su borrador, enviar y consultar solicitudes de su ámbito. | Puede aprobar su propia solicitud solo si también tiene permiso de aprobación; la decisión queda en bitácora. |
| Aprobador de necesidad | Aprobar, rechazar o aceptar parcialmente solicitudes dentro del ámbito autorizado. | “Aprobada” no significa “ordenada” ni “recibida”; guardar decisión y motivo. |
| Compras | Ver demanda aprobada, consolidar, consultar abastecimiento, preparar RFQ, registrar ofertas, comparar y proponer adjudicación. | Precios/documentos de proveedor se limitan a usuarios autorizados. Adjudicar sigue siendo una decisión humana. |
| Aprobador de orden | Aprobar o rechazar OC según permisos y eventual política de umbrales. | Montos límite y fuente presupuestaria no se fijan hasta que Finanzas los defina. |
| Bodega/recepción | Consultar líneas esperadas, contar, inspeccionar, registrar diferencias, aceptar/rechazar y ubicar mercancía. | Solo la cantidad aceptada y ubicada se propone como disponible; conservar evidencia y trazabilidad. |
| Costeo/retaceo | Capturar costos documentados, calcular y verificar retaceo conforme a política aprobada. | No cambiar cantidades de inventario; tasas y clasificación fiscal vienen de reglas aprobadas. |

**Aprobación de inversión (recomendación, no regla configurada):** puede significar comprobar autoridad/presupuesto antes de comprometer el monto y escalar si supera un límite. Los flujos ERP permiten condicionar pasos de aprobación por monto y revisar documentos completos o líneas; son patrones configurables, no una regla universal para este proyecto ([Microsoft Learn: flujo de solicitudes de compra](https://learn.microsoft.com/en-us/dynamics365/supply-chain/procurement/purchase-requisitions-workflow), [Microsoft Learn: aprobaciones condicionales](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/fin-ops/organization-administration/configure-approval-step-workflow)). Para la primera ruta se recomienda mostrar total y moneda de la OC y exigir aprobación por permiso. No fijar un umbral hasta definir monto, moneda, período, fuente presupuestaria y aprobadores.

**Auditoría del Bloque 1:** el informe registra los permisos técnicos revisados y las brechas de ámbito en cotizaciones/órdenes. Los permisos nuevos de consolidar, comparar y adjudicar se mapearán a acciones concretas al diseñar cada bloque; esta documentación no modifica RBAC.

## 7. Fases de trabajo recomendadas

### Bloque 0 — Planificación funcional y arquitectónica (actualizado)

Consolidar los siete PDF, incorporar decisiones del responsable, separar recomendaciones y cuestiones aún abiertas, definir el flujo objetivo, límites de alcance, correspondencia con el ERD y arquitectura candidata. Esta versión es el entregable documental actualizado del bloque.

**Cierre:** se incorporaron las respuestas recibidas el 30 de septiembre de 2026. Las recomendaciones de flujo se usan como criterio de diseño provisional; contratos técnicos y tratamiento contable/fiscal siguen sujetos a verificación con Inventario y Finanzas antes de implementarlos.

### Bloque 1 — Auditoría de estado actual (realizada; criterios funcionales actualizados)

Se realizó una revisión de solo lectura del repositorio: rama/commit, cambios locales, modelos, casos de uso, API, permisos, pantallas y documentación. No se ejecutaron pruebas ni se consultó la base de datos activa. Los hallazgos técnicos están en docs/auditoria-estado-actual-flujo-compras.md. Esta actualización añade criterios de negocio posteriores; no vuelve a ejecutar la auditoría de código ni cambia los hechos observados.

**Entregable:** matriz de brechas, flujo actual, riesgos de alcance por sucursal y arquitectura recomendada en el informe de auditoría indicado arriba.

### Bloque 2 — Protección de la base y estabilización del flujo actual

Registrar el estado de Git, separar el trabajo nuevo en una rama y respaldar la base de desarrollo. Revisar los cambios locales sin descartarlos. Cerrar primero regresiones conocidas de permisos/alcance por sucursal, navegación a detalles y lectura de proveedor. No cambiar en un mismo paso todos los cinco módulos ni alterar producción.

**Salida verificable:** punto de recuperación claro; cambios existentes preservados; ruta actual probada/documentada; cualquier brecha de permisos o sucursal reproducible y acotada.

### Bloque 3 — Contrato con Inventario y primera ruta vertical

Con una OC existente y una sola línea, completar el recorrido verificable de recepción: conteo físico, cantidad aceptada/rechazada, condición y ubicación; verificación autorizada; movimiento idempotente en el Inventario existente; y trazabilidad desde el movimiento hasta la línea de compra. Consultar también los saldos necesarios para planificar. Definir cuándo queda disponible, cómo se reintenta sin duplicar y cómo se corrige/reversa. No reconstruir existencias ni Kardex.

Antes de publicar movimiento se confirma el mapeo entre producto/unidad de Compras e ítem/unidad de Inventario. Si los identificadores o unidades no son equivalentes, usar una relación y conversión explícitas; nunca asumir que dos IDs numéricamente iguales son el mismo artículo.

**Salida verificable:** una recepción parcial aceptada actualiza Inventario una vez; repetir la confirmación no duplica saldo; la cantidad no aceptada no queda disponible; el movimiento conserva referencia al detalle de compra/recepción.

### Bloque 4 — Retaceo ligado a la recepción

Conservar `retaceos` y `retaceo_details` ligados a `purchase_details`. Validar una regla de costos con el responsable contable y asociar el costo aterrizado final a la línea/lote recibido sin cambiar cantidades. DAI e IVA continúan siendo datos documentados según reglas aprobadas, no tasas inferidas por categoría.

**Salida verificable:** cada importe distribuido se explica desde los costos reales y cantidades recibidas; cerrar o recalcular el retaceo no crea movimiento de cantidad.

### Bloque 5 — Consolidado de demanda

Agregar solo el modelo necesario para agrupar solicitudes por período, producto y unidad compatible, conservando sucursal, solicitud y cantidad de origen. Consultar stock/reservas/tránsito mediante el contrato de Inventario. Separar la demanda de sucursales de la cantidad planificada para bodega central; registrar reducciones, exclusiones y agregados de Compras con motivo y usuario.

**Salida verificable:** una línea consolidada muestra la suma y el desglose de origen; cambios de Compras no sobrescriben solicitudes originales; la demanda central queda identificada separadamente.

### Bloque 6 — RFQ por proveedor y oferta recibida

Usar el modelo del diagrama como base y separar los dos momentos del negocio: lo enviado al proveedor y su respuesta. Guardar copia/versionado de cantidades enviadas y registrar respuestas parciales, condiciones, documentos y fecha. Agregar tablas solo si el esquema existente no puede distinguir ambos estados ni preservar la versión enviada. PDF y correo se incorporan con alcance aprobado.

**Salida verificable:** cada respuesta indica exactamente a qué lista y versión responde; puede haber varias respuestas para el mismo consolidado y se conserva lo enviado aunque cambie después.

### Bloque 7 — Comparación y adjudicación por línea

Comparar precio, moneda normalizada, descuento, impuesto declarado, cargos y entrega por producto. Persistir decisión humana por proveedor/producto/cantidad, con usuario y motivo; permitir dividir una línea entre proveedores. No crear una orden automáticamente por recibir una oferta.

**Salida verificable:** no se adjudica más que la cantidad elegible/ofrecida; las ofertas no elegidas permanecen consultables y las decisiones tienen autor y motivo.

### Bloque 8 — Órdenes y ruta consolidada completa

Generar órdenes por proveedor desde las cantidades adjudicadas y reutilizar `purchase_orders`/`purchase_order_details`. Añadir referencia a la adjudicación para mantener trazabilidad. Conectar esta ruta nueva con los Bloques 3 y 4 ya verificados, sin volver a implementar recepción, movimientos ni costos.

**Salida verificable:** cada OC contiene solo las líneas y cantidades adjudicadas a su proveedor; la suma de órdenes no excede la adjudicación y cada línea puede rastrearse hasta su solicitud fuente.

### Bloque 9 — Bandeja de trabajo y mejoras posteriores

Colocar la cola operativa dentro de Cotizaciones de compra o del flujo actual de Compras, con conteos calculados en backend, alcance por empresa/sucursal y enlaces directos a cada pendiente. La interfaz se construye sobre contratos ya probados; no crear dashboard de Ventas ni un módulo departamental nuevo. Después se pueden sumar historial comparativo de precios, PDF/reporte y analítica cuando existan datos confiables. La revisión del compañero en el período 3 valida el trabajo; no detiene los bloques anteriores.

**Salida verificable:** tarjetas, filtros y totales respetan permisos y sucursal; cada acción lleva al documento correcto; la interfaz presenta estados vacíos, carga y error sin ocultar fallas de API.

## 8. Definiciones tomadas y decisiones aún abiertas

### Definiciones confirmadas por el responsable del proyecto

- La fecha requerida es opcional; solicitud con sucursal, almacén, justificación y al menos una línea.
- Se permite autoaprobar si el usuario posee el permiso correspondiente.
- Filtros: 7, 15, 30 y 90 días más rango personalizado; valor inicial 30 días. Paginación inicial 20, con opciones 10, 20, 25, 30 y personalizada.
- Una solicitud debe aprobarse para ser elegible; la aceptación puede ser total, por línea o parcial por cantidad. Se pueden agregar solicitudes aprobadas a un consolidado abierto antes del envío de RFQ.
- Compras puede añadir demanda para bodega central sin solicitud de sucursal. Mantener separados ambos orígenes.
- Guardar todas las ofertas; comparar hasta tres proveedores por matriz, mostrando resumen de grupo y detalle por producto/línea. La decisión y adjudicación son humanas y pueden dividirse.
- La RFQ y la OC son documentos/estados distintos. PDF por proveedor, archivo original de la oferta y reporte comparativo PDF/Excel están incluidos en el alcance aprobado; no se presupone envío automático por correo.
- El nombre de rol no asigna privilegios: las acciones dependen de permisos y alcance verificado en backend.

### Recomendaciones para usar como base del diseño

- Los estados que ve la sucursal deben separar aprobación de necesidad, inclusión en consolidado, solicitud de precio, adjudicación, orden, recepción y disponibilidad. Propuesta: `Borrador → En aprobación → Aprobada / Parcialmente aprobada / Rechazada → En consolidado → En cotización → Adjudicada total/parcial → Ordenada → Recibida parcial/total → Ubicada/Disponible`. Mostrar cada cambio en una cronología y no llamar “comprada” a una solicitud que solo fue incluida en una RFQ.
- El filtro de fechas es una consulta; el comprador define el cierre del consolidado. Al enviar RFQ se congela la versión enviada; demandas tardías se agregan a otro lote o versión.
- Para la necesidad central, usar existencias utilizables, restar reservas una sola vez y restar solo entradas confirmadas que no estén comprometidas a otra necesidad; añadir demanda aprobada de sucursales y objetivo explícito de bodega central. Primero validar qué significan esos saldos en Inventory. No activar stock de seguridad ni pronóstico hasta tener datos y política confiables.
- Comparar por línea y presentar además totales por proveedor/consolidado. No convertir monedas sin tasa, fecha y fuente acordadas.
- La disponibilidad física se publica después de contar, verificar aceptación y ubicar la mercancía. El retaceo/costo puede quedar pendiente en paralelo, salvo que Contabilidad defina que el costo final debe bloquear disponibilidad.
- Mantener SKU común como identidad del producto; usar lote para trazabilidad/fecha de vencimiento cuando aplique y número de serie por unidad solo para artículos serializados. La simbología Code 128/QR queda configurable por Bodega.
- Modelar compra centralizada y compra local como variantes/destinos del mismo flujo compartido, sin duplicar solicitudes, órdenes ni movimientos. El alcance actual prioriza consolidación y abastecimiento centralizado.

### Pendientes que sí bloquean reglas detalladas o cálculos

1. Contrato de Inventory: definiciones exactas de disponible, reservado, en inspección, en tránsito y no asignado; consulta por producto, unidad y almacén; idempotencia y reversa del movimiento de recepción.
2. Finanzas/Contabilidad: moneda/tipo de cambio, qué cargos son capitalizables, distribución del retaceo, tratamiento del IVA, documentación aceptada y momento de costo final. No fijar tasas DAI ni política fiscal desde este plan.
3. Aprobación de inversión: fuente del presupuesto, moneda, período, límites y personas/permisos de escalamiento. Hasta entonces, no hay umbral monetario automatizado.
4. Política de proveedor: campos obligatorios finales, criterios de evaluación y si se califica al proveedor además de comparar ofertas.
5. Operación de almacén: ubicaciones de recepción/inspección y momento exacto de putaway que hace disponible la cantidad aceptada; revisar estados y movimientos que ya soporta el módulo.
6. Modalidad local: reglas particulares de una compra directa por sucursal que difieran de la compra centralizada; se documentarán como variante antes de ampliar el alcance.

Estos pendientes no impiden preservar solicitudes originales, diseñar trazabilidad, ni continuar con la revisión técnica. Sí impiden automatizar cálculo de necesidad, límites presupuestarios y valoración contable sin contratos aprobados.

## 9. Límites explícitos del encargo

### Se planifica dentro del flujo de compras

Las cinco capacidades existentes (solicitudes, cotizaciones, órdenes, compras/recepciones y retaceo) y el diseño de la consolidación como paso de abastecimiento, sujeto a confirmación con el ingeniero y las áreas responsables después de revisar la auditoría. La comparación y adjudicación humana son parte de los resultados de aprendizaje anotados.

### No construir en esta etapa

- Departamentos o dashboards organizativos nuevos de Compras o Ventas; su dueño/implementador se debe coordinar con los compañeros.
- Un módulo nuevo o reconstrucción de Inventario, almacenes, categorías, sucursales o traslados. La integración con las capacidades existentes sí está dentro del alcance.
- Seguimiento completo de contenedores, barcos y rutas, etiquetado avanzado y lectura con escáner. El conteo/inspección básico y el registro del stock aceptado en Inventario sí son prioritarios; los traslados se atenderán mediante la capacidad existente, sin reconstruirla.
- Analítica predictiva, compras automáticas o selección automática de proveedor.
- Evaluación/ranking de proveedores sin criterios aprobados.
- Envío automático por correo o límites rígidos de proveedores sin definición del negocio.
- Cambios fiscales, porcentajes estimados de DAI o reglas nuevas de costeo no aprobadas.

El proyecto conserva el contrato entre Compras e Inventario para que futuras ampliaciones se conecten sin rehacer el flujo. La propiedad y ejecución de esta integración corresponden al responsable actual del proyecto; la revisión del compañero se hará en el período 3.

## 10. Riesgos y controles del plan

| Riesgo | Control antes de implementar |
|---|---|
| Confundir una solicitud aprobada con una compra o despacho | Definir estados y eventos por separado, visibles también a la sucursal. |
| Sobrecomprar o duplicar pedidos | Consultar órdenes abiertas/en tránsito y conservar demanda sin sumarla dos veces. |
| Perder procedencia al editar un consolidado | Guardar cantidades fuente y cambios de Compras con autor, fecha y motivo. |
| Enviar a proveedores una versión ambigua | Congelar la lista y cantidad exactas por proveedor y versión. |
| Sumarse ofertas alternativas como si fueran una compra | Separar respuesta, adjudicación y OC; sumar solo cantidades adjudicadas. |
| Revelar ofertas de un proveedor a otro | Aislar cotizaciones por proveedor y limitar acceso por permisos. |
| Registrar stock antes de completar trabajo físico | Exigir conteo, inspección, cantidad aceptada y ubicación; registrar el movimiento idempotente y definir el estado de disponibilidad. |
| Cambiar costos o impuestos con reglas no confirmadas | Obtener aprobación contable/logística y probar el cálculo contra casos acordados. |
| Afectar cambios locales de otros compañeros | En la auditoría registrar rama, commit y árbol de trabajo; preservar todo cambio sin responsable identificado. |
| Hacer una arquitectura sobredimensionada | Mantener monolito modular y crear solo los límites justificados por trazabilidad/propiedad del dato. |

## 11. Criterio de cierre de la planificación

El Bloque 0 está actualizado y la revisión inicial del Bloque 1 está documentada. Antes de iniciar implementación:

- Las áreas distinguen solicitud, consolidado, RFQ enviada, oferta recibida, adjudicación, orden, recepción y retaceo.
- Los pendientes de la sección 8 tienen responsables para responderlos; los de Inventory/Finanzas quedan explícitamente fuera de cualquier automatización hasta acordar sus contratos.
- La consolidación y la integración mínima con Inventario quedan asignadas al responsable actual del proyecto; se confirma el contrato y los puntos operativos antes de implementar cada bloque.
- Se acuerda qué significa stock disponible/reservado/en tránsito y quién realiza conteo/verificación. La revisión del compañero en el período 3 valida el trabajo, pero no es bloqueo de alcance.
- El alcance por módulos y fuera de alcance es aceptado por el usuario y el responsable técnico.

**Siguiente etapa:** la matriz de decisiones y brechas del Bloque 1 quedó incorporada al informe de auditoría como diagnóstico de solo lectura de la rama/commit registrados. La fotografía técnica no incluye base activa, ejecución del sistema ni pruebas. Cuando el usuario decida iniciar código, empezar por el Bloque 2: preservar los cambios locales y preparar una ruta segura; luego verificar el contrato recepción↔Inventario antes de ampliar consolidación, ofertas y adjudicación. No se reconstruye Inventario.

## 12. Documentación interna de referencia

- `docs/flujo-compras-inventario-retaceo.md`
- `docs/plan-seguro-compras-inventario.md`
- `docs/architecture.md`
- `docs/module-creation-guide.md`
- `docs/database-schema.md`
- `docs/rbac-model.md`
- `docs/product-module-future-debt.txt`
- `.agents/AGENTS.md`

Estas referencias describen la arquitectura y el estado previamente documentado. El informe de auditoría registra qué comportamiento se contrastó con el código en la rama y commit indicados; las decisiones de negocio siguen pendientes.

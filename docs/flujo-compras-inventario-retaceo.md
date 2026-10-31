# Guía funcional: compras, recepción, retaceo e inventario

**Documento preliminar para alinear al equipo y capacitar usuarios**

Fecha de revisión: 26 de septiembre de 2026. Esta guía describe el flujo que se encontró en el repositorio del ERP y separa el comportamiento implementado de las propuestas todavía pendientes de decisión.

> **Lectura importante.** No se propone rehacer todo el ERP. El flujo de compras existe. Inventario también tiene backend y algunas pantallas; lo que falta conectar es, principalmente, la recepción de compras con los movimientos de stock y el efecto del retaceo sobre el costo inventariable.

**Flujo de extremo a extremo**

Necesidad de sucursal -> Solicitud de compra SCR -> Aprobación -> Solicitud de precio COT -> Respuesta del proveedor -> Evaluación y selección -> Orden de compra OC -> Recepción física -> Retaceo -> Inventario y Kardex

## Tres términos para no confundir

| Término | Significado práctico |
|---|---|
| Solicitud de compra SCR | Necesidad interna de una sucursal o área. Todavía no es una compra ni aumenta el stock. |
| Solicitud de cotización COT | Pedido de precio preparado para un proveedor. En el sistema, el mismo registro COT recibe después la respuesta del proveedor. |
| Oferta del proveedor | Precio, moneda, impuestos, entrega y condiciones que el equipo registra cuando el proveedor responde al COT. |

> **Estado actual.** La respuesta del proveedor se registra manualmente en la pantalla de la cotización. En el flujo revisado no aparece una bandeja que lea correos ni un campo para adjuntar el PDF de la oferta.

## 1. Solicitud interna y aprobación

**La solicitud expresa qué necesita la operación y para cuándo.**

El solicitante registra sucursal, almacén, fecha requerida, justificación y líneas de producto con unidad y cantidad. Al enviar el borrador, pasa a la cola de aprobación. Aprobar autoriza a continuar con el sondeo a proveedores; no crea una orden de compra ni registra existencias.

| Estado actual | Qué significa | Siguiente paso |
|---|---|---|
| Borrador (draft) | Editable por quien gestiona la solicitud. | Completar y enviar a aprobación, o cancelar. |
| Enviada (submitted) | Pendiente de revisión y decisión. | Aprobar o rechazar con permiso de aprobación. |
| Aprobada (approved) | Autorizada para iniciar cotizaciones. | Crear uno o más COT para proveedores. |
| Rechazada (rejected) | No autorizada; estado terminal en el flujo actual. | Aclarar motivo y crear una nueva solicitud si corresponde. |
| Parcialmente cotizada (partially_quoted) | Hay respuestas para parte de las cantidades solicitadas. | Continuar con ofertas o evaluar lo recibido. |
| Cotizada (quoted) | La cobertura de cotización registrada alcanza las cantidades solicitadas. | Comparar ofertas y preparar una orden. |
| Parcialmente ordenada (partially_ordered) | Solo parte de lo cotizado se convirtió en orden. | Completar la necesidad o cerrar según la operación. |
| Completada (completed) | La necesidad llegó al cierre de compras. | Consulta histórica. |
| Cancelada (cancelled) | La solicitud se anuló antes de completar el flujo. | Consulta histórica. |

> **Control de aprobación.** La decisión debe seguir protegida por purchase_requests:approve. La tarjeta o el dashboard facilita encontrar y revisar solicitudes, pero no debe aprobar por sí solo. Conviene confirmar si la persona solicitante puede aprobar su propia solicitud; esa regla no se observa aplicada en el flujo actual.

En el listado actual existe un filtro por estado, pero no una cola con conteo ni acciones de aprobación en la fila. La aprobación ocurre desde el detalle. Una mejora útil es mostrar una tarjeta de pendientes y un acceso directo a revisar cada SCR.

## 2. Cotizaciones a proveedores

**El COT une la solicitud enviada y la respuesta registrada.**

El comprador selecciona proveedor y moneda, agrega notas, vincula solicitudes aprobadas o con cotizaciones previas y marca las líneas y cantidades que pedirá cotizar. El formulario actual permite solicitudes aprobadas, parcialmente cotizadas y cotizadas. El borrador se crea para un proveedor. Para comparar varios proveedores, normalmente se prepara un COT por proveedor y se comparan sus respuestas para el mismo SCR.

| Estado COT | Qué significa | Acción siguiente |
|---|---|---|
| Borrador (draft) | Se armó el pedido de precio; aún no se ha marcado como enviado. | Revisar datos y enviar al proveedor. |
| Solicitada (requested) | La solicitud de precio se envió; se espera respuesta. | Registrar la oferta recibida o marcar vencimiento/cancelación. |
| Recibida (received) | El equipo capturó manualmente los precios y condiciones. | Evaluar la oferta. |
| En evaluación (under_evaluation) | Se está comparando la respuesta. | Seleccionar, rechazar o marcar vencida. |
| Seleccionada (selected) | Oferta elegida para generar una orden. | Crear la orden de compra. |
| Rechazada (rejected) | Oferta no elegida. | Consulta histórica. |
| Vencida (expired) | La vigencia terminó sin selección. | Solicitar una oferta vigente si aplica. |
| Cancelada (cancelled) | Se canceló el pedido al proveedor. | Consulta histórica. |

> **Por qué no ves el SCR en la lista COT.** La lista de Cotizaciones muestra registros COT, no solicitudes SCR. Una solicitud aprobada aparece en el selector de Nueva cotización hasta que se crea el COT. La lista tampoco muestra hoy el código SCR asociado, por lo que conviene agregarlo como referencia visible.

El formulario conserva proveedor, moneda, notas y líneas. Un acceso desde la tarjeta de solicitudes aprobadas podría abrir ese mismo formulario con el SCR ya seleccionado, evitando buscarlo de nuevo sin crear un flujo paralelo.

## 3. Orden de compra y recepción

**La orden compromete una compra; la recepción documenta lo que llegó.**

La orden se prepara a partir de una oferta seleccionada. Su aprobación y envío al proveedor son pasos distintos. La recepción solo puede originarse desde una orden enviada o parcialmente recibida, y permite registrar entregas parciales sin superar lo pendiente.

| Estado OC | Significado operativo |
|---|---|
| Borrador (draft) | Orden editable. |
| Pendiente de aprobación (pending_approval) | En revisión de autorización. |
| Aprobada (approved) | Autorizada para enviar. |
| Enviada (sent) | Transmitida al proveedor; se puede recibir. |
| Parcialmente recibida (partially_received) | Llegó parte de lo ordenado; queda cantidad pendiente. |
| Recibida (received) | Se recibió toda la cantidad de la orden. |
| Cerrada (closed) | Orden finalizada. |
| Cancelada (cancelled) | Orden anulada. |

| Estado de recepción | Significado operativo |
|---|---|
| Borrador (draft) | Preparar cantidades reales recibidas por línea. |
| Recibida (received) | Recepción confirmada; falta verificación. |
| Verificada (verified) | La recepción pasó revisión. |
| Cerrada (closed) | Recepción finalizada. |
| Cancelada (cancelled) | Se anuló el borrador. |

> **No confundir.** La cantidad de la orden es una cantidad esperada. La cantidad de una recepción es lo que físicamente llegó. Ninguna solicitud aprobada, cotización u orden debería sumarse al stock antes de una recepción física confirmada.

## 4. Retaceo e inventario

**El retaceo distribuye costo; Inventario controla cantidades y movimientos.**

El retaceo se crea desde una compra o recepción elegible, no directamente desde una orden. Distribuye flete, gastos y DAI entre líneas proporcionalmente al FOB. El IVA de importación se conserva por separado y no forma parte del costo total calculado por el retaceo.

| Estado del retaceo | Significado |
|---|---|
| Borrador (draft) | Captura editable de costos de importación. |
| Calculado (calculated) | Distribución calculada y congelada para revisar. |
| Verificado (verified) | Cálculo revisado. |
| Cerrado (closed) | Retaceo finalizado. |
| Cancelado (cancelled) | Retaceo anulado antes del cierre. |

### Qué hay hoy en Inventario

En este repositorio Inventario no está vacío: hay backend para identidad de artículos, presentaciones, movimientos, saldos, consultas de stock, unidades logísticas, reservas y capacidad. También hay componentes y algunas pantallas frontend. Sin embargo, no aparece completa la pantalla operativa de movimientos conectada a compras, y el código revisado no enlaza automáticamente la recepción con un movimiento de inventario.

> **Brecha confirmada.** La documentación técnica indica que el retaceo actual no genera movimientos de Inventario ni Kardex. Por tanto, el enlace pendiente es integración y experiencia operativa, no reconstruir todo el módulo desde cero.

- Stock: cantidad física registrada por artículo, almacén/ubicación y estado. No es la cantidad pedida ni la cantidad de una orden.
- Capacidad: espacio físico disponible por peso o volumen. No equivale al stock que existe.
- Recepción: evidencia de llegada física y cantidades aceptadas.
- Retaceo: cálculo del costo importado por línea; no debe sumar unidades otra vez.

## 5. Recomendación de UX, permisos y plan seguro

**Cambios graduales para simplificar el trabajo sin rehacer el proceso completo.**

### Tarjetas útiles por etapa

- Solicitudes de compra: pendientes de aprobación y aprobadas listas para pedir precio.
- Cotizaciones: COT pendientes de respuesta del proveedor y ofertas recibidas por evaluar.
- Órdenes: pendientes de aprobación y parcialmente recibidas.
- Compras e Inventario: recepciones por verificar y artículos recibidos pendientes de ubicación.

Las tarjetas deben mostrar conteos y llevar a una lista filtrada. Desde SCR aprobado se puede abrir el formulario COT existente con esa solicitud preseleccionada. La lista COT debe mostrar sus SCR relacionados. Mantener aprobación y selección protegidas por permiso y revisar el documento antes de cualquier acción.

| Acción | Permiso que gobierna el acceso |
|---|---|
| Crear, ver y enviar SCR | purchase_requests:read + purchase_requests:manage |
| Revisar, aprobar o rechazar SCR | purchase_requests:read + purchase_requests:approve |
| Crear COT desde una solicitud | purchase_requests:read + purchase_quotations:manage + suppliers:read |
| Registrar respuesta y evaluar COT | purchase_quotations:read + purchase_quotations:manage |
| Seleccionar oferta ganadora | purchase_quotations:read + purchase_quotations:select |
| Crear o editar OC | purchase_orders:read + purchase_orders:manage |
| Aprobar y enviar OC | purchase_orders:approve + purchase_orders:send |
| Preparar, recibir y verificar mercancía | purchases:read + purchases:manage + purchases:receive + purchases:verify |
| Crear, calcular y verificar retaceo | retaceos:read + retaceos:manage + retaceos:calculate + retaceos:verify |
| Consultar y registrar movimientos de stock | inventory:read + inventory:receive o inventory:move |

> **Los cargos no conceden permisos por el nombre.** Super Admin recibe todos los permisos en el catálogo base. El rol base ADMINISTRADOR no incluye automáticamente purchase_requests:approve; ese permiso debe asignarse al rol que la empresa defina como aprobador. Hallazgo técnico: la lista de solicitudes y el formulario COT no envían la sucursal seleccionada a la API; un usuario limitado a sucursales podría recibir 403. Corregir y validar ese alcance antes de confiar en los conteos del dashboard.

### Orden recomendado de trabajo

1. Acordar este vocabulario, quién aprueba por sucursal y qué significa una respuesta recibida del proveedor.
2. Proteger los cambios locales y trabajar aislados; corregir primero el alcance de sucursal y confirmar la matriz de permisos.
3. Implementar un primer dashboard de solo lectura con conteos, filtros y enlaces a los formularios existentes.
4. Diseñar por separado la integración de recepción verificada -> movimiento de entrada de stock y retaceo cerrado -> actualización del costo, con trazabilidad e idempotencia.
5. Probar recepción parcial, reintentos, permisos y sucursales antes de habilitar el nuevo flujo al personal.

> **Decisión de negocio pendiente.** Propuesta para validar: aumentar cantidades de stock una sola vez al verificar la recepción física; al cerrar el retaceo, actualizar el costo unitario aterrizado sin volver a sumar cantidades. También debe decidirse si el stock queda disponible antes de cerrar el retaceo o en un estado de costo pendiente.

Base revisada: docs/api.md, docs/database-schema.md, estados de solicitud, cotización, orden, compra y retaceo del dominio, y router backend de Inventario. El alcance funcional aquí descrito requiere validación del equipo antes de convertirse en reglas definitivas.

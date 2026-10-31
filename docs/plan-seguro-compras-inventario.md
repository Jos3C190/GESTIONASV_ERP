# Plan seguro: cola de compras e integración con Inventario

**Fecha:** 26 de septiembre de 2026  
**Estado:** propuesta técnica preliminar del 26 de septiembre. Su decisión de dejar la integración automática para más adelante fue reemplazada el 30 de septiembre por `docs/planificacion-bloque-0-alcance-y-hoja-de-ruta-compras.md`: la consulta de Inventario para consolidar y el registro de recepción física aceptada son prioridad actual. Este archivo se conserva como referencia técnica; sus reglas de idempotencia, trazabilidad y seguridad siguen siendo útiles, pero su orden de trabajo y su aplazamiento no son la hoja de ruta vigente.

## Objetivo

Ayudar al personal autorizado a encontrar el siguiente paso de compra y conservar una referencia técnica para conectar las recepciones con el Inventario existente. La responsabilidad de avanzar esta integración corresponde al responsable actual del proyecto; el compañero podrá revisarla en el período 3.

La primera iteración no cambia cantidades de stock, no calcula impuestos y no agrega permisos. Las tarjetas consultan conteos con las API existentes, muestran únicamente los pasos que el usuario puede consultar y ejecutar, y llevan a los formularios actuales.

## Alcance de la propuesta preliminar de tablero

- Dashboard con conteos de solicitudes pendientes de aprobación, solicitudes aprobadas para cotizar, ofertas recibidas, cotizaciones en evaluación y recepciones por verificar.
- Cada tarjeta abre el módulo existente con el filtro de estado correspondiente.
- Las solicitudes y recepciones se consultan con la sucursal operativa seleccionada.
- La cotización se puede iniciar desde el detalle de una solicitud elegible; el formulario abre con esa solicitud preseleccionada.
- El formulario de retaceo incluye enlaces a la consulta SAC/DAI y a la guía de clasificación de la Dirección General de Aduanas.
- La tarjeta de almacenes abre la vista existente de almacenes y capacidad. Esa vista no se presenta como una pantalla completa de movimientos o Kardex.
- “Oferta recibida” significa que el proveedor respondió y alguien registró esa respuesta en el formulario actual. Esta entrega no integra correo, carga automatizada de ofertas PDF ni portal de proveedores.

## Hallazgos de arquitectura que condicionan la integración

1. **Inventario ya tiene un modelo de movimientos.** El dominio incluye entradas (`receipt`), traslados, salidas, ajustes y reversas. El comando de movimiento almacena una clave de idempotencia y una referencia de origen, así que la integración puede registrar el vínculo con la recepción de compra y proteger reintentos.
2. **La recepción de compra todavía no publica un movimiento.** `receive_purchase` y `verify_purchase` actualizan el estado de la compra. No invocan el caso de uso de Inventario. El cierre del retaceo también cambia su estado sin actualizar cantidades o costos en Inventario.
3. **La recepción tiene almacén, pero no ubicación por línea.** Antes de registrar stock hace falta indicar a qué ubicación física llega cada línea. La compra tampoco captura en esta pantalla evidencia fotográfica o cantidades dañadas/rechazadas por línea.
4. **Las cantidades deben salir de lo físicamente aceptado.** Una solicitud y una orden describen lo requerido; no prueban que esa cantidad haya llegado. El retaceo toma las líneas de la compra recibida y su cantidad recibida.
5. **La vista completa de Inventario está pendiente.** En la navegación, la entrada general de Inventario todavía es un placeholder. Ya existen APIs de saldos, unidades logísticas y capacidad, y pantallas de almacenes, ubicaciones y presentaciones.
6. **Hay una diferencia de alcance entre listas.** Solicitudes y compras aceptan un filtro `branch_id`. La lista de cotizaciones opera a nivel de empresa y no tiene filtro por sucursal. Por eso la cola solo muestra esos conteos cuando el usuario puede ver todas las sucursales y el contexto está en “Todas las sucursales”. No se deben mezclar esos totales con una tarjeta que diga que corresponden a una sucursal.

## Referencias de código revisadas

- `backend/app/application/purchases/use_cases.py` y `backend/app/application/retaceos/use_cases.py`: creación y verificación de compras, cálculo y transiciones de retaceo.
- `backend/app/domain/entities/retaceo.py`, `backend/app/domain/entities/inventory.py`, `backend/app/infrastructure/models/inventory.py` y `backend/app/api/v1/routers/inventory.py`: distribución de costos, movimientos, saldos, capacidad y permisos de Inventario.
- `backend/app/application/rbac/catalogue.py` y `docs/rbac-model.md`: catálogo de permisos, asignación a roles y cálculo de permisos efectivos.

## Permisos existentes: no agregar códigos para las tarjetas

El backend decide el acceso con permisos `recurso:acción`; el rol sirve para agrupar permisos. Los permisos efectivos del usuario son la unión de los asignados a sus roles. El nombre “Administrador”, “Gerente” o “Empleado” no concede por sí solo una acción.

| Tarjeta o acción                                      | Permisos que se deben asignar                                                 | Regla de interfaz y backend                                                                                                    |
| ----------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Ver solicitudes                                       | `purchase_requests:read`                                                      | La lista y el detalle siguen comprobando lectura.                                                                              |
| Aprobar solicitudes                                   | `purchase_requests:read` + `purchase_requests:approve`                        | La tarjeta de aprobación solo aparece si están ambos; el backend sigue protegiendo aprobar/rechazar.                           |
| Preparar una cotización desde una solicitud           | `purchase_requests:read` + `purchase_quotations:manage`                       | El acceso abre el formulario actual con la solicitud elegida. Crear la cotización sigue sujeto a `purchase_quotations:manage`. |
| Ver la cola y consultar ofertas                       | `purchase_quotations:read`                                                    | La tarjeta de cotizaciones solo aparece en contexto global porque la lista aún no filtra por sucursal.                         |
| Gestionar cotizaciones y registrar/evaluar respuestas | `purchase_quotations:manage`                                                  | La lectura basta para consultar; crear y cambiar estados sigue protegido por gestión.                                          |
| Seleccionar la oferta ganadora                        | `purchase_quotations:select`                                                  | La selección se conserva como una acción separada de lectura y gestión general.                                                |
| Verificar recepciones                                 | `purchases:read` + `purchases:verify`                                         | La tarjeta abre la lista en “Recibida”; verificar sigue siendo una acción protegida.                                           |
| Consultar existencias o saldos                        | `inventory:read`                                                              | Solo lectura de datos disponibles.                                                                                             |
| Registrar una entrada de Inventario                   | `inventory:receive`                                                           | La integración prioritaria debe validar `purchases:verify` y `inventory:receive`, o el permiso de acción que se acuerde.         |
| Consultar almacenes y capacidad                       | `warehouses.view`; la proyección de capacidad además usa `inventory:capacity` | La tarjeta abre la pantalla existente de almacenes, sin prometer un Kardex completo.                                           |
| Gestionar retaceo                                     | `retaceos:manage`, `retaceos:calculate`, `retaceos:verify`                    | Se conservan los controles actuales por acción.                                                                                |

No se necesita crear un permiso por tarjeta. Ocultar una tarjeta ayuda a la navegación, pero no reemplaza la validación del backend. La integración prioritaria debe validar los permisos de verificación de recepción y registro de entrada para que solo personal autorizado complete el paso.

## Flujo propuesto para recepción e Inventario

```text
Orden enviada
  → recepción en borrador con cantidades realmente recibidas
  → revisión de ubicación, condición y cantidad aceptada
  → verificación autorizada
  → movimiento receipt en Inventario/Kardex, una sola vez
  → retaceo con los documentos e importes reales
  → costo aterrizado asociado a las mismas líneas, sin aumentar cantidades
```

### Reglas técnicas para la integración prioritaria

- Crear un movimiento de entrada por cada recepción verificada y por la cantidad aceptada de cada línea. Las recepciones parciales generan movimientos parciales.
- Vincular el movimiento a la recepción y a la línea de compra mediante `source_reference`. Crear una `idempotency_key` estable por recepción para que reintentar la verificación no duplique existencias.
- Registrar almacén, ubicación, artículo de Inventario, unidad convertida y estado del stock. No convertir unidades de compra a unidades base por suposición: usar una equivalencia de presentación explícita.
- Registrar evidencia y diferencias de inspección: aceptado, dañado, rechazado o pendiente de revisión, según los estados que el equipo apruebe.
- Aplicar las validaciones existentes de capacidad física. El dominio contempla peso, volumen, ubicaciones y cuarentena cuando las medidas físicas están incompletas.
- Si una operación falla a mitad del proceso, la transacción o un mecanismo de reintento debe conservar el vínculo y evitar que la cantidad se publique dos veces.
- Al cerrar el retaceo, asociar el costo aterrizado a las líneas/lote recibidos. Ese paso no crea otra entrada de cantidad.
- Definir cómo se corrigen o revierten recepciones verificadas sin borrar el movimiento histórico.

## Retaceo, histórico y consulta DAI

Los enlaces a Aduanas sirven para investigar una clasificación; no son una calculadora fiscal ni una determinación automática. La clasificación SAC depende de la descripción, composición y uso del producto, y el DAI puede cambiar según el origen o el tratado aplicable. La tasa debe verificarse con el inciso arancelario y los documentos aduaneros de la importación.

Para una mejora histórica posterior, el panel puede mostrar datos de retaceos cerrados del mismo producto: fecha, cantidad, moneda, FOB, flete, gastos, DAI aplicado, IVA registrado y costo unitario resultante. Debe decir “referencia histórica”, indicar cuántas operaciones la respaldan y permitir abrir el retaceo de origen. No debe copiar valores ni reemplazar los importes de los documentos actuales automáticamente.

En la comparación de cotizaciones, otra mejora puede mostrar ofertas anteriores del mismo proveedor y producto junto con la última compra efectivamente recibida. La vista debe conservar fecha, unidad, cantidad, moneda, impuestos y condiciones de entrega/pago disponibles, y enlazar el documento de origen. Solo debe comparar importes cuando unidad y moneda se puedan normalizar; una oferta no equivale a un precio pagado ni debe seleccionar automáticamente al proveedor.

En el código actual, flete, gastos y DAI se distribuyen entre líneas en proporción al FOB. El IVA de importación se guarda aparte y se excluye del total del costo aterrizado. Cualquier cambio de base de reparto o tratamiento del IVA requiere una decisión del responsable contable/logístico; por ejemplo, algunos gastos pueden depender de peso o volumen. No se recomienda inventar porcentajes por familias generales como “harina” o “computadora”.

Fuentes oficiales para consulta:

- [Consulta del SAC y DAI](https://aduana2.mh.gob.sv/SAC/)
- [Preguntas de Aduanas sobre clasificación arancelaria de mercancías](https://sitio.aduana.gob.sv/faq-category/consultas-dga/clasificacion-arancelaria-de-mercancias/)
- [Consulta interactiva del arancel utilizado en Centroamérica](https://sitio.aduana.gob.sv/servicios/consulta-interactiva-de-arancel-utilizado-en-centroamerica/)

## Criterios de aceptación

- La tarjeta no aparece a quien carece de los permisos de lectura y acción correspondientes.
- Los conteos de solicitudes y recepciones responden al contexto de sucursal seleccionado.
- La lista de cada módulo abre con el estado que indica la tarjeta.
- Un usuario sin autorización recibe la respuesta de acceso denegado del backend al intentar una acción aunque conozca la URL.
- El acceso “Preparar cotización” solo aparece en solicitudes aprobadas/cotizables y con lectura de solicitud y gestión de cotización.
- La cotización conserva proveedor, moneda, notas, líneas y solicitud seleccionada en el mismo formulario existente.
- Los enlaces del panel DAI abren sitios oficiales en otra pestaña, y la pantalla explica que el dato final debe comprobarse con documentación aduanera.
- La integración de Inventario debe probar recepción parcial, reintento, ubicación distinta, cantidad dañada, capacidad insuficiente y reversa, y demostrar que no duplica stock.
- El cierre de retaceo no incrementa la cantidad disponible.

## Decisiones pendientes antes de publicar movimientos

1. ¿En qué momento exacto entra la cantidad al stock: al recibir, al verificar o al cerrar la recepción?
2. ¿La ubicación se elige por línea o hay una ubicación predeterminada revisada por el encargado?
3. ¿Qué condición deja la mercancía disponible, en cuarentena, dañada o bloqueada?
4. ¿Qué evidencia debe adjuntarse para marcar una recepción como verificada?
5. ¿Cómo se traducen unidades de compra y empaques a la unidad base de Inventario?
6. ¿El IVA de importación es recuperable para este negocio y cómo debe mostrarse en costo/informes?
7. ¿Qué base se aprueba para repartir flete y cada gasto: FOB, cantidad, peso, volumen o asignación manual?
8. ¿Puede una cotización enlazar solicitudes de sucursales distintas? La API actual no filtra la lista de cotizaciones por sucursal; esto requiere una decisión de alcance y autorización antes de generalizar la cola.

## Orden de trabajo y recuperación

1. Acordar las decisiones pendientes con Compras, bodega y contabilidad, en particular la semántica de disponibilidad y ubicación.
2. Implementar por bloques pequeños en una rama de trabajo, empezando por una recepción parcial y una ubicación.
3. Validar autorización, alcance por sucursal, idempotencia, saldos y auditoría en datos de desarrollo.
4. Pedir revisión del compañero en el período 3; esa revisión no sustituye ni aplaza el trabajo del responsable actual.

Punto de recuperación local previo a esta iteración: rama `codex/pre-inventory-safe-checkpoint-2026-09-26`, commit `a9bc45e`. La rama de trabajo actual es `codex/inventory-workflow-dashboard`. Ninguna de las dos se ha subido al remoto.

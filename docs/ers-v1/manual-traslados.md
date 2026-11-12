# Manual operativo de traslados — ERS-B04

**Actualizado:** 12/11/2026  
**Estado:** flujo conectado y comprobado técnicamente. La aceptación autenticada completa se hará junto con B01–B08 al finalizar B08. Las rutas entre sucursales y retorno a matriz, con aprobación (migración `0114`), se describen en las secciones nuevas; vienen **apagadas por defecto** y el recorrido de distribución desde la matriz no cambia.

## Recorrido de operación

1. Abra **Inventario → Traslados**. El panel **Abastecimiento** muestra el nombre del producto, SKU, unidad base, HUs y existencias liberadas de la bodega central.
2. Revise **Sucursal / solicitud** para elegir una necesidad aprobada. La tabla muestra solicitado, asignado, despachado, en tránsito, recibido y **pendiente de asignar**. Este último dato significa solicitado menos asignado; no es una cantidad pendiente de recepción.
3. Pulse **Preparar** junto a la solicitud. Se seleccionan la sucursal y la línea de solicitud. También puede usar **Envío manual** si no hay solicitud; documente el motivo de cualquier cantidad no asignada.
4. Elija una o más HUs, compruebe producto, lote y unidad, e indique la cantidad base que se enviará. Una cantidad sobre la demanda pendiente exige un motivo de excedente. El servidor vuelve a validar existencia y demanda.
5. Pulse **Guardar en preparación**. El sistema crea el documento, pero no reserva, divide ni mueve stock. Puede editarlo o cancelarlo antes del despacho; cerrar el formulario no cancela un documento guardado.
6. En **Documentos**, abra la preparación, seleccione un vehículo activo y confirme el despacho. Solo esta acción mueve la cantidad desde la bodega de origen a la ubicación móvil del vehículo y cambia el estado a **En tránsito**. Si el traslado sale de una sucursal y la empresa exige aprobación, primero debe estar **Aprobado** (ver [Aprobación](#aprobación-de-traslados-que-salen-de-una-sucursal)).
7. El usuario autorizado de la sucursal destino abre el documento en **Traslados**. En cada línea escribe la cantidad que contó físicamente y elige una ubicación activa y apta para almacenamiento/cuarentena. Los campos quedan vacíos hasta que se capture el conteo.
8. Confirme la recepción. Una recepción parcial mantiene el remanente **En tránsito**; lo recibido queda en **Cuarentena**, pendiente de revisión. Desde **Almacenes**, verifique las medidas y la etiqueta y libere la HU cuando corresponda. La recepción por sí sola no libera la mercancía.
9. Para una diferencia, abra una incidencia, describa el motivo y agregue la referencia de evidencia. Si se confirma una pérdida, desde la incidencia use **Crear ajuste por faltante**, adjunte el soporte, apruebe el borrador y aplíquelo con el permiso autorizado. El sistema descuenta únicamente la cantidad aún en tránsito. Si no queda remanente sin resolver, cierra como **Cerrado con ajuste**; la cantidad recibida conserva solo el conteo físico real. Para diferencias no confirmadas, mantenga la incidencia abierta o reanude el tránsito según corresponda.

## Rutas de traslado

Cada documento se clasifica automáticamente según la bodega de origen y la de destino. La ruta se muestra como insignia en la lista, en el detalle y en el diálogo de preparación.

| Ruta | Sale de | Llega a | Aprobación | Disponibilidad |
| --- | --- | --- | --- | --- |
| **Distribución desde matriz** | Bodega central (casa matriz) | Bodega activa de una sucursal | No | Siempre habilitada. Es el recorrido de las secciones anteriores. |
| **Entre sucursales** | Bodega de una sucursal | Bodega de otra sucursal | Según la regla de la empresa | Hay que activarla en **Reglas de traslados**. |
| **Retorno a matriz** | Bodega de una sucursal | Bodega central | Según la regla de la empresa | Hay que activarla en **Reglas de traslados**. |

Reglas comunes:

- Las dos rutas de sucursal vienen **apagadas** en cada empresa. Mientras ambas estén apagadas, un traslado nuevo que sale de una bodega no central se rechaza como hasta ahora (`transfer_origin_not_central`: «El traslado a sucursal debe salir de la bodega central»). Si solo una está apagada, esa ruta responde `transfer_route_disabled`.
- Origen y destino deben ser bodegas activas, aptas para almacenar, de sucursales activas. Dos bodegas de la **misma sucursal** no forman un traslado entre sucursales (`transfer_same_branch`); para mover dentro de una sucursal use los movimientos de ubicación de Almacenes.
- El selector **Bodega de origen** solo ofrece las bodegas de su alcance y asignación; la central únicamente si está en la matriz, y las de sucursal solo si alguna ruta de sucursal está activa. **Bodega destino** muestra solo las bodegas que forman una ruta válida con el origen elegido, agrupadas por sucursal. Si no queda ninguna, aparece «No hay una bodega destino habilitada para esta ruta. Revisa Reglas de traslados o Almacenes.»
- La demanda de compras (solicitudes de sucursal) solo se vincula en **Distribución desde matriz**. Un traslado entre sucursales o de retorno no acepta vínculos a solicitudes (`transfer_demand_not_allowed_for_route`); en su lugar, cada línea lleva un **Motivo del traslado**. Con origen de sucursal, el panel se titula **Preparar traslado desde sucursal** y no muestra la tabla de demanda.
- Una misma HU no puede estar a la vez en dos traslados que esperan despacho (**Pendiente de aprobación** o **Aprobado**). Al enviar, aprobar o despachar, el sistema bloquea las unidades y rechaza las que ya están comprometidas en otro documento (`transfer_handling_unit_committed`). Los borradores en preparación no comprometen unidades.

## Aprobación de traslados que salen de una sucursal

La aprobación aplica solo a **Entre sucursales** y **Retorno a matriz**, y solo si la empresa mantiene activa la regla «Exigir aprobación para traslados que salen de una sucursal» (activa por defecto). La distribución desde la matriz nunca pasa por aprobación.

Flujo normal: **En preparación** → *Enviar a aprobación* → **Pendiente de aprobación** → *Aprobar traslado* → **Aprobado** → *Confirmar despacho* → **En tránsito**.

1. **Preparar y guardar.** La sucursal de origen prepara el documento con sus propias unidades y pulsa **Guardar en preparación**; el mensaje indica que debe enviarse a aprobación cuando esté lista. Aparece el aviso «Este traslado sale de {sucursal} y necesita aprobación antes de despacharse». El despacho no está disponible todavía.
2. **Enviar.** Con el permiso de movimiento de inventario y acceso a la sucursal de origen, pulse **Enviar a aprobación**. El sistema revalida ruta, regla vigente, existencias y unidades comprometidas, registra quién y cuándo envió y sube la **ronda de aprobación** (1, 2, 3…). Mientras está pendiente, el documento no se edita.
3. **Aprobar.** Quien tenga el permiso `inventory:transfer_approve` y acceso a la sucursal **de origen** ve el botón **Aprobar traslado**. Antes de aprobar se revalidan las existencias («Se revalidarán las existencias»). El documento pasa a **Aprobado**, con el aviso «Aprobado por {usuario} el {fecha}», y aparece el panel de despacho con **Confirmar despacho**.
4. **Rechazar con motivo.** El aprobador pulsa **Rechazar**, escribe el **Motivo del rechazo** (mínimo 5 y máximo 1000 caracteres) y pulsa **Confirmar rechazo**. El documento vuelve a **En preparación** y muestra «Rechazado por {usuario} el {fecha}: {motivo}. Corrige la preparación y vuelve a enviarla». Tras corregir, se envía de nuevo y arranca una ronda nueva.
5. **Retirar la solicitud.** Quien tenga permiso de movimiento y acceso al origen, y no esté decidiendo, ve **Retirar solicitud** mientras el traslado está pendiente: vuelve a **En preparación** para corregirlo.
6. **Cancelar.** Se puede cancelar en **En preparación**, **Pendiente de aprobación** y **Aprobado**. Fuera de preparación el botón se llama **Cancelar traslado**.

Reglas de protección:

- **Ronda.** Aprobar y rechazar indican la ronda que la persona vio. Si el documento se retiró y reenvió mientras tanto, la decisión se rechaza (`transfer_approval_stale`: «La solicitud cambió desde que la abriste; actualiza el documento antes de decidir») y nadie aprueba una versión que no revisó. Si se aprueba y se retira a la vez, solo una de las dos acciones tiene efecto.
- **Segregación de funciones.** Quien creó o envió el traslado no puede aprobarlo ni rechazarlo (`transfer_approval_self_forbidden`: «No puedes aprobar un traslado que tú preparaste o enviaste»). La excepción es el **superusuario**, para que una empresa de demostración con una sola persona pueda completar el flujo.
- **Alcance del aprobador.** Necesita el permiso y acceso a la sucursal de **origen** (o acceso a todas las sucursales). No basta con tener acceso al destino.
- **Bandeja.** Quien puede aprobar ve en la cabecera la píldora «Tienes {n} traslados por aprobar», que abre **Documentos** filtrado por **Por aprobar**. La lista también ofrece el selector **Todos / Por aprobar ({n})**. Un traslado propio no cuenta como pendiente para su autor, salvo superusuario.
- **Existencias y comprometidos.** Si al enviar, aprobar o despachar una unidad ya no está disponible o está comprometida en otro traslado, la operación se rechaza sin cambios parciales.
- Si la empresa **desactiva la aprobación**, lo que ya está pendiente puede retirarse y despacharse, o aprobarse; los borradores en preparación se despachan directamente.
- Si la empresa **activa la aprobación**, los borradores en preparación de una ruta de sucursal necesitan envío antes de despachar (`transfer_approval_required`).

## Reglas de traslados

Página **Inventario → Reglas de traslados** (`/transfers/settings`), también accesible desde el enlace de la cabecera de **Traslados**. El menú y el enlace aparecen solo con el permiso `inventory:transfer_settings`; sin él, la página es de solo lectura. Cada guardado queda en la bitácora de auditoría con el estado anterior y el nuevo.

| Sección | Interruptor | Efecto |
| --- | --- | --- |
| Rutas permitidas | **Permitir traslados entre sucursales** | Habilita la ruta **Entre sucursales**. Apagado por defecto. |
| Rutas permitidas | **Permitir retornos a la bodega central** | Habilita la ruta **Retorno a matriz**. Apagado por defecto. |
| Control | **Exigir aprobación para traslados que salen de una sucursal** | Activado por defecto. Si se apaga, los traslados de sucursal se despachan sin pasar por aprobación. |

La distribución desde la matriz siempre está habilitada y no tiene interruptor.

**Qué pasa al apagar una ruta.** La página muestra una advertencia cuando hay traslados **pendientes de aprobación** o **aprobados** esperando despacho. Al apagar una ruta, los traslados de esa ruta quedan congelados: no se pueden crear, editar, enviar, aprobar ni despachar (`transfer_route_disabled`: «Los traslados entre sucursales no están habilitados en esta empresa» o «Los retornos a la bodega central no están habilitados en esta empresa»), pero aún se pueden **rechazar, retirar o cancelar**. Lo que ya está **En tránsito** o **Con incidencia** no se afecta: se recibe y se resuelve normalmente. Si vuelve a encender la ruta, los documentos congelados continúan donde estaban.

## Acceso desde Almacenes

La acción **Trasladar a sucursal** (en la bodega central) abre el mismo recorrido documental con la bodega de origen y HU seleccionadas. El destino y la solicitud se eligen en Abastecimiento. En una bodega de sucursal, cuando alguna ruta de sucursal está activa, la acción se llama **Trasladar a otra bodega** y abre el traslado con esa bodega como origen. Los traslados entre bodegas no se registran desde el formulario genérico del Kardex.

**Dividir unidad** sigue disponible como operación explícita cuando haya una separación física real. Abrir, cerrar o cancelar paneles, consultar el QR o revisar/reimprimir una etiqueta no divide ni mueve unidades. Una HU ya liberada no necesita volver a dividirse para completar el flujo de traslado.

## Seguimiento y matriz sin coordenadas

El mapa de **Seguimiento** usa las coordenadas del almacén o, si no tiene, las de su sucursal. La matriz puede no tener coordenadas (es una sede administrativa). Si en un traslado una de las dos sucursales no las tiene, por ejemplo la matriz en un **Retorno a matriz** o en una distribución, Seguimiento no puede planear la ruta ni el avance: la matriz aparece **sin coordenadas** y se muestra el aviso «Una de las sucursales no tiene coordenadas; regístralas para ver la ruta». El recorrido y la última posición del vehículo se conservan. Registre las coordenadas de la matriz en **Sucursales** si desea ver la ruta completa.

## Estados y efectos

| Estado o acción | Efecto esperado |
| --- | --- |
| En preparación | Documento editable/cancelable; no reserva ni mueve existencias. Tras un rechazo, conserva el motivo visible hasta el siguiente envío. |
| Cancelar preparación | Conserva el historial y no crea un movimiento. |
| Enviar a aprobación | Solo rutas de sucursal con aprobación exigida. Pasa a Pendiente de aprobación, registra quién y cuándo y sube la ronda. No mueve existencias. |
| Pendiente de aprobación | Congelado para edición. Se puede aprobar, rechazar con motivo, retirar o cancelar. |
| Aprobar | Revalida ruta, regla, existencias y unidades comprometidas; pasa a Aprobado. Lo hace un aprobador distinto del autor (salvo superusuario). |
| Rechazar | Vuelve a En preparación y guarda el motivo (5 a 1000 caracteres). |
| Retirar solicitud | Vuelve a En preparación; se puede corregir y reenviar. |
| Aprobado | Listo para despachar. Se puede cancelar o despachar; no se edita. |
| Despachar | Movimiento bodega de origen → vehículo; estado En tránsito. Requiere confirmación explícita. En rutas de sucursal exige estado Aprobado (o En preparación si la empresa no exige aprobación). |
| Cancelar traslado | Disponible en En preparación, Pendiente de aprobación y Aprobado; conserva el historial y no crea un movimiento. Un traslado ya despachado no se cancela. |
| Recepción parcial | Mueve solo lo contado a cuarentena; el resto sigue en tránsito. |
| Recibido | No quedan unidades en tránsito; las recibidas esperan revisión de HU/etiqueta. |
| Con incidencia | Conserva cantidades, motivo y evidencia sin eliminar movimientos. |
| Cerrado con ajuste | Todo quedó recibido/devuelto o justificado por un ajuste aprobado; la pérdida no se cuenta como recibida. |
| Liberar HU | Se hace después de verificar medidas y etiqueta desde Almacenes. |

## Escenarios manuales para el cierre integrado de B08

Estos pasos aún no se han aceptado en el navegador; forman parte del recorrido integrado pendiente:

- Preparar una línea vinculada a una solicitud y confirmar que producto, sucursal, unidad y pendiente se entienden sin usar el código HU como nombre.
- Preparar un envío manual y otro con excedente justificado; comprobar que solo las cantidades enlazadas avanzan la solicitud.
- Guardar, editar y cancelar una preparación; comprobar antes/después que no cambió el stock ni apareció un movimiento.
- Despachar dos unidades y recibir primero una; verificar una unidad en cuarentena y una en tránsito. Recibir la segunda y revisar medidas/etiqueta antes de liberar.
- Reportar una incidencia y verificar que conserva la cantidad en tránsito; resolver solo con una acción autorizada.
- Intentar recepción con una ubicación inactiva/no apta y comprobar que no se confirma.
- Revisar alcance de emisor, receptor, usuario de otra sucursal y otra empresa; cambiar sucursal/empresa con un formulario abierto y confirmar que la selección anterior se descarta.
- Reintentar tras una respuesta incierta o doble clic y confirmar que no se duplica el despacho/recepción.
- Probar la tabla de demanda en pantalla pequeña, navegación por teclado, diálogo de confirmación y temas claro/oscuro.

## Escenarios manuales de rutas y aprobación

Requieren una empresa con dos sucursales con bodega, existencias liberadas en una de ellas, un vehículo activo y tres personas (o el superusuario para el atajo de una sola persona). Active las rutas primero en **Reglas de traslados**. Identifique los documentos con una nota de demostración.

- **A→B aprobado.** Con las rutas encendidas, el operador de la sucursal A elige su bodega como origen y la de la sucursal B como destino (insignia **Entre sucursales**), agrega una unidad con **Motivo del traslado** y guarda. Pulse **Enviar a aprobación**: el estado cambia a **Pendiente de aprobación** y no se puede despachar. Un aprobador con acceso a la sucursal A abre **Por aprobar**, pulsa **Aprobar traslado** y confirma. El operador despacha con vehículo (**Confirmar despacho**), el receptor de B recibe en cuarentena y el Kardex muestra A → vehículo → B con valor global neutro.
- **Rechazo y reenvío.** Envíe un traslado y, como aprobador, pulse **Rechazar** con un motivo de menos de 5 caracteres: debe pedir el motivo. Con un motivo válido, **Confirmar rechazo**; el documento vuelve a **En preparación** mostrando el motivo. Corrija la cantidad o la unidad y envíe de nuevo: la ronda es ahora la siguiente y el aprobador puede aprobarlo. Abra el documento en dos pestañas, retire y reenvíe en una, y decida en la otra con la vista vieja: debe indicar que la solicitud cambió.
- **Autoaprobación.** El usuario que preparó o envió ve «No puedes aprobar un traslado que tú preparaste o enviaste» y no tiene botones de decisión, aunque tenga el permiso. Un superusuario sí puede aprobar el suyo. Un aprobador sin acceso a la sucursal de origen no puede decidir sobre el documento.
- **Retorno a matriz.** Encienda **Permitir retornos a la bodega central**. Desde la bodega de la sucursal A elija la bodega central como destino (insignia **Retorno a matriz**), envíe, apruebe, despache y reciba en la matriz. Si la matriz no tiene coordenadas, compruebe el aviso de Seguimiento descrito arriba.
- **Ruta apagada con un pendiente.** Deje un traslado **Entre sucursales** en **Pendiente de aprobación** y otro **Aprobado**. En **Reglas de traslados** aparece la advertencia con los dos conteos; apague **Permitir traslados entre sucursales** y guarde. Los dos documentos indican que la ruta está desactivada, no se pueden aprobar ni despachar, y sí se pueden rechazar, retirar o cancelar. Un traslado ya **En tránsito** se recibe sin problema. Vuelva a encender la ruta y compruebe que los congelados continúan.
- **Sin aprobación.** Apague **Exigir aprobación…**: un borrador nuevo de ruta de sucursal se despacha directamente desde **En preparación**; los pendientes pueden retirarse y despacharse.
- **Rutas apagadas por defecto.** En una empresa sin rutas activas, la bodega de una sucursal no aparece como origen y la distribución desde la matriz sigue igual que antes.
- **Unidad comprometida.** Con una unidad ya pendiente o aprobada en un traslado, intente incluirla en otro y enviarlo: se rechaza indicando el traslado que la tiene.

No se exige lector físico ni impresora. La demostración usa datos ficticios y la generación/consulta de etiquetas del sistema.

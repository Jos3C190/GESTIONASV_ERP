# Manual operativo de traslados — ERS-B04

**Actualizado:** 12/11/2026  
**Estado:** flujo conectado y comprobado técnicamente. La aceptación autenticada completa se hará junto con B01–B08 al finalizar B08. Las rutas entre sucursales y retorno a matriz, con aprobación (migración `0114`), se describen en las secciones nuevas; vienen **apagadas por defecto** y el recorrido de distribución desde la matriz no cambia. La migración `0116` agrega el transporte en la preparación, la recepción parcial como estado propio y las discrepancias de la recepción (averías, sobrantes y faltantes); se describen en [Transporte en la preparación](#transporte-en-la-preparación-y-sustitución-al-despachar), [Recepción parcial, averías y sobrantes](#recepción-parcial-averías-y-sobrantes) y [Discrepancias de la recepción](#discrepancias-de-la-recepción-y-su-resolución). La comprobación en el navegador de estos flujos queda pendiente.

## Recorrido de operación

1. Abra **Inventario → Traslados**. El panel **Abastecimiento** muestra el nombre del producto, SKU, unidad base, HUs y existencias liberadas de la bodega central.
2. Revise **Sucursal / solicitud** para elegir una necesidad aprobada. La tabla muestra solicitado, asignado, despachado, en tránsito, recibido y **pendiente de asignar**. Este último dato significa solicitado menos asignado; no es una cantidad pendiente de recepción.
3. Pulse **Preparar** junto a la solicitud. Se seleccionan la sucursal y la línea de solicitud. También puede usar **Envío manual** si no hay solicitud; documente el motivo de cualquier cantidad no asignada.
4. Elija una o más HUs, compruebe producto, lote y unidad, e indique la cantidad base que se enviará. Una cantidad sobre la demanda pendiente exige un motivo de excedente. El servidor vuelve a validar existencia y demanda.
5. Elija el **Vehículo** y el **Conductor** de la sucursal de origen (obligatorios para enviar a aprobación; opcionales en la distribución desde la matriz, donde se confirman al despachar). Junto a los selectores aparece un chip **Apto**, **Con advertencias** o **No apto**. Pulse **Guardar en preparación**. El sistema crea el documento, pero no reserva, divide ni mueve stock. Puede editarlo o cancelarlo antes del despacho; cerrar el formulario no cancela un documento guardado, y al editar se conservan el vehículo y el conductor guardados.
6. En **Documentos**, abra la preparación; el vehículo y el conductor guardados (o los aprobados) aparecen preseleccionados. Confirme el despacho; si cambió el vehículo o el conductor aprobado, indique el motivo del cambio (ver [Transporte en la preparación](#transporte-en-la-preparación-y-sustitución-al-despachar)). Solo esta acción mueve la cantidad desde la bodega de origen a la ubicación móvil del vehículo y cambia el estado a **En tránsito**. Si el traslado sale de una sucursal y la empresa exige aprobación, primero debe estar **Aprobado** (ver [Aprobación](#aprobación-de-traslados-que-salen-de-una-sucursal)).
7. El usuario autorizado de la sucursal destino abre el documento en **Traslados**. En cada línea escribe la cantidad que contó físicamente y elige una ubicación activa y apta para almacenamiento/cuarentena. Los campos quedan vacíos hasta que se capture el conteo.
8. Confirme la recepción con **Confirmar cantidades recibidas**. Una recepción parcial pasa el traslado a **Recepción parcial** y mantiene el remanente en el vehículo; lo recibido en buen estado queda en **Cuarentena**, pendiente de revisión. Si una parte llegó dañada o llegó mercadería de más, márquelo en la línea con **Registrar avería o sobrante** (ver [Recepción parcial, averías y sobrantes](#recepción-parcial-averías-y-sobrantes)). Desde **Almacenes**, verifique las medidas y la etiqueta y libere la HU cuando corresponda. La recepción por sí sola no libera la mercancía.
9. Para una diferencia, abra una incidencia, describa el motivo y agregue la referencia de evidencia. Si se confirma una pérdida, desde la incidencia use **Crear ajuste por faltante**, adjunte el soporte, apruebe el borrador y aplíquelo con el permiso autorizado. El sistema descuenta únicamente la cantidad aún en tránsito. Si no queda remanente sin resolver, cierra como **Cerrado con ajuste**; la cantidad recibida conserva solo el conteo físico real. Para diferencias no confirmadas, mantenga la incidencia abierta o reanude el tránsito según corresponda (vuelve a **Recepción parcial** si ya se recibió algo). Una pérdida detectada al recibir ya no necesita incidencia: use **Registrar faltante y cerrar recepción** y resuélvala como se explica en [Discrepancias de la recepción](#discrepancias-de-la-recepción-y-su-resolución).

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

Flujo normal: **En preparación** → *Enviar a aprobación* → **Pendiente de aprobación** → *Aprobar traslado* → **Aprobado** → *Confirmar despacho* → **En tránsito**. Para enviar, el traslado debe tener **vehículo y conductor**, y el aprobador ve el bloque **Transporte asignado** con su aptitud.

1. **Preparar y guardar.** La sucursal de origen prepara el documento con sus propias unidades y pulsa **Guardar en preparación**; el mensaje indica que debe enviarse a aprobación cuando esté lista. Aparece el aviso «Este traslado sale de {sucursal} y necesita aprobación antes de despacharse». El despacho no está disponible todavía.
2. **Enviar.** Con el permiso de movimiento de inventario y acceso a la sucursal de origen, pulse **Enviar a aprobación**. Si falta el vehículo o el conductor, el botón queda deshabilitado con la explicación «Elige vehículo y conductor antes de enviar el traslado a aprobación. Usa «Editar preparación» para asignarlos.»; también se deshabilita si la revisión de planificación del transporte está bloqueada. El sistema revalida ruta, regla vigente, transporte, existencias y unidades comprometidas, registra quién y cuándo envió y sube la **ronda de aprobación** (1, 2, 3…). Mientras está pendiente, el documento no se edita.
3. **Aprobar.** Quien tenga el permiso `inventory:transfer_approve` y acceso a la sucursal **de origen** ve el botón **Aprobar traslado**. Antes de aprobar se revalidan las existencias («Se revalidarán las existencias») y el transporte; **Aprobar traslado** queda deshabilitado si el transporte asignado está bloqueado («No se puede aprobar mientras el transporte asignado no sea apto. Recházalo para que lo corrijan.»). Al aprobar se guarda una copia del vehículo y el conductor aprobados. El documento pasa a **Aprobado**, con el aviso «Aprobado por {usuario} el {fecha}», y aparece el panel de despacho con **Confirmar despacho**.
4. **Rechazar con motivo.** El aprobador pulsa **Rechazar**, escribe el **Motivo del rechazo** (mínimo 5 y máximo 1000 caracteres) y pulsa **Confirmar rechazo**. El documento vuelve a **En preparación** y muestra «Rechazado por {usuario} el {fecha}: {motivo}. Corrige la preparación y vuelve a enviarla». Tras corregir, se envía de nuevo y arranca una ronda nueva.
5. **Retirar la solicitud.** Quien tenga permiso de movimiento y acceso al origen, y no esté decidiendo, ve **Retirar solicitud** mientras el traslado está pendiente: vuelve a **En preparación** para corregirlo.
6. **Cancelar.** Se puede cancelar en **En preparación**, **Pendiente de aprobación** y **Aprobado**. Fuera de preparación el botón se llama **Cancelar traslado**.

Reglas de protección:

- **Ronda.** Aprobar y rechazar indican la ronda que la persona vio. Si el documento se retiró y reenvió mientras tanto, la decisión se rechaza (`transfer_approval_stale`: «La solicitud cambió desde que la abriste; actualiza el documento antes de decidir») y nadie aprueba una versión que no revisó. Si se aprueba y se retira a la vez, solo una de las dos acciones tiene efecto.
- **Segregación de funciones.** Quien creó, editó o envió el traslado no puede aprobarlo ni rechazarlo (`transfer_approval_self_forbidden`: «No puedes aprobar un traslado que tú preparaste, editaste o enviaste»). La excepción es el **superusuario**, para que una empresa de demostración con una sola persona pueda completar el flujo.
- **Alcance del aprobador.** Necesita el permiso y acceso a la sucursal de **origen** (o acceso a todas las sucursales). No basta con tener acceso al destino.
- **Bandeja.** Quien puede aprobar ve en la cabecera la píldora «Tienes {n} traslados por aprobar», que abre **Documentos** filtrado por **Por aprobar**. La lista también ofrece el selector **Todos / Por aprobar ({n})**. Un traslado propio no cuenta como pendiente para su autor, salvo superusuario.
- **Existencias y comprometidos.** Si al enviar, aprobar o despachar una unidad ya no está disponible o está comprometida en otro traslado, la operación se rechaza sin cambios parciales.
- Si la empresa **desactiva la aprobación**, lo que ya está pendiente puede retirarse y despacharse, o aprobarse; los borradores en preparación se despachan directamente.
- Si la empresa **activa la aprobación**, los borradores en preparación de una ruta de sucursal necesitan envío antes de despachar (`transfer_approval_required`).

## Transporte en la preparación y sustitución al despachar

Desde la migración `0116` el vehículo y el conductor se eligen al **preparar**, no solo al despachar, y el aprobador los ve.

- **Selectores.** En el diálogo de preparación y en el panel de despacho aparecen **Vehículo de {sucursal de origen}** y **Conductor**. Al elegir un vehículo se ofrece el conductor asignado en Flota, pero puede elegir otro. El texto de ayuda dice «Obligatorio para enviar a aprobación» (rutas de sucursal) u «Opcional; se confirma al despachar» (distribución desde la matriz).
- **Chip de aptitud.** **Apto**, **Con advertencias** o **No apto**, con la lista de impedimentos y advertencias, la **carga estimada** en kg (y cuántos productos no tienen peso registrado) y los conflictos de planificación. La revisión espera a que deje de escribir y descarta respuestas viejas.
- **Qué impide planificar.** Solo lo estructural: vehículo inactivo o no apto para conducir, vehículo o conductor de otra sucursal, conductor faltante o inactivo (o empleado inactivo) y vehículo que no está registrado en Flota. El **exceso de peso** impide planificar únicamente si la empresa activó la regla que lo bloquea y la carga es conocida; si no, es una advertencia.
- **Lo que depende del momento de salir** (inspección pendiente, vehículo o conductor en ruta, vehículo en taller o reservado) es solo una advertencia con el prefijo «Al despachar:». Los documentos vencidos son advertencia para el aprobador; al despachar siguen impidiendo la salida, salvo la excepción autorizada de siempre.
- **Conflictos de planificación.** Solo se avisan: «El vehículo también está asignado a TR-… (aprobado)». No impiden nada.
- **Vehículo ocupado.** Un vehículo y su conductor cuentan como ocupados únicamente mientras el traslado está **En tránsito**, en **Recepción parcial** o **Con incidencia** y todavía no terminó su recorrido. Al pasar a **Con discrepancia** o cerrarse quedan libres y el recorrido GPS se archiva. Un faltante que luego «llegó» devuelve el traslado a **Recepción parcial**, pero **no** pone otra vez el vehículo en ruta.
- **Despacho con transporte aprobado.** El panel preselecciona lo aprobado (o lo guardado), aunque ya no esté disponible, para que la validación explique qué cambió. Si cambia el vehículo o el conductor aprobado aparece **Motivo del cambio** (un código) y **Explica el cambio** (mínimo 10 caracteres), con el aviso «Se aprobó con {vehículo} y {conductor}. El cambio quedará registrado y auditado.», y se indica si lo aprobado todavía estaba apto. Los códigos son: el vehículo aprobado ya no está apto, el vehículo aprobado no está disponible, el conductor aprobado ya no está apto, el conductor aprobado no está disponible, cambió la carga u otro motivo. No hace falta repetir la aprobación; el cambio queda en la auditoría (`DISPATCH_TRANSFER_SUBSTITUTION`) y en la tarjeta **Transporte** del detalle («Se cambió el transporte aprobado: …», con quién y cuándo). Sin el motivo, el servidor rechaza el despacho (`transfer_substitution_reason_required`: «Indica por qué cambias el vehículo o el conductor aprobado (mínimo 10 caracteres).»).
- **Distribución desde la matriz.** No pasa por aprobación: lo elegido al preparar solo viene preseleccionado y puede cambiarse al despachar sin motivo.
- **Excepción de cumplimiento.** Sigue siendo independiente: quien tenga el permiso de excepciones puede despachar con documentos vencidos y la tarjeta **Transporte** muestra «Salió con una excepción autorizada».
- **Solicitudes antiguas.** Un pendiente enviado antes de esta versión sin vehículo ni conductor no se puede aprobar (`transfer_assignment_required`); recházelo o retírelo y complételo.

## Recepción parcial, averías y sobrantes

**Recepción parcial.** Cuando el destino recibe menos de lo despachado, el traslado pasa a **Recepción parcial** (antes seguía como En tránsito). El detalle muestra «Recepción parcial: faltan {n} por llegar. ¿Llegará el resto?» con dos salidas:

- **Seguir esperando.** No cambia nada; registre lo que llegue cuando llegue, con **Confirmar cantidades recibidas**.
- **Registrar faltante y cerrar recepción.** Pide el **Motivo del faltante** (mínimo 5 caracteres) y una **Referencia de evidencia** opcional; confirme con **Confirmar faltante y cerrar**. Lo que no llegó queda como **faltante** abierto, con aviso de conteo en origen, y el traslado pasa a **Con discrepancia**. Solo se puede cerrar si ya se recibió algo; si no llegó nada, reporte una incidencia del traslado («Si no llegó nada, reporta una incidencia del traslado.»).

**Avería y sobrante al recibir.** En cada línea, la cantidad escrita es **solo lo que llegó en buen estado**. Active **Registrar avería o sobrante** para declarar:

- **Cantidad con avería**, **Tipo de avería**, **Describe el daño** (mínimo 5 caracteres) y **Ubicación para averías** (por defecto, la ubicación de recepción). Tipos: Rotura, Golpe o aplastamiento, Humedad o mojado, Derrame o contaminación, Empaque dañado, Empaque abierto o sello violado, Cadena de frío rota y Otro. Lo averiado entra a la bodega destino como existencia **dañada**, separada de lo vendible, y abre una discrepancia de tipo **Avería**. Cuenta como recibido físicamente, pero no como bueno.
- **Cantidad sobrante** y **Describe el sobrante** (mínimo 5 caracteres). El sobrante solo se declara cuando se registra **todo** lo pendiente de la línea («Declara sobrante solo cuando registras todo lo pendiente de la línea.»). No mueve existencias todavía: abre una discrepancia de tipo **Sobrante** y exige regularizarla.
- **Referencia de evidencia** opcional para la línea.

La línea debe tener algo recibido (bueno o averiado) y no puede superar lo pendiente. Una línea con un **faltante abierto** no se puede recibir hasta marcarlo como «Llegó la mercadería» (`transfer_discrepancy_open`).

El botón sigue siendo **Confirmar cantidades recibidas**. Si la recepción deja diferencias abiertas, el traslado pasa a **Con discrepancia**; si no queda nada pendiente ni diferencias, a **Recibido**.

**Estimación de peso de las averías.** Las unidades averiadas conservan la estimación proporcional de peso y volumen; pasarlas a existencia disponible exige la verificación habitual de medidas y etiqueta.

## Discrepancias de la recepción y su resolución

Todas las diferencias (faltante, avería, sobrante) viven en un solo registro por traslado. El detalle las muestra en **Diferencias de la recepción**, con un resumen como «1 avería en reclamo · 1 sobrante regularizado». Con el traslado en **Con discrepancia** aparece «Con discrepancia: resuelve cada diferencia para cerrar el traslado.». Cada fila muestra el tipo, el producto, la cantidad, el tipo de avería, las notas, la ubicación o unidad, el estado, el reclamo y el ajuste vinculado (con enlace).

| Tipo | Qué significa | Cómo se resuelve |
| --- | --- | --- |
| **Faltante** | No llegó. El stock sigue en tránsito en el sistema. | **Preparar ajuste de baja** (baja desde tránsito, con aprobación) → **Dado de baja**; o **Llegó la mercadería** → se anula y el traslado vuelve a **Recepción parcial**. |
| **Avería** | Llegó dañado; ya es existencia dañada en el destino. | **Preparar ajuste de baja** (baja desde dañado al costo promedio, con aprobación) → **Dada de baja**; **Liberar a cuarentena** tras inspeccionarla → **Liberada a cuarentena**; o **Registrar reclamo**. |
| **Sobrante** | Llegó de más. Todavía no hay stock en el sistema. | **Preparar ajuste de ingreso** → **Regularizado con ajuste**; o **Descartar sobrante** (fue un error de conteo) → **Descartado**. |

Estados de una diferencia: **Abierta** → **En reclamo** (solo averías) → **Resuelta**, o **Anulada** (cuando el faltante «llegó» o el sobrante se descartó).

**Ajustes de discrepancia.** **Preparar ajuste de baja** o **Preparar ajuste de ingreso** abre un formulario (motivo, documento de respaldo, fechas operativa y contable, notas) y crea un **borrador**; el sistema arma la línea según el tipo. Después se adjunta la evidencia, se aprueba y se aplica desde el ajuste, con los permisos de ajustes. Para un sobrante se indica además cómo viene empacado (el mismo empaque de origen, otro empaque o peso y volumen) y, si el usuario ve costos, el costo unitario o total documentado; sin costo documentado se usa el costo promedio, y si no existe ninguno el sistema lo exige al aplicar (`valuation_cost_required`). El sobrante entra a **cuarentena** en el destino. Al aplicar el ajuste, la diferencia se resuelve y el traslado recalcula su estado. El detalle del ajuste muestra «Vinculado a {Faltante|Avería|Sobrante} del traslado {código}» con enlace al traslado (`/transfers?transfer={id}`), y **no se edita ni se corrige**: se cancela el borrador y se prepara otro.

**Un ajuste en curso bloquea las demás salidas.** Mientras haya un ajuste en borrador o aprobado vinculado, no se puede liberar, marcar como llegado, descartar ni pasar a reclamo la diferencia (`transfer_discrepancy_has_adjustment`: «…tiene el ajuste {código} en curso. Cancela el ajuste {código} primero.»). Si se aprueba o aplica un ajuste viejo contra una diferencia que ya se cerró de otra forma, el sistema lo rechaza (`adjustment_transfer_discrepancy_closed`) y hay que cancelarlo.

**Reclamo.** **Registrar reclamo** (referencia de al menos 3 caracteres) entrega la avería al transportista o a la aseguradora. **No bloquea** el cierre del traslado: la mercancía sigue visible como dañada y puede liberarse o darse de baja más tarde. Si todo lo abierto queda en reclamo o resuelto, el traslado pasa a **Cerrado con ajuste**.

**Liberar a cuarentena.** Pide el **Resultado de la inspección** y, opcionalmente, otra **Ubicación de cuarentena** de la bodega destino; por defecto sigue a la unidad donde esté ahora dentro de esa bodega. La mercancía pasa a cuarentena y se libera a disponible con la verificación habitual de Almacenes. Si la unidad cambió de estado, salió de la bodega, se cerró o se consumió en parte, se rechaza (`transfer_discrepancy_unit_changed`). La baja de una avería también toma la unidad donde esté ahora.

**Inspección mixta.** No hay una acción especial para «una parte sirve y otra no»: libere **todo** a cuarentena y dé de baja la parte inservible con un ajuste ordinario de Inventario → Ajustes.

**Conteo en origen.** Cada faltante y cada sobrante exige contar las existencias de la bodega origen. El aviso «Conteo pendiente en origen: cuenta las existencias de {sucursal} y registra el resultado en cada diferencia con «Registrar conteo en origen». No impide cerrar el traslado.» aparece al personal del origen con permiso de ajustes, y la lista muestra la insignia **Conteo pendiente en origen** (también como filtro). **Registrar conteo en origen** pide el resultado del conteo (mínimo 5 caracteres) y solo se registra una vez.

**Quién puede hacer qué.** Resuelven las diferencias las personas con acceso al **destino**: ajuste de baja o ingreso (`inventory:adjust`), reclamo, liberación y descarte (`inventory:adjust_approve`), «Llegó la mercadería» (`inventory:receive`). El faltante también puede prepararlo el origen. El conteo en origen es del origen (`inventory:adjust`). Detalle en `docs/rbac-model.md`.

**Cierre.** Cuando ninguna diferencia queda abierta (las que están en reclamo no cuentan como abiertas) y no queda nada pendiente, el traslado pasa a **Cerrado con ajuste**. Si no hubo diferencias ni pérdida, pasa a **Recibido**. Un traslado terminado no se reabre.

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
| Despachar | Movimiento bodega de origen → vehículo; estado En tránsito. Requiere confirmación explícita. En rutas de sucursal exige estado Aprobado (o En preparación si la empresa no exige aprobación). Si cambia el vehículo o el conductor aprobado, exige código y motivo (mínimo 10 caracteres) y queda auditado. |
| Cancelar traslado | Disponible en En preparación, Pendiente de aprobación y Aprobado; conserva el historial y no crea un movimiento. Un traslado ya despachado no se cancela. |
| Recepción parcial | Estado propio (antes seguía En tránsito). Mueve solo lo contado: lo bueno a cuarentena y lo averiado a existencia dañada; el resto sigue en el vehículo, que sigue ocupado. Se puede seguir recibiendo, abrir una incidencia o **Registrar faltante y cerrar recepción**. |
| Registrar faltante y cerrar recepción | Lo que no llegó queda como faltante abierto con conteo pendiente en origen; pasa a Con discrepancia. |
| Con discrepancia | Ya no queda nada por llegar, pero hay faltantes, averías o sobrantes abiertos. El vehículo y el conductor quedan libres y el recorrido GPS se archiva. Un faltante que «llegó» devuelve a Recepción parcial. |
| Recibido | No quedan unidades en tránsito; las recibidas esperan revisión de HU/etiqueta. |
| Con incidencia | Conserva cantidades, motivo y evidencia sin eliminar movimientos. Se abre desde En tránsito o Recepción parcial; al reanudar vuelve a Recepción parcial si ya se recibió algo. |
| Cerrado con ajuste | Todo quedó recibido/devuelto o justificado, y hubo diferencias o pérdida: ajuste aprobado, liberación, reclamo, descarte o faltante que llegó. La pérdida no se cuenta como recibida. Muestra un resumen por tipo, por ejemplo «1 avería en reclamo · 1 sobrante regularizado». |
| Ajuste de discrepancia | Borrador creado desde la diferencia; al aplicarlo se resuelve y el traslado recalcula su estado. Un ajuste vinculado no se edita ni se corrige. |
| Liberar a cuarentena | Mueve la avería de dañado a cuarentena; después se verifica y libera como cualquier HU. |
| Registrar reclamo | Avería en reclamo; no impide cerrar el traslado. |
| Registrar conteo en origen | Atiende el aviso de conteo; no impide cerrar. |
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
- **Autoaprobación.** El usuario que preparó, editó o envió ve «No puedes aprobar un traslado que tú preparaste, editaste o enviaste» y no tiene botones de decisión, aunque tenga el permiso. Un superusuario sí puede aprobar el suyo. Un aprobador sin acceso a la sucursal de origen no puede decidir sobre el documento.
- **Retorno a matriz.** Encienda **Permitir retornos a la bodega central**. Desde la bodega de la sucursal A elija la bodega central como destino (insignia **Retorno a matriz**), envíe, apruebe, despache y reciba en la matriz. Si la matriz no tiene coordenadas, compruebe el aviso de Seguimiento descrito arriba.
- **Ruta apagada con un pendiente.** Deje un traslado **Entre sucursales** en **Pendiente de aprobación** y otro **Aprobado**. En **Reglas de traslados** aparece la advertencia con los dos conteos; apague **Permitir traslados entre sucursales** y guarde. Los dos documentos indican que la ruta está desactivada, no se pueden aprobar ni despachar, y sí se pueden rechazar, retirar o cancelar. Un traslado ya **En tránsito** se recibe sin problema. Vuelva a encender la ruta y compruebe que los congelados continúan.
- **Sin aprobación.** Apague **Exigir aprobación…**: un borrador nuevo de ruta de sucursal se despacha directamente desde **En preparación**; los pendientes pueden retirarse y despacharse.
- **Rutas apagadas por defecto.** En una empresa sin rutas activas, la bodega de una sucursal no aparece como origen y la distribución desde la matriz sigue igual que antes.
- **Unidad comprometida.** Con una unidad ya pendiente o aprobada en un traslado, intente incluirla en otro y enviarlo: se rechaza indicando el traslado que la tiene.

## Escenarios manuales de transporte, recepción parcial y discrepancias

Requieren una empresa con dos sucursales con bodega, existencias liberadas en la sucursal de origen, dos vehículos activos con sus conductores y las rutas de sucursal encendidas. Identifique los documentos con una nota de demostración. Estos escenarios están **pendientes de comprobación en el navegador**.

- **Transporte desde la preparación.** Prepare un traslado A→B y elija vehículo y conductor: aparecen los chips de aptitud y la carga estimada. Guarde, reabra con **Editar preparación** y compruebe que el vehículo y el conductor siguen ahí. Sin conductor, **Enviar a aprobación** queda deshabilitado con su explicación. Elija un vehículo ocupado en otro traslado: solo avisa «Al despachar: …».
- **Aprobador.** Con otro perfil, abra el traslado en **Por aprobar**: el bloque **Transporte asignado** muestra vehículo, conductor, aptitud y conflictos. **Aprobar traslado** queda deshabilitado si el transporte está bloqueado.
- **Sustitución.** Con el traslado **Aprobado**, en el panel de despacho elija otro vehículo: aparece **Motivo del cambio** y **Explica el cambio**. Con menos de 10 caracteres no se confirma. Tras despachar, la tarjeta **Transporte** muestra lo aprobado frente a lo real y la sustitución.
- **Recepción parcial.** Reciba la mitad: estado **Recepción parcial** y el vehículo sigue ocupado en Flota y Seguimiento. Pulse **Seguir esperando** y compruebe que nada cambia.
- **Avería y sobrante.** Reciba el resto con **Registrar avería o sobrante**: una cantidad con avería (tipo y descripción) y un sobrante (descripción). El traslado pasa a **Con discrepancia**, el vehículo queda libre, el recorrido se archiva y el origen ve «Conteo pendiente en origen». En Almacenes, la avería aparece como existencia dañada y lo bueno en cuarentena.
- **Resolver la avería.** **Liberar a cuarentena** con el resultado de la inspección, o **Preparar ajuste de baja**, adjuntar evidencia, aprobar y aplicar. Compruebe que con el ajuste en borrador los botones de liberar y reclamo no están disponibles.
- **Regularizar el sobrante.** **Preparar ajuste de ingreso** (empaque o medidas, costo y documento), adjuntar evidencia, aprobar y aplicar; el sobrante entra a cuarentena. Pruebe también **Descartar sobrante** en otro caso.
- **Reclamo.** Ponga una avería en reclamo: el traslado puede cerrarse como **Cerrado con ajuste** y la mercancía sigue como dañada; libérela o dé de baja más tarde.
- **Faltante.** En otro traslado, reciba una parte y use **Registrar faltante y cerrar recepción** con su motivo. Resuelva con **Preparar ajuste de baja** o, en otro caso, con **Llegó la mercadería** (vuelve a **Recepción parcial** sin poner el vehículo en ruta). Use **Registrar conteo en origen** desde el perfil del origen.
- **Inspección mixta.** Libere toda una avería a cuarentena y dé de baja una parte con un ajuste ordinario; compruebe el Kardex.
- **Enlace al traslado.** Desde el detalle de un ajuste de discrepancia, abra «Abrir el traslado {código}» (`/transfers?transfer={id}`) y compruebe que abre ese documento.
- **Permisos.** Un usuario del origen sin acceso al destino no puede liberar, reclamar ni descartar; un usuario del destino no registra el conteo en origen.

No se exige lector físico ni impresora. La demostración usa datos ficticios y la generación/consulta de etiquetas del sistema.

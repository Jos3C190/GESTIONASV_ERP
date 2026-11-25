# Plan: Ventas V4 — Robustez del DTE

Fuente: `docs/plan-area-ventas-el-salvador.pdf`, bloque V4 («Contingencia por empresa y establecimiento,
invalidación, nota de crédito, nota de débito, nota de remisión emitida al despachar traslados, evento de
retorno, plantillas faltantes y certificación ante Hacienda»). El generador `docs/plan_area_ventas_pdf.py`
tiene el texto completo.

Resultado verificable: los cinco desvíos de la Figura 1 se prueban de extremo a extremo y la herramienta de
certificación está lista. Los cinco desvíos son: rechazado (corregir y reenviar), sin respuesta (consultar y
reintentar), sin conexión (contingencia), error posterior (invalidación) y ajuste posterior (nota de crédito
o de débito).

Documentación oficial: `D:\josec\Downloads\Documentacion DTE\` (Manual Técnico y Funcional v2, schemas y
catálogos). El proyecto de referencia es de solo lectura.

## Decisiones del usuario (17/11/2026)

- **Corte**: cinco PR hacia `develop`, en este orden:
  - **V4a** contingencia por empresa y establecimiento, más «sin respuesta: consultar y reintentar».
  - **V4b** invalidación, más «rechazado: corregir y reenviar». Con V4b, un pedido facturado ya se puede
    cancelar invalidando su documento.
  - **V4c** notas de crédito (05) y de débito (06) sobre un CCF sellado.
  - **V4d** nota de remisión (04) al despachar traslados, y evento de retorno.
  - **V4e** herramienta del lote de certificación.
- **Notas de crédito y débito (V4c)**: solo ajustan el documento.
  - Se emiten sobre un CCF sellado, con líneas tomadas de él, sin pasar de su saldo y dentro del plazo legal.
  - No mueven inventario ni reintegran dinero: eso se conecta en V8 (devoluciones con efecto fiscal).
- **Nota de remisión (V4d)**: configurable por empresa.
  - Si la empresa habilita el tipo 04 en sus documentos, se emite sola al despachar un traslado.
  - Si no lo habilita, el despacho sigue como hoy.
- **Certificación (V4e)**: se construye ahora la herramienta que arma y transmite el lote por tipo de
  documento y muestra su avance. Se prueba contra el stub; el lote real se corre cuando haya credenciales.
- **Pendiente para V8 (decidido el 20/11/2026): invalidación tipo 3 «Otro» de CAT-024.**
  - Qué es: el Manual Funcional V2.0 (§VII, pág. 12) dice «Otro (esta opción incluye el cambio de
    bienes/servicios)». Igual que el tipo 1, exige que el documento de reemplazo esté sellado antes.
  - Hoy (V4b) el ERP solo usa el tipo 1 («Corregir documento») y el 2 («Anular documento»). El servicio DTE
    ya acepta el 3; el ERP no (`InvalidationKind` y el CHECK de `sales_fiscal_invalidations.kind` admiten
    1 y 2).
  - No se agrega ahora: el reemplazo se arma con los datos actuales del pedido y un pedido facturado no
    permite cambiar el producto, así que un tipo 3 sería un tipo 1 con otra etiqueta. Además, un cambio de
    producto también mueve inventario (devolución B08).
  - En V8, al diseñar devoluciones y cambios, decidir por caso entre: invalidar con tipo 3 y emitir el
    documento nuevo (si el cambio ocurre dentro del plazo de invalidación), o documentar la devolución con
    evento de retorno (factura) o nota de crédito (CCF) y emitir el documento nuevo. Cambios: ampliar el
    CHECK, acción «cambio» con motivo obligatorio y selector del tipo en el formulario.
- Siguen vigentes:
  - merge delegado con los checks propios en verde, con Auto-fix y auto-merge (merge) en cada PR;
  - commits y PR sin atribución;
  - ignorar el check de Vercel;
  - el `.env` no se lee ni se toca sin un «sí» explícito del usuario.

## Para el futuro: punto de venta y caja (antes V6, pospuesto el 24/11/2026)

El ingeniero de la materia pidió un alcance más simple; el usuario decidió no hacer el POS ahora y guardarlo.
Contenido previsto (plan de Ventas, módulo 4 y bloque V6), para retomarlo después:
- Pantalla de venta rápida de mostrador: búsqueda o lector de código de barras, cobro mixto, tiquete de 80 mm.
- Turnos por cajero, arqueo por denominación, depósito del día; el cierre aprobado no se modifica.
- Existencia de vitrina que se descuenta por pieza (se alimenta abriendo una unidad logística).
- Operación en contingencia, con enlace de respaldo o nodo local por tienda; anular una venta cobrada pide
  supervisor.
- Promociones de mostrador: 2×1, combos, precio por horario. (La **promoción por sucursal** que pidió el
  ingeniero no depende del POS: ver «Pedido del ingeniero».)

## Pedido del ingeniero (24/11/2026)

Alcance simple que pidió el docente, y su estado al 24/11/2026:
1. Kardex con costo promedio ponderado que viene del retaceo, sin editar ni borrar historial: **hecho**
   (valoración por promedio móvil de la empresa, retaceo como ajuste de costo, triggers de inmutabilidad y
   rutas de solo lectura).
2. Precio de venta global con historial, y nunca por debajo del costo del kardex: **parcial**. Hay listas con
   vigencia e historial (y precio opcional por sucursal), pero hoy vender bajo costo se permite con
   autorización de un rol con `can_sell_below_cost`; el ingeniero pide bloquearlo siempre.
3. Promoción por sucursal que bloquea el descuento manual del vendedor: **falta** (hay descuentos con topes
   por rol, no promociones).
4. Descontar existencias al confirmar la venta y verlo en el kardex: **parcial**. Confirmar el pedido aparta
   (reserva comercial); la salida del kardex ocurre al confirmar la entrega.
5. PDF de factura (01, IVA incluido) o crédito fiscal (03, IVA y retención desglosados) con empresa, cliente,
   tabla, total en letras y QR: **hecho** (el sistema elige 03 si el cliente puede recibirlo y 01 si no; el
   PDF dice «Total en Letras: …» en vez de «SON: …»).

## Bloques

### PI — Pedido del ingeniero: puntos 2, 3 y 4 (rama `feature/ventas-pedido-ingeniero`)

Se hace antes de V4d, a pedido del usuario (24/11/2026). Decisiones:
- **Punto 2, venta bajo costo**: se bloquea siempre, sin excepción por rol. La línea compara su precio neto
  sin IVA, ya con el descuento de línea **y el global**, contra el costo promedio del kardex. La vista previa lo
  marca (no lanza error) para que la pantalla lo muestre; guardar, emitir, confirmar y autorizar lo rechazan
  con `sales_price_below_cost`. Al confirmar se usa el costo vigente del kardex, no el guardado. Se retira el
  permiso de rol «Puede vender bajo costo» (columna `can_sell_below_cost`) y el motivo de autorización
  `below_cost`.
- **Punto 3, promoción por sucursal** (el usuario eligió «la promoción reemplaza todo»): porcentaje por
  producto y sucursal con vigencia. En una línea con promoción el descuento es el de la promoción: no se
  aplican el del cliente ni el de volumen, el vendedor no puede cambiarlo (la pantalla lo deshabilita y el
  servidor usa el de la promoción aunque llegue otro, para que un borrador viejo se siga abriendo) y el
  documento no admite descuento global
  (`sales_global_discount_with_promotion`). La promoción no pasa por el tope del rol, pero sí por el costo:
  si deja la línea bajo costo, se bloquea. Permiso `sales_promotions:manage`; leer pide `sales:read`.
- **Punto 4, salida al confirmar** (el usuario eligió «automático con cajas completas»): al quedar
  confirmado (al confirmar o al autorizar), el pedido se entrega solo con unidades logísticas **completas**
  de la sucursal, primero las que vencen antes (como «Preparar entrega»), y la salida queda en el kardex en la
  misma transacción. Una línea que no se cubre exacto con unidades completas queda apartada y el pedido
  muestra un aviso para separar la unidad en bodega y entregarla con «Preparar entrega». Aplica a retiro y a
  entrega a domicilio. Se agregó la configuración por empresa `sales_settings.auto_deliver_on_confirm`
  (migración 0136, **encendida por omisión**, `GET/PUT /sales/settings/orders`) para que una empresa que
  despacha después conserve el flujo manual; las e2e de entregas la apagan mientras corren.

Pasos:
- [x] **Paso 0: plan y rama.**
- [x] **Paso 1: venta bajo costo bloqueada.** Dominio (`sales_quotation.py`, `sales_margin.py`), cálculo con
  el descuento global, error al guardar/emitir/confirmar/autorizar, costo vigente al confirmar, migración 0134
  que retira `can_sell_below_cost`, API y pantalla de topes sin «Puede vender bajo costo». Verificar:
  unitarias, e2e de cotización y pedido.
- [x] **Paso 2: promociones por sucursal (backend).** Migración 0135 (`sales_branch_promotions`, fuente de
  descuento `promotion`, permiso), dominio, casos de uso, API `/sales/promotions` y su efecto en el cálculo.
  Verificar: unitarias, prueba de migración, e2e.
- [x] **Paso 3: salida automática al confirmar.** Entrega automática con unidades completas al confirmar o
  autorizar, y aviso de lo pendiente. Verificar: e2e (kardex con la salida, línea que no se cubre).
  - Pasos 1 a 3 hechos: migraciones 0134 (retira `can_sell_below_cost`), 0135 (`sales_branch_promotions`,
    fuente `promotion`, permiso) y 0136 (configuración). `require_not_below_cost` en guardar, emitir,
    confirmar y autorizar, con el costo vigente del kardex al confirmar (`reevaluate(current_costs=True)`).
    Promociones en `SalesDiscountUseCases` y router `sales_promotions.py`. Entrega automática:
    `SalesDeliveryService.auto_deliver` desde el router de pedidos al confirmar o autorizar; la respuesta trae
    `auto_delivery`. Pruebas: `tests/unit/test_sales_engineer_rules.py`, `tests/e2e/test_sales_engineer_rules.py`
    y `tests/integration/test_sales_engineer_rules_migration.py`; e2e de ventas en verde.
- [x] **Paso 4: interfaz.** Pantalla Ventas → Promociones; en el editor, insignia de promoción y descuento
  bloqueado, y línea bajo costo marcada con el guardado deshabilitado; aviso de entrega en el pedido.
  Verificar: vitest.
  - Hecho: `PromotionsPage` (ruta /sales/promotions), `OrderSettingsPanel` en Configuración de ventas
    (interruptor «Descontar existencias al confirmar el pedido»), aviso `auto_delivery` en `SaleDetail`.
    Políticas de descuento sin la casilla de vender bajo costo. vitest de ventas y listas: 92 en verde.
- [x] **Paso 5: documentación.** Manuales de descuentos, cotizaciones, pedidos y entregas; `api.md` y
  `database-schema.md` (sección 44).
- [x] **Paso 6: verificación y PR.** Batería completa, QA en el navegador, PR con Auto-fix y auto-merge.
  - PR #58 mergeado en develop (24/11/2026). En CI, el fixture autouse de entregas cerraba después de liberar
    la pool y dejaba una conexión en otro loop; ahora depende de `e2e_client`.
  - QA en el navegador (24/11/2026): promoción creada y terminada en la Matriz; el editor fija el 10 %
    y bloquea el descuento global; precio manual bajo costo muestra el aviso y deshabilita guardar;
    confirmar un pedido de 1 kg de café (unidad de 120 kg en bodega) deja el aviso de separar la unidad.
    Ajustes: pestaña «Cotizaciones y pedidos», textos de apartado/salida y botón sin salto de línea.
  - Batería: backend 2044 pasan; `test_inventory_final_acceptance` apartaba y entregaba a mano, ahora apaga
    la salida automática durante su confirmación; `test_sales_discounts` falló una vez por un loop de asyncio
    y pasa al repetirla. Frontend completo (vitest, check, lint, build) en verde.


### V4a — Contingencia por empresa y establecimiento (rama `feature/ventas-v4a-contingencia`)

Hechos verificados en el servicio (`dte-service/src/services/contingenciaService.js`):
- La ventana de contingencia es única para todo el servicio: `ventanaActiva()` no filtra por emisor y la
  tabla `contingencias` no guarda NIT ni establecimiento.
- Quedan 3 usos de `config.emisor.nit`: consultar un documento, transmitirlo y transmitir el evento. El
  responsable del evento sale de `MH_RESPONSABLE_*` o de la solicitud.
- `transmisionService` ya aplica la política del manual (8 s, consultar el estado, máximo dos reenvíos) y
  después pasa a contingencia con `registrarFallaDeConectividad`.
- Las rutas `/api/contingencia` (listar, forzar, cerrar, enviar el evento y transmitir) no están por emisor.

Pasos:
- [x] **Paso 0: plan y rama.** Este plan; rama desde `develop` actualizado.
- [x] **Paso 1: ventana por emisor y establecimiento en el servicio.**
  - Migración SQLite: `contingencias` gana `nit_emisor` y `cod_establecimiento`; el índice único de ventana
    activa pasa a ser por (NIT, establecimiento). Las filas viejas toman el emisor del entorno, si existe.
  - `ventanaActiva`, `abrirVentana` y `vincular` usan el emisor y el establecimiento del documento.
  - Se quitan los 3 usos de `config.emisor`: el NIT sale del contexto del emisor del documento o de la ventana.
  - El responsable del evento sale del registro del emisor; el ERP lo envía al registrar a la empresa.
  - Verificar: pruebas nuevas con dos empresas, y un establecimiento en contingencia mientras otro de la misma
    empresa emite normal; `./scripts/run-tests.sh dte`.
- [x] **Paso 2: rutas de contingencia por emisor.**
  - `/api/emisores/:nit/contingencias` para listar, forzar con tipo y motivo, cerrar, enviar el evento y
    transmitir, con el alcance `contingency`.
  - Las rutas globales quedan para el emisor del entorno, o se retiran si nada las usa.
  - En simulado, la contingencia se simula (el escenario se fuerza con `simulacion`) para poder probarla
    sin Hacienda.
  - Verificar: pruebas de integración del servicio.
- [x] **Paso 3: estado «en contingencia» en el ERP.**
  - Migración: `sales_fiscal_documents` agrega el estado `contingency` y los campos de transmisión
    (`transmission_type`, `contingency_type`, `contingency_reason`, `contingency_window_id`).
  - Dominio: transiciones `pending → contingency → issued | rejected`. Un documento en contingencia ya tiene
    número de control y versión legible: se entrega al cliente, con el correo automático.
  - `dte_worker`:
    - el resultado CONTINGENCIA deja el documento en `contingency`;
    - una tarea de conciliación consulta su estado hasta el sello, sin volver a emitir.
  - Verificar: unitarias del dominio y e2e con el cliente DTE falso.
- [x] **Paso 4: API y permisos.**
  - `GET /sales/contingencies`, `POST /sales/contingencies` (forzar por establecimiento, con tipo del
    catálogo CAT-005 y motivo) y `POST /sales/contingencies/{id}/close`.
  - Permiso `sales_invoices:contingency` (creado en la migración 0130; sigue el espacio de nombres de
    `sales_invoices:read`/`issue`) y auditoría.
  - Verificar: e2e de permisos, auditoría y aislamiento entre empresas.
- [x] **Paso 5: interfaz.**
  - En la bandeja de documentos: estado «En contingencia» y filtro.
  - Pantalla «Contingencia», con las ventanas por establecimiento (activa o cerrada), sus documentos, el
    estado del evento y el plazo de 24 h para el evento y de 72 h para los documentos.
  - Acciones «Activar contingencia» y «Cerrar contingencia».
  - Aviso en la bandeja cuando hay una ventana activa.
  - Verificar: vitest con estados de carga, vacío y error.
- [x] **Paso 6: documentación.** `api.md`, esquema, manual de documentos fiscales y `multiemisor.md`.
- [x] **Paso 7: verificación y PR.**
  - Batería completa y QA en el navegador: forzar la contingencia en simulado, emitir, cerrar y ver el sello.
  - PR hacia `develop`.

### V4b — Invalidación y rechazos (rama `feature/ventas-v4b-invalidacion`)

Decisiones del usuario (18/11/2026):
- **Responsable**: el responsable del evento de contingencia (V4a) pasa a ser el «responsable fiscal de la
  empresa» y también firma las invalidaciones.
- **Error en los datos (tipo 1)**: automático. «Corregir documento» emite el reemplazo con los datos actuales
  del cliente y del pedido y, cuando queda sellado, el sistema invalida el original y lo vincula.
- **Correo**: al invalidar se avisa al cliente, si tiene correo, con el PDF del evento de invalidación.
- **Cancelar un pedido facturado**: en un solo paso desde el pedido. Se piden el motivo y el solicitante,
  se invalida el documento (tipo 2, rescindir la operación) y, cuando Hacienda lo acepta, se cancela el pedido.

Hechos verificados:
- El servicio ya tiene la invalidación completa:
  - `POST /api/dte/:codigo/anular` y `GET /api/dte/:codigo/invalidacion` (vista previa con el plazo y las
    reglas de reemplazo);
  - el constructor valida tipo (1 error, 2 rescindir, 3 otro), responsable y solicitante (CAT-022);
  - tipos 1 y 3 exigen el reemplazo ya sellado, salvo en 05 y 08;
  - plazos: tres meses desde el sello para 01, 11 y 14; décimo día hábil del mes siguiente para los demás.
- La invalidación simulada (`/api/dte/simulacion/...`) solo se monta con el despliegue en simulado. En el
  real, `/anular` responde 409 a un emisor simulado: hay que despachar por el modo del emisor.
- En el ERP un documento rechazado cuenta como activo. Bloquea volver a facturar el pedido (índice
  `uq_sales_fiscal_documents_active_sale`, con `status <> 'failed'`) y también cancelarlo (`invoiced()`).

Pasos:
- [x] **Paso 0: plan y rama.**
- [x] **Paso 1: invalidación por modo del emisor en el servicio.**
  - `/anular` y `/invalidacion` usan el proveedor simulado cuando el emisor es simulado, y el real en otro
    caso, en cualquier despliegue. Las rutas `/simulacion` se conservan.
  - Verificar: pruebas de integración (emisor simulado en un despliegue en pruebas) y `run-tests.sh dte`.
- [x] **Paso 2: migración 0131 y dominio.**
  - `sales_fiscal_documents`:
    - estado `invalidated`;
    - `replaces_document_id` y `superseded_by_id` (FK compuestas a la misma tabla);
    - el índice del documento activo del pedido pasa a ser
      `status IN ('pending','contingency','issued','simulated') AND superseded_by_id IS NULL`.
    Un rechazado o un invalidado ya no bloquea volver a facturar.
  - Tabla `sales_fiscal_invalidations`, una por intento:
    - `kind` (1 o 2), `reason`, solicitante (nombre, tipo y número de documento) y responsable (copia);
    - `replacement_document_id`, `cancel_order` y la clave de idempotencia;
    - estado `pending`, `accepted`, `rejected` o `failed`;
    - código de generación y sello del evento, error, `requested_by` y fechas.
    Solo una pendiente por documento.
  - Permiso `sales_invoices:invalidate`. El downgrade se niega si hay invalidaciones o documentos vinculados.
  - Dominio: reglas de lo que se puede invalidar (emitido o simulado, sin invalidación en curso) y de lo que
    se puede corregir (factura o CCF emitido, sin reemplazo en curso).
  - Verificar: unitarias y prueba de migración.
- [x] **Paso 3: rechazados y reemplazo.**
  - Un documento rechazado deja de bloquear: se corrigen los datos y «Facturar de nuevo» crea otro.
    Las observaciones de Hacienda se muestran legibles.
  - «Corregir documento» crea el reemplazo (`replaces_document_id`) con los datos actuales y marca el original
    `superseded_by_id`. Si el reemplazo falla o lo rechazan, se suelta el vínculo y el original sigue vigente.
  - Verificar: e2e con el servicio simulado.
- [x] **Paso 4: invalidación en el trabajador y en la API.**
  - Tarea arq `invalidate_fiscal_document`: registra a la empresa con el responsable, llama a `/anular` con su
    clave, y al aceptarse deja el documento `invalidated`, audita, encola el correo y, si `cancel_order`,
    cancela el pedido. Con un rechazo o un fallo, el error queda en la invalidación y el documento vigente.
  - Tipo 1: al sellarse el reemplazo, el trabajador encola la invalidación del original con su código.
  - API:
    - `GET /sales/fiscal-documents/{id}/invalidation` (vista previa: plazo y si está vencido);
    - `POST .../invalidate` (tipo 2, motivo, solicitante);
    - `POST .../correct` (tipo 1);
    - en el pedido, `cancel` con documento: invalida y cancela al aceptarse.
    Permiso `sales_invoices:invalidate` y bitácora.
  - Verificar: e2e del recorrido simulado completo, con permisos, plazos y errores.
- [x] **Paso 5: correo del aviso de invalidación.** Composición, adjunto con el PDF del evento (lo arma el
  servicio) y envío automático. Verificar: unitarias y e2e.
- [x] **Paso 6: interfaz.**
  - Detalle del documento:
    - «Anular documento» (rescindir) con motivo y solicitante;
    - «Corregir documento» con su explicación;
    - estado «Invalidado» con el evento, el sello y el reemplazo vinculado;
    - observaciones del rechazo y «Facturar de nuevo».
  - Pedido: cancelar un pedido facturado pide el motivo y el solicitante.
  - La bandeja agrega el estado «Invalidado» y su filtro.
  - La pantalla de contingencia pasa a decir «Responsable fiscal» (firma contingencias e invalidaciones).
  - Verificar: vitest.
- [x] **Paso 7: documentación.** `api.md`, esquema, manual de facturación y `multiemisor.md`.
- [x] **Paso 8: verificación y PR.** Batería completa, QA en el navegador con el servicio simulado y PR.

### V4b2 — Clasificación de renta por documento (rama `feature/ventas-renta-por-documento`)

Pedido del usuario (18/11/2026), a partir de lo que señaló su contador: el «tipo de operación» y el «tipo de
ingreso» de renta de los anexos del F-07 se eligen antes de emitir cada factura, no al exportar (como hace el
proyecto de referencia). El usuario decidió hacerlo antes de V4c.

Hechos verificados (Manual de anexos del F-07 V14, DGII, enero 2025):
- Son columnas de cada fila de los anexos de ventas: R y S en contribuyentes, U y V en consumidor final.
  Rigen desde el período de enero de 2025.
- Tipo de operación: 1 gravada, 2 no gravada o exenta, 3 excluido o no constituye renta, 4 mixta («cuando
  en un mismo documento» hay operación gravada y exenta), 12 ya retenido en F910, 13 sujetos excluidos
  (art. 6 LISR).
- Tipo de ingreso: 1 profesiones, artes y oficios; 2 servicios; 3 comerciales; 4 industriales;
  5 agropecuarias; 6 utilidades y dividendos; 7 exportación de bienes; 8 servicios del exterior utilizados en
  El Salvador; 9 exportación de servicios; 10 otras rentas gravables; 12 y 13 como arriba.
- El DTE no los lleva: en los esquemas oficiales no hay campo y `identificacion.tipoOperacion` es la
  transmisión. Es clasificación de renta, no de IVA, así que no se deduce de los montos del IVA.
- No se pudo leer el complemento del F-07 V14 de agosto de 2025: el sitio del MH bloquea la descarga.

Diseño:
- Cada actividad económica de la empresa tiene una clasificación sugerida (tipo de operación y tipo de
  ingreso), que se configura en Configuración fiscal → Actividades.
- Al facturar, la sección Factura del pedido muestra los dos valores, tomados de la actividad del
  establecimiento (o la principal), y se pueden cambiar. Sin valor sugerido hay que elegirlos.
- El documento fiscal guarda los dos valores. El reemplazo de una corrección hereda los del original. Los
  anexos (V8) los usarán tal cual. Los documentos ya emitidos quedan sin clasificación.
- Regla: 12 y 13 van iguales en las dos columnas (son el mismo concepto en los dos catálogos).

Pasos:
- [x] **Paso 0: plan y rama.**
- [x] **Paso 1: migración 0132 y dominio.** Columnas `renta_operation_type` y `renta_income_type` en
  `company_economic_activities` y `sales_fiscal_documents`, con checks de catálogo y «las dos o ninguna».
  Dominio `sales_renta.py` con los catálogos y `validate_renta`. Verificar: unitarias y prueba de migración.
- [x] **Paso 2: API.** `PUT /fiscal/activities/{id}/renta` (`fiscal_settings:manage`, auditado). Las actividades
  devuelven su clasificación. `invoice` acepta `renta_operation_type` y `renta_income_type`; sin ellos usa la
  sugerida y, sin sugerida, responde `sales_invoice_renta_required`. `invoice-options` devuelve la sugerida. El
  documento expone su clasificación. Verificar: e2e.
- [x] **Paso 3: interfaz.** Selectores en la pestaña Actividades, en la sección Factura del pedido y la
  clasificación en el detalle del documento. Verificar: vitest.
- [x] **Paso 4: documentación.** `api.md`, esquema, manual de configuración fiscal y manual de facturación.
- [x] **Paso 5: verificación y PR.** Batería completa, QA en el navegador y PR a `develop`.

### V4c — Notas de crédito y de débito (rama `feature/ventas-v4c-notas`)

Decisiones (18/11/2026):
- **Nota de crédito**: elegida por el usuario. Se arma con líneas del CCF y dos motivos por línea: la
  cantidad devuelta (devolución sin mover inventario) o el monto rebajado (descuento o corrección de precio).
  No pasa del saldo de cada línea ni del CCF.
- **Retención y percepción**: el usuario pidió investigarlo. El Manual Funcional V2.0 (sección XVIII, ejemplo
  «Ajuste con NCE a CCFE con Descuento Global y Retención», pp. 46-47) resuelve así: el CCF retuvo 1 %
  ($6.98 de $697.50) y la NC que acredita $90 gravados lleva «IVA Retenido» $0.90 (1 %), en la línea y en el
  resumen. **La nota repite la regla del CCF sobre su propio monto gravado**: si el CCF retuvo o percibió,
  la nota también, con la misma tasa y aunque la nota sea menor de $100 (ajusta la operación original).
  Los esquemas `fe-nc-v4` y `fe-nd-v4` traen `ivaRete` e `ivaPerci` por línea y en el resumen.
- **Descuentos**: en el mismo ejemplo, el descuento por ítem de la NC lleva el descuento del ítem más el
  descuento global prorrateado del CCF. La NC acredita al precio neto con el que se vendió.
- **Nota de débito**: el usuario pidió investigarlo y decidir. El Código Tributario, art. 110, la usa «por las
  cantidades que aumentan tanto los valores como el impuesto antes documentado»: ajustes de precio al alza,
  intereses devengados, cargos u otras modificaciones. Decisión: **cargos sobre el CCF**, uno o varios
  (descripción, cantidad, precio y si es gravado, exento o no sujeto). Cada cargo puede partir de una línea
  del CCF (un ajuste de precio) o ser libre (intereses, flete). No tiene tope de saldo y lleva la misma
  retención y percepción del CCF.
- **Plazo**: la NC se emite hasta 3 meses desde la fecha del CCF (Normativa 2.0, anexo IV, campo 17,
  regla 2c; CT art. 111: «los ajustes a las ventas que rebajen el débito fiscal deben hacerse dentro del plazo
  de tres meses»). Ese plazo limita los ajustes que rebajan, así que la ND no se bloquea: queda anotado para
  que lo confirme el contador.
  - **Revisado el 19/11/2026, a pedido del usuario**: la Normativa 2.0, anexo IV, campo 17, regla 2c (pág. 104) dice
    «Si se genera NCE **o NDE** relacionando un CCF o CR, la NC o ND deberá generarse a más tardar dentro de
    3 meses en relación a la fecha de generación del CCF o CR, salvo las excepciones legales». La ley sola no lo
    exige para la ND (CT arts. 110 y 111; Ley IVA art. 62 num. 2 suma incrementos e intereses sin plazo; art. 63
    da al comprador tres períodos desde la emisión de la ND), pero Hacienda valida la regla al recibir el DTE.
    **Decisión del usuario (19/11/2026): se aplica el mismo plazo a la ND.** `note_deadline` y
    `require_note_in_time` valen para las dos; la API expone `deadline`. Queda para el contador qué
    son las «excepciones legales» que menciona la regla.
- **Una nota relaciona un solo CCF**. La normativa admite hasta 50; se deja para después.
- Un CCF con una nota vigente no se invalida ni se corrige (Manual Funcional, regla 633: primero se invalida
  la nota). Una nota se anula (tipo 2) y no se corrige.
- Las notas heredan la clasificación de renta del CCF. Se envían por correo al cliente como los demás
  documentos y van como tipo 05 y 06 en el anexo de contribuyentes (V8).

Hechos verificados en el código:
- Servicio: `/v2/nota-credito` ya es multiemisor (copia del emisor, contingencia, 1 a 50 relacionados, solo
  CCF), pero manda `ivaRete` e `ivaPerci` en 0. `/nota-debito` es la ruta antigua: usa el emisor del entorno,
  no valida relacionados y no admite contingencia. El PDF ya trata 05 y 06 como documentos de venta.
- ERP: `sales_fiscal_documents` solo admite 01 y 03, y el índice del documento activo del pedido contaría la
  nota como otro documento vigente.

Pasos:
- [x] **Paso 0: plan y rama.**
- [x] **Paso 1: servicio.** NC con `ivaRete` e `ivaPerci` por línea (tasas que manda el ERP). Ruta
  `/v2/nota-debito` multiemisor como la NC (copia del emisor, relacionados validados, contingencia y escenarios
  simulados). Verificar: pruebas del servicio, esquema y PDF de las dos.
  - Hecho: NC y ND comparten `_construirNota` (dteBuilderNotas.js). El ERP manda
    `ajustes: { retencionIva, percepcionIva }` (booleanos); el servicio calcula el 1 % del gravado de la nota, lo
    reparte por línea en centavos y fija `totalPagar = operación + ivaPerci − ivaRete + no gravado`. La ND usa el
    mismo contrato (`documentosRelacionados`, `numeroDocumento` por línea) y agrega `numPagoElectronico: null`.
    Rutas `/v2/nota-debito` y `/nota-debito` (emisor del .env) con escenario simulado. La ND se anula con tipo 2
    (tipos 1 y 3 piden reemplazo). 493 pruebas del servicio en verde.
- [x] **Paso 2: migración 0133 y dominio.** Tipos 05 y 06 en el documento fiscal, con `related_document_id` (el
  CCF) y el motivo. El índice del documento activo y `invoiced()` cuentan solo 01 y 03. Dominio
  `sales_fiscal_notes.py`: saldo por línea y del CCF, plazo, prorrata del descuento global y retención y
  percepción espejo. Verificar: unitarias y prueba de migración.
  - Hecho: 0133 agrega `related_document_id` y `note_reason` (obligatorios en 05/06), la tabla
    `sales_fiscal_note_lines` (return/discount/charge, naturaleza, cantidad y monto neto) y el permiso
    `sales_invoices:notes`. El índice del activo, `active_for_order`, `latest_for_order` e `invoiced()` cuentan solo
    01 y 03. Dominio `sales_fiscal_notes.py`: líneas del CCF desde su `dte_json` con la prorrata en centavos del
    descuento global, saldo por línea, devolución al precio neto (las últimas unidades toman el saldo exacto),
    rebaja como línea «Rebaja: …» con cantidad 1, cargos de la ND, totales (IVA 13 %, retención y percepción del
    1 % si el CCF las tuvo), plazo de 3 meses, solicitud al servicio y conciliación.
- [x] **Paso 3: casos de uso, trabajador y API.**
  - `GET /sales/fiscal-documents/{id}/notes` (saldo por línea, plazo y notas);
  - `POST .../credit-note` y `.../debit-note`, con permiso `sales_invoices:notes`;
  - el trabajador emite 05 y 06;
  - el CCF con una nota vigente no se invalida ni se corrige;
  - correo al cliente.
  Verificar: e2e contra el servicio simulado.
  - Hecho: `application/sales_invoices/notes.py` (`overview`, `credit_note`, `debit_note`; bloquea el CCF,
    usa el emisor actual en el punto de venta del CCF y hereda su renta) y router `sales_notes.py`
    (`GET /{id}/notes`, `POST /{id}/credit-note`, `POST /{id}/debit-note`, con alcance de sucursal y auditoría
    `ISSUE_CREDIT_NOTE` / `ISSUE_DEBIT_NOTE`). El cliente DTE usa `/v2/nota-credito` y `/v2/nota-debito`; el
    trabajador concilia la nota con sus líneas y registra 05/06 como tipos del emisor. Invalidar o corregir un
    CCF con notas vigentes da `sales_invoice_has_notes`; anular una nota no cancela el pedido. `compose.yaml`
    habilita 01,03,05,06 en el servicio (`DTE_ALLOWED_DOCUMENT_TYPES`). E2e `test_sales_notes.py` (3) en verde.
- [x] **Paso 4: interfaz.** En el detalle de un CCF:
  - «Emitir nota de crédito»: líneas, devolución o rebaja, saldo y total;
  - «Emitir nota de débito»: cargos;
  - las notas del CCF y el enlace de cada nota a su CCF;
  - en la bandeja, los tipos 05 y 06.
  Verificar: vitest.
  - Hecho: `FiscalNotesPanel.svelte` en el detalle de un CCF (saldo por línea, plazo, retención, notas con
    enlace y formularios de NC y ND con total estimado de `note-calc.ts`). El detalle de una nota enlaza su CCF y
    muestra el motivo; la anulación de una nota no ofrece «Corregir» y la del CCF se bloquea con notas vigentes.
    La bandeja filtra y nombra 05 y 06 (`FISCAL_DOCUMENT_LABELS`). Vitest de ventas (73), svelte-check y eslint
    en verde.
- [x] **Paso 5: documentación.**
  - Hecho: manual de facturación (4.2 y permisos), `docs/api.md`, `docs/database-schema.md` (sección 43)
    y `dte-service/README.md` (retención en las notas y `/v2/nota-debito`).
- [x] **Paso 6: verificación y PR.**
  - Batería completa en verde (backend 2034, OCR 5, servicio 493, frontend 1209, ruff, mypy, svelte-check,
    eslint y build). Con el plazo de la ND se repitieron las e2e de notas e invalidaciones, las unitarias y el
    vitest de ventas (75), en verde.
  - QA en el navegador con Grupo Lorena: CCF simulado de $21.92 (pedido PED-20261119-6E4D46D5); NC por 50
    unidades ($5.48, saldo a $14.55); ND con cargo sobre la línea y flete exento ($5.26); sin diferencias de
    totales y con correo al cliente; anulación del CCF bloqueada con notas vigentes; al anular la NC el saldo
    vuelve a $19.40. Modo oscuro y claro a 375 px sin desbordes.

### V4d — Nota de remisión al despachar traslados (rama `feature/ventas-v4d-remision`)

Decisiones (24/11/2026, el usuario dijo «continúa» con PR #58 en develop, sobre la propuesta del 19/11):
- **V4d se parte en dos PR**, como V4b y V4b2: **V4d** la nota de remisión de traslados y **V4d2** el evento de
  retorno. Son flujos distintos (inventario frente a factura) y cada uno toca servicio, base, trabajador e
  interfaz.
- Se sigue la investigación del 19/11 (abajo): una NR por traslado al despachar, título CAT-025 04
  «Traslado», receptor la misma empresa con la dirección del establecimiento destino; recepción parcial y
  diferencias no cambian la nota.
- **Emisor**: el establecimiento fiscal de la sucursal de la bodega de origen y su primer punto de venta activo.
  Si la empresa habilitó el 04 y el origen no tiene establecimiento con punto de venta, el despacho se rechaza
  (`transfer_remission_issuer_missing`) con el motivo a la vista.
- **Valores**: cada línea al costo promedio del kardex al despachar, como gravada (la NR no causa IVA; el tributo
  20 queda informativo en el resumen). Queda anotado para que lo confirme el contador.
- **Transporte**: placa, vehículo y conductor en `observaciones` del resumen (el esquema no trae transporte).
- El despacho y la NR pendiente se guardan en la misma transacción; el trabajador la transmite. Si no se pudo
  crear, no hay despacho. Rechazada: el traslado ofrece «Emitir de nuevo» con los datos del despacho.
- **Corrección**: invalidación tipo 1 con una NR de reemplazo armada con los datos del despacho y el catálogo
  actual. Tipo 2 no se ofrece: un traslado despachado no se cancela (se resuelve con incidencias y ajustes).
- La NR no se envía por correo ni lleva clasificación de renta.

Hechos verificados en el código:
- Servicio: `/nota-remision` es la ruta antigua (emisor del `.env`, sin escenarios simulados ni contingencia);
  `construirNotaRemision` no usa el emisor de la solicitud. El PDF ya trata 04 como documento de venta.
- ERP: `sales_fiscal_documents.sale_id` es obligatorio y el trabajador, la bandeja y el detalle suponen pedido.
  Hay un establecimiento por sucursal (`uq_fiscal_establishments_branch`) y la empresa habilita tipos en
  «Documentos» (`DOCUMENT_TYPES` ya trae 04).

Pasos:
- [x] **Paso 0: plan y rama.**
- [x] **Paso 1: servicio.** `/v2/nota-remision` multiemisor como la NC: copia del emisor con establecimiento y
  punto de venta, contingencia y escenarios simulados; receptor y `bienTitulo` de la solicitud; `observaciones`.
  PDF con «Título: Traslado» y observaciones. Verificar: pruebas del servicio, esquema y PDF.
  - Hecho: `construirNotaRemision` (dteBuilderNotas.js) con emisor v2 o del entorno, contingencia, receptor
    validado, `bienTitulo` de CAT-025, relacionados opcionales y `observaciones`; totales como el CCF (IVA
    informativo, `montoTotalOperacion = subTotal + IVA`). Rutas `/v2/nota-remision` y `/nota-remision` con
    escenario simulado. El PDF muestra «Título de los bienes» en vez de la condición. `compose.yaml` habilita 04.
    Servicio: 501 pruebas en verde. Para correr las pruebas del servicio sin npm (el registro falla por TLS),
    copiar `package.json`, `src` y `test` al contenedor `dte-service`, enlazar `/app/node_modules` y
    correr `env -i PATH=... node --test` (la clave de API del contenedor pisa la de las pruebas).
- [x] **Paso 2: migración 0137 y dominio.** `sale_id` opcional y `transfer_id` (FK compuesta al traslado), con
  CHECK: 04 lleva traslado y no pedido; 01/03/05/06 llevan pedido. Índice único de NR vigente por traslado.
  Dominio `transfer_remission.py`: líneas desde lo despachado con costo, receptor, observaciones y solicitud.
  Verificar: unitarias y prueba de migración.
  - Hecho: 0137 (`transfer_id`, `sale_id` opcional, `ck_sales_fiscal_documents_origin`, índice
    `uq_sales_fiscal_documents_active_transfer`, guarda del downgrade). El repositorio une pedido y cliente con
    `outerjoin` y trae `transfer_code`; `active_for_transfer` y `latest_for_transfer`.
    `FiscalDocument.order_id()` exige el pedido en las acciones de pedido (`sales_invoice_not_an_order_document`);
    reintentar una NR fallida mira la vigente del traslado. Dominio `transfer_remission.py` (líneas al costo,
    receptor = la empresa en el destino, observaciones del transporte, solicitud y conciliación por
    `montoTotalOperacion`). Pruebas: `test_transfer_remission.py` (5) y
    `test_sales_transfer_remission_migration.py`; unitarias de ventas y e2e de facturas y notas en verde.
    La base de desarrollo ya está en 0137.
- [ ] **Paso 3: despacho, trabajador y API.** Al despachar, si la empresa habilitó 04: crear la NR pendiente y
  encolarla. El trabajador emite 04 sin pedido (sin correo ni renta). `GET /inventory/transfers/{id}/remission`,
  `POST .../remission/retry` (rechazada) y corrección tipo 1 desde el documento. Verificar: e2e contra el
  servicio simulado.
- [ ] **Paso 4: interfaz.** Tarjeta «Nota de remisión» en el traslado (estado, número, PDF, «Emitir de nuevo»);
  la bandeja y el detalle del documento muestran el 04 con enlace al traslado y sin correo ni notas. Verificar:
  vitest.
- [ ] **Paso 5: documentación.** Manual de traslados y de facturación, `api.md`, esquema y README del servicio.
- [ ] **Paso 6: verificación y PR.** Batería completa, QA en el navegador, PR con Auto-fix y auto-merge.

### V4d2 — Evento de retorno (se detalla al empezar)
- Sobre facturas (01) selladas, como la NC: líneas de la factura, cantidad devuelta y saldo; plazo de 3 meses
  desde el sello; IVA incluido. Varios eventos por factura mientras no pasen de lo vendido (Manual Funcional
  §X, condición 4); cada evento relaciona una factura.
- Tipo 18 de CAT-002: el esquema `fe-eret-v1` no trae número de control. **Por confirmar** el endpoint de
  Hacienda (el Manual Técnico disponible no tiene texto extraíble): se supone `recepciondte` con `tipoDte` 18,
  como sugiere el Manual Funcional (modelo diferido y contingencia); se prueba contra el stub y se confirma en
  la certificación.
- Una factura con un retorno vigente no se invalida ni se corrige; el retorno se invalida con tipo 2.

Detalle original de V4d (antes de partirlo):
- Nota de remisión (04) al despachar un traslado, si la empresa habilita el tipo; queda vinculada al traslado.
- Evento de retorno sobre facturas selladas: el servicio tiene el esquema pero no el generador. Hasta 50
  documentos del mismo tipo; una factura con un evento de retorno vigente no se invalida sin invalidar antes
  el evento.
- Plantillas PDF que falten.

Investigación del 19/11/2026 (pedida por el usuario). Propuesta pendiente de su confirmación:
- **Evento de retorno = como la NC, con tres diferencias.** Fuentes: Normativa 2.0, regla 13.3 (págs. 31-32),
  Manual Funcional V2.0 §X, esquema `fe-eret-v1`. Se arma con las líneas de la factura tal como se selló, la
  cantidad devuelta por línea y el saldo (los retornos vigentes no pasan de lo vendido: «no deberá exceder al
  valor de lo vendido»; «los bienes … retornados deberán individualizarse»). Diferencias con la NC:
  1. **Solo devolución por cantidad**, sin rebaja por monto: «El retorno no constituye un descuento».
  2. **Plazo de tres meses desde el sello** de la factura (la NC cuenta desde la fecha del CCF).
  3. **Montos con IVA incluido** (estilo factura: `ivaItem`, `ivaRete`) y sin efecto en el crédito fiscal del
     receptor; reduce la venta y el débito fiscal del emisor (13.3.2).
  Además: aplica a FE (también FEXE y FSEE, que el ERP no emite); un evento por factura (la norma admite 50);
  no se ajusta con otro evento ni documento; se invalida con el evento de invalidación; la factura con un
  retorno vigente no se invalida ni se corrige. El cambio de producto exige una factura nueva (Manual §X).
  Solo fiscal en V4d, como las notas; el enlace con las devoluciones físicas de B08 (`sales_returns`) llega en V8.
- **Una nota de remisión por traslado, al despachar.** CT art. 109 inciso 4 («traslados que no constituyan
  transferencias»), Decreto 487 (requisitos de la NRE) y plan de Ventas 6.8. Título CAT-025 04 «Traslado»;
  emisor: establecimiento de origen; receptor: la misma empresa con la dirección del establecimiento de
  destino; líneas: lo despachado; placa y conductor en observaciones o apéndice (el esquema no trae
  transporte). Vale para las tres rutas (distribución, entre sucursales y retorno a matriz).
  - **Recepción parcial, averías, sobrantes y faltantes no cambian la nota**: ampara la circulación de lo que
    salió, no transfiere propiedad ni causa IVA, y no admite notas de crédito o débito (solo se relacionan con
    CCF o CR). Las diferencias se resuelven en el traslado (ajustes que ya existen).
  - **Error en la nota** (cantidades o datos mal despachados): invalidación tipo 1 con una NR de reemplazo;
    **traslado cancelado** después de emitirla: invalidación tipo 2. Plazo: décimo día hábil del mes siguiente.
  - El despacho no se confirma si la nota no se pudo generar (o queda en contingencia).
- **Entregas de venta: no en V4d.** CT art. 109 inciso 1 exige NR cuando la mercadería sale **antes** del CCF
  (y la Normativa, regla 2a del campo 17, deja que FE, CCFE o FEXE relacionen la NR, emitiéndose en el mismo
  período o hasta 3 días después). Si se factura antes de entregar, el DTE de venta ampara el tránsito y no hace
  falta NR. Hoy el ERP permite confirmar una entrega sin factura. El plan de Ventas lo deja en el módulo
  «Entregas y despacho»: NR título 02 «Propiedad» si la entrega sale sin factura, y control del plazo para
  facturar relacionándola.

### V4e — Lote de certificación (se detalla al empezar)
- Pantalla por empresa: cuántos documentos pide Hacienda por tipo, cuántos van transmitidos y aceptados, y
  cuáles fueron rechazados con su motivo.
- Generación del lote con datos de prueba, transmisión y avance; probado contra el stub.

## Estado actual

- **Paso en curso**: V4d paso 3 (despacho, trabajador y API). Pasos 1 y 2 hechos. PI terminado y en develop (#58); V4c en develop (#57).
Tras cambiar el servicio DTE:
  `docker compose up -d --build dte-service` (también toma `DTE_ALLOWED_DOCUMENT_TYPES`).
  - Paso 5: batería completa en verde (backend 2014, OCR 5, servicio 489, frontend 1200, ruff, mypy,
    svelte-check, ESLint y el build). QA en el navegador con Grupo Lorena: en Actividades se guardó para la
    principal (10712) «Gravada · Actividades industriales» como valor de demostración; el contador debe
    confirmarlo. El detalle del documento muestra «Clasificación de renta (F-07)»; los anteriores salen sin
    clasificar. El formulario de facturar lo cubre vitest (Grupo Lorena no tiene un pedido sin facturar).
  - Pasos 2 y 3 hechos: la sugerida sale de la actividad del establecimiento (o la principal); `invoice` valida
    el par; el reemplazo hereda la del original. Interfaz: `RentaFields.svelte` (dos selectores) en
    Actividades («Guardar renta») y en la sección Factura (Facturar se deshabilita sin clasificación
    completa); el detalle muestra «Clasificación de renta (F-07)». `renta-labels.ts` con los catálogos.
  - Cuidado: `prettier --write` sobre carpetas enteras reformatea muchos archivos ajenos; usarlo solo sobre
    los archivos tocados.
  después de V4b2.
  - Paso 8:
    - Batería completa: backend 2002 en verde y 1 roja, `test_sales_fiscal_documents_migration` (0126), que
      todavía esperaba que un rechazado bloqueara volver a facturar. Se ajustó a la regla de la 0131 y pasa.
    - Etapas que no corrieron en la batería, corridas aparte: OCR 5, servicio 489, frontend (191 archivos),
      ruff, mypy, svelte-check, ESLint y el build. Todo en verde.
  - QA en el navegador ya hecha con Grupo Lorena (simulado): «Corregir documento» en
    DTE-01-M001P001-000000000000001 (pedido PED-20261117-63FB7EB4). Se emitió el reemplazo …0002, el
    original quedó invalidado y salió el «Aviso de anulación» (Mailpit). La sección Factura del pedido
    muestra el reemplazo y ofrece «Cancelar pedido» con el solicitante (abierto, sin enviar). 375 px sin
    desborde.
  - La QA encontró dos textos y ya están corregidos (commit «Paso 8 (QA)»): un documento invalidado ahora
    dice «Se invalidó y lo reemplaza…» y su sección de correo explica que ya no se envía. vitest: ventas
    65 en verde.
  - La base de desarrollo ya está en 0131.
  - Paso 7 hecho: `api.md` («Invalidation and correction»), esquema §41, manual de facturación §4.1 y
    `multiemisor.md` («Invalidación por emisor»).
  - Paso 6 hecho:
    - `FiscalInvalidationPanel.svelte` en el detalle del documento:
      - plazo, o el aviso de que venció;
      - «Corregir documento» y «Anular documento», con el solicitante y, al anular, el motivo;
      - historial con estado, sello y error;
      - vínculos al reemplazo y al original.
    - Pedido: «Cancelar pedido» también en uno facturado y sellado, con los permisos `sales:cancel` y
      `sales_invoices:invalidate`. Pide el solicitante, anula con `cancel_order` y el pedido se cancela al
      aceptarse. `onInvoiced` ahora entrega el documento vigente.
    - `invoice-options` devuelve `previous_document` (el último del pedido) cuando no hay uno vigente. La
      sección Factura muestra el rechazo con las observaciones de Hacienda, o la anulación, y deja facturar
      de nuevo.
    - Bandeja: estado «Invalidado» y su filtro. Los envíos muestran «Aviso de anulación». La pantalla de
      contingencia dice «Responsable fiscal».
    - vitest: `FiscalInvalidationPanel.test.ts` (3); ventas: 64 en verde.
  - Paso 5 hecho:
    - `sales_fiscal_document_emails.invalidation_id` (en la 0131): el aviso es un envío automático aparte,
      uno por invalidación aceptada.
    - `compose_invalidation`: el asunto «Anulación de …», el reemplazo si lo hay y, si no, el motivo; marca
      de simulado. Adjunta el PDF del evento, que se pide al servicio en el momento del envío.
    - Servicio: `/api/dte/eventos/:codigo/pdf/render` también arma el PDF de un evento simulado.
    - La API de envíos expone `invalidation_id`; la interfaz lo muestra como «Aviso de anulación».
  - Pasos 3 y 4 hechos en un mismo commit (la API de corrección necesita al trabajador):
    - `FiscalInvalidationUseCases` (`application/sales_invoices/invalidation.py`):
      - `invalidate`: tipo 2, con motivo, solicitante y `cancel_order`, que además pide `sales:cancel` y que
        el pedido se pueda cancelar;
      - `correct`: crea el reemplazo con `SalesInvoiceUseCases.prepare_replacement`, que exige el mismo tipo
        de documento, y la invalidación tipo 1;
      - antes de crear: plazo vigente (`sales_invoice_invalidation_expired`) y responsable fiscal registrado
        (`sales_invoice_responsible_missing`).
    - La FK `superseded_by_id` es diferible: el original se marca antes de insertar su reemplazo.
    - Trabajador `process_fiscal_invalidation` (tarea `invalidate_fiscal_document`):
      - una corrección espera el sello del reemplazo sin gastar intentos;
      - si el reemplazo falla o lo rechazan, la solicitud falla y se suelta `superseded_by_id`;
      - al aceptarse, el documento queda `invalidated` y, si `cancel_order`, se cancela el pedido con la
        bitácora `SALES_ORDER_CANCELLED`;
      - al sellarse un reemplazo se encola enseguida la invalidación de su original, y la conciliación
        retoma las pendientes.
    - Cliente: `invalidation_window`, `invalidate` (INVALIDATION_REJECTED como rechazo y no como error) e
      `invalidation_pdf`.
    - API `/sales/fiscal-documents/{id}/invalidation` (GET), `/invalidate` y `/correct` (202). Bitácora:
      `REQUEST_INVALIDATION`, `CORRECT_FISCAL_DOCUMENT`, `FISCAL_DOCUMENT_INVALIDATED` y
      `FISCAL_INVALIDATION_REJECTED`/`FAILED`.
    - e2e `test_sales_invalidations.py` (5) contra el servicio simulado.
  - Paso 2 hecho:
    - Migración 0131 según el plan. El downgrade también se niega si un pedido tiene más de un documento no
      fallido (uno rechazado y otro posterior no cabrían en el índice anterior).
    - `ACTIVE_STATUSES` ya no incluye `rejected`. `active_for_order` y `invoiced()` cuentan solo pendiente,
      contingencia, emitido y simulado sin reemplazo en curso.
    - Dominio `sales_fiscal_invalidation.py`: `require_invalidatable`, `require_correctable`, `validate_reason`
      (5 a 200 caracteres) y `validate_requester`. `validate_responsible` acepta el código de error y sus
      mensajes ya son neutros.
    - Repositorio `SqlAlchemySalesFiscalInvalidationRepository` (crear, buscar, guardar, tomar con
      `SKIP LOCKED` y pendientes).
  - Paso 1 hecho: `/anular` y `/invalidacion` usan el proveedor simulado con un emisor simulado, en
    cualquier despliegue (respuesta `SIMULADO_INVALIDADO`, sin Hacienda ni firmador). Se actualizó la prueba
    que esperaba 409 en simulado. Servicio: 489 en verde.
  - V4a mergeado (#53). Un colaborador mergeó la #54: cada push a develop se mezcla sola en
    `feature/ai-bedrock-guardrails` y desde esa rama se despliega a EC2.
  - Paso 7:
    - Batería completa en verde: backend 1990, OCR 5, servicio 488, frontend 1193, más ruff, mypy,
      svelte-check, ESLint y el build.
    - QA en el navegador con Grupo Lorena (simulado): registrar al responsable; activar la contingencia
      de S001 (aviso en la bandeja); cerrarla con confirmación («se informó el evento»); 375 px sin
      desborde; modo claro y oscuro.
    - Hallazgo: las e2e comparten el servicio DTE de desarrollo, y su empresa tiene el mismo NIT que
      Grupo Lorena. Las primeras corridas fallidas dejaron ventanas abiertas (M4xx); se cerraron desde
      la pantalla y quedan en el historial. La e2e ahora cierra sus ventanas con el fixture
      `opened_windows`, aunque falle.
    - El PR #52 (actor nulo en las existencias de prueba) ya está en develop.
  - Paso 6 hecho: `docs/api.md` («Billing contingency»), esquema §40, manual de facturación §5
    «Contingencia» (las secciones siguientes se renumeran) y `dte-service/docs/multiemisor.md`.
  - Paso 5 hecho:
    - Pantalla `/sales/contingencies` (menú Ventas → «Contingencia», con `sales_invoices:read`) y
      `ContingencyPanel.svelte`:
      - ventanas abiertas con su estado, documentos, plazo y último error;
      - «Activar contingencia» (establecimiento, tipo de CAT-005 y motivo), «Cerrar contingencia» con
        confirmación e «Informar evento»;
      - responsable del evento (nombre y documento de CAT-022) e historial reciente.
      Sin `sales_invoices:contingency` la pantalla es de solo lectura.
    - Bandeja: estado y filtro «En contingencia», y un aviso cuando hay establecimientos en contingencia.
    - Detalle: nota «Generado en contingencia» con el tipo y el motivo, y si ya se transmitió.
    - `formatMoment` (DD/MM/YYYY HH:mm, hora de El Salvador).
    - vitest: `ContingencyPanel.test.ts` (5), más navegación y bandeja.
  - Paso 4 hecho:
    - API `/sales/contingencies`: GET (`sales_invoices:read`; ventanas, responsable y `active`); POST para
      activar (`establishment_id`, `contingency_type` de CAT-005, `reason`, obligatorio para el tipo 5);
      `/{id}/close`, `/{id}/event` y PUT `/responsible`, todo con `sales_invoices:contingency`.
      Bitácora: `ACTIVATE_CONTINGENCY`, `CLOSE_CONTINGENCY`, `SEND_CONTINGENCY_EVENT` y CREATE/UPDATE
      del responsable.
    - Decisión: el responsable del evento es uno por empresa, en la tabla `company_contingency_responsibles`
      (en la misma 0130, que todavía no está mergeada). El ERP lo entrega al servicio en cada registro, al
      emitir y antes de cada acción de contingencia.
    - `ContingencyUseCases` registra a la empresa (modo, credenciales y responsable) antes de activar,
      cerrar o reenviar. Los códigos del servicio se traducen a `sales_contingency_*`.
    - Servicio: el PDF ya se entrega en CONTINGENCIA y CONTINGENCIA_REPORTADA, con el sello «Pendiente:
      documento generado en contingencia» (el Manual pide entregar la versión legible).
    - Pruebas: unitarias `test_fiscal_contingency.py` y e2e `test_sales_contingencies.py`, contra el
      servicio real en simulado (activar, facturar en contingencia, cerrar, seguir hasta `simulated`).
  - Arreglo aparte: el CI de develop tras V3d falló de forma intermitente porque el ayudante `_stock` de
    `test_sales_orders.py` tomaba como actor un registro de la bitácora del trabajador DTE, que no tiene
    usuario. Va en la PR #52 (`fix/e2e-actor-sin-usuario`) y el mismo cambio en esta rama.
  - Paso 3 hecho:
    - Migración 0130: estado `contingency` y columnas `contingency_type` (CAT-005), `contingency_reason` y
      `contingency_at`. Un documento en contingencia exige número, código de generación y `issued_at`.
      La 0130 también crea el permiso `sales_invoices:contingency`. El downgrade se niega si hay documentos
      generados en contingencia.
    - `service_status`: CONTINGENCIA y CONTINGENCIA_REPORTADA se traducen a `contingency`. `dte_worker`
      guarda el JSON y el PDF, el tipo y el motivo (`contingency_details`) y lo audita como
      `FISCAL_DOCUMENT_CONTINGENCY`. Antes, un documento así se reintentaba hasta quedar FAILED.
    - Seguimiento: `follow_contingency_document` (tarea arq `follow_fiscal_contingency`, encolada por
      `reconcile_fiscal_documents`) consulta `GET /api/dte/:codigo` (`DteService.document_state`). Con el
      sello vuelve a bajar el JSON y el PDF y pasa a `issued` o `simulated`; si Hacienda lo rechaza, a
      `rejected`. Nunca vuelve a emitir.
    - Correo: el automático sale al quedar en contingencia, con el aviso `CONTINGENCY_NOTE`, y no se repite
      al sellarse (se puede reenviar a mano). Un documento simulado se marca como tal también en contingencia.
    - Facturar de nuevo un pedido con un documento en contingencia devuelve ese mismo documento.
    - Pruebas: unitarias, `test_sales_fiscal_contingency_migration.py` y e2e `test_fiscal_contingency.py`.
  - Paso 2 hecho:
    - Rutas `/api/emisores/:nit/contingencias`: GET; POST con `establecimiento`, `tipoContingencia` y
      `motivoContingencia`; y `/:id/cerrar`, `/:id/evento` y `/:id/transmitir`, con el alcance `contingency`. Una
      ventana de otro emisor da 404, y un emisor sin registrar, `ISSUER_NOT_FOUND`.
    - Decisión: la activación por emisor es manual (`forzar({ manual: true })`) y vale en cualquier modo. La
      activa el operador de la empresa ante una falla que el servicio no ve (energía, internet de la tienda);
      el ERP la audita. Las rutas globales siguen pidiendo `DTE_ALLOW_FORCED_CONTINGENCY` para la certificación.
    - Emisor simulado: la contingencia funciona sin Hacienda. El documento nace en diferido con firma simulada
      y responde 202 `CONTINGENCIA`. Al cerrar, el evento se construye y se valida contra el esquema, recibe un
      sello simulado, los documentos pasan a `SIMULADO` y la ventana a `COMPLETADA`.
    - `cerrarEInformar` usa el responsable enviado o el registrado; sin ninguno, la ventana queda `CERRADA`.
    - Pruebas: `contingenciaPorEmisor.test.js` (4) y `contingenciaSimulada.test.js`. Servicio: 488 en verde.
  - Paso 1 hecho:
    - `contingencias` tiene `nit_emisor` y `cod_establecimiento` ('' = emisor heredado), con un índice único
      de ventana activa por los dos. Las ventanas viejas toman el NIT y el `codEstable` de sus documentos.
    - El establecimiento es el `codEstable` interno (por ejemplo M001): antes de construir el documento sale de
      `body.emisor.codEstable` y, después, del documento.
    - El sondeo recorre cada ventana automática y el evento se envía dentro del contexto de su emisor
      (`conEmisor`). Ya no queda ningún uso de `config.emisor` en `contingenciaService`.
    - Decisión: un solo responsable del evento por empresa (`responsable` en `PUT /api/emisores/:nit`, columna
      `responsable_json`). Si no se envía el campo se conserva; si se envía null, se quita. El emisor heredado
      sigue usando `MH_RESPONSABLE_*`. Sin responsable, el evento espera a que el operador lo envíe.
    - `estadoGeneral({ nit })` filtra por emisor. Las rutas globales `/api/dte/contingencia` siguen sirviendo
      al emisor del entorno; el Paso 2 las pasa a ser por emisor.
    - Prueba nueva: `test/integration/contingenciaPorEmisor.test.js`. Servicio: 486 en verde.
- **Contexto**:
  - V3 completo en `develop`: #48 a #51.
  - En desarrollo `DTE_MODE` es simulado y el `.env` no tiene `DTE_CREDENTIALS_KEY`.
  - CVE-2026-112366 de picomatch está ignorada en `.trivyignore` hasta el 31/01/2027.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` siempre con un objetivo explícito (`dte`, `backend`, `frontend`,
    `lint`). Sin objetivo corre la batería completa: 35 a 45 minutos, y se detiene si falla el backend.
  - Mientras corre la batería: no hacer commits, no correr pruebas de base y no agregar migraciones.
  - Git: `git -c http.sslBackend=schannel` para `fetch` y `push`.
  - Si el login de desarrollo da 500 o una pantalla nueva no aparece, reiniciar `frontend`. Después de
    cambiar `dte-worker`, reiniciarlo.

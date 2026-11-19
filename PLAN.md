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
- Siguen vigentes:
  - merge delegado con los checks propios en verde, con Auto-fix y auto-merge (merge) en cada PR;
  - commits y PR sin atribución;
  - ignorar el check de Vercel;
  - el `.env` no se lee ni se toca sin un «sí» explícito del usuario.

## Bloques

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

### V4c — Notas de crédito y de débito (se detalla al empezar)
- Se emiten desde un CCF sellado: devolución sin mover inventario, descuento posterior o anulación parcial
  (nota de crédito), y cargo adicional (nota de débito).
- Saldo del CCF, plazo legal, documento relacionado y plantillas PDF para los tipos 05 y 06.

### V4d — Nota de remisión y evento de retorno (se detalla al empezar)
- Nota de remisión (04) al despachar un traslado, si la empresa habilita el tipo; queda vinculada al traslado.
- Evento de retorno sobre facturas selladas: el servicio tiene el esquema pero no el generador. Hasta 50
  documentos del mismo tipo; una factura con un evento de retorno vigente no se invalida sin invalidar antes
  el evento.
- Plantillas PDF que falten.

### V4e — Lote de certificación (se detalla al empezar)
- Pantalla por empresa: cuántos documentos pide Hacienda por tipo, cuántos van transmitidos y aceptados, y
  cuáles fueron rechazados con su motivo.
- Generación del lote con datos de prueba, transmisión y avance; probado contra el stub.

## Estado actual

- **Paso en curso**: V4b2 terminado; falta el merge de su PR. Sigue V4c (detallarlo al empezar).
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

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
- [ ] **Paso 5: interfaz.**
  - En la bandeja de documentos: estado «En contingencia» y filtro.
  - Pantalla «Contingencia», con las ventanas por establecimiento (activa o cerrada), sus documentos, el
    estado del evento y el plazo de 24 h para el evento y de 72 h para los documentos.
  - Acciones «Activar contingencia» y «Cerrar contingencia».
  - Aviso en la bandeja cuando hay una ventana activa.
  - Verificar: vitest con estados de carga, vacío y error.
- [ ] **Paso 6: documentación.** `api.md`, esquema, manual de documentos fiscales y `multiemisor.md`.
- [ ] **Paso 7: verificación y PR.**
  - Batería completa y QA en el navegador: forzar la contingencia en simulado, emitir, cerrar y ver el sello.
  - PR hacia `develop`.

### V4b — Invalidación y rechazos (se detalla al empezar)
- Invalidar documentos con un evento firmado y sus plazos (tres meses para 01, 11 y 14; décimo día hábil del
  mes siguiente para 03, 04, 05, 06 y 07). Tipos de invalidación del catálogo: error en datos con documento
  de reemplazo, rescindir la operación, y otro.
- «Rechazado: corregir y reenviar»: ver las observaciones de Hacienda, corregir los datos del cliente o del
  pedido y emitir un documento nuevo.
- Cancelar un pedido facturado: invalidar primero y después cancelar.
- Estado «Invalidado» en la bandeja, PDF del evento y correo al cliente.

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

- **Paso en curso**: 5 de V4a (interfaz: bandeja y pantalla «Contingencia»).
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

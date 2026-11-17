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
- [ ] **Paso 1: ventana por emisor y establecimiento en el servicio.**
  - Migración SQLite: `contingencias` gana `nit_emisor` y `cod_establecimiento`; el índice único de ventana
    activa pasa a ser por (NIT, establecimiento). Las filas viejas toman el emisor del entorno, si existe.
  - `ventanaActiva`, `abrirVentana` y `vincular` usan el emisor y el establecimiento del documento.
  - Se quitan los 3 usos de `config.emisor`: el NIT sale del contexto del emisor del documento o de la ventana.
  - El responsable del evento sale del registro del emisor; el ERP lo envía al registrar a la empresa.
  - Verificar: pruebas nuevas con dos empresas, y un establecimiento en contingencia mientras otro de la misma
    empresa emite normal; `./scripts/run-tests.sh dte`.
- [ ] **Paso 2: rutas de contingencia por emisor.**
  - `/api/emisores/:nit/contingencias` para listar, forzar con tipo y motivo, cerrar, enviar el evento y
    transmitir, con el alcance `contingency`.
  - Las rutas globales quedan para el emisor del entorno, o se retiran si nada las usa.
  - En simulado, la contingencia se simula (el escenario se fuerza con `simulacion`) para poder probarla
    sin Hacienda.
  - Verificar: pruebas de integración del servicio.
- [ ] **Paso 3: estado «en contingencia» en el ERP.**
  - Migración: `sales_fiscal_documents` agrega el estado `contingency` y los campos de transmisión
    (`transmission_type`, `contingency_type`, `contingency_reason`, `contingency_window_id`).
  - Dominio: transiciones `pending → contingency → issued | rejected`. Un documento en contingencia ya tiene
    número de control y versión legible: se entrega al cliente, con el correo automático.
  - `dte_worker`:
    - el resultado CONTINGENCIA deja el documento en `contingency`;
    - una tarea de conciliación consulta su estado hasta el sello, sin volver a emitir.
  - Verificar: unitarias del dominio y e2e con el cliente DTE falso.
- [ ] **Paso 4: API y permisos.**
  - `GET /sales/contingencies`, `POST /sales/contingencies` (forzar por establecimiento, con tipo del
    catálogo CAT-005 y motivo) y `POST /sales/contingencies/{id}/close`.
  - Permisos `fiscal_documents:contingency` (nuevo) y auditoría.
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

- **Paso en curso**: 1 de V4a (ventana de contingencia por emisor y establecimiento en el servicio).
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

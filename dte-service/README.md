> **Servicio DTE de GestionaSV.** Este servicio se incorporó al ERP a partir del servicio DTE de un
> proyecto de referencia (bloque V3 del área de Ventas, `docs/plan-area-ventas-el-salvador.pdf`,
> secciones 6.4 y 6.5). En el ERP se vuelve multiemisor: cada empresa es un emisor aislado, con su
> modo, su numeración y sus documentos. Mientras dure esa adaptación, este README describe el
> comportamiento heredado; los cambios multiemisor se documentan en `docs/` del servicio.

# Microservicio DTE — Facturación Electrónica El Salvador

Microservicio Node.js/Express para emitir Documentos Tributarios Electrónicos
(DTE) contra el Ministerio de Hacienda (DGII) de El Salvador.

Esta versión fue verificada contra:
- **Manual Tecnológico para la Integración del Sistema de Transmisión V2.0**
  (Ministerio de Hacienda, 05/2026) — endpoints, payloads, códigos de error.
- **Catálogos – Facturación Electrónica V1.1** (Excel oficial, 07/2026) — los
  33 catálogos completos, generados directamente desde el archivo oficial
  (no transcritos a mano) en `src/config/catalogos.json`.
- **JSON Schemas oficiales reales** (`svfe-json-schemas`, paquete de Hacienda
  del 11/08/2026) — copiados sin modificar en `src/schemas/`, y usados en
  producción por `validators/dteSchema.js` (Ajv compila el schema real, no
  una aproximación). El objeto que arma `dteBuilder.js` para Factura y CCF
  fue probado y **valida exitosamente** contra estos schemas reales.
- **Código fuente real de SVFE-API-Firmador** (Java/Spring Boot) — para
  confirmar los nombres exactos de campos del servicio de firma.

> Que un JSON valide contra el schema (Ajv) solo prueba su **estructura**.
> Hacienda además valida cálculos, fechas y coherencia entre campos; esas
> reglas están implementadas en los builders y cubiertas por las pruebas
> (ver `DTE_AUDITORIA_HACIENDA.md` en la raíz del repositorio).

## Reglas fiscales y de transmisión implementadas

Contrastadas con el Manual Funcional y el Manual Técnico v2.0 (05/2026):

- **Factura (01)**: `precioUni` y ventas **con IVA incluido**, `tributos` en
  `null`, `totalIva` informativo (`venta × 0.13/1.13`) y
  `totalPagar = Sub-Total − ivaRete + totalNoGravado`.
- **CCF (03)**: montos **sin IVA**; tributo `20` = 13 % de
  `totalGravada − descuGravada` (holgura ±0.01) y
  `montoTotalOperacion = Sub-Total + IVA`.
- **Línea**: `cantidad × precioUni − montoDescu = venta` (±0.01) antes de
  reservar el correlativo; los `descu*` del resumen son descuentos
  **globales** y `subTotal = subTotalVentas − descu*`. `noGravado` sigue el
  MF XII (unidad 99, precio y ventas en 0).
- **Redondeo**: cuerpo a 8 decimales y resumen a 2 (mitad hacia arriba).
- **Fecha y hora** de emisión siempre en `America/El_Salvador`
  (`utils/fechaHoraSV.js`), independiente de la zona del contenedor; el
  número de control usa el correlativo del mismo año de `fecEmi`. Un
  documento nunca transmitido que se reanuda otro día actualiza
  `fecEmi/horEmi` (y el número de control si cambió el año).
- **Política de reintentos** (MT 3.3): sin respuesta en `MH_TIMEOUT_MS`
  (8 s) se **consulta** el estado; si Hacienda no lo tiene se reenvía como
  máximo 2 veces y, agotado eso, el documento pasa a **contingencia**. Un
  `RECHAZADO` (HTTP 400) es definitivo; "ya existe" (004) se resuelve
  consultando el mismo código. `idEnvio` es un correlativo propio de 32 bits.
- **Contingencia** (MF VIII): ver sección "Contingencia" más abajo.
- **Invalidación** (MF VII): ver sección "Invalidación" más abajo.
- **Errores de configuración** con código propio: `FIRMADOR_CONFIGURATION_ERROR`
  (803/809/812 del firmador) y `HACIENDA_AUTH_CONFIGURATION_ERROR`
  (credenciales del API rechazadas); el documento conserva su identidad y la
  misma `Idempotency-Key` lo reanuda al corregir la configuración.

## Invalidación

`POST /api/dte/:codigoGeneracion/anular` (scope `invalidate`, requiere
`Idempotency-Key`) construye el evento con los datos del **DTE histórico**
(emisor, establecimiento del número de control, receptor; en CCF tipo `36` +
NIT):

- Tipo 1 (error en la información) y 3 (otro): exigen
  `codigoGeneracionReemplazo`, un DTE ya transmitido con sello (salvo NC 05 y
  CL 08). Tipo 2 (rescindir): sin reemplazo. Tipo 3 exige `motivoAnulacion`.
- Fecha del evento: la de generación del DTE en CCF/NR/NC/ND/CR/CL/DCL/CD; en
  FE/FEX/FSE hoy, hasta 3 meses después de la generación.
- Plazos de transmisión: FE/FEX/FSE 3 meses desde el sello (se bloquea si
  venció); CCF y demás, décimo día hábil del mes siguiente (estimado con los
  asuetos nacionales más `DTE_DIAS_INHABILES`; solo advierte).
- El evento se persiste (`eventos`) antes de firmar: si Hacienda no responde
  (`502 INVALIDATION_NO_RESPONSE`), reintentar con la misma key reenvía el
  mismo evento. El DTE pasa a `INVALIDADO` solo con `PROCESADO` y sello.
- `GET /api/dte/:codigo/invalidacion` (fecha del evento y plazo),
  `GET /api/dte/:codigo/eventos` y `GET /api/dte/eventos/:codigo/json`
  (evento firmado + sello).

Body:

```json
{
  "motivo": {
    "tipoAnulacion": 2,
    "motivoAnulacion": "Devolución del producto",
    "responsable": { "nombre": "Juan Pérez", "tipoDocumento": "13", "numeroDocumento": "01234567-8" },
    "solicitante": { "nombre": "Ana López", "tipoDocumento": "36", "numeroDocumento": "06141804941035" }
  },
  "codigoGeneracionReemplazo": null
}
```

## Contingencia

1. **Momento 1**: agotada la política de reintentos se abre una ventana
   (tabla `contingencias`) y el documento pasa a modelo diferido
   (`tipoModelo 2`, `tipoOperacion 2`, `tipoContingencia` y motivo de la
   ventana) con el mismo código, número y fecha; se conserva la versión
   original por si Hacienda sí la había recibido. Con la ventana activa,
   las emisiones nuevas nacen en diferido y responden `202 CONTINGENCIA`.
2. **Momento 2**: el worker sondea a Hacienda (`DTE_CONTINGENCIA_SONDEO_MS`);
   al responder, cierra la ventana, concilia los documentos convertidos y
   envía el Evento de Contingencia (máx. 1000 documentos) con el
   responsable de `MH_RESPONSABLE_*`. Solo `RECIBIDO` con sello lo da por
   informado; plazo de 24 h desde el cese.
3. **Momento 3**: cada documento informado se transmite uno a uno sin
   cambiar sus campos de contingencia; plazo de 72 h desde el sello del
   evento.

Endpoints (scope `contingency`): `GET /api/dte/contingencia` (ventanas y
plazos), `POST /api/dte/contingencia/:id/cerrar`, `POST
/api/dte/contingencia/:id/evento` (body opcional `{ responsable }`), `POST
/api/dte/contingencia/:id/transmitir` y, solo en `hacienda-test` con
`DTE_ALLOW_FORCED_CONTINGENCY=true`, `POST /api/dte/contingencia/forzar`
(`{ tipoContingencia, motivoContingencia }`) para las pruebas de certificación.

## JSON Schemas oficiales integrados

`src/schemas/manifest.js` mapea cada tipoDte (y cada evento) a su archivo de
schema real y su número de versión, confirmado inspeccionando el `const` de
`identificacion.tipoDte` / `identificacion.version` de cada archivo:

| tipoDte | Documento | Archivo | Versión |
|---|---|---|---|
| 01 | Factura Electrónica | `v2/fe-f-v2.json` | 2 |
| 03 | Comprobante de Crédito Fiscal | `v4/fe-ccf-v4.json` | 4 |
| 04 | Nota de Remisión | `v4/fe-nr-v4.json` | 4 |
| 05 | Nota de Crédito | `v4/fe-nc-v4.json` | 4 |
| 06 | Nota de Débito | `v4/fe-nd-v4.json` | 4 |
| 07 | Comprobante de Retención | `v2/fe-cr-v2.json` | 2 |
| 08 | Comprobante de Liquidación | `v2/fe-cl-v2.json` | 2 |
| 09 | Documento Contable de Liquidación | `v2/fe-dcl-v2.json` | 2 |
| 11 | Factura de Exportación | `v3/fe-fex-v3.json` | 3 |
| 14 | Factura de Sujeto Excluido | `v2/fe-fse-v2.json` | 2 |
| 15 | Comprobante de Donación | `v2/fe-cd-v2.json` | 2 |

Eventos: `invalidacion-schema-v3.json` (v3), `contingencia-schema-v4.json`
(v4), `fe-eop-v1.json` (Operaciones Especiales, v1), `fe-eret-v1.json`
(Retorno, v1).

**`dteBuilder.js` implementa la construcción completa para Factura (01) y
CCF (03)**, incluyendo los detalles finos que solo aparecen leyendo el
schema real y que NO son intuitivos:
- El **Número de Control** no es simplemente `EEEE`+`PPPP`: el patrón real
  es `DTE-{tt}-{letra}{3 dígitos}P{3 dígitos}-{15 dígitos}`, donde la letra
  es el tipo de establecimiento (M=Matriz, B=Bodega, S=Sucursal, P=Patio,
  CAT-009) — confirmado por el regex del propio schema.
- **Factura usa `totalIva` e `ivaItem` por línea; CCF usa `ivaPerci` a nivel
  de resumen y NO lleva `ivaItem` por línea** (usa `tributos: ["20"]` por
  línea en su lugar). Son campos con nombres distintos entre schemas, no
  intercambiables — esto causó rechazos silenciosos en mi primera versión
  antes de tener los schemas reales.
- CCF exige `receptor.nit` y `receptor.nrc` no-nulos (es una operación entre
  contribuyentes); Factura permite `receptor: null` (consumidor final).

**Los 11 tipos de DTE del catálogo CAT-002 están implementados y cada uno
fue probado individualmente con Ajv contra su JSON Schema oficial real**
(no una aproximación): Factura, CCF, Nota de Remisión, Nota de Crédito, Nota
de Débito, Comprobante de Retención, Comprobante de Liquidación, Documento
Contable de Liquidación, Factura de Exportación, Factura de Sujeto Excluido
y Comprobante de Donación.

| tipoDte | Documento | Función en dteBuilder*.js | Archivo |
|---|---|---|---|
| 01 | Factura | `construirFactura` | `dteBuilder.js` |
| 03 | CCF | `construirCCF` | `dteBuilder.js` |
| 04 | Nota de Remisión | `construirNotaRemision` | `dteBuilderNotas.js` |
| 05 | Nota de Crédito | `construirNotaCredito` | `dteBuilderNotas.js` |
| 06 | Nota de Débito | `construirNotaDebito` | `dteBuilderNotas.js` |
| 07 | Comprobante de Retención | `construirComprobanteRetencion` | `dteBuilderOtros.js` |
| 08 | Comprobante de Liquidación | `construirComprobanteLiquidacion` | `dteBuilderOtros.js` |
| 09 | Documento Contable de Liquidación | `construirDocumentoContableLiquidacion` | `dteBuilderOtros.js` |
| 11 | Factura de Exportación | `construirFacturaExportacion` | `dteBuilderOtros.js` |
| 14 | Factura de Sujeto Excluido | `construirFacturaSujetoExcluido` | `dteBuilderOtros.js` |
| 15 | Comprobante de Donación | `construirComprobanteDonacion` | `dteBuilderOtros.js` |

Además, los dos **eventos** (no son DTE, pero sí van firmados y transmitidos)
también están implementados y probados contra su schema oficial:

| Evento | Función | Archivo |
|---|---|---|
| Invalidación (anulación) | `construirEventoInvalidacion` | `eventoInvalidacionBuilder.js` |
| Contingencia | `construirEventoContingencia` | `eventoContingenciaBuilder.js` |

### Detalles no intuitivos que solo aparecen leyendo los schemas reales

- **Número de Control**: `DTE-{tt}-{letra}{3 dígitos}P{3 dígitos}-{15 dígitos}`,
  donde la letra es el tipo de establecimiento (M/B/S/P, CAT-009) — no es
  simplemente `EEEE-PPPP` como parecería intuitivo.
- **`codEstableMH`/`codPuntoVentaMH` de 4 caracteres**: los schemas de los
  eventos (Invalidación, Contingencia) piden estos códigos como campos
  STRING de exactamente 4 caracteres cada uno — que resultan ser,
  literalmente, los primeros 8 caracteres tras `DTE-{tt}-` del Número de
  Control (`"M001"` + `"P001"`). Confirma que ambas piezas usan la MISMA
  fuente de verdad: `utils/establecimientoMH.js`.
- **IVA con nombres de campo distintos por tipo**: Factura usa `totalIva` +
  `ivaItem` por línea; CCF/NC/ND usan `ivaPerci` a nivel resumen (NC/ND
  también llevan `totalIva`/`ivaPerci` por línea, pero **no** `ivaItem`).
  Confundir estos nombres causa rechazos silenciosos.
- **`identificacion` no siempre tiene los mismos campos**: `tipoContingencia`
  / `motivoContin` faltan en CL, DCL y CD; el campo `fusion` solo existe en
  NC, ND y CL. Esto está resuelto con flags explícitas en
  `_construirIdentificacion(...)` de cada archivo.
- **CD (Comprobante de Donación) invierte emisor/receptor**: el "emisor" es
  quien RECIBE la donación (ONG) y el "receptor" es el donante.
- **NC/ND siempre requieren `documentoRelacionado`** (el CCF que corrigen);
  NR y FEX lo permiten `null`.
- **`otrosDocumentos` en CD** no puede ser `null`: debe ser un arreglo con
  mínimo 1 elemento (aunque sus campos internos sean nullable).
- **DCL exige `totalLetras` como string real** (no nullable, a diferencia de
  los demás tipos) — se implementó `utils/numeroALetras.js`, un conversor
  número→letras en español para montos en USD.
- **`bienTitulo` en Nota de Remisión** debe ser string (`"04"`), no entero.

### Lo que SÍ tienes que decidir tú (no es responsabilidad de este código)

Los builders resuelven la ESTRUCTURA (lo que Hacienda exige que el JSON
tenga), pero varios tipos requieren datos de negocio que este microservicio
no puede inventar:
- `construirDocumentoContableLiquidacion` recibe `datos` ya calculados
  (montos de comisión, IVA percibido, etc.) — la matemática de liquidación
  varía por modelo de negocio.
- `construirComprobanteRetencion` y `construirComprobanteLiquidacion` reciben
  la lista de documentos ya retenidos/liquidados con sus montos.
- `construirFacturaExportacion` requiere que definas `recintoFiscal`
  (CAT-027), `regimen` (CAT-028) y `tipoRegimen` (CAT-033) según tu aduana y
  tipo de operación real.

### Pruebas de certificación de Hacienda

`scripts/enviar-lote-certificacion.js` (`npm run certificacion`) ejecuta los
mínimos del Manual Funcional XXIV para lo que emite el comercio: **90
Facturas, 75 CCF, 5 invalidaciones (tipo 2) y 5 contingencias** con sello de
recepción. Exige `DTE_MODE=hacienda-test`, usa una `Idempotency-Key` estable
por documento (reanudable con el mismo `CERT_RUN_ID`) y deja un reporte
`certificacion-<CERT_RUN_ID>.json`. Variables y requisitos en el encabezado
del script (keys de emisión y fiscal, receptor de los CCF, responsable de
los eventos y `DTE_ALLOW_FORCED_CONTINGENCY=true` para las contingencias).

## Endpoints de Hacienda (confirmados)

| Servicio | URL Test | URL Producción | Método |
|---|---|---|---|
| Autenticación | `https://apitest.dtes.mh.gob.sv/seguridad/auth` | `https://api.dtes.mh.gob.sv/seguridad/auth` | POST |
| Recepción (uno a uno) | `.../fesv/recepciondte` | `.../fesv/recepciondte` | POST |
| Recepción (lote, máx 100 DTE) | `.../fesv/recepcionlote` | `.../fesv/recepcionlote` | POST |
| Consulta de DTE | `.../fesv/recepcion/consultadte` | igual | **POST** (no GET) |
| Consulta de lote | `.../fesv/recepcion/consultadtelote/{codigoLote}` | igual | GET |
| Contingencia | `.../fesv/contingencia` | `.../fesv/contingencia` | POST |
| Invalidación (anulación) | `.../fesv/anulardte` | `.../fesv/anulardte` | POST |

Detalles operativos confirmados por el Manual v2.0:
- El token de autenticación se renueva cada 24h en producción y cada 48h en
  pruebas (el código lo renueva cada 12h por seguridad, ver `authService.js`).
- Umbral de espera antes de reintentar: 8 segundos, máximo 2 reintentos, luego
  consulta de estado; si tampoco responde, se activa contingencia.
- Lotes: máximo 100 DTE por lote, máximo 400 lotes/día. En pruebas se procesan
  de 08:00 a 17:00; en producción de 22:00 a 05:00 (para contribuyentes con
  facturación cíclica). Contingencia no tiene restricción horaria.
- Holgura de transmisión: se aceptan documentos hasta 1 día después de la
  fecha de emisión, excepto el último día del período tributario (30 min).

## Catálogos oficiales (reales, no simulados)

`src/config/catalogos.json` contiene los 33 catálogos completos (CAT-001 a
CAT-033) generados automáticamente desde el Excel oficial de Hacienda. Esto
incluye actividades económicas (774 códigos), países (249), departamentos,
municipios y distritos (los distritos vienen agrupados por departamento en
`entradas_por_departamento`, porque sus códigos se repiten entre
departamentos — ej. el distrito "01" existe en los 14 departamentos con
significados distintos).

**Cuando Hacienda publique una nueva versión del Excel**, no edites el JSON a
mano. Regénéralo con Python 3 (solo usa la biblioteca estándar):

```bash
python scripts/generar-catalogos.py "/ruta/Catálogos - Facturación Electrónica.xlsx"
python scripts/generar-catalogos.py "/ruta/Catálogos - Facturación Electrónica.xlsx" --check
```

El regenerador solo acepta filas con código y valor, conserva códigos de texto
como `NA`, reconstruye `entradas_por_departamento` y falla ante catálogos
faltantes, códigos vacíos o duplicados inesperados. La suite fija los conteos
de la versión del 1 de julio para que una actualización requiera revisión
explícita antes de reemplazar el archivo.

`src/config/catalogs.js` expone helpers: `esCodigoValido(catId, codigo)`,
`distritosDeDepartamento(codDepartamento)`, y constantes con nombre para los
catálogos más usados (`TIPO_DTE`, `AMBIENTE`, `CONDICION_OPERACION`, etc.).

### Resolviendo códigos desde tu ERP/frontend (sin duplicar el catálogo)

Los códigos del **emisor** (tu empresa) se configuran una sola vez en `.env`
y no cambian por transacción. Pero los códigos del **receptor** (dirección,
tipo de documento, actividad económica de cada cliente) varían en cada
DTE, y quien arma el request al microservicio necesita resolverlos. Si tu
ERP/frontend no corre en Node (o simplemente no quieres duplicar el JSON),
usa estos endpoints de solo lectura para resolver nombre → código en tiempo
real:

- `GET /api/catalogos` — lista los 33 catálogos disponibles
- `GET /api/catalogos/:catId?q=texto` — entradas de un catálogo, con
  búsqueda opcional por texto (ignora acentos/mayúsculas). Ej.:
  `GET /api/catalogos/CAT-013?q=san salvador` → municipios que coinciden
- `GET /api/catalogos/CAT-008/departamento/:codDepartamento` — distritos
  válidos para un departamento específico (recuerda que CAT-008 se repite
  entre departamentos, así que consultarlo "a secas" no alcanza)

## Firmador (confirmado contra el código fuente real)

El body exacto que espera `POST /firmardocumento/` (confirmado leyendo
`FirmarDocumentoFilter.java` del propio proyecto SVFE-API-Firmador) es:

```json
{
  "nit": "06141804941035",
  "activo": true,
  "passwordPri": "clave_de_la_llave_privada",
  "dteJson": { "...": "..." }
}
```

Y la respuesta siempre tiene forma `{ "status": "OK"|"ERROR", "body": ... }`
— `body` es el string firmado (JWS) si status es OK, o `{codigo, mensaje}` si
es ERROR. Esto ya está implementado en `src/services/firmadorClient.js`.

**Sobre la imagen Docker del firmador**: el archivo `dte-firmador.zip` que
entrega Hacienda pesa ~226 MB (incluye la imagen Docker exportada) y no se
incluye en este paquete. Coloca su contenido en `firmador-docker/` siguiendo
la estructura real documentada en el Manual v2.0 sección 2.1:
- `firmador-docker/certificado/<TU_NIT>.crt` — tu certificado de firma
- `firmador-docker/svfe-api.env` — ya viene con `SPRING_PROFILES_ACTIVE=nonssl`
  por defecto; cámbialo a `ssl` y coloca tu `.p12` en `firmador-docker/ssl/`
  si necesitas TLS en la comunicación local con el firmador.
- Actualiza el `image:` en `docker-compose.yml` con el tag exacto que te
  entregue Hacienda (ej. `svfe/svfe-api-firmador:v20250526`).

Alternativamente, el proyecto fuente `svfe-api-firmador.zip` (Java Spring
Boot, Maven) se puede compilar y correr directamente sin Docker si lo
prefieres — el `Dockerfile` incluido en ese zip ya está listo para `docker build`.

## Arquitectura

```
Cliente (ERP/POS) → [Microservicio DTE] → Firmador (local, Java) → Hacienda (Internet)
                            │
                            └── SQLite: correlativos, DTEs emitidos, cola de reintentos
```

Flujo por cada emisión (`POST /api/dte/factura` o `/api/dte/ccf`):

1. **Construir** el JSON del DTE (`dteBuilder.js`): `codigoGeneracion` (UUID
   v4 mayúsculas) y `numeroControl` (correlativo atómico en SQLite).
2. **Validar** estructuralmente con Ajv (`validators/dteSchema.js`).
3. **Persistir** en estado `PENDIENTE` antes de firmar (nunca se pierde
   trazabilidad aunque el proceso muera a mitad de camino).
4. **Firmar** contra el firmador local (`firmadorClient.js`).
5. **Transmitir** a Hacienda (`transmisionService.js` + `haciendaClient.js`)
   con token cacheado (renovación única ante 401).
6. Sin respuesta: `PENDIENTE_RECONCILIACION` y la cola (`retryQueue.js`)
   consulta antes de reenviar (máx. 2 reenvíos); agotada la política, el
   documento entra en contingencia (`contingenciaService.js`).

## Operación del proceso

- **Cierre ordenado (graceful shutdown)**: `server.js` escucha
  `SIGTERM`/`SIGINT` (lo que manda `docker stop` o un reinicio del
  contenedor) y: deja de aceptar conexiones nuevas, deja terminar las
  peticiones en curso, cierra la conexión a SQLite, y recién ahí sale con
  código 0. Si por algo se cuelga, fuerza la salida a los 10s en vez de
  quedarse colgado para siempre. `docker-compose.yml` le da 15s de margen
  (`stop_grace_period`) para que esto siempre alcance a terminar antes de
  que Docker mande `SIGKILL`. Probado con un test que arranca el proceso
  real y manda las señales de verdad (`test/integration/server.test.js`),
  no solo simulado.
- **Errores no manejados a nivel de proceso**: una excepción async sin
  capturar (`uncaughtException`/`unhandledRejection`) se registra con
  detalle en el log y CIERRA el proceso a propósito — seguir corriendo
  después de eso es más riesgoso que reiniciar limpio. Configura tu
  orquestador (Docker `restart: unless-stopped`, ya está en el
  `docker-compose.yml`, o PM2/systemd si corres esto sin Docker) para que
  reinicie automáticamente.
- **Health check que verifica de verdad**: `GET /api/health` corre un
  `SELECT 1` contra SQLite y responde `503` + `status: "degraded"` si falla
  (antes solo respondía "ok" sin comprobar nada). A propósito NO verifica
  el firmador ni Hacienda — son llamadas de red lentas, y que Hacienda esté
  caída no significa que el microservicio en sí esté enfermo (para eso
  existe el estado `CONTINGENCIA`, que es una situación esperada, no una
  falla).

## Lo que TODAVÍA falta para producción

1. **Cálculo fiscal — lo que ya cubre y lo que no**: Factura, CCF, Nota de
   Crédito/Débito y Comprobante de Liquidación ya manejan ventas gravadas,
   exentas y no sujetas, descuentos por línea, y **descuento global a nivel
   de documento** (`descuentoGlobal: { gravada?, exenta?, noSuj? }`, se
   reparte proporcionalmente entre líneas — ver `calculoFiscal.js`). Lo que
   **todavía no** cubre: IVA percibido o retenido combinado en la misma
   operación, ni pagos parciales/combinados.
2. **Códigos de establecimiento/punto de venta**: deben ser los
   oficialmente asignados por Hacienda (Formulario F-210) — van en
   `MH_COD_ESTABLECIMIENTO` / `MH_COD_PUNTO_VENTA` del `.env` (3 dígitos).
3. **Certificado de firma**: se obtiene desde `admin.factura.gob.sv` al
   completar el proceso de incorporación como emisor electrónico.
4. **Representación gráfica (PDF/QR) ya implementada**:
   `GET /api/dte/:codigoGeneracion/pdf` genera el PDF con el QR apuntando a
   `https://admin.factura.gob.sv/consultaPublica?ambiente={ambiente}&codGen={codigoGeneracion}&fechaEmi={fecha}`
   (confirmado en Manual v2.0 sección 5). `representacionGraficaBuilder.js`
   sigue el formato de un DTE real, en papel Carta y monocromático (negro,
   blanco y grises).
   - **Encabezado:** emisor con logo opcional (`POST .../pdf/render`) y caja
     DTE con el QR clicable.
   - **Receptor:** caja con sus datos.
   - **Referencias:** venta a cuenta de terceros, documento relacionado y
     otros documentos asociados. Se muestran siempre, con "-" cuando están
     vacíos.
   - **Ítems:** tabla con total en letras y sumas.
   - **Cierre:** observaciones (incluye la forma de pago), cuadro de totales
     y firmas ENTREGA/RECIBE.

   Comportamiento:
   - **Códigos de catálogo:** se imprimen con su nombre (dirección, unidad,
     tipo de documento, forma de pago), vía `utils/etiquetasCatalogo.js`.
   - **Columnas por tipo:** la tabla de ítems usa columnas propias para 07,
     08, 14 y 15; la DCL muestra su cuerpo (un objeto) como cuadrícula.
   - **IVA:** se imprime una sola vez. Es una fila que suma si
     `subTotal + IVA = montoTotalOperacion`; si no, es una línea informativa.
   - **Paginación:** repite la cabecera de ítems y nunca parte el bloque final.
   - **Fecha de representación:** la opción `fechaRepresentacion`
     (`YYYY-MM-DD`) la fija; por defecto es hoy en El Salvador.
   - **Caracteres:** las fuentes estándar solo cubren WinAnsi, así que los
     caracteres fuera de ese juego se reemplazan antes de dibujar.
5. **Sanitización UTF-8/caracteres residuales ya implementada**
   (`utils/sanitizarDte.js`): normaliza a NFC, quita caracteres de control
   no imprimibles, y quita `;`/espacios sueltos al final de cada valor —
   se aplica ANTES de validar contra el schema (no después de firmar), así
   lo que se valida es exactamente lo mismo que se firma y transmite.
6. **`numeroALetras.js` es una implementación propia** (Hacienda no publica
   un algoritmo oficial): hasta 999 999 999.99 con centavos, apócope delante
   de MIL/MILLONES (VEINTIÚN MIL, CIENTO UN MIL) y tildes.
7. **Autenticación y rate limiting de la API ya implementados** (ver
   sección "Seguridad de la API" más abajo): API key por header con
   comparación segura contra timing attacks, más límite de peticiones por
   API key (en memoria, de un solo proceso — ver limitación de escalado
   horizontal documentada en `middleware/rateLimiter.js`). Si necesitas
   usuarios con permisos distintos o exponer esto más allá de tu red
   privada, considera JWT propio con roles — eso sí sigue sin implementar.
8. **`TIPO_ANULACION` está confirmado**: resultó ser `CAT-024 Motivo del
   evento`, que sí vino en el Excel oficial — simplemente no lo había
   cruzado con el catálogo ya cargado cuando escribí el builder. Ya se
   corrigió para que lo tome de `catalogs.js` (derivado de
   `catalogos.json`) en vez de tener una constante separada, con una
   verificación al arrancar que falla ruidosamente si Hacienda cambia
   CAT-024 en una futura versión del Excel.
9. **Ventana horaria de envío de lotes**: `utils/ventanaHoraria.js`
   verifica si estás dentro del horario documentado (pruebas 08:00–17:00,
   producción 22:00–05:00) y deja una advertencia en el log si no —
   **no bloquea el envío**, porque el propio Manual v2.0 aclara que esa
   restricción solo aplica a contribuyentes con "facturación cíclica", no
   a todos los que usan el modelo de lotes.
10. **Cierre ordenado, errores de proceso y health check real ya
    implementados** — ver sección "Operación del proceso" más arriba.
11. **Sin CORS configurado**: si algún día un frontend en el navegador (no
    tu ERP corriendo en servidor) necesita llamar esta API directamente
    desde JavaScript del lado del cliente, fallará por política de mismo
    origen. Si lo necesitas, hay que agregar el paquete `cors` con la
    lista de orígenes permitidos explícita (nunca `*` para una API que
    factura con tu NIT).
12. **Idempotencia ya implementada** (`services/idempotency.js`): si tu ERP
    manda el header `Idempotency-Key` (una clave que tú generes, una por
    intento lógico de venta — no una nueva por cada reintento HTTP), una
    repetición exacta de esa key devuelve el MISMO resultado guardado en
    vez de reprocesar, así un timeout de red que hace que tu ERP reintente
    no duplica el DTE ante Hacienda. Es **obligatoria** en las rutas de
    emisión y en `/anular`. Ver la sección "Idempotencia" más abajo.
13. **CI**: `.github/workflows/deploy.yml` corre `npm test` del
    microservicio y las pruebas DTE del backend contra PostgreSQL efímero.

## Seguridad de la API (autenticación propia del microservicio)

Esto es DISTINTO de `authService.js` (que autentica tu microservicio hacia
Hacienda). Aquí se trata de que alguien tenga que autenticarse para poder
usar TU microservicio — sin esto, cualquiera con acceso de red al servicio
podía emitir o anular DTE con tu NIT sin ninguna credencial.

Protección: **API key por header**, verificada con `crypto.timingSafeEqual`
(comparar con `===` es vulnerable a ataques de temporización). El servidor
**se niega a arrancar** si no hay ninguna key configurada — falla rápido a
propósito, para que no quede desprotegido por accidente.

```bash
# Genera una key nueva
node scripts/generar-api-key.js

# Pégala en tu .env (puedes tener varias separadas por coma, ej. una por sistema consumidor)
MS_API_KEYS=la-key-generada,otra-key-para-otro-sistema
# Scopes en el mismo orden, separados por punto y coma. Si se omite,
# cada key recibe solo issue,read.
MS_API_KEY_SCOPES=issue,read;issue,read,invalidate,contingency
# El checkout habilita inicialmente únicamente Factura 01 y CCF 03.
DTE_ALLOWED_DOCUMENT_TYPES=01,03
```

Los scopes disponibles son `issue` (emitir), `read` (consultar/descargar),
`invalidate` (anular) y `contingency` (declarar contingencia). Una key usada
por el checkout debe conservar únicamente `issue,read`; las operaciones
fiscales de mayor riesgo deben usar otra key con permisos explícitos.

Tus consumidores (ERP/POS) deben mandar la key en cada request, con
cualquiera de estos dos headers:

```
Authorization: Bearer <tu-api-key>
X-API-Key: <tu-api-key>
```

`GET /api/health` queda **público a propósito** (health checks de
infraestructura — balanceadores de carga, `docker healthcheck`, Kubernetes
probes — normalmente no mandan credenciales, y este endpoint no expone
nada sensible). Todo lo demás (`/api/dte/*`, `/api/catalogos/*`) exige la key.

**Para desarrollo local** sin configurar una key todavía: `MS_AUTH_DESHABILITADA=true`
en tu `.env` — pero esto nunca debería usarse en un entorno accesible por
más gente que tú.

Esta protección es apropiada para un microservicio **interno** (detrás de tu
red privada / VPN, consumido solo por tu propio ERP/POS). Para consumidores
internos con permisos distintos usa `MS_API_KEY_SCOPES`; si necesitas
identidades de usuario, expiración/revocación online o exponerlo a internet,
correspondería JWT propio con roles, que es un cambio más grande.

### Rate limiting

También hay un límite de peticiones por API key (`middleware/rateLimiter.js`,
sin dependencia nueva — implementación propia en memoria):

```bash
MS_RATE_LIMIT_MAX=120          # peticiones permitidas por ventana (0 = deshabilitado)
MS_RATE_LIMIT_WINDOW_MS=60000  # duración de la ventana en ms (60000 = 1 minuto)
```

Al superar el límite, responde `429 Too Many Requests` con un header
`Retry-After`. **Limitación conocida**: el contador vive en memoria de un
solo proceso — si corres varias instancias detrás de un balanceador, cada
una lleva su propio contador (el límite efectivo se multiplica por la
cantidad de instancias). Para un límite compartido de verdad en un
despliegue con múltiples instancias, necesitarías un store centralizado
(Redis, etc.) — no incluido a propósito, para no forzar esa dependencia de
infraestructura en el caso común de una sola instancia.

## Idempotencia

Protege contra el caso real: tu ERP manda `POST /factura`, la red se
cuelga antes de que la respuesta llegue, tu ERP lo interpreta como fallo y
reintenta — pero el servidor SÍ lo había procesado la primera vez. Sin
idempotencia, eso son dos DTE distintos ante Hacienda con los mismos datos.

Uso: manda un header `Idempotency-Key` con un valor único por **intento
lógico de venta** (generado una sola vez por tu ERP antes del primer
intento — no una key nueva en cada reintento HTTP, eso anularía el propósito):

```bash
curl -X POST http://localhost:3000/api/dte/factura \
  -H "Authorization: Bearer TU_API_KEY" \
  -H "Idempotency-Key: venta-12345-intento-1" \
  -H "Content-Type: application/json" \
  -d '{ "receptor": null, "items": [...] }'
```

La key queda ligada al hash canónico de método, ruta y body. Reutilizarla
con datos distintos responde `409 Conflict`. Los resultados terminales y
los `202` pendientes se reproducen sin volver a construir, firmar o
transmitir. Si el firmador falla con `502`, el siguiente reintento conserva
el mismo `codigoGeneracion`, número de control y payload; no consume otra
identidad fiscal. Dos solicitudes simultáneas con la misma key también
responden `409` para el segundo proceso.

Es **obligatoria** y debe tener entre 8 y 200 caracteres. Sin el header, las
rutas mutables responden `400` antes de reservar una identidad. Protege las
11 rutas de emisión y `/anular`.

Si una clave queda "en curso" porque el proceso se cayó a medio camino, se
considera abandonada después de 120 segundos (más que el peor caso de firma,
autenticación y transmisión). La emisión reanuda `PENDIENTE`, `ERROR_FIRMA` y
`FIRMADO` desde la identidad enlazada, y la invalidación reenvía el mismo
evento persistido.

## Levantar el proyecto

```bash
cp .env.example .env
# edita .env con tu NIT, clave API, clave de llave privada y códigos MH

npm install
docker compose up --build
```

## Tests

Usa el test runner nativo de Node (`node:test`), sin dependencias extra de
testing. **267 pruebas** (unitarias e integración; `server.test.js` necesita
señales POSIX y se ejecuta en Linux/CI), en dos capas:

```bash
npm run test:unit         # rápidos, sin red, sin SQLite, sin credenciales
npm run test:integration  # levantan el servidor Express real + SQLite real
npm test                  # ambos
```

Además de los casos históricos descritos abajo, la suite cubre los
escenarios del Manual Funcional (descuento global 775.00 − 77.50, IVA de CCF
±0.01, FE con IVA incluido, reloj fijo a las 23:30 de El Salvador en fin de
mes), la política de reintentos contra un **servidor HTTP que imita a
Hacienda** (`test/integration/haciendaStub.test.js`: 400 RECHAZADO, 004,
timeout → consulta → 2 reenvíos → contingencia, 401, credenciales, firmador
809), invalidación (`test/unit/invalidacion.test.js`) y el ciclo completo de
contingencia (`test/integration/contingencia.test.js`).

**`test/unit/`** cubre lo que más importa para no romper la
certificación de Hacienda sin darte cuenta:
- Los 11 builders de DTE + los 2 builders de eventos generan un JSON que
  **valida contra el schema oficial real** (Ajv), no una aproximación.
- El Número de Control respeta el patrón exacto `DTE-tt-(M|B|S|P)dddPddd-ddddddddddddddd`.
- Casos de error: CCF sin NIT/NRC, NC sin documento relacionado, NR sin
  bienTitulo, DCL con datos incompletos, etc.

**`test/integration/`** levanta la app Express real y **SQLite
real** (usa `node:sqlite`, el módulo nativo de Node, para no depender de
`better-sqlite3` compilado durante el desarrollo) y prueba de punta a punta:
emisión de DTE (camino feliz, fallo del firmador, fallo de Hacienda con
reintento), anulación, contingencia, y la cola de reintentos completa
(`retryQueue.js`) con backoff real.

Para que los builders sean testeables sin depender de la base de datos real,
el correlativo de Número de Control pasa por
`src/services/correlativoStore.js`: en tests usa un contador en memoria; en
el servidor real, `server.js` lo conecta con la persistencia en SQLite al
arrancar. **Si tocas ese cableo, revisa que sigue conectado** — sin él, los
correlativos se perderían en cada reinicio del servidor.

### Bugs reales que esta suite encontró (y corrigió)

Vale la pena dejarlos documentados porque son el tipo de error que pasa
inadvertido hasta que Hacienda rechaza algo en producción:

1. **`retryQueue.js` nunca reintentaba tras el primer fallo.** El
   reagendado usaba `new Date().toISOString()` (formato
   `2026-07-14T20:55:30.123Z`) pero la consulta compara contra
   `datetime('now')` de SQLite (formato `2026-07-14 20:55:30`). Al ser
   formatos de texto distintos, la comparación `<=` nunca se cumplía de
   nuevo, y el DTE quedaba atascado en `PENDIENTE_REINTENTO` para siempre,
   silenciosamente. Corregido: ahora el reagendado se calcula con
   `datetime('now', '+N seconds')` de la propia SQLite, así el formato
   siempre es consistente.
2. **Redondeo de IVA por línea vs. total.** En Factura, Nota de
   Crédito/Débito y Comprobante de Liquidación, el IVA se declaraba dos
   veces (por línea y en el resumen) con cálculos independientes — con
   ciertas combinaciones de montos (ej. 3 líneas de $33.33/$33.33/$33.34)
   el redondeo por línea da $12.99 pero `totalGravada * 0.13` por separado
   da $13.00. Corregido: el resumen ahora siempre deriva el total como la
   suma de las líneas ya redondeadas, nunca un cálculo aparte.
3. **`PRAGMA foreign_keys` no estaba habilitado.** La restricción `FOREIGN
   KEY` entre `cola_reintentos` y `dtes` estaba declarada en el schema SQL
   pero SQLite no la aplicaba (es su comportamiento por defecto). Ya está
   habilitada explícitamente en `db/index.js`.
4. **DCL con `iva`/`ivaPercibido` en cero** — el schema exige
   `exclusiveMinimum: 0`, no `>= 0`. Ver detalle más abajo.
5. **Ajv rechazaba montos matemáticamente válidos por precisión de punto
   flotante.** Al extender el cálculo fiscal a ventas mixtas (gravada +
   exenta + no sujeta), apareció un caso real: `90 + 41.70` en JS no se
   representa exactamente como `131.70` en binario, y el `multipleOf: 0.01`
   de los schemas oficiales lo rechazaba — es un bug conocido y todavía
   abierto en Ajv (`ajv-validator/ajv#2329`), no un error de cálculo.
   Corregido agregando `multipleOfPrecision: 6` a la configuración de Ajv en
   `validators/dteSchema.js`. Sin este fix, facturas válidas se habrían
   rechazado silenciosamente antes de llegar siquiera a Hacienda.

## Endpoints del microservicio

- `POST /api/dte/factura` — Factura (tipo 01)
- `POST /api/dte/ccf` — Comprobante de Crédito Fiscal (tipo 03)
- `POST /api/dte/nota-remision` — Nota de Remisión (tipo 04)
- `POST /api/dte/nota-credito` y `POST /api/dte/v2/nota-credito` (emisor de
  la revisión del panel) — Nota de Crédito (tipo 05). Solo ajusta CCF:
  `{ emisor, receptor, items, documentosRelacionados, observaciones }`, con el
  receptor por NIT (`tipoDocumento` 36), de 1 a 50 CCF relacionados (código de
  generación y `fechaEmision`) y `numeroDocumento` en cada línea. Fuera de la
  allowlist por defecto (`01,03`): responde 403 hasta que el backend la use
- `POST /api/dte/nota-debito` — Nota de Débito (tipo 06)
- `POST /api/dte/comprobante-retencion` — Comprobante de Retención (tipo 07)
- `POST /api/dte/comprobante-liquidacion` — Comprobante de Liquidación (tipo 08)
- `POST /api/dte/documento-contable-liquidacion` — Doc. Contable de Liquidación (tipo 09)
- `POST /api/dte/factura-exportacion` — Factura de Exportación (tipo 11)
- `POST /api/dte/factura-sujeto-excluido` — Factura de Sujeto Excluido (tipo 14)
- `POST /api/dte/comprobante-donacion` — Comprobante de Donación (tipo 15)
- `GET /api/dte/:codigoGeneracion` — estado local
- `GET /api/dte/:codigoGeneracion/pdf` — representación gráfica (PDF con QR); requiere estado TRANSMITIDO
- `GET /api/dte/:codigoGeneracion/hacienda` — estado directo en Hacienda
- `GET /api/dte/lote/:codigoLote` — resultado de un lote transmitido
- `POST /api/dte/:codigoGeneracion/anular` — Evento de Invalidación (ver
  sección "Invalidación"); `GET /api/dte/:codigoGeneracion/invalidacion`,
  `GET /api/dte/:codigoGeneracion/eventos`, `GET /api/dte/eventos/:codigo/json`
- `GET|POST /api/dte/contingencia...` — operación en contingencia (ver
  sección "Contingencia")
- `GET /api/catalogos*` — ver sección "Catálogos oficiales" arriba
- `GET /api/health` — health check

### Ejemplo de body para `POST /api/dte/factura`

```json
{
  "receptor": {
    "tipoDocumento": "13",
    "numDocumento": "01234567-8",
    "nombre": "Cliente de Prueba",
    "correo": "cliente@example.com"
  },
  "items": [
    { "descripcion": "Servicio de consultoría", "cantidad": 1, "precioUni": 113.00, "ventaGravada": 113.00 }
  ],
  "pago": { "codigo": "05", "montoPago": 113.00, "referencia": "TRANSF-001", "numPagoElectronico": null }
}
```

En la Factura los precios llevan **IVA incluido** (113.00 = 100.00 + 13 %);
en el CCF van sin IVA y cada línea gravada informa `ivaItem`.

Con ventas mixtas (gravada + exenta + no sujeta) y descuento por línea —
`ventaGravada`/`ventaExenta`/`ventaNoSuj` van ya netas del descuento de esa
línea (`cantidad × precioUni − montoDescu`, ver `calculoFiscal.js`):

```json
{
  "receptor": null,
  "items": [
    { "descripcion": "Producto con descuento", "cantidad": 1, "precioUni": 100.00, "ventaGravada": 90.00, "montoDescu": 10.00 },
    { "descripcion": "Producto exento", "cantidad": 1, "precioUni": 50.00, "ventaGravada": 0, "ventaExenta": 50.00 },
    { "descripcion": "Servicio no sujeto", "cantidad": 1, "precioUni": 20.00, "ventaGravada": 0, "ventaNoSuj": 20.00 }
  ]
}
```

Los otros 9 tipos están deshabilitados por `DTE_ALLOWED_DOCUMENT_TYPES`
(01,03); sus builders requieren revisión fiscal antes de habilitarlos.

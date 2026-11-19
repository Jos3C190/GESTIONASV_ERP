# Servicio DTE multiemisor

El servicio arma, valida, firma y transmite los documentos tributarios electrónicos. En el ERP
es **multiemisor**: cada empresa es un emisor aislado, con su modo, sus tipos de documento, su
numeración y sus documentos. El ERP lo usa desde la red interna; el servicio nunca se expone.

## Arranque

El servicio arranca con el resto del entorno (`make up`). En la red interna lo usan el
backend y el trabajador `dte-worker` en `http://dte-service:3000`:

```bash
docker compose up -d dte-service dte-worker
```

| Variable | Para qué |
|---|---|
| `DTE_SERVICE_API_KEY` | API key que comparten el backend y el servicio. `scripts/setup.sh` la genera en `.env`. |
| `DTE_MODE` | Modo **máximo** del despliegue: `simulated` (desarrollo y demostración), `hacienda-test` o `production`. Por defecto `simulated`. Cada empresa usa el suyo hasta ese límite. |
| `DTE_CREDENTIALS_KEY` | Clave de 32 bytes (base64url) con la que se cifran las contraseñas de Hacienda de cada empresa. `scripts/setup.sh` la genera. |
| `DTE_CERTIFICATES_DIR` | Carpeta de los certificados `{nit}.crt`, compartida con el firmador (volumen `dte-certificates`). |
| `FIRMADOR_URL` | Firmador oficial (`dte-signer`, compilado desde `dte-signer/`). |
| `DTE_LOG_LEVEL` | Nivel de registro (`info` por defecto). |

No hace falta un emisor en el entorno (`MH_*`): cada empresa trae el suyo y, fuera de simulado,
sus credenciales. El emisor del entorno queda para despliegues heredados de una sola empresa.
Sin `MH_*_URL` se usan las rutas oficiales del host de cada modo (`apitest.dtes.mh.gob.sv` en
pruebas, `api.dtes.mh.gob.sv` en producción).

## Registro de emisores

El ERP registra cada empresa con el alcance `issuers`:

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/api/emisores` | Lista los emisores. |
| `GET` | `/api/emisores/:nit` | Un emisor. |
| `PUT` | `/api/emisores/:nit` | Alta o actualización: `nombre`, `modo`, `tiposHabilitados` (códigos de dos dígitos), `activo`; fuera de simulado, `credenciales` (`passwordApi`, `passwordPri`, `certificado` en base64); y `responsable` (`nombre`, `tipoDocumento` de CAT-022, `numeroDocumento`) del Evento de Contingencia. Sin `responsable` se conserva el guardado; `null` lo quita. |
| `POST` | `/api/emisores/:nit/probar` | Autentica contra Hacienda y firma un documento de prueba con el certificado de la empresa. Devuelve `{ok, autenticacion, firma}`; no emite ni consume números de control. |

Un emisor emite solo si cumple todo esto:

- está registrado y activo;
- su modo no supera el del despliegue (simulado < pruebas < producción). Conviven empresas en
  modos distintos: cada una tiene su token de Hacienda, firma con su certificado y su contraseña
  privada, y usa el ambiente de su modo (`00` pruebas, `01` producción);
- el tipo de DTE está habilitado para él y para el despliegue (`DTE_ALLOWED_DOCUMENT_TYPES`).

## Credenciales de Hacienda

- Las contraseñas de la API y de la llave privada se guardan cifradas (AES-256-GCM con
  `DTE_CREDENTIALS_KEY`) y solo se descifran en memoria al autenticar o firmar. Ninguna
  respuesta las devuelve: el registro solo dice `credenciales.{configuradas, certificadoPresente,
  certificadoSha256}`.
- El certificado debe ser del NIT del emisor y abrir con su contraseña privada (el SHA-512 de la
  contraseña va en `privateKey/clave`, como lo comprueba el firmador). Se escribe de forma
  atómica en `DTE_CERTIFICATES_DIR`, donde lo lee el firmador.
- Cada solicitud de `/api/dte` corre con el contexto de su emisor (`src/services/issuerContext.js`),
  y la cola de reintentos usa el emisor de cada documento.

## Contingencia por emisor y establecimiento (V4a)

Cada ventana es de un emisor y un establecimiento (`codEstable` del documento, por ejemplo
`M001`): una caída en una tienda no pone en contingencia a las demás ni a otras empresas.

- **Automática**: agotada la política de reintentos (8 s, consultar el estado, dos reenvíos), el
  documento pasa a modelo diferido y abre la ventana de su emisor y establecimiento. El sondeo
  revisa cada ventana con el contexto de su emisor y la cierra cuando Hacienda vuelve a responder.
- **Manual**: el ERP la activa ante una falla que el servicio no ve (corte de energía o de internet
  en la tienda) con `POST /api/emisores/:nit/contingencias`.
- Al cerrarla se informa el Evento de Contingencia con el responsable registrado con el emisor
  (sin él, la ventana queda `CERRADA` hasta que se envíe indicándolo). Con el sello del evento,
  los documentos se transmiten uno a uno dentro de las 72 h.
- Mientras tanto la versión legible (`/pdf`) se entrega con el sello «Pendiente: documento
  generado en contingencia».
- **Emisor simulado**: la contingencia manual funciona sin Hacienda. El evento se construye y se
  valida contra el esquema, recibe un sello simulado y los documentos quedan `SIMULADO`.

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/api/emisores/:nit/contingencias` | Ventanas abiertas y recientes, con plazos (`eventoLimite` 24 h, `transmisionLimite` 72 h). |
| `POST` | `/api/emisores/:nit/contingencias` | Activa la ventana: `establecimiento`, `tipoContingencia` (CAT-005) y `motivoContingencia` (obligatorio para el tipo 5). |
| `POST` | `/api/emisores/:nit/contingencias/:id/cerrar` | Cierra e informa el evento si hay responsable (enviado o registrado). |
| `POST` | `/api/emisores/:nit/contingencias/:id/evento` | Envía o reenvía el evento de una ventana cerrada. |
| `POST` | `/api/emisores/:nit/contingencias/:id/transmitir` | Encola los documentos informados pendientes. |

Todas piden el alcance `contingency`; la ventana de otro emisor responde 404. Las rutas
globales `/api/dte/contingencia` quedan para el emisor heredado del entorno y la certificación
(`DTE_ALLOW_FORCED_CONTINGENCY`).

## Invalidación por emisor (V4b)

`POST /api/dte/:codigo/anular` y `GET /api/dte/:codigo/invalidacion` usan el modo del emisor del
documento, en cualquier despliegue. Con un emisor simulado el evento se construye y se valida
igual, pero se marca con un sello simulado y no sale del servicio (`SIMULADO_INVALIDADO`).
`/api/dte/eventos/:codigo/pdf/render` arma también el PDF de un evento simulado, con la marca sin
validez fiscal. Las rutas `/api/dte/simulacion` se conservan para el despliegue simulado.

## Aislamiento

- Cada solicitud a `/api/dte` declara la empresa en el encabezado `X-DTE-Issuer-NIT`. En un
  despliegue sin emisor en el entorno, el encabezado es obligatorio.
- Si el cuerpo trae el snapshot del emisor (contrato v2), su NIT debe coincidir con el encabezado.
- **Documentos**: cada uno guarda su NIT, y un código de generación de otra empresa responde 404
  (JSON, PDF, consulta, invalidación y eventos).
- **Numeración**: el correlativo se lleva por NIT, ambiente, tipo, año, establecimiento y punto de
  venta. Dos empresas con el mismo establecimiento 001 y punto 001 empiezan cada una en 1.
- **Idempotencia**: la clave se guarda por empresa; la misma clave en dos empresas crea dos
  documentos. Un rechazo del emisor antes de reservar identidad (`ISSUER_REQUIRED`,
  `UNAUTHORIZED_ISSUER`, `ISSUER_INACTIVE`, `ISSUER_MODE_UNAVAILABLE`,
  `DTE_DOCUMENT_TYPE_NOT_ALLOWED`) no se guarda: la clave queda libre para reintentar el mismo
  documento cuando cambie la configuración.

## Errores

| Código | HTTP | Cuándo |
|---|---|---|
| `ISSUER_REQUIRED` | 400 | Falta `X-DTE-Issuer-NIT` o el emisor. |
| `ISSUER_MISMATCH` | 400 | El snapshot del documento es de otra empresa. |
| `UNAUTHORIZED_ISSUER` | 403 | Emisor no registrado o desactivado. |
| `ISSUER_INACTIVE` | 403 | Emisor desactivado, al emitir. |
| `DTE_DOCUMENT_TYPE_NOT_ALLOWED` | 403 | Tipo no habilitado para la empresa o el despliegue. |
| `ISSUER_MODE_UNAVAILABLE` | 409 | El modo de la empresa supera el del despliegue. |
| `ISSUER_CREDENTIALS_REQUIRED` | 400 | Registro fuera de simulado sin credenciales. |
| `INVALID_CERTIFICATE`, `CERTIFICATE_NIT_MISMATCH`, `INVALID_PRIVATE_KEY_PASSWORD` | 400 | El certificado no es de Hacienda, es de otro NIT o la contraseña privada no le corresponde. |
| `ISSUER_CREDENTIALS_UNAVAILABLE` | 503 | Falta `DTE_CREDENTIALS_KEY` en el despliegue. |
| `INVALID_ISSUER`, `INVALID_ISSUER_MODE` | 400 | Datos de registro inválidos. |

## Pruebas

```bash
./scripts/run-tests.sh dte
```

Corre `npm test` en `node:22-slim` sobre una copia del servicio. Las pruebas multiemisor están en
`test/integration/multiemisor.test.js`; las de modo y credenciales por empresa, contra un Hacienda
y un firmador simulados por HTTP, en `test/integration/modoPorEmisor.test.js`; la contingencia
por emisor y establecimiento, en `contingenciaPorEmisor.test.js` y `contingenciaSimulada.test.js`.
`test/helpers/certificadoPrueba.js` genera certificados con el formato de Hacienda y llaves RSA
reales; el firmador oficial firma con ellos (verificado).

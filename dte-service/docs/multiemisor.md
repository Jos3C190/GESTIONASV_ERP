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
| `PUT` | `/api/emisores/:nit` | Alta o actualización: `nombre`, `modo`, `tiposHabilitados` (códigos de dos dígitos), `activo` y, fuera de simulado, `credenciales` (`passwordApi`, `passwordPri`, `certificado` en base64). |
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
- Pendiente para V4: la contingencia todavía toma parte de sus datos del emisor del entorno.

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
y un firmador simulados por HTTP, en `test/integration/modoPorEmisor.test.js`.
`test/helpers/certificadoPrueba.js` genera certificados con el formato de Hacienda y llaves RSA
reales; el firmador oficial firma con ellos (verificado).

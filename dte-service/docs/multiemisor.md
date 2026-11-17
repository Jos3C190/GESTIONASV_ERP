# Servicio DTE multiemisor

El servicio arma, valida, firma y transmite los documentos tributarios electrónicos. En el ERP
es **multiemisor**: cada empresa es un emisor aislado, con su modo, sus tipos de documento, su
numeración y sus documentos. El ERP lo usa desde la red interna; el servicio nunca se expone.

## Arranque

El servicio corre con el perfil `dte` de `compose.yaml`:

```bash
docker compose --profile dte up -d dte-service
```

| Variable | Para qué |
|---|---|
| `DTE_SERVICE_API_KEY` | API key que comparten el backend y el servicio. `scripts/setup.sh` la genera en `.env`. |
| `DTE_MODE` | Modo del despliegue: `simulated` (desarrollo y demostración), `hacienda-test` o `production`. Por defecto `simulated`. |
| `DTE_LOG_LEVEL` | Nivel de registro (`info` por defecto). |

En modo simulado no hace falta configurar un emisor en el entorno (`MH_*`): cada solicitud trae
el suyo. Los modos `hacienda-test` y `production` siguen pidiendo el emisor del entorno hasta el
bloque V3d, que agrega credenciales y certificado por empresa.

## Registro de emisores

El ERP registra cada empresa con el alcance `issuers`:

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/api/emisores` | Lista los emisores. |
| `GET` | `/api/emisores/:nit` | Un emisor. |
| `PUT` | `/api/emisores/:nit` | Alta o actualización: `nombre`, `modo`, `tiposHabilitados` (códigos de dos dígitos) y `activo`. |

Un emisor emite solo si cumple todo esto:

- está registrado y activo;
- su modo es el del despliegue. Que convivan empresas en modos distintos llega en V3d, con una
  sesión con Hacienda por empresa;
- el tipo de DTE está habilitado para él y para el despliegue (`DTE_ALLOWED_DOCUMENT_TYPES`).

## Aislamiento

- Cada solicitud a `/api/dte` declara la empresa en el encabezado `X-DTE-Issuer-NIT`. En un
  despliegue sin emisor en el entorno, el encabezado es obligatorio.
- Si el cuerpo trae el snapshot del emisor (contrato v2), su NIT debe coincidir con el encabezado.
- **Documentos**: cada uno guarda su NIT, y un código de generación de otra empresa responde 404
  (JSON, PDF, consulta, invalidación y eventos).
- **Numeración**: el correlativo se lleva por NIT, ambiente, tipo, año, establecimiento y punto de
  venta. Dos empresas con el mismo establecimiento 001 y punto 001 empiezan cada una en 1.
- **Idempotencia**: la clave se guarda por empresa; la misma clave en dos empresas crea dos
  documentos.

## Errores

| Código | HTTP | Cuándo |
|---|---|---|
| `ISSUER_REQUIRED` | 400 | Falta `X-DTE-Issuer-NIT` o el emisor. |
| `ISSUER_MISMATCH` | 400 | El snapshot del documento es de otra empresa. |
| `UNAUTHORIZED_ISSUER` | 403 | Emisor no registrado o desactivado. |
| `ISSUER_INACTIVE` | 403 | Emisor desactivado, al emitir. |
| `DTE_DOCUMENT_TYPE_NOT_ALLOWED` | 403 | Tipo no habilitado para la empresa o el despliegue. |
| `ISSUER_MODE_UNAVAILABLE` | 409 | El modo de la empresa no es el del despliegue. |
| `INVALID_ISSUER`, `INVALID_ISSUER_MODE` | 400 | Datos de registro inválidos. |

## Pruebas

```bash
./scripts/run-tests.sh dte
```

Corre `npm test` en `node:22-slim` sobre una copia del servicio. Las pruebas multiemisor están en
`test/integration/multiemisor.test.js`.

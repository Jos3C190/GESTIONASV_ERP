# Plan: Ventas V3a — Servicio DTE multiemisor (modo simulado)

Rama: `feature/ventas-v3-dte`, desde `develop`, con V2 completo (#42 a #47).

Fuente: `docs/plan-area-ventas-el-salvador.pdf`.
- Módulo 5: «Facturación electrónica (DTE)».
- Secciones:
  - 6.3, estados del documento fiscal;
  - 6.4, arquitectura: ERP → cola de tareas → servicio DTE → firmador → Hacienda;
  - 6.5, facturación multiemisor.
- Bloque V3, resultado verificable: «Dos empresas emiten en simulado desde el ERP con numeración, credenciales y plantillas separadas; con credenciales, sellan en el ambiente de pruebas».

## Decisiones del usuario

- 15/11/2026: facturación multiemisor. Cada empresa es un emisor aislado y elige sus documentos. Cada sucursal es un establecimiento y cada caja un punto de venta. En los documentos compartidos se habla del «proyecto de referencia».
- 17/11/2026 (V3):
  - **Facturar**: acción sobre un pedido confirmado. Se emite un DTE por el pedido completo; facturar por entregas queda para después.
  - **Servicio**: se copia (sin tocar el original, que es de solo lectura) a `dte-service/` del monorepo, como contenedor propio, y ahí se vuelve multiemisor.
  - **Correo**: SMTP del ERP (Mailpit en desarrollo). Cada empresa define su nombre de remitente y su correo de respuesta.
  - **Sub-bloques**, una PR cada uno:
    - V3a: servicio multiemisor en modo simulado;
    - V3b: documento fiscal en el ERP (Facturar, bandeja, PDF y JSON guardados);
    - V3c: correo al cliente;
    - V3d: ambiente de pruebas de Hacienda (credenciales cifradas, certificado y firmador).
- El usuario delegó el merge de las PR cuando pasen los checks propios.

## Hechos verificados del servicio de referencia (solo lectura)

- Node 18+, Express, SQLite (better-sqlite3), pdfkit, qrcode y Ajv con los schemas oficiales. Unas 7300 líneas en `src/`; pruebas con `node --test` (`test/unit` y `test/integration`).
- Ya acepta el emisor por solicitud (contrato v2, `issuerContractV2.js`, con hash del snapshot), pero sigue siendo de un solo emisor:
  - el modo (`DTE_MODE`) es global;
  - la lista de NIT autorizados y el emisor por defecto vienen del entorno (`MH_*`);
  - `correlativos` usa como llave (tipo, año, establecimiento, punto de venta), sin NIT ni ambiente;
  - `dtes`, `eventos`, `idempotency_keys` y `contingencias` no guardan a qué emisor pertenecen;
  - hay un solo token de Hacienda en memoria.
- Rutas: `/api/dte/v2/factura`, `/v2/ccf` y `/v2/nota-credito` (contrato v2), más consulta, JSON, PDF, invalidación, contingencia y simulación. Usan API keys con alcances.

## Diseño de V3a

- **Copia**: `dte-service/` con `src/`, `test/`, `package.json` y `package-lock.json`, el Dockerfile y el README. Sin `node_modules` ni `data`. La procedencia queda en el README, sin nombrar al proyecto.
- **Contenedor**:
  - `dte-service` en `compose.yaml`, solo en la red interna;
  - volumen propio para SQLite;
  - API key generada en `.env` para el backend;
  - healthcheck a `/health`.
- **Registro de emisores** (`emisores`, administrado por el ERP con un alcance nuevo `issuers`):
  - columnas: NIT, nombre, modo (`simulated`, `hacienda-test` o `production`), tipos de DTE habilitados y activo;
  - reemplaza la lista de NIT del entorno;
  - el modo de cada documento sale de su emisor;
  - el arranque solo fija qué modos admite el despliegue.
- **Aislamiento**:
  - cada solicitud declara el emisor en `X-DTE-Issuer-NIT`, que debe coincidir con el snapshot;
  - toda consulta filtra por ese NIT;
  - un documento de otro emisor responde 404.
- **Numeración**: la llave pasa a (NIT, ambiente, tipo, año, establecimiento, punto de venta).
- **Idempotencia**: la clave se guarda por emisor.
- **Fuera de V3a**:
  - contingencia por empresa y token por empresa (V3d y V4);
  - correo (V3c);
  - integración con el ERP (V3b).
- **Pruebas**:
  - las del servicio siguen pasando;
  - se agregan: dos emisores con el mismo tipo, establecimiento y punto de venta llevan correlativos separados; un emisor no ve documentos del otro; un emisor inactivo o un tipo no habilitado se rechaza; un modo no admitido se rechaza.
  - El CI corre `npm test` del servicio.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: copiar el servicio y levantarlo.**
  - Copia sin dependencias ni datos.
  - Contenedor en compose, con su volumen y su API key.
  - README de procedencia.
  - Sus pruebas pasan sin cambios en el contenedor.
- [x] **Paso 2: registro de emisores y modo por emisor.**
  - Tabla `emisores` y su API (alcance `issuers`).
  - El emisor de la solicitud debe estar registrado, activo y con el tipo habilitado.
  - El modo sale del emisor.
- [x] **Paso 3: aislamiento de datos.**
  - Columnas `nit` y `ambiente` en `correlativos`, `dtes`, `eventos`, `idempotency_keys` y `contingencias`, con migración de bases existentes.
  - Filtro por emisor en todas las rutas.
- [x] **Paso 4: pruebas de aislamiento y CI.** Pruebas multiemisor y job de CI con `npm test`.
- [x] **Paso 5: documentación.** `docs/` del servicio: API, variables, emisores y modos.
- [x] **Paso 6: verificación y PR.** Batería completa del ERP más pruebas del servicio, y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: ninguno. V3a está terminado y en PR hacia `develop` con auto-merge. Sigue V3b.
  - Paso 6:
    - El CI genera `DTE_SERVICE_API_KEY` y valida el perfil `dte` de compose.
    - La batería completa del ERP no se corrió local porque la PR no toca backend ni frontend; la corre el CI. Pasaron `run-tests.sh dte` (467) y la validación de compose de desarrollo y producción.
  - Paso 5: `dte-service/docs/multiemisor.md` con arranque, variables, registro de emisores, aislamiento, errores y pruebas.
  - Paso 4:
    - `test/integration/multiemisor.test.js` (7 pruebas):
      - despliegue simulado sin emisor en el entorno;
      - dos empresas con el mismo establecimiento y punto de venta;
      - series separadas, propiedad, clave compartida, emisor que no coincide, no registrado, inactivo, tipo no habilitado y modo no disponible.
    - `scripts/run-tests.sh dte` corre `npm test` en `node:22-slim` sobre una copia, y `all` lo incluye: así el CI lo cubre en «Tests and static quality».
    - Resultados: 467 pruebas en verde y `npm audit --omit=dev` sin vulnerabilidades.
  - Paso 3:
    - `src/middleware/emisorSolicitud.js` (`X-DTE-Issuer-NIT`):
      - es obligatorio sin emisor en el entorno y debe coincidir con el snapshot;
      - `propietarioDocumento` responde 404 a códigos de otro emisor, con `router.param` en dte y simulación.
    - La tabla `correlativos` suma `nit` y `ambiente` a su llave, con migración que conserva las filas heredadas (`''`).
    - El emisor heredado del entorno conserva su serie.
    - `dtes.nit` guarda el emisor de cada documento.
    - La clave de idempotencia se guarda como `NIT:clave` cuando hay encabezado.
    - Eventos y contingencias heredan la propiedad de su documento; su columna propia llega con contingencia por empresa (V4).
    - Pruebas: 460 en verde.
  - Paso 2:
    - `src/services/issuerRegistry.js` (tabla `emisores`) y `src/routes/emisores.routes.js`: `GET /api/emisores`, `GET` y `PUT /api/emisores/:nit`, con alcance `issuers`.
    - `emitir()` exige emisor registrado, activo, en el modo del despliegue y con el tipo habilitado.
    - En modo simulado las variables `MH_*` son opcionales (`config.emisor` es null) y se agrega `config.ambiente`.
    - Un NIT de `DTE_AUTHORIZED_ISSUER_NITS` sin registrar sigue autorizado, por compatibilidad.
    - Compose:
      - `dte-service` con perfil `dte` y volumen `dte-data`;
      - `DTE_SERVICE_API_KEY` en `.env.example` y en `scripts/setup.sh` (`ensure_secret`).
    - Pruebas: 457 heredadas y 3 del registro, en verde.
- **Decisiones técnicas**:
  - En V3a el modo de cada emisor debe coincidir con el del despliegue (`ISSUER_MODE_UNAVAILABLE`). Para que convivan modos hace falta una sesión con Hacienda por emisor (V3d).
  - Para usar el servicio, el `.env` local necesita `DTE_SERVICE_API_KEY`. `scripts/setup.sh` la genera; no se leyó ni se editó el `.env` del usuario.
  - Paso 1:
    - Servicio copiado a `dte-service/`: 125 archivos, sin `.env`, `data`, `node_modules` ni `firmador-docker`, que tiene el certificado.
    - El agente de usuario pasa a `GestionaSV-DTE/2.0`.
    - Sus 457 pruebas pasan sin cambios en `node:22-slim`. Se corren sobre una copia en `/tmp` para no escribir `node_modules` en el repo.
    - El contenedor se agrega a compose en el paso 2, cuando ya no exija el emisor por variables `MH_*`.
- **Contexto**: el ERP es multiempresa; no se fija nada fiscal por despliegue y se prueba siempre con dos empresas. El proyecto de referencia (`D:\josec\Documents\PROYECTO`) es de solo lectura: no se modifica, no se corren sus pruebas ni nada que escriba ahí.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con un objetivo explícito. Sin argumento corre la batería completa, de unos 45 minutos.
  - No hacer commits mientras corre la batería.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop` con Auto-fix y auto-merge (merge commit).
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

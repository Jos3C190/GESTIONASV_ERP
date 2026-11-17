# Plan: Ventas V3d — Ambiente de pruebas de Hacienda por empresa

Rama: `feature/ventas-v3d-hacienda`, desde `develop` con V3c (#50).

Fuente: `docs/plan-area-ventas-el-salvador.pdf` (módulo 5, DTE).
Documentación oficial: `D:\josec\Downloads\Documentacion DTE\`, en especial el Manual Técnico v2, el firmador `svfe-api-firmador.zip` y los schemas.

## Decisiones del usuario

- 17/11/2026 (V3d):
  - **Credenciales**: todavía no hay credenciales del ambiente de pruebas. Se construye y se prueba contra un Hacienda simulado (stub) y el firmador real; la prueba contra `apitest.dtes.mh.gob.sv` queda para cuando las haya.
  - **Dónde**: en el ERP, en una pestaña «Hacienda» de Configuración fiscal. Ahí se suben el certificado y las contraseñas (API y llave privada), que se guardan cifrados. El ERP se los entrega al servicio DTE al registrar a la empresa. Incluye «Probar conexión».
  - **Firmador**: el oficial, compilado desde `svfe-api-firmador.zip` (Java 21) dentro de compose. Los certificados de cada empresa van en un volumen compartido con el servicio.
  - **Modos**: por empresa. Cada empresa usa el modo de su perfil fiscal (simulado, pruebas o producción) en el mismo despliegue.
- Decisiones anteriores que siguen vigentes:
  - Producción con la facturación apagada (perfil `dte`), salvo que se decida otra cosa al cerrar V3d.
  - Merge delegado cuando pasen los checks propios.
  - El proyecto de referencia es de solo lectura.

## Hechos verificados

- El servicio asume un emisor por despliegue para Hacienda:
  - `MH_NIT`, `MH_PASSWORD_API` y `MH_PASSWORD_PRI` vienen del entorno; `DTE_MODE` es global.
  - `authService` guarda un solo token; `firmadorClient` firma con `config.emisor.nit` y `passwordPri`.
  - `issuerRegistry.exigirEmision` exige que el modo del emisor sea el del despliegue (`ISSUER_MODE_UNAVAILABLE`).
  - Hay 32 usos de `config.dteMode` y 110 de `config.emisor` en `src/`.
- Autenticación con Hacienda: `POST /seguridad/auth` con `user` (el NIT) y `pwd` (la contraseña de la API). El token dura 48 h en pruebas y 24 h en producción.
- Firmador oficial: `POST /firmardocumento/` con `nit`, `activo`, `passwordPri` y `dteJson`. Firma con `{nit}.crt` de su carpeta de certificados, así que varias empresas pueden compartir un firmador.
  - Errores de configuración: 803 (no hay certificado para el NIT o la contraseña no corresponde; verificado), 809 (datos) y 812.
  - Busca `{nit}.crt` en `./uploads` o en `CERTIFICATE_HOME`. El `.crt` es un XML (`CertificadoMH`) con las llaves; `privateKey.clave` es el SHA-512 de la contraseña privada. Se puede generar un certificado de prueba propio para firmar de verdad sin Hacienda.
  - El `Dockerfile` oficial copia `target/*-exec.jar`: hace falta una etapa Maven previa. Puerto 8113, perfil `nonssl`.
- El ERP ya cifra con AES-GCM (`app/core/secret_encryption.py`) y el modo de la empresa está en `company_fiscal_profiles.operating_mode` (`simulated`, `test`, `production`).
- El servicio ya numera por NIT y ambiente, y el documento fiscal guarda su `mode`.
- Hay un stub de Hacienda en las pruebas del servicio (`test/integration/haciendaStub.test.js`).

## Diseño

- **Firmador en compose**:
  - Servicio `dte-signer`, que construye el jar con Maven en una etapa y lo corre sobre `amazoncorretto:21-alpine`.
  - Volumen `dte-certificates`: el servicio DTE escribe ahí `{nit}.crt` y el firmador lo lee.
  - Sin puertos publicados.
- **Servicio DTE, emisor con credenciales y modo propio**:
  - `PUT /api/emisores/:nit` acepta además `passwordApi`, `passwordPri` y `certificado` (base64). En modos distintos de simulado son obligatorios.
  - Las contraseñas se guardan cifradas en SQLite con una clave del servicio (`DTE_CREDENTIALS_KEY`); el certificado se escribe en el volumen del firmador.
  - El modo y el ambiente se leen del emisor, no del despliegue (`00` para pruebas, `01` para producción):
    - token de Hacienda por NIT;
    - firma con el NIT y la contraseña del emisor;
    - host de Hacienda según el modo del emisor.
  - Se quita `ISSUER_MODE_UNAVAILABLE`: `DTE_MODE` pasa a ser el modo máximo que el despliegue permite (simulado ⊂ pruebas ⊂ producción).
  - `POST /api/emisores/:nit/probar` autentica contra Hacienda (o el stub) y verifica que el certificado esté.
- **ERP**:
  - Tabla `company_hacienda_credentials` (migración 0129): contraseña de la API, contraseña de la llave privada y certificado, todo cifrado. Además, el NIT del certificado, la fecha de carga y la última prueba de conexión.
  - `GET`, `PUT` y `DELETE /fiscal/hacienda-credentials` y `POST …/test`. Nada secreto vuelve.
  - Al registrar al emisor, `dte-worker` envía el modo del perfil y, fuera de simulado, las credenciales.
  - Pasar el perfil a pruebas exige credenciales cargadas y probadas.
- **Pantalla**: pestaña «Hacienda» en Configuración fiscal (subir el certificado, contraseñas de solo escritura, probar la conexión, estado y ayuda).
- **Seguridad**: secretos solo en memoria al usarlos, nunca en la bitácora ni en registros; permisos `fiscal_settings:manage`.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: firmador oficial en compose.** Construcción Maven más JRE, volumen de certificados, salud y prueba de que responde (error 803 sin certificado).
- [x] **Paso 2: servicio, emisores con credenciales.** Registro con contraseñas cifradas y certificado al volumen. Pruebas.
- [x] **Paso 3: servicio, modo y ambiente por emisor.**
  - Token por NIT, firma por emisor, host y ambiente por modo; sin `ISSUER_MODE_UNAVAILABLE`.
  - Pruebas con el stub, con dos emisores en modos distintos.
- [x] **Paso 4: servicio, probar la conexión del emisor.** Endpoint y pruebas.
- [x] **Paso 5: ERP, migración `0129` y credenciales cifradas.** Aplicación, API, regla para pasar a pruebas y e2e.
- [x] **Paso 6: ERP, registro del emisor con modo y credenciales.** `dte-worker` y e2e contra el stub.
- [x] **Paso 7: frontend.** Pestaña «Hacienda». vitest.
- [ ] **Paso 8: documentación.** API, esquema y manuales (cómo obtener el certificado y las credenciales de pruebas).
- [ ] **Paso 9: verificación y PR.** Batería completa, QA en el navegador con el stub y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: 8 (documentación).
  - Paso 7: pestaña «Hacienda» en Configuración fiscal (`FiscalHaciendaPanel.svelte`).
    - El certificado se lee en el navegador y viaja en base64; las contraseñas no se vuelven a mostrar.
    - Estado: Sin cargar, Sin probar o Probadas, con el NIT y la huella del certificado.
    - «Probar conexión» muestra la autenticación y la firma por separado; también se puede quitar.
    - vitest: 4 pruebas nuevas.
  - Paso 6:
    - `dte-worker` registra al emisor con el modo del documento y, fuera de simulado, con sus credenciales descifradas en memoria (`_credentials`).
    - Sin credenciales, el documento falla sin reintentar (`hacienda_credentials_missing`).
    - e2e `tests/e2e/test_hacienda_issuing.py` con un cliente DTE falso. El camino real (firmador y Hacienda simulados) lo cubre `modoPorEmisor.test.js` en el servicio.
    - Decisión: no se levanta un segundo servicio DTE en modo pruebas para las e2e del ERP; la QA con el stub se hará a mano si hace falta.
  - Paso 5:
    - Migración 0129 `company_hacienda_credentials`: contraseñas y certificado cifrados con AES-GCM (`secret_encryption`), más la huella y el NIT del certificado y la última prueba.
    - Dominio `hacienda_credentials.py`: el certificado debe ser del NIT de la empresa y abrir con su contraseña privada (SHA-512, como el firmador).
    - Casos de uso `application/fiscal/hacienda_credentials.py`:
      - lo que se deja en blanco se conserva;
      - quitar exige estar en simulado;
      - probar registra a la empresa en el servicio con sus credenciales (modo pruebas, o producción si ya lo está) y llama a `/probar`.
    - API `/fiscal/hacienda-credentials` (GET, PUT, DELETE y `/test`); nada secreto vuelve ni entra en la bitácora.
    - `IssuerFacts.hacienda_credentials_tested`: pasar a pruebas exige credenciales probadas (`fiscal_test_not_ready`) y producción también lo exige.
    - Servicio: `/probar` informa si el despliegue no admite el modo de la empresa.
    - Pruebas: unitarias del certificado, de migración y e2e `test_hacienda_credentials.py`. `test_fiscal_settings` ahora siembra credenciales probadas antes de pasar a producción.
  - Paso 4: `POST /api/emisores/:nit/probar` (alcance `issuers`, `src/services/issuerConnectionTest.js`). Autentica con Hacienda y firma un documento de prueba con el certificado del emisor; devuelve `{ok, autenticacion:{ok,mensaje}, firma:{ok,mensaje}}`. No transmite ni consume números de control; en simulado responde ok sin salir. Servicio: 483 en verde.
  - Paso 3:
    - `src/services/issuerContext.js` (`AsyncLocalStorage`): el middleware `contextoEmisor` corre cada solicitud de `/api/dte` con el modo, el ambiente, las URLs de Hacienda y las credenciales (descifradas solo al usarlas) del emisor del encabezado.
    - `retryQueue` usa el emisor de cada documento. Sin contexto se usa el emisor del entorno, como antes.
    - `authService` guarda un token por NIT y modo; el firmador recibe el NIT y la contraseña privada del emisor; la identificación y la transmisión usan el ambiente del emisor.
    - En `dte.routes.js`, «simulado» es el modo del emisor.
    - `DTE_MODE` es el modo máximo (simulado < pruebas < producción): un emisor de un modo mayor recibe `ISSUER_MODE_UNAVAILABLE`.
    - Config: el emisor del entorno solo existe si hay `MH_NIT`. Sin `MH_*_URL` se usan las rutas oficiales del host del modo, y `haciendaPorModo` da las URLs de otro modo.
    - Prueba nueva `test/integration/modoPorEmisor.test.js`: dos empresas en pruebas y una simulada en el mismo despliegue, con token y firma por empresa y ambiente 00; credenciales equivocadas; producción rechazada. Servicio: 482 en verde.
  - **Límite conocido** (para V4): la contingencia ya usa el token y las URLs del emisor, pero `contingenciaService` todavía toma datos del emisor del entorno (3 usos de `config.emisor`). La invalidación no depende de `config.emisor`. Se revisa con V4.
  - **Para las pruebas del paso 6 y la QA**: el despliegue de desarrollo tiene `DTE_MODE=simulated`, así que una empresa en pruebas recibe 409. Para probar contra el stub hay que levantar el servicio con `DTE_MODE=hacienda-test` y las `MH_*_URL` del stub.
  - Paso 2:
    - `src/services/issuerCredentials.js`:
      - contraseñas cifradas con AES-256-GCM (`DTE_CREDENTIALS_KEY`, formato `v1:`) en la tabla `emisor_credenciales`;
      - certificado validado (mismo NIT y SHA-512 de la contraseña privada) y escrito de forma atómica en `DTE_CERTIFICATES_DIR`.
    - `PUT /api/emisores/:nit` acepta `credenciales` y, fuera de simulado, las exige (`ISSUER_CREDENTIALS_REQUIRED`). La respuesta solo trae `credenciales.{configuradas, certificadoPresente, certificadoSha256}`.
    - Helper `test/helpers/certificadoPrueba.js`: genera un `.crt` con llaves RSA reales. Verificado a mano: el firmador oficial firma con él (JWS RS512 que se verifica con la llave pública).
    - `DTE_CREDENTIALS_KEY` está en compose, `setup.sh`, `.env.example` y CI. El `.env` del usuario todavía no la tiene: pedir permiso para agregarla al llegar a las e2e del paso 6.
    - Servicio: 479 pruebas en verde.
  - Paso 1:
    - Código oficial copiado sin cambios a `dte-signer/`, con `Dockerfile.erp` (Maven 3.9.9 + Temurin 21 JRE, usuario sin privilegios, salud en `/firmardocumento/status`) y `PROCEDENCIA.md`.
    - Servicio `dte-signer` en compose (perfil `dte` en producción) y volumen `dte-certificates`: el firmador lo monta de solo lectura en `/certificados` y `dte-service` lo escribe en `/app/certificados`, que la imagen crea con dueño `node`.
    - `dte-service` recibe `FIRMADOR_URL` y `DTE_CERTIFICATES_DIR`.
    - Verificado: compila, arranca en 6 s y, sin certificado, responde 803.
- **Contexto**:
  - El frontend usa SvelteKit 3.
  - El servicio DTE se prueba con `./scripts/run-tests.sh dte`.
  - Si el login de desarrollo da 500 o una pantalla nueva no aparece, reiniciar el contenedor `frontend`.
  - `dte-worker` no recarga solo: reiniciarlo tras cambios.
- **Comandos**:
  - Pruebas con objetivo explícito; sin argumento corre la batería completa (unos 35 a 45 minutos).
  - No hacer commits ni correr pruebas de base mientras corre la batería. Tampoco agregar migraciones mientras corre: las guardas de traslados comparan la revisión de la base con la cabeza del repositorio.
  - Git: `git -c http.sslBackend=schannel` para `fetch` y `push`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop` con Auto-fix y auto-merge.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.
  - Credenciales reales: nunca en el chat ni en archivos del repo; las carga el usuario en la pantalla.

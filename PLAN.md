# Plan: Ventas V3c — Enviar el DTE al cliente por correo

Rama: `feature/ventas-v3c-correo`, desde `develop` con V3b (#49).

Fuente: `docs/plan-area-ventas-el-salvador.pdf`.
- Módulo 5 (DTE): «Envío al cliente del JSON y el PDF por correo, y descarga desde el sistema».
- Protección de datos: el aviso de privacidad de la empresa va en el correo del documento (art. 24).

## Decisiones del usuario

- 17/11/2026 (V3c):
  - **SMTP**: uno por despliegue, en variables de entorno. Cada correo sale con el nombre de la empresa como remitente y con `Reply-To` al correo DTE de esa empresa. En desarrollo se usa Mailpit, un buzón de prueba en compose.
  - **Cuándo**: automático al emitirse, si el cliente tiene correo. Además hay un botón «Enviar por correo» para reenviar o mandar a otras direcciones. Cada envío queda registrado.
  - **Simulados**: sí se envían, con «SIMULADO — sin validez fiscal» en el asunto y en el cuerpo.
  - **Cambio, SMTP por empresa** (tras la QA): cada empresa configura su propio SMTP y su correo remitente en Configuración fiscal. El dominio y el DNS (SPF, DKIM, DMARC) son responsabilidad de la empresa.
    - Se autentica con usuario y contraseña (de aplicación en Google), sobre STARTTLS o SSL. OAuth de Microsoft queda como mejora posterior.
    - Decisión por defecto, tomada por Claude: si la empresa no configuró su SMTP, se usa el del servidor (en desarrollo, Mailpit; en producción viene vacío).
- Decisiones anteriores que siguen vigentes (V3b):
  - Producción con la facturación apagada hasta V3d.
  - Merge delegado cuando pasen los checks propios.

## Hechos verificados

- El ERP no tiene envío de correo: no hay SMTP, ni librería, ni configuración.
- El documento fiscal (V3b) guarda `dte_json` en la base y el PDF en el almacenamiento (`pdf_object_key`). El almacenamiento tiene `download_to`.
- El cliente tiene `email` en su ficha (`CustomerDraft.email`).
- Hay un aviso de privacidad versionado por empresa (`PrivacyUseCases.current_notice`).
- El trabajador `dte-worker` (arq, cola `arq:dte`) emite y tiene conciliación periódica.
- Producción no tiene Redis ni almacenamiento: allí la facturación sigue apagada.

## Diseño

- **Envío SMTP**:
  - `smtplib` de la biblioteca estándar dentro de `asyncio.to_thread`, sin dependencias nuevas.
  - Puerto `EmailSender` en el dominio y adaptador `SmtpEmailSender`.
  - Configuración: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_ADDRESS`, `SMTP_SECURITY` (`none`, `starttls` o `ssl`) y `SMTP_TIMEOUT_SECONDS`.
  - `SMTP_HOST` vacío deshabilita el envío.
- **Registro** (`sales_fiscal_document_emails`, migración 0127): documento, destinatarios, origen (`auto` o `manual`), estado (`pending`, `sent`, `failed`), intentos, error, `message_id`, quién lo pidió y fechas.
- **Mensaje** (dominio):
  - Asunto: tipo de documento, número de control, empresa y, si es simulado, la marca.
  - Cuerpo en texto y HTML: saludo, datos del documento (código de generación, fecha, total), adjuntos y el aviso de privacidad vigente.
  - Adjuntos: `{número de control}.pdf` y `.json`.
- **Flujo**:
  - Al quedar `issued` o `simulated`, el trabajador crea el envío automático si el cliente tiene correo y lo encola.
  - El envío manual valida de 1 a 5 destinatarios y lo encola.
  - El trabajador baja el PDF del almacenamiento (o del servicio si no está guardado), arma el mensaje y envía; reintenta los errores temporales.
- **Permisos**: enviar requiere `sales_invoices:issue`; ver el historial, `sales_invoices:read`. Todo queda en la bitácora.
- **Pantallas**: «Enviar por correo» en el detalle del documento y en la sección Factura del pedido (con el correo del cliente propuesto), e historial de envíos en el detalle.
- **SMTP por empresa** (pasos 7 a 10):
  - Tabla `company_email_settings` (migración 0128): servidor, puerto, seguridad, usuario, contraseña cifrada con AES-GCM (`app/core/secret_encryption.py`), correo y nombre del remitente, activo y resultado de la última prueba.
  - La contraseña nunca se devuelve por la API: solo `has_password`. Si se deja vacía al guardar, se conserva la anterior.
  - Al enviar se usa el SMTP de la empresa si está activo; si no, el del servidor; si no hay ninguno, no se envía.
  - «Enviar correo de prueba» manda un correo a la dirección que se indique y guarda el resultado.
  - Permisos: `fiscal_settings:read` y `fiscal_settings:manage`. Se audita sin la contraseña.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: envío SMTP.**
  - Configuración, puerto y adaptador con pruebas unitarias (SMTP falso).
  - Mailpit en compose y `.env.example`.
- [x] **Paso 2: migración `0127` y modelo** del registro de envíos, con prueba de migración.
- [x] **Paso 3: dominio del mensaje.** Asunto, cuerpo, marca de simulado, aviso de privacidad y validación de destinatarios. Pruebas unitarias.
- [x] **Paso 4: trabajador, aplicación y API.**
  - Envío automático tras emitir y envío manual.
  - Historial y bitácora.
  - e2e con Mailpit (el correo llega con sus dos adjuntos).
- [x] **Paso 5: frontend.** «Enviar por correo» e historial. vitest.
- [x] **Paso 6: documentación.** `docs/api.md`, `docs/database-schema.md` §37 y manual de facturación.
- [x] **Paso 7: migración `0128`** de la configuración de correo por empresa, con prueba de migración.
- [x] **Paso 8: aplicación y API.** Leer, guardar (contraseña cifrada y escrita solo una vez), quitar y probar. Auditoría. e2e.
- [x] **Paso 9: envío con el SMTP de la empresa.** Elegir el remitente por documento en `dte-worker`; el historial indica si hay correo disponible. e2e con Mailpit como SMTP de la empresa.
- [x] **Paso 10: frontend.** Pestaña «Correo» en Configuración fiscal con prueba de envío. vitest.
- [x] **Paso 11: documentación.** API, esquema §38 y manuales.
- [x] **Paso 12: verificación y PR.** Batería completa, QA en el navegador con Mailpit y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: V3c terminado; PR hacia `develop`. Sigue V3d (ambiente de pruebas de Hacienda).
  - Paso 12:
    - Batería completa en verde: pytest 1968 (2 omitidas), servicio DTE 474, vitest, lint y build. Se confirmó que los 7 fallos anteriores eran por la migración agregada mientras corría.
    - QA en el navegador con Mailpit como SMTP propio de Grupo Lorena: guardar, probar («se envió bien») y reenviar el DTE. El correo salió como «Pastelería Lorena <facturacion@grupolorena.example>», con dos adjuntos y `Reply-To` al correo DTE.
    - En desarrollo, Grupo Lorena queda con Mailpit como SMTP propio (útil para demostrar; se quita en Configuración fiscal → Correo).
  - La batería sobre los pasos 1 a 6 dio 1947 pasadas y 7 fallos. Los 7 son guardas de migración de traslados que comparan la revisión de la base con la cabeza del repositorio: la 0128 se agregó mientras corría. La batería nueva debe confirmarlo.
  - Error latente corregido: `secret_encryption._key` no aceptaba la clave sin relleno que genera `scripts/setup.sh` (base64url de 43 caracteres), así que en desarrollo tampoco se podían cifrar los datos bancarios de proveedores. Ahora completa el relleno. Pruebas en `test_supplier_master_data.py`; `fails_closed_without_key` ahora también quita la variable de entorno.
  - Paso 7: migración 0128 `company_email_settings`, modelo `CompanyEmailSettingsModel` y prueba de migración. Ya está aplicada en desarrollo.
  - Paso 8:
    - Dominio `domain/entities/company_email.py` (`validate_settings`) con 9 pruebas unitarias en verde; puerto y repositorio.
    - Casos de uso `application/fiscal/email_settings.py`; el remitente se inyecta con `company_email_sender`, que descifra en memoria.
    - API `/fiscal/email-settings` (GET, PUT, DELETE y `/test`).
  - Paso 9:
    - `process_fiscal_email` usa el SMTP de la empresa si está activo; si no, el del servidor; si no hay ninguno, falla con `email_unavailable`.
    - `SalesInvoiceEmailUseCases.available` decide `enabled` y bloquea el envío manual.
    - `dte-worker` recibe `SUPPLIER_DATA_ENCRYPTION_KEY`. e2e en `tests/e2e/test_company_email_settings.py`.
  - Paso 10: pestaña «Correo» (`FiscalEmailPanel.svelte`) con prueba de envío y ayuda para Google y Microsoft 365. vitest: 70 en verde (fiscal y ventas).
  - Paso 11: `api.md` («Company outgoing email»), esquema §38, manual de configuración fiscal §5 y manual de facturación §6.
  - QA de los pasos 1 a 6 en el navegador: el envío manual desde el detalle del documento llegó a Mailpit, a dos destinatarios, con el PDF, el JSON y el aviso de privacidad de Grupo Lorena. El historial lo marcó Enviado y la vista a 375 px no se desborda.
  - La primera batería completa de V3c corrió sobre los pasos 1 a 6.
  - Paso 6: `docs/api.md` (Sales invoice emails), `docs/database-schema.md` §37 y sección 6 del manual de facturación.
  - Paso 5: componente `FiscalDocumentEmails.svelte`, en el detalle del documento y en la sección Factura del pedido.
    - Propone el correo del cliente y acepta varios separados por comas, punto y coma o espacios.
    - Historial con estado (Enviando, Enviado, No se envió), origen, quién lo pidió y error; se actualiza solo mientras hay envíos pendientes.
    - Avisa si el servidor no envía correos. vitest: 5 pruebas nuevas.
  - Paso 4:
    - Repositorio `sales_fiscal_email_repository.py`; el documento fiscal trae `customer_email`.
    - Casos de uso `application/sales_invoices/emails.py` (envío manual e historial).
    - Entrega en `infrastructure/dte_email.py`:
      - `queue_auto_email` crea el envío automático al emitirse;
      - `process_fiscal_email` baja el PDF del almacenamiento o del servicio, arma el mensaje y envía.
    - `dte-worker`: tarea `send_fiscal_email`; la conciliación también reencola los envíos pendientes.
    - API:
      - `GET /sales/fiscal-documents/{id}/emails` devuelve `enabled`, `customer_email` e `items`;
      - `POST …/emails` con `{recipients?}` responde 202.
      - Bitácora: `REQUEST_FISCAL_DOCUMENT_EMAIL`, `FISCAL_DOCUMENT_EMAIL_SENT` y `_FAILED`.
    - e2e: 2 pruebas nuevas en `test_sales_invoices.py` que comprueban en Mailpit (`http://mailpit:8025/api/v1/search`) la llegada con dos adjuntos, el `Reply-To`, que no se reenvía, las reglas y los permisos.
    - Después de cambiar el código del trabajador hay que reiniciar `dte-worker`; arq no recarga solo.
  - Paso 3: `app/domain/entities/sales_fiscal_email.py`.
    - `normalize_recipients`: recorta, pasa a minúsculas, quita repetidos y acepta de 1 a 5 correos.
    - `customer_recipients` usa el correo de la ficha del cliente.
    - `compose` arma el asunto, el texto y el HTML escapado, con la fecha en El Salvador y el total en formato `$1,250.00`.
    - Marca de simulado en el asunto y en el cuerpo; aviso de privacidad al pie.
    - Al cliente se le trata de usted.
  - Paso 2: `sales_fiscal_document_emails`, con:
    - destinatarios `text[]` (de 1 a 5) y origen `auto` o `manual`; el manual exige quién lo pidió;
    - estado `pending`, `sent` o `failed`; `sent` exige `sent_at` y `message_id`;
    - un solo envío automático por documento.
    - Modelo `SalesFiscalDocumentEmailModel`; prueba `tests/integration/test_sales_fiscal_document_emails_migration.py`.
  - Paso 1:
    - Puerto `app/domain/ports/email_sender.py` y adaptador `app/infrastructure/smtp_email_sender.py` (smtplib en hilo; errores 4xx y de red son reintentables).
    - Configuración `SMTP_*`; `SMTP_HOST` exige `SMTP_FROM_ADDRESS`.
    - Mailpit `axllent/mailpit:v1.21.8` con su interfaz en `127.0.0.1:8025`; backend y `dte-worker` apuntan a `mailpit:1025` sin TLS. En producción, Mailpit va con el perfil `local-mail` y el SMTP sale de las variables.
    - Prueba de humo: un correo real llegó a Mailpit con su adjunto.
- **Contexto**:
  - El frontend usa SvelteKit 3.
  - El servicio DTE se prueba con `./scripts/run-tests.sh dte`.
  - El proyecto de referencia es de solo lectura.
  - Si el login de desarrollo da 500 tras cambios grandes del frontend, reiniciar el contenedor `frontend`.
- **Comandos**:
  - Pruebas con objetivo explícito; sin argumento corre la batería completa (unos 45 minutos).
  - No hacer commits mientras corre la batería.
  - Git: `git -c http.sslBackend=schannel` para `fetch` y `push`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop` con Auto-fix y auto-merge.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

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

## Pasos

- [x] **Paso 0: plan.**
- [ ] **Paso 1: envío SMTP.**
  - Configuración, puerto y adaptador con pruebas unitarias (SMTP falso).
  - Mailpit en compose y `.env.example`.
- [ ] **Paso 2: migración `0127` y modelo** del registro de envíos, con prueba de migración.
- [ ] **Paso 3: dominio del mensaje.** Asunto, cuerpo, marca de simulado, aviso de privacidad y validación de destinatarios. Pruebas unitarias.
- [ ] **Paso 4: trabajador, aplicación y API.**
  - Envío automático tras emitir y envío manual.
  - Historial y bitácora.
  - e2e con Mailpit (el correo llega con sus dos adjuntos).
- [ ] **Paso 5: frontend.** «Enviar por correo» e historial. vitest.
- [ ] **Paso 6: documentación.** `docs/api.md`, `docs/database-schema.md` §37 y manual de facturación.
- [ ] **Paso 7: verificación y PR.** Batería completa, QA en el navegador con Mailpit y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: 1 (envío SMTP).
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

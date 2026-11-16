# Plan: Ventas V1d — Datos personales

Rama: `feature/ventas-v1d-datos-personales`, desde `develop` (ya incluye V1a, V1b y V1c, PR #38 a #40).
Fuente: `docs/plan-area-ventas-el-salvador.pdf`, sección 3.7 (Protección de datos personales) y bloque V1 («aviso de privacidad, consentimientos y solicitudes de titulares de datos»).
Con V1d termina el bloque V1. Después viene V2 (precios e impuestos), que rehace cotizaciones y ventas.

## Alcance

Cada empresa cumple la Ley para la Protección de Datos Personales sobre los datos de sus clientes:
- un aviso de privacidad versionado;
- consentimientos por cliente y finalidad;
- una bandeja de solicitudes ARCO-POL con plazo;
- la exportación y la anonimización de los datos de un cliente;
- un registro de vulneraciones con su plazo de 72 horas.

Queda fuera de V1d:
- **Enlazar el aviso en el correo del DTE y en caja.** Lo harán V3 y V6, leyendo la versión vigente que expone este bloque.
- **Bitácora de cada consulta de datos.** El ERP ya registra los cambios; registrar cada lectura se evaluará aparte.

## Hechos verificados

Fuente: D.L. 144 de 2024, reformado por el D.L. 659 de 2026. Los textos están en el scratchpad de la sesión: `lpdp/d144u.txt` y `d659u.txt`.

**Derechos ARCO-POL** (art. 2 literal i, y arts. 6 a 14). Son siete: acceso, rectificación, cancelación, oposición, portabilidad, olvido y limitación.

**Plazos:**
| Trámite | Plazo | Artículo |
|---|---|---|
| Responder una solicitud | 20 días hábiles desde la recepción. Prorrogable una vez por otros 20, con causa justificada. | 20, reformado por el D.L. 659 |
| Pedir al titular que corrija su solicitud (prevención) | Una sola vez; el titular tiene 10 días hábiles para subsanar. Si no lo hace, se archiva. | 18 |
| Devolver una solicitud cuando no es competencia de la empresa o pide otro derecho | 5 días hábiles | 19 |
| Notificar una negativa | Resolución motivada, dentro de 3 días hábiles desde la decisión. | 22 |
| Atender la revocación del consentimiento | 5 días hábiles | 30 |
| Notificar una vulneración a la ACE, a la Fiscalía y a los afectados | 72 horas desde que se conoce | 25 |

**Aviso de privacidad (art. 24).** Debe indicar:
1. el domicilio del responsable;
2. los datos que se tratan, señalando los sensibles;
3. el fundamento legal;
4. las finalidades, separando las que requieren consentimiento;
5. cómo ejercer los derechos y cómo revocar el consentimiento;
6. dónde y cómo presentar las solicitudes (según la reforma);
7. cómo se comunicarán los cambios al aviso;
8. el encargado del tratamiento, si existe;
9. el uso de cookies.

**Supresión (arts. 10 y 11).** No procede si contraviene una obligación legal. Los documentos fiscales se conservan 10 años (Código Tributario, art. 147), así que la supresión se resuelve anonimizando el cliente en el maestro.

**Días hábiles.** Se excluyen los sábados, los domingos y los asuetos nacionales del Código de Trabajo (art. 190):
- 1 de enero;
- jueves, viernes y sábado de Semana Santa;
- 1 de mayo, 10 de mayo y 17 de junio;
- 6 de agosto y 15 de septiembre;
- 2 de noviembre y 25 de diciembre.

## Decisiones

- **Aviso de privacidad versionado** (`company_privacy_notices`).
  - Cada publicación crea una versión nueva y la anterior queda en el historial. Los consentimientos guardan la versión vigente al otorgarse.
  - Al publicar, el sistema exige que el texto cubra cada elemento del art. 24, con una casilla por elemento marcada por quien publica.
  - El sistema ofrece una plantilla inicial con los datos de la empresa.
- **Consentimientos** (`customer_consents`).
  - Se registran por cliente y finalidad: `marketing`, `profiling` o `third_party_sharing`.
  - Llevan el medio (en persona, teléfono, correo, web o escrito), la fecha, quién lo registró y la versión del aviso.
  - La revocación queda con fecha y medio. Solo puede haber un consentimiento vigente por cliente y finalidad.
  - Los datos fiscales para facturar no requieren consentimiento (art. 28 f).
- **Solicitudes ARCO-POL** (`data_subject_requests`).
  - Llevan:
    - un código `SOL-00001`;
    - el titular, que puede ser cliente o no, con su nombre, documento y medio de respuesta;
    - el derecho y la descripción;
    - la fecha de recepción y el plazo, calculado en días hábiles;
    - el responsable, que es un usuario de la empresa.
  - Estados:
    - `received`: recibida;
    - `in_progress`: en trámite;
    - `awaiting_correction`: prevención, con su propio plazo de 10 días hábiles;
    - `extended`: prorrogada, con motivo obligatorio y plazo nuevo;
    - `resolved`: atendida;
    - `denied`: denegada, con motivo;
    - `returned`: devuelta por no ser competencia o pedir otro derecho;
    - `archived`: archivada si el titular no subsanó.
  - La resolución guarda la respuesta y la fecha.
- **Acciones sobre un cliente:**
  - **Exportar sus datos** en JSON, para los derechos de acceso y portabilidad: ficha, direcciones de entrega, consentimientos y referencias de sus cotizaciones y ventas.
  - **Anonimizarlo**, para la cancelación y el olvido:
    - borra la identidad, el contacto y la dirección, y quita las direcciones de entrega;
    - desactiva el cliente y guarda la fecha en `anonymized_at`;
    - exige una solicitud de cancelación u olvido en trámite y no se deshace.
  - Los documentos fiscales emitidos se conservan; V3 guardará en cada DTE la copia de los datos del receptor.
- **Vulneraciones** (`personal_data_incidents`).
  - Llevan un código `INC-00001`, la fecha en que se conoció y la de ocurrencia, la descripción, los datos y titulares afectados, y las medidas.
  - El límite de notificación es la fecha en que se conoció más 72 horas.
  - Se registra la constancia de cada notificación: ACE, Fiscalía y titulares, con fecha y referencia.
  - Estados: abierto y cerrado. Solo se cierra con las tres notificaciones registradas o con un motivo cuando no aplica la de titulares.
- **Permisos nuevos** (módulo `privacy`):
  - `privacy:read`: consultar;
  - `privacy:manage`: aviso, solicitudes y vulneraciones;
  - `privacy:erase`: anonimizar.
  - Los consentimientos del cliente usan `sales_customers:manage`, porque los registra quien atiende al cliente.
- **Interfaz.**
  - La página «Datos personales» va en el menú de Administración, con pestañas Aviso, Solicitudes y Vulneraciones.
  - La ficha del cliente gana un panel de consentimientos.
  - Los textos no mencionan a otras empresas.

## Pasos

- [x] **Paso 1: migración `0121_personal_data_protection` y modelos.**
  - Crea las cuatro tablas y `sales_customers.anonymized_at`, más los permisos.
  - Verificar con upgrade, downgrade y upgrade, y con su prueba de integración.
- [x] **Paso 2: dominio.**
  - Días hábiles con los asuetos, incluida la Semana Santa calculada.
  - Plazos, transiciones de estado de las solicitudes, plantilla y elementos del aviso, finalidades de consentimiento y reglas de las vulneraciones.
  - Verificar con pruebas unitarias.
- [x] **Paso 3: repositorio, casos de uso y API.** (`tests/e2e/test_privacy.py`; el cliente anonimizado expone `anonymized_at` y no se edita ni se reactiva)
  - `/privacy/...` y `/customers/{id}/consents`.
  - Verificar con pruebas e2e: aislamiento entre empresas, permisos, auditoría, exportación y anonimización.
- [x] **Paso 4: frontend.** La página «Datos personales» y el panel de consentimientos. Verificar con vitest.
- [x] **Paso 5: semilla.** El aviso de privacidad inicial de Grupo Lorena, publicado.
- [x] **Paso 6: documentación.** `docs/api.md`, `docs/database-schema.md` y el manual.
- [x] **Paso 7: verificación y PR.** Correr la batería completa, revisar en el navegador y abrir el PR hacia `develop`.

## Estado actual

- **Paso en curso**: ninguno; V1d terminado y en PR hacia `develop`. Batería completa: backend 1,831 y frontend 1,146 pruebas, todo en verde. Documentación en `docs/api.md`, `docs/database-schema.md` §31 y `docs/ers-v1/manual-datos-personales.md`. La semilla del aviso es el paso de seguimiento `seed.grupo_lorena.privacy_notice` (`backend/seed/seed_grupo_lorena_privacy.py`); no republica si ya hay aviso. El frontend está en `lib/features/privacy` y la ruta `/privacy`. En pruebas, los correos con dominio `.test` los rechaza `EmailStr`: usar `example.com`. En vitest, un `<select bind:value>` dentro de un modal no tomó el cambio: usar `value` + `onchange`.
- **QA en el navegador (16/11/2026)**: aviso sembrado visible; solicitud SOL-00001 creada, en trámite, exportada y atendida; consentimiento registrado y revocado en CLI-00003; modo claro, oscuro y 375 px revisados. Correcciones de la QA:
  - la plantilla del aviso decía «escribiendo a» un teléfono; ahora arma «escribiendo a {correo}, llamando al {teléfono} o en cualquiera de nuestras sucursales»;
  - el selector de cliente de la solicitud no mostraba el nombre elegido;
  - estados vacíos con icono, mensaje y botón (`PrivacyEmptyState.svelte`);
  - botones del encabezado sin partirse en dos líneas;
  - el consentimiento revocado muestra el canal de revocación.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con los objetivos `backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
- **Navegador**:
  - Iniciar sesión en `http://localhost:5173/login` con la cuenta local que dio el usuario.
  - Navegar con el menú, sin recargar la página.
  - Si una ruta nueva da «Not found», reiniciar el contenedor `frontend`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

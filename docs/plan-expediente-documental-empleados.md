# Plan de implementación: expediente documental de Empleados y gestor central de Documentos

## Estado del documento

- Tipo: plan técnico y funcional.
- Estado: implementado y validado en la rama actual.
- Alcance inicial: Empleados y gestor documental central.
- Fuera de alcance: integración documental con otros módulos del ERP.
- Migración aplicada: `0043`.
- Validación ejecutada: 339 pruebas unitarias, 107 pruebas frontend y 91 pruebas E2E
  dentro de Docker; Ruff, compilación Python, Prettier, ESLint, Svelte Check y la
  configuración de Compose también fueron verificados.

## 1. Resumen ejecutivo

El ERP ya dispone de una infraestructura documental genérica y segura formada por RustFS,
ClamAV, Redis, ARQ y OCRmyPDF. La nueva fase utilizará esos servicios para construir un
expediente documental por empleado y una biblioteca central desde la que puedan consultarse y
administrarse los documentos autorizados de la empresa.

La solución separará claramente dos conceptos:

1. El archivo físico y su procesamiento técnico, representado por `document_assets`.
2. El registro de negocio, que indicará a quién pertenece, qué tipo de documento es, su vigencia,
   confidencialidad y relación con otras versiones.

Esta separación permitirá incorporar posteriormente documentos de sucursales, almacenes,
productos, proveedores u otros módulos sin modificar RustFS ni duplicar la lógica de seguridad,
antivirus, OCR, retención o respaldo.

La primera entrega incluirá:

- expediente documental completo dentro del detalle de cada empleado;
- módulo global `Documentos`;
- documentos generales de empresa sin entidad asociada;
- categorías configurables por empresa;
- carga múltiple desde el navegador;
- búsqueda por nombre y metadatos;
- vencimientos e indicadores visuales;
- versiones y reemplazo controlado;
- apertura de PDF en el visor nativo del navegador;
- permisos específicos para Recursos Humanos;
- auditoría y observabilidad de todas las operaciones relevantes.

## 2. Decisiones funcionales fijadas

### 2.1 Alcance de la primera fase

Se implementarán tanto el expediente por empleado como el gestor documental central. En esta
fase, el gestor central mostrará:

- documentos generales de la empresa;
- documentos vinculados a empleados;
- versiones actuales por defecto;
- versiones históricas cuando el usuario solicite ver el historial;
- documentos enviados a la Papelera cuando el usuario tenga permiso de restauración.

No se implementarán todavía asociaciones con otros módulos.

### 2.2 Usuarios autorizados

Los expedientes de empleados serán accesibles inicialmente solo para:

- `SUPER_ADMIN`;
- `RECURSOS_HUMANOS`.

El rol `ADMINISTRADOR`, las jefaturas y los empleados no recibirán acceso inicial. Los permisos
podrán concederse posteriormente a roles personalizados mediante la matriz RBAC.

### 2.3 Organización

No se crearán carpetas físicas ni jerarquías manuales. La organización se realizará mediante:

- módulo;
- entidad relacionada;
- categoría;
- grupo documental;
- etiquetas;
- vigencia;
- estado técnico;
- estado documental;
- búsqueda y filtros combinables.

### 2.4 Búsqueda

La búsqueda abarcará:

- título;
- nombre original del archivo;
- código o referencia oficial;
- emisor;
- etiquetas;
- nombre y código del empleado.

No se indexará ni buscará dentro del contenido del archivo. OCR continuará generando un PDF
buscable para descarga y visualización, pero no se almacenará el texto extraído en PostgreSQL.

### 2.5 Apertura en navegador

- Los PDF activos se abrirán en una nueva pestaña mediante el visor nativo del navegador.
- La interfaz tendrá una única acción, **Abrir en navegador**, para el original canónico.
- El derivado OCR se conservará como descarga independiente, sin un segundo visor.
- DOC, DOCX, XLS, XLSX, CSV, TXT, ODT y ODS mostrarán sus metadatos y ofrecerán descarga.
- No se incorporará conversión de documentos Office en esta fase.

### 2.6 Carga múltiple

La interfaz permitirá seleccionar o arrastrar varios archivos. La API continuará procesando un
archivo por solicitud para conservar el flujo seguro actual. El navegador mantendrá una cola,
calculará el SHA-256 de cada archivo y ejecutará como máximo tres cargas simultáneas.

### 2.7 Vencimientos

- La fecha de vencimiento será opcional.
- Los indicadores principales considerarán “próximo a vencer” un documento que venza dentro de
  30 días.
- Los filtros permitirán consultar períodos de 7, 30, 60 y 90 días.
- No se enviarán correos, webhooks ni notificaciones internas en esta fase.

### 2.8 Eliminación de empleados

La eliminación lógica de un empleado no eliminará ni enviará sus documentos a la Papelera. El
expediente se conservará por trazabilidad laboral y podrá consultarse desde el módulo Documentos
con el indicador “Empleado en Papelera”.

## 3. Arquitectura propuesta

### 3.1 Separación de responsabilidades

La infraestructura existente conservará sus responsabilidades:

- `document_assets`: archivo, checksum, estado de carga, análisis antivirus y eliminación lógica;
- `document_derivatives`: derivado OCR;
- RustFS: contenido binario privado;
- ClamAV: análisis antimalware;
- OCRmyPDF: generación del PDF buscable;
- mantenimiento: cargas abandonadas, cuarentena y purga;
- respaldo/restauración: originales y derivados.

La nueva capa documental de negocio administrará:

- categoría;
- título y descripción;
- propietario;
- fechas y vigencia;
- confidencialidad;
- etiquetas;
- versiones;
- búsqueda transversal.

### 3.2 Capas hexagonales

La implementación seguirá la arquitectura existente:

- Dominio: entidades de registro documental, categorías, estados y reglas de versión.
- Aplicación: casos de uso para cargas asociadas, consultas, edición, reemplazo y categorías.
- Puertos: repositorios documentales y política de autorización por módulo.
- Infraestructura: modelos y repositorios SQLAlchemy.
- API: routers y DTO Pydantic v2.
- Frontend: servicios tipados, componentes reutilizables y páginas SvelteKit 5 con Runes.

La capa de aplicación específica de Empleados reutilizará `DocumentService`; no duplicará
validación de firmas, checksum, ClamAV, OCR, URLs prefirmadas ni límites de tamaño.

## 4. Migración `0043`

### 4.1 Tabla `document_categories`

Campos previstos:

- `id`: UUID.
- `company_id`: empresa propietaria.
- `module`: inicialmente `general` o `employees`.
- `code`: identificador estable y no dependiente del nombre mostrado.
- `name`: nombre visible.
- `group_name`: agrupación funcional.
- `description`: descripción opcional.
- `sort_order`: orden de presentación.
- `is_active`: disponibilidad para nuevas cargas.
- `created_by` y `updated_by`.
- `created_at` y `updated_at`.

Restricciones e índices:

- unicidad de `company_id + module + code`;
- unicidad del nombre normalizado visible por empresa y módulo;
- índice por empresa, módulo, estado y orden;
- una categoría usada por documentos no podrá borrarse físicamente;
- desactivarla no afectará documentos históricos.

### 4.2 Tabla `document_records`

Campos previstos:

- `document_id`: PK y FK uno a uno hacia `document_assets.id`;
- `company_id`;
- `module`;
- `owner_type`: `employee` o nulo para documentos generales;
- `owner_id`: UUID del empleado o nulo para documentos generales;
- `category_id`;
- `title`;
- `description`;
- `reference_code`;
- `issuer`;
- `issued_on`;
- `expires_on`;
- `confidentiality`: `internal` o `restricted`;
- `tags`: lista normalizada y acotada;
- `version_group_id`;
- `version_number`;
- `is_current`;
- `replaces_document_id`;
- `created_by` y `updated_by`;
- `created_at` y `updated_at`.

Restricciones e índices:

- un solo registro por `document_asset`;
- versión positiva;
- unicidad de `version_group_id + version_number`;
- una única versión actual por grupo;
- consistencia entre módulo, `owner_type` y `owner_id`;
- índices por empresa/módulo/propietario, categoría, vigencia, versión actual y fecha;
- cascada desde la eliminación física de `document_assets` para que la purga no deje metadatos
  huérfanos.

La validez del propietario polimórfico se verificará en aplicación. Para Empleados, el servidor
comprobará existencia, empresa, estado y alcance de sucursal antes de crear o consultar el enlace.

### 4.3 Migración de datos existentes

Por cada `document_asset` existente se creará un `document_record` con:

- módulo `general`;
- propietario nulo;
- categoría general “Otros”;
- título derivado del nombre original;
- confidencialidad `internal`;
- versión 1;
- grupo de versión nuevo;
- marca de versión actual.

La migración será idempotente y no cambiará bucket, object key, checksum, estado técnico ni
derivados OCR.

### 4.4 Catálogo inicial de Empleados

Se crearán las siguientes categorías para cada empresa existente y futura.

#### Expediente personal

- CV.
- Ficha del empleado.
- Solicitud de empleo.
- DUI.
- NIT.
- Pasaporte.
- Permiso de trabajo.
- Documento de identidad.
- Referencia personal.
- Referencia laboral.
- Constancia de antecedentes.
- Contactos de emergencia.

#### Formación y experiencia

- Título académico.
- Diploma.
- Certificación profesional.
- Constancia de curso.
- Constancia de capacitación.
- Licencia profesional.
- Carta de recomendación.
- Historial de capacitación interna.

#### Relación laboral

- Contrato laboral.
- Adenda de contrato.
- Descripción o perfil de puesto.
- Acuerdo de confidencialidad.
- Carta de oferta.
- Acuse de reglamento interno.
- Autorización o consentimiento.
- Acta de entrega de uniforme.
- Acta de entrega de herramientas o equipo.
- Carta de ascenso.
- Carta de traslado.
- Carta de cambio salarial.

#### Seguimiento

- Evaluación de desempeño.
- Plan de mejora.
- Reconocimiento.
- Amonestación.
- Acta disciplinaria.
- Permiso.
- Licencia.
- Incapacidad.
- Accidente laboral.
- Constancia médica.

#### Finalización laboral

- Carta de renuncia.
- Notificación de despido.
- Finiquito.
- Solvencia de equipos y activos.
- Entrevista de salida.
- Constancia laboral.

#### General

- Otros.

Todas las categorías de Empleados usarán confidencialidad `restricted` como valor sugerido. La
fecha de vencimiento seguirá siendo opcional porque incluso documentos del mismo tipo pueden
tener reglas diferentes.

## 5. Versionado y estados

### 5.1 Grupos documentales

Una categoría podrá contener múltiples documentos independientes. Cada documento inicial creará
un `version_group_id`. La acción “Reemplazar” conservará ese grupo y creará la siguiente versión.

Ejemplo:

```text
Contrato laboral
└── Grupo 8f…
    ├── Versión 1 · reemplazada
    ├── Versión 2 · reemplazada
    └── Versión 3 · vigente
```

### 5.2 Activación del reemplazo

1. La versión nueva se crea como candidata.
2. El archivo se carga en una clave privada e inmutable diferente.
3. Se valida checksum, formato y estructura.
4. ClamAV analiza el archivo.
5. Si queda activo, una transacción bloquea el grupo, desmarca la versión anterior y activa la
   nueva.
6. Si falla, la versión anterior continúa siendo actual.

Las solicitudes concurrentes para reemplazar el mismo documento se serializarán y no podrán
crear dos versiones actuales.

### 5.3 Estados expuestos

La API conservará el estado técnico existente y añadirá un estado documental calculado:

- `uploading`;
- `processing`;
- `current`;
- `expiring`;
- `expired`;
- `replaced`;
- `quarantined`;
- `rejected`;
- `deleted`.

No se almacenará un estado `expired` mutable: se calculará usando `expires_on` y la fecha local de
El Salvador para evitar trabajos de actualización masiva.

## 6. Seguridad y RBAC

### 6.1 Permisos nuevos

- `employee_documents:read`
- `employee_documents:upload`
- `employee_documents:update`
- `employee_documents:download`
- `employee_documents:delete`
- `employee_documents:restore`
- `employee_documents:process`
- `employee_documents:restricted`
- `employee_documents:manage_categories`

Se agregarán al catálogo RBAC y se asignarán inicialmente a `SUPER_ADMIN` y
`RECURSOS_HUMANOS`. `ADMINISTRADOR` no los recibirá.

Los permisos `documents:*` existentes seguirán administrando documentos generales. Los endpoints
comunes resolverán primero el módulo real del registro y luego exigirán el permiso correspondiente.

### 6.2 Autorización dinámica

- Un documento general requerirá `documents:<acción>`.
- Un documento de empleado requerirá `employee_documents:<acción>`.
- Un documento `restricted` requerirá además `employee_documents:restricted`.
- El listado global filtrará módulos no autorizados antes de calcular totales y paginación.
- No se revelará mediante conteos que existen documentos de un módulo no autorizado.

### 6.3 Empresas y sucursales

- Toda operación autenticada requerirá `X-Company-ID`.
- El propietario se obtendrá desde la ruta y la base de datos, nunca desde datos confiados del
  navegador.
- Un cruce empresarial devolverá `404`.
- Cuando exista `X-Branch-ID`, solo se mostrarán empleados con asignación activa en esa sucursal.
- El alcance de todas las sucursales permitirá consultar todos los expedientes de la empresa.
- Los documentos generales requerirán alcance empresarial completo.

## 7. Contratos de API

### 7.1 Respuesta documental

`DocumentOut` conservará todos sus campos actuales y añadirá campos opcionales compatibles:

- módulo;
- propietario seguro con tipo, UUID, etiqueta y estado eliminado;
- categoría;
- título y descripción;
- referencia y emisor;
- emisión y vencimiento;
- confidencialidad;
- etiquetas;
- estado documental;
- grupo y número de versión;
- indicador de versión actual;
- UUID del documento reemplazado;
- información OCR existente.

Nunca devolverá bucket, object key ni credenciales.

### 7.2 Endpoints de Empleados

```text
GET  /api/v1/employees/{employee_id}/documents
POST /api/v1/employees/{employee_id}/documents/uploads
```

El listado admitirá paginación, búsqueda, categoría, estado, vigencia e inclusión opcional de
versiones históricas. La carga recibirá los datos técnicos actuales más los metadatos de negocio.

### 7.3 Endpoints comunes

```text
GET    /api/v1/documents
GET    /api/v1/documents/{document_id}
PATCH  /api/v1/documents/{document_id}/metadata
POST   /api/v1/documents/{document_id}/complete
POST   /api/v1/documents/{document_id}/download-url
POST   /api/v1/documents/{document_id}/preview-url
GET    /api/v1/documents/{document_id}/versions
POST   /api/v1/documents/{document_id}/replacements/uploads
POST   /api/v1/documents/{document_id}/ocr/retry
DELETE /api/v1/documents/{document_id}
POST   /api/v1/documents/{document_id}/restore
```

`POST /documents/uploads` seguirá disponible para documentos generales y admitirá metadatos
opcionales sin romper clientes actuales.

### 7.4 Filtros del gestor global

`GET /documents` aceptará:

- `page` y `size`;
- `search`;
- `module`;
- `owner_type` y `owner_id` cuando estén autorizados;
- `category_id`;
- `storage_status`;
- `document_status`;
- `confidentiality`;
- `expires_within_days`;
- `include_versions`;
- `include_deleted`.

Por defecto devolverá únicamente versiones actuales y no eliminadas.

### 7.5 Categorías

```text
GET   /api/v1/document-categories
POST  /api/v1/document-categories
PATCH /api/v1/document-categories/{category_id}
POST  /api/v1/document-categories/{category_id}/activate
POST  /api/v1/document-categories/{category_id}/deactivate
```

No habrá eliminación física desde la API.

### 7.6 Validaciones de metadatos

- título obligatorio y normalizado;
- categoría activa y perteneciente a la misma empresa/módulo;
- descripción, referencia y emisor con límites explícitos;
- máximo diez etiquetas únicas por documento;
- etiquetas normalizadas, sin valores vacíos;
- `expires_on` no anterior a `issued_on`;
- UUID de propietario no aceptado en cargas generales;
- reemplazo permitido únicamente sobre una versión del mismo módulo, propietario y empresa.

Los códigos de error serán estables, por ejemplo:

- `document_category_not_found`;
- `document_category_inactive`;
- `employee_document_not_found`;
- `document_metadata_invalid`;
- `document_replacement_conflict`;
- `document_preview_not_available`;
- `document_ocr_not_ready`.

## 8. Flujo de carga

Por cada archivo:

1. El navegador valida extensión y tamaño para ofrecer respuesta inmediata.
2. Calcula SHA-256 mediante Web Crypto.
3. Solicita una URL prefirmada al endpoint general o al endpoint del empleado.
4. El backend valida permisos, empresa, empleado, sucursal, categoría y metadatos.
5. El backend crea `document_asset` y `document_record` en una sola transacción.
6. El navegador ejecuta el PUT directo a RustFS con los encabezados exactos.
7. El navegador solicita `complete`.
8. El backend valida el objeto, formato, checksum y estructura.
9. ClamAV analiza el archivo.
10. El documento limpio pasa a `active`.
11. Si es PDF, OCR se agenda sin bloquear la disponibilidad del original.
12. La interfaz actualiza únicamente el elemento correspondiente de la cola.

Si la pestaña se cierra, las cargas incompletas seguirán sujetas a la limpieza de 24 horas ya
existente. La cola del navegador no se persistirá entre sesiones.

## 9. Apertura en navegador y descarga

Se ampliará el puerto de almacenamiento para generar una URL de lectura con disposición
`inline`, distinta de la URL de descarga `attachment`.

Reglas:

- solamente documentos activos;
- solamente PDF;
- URL temporal con la expiración configurada actualmente;
- autorización y auditoría antes de emitirla;
- siempre la variante `original`;
- renovación de URL al reabrir o cuando expire;
- la interfaz no usará modal, `iframe` ni una ruta propia de visualización;
- los formatos no PDF conservarán únicamente la descarga.

La aplicación no actuará como proxy del archivo ni mantendrá una segunda copia persistente.

## 10. UX/UI del expediente de Empleados

### 10.1 Navegación del detalle

La pantalla del empleado se reorganizará en pestañas accesibles:

- Resumen.
- Documentos, con contador.
- Asignaciones.

La cabecera actual con avatar, nombre, cargo, código y estado se conservará.

### 10.2 Pestaña Documentos

Mostrará:

- total vigente;
- próximos a vencer;
- vencidos;
- en carga o procesamiento;
- búsqueda local/remota;
- filtros por grupo, categoría, estado y vigencia;
- tabla en escritorio;
- tarjetas compactas en móvil.

Cada documento mostrará:

- icono y extensión;
- título y nombre original;
- categoría y grupo;
- versión;
- tamaño;
- emisión y vencimiento;
- estado documental;
- estado de antivirus/carga;
- disponibilidad OCR;
- confidencialidad.

Acciones condicionales:

- ver PDF;
- descargar original;
- descargar OCR;
- editar metadatos;
- reemplazar;
- abrir historial;
- reintentar OCR;
- enviar a Papelera;
- restaurar.

### 10.3 Estados visuales

- Skeleton durante carga inicial.
- Empty state con acción “Agregar documentos”.
- Banner de error con reintento.
- Confirmación visual por carga terminada.
- Badge de advertencia para vencimientos.
- Badge de peligro para vencidos, cuarentena o rechazo.
- Mensaje explícito cuando RustFS, ClamAV u OCR no estén disponibles.

## 11. UX/UI del módulo Documentos

### 11.1 Navegación

- Añadir “Documentos” en la navegación principal.
- Ruta principal: `/documents`.
- Ruta de configuración: `/documents/categories`.
- Mostrar el módulo si existe `documents:read` o `employee_documents:read`.
- Añadir título de ruta y búsqueda global.

### 11.2 Biblioteca central

La cabecera mostrará indicadores de:

- documentos vigentes;
- próximos a vencer;
- vencidos;
- procesándose.

La biblioteca incluirá:

- alternancia tabla/cuadrícula;
- búsqueda;
- filtros combinables;
- agrupación opcional por módulo o categoría;
- chips de filtros activos;
- paginación del servidor;
- selector de cantidad por página;
- panel lateral de detalle;
- historial de versiones;
- apertura de PDF en nueva pestaña;
- acciones según permiso.

La vista elegida podrá conservarse localmente en el navegador, pero no requerirá persistencia en
PostgreSQL.

### 11.3 Alta desde el gestor

El formulario preguntará primero el destino:

- General de empresa, si existe `documents:upload`.
- Empleado, si existe `employee_documents:upload`.

Para Empleados se utilizará un selector remoto que respete empresa y sucursal. El navegador no
podrá enviar un propietario arbitrario fuera de las opciones autorizadas.

### 11.4 Gestión de categorías

RRHH podrá:

- buscar categorías;
- filtrar por grupo o estado;
- crear categorías;
- editar nombre, descripción, grupo y orden;
- activar o desactivar;
- comprobar cuántos documentos utilizan cada categoría.

Una categoría desactivada continuará visible en documentos históricos, pero no aparecerá como
opción normal para nuevas cargas.

## 12. Componente de carga múltiple

Crear un componente reutilizable para Empleados y Documentos con:

- drag and drop y selector tradicional;
- máximo 20 archivos por cola;
- máximo tres transferencias concurrentes;
- validación de extensiones y 50 MiB;
- progreso por fases: preparando, autorizando, cargando, verificando, analizando y listo;
- metadatos independientes por archivo;
- edición masiva opcional de categoría/confidencialidad antes de iniciar;
- cancelación de elementos que aún no hayan comenzado;
- reintento individual;
- resumen de éxitos y fallos;
- advertencia al navegar mientras existan transferencias activas;
- soporte completo de teclado, foco y mensajes `aria-live`.

Los errores de un archivo no cancelarán los demás.

## 13. Ciclo de vida, mantenimiento y respaldo

- Eliminar un documento aplicará soft delete al `document_asset`.
- `document_record` permanecerá asociado para restauración e historial.
- Restaurar conservará grupo y número de versión.
- Si una versión actual eliminada no fue reemplazada, volverá a ser actual al restaurarse.
- Si durante su eliminación apareció una versión más nueva, la restaurada quedará histórica.
- La purga existente eliminará primero derivados, luego objeto original y finalmente filas; la FK
  eliminará el registro de negocio.
- La eliminación del empleado no alterará sus documentos.
- La eliminación de una empresa continuará eliminando sus registros según las políticas actuales.
- El respaldo de objetos no cambia; los nuevos metadatos quedarán incluidos en el dump PostgreSQL
  que debe acompañar al respaldo RustFS.

## 14. Auditoría y observabilidad

Registrar en `audit_logs`:

- inicio y finalización de carga asociada;
- edición de metadatos;
- emisión de URL inline para apertura en navegador;
- descarga original y OCR;
- inicio de reemplazo;
- activación de nueva versión;
- fallo de reemplazo;
- eliminación y restauración;
- creación, edición, activación y desactivación de categorías.

La observabilidad añadirá métricas y spans de baja cardinalidad para:

- módulo;
- operación;
- formato general;
- resultado;
- estado técnico;
- duración de carga/finalización.

No incluirá como atributos de telemetría:

- empresa;
- empleado;
- nombre de archivo;
- título;
- referencia;
- etiquetas;
- object key;
- URLs prefirmadas.

## 15. Estrategia de implementación incremental

### Fase 1: dominio y persistencia

- Crear migración `0043`.
- Añadir entidades, puertos, modelos y repositorios.
- Ejecutar backfill de documentos existentes.
- Añadir catálogo inicial y bootstrap para empresas nuevas.
- Actualizar revisión esperada de salud.

### Fase 2: autorización y casos de uso

- Añadir permisos RBAC.
- Implementar política dinámica por módulo.
- Implementar metadatos, categorías, listados y filtros.
- Implementar asociación con empleados y alcance de sucursal.
- Implementar versionado y reemplazo atómico.

### Fase 3: API pública

- Extender DTO sin romper campos actuales.
- Añadir endpoints de Empleados, categorías, metadata, historial, reemplazo y URL inline para PDF.
- Mantener compatibles carga, complete, descarga y OCR.
- Añadir eliminación/restauración documental con permisos dinámicos.

### Fase 4: cliente documental reutilizable

- Crear tipos y servicios TypeScript.
- Implementar cálculo SHA-256.
- Implementar cola con concurrencia acotada.
- Crear componentes para lista, filtros, estados, metadatos e historial; la visualización PDF quedará a cargo del navegador.

### Fase 5: integración con Empleados

- Reorganizar detalle en pestañas.
- Añadir panel documental.
- Validar alcance, permisos y responsive design.

### Fase 6: gestor central

- Añadir navegación y rutas.
- Construir biblioteca, indicadores, filtros y vistas.
- Añadir carga general/vinculada y configuración de categorías.

### Fase 7: endurecimiento y cierre

- Completar auditoría y telemetría.
- Ejecutar pruebas unitarias, integración y E2E.
- Validar seguridad, accesibilidad, modo claro/oscuro y regresiones.
- Actualizar documentación operativa y Swagger.

## 16. Pruebas

### 16.1 Unitarias de backend

- normalización y límites de metadatos;
- etiquetas duplicadas, vacías o excesivas;
- fecha de vencimiento anterior a emisión;
- categoría inactiva o de otra empresa;
- asociación a empleado inexistente, eliminado o de otra empresa;
- autorización `internal` y `restricted`;
- cálculo de vigente, próximo a vencer y vencido;
- creación de grupos y números de versión;
- reemplazo exitoso, fallido y concurrente;
- versión anterior conservada durante el análisis;
- filtrado de módulos no autorizados.

### 16.2 Integración de backend

- migración `0043` sobre una base con documentos existentes;
- creación de catálogos para empresas existentes y nuevas;
- unicidad e índices;
- paginación y búsqueda por metadatos;
- aislamiento por empresa;
- filtrado por sucursal;
- soft delete y restauración;
- comportamiento con empleado en Papelera;
- purga en cascada de registros documentales;
- compatibilidad con OCR y mantenimiento.

### 16.3 API y E2E

- RRHH completa el flujo de carga a un empleado;
- superadministrador administra documentos generales y laborales;
- administrador sin permisos recibe `403`;
- cruce de empresa o sucursal recibe `404`;
- archivo limpio queda activo;
- malware queda en cuarentena;
- caída de ClamAV conserva reintento de complete;
- PDF original queda disponible antes de OCR;
- preview original y OCR;
- reemplazo no cambia el checksum del original anterior;
- eliminación/restauración conserva historial;
- empleado eliminado permanece consultable desde Documentos.

### 16.4 Frontend

- cálculo SHA-256;
- cola máxima y concurrencia de tres;
- éxito parcial y reintento individual;
- permisos de botones y rutas;
- filtros y paginación;
- historial de versiones;
- apertura de PDF en nueva pestaña y descarga de formatos no compatibles;
- estados loading, empty, error y success;
- teclado, foco y lectores de pantalla;
- diseño responsive y temas claro/oscuro.

### 16.5 Validación final

- `alembic upgrade head` y downgrade controlado de `0043`;
- Ruff;
- mypy;
- suite Pytest completa;
- Svelte Check;
- ESLint;
- Vitest;
- Playwright;
- `docker compose config` local y productivo;
- flujo real contra RustFS y ClamAV;
- OCR real opcional;
- escaneo Trivy sin vulnerabilidades HIGH o CRITICAL introducidas.

## 17. Criterios de aceptación

La funcionalidad se considerará completa cuando:

1. RRHH pueda cargar varios documentos a un empleado desde una cola con progreso individual.
2. Todos los archivos sigan pasando por las validaciones, ClamAV y OCR existentes.
3. Los documentos puedan clasificarse y encontrarse por sus metadatos.
4. Los vencimientos sean visibles y filtrables.
5. Un documento pueda reemplazarse sin perder versiones anteriores.
6. La versión anterior permanezca vigente si el reemplazo falla.
7. Un PDF pueda visualizarse dentro del ERP y descargarse como original u OCR.
8. El expediente pueda administrarse desde el empleado y desde el módulo Documentos.
9. Los usuarios no autorizados no puedan inferir ni consultar documentos laborales.
10. El expediente sobreviva a la eliminación lógica del empleado.
11. Reinicios o reconstrucciones de contenedores no pierdan archivos ni metadatos.
12. La suite completa, validaciones de tipos, lint y seguridad terminen correctamente.

## 18. Fuera de alcance

- Documentos vinculados a Sucursales, Almacenes, Productos, Proveedores u otros módulos.
- Acceso del empleado a su propio expediente.
- Carpetas manuales.
- Búsqueda dentro del contenido.
- Extracción y almacenamiento separado de texto OCR.
- Conversión o preview de formatos Office.
- Notificaciones por correo, webhook o bandeja interna.
- Flujos de aprobación.
- Firma electrónica o aceptación documental.
- Plantillas y generación automática de contratos o constancias.
- Documentos compartidos entre múltiples entidades.
- Cambios en el proveedor RustFS, ClamAV, Redis, OCRmyPDF o Cloudinary.

## 19. Resultado esperado

El ERP contará con una base documental modular y reutilizable. Recursos Humanos podrá mantener
expedientes laborales seguros, organizados, versionados y auditables, mientras el gestor central
ofrecerá una visión unificada de todos los documentos autorizados. Los futuros módulos solo
necesitarán implementar su política de propietario, permisos, categorías y presentación; el flujo
de archivos seguirá reutilizando la infraestructura documental existente.

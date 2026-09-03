# Biblioteca documental

La biblioteca de documentos del ERP presenta una organización de carpetas
virtuales. Las carpetas se calculan a partir de los módulos, empleados y
categorías que el usuario puede consultar; no se crean directorios ni objetos
adicionales en RustFS.

## Navegación

| Vista | URL |
| --- | --- |
| Raíz | `/documents` |
| Documentos generales | `/documents/general` |
| Categoría general | `/documents/general/categories/<categoryId>` |
| Expedientes | `/documents/employees` |
| Expediente de empleado | `/documents/employees/<employeeId>` |
| Categoría del expediente | `/documents/employees/<employeeId>/categories/<categoryId>` |

La URL es la fuente de verdad de la carpeta abierta. Por eso los niveles son
compatibles con recarga, enlaces compartidos y los botones Atrás/Adelante del
navegador. La búsqueda y los filtros se conservan como parámetros de consulta
(`search`, `status`, `expires`, `category` y `visibility`).
Al volver con el navegador, la vista sincroniza de nuevo esos parámetros antes
de solicitar los datos.

## Organización virtual

```text
Documentos
├── General
│   └── Categorías
└── Empleados
    └── Empleado
        └── Categorías
```

Cambiar la categoría de un documento actualiza su ubicación lógica. La clave
privada, el bucket y el objeto original de RustFS permanecen inmutables.

## API de carpetas

`GET /api/v1/documents/library/folders` devuelve únicamente carpetas visibles
para el contexto `X-Company-ID` y `X-Branch-ID` del usuario. Acepta:

- `parent=root|general|employees|employee`;
- `employee_id` cuando `parent=employee`;
- `search`, `page` y `size`.

La respuesta incluye conteos agrupados de documentos, vigentes, próximos a
vencer, vencidos y última actualización. No incluye nombres de archivos,
claves privadas ni URLs prefirmadas. El backend mantiene el aislamiento por
empresa, sucursal, permisos y confidencialidad; un cruce responde `404`.

La lista de archivos se carga desde los contratos existentes: `GET
/api/v1/documents/library` para documentos generales y `GET
/api/v1/employees/<employeeId>/documents` para expedientes. Ambos aceptan
`category_id`, `status`, `expires_within_days` y `confidentiality`, además de
búsqueda y paginación.

Las categorías activas aparecen siempre para conservar una estructura estable.
Una categoría inactiva solo se conserva en el árbol si aún tiene alguna
versión documental no eliminada y visible para el usuario.

## Cargas contextuales

El botón de carga conserva el destino desde el que se abrió:

- raíz: permite elegir General o un empleado autorizado;
- General: selecciona el módulo general;
- empleado: selecciona el empleado actual;
- categoría: selecciona empleado y categoría actuales.

La cola existente mantiene validación, antivirus, progreso y reintentos. El
archivo original sigue siendo la evidencia canónica y la descarga predeterminada.

## Accesibilidad y estilo

Las tarjetas, breadcrumbs, filtros y lista usan Geist Sans/Mono local, tokens
del sistema y áreas táctiles de al menos 44 px. La navegación funciona con
teclado (Enter y barra espaciadora en carpetas), muestra foco visible y anuncia
estados de carga, vacío y error. Las transiciones duran aproximadamente
150–200 ms y se desactivan cuando el usuario activa
`prefers-reduced-motion: reduce`.

El panel de detalle conserva las acciones existentes: editar metadatos,
reemplazar, abrir PDF en el navegador, descargar, consultar versiones,
reintentar OCR y enviar a papelera. Las acciones se vuelven a validar en el
backend aunque la interfaz las oculte por permisos.

## Apertura en el navegador

Los documentos PDF activos tienen una única acción, **Abrir en navegador**.
La aplicación solicita al backend una URL prefirmada de corta duración y abre
el visor nativo del navegador en una nueva pestaña. No se renderiza el archivo
en un modal, `iframe` ni una ruta propia del ERP.

La pestaña se crea al iniciar la acción para evitar bloqueos de ventanas
emergentes mientras se solicita la URL. Si el navegador la bloquea, la
aplicación muestra un mensaje para permitir ventanas emergentes y reintentar.
La URL firmada nunca se guarda en la ruta del ERP ni se muestran el bucket o
la clave privada de RustFS.

El original permanece como archivo canónico. El PDF OCR continúa disponible
como descarga independiente, no como un segundo visor. Los formatos DOCX,
XLSX, ODT, CSV y demás formatos no PDF conservan únicamente la acción de
descarga, porque su renderizado depende del navegador o de una aplicación
externa.

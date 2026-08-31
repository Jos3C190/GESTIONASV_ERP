# Almacenamiento documental local

## Alcance

Los documentos genéricos de empresa se almacenan en RustFS mediante su API compatible con S3.
PDF, DOC, DOCX, XLS, XLSX, CSV, TXT, ODT y ODS admiten entre 1 byte y 50 MiB. Cloudinary sigue
siendo el proveedor exclusivo para imágenes. Esta fase expone API y Swagger, sin páginas ni
cliente TypeScript en SvelteKit.

La implementación usa puertos hexagonales para repositorio, objetos y antivirus. Cambiar RustFS
por AWS S3, Cloudflare R2 o MinIO no cambia el dominio ni la API.

## Servicios locales

Los archivos de infraestructura están separados a nivel del proyecto:

- [`object-storage/`](../object-storage/) contiene la configuración no secreta y la guía de
  operación de RustFS;
- [`antivirus/`](../antivirus/) contiene los límites de ClamAV y su guía de operación.
- [`redis/`](../redis/) contiene la configuración AOF/noeviction y la guía de la cola local;
- [`ocr/`](../ocr/) documenta el worker OCRmyPDF y su operación.

El código de integración permanece dentro de `backend/app/` para respetar la arquitectura
hexagonal. Las credenciales nunca se guardan en esas carpetas: pertenecen al `.env` local.

`make setup` genera credenciales diferentes para cada instalación, crea el bucket privado
`erp-documents`, aplica CORS para el frontend local, ejecuta Alembic `0042` y levanta:

- RustFS en `127.0.0.1:9000`, con consola en `127.0.0.1:9001`;
- ClamAV solo en la red interna de Compose;
- un inicializador idempotente del bucket;
- mantenimiento documental horario.
- Redis autenticado con AOF para la cola ARQ y el rate limiting distribuido;
- un worker OCRmyPDF sin puertos públicos, con Tesseract en español e inglés.

`/health/ready` y `/health` muestran `rustfs`, `clamav`, `redis` y `ocr_worker`. Una caída de
Redis degrada la salud, activa el rate limiter en memoria y deja el trabajo durable pendiente en
PostgreSQL; el proceso web continúa sirviendo. `/health/live` no realiza I/O.
Fuera del Compose local, `OBJECT_STORAGE_ENABLED` es `false` por defecto. La API responde
`503 document_storage_unavailable` hasta configurar un proveedor real y un antivirus.

## Flujo de API

Todas las operaciones requieren autenticación, contexto `X-Company-ID` y el permiso indicado.
Las claves privadas y el nombre del bucket nunca aparecen en respuestas.

1. `POST /api/v1/documents/uploads` (`documents:upload`) recibe nombre, MIME, tamaño y SHA-256.
2. El cliente ejecuta un único `PUT` a la URL prefirmada usando exactamente los encabezados
   devueltos.
3. `POST /api/v1/documents/{id}/complete` valida HEAD, tamaño, metadatos, checksum, firma y
   estructura; después escanea mediante ClamAV.
4. Solo el estado `active` puede emitir una URL mediante
   `POST /api/v1/documents/{id}/download-url` (`documents:download`).
5. Listado y detalle usan `documents:read`. Eliminación y restauración reutilizan
   `/api/v1/lifecycle/documents/{id}` con `documents:delete` y `documents:restore`.
6. Para PDF activo, el backend crea idempotentemente un derivado OCR `pending`; esto nunca retrasa
   la activación ni la descarga del original.
7. `POST /api/v1/documents/{id}/download-url?variant=ocr` descarga la copia buscable sólo cuando
   está `ready`. `POST /api/v1/documents/{id}/ocr/retry` requiere `documents:process`.

Los permisos nuevos se asignan automáticamente solo al rol global `SUPER_ADMIN`. Un
administrador puede concederlos manualmente a otros roles. Todo cruce de empresa devuelve `404`.

Si ClamAV no responde, el archivo permanece en `pending_scan` y `complete` se puede reintentar.
Un hallazgo queda en `quarantined` sin descarga. La toma atómica del estado `scanning` impide
escaneos concurrentes duplicados.

El original es siempre la evidencia canónica y la variante predeterminada. OCRmyPDF usa
`--skip-text`, rotación y corrección de inclinación. Rechaza PDF cifrado, firmado o con más de 300
páginas; el resultado se valida, se escanea otra vez con ClamAV y se guarda bajo una clave privada
inmutable distinta. Los fallos temporales tienen tres intentos y los trabajos abandonados vuelven
a `pending` después de 20 minutos.

## Seguridad y retención

Los nombres se normalizan únicamente como metadato; las claves se generan en el servidor. Los
formatos ZIP rechazan rutas relativas, cifrado, macros, más de 10 000 entradas, más de 200 MiB
descomprimidos o una relación superior a 100:1. El backend usa un archivo temporal acotado y no
conserva una segunda copia persistente.

El mantenimiento:

- elimina cargas incompletas después de 24 horas;
- devuelve escaneos interrumpidos por más de 15 minutos a `pending_scan`;
- elimina el objeto en cuarentena después de 7 días y conserva su tombstone auditable;
- purga objeto y fila tras 30 días en papelera;
- elimina todos los objetos derivados antes que el original durante una purga;
- reintenta objetos rechazados cuya eliminación inmediata haya fallado.

No se usa versionado, Object Lock ni lifecycle del proveedor. Las claves son inmutables y la
retención pertenece a la aplicación.

## Respaldo y restauración

```bash
make storage-backup
make storage-restore BACKUP_DIR=20260830T231500Z
STORAGE_RESTORE_FORCE=true make storage-restore BACKUP_DIR=20260830T231500Z
```

Cada respaldo se guarda en `object-storage/backups/<timestamp>` con objetos originales, derivados
OCR y `manifest.json`
(tamaño, ETag, metadatos y SHA-256). La restauración verifica checksums y no sobrescribe claves
existentes, salvo la opción explícita. El respaldo documental debe conservarse junto al dump de
PostgreSQL tomado en el mismo punto lógico; uno sin el otro no representa un respaldo consistente.

## Límites del modo local

RustFS single-node/single-disk tiene cero redundancia: es adecuado para desarrollo y cargas
pequeñas, no para alta disponibilidad. Reiniciar o reconstruir contenedores conserva documentos
porque `rustfs-data` es un volumen nombrado. `make clean` ejecuta Compose con `-v` y elimina
también ese volumen documental; esta acción es destructiva.

Las pruebas reales opcionales se habilitan con `RUN_DOCUMENT_STORAGE_INTEGRATION=true` y validan
PUT/GET/HEAD/delete, CORS y EICAR con el stack local levantado.

```bash
docker compose exec -e RUN_DOCUMENT_STORAGE_INTEGRATION=true \
  -e OBJECT_STORAGE_TEST_PUBLIC_ENDPOINT=http://rustfs:9000 \
  backend pytest -q tests/integration/test_document_services_optional.py
```

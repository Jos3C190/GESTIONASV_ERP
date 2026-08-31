# Object storage local — RustFS

Esta carpeta reúne los archivos de infraestructura y la documentación específica del
almacenamiento de objetos. RustFS almacena documentos empresariales y expone una API compatible
con S3. Las imágenes continúan en Cloudinary.

## Contenido

- `rustfs.env`: configuración no secreta cargada por `compose.yaml`.
- `backups/`: respaldos creados por `make storage-backup`; se crea bajo demanda y está ignorada
  por Git.

El adaptador S3, la inicialización del bucket, el mantenimiento y el respaldo siguen en
`backend/app/infrastructure/` porque son parte de la arquitectura del backend. La guía del flujo
completo está en [`docs/document-storage.md`](../docs/document-storage.md).

## Seguridad y secretos

Las credenciales no deben añadirse a esta carpeta. `scripts/setup.sh` genera
`OBJECT_STORAGE_ACCESS_KEY` y `OBJECT_STORAGE_SECRET_KEY` en el `.env` local cuando faltan. El
archivo `.env` está excluido de Git.

El bucket `erp-documents` es privado. Los puertos `9000` (S3) y `9001` (consola) se publican solo
en `127.0.0.1`. Las claves de objeto son generadas por el backend y nunca usan el nombre recibido
como ruta.

## Operación local

```bash
docker compose up -d rustfs storage-init
docker compose ps rustfs
```

- API S3: `http://localhost:9000`
- Consola: `http://localhost:9001`
- Volumen de documentos: `rustfs-data`
- Volumen de logs: `rustfs-logs`

Los datos viven en volúmenes nombrados de Docker, no dentro de esta carpeta. Esto evita problemas
de permisos y rendimiento con bind mounts, especialmente en Windows. Reiniciar o reconstruir el
contenedor conserva los documentos; `make clean` elimina los volúmenes y, por tanto, los datos.

## Respaldo y restauración

```bash
make storage-backup
make storage-restore BACKUP_DIR=YYYYMMDDTHHMMSSZ
STORAGE_RESTORE_FORCE=true make storage-restore BACKUP_DIR=YYYYMMDDTHHMMSSZ
```

Cada respaldo queda en `object-storage/backups/<timestamp>` con los objetos y un
`manifest.json`. La restauración verifica SHA-256 y rechaza sobrescrituras salvo que se habilite
explícitamente. El respaldo debe conservarse junto con el dump PostgreSQL correspondiente.

## Limitación

El modo single-node/single-disk no ofrece redundancia ni alta disponibilidad. Es adecuado para
desarrollo y cargas pequeñas; un despliegue externo debe configurar un proveedor S3 real.

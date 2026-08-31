# Redis local

Redis sostiene la cola ARQ del OCR y los límites distribuidos de autenticación. No almacena datos de negocio ni reemplaza PostgreSQL.

- Imagen y configuración: `compose.yaml` y `redis/redis.conf`.
- Persistencia: AOF en el volumen `redis-data`.
- Política de memoria: `noeviction`, para no perder trabajos silenciosamente.
- Acceso desde el host: únicamente `127.0.0.1:6379`.
- Autenticación: `REDIS_PASSWORD`, generado en `.env` por `scripts/setup.sh`.

La caída de Redis no impide iniciar sesión: el rate limiter usa temporalmente memoria local. Los trabajos OCR quedan pendientes en PostgreSQL y el reconciliador los recupera cuando Redis vuelve.

Para revisar salud y registros:

```bash
docker compose ps redis ocr-worker
docker compose logs redis ocr-worker
```

`make clean` elimina el volumen `redis-data`. Los documentos y el estado durable del OCR permanecen en RustFS y PostgreSQL, respectivamente.

# OCR documental con OCRmyPDF

El servicio `ocr-worker` genera una copia PDF buscable después de que FastAPI activa un PDF limpio. El original de RustFS nunca se modifica y sigue siendo la descarga predeterminada.

## Flujo

1. FastAPI activa el original y crea un derivado OCR `pending` en PostgreSQL.
2. El reconciliador ARQ publica un trabajo único en Redis.
3. El worker reclama el derivado, verifica el SHA-256 y valida que el PDF no esté cifrado, firmado ni exceda 300 páginas.
4. OCRmyPDF procesa español e inglés con rotación, corrección de inclinación y `--skip-text`.
5. ClamAV escanea el resultado y el worker lo almacena bajo una clave privada nueva en RustFS.

El contenedor incluye Ghostscript, Tesseract `spa+eng`, qpdf, pngquant y unpaper. Tiene un único trabajo concurrente, límite de 2 CPU, 2 GiB de RAM y `/tmp` efímero de 1 GiB.

## Operación

- Estado: `GET /api/v1/documents/{id}` (`ocr_status` y `ocr_available`).
- Descarga OCR: `POST /api/v1/documents/{id}/download-url?variant=ocr`.
- Reintento administrativo: `POST /api/v1/documents/{id}/ocr/retry`.
- Registros: `docker compose logs -f ocr-worker`.

Los errores permanentes (PDF cifrado, firmado, inválido o excesivo) quedan `skipped`. Los errores temporales se intentan tres veces y luego quedan `failed`. Un trabajo abandonado vuelve a `pending` después del periodo configurado.

En despliegues externos, `REDIS_ENABLED=false` y `OCR_ENABLED=false` hasta provisionar Redis, un worker y almacenamiento de objetos reales.

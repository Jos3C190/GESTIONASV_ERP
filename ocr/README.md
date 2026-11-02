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

## Lectura de licencias con el modelo de visión

Es un flujo aparte del OCR de PDF: `vlm-worker` propone los datos de la licencia y
una persona los confirma. El modelo solo ocupa VRAM mientras hay trabajo. Sin él, la
captura sigue funcionando a mano.

### Preparar el modelo (solo una vez)

1. Descarga los pesos oficiales de `tencent/HunyuanOCR` sin `v1.0/` ni `dflash/`.
2. Conviértelos con `convert_hf_to_gguf.py` de llama.cpp, en la misma versión del motor
   (la imagen `vlm` de `backend/Dockerfile`), para obtener `hyocr-f16.gguf` y, con
   `--mmproj`, `mmproj-hyocr-f16.gguf`.
3. Cópialos al volumen `proyecto_erp_vlm-models`. Un volumen de Docker arranca el modelo
   unas cuatro veces más rápido que un montaje desde Windows.

### Encender

En `.env`, pon `LICENSE_CAPTURE_ENABLED=true` y `VLM_ENABLED=true`, y luego:

```bash
docker compose --profile vlm up -d --build vlm-worker backend
```

### Móviles en la misma red

La cámara en vivo exige HTTPS. En `.env`, usa la IP de la PC:

```dotenv
LAN_HOST=192.168.1.50
FRONTEND_ORIGIN=https://192.168.1.50
PUBLIC_API_URL=https://192.168.1.50
CORS_ORIGINS=https://192.168.1.50,http://localhost:5173
OBJECT_STORAGE_PUBLIC_ENDPOINT=https://192.168.1.50:9443
OBJECT_STORAGE_CORS_ORIGINS=https://192.168.1.50,http://localhost:5173
```

```bash
docker compose --profile lan up -d
```

Cada móvil debe confiar una vez en el certificado local, que está en
`/data/caddy/pki/authorities/local/root.crt` dentro de `lan-proxy`. El puerto de la PC no
debe exponerse a internet. Sin HTTPS, el móvil aún puede tomar la foto con su cámara nativa
mediante el botón «Tomar con el teléfono», pero necesita alcanzar el API y el almacenamiento.

### Resultados de la prueba técnica (RTX 4060, 8 GB, noviembre de 2026)

| Medida | Resultado | Meta |
|---|---|---|
| Arranque en frío (volumen / montaje desde D:) | ~4.5 s / ~19 s | ≤ 25 s |
| Inferencia por lado a 1280 px, sin caché | 1.7–2.7 s | ≤ 8 s |
| VRAM añadida en el pico | ~2.9 GB | ≤ 4.5 GB |
| VRAM al detener el modelo | vuelve al nivel inicial | igual |

- **1280 px es el tamaño elegido.** A 1600 px el tiempo casi se duplica y la salida empeoró.
- **Precisión:** solo se midió con 2 frentes y 1 reverso, así que es una prueba de que
  funciona, no una medida de precisión. Hacen falta más muestras.
- **La fecha tapada devolvió texto, no `null`.** El modelo no inventó una fecha, y el
  validador de formato lo rechaza. Por eso el backend tiene la última palabra.
- **La imagen CUDA 13 pide un driver ≥ 13.4;** esta PC tiene 13.3, y por eso se usa la de CUDA 12.

### Límites

- El sistema comprueba que los datos sean coherentes; **no certifica que el documento sea
  auténtico**.
- Trivy no inspecciona dentro del binario `llama-server`; se compensa fijando la imagen por
  digest y revisando sus publicaciones.
- No se extraen sangre, alergias, medicación, dirección, correo ni contacto de emergencia,
  pero siguen visibles en la foto del reverso: solo la ve quien tiene `drivers:documents`.
- La política de uso de Tencent prohíbe decisiones automatizadas de alto impacto en el ámbito
  laboral, y por eso la confirmación humana es obligatoria.

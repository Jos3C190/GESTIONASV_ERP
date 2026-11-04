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
una persona los confirma. El modelo solo ocupa VRAM mientras hay trabajo. Es la única vía
para registrar una licencia: las rutas de documentos de Conductores y RR. HH. rechazan esas
categorías. Sin el modelo, la captura sigue funcionando a mano, con las mismas validaciones.

### Instalar

Con el ERP ya instalado (`make setup`), un solo comando:

```bash
make setup-vlm
```

Sin Make, usa `bash scripts/setup-vlm.sh`. Te pedirá confirmar antes de descargar.

**Qué necesitas:**
- GPU NVIDIA con al menos 4 GB de memoria y Docker con acceso a ella. Se probó en una RTX 4060.
- Unos 10 GB libres para Docker durante la instalación. Al terminar, el modelo ocupa unos 2 GB.
- Internet para descargar unos 3 GB. Solo la primera vez.
- Aceptar la [licencia de Tencent](https://huggingface.co/tencent/HunyuanOCR).

**Qué hace:**
1. Comprueba la GPU y el disco.
2. Descarga los pesos oficiales y los convierte con la misma versión del motor. Todo queda fijado
   por versión, así que el resultado es idéntico en cada instalación y se verifica con su checksum.
3. Guarda el modelo en un volumen de Docker, que arranca unas cuatro veces más rápido que un
   montaje desde Windows.
4. Pone `VLM_ENABLED=true` en `.env`, enciende el worker y comprueba que el modelo cargue en la GPU.

Se puede repetir: si el modelo ya está bien, no descarga nada. Si la instalación se corta, repítela
y aprovechará lo ya descargado. Con `--no-start` solo prepara el modelo; con `--yes` no pregunta.

**Comprobar que funciona:** en Conductores, abre un conductor, entra a la pestaña Licencia y usa
**Capturar con fotos** con una licencia de muestra. Debe proponer los datos para que los revises.
El comando prueba que el modelo carga, pero no que lea bien; eso solo lo dice esta prueba.

### Si algo falla

| Mensaje o síntoma | Qué hacer |
|---|---|
| No se encontró una GPU NVIDIA | Sin GPU no hay lector: las licencias se escriben a mano |
| El worker no quedó sano o el modelo no carga | Revisa `docker compose --profile vlm logs vlm-worker`. La imagen usa CUDA 12: comprueba el driver y que Docker vea la GPU |
| El checksum no coincide | No uses ese modelo; repite el comando. Si cambiaste la versión del motor, hay que actualizar también las versiones y checksums de `scripts/setup-vlm.sh` |
| El asistente dice que la lectura automática no está disponible | Revisa que `vlm-worker` esté corriendo y que `.env` tenga `VLM_ENABLED=true` |

### Actualizar el motor

Si cambias la imagen `vlm` de `backend/Dockerfile`, actualiza `LLAMA_COMMIT` en
`scripts/setup-vlm.sh`, reconvierte el modelo y actualiza sus checksums. El conversor y el motor
deben ser de la misma versión.

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

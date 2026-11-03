---
name: setup-vlm
description: Instala, repara o verifica el lector de licencias con modelo de visión (HunyuanOCR, llama.cpp, vlm-worker). Úsala cuando pidan activar la lectura automática de licencias, preparar el modelo, o cuando el asistente de captura diga que la lectura automática no está disponible. No aplica al OCR de PDF ni a ejecutar el modelo fuera de una GPU NVIDIA.
---

# Instalar el lector de licencias

`scripts/setup-vlm.sh` hace el trabajo y `ocr/README.md` lo explica. No repitas sus pasos a mano ni copies sus comandos: el script fija versiones y verifica checksums, y una conversión manual puede producir un modelo distinto.

## Antes de correrlo

1. **Comprueba la GPU:** `nvidia-smi`. Si no hay GPU NVIDIA, detente y dilo. El ERP funciona sin el lector: los datos de la licencia se escriben a mano. No propongas ejecutarlo en CPU.
2. **Comprueba que el ERP esté instalado:** debe existir `.env`. Si no, es `make setup` primero.
3. **Pide confirmación a la persona.** Di que descarga unos 3 GB, que usará unos 10 GB de Docker durante la instalación y que los pesos son de Tencent con su [propia licencia](https://huggingface.co/tencent/HunyuanOCR). `--yes` omite la pregunta del script, así que solo úsalo después de esa confirmación.

## Correrlo

```bash
bash scripts/setup-vlm.sh --yes
```

Tarda varios minutos en la primera ejecución: lánzalo en segundo plano. Se puede repetir; si el modelo ya está bien, no descarga nada, y si se corta, aprovecha lo descargado.

Para probar cambios del script sin tocar el modelo real, usa un volumen aparte y bórralo al terminar, solo ese:

```bash
VLM_MODELS_VOLUME=vlmtest-models bash scripts/setup-vlm.sh --yes --no-start
```

## Qué no hacer

- No borres el volumen `*_vlm-models`: con el script basta para detectar y reemplazar un modelo dañado.
- No bajes la verificación de checksums para que el script pase. Si no coinciden, investiga la causa.
- No subas pesos ni archivos `.gguf` al repositorio.
- No leas ni muestres secretos de `.env`. El script solo escribe `VLM_ENABLED=true`.
- No uses licencias reales para probar. Pide muestras ficticias a la persona.
- No cambies la imagen `vlm` de `backend/Dockerfile` sin actualizar `LLAMA_COMMIT` y los checksums: conversor y motor deben ser de la misma versión.

## Cómo saber que funcionó

Que el script termine bien prueba que el modelo carga en la GPU, **no que lea bien**. Dilo así al informar. Para darlo por bueno falta una lectura real, hecha en la app o por la persona: Conductores > un conductor > pestaña Licencia > **Capturar con fotos**, con una licencia de muestra.

Comprueba también que no se quede ocupando la GPU: tras `VLM_IDLE_SECONDS` sin trabajo (5 minutos por defecto), el modelo debe liberarse. La memoria en uso se ve con `nvidia-smi`.

Si algo falla, consulta "Si algo falla" en `ocr/README.md` y los registros con `docker compose --profile vlm logs vlm-worker`.

# Antivirus documental — ClamAV

Esta carpeta reúne la configuración y documentación específica del antivirus usado por el flujo
documental. ClamAV escanea cada archivo antes de que pueda alcanzar el estado `active`.

## Contenido

- `clamav.env`: límites de escaneo y frecuencia de actualización de firmas cargados por
  `compose.yaml`.

El cliente INSTREAM permanece en `backend/app/infrastructure/malware_scanner.py` porque es el
adaptador de infraestructura del backend.

## Configuración

| Variable | Valor | Propósito |
|---|---:|---|
| `CLAMD_CONF_StreamMaxLength` | `55M` | Permite transmitir un documento de hasta 50 MiB con margen. |
| `CLAMD_CONF_MaxFileSize` | `55M` | Límite máximo por archivo. |
| `CLAMD_CONF_MaxScanSize` | `200M` | Límite total al inspeccionar contenedores y archivos comprimidos. |
| `FRESHCLAM_CHECKS` | `4` | Actualiza las firmas cuatro veces al día. |

El puerto `3310` solo se expone dentro de la red de Docker Compose; no se publica al host. Las
firmas persisten en el volumen `clamav-db`.

## Operación y diagnóstico

```bash
docker compose up -d clamav
docker compose ps clamav
docker compose logs --tail=100 clamav
```

`GET /health/ready` informa el componente `clamav`. Si el servicio no responde, el backend falla
cerrado: conserva el documento en `pending_scan`, no permite descargarlo y deja que la operación
`complete` sea reintentada.

Cuando se detecta malware, el documento pasa a `quarantined`, se registra la auditoría y nunca se
genera una URL de descarga. La tarea de mantenimiento elimina físicamente el objeto después del
periodo configurado, conservando el registro auditable.

## Prueba segura

La integración opcional usa la cadena de prueba EICAR para verificar que ClamAV rechaza contenido
malicioso sin utilizar malware real:

```bash
docker compose exec -e RUN_DOCUMENT_STORAGE_INTEGRATION=true \
  -e OBJECT_STORAGE_TEST_PUBLIC_ENDPOINT=http://rustfs:9000 \
  backend pytest -q tests/integration/test_document_services_optional.py
```

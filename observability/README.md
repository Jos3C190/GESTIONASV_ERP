# Observabilidad local del ERP

Este directorio contiene el stack completo de métricas, trazas, logs y alertas del backend.
La aplicación emite OTLP y no depende de Grafana: el mismo contrato permite conectar en el futuro
Grafana Cloud, Datadog, New Relic u otro receptor compatible sin modificar módulos de negocio.

## Servicios y acceso

`make setup` inicia y verifica automáticamente:

| Componente | Función | Acceso local |
| --- | --- | --- |
| OpenTelemetry Collector | Recibe, depura y enruta OTLP | Solo red Docker |
| Prometheus | Métricas y reglas | http://localhost:9090 |
| Loki | Logs centralizados | Solo red Docker |
| Tempo | Trazas distribuidas | Solo red Docker |
| Alertmanager | Agrupación y deduplicación | http://localhost:9093 |
| Grafana | Paneles y exploración | http://localhost:3000 |

El usuario inicial de Grafana es `admin` salvo que se cambie `GRAFANA_ADMIN_USER`. La contraseña
se genera en el `.env` ignorado por Git. El setup nunca la imprime. No existe acceso anónimo ni
registro público.

Comandos operativos:

```text
make observability-status
make observability-logs
make observability-validate
make observability-restart
```

## Flujo y persistencia

FastAPI, el worker OCR, el mantenimiento documental y RustFS envían señales por OTLP/HTTP al
Collector. Este expone métricas para Prometheus y utiliza colas persistentes para reintentar logs y
trazas cuando Loki o Tempo estén temporalmente caídos. La retención local es de siete días;
Prometheus también está limitado a 1 GiB.

Los volúmenes `prometheus-data`, `grafana-data`, `loki-data`, `tempo-data`, `alertmanager-data` y
`otel-queue-data` sobreviven reinicios y reconstrucciones. `make clean` elimina deliberadamente
todos estos históricos junto con los demás volúmenes del proyecto.

## Paneles provisionados

La carpeta Grafana **ERP Observability** contiene seis paneles inmutables: Resumen ERP; API y
PostgreSQL; Documentos; OCR y Redis; Exploración correlacionada; y Stack de observabilidad.
Tempo enlaza cada traza con sus logs en Loki; Loki reconoce `trace_id`; los exemplars y el mapa de
servicios enlazan hacia Prometheus. Los cambios permanentes se realizan en los JSON versionados.

## Privacidad y seguridad

- No se exportan cuerpos HTTP, query strings, cookies ni encabezados de autorización.
- Botocore no se auto-instrumenta, evitando URLs firmadas y claves de objetos.
- SQL se captura sin parámetros y las órdenes Redis se sustituyen por `[REDACTED]`.
- La aplicación y el Collector redactan contraseñas, tokens, firmas S3 y rutas documentales.
- Loki usa únicamente servicio, entorno y severidad como etiquetas estables. IDs de traza y
  solicitud son metadatos estructurados.
- Prometheus y Alertmanager solo escuchan en `127.0.0.1`; no deben publicarse sin autenticación.

Para comprobar la redacción, envíe un valor centinela en un campo sensible de un entorno aislado y
búsquelo en Grafana Explore, Prometheus y Tempo. Debe estar ausente o aparecer como `[REDACTED]`.

## Alertas

Las reglas cubren ausencia del backend, tasa 5xx, latencia p95, dependencias documentales, fallback
de Redis, fallos OCR y salud del propio stack. Alertmanager agrupa, deduplica e inhibe avisos. En
esta fase no envía correo ni webhooks: los avisos se consultan en Grafana o Alertmanager.

## Producción y receptores externos

La observabilidad está deshabilitada por defecto en `compose.prod.yaml` y `render.yaml`. Para
habilitarla configure al menos:

```text
OBSERVABILITY_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer ...
OTEL_TRACE_SAMPLE_RATIO=0.1
```

HTTP en staging o producción se rechaza salvo `OTEL_EXPORTER_OTLP_INSECURE=true`. Las cabeceras
OTLP son secreto y nunca deben confirmarse. El perfil `local-observability` permite levantar este
stack junto al overlay de producción solo para diagnóstico explícito.

## Diagnóstico

- Backend `degraded` con `otel_collector=down`: revise `make observability-logs`; el negocio debe
  continuar funcionando y el Collector se recuperará al reiniciarse.
- Métricas sin datos: compruebe los targets en Prometheus y el exporter `erp-application`.
- Trazas sin logs: confirme que el log contiene `trace_id` y que Loki está saludable.
- Cola creciente: revise espacio en `otel-queue-data` y disponibilidad de Loki/Tempo.
- Dashboard sin fuente: ejecute `make observability-validate` y reinicie Grafana.

## Actualización de versiones

Cambie una imagen fijada por vez, consulte sus notas de migración, ejecute las validaciones de
configuración y complete el flujo real API → traza → logs → métrica. No use `latest`.

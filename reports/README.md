# Reportes locales de seguridad

Esta carpeta conserva únicamente la configuración versionada de OWASP ZAP. Los
archivos JSON y HTML son resultados locales efímeros y no se incluyen en Git,
porque una copia histórica puede aparentar que representa dependencias actuales.

Comandos disponibles:

- `make security-scan-images`: construye y analiza `dev`, `prod` y `ocr`.
- `make security-scan`: pruebas adversariales, ZAP baseline y Trivy.
- `make security-scan-deep`: añade el escaneo activo OpenAPI de ZAP.

Trivy genera:

- `trivy-report.json`: repositorio y lockfiles.
- `trivy-backend-dev-report.json` y `trivy-backend-dev-os-report.json`: backend local.
- `trivy-backend-prod-report.json` y `trivy-backend-prod-os-report.json`: backend productivo.
- `trivy-ocr-report.json` y `trivy-ocr-os-report.json`: worker OCR.

El escaneo del repositorio monta únicamente los manifiestos y lockfiles reales de
`backend` y `frontend`, incluyendo dependencias de desarrollo. Esto evita analizar
artefactos generados o cachés locales sin dejar fuera paquetes que llegan a las
imágenes o a las herramientas de prueba.

GitHub Actions conserva estos reportes como artefactos durante 14 días. Todos los
controles fallan ante cualquier vulnerabilidad `HIGH` o `CRITICAL`. Las bibliotecas
usan severidad GHSA/NVD y el sistema operativo usa la severidad de Debian, evitando
reinterpretar como bloqueo un CVE que Debian todavía no ha clasificado. No se usa
`--ignore-unfixed`, `--ignore-status` ni una lista de excepciones.

Una excepción futura deberá registrar el ID del hallazgo, su justificación, el
responsable y una fecha de expiración. Esta remediación no incorpora excepciones.

Los contenedores Trivy eliminan todas las capacidades Linux y recuperan únicamente
`DAC_OVERRIDE`. Esta capacidad limitada permite escribir los JSON en el directorio
enlazado `reports/` cuando pertenece al usuario del runner de GitHub Actions.

# Sistema Red Team / Blue Team y Automatización de Seguridad (DevSecOps)

> **Versión:** `v1.1.0` | **Última actualización:** `01/09/2026`
> **Proyecto:** ERP System  
> **Stack:** OWASP ZAP + Trivy + Pytest Adversarial Bounds + Git Hooks (.githooks)

Este documento detalla la arquitectura de seguridad defensiva (**Blue Team**) y ofensiva (**Red Team**), los contenedores de auditoría automatizada, el sistema de bloqueo de `commit` y `push` mediante Git Hooks y las notificaciones flotantes de Windows.

---

## 1. Visión General de la Arquitectura Red Team / Blue Team

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RED TEAM (Capa Ofensiva)                           │
│  ┌───────────────────────────┐ ┌──────────────────────┐ ┌─────────────────┐ │
│  │ OWASP ZAP DAST / OpenAPI  │ │ Trivy SCA & Secrets  │ │ Pytest Fuzzing  │ │
│  └─────────────┬─────────────┘ └──────────┬───────────┘ └────────┬────────┘ │
└────────────────│──────────────────────────│──────────────────────│──────────┘
                 │                          │                      │
                 ▼                          ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REPORTES EN ./reports/*.json                         │
└──────────────────────────────────────────┬──────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BLUE TEAM (Capa Defensiva)                           │
│  ┌───────────────────────────┐ ┌──────────────────────┐ ┌─────────────────┐ │
│  │ Agentes IA Remedición     │ │ RBAC & Security Hdrs │ │ Pydantic v2 DTOs│ │
│  └───────────────────────────┘ └──────────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

El ERP System implementa un ciclo cerrado de seguridad automatizada:
1. **Red Team (Simulaciones de Ataque Real):** Contenedores Docker aislados que ejecutan escaneos DAST activos, inyecciones de código y fuzzing de entradas.
2. **Reportes estructurados:** Generación local de diagnósticos en `./reports/`. Estos resultados son efímeros y GitHub Actions los conserva como artefactos durante 14 días; no se versionan reportes obsoletos.
3. **Blue Team (Remediación Defensiva):** Habilidad de Agentes de IA (`.agents/skills/security-remediation/SKILL.md`) que lee los reportes JSON y aplica parches de código en FastAPI/SvelteKit.

---

## 2. Contenedores y Herramientas de Auditoría Real

Los escáneres de seguridad están containerizados en el perfil opcional `security` y `security-deep` de `compose.yaml`, evitando instalar herramientas pesadas en la máquina host.

### 2.1 OWASP ZAP (DAST - Dynamic Application Security Testing)
- **Imagen Docker:** `ghcr.io/zaproxy/zaproxy:stable`
- **Servicio `security-zap` (Baseline):** Ejecuta `zap-baseline.py` contra `http://backend:8000`. Detecta fallas pasivas de cabeceras HTTP, cookies inseguras y fugas de información.
- **Servicio `security-zap-deep` (Active OpenAPI Scan):** Ejecuta `zap-api-scan.py -t http://backend:8000/openapi.json -f openapi`. Lanza **118 reglas de ataque activo** probando inyecciones SQL en PostgreSQL, Remote Command Execution (RCE), Path Traversal (LFI), XSS reflejado/persistente, Server-Side Template Injection (SSTI), XXE y desinteligencia de firmas JWT.

### 2.2 Trivy Scanner (SCA - Software Composition Analysis)
- **Imagen Docker fijada:** `aquasec/trivy:0.74.0`.
- **Servicio `security-trivy`:** Analiza el repositorio y los lockfiles de Python y Node.js.
- **Versiones Python corregidas:** FastAPI `0.141.1`, Starlette `1.4.1` y cryptography `50.0.1` como mínimos fijados por el lockfile.
- **Dependencias frontend corregidas:** Happy DOM `20.12.0` y resoluciones seguras explícitas para `brace-expansion`, `js-yaml` y `nanoid`.
- **Imágenes verificadas:** backend `dev`, backend `prod` y worker `ocr`; una construcción adicional sin `target` confirma que Render inicia Uvicorn y no ARQ.
- **Política:** cualquier hallazgo `HIGH` o `CRITICAL` produce código de salida distinto de cero. Las bibliotecas se evalúan con severidad GHSA/NVD y los paquetes del sistema con la clasificación oficial de Debian. No se usa `--ignore-unfixed`, `--ignore-status` ni una lista de excepciones.
- **Reportes:** `trivy-report.json` para lockfiles y pares `*-report.json` / `*-os-report.json` para las bibliotecas y el sistema operativo de cada imagen.
- **Excepciones futuras:** solo podrán incorporarse con el identificador exacto del hallazgo, justificación técnica, responsable y fecha de expiración; una excepción vencida vuelve a bloquear el control.

### 2.3 Pytest Adversarial Bounds (`test_security_bounds.py`)
- **Ubicación:** [`backend/tests/integration/api/test_security_bounds.py`](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/backend/tests/integration/api/test_security_bounds.py)
- **Propósito:** Valida el comportamiento ante tampering de firmas JWT (`alg: none`, claves erróneas), desestimación de peticiones no autenticadas (401), fuzzing con NUL bytes (`\x00`), payloads SQLi y scripts `<script>` en credenciales.

---

## 3. Bloqueo Automatizado de Git Hooks (`pre-commit` y `pre-push`)

Para impedir que se suba código inseguro o con vulnerabilidades a los entornos de desarrollo o producción, se utiliza el sistema de **Git Hooks** versionado en la carpeta [`.githooks/`](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/.githooks).

### 3.1 Hook `pre-commit` (Pruebas Rápida de Límites de Seguridad)
- **Ubicación:** `.githooks/pre-commit`
- **Disparador:** Se ejecuta automáticamente cada vez que el desarrollador hace `git commit` (en la terminal o mediante la interfaz de VS Code/Cursor/GitHub Desktop).
- **Acción:** Ejecuta la suite pytest de seguridad (`test_security_bounds.py`) en ~3 segundos.
- **Resultado:**
  - **Si aprueba:** Continúa con el commit y emite una notificación flotante en Windows.
- **Si falla o Docker no está disponible:** **cancela y aborta el commit inmediatamente**, indicando el control que no pudo ejecutarse.

### 3.2 Hook `pre-push` (Auditoría Profunda Red Team)
- **Ubicación:** `.githooks/pre-push`
- **Disparador:** Se activa explícitamente con `ENABLE_PRE_PUSH_SECURITY_SCAN=1` antes de hacer `git push`.
- **Acción:** Lanza el escaneo DAST Activo Profundo (OWASP ZAP OpenAPI) + Trivy SCA (~1 a 2 minutos).
- **Resultado:**
  - **Si aprueba:** Subida exitosa al repositorio remoto y notificación flotante en Windows.
- **Si falla:** Propaga el código de error y aborta el `push`, conservando todos los reportes que alcanzaron a generarse.

GitHub Actions ejecuta siempre el control Trivy para pull requests y pushes a `develop` y `main`, por lo que la protección remota no depende de habilitar el hook local.

### 3.3 Activación 100% Automática sin Pasos Manuales
Git por defecto no rastrea `.git/hooks/`. Para resolver esto, el script [`scripts/setup.sh`](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/scripts/setup.sh) ejecuta automáticamente:

```bash
git config core.hooksPath .githooks
```

De este modo, cuando cualquier desarrollador clona el proyecto y levanta el entorno por primera vez, Git vincula los hooks de seguridad automáticamente.

---

## 4. Notificaciones Flotantes de Windows (Toast Notifications)

El script de ayuda [`scripts/notify.ps1`](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/scripts/notify.ps1) interactúa con la API nativa de notificaciones de Windows (`System.Windows.Forms.NotifyIcon`).

Al completar un `commit` o `push` con éxito, aparece un globo informativo flotante en la esquina inferior derecha de la pantalla:

> 🔒 **ERP Security - Pre-Commit / Pre-Push**  
> *Auditoría de seguridad aprobada con éxito: 0 vulnerabilidades críticas.*

---

## 5. Comandos de Ejecución Manual

Los desarrolladores y auditores pueden lanzar los escaneos de seguridad en cualquier momento:

### En Windows PowerShell:
```powershell
# Escaneo de seguridad estándar (Baseline DAST + Trivy)
.\scripts\security-scan.ps1

# Escaneo profundo de seguridad (OWASP ZAP OpenAPI Active Scan + Pytest Fuzzing + Trivy)
.\scripts\security-scan.ps1 -Deep
```

### En Linux / macOS / WSL / Make:
```bash
# Escaneo estándar
make security-scan

# Construcción y escaneo exclusivo de imágenes propias
make security-scan-images

# Escaneo profundo
make security-scan-deep
```

---

## 6. Remediación Asistida por Agentes de IA (Blue Team Protocol)

Cuando un escaneo detecta vulnerabilidades, los agentes de IA invocan la habilidad [`.agents/skills/security-remediation/SKILL.md`](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/.agents/skills/security-remediation/SKILL.md):

1. Leen los reportes locales recién generados o descargan el artefacto correspondiente de GitHub Actions.
2. Identifican la causa raíz (Falta de permiso RBAC, header HTTP ausente, Pydantic DTO permisivo, paquete desactualizado).
3. Aplican la solución defensiva en el código fuente.
4. Vuelven a ejecutar `.\scripts\security-scan.ps1 -Deep` para validar que no quedan hallazgos `HIGH` o `CRITICAL` antes de cerrar la tarea.

# Seguridad, RBAC y Bitácora de Auditoría (Security & Audit Guide)

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  

Este documento describe la arquitectura de seguridad, los mecanismos de autenticación y autorización (RBAC), la política de protección de datos y el funcionamiento de la **bitácora de auditoría append-only** en **ERP System**.

---

## 1. Arquitectura de Seguridad en 5 Capas

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CAPA 1: RED Y BORDES (Nginx Reverse Proxy, SSL/TLS, Security Headers)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│ CAPA 2: AUTENTICACIÓN (JWT Tokens + Rotation + HTTP-Only Cookies)       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│ CAPA 3: AUTORIZACIÓN (RBAC Dinámico: resource:action en FastAPI)        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│ CAPA 4: SANITIZACIÓN & VALIDACIÓN (Pydantic v2 + SQLAlchemy ORM)        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│ CAPA 5: AUDITORÍA & ALMACENAMIENTO (Audit Logs Append-Only + Argon2id)  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Autenticación y Gestión de Tokens

### 2.1 Esquema Dual de Tokens (Access + Refresh Token)

El sistema emplea JWT (JSON Web Tokens) firmados mediante algoritmos asimétricos o simétricos HMAC-SHA256 (`HS256`).

- **Access Token:**
  - **Vida útil:** Short-lived (15 minutos).
  - **Uso:** Header HTTP `Authorization: Bearer <token>`.
  - **Contenido del payload:** `sub` (User ID), `role`, `permissions`, `exp`, `jti`.
- **Refresh Token:**
  - **Vida útil:** Long-lived (7 días).
  - **Uso:** Almacenado en `Cookie` HTTP-Only (`SameSite=Lax`, `Secure`, `HttpOnly`).
  - **Rotación (Token Rotation):** Cada vez que se solicita un nuevo Access Token con el Refresh Token, el Refresh Token anterior se invalida y se genera un nuevo par de tokens. Si se detecta la re-utilización de un Refresh Token antiguo, la sesión se revoca inmediatamente por sospecha de secuestro.

---

## 3. Autorización Granular (RBAC)

El Control de Acceso Basado en Roles (RBAC) asigna permisos explícitos en formato `recurso:acción`.

### 3.1 Formato de Permisos
- `users:read`, `users:create`, `users:update`, `users:delete`
- `roles:read`, `roles:assign`
- `audit:read`
- `*` (Comodín reservado exclusivamente para el rol `superadmin`).

### 3.2 Inyección y Verificación en FastAPI

Los routers de FastAPI protegen endpoints mediante el middleware/dependencia `require_permission`:

```python
from fastapi import APIRouter, Depends
from app.api.v1.deps import require_permission, get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/employees")

@router.get("", dependencies=[Depends(require_permission("employees:read"))])
async def list_employees():
    ...

@router.post("", status_code=201)
async def create_employee(
    payload: EmployeeCreateSchema,
    current_user: User = Depends(require_permission("employees:create"))
):
    ...
```

---

## 4. Bitácora de Auditoría Append-Only (Audit Logs)

El ERP cuenta con una bitácora inmutable en la que se registran automáticamente todas las operaciones sensibles (creación, edición, desactivación de usuarios, cambios de roles, accesos).

### 4.1 Estructura de la Tabla `audit_logs`

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,          -- e.g., 'user.login', 'employee.create', 'role.update'
    resource VARCHAR(50) NOT NULL,        -- e.g., 'users', 'employees', 'roles'
    resource_id VARCHAR(100),             -- ID del recurso afectado
    changes_before JSONB,                 -- Estado previo (para edicion/borrado)
    changes_after JSONB,                  -- Estado resultante
    ip_address VARCHAR(45),               -- IPv4 o IPv6 del cliente
    user_agent TEXT,                      -- User-Agent del navegador
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

> **Inmutabilidad:** La API **NO** expone endpoints de modificación (`PUT`/`PATCH`) ni eliminación (`DELETE`) sobre la tabla `audit_logs`. La bitácora es strictly append-only.

### 4.2 Servicio de Registro en la Capa de Aplicación

Para registrar un evento en la bitácora dentro de un caso de uso:

```python
from app.domain.ports.audit_log_repository import AuditLogRepositoryPort
from app.domain.entities.audit_log import AuditLogEvent

class AuditLoggerService:
    def __init__(self, audit_repo: AuditLogRepositoryPort):
        self._audit_repo = audit_repo

    async def log_event(
        self,
        user_id: UUID | None,
        action: str,
        resource: str,
        resource_id: str | None = None,
        changes_before: dict | None = None,
        changes_after: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ):
        event = AuditLogEvent(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            changes_before=changes_before,
            changes_after=changes_after,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await self._audit_repo.save(event)
```

---

## 5. Almacenamiento Seguro de Contraseñas y Secretos

1. **Hashing de Contraseñas:** Se utiliza **Argon2id** (vía `passlib` o `argon2-cffi`) con parámetros de memoria y tiempo recomendados por OWASP.
   - Las comparaciones se ejecutan en tiempo constante (`hmac.compare_digest`) para prevenir ataques de timing.
2. **Variables de Entorno y Secretos:**
   - **`JWT_SECRET_KEY`**: Clave criptográfica aleatoria de 256 bits para firmar tokens.
   - **`POSTGRES_PASSWORD`**: Credenciales de la base de datos.
   - **Regla estricta:** Ninguna clave o secreto se incluye en el código fuente ni en el historial de Git.

---

## 6. Cabeceras de Seguridad y CORS

El middleware de la aplicación configura automáticamente las cabeceras HTTP de protección:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy`: Restringe el origen de scripts, estilos e imágenes.
- **CORS:** Restringido a los dominios configurados en `BACKEND_CORS_ORIGINS`. Nunca se permite `*` en combinación con `allow_credentials=True`.

---

## 7. Sistema Red Team / Blue Team y Git Hooks

Product image galleries use the `products:images` permission in addition to
`products:manage`. Local uploads require `media.upload`; external images are
HTTPS references rendered by the browser and are never fetched by the API.
The CSP therefore permits HTTPS image sources while keeping scripts and
connections restricted. Gallery mutations are recorded in the append-only
audit log without storing binary content.

Para conocer la arquitectura completa de escáneres DAST en contenedor (OWASP ZAP OpenAPI scan), auditoría de dependencias (Trivy), pruebas adversariales (Pytest fuzzing) y el bloqueo automático mediante `.githooks` (`pre-commit` y `pre-push`), consulta el documento dedicado:

👉 **[docs/red-team-blue-team.md](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/docs/red-team-blue-team.md)**

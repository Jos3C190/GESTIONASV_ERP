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

### Catalog variant authorization and audit

The `products:variants` permission controls family attributes, values and
variant lifecycle. `products:read` is sufficient for viewing them;
`products:identifiers` controls variant identifiers and `products:images`
controls variant images. A Cloudinary upload additionally requires
`media.upload`. Permissions are resolved from the authenticated user's company
scope and are never inferred from a role name supplied by a tenant.

Variant operations are audited with product/variant IDs, SKU, combination,
state, identifiers and image source metadata. Binary content and secrets are
never written to the audit log.

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

Supplier logos and contact avatars use `suppliers:images`. Local uploads also
require `media.upload`; external HTTPS references do not. Assets are claimed
transactionally with the supplier/contact UUID and company scope, and are
detached rather than physically deleted during the business transaction.

Supplier master data adds `suppliers:tax_identifiers`, `suppliers:addresses` and
`suppliers:bank_accounts`. The first two protect fiscal/address mutations;
bank endpoints additionally require the banking permission and return only
masked last-four projections. Bank account and IBAN values are encrypted with
AES-GCM before persistence using the environment-managed
`SUPPLIER_DATA_ENCRYPTION_KEY`. Missing key configuration fails closed for bank
writes. Audit snapshots include IDs, origin, status and last four digits only;
they never contain plaintext, ciphertext or complete financial identifiers.

Supplier tax identifiers are intentionally country/type driven rather than
hard-coded to El Salvador's NIT/NRC. No external URL is fetched by the backend;
only HTTPS references without credentials or local/private hosts are accepted.

### Product-domain security boundaries

Future product capabilities are intentionally blocked until their consuming
modules exist. Inventory, purchasing, landed costs, price lists, packaging,
variant operations, fiscal data and compliance documents must not be simulated with
unvalidated product columns. When activated, each capability must define its
own RBAC permission, tenant/company checks, append-only audit events,
idempotency and rollback behavior. Sensitive future values such as costs,
accounting mappings, compliance files or integration credentials must be
permission-filtered and must never be written to audit logs in plaintext.

The complete dependency and acceptance register is maintained in
`docs/product-module-future-debt.txt`.

Product master mutations are separated by permission: `products:master_data`
for the commercial/storage ficha, `products:identifiers` for codes,
`products:suppliers` for sourcing terms and `products:lifecycle` for status
transitions. Product supplier and identifier endpoints always bind both the
product and relation to the effective company; preferred-supplier changes lock
the product row. Audit events retain IDs, origin/type, preferred state and
commercial terms needed for traceability, without exposing credentials or
future inventory secrets.

### Physical warehouse capacity and inventory (revisions 0039–0040)

Capacity changes are tenant-scoped and audited with before/after certified and
operational limits, profile and enforcement mode. Database checks keep every
operational limit at or below its certified boundary. Certified limits are
never overridable. A temporary operational exception requires the dedicated
`capacity:override_operational` permission, a non-empty business reason, a short
expiration and an audit record.

Revision 0040 auto-assigns its new permissions only to the visible, global
`SUPER_ADMIN` system role. Company-owned role names are user-managed labels and
are never treated as a stable authorization identity by the migration;
administrators (or the development seed) must assign the inventory permissions
explicitly. Permission catalogue rows and grants are preserved on downgrade
because they are shared RBAC data and may have existed before the revision.

Inventory commands use deterministic locks from warehouse and structural group
to location, plus idempotency keys for posted movements. A movement header and
its lines form an immutable ledger. Posted rows cannot be edited or deleted;
the dedicated workflow that will create compensating reversal movements remains
an explicit follow-up. Balance and handling-unit updates commit atomically with
the ledger so a transfer cannot free its origin without occupying its destination.

Missing or unreliable weight/volume fails closed for normal stock: reception is
limited to quarantine until measurements are verified. Active reservations are
included in projected consumption and cannot silently disappear; cancellation,
expiry and consumption are explicit audited transitions. Company predicates at
the application boundary and composite foreign keys protect inventory identities
and scoped overrides. Because a location inherits its company through
`location -> warehouse -> branch`, direct SQL imports must use the same validated
service boundary until that lineage is also enforced by a database trigger or a
denormalized composite key.

Para conocer la arquitectura completa de escáneres DAST en contenedor (OWASP ZAP OpenAPI scan), auditoría de dependencias (Trivy), pruebas adversariales (Pytest fuzzing) y el bloqueo automático mediante `.githooks` (`pre-commit` y `pre-push`), consulta el documento dedicado:

👉 **[docs/red-team-blue-team.md](file:///d:/josec/Documents/Ciclo%20X/TRANSACCIONES%20COMERCIALES%20POR%20MEDIOS%20ELECTR%C3%93NICOS%20SECCI%C3%93N%20A/PROYECTO_ERP/docs/red-team-blue-team.md)**

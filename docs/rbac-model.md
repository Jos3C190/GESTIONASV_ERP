# RBAC Model

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  
> Dynamic Role-Based Access Control model and permission matrix design.

## 1. Goals

- **Dynamic**: permissions-to-roles and roles-to-users are configured at runtime
  from the database, never hardcoded as static decorators only.
- **Administrable from the UI**: a permissions matrix lets an admin toggle
  `recurso:accion` per role.
- **Deny-by-default backend enforcement**: every sensitive endpoint passes
  through a `require_permission("code")` dependency. Hiding UI is convenience,
  not security.
- **Auditable**: every role/permission/assignment change is recorded in the
  audit log with before/after state.
- **Extensible to ABAC**: a `conditions JSONB` column is reserved (unused in
  Phase 2) so future policy conditions ("only own department") can be added
  without a schema rewrite.

## 2. Permission catalogue

Permission codes follow the format `recurso:accion`.

| Module | Code | Description |
|--------|------|-------------|
| users | `users:create` | Create users |
| users | `users:read` | List/view users |
| users | `users:update` | Edit user attributes |
| users | `users:deactivate` | Deactivate / soft-delete |
| users | `users:force_password_reset` | Force password reset |
| users | `users:unlock` | Unlock a locked account |
| users | `users:manage_sessions` | View/revoke sessions |
| employees | `employees:create` | Create employees |
| employees | `employees:read` | List/view employees |
| employees | `employees:update` | Edit employees |
| employees | `employees:delete` | Soft-delete employees |
| employees | `departments:manage` | Manage departments |
| rbac | `roles:create` | Create roles |
| roles | `roles:read` | List/view roles |
| roles | `roles:update` | Edit roles |
| roles | `roles:delete` | Delete roles (non-system only) |
| roles | `roles:assign` | Assign roles to users |
| roles | `roles:revoke` | Revoke roles from users |
| roles | `permissions:manage` | Modify role/permission mappings |
| purchase_requests | `purchase_requests:read` | Ver solicitudes de compra |
| purchase_requests | `purchase_requests:manage` | Crear, editar, enviar y cancelar solicitudes |
| purchase_requests | `purchase_requests:approve` | Aprobar o rechazar solicitudes |
| purchase_quotations | `purchase_quotations:read` | Ver solicitudes de cotización, ofertas y comparativas |
| purchase_quotations | `purchase_quotations:manage` | Crear, enviar, registrar y evaluar cotizaciones |
| purchase_quotations | `purchase_quotations:select` | Seleccionar la oferta ganadora |
| purchase_orders | `purchase_orders:read` | Ver órdenes de compra |
| purchase_orders | `purchase_orders:manage` | Crear, editar, enviar a aprobación y cancelar órdenes de compra |
| purchase_orders | `purchase_orders:approve` | Aprobar órdenes de compra |
| purchase_orders | `purchase_orders:send` | Enviar órdenes de compra aprobadas |
| purchases | `purchases:read` | Ver compras y recepciones |
| purchases | `purchases:manage` | Crear, editar y cancelar borradores de recepción |
| purchases | `purchases:receive` | Confirmar recepciones de órdenes de compra |
| purchases | `purchases:verify` | Verificar y cerrar recepciones de compra |
| retaceos | `retaceos:read` | Ver retaceos y costos landed |
| retaceos | `retaceos:manage` | Crear, editar y cancelar retaceos |
| retaceos | `retaceos:calculate` | Calcular distribución de costos de retaceo |
| retaceos | `retaceos:verify` | Verificar y cerrar retaceos |
| audit | `audit_log:read` | Read audit log |
| auth | `auth:refresh` | Refresh tokens (system-granted) |

> Codes are seeded by a dedicated migration. Adding a new permission = adding a
> row + (optionally) a UI entry in the matrix.

## 3. Effective permissions

A user's effective permissions = **union** of permissions across all their
roles. Exposed at `GET /api/v1/me/permissions` for the frontend to render
conditionally. The backend NEVER trusts this for authorisation — it recomputes
on each request inside `require_permission(...)`.

## 4. Base roles (seeded)

| Role | `is_system` | Permissions |
|------|-------------|-------------|
| `SUPER_ADMIN` | yes | all |
| `ADMINISTRADOR` | no | users, employees, roles management |
| `RECURSOS_HUMANOS` | no | employees, departments |
| `EMPLEADO` | no | self-service only (read own profile) |

System roles (`is_system = true`) cannot be deleted and cannot lose their
critical permissions. The last `SUPER_ADMIN` user-role assignment cannot be
removed (business rule, tested).

## 5. Backend enforcement (Phase 2 API)

```python
@router.post("/users", dependencies=[Depends(require_permission("users:create"))])
async def create_user(...): ...
```

`require_permission(code)` is a dependency factory that:
1. Resolves the current authenticated user (Phase 1).
2. Computes effective permissions (cached in Redis when available).
3. Raises `AuthorizationError` (HTTP 403) if `code` is not present.
4. Logs an `ACCESS_DENIED` audit event if the user was authenticated but
   lacked the permission.

## 6. Frontend integration

- After login, fetch `/me/permissions` and store in a Svelte store.
- Sidebar items declare `requiredPermission`; items without a match are hidden
  (or rendered disabled — design decision documented in Phase 5).
- Buttons/links to protected actions are hidden when the permission is missing,
  but the backend remains the source of truth.

## 7. Path to ABAC (future)

The `conditions JSONB` column on `role_permissions` (added in Phase 2, unused)
is the extension point. Example future condition:

```json
{ "own_department_only": true }
```

A future `evaluate_conditions(user, resource, conditions)` function will be
composed with `require_permission` to support attribute-based rules without
schema changes.
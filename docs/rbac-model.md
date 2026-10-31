# RBAC Model

> **Versión:** `v1.0.0` | **Última actualización:** `20/10/2026`
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
| purchase_requests | `purchase_requests:create` | Crear, editar y enviar solicitudes propias |
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

## 8. Branch scope for the company headquarters (ERS-B01)

`is_headquarters` is an organizational marker, not an access grant. A user's
company membership and assigned branch IDs remain authoritative. Access to the
headquarters branch grants access to resources assigned to that branch,
including the central warehouse. It does not set `access_all_branches` or grant
access to other stores. Company-wide users retain access to both the matrix and
stores.

Central purchase orders and receipts are authorized through their persisted
warehouse assignment. Legacy central documents keep `branch_id = NULL`; routes
resolve their effective branch through `warehouse_id` and require membership in
that branch. Branch-filtered lists include such documents only when the filter
is the matrix linked to the central warehouse. An inconsistent document/bodega
assignment or a central warehouse without an active matrix is rejected.

## 9. Transfer engine authorization (ERS-B03 / revision 0086)

The transfer API reuses `inventory:read`, `inventory:move` and
`inventory:receive`; revision `0086` adds no permission code. Creating,
editing, cancelling and dispatching require the move permission plus access to
the origin warehouse/branch. Creating or changing vehicles additionally
requires access to headquarters. Receiving requires the receive permission and
the destination branch/warehouse. A receiver assigned only to the destination
can receive the specifically authorized transfer without company-wide branch
access; transfer detail reads are scoped to the caller's origin or destination.

Incident reporting/resolution is authorized through the relevant origin
movement or destination receipt scope. Company ownership, warehouse branch,
vehicle and location relationships are independently validated in the service
and persistence layer. Permission checks also apply to idempotent replays, so a
stored response is not a way to bypass a later authorization change. The legacy
generic movement route remains usable for unrelated operations but cannot
write into a registered vehicle transit location; new transit movement must
use the transfer document and its state machine.

## 10. Inventory adjustment authorization (ERS-B05 / revision 0087)

`inventory:adjust` permits creating/editing drafts, managing their draft
evidence, cancelling before application and requesting a supported correction.
`inventory:adjust_approve` permits approval and application. Both permissions
are company-scoped and are checked in addition to `inventory:read`, which is
the route/module gate. The same user may create, approve and apply when that
user has both permissions; no separation of duties is imposed.

Every operation independently checks the active company and the adjustment's
warehouse branch. Transfer-loss adjustments additionally require the linked
open incident, transfer detail and transit handling unit, plus the relevant
logistics scope; the technical transit warehouse is not exposed as general
branch access. Replays repeat permission and scope checks. The generic
movement endpoint rejects public `adjustment_in`/`adjustment_out` writes.

`inventory:valuation` remains separate from adjustment permissions. Adjustment
read models redact documented costs when this permission is absent. Evidence
download requires `inventory:read`, `inventory:valuation`, the active company
and warehouse scope, and an active link from the exact adjustment to the
document. A caller cannot download by guessing an asset ID. Each new request
rechecks permission and scope. An already issued short-lived signed URL is a
bearer capability and is not retroactively revoked when a link is detached or
scope changes; the storage expiry policy bounds it. The focused E2E test covers
cost redaction, denied upload/complete/detach/download, allowed URL issuance,
unlinked ID, wrong branch/company, detach and scope revocation. Its URL service
is stubbed, so it does not verify bytes, storage scanning or URL expiry; see
[`test_adjustment_evidence_download_requires_valuation_permission`](../backend/tests/e2e/test_inventory_adjustment_permissions.py)
and [the command/output log](../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log).
Revision `0087` inserts the two new permission codes and grants them to the
system `SUPER_ADMIN` role. Other roles receive them only through explicit role
configuration.

## 11. Sales authorization (ERS-B06–B07 / revisions 0088–0089)

Revision `0088` adds these company-scoped permissions and assigns them to the
system `SUPER_ADMIN` role. Other roles must receive each permission explicitly.

| Permission | Responsibility |
| --- | --- |
| `sales_customers:read` | Read company customers. |
| `sales_customers:manage` | Create, update and deactivate customers. |
| `sales_quotations:read` | Read quotations after branch-scope validation. |
| `sales_quotations:manage` | Read sellable catalog options; create/update quotation drafts. |
| `sales_quotations:confirm` | Confirm or cancel an eligible quotation. |
| `sales_quotations:convert` | Convert a confirmed quotation to one sale draft. |
| `sales:read` | Read/list sales after branch-scope validation. |
| `sales:manage` | Edit sale drafts. |
| `sales:confirm` | Confirm a sale draft. |
| `sales:cancel` | Cancel a sale with a required reason. |
| `sales_deliveries:read` | Read delivery documents and assignments after company/branch checks. |
| `sales_deliveries:manage` | Read eligible delivery stock; create or edit delivery drafts. |
| `sales_deliveries:confirm` | Confirm a draft and post its physical/valued shipment. |
| `sales_deliveries:cancel` | Cancel an unposted delivery draft with a reason. |

Customer reads/writes are restricted to the active company. Every quotation
and sale list, detail, mutation and command additionally validates the
document's branch against the caller's branch assignments. Permission and
scope checks run before an idempotent replay is returned. No purchase or
inventory-movement permission authorizes a sales command. Costs and margins
are not included in sales DTOs. B07 delivery reads, options, mutations and
idempotent replays validate company and sale-branch scope. The sale branch
determines eligible outbound HUs; a user does not gain access to another
branch's sale by having a global company selector. Delivery permissions are
granted to system `SUPER_ADMIN` by revision `0089`; other roles need an explicit
grant. Reading or confirming deliveries does not require the
inventory-valuation permission, and applied cost amounts remain private to the
server and the B08 return linkage.

Revision `0090` adds five separate return permissions:

| Permission | Capability |
| --- | --- |
| `sales_returns:read` | List/read returns and their visible origin, evidence and events within company/branch scope. |
| `sales_returns:manage` | Read returnable allocations and create return drafts. |
| `sales_returns:receive` | Register return receipt for review without changing stock. |
| `sales_returns:resolve` | Accept/reject quantities; accepted stock requires an authorized destination. |
| `sales_returns:cancel` | Cancel an eligible draft with a reason. |

The permissions are granted to the system `SUPER_ADMIN` by migration 0090;
other roles require explicit grants. Return detail, evidence access and
idempotent replays revalidate active-company and branch access. Cost amounts
remain server-side; responses include traceability IDs and quantities only.
See the B08 endpoint table in `docs/api.md` and
`tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md` for the
verification actually performed.

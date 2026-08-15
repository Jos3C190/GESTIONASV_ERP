# API Reference

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  
> Interactive docs at `/docs` (Swagger) and `/redoc` when running in non-production mode.

## 1. Base URL

| Environment | Base URL |
|-------------|----------|
| Local dev (compose) | `http://localhost:8000` |
| Prod (Nginx) | `https://<your-domain>/api` (reverse-proxied) |

## 2. Endpoints

### Health (no auth)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | App name + status |
| `GET` | `/health/live` | Liveness probe (no I/O) |
| `GET` | `/health/ready` | Readiness probe (DB check) |
| `GET` | `/health` | Full health report |

### Auth
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `POST` | `/api/v1/auth/login` | public (rate-limited 10/min) | Login, returns access+refresh tokens |
| `POST` | `/api/v1/auth/refresh` | public (rate-limited 30/min) | Rotate refresh token (reuse detection) |
| `POST` | `/api/v1/auth/logout` | authenticated | Revoke refresh token |
| `GET` | `/api/v1/auth/me` | authenticated | Current user profile |
| `GET` | `/api/v1/auth/me/permissions` | authenticated | Effective permissions |

### Users (require_permission)
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/users` | `users:read` | List users (paginated, search) |
| `GET` | `/api/v1/users/{id}` | `users:read` | Get user by id |
| `POST` | `/api/v1/users` | `users:create` | Create user |
| `PATCH` | `/api/v1/users/{id}` | `users:update` | Update user (active/superadmin) |
| `POST` | `/api/v1/users/{id}/force-password-reset` | `users:force_password_reset` | Force password reset |
| `POST` | `/api/v1/users/{id}/unlock` | `users:unlock` | Unlock account |
| `DELETE` | `/api/v1/users/{id}` | `users:deactivate` | Deactivate (soft delete) |

### Roles & Permissions (require_permission)
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/roles` | `roles:read` | List roles (with permissions) |
| `GET` | `/api/v1/roles/permissions` | `permissions:read` | Permission catalogue |
| `GET` | `/api/v1/roles/{id}` | `roles:read` | Get role by id |
| `POST` | `/api/v1/roles` | `roles:create` | Create role |
| `PATCH` | `/api/v1/roles/{id}` | `roles:update` | Update role |
| `DELETE` | `/api/v1/roles/{id}` | `roles:delete` | Delete role (non-system) |
| `PUT` | `/api/v1/roles/{id}/permissions` | `permissions:manage` | Set role permissions (matrix) |
| `POST` | `/api/v1/roles/assign` | `roles:assign` | Assign role to user |
| `POST` | `/api/v1/roles/revoke` | `roles:revoke` | Revoke role from user |
| `GET` | `/api/v1/roles/users/{id}/roles` | `roles:read` | Roles assigned to a user |

### Employees (require_permission)
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/employees` | `employees:read` | List employees (paginated, search, filters) |
| `GET` | `/api/v1/employees/{id}` | `employees:read` | Get employee by id |
| `POST` | `/api/v1/employees` | `employees:create` | Create employee |
| `PATCH` | `/api/v1/employees/{id}` | `employees:update` | Update employee |
| `DELETE` | `/api/v1/employees/{id}` | `employees:delete` | Delete employee (soft) |
| `POST` | `/api/v1/employees/{id}/link-user` | `employees:update` | Link employee to user account |
| `POST` | `/api/v1/employees/{id}/unlink-user` | `employees:update` | Unlink user account |

### Departments (require_permission)
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/departments` | `employees:read` | List departments |
| `GET` | `/api/v1/departments/{id}` | `employees:read` | Get department by id |
| `POST` | `/api/v1/departments` | `departments:manage` | Create department |
| `PATCH` | `/api/v1/departments/{id}` | `departments:manage` | Update department |
| `DELETE` | `/api/v1/departments/{id}` | `departments:manage` | Delete department (if empty) |

### Suppliers and contacts (require_permission)
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/suppliers` | `suppliers:read` | List suppliers; includes a lightweight logo projection when available |
| `GET` | `/api/v1/suppliers/{id}` | `suppliers:read` | Get supplier, complete logo and contact avatars |
| `POST` | `/api/v1/suppliers` | `suppliers:manage` + `suppliers:images` (when `image` is sent) | Create supplier with optional primary logo |
| `PUT` | `/api/v1/suppliers/{id}` | `suppliers:manage` + `suppliers:images` (when `image` is present) | Update supplier; omitted `image` preserves it, `null` removes it |
| `POST` | `/api/v1/suppliers/{id}/contacts` | `suppliers:manage` + `suppliers:images` (when `image` is sent) | Add contact with optional avatar |
| `PUT` | `/api/v1/suppliers/contacts/{id}` | `suppliers:manage` + `suppliers:images` (when `image` is present) | Update contact; omitted `image` preserves it, `null` removes it |

Image objects use `source_type=cloudinary` with a previously confirmed asset
(`media_asset_id`) or `source_type=external` with an HTTPS URL. Local uploads
also require `media.upload`; external URLs are rendered by the browser and are
never fetched by the API.

### International supplier master data

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/currencies` | `suppliers:read` | Active ISO-4217 currency catalogue |
| `GET/POST` | `/api/v1/supplier-groups` | `suppliers:read` / `suppliers:manage` | Company-scoped supplier groups |
| `PATCH/DELETE` | `/api/v1/supplier-groups/{id}` | `suppliers:manage` | Maintain a supplier group |
| `GET/POST/PATCH` | `/api/v1/payment-terms[/{id}]` | `suppliers:read` / `suppliers:manage` | Company-scoped payment terms |
| `GET/POST/PATCH/DELETE` | `/api/v1/suppliers/{id}/tax-identifiers[/{tax_id}]` | `suppliers:read` / `suppliers:tax_identifiers` | Optional country/type fiscal identifiers |
| `GET/POST/PATCH/DELETE` | `/api/v1/suppliers/{id}/addresses[/{address_id}]` | `suppliers:read` / `suppliers:addresses` | Multiple typed supplier addresses |
| `GET/POST/PATCH/DELETE` | `/api/v1/suppliers/{id}/bank-accounts[/{account_id}]` | `suppliers:bank_accounts` | Encrypted accounts, masked responses only |

`POST/PUT /suppliers` accepts optional `legal_name`, `supplier_group_id`,
`supplier_status`, hold fields, `default_currency_code`, `payment_terms_id`,
`default_payment_method` and `external_reference`. Omitting an existing
optional field on update preserves it. Tax identifiers accept arbitrary
country-specific types; the API never requires NIT, NRC or VAT.

### Audit Log (read-only)
| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/audit-logs` | `audit_log:read` | List audit entries (cursor pagination, filters) |

## 3. Conventions

- **Auth**: `Authorization: Bearer <access_token>`. Refresh token as httpOnly
  Secure SameSite=Strict cookie on `/api/v1/auth` path.
- **Errors**: `{ "code": "...", "message": "..." }` with HTTP status. Generic
  client messages; details in server logs only.
- **Pagination**: `?page=1&size=20` for catalogues; `?cursor=...&limit=50`
  for audit log (keyset over `created_at DESC, id DESC`).
- **IDs**: all UUIDs.
- **Rate limiting**: login 10/min, refresh 30/min, reset 5/min per IP.

## 4. Security headers (applied)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Content-Security-Policy`: conservative default
- `Strict-Transport-Security` (production only)

## 5. CORS
Origins from `CORS_ORIGINS` env. Credentials allowed. `*` never used with credentials.

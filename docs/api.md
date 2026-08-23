# API Reference

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  
> Interactive docs at `/docs` (Swagger) and `/redoc` when running in non-production mode.

## 1. Base URL

| Environment | Base URL |
|-------------|----------|
| Local dev (compose) | `http://localhost:8000` |
| Prod (Nginx) | `https://<your-domain>/api` (reverse-proxied) |

## 2. Endpoints

### Product families and variants

`POST` and `PUT /api/v1/catalog/products` accept the optional `variant_config`
object with up to five attributes and 500 variants. Sending it is protected by
`products:variants`; variant images additionally require `products:images` and
local Cloudinary uploads require `media.upload`. Omitting it on update preserves
the existing family configuration. `variants` is a sparse declaration: it does
not need to contain the full Cartesian product of attribute values. This allows
business combinations such as `Rojo/S` and `Azul/M` without creating
unsupported combinations. On a replacement, an existing variant omitted from
the declaration is retired (never physically deleted), so clients should show
an explicit confirmation before saving that change.

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/catalog/products/{id}/variants` | `products:read` | List family variants |
| `GET` | `/api/v1/catalog/products/{id}/variants/{variant_id}` | `products:read` | Get one variant |
| `PATCH` | `/api/v1/catalog/products/{id}/variants/{variant_id}` | field-dependent | Edit SKU, name, status, identifiers or image without changing the combination |
| `POST` | `/api/v1/catalog/products/{id}/variants/preview` | `products:variants` | Validate and preview a complete or sparse combination set |
| `PUT` | `/api/v1/catalog/products/{id}/variant-config` | `products:variants` | Replace declared attributes and variants atomically |

The product detail includes complete family attributes, variants, identifiers
and primary variant images. Product lists expose only `variant_mode` and
`variant_count`.

Products and variants may each own multiple identifiers. `GET /api/v1/catalog/products/{id}`
returns the product's own `identifiers`; variant responses return only the identifiers
of that variant. Each identifier has a stable `identifier_type`, readable `value`,
`is_primary` and `is_active`. SKU, original code and internal code remain separate
catalog fields. EAN/UPC/GTIN/ISBN values are validated before saving; the frontend
may render a compatible barcode format (EAN-8/EAN-13, UPC-A, ITF-14 or Code 128)
and falls back to text for unsupported or historical values.

### Large-catalogue filters and distribution

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/catalog/category-options?q=&page=1&size=50` | `products:read` | Bounded, company-scoped category lookup for filters |
| `GET` | `/api/v1/catalog/sub-category-options?category_id=&q=&page=1&size=50` | `products:read` | Bounded subcategory lookup; `category_id` is optional for global search |
| `GET` | `/api/v1/catalog/products/distribution` | `products:read` | Server-side category/subcategory aggregates following the active product filters |

Option lookups return only `{id, label, parent_id}` plus standard pagination
metadata. The frontend never downloads the complete category catalogue to
populate a dropdown. Distribution returns at most six named groups plus
non-filterable `Otros`/`Sin subcategoría` buckets, so chart payloads remain
bounded for companies with thousands of categories.

The individual `PATCH` is sparse: omitted fields are preserved; `name_override: null`,
`identifiers: []` and `image: null` explicitly clear those values. It requires
`expected_updated_at` and returns `409 variant_stale` when the row changed after
it was loaded. The attribute combination is intentionally immutable in this
endpoint; structural changes belong in the family manager. General variant
fields require `products:variants`, identifiers require `products:identifiers`,
and images require `products:images` (plus `media.upload` only for local uploads).

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

### Products and measurements (require_permission)

`POST` and `PUT /api/v1/catalog/products` accept structured physical
measurements: `dimension_length`, `dimension_width`, `dimension_height`,
`dimension_unit`, `weight` and `weight_unit`. Dimension units are fixed to
`mm`, `cm`, `m`, `in`, `ft`; weight units are fixed to `mg`, `g`, `kg`, `t`,
`oz`, `lb`. They are independent of the configurable purchase/sale `units`
catalogue. `size` remains free text. `dimensions` is response-only legacy
compatibility and is not a writable field.

The product response includes `dimension_summary`, `volume` and `volume_unit`.
Volume is read-only, expressed in m³, and is `null` until all three dimensions
are present. Omitting measurement fields on update preserves them; sending
`null` clears the corresponding measurement.

`GET /api/v1/catalog/products/{id}` also returns the optional `category_name`
when the referenced category belongs to the same company as the product. The
numeric `id_category` remains the authoritative relationship; `category_name`
is left `null` only when the name cannot be resolved within that company.

The product detail also enriches each `supplier_links` entry with the optional
`supplier_name`, resolved from the commercial supplier record in the same
company. `supplier_id` remains the stable relationship identifier, and
`supplier_name` is `null` for historical relations whose supplier is no longer
visible. The field is additive and does not change supplier permissions or
create an extra supplier request in the frontend.

### Variant detail and inventory summary

The read-only variant detail page uses the existing variant resource together
with the inventory identity associated with that variant:

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/catalog/products/{id}/variants/{variant_id}` | `products:read` | Variant SKU, attributes, identifiers, image and lifecycle |
| `GET` | `/api/v1/inventory/items/by-target?variant_id={variant_id}` | `inventory:read` | Resolve the inventory identity without mixing it with the parent template |
| `GET` | `/api/v1/inventory/items/{item_id}/packaging` | `inventory:read` | Read versioned packaging and physical measures |
| `GET` | `/api/v1/inventory/items/{item_id}/summary` | `inventory:read` | Global stock totals for the variant across all warehouses |

The inventory summary reports quantity by stock status, active handling-unit
counts, warehouse/location/lot counts, and physical totals. Weight and volume
are `null` whenever an active handling unit for the variant is incomplete; the
API never converts an unknown physical measure into zero. Closed handling units
are excluded from active totals. If no inventory identity exists, the client
shows an empty state instead of treating the variant as stocked.

The catalogue detail endpoint remains read-only. SKU, lifecycle, identifiers
and image changes continue through the field-specific `PATCH` endpoint, and
the UI keeps the edit route separate from the detail route.

### Deferred product API scope

The API does not expose purchase orders, landed-cost allocation, price lists,
fiscal accounting rules or compliance documents yet. Variant master data and
the global inventory summary are available, while purchasing, sales and
pricing endpoints that consume `variant_id` remain deferred
until their consuming modules exist. The dependency and acceptance matrix is
documented in [`docs/product-module-future-debt.txt`](product-module-future-debt.txt).

### Product master and sourcing

`POST`/`PUT /api/v1/catalog/products` accept the product kind/lifecycle,
commercial names and descriptions, keywords, origin, brand/manufacturer and
storage/handling fields. They may also receive an `identifiers` array when the
caller has `products:identifiers`; an empty array clears product-owned
identifiers without touching variant identifiers. Services cannot carry
physical storage data, and `is_active` remains a compatibility projection of
lifecycle status.

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `GET/POST/PATCH/DELETE` | `/api/v1/catalog/brands[/{id}]` | `products:read` / `products:master_data` | Company-scoped brands |
| `GET/POST/PATCH/DELETE` | `/api/v1/catalog/manufacturers[/{id}]` | `products:read` / `products:master_data` | Company-scoped manufacturers |
| `GET/POST/PATCH/DELETE` | `/api/v1/catalog/products/{id}/identifiers[/{identifier_id}]` | `products:read` / `products:identifiers` | Product identifiers |
| `GET/POST/PATCH/DELETE` | `/api/v1/catalog/products/{id}/suppliers[/{relation_id}]` | `products:read` / `products:suppliers` | Current supplier sourcing links |
| `PUT` | `/api/v1/catalog/products/{id}/suppliers` | `products:suppliers` | Replace the complete sourcing set atomically from the product editor |
| `GET` | `/api/v1/suppliers/{id}/products` | `suppliers:read` | Products sourced from a supplier |

The product list remains lightweight; detail responses include structured
identifiers and supplier links. Costs are not exposed in catalogue rows.

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

### Warehouse, location and inventory capacity (0039–0040)

Warehouse and location create/update endpoints accept certified and operational
limits for `weight_kg` and `usable_volume_m3`, plus `capacity_profile`,
`capacity_enforcement_mode`, `storage_eligible` and optional usable dimensions.
There is no pallet-capacity field or generic `capacity` alias.

`GET /api/v1/warehouses/{warehouse_id}/locations` accepts the additive query
parameters `capacity_group_id`, `include_descendants` (default `true`) and
`unassigned`. A structure filter returns direct assignments plus all visible
descendant structures; `unassigned=true` returns only locations directly under
the warehouse and cannot be combined with `capacity_group_id`. Invalid
combinations return `location_filter_conflict`; a structure from another
warehouse or a deleted structure returns `location_capacity_group_not_found`.
`GET /api/v1/warehouses/{warehouse_id}/locations/{location_id}` returns one
location for the warehouse and requires `locations.view`; the warehouse scope is
checked before the location is returned, so an ID from another warehouse is not
disclosed.
`GET /api/v1/warehouses/{warehouse_id}/capacity-groups` adds
`direct_location_count` and `subtree_location_count`; these are assignment
counts, not occupied inventory or available capacity.

Enforcement modes are `disabled`, `observe` and `enforce`. Responses keep the
operational state separate from a derived `capacity_status`. Inventory capacity
summaries return occupied, reserved, projected, available and utilisation values
for weight and volume independently. A missing measurement is returned as
unknown/incomplete, never as numeric zero.

For a location summary, the additive `scope_path` field lists the location,
each structural ancestor and the warehouse. Every entry contains its own weight
and volume metrics and measurement state. `limiting_scope` identifies the most
utilised applicable scope; ties prefer the most specific scope. It is `null`
when any applicable scope has incomplete measurements.

The summary status can be `not_configured`, `incomplete`, `available`,
`warning`, `critical`, `full`, `over_operational` or `over_certified`.
`over_certified` is a hard safety alarm and takes precedence over an active
operational override and the generic `full` state.

Packaging definitions are versioned per inventory item and unit of measure.
Movement writes require an idempotency key, persist immutable lines and update
balances atomically. Receiving with incomplete physical measures is restricted
to quarantine. Reservations expire, can be cancelled or consumed, and remain in
the projected load until their terminal transition. Operational overrides
require their own permission, reason and expiration; certified limits never
accept an override.

`GET /api/v1/warehouses/{warehouse_id}/capacity-configuration-diagnostics`
requires `warehouses.view`. It returns configuration-only issues and never
inventory quantities. Codes include `parent_limit_not_configured`,
`nominal_capacity_overallocated` and historical
`capacity_child_limit_exceeds_parent` inconsistencies. Nominal overallocation
is diagnostic only.

Capacity and hierarchy writes retain the standard `{ "code", "message" }`
error contract. Stable conflict codes are
`capacity_child_limit_exceeds_parent`,
`capacity_limit_below_projected_usage`, `capacity_usage_incomplete`,
`capacity_group_reparent_exceeds_target` and
`capacity_group_has_active_assignments`. New configurations are validated
immediately; historical inconsistencies remain readable and appear in
diagnostics, while unrelated metadata edits are not blocked.

## 4. Security headers (applied)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Content-Security-Policy`: conservative default
- `Strict-Transport-Security` (production only)

## 5. CORS
Origins from `CORS_ORIGINS` env. Credentials allowed. `*` never used with credentials.

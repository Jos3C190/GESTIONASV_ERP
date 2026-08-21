# Architecture

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  
> Architecture and design contracts for the modular ERP monorepo.

## 1. Overview

ERP System is a modular enterprise resource planning boilerplate. The repository
is a **monorepo** with two deployable units and one stateful service:

```
erp-system/
├── backend/      FastAPI (async) — Python 3.12
├── frontend/     SvelteKit 5 (TypeScript strict) — Svelte 5 runes
└── (compose)     PostgreSQL 16, optional Redis, optional Nginx (prod)
```

## 2. Backend — Clean / Hexagonal layering

### 2.4 Catalog variants boundary

Product families and variants are a catalog bounded context. The parent product
owns inherited master data and supplier relations; each variant owns only its
SKU, canonical attribute combination, lifecycle, identifiers and one primary
image. The repository reserves SKUs and synchronizes the family graph in one
transaction. The family graph supports sparse combinations: the catalog can
declare only the combinations the business actually offers, while preserving
omitted historical variants as retired for traceability. Inventory now consumes
`variant_id` through an exclusive inventory identity, balances and handling
units; purchase, sales, price and replenishment behavior remains deferred until
those contexts consume the identifier.

Individual variant maintenance is deliberately separate from the family
manager. `PATCH /variants/{variant_id}` locks the parent and variant in a
stable order, applies a sparse update under optimistic concurrency, and never
accepts attribute/value assignments. SKU, identifiers, lifecycle and image
changes are audited independently; changing a combination requires a new
family combination plus retirement of the old identity.

```
Presentation (api/v1) ──► Application (use cases) ──► Domain (entities, ports)
                                  ▲
                          Infrastructure (db, repos, external)
```

### 2.1 Direction of dependencies (enforced)

| Layer            | May import                                       | May NOT import |
|------------------|--------------------------------------------------|----------------|
| `domain/`        | stdlib only                                      | FastAPI, SQLAlchemy, Pydantic, infrastructure |
| `application/`   | `domain/` (ports), stdlib                        | FastAPI, SQLAlchemy, infrastructure |
| `infrastructure/`| `domain/` (ports), `core/`, SQLAlchemy, etc.     | `api/`, `application/` |
| `api/v1/`        | `application/`, `core/`, `infrastructure/db` (session only) | concrete repositories beyond session wiring |
| `core/`          | stdlib + 3rd-party cross-cutting (config, logging, security) | any layer above |
| `middlewares/`   | `core/`                                          | domain/application/infrastructure |

### 2.2 Key patterns

- **Repository + Unit of Work** for persistence. Repos are port interfaces in
  `domain/ports/` and concrete implementations in `infrastructure/repositories/`.
- **Use cases** in `application/` are small async classes with `execute(...)`.
  They depend on ports, not on concrete repos.
- **FastAPI `Depends()`** is the only DI mechanism. Providers live in
  `api/v1/deps.py`. Tests override a single dependency to swap a real repo for
  an in-memory fake.
- **DTOs (Pydantic v2)** in `api/v1/schemas/` are intentionally separate from
  ORM models in `infrastructure/models/`. Routers never return ORM models.

### 2.3 Cross-cutting concerns

| Concern         | Location |
|-----------------|----------|
| Configuration   | `app/core/config.py` (pydantic-settings, env-driven) |
| Logging         | `app/core/logging.py` (structlog: dev=console, prod=JSON) |
| Security primitives | `app/core/security.py` (Argon2id, constant-time compare) |
| Error hierarchy | `app/core/exceptions.py` → mapped by `api/v1/exception_handlers.py` |
| Security headers | `app/middlewares/security_headers.py` |
| Request context + access log | `app/middlewares/request_context.py` |
| CORS            | `app/main.py` (origins from settings, never `*` with credentials) |
| Rate limiting   | *(planned Phase 1)* slowapi or Redis-backed middleware |
| Audit hook      | *(planned Phase 4)* middleware + use-case integration |

## 3. Frontend — feature-sliced

```
src/
├── routes/             thin route files only (SvelteKit file-based routing)
├── lib/
│   ├── api/            centralised client (refresh interceptor: Phase 1)
│   ├── components/ui/  design system (Button, Card, ThemeToggle, ...)
│   ├── features/       feature modules (auth, users, employees, roles, audit-log)  *(planned)*
│   ├── stores/         global state (theme, session, permissions)
│   ├── types/          shared TypeScript types
│   └── utils/          pure helpers
```

Rules:

- `routes/*.svelte` import from `lib/features/<feature>` and `lib/components/ui`
  only. No business logic in route files.
- `lib/features/<feature>` groups that feature's components, hooks, types and
  API calls. Features do not import from each other except via well-defined
  shared utilities.
- `lib/components/ui` is business-agnostic and reusable across features.

## 4. Request lifecycle (Phase 0)

```
Client ─► CORS ─► RequestContext (request_id, access log) ─► SecurityHeaders
       ─► Router ─► Dependency providers (SessionDep) ─► Use case
       ─► (exception handler if AppError) ─► JSONResponse
```

## 5. Deployment topologies

- **Development** (`compose.yaml`): `db` + `backend` (hot reload) + `frontend`
  (Vite dev server). Schema upgrades are an explicit operator step; startup
  migration remains opt-in only for disposable environments.
- **Production** (`compose.prod.yaml`, `--profile prod`): multi-stage images,
  non-root users, no dev tools, Nginx in front as reverse proxy. TLS is
  terminated upstream (configurable). `/docs` and `/redoc` disabled.
- **Optional Redis** (`--profile redis`): used from Phase 1+ for rate limiting,
  token revocation list, permission cache.

## 6. OWASP mapping (final state)

| OWASP Top 10 (2021) | Mitigation | Status |
|---|---|---|
| A01 Broken Access Control | `require_permission(...)` dependency on every sensitive endpoint, deny-by-default, superuser shortcut, 403 tests per endpoint | ✅ |
| A02 Cryptographic Failures | Argon2id, JWT secrets from env, short access TTL (15min), refresh rotation with reuse detection | ✅ |
| A03 Injection | SQLAlchemy parameterised queries only, Pydantic input validation on every endpoint | ✅ |
| A04 Insecure Design | Abuse-case tests (brute force lockout, self-deactivate blocked, last-superadmin protected, cycle detection in dept hierarchy) | ✅ |
| A05 Security Misconfiguration | Security headers (CSP, X-Frame-Options, HSTS in prod), restricted CORS, debug off in prod, generic error messages | ✅ |
| A06 Vulnerable Components | Pinned versions in pyproject/package.json, `pip-audit`/`pnpm audit` documented | ✅ |
| A07 Identification & Auth Failures | Rate limiting (10/min login, 30/min refresh), progressive lockout (5 attempts → backoff), refresh rotation with reuse detection → revoke all sessions | ✅ |
| A08 Software & Data Integrity Failures | Audit log append-only (no UPDATE/DELETE endpoints, repo only exposes add+list), AuditService never raises | ✅ |
| A09 Logging & Monitoring Failures | Structured logs (structlog, JSON in prod), audit log captures security events (login success/failure, IP, user agent), no secret logging (mask_token helper) | ✅ |
| A10 SSRF | N/A in current scope; documented policy: no outbound calls to user-supplied URLs. Future integrations (email/storage) must validate and whitelist destinations. | ✅ (N/A) |

## 7. ADRs (Architecture Decision Records, short form)

### ADR-001 — UUID primary keys
**Decision:** All entities use UUID (server-side `gen_random_uuid()`), not
autoincrement int. **Rationale:** prevents resource enumeration, eases future
sharding/federation, safe to expose in URLs. **Consequences:** slightly larger
indexes; sort order is not insertion order (use `created_at` for ordering).

### ADR-002 — Async-only data access
**Decision:** Backend uses async SQLAlchemy (`AsyncSession`, `asyncpg`) end to
end; sync access only inside Alembic offline mode. **Rationale:** FastAPI is
async-native; mixing sync DB calls would block the event loop. **Consequences:**
test code must be async; some third-party libs that require sync sessions are
unsuitable.

### ADR-003 — Explicit migration step
**Decision:** development and production deployments run `alembic upgrade
head` as an explicit one-shot operator/CI step; `RUN_MIGRATIONS_ON_STARTUP`
defaults to false in Compose. **Rationale:** a hot reload must never turn a
newly created revision file into an implicit database write. **Consequences:**
local setup and deployments must migrate before starting or promoting the API;
production should use a Job/InitContainer with backup and readiness checks.

Product image galleries follow the same explicit migration policy. Revision
0031 creates a product-owned relational gallery; the API claims staged
Cloudinary assets transactionally and never performs server-side requests to
external HTTPS image URLs.

Supplier logos and contact avatars use the same media boundary with revision
0032. They are one-to-one relational attachments, use persistent owner UUIDs,
and are edited inside the existing supplier/contact modals. Their API accepts
either a claimed Cloudinary asset or an HTTPS reference without making
server-side requests to the external host.

Supplier master data in revision `0033` keeps tax identifiers, addresses,
payment terms and bank accounts in separate aggregates. Fiscal identifiers are
country/type/value records rather than El Salvador-specific columns. Bank
secrets cross the application boundary only as plaintext request values, are
immediately AES-GCM encrypted with the deployment key, and leave the API as
masked last-four projections. The supplier list deliberately projects no bank
data and the detailed response is permission-filtered.

Product physical measurements in revision `0034` are deliberately independent
from the commercial unit catalogue. The domain owns a small fixed set of SI
and imperial dimension/weight codes, validates them again at the API and
database boundaries, and computes volume in m³ only when length, width and
height are all present. This keeps purchase/sale units configurable without
making physical dimensions ambiguous or silently mixing business concepts.

The product catalogue list is designed for high-cardinality tenants. Product
rows remain server-paginated; category and subcategory filters use company-
scoped searchable option endpoints with bounded pages instead of loading every
option into the browser. Distribution charts aggregate in PostgreSQL and
return only leading groups plus informational remainder buckets. Chart
failures are isolated from the product table, and asynchronous selections are
guarded against stale responses.

### ADR-005 — Deferred product-domain capabilities

The product master remains a stable reference aggregate. Inventory balances,
purchase transactions, retaceo, price assignment, packaging conversions,
variants, fiscal accounting and compliance documents are separate bounded
capabilities and are not represented by placeholder columns. Each capability
must arrive with its own transaction model, permissions, audit events,
tenant-scoped constraints and consuming UI. The activation gates and future
debt register live in `docs/product-module-future-debt.txt`.

### ADR-006 — Product master and procurement reference data

Revisions `0035` and `0036` add stable product reference data before inventory
and purchasing transactions exist. Lifecycle, names, descriptions, keywords,
storage constraints, identifiers and current supplier terms are useful to
catalogue, receiving preparation and future purchasing without pretending that
stock or price history already exists. Supplier links use company-composite
foreign keys and row locks for preferred-supplier changes. Historical price
curves, MOQ conversions and replenishment rules remain deferred until their
consuming modules exist.

### ADR-004 — No FOUC for theme
**Decision:** Theme is applied by an inline blocking script in `app.html`
before Svelte hydrates. **Rationale:** avoids the dark-mode flash. The script
is tiny and does not itself introduce XSS (no user input is read).
**Consequences:** CSP allows inline scripts in dev only; production tightens
this with a nonce strategy once auth is wired (Phase 1).

### ADR-007 — Physical capacity is not stock

Revisions `0039` and `0040` separate approved physical limits from transactional
inventory. Warehouses, structural groups and storage locations expose certified
and operational limits in canonical kilograms and usable cubic metres. No pallet
shape, container type or product count is assumed. A certified limit is a hard
safety boundary; an operational limit is the lower day-to-day boundary and may
only be exceeded by an authorised, expiring and audited exception.

Inventory consumption comes from versioned packaging definitions or actual
receiving measurements. The immutable movement ledger updates materialised
balances and lightweight handling units in the same transaction. Capacity is
evaluated as `occupied + active reservations`, independently for weight and
volume, under deterministic `Warehouse -> structural group -> Location` locks.
The largest known percentage is a summary indicator only; both metrics remain
visible, and missing measurements never become zero.

Storage, transit and virtual locations are distinguished explicitly. Only a
storage-eligible scope participates in normal capacity enforcement. Operational
state (`active`, `maintenance`, `inactive`) is independent from derived capacity
state (`not_configured`, `incomplete`, `available`, `warning`, `critical`,
`full`, `over_operational`, `over_certified`). A known certified-limit breach
is reported as `over_certified` ahead of any operational override or generic
full state because no operational authorisation can relax that safety boundary.

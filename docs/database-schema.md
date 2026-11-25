# Database Schema

## Product families and variants (0037)

The catalog keeps the current product as the family parent. `products.variant_mode`
is `standalone` for regular products and becomes `template` when the first
variant is created. Family attributes and allowed values live in
`product_family_attributes` and `product_family_attribute_values`; variants,
their canonical combinations and lifecycle are stored in `product_variants`.
`product_variant_attribute_values` enforces one value per attribute. A variant
may have one primary image in `product_variant_images`.

`product_sku_registry` reserves SKUs across products and variants within a
company. `product_identifiers` now targets exactly one product or variant, so
EAN/UPC/GTIN uniqueness cannot be bypassed by moving between tables. Existing
products are not backfilled into families. The migration is fail-closed on
downgrade when variant data exists.

Variants are catalog identity only in this revision. Inventory, purchasing,
sales, pricing, lot and serial tables must reference `variant_id` only when
those bounded contexts are implemented.

> **Versión:** `v1.0.0` | **Última actualización:** `19/10/2026`
> Complete schema design and conventions for PostgreSQL 16.

## 1. Conventions

- **Primary keys:** `UUID` (server-side `gen_random_uuid()`). No int autoincrement.
- **Timestamps:** `TIMESTAMPTZ` everywhere. `created_at` and `updated_at` on every
  entity; `deleted_at` for soft-delete on business entities.
- **Soft delete:** `users`, `employees`, `departments` use `deleted_at`. Hard
  delete is reserved for junction rows where history is captured elsewhere.
- **Naming:** snake_case tables and columns; constraints get stable names via
  Alembic autogenerate + manual review.
- **Audit log:** append-only (`INSERT` only); no `UPDATE`/`DELETE` API surface.

## 2. Phase 0 — current schema (Mermaid)

```mermaid
erDiagram
  app_meta {
    text key PK
    text value
    timestamptz updated_at
  }
```

`app_meta` holds key/value markers (e.g. `schema_phase = 0`) and exists so
migrations are wired end-to-end and verifiable.

## 3.1 Explicit headquarters and company central warehouse (0084)

`branches.is_headquarters` identifies the company's administrative receiving
and distribution branch. A partial unique index
`uq_branches_company_active_headquarters` allows at most one active matrix per
company. The matrix may reuse the company's registered address and geography;
its coordinates can remain `NULL` because an administrative address does not
establish a physical warehouse location.

Every warehouse has an assigned branch after migration 0084. The former
company-level central warehouse keeps its existing `id`, location rows, stock,
handling units, movements and document references; only its `branch_id` is
associated with the company's matrix. `uq_warehouses_company_active_central`
retains one active central warehouse per company without inferring its role from
a missing branch. A database trigger rejects a central warehouse assigned to
another company's branch or a non-active/non-matrix branch and prevents
deactivating its matrix while the link remains.

Alembic 0084 preflights duplicate active central warehouses, unresolved
unassigned non-central warehouses and required company address/geography before
writing. It logs a company-to-matrix-to-central-warehouse map in the migration
log. DDL and row mapping execute transactionally. Downgrade restores the prior
branchless representation for central warehouses and removes the explicit
marker; it deliberately preserves any generated administrative branch so
organization data is not deleted. The read-only
`backend/scripts/preview_headquarters_migration.py` prints the proposed mapping
only after confirming the exact database name supplied by the operator.

## 3. Target schema (Phases 1–4)

```mermaid
erDiagram
  users ||--o{ user_roles : has
  roles ||--o{ user_roles : assigned_to
  roles ||--o{ role_permissions : grants
  permissions ||--o{ role_permissions : granted_by
  users ||--o{ refresh_tokens : owns
  users ||--o{ audit_logs : performs
  users ||--o| employees : is
  employees }o--|| departments : belongs_to
  departments }o--o| departments : parent_of
  users ||--o{ password_reset_tokens : requests

  users {
    uuid id PK
    varchar username UK
    varchar email UK
    text password_hash
    bool is_active
    bool is_superuser
    bool mfa_enabled
    timestamptz last_login_at
    int failed_login_attempts
    timestamptz locked_until
    timestamptz created_at
    timestamptz updated_at
    timestamptz deleted_at
  }

  employees {
    uuid id PK
    uuid user_id FK "nullable"
    varchar employee_code UK
    varchar first_name
    varchar last_name
    varchar document_id
    date birth_date
    varchar phone
    text address
    uuid department_id FK
    varchar position
    date hire_date
    date termination_date
    status status
    text photo_url
    timestamptz created_at
    timestamptz updated_at
    timestamptz deleted_at
  }

  departments {
    uuid id PK
    varchar name
    text description
    uuid parent_department_id FK "self-ref, no cycles"
  }

  roles {
    uuid id PK
    varchar name UK
    text description
    bool is_system
    timestamptz created_at
    timestamptz updated_at
  }

  permissions {
    uuid id PK
    varchar code UK "format: recurso:accion"
    text description
    varchar module
  }

  role_permissions {
    uuid role_id PK,FK
    uuid permission_id PK,FK
  }

  user_roles {
    uuid user_id PK,FK
    uuid role_id PK,FK
    uuid assigned_by FK
    timestamptz assigned_at
  }

  refresh_tokens {
    uuid id PK
    uuid user_id FK
    text token_hash
    text user_agent
    inet ip_address
    timestamptz expires_at
    timestamptz revoked_at
    timestamptz created_at
  }

  audit_logs {
    uuid id PK
    uuid user_id FK "nullable"
    varchar action
    varchar resource_type
    uuid resource_id
    jsonb before_state
    jsonb after_state
    inet ip_address
    text user_agent
    status status
    jsonb metadata
    timestamptz created_at
  }

  password_reset_tokens {
    uuid id PK
    uuid user_id FK
    text token_hash
    timestamptz expires_at
    timestamptz used_at
  }
```

## 4. Indexes (target)

| Table | Column(s) | Type |
|-------|-----------|------|
| `users` | `email` | unique, btree |
| `users` | `username` | unique, btree |
| `employees` | `employee_code` | unique, btree |
| `audit_logs` | `created_at` | btree (DESC, for cursor pagination) |
| `audit_logs` | `user_id` | btree |
| `audit_logs` | `(resource_type, resource_id)` | composite btree |
| `refresh_tokens` | `token_hash` | unique, btree |
| `refresh_tokens` | `(user_id, revoked_at)` | partial where `revoked_at IS NULL` |

## 5. Migration policy

- One Alembic revision per logical change. Revisions are reversible
  (`downgrade()` implemented and tested).
- `compare_type` and `compare_server_default` are enabled so autogenerate
  catches type drift.
- Migrations are an explicit one-shot deployment step (see ADR-003 in
  `architecture.md`). The API startup hook remains opt-in for disposable
  environments only; ordinary development and production set
  `RUN_MIGRATIONS_ON_STARTUP=false`.
- `create_all()` is **dev/test only**; production always uses Alembic.

## 6. Warehouse location integrity (revision 0030)

Revision `0030` makes two application invariants enforceable by PostgreSQL:

- `code_scheme_id` and `scheme_version` are either both null (legacy code) or
  both present, in both `locations` and `location_code_aliases`. The existing
  composite foreign keys then validate the exact warehouse-scoped scheme
  version.
- A location is retired if and only if `is_active` is false. Every non-retired
  lifecycle state (`draft`, `active`, blocked variants, or `maintenance`) stays
  active in the persistence model.

The migration runs read-only preflight checks before creating constraints and
aborts without repairing data when it finds an inconsistent row. Operators
must resolve those rows deliberately, rerun the preflight, and only then
promote the migration. Its downgrade drops only the three checks and does not
rewrite business data or permissions.

## 7. Product image galleries (revision 0031)

Revision `0031` adds the normalized `product_images` table. Each product can
have up to 20 ordered images and exactly one cover when the gallery is
non-empty. Cloudinary images reference a staged/active `media_assets` row owned
by the same company; external images are stored as HTTPS references only. The
backend never fetches external image URLs.

The gallery stores `source_type`, URL, optional accessible `alt_text`,
zero-based `position`, and `is_cover`. Product list responses project only
`cover_image` and `image_count`; individual product responses include the
complete ordered gallery. Removed Cloudinary assets are marked `detached` for
the existing cleanup process.

## 8. Supplier and supplier-contact primary images (revision 0032)

Revision `0032` adds one normalized primary image relation for each supplier
and supplier contact. `supplier_images` stores the supplier logo and
`supplier_contact_images` stores the contact avatar. Both tables validate
Cloudinary/external source parity, enforce one relation per owner, and retain
accessible alternative text without storing binary content. Existing supplier
contacts receive a persistent UUID so staged Cloudinary assets can be claimed
with the same owner isolation used by other media flows.

External images are HTTPS references rendered directly by the browser; the API
never downloads or probes those URLs. Cloudinary assets must be staged/active,
belong to the current company, and have the purpose matching the relation.
Removed assets are marked `detached` for the existing cleanup process.

## 9. International supplier master data (revision 0033)

`suppliers.name` remains the commercial name and `suppliers.address` remains a
legacy compatibility field. Revision `0033` adds optional legal identity,
company-scoped supplier groups, workflow status/hold dates, currency, payment
terms, payment method and an external reference. Existing suppliers are
backfilled only to `supplier_status = approved`; no tax or legal values are
invented.

Fiscal identifiers live in `supplier_tax_identifiers` and are generic
(`country_id`, `identifier_type`, `value`) so an El Salvador supplier may use
NIT/NRC while an international supplier may use VAT, EIN, RFC or any local
identifier. They are optional, repeatable and normalized for duplicate
detection; only one may be primary per country.

`supplier_groups`, `currencies`, `payment_terms` and `supplier_addresses` are
normalized catalogues/relations. Existing non-empty legacy addresses are copied
to one primary `other` address without deleting the original column.

`supplier_bank_accounts` stores only AES-GCM ciphertext and the last four
digits. The encryption key is supplied by `SUPPLIER_DATA_ENCRYPTION_KEY` from
the deployment secret manager; APIs never return or audit full account numbers,
IBANs, ciphertext or keys. The 0033 downgrade refuses to run while supplier
master data, addresses, banking records or custom catalog rows exist.

## 10. Product measurements (revision 0034)

Revision `0034` normalizes physical product measurements without changing the
commercial `units` catalogue used by purchase and sale units. Products now
store optional `dimension_length`, `dimension_width`, `dimension_height`,
`dimension_unit`, `weight` and `weight_unit` values. Dimension units are the
fixed codes `mm`, `cm`, `m`, `in` and `ft`; weight units are `mg`, `g`, `kg`,
`t`, `oz` and `lb`. PostgreSQL checks reject negative values, unsupported
codes, and measurements without their paired unit.

The former free-text `dimensions` column remains for API compatibility. During
the migration, unambiguous strings such as `20 x 30 x 10 cm` are backfilled
into structured columns; ambiguous values remain in `dimensions_legacy` and
are never discarded. New writes use only structured fields. Volume is derived
at read time in cubic metres from all three dimensions and is never stored as
a user-editable value.

## 11. Product-domain transactional boundaries

Inventory identity, versioned packaging conversions, lightweight handling units,
lots, expiry, movements, balances and capacity reservations are implemented by
revision `0040`.

The purchasing document flow and the current Retaceo landed-cost allocation are
also implemented, but remain separate transactional capabilities from the
physical-capacity model. Price history, replenishment policies, serial tracking
and broader regulatory compatibility remain separate concerns.

### Purchasing flow migrations

The implemented purchasing and Retaceo flow is represented by these Alembic
revisions:

- `0044_purchase_requests.py`
- `0045_reconcile_purchase_request_permissions.py`
- `0048_purchase_quotations.py`
- `0049_reconcile_purchase_quotation_permissions.py`
- `0050_purchase_orders.py`
- `0051_reconcile_purchase_order_permissions.py`
- `0052_purchase_order_expense_documents.py`
- `0053_purchase_order_detail_traceability.py`
- `0054_purchases.py`
- `0055_reconcile_purchase_permissions.py`
- `0056_retaceos.py`
- `0057_purchase_receipt_inventory_link.py`
- `0058_expense_type_management.py`
- `0059_inventory_packaging_purchase_unit.py`
- `0060_retaceo_itemized_costs.py`
- `0061_retaceo_cost_document_soft_delete.py`
- `0062_purchase_demand_consolidations.py`
- `0063_purchase_request_create_permission.py`
- `0064_purchase_consolidation_event_uuid_default.py`
- `0065_purchase_quotation_rfq_versions.py`
- `0066_purchase_quotation_documents.py`
- `0067_purchase_consolidation_awards.py`
- `0068_purchase_quotation_document_detach.py`
- `0069_purchase_order_consolidation_award_link.py`
- `0070_purchase_consolidation_branch_demand_level.py`
- `0071_branch_product_demand_levels.py`
- `0072_central_warehouse_designation.py`
- `0073_company_level_mother_warehouse.py`
- `0074_branchless_central_purchases.py`
- `0075_transfer_handling_unit_splits.py`
- `0076_purchase_consolidation_close.py`
- `0077_purchase_consolidation_quotation_outcomes.py`
- `0078_inventory_movement_actor_history.py`
- `0079_inventory_valuation.py`
- `0080_inventory_receipt_lots.py`
- `0081_inventory_label_prints.py`
- `0082_inventory_trace_capabilities.py`
- `0083_inventory_label_confirmation_and_receipt_origin.py`
- `0084_explicit_headquarters_branch.py`
- `0085_receipt_detail_lot_identity.py`
- `0095_retaceo_manual_components.py`
- `0098_retaceo_calculation_mode.py` (columns removed again by `0117`)
- `0117_retaceo_fixed_amounts_without_vat.py`

### Purchasing flow tables

The main tables introduced for the purchasing and Retaceo flow are:

- `purchase_requests`
- `purchase_request_details`
- `purchase_quotations`
- `purchase_quotation_requests`
- `purchase_quotation_request_details`
- `purchase_quotation_details`
- `purchase_quotation_line_snapshots`
- `purchase_quotation_documents`
  - `deleted_at` registra cuándo se desvinculó un archivo sin borrar la evidencia de auditoría.
- `purchase_quotation_expenses`
- `purchase_consolidations`
- `purchase_consolidation_lines`
- `purchase_consolidation_sources`
- `purchase_consolidation_events`
- `expense_types`
- `purchase_orders`
- `purchase_order_details`
- `purchase_order_expenses`
- `purchase_order_expense_documents`
- `purchases`
- `purchase_details`
- `retaceos`
- `retaceo_details`

### Purchasing line traceability

The purchasing flow preserves exact line-level traceability across each
transactional stage:

```text
Purchase Request Detail
    -> Purchase Quotation Request Detail
    -> Purchase Quotation Detail
    -> Purchase Order Detail
    -> Purchase Detail
    -> Retaceo Detail
```

The persisted references that maintain this chain are:

- `purchase_quotation_request_details.purchase_request_detail_id`
- `purchase_quotation_request_details.purchase_quotation_detail_id`
- `purchase_order_details.purchase_quotation_detail_id`
- `purchase_details.purchase_order_detail_id`
- `retaceo_details.purchase_detail_id`

These foreign-key relationships preserve company-scoped ownership and prevent
the transactional documents from losing the exact source line that originated
each downstream detail.

Revision `0065` links supplier RFQs to a purchase consolidation and stores a
version number per supplier. `purchase_quotation_details.offered_quantity`
holds the supplier's offer separately from the immutable requested quantity.
`purchase_quotation_line_snapshots` preserves the copied product labels,
branch/central quantities and source-request breakdown for each RFQ version.
Revision `0066` links company-scoped, security-scanned document assets to a
purchase quotation so the original supplier offer can be retained and downloaded
without storing file contents in the purchasing tables.

## 13. Physical capacity and inventory (revisions 0039–0040)

Revision `0039` removes ambiguous pallet/generic capacity from the forward
schema. Warehouses and storage locations store certified and operational limits
for kilograms and usable cubic metres, a capacity profile, enforcement mode,
storage eligibility and optional usable dimensions. Structural groups represent
shared rack, bay, level, floor or cold-room constraints; location maximums are
not summed to infer structural strength.

Revision `0040` adds inventory identities for standalone products or variants,
versioned packaging definitions, non-nested handling units, immutable movement
headers and lines, materialised balances, expiring capacity reservations and
temporary operational overrides. Movement lines preserve packaging and physical
measurement snapshots so later master-data changes do not rewrite history.

Capacity uses canonical units and computes `projected = occupied + reserved` at
the location, warehouse and applicable structural groups. PostgreSQL constraints
enforce positive limits, operational-at-or-below-certified boundaries, valid
state catalogues and composite item/override references. Company ownership of
locations is resolved through warehouse and branch and is also checked by every
inventory application command. Unknown measurements remain
explicit; they do not contribute a fabricated zero and normal receipt is blocked
until the stock is measured or placed in controlled quarantine.

## 14. Document storage and OCR (revisions 0041–0042)

`document_assets` stores tenant-scoped metadata for immutable private objects. It records the
normalized display name, declared and detected MIME, size, SHA-256, private bucket/key, ETag,
scan state and audited soft-delete fields. The supported states are `pending_upload`,
`pending_scan`, `scanning`, `active`, `quarantined` and `rejected`; only `active` is downloadable.
The unique `(bucket, object_key)` constraint and company/status/date indexes support safe lookup,
maintenance and retention without exposing storage coordinates through the API.

`document_derivatives` records immutable generated objects without changing the canonical
document. Revision `0042` initially supports one `ocr_pdf` per document with states `pending`,
`processing`, `ready`, `failed` and `skipped`; it stores size, SHA-256, ETag, attempts, failure
code and processing timestamps. The unique `(document_id, kind)` constraint makes creation
idempotent, while company/status/date indexes support tenant isolation, reconciliation and stale
job recovery. PostgreSQL—not Redis—is the durable source of processing state.

## 12. Product master enrichment (revisions 0035–0036)

Revisions `0035` and `0036` extend the product master without embedding
transactional inventory or purchasing balances in the catalogue row. Products now have an explicit kind
(`goods` or `service`), lifecycle (`draft`, `active`, `blocked`,
`discontinued`, `retired`), purchase/sale flags, commercial and internal names,
separate descriptions, keywords, origin country, company-scoped brand and
manufacturer references, and physical storage/handling rules. `is_active` is
kept for compatibility and is constrained to match the lifecycle.

`product_brands` and `product_manufacturers` are company-scoped catalogs with
composite tenant-safe foreign keys. Physical storage fields are only valid for
goods; temperature is expressed in Celsius and ranges are checked in the
database.

`product_identifiers` stores optional EAN/UPC/GTIN/ISBN, manufacturer, internal
and generic identifiers. Values are normalized for uniqueness, and only one
primary identifier is allowed per product/type. `product_suppliers` stores the
current sourcing relationship (cost, currency, MOQ, multiple, lead time,
preferred flag and validity), with company-composite foreign keys, one active
preferred supplier per product and constraints for approved suppliers. Price
history, purchasing documents and inventory conversions remain deferred.

## 15. Consolidated purchase awards (revision 0067)

`purchase_consolidation_awards` stores each manual allocation from one
consolidation product line to a specific supplier quotation detail. Quantity,
actor and required reason are decision data; reversals set the reversal
timestamp, actor and reason rather than deleting the award. Composite foreign
keys keep the consolidation, line, quote, quote detail and supplier in the same
company. The line/active and quote-detail/active indexes support remaining
demand calculations. Consolidation event history records both award and
reversal actions. Aggregate limits (not exceeding remaining demand or offer)
are checked transactionally while the consolidation header is locked.

## 16. Receipt lots, label prints and public trace links (revisions 0080–0082)

Revision `0080` adds `inventory_lots` and `inventory_lot_details`, linking each
verified purchase receipt to accepted quantities by inventory item. Handling
units reference the receipt lot; their inventory item and base quantity are
matched to its accepted details when placement and trace data are assembled.

Revision `0081` adds append-only `inventory_label_prints`. It records the
company, receipt lot/detail or handling unit, idempotency key, print count and
date, initial/reprint reason, actor, and a snapshot of the printed label. It
does not change inventory balances.

Revision `0082` adds `inventory_trace_capabilities`, a company-scoped,
revocable bearer link for public read-only traceability of one handling unit.
Only a unique SHA-256 token digest is persisted; the plaintext token is
returned at issuance and placed in the QR URL fragment. The capability has
created/revoked actor references, timestamp fields, and a composite foreign key
to the unit in the same company. The public response is an API allowlist, not a
direct serialization of the internal trace model.

## 17. Canonical receipt-detail identity (revision 0085)

`inventory_lot_details.code` is the stable lot identity for one product line
accepted on one purchase receipt. The code is derived from the existing receipt
header code and immutable detail UUID; it is unique within a company. Separate
details, including separate partial receipts for the same product, retain
different codes and their original `purchase_detail_id`.

`inventory_movement_lines.inventory_lot_detail_id` is a nullable,
company-composite FK for new physical movements. The column remains nullable so
pre-0085 immutable ledger rows are not rewritten. Read models can resolve those
older rows through the exact handling unit's `inventory_lot_detail_id`; rows
without that evidence remain unlinked legacy history. This is a read-time
compatibility mapping, not a second editable stock balance. `inventory_lots`
remains the receipt header and its prior code is a search alias that can resolve
to several detail codes.

The 0085 migration adds identity and relationship schema only. It does not
create label-print or label-confirmation events and does not change receipt
quantities, handling units, balances, movement entries or valuation. The ERS
mapping is functional; the existing physical schema does not claim that every
teaching-diagram table is implemented under the same name.

## 18. Transfer documents and mobile vehicle stock (revision 0086)

Revision `0086` adds one technical transit warehouse per company and marks it
`is_transit`; its `vehicle` locations are bound to company-scoped rows in
`inventory_vehicles`. Technical transit warehouses are excluded from ordinary
storage eligibility and shelf-capacity calculations but remain in global
physical reconciliation and company/product valuation.

`inventory_transfers` is the document header. `inventory_transfer_details`
records the product, canonical receipt-detail lot, source handling unit,
planned/dispatched/received/returned quantities and any manual-excess reason.
`inventory_transfer_demand_allocations` links a line to a purchase-request
detail without creating a second stock reservation. `inventory_transfer_commands`
stores action-scoped idempotency keys and response snapshots. Each partial
receipt is separately recorded in `inventory_transfer_receipts`, linked to its
command, movement and resulting destination handling unit. Open/resolved
incidents and their reason/evidence/resolution are retained in
`inventory_transfer_incidents`.

Company-composite foreign keys and transactional quantity checks protect
cross-company references and prevent received/returned quantity from exceeding
dispatch. Dispatch and receipt invoke existing inventory movements; they do not
edit historic entries or create a second valuation balance. Revision `0086`
does not backfill old generic transfer movements into documents or invent
vehicles for legacy stock. No transfer return command is exposed in this block;
the returned-quantity field is reserved for a later explicitly authorized
return path.

## 19. Authorized inventory adjustments and transfer losses (revision 0087)

`inventory_adjustments` stores the company-scoped document code, warehouse,
operational/accounting dates, reason, document reference, lifecycle/version,
correction link, optional transfer/incident link, actors, idempotency data and
application snapshot. Its lifecycle is `draft`, `approved`, `applied` or
`cancelled`; the approved version must equal the current version. Company-safe
foreign keys bind the warehouse, correction origin, transfer, incident and
actors.

`inventory_adjustment_details` stores ordered lines with item, warehouse,
location, stock status, direction, positive base quantity, optional canonical
receipt-detail lot/handling unit/packaging, documented cost, physical measures,
transfer detail and movement references. Compound foreign keys prevent using
another company's item, lot, location, unit, transfer detail or movement.
Positive lines can only enter quarantine and record either documented unit or
total cost. Negative lines must identify an existing handling unit and cannot
inject a cost.

`inventory_adjustment_documents` pins the file asset ID, company, SHA-256,
filename, linker and timestamps. Detaching a draft support is a timestamped
event in the row; the file itself is not deleted. `inventory_adjustment_events`
is append-only and records actor, action, time, reason and document version.
Database triggers prevent updates/deletes of applied headers/details and event
mutation, and prevent deleting or changing a file asset linked to an approved
or applied adjustment.

Revision `0087` adds `quantity_adjusted_out` (default zero) to
`inventory_transfer_details` and `inventory_transfer_demand_allocations`, and
extends their checks so received, returned and adjusted-out quantities cannot
exceed dispatched/allocated quantities. Transfer state `closed_with_adjustment`
and the idempotent `resolve_adjustment` command distinguish a documented loss
from an actual receipt. Existing rows start at zero; revision `0087` does not
rewrite legacy movements or cost averages.

## 20. Sales base without delivery (revision 0088)

Revision `0088` adds six company-scoped tables for the commercial flow:

- `sales_customers` stores code, name, optional phone/email, active flag and
  creator/updater. A case-insensitive unique index enforces customer code per
  company. Deactivation retains the row and existing documents.
- `sales_quotations` stores branch, customer, code, quotation/validity dates,
  USD currency, server-calculated totals, lifecycle/version, notes and
  confirmation/cancellation actors and timestamps. Composite foreign keys
  bind company, branch, customer and users. Checks constrain status,
  dates/version, totals and transition metadata.
- `sales_quotation_lines` snapshots product/variant/inventory-item identity,
  packaging definition and version, commercial/base units and names, factor,
  quantity in each unit, SKU/product label, explicit unit price and rounded
  line total. Composite foreign keys keep catalog references in the same
  company; positive quantity/factor and nonnegative price checks apply.
- `sales` stores one draft/confirmed/cancelled sale for a quotation, with
  company, branch, customer, document code, USD totals, version, notes and
  actor/timestamp/reason history. `uq_sales_source_quotation` prevents a
  second sale from the same origin even when conversion uses a different
  idempotency key.
- `sales_lines` copies the source quotation-line ID and its commercial and
  packaging snapshots. A unique source-line constraint and company-safe FKs
  protect the origin and line identity. Triggers make quotation and sale lines
  insertable/editable/deletable only while their parent remains a draft.
- `sales_idempotency_commands` stores action, company, key, request
  fingerprint, resource type/ID, actor and creation time. A unique
  company/action/key constraint protects retries.

Amounts use `numeric(18,6)` for unit prices and quantities, `numeric(18,2)`
for persisted totals. The service uses Decimal and rounds each line to cents
with `ROUND_HALF_UP`, then sums those rounded lines. USD is the only accepted
currency. At revision 0088, no B06 commercial operation wrote inventory. B07
adds delivery movements and valuation entries; delivered/pending quantities
are now derived from confirmed delivery lines rather than written by clients.

Revision `0088` inserts ten sales permissions and assigns them to the system
`SUPER_ADMIN` role. It creates new tables and constraints only; it does not
backfill customers, quotations, sales or alter pre-existing inventory rows.
The backup, isolated restore rehearsal and pre/post inventory fingerprints
are recorded in `tmp/ers-v1/bloque-06/evidencia-2026-10-19.md`.

## 21. Sales delivery and fulfillment (revision 0089)

Revision `0089` adds four company-scoped tables and a composite source-line
identity:

- `sales_deliveries` is the draft/confirmed/cancelled header. It stores sale,
  company, delivery branch, code, expected-version counter, notes, actors and
  transition timestamps/reason. Composite FKs enforce company and branch
  membership; checks enforce valid state metadata.
- `sales_delivery_lines` links a delivery to one `sales_lines` row and stores
  the item, base quantity, original sale-unit factor, product/SKU names and
  unit snapshots. `(company_id, sale_id, id)` on `sales_lines` permits a
  company-safe composite FK to the exact commercial line.
- `sales_delivery_allocations` links each line to a complete handling unit,
  its inventory item, warehouse/location, canonical lot detail/code, expiry,
  base quantity and packaging snapshot. On confirmation it stores the
  physical `movement_line_id`, `valuation_entry_id`, effective total cost and
  unit cost used for a later B08 return.
- `sales_delivery_commands` stores action, idempotency key and request
  fingerprint, delivery and actor. The company/action/key unique constraint
  protects creation and confirmation retries.

Foreign keys keep the delivery, sale line, HU, location, canonical lot,
movement line, valuation entry, company and actor linked. Check constraints
require positive base quantities and keep cost/movement/valuation links either
all absent on a draft or all present after posting. Triggers reject changes to
confirmed/cancelled headers and reject child mutations unless the header is a
draft. Confirmed delivery is append-only at the document level.

B07 confirmation invokes the existing physical movement and weighted-average
valuation engine in the same transaction as the delivery and success audit.
The average remains shared by company/item across warehouses; the sale branch
only determines eligible physical stock. Public sales delivery DTOs omit
applied cost values while retaining movement/valuation identifiers. The
private allocation cost snapshot is intentionally available to the B08 return
flow. B07 does not backfill historical sales as deliveries or alter prior
inventory rows. Its migration, backup and row-count evidence are in
`tmp/ers-v1/bloque-07/evidencia-2026-10-19.md`.

## 22. Customer returns and review (revision 0090)

Revision `0090` adds five company-scoped tables for B08 and does not rewrite
pre-existing inventory, delivery, valuation or customer data:

- `sales_returns` is the append-only header linked to a sale and branch. It
  records draft, receipt/review/final status, notes, actors and transition
  timestamps. Company-safe FKs protect the sale, branch and actors.
- `sales_return_lines` links each returned quantity to the exact confirmed
  delivery, delivery line, allocation, item, original valuation entry, source
  HU, warehouse/location and canonical lot. It snapshots the visible product,
  unit, lot/expiry and received base quantity.
- `sales_return_events` is an append-only decision history. Accepted and
  rejected quantities, reason, condition, actor and destination are recorded
  separately. Accepted events link the generated physical movement, movement
  line and valuation entry; rejected events cannot carry inventory links.
- `sales_return_commands` stores action-scoped idempotency key, request
  fingerprint, return document and actor. Company/action/key uniqueness
  prevents duplicate create/receive/resolve/cancel commands.
- `sales_return_documents` links optional evidence assets to the return and
  records who attached them. The API verifies company and document access.

Foreign keys preserve the chain back to the confirmed delivery allocation
and its original issue/valuation. The service calculates effective original
issue cost using the valuation entry and allocation snapshot; it does not
substitute the current average or commercial price. Accepted events use the
existing movement/valuation engine in the same transaction. Receipt alone and
rejected events have no stock/value effect. The event and command tables
reject updates/deletes, and final return headers are immutable. Draft lines
may change only while the header is a draft. Migration rehearsal, backup and
row comparison are recorded in
`tmp/ers-v1/bloque-08/aceptacion-integrada/evidencia-2026-10-19.md`.

## 23. Purchase valuation conversion (revision 0091)

Revision `0091` adds nullable JSONB `purchases.valuation_conversion`. Its
documented snapshot contains `currency` (valuation target), `rate` (purchase
currency units per target currency unit), `effective_date` and `reference`.
Decimal rates are serialized as strings to preserve precision. A CHECK
requires object shape, required keys, three-letter target currency, positive
numeric rate and a nonempty reference of 3–500 characters. DTO/domain validation
also limits the rate to less than 10^12 and twelve fractional digits and
validates its date. The gateway matches the target against active company
valuation; it never trusts a source currency supplied by the caller.

No existing row is converted or backfilled. Same-currency receipts retain a
null snapshot. A successful foreign-currency receipt saves the snapshot in the
same transaction as accepted quantities, movement, ledger posting and required
audit. Purchase currency and commercial amounts are retained. Retaceo
application consumes the immutable receipt snapshot and keeps a copy, source
currency and valuation currency in its existing summary. No new exchange-rate
catalog or foreign-exchange gain/loss ledger is introduced.

## 24. Retaceo before receipt and warehouse assignment (0092–0094)

- `0092`: `purchases.inventory_workflow VARCHAR(32) NOT NULL`. Existing rows
  are backfilled `receipt_before_retaceo`; new rows default to
  `retaceo_before_inventory`. A CHECK limits the two policies. Application
  creation explicitly selects the new policy and later updates preserve it.
- `0093`: nullable `retaceos.origin_country VARCHAR(120)`,
  `import_invoice_number VARCHAR(80)`, `import_invoice_date DATE`,
  `import_policy_number VARCHAR(80)`, `import_policy_date DATE`.
- `0094`: `user_companies.warehouse_restricted BOOLEAN NOT NULL DEFAULT false`;
  `user_warehouse_access(user_id, company_id, warehouse_id)` composite primary
  key and composite foreign keys to membership and warehouse/company. Restricted
  memberships without assignments have no warehouse access. Existing unrestricted
  memberships and superusers retain their preceding authorization model.
- `0094` also registers `inventory:warehouse_receipts` idempotently.

No historic valuation entries are rewritten. New receipt entries reuse the
existing `retaceo_id` foreign key. `inventory_retaceo_applications.summary`
records `mode=initial_receipt`, accepted quantities, movement and any documented
conversion. Retaceo `applied_at/by` are populated when the receipt actually posts,
not when its retaceo closes. A fully rejected receipt records the application
without creating a physical movement. Existing costs/attachments and the
append-only ledger retain their existing tables.

These revisions were applied after a full local database backup. Downgrades
refuse to discard in-use workflow, document or warehouse restriction data.
See `docs/ers-v1/retaceo-recepcion-bodega-2026-10-23.md` for the inspected diagram,
actual account provisioning and remaining acceptance work.

## 25. Manual retaceo components and actual spending (0095)

- `retaceos.manual_entry BOOLEAN NOT NULL DEFAULT false`: preserves existing
  record policies; the HTTP create command explicitly sets true for new drafts.
- `retaceo_costs.incurred_on DATE NULL`: date of the documented actual expense.
- `purchase_order_expenses.is_actual BOOLEAN NOT NULL DEFAULT false`,
  `incurred_on DATE NULL`, `reference VARCHAR(240) NULL`: separate actual expense
  log using existing categories, company/order keys and attachment relations.
- `ck_order_actual_expense_documented`: actual rows require nonnull date,
  nonblank description and nonblank reference. Existing budget rows retain their
  original meaning and are the only rows included in commercial budget totals.
- Actual expense usage is derived from active retaceo costs referencing the source;
  no independently mutable reservation counter or duplicated attachment file.
- Downgrade refuses while manual retaceos or actual expenses exist. No migration
  edits existing financial values, quantities or immutable valuation entries.

Applied locally after a full database backup. Storage and legacy correction
simulations were rolled back. COM-00024's confirmed correction is documented in
`docs/ers-v1/com-00024-correccion-documentada-2026-10-27.md`; it has not been posted
as a real retaceo because its actual freight/DAI/VAT must still be captured.

## 26. Transfer transport, partial reception and discrepancies (0116)

Revision `0116` (revises `0115`) adds the transport chosen at preparation, the
`partially_received` and `discrepancy` states, and a single register of
reception differences. It is a database-only description; endpoints are in
`docs/api.md` section 18.

**`inventory_transfers`**

- `ck_inventory_transfers_status` now also accepts `partially_received` and
  `discrepancy`.
- New columns: `approved_vehicle_id` and `approved_driver_id` (copy of the
  transport the approver authorised; compound foreign keys
  `(company_id, approved_vehicle_id)` to `inventory_vehicles` and
  `(company_id, approved_driver_id)` to `drivers`, both `ON DELETE RESTRICT`),
  `assignment_substitution_code`, `assignment_substitution_reason`,
  `assignment_substitution_by_id` (foreign key to `users`, `RESTRICT`),
  `assignment_substitution_at`, and `closed_at timestamptz`.
- `ck_inventory_transfers_assignment_substitution`: the four substitution
  fields are all null or all set; the code is one of `vehicle_unfit`,
  `vehicle_unavailable`, `driver_unfit`, `driver_unavailable`, `load_change`,
  `other`; the trimmed reason has at least 10 characters.
- No check forces vehicle and driver to exist: the route-guard tests insert
  pending transfers without them, and the rule is enforced by the submit and
  approve commands.
- Backfill: `closed_at = COALESCE(received_at, updated_at)` for transfers in
  `received`, `closed_with_adjustment` or `cancelled`; and every `in_transit`
  transfer with some quantity already received becomes `partially_received`.

**Quantities and receipts**

- `inventory_transfer_details`: `quantity_received_damaged` and
  `quantity_surplus` (`numeric(18,6) NOT NULL DEFAULT 0`) with
  `ck_inventory_transfer_details_condition_quantities` (both non-negative and
  damaged not above `quantity_received`). `quantity_received` still counts
  everything physically received.
- `inventory_transfer_demand_allocations`: `quantity_damaged` (default 0) with
  `ck_transfer_demand_allocations_damaged` (between 0 and `quantity_received`).
- `inventory_transfer_receipts`: `condition` (`good` or `damaged`, default
  `good`, `ck_inventory_transfer_receipts_condition`) and
  `uq_inventory_transfer_receipts_company_id (company_id, id)` so discrepancies
  can reference a receipt with a compound key.

**`inventory_transfer_discrepancies`** (new): one row per transfer detail, kind
and event.

| Group | Columns |
| --- | --- |
| Identity | `id`, `company_id`, `transfer_id`, `transfer_detail_id` |
| Classification | `kind` (`shortage`, `surplus`, `damage`), `status` (`open`, `in_claim`, `resolved`, `cancelled`; default `open`), `source` (`receipt`, `reception_close`, `incident`), `quantity` (> 0), `damage_type`, `notes`, `evidence_reference` |
| Links | `location_id`, `handling_unit_id`, `receipt_id`, `command_id`, `incident_id` |
| Opening | `opened_by_id`, `opened_at` |
| Claim | `claim_reference`, `claimed_by_id`, `claimed_at` |
| Resolution | `resolution` (`written_off`, `found`, `released`, `regularized`, `dismissed`), `resolution_notes`, `resolved_by_id`, `resolved_at` |
| Origin count | `origin_count_required` (default false), `origin_counted_by_id`, `origin_counted_at`, `origin_count_notes` |
| Audit | `created_at`, `updated_at` |

- Uniqueness: `uq_inventory_transfer_discrepancies_company_id (company_id, id)`
  and `uq_inventory_transfer_discrepancies_transfer_identity
  (company_id, transfer_id, id)`.
- Foreign keys, all `ON DELETE RESTRICT`: compound `(company_id, transfer_id)`,
  `(company_id, transfer_detail_id)`, `(company_id, handling_unit_id)`,
  `(company_id, receipt_id)`, `(company_id, command_id)` and
  `(company_id, transfer_id, incident_id)` (the incident must belong to the same
  transfer); `location_id` to `locations`; and the four actor columns to
  `users`.
- Checks: valid `kind`, `status` and `source`; `quantity > 0`; trimmed `notes`
  of at least 5 characters; `damage_type` present if and only if `kind` is
  `damage` and one of `broken`, `crushed`, `wet`, `contaminated`, `packaging`,
  `tampered`, `temperature`, `other`; `location_id` required unless the kind is
  `shortage`; resolution valid for the kind (shortage: `written_off`/`found`,
  damage: `written_off`/`released`, surplus: `regularized`/`dismissed`); claim
  fields all set or all null and only for damage; lifecycle coherent with the
  status (`open` has no resolution or claim; `in_claim` is damage with a claim and
  no resolution; `resolved` has resolver data and `written_off`, `released` or
  `regularized`; `cancelled` has resolver data and `found` or `dismissed`);
  origin count fields all set or all null, only when required, and never required
  for damage.
- Indexes: `ix_inventory_transfer_discrepancies_transfer (company_id,
  transfer_id, status)`; the partial unique
  `uq_inventory_transfer_discrepancies_open_shortage (company_id,
  transfer_detail_id) WHERE kind = 'shortage' AND status = 'open'` (one open
  shortage per detail); and the partial
  `ix_inventory_transfer_discrepancies_origin_count (company_id, transfer_id)
  WHERE origin_count_required AND origin_counted_at IS NULL`.

**`inventory_adjustments`**

- New column `transfer_discrepancy_id` with compound foreign keys
  `(company_id, transfer_discrepancy_id)` and
  `(company_id, transfer_id, transfer_discrepancy_id)` to the discrepancy
  (`RESTRICT`).
- `ck_inventory_adjustments_transfer_context` is replaced: either there is no
  transfer link, or `transfer_id` is set with exactly one of
  `transfer_incident_id` and `transfer_discrepancy_id`. Damage and surplus
  adjustments carry only the discrepancy (no `transfer_id`), so the second
  foreign key only applies when both are present.
- `uq_inventory_adjustments_active_discrepancy (company_id,
  transfer_discrepancy_id) WHERE transfer_discrepancy_id IS NOT NULL AND status
  <> 'cancelled'`: one non-cancelled adjustment per discrepancy.

**`inventory_transfer_commands`**: `ck_inventory_transfer_commands_action` adds
`close_reception`, `discrepancy_adjust`, `discrepancy_claim`,
`discrepancy_release`, `discrepancy_found`, `discrepancy_dismiss`,
`resolve_discrepancy` and `origin_count`.

**Downgrade.** It refuses with a `RuntimeError` ("Hay {n} registros de recepción
parcial, discrepancias o sustituciones de transporte que se perderían…") while
there is any discrepancy, any transfer in `discrepancy` or with a substitution,
any detail with damaged or surplus quantity, or any receipt that is not `good`.
Otherwise it returns `partially_received` transfers to `in_transit`, deletes the
new commands, and drops everything added here in reverse order. The model classes
mirror the migration, including `InventoryTransferDiscrepancyModel`, without
`relationship()`.

## 27. Retaceo with fixed amounts and without import VAT (0117)

Revision `0117` (revises `0116`). Landed cost is FOB + freight and insurance +
DAI + additional expenses, all distributed by FOB on the server; import VAT and the
automatic (percentage) mode leave the model.

**Upgrade**

1. `DELETE FROM retaceo_costs WHERE classification = 'import_vat'`. Their
   `retaceo_cost_allocations` and `retaceo_cost_documents` rows go away by
   `ON DELETE CASCADE`. The uploaded files in `document_assets` are not deleted.
   The stored VAT was test data and is lost for good.
2. `ck_retaceo_costs_classification` becomes `classification IN
   ('freight','expense','dai')`.
3. `ck_retaceos_calculation_rates` and `ck_retaceos_calculation_mode` are dropped.
4. `ck_retaceos_amounts_nonnegative` is recreated without `import_vat`;
   `ck_retaceos_total_cost` is unchanged.
5. Columns `retaceos.import_vat`, `vat_rate`, `dai_rate` and `calculation_mode`
   are dropped.

**Downgrade.** Re-adds `calculation_mode VARCHAR(16) NOT NULL DEFAULT 'manual'`,
`dai_rate` and `vat_rate` (`NUMERIC(10,6) NULL`) and `import_vat NUMERIC(18,6) NOT
NULL DEFAULT 0`, and recreates the checks of `0098` and the four-value
classification. Deleted VAT costs, amounts, rates and modes are not restored.

`RetaceoModel` mirrors the migration exactly (tests run with
`-W error::SAWarning`); `manual_entry` is kept. Covered by
`backend/tests/integration/test_retaceo_without_vat_migration.py`.

## 28. Fiscal issuer base (0118)

Revision `0118` (revises `0117`). First block of the sales area (V1a): Hacienda
catalogs and the DTE issuer settings of each company.

**Global data**

- `hacienda_catalog_items` (`catalog_code`, `group_code`, `code`) primary key, with
  `name`, `sort_order`, `catalog_version` and `is_active`. Loaded from
  `app/infrastructure/catalogs/hacienda_dte.py` (catalogs version 1.1, July 2026;
  1,681 codes), which `backend/scripts/generate_hacienda_catalogs.py` builds from the
  official workbook. `group_code` is the department code in CAT-008 and CAT-013,
  whose codes repeat across departments, and the section in CAT-015, where D4 and D5
  appear twice.
- `geographic_departments`, `municipalities` and `districts` gain
  `hacienda_code VARCHAR(2)` (two digits, nullable for rows created outside the
  official catalog), filled for all 14 departments, 44 municipalities and 262
  districts. Unique indexes: department code, and municipality code per department.
  District codes are unique per department (checked by tests, not by an index,
  because districts reference their municipality).

**Per company**

- `company_fiscal_profiles` (1:1 with `companies`, cascade): `taxpayer_category`,
  `person_type`, `operating_mode` (`simulated` by default), `dte_email`, `dte_phone`.
- `company_economic_activities`: `activity_code` (5 or 6 digits, unique per company)
  and `is_primary` (one per company, partial unique index).
- `fiscal_establishments`: one per branch (`UNIQUE (company_id, branch_id)`), `code`
  unique per company and whose letter must match `establishment_type`
  (`ck_fiscal_establishments_code_matches_type`), optional `activity_id` (composite FK
  to the company's activities).
- `fiscal_points_of_sale`: `code` `P` plus three digits, unique per establishment;
  composite FK `(company_id, establishment_id)`.
- `company_dte_document_types`: primary key `(company_id, document_type)`, the 13
  CAT-002 codes, `is_enabled`, `certification_status` and `certified_at`, present if
  and only if the status is `approved`.

Permissions `fiscal_settings:read` and `fiscal_settings:manage` are inserted and
granted to `SUPER_ADMIN`.

**Downgrade** refuses with `RuntimeError` while any profile, activity, establishment
or document setting exists; otherwise it drops everything above. Models live in
`app/infrastructure/models/fiscal.py`. Covered by
`backend/tests/integration/test_fiscal_migration.py`.

## 29. Customers with fiscal identity (0119)

Revision `0119` (revises `0118`). `sales_customers` is extended, not replaced, so
quotations and sales keep their foreign keys. The database guarantees formats and
combinations; whether a customer can receive a tax credit document is computed by the
domain (`app/domain/entities/customer.py`), because a taxpayer may be registered
incomplete and completed later.

**New columns on `sales_customers`**: `customer_type` (`final_consumer` by default,
`taxpayer`, `foreign`), `taxpayer_category` (required only for taxpayers),
`is_withholding_agent`, `person_type`, `commercial_name`, `document_type` and
`document_number` (both or none; CAT-022), `nrc` (2 to 8 digits), `activity_code`
(5 or 6 digits), `department_id`, `municipality_id` and `district_id` (all or none),
`address_line`, `country_code` (present if and only if the customer is foreign, and then
without Salvadoran geography), `credit_days` (0 to 365), `credit_limit` (>= 0),
`seller_employee_id`, `is_generic` and `branch_id` (generic customers: one per branch,
final consumers without document or NRC).

Checks use explicit `IS NOT NULL` where a NULL would otherwise satisfy an `IN (...)`.

**Indexes**: unique `(company_id, branch_id) WHERE is_generic`, unique
`(company_id, document_type, document_number)` and `(company_id, nrc)` when present,
and `(company_id, customer_type, is_active)`.

**`sales_customer_delivery_addresses`**: label, address line, optional geography,
optional coordinates (both or none, within range), contact, phone, `is_default` (one
per customer, partial unique index; must be active) and `is_active`. Composite FK
`(company_id, customer_id)` with `ON DELETE CASCADE`.

**Downgrade** refuses while any delivery address or customer with fiscal data exists.
Covered by `backend/tests/integration/test_customer_migration.py`.

## 30. Product fiscal classification (0120)

Revision `0120` (revises `0119`).

- `products` gains `tax_treatment` (`taxed` by default, `exempt`, `not_subject`),
  `dte_item_type` (nullable, `1`/`2`/`3`; null means derived from `product_kind`) and
  `additional_tax_codes varchar(4)[]` (empty by default). Checks: valid treatment and item
  type, additional taxes only on taxed products, and never IVA `20` or `C3`.
- `company_units` gains `hacienda_unit_code` (one or two digits, nullable). It stays empty
  until the company chooses a code; meanwhile the domain applies the suggestion by unit code
  (UNIT 59, KILOGRAM 34, GRAM 39, POUND 36, LITER 23, MILLILITER 26, GALLON 22, METER 1,
  others 99), so suggested and chosen codes stay distinguishable.
- Permission `products:fiscal` is inserted and granted to `SUPER_ADMIN`.

**Downgrade** refuses while any product is not taxed or has an item type or additional
taxes. Covered by `backend/tests/integration/test_product_fiscal_migration.py`.

## 31. Personal data protection (0121)

Revision `0121` (revises `0120`).

- `company_privacy_notices`: published versions of the company's privacy notice. `version`
  is unique per company, `body` has at least 200 characters and `covered_elements
  varchar(32)[]` records the nine elements of art. 24 confirmed by `published_by`.
  Versions are never edited; a new one is published.
- `customer_consents`: one row per consent of a customer for `marketing`, `profiling` or
  `third_party_sharing`, with the `channel` used, the `notice_id` informed (composite FK to
  the company's notice), who granted it and, when revoked, the revocation date, user and
  channel. A partial unique index allows one active consent per customer and purpose.
- `data_subject_requests`: ARCO-POL requests with `code` (`SOL-00001`), optional
  `customer_id`, requester, `response_channel`, `right_type`, `received_on`, `due_on`,
  `correction_due_on`, `extended_due_on` with its `extension_reason`, `status` (`received`,
  `in_progress`, `awaiting_correction`, `extended`, `resolved`, `denied`, `returned`,
  `archived`), assignee and the closing `resolution`, `closed_at` and `closed_by`. Checks
  keep the extension pair together and the closing fields consistent with the status.
- `personal_data_incidents`: security incidents with `code` (`INC-00001`), discovery and
  occurrence dates, description, data categories, affected count, measures, the
  notifications to ACE, Fiscalía and subjects (timestamp and reference) or the reason the
  subjects are not notified, and `status` `open`/`closed`. A check forbids closing without
  the notifications.
- `sales_customers` gains `anonymized_at`; a check requires an anonymized customer to be
  inactive and not generic.
- Permissions `privacy:read`, `privacy:manage` and `privacy:erase` are inserted and granted
  to `SUPER_ADMIN`.

**Downgrade** refuses while any notice, consent, request, incident or anonymized customer
exists. Covered by `backend/tests/integration/test_privacy_migration.py`.

## 32. Sales price lists (0122)

Revision `0122` (revises `0121`). Enables `btree_gist`.

- `sales_price_lists`: `code` (unique per company, upper case), `name`, `description`,
  `prices_include_vat`, `is_default` (a partial unique index allows one per company; the
  default must be active), `is_active`, authors and timestamps.
- `sales_price_list_items`: one row per price and validity: `price_list_id`, `product_id`,
  `variant_id` (null for products without variants), `unit_id`, `branch_id` (null = all
  branches), `price numeric(19,8)` (≥ 0), `valid_from`, `valid_to` (null = open), author and
  creation time. Composite foreign keys keep the list, product, variant, unit and branch in
  the same company. The exclusion constraint `ex_sales_price_list_items_overlap` (GiST over
  list, product, variant, unit, branch and `daterange(valid_from, valid_to, '[]')`) forbids
  two prices of the same key in force on the same day. Rows are not edited; only `valid_to`
  changes when a newer price closes them, and a scheduled row may be deleted.
- `sales_customers.price_list_id`: optional list of the customer (composite foreign key).
- Permissions `price_lists:read` and `price_lists:manage`, granted to `SUPER_ADMIN`.

**Downgrade** refuses while any price list exists. Covered by
`backend/tests/integration/test_price_lists_migration.py`.

## 33. Sales margins and discounts (0123)

Revision `0123` (revises `0122`).

- `sales_price_lists.target_margin_percent` (0–95, nullable): target margin on the price without
  VAT.
- `sales_price_list_category_margins`: target margin of a product category inside a list
  (unique per list and category; composite foreign keys keep list and category in the company;
  deleted with the list).
- `sales_customers.discount_percent` (0–100, default 0): fixed customer discount.
- `sales_volume_discounts`: volume tiers per list, product, variant, unit and `min_quantity`
  (> 0) with `discount_percent` (> 0, ≤ 100) and validity. The exclusion constraint
  `ex_sales_volume_discounts_overlap` forbids two tiers with the same key and minimum quantity
  in force on the same day.
- `sales_discount_policies`: per company and role, `max_line_discount_percent`,
  `max_global_discount_percent` (0–100) and `can_sell_below_cost` (dropped in 0134).
- Permissions `sales_costs:read` and `sales_discounts:manage`, granted to `SUPER_ADMIN`.

**Downgrade** refuses while any category margin, tier, policy, customer discount or list
target margin exists. Covered by `backend/tests/integration/test_sales_margins_migration.py`.

## 34. Redesigned sales quotation (0124)

Revision `0124` (revises `0123`). The B06 quotation is reworked in place.

- `sales_quotations`:
  - `status` (varchar 24): `draft`, `pending_authorization`, `issued`, `accepted`, `rejected`,
    `cancelled`;
  - `confirmed_at`/`confirmed_by_id` renamed to `issued_at`/`issued_by_id`;
  - new: `document_type` (`01`/`03`), `price_list_id`, `prices_include_vat`,
    `global_discount_percent`, the tax-engine totals (`total_not_subject`, `total_exempt`,
    `total_taxed`, `subtotal_sales`, `total_discount`, `vat`, `vat_perceived`, `vat_withheld`,
    `total_in_words`), `requires_authorization`, `authorization_reasons`, `authorized_by_id`,
    `authorized_at`, `authorization_note`, `customer_response_by_id`, `customer_response_at`,
    `rejection_reason`;
  - checks tie issue, authorization and customer response to the state (accepted/rejected ↔
    response; rejected ↔ reason).
- `sales_quotation_lines`: `unit_price` and `line_total` become numeric(19,8); new
  `price_list_id`, `list_price`, `price_overridden`, `discount_percent`,
  `suggested_discount_percent`, `suggested_discount_source`, `tax_treatment`, `item_type`,
  `document_unit_price`, `discount_amount`, `not_subject`, `exempt`, `taxed`, `vat_item`, `cost`,
  `margin_percent`, `authorization_reasons`. A line without list price must be manual.
- `sales_settings`: per company `quotation_validity_days` (1–365, default 15).
- Permissions `sales_discounts:authorize` and `sales_prices:override`, granted to `SUPER_ADMIN`.

**Upgrade and downgrade** refuse while quotations exist (the downgrade also while settings exist).
Covered by `backend/tests/integration/test_sales_quotation_redesign_migration.py`.

## 35. Sales order (0125)

Revision `0125` (revises `0124`). The B06 sale becomes the sales order in place.

- `sales`:
  - `quotation_id` becomes optional (still unique);
  - `status` (varchar 24): `draft`, `pending_authorization`, `confirmed`, `cancelled`;
  - same fiscal and authorization columns as the quotation (`document_type`, `price_list_id`,
    `prices_include_vat`, `global_discount_percent`, tax totals, `total_in_words`,
    `requires_authorization`, `authorization_reasons`, `authorized_by_id`, `authorized_at`,
    `authorization_note`);
  - delivery: `promised_date`, `delivery_mode` (`pickup`/`delivery`), `delivery_address_id`
    (composite FK to the customer's address) and `delivery_address_text` (copy);
  - payment: `payment_terms` (`cash`/`credit`) and `credit_days` (0–365; 0 for cash).
- `sales_lines`: `source_quotation_line_id` optional, amounts numeric(19,8) and the same pricing
  and tax columns as quotation lines; index `ix_sales_lines_reservation`.
- `sales_customer_delivery_addresses`: unique `(company_id, customer_id, id)` for the FK above.
- The line guards `guard_sales_lines_draft` and `guard_sales_order_lines_draft` read the status
  into varchar(24).

The commercial reservation has no table: it is the pending quantity of confirmed orders.

**Upgrade and downgrade** refuse while sales, deliveries or returns exist. Covered by
`backend/tests/integration/test_sales_order_migration.py`.


## 36. Fiscal document of the order (0126)

Revision `0126` (revises `0125`), block V3b.

- `sales_fiscal_documents`: one row per DTE issued from an order.
  - Keys: `company_id`, `branch_id`, `sale_id` (composite FK to `sales`), `establishment_id` and
    `point_of_sale_id` (composite FKs to `fiscal_establishments` and `fiscal_points_of_sale`),
    `created_by_id` (composite FK to `user_companies`).
  - `document_type` (`01`, `03`), `mode` (`simulated`, `hacienda-test`, `production`) and
    `status` (`pending`, `issued`, `simulated`, `rejected`, `failed`).
  - Identity: `idempotency_key` (unique per company), `generation_code` (unique per company),
    `control_number`; `ck_sales_fiscal_documents_identity` requires both and `issued_at` once
    `issued` or `simulated`, and `ck_sales_fiscal_documents_seal` requires `seal` once `issued`.
  - Content: `total`, `issuer_snapshot` (canonical snapshot plus `snapshotSha256`),
    `request_payload` (body sent to the service), `dte_json`, `service_response`,
    `json_object_key`, `pdf_object_key`.
  - Control: `attempts`, `error_code`, `error_message`, timestamps.
  - `uq_sales_fiscal_documents_active_sale`: one non-failed document per order (partial unique
    index); `ix_sales_fiscal_documents_company_status` for the inbox.
- Permissions `sales_invoices:read` and `sales_invoices:issue`, granted to `SUPER_ADMIN`.

**Downgrade** refuses while fiscal documents exist (they are kept ten years). Covered by
`backend/tests/integration/test_sales_fiscal_documents_migration.py`.


## 37. Fiscal document emails (0127)

Revision `0127` (revises `0126`), block V3c.

- `sales_fiscal_document_emails`: one row per email of a fiscal document.
  - `document_id` (composite FK to `sales_fiscal_documents`), `recipients` (`text[]`, 1–5).
  - `origin` (`auto`, `manual`); `requested_by_id` (composite FK to `user_companies`) is required
    for `manual` and empty for `auto`.
  - `status` (`pending`, `sent`, `failed`); `sent` requires `sent_at` and `message_id`.
  - `attempts`, `error_code`, `error_message`, timestamps.
  - `uq_sales_fiscal_document_emails_auto`: one automatic send per document;
    `ix_sales_fiscal_document_emails_document` for the history and a partial index on pending
    sends for the reconcile job.

**Downgrade** refuses while sends exist. Covered by
`backend/tests/integration/test_sales_fiscal_document_emails_migration.py`.

## 38. Company outgoing email (0128)

Revision `0128` (revises `0127`), block V3c.

- `company_email_settings`: one row per company (`company_id` primary key, cascades with the
  company).
  - Connection: `host`, `port` (1–65535), `security` (`none`, `starttls`, `ssl`), `username`.
  - `password_encrypted` (`bytea`, AES-GCM with a random nonce); requires `username`.
  - Sender: `from_address` (required), `from_name` (optional); `is_enabled`.
  - Last test: `last_test_at`, `last_test_ok`, `last_test_error` (all empty or set together;
    a failed test keeps its error).
  - `updated_by`, timestamps.

**Downgrade** refuses while settings exist. Covered by
`backend/tests/integration/test_company_email_settings_migration.py`.

## 39. Hacienda credentials (0129)

Revision `0129` (revises `0128`), block V3d.

- `company_hacienda_credentials`: one row per company (`company_id` primary key, cascades with
  the company).
  - `api_password_encrypted`, `private_key_password_encrypted` and `certificate_encrypted`
    (`bytea`, AES-GCM with a random nonce).
  - `certificate_sha256` (lowercase hex) and `certificate_nit` (9 or 14 digits).
  - Last connection test: `last_test_at`, `last_test_ok`, `last_test_error` (all empty or set
    together; a failed test keeps its error).
  - `updated_by`, timestamps.

**Downgrade** refuses while credentials exist. Covered by
`backend/tests/integration/test_company_hacienda_credentials_migration.py`.

## 40. Billing contingency (0130)

Revision `0130` (revises `0129`), block V4a.

- `sales_fiscal_documents`:
  - status `contingency` (generated without Hacienda, waiting for the event and its seal);
  - `contingency_type` (CAT-005, 1–5), `contingency_reason` and `contingency_at`. A document in
    `contingency` needs its generation code, control number, `issued_at`, type and time; it keeps
    the type after it is sealed.
- `company_contingency_responsibles`: one row per company (`company_id` primary key, cascades with
  the company): `name` (3–100), `document_type` (CAT-022: 36, 13, 37, 03, 02),
  `document_number` (1–25), `updated_by`, timestamps.
- Permission `sales_invoices:contingency`, granted to `SUPER_ADMIN`.

**Downgrade** refuses while documents generated in contingency exist. Covered by
`backend/tests/integration/test_sales_fiscal_contingency_migration.py`.

## 41. Invalidations and replacements (0131)

Revision `0131` (revises `0130`), block V4b.

- `sales_fiscal_documents`:
  - status `invalidated`;
  - `replaces_document_id` and `superseded_by_id` (composite FKs to the same table; the second is
    `DEFERRABLE INITIALLY DEFERRED` so the original is marked before its replacement is inserted);
  - `uq_sales_fiscal_documents_active_sale` now covers
    `status IN ('pending','contingency','issued','simulated') AND superseded_by_id IS NULL`;
  - `uq_sales_fiscal_documents_replaces`: one live replacement per original.
- `sales_fiscal_invalidations`: `kind` (1 with a replacement, 2 without), `reason`, requester and
  responsible (name and CAT-022 document), `replacement_document_id`, `cancel_order`, `status`
  (`pending`, `accepted`, `rejected`, `failed`), `idempotency_key`, `attempts`, the event's
  generation code and seal, error, `requested_by_id` and timestamps. One pending request per
  document.
- `sales_fiscal_document_emails.invalidation_id`: the customer notice of an accepted
  invalidation (one automatic notice per invalidation).
- Permission `sales_invoices:invalidate`, granted to `SUPER_ADMIN`.

**Downgrade** refuses while invalidations, invalidated or replacement documents, or orders with
more than one non-failed document exist. Covered by
`backend/tests/integration/test_sales_fiscal_invalidations_migration.py`.

## 42. Income-tax classification (0132)

Revision `0132` (revises `0131`), block V4b2.

- `company_economic_activities` and `sales_fiscal_documents` gain `renta_operation_type` and
  `renta_income_type` (`smallint`), both set or both empty, from the F-07 annex catalogues; 12 and
  13 must be equal in both columns (`ck_<table>_renta`).
- The downgrade drops the columns. Covered by
  `backend/tests/integration/test_sales_renta_migration.py`.

## 43. Credit and debit notes (0133)

Revision `0133` (revises `0132`), block V4c.

- `sales_fiscal_documents` accepts `document_type` `05` and `06` and gains `related_document_id`
  (the adjusted CCF, composite FK) and `note_reason` (5–300 characters); both are required exactly
  for notes (`ck_sales_fiscal_documents_note`). `ix_sales_fiscal_documents_related` indexes them.
- `uq_sales_fiscal_documents_active_sale` only covers `01` and `03`: notes live beside the CCF.
- `sales_fiscal_note_lines`: `note_id`, `line_number`, `ccf_line_number` (null for a free charge),
  `kind` (`return` with a quantity, `discount` without one, `charge` with one), `nature`
  (`taxed`, `exempt`, `not_subject`), `description`, `quantity` and `amount` (net, without VAT,
  greater than zero). Vigent credit-note lines give each CCF line its balance.
- Permission `sales_invoices:notes`, granted to `SUPER_ADMIN`.

**Downgrade** refuses while notes exist. Covered by
`backend/tests/integration/test_sales_fiscal_notes_migration.py`.

## 44. Engineer's rules: cost floor, branch promotions, stock exit on confirm (0134–0136)

- **0134**: drops `sales_discount_policies.can_sell_below_cost`. No role may sell below the kardex
  weighted-average cost; the rule lives in the application layer.
- **0135**: `sales_branch_promotions` (company, branch, product, `discount_percent` > 0 and < 100,
  `valid_from`, optional `valid_to` ≥ `valid_from`, notes, `created_by`/`created_at`,
  `ended_by`/`ended_at`). Composite foreign keys keep branch and product in the company. One
  promotion per product and branch per day is enforced by the use case. The line checks of
  quotations and orders accept `suggested_discount_source = 'promotion'`. Permission
  `sales_promotions:manage`, granted to `SUPER_ADMIN`.
- **0136**: `sales_settings.auto_deliver_on_confirm boolean NOT NULL DEFAULT true`.

**Downgrade** refuses while promotions exist. Covered by
`backend/tests/integration/test_sales_engineer_rules_migration.py`.

## 45. Remission notes of transfers (0137)

- `sales_fiscal_documents.transfer_id` (composite FK to `inventory_transfers`, RESTRICT): the transfer a
  remission note (`04`) covers. `sale_id` becomes nullable.
- `ck_sales_fiscal_documents_origin`: a `04` has a transfer and no sale; every other type has a sale and
  no transfer. `ck_sales_fiscal_documents_document` admits `04`.
- `uq_sales_fiscal_documents_active_transfer`: one vigent note per transfer (pending, contingency, issued or
  simulated, without a replacement).

**Downgrade** refuses while remission notes exist. Covered by
`backend/tests/integration/test_sales_transfer_remission_migration.py`.

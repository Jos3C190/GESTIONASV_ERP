# API Reference

> **Versión:** `v1.0.0` | **Última actualización:** `20/10/2026`
> Interactive docs at `/docs` (Swagger) and `/redoc` when running in non-production mode.

## 1. Base URL

| Environment | Base URL |
|-------------|----------|
| Local dev (compose) | `http://localhost:8000` |
| Prod (Nginx) | `https://<your-domain>/api` (reverse-proxied) |

## 2. Endpoints

### Sucursal matriz y bodega central (ERS-B01 / Alembic 0084)

Las respuestas de sucursal incluyen `is_headquarters`. `POST /api/v1/branches` y
`PATCH /api/v1/branches/{record_id}` permiten crear o mantener una matriz
administrativa con `is_headquarters: true`; la empresa puede tener como máximo
una matriz activa. La matriz puede omitir código y ubicación física. Si se
omite la dirección/geografía, el servidor usa el domicilio registrado de la
empresa y deja latitud/longitud vacías. No se crea una tienda ni una segunda
bodega como efecto de esta marca.

`POST /api/v1/warehouses` y `PATCH /api/v1/warehouses/{record_id}` requieren
`branch_id`. Una bodega enviada con
`is_central: true` debe apuntar a la matriz activa de la misma empresa; el
servidor rechaza otra sucursal aunque pertenezca a la empresa. La bodega central
conserva su identificador y estructura, y se muestra con la matriz en los
detalles y catálogos autorizados. `GET /api/v1/warehouses/catalogue` con
`include_company_central=true` solo agrega la bodega central al catálogo de otra
sucursal cuando el usuario tiene acceso a la matriz o alcance global.

El alcance de órdenes y recepciones centrales se deriva de la sucursal asignada
a la bodega. Los documentos históricos cuyo `branch_id` quedó vacío conservan
ese dato; lectura, detalle y acciones autorizadas resuelven el alcance desde
`warehouse_id`. En listas filtradas por la matriz también se incluyen esos
documentos sin reescribir su historial. Un usuario limitado a una tienda no
obtiene acceso a la bodega central por el solo hecho de pertenecer a la misma
empresa.

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

### Documentos privados y OCR

Todos los endpoints documentales requieren `X-Company-ID`; los cruces de empresa responden `404`.
El bucket y las claves privadas nunca forman parte del contrato HTTP.

| Método | Endpoint | Permiso | Propósito |
|---|---|---|---|
| `POST` | `/api/v1/documents/uploads` | `documents:upload` | Autorizar un PUT directo del original |
| `POST` | `/api/v1/documents/{id}/complete` | `documents:upload` | Validar, escanear y activar el original |
| `GET` | `/api/v1/documents[/{id}]` | `documents:read` | Listar o consultar metadatos y estado OCR |
| `POST` | `/api/v1/documents/library/{id}/preview-url` | `documents:download` | Emitir una URL privada inline para abrir un PDF en el visor del navegador |
| `POST` | `/api/v1/employees/{employee_id}/documents/{id}/preview-url` | `employee_documents:download` | Emitir una URL inline para un PDF del expediente del empleado |
| `POST` | `/api/v1/documents/{id}/download-url?variant=original|ocr` | `documents:download` | Emitir una descarga privada; original por defecto |
| `POST` | `/api/v1/documents/{id}/ocr/retry` | `documents:process` | Reintentar un OCR fallido; responde `202` |

Solicitar `variant=ocr` antes de `ready` responde `409 document_ocr_not_ready`. La activación y
descarga original no esperan al worker OCR.

### Purchase Requests

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/purchase-requests` | `purchase_requests:read` | Listar solicitudes de compra |
| `GET` | `/api/v1/purchase-requests/{request_id}` | `purchase_requests:read` | Obtener una solicitud de compra |
| `POST` | `/api/v1/purchase-requests` | `purchase_requests:create` o `purchase_requests:manage` | Crear una solicitud en borrador |
| `PUT` | `/api/v1/purchase-requests/{request_id}` | `purchase_requests:create` (solo borradores propios) o `purchase_requests:manage` | Actualizar una solicitud en borrador |
| `POST` | `/api/v1/purchase-requests/{request_id}/submit` | `purchase_requests:create` (solo borradores propios) o `purchase_requests:manage` | Enviar a aprobación |
| `POST` | `/api/v1/purchase-requests/{request_id}/approve` | `purchase_requests:approve` | Aprobar solicitud |
| `POST` | `/api/v1/purchase-requests/{request_id}/reject` | `purchase_requests:approve` | Rechazar solicitud |
| `POST` | `/api/v1/purchase-requests/{request_id}/cancel` | `purchase_requests:manage` | Cancelar solicitud |

### Purchase Quotations

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/purchase-quotations` | `purchase_quotations:read` | Listar cotizaciones de compra |
| `GET` | `/api/v1/purchase-quotations/comparison/{purchase_request_id}` | `purchase_quotations:read` | Comparar ofertas para una solicitud de compra |
| `GET` | `/api/v1/purchase-quotations/{quotation_id}` | `purchase_quotations:read` | Obtener una cotización de compra |
| `POST` | `/api/v1/purchase-quotations` | `purchase_quotations:manage` | Crear borrador de solicitud de cotización |
| `PUT` | `/api/v1/purchase-quotations/{quotation_id}/response` | `purchase_quotations:manage` | Registrar o actualizar la respuesta del proveedor |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/send` | `purchase_quotations:manage` | Registrar que la solicitud fue enviada al proveedor |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/evaluate` | `purchase_quotations:manage` | Pasar la cotización a evaluación |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/select` | `purchase_quotations:select` | Seleccionar la oferta |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/reject` | `purchase_quotations:manage` | Rechazar la oferta |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/cancel` | `purchase_quotations:manage` | Cancelar la solicitud de cotización |
| `GET` | `/api/v1/purchase-consolidations/{consolidation_id}/purchase-quotations` | `purchase_requests:read` + `purchase_quotations:read` | Listar RFQ y versiones ligadas al consolidado |
| `POST` | `/api/v1/purchase-consolidations/{consolidation_id}/purchase-quotations` | `purchase_requests:read` + `purchase_quotations:manage` | Crear una versión inmutable para un proveedor |
| `GET` | `/api/v1/purchase-consolidations/{consolidation_id}/adjudication` | `purchase_requests:read` + `purchase_quotations:read` | Comparar por producto las respuestas de proveedor y revisar decisiones |
| `POST` | `/api/v1/purchase-consolidations/{consolidation_id}/awards` | `purchase_requests:read` + `purchase_quotations:read` + `purchase_quotations:select` | Adjudicar manualmente una cantidad de una oferta a una línea |
| `POST` | `/api/v1/purchase-consolidations/{consolidation_id}/awards/{award_id}/revoke` | `purchase_requests:read` + `purchase_quotations:read` + `purchase_quotations:select` | Revertir una adjudicación con motivo conservando el historial |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/documents/uploads` | `purchase_quotations:manage` | Iniciar carga segura del archivo original de la oferta |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/documents/{document_id}/complete` | `purchase_quotations:manage` | Completar la carga y ejecutar la revisión documental |
| `GET` | `/api/v1/purchase-quotations/{quotation_id}/documents` | `purchase_quotations:read` | Listar archivos originales adjuntos a la oferta |
| `DELETE` | `/api/v1/purchase-quotations/{quotation_id}/documents/{document_id}` | `purchase_quotations:manage` | Quitar un adjunto de la respuesta; conserva auditoría |
| `POST` | `/api/v1/purchase-quotations/{quotation_id}/documents/{document_id}/download-url` | `purchase_quotations:read` | Crear una URL temporal para descargar un archivo adjunto |

Las RFQ creadas desde un consolidado conservan el código/version y una copia de las líneas y
cantidades exactas enviadas. La respuesta registra `offered_quantity` por separado de la cantidad
solicitada y acepta líneas no cotizadas con cantidad ofrecida cero. Para estos documentos, el
endpoint `/send` solo registra la confirmación de envío manual: no transmite correo. La
respuesta original se carga mediante el servicio documental seguro y sus archivos solo se descargan
cuando pasan la revisión. Los endpoints de adjuntos reciben `consolidation_id` para cotizaciones
consolidadas o `branch_id` para cotizaciones de sucursal. La comparación y adjudicación por línea
están disponibles en la vista del consolidado. La selección de una cantidad no cambia el estado de
otras cotizaciones ni crea una orden; órdenes desde adjudicaciones consolidadas pertenecen al Bloque 8.
Los importes permanecen en su moneda original hasta que se apruebe una política de conversión.

### Purchase Orders

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/purchase-orders` | `purchase_orders:read` | Listar órdenes de compra |
| `GET` | `/api/v1/purchase-orders/{order_id}` | `purchase_orders:read` | Obtener una orden de compra |
| `POST` | `/api/v1/purchase-orders` | `purchase_orders:manage` | Crear una orden desde una cotización seleccionada |
| `PUT` | `/api/v1/purchase-orders/{order_id}` | `purchase_orders:manage` | Editar una orden en borrador |
| `POST` | `/api/v1/purchase-orders/{order_id}/submit` | `purchase_orders:manage` | Enviar la orden a aprobación |
| `POST` | `/api/v1/purchase-orders/{order_id}/approve` | `purchase_orders:approve` | Aprobar la orden |
| `POST` | `/api/v1/purchase-orders/{order_id}/send` | `purchase_orders:send` | Enviar la orden aprobada al proveedor |
| `POST` | `/api/v1/purchase-orders/{order_id}/cancel` | `purchase_orders:manage` | Cancelar la orden antes de su envío |
| `POST` | `/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents/uploads` | `purchase_orders:manage` | Iniciar carga de documento para un gasto |
| `POST` | `/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents/{document_id}/complete` | `purchase_orders:manage` | Completar el documento de gasto |
| `GET` | `/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents` | `purchase_orders:read` | Listar documentos de un gasto |
| `POST` | `/api/v1/purchase-orders/{order_id}/expenses/{expense_id}/documents/{document_id}/download-url` | `purchase_orders:read` | Generar URL temporal de descarga |

### Purchases / Receiving

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/purchases` | `purchases:read` | Listar compras y recepciones |
| `GET` | `/api/v1/purchases/{purchase_id}` | `purchases:read` | Obtener una compra o recepción |
| `GET` | `/api/v1/purchase-orders/{order_id}/receivable` | `purchases:read` | Consultar cantidades pendientes de recibir de una orden |
| `POST` | `/api/v1/purchases` | `purchases:manage` | Crear un borrador de recepción desde una orden de compra |
| `PUT` | `/api/v1/purchases/{purchase_id}` | `purchases:manage` | Editar una recepción mientras permanezca en borrador |
| `POST` | `/api/v1/purchases/{purchase_id}/receive` | `purchases:receive` | Confirmar la recepción |
| `POST` | `/api/v1/purchases/{purchase_id}/verify` | `purchases:verify` | Verificar la recepción |
| `POST` | `/api/v1/purchases/{purchase_id}/cancel` | `purchases:manage` | Cancelar un borrador de recepción |
| `POST` | `/api/v1/purchases/{purchase_id}/close` | `purchases:verify` | Cerrar una recepción verificada |

Reglas principales:

- Toda compra o recepción se crea a partir de una orden de compra enviada o parcialmente recibida.
- Se permite recepción parcial; la orden pasa a `partially_received` mientras existan cantidades pendientes.
- La API bloquea cantidades que excedan lo pendiente de recibir en la orden.
- Cada detalle conserva la trazabilidad exacta mediante `purchase_order_detail_id`.
- Una compra confirmada como recibida ya no puede editarse como borrador.

### Retaceo

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `GET` | `/api/v1/retaceos` | `retaceos:read` | Listar retaceos |
| `GET` | `/api/v1/retaceos/{retaceo_id}` | `retaceos:read` | Obtener un retaceo |
| `POST` | `/api/v1/retaceos` | `retaceos:manage` | Crear un borrador de retaceo desde una compra |
| `PUT` | `/api/v1/retaceos/{retaceo_id}` | `retaceos:manage` | Editar un retaceo en borrador |
| `POST` | `/api/v1/retaceos/{retaceo_id}/calculate` | `retaceos:calculate` | Congelar el cálculo del retaceo |
| `POST` | `/api/v1/retaceos/{retaceo_id}/verify` | `retaceos:verify` | Verificar un retaceo calculado |
| `POST` | `/api/v1/retaceos/{retaceo_id}/cancel` | `retaceos:manage` | Cancelar un retaceo |
| `POST` | `/api/v1/retaceos/{retaceo_id}/close` | `retaceos:verify` | Cerrar un retaceo verificado |

Reglas principales:

- El Retaceo pertenece a una compra real, no directamente a una orden de compra.
- La compra debe estar en estado `received`, `verified` o `closed`.
- Los retaceos históricos se conservan; las nuevas capturas permiten un retaceo activo por compra.
- Desde la revisión 0095 el FOB de cada línea se captura manualmente; los registros anteriores conservan su política.
- Flete y DAI se distribuyen según FOB. Los otros gastos se desglosan y asignan por producto.
- El IVA de importación (`import_vat`) se almacena y muestra por separado y no forma parte del landed cost (`total_cost`).
- El flujo es `draft -> calculated -> verified -> closed`; desde `draft` o `calculated` también puede pasar a `cancelled`.
- Guardar/calcular no mueve stock. El flujo anterior puede aplicar un ajuste de valor al Kardex; el flujo nuevo incorpora el costo con el registro de recepción.

### Remaining deferred product API scope

Price lists, fiscal accounting rules and compliance documents are not exposed
by the API yet. Variant master data and the global inventory summary are
available.

The purchasing transaction flow is implemented for product-level lines, but
purchasing endpoints do not yet consume `variant_id`. Sales and pricing
endpoints that consume `variant_id` also remain deferred until their consuming
modules exist.

The dependency and acceptance matrix is documented in
[`docs/product-module-future-debt.txt`](product-module-future-debt.txt).

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

## 6. Receipt lots, grouped putaway and trace QR

- `GET /api/v1/inventory/lots` lists receipt lots and placement progress. Filter
  by `status`, `warehouse_id` or `purchase_id`; `pending_placement` includes
  partially placed lots that still have remaining work. Requires
  `inventory:read` and access to the selected warehouse.
- `POST /api/v1/inventory/putaway-groups/confirm` accepts idempotent grouped
  quantity allocations from receiving locations to storage locations in one
  warehouse. Requires `inventory:read` and `inventory:move`.
- `GET /api/v1/inventory/labels/preview` returns the printable product, receipt
  lot and handling-unit data. `POST /api/v1/inventory/labels/prints` records
  initial prints and reprints without changing stock. Both require
  `inventory:receive`.
- `POST /api/v1/inventory/trace-capabilities` issues a revocable QR link for an
  eligible unit and requires `inventory:read`. `POST
  /api/v1/inventory/trace-capabilities/{handling_unit_id}/revoke` invalidates
  all active links for that unit and requires `inventory:read` and
  `inventory:receive`.
- `POST /api/v1/inventory/public-traces/resolve` returns a limited read-only
  trace response using the bearer token in the request body. It requires no
  login and omits cookies/credentials. Anyone with the label can use the link
  until it is revoked.

### ERS-B02 — canonical receipt-detail identity (0085)

- `GET /api/v1/inventory/lots` includes each received product detail and its
  canonical `receipt_lot_detail_code`. The code identifies one actual purchase
  detail, not the whole receipt header. Company/warehouse scope and
  `inventory:read` are enforced.
- `GET /api/v1/inventory/kardex/physical` accepts `lot_code`. A canonical
  detail code filters to that product origin; a prior receipt-header code
  remains a supported alias and can return multiple detail origins. The result
  exposes both `receipt_lot_code` (canonical detail) and
  `receipt_lot_header_code` (receipt alias). Existing product/date/company
  filters continue to combine with the lot filter.
- `GET /api/v1/inventory/labels/preview` accepts exactly one of
  `inventory_lot_detail_id` or `handling_unit_id`. Its response identifies the
  product, internal barcode value, canonical detail code, receipt-header code,
  manufacturer lot and receipt date where present. `POST
  /api/v1/inventory/labels/prints` records software print/reprint events;
  `POST /api/v1/inventory/labels/confirmations` records confirmation of the
  current handling-unit label. These actions do not require or invoke a
  physical printer.
- Existing stock retains its label identity after its product or base unit is
  soft-deleted from the catalogue. Label lookups read that historical metadata
  through the persisted company/receipt/item relationships, without restoring
  catalogue records. Stock-state, permissions and retaceo checks still apply.
- `POST /api/v1/inventory/labels/prints` also accepts optional `layout`:
  `{ "content": "full" | "qr" | "barcode", "width_mm": 100, "height_mm": 125 }`.
  Dimensions are strict integers: width 25–200 mm, height 20–200 mm. Full labels
  require at least 80 × 80 mm, QR at least 50 × 60 mm, and barcode at least
  50 × 50 mm to reserve space for visible product, lot and receipt/expiry dates.
  Code 128B additionally requires printable ASCII and sufficient
  width for the product code including quiet zones. Invalid paper/content is
  rejected before appending a print event. The chosen layout is stored under
  `label_snapshot.print_layout` and included in the idempotency fingerprint;
  changing it while reusing a key returns a conflict. Requests without a layout
  retain their prior fingerprint and response shape. Paper configuration does
  not alter stock, label revision or placement confirmation. Software events
  record print requests, not hardware completion.
- Label print requests also accept optional `notes` (up to 160 characters),
  included in the immutable snapshot, audit and idempotency identity when nonempty.
  Empty notes preserve the earlier fingerprint. Reprinting retains the receipt
  lot/date, never the print date as receipt date. New `retaceo_before_inventory`
  purchases require a closed retaceo for preview and printing, including direct
  API calls; historical purchases retain their earlier readiness policy.
- Alembic `0085` adds a company-unique `inventory_lot_details.code` and nullable
  direct `inventory_movement_lines.inventory_lot_detail_id` for new movements.
  Historical immutable movement lines are resolved through their exact
  handling-unit relation where available; rows with no reliable relation stay
  explicitly unattributed. No origin is inferred from free-text movement data.

## 18. Transfer documents, vehicles and branch demand (revision 0086)

All routes are under `/api/v1/inventory/transfers`. Transfer commands use an
idempotency key, a company-scoped document, a database transaction/savepoint,
the existing inventory movement engine, and a required success audit entry.
The response includes product name, SKU, packaging snapshot, base unit, lot
detail identity, source/transit handling units, demand allocations, and each
receipt event so clients do not have to infer the product from the HU code.

### Routes

| Method and path | Purpose | Permission and scope |
| --- | --- | --- |
| `GET /demand?branch_id=...&product_id=...&search=...` | One row per eligible request detail, with requested, assigned, dispatched, in-transit, received and unassigned pending quantities | `inventory:read`; user's destination branch, or headquarters access plus `inventory:move` |
| `GET /vehicles` | List company vehicles | `inventory:read` and headquarters branch access |
| `POST /vehicles` | Create a vehicle and its mobile location | `inventory:read` + `inventory:move` and headquarters branch access |
| `PATCH /vehicles/{vehicle_id}` | Activate/deactivate a vehicle | `inventory:read` + `inventory:move` and headquarters branch access |
| `GET /` and `GET /{transfer_id}` | List or read documents within the caller's branch scope | `inventory:read` |
| `POST /` | Create a preparation | `inventory:read` + `inventory:move` and origin branch access |
| `PUT /{transfer_id}` | Edit preparation lines/destination/vehicle | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/cancel` | Cancel a preparation | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/dispatch` | Move stock from central warehouse to its assigned vehicle | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/receive` | Receive all or part into a destination quarantine location | `inventory:read` + `inventory:receive` and destination branch access |
| `POST /{transfer_id}/incidents` | Open an incident with reason and optional evidence reference | `inventory:read` plus either authorized origin/`inventory:move` or destination/`inventory:receive` |
| `POST /{transfer_id}/incidents/resolve` | Resume transit or close receipt when no unresolved quantity remains | Same authorized origin or destination scope as incident handling |

### State and stock rules

| Current state | Command | Result |
| --- | --- | --- |
| `preparation` | Edit | Revalidates company, branch, product, HU, lot, quantity and request demand; no reservation or stock movement |
| `preparation` | Cancel | `cancelled`; no stock movement |
| `preparation` | Dispatch | `in_transit`; central stock moves to the vehicle location once |
| `in_transit` | Partial receipt | Remains `in_transit`; received quantity moves into the destination in `quarantine`, remainder stays in the vehicle |
| `in_transit` | Final receipt | `received` when all dispatched quantity has been received or explicitly returned through a future authorized flow |
| `in_transit` | Open incident | `incident`; stock remains in transit and the incident keeps reason/evidence/history |
| `incident` | Resolve `resume_transit` | Returns to `in_transit` only after the remaining quantity is confirmed still present |
| `incident` | Resolve `close_received` | Allowed only when no unexplained quantity remains; loss/damage must first use the B05 adjustment |

Cancellation is allowed only before dispatch. No command silently removes stock.
Transfer movements preserve the handling unit's canonical receipt-detail lot
identity and use the inventory engine, so the company/product weighted-average
quantity and value remain unchanged. The vehicle warehouse is technical: it is
excluded from ordinary warehouse pickers and shelf-capacity calculations but
included in physical reconciliation and global valuation.

### Request and response examples

Create a preparation for an existing handling unit. A line quantity not linked
to a request needs an explicit reason:

```json
{
  "idempotency_key": "transfer-create-demo-001",
  "origin_warehouse_id": "<central-warehouse-uuid>",
  "destination_warehouse_id": "<branch-warehouse-uuid>",
  "vehicle_id": "<vehicle-uuid>",
  "notes": "Traslado de demostración",
  "lines": [{
    "handling_unit_id": "<handling-unit-uuid>",
    "quantity_base": "10.000000",
    "demand_allocations": [],
    "excess_reason": "Traslado manual de demostración"
  }]
}
```

Dispatch body:

```json
{"vehicle_id":"<vehicle-uuid>","idempotency_key":"transfer-dispatch-demo-001"}
```

Partial or full receipt body:

```json
{
  "idempotency_key": "transfer-receive-demo-001",
  "lines": [{
    "transfer_detail_id": "<transfer-detail-uuid>",
    "destination_location_id": "<receiving-location-uuid>",
    "quantity_base": "8.000000"
  }]
}
```

The transfer response includes per line `product_name`, `sku`,
`presentation_name`, `base_unit_name`/`base_unit_symbol`,
`inventory_lot_detail_code`, `source_handling_unit_code`,
`transit_handling_unit_code`, `quantity_planned`, `quantity_dispatched`,
`quantity_received`, `quantity_in_transit`, `demand_allocations`, and a receipt
history containing the movement and resulting handling-unit IDs/codes.

`GET /demand` returns one row per request detail. `quantity_assigned` includes
active preparation allocations; it is demand attribution rather than a
physical stock reservation. `quantity_pending` means
`max(requested - assigned, 0)`. `quantity_in_transit` means
`max(dispatched - received, 0)`. A quantity without request linkage is reported
on the transfer line as manual/excess with `excess_reason`; it does not appear
as request demand.

### Idempotency and compatibility

An idempotency key is unique by company and action. Repeating the same action
with the same key and request body returns the stored response snapshot, even
after later state changes. Reusing the key for a different body returns
`409 transfer_idempotency_conflict`. The transfer header and line locks serialize
competing dispatches and receipts; stock and document changes are protected by
one transaction/savepoint. A failed command leaves no partial movement, value
change, audit success or command response.

Legacy `POST /inventory/movements/confirm` remains available for unrelated
movement types and same-warehouse location operations. A generic transfer is
rejected with `409 inventory_transfer_document_required` if it assigns either
stock status to `in_transit` or moves between locations owned by different
warehouses. New cross-warehouse dispatch/receipt must go through the transfer
document so demand, vehicle, quarantine, idempotency and audit history remain
linked. Existing pre-0086 transit movements remain immutable legacy history
and are not assigned an invented vehicle or transfer document.

Common stable errors include `transfer_not_in_preparation`,
`transfer_handling_unit_unavailable`, `transfer_over_dispatch`,
`transfer_over_receipt`, `transfer_request_scope_mismatch`,
`transfer_excess_reason_required`, `transfer_vehicle_unavailable`,
`transfer_receipt_location_invalid`, and
`inventory_transfer_integrity_conflict`. B04 should consume these contracts;
this revision does not add the transfer screens.

## ERS-B05: authorized inventory adjustments (revision 0087)

All routes below are under `/api/v1/inventory/adjustments` and require
`inventory:read` as the module gate. The write operation also checks its
specific permission and company/warehouse scope in the backend.

| Method and path | Permission | Purpose |
| --- | --- | --- |
| `GET /options?warehouse_id=...` | `inventory:read` + warehouse scope | Active products/base units and eligible locations. |
| `GET /?warehouse_id=&status=&date_from=&date_to=&limit=&offset=` | `inventory:read` + branch scope | List and filter adjustments. |
| `POST /` | `inventory:adjust` | Create an idempotent draft; no movement. |
| `GET /{id}` | `inventory:read` + document scope | Read lines, support, actors and events. |
| `PUT /{id}` | `inventory:adjust` | Update a draft; an approved version must be revoked with a reason first. |
| `POST /{id}/documents` | `inventory:adjust` | Start a company-scoped upload and return an upload ticket. |
| `POST /{id}/documents/{document_id}/complete` | `inventory:adjust` | Complete/validate the upload and pin its checksum to the draft. |
| `DELETE /{id}/documents/{document_id}` | `inventory:adjust` | Detach support only while still a draft; preserves link history. |
| `GET /{id}/documents/{document_id}/download` | `inventory:read` + `inventory:valuation` + company/warehouse scope + active adjustment-document link | Return a short-lived authorized download URL. |
| `POST /{id}/approve` | `inventory:adjust_approve` | Approve the current `expected_version`; requires reason, reference and active completed evidence. |
| `POST /{id}/cancel` | `inventory:adjust` | Cancel a draft or approved adjustment with a reason; no movement. |
| `POST /{id}/apply` | `inventory:adjust_approve` | Explicitly post movements and valuation with an idempotency key. |
| `POST /{id}/correction` | `inventory:adjust` | Create a linked correction draft for a supported applied adjustment. |

Draft creation requires `idempotency_key`, `warehouse_id`, operational and
accounting dates, reason, document reference, and one or more lines. Each line
uses an inventory item and location, a positive base quantity of up to six
decimal places, and `direction` `increase` or `decrease`. An increase enters
quarantine and may provide documented unit **or** total cost; a decrease must
name an existing handling unit and consumes the average cost at application.
Optional line data includes canonical receipt lot, physical packaging/measures,
stock status and transfer detail. A transit decrease must also carry the
transfer and incident IDs and can only resolve a matching open incident.

Approval is version-bound. Application revalidates the evidence and current
stock, posts through the existing inventory movement/valuation services, and
stores its action key. Replaying the same key returns the applied document;
applying it with another key conflicts. Corrections are new drafts and still
need evidence, approval and application; the original adjustment and movement
are never edited. The supported automatic correction is limited to the full
quantity of a one-line ordinary negative adjustment when no later physical or
valued operations make the original cost ambiguous.

An applied transfer loss increments `quantity_adjusted_out` separately from
received quantity. When nothing remains in transit, the transfer becomes
`closed_with_adjustment`, not `received`. Public generic inventory movement
routes reject `adjustment_in` and `adjustment_out`; they cannot bypass the
approved adjustment document. Users without `inventory:valuation` receive
adjustment data with documented cost fields redacted. Evidence download also
requires `inventory:read`, `inventory:valuation`, the active company and
warehouse scope, and an active link from the exact adjustment to the document;
knowing an asset ID alone grants no access. Each new request rechecks these
conditions. An issued short-lived signed URL is a bearer capability and is not
retroactively revoked by detaching the link or changing scope; the storage
expiry policy bounds it. The focused E2E test stubs URL issuance and validates
authorization, not file bytes, storage, scanning, or expiry; see
[`test_adjustment_evidence_download_requires_valuation_permission`](../backend/tests/e2e/test_inventory_adjustment_permissions.py)
and its [command/output log](../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log).

## ERS-B06: customers, sales quotations and unfulfilled sales (revision 0088)

All routes use `/api/v1/sales`. Customers are scoped to the active company;
quotations and sales are additionally scoped to an authorized branch. The
commercial catalog includes only active, sellable products/variants that have
an inventory identity and an enabled base or packaging unit. The B06 catalog
does not include availability or cost. Physical deliveries are added by B07;
there are still no reservation, invoice, tax, discount, payment or receivable
endpoints.

| Method and path | Permission | Scope and purpose |
| --- | --- | --- |
| `GET /customers?search=&active=&page=&size=` | `sales_customers:read` | Search the active company's customer catalog. |
| `POST /customers` | `sales_customers:manage` | Create a customer with company-unique code and required name. |
| `GET /customers/{customer_id}` | `sales_customers:read` | Read a customer in the active company. |
| `PATCH /customers/{customer_id}` | `sales_customers:manage` | Update basic contact data or deactivate; no physical deletion. |
| `GET /catalog` | `sales_quotations:manage` | Read company-scoped sellable inventory identities and valid units. |
| `GET /quotations?branch_id=&customer_id=&status=&from_date=&to_date=&page=&size=` | `sales_quotations:read` | List quotations within assigned branches; status also projects expiry. |
| `POST /quotations` | `sales_quotations:manage` | Create an idempotent draft after branch, customer, product, unit and line validation. Requires `Idempotency-Key`. |
| `GET /quotations/{quote_id}` | `sales_quotations:read` | Read a quotation only within authorized company/branch scope. |
| `PUT /quotations/{quote_id}` | `sales_quotations:manage` | Replace a draft revision using `expected_version`; confirmed/converted lines are immutable. |
| `POST /quotations/{quote_id}/confirm` | `sales_quotations:confirm` | Confirm a current, unexpired draft revision. Requires `expected_version`. |
| `POST /quotations/{quote_id}/cancel` | `sales_quotations:confirm` | Cancel an eligible quotation with reason and expected version. |
| `POST /quotations/{quote_id}/convert` | `sales_quotations:convert` | Convert the whole confirmed quotation into one sale draft. Requires `Idempotency-Key` and `expected_version`. |
| `GET /?branch_id=&customer_id=&status=&from_date=&to_date=&page=&size=` | `sales:read` | List sales within assigned branches. |
| `GET /{sale_id}` | `sales:read` | Read a sale and its quotation origin within branch scope. |
| `PUT /{sale_id}` | `sales:manage` | Edit a sale draft using `expected_version`, preserving the quotation-line links. |
| `POST /{sale_id}/confirm` | `sales:confirm` | Confirm and freeze a sale draft revision. Requires `expected_version`. |
| `POST /{sale_id}/cancel` | `sales:cancel` | Cancel with reason only before a confirmed delivery exists; otherwise use the B08 return flow. |

Quotation request example (the server recalculates all totals):

```json
{
  "branch_id": "<authorized-branch-uuid>",
  "customer_id": "<company-customer-uuid>",
  "valid_until": "2026-10-21",
  "currency": "USD",
  "notes": "Demostración comercial",
  "lines": [
    {
      "product_id": 125,
      "variant_id": null,
      "unit_id": 7,
      "quantity": "3",
      "unit_price": "1.255"
    }
  ]
}
```

In this example, the server rounds the line amount to USD 3.77 using decimal
`ROUND_HALF_UP` to two places and sums rounded line amounts. USD is the only
accepted currency. Unit price is captured explicitly and may be zero; it is
not derived from inventory cost. Product, unit, packaging factor/version, SKU,
name and base-unit data are snapshotted on each line. At B06, sales responses
reported zero delivered and the full base quantity pending. In B07 these
read-only fields are recalculated from confirmed deliveries at six decimal
places; clients cannot write delivery state. Quotations and confirming or
cancelling a sale without delivery do not call inventory movement or
valuation services.

Creation and conversion use company/action-scoped idempotency records with a
canonical request fingerprint. A matching replay returns the same document;
the same key with a different body returns `409`. The API enforces permission
and branch/company scope before serving a replay. Quote confirmation, draft
editing, sale confirmation and cancellation use an expected version and
transaction savepoint; conversion is serialized by quotation and guarded by a
unique company/quotation constraint. A sale converted from a quotation keeps
the source quotation and source line IDs. Cancelling that sale does not free
the quotation for a second sale.

## ERS-B07: physical fulfillment of confirmed sales (revision 0089)

Deliveries are documents linked to confirmed sales and their source lines.
Availability is scoped to the sale's company and branch; only released,
available, open handling units in eligible locations can be selected. A draft
stores complete-HU assignments but does not move stock. Confirmation rechecks
the sale, pending quantity, branch, HU state, current label confirmation,
location, lot and expiry, then records the inventory shipment, weighted-average
issue, delivery document and audit event atomically. Partial fulfillment is
allowed; delivered quantity is derived only from confirmed delivery lines.

| Method and path | Permission | Scope and purpose |
| --- | --- | --- |
| `GET /{sale_id}/delivery-stock` | `sales_deliveries:manage` | Preview eligible full HUs for each pending sale line; no reservation or movement. |
| `GET /{sale_id}/deliveries` | `sales_deliveries:read` | List a sale's delivery documents and assignments. |
| `POST /{sale_id}/deliveries` | `sales_deliveries:manage` | Create an idempotent draft from sale-line/HU assignments. Requires `Idempotency-Key`. |
| `GET /deliveries/{delivery_id}` | `sales_deliveries:read` | Read one delivery within company and authorized branch scope. |
| `PUT /deliveries/{delivery_id}` | `sales_deliveries:manage` | Replace draft assignments and notes using `expected_version`. |
| `POST /deliveries/{delivery_id}/confirm` | `sales_deliveries:confirm` | Revalidate and post physical/valued output atomically. Requires `expected_version` and `Idempotency-Key`. |
| `POST /deliveries/{delivery_id}/cancel` | `sales_deliveries:cancel` | Cancel a draft with a reason and `expected_version`; no stock effect. |

Create draft example:

```json
{
  "notes": "Entrega parcial de la sucursal",
  "assignments": [
    {
      "sale_line_id": "<sale-line-uuid>",
      "handling_unit_id": "<available-hu-uuid>"
    }
  ]
}
```

Confirmation consumes the selected HUs in full. A partial package quantity
must first be physically separated and reviewed through the warehouse flow.
The server values the issue using the current company/item weighted average;
commercial sale price is independent. Commercial delivery DTOs expose IDs of
movement, movement line and valuation entry for traceability, but omit applied
cost amounts. The stored allocation retains the cost and its valuation link
for B08 returns. Confirmed/cancelled documents and their lines are immutable.

Create/confirm commands are idempotent. A matching key/fingerprint returns
the stored document; reuse with different content returns `409`. Two
concurrent commands cannot consume the same last HU or exceed the sale-line
pending quantity. A sale with any confirmed delivery cannot be cancelled;
cancel any remaining draft if no delivery has been posted. Returns are not
part of B07.

## ERS-B08: customer returns and review (revision 0090)

Review correction (19–20/10/2026): return reasons are trimmed before validating
their 3–500 character length in create, resolve and cancel contracts. The
application service also rejects invalid normalized reasons before writing.
Receiving a return remains documentary; only an accepted decision creates a
stock/value entry, so retrying receipt must not be used as an inventory update.
Browser preflights allow the `Idempotency-Key` request header on configured
origins. Origin restrictions, credentials handling and command authorization
remain enforced; this is required for the commercial client to send its
idempotent commands across the frontend/API ports.

Returns are company/branch-scoped documents linked to confirmed delivery
allocations and their original issue/valuation entry. Creating a draft or
receiving it for review does not change physical stock or valuation. The
operator resolves each received quantity in append-only events: accepted
quantities create a customer-return movement at the effective cost of the
original delivery allocation; rejected quantities create no available stock.
An accepted quantity is placed in an authorized location and may remain in
quarantine until the existing warehouse review releases it. The API does not
create refunds, credit notes, tax documents or payments.

| Method and path | Permission | Scope and purpose |
| --- | --- | --- |
| `GET /returns?branch_id=` | `sales_returns:read` | List returns for the active company and assigned branches; an optional branch further narrows the result. |
| `GET /returns/{return_id}` | `sales_returns:read` | Read one return, its delivery origin, evidence and decision events after branch authorization. |
| `GET /{sale_id}/returns` | `sales_returns:read` | List returns belonging to a sale the caller may read. |
| `GET /{sale_id}/returnable-allocations` | `sales_returns:manage` | Show delivered allocations and the remaining quantity eligible for return. |
| `POST /{sale_id}/returns` | `sales_returns:manage` | Create an idempotent draft from delivery-allocation IDs, quantities, reason/condition and optional authorized evidence. Requires `Idempotency-Key`. |
| `POST /returns/{return_id}/receive` | `sales_returns:receive` | Register receipt for review. Requires `Idempotency-Key`; no stock effect. |
| `POST /returns/{return_id}/resolve` | `sales_returns:resolve` | Append accepted/rejected line decisions. Accepted lines require a valid destination; stock, cost and events commit atomically. Requires `Idempotency-Key`. |
| `POST /returns/{return_id}/cancel` | `sales_returns:cancel` | Cancel an eligible draft with a reason. Requires `Idempotency-Key`; no stock effect. |

Return request example:

```json
{
  "notes": "Demostración ficticia de devolución",
  "document_ids": [],
  "lines": [
    {
      "delivery_allocation_id": "<allocation-from-confirmed-delivery>",
      "quantity_base": "1.000000",
      "reason": "Envase dañado al recibir",
      "declared_condition": "damaged"
    }
  ]
}
```

The server rechecks the delivered allocation and serializes competing
acceptances so the accepted total cannot exceed quantity delivered less
previously accepted quantity. A repeated action with the same key and body
returns its saved result; key reuse with different content returns `409`.
Permission, company and branch authorization are checked before a replay is
returned. Evidence is optional, but attached document IDs must be accessible
to the caller and belong to the active company. The return DTO exposes product,
unit, delivery/lot origin, received/accepted/rejected/pending/returnable
quantities and movement/valuation identifiers; it does not expose inventory
cost. Rejected and unresolved quantities remain distinguishable and never
become available stock. Final documents and decision events are immutable;
corrections require a separate authorized compensating workflow.

## Foreign-currency purchase valuation (revision 0091)

`GET /purchases/{id}/valuation-context` requires `purchases:verify` and
`inventory:receive` and uses the existing company/warehouse visibility checks.
It returns the receipt currency and the company's active valuation currency
(nullable before opening). This does not require access to the full valuation
ledger.

`POST /purchases/{id}/verify` accepts an optional `valuation_conversion`:

```json
{
  "currency": "USD",
  "rate": "500",
  "effective_date": "2026-10-21",
  "reference": "Fictional demonstration rate"
}
```

This object accompanies the existing `lines` field; it is required when the
accepted receipt and active valuation use different currencies. Rate means
source currency units per one valuation currency unit: this fictional CRC
example means 1 USD = 500 CRC, so the inventory cost is the accepted CRC cost
divided by 500. Rate must be positive, less than 10^12, with at most twelve
decimal places. Date and a 3–500 character reference are required. The source
currency comes from the persisted purchase. Target currency must match the
active company valuation. An entirely rejected receipt does not require a
conversion.

The receipt currency and commercial amounts are retained. The conversion is
included in the purchase DTO and VERIFY audit state and saved atomically with
verification. Retaceo application reuses this saved conversion for provisional
FOB matching and final landed cost; its application summary includes both
currencies and the conversion. No live exchange-rate service is called.

Expected errors include `purchase_valuation_conversion_required`,
`purchase_valuation_currency_changed`, `purchase_valuation_conversion_invalid`
and `purchase_valuation_conversion_unnecessary`. Apply migration 0091 before
running the updated backend. Verification and rollback evidence is documented
in `docs/ers-v1/conversion-monedas-compras-2026-10-21.md`.

### Kardex statements and exports (2026-10-29)

`GET /inventory/kardex/physical/export?format=pdf|xlsx` accepts the same warehouse,
item, period, movement, lot and source-reference filters as the physical query.
`inventory:read`, branch access and explicit warehouse assignments are enforced;
other warehouse endpoints/HUs are masked. Human purchase/delivery codes can be
used as document filters. The matching incoming/outgoing totals use that filter.

`GET /inventory/kardex/valuation/export?format=pdf|xlsx` and
`GET /inventory/kardex/reconciliation/export?format=pdf|xlsx` require
`inventory:valuation` and unrestricted company-wide warehouse/branch scope.
All exports include the entire filtered result (maximum 5,000 rows, otherwise 422),
company/product identification and available NIT/NRC, and return `Cache-Control:
no-store`. XLSX numeric cells preserve amounts and text is not interpreted as formulas.

Reconciliation also accepts `as_of=YYYY-MM-DD`, `q` and `difference_only` on both
JSON and export routes. A historical cut reconstructs the approved physical
baseline plus external movements and the last persisted valuation balance through
the end of the selected **registration** day in El Salvador. It is not a retroactive
accounting-date recomputation. Before the approved cut, quantities/values remain
unknown. Omitting `as_of` retains the current-balance query. Response totals apply
to all matching products, before pagination; unknown-valued products are identified.

Statement responses add optional company/product context, readable document
references, operator, and applied unit cost. Technical references and historical
ledger amounts remain unchanged. These are internal reports; no specific fiscal
template certification is implied.

### Kardex product picker (2026-10-21)

`GET /inventory/kardex/items?warehouse_id=<uuid>&q=<text>` retains the existing
`inventory:read` permission and warehouse/company/branch authorization. `q` is now optional
(maximum 120 characters). Without a query, it returns up to 20 eligible products ordered by
their latest movement in that warehouse, descending with missing movement dates last.
Products with a positive balance but no recorded movement remain eligible.

With a query, search covers product/variant names and SKUs, the product internal/original
codes, and an exact inventory-item UUID. Text results retain their name/ID ordering and
20-result limit. Responses add the optional nullable `last_movement_at` datetime; existing
fields remain unchanged. This is a read operation and requires no migration.

`/inventory/kardex?warehouse_id=<uuid>&inventory_item_id=<uuid>` is the frontend link used
by the warehouse inventory's **Ver Kardex** action. The page resolves the exact item inside
the authorized warehouse before consulting its movements. UI details and evidence are in
`docs/ers-v1/selector-productos-kardex-2026-10-21.md`.

### Adjustment product search (2026-10-22)

`GET /inventory/adjustments/options` retains `inventory:read` and the existing
company/warehouse/branch authorization. It accepts optional `q` (up to 120
characters), `limit` (1–50), `offset` (nonnegative), `include_items` and
`include_locations` (both default true). Responses retain `items`/`locations`
and add nullable `items_total`. Without the new parameters, the existing
catalog response remains available.

The new adjustment editor requests locations with `include_items=false` and
searches the company catalog with `limit=20&include_locations=false`. Search
combines words across product/variant names and SKUs, ignoring case and Spanish
accents, treating SQL wildcard characters literally. Results have stable
name/ID ordering. This is read-only and requires no migration. Details and
static-review limits: `docs/ers-v1/buscador-productos-ajustes-2026-10-22.md`.

### Manual retaceo and operational warehouse receipt (2026-10-23)

Purchase DTOs expose `inventory_workflow`: existing documents use
`receipt_before_retaceo`, new purchases use `retaceo_before_inventory`.

- `GET /purchases/{id}/receiving-readiness`: `purchases:read` and document
  warehouse/branch authorization. Returns `required`, `ready`, nullable
  `retaceo_id`, `retaceo_code`, `retaceo_status`. New purchases require exactly
  one active closed retaceo before verification can create stock.
- Retaceo create/update accept `fob_lines: [{purchase_detail_id, amount}]` for
  the new workflow. Creation requires exactly one positive, finite manually
  documented FOB per received detail. Update preserves existing FOB when omitted.
  Legacy documents cannot use this input to rewrite historic receipt FOB.
- Retaceo create/update accept optional `import_data` with nullable
  `origin_country`, `import_invoice_number/date`, `import_policy_number/date`.
  The response exposes these five fields. Actual cost concepts, classifications,
  manual allocations and documentary validation use the existing cost API.
  New retaceos do not automatically import planned order expenses.
- `GET /retaceos/{id}/average-comparison`: `retaceos:read`,
  `inventory:valuation`, company-wide branch access. Returns `currency`,
  `mode=preview|posted`, and per-item previous/incoming/resulting quantity,
  value and average, plus item/product/base-unit IDs. Projections use current
  company balances; posted comparisons use immutable entries linked to the
  retaceo. Missing opening balances or unit/currency conversion return explicit
  business errors. A fully rejected receipt can return an empty posted list.
- New-workflow retaceos can close before inventory registration. The separate
  legacy apply-cost command is rejected for them: receipt verification posts
  final cost once and records the application.
- `GET /warehouse-receipts?warehouse_id=<uuid>&page=1&size=10`:
  `inventory:warehouse_receipts`, company/branch and explicit warehouse scope.
  Returns pending received documents with readiness, quantities, product names,
  SKUs and units. It does not return commercial amounts or valuation costs.
- `POST /warehouse-receipts/{purchase_id}/verify`: same scope and permission,
  plus `inventory:receive` and `locations.view`. Uses the existing
  `PurchaseVerify` payload (`lines`, optional documented `valuation_conversion`)
  and the audited purchase verification use case. Response remains operational
  and excludes prices. The simplified UI submits one location per detail.
- Generic `POST /inventory/movements` with type `receipt` now returns conflict
  `purchase_receipt_document_required`; purchase receipts must use their
  document flow. Existing authorized transfer/adjustment flows retain their
  own commands.

Warehouse-restricted memberships are additionally checked for inventory,
handling-unit labels, lot details, locations, putaway and transfer-source
operations. Hiding administration navigation is supplementary; server-side
company, branch, permission and warehouse checks remain authoritative.

### Manual fixed amounts and actual expense log (2026-10-27, revision 0095)

- New `POST /retaceos` records always use `manual_entry=true`. FOB lines,
  freight, DAI and import VAT are explicitly entered; no financial amounts or
  planned expenses are copied from an order. A missing fixed amount is rejected;
  explicit zero is accepted for a non-applicable charge. Other expenses start at
  zero and must be itemized through the draft editor.
- `GET /retaceos/cost-categories` requires `retaceos:manage` and returns active
  company categories for other expenses. Fixed FOB/freight/DAI/import VAT are
  excluded. Draft cost inputs accept `expense_type_id`, `incurred_on` and optional
  `source_purchase_order_expense_id`. Other expenses require category, date and
  description. Attachments are optional for every retaceo cost. An upload already
  started must finish or be removed; absence of files never blocks calculation.
  Exact allocation checks remain required. Freight and DAI are distributed proportionally to typed FOB;
  import VAT is separate and never capitalized.
- `GET /purchase-orders/{order_id}/actual-expenses` requires
  `purchase_orders:read`. `POST` requires `purchase_orders:manage` and accepts
  `expense_type_id`, `amount`, `incurred_on`, `reference`, `description`.
  Company, branch and warehouse document visibility apply to both routes.
  Recording is allowed after approval, including shipment wait and partial receipt,
  until any retaceo linked to a receipt of that order is closed. The shared order
  log then refuses new financial entries with `actual_expense_retaceo_closed`,
  including when the order itself still reads `received`. This also locks the
  shared log for other partial receipts of the same order. Closing a retaceo and
  creating an expense serialize on the same order row lock.
  `GET /purchase-orders/{order_id}/actual-expenses/availability` uses the same
  read permission and document visibility and returns `can_record`, `reason`,
  `closed_retaceo_id`, and `closed_retaceo_code`. Expense responses include
  `unallocated_amount` (amount minus active retaceo assignments). Existing
  unassigned entries remain visible for review and never change closed costs.
  Required audit action: `ACTUAL_EXPENSE_RECORDED`. Actual rows are excluded from
  the approved budget and order totals. Their files use existing expense-document
  routes. Recording an actual expense alone does not apply it to inventory.

### Procurement document exports

- `GET /retaceos/{retaceo_id}/export?format=pdf|xlsx` downloads the saved retaceo
  with company, supplier, purchase/order references, import documentation, per-product
  quantity/FOB/freight/other expenses/DAI/total/unit cost, totals and expense evidence
  filenames. Requires `retaceos:read`, source branch visibility and source warehouse
  access. VAT is separate from landed cost. The current global average is not
  recomputed or substituted for this entry's saved unit cost.
- `GET /purchase-consolidations/{consolidation_id}/export` downloads an internal
  general-demand PDF. Requires `purchase_requests:read` and access to all source
  branches and the central destination, matching the document detail. Quantities
  are grouped per product/unit; source requests and included quantities are preserved.
  Existing supplier-specific RFQ printing remains separate.
- Both exports are read-only, use `Content-Disposition: attachment` and
  `Cache-Control: no-store`, and retain the saved document's status. A draft export
  does not include unsaved form changes. XLSX cells preserve numeric values and
  six-decimal unit costs; supplied text is forced to string cells to prevent Excel
  formula injection. PDF tables repeat headers on subsequent pages.

### Manual retaceo source assignments (continued)
- A cost may explicitly link a real expense from its own order. Amount, category
  and date are still entered manually and checked. Active retaceos reserve the
  linked amount; the sum across partial receipts cannot exceed the documented
  actual expense. Cancellation releases its reservation. The parent order is locked
  while validating/saving to serialize competing assignments.
- Confirmed supplier invoice number/date are read-only in manual retaceos.
  Existing historical retaceos keep their prior policy. New manual drafts are
  unique per purchase while active. A changed legacy FOB requires a documented
  reason of at least 20 characters in `notes`. Application appends a zero-quantity
  cost adjustment, retaining original receipt values and historic balances. Its
  summary records original FOB, typed FOB and reason; it does not rewrite the
  closed purchase or earlier ledger entries.
- Average comparison adds `value_only`. An already posted legacy receipt is
  projected with value adjustments and zero incoming quantity, including effects
  on intervening issues/returns. Future receipts continue showing incoming stock.
  Applied comparisons use recorded receipt or adjustment entries. This block does
  not move the final stock-posting point; that remains part of the placement block.

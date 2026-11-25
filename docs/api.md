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
- Regla vigente (ERS p. 81-82, CA-COM-021/022/024; revisión 0117): costo = FOB + flete y seguro + DAI + gastos adicionales. El FOB es automático y fijo: sale siempre de la factura de compra (subtotal menos descuento, proporcional a la cantidad aceptada) y nunca se envía en la solicitud.
- Flete y seguro y DAI son importes fijos tecleados (`total_freight`, `total_dai`, ambos obligatorios y mayores o iguales a 0; `0` es válido). Los gastos adicionales se desglosan por categoría.
- Todos los componentes (flete, DAI y gastos adicionales) se reparten en el servidor según el FOB de cada línea (mayor residuo a 6 decimales); el costo unitario es el costo total de la línea entre su cantidad. No se aceptan repartos por línea.
- El IVA de importación no forma parte del retaceo: no se captura, almacena ni muestra.
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

## 18. Transfer documents, vehicles and branch demand (revision 0086; routes and approval in 0114; last editor in 0115; transport, partial reception and discrepancies in 0116)

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
| `GET /settings` | Company transfer rules plus the count of transfers a rule change would freeze | `inventory:read` |
| `PUT /settings` | Save the route switches and the approval rule | `inventory:transfer_settings` |
| `GET /route-options?origin_warehouse_id=...` | Warehouses the caller may ship from; with an origin, the destinations that classify to a valid route | `inventory:read`; origins limited to the caller's branch scope and warehouse assignment |
| `GET /pending-approval-count` | Number of transfers the caller could approve right now | `inventory:read`; returns `{"count": 0}` without `inventory:transfer_approve` |
| `GET /` and `GET /{transfer_id}` | List or read documents within the caller's branch scope | `inventory:read` |
| `POST /` | Create a preparation (vehicle and driver optional) | `inventory:read` + `inventory:move` and origin branch access |
| `PUT /{transfer_id}` | Edit preparation lines/destination/vehicle/driver | `inventory:read` + `inventory:move` and origin branch access; moving the document to another origin also requires access to the new origin |
| `POST /{transfer_id}/cancel` | Cancel a preparation, pending or approved transfer | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/submit` | Send a branch-route preparation to approval; needs vehicle and driver, and a transport fit to be planned | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/withdraw` | Take a pending transfer back to preparation | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/approve` | Approve a pending transfer | `inventory:transfer_approve` and origin branch access; not the creator/submitter unless superuser |
| `POST /{transfer_id}/reject` | Reject a pending transfer with a reason; it returns to preparation | `inventory:transfer_approve` and origin branch access; same segregation as approve |
| `POST /{transfer_id}/dispatch` | Move stock from the origin warehouse to its assigned vehicle; a different vehicle or driver than the approved ones needs a coded, audited reason | `inventory:read` + `inventory:move` and origin branch access |
| `POST /{transfer_id}/receive` | Receive all or part; each line splits into good (quarantine), damaged (`damaged` stock) and surplus (0116) | `inventory:read` + `inventory:receive` and destination branch access |
| `POST /{transfer_id}/incidents` | Open an incident (from `in_transit` or `partially_received`) with reason and optional evidence reference | `inventory:read` plus either authorized origin/`inventory:move` or destination/`inventory:receive` |
| `POST /{transfer_id}/incidents/resolve` | Resume transit or close receipt when no unresolved quantity remains | Same authorized origin or destination scope as incident handling |
| `GET /assignment-options?origin_warehouse_id=...&transfer_id=...` | Vehicles and drivers of the origin branch that can be chosen while preparing (0116) | `inventory:read` and origin warehouse scope |
| `POST /assignment-check` | Judge the vehicle and driver chosen for a draft, with the weight of its lines and planning conflicts (0116) | `inventory:read` and origin warehouse scope (and origin branch scope of `transfer_id`, if sent) |
| `GET /{transfer_id}/assignment-check` | The same judgement for the transport saved in a transfer, for the approver (0116) | `inventory:read` and origin branch access |
| `POST /{transfer_id}/close-reception` | Stop waiting for what has not arrived: it becomes open shortages and the transfer goes to `discrepancy` (0116) | `inventory:read` + `inventory:receive` and destination branch access |
| `POST /{transfer_id}/discrepancies/{discrepancy_id}/adjustment` | Prepare, as a draft, the adjustment that regularises a shortage, damage or surplus; answers `201` with the adjustment (0116) | `inventory:read` + `inventory:adjust`; shortage: origin **or** destination branch access, damage and surplus: destination |
| `POST /{transfer_id}/discrepancies/{discrepancy_id}/claim` | Hand a damage to the carrier or insurer (`in_claim`); it stops blocking the transfer (0116) | `inventory:read` + `inventory:adjust_approve` and destination branch access |
| `POST /{transfer_id}/discrepancies/{discrepancy_id}/release` | After inspection, move a damaged unit to quarantine (0116) | `inventory:read` + `inventory:adjust_approve` and destination branch access |
| `POST /{transfer_id}/discrepancies/{discrepancy_id}/found` | The missing goods arrived after all: the shortage is cancelled and reception resumes (0116) | `inventory:read` + `inventory:receive` and destination branch access |
| `POST /{transfer_id}/discrepancies/{discrepancy_id}/dismiss` | The surplus was a counting mistake: nothing enters stock (0116) | `inventory:read` + `inventory:adjust_approve` and destination branch access |
| `POST /{transfer_id}/discrepancies/{discrepancy_id}/origin-count` | The origin warehouse counted its stock after a shortage or a surplus (0116) | `inventory:read` + `inventory:adjust` and origin branch access |

The static paths (`/demand`, `/vehicles`, `/settings`, `/route-options`,
`/pending-approval-count`, `/assignment-options`, `/assignment-check`) are
declared before `/{transfer_id}`.
`GET /` accepts `branch_id` (matches origin **or** destination branch),
`status` (`preparation`, `pending_approval`, `approved`, `in_transit`,
`partially_received`, `discrepancy`, `received`, `closed_with_adjustment`,
`incident`, `cancelled`), `route_type`
(`central_distribution`, `branch_to_branch`, `branch_to_central`),
`side` (`origin` or `destination`, relative to `branch_id`),
`awaiting_my_approval` (boolean; empty list when the caller lacks
`inventory:transfer_approve`), `origin_count_pending` and
`with_open_discrepancies` (booleans, 0116), `page` and `size`.

### Routes and company rules (revision 0114)

Every document has a `route_type` computed from its origin and destination:

| `route_type` | Origin | Destination | Approval |
| --- | --- | --- | --- |
| `central_distribution` | Central warehouse (headquarters) | Active branch warehouse | Never |
| `branch_to_branch` | Branch warehouse | Warehouse of another branch | When `require_approval` is on |
| `branch_to_central` | Branch warehouse | Central warehouse | When `require_approval` is on |

Rules live in `inventory_transfer_settings`, one row per company. Without a
row the defaults apply: both branch routes off and `require_approval` on, so
existing behaviour does not change until a company turns a route on.

```json
// GET or PUT /settings
{
  "allow_branch_to_branch": true,
  "allow_branch_to_central": false,
  "require_approval": true
}
```

`GET` additionally returns `updated_at`, `pending_count` (transfers in
`pending_approval`) and `approved_count` (transfers in `approved`) so a client
can warn that switching a route off freezes them. `PUT` takes exactly the three
booleans, locks the row, and writes the audit entry
`UPDATE_INVENTORY_TRANSFER_SETTINGS` with the before and after values.

`GET /route-options` returns:

```json
{
  "policy": {"allow_branch_to_branch": true, "allow_branch_to_central": false, "require_approval": true},
  "origins": [{"id": "<uuid>", "code": "ALM-01", "name": "Bodega Central", "branch_id": "<uuid>", "branch_name": "Casa matriz", "is_central": true}],
  "destinations": [{"id": "<uuid>", "code": "ALM-02", "name": "Bodega Sur", "branch_id": "<uuid>", "branch_name": "Sucursal Sur", "is_central": false, "route_type": "central_distribution"}]
}
```

`origins` carry no `route_type`; `destinations` (empty unless
`origin_warehouse_id` is sent) do. The central warehouse is an origin only when
it belongs to the headquarters branch; branch warehouses are origins only when at
least one branch route is on. Every origin and every destination must also be
`storage_eligible`: a warehouse that cannot store stock is never offered. The
create and update commands apply the same rule on the central route
(`409 transfer_origin_invalid` for the origin, `422 transfer_destination_invalid`
for the destination), as they already did on branch routes. An
`origin_warehouse_id` outside the caller's allowed origins returns `403`. `GET /pending-approval-count` returns
`{"count": 3}`.

Transfer responses add: `route_type`, `requires_approval`, `approval_round`,
`submitted_by_id/_name/_at`, `last_edited_by_id/_name` (null until someone
edits the preparation; migration 0115 adds the nullable column
`inventory_transfers.last_edited_by_id`, a foreign key to `users` with
`ON DELETE RESTRICT`), `approved_by_id/_name/_at`,
`rejected_by_id/_name/_at`, `rejection_reason`, `origin_branch_name`,
`origin_is_central`, `destination_branch_name` and `destination_is_central`.
`requires_approval` is recalculated on create, update and submit; for a
document in `preparation` it reflects the current company rule, and a draft
dispatched directly (approval turned off in the meantime) is stored with
`requires_approval = false`, so it never claims an approval it did not have.

### Approval commands

`submit` and `withdraw` take only `idempotency_key`. `approve` and `reject`
also take the round the person saw:

```json
// POST /{transfer_id}/approve
{"idempotency_key": "transfer-approve-demo-001", "expected_round": 1}

// POST /{transfer_id}/reject  (reason: 5 to 1000 characters)
{"idempotency_key": "transfer-reject-demo-001", "expected_round": 1,
 "reason": "Faltan 2 unidades por confirmar en la sucursal destino"}
```

`approval_round` increases by one on every `submit`. A decision whose
`expected_round` differs from the current one fails with
`409 transfer_approval_stale`, so nobody approves a version they did not see.
The creator, the submitter and the last editor cannot approve or reject
their own transfer (`403 transfer_approval_self_forbidden`) unless the caller
is a superuser. Every `PUT /{transfer_id}` records the caller in
`last_edited_by_id`; the same three people are left out of
`GET /pending-approval-count` and `awaiting_my_approval`.
`submit` and `approve` revalidate the route, the company rule, available stock
and units already committed to another transfer; `reject` and `withdraw` do not
require the route to be enabled. `reject` and `withdraw` return the document to
`preparation`; `reject` stores the reason and the rejecting user, and the next
`submit` clears the rejection and approval data. Each of these commands is
audited as `SUBMIT_TRANSFER`, `WITHDRAW_TRANSFER`, `APPROVE_TRANSFER` or
`REJECT_TRANSFER`. Idempotency keys are unique per company and action, and
replays follow the rules of the other transfer commands.

### State and stock rules

| Current state | Command | Result |
| --- | --- | --- |
| `preparation` | Edit | Revalidates company, branch, product, HU, lot, quantity and request demand; no reservation or stock movement |
| `preparation` | Cancel | `cancelled`; no stock movement |
| `preparation` | Submit (branch route with approval) | `pending_approval`; `approval_round + 1`; no stock movement |
| `pending_approval` | Approve | `approved`; stock, route, rule and committed units are revalidated |
| `pending_approval` | Reject | `preparation` with `rejection_reason`; the next submit starts a new round |
| `pending_approval` | Withdraw | `preparation` |
| `pending_approval` / `approved` | Cancel | `cancelled`; no stock movement |
| `approved` | Dispatch | `in_transit`; origin stock moves to the vehicle location once |
| `preparation` | Dispatch | `in_transit` for `central_distribution`, or for a branch route when the rule does not require approval; otherwise `409 transfer_approval_required` |
| `in_transit` / `partially_received` | Partial receipt (0116) | `partially_received`; received quantity moves into the destination (good part in `quarantine`, damaged part in `damaged`), remainder stays in the vehicle. Before 0116 this stayed `in_transit` |
| `in_transit` / `partially_received` | Final receipt | `received` when all dispatched quantity has been received or explicitly returned through a future authorized flow; `discrepancy` if damage or surplus is still open; `closed_with_adjustment` if differences existed and none is open (see "Status settlement") |
| `partially_received` | `close-reception` (0116) | `discrepancy`: what has not arrived becomes open shortages |
| `discrepancy` | `found` on a shortage (0116) | `partially_received`: the shortage is cancelled and the line can be received again |
| `discrepancy` | Last open difference resolved, or damage handed to a claim (0116) | `closed_with_adjustment` |
| `in_transit` / `partially_received` | Open incident | `incident`; stock remains in transit and the incident keeps reason/evidence/history |
| `incident` | Resolve `resume_transit` | Returns to `partially_received` if something was already received, otherwise `in_transit`; only after the remaining quantity is confirmed still present |
| `incident` | Resolve `close_received` | Allowed only when no unexplained quantity remains; loss/damage must first use the B05 adjustment |

Cancellation is allowed only before dispatch (`preparation`, `pending_approval`
and `approved`). Cancelling an `in_transit` central transfer still returns
`409 transfer_not_in_preparation`; for branch routes the error is
`409 transfer_not_cancellable`. Dispatch of a `central_distribution` document
outside `preparation` still returns `409 transfer_not_dispatchable`; branch
routes return `transfer_approval_required` for a `preparation`/`pending_approval`
document that needs approval and `transfer_not_dispatchable` for other states.
Only `preparation` is editable.

When a company changes its rules, a branch-route transfer whose route is now
off cannot be created, edited, submitted, approved or dispatched and fails
with `409 transfer_route_disabled`; reject, withdraw and cancel remain
available, and transfers already `in_transit` or in `incident` are unaffected.
A transfer saved from a branch warehouse while both branch routes are off
returns `transfer_route_disabled`, also when it is edited (`PUT`) keeping its
origin; a new document in that situation still gets
`422 transfer_origin_not_central`. That error and the other route errors reach
the client as `{ "code", "message" }` (after the origin scope check), no longer
as a plain-text `detail` as the old "debe salir de una bodega central activa"
message did. Turning approval off lets pending documents
be withdrawn and dispatched, or approved; turning it on makes branch-route
drafts require `submit`.

Units are locked `FOR UPDATE` on submit, approve and dispatch. A handling unit
already included in another `pending_approval` or `approved` transfer is
refused with `409 transfer_handling_unit_committed`; drafts in `preparation`
do not commit units. Purchase-request demand is linked only on
`central_distribution`: lines on a branch route that send `demand_allocations`
fail with `422 transfer_demand_not_allowed_for_route` and need a line reason.
No command silently removes stock.
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

Errors added with routes and approval (revision 0114):

| Code | HTTP | When |
| --- | --- | --- |
| `transfer_route_disabled` | 409 | The route is off for the company (branch to branch or return to central); also for a saved branch transfer when both routes were turned off |
| `transfer_origin_not_central` | 422 | A new transfer leaves a non-central warehouse while both branch routes are off (unchanged contract) |
| `transfer_same_branch` | 422 | Origin and destination belong to the same branch on a branch route |
| `transfer_destination_invalid` / `transfer_origin_invalid` | 422 / 409 | The warehouse is inactive, in transit, or not eligible to store/dispatch (`storage_eligible`), on every route including `central_distribution` |
| `transfer_demand_not_allowed_for_route` | 422 | A branch-route line sends purchase-request `demand_allocations` |
| `transfer_approval_not_applicable` | 422 | `submit` on a central distribution or on a route whose approval is off |
| `transfer_approval_required` | 409 | Dispatch of a branch-route transfer that is not yet `approved` |
| `transfer_not_pending_approval` | 409 | `approve`, `reject` or `withdraw` when the transfer is not `pending_approval` |
| `transfer_approval_stale` | 409 | `expected_round` is not the current `approval_round` |
| `transfer_approval_self_forbidden` | 403 | The creator, submitter or last editor tries to approve or reject (superuser exempt) |
| `transfer_rejection_reason_required` | 422 | The rejection reason is shorter than 5 or longer than 1000 characters |
| `transfer_handling_unit_committed` | 409 | The unit is already in another `pending_approval` or `approved` transfer |
| `transfer_not_cancellable` | 409 | Cancel of a branch-route transfer that already left (central routes keep `transfer_not_in_preparation`) |

`transfer_dispatch_blocked` and `transfer_override_reason_required` come from
the dispatch compliance check, which is independent of approval.

### Transport at preparation (revision 0116)

`POST /` and `PUT /{transfer_id}` accept `driver_id` next to `vehicle_id`; both
are optional while the transfer is in `preparation`. An edit that omits them
clears them, so clients resend what they loaded. `driver_id` must be an active
driver of the company (`422 transfer_driver_unavailable`). Idempotency
fingerprints include the driver only when it is not null, so a retry from a
client that does not know the field still replays.

`GET /assignment-options?origin_warehouse_id=...&transfer_id=...` returns the
same shape as `GET /{id}/dispatch-options` (`vehicles`, `drivers`,
`origin_branch_id`, `origin_branch_name`, `planned_vehicle_id`,
`planned_driver_id`, `approved_vehicle_id`, `approved_driver_id`). The
difference is the viewpoint: while planning, a vehicle that is on the road now
or in the workshop is still offered (`available = true`) and carries a `note`,
because departure may be hours away; only a vehicle that is not `active` is
unavailable. At dispatch the option list keeps excluding vehicles that are busy
now.

```json
// POST /assignment-check
{
  "origin_warehouse_id": "<uuid>",
  "vehicle_id": "<inventory-vehicle-uuid>",
  "driver_id": "<driver-uuid>",
  "transfer_id": "<uuid or null: the saved transfer being edited>",
  "lines": [{"handling_unit_id": "<uuid>", "quantity_base": "10.000000"}]
}
```

The response (`AssignmentCheckOut`, also returned by
`GET /{id}/assignment-check`) has `vehicle_id`, `driver_id`, `vehicle_issues`
and `driver_issues` (`code`, `severity` `blocking|warning`, `message`,
`overridable`, always `false` while planning), `planning_blocked`, `warnings`,
`conflicts` (`transfer_id`, `code`, `status`, `same_vehicle`, `same_driver`,
`message`, such as "El vehículo también está asignado a TR-... (aprobado)"),
`load_kg` and `load_missing_weight`. A unit that is not in the origin warehouse
answers `422 transfer_assignment_units_invalid`. Without `lines`, the weight
comes from the saved transfer. `GET /{id}/assignment-check` adds the issue
`vehicle_required` (and `driver_required`) when the saved transfer lacks them.

Planning rules (`evaluate_dispatch(stage="planning")`):

- Only these issue codes block: `vehicle_not_active`, `vehicle_not_drivable`,
  `vehicle_branch_mismatch`, `driver_required`, `driver_branch_mismatch`,
  `driver_not_active`, `employee_not_active` and `transfer_vehicle_not_in_fleet`.
  While planning, the driver is chosen, never inferred from Fleet, so a missing
  driver is `driver_required`.
- `vehicle_overweight` blocks only when the company rule `block_overweight` is on
  and the load is known; otherwise it is a warning.
- What depends on the moment of departure (`inspection_required`,
  `vehicle_on_road`, `driver_on_road`, `vehicle_in_maintenance`,
  `vehicle_reserved`) becomes a warning with the prefix "Al despachar: ".
  Expired documents are warnings for the approver; they still block at dispatch,
  with the usual authorized exception.
- Planning conflicts are only advice: another `pending_approval` or `approved`
  transfer with the same vehicle or driver. A vehicle or driver counts as busy
  only while a transfer is on the road, that is, its status is `in_transit`,
  `partially_received` or `incident` **and** `received_at` is null. A shortage
  marked as found brings a transfer back to `partially_received` but does not
  put the vehicle back on the road.

`submit` and `approve` judge the saved transport the same way. A blocked
transport answers `409 transfer_assignment_unfit` ("El vehículo o el conductor
no es apto para el traslado: ..."). `submit` without vehicle or driver answers
`422 transfer_assignment_required` ("Elige vehículo y conductor antes de enviar
el traslado a aprobación."); if the transport changed while the request was
reviewed, `409 transfer_assignment_changed`. `submit` stores a summary of the
review (warnings, conflicting codes) in the command snapshot. `approve` of a
legacy pending transfer sent without vehicle or driver answers
`409 transfer_assignment_required` with its own message. Approving copies the
transport into `approved_vehicle_id` and `approved_driver_id`; `reject`,
`withdraw` and a new `submit` clear the copy. Central distribution never
approves, so it has no copy: the vehicle and driver chosen at preparation are
only the preselection at dispatch and can be changed without a reason.

Dispatch (`POST /{id}/dispatch`) takes two new optional fields:

```json
{
  "vehicle_id": "<vehicle-uuid>",
  "driver_id": "<driver-uuid or omitted>",
  "substitution_code": "vehicle_unfit",
  "substitution_reason": "El camión aprobado no arrancó; sale con el de respaldo.",
  "idempotency_key": "transfer-dispatch-demo-002"
}
```

The driver is the one in the request, then the one saved at preparation, then
the one assigned in Fleet (`dispatch-check` uses the same default). When the
transfer is `approved` and the vehicle or the driver differs from the approved
ones, `substitution_code` (`vehicle_unfit`, `vehicle_unavailable`,
`driver_unfit`, `driver_unavailable`, `load_change` or `other`) and a reason of
at least 10 characters are required; otherwise `422
transfer_substitution_reason_required` ("Indica por qué cambias el vehículo o el
conductor aprobado (mínimo 10 caracteres).") or `422
transfer_substitution_code_invalid`. No new approval round is needed. The four
`assignment_substitution_*` columns are stored and the dispatch is audited as
`DISPATCH_TRANSFER_SUBSTITUTION`; when it also carries a compliance exception the
action stays `DISPATCH_TRANSFER_OVERRIDE` and a separate
`DISPATCH_TRANSFER_SUBSTITUTION` entry records the change. Dispatch no longer
answers `transfer_vehicle_mismatch` for a vehicle different from the saved one.

The transfer response adds `approved_vehicle`, `approved_driver`,
`assignment_substitution` (`code`, `reason`, `by_id`, `by_name`, `at`) and
`closed_at` (set when the transfer reaches `received`, `closed_with_adjustment`
or `cancelled`).

### Reception with damage and surplus (revision 0116)

Each receipt line describes one transfer detail; the same detail still cannot
appear twice in one request:

```json
{
  "idempotency_key": "transfer-receive-demo-002",
  "lines": [{
    "transfer_detail_id": "<uuid>",
    "destination_location_id": "<receiving-location-uuid>",
    "quantity_base": "6.000000",
    "damaged_quantity": "2.000000",
    "damage_type": "crushed",
    "damage_notes": "Cajas aplastadas en la parte baja del camión",
    "damaged_location_id": "<optional-location-uuid>",
    "surplus_quantity": "1.000000",
    "surplus_notes": "Llegó una caja de más sin documento",
    "surplus_location_id": "<optional-location-uuid>",
    "evidence_reference": "FOTO-001"
  }]
}
```

`quantity_base` is what arrived in good condition (it may be `0` when
everything that arrived is damaged); `damaged_quantity` and `surplus_quantity`
default to `0`. Damage or surplus data without its quantity is rejected by the
schema (`422`). `damage_type` is one of `broken`, `crushed`, `wet`,
`contaminated`, `packaging`, `tampered`, `temperature` or `other`. The damaged
and surplus locations default to the receiving location; every location must be
an active receiving location of the destination warehouse
(`422 transfer_receipt_location_invalid`).

Line rules: `transfer_receipt_empty` (good plus damaged is zero),
`transfer_over_receipt` (good plus damaged exceeds what is pending, `409`),
`transfer_surplus_requires_full_receipt` ("Declara sobrante solo cuando
registras todo lo pendiente de la línea."), `transfer_damage_details_required`
(type and notes of at least 5 characters) and
`transfer_surplus_notes_required`, all `422` except over-receipt. A line that
has an open shortage cannot be received (`409 transfer_discrepancy_open`) until
the shortage is marked as found.

Stock: one inventory movement per receipt. The damaged part goes first, from
in transit to `damaged` stock in `damaged_location_id`, so the original unit
keeps what arrived well; then the good part goes to `quarantine`. The inventory
engine accepts a split of a labelled lot toward `damaged` (before, a partial
receipt only accepted quarantine). Neither affects valuation. A surplus does not
touch stock when it is declared. One receipt row is stored per condition
(`good` or `damaged`).

Counters: `quantity_received` is everything physically received, good or
damaged; `quantity_received_damaged` (never above received) and
`quantity_surplus` (informative) are new per line, and demand allocations gain
`quantity_damaged`. Lines also report `quantity_short_open` (declared missing
and not yet resolved) and `quantity_pending_reception` (still being waited
for). Receipt responses carry `condition`. The proportional weight estimate of
damaged units is kept (`split_estimate`), so releasing them to available stock
still requires the usual verification of measures and label.

### Discrepancy register (revision 0116)

`inventory_transfer_discrepancies` is the single register of differences, one
row per detail, kind and event. The transfer response lists them in
`discrepancies`, plus `has_open_discrepancies` and `origin_count_pending`.

| Field | Values |
| --- | --- |
| `kind` | `shortage` (stock is still in transit in the system), `surplus` (no stock in the system yet), `damage` (already `damaged` stock at the destination) |
| `source` | `receipt`, `reception_close`, `incident` (legacy loss path, stored already resolved) |
| `status` | `open` → `in_claim` (damage only) → `resolved`, or `cancelled` (`found` and `dismissed` end here) |
| `resolution` | shortage: `written_off`, `found`; damage: `written_off`, `released` (both also from claim); surplus: `regularized`, `dismissed` |

Each item has `kind`, `status`, `source`, `quantity`, `damage_type`, `notes`,
`evidence_reference`, location and handling unit (id and code), receipt and
incident ids, opened/claimed/resolved actors and timestamps, `claim_reference`,
`resolution`, `resolution_notes`, the origin count fields
(`origin_count_required`, `origin_counted_by_id/_name`, `origin_counted_at`,
`origin_count_notes`), product name, SKU, base unit and
`adjustment` (`id`, `code`, `status` of the linked adjustment).

Command bodies (all take `idempotency_key`):

| Endpoint | Body | Effect |
| --- | --- | --- |
| `close-reception` | `reason` (5 to 4000), optional `evidence_reference` | Creates one open shortage per detail for what is pending and not yet declared, with `origin_count_required`; the transfer settles to `discrepancy`. `409 transfer_reception_close_not_allowed` outside `in_transit`/`partially_received`; `409 transfer_reception_close_requires_receipt` ("Si no llegó nada, reporta una incidencia del traslado.") when nothing was received; `409 transfer_no_pending_transit` when nothing is left to declare |
| `.../adjustment` | `operational_date`, `accounting_date`, `reason`, `document_reference`, optional `notes`; surplus only: `packaging_definition_id`, `actual_gross_weight_kg`, `actual_volume_m3`, `inventory_lot_detail_id`, `documented_unit_cost` **or** `documented_total_cost` | Creates a draft adjustment built by the server from the kind: shortage, a decrease from in transit in the origin warehouse; damage, a decrease from `damaged` in the destination warehouse (where the unit is now); surplus, an increase into quarantine in the destination, at the documented cost or the average cost. Idempotent per discrepancy; one active adjustment per discrepancy. Applying it resolves the discrepancy and settles the transfer |
| `claim` | `claim_reference` (3 to 500) | Damage only; `open` → `in_claim` |
| `release` | `notes` (5 to 4000), optional `destination_location_id` | Damage only, from `open` or `in_claim`; moves the damaged unit to quarantine, in its current location or the one given inside the destination warehouse; resolution `released`. The goods are not available until their handling unit is verified and released from Almacenes |
| `found` | `notes` | Shortage only; the discrepancy ends `cancelled` with resolution `found` and the transfer goes back to `partially_received` |
| `dismiss` | `notes` | Surplus only; ends `cancelled` with resolution `dismissed` and subtracts the quantity from `quantity_surplus` |
| `origin-count` | `notes` | Records the count at the origin; only for a difference with `origin_count_required` (shortage or surplus). It never blocks closing the transfer |

A claim stops blocking the transfer: the goods remain `damaged` and can be
released or written off later. A mixed inspection (part usable, part not) has
no special command: release everything to quarantine and write the unusable part
off with an ordinary adjustment.

Release, found, dismiss and claim are refused while a draft or approved
adjustment is linked to the discrepancy (`409
transfer_discrepancy_has_adjustment`: "...: tiene el ajuste {code} en curso.
Cancela el ajuste {code} primero."). The damaged unit is followed wherever it
was moved inside the destination warehouse, and a write-off takes it from where
it is now; if it changed status, left the warehouse, was closed or consumed in
part, release and write-off answer `409 transfer_discrepancy_unit_changed`.
Audit actions: `CLOSE_TRANSFER_RECEPTION`, `CREATE_DISCREPANCY_ADJUSTMENT`,
`CLAIM_TRANSFER_DISCREPANCY`, `RELEASE_TRANSFER_DAMAGE`,
`MARK_TRANSFER_SHORTAGE_FOUND`, `DISMISS_TRANSFER_SURPLUS` and
`RECORD_TRANSFER_ORIGIN_COUNT`. The transfer command actions are `close_reception`,
`discrepancy_adjust`, `discrepancy_claim`, `discrepancy_release`,
`discrepancy_found`, `discrepancy_dismiss`, `resolve_discrepancy` and
`origin_count`; each is idempotent with the usual conflict on a different body.

### Status settlement (revision 0116)

After a dispatch, one function, `settle_transfer`, applies the pure domain rule
`settle_transfer_status` and is the only writer of the status. It receives
`uncovered_pending` (dispatched minus received, returned, adjusted out and open
shortages), whether open discrepancies exist (`in_claim` damage does not count
as open), whether any discrepancy existed (cancelled ones excluded), whether
there was a loss, whether anything was received and whether an incident is open.
In order:

1. Open incident: `incident`.
2. Something still pending: `partially_received` if something was already
   received, otherwise `in_transit`.
3. Open discrepancies: `discrepancy`.
4. A discrepancy or a loss existed: `closed_with_adjustment`.
5. Otherwise `received`.

A final state (`received`, `closed_with_adjustment`, `cancelled`) is never
reopened. `received_at` is set the first time nothing is pending (also when the
transfer ends in `discrepancy`), and `closed_at` when it reaches `received` or
`closed_with_adjustment`. Tracking archives the trip, and releases the vehicle
and driver, in `discrepancy`, `received` and `closed_with_adjustment`; the
adjustment `apply` route archives it when the loss or write-off ends the
transfer. The legacy loss path (incident plus an adjustment of the transit
quantity) still closes as `closed_with_adjustment` and now leaves a resolved
shortage with source `incident`.

Migration `0116` converts transfers that were `in_transit` with something
already received into `partially_received`.

Errors added with transport and discrepancies (revision 0116):

| Code | HTTP | When |
| --- | --- | --- |
| `transfer_assignment_required` | 422 / 409 | `submit` without vehicle or driver (422); `approve` of a legacy pending transfer without them (409) |
| `transfer_assignment_unfit` | 409 | `submit` or `approve` with a transport blocked at planning |
| `transfer_assignment_changed` | 409 | The vehicle or driver changed between the review and the `submit` |
| `transfer_assignment_units_invalid` | 422 | `assignment-check` with a unit outside the origin warehouse |
| `transfer_driver_unavailable` | 422 | The driver is not an active driver of the company |
| `transfer_substitution_reason_required` | 422 | Dispatch with another vehicle or driver than the approved ones, reason shorter than 10 characters |
| `transfer_substitution_code_invalid` | 422 | Dispatch substitution without a valid code |
| `transfer_receipt_empty` | 422 | A receipt line with no good and no damaged quantity |
| `transfer_surplus_requires_full_receipt` | 422 | Surplus declared without receiving everything pending on the line |
| `transfer_damage_details_required` | 422 | Damage without type or notes (5 characters) |
| `transfer_surplus_notes_required` | 422 | Surplus without notes (5 characters) |
| `transfer_discrepancy_open` | 409 | Receiving a line that has an open shortage |
| `transfer_reception_close_not_allowed` | 409 | `close-reception` outside `in_transit`/`partially_received` |
| `transfer_reception_close_requires_receipt` | 409 | `close-reception` when nothing has been received |
| `transfer_no_pending_transit` | 409 | `close-reception` with nothing left to declare; also resuming transit with nothing pending |
| `transfer_discrepancy_not_found` | 404 | The discrepancy does not belong to the transfer |
| `transfer_discrepancy_not_open` | 409 | The discrepancy is no longer open (or in claim, where allowed) |
| `transfer_discrepancy_action_invalid` | 409 | The action does not fit the kind (claim or release on a shortage, found on a damage, origin count where none is required) |
| `transfer_discrepancy_has_adjustment` | 409 | Release, found, dismiss or claim while a draft or approved adjustment is linked |
| `transfer_discrepancy_unit_changed` | 409 | The damaged unit changed status, left the destination warehouse, was closed or was consumed in part |
| `transfer_origin_count_already_recorded` | 409 | The origin count was already recorded |
| `transfer_incident_not_allowed` | 409 | An incident from a state other than `in_transit`/`partially_received` |
| `adjustment_transfer_discrepancy_closed` | 409 | Preparing, approving or applying an adjustment against a discrepancy that is no longer open; cancel the adjustment |
| `adjustment_linked_document_immutable` | 409 | Editing an adjustment linked to a transfer, discrepancy or correction |
| `adjustment_cost_ambiguous` | 422 | A surplus adjustment with both documented unit and total cost |
| `adjustment_surplus_measures_required` | 422 | A surplus adjustment without packaging or without weight and volume together |
| `valuation_cost_required` | 409 | Applying a surplus with no documented cost and no average cost to use |

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
`closed_with_adjustment`, not `received`. Since revision 0116 the loss is also
registered as a resolved shortage of the transfer (source `incident`).

Adjustments linked to a transfer difference (revision 0116) are created with
`POST /inventory/transfers/{id}/discrepancies/{discrepancy_id}/adjustment` (see
section 18), not with `POST /`. The adjustment response adds
`transfer_discrepancy_id`, `transfer_discrepancy_kind` (`shortage`, `surplus` or
`damage`), `transfer_reference` (code of the linked transfer, through its
incident or its discrepancy) and `linked_transfer_id` (used for the deep link
`/transfers?transfer={id}`). `transfer_id` and `transfer_incident_id` stay for
the incident path; a discrepancy adjustment for a shortage keeps `transfer_id`,
while damage and surplus adjustments carry only the discrepancy. The database
check requires either no transfer link, or a `transfer_id` with exactly one of
incident and discrepancy. A linked adjustment is immutable (`PUT` answers
`409 adjustment_linked_document_immutable`; a correction answers
`409 adjustment_correction_not_supported`): cancel the draft and prepare a new
one. There is at most one non-cancelled adjustment per discrepancy. Approving or
applying it after the discrepancy was closed another way fails with
`409 adjustment_transfer_discrepancy_closed`. Applying it resolves the
discrepancy (`written_off` for shortage and damage, `regularized` for surplus,
whose resulting handling unit is then linked to the discrepancy), records the
`resolve_discrepancy` command and settles the transfer status. A write-off of a
damage is a decrease from `damaged` stock at the average cost; a surplus enters
quarantine at the documented cost or the average cost, and
`409 valuation_cost_required` appears if there is neither. Public generic inventory movement
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

The customer routes of this block (`/sales/customers`) were replaced in revision 0119 by
`/api/v1/customers`; see «Customers with fiscal identity» below.

| Method and path | Permission | Scope and purpose |
| --- | --- | --- |
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
- The FOB of every retaceo line is taken from the purchase receipt on each create
  and update of a draft; it is not an input (`fob_lines` was removed, see
  "Retaceo with fixed amounts and without VAT" below).
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

- New `POST /retaceos` records always use `manual_entry=true`. (Superseded by
  revision 0117: the FOB comes from the invoice and import VAT no longer exists.)
  Freight and DAI are explicitly entered; no financial amounts or
  planned expenses are copied from an order. A missing fixed amount is rejected;
  explicit zero is accepted for a non-applicable charge. Other expenses start at
  zero and must be itemized through the draft editor.
- `GET /retaceos/cost-categories` requires `retaceos:manage` and returns active
  company categories for other expenses. Fixed FOB/freight/DAI/import VAT are
  excluded. Draft cost inputs accept `expense_type_id`, `incurred_on` and optional
  `source_purchase_order_expense_id`. Other expenses require category, date and
  description. Attachments are optional for every retaceo cost. An upload already
  started must finish or be removed; absence of files never blocks calculation.
  Freight, DAI and other expenses are distributed by the server proportionally
  to the invoice FOB (revision 0117); import VAT is not part of the retaceo.
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
  unique per purchase while active. Since revision 0117 the FOB can no longer be
  corrected from a retaceo (no typed FOB and no reason in `notes`; a long note no
  longer bypasses anything). Applying a retaceo whose FOB differs from the
  provisional receipt cost is rejected with `retaceo_receipt_cost_mismatch`.
  Application still appends a zero-quantity cost adjustment, retaining original
  receipt values and historic balances; it does not rewrite the closed purchase or
  earlier ledger entries. The application summary keeps `receipt_fob` and
  `documented_fob` (now always equal) and no longer has `fob_correction_reason`.
- Average comparison adds `value_only`. An already posted legacy receipt is
  projected with value adjustments and zero incoming quantity, including effects
  on intervening issues/returns. Future receipts continue showing incoming stock.
  Applied comparisons use recorded receipt or adjustment entries. This block does
  not move the final stock-posting point; that remains part of the placement block.

### Retaceo with fixed amounts and without VAT (revision 0117)

Rule (ERS p. 81-82, CA-COM-021/022/024): landed cost = FOB (fixed, from the
purchase invoice) + freight and insurance (typed fixed amount) + DAI (typed fixed
amount) + additional expenses. Every component is distributed on the server by the
FOB of each line (largest remainder at six decimals) and the unit cost is the line
total divided by its quantity. Import VAT is recoverable tax and is not part of the
retaceo. Inventory valuation is unchanged (it already excluded VAT).

Request contract (`POST /retaceos`, `PUT /retaceos/{id}`, `extra=forbid`):

- Create: `purchase_id`, optional `import_data`, `total_freight` (>= 0, required),
  `total_dai` (>= 0, required), `total_expenses` (>= 0), `notes`.
- Update: the same without `purchase_id`, plus optional `costs`. Each cost has
  `id`, `classification` (`freight`, `expense` or `dai`), `title`, `description`,
  `amount`, `expense_type_id`, `source_purchase_order_expense_id`, `incurred_on`.
  For `manual_entry` retaceos (every retaceo created through this API) at most
  one active freight cost and one active DAI cost may exist and each must equal
  its typed amount; `0` needs no cost row. Older non-manual drafts are not held to
  this rule but still have every cost distributed by FOB.
- On `calculate`, a draft whose stored FOB or cost distribution no longer matches
  the purchase receipt is rejected with `retaceo_cost_allocation_incomplete`;
  saving the draft again rebuilds both.
- Responses no longer contain `import_vat`, `calculation_mode`, `dai_rate` or
  `vat_rate`. Costs still return their server-computed `allocations`.

**Breaking change.** These now fail with `422`: the fields `calculation_mode`,
`dai_rate`, `vat_rate`, `import_vat`, `fob_lines`; `costs[].allocations`; and the
cost classification `import_vat`. The automatic (percentage) mode, the manual FOB
and the historical FOB correction with a reason were removed.

Removed error codes: `retaceo_import_vat_invalid`, `retaceo_import_vat_not_allocated`,
`retaceo_automatic_fob_locked`, `retaceo_fob_required`, `retaceo_fob_lines_invalid`,
`retaceo_fob_invalid`, `retaceo_historical_fob_locked`, `retaceo_calculation_invalid`.
Messages changed for `retaceo_fixed_amount_invalid`, `retaceo_fixed_amount_mismatch`,
`retaceo_fixed_category_invalid`, `retaceo_expense_category_invalid`,
`retaceo_cost_allocation_incomplete` and `actual_expense_fixed_category`.
The retaceo export no longer has the VAT column.

## DTE issuer settings (revision 0118)

Base of the sales area plan, block V1a (`docs/plan-area-ventas-el-salvador.pdf`,
section 6.5). Every company is an independent DTE issuer: all endpoints resolve the
company from `X-Company-ID` and never read or write another company's settings.
Hacienda catalogs are the only global data.

Permissions: `fiscal_settings:read` (GET) and `fiscal_settings:manage` (writes);
catalogs use `reference_data:read`. Every write is audited with resource type
`fiscal_profile`, `fiscal_activity`, `fiscal_establishment`, `fiscal_point_of_sale`
or `fiscal_document_type`, with before and after states.

| Method | Path | Purpose |
|---|---|---|
| GET | `/fiscal/catalogs` | The 33 Hacienda catalogs (version 1.1, July 2026): code and title. |
| GET | `/fiscal/catalogs/{CAT-xxx}?group=&search=&limit=` | Items of one catalog. `group` is the department code in CAT-008 and CAT-013 and the section (`summary`, `body`, `informative`) in CAT-015. `search` matches code or name, ignoring accents. `limit` 1 to 1000. |
| GET / PUT | `/fiscal/profile` | Issuer profile: `taxpayer_category` (`large`, `medium`, `other`), `person_type` (`1`, `2`), `operating_mode` (`simulated`, `test`, `production`), `dte_email`, `dte_phone`. The response adds the company name, NIT and NRC and `production_blockers` (Spanish reasons). |
| GET / POST | `/fiscal/activities` | Economic activities (CAT-019). The first one becomes primary. |
| POST | `/fiscal/activities/{id}/primary` | Mark the primary activity. |
| DELETE | `/fiscal/activities/{id}` | Remove an activity not used by an establishment. |
| GET | `/fiscal/branch-options` | Branches of the company and the establishment each one already has. |
| GET / POST | `/fiscal/establishments` | Establishments with address, Hacienda codes and points of sale. One per branch. |
| GET / PATCH | `/fiscal/establishments/{id}` | Detail and edition (`establishment_type`, `code`, `activity_id`, `is_active`). |
| POST | `/fiscal/establishments/{id}/points-of-sale` | New point of sale (`code`, `name`). |
| PATCH | `/fiscal/points-of-sale/{id}` | Edit a point of sale (`code`, `name`, `is_active`). |
| GET | `/fiscal/document-types` | The 13 CAT-002 types with `is_enabled`, `certification_status` and `certified_at`. |
| PUT | `/fiscal/document-types/{code}` | Enable a type or change its certification (`pending`, `in_progress`, `approved`). |

Rules:

- Establishment code: the type letter plus three digits (`M` headquarters 02, `S`
  branch 01, `B` warehouse 04, `P` yard 07), unique in the company. Point of sale:
  `P` plus three digits, unique in its establishment. Both form the control number
  `DTE-TT-S001P001-…`, so another company may reuse them.
- The DTE address of an establishment is its branch address, with the Hacienda
  department, municipality and district codes (`address.complete` is false when a
  code is missing).
- In `production` a type can be enabled only when its certification is `approved`.
- Moving to `production` requires NIT, NRC, a primary activity, an active
  establishment with an active point of sale and at least one enabled document, all
  certified. While in production, any change that breaks one of those conditions is
  rejected and nothing is saved.

Error codes (`422` unless noted): `fiscal_catalog_unknown` (404),
`fiscal_activity_code_invalid`, `fiscal_activity_unknown`,
`fiscal_activity_duplicate` (409), `fiscal_activity_in_use` (409),
`fiscal_activity_not_found` (404), `fiscal_branch_not_found` (404),
`fiscal_branch_already_establishment` (409), `fiscal_establishment_code_invalid`,
`fiscal_establishment_code_type_mismatch`, `fiscal_establishment_code_duplicate` (409),
`fiscal_establishment_not_found` (404), `fiscal_point_of_sale_code_invalid`,
`fiscal_point_of_sale_code_duplicate` (409), `fiscal_point_of_sale_not_found` (404),
`fiscal_document_type_invalid`, `fiscal_document_not_certified`,
`fiscal_production_not_ready`, `fiscal_production_would_break`,
`fiscal_company_not_found` (404).

## Customers with fiscal identity (revision 0119)

Sales area block V1b. Replaces `/api/v1/sales/customers`. Routes live in
`/api/v1/customers`, resolve the company from `X-Company-ID` and use
`sales_customers:read` (GET) and `sales_customers:manage` (writes). Every write is
audited as `sales_customer` or `sales_customer_delivery_address`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/customers?search=&customer_type=&active=&include_generic=&page=&size=` | List. `search` matches code, name, commercial name and, with 3 or more digits, NIT, DUI or NRC. Generic customers are hidden unless `include_generic=true`. |
| POST | `/customers` | Create. `code` is optional (the server proposes `CLI-00001`, `CLI-00002`…); `customer_type` defaults to `final_consumer`. |
| GET | `/customers/seller-options?search=` | Active employees of the company that can be assigned as the customer's seller (`id`, `code`, `name`, `position`). Uses `sales_customers:read`, so the customer screen does not need `employees:read`. |
| GET | `/customers/generic?branch_id=` | The branch's generic «Consumidor final» customer; created the first time (code `CF-<branch code>`). |
| GET | `/customers/{id}` | Customer file with delivery addresses. |
| PUT | `/customers/{id}` | Replace the customer data. |
| PATCH | `/customers/{id}/status` | `{"is_active": bool}`. Inactive customers cannot be quoted or sold to. |
| POST | `/customers/{id}/delivery-addresses` | Add a delivery address; the first active one becomes the default. |
| PUT / DELETE | `/customers/{id}/delivery-addresses/{address_id}` | Edit or remove a delivery address. |

Body fields: `customer_type` (`final_consumer`, `taxpayer`, `foreign`), `name`,
`person_type` (`1`, `2`), `taxpayer_category` (required for taxpayers: `large`,
`medium`, `other`), `is_withholding_agent`, `commercial_name`, `document_type`
(CAT-022: `36` NIT, `13` DUI, `02`, `03`, `37`) with `document_number`, `nrc`,
`activity_code` (CAT-019), `geography` (`department_id`, `municipality_id`,
`district_id`), `address_line`, `country_code` (CAT-020, foreign customers only),
`phone`, `email`, `credit_days` (0 to 365), `credit_limit`, `seller_employee_id`.

Rules:

- NIT is stored as 14 or 9 digits and DUI as 9 digits, without dashes; NRC as 2 to 8
  digits. Document and NRC are unique per company.
- The response adds `receivable_documents` (CAT-002 codes the customer can receive
  today) and `tax_credit_missing` (Spanish reasons). Tax credit (`03`) needs a taxpayer
  with NIT or DUI, NRC, activity and a complete address whose district has Hacienda
  codes. Foreign customers receive export invoices (`11`); everyone else, invoices
  (`01`).
- `seller_employee_id` must be an active employee of the same company; the response adds
  `seller_name`.
- Generic customers cannot be edited, deactivated or given delivery addresses.

Error codes (`422` unless noted): `customer_name_required`,
`customer_taxpayer_category_required`, `customer_document_incomplete`,
`customer_taxpayer_document_invalid`, `customer_nit_invalid`, `customer_dui_invalid`,
`customer_document_invalid`, `customer_nrc_invalid`, `customer_activity_invalid`,
`customer_activity_unknown`, `customer_country_required`, `customer_country_unknown`,
`customer_country_not_foreign`, `customer_foreign_geography`, `customer_geography_invalid`,
`customer_credit_days_invalid`, `customer_credit_limit_invalid`, `customer_generic_locked`,
`customer_delivery_label_required`, `customer_delivery_line_required`,
`customer_delivery_coordinates_invalid`, `customer_delivery_default_inactive`,
`customer_document_duplicate` (409), `customer_nrc_duplicate` (409),
`sales_customer_code_exists` (409), `sales_customer_not_found` (404),
`customer_branch_not_found` (404), `customer_seller_not_found` (404),
`customer_delivery_not_found` (404).

## Product fiscal classification and Hacienda units (revision 0120)

Sales area block V1c. Every product of every company declares how it goes on a DTE line,
and every unit enabled in a company has its Hacienda unit of measure (CAT-014).

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/product-fiscal/options` | `products:read` | CAT-015 taxes a product can carry (without IVA `20` and `C3`) and CAT-014 units. Lives outside `/products/...` because `/products/{product_id}` takes an integer. |
| GET | `/products/{product_id}/fiscal` | `products:read` | `tax_treatment`, `dte_item_type` (override or `null`), `effective_item_type`, `additional_taxes`, `sale_unit` with its Hacienda code and `billing_issues` (Spanish). |
| PUT | `/products/{product_id}/fiscal` | `products:fiscal` | Body: `tax_treatment` (`taxed`, `exempt`, `not_subject`), optional `dte_item_type` (`1`, `2`, `3`), `additional_tax_codes`. Audited as `product_fiscal`. |
| GET | `/fiscal/units` | `fiscal_settings:read` | The company's units with `hacienda_unit_code` (stored or `null`), `suggested_code` and `effective_code`. |
| PUT | `/fiscal/units/{unit_id}` | `fiscal_settings:manage` | Body: `hacienda_unit_code` (CAT-014 code or `null` to use the suggestion). Audited as `fiscal_unit`. |

Rules: the item type defaults to goods (`1`) or services (`2`) from `product_kind`;
additional taxes are normalized to upper case, must exist in CAT-015, cannot be IVA and
are only allowed on taxed products. Suggested units: UNIT 59, KILOGRAM 34, GRAM 39,
POUND 36, LITER 23, MILLILITER 26, GALLON 22, METER 1, everything else 99 («Otra»).

Error codes (`422` unless noted): `product_fiscal_taxes_require_taxed`,
`product_fiscal_tax_is_iva`, `product_fiscal_tax_unknown`, `fiscal_unit_code_unknown`,
`product_not_found` (404), `fiscal_unit_not_found` (404).

## Personal data protection (revision 0121)

Sales area block V1d. Compliance with the Ley para la Protección de Datos Personales
(D.L. 144/2024, reformed by D.L. 659/2026) for the company's customers: the privacy notice,
consents for optional uses, ARCO-POL requests of data subjects, anonymization and security
incidents. Every write is audited; every read and write is scoped by `X-Company-ID`.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/privacy/notice` | `privacy:read` or `sales_customers:read` | Current published notice or `null`. |
| GET | `/privacy/notices` | `privacy:read` | Every version, newest first. |
| GET | `/privacy/notice-template` | `privacy:manage` | `title`, a `body` filled with the company's name, address, email and phone, and the nine `elements` of art. 24. |
| POST | `/privacy/notices` | `privacy:manage` | Body: `title`, `body` (at least 200 characters), `covered_elements` (all nine keys). Publishes the next version; earlier ones stay. Audited as `privacy_notice`. |
| GET | `/customers/{id}/consents` | `sales_customers:read` | Consents of a customer, active and revoked. |
| POST | `/customers/{id}/consents` | `sales_customers:manage` | Body: `purpose` (`marketing`, `profiling`, `third_party_sharing`), `channel` (`in_person`, `phone`, `email`, `web`, `written`), optional `notes`. Stores the current notice version. Audited as `customer_consent`. |
| POST | `/customers/{id}/consents/{consent_id}/revoke` | `sales_customers:manage` | Body: `channel`. |
| GET | `/privacy/requests?scope=open,closed,all` | `privacy:read` | Requests with `effective_due_on` and `overdue`. `scope` takes one of the three values. |
| GET | `/privacy/assignee-options` | `privacy:manage` | Active users of the company. |
| POST | `/privacy/requests` | `privacy:manage` | Body: optional `customer_id`, `requester_name`, optional `requester_document`, `response_channel`, `right_type` (`access`, `rectification`, `cancellation`, `opposition`, `portability`, `erasure`, `restriction`), `description`, `received_on` (not in the future), optional `assignee_id`. Code `SOL-00001`. Audited as `data_subject_request`. |
| GET | `/privacy/requests/{id}` | `privacy:read` | One request. |
| POST | `/privacy/requests/{id}/actions` | `privacy:manage` | Body: `action` (`start`, `request_correction`, `correction_received`, `extend`, `resolve`, `deny`, `return`, `archive`), `text`, `extension_reason`. |
| PUT | `/privacy/requests/{id}/assignee` | `privacy:manage` | Body: `assignee_id` or `null`. |
| GET | `/privacy/customers/{id}/export` | `privacy:manage` | JSON with the customer, delivery addresses, consents, quotations and sales. Audited as `EXPORT`. |
| POST | `/privacy/customers/{id}/anonymize` | `privacy:erase` | Body: `request_id` of a cancellation or erasure request in process for that customer. Returns 204. Audited as `ANONYMIZE`. |
| GET | `/privacy/incidents` | `privacy:read` | Incidents with `notification_deadline` (discovery + 72 h). |
| POST | `/privacy/incidents` | `privacy:manage` | Body: `discovered_at`, `occurred_at`, `description`, `data_categories`, `affected_count`, `measures` and the notifications to ACE, Fiscalía and subjects (date and reference) or `subjects_not_required_reason`. Code `INC-00001`. |
| PUT | `/privacy/incidents/{id}` | `privacy:manage` | Same body; only while open. |
| POST | `/privacy/incidents/{id}/close` | `privacy:manage` | Requires the ACE and Fiscalía notifications and the subjects' notification or its reason. |

Request deadlines, in business days of El Salvador (weekends and the holidays of the
Código de Trabajo, art. 190, are skipped): answer within 20 (art. 20), extendable once by 20
with a reason; correction requested from the subject within 10 (art. 18); archiving only
after that term. `resolve`, `deny`, `return` and `archive` need a text of at least 10
characters, which is stored as the resolution.

Anonymization replaces the name with «Titular anonimizado CLI-…», clears identity, contact,
address and seller, deletes the delivery addresses, revokes the active consents and
deactivates the customer with `anonymized_at`. Issued quotations, sales and fiscal documents
are kept, as the tax law requires. An anonymized customer cannot be edited or reactivated
(`customer_anonymized_locked`).

Error codes: `privacy_notice_title_required`, `privacy_notice_body_too_short`,
`privacy_notice_element_unknown`, `privacy_notice_incomplete`, `privacy_notice_missing`,
`privacy_consent_already_granted`, `privacy_consent_already_revoked`,
`privacy_request_future_date`, `privacy_request_action_invalid`,
`privacy_request_extension_reason_required`, `privacy_request_correction_note_required`,
`privacy_request_resolution_required`, `privacy_request_archive_too_early`,
`privacy_request_customer_mismatch`, `privacy_erasure_request_required`,
`privacy_customer_already_anonymized`, `privacy_assignee_not_found`,
`privacy_incident_description_required`, `privacy_incident_data_required`,
`privacy_incident_dates_invalid`, `privacy_incident_future_date`, `privacy_incident_closed`,
`privacy_incident_notifications_missing`, `customer_anonymized_locked`; not found (404):
`privacy_request_not_found`, `privacy_consent_not_found`, `privacy_incident_not_found`,
`privacy_company_not_found`, `sales_customer_not_found`.

## Sales tax calculation (block V2a)

One calculation engine (`app/domain/entities/sales_tax.py`) computes the fiscal amounts of
every sales document; quotation, order, point of sale and DTE all call it. This endpoint
previews a calculation without storing anything, so it writes no audit record.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/sales/tax-calculation` | `sales_quotations:read` or `sales:read` | Body: `document_type` (`01` invoice, `03` tax credit), optional `customer_id`, `lines` (`product_id`, `quantity`, `unit_price`, `price_includes_vat`, optional `discount` for the whole line) and optional `global_discounts` (`taxed`, `exempt`, `not_subject`). Returns each line in the document's price convention and the summary. |

The issuer category comes from the fiscal profile, the customer's category and withholding
flag from the customer, and each line's VAT treatment and item type from the product's
fiscal classification. The caller cannot override them.

Response: `prices_include_vat` (`true` for the invoice), `lines` (`unit_price`, `discount`,
`not_subject`, `exempt`, `taxed` with 8 decimals; `vat_item` on the invoice only,
`hacienda_unit_code`) and `summary` (`total_not_subject`, `total_exempt`, `total_taxed`,
`subtotal_sales`, global discounts, `total_discount`, `subtotal`, `vat`, `vat_perceived`,
`vat_withheld`, `total_operation`, `total_to_pay`, `total_in_words`), with 2 decimals.

Rules (Manual Funcional v2.0, chapters XVIII and XXI; Código Tributario arts. 162 and 163):
- prices are converted with ÷ 1.13 or × 1.13; lines round half up to 8 decimals, the summary
  to 2;
- invoice VAT is contained in the price; tax credit VAT is 13 % of the taxed amount net of
  the global taxed discount;
- 1 % withholding when the customer is a large taxpayer or a withholding agent, the issuer
  is not a large taxpayer and the taxed base without VAT reaches $100;
- 1 % perception on a tax credit when the issuer is a large taxpayer, the customer is not,
  and the taxed goods base reaches $100;
- `total_operation` = subtotal + added VAT + perception − withholding.

Error codes (`422` unless noted): `sales_tax_document_disabled`,
`sales_tax_customer_required`, `sales_tax_customer_inactive`,
`sales_tax_document_not_receivable`, `sales_tax_credit_requires_taxpayer`,
`sales_tax_product_not_sellable`, `sales_tax_additional_unsupported`,
`sales_tax_untaxed_price_with_vat`, `sales_tax_lines_required`,
`sales_tax_quantity_invalid`, `sales_tax_price_invalid`, `sales_tax_discount_invalid`,
`sales_tax_discount_exceeds_line`, `sales_tax_global_discount_exceeds`; not found (404):
`sales_customer_not_found`, `product_not_found`.

## Sales price lists (revision 0122, block V2b)

Each company defines its price lists (for example «Mostrador» with VAT and «Mayoreo» without
VAT). One list is the default. A price is set per product (or variant) and selling unit, from
a date, and optionally for one branch only. Prices are never edited: a new price closes the
one in force the day before, so the history answers which price applied on any day.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/price-lists` | `price_lists:read`, `sales_customers:read` or `sales:read` | The company's lists, default first, with `price_count` and `customer_count`. |
| POST | `/price-lists` | `price_lists:manage` | Body: `code` (1–20 letters, digits or hyphens, stored upper case), `name`, `description`, `prices_include_vat`, `is_default`, `is_active`. The first list becomes the default. Audited as `price_list`. |
| GET | `/price-lists/{id}` | `price_lists:read` | One list. |
| PUT | `/price-lists/{id}` | `price_lists:manage` | Same body. Marking a list as default unmarks the previous one; the default cannot be unmarked directly. |
| GET | `/price-lists/sellable-units?search=` | `price_lists:read` | Active, sellable products (and variants) with their base unit and current packaging units (`factor` to the base unit). A product without inventory item that is not goods uses its sale unit. |
| GET | `/price-lists/{id}/prices?search=&branch_id=&on=` | `price_lists:read` | Each sellable unit with the `current` price for that branch and day (the branch price wins over the general one), the `next` scheduled change and `branch_overrides`. |
| GET | `/price-lists/{id}/history?product_id=&unit_id=&variant_id=` | `price_lists:read` | Every price of that product and unit in the list, all branches, with `status` (`scheduled`, `current`, `expired`). |
| POST | `/price-lists/{id}/prices` | `price_lists:manage` | Body: `product_id`, `variant_id`, `unit_id`, `branch_id` (null = all branches), `price` (8 decimals), `valid_from` (today by default; never in the past). Audited as `price_list_item`. |
| POST | `/price-lists/items/{entry_id}/end` | `price_lists:manage` | Body: `ends_on` (today or later). A branch price that ends falls back to the general price. |
| DELETE | `/price-lists/items/{entry_id}` | `price_lists:manage` | Cancels a scheduled price; the previous one gets its end date back. Returns 204. |
| GET | `/sales/prices/resolve?product_id=&unit_id=&variant_id=&customer_id=&branch_id=&on=` | `price_lists:read`, `sales_quotations:read` or `sales:read` | The price for a customer at a branch and date: the customer's list if active, otherwise the default list. Returns `found`, `price`, `prices_include_vat`, `price_list_id`, `price_list_name`, `source` (`customer` or `default`), `branch_specific`, `entry_id`, `valid_to` and a Spanish `message` when there is no price. |

Customers gain `price_list_id` (input and output) and `price_list_name` (output). The list
must belong to the company and be active (`customer_price_list_invalid`).

Error codes (`422` unless noted): `price_list_code_invalid`, `price_list_name_required`,
`price_list_default_inactive`, `price_list_default_required`, `price_list_code_taken` (409),
`price_list_price_invalid`, `price_list_backdated`, `price_list_future_exists` (409),
`price_list_unit_invalid`, `price_list_not_scheduled`, `price_list_already_ended`,
`price_list_end_invalid`, `customer_price_list_invalid`; not found (404):
`price_list_not_found`, `price_list_entry_not_found`, `price_list_product_not_sellable`,
`branch_not_found`, `sales_customer_not_found`.

## Sales margins and discounts (revision 0123, block V2c)

Margin is measured on the price without VAT: `(price − cost) ÷ price`. The cost is the inventory
average cost (it already includes the retaceo) × the unit factor. Suggested price without VAT =
`cost ÷ (1 − target margin)`; ×1.13 for a list with VAT, rounded to the cent.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/price-lists/{id}/prices` | `price_lists:read` | Now also returns `cost`, `margin_percent`, `target_margin_percent`, `suggested_price`, `below_cost` and `below_target` — only for users with `sales_costs:read`; otherwise they are `null`/`false`. |
| POST, PUT | `/price-lists`, `/price-lists/{id}` | `price_lists:manage` | Accept `target_margin_percent` (0–95, optional). |
| GET | `/price-lists/categories` | `price_lists:read` | Product categories of the company. |
| GET | `/price-lists/{id}/category-margins` | `price_lists:read` | Target margin per category inside the list. |
| PUT | `/price-lists/{id}/category-margins` | `price_lists:manage` | Body: `margins` (`category_id`, `target_margin_percent`); replaces them. Audited as `price_list_category_margins`. |
| GET | `/price-lists/{id}/volume-discounts` | `price_lists:read` | Volume tiers with `status`. |
| POST | `/price-lists/{id}/volume-discounts` | `price_lists:manage` | Body: `product_id`, `variant_id`, `unit_id`, `min_quantity` (> 0), `discount_percent` (> 0, ≤ 100), `valid_from` (today by default). A new tier for the same product, unit and quantity closes the one in force the day before. Audited as `sales_volume_discount`. |
| DELETE | `/price-lists/volume-discounts/{scale_id}` | `price_lists:manage` | Cancels a scheduled tier or ends a current one today. Returns 204. |
| GET | `/sales/discount-policies` | `sales_discounts:manage` | Every role of the company with `max_line_discount_percent`, `max_global_discount_percent` and `configured`. |
| PUT | `/sales/discount-policies/{role_id}` | `sales_discounts:manage` | Sets the limits of a role. Audited as `sales_discount_policy`. |
| GET | `/sales/my-discount-policy` | `sales_quotations:read`, `sales:read` or `price_lists:read` | Effective limits of the current user: the maximum of their roles; none without policies; unlimited for superusers. |
| POST | `/sales/discount-evaluation` | same as above | Body: optional `customer_id`, `branch_id`, `on`, `global_discount_percent`, and `lines` (`product_id`, `variant_id`, `unit_id`, `quantity`, optional `discount_percent`). Each line returns the resolved list price, the suggested discount (customer or volume, the larger one, never both added), the applied discount, `net_price`, `cost` and `margin_percent` (only with `sales_costs:read`), and `reasons` (`discount_above_limit`, `below_cost`) with Spanish messages. Also returns `global_reasons` and `requires_authorization`. |

Customers gain `discount_percent` (0–100, default 0).

Error codes (`422` unless noted): `sales_margin_target_invalid`, `sales_volume_quantity_invalid`,
`sales_volume_percent_invalid`, `sales_volume_backdated`, `sales_volume_future_exists` (409),
`sales_volume_expired`, `sales_policy_invalid`, `sales_discount_percent_invalid`,
`customer_discount_invalid`, `price_list_unit_invalid`; not found (404):
`price_list_category_not_found`, `sales_volume_not_found`, `sales_policy_role_not_found`,
`sales_customer_not_found`.

## Sales quotations (revision 0124, block V2d)

The quotation replaces the B06 one. On every draft save the server resolves the list price of
each line (customer list or the default one, branch and date), applies the suggested or typed
discount, evaluates it against the user's limits and runs the tax engine. Prices, costs and
totals are stored: a later change of list or cost does not alter the quotation.

States: `draft` → `pending_authorization` (only if a line or the global discount exceeds the
user's limit or a line falls below cost) → `issued` → `accepted` / `rejected`; `cancelled` from
any open state. `expired` is not stored: an issued quotation whose `valid_until` passed comes
with `expired: true` and cannot be accepted.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/quotations` | `sales_quotations:read` | Paged list in the user's branches. Filters: `branch_id`, `customer_id`, `status` (`draft`, `pending_authorization`, `issued` = in force, `expired`, `accepted`, `rejected`, `cancelled`), `from_date`, `to_date`. |
| POST | `/sales/quotations/preview` | `sales_quotations:manage` | Same body as create; calculates without saving. |
| POST | `/sales/quotations` | `sales_quotations:manage` | Header `Idempotency-Key`. Body: `branch_id`, `customer_id`, optional `document_type` (`01`/`03`; proposed from the customer), optional `valid_until` (today + company validity days), `global_discount_percent`, `notes`, `lines` (`product_id`, `variant_id`, `unit_id`, `quantity`, optional `discount_percent` — the suggested one when missing — and optional `manual_price`, which needs `sales_prices:override`). |
| GET | `/sales/quotations/{id}` | `sales_quotations:read` | Detail. Lines carry list price, applied price, discounts, fiscal amounts and authorization reasons. `cost` and `margin_percent` come only for users with `sales_costs:read` or `sales_discounts:authorize`. |
| PUT | `/sales/quotations/{id}` | `sales_quotations:manage` | Draft only; body of create plus `expected_version`. Recalculates everything. A user without `sales_prices:override` may keep, unchanged, manual prices already in the draft. |
| GET | `/sales/quotations/{id}/pdf` | `sales_quotations:read` | Printable version (never shows cost or margin). |
| POST | `/sales/quotations/{id}/issue` | `sales_quotations:confirm` | Re-evaluates with the issuer's limits: `issued` or `pending_authorization`. |
| POST | `/sales/quotations/{id}/authorize` | `sales_discounts:authorize` | Optional `note`. The authorizer's own limits must cover every reason; below-cost lines need a role that may sell below cost. |
| POST | `/sales/quotations/{id}/return` | `sales_discounts:authorize` | `reason` (≥ 3 characters): back to draft. |
| POST | `/sales/quotations/{id}/accept` | `sales_quotations:confirm` | Issued and in force only. |
| POST | `/sales/quotations/{id}/reject` | `sales_quotations:confirm` | `reason` (≥ 3 characters). Allowed after expiry. |
| POST | `/sales/quotations/{id}/cancel` | `sales_quotations:confirm` | `reason` (≥ 3 characters). Not after conversion. |
| POST | `/sales/quotations/{id}/order` | `sales_quotations:convert` | Accepted only. Replaced the B06 `convert` in V2e: creates the sales order (see "Sales orders"). |
| GET | `/sales/settings/quotations` | `sales_quotations:read` or `fiscal_settings:read` | `quotation_validity_days`. |
| PUT | `/sales/settings/quotations` | `fiscal_settings:manage` | `quotation_validity_days` (1–365). Audited as `SALES_SETTINGS_UPDATED`. |

Every action is audited on `sales_quotation` (`SALES_QUOTATION_CREATED`, `_UPDATED`, `_ISSUED`,
`_SUBMITTED_FOR_AUTHORIZATION`, `_AUTHORIZED`, `_RETURNED`, `_ACCEPTED`, `_REJECTED`,
`_CANCELLED`) with, per line, list price, applied price, manual flag, discount, cost, margin and
reasons.

Error codes (`422` unless noted): `sales_quote_status_invalid`, `sales_quote_price_missing`,
`sales_quote_price_override_forbidden`, `sales_quote_authority_insufficient`,
`sales_quote_expired`, `sales_quote_validity_invalid`, `sales_quote_reason_required`,
`sales_quote_converted`, `sales_quote_not_convertible`, `sales_quote_lines_required`,
`sales_tax_document_disabled`, `sales_tax_document_not_receivable`, `sales_customer_inactive`,
`sales_branch_inactive`; `sales_quote_version_conflict` and
`sales_idempotency_payload_conflict` (409); `sales_quotation_not_found` (404).

## Sales orders (revision 0125, block V2e)

The B06 sale is reworked in place as the **sales order**: same `/sales` routes and tables
(`sales`, `sales_lines`), so deliveries and returns keep working. Order ids use a UUID path
convertor, so `/sales/returns` and `/sales/deliveries` are not captured.

An order is created directly (same pricing as the quotation: list price, suggested discount,
limits and tax engine) or from an **accepted** quotation, whose lines, prices and totals are
copied as accepted. While it is not edited, such an order keeps the quotation's authorization.

States: `draft` → `pending_authorization` (only if it exceeds the confirmer's limits) →
`confirmed`; `cancelled` from any open state without confirmed deliveries.

**Commercial reservation.** Confirming checks, per branch and inventory item (advisory lock),
that `available to sell = available handling units in the branch's active non-transit
warehouses − pending quantity of other confirmed orders` covers the order. Nothing physical
moves; deliveries consume the reservation and cancelling releases it. Transfers and
adjustments do not respect reservations yet.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales` | `sales:read` | Paged list in the user's branches. Filters: `branch_id`, `customer_id`, `status`, `from_date`/`to_date` (promised date). |
| POST | `/sales/preview` | `sales:manage` | Calculates without saving; open orders return `available_base` per line. |
| POST | `/sales` | `sales:manage` | Header `Idempotency-Key`. Body: the quotation draft fields (without `valid_until`) plus `promised_date` (not in the past), `delivery_mode` (`pickup`/`delivery`) and `delivery_address_id` (required for delivery, an active address of the customer). Payment terms come from the customer (`credit_days` > 0 → credit). |
| POST | `/sales/quotations/{id}/order` | `sales_quotations:convert` | Header `Idempotency-Key`. Body: `promised_date`, `delivery_mode`, `delivery_address_id`, `notes`. One order per quotation (returns the existing one). |
| GET | `/sales/{id}` | `sales:read` | Detail with fiscal totals, delivery data, `quantity_delivered_base`, `quantity_pending_base` and, while open, `available_base`. Cost and margin only with `sales_costs:read` or `sales_discounts:authorize`. |
| PUT | `/sales/{id}` | `sales:manage` | Draft only; recalculates and drops an inherited authorization. |
| POST | `/sales/{id}/confirm` | `sales:confirm` | Confirms and reserves, or sends to authorization. |
| POST | `/sales/{id}/authorize` | `sales_discounts:authorize` | Optional `note`; the authorizer's own limits must cover the order; then reserves and confirms. |
| POST | `/sales/{id}/return` | `sales_discounts:authorize` | `reason`: back to draft. |
| POST | `/sales/{id}/cancel` | `sales:cancel` | `reason`; not with confirmed deliveries. Releases the reservation. |

The B06 endpoints `POST /sales/quotations/{id}/convert` and the line-price edit of a draft sale
were removed. `GET /sales/catalog` now also accepts `sales:manage`.

Audited on `sale`: `SALES_ORDER_CREATED`, `_CREATED_FROM_QUOTATION`, `_UPDATED`, `_CONFIRMED`,
`_SUBMITTED_FOR_AUTHORIZATION`, `_AUTHORIZED`, `_RETURNED`, `_CANCELLED`.

Error codes (`422` unless noted): `sales_order_status_invalid`, `sales_order_stock_insufficient`,
`sales_order_has_deliveries`, `sales_order_promised_date_past`, `sales_order_address_required`,
`sales_order_address_not_allowed`, `sales_order_address_invalid`,
`sales_order_reason_required`, `sales_quote_not_convertible`; `sales_order_version_conflict`
(409); `sales_order_not_found` (404).


## Sales invoices (revision 0126, block V3b)

A **confirmed** order is invoiced as a whole: one fiscal document (`01` factura or `03` crédito
fiscal, the order's `document_type`) at any moment after confirmation, before, during or after
delivering. The ERP owns the sale and the tax calculation; the DTE service (`dte-service`,
contract v2) builds, signs and transmits the DTE, and the ERP keeps its copy (issuer snapshot,
request, JSON, seal, PDF).

**Issuing is asynchronous.** `POST /sales/{id}/invoice` validates the order, builds the issuer
snapshot (company identity, the establishment of the order's branch and the chosen point of
sale, with the SHA-256 of its canonical JSON), the receiver, the lines and the summary, checks
that the request reconciles to the cent with the stored totals, and saves the document as
`pending`. The `dte-worker` registers the company in the service (`PUT /api/emisores/:nit`),
issues with the document's `Idempotency-Key` (`erp-{document id}`), downloads the JSON and the
PDF into object storage and compares the returned summary with the order. A reconcile job
re-enqueues stale `pending` documents every `DTE_RECONCILE_SECONDS`.

States: `pending` → `simulated` (simulated mode), `issued` (sealed by Hacienda) or `rejected`;
`failed` when the service refuses for good or attempts run out (`DTE_MAX_ATTEMPTS`). An order has
at most one non-failed document; an invoiced order cannot be cancelled (`sales_order_invoiced`)
until credit notes and invalidation arrive (V4).

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/{id}/invoice-options` | `sales_invoices:read` | Points of sale of the branch's establishment, mode, `blockers` (what is missing, in Spanish) and the current document. |
| POST | `/sales/{id}/invoice` | `sales_invoices:issue` | Body `{"point_of_sale_id": uuid \| null}` (optional when the establishment has one active point of sale). `202` with the new `pending` document; `200` with the existing one when the order is already invoiced. |
| GET | `/sales/fiscal-documents` | `sales_invoices:read` | Paged inbox in the user's branches. Filters: `branch_id`, `sale_id`, `status`, `document_type`, `q` (control number, order code or customer). |
| GET | `/sales/fiscal-documents/{id}` | `sales_invoices:read` | One document: status, control number, generation code, seal, attempts, last error, `has_json`, `has_pdf`. |
| POST | `/sales/fiscal-documents/{id}/retry` | `sales_invoices:issue` | Back to `pending` with the same idempotency key and payload (only `pending` or `failed`). |
| GET | `/sales/fiscal-documents/{id}/json` | `sales_invoices:read` | The DTE JSON as delivered by the service (attachment). `409` until issued. |
| GET | `/sales/fiscal-documents/{id}/pdf` | `sales_invoices:read` | `{"url"}`: presigned link to the PDF. `409` until issued. |

Audited on `sales_fiscal_document`: `ISSUE_FISCAL_DOCUMENT`, `RETRY_FISCAL_DOCUMENT` (user) and
`FISCAL_DOCUMENT_ISSUED`, `_REJECTED`, `_FAILED` (worker).

Error codes (`422` unless noted): `sales_invoice_order_not_confirmed`,
`sales_invoice_document_unsupported`, `sales_invoice_document_disabled`,
`sales_invoice_establishment_missing`, `sales_invoice_point_of_sale_required`,
`sales_invoice_point_of_sale_missing`, `sales_invoice_point_of_sale_invalid`,
`sales_invoice_issuer_incomplete`, `sales_invoice_receiver_incomplete`,
`sales_invoice_totals_mismatch`, `sales_invoice_not_retryable`, `sales_invoice_already_issued`,
`sales_invoice_service_unavailable`; `sales_invoice_not_ready` (409); `sales_invoice_not_found`
(404). A document whose returned summary differs from the order keeps its status and carries
`error_code = dte_totals_mismatch` for review.

Configuration: `DTE_SERVICE_URL` (empty disables invoicing), `DTE_SERVICE_API_KEY`,
`DTE_SERVICE_TIMEOUT_SECONDS`, `DTE_MAX_ATTEMPTS`, `DTE_RECONCILE_SECONDS`, `DTE_STALE_MINUTES`.


## Sales invoice emails (revision 0127, block V3c)

An issued (`issued` or `simulated`) fiscal document is emailed to the customer with its PDF and
JSON attached. The ERP sends it through the **company's own SMTP** (see «Company outgoing
email» below) when it is configured and enabled: the sender is its `from_address` with its
`from_name` (or the trade name). Otherwise it falls back to the deployment's SMTP server
(`SMTP_FROM_ADDRESS` with the trade name); with neither, nothing is sent. `Reply-To` is always
the company's DTE email from the issuer snapshot. The body lists the control number, generation code, issue date and total,
and closes with the company's current privacy notice. Simulated documents carry
«SIMULADO — sin validez fiscal» in the subject and the body.

- **Automatic**: when `dte-worker` issues a document and the customer's record has a valid
  email, it creates one `auto` send (at most one per document) and delivers it.
- **Manual**: a user sends the document to the customer's email or to up to five addresses.
- Delivery is asynchronous (`pending` → `sent` or `failed`); temporary SMTP or network errors are
  retried with the same record, and the reconcile job re-enqueues stale pending sends.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/fiscal-documents/{id}/emails` | `sales_invoices:read` | `{enabled, customer_email, items}`: whether the company can send email (own SMTP enabled or server fallback), the customer's email and the history (recipients, origin, status, attempts, error, requester, sent date). |
| POST | `/sales/fiscal-documents/{id}/emails` | `sales_invoices:issue` | Body `{"recipients": [...]}` (1–5 after trimming, lowercasing and removing duplicates) or empty for the customer's email. `202` with the `pending` send. |

Audited on `sales_fiscal_document`: `REQUEST_FISCAL_DOCUMENT_EMAIL` (user),
`FISCAL_DOCUMENT_EMAIL_SENT` and `FISCAL_DOCUMENT_EMAIL_FAILED` (worker).

Error codes (`422`): `sales_invoice_email_not_issued`, `sales_invoice_email_required`,
`sales_invoice_email_invalid`, `sales_invoice_email_too_many`,
`sales_invoice_email_unavailable`. `FiscalDocumentOut` now includes `customer_email`.

Configuration: `SMTP_HOST` (empty disables email), `SMTP_PORT`, `SMTP_SECURITY`
(`none`, `starttls`, `ssl`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_ADDRESS` (required with
a host) and `SMTP_TIMEOUT_SECONDS`. In development compose points the backend and `dte-worker` to
Mailpit (`mailpit:1025`); its inbox is at <http://localhost:8025>.

### Company outgoing email (revision 0128)

Each company can send its documents from its own SMTP server and domain. The domain's DNS
(SPF, DKIM, DMARC) is the company's responsibility. Authentication is username and password
(an app password for Google) over STARTTLS or SSL. The password is encrypted with AES-GCM
(`SUPPLIER_DATA_ENCRYPTION_KEY`, which `dte-worker` also receives) and is never returned.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/fiscal/email-settings` | `fiscal_settings:read` | `configured`, `host`, `port`, `security`, `username`, `has_password`, `from_address`, `from_name`, `is_enabled`, last test (`last_test_at`, `last_test_ok`, `last_test_error`) and `server_fallback`. |
| PUT | `/fiscal/email-settings` | `fiscal_settings:manage` | Create or replace. An empty `password` keeps the stored one; without `username` there is no password. Saving clears the last test. |
| DELETE | `/fiscal/email-settings` | `fiscal_settings:manage` | Remove; documents fall back to the server SMTP, if any. `204`. |
| POST | `/fiscal/email-settings/test` | `fiscal_settings:manage` | Body `{"recipient"}`. Sends a test email synchronously and records the result; returns `{ok, message}`. |

Audited on `company_email_settings` (`CREATE`, `UPDATE`, `DELETE`, `TEST_COMPANY_EMAIL_SETTINGS`)
without the password. Error codes (`422`): `email_settings_host_invalid`,
`email_settings_port_invalid`, `email_settings_security_invalid`,
`email_settings_username_required`, `email_settings_password_required`,
`email_settings_from_invalid`, `email_settings_from_name_too_long`,
`email_settings_test_recipient_invalid`; `email_settings_not_found` (404). A send whose company
has no usable SMTP fails with `email_unavailable`.

## Hacienda credentials (revision 0129, block V3d)

Each company keeps its own Hacienda API password, private-key password and certificate
(`{nit}.crt`, the XML that Hacienda generates). They are encrypted with AES-GCM
(`SUPPLIER_DATA_ENCRYPTION_KEY`) and never returned. The certificate must belong to the company's
NIT and open with the private-key password (SHA-512 in `privateKey/clave`, as the official
signer checks).

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/fiscal/hacienda-credentials` | `fiscal_settings:read` | `configured`, `certificate_nit`, `certificate_sha256` and the last connection test. |
| PUT | `/fiscal/hacienda-credentials` | `fiscal_settings:manage` | `api_password`, `private_key_password`, `certificate_base64`; empty fields keep the stored value. Saving clears the last test. |
| DELETE | `/fiscal/hacienda-credentials` | `fiscal_settings:manage` | Only while the company is in simulated mode. `204`. |
| POST | `/fiscal/hacienda-credentials/test` | `fiscal_settings:manage` | Registers the company in the DTE service with its credentials (test mode, or production if already there) and runs the service's connection test: Hacienda authentication and a test signature. Returns `{ok, authentication_ok, authentication_message, signature_ok, signature_message}`. |

Switching the fiscal profile to `test` requires tested credentials (`fiscal_test_not_ready`);
`production` also lists them among its blockers. When `dte-worker` issues a document outside
simulated mode it registers the company with its mode and credentials; without credentials the
document fails with `hacienda_credentials_missing`.

Audited on `company_hacienda_credentials` (`CREATE`, `UPDATE`, `DELETE`,
`TEST_HACIENDA_CREDENTIALS`) with the certificate NIT and fingerprint only. Error codes (`422`):
`hacienda_certificate_required`, `hacienda_certificate_invalid`,
`hacienda_certificate_nit_mismatch`, `hacienda_private_key_password_invalid`,
`hacienda_api_password_required`, `hacienda_private_key_password_required`,
`hacienda_company_nit_missing`, `hacienda_credentials_in_use`; `hacienda_credentials_not_found`
(404).

## Billing contingency (revision 0130, block V4a)

A contingency window belongs to one company and one fiscal establishment and lives in the DTE
service. The service opens it by itself when Hacienda does not answer; an operator opens it for a
failure the service cannot see (power or internet outage at the store). Documents issued meanwhile
are generated in the deferred model and stay in the fiscal status `contingency` (with
`contingency_type`, `contingency_reason` and `contingency_at`) until the service seals them
(`issued`/`simulated`) or Hacienda rejects them; `dte-worker` follows them
(`follow_fiscal_contingency`) and never issues them again. The customer receives the readable
version during the contingency.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/contingencies` | `sales_invoices:read` | Windows (open and recent) with status `ACTIVA`, `CERRADA`, `REPORTADA` or `COMPLETADA`, documents, deadlines (24 h for the event, 72 h for the documents) and last error; the responsible person; `active`. |
| POST | `/sales/contingencies` | `sales_invoices:contingency` | Opens the window of `establishment_id` with `contingency_type` (CAT-005, 1–5) and `reason` (required for 5). `201`. |
| POST | `/sales/contingencies/{id}/close` | `sales_invoices:contingency` | Closes it and reports the event with the registered responsible person. |
| POST | `/sales/contingencies/{id}/event` | `sales_invoices:contingency` | Sends the event of a closed window again. |
| PUT | `/sales/contingencies/responsible` | `sales_invoices:contingency` | `name`, `document_type` (CAT-022: 13, 36, 03, 02, 37) and `document_number` of the person who signs the event. |

Before each action the ERP registers the company in the service with its mode, credentials and
responsible person. `/sales/fiscal-documents` accepts `status=contingency`.

Audited: `ACTIVATE_CONTINGENCY`, `CLOSE_CONTINGENCY`, `SEND_CONTINGENCY_EVENT` on
`sales_contingency`; `CREATE`/`UPDATE` on `company_contingency_responsible`; the worker records
`FISCAL_DOCUMENT_CONTINGENCY`. Error codes: `sales_contingency_type_invalid`,
`sales_contingency_reason_required`, `sales_contingency_responsible_invalid`,
`sales_contingency_responsible_required`, `sales_contingency_active`,
`sales_contingency_nit_missing`, `sales_contingency_rejected` (422);
`sales_contingency_already_active` (409); `sales_contingency_not_found`,
`sales_contingency_establishment_not_found` (404).

## Invalidation and correction (revision 0131, block V4b)

A sealed document is never deleted. It is invalidated with a signed event (CAT-024 type 2,
rescind the operation) or corrected (type 1): a replacement is issued first with the current
order and customer data and, once it is sealed, the worker invalidates the original and links
both. The company's fiscal responsible person (`/sales/contingencies/responsible`) signs every
event. Requests are stored in `sales_fiscal_invalidations` and processed by `dte-worker`
(`invalidate_fiscal_document`) with their own idempotency key.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/fiscal-documents/{id}/invalidation` | `sales_invoices:read` | `deadline` (from the DTE service: three months after the seal for 01, the tenth business day of the next month for 03), `expired`, `estimated` and the request `history`. |
| POST | `/sales/fiscal-documents/{id}/invalidate` | `sales_invoices:invalidate` | Type 2 with `reason` (5–200), `requester` (`name`, `document_type` of CAT-022, `document_number`) and `cancel_order` (also needs `sales:cancel`; the order is cancelled when Hacienda accepts). `202`. |
| POST | `/sales/fiscal-documents/{id}/correct` | `sales_invoices:invalidate` | Type 1 with `requester`: creates the replacement (`replaces_document_id`) and the pending invalidation. `202` with both. |

Fiscal documents gain the status `invalidated` and the fields `replaces_document_id` and
`superseded_by_id`. The order's active document is the pending, contingency, issued or simulated
one that is not being replaced: a rejected or invalidated document no longer blocks invoicing
again. `/sales/{order_id}/invoice-options` returns `previous_document` (the latest one) when there
is no active document. When the invalidation is accepted the customer receives a separate notice
with the event PDF (emails expose `invalidation_id`).

Audited: `REQUEST_INVALIDATION`, `CORRECT_FISCAL_DOCUMENT`, `FISCAL_DOCUMENT_INVALIDATED`,
`FISCAL_INVALIDATION_REJECTED`, `FISCAL_INVALIDATION_FAILED` and, when it applies,
`SALES_ORDER_CANCELLED`. Error codes (`422`): `sales_invoice_not_invalidatable`,
`sales_invoice_invalidation_in_progress`, `sales_invoice_replacement_in_progress`,
`sales_invoice_not_correctable`, `sales_invoice_correction_type_changed`,
`sales_invoice_invalidation_reason_required`, `sales_invoice_requester_invalid`,
`sales_invoice_responsible_missing`, `sales_invoice_invalidation_expired`.

## Income-tax classification of sales (revision 0132, block V4b2)

Since the January 2025 period the F-07 sales annexes carry, for every document, the operation type
and the income type for income tax (F-07 annex manual V14: operation 1, 2, 3, 4, 12, 13; income 1–10,
12, 13; 12 and 13 must match in both columns). The DTE does not carry them, so the ERP stores them.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| PUT | `/fiscal/activities/{id}/renta` | `fiscal_settings:manage` | `operation_type` and `income_type` suggested for the activity's sales; both `null` clears them. Audited `UPDATE` on `fiscal_activity`. |

- Activities expose `renta_operation_type` and `renta_income_type`.
- `/sales/{order_id}/invoice-options` returns the suggestion of the establishment's activity (or the
  primary one).
- `POST /sales/{order_id}/invoice` accepts `renta_operation_type` and `renta_income_type`; without
  them the suggestion is used and, with no suggestion, it fails with `sales_invoice_renta_required`.
  An invalid pair fails with `sales_renta_invalid`.
- Fiscal documents expose their classification. A correction's replacement keeps the original's.
  Documents issued before revision 0132 have none.

## Credit and debit notes (revision 0133, block V4c)

Notes adjust a sealed tax credit (`03`, issued or simulated, not being replaced and without a
pending invalidation). A credit note (`05`) lowers it and a debit note (`06`) raises it (Tax
Code art. 110). A note belongs to the CCF's order and point of sale, carries the current issuer
and the CCF's income-tax classification, stays `pending` and is issued by `dte-worker` through
`/api/dte/v2/nota-credito` or `/api/dte/v2/nota-debito`; it is emailed like any document. Notes
are fiscal only: they move no stock and no money.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/fiscal-documents/{id}/notes` | `sales_invoices:read` | CCF lines with `net` (sale minus its share of the global discount), `returned`, `credited`, `remaining_quantity` and `remaining_amount`; `deadline` (three months after the CCF's `fecEmi`, for both notes), `withholding` and `perception` (whether the CCF withheld or perceived VAT), `credit_blocker` and `debit_blocker` (why a note cannot be issued now) and the `notes` with their lines. |
| POST | `/sales/fiscal-documents/{id}/credit-note` | `sales_invoices:notes` | `reason` (5–300) and `lines`: `{ccf_line_number, kind: "return", quantity}` (credited at the remaining net price; the last units take the exact remaining amount) or `{ccf_line_number, kind: "discount", amount}` (without VAT). Each line at most once, within its balance. `202`. |
| POST | `/sales/fiscal-documents/{id}/debit-note` | `sales_invoices:notes` | `reason` and `charges`: `{description, quantity, unit_price, nature?, ccf_line_number?}`. A charge on a CCF line takes its nature; a free charge needs `nature` (`taxed`, `exempt`, `not_subject`). No cap; same deadline as the credit note. `202`. |

Both notes must be issued within three months of the CCF date (Normativa de Cumplimiento DTE 2.0,
annex IV, field 17, rule 2c, which Hacienda validates; for credit notes also Tax Code art. 111).
VAT is 13 % of the taxed amount; if the CCF withheld or perceived VAT the note repeats it at 1 %
of its own taxed amount, without the $100 threshold (Manual Funcional V2.0, NCE-with-withholding
example). Fiscal documents accept `document_type` `05` and `06` (also as a list filter) and gain
`related_document_id` and `note_reason`. A note is not counted as the order's active document.

A note is invalidated with type 2 and never corrected; invalidating it cannot cancel the order. A
CCF with vigent notes (pending, contingency, issued or simulated) cannot be invalidated or
corrected (rule 633).

Audited: `ISSUE_CREDIT_NOTE`, `ISSUE_DEBIT_NOTE` and the usual issuance events. Error codes
(`422`): `sales_note_requires_ccf`, `sales_note_ccf_not_sealed`,
`sales_note_ccf_invalidation_pending`, `sales_note_deadline_passed`,
`sales_note_document_disabled`, `sales_note_reason_required`, `sales_note_lines_required`,
`sales_note_line_invalid`, `sales_note_line_repeated`, `sales_note_quantity_exceeded`,
`sales_note_amount_exceeded`, `sales_note_charge_invalid`, `sales_invoice_has_notes`,
`sales_note_cancel_order_invalid`.

## Engineer's rules (revisions 0134–0136)

**Never below cost.** The final net price of a line (its discount plus its share of the global
discount) is compared with the current kardex cost. Previews flag it with the line reason
`below_cost`; saving a quotation, issuing it, and confirming or authorizing an order reject it
with `sales_price_below_cost` (422). No role or authorization overrides it.
`can_sell_below_cost` is gone from the discount policies.

**Branch promotions.**

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/sales/promotions` | `sales:read` or `sales_promotions:manage` | Optional `branch_id`, `include_ended`. Limited to the user's branches. Each item has `status`: `current`, `scheduled`, `expired` or `ended`. |
| POST | `/sales/promotions` | `sales_promotions:manage` | Body: `branch_id`, `product_id`, `discount_percent` (> 0, < 100), optional `valid_from` (today by default), `valid_to`, `notes`. Audited as `CREATE` on `sales_branch_promotion`. |
| POST | `/sales/promotions/{id}/end` | `sales_promotions:manage` | Ends a current promotion today or cancels a scheduled one. Audited as `END_PROMOTION`. |

A current promotion replaces every other discount on its lines (`suggested_discount_source =
'promotion'`): the vendor's discount is ignored, customer and volume discounts do not apply, no
role limit is checked, and the document rejects a global discount
(`sales_global_discount_with_promotion`).

**Stock exit on confirm.**

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/sales/settings/orders` | `sales:read` or `fiscal_settings:read` | `{ "auto_deliver_on_confirm": true }`. |
| PUT | `/sales/settings/orders` | `fiscal_settings:manage` | Same body. Audited. |

When it is on, `POST /sales/orders/{id}/confirm` and `/authorize` also create and confirm a delivery
with the whole handling units that cover each line (FEFO). The response carries `auto_delivery`:
`delivery_id`, `delivery_code`, `pending_products` (lines that need a unit split in the warehouse)
and `message` (why nothing could be delivered). A failure there never undoes the confirmation.

Error codes: `sales_price_below_cost`, `sales_global_discount_with_promotion`,
`sales_promotion_percent_invalid`, `sales_promotion_backdated`, `sales_promotion_validity_invalid`,
`sales_promotion_branch_invalid` (404), `sales_promotion_product_invalid`, `sales_promotion_overlap` (409),
`sales_promotion_not_found` (404), `sales_promotion_already_ended`.

## Remission note of a transfer (revision 0137, block V4d)

When the company enables document type `04`, `POST /inventory/transfers/{id}/dispatch` also creates the
transfer's remission note in `pending`, in the same transaction, and the DTE worker issues it
(`/api/dte/v2/nota-remision`). If the note cannot be built the dispatch is rolled back.

- Issuer: the fiscal establishment of the origin warehouse's branch and its first active point of sale.
- Receiver: the company itself at the destination establishment's address; `bienTitulo` `04`.
- Lines: what was dispatched, at the kardex average cost, taxed (informative VAT); vehicle, plate and
  driver in `observaciones`. `total` is `montoTotalOperacion` and is reconciled with the issued JSON.

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/inventory/transfers/{id}/remission` | `inventory:read` (either side) | `{ enabled, document }`: the vigent note or the latest one. |
| POST | `/inventory/transfers/{id}/remission/reissue` | `inventory:read` + `inventory:move` (origin side) | New note with the dispatch data when the latest was rejected or failed. Audited as `REISSUE_TRANSFER_REMISSION`. |

Fiscal documents (`/sales/fiscal-documents`) now include `04` (filter `document_type=04`), with
`sale_id: null`, `transfer_id` and `transfer_code`. A sealed note is corrected with `/correct` (type 1, the
replacement is rebuilt from the transfer); `/invalidate` answers `transfer_remission_not_annullable`.

Error codes: `transfer_remission_issuer_missing`, `transfer_remission_receiver_incomplete`,
`transfer_remission_lines_missing`, `transfer_remission_already_issued`, `transfer_remission_not_reissuable`,
`transfer_remission_disabled`, `transfer_remission_not_annullable`,
`transfer_remission_transfer_not_dispatched` (404), `sales_invoice_not_an_order_document`.

## Return events (revision 0138, block V4d2)

A return event (evento de retorno, CAT-002 type 18; Normativa 2.0 rule 13.3) records goods a
consumer gives back on a sealed invoice (`01`, issued or simulated, not being replaced and
without a pending invalidation). It is built from the invoice as it was sealed: issuer, receiver
and the related document come from the stored DTE. It is fiscal only: it moves no stock and no
money. The event stays `pending` and `dte-worker` issues it through
`POST /api/dte/{codigo}/retorno`; when it is accepted the customer gets it by email with its PDF
and JSON.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/sales/fiscal-documents/{id}/returns` | `sales_invoices:read` | Invoice lines with `net`, `returned`, `remaining_quantity` and `remaining_amount`; `deadline`, `withholding` (whether the invoice withheld VAT), `blocker` (why a return cannot be registered now) and the `returns` with their lines. |
| POST | `/sales/fiscal-documents/{id}/returns` | `sales_invoices:returns` | `reason` (5–300) and `lines`: `{invoice_line_number, quantity}`. Each line at most once, within its balance; the last units take the exact remaining amount. `202`. |
| POST | `/sales/fiscal-returns/{id}/annul` | `sales_invoices:returns` | `requester` (`name`, `document_type`, `document_number`). Annuls the event with an invalidation type 2 (no replacement); the branch responsible signs it. `202`. |
| GET | `/sales/fiscal-returns/{id}/json` | `sales_invoices:read` | The event as transmitted. |
| GET | `/sales/fiscal-returns/{id}/pdf` | `sales_invoices:read` | Graphic representation («EVENTO DE RETORNO»). |

Amounts include VAT (13/113 of the taxed amount is shown as `vat`). If the invoice withheld VAT,
the event repeats 1 % of its taxed base. The deadline is three months from the invoice
generation date, or two years when the issuer's activity sells medicines (01282, 21001, 46484,
47721; VAT Law art. 62). Return statuses: `pending`, `issued`, `simulated`, `rejected`,
`failed`, `invalidated`; `annul_status`: `pending`, `accepted`, `rejected`, `failed`.

An invoice with vigent returns (pending, issued or simulated) cannot be invalidated or corrected
(`sales_invoice_has_returns`): annul its returns first.

Audited: `ISSUE_FISCAL_RETURN`, `ANNUL_FISCAL_RETURN`, and from the worker `FISCAL_RETURN_ISSUED`,
`FISCAL_RETURN_REJECTED`, `FISCAL_RETURN_FAILED`, `FISCAL_RETURN_ANNULLED`,
`FISCAL_RETURN_ANNUL_REJECTED` and `FISCAL_RETURN_ANNUL_FAILED`. Error codes (`422`):
`sales_return_document_invalid`, `sales_return_document_not_issued`,
`sales_return_invoice_not_sealed`, `sales_return_invalidation_pending`,
`sales_return_deadline_passed`, `sales_return_reason_required`, `sales_return_lines_required`,
`sales_return_line_invalid`, `sales_return_line_repeated`, `sales_return_quantity_exceeded`,
`sales_return_amount_exceeded`, `sales_return_not_annullable`, `sales_invoice_has_returns`;
`sales_return_not_found` (`404`).

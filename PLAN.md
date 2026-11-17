# Plan: Ventas V2e — Pedido de venta

Rama: `feature/ventas-v2e-pedido`. V2d (PR #46) ya está en `develop` y se trajo a esta rama.

Fuente: `docs/plan-area-ventas-el-salvador.pdf`.
- Módulo 5.3:
  - «Pedido de venta: compromiso con fecha y lugar de entrega, que puede nacer de una cotización o directamente».
  - «Reserva de existencias al confirmar el pedido».
  - «El pedido es un documento distinto de la factura: tiene su propia numeración y sus estados de entrega…».
  - «Toda cancelación exige motivo y libera las reservas».
- Bloque V2: «Nuevo modelo de cotización y pedido, que sustituye al actual». El resultado verificable es una cotización y un pedido con totales fiscales correctos en ambos documentos.

## Decisiones del usuario

- 16/11/2026 (V2): la venta B06 se rehace en su lugar con migración. Si hay datos, la migración se niega a seguir en lugar de perderlos. Las entregas y devoluciones se adaptan.
- 16/11/2026 (V2e):
  - **Reserva comercial al confirmar**:
    - El pedido aparta cantidad por artículo en la sucursal sin mover unidades físicas.
    - La entrega la consume.
    - Cancelar la libera.
  - **Origen**: el pedido nace de una cotización aceptada (copia precios y descuentos) o se arma directamente, con el mismo editor y las mismas reglas de topes y autorización.
  - **Entrega**: fecha comprometida obligatoria. El lugar es retiro en la sucursal o una dirección de entrega del cliente.
  - **Crédito**: el bloqueo por cupo y saldos vencidos queda para V5. En V2e el pedido solo copia la condición de pago del cliente (contado o crédito, y días).
- 16/11/2026: el usuario delegó el merge de las PR cuando pasen los checks propios.

## Hechos verificados

- `sales` y `sales_lines` (B06):
  - `quotation_id` es obligatorio y único;
  - `total` = `subtotal`, sin impuestos;
  - estados `draft`, `confirmed` y `cancelled`.
  - Las líneas tienen `source_quotation_line_id` obligatorio.
- Entregas (`sales_deliveries`) y devoluciones (`sales_returns`):
  - Apuntan a `sales` y `sales_lines` y solo usan cantidades, no precios.
  - Las entregas toman unidades `available` de cualquier bodega activa, no de tránsito, de la sucursal del documento.
- El inventario no tiene reservas de producto; solo de capacidad.
- La cotización V2d ya calcula todo en `SalesQuotationUseCases._build`:
  - precio de lista, descuento sugerido, tope y motor fiscal;
  - identidad de línea en `sales_line_identity.py`.
- `sales_customers` tiene `credit_days` y `credit_limit`, y existen las direcciones de entrega del cliente.

## Diseño

- **Tablas**: se conservan `sales` y `sales_lines`, porque las entregas y devoluciones ya apuntan a ellas. En la interfaz el documento se llama **Pedido**.
- **Cabecera**:
  - `quotation_id` pasa a opcional;
  - mismos campos fiscales y de autorización que la cotización: documento, lista, IVA, descuento global, totales, motivos y autorización;
  - entrega: `promised_date`, `delivery_mode` (`pickup` o `delivery`), `delivery_address_id` y una copia de la dirección;
  - condición de pago: `payment_terms` (`cash` o `credit`) y `credit_days`.
- **Línea**:
  - mismos campos que la línea de cotización;
  - `source_quotation_line_id` pasa a opcional.
- **Estados**: Borrador → Por autorizar (si pasa el tope o queda bajo costo) → Confirmado → Cancelado.
  - La entrega sigue con su avance calculado: pendiente, parcial o completa.
  - Facturación y cobro llegan en V3 y V5.
- **Reserva comercial**: calculada, sin tabla nueva.
  - Reservado de un artículo en una sucursal = suma de lo pendiente de entregar (en unidad base) de los pedidos confirmados de esa sucursal.
  - Disponible para vender = unidades `available` en las bodegas activas de la sucursal − reservado.
  - Al confirmar se bloquea por empresa, sucursal y artículo (lock consultivo) y se valida que alcance. Si no alcanza, error por línea.
  - Cancelar un pedido confirmado sin entregas libera lo reservado. Con entregas parciales, cancelar no se permite en V2e.
  - **Límite**: los traslados y ajustes todavía no respetan la reserva. Lo verán como aviso en un bloque posterior.
- **Cálculo compartido**: `_build` de la cotización pasa a un constructor común de documentos de venta. Lo usan la cotización y el pedido, sin duplicar código.
- **Desde cotización**: «Crear pedido» en una cotización Aceptada.
  - Copia líneas, precios, descuentos y totales tal como se aceptaron, sin recalcular.
  - Pide fecha y lugar de entrega, y el pedido queda en borrador.
  - Es idempotente: una cotización origina un solo pedido.
- **Permisos**: se reutilizan `sales:read`, `sales:manage`, `sales:confirm`, `sales:cancel` y `sales_quotations:convert`, y los de topes y precio manual de V2d. Todo queda en la bitácora.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: migración `0125` y modelos.**
  - Guarda: se niega si hay ventas, entregas o devoluciones.
  - Columnas nuevas de pedido y línea, estados y opcionales.
  - Prueba de migración.
- [x] **Paso 2: dominio y cálculo compartido.**
  - Extraer de la cotización el constructor común.
  - Transiciones del pedido.
  - Regla de reserva: disponible, reservado y suficiencia.
  - Pruebas unitarias.
- [ ] **Paso 3: aplicación, repositorio y API.**
  - Pedido directo y desde cotización.
  - Confirmar con reserva, autorizar o devolver, y cancelar con liberación.
  - Disponible para vender en la vista previa.
  - Adaptar entregas y devoluciones al pedido confirmado.
  - Retirar el `convert` B06.
  - Pruebas e2e: reserva insuficiente, concurrencia, cancelación que libera, aislamiento y permisos.
- [ ] **Paso 4: frontend.**
  - Editor de pedido (el de cotización con fecha y lugar de entrega), con disponible por línea.
  - Detalle con acciones por estado y entregas.
  - Lista de pedidos.
  - «Crear pedido» en la cotización aceptada.
  - vitest.
- [ ] **Paso 5: documentación.** `docs/api.md`, `docs/database-schema.md` §35, manual de pedidos y ajuste del manual de ventas base.
- [ ] **Paso 6: verificación y PR.** Batería completa, QA en el navegador y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: 3. El puerto `domain/ports/sales_order_repository.py` ya está escrito.
  - Paso 2:
    - `application/sales_documents/pricing.py` (`SalesDocumentPricing`): cálculo común de cotización y pedido.
    - `domain/ports/sales_document.py`: `LineIdentity`, `DocumentLine`, `DocumentTotals` y `SalesCatalog`. La cotización los usa por alias.
    - `domain/entities/sales_order.py`, con sus pruebas unitarias en verde.
    - Las e2e de cotización pasan, salvo la conversión B06, que se reemplaza en el paso 3.
  - Paso 1:
    - Migración `0125` y modelos.
    - La migración redefine los triggers `guard_sales_lines_draft` y `guard_sales_order_lines_draft` con `varchar(24)`, porque `pending_authorization` no cabía.
    - Agrega `uq_sales_customer_delivery_addresses_owner` (empresa, cliente, id), para que la dirección de entrega quede ligada al cliente del pedido.
    - Ya está aplicada en desarrollo. Antes se borró la venta de QA VTA-20261116-6C21B05C, con respaldo JSON en el scratchpad de la sesión.
    - El servicio B06 solo tolera pedidos sin cotización. Las e2e de ventas, entregas y aceptación final fallarán hasta el paso 3.
- **Contexto**: el frontend usa SvelteKit 3 (imports `#lib/…` con extensión, `$app/env`).
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con un objetivo explícito: `backend-unit`, `backend-integration`, `backend-e2e`, `frontend` o `lint`. Sin argumento corre la batería completa, de unos 45 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop` con Auto-fix y auto-merge (merge commit).
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

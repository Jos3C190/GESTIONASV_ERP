# Plan: Ventas V2d — Cotización rediseñada

Rama: `feature/ventas-v2d-cotizacion`, apilada sobre `feature/ventas-v2c-descuentos-margen` (PR #45, con auto-merge). Cuando la #45 entre, se trae `develop`.
Fuente: `docs/plan-area-ventas-el-salvador.pdf`:
- módulo 5.3: «Cotización rediseñada: precios de lista, impuestos, descuentos, vigencia y margen visible para quien autoriza»; «Versión imprimible y envío por correo de la cotización»;
- módulo 5.2: «El precio de lista se propone automáticamente; cambiarlo exige permiso y deja rastro»; «No se vende por debajo del costo promedio sin autorización explícita»;
- sección 6.7: un descuento fuera de tope queda en la bitácora con usuario, fecha, motivo y valores.

## Decisiones del usuario

- 16/11/2026 (V2): la cotización actual (B06) se rehace en su lugar con migración. Si hay datos, la migración se niega a seguir en lugar de perderlos. Las promociones van en V6.
- 16/11/2026 (V2d):
  - **Estados**: Borrador → Por autorizar (solo si una línea o el descuento global pasa el tope o queda bajo costo) → Emitida → Aceptada / Rechazada / Cancelada. «Vencida» es una Emitida cuya vigencia pasó. El pedido (V2e) nace de una Aceptada.
  - **Quién autoriza**: un usuario con el permiso nuevo `sales_discounts:authorize` y cuyo **propio tope** cubra el descuento. Si la línea queda bajo costo, su rol debe poder vender bajo costo.
  - **Precio manual**: solo con el permiso nuevo `sales_prices:override`. Queda registrado y la diferencia contra el precio de lista cuenta como descuento ante el tope.
  - **Entrega**: días de vigencia por defecto configurables por empresa (15 de entrada) y editables en cada cotización; PDF imprimible. El envío por correo llega con el DTE (V3).
- 16/11/2026: el usuario delegó el merge de las PR cuando pasen los checks propios. El repositorio tiene auto-merge y `develop` protegida con esos checks.

## Hechos verificados

- `sales_quotations` (B06):
  - estados `draft`, `confirmed` y `cancelled`; `subtotal` = `total` (sin impuestos);
  - líneas con precio tecleado, unidad, factor y artículo de inventario.
  - Se convierte en venta: `sales.quotation_id` es obligatorio y único.
  - En la base local hay 0 cotizaciones y 0 ventas.
- Endpoints actuales: `/sales/catalog` y `/sales/quotations` (crear, editar, confirmar, cancelar, convertir), en `application/sales/service.py`. Pantallas: `SalesQuotationList`, `SalesQuotationEditor` y `SalesQuotationDetail`.
- Ya existen:
  - el motor fiscal (`sales_tax.calculate`, V2a);
  - la resolución de precio (`PriceListUseCases.resolve`, V2b);
  - la evaluación de descuentos y topes (`SalesDiscountUseCases.evaluate`, V2c).
- reportlab está en las dependencias (`procurement_report_renderer.py`).

## Diseño

- **Tipo de documento**: factura (01) o crédito fiscal (03). Se propone según el cliente (`receivable_documents`) y se puede cambiar entre los válidos y habilitados en la empresa.
- **Cálculo en el servidor**:
  - Cada vez que se guarda un borrador se resuelve el precio de lista de cada línea (cliente, sucursal, fecha), salvo que tenga precio manual.
  - Luego se aplican el descuento sugerido o el propuesto y la evaluación contra el tope del usuario.
  - Al final, el motor fiscal calcula gravado, exento, no sujeto, IVA, retención, percepción, total y total en letras.
  - Todo queda guardado en la cotización: un cambio posterior de lista o de costo no la altera.
- **Línea**:
  - precio de lista, lista usada y si el precio es manual;
  - precio aplicado y % de descuento, más el descuento sugerido y su origen;
  - montos fiscales;
  - costo y margen al momento de calcular;
  - motivos de autorización.
- **Cotización**:
  - documento, lista de precios y si sus precios llevan IVA;
  - descuento global %;
  - totales fiscales;
  - si requiere autorización y el registro de la autorización: quién, cuándo y nota;
  - fechas y responsables de emisión, respuesta del cliente y cancelación.
- **Vigencia**: `sales_settings.quotation_validity_days` por empresa (15 por defecto). `valid_until` = fecha + días, editable.
- **Conversión a venta (B06)** hasta que V2e la reemplace: solo desde Aceptada, copiando el precio neto de cada línea.
- **PDF**: encabezado de la empresa, cliente, documento, líneas con descuento, resumen fiscal, total en letras y vigencia. Nunca muestra costo ni margen.
- **Permisos nuevos**: `sales_discounts:authorize` y `sales_prices:override`. Los demás usan `sales_quotations:*`. Toda acción queda en la bitácora, incluidos los precios manuales y las autorizaciones con valores.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: migración `0124` y modelos.**
  - Guarda: se niega si hay cotizaciones.
  - Columnas nuevas de cotización y línea, estados nuevos, `sales_settings` y permisos.
  - Prueba de migración.
- [x] **Paso 2: dominio.**
  - Transiciones de estado.
  - Cálculo de la cotización con el motor fiscal y la evaluación.
  - Regla del autorizador.
  - Pruebas unitarias.
- [x] **Paso 3: aplicación, repositorio y API.**
  - Borrador con recálculo.
  - Emitir, autorizar o devolver, aceptar, rechazar y cancelar.
  - Convertir a venta.
  - Vigencia por empresa.
  - PDF.
  - Pruebas e2e (permisos, autorizador con tope insuficiente, precio manual sin permiso, aislamiento).
- [x] **Paso 4: frontend.**
  - Editor: precio de lista automático, descuentos con sugeridos, totales fiscales en vivo y aviso de autorización.
  - Detalle: acciones por estado, margen para quien autoriza y PDF.
  - Lista con los estados nuevos.
  - Vigencia en Configuración fiscal.
  - vitest.
- [x] **Paso 5: semilla y documentación.** `docs/api.md`, `docs/database-schema.md` §34 y el manual de cotizaciones.
- [x] **Paso 6: verificación y PR.** Batería completa, QA en el navegador y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: ninguno. V2d está terminado y en PR hacia `develop` con auto-merge. Sigue V2e (pedido de venta).
  - Batería completa: 1896 pruebas de backend; 8 fallaron por el fixture de `test_sales_lock_refresh.py` sin `document_type` (ya corregido; 13/13 al volver a correr). Lint, build y 1164 de vitest en verde.
  - Pruebas verdes:
    - migración: `test_sales_quotation_redesign_migration.py`;
    - e2e: `test_sales_quotations.py`, `test_sales_base.py`, `test_sales_deliveries.py`, `test_inventory_final_acceptance.py` y `test_sales_discounts.py`;
    - unitarias de ventas y vitest.
  - En `test_sales_base.py`, la carrera emitir-contra-editar acepta un 409 o un 422 para quien pierde.
  - Paso 1 (migración y modelos):
    - Migración `0124`; modelos en `sales.py` y `SalesSettingsModel` en `sales_pricing.py`; permisos en el catálogo.
    - Ya está aplicada en la base de desarrollo.
    - `status` pasa a varchar(24).
  - Paso 2 (dominio): `domain/entities/sales_quotation.py`, con sus pruebas unitarias en verde. Se agregó `sales_tax.document_unit_price`.
  - Paso 3 (backend): ruff y mypy en verde.
    - Archivos:
      - puerto `domain/ports/sales_quotation_repository.py`;
      - repositorio `infrastructure/repositories/sales_quotation_repository.py`;
      - `sales_line_identity.py`, que saca del servicio B06 la identidad de artículo y unidad;
      - casos de uso en `application/sales_quotations/`;
      - router `api/v1/routers/sales_quotations.py`, registrado antes de `sales` para que `/sales/settings` no choque con `/sales/{sale_id}`;
      - esquemas `schemas/sales_quotation.py`;
      - PDF `infrastructure/sales_quotation_pdf.py`.
    - Se retiraron los endpoints y métodos viejos de cotización. `convert` exige Aceptada.
    - `EvaluatedLine.cost` (V2c) devuelve el costo aunque no haya precio de lista.
    - Pruebas:
      - nueva: `tests/e2e/test_sales_quotations.py`;
      - adaptadas con `tests/e2e/sales_quote_flow.py`: `test_sales_base.py`, `test_sales_deliveries.py` y `test_inventory_final_acceptance.py`.
  - Paso 4 (frontend): svelte-check, eslint y vitest (50 pruebas) en verde.
    - Archivos:
      - tipos en `types/sales.ts` y API en `api/sales.ts`;
      - `features/sales/quotation-labels.ts`;
      - editor con cálculo en vivo (`/sales/quotations/preview`), detalle con acciones por estado y PDF, y lista con estados nuevos;
      - pestaña «Cotizaciones» en Configuración fiscal (`QuotationSettingsPanel.svelte`).
  - Paso 5 (documentación):
    - `docs/api.md`, `docs/database-schema.md` §34, `docs/ers-v1/manual-cotizaciones.md` y `manual-ventas-base.md`.
    - La semilla no necesita cambios: la vigencia por defecto es 15 y SUPER_ADMIN recibe los permisos en la migración.
  - QA en el navegador (16/11), en la base de desarrollo:
    - Recorrido completo: cotización COT-20261116-3F7C82B6 de borrador a emitida, aceptada y venta VTA-20261116-6C21B05C.
    - Cálculo en vivo, crédito fiscal propuesto, descuento del cliente 3 %, PDF sin costos, lista por sucursal y pestaña de vigencia.
    - Quedan esos dos documentos de prueba en desarrollo.
- **Decisiones técnicas**:
  - En una lista con IVA, el precio de un producto exento o no sujeto se toma sin IVA: no le aplica.
  - Un precio manual mayor que el de lista no cuenta como descuento negativo: el descuento efectivo es 0.
  - El descuento global % se reparte sobre los totales gravado, exento y no sujeto; cada parte se redondea al centavo.
  - Se puede rechazar una cotización vencida, pero no aceptarla.
- **Contexto**: el frontend usa SvelteKit 3 (imports `#lib/…` con extensión, `$app/env`).
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con los objetivos `backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop` con Auto-fix y auto-merge (merge commit).
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

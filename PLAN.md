# Plan: Ventas V2b — Listas de precios

Rama: `feature/ventas-v2b-listas-precios`, desde `develop` (incluye V1 completo y V2a, PR #42).
Fuente: `docs/plan-area-ventas-el-salvador.pdf`, módulos 5.1 («Condiciones comerciales: lista de precios…») y 5.2 («Listas de precios con vigencia… por sucursal cuando el precio cambie entre tiendas. Precio por producto y unidad de venta, indicando si incluye IVA»), sección 3.6 (precio al público con impuestos incluidos) y bloque V2.

## Decisiones del usuario para V2 (16/11/2026)

- V2 se divide en V2a (motor de cálculo, ya en `develop`), V2b (listas de precios, este plan), V2c (descuentos con topes por rol y venta bajo costo), V2d (cotización rediseñada) y V2e (pedido de venta). Cada uno lleva su PR a `develop`.
- Las promociones van en V6, con la caja.
- La cotización y la venta actuales se rehacen en su lugar (V2d y V2e).

## Alcance de V2b

El precio de venta sale de una lista de precios, no lo teclea el vendedor.

- Cada empresa define sus listas, por ejemplo Mostrador, Mayoreo o Institucional. Una de ellas es la predeterminada.
- Cada lista indica si sus precios incluyen IVA.
- El precio se fija por producto (o variante) y unidad de venta, con fecha de vigencia.
- Una sucursal puede tener su propio precio dentro de la misma lista.
- El cliente puede tener asignada una lista.
- Un endpoint resuelve qué precio corresponde a un cliente en una sucursal y fecha. Lo usarán la cotización y el pedido (V2d y V2e).

Resultado verificable:
- Grupo Lorena tiene «Mostrador» (predeterminada, con IVA) y «Mayoreo» (sin IVA) con precios.
- El precio se resuelve según el cliente, la sucursal y la fecha:
  - un cliente con Mayoreo recibe el precio de mayoreo;
  - un cliente sin lista, el de Mostrador;
  - en una sucursal con precio propio, ese precio;
  - un precio con vigencia futura todavía no aplica.
- Cambiar un precio no borra el anterior: queda el historial de vigencias.

## Hechos verificados

- No existe ningún precio de venta en el ERP. «Asignación de precios» es un marcador sin implementar en el grupo Compras del menú.
- Una línea de venta actual se identifica por:
  - producto y variante (`variant_id`);
  - artículo de inventario;
  - unidad, que es la unidad base del artículo o la de un empaque vigente con su factor (`application/sales/service.py`, `_catalog_option`).
- Los productos tienen `sale_unit`, `variant_mode` (`standalone` o `template`) y `can_sell`.
- Los 13 productos vendibles de Grupo Lorena son bienes; uno tiene variantes.
- El costo promedio vive en `inventory_cost_averages`. El margen y la venta bajo costo quedan para V2c.

## Diseño

- **`sales_price_lists`**: `company_id`, `code` (único por empresa), `name`, `description`, `prices_include_vat`, `is_default` (una sola activa por empresa, con índice parcial), `is_active`, autor y fechas.
- **`sales_price_list_items`**: una fila por precio y vigencia.
  - Columnas: `price_list_id`, `product_id`, `variant_id` (nulo si el producto no tiene variantes), `unit_id`, `branch_id` (nulo = todas las sucursales), `price` (8 decimales, ≥ 0), `valid_from`, `valid_to` (nulo = sin fin), `created_by` y `created_at`.
  - Las filas no se editan: un cambio cierra la vigente el día anterior y crea otra.
  - Dos filas de la misma clave no se traslapan; lo cuida el caso de uso con bloqueo y lo garantiza una restricción de exclusión con `btree_gist`.
  - Un precio que aún no empezó se puede anular (borrar), y la fila anterior recupera su fin.
- **`sales_customers.price_list_id`**: lista asignada al cliente, opcional, de la misma empresa.
- **Resolución** del precio de un producto, variante y unidad para una fecha:
  1. lista del cliente, si tiene y está activa;
  2. si no, la lista predeterminada.
  - Dentro de la lista, el precio de la sucursal gana al general.
  - Si no hay precio, responde «sin precio» con un mensaje, sin error.
- **Unidades con precio**: la unidad base del artículo de inventario y las de sus empaques vigentes; un producto sin artículo (servicio) usa su `sale_unit`.
- **Permisos**: `price_lists:read` y `price_lists:manage`, otorgados a `SUPER_ADMIN`. Toda escritura queda en la bitácora.
- **Menú**: «Listas de precios» en Ventas (`/sales/price-lists`), que reemplaza el marcador «Asignación de precios» de Compras.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: migración `0122_sales_price_lists` y modelos.**
  - Tablas, columna del cliente, permisos, `btree_gist` y una guarda en el downgrade.
  - Verificar con una prueba de migración.
- [ ] **Paso 2: dominio, repositorio, casos de uso y API.**
  - CRUD de listas, fijar o anular precios con vigencia, historial, precios de una lista con búsqueda, resolución y lista del cliente.
  - Verificar con pruebas unitarias y e2e (permisos, aislamiento, traslapes, resolución).
- [ ] **Paso 3: frontend.**
  - Pantalla de listas y de precios de una lista.
  - Selector de lista en la ficha del cliente.
  - Menú.
  - Verificar con vitest, svelte-check y ESLint.
- [ ] **Paso 4: semilla y documentación.**
  - Listas y precios de Grupo Lorena.
  - `docs/api.md`, `docs/database-schema.md` §32 y el manual.
- [ ] **Paso 5: verificación y PR.** Batería completa, QA en el navegador y PR a `develop`.

## Estado actual

- **Paso en curso**: 2 (dominio, repositorio, casos de uso y API). Migración `0122_sales_price_lists.py` y modelos en `models/sales_pricing.py`; el traslape de vigencias lo garantiza `ex_sales_price_list_items_overlap` (solo en la migración).
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con los objetivos `backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
- **Navegador**:
  - Iniciar sesión en `http://localhost:5173/login` con la cuenta local que dio el usuario.
  - Navegar con el menú, sin recargar la página.
  - Si una ruta nueva da «Not found», reiniciar el contenedor `frontend`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.
  - En documentos compartidos, el servicio DTE de referencia se llama «proyecto de referencia».

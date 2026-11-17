# Plan: Ventas V2c — Margen, precio sugerido y descuentos

Rama: `feature/ventas-v2c-descuentos-margen`, desde `develop` (incluye V2a, V2b y el frontend en SvelteKit 3).
Fuente: `docs/plan-area-ventas-el-salvador.pdf`:
- módulo 5.2: «Descuentos por línea, por cliente y por volumen, con tope según el rol»; «No se vende por debajo del costo promedio sin autorización explícita»; «Toma el costo promedio… para mostrar el margen»;
- sección 6.7: el costo solo lo ven roles autorizados; un descuento fuera de tope queda en la bitácora.

## Decisiones del usuario

- 16/11/2026, antes de V2c:
  - el costo del retaceo no es el precio de venta;
  - V2c muestra el costo actual y el margen junto a cada precio de la lista y resalta los precios bajo costo;
  - V2c da un precio sugerido = costo + margen objetivo.
- 16/11/2026, al planificar V2c:
  - **Margen sobre el precio**: margen % = (precio sin IVA − costo) ÷ precio sin IVA. Precio sugerido sin IVA = costo ÷ (1 − margen). Con 30 % y costo $7.00: $10.00 sin IVA, o $11.30 en una lista con IVA.
  - **Margen objetivo por lista, con excepción por categoría** de productos dentro de la lista.
  - Entran el **descuento fijo del cliente** y el **descuento por volumen**, además del tope por rol.

## Alcance

1. **Costo y margen en la lista de precios.** Junto a cada precio aparecen el costo actual de la unidad y el margen %. Los precios bajo costo o bajo el margen objetivo se resaltan. Solo lo ve quien tiene el permiso nuevo `sales_costs:read`.
2. **Precio sugerido** al fijar un precio: costo actual ÷ (1 − margen objetivo), con IVA si la lista lo incluye.
3. **Descuento fijo del cliente**: un % en la ficha del cliente (condiciones comerciales).
4. **Descuento por volumen**: escalas por lista, producto (o variante) y unidad, desde una cantidad mínima, con vigencia.
5. **Tope de descuento por rol**: % máximo por línea y global para cada rol de la empresa, y si el rol puede vender bajo costo.
6. **Evaluación**: un endpoint que, para el usuario, cliente, sucursal y líneas propuestas, devuelve:
   - el precio de lista;
   - el descuento sugerido (cliente o volumen, el mayor);
   - el descuento aplicado;
   - el costo, el margen y el tope del usuario;
   - si la línea **requiere autorización** y por qué (excede el tope o queda bajo costo).
   - La cotización y el pedido (V2d y V2e) lo usan para decidir; la autorización en sí se registra en esos documentos.

Fuera de alcance: las promociones (V6) y el registro de la autorización (V2d y V2e).

## Diseño

- **Costo de una unidad vendible**: `inventory_cost_averages.average_unit_cost` (por unidad base, ya incluye el retaceo) × factor de la unidad. Sin costo registrado → «sin costo» y no se calcula margen.
- **Margen objetivo**:
  - `sales_price_lists.target_margin_percent` (0 a 95, opcional);
  - tabla `sales_price_list_category_margins` (lista, categoría, margen) para las excepciones;
  - el de la categoría gana al de la lista.
- **Descuento del cliente**: `sales_customers.discount_percent` (0 a 100, por defecto 0).
- **Escalas por volumen**: `sales_volume_discounts`:
  - columnas: lista, producto, variante, unidad, `min_quantity` > 0, `discount_percent`, `valid_from`, `valid_to`;
  - no se traslapan en el tiempo dos escalas con la misma clave y cantidad mínima;
  - aplica la de mayor `min_quantity` que la cantidad alcance.
- **Topes por rol**: `sales_discount_policies`:
  - columnas: empresa, rol, `max_line_discount_percent`, `max_global_discount_percent`, `can_sell_below_cost`;
  - un usuario con varios roles toma el máximo de cada valor;
  - un rol sin política tiene 0 % y no vende bajo costo;
  - el superusuario no tiene tope.
- **Descuento sugerido** de una línea: el mayor entre el del cliente y el de volumen. No se suman.
- **Permisos**:
  - `sales_costs:read` para ver costo y margen;
  - `sales_discounts:manage` para configurar topes por rol;
  - el margen objetivo y las escalas usan `price_lists:manage`, y el descuento del cliente `sales_customers:manage`.
  - Todo cambio queda en la bitácora.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: migración `0123` y modelos.**
  - Cambios en la base:
    - margen objetivo en la lista;
    - márgenes por categoría;
    - descuento del cliente;
    - escalas por volumen con exclusión de traslape;
    - políticas por rol;
    - permisos;
    - guarda en el downgrade.
  - Prueba de migración.
- [x] **Paso 2: dominio.**
  - Funciones: margen, precio sugerido, elección de escala, descuento sugerido, topes efectivos de varios roles y evaluación de una línea.
  - Pruebas unitarias con valores exactos.
- [x] **Paso 3: repositorio, casos de uso y API.**
  - Costo y margen en los precios de la lista, solo con `sales_costs:read`.
  - Margen objetivo de la lista y por categoría.
  - Escalas por volumen.
  - Descuento del cliente.
  - Políticas por rol.
  - Endpoint de evaluación.
  - Pruebas e2e.
- [x] **Paso 4: frontend.**
  - En el detalle de la lista: costo, margen, resaltado, precio sugerido en el modal y escalas por volumen.
  - En la edición de la lista: margen objetivo y márgenes por categoría.
  - En la ficha del cliente: descuento fijo.
  - Pantalla de topes por rol.
  - vitest.
- [x] **Paso 5: semilla y documentación.**
  - Semilla de Grupo Lorena: márgenes de Mostrador y Mayoreo, escalas en Mayoreo, descuento a un cliente y topes para GERENTE DE SUCURSAL.
  - `docs/api.md`, `docs/database-schema.md` §33 y el manual.
- [x] **Paso 6: verificación y PR.** Batería completa, QA en el navegador (claro, oscuro, 375 px) y PR a `develop`.

## Estado actual

- **Paso en curso**: ninguno; V2c terminado y en PR hacia `develop`. Batería completa: backend 1,886 pruebas y frontend 183 archivos en verde. Lo siguiente es V2d (cotización rediseñada), que usará `POST /sales/discount-evaluation` para pedir autorización.
- **QA en el navegador (16/11/2026)**, con el panel oculto, por texto y JavaScript:
  - Mostrador muestra costo, margen e insignias «Bajo el objetivo» y «Bajo costo»;
  - el sugerido del café da $19.82 ($11.40 de costo, 35 %) y «Usar» lo copia;
  - la pantalla de topes muestra GERENTE 10/5 y EMPLEADO 3/0;
  - El Trigal tiene 3 % fijo y la lista Mayoreo.
  - No se revisaron capturas en modo oscuro ni a 375 px porque el panel del navegador estaba oculto.
- **Hallazgo**: con los costos de la demo, el café de Mostrador ($11.50 con IVA) queda bajo costo ($11.40 sin IVA) y varios productos quedan bajo el margen objetivo. La pantalla lo marca bien; los precios de la semilla de V2b no se tocaron.
- **Contexto**: el frontend usa SvelteKit 3: imports `#lib/…` con extensión, `$app/env`, `goto(…, { replace, reset: false })`.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con los objetivos `backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
- **Navegador**:
  - Iniciar sesión en `http://localhost:5173/login` con la cuenta local del usuario.
  - Si una ruta nueva da «Not found», reiniciar el contenedor `frontend`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

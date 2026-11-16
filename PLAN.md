# Plan: Ventas V1c — Clasificación fiscal de productos

Rama: `feature/ventas-v1c-clasificacion-fiscal-productos`, desde `develop` (ya incluye V1a y V1b, PR #38 y #39).
Fuente: `docs/plan-area-ventas-el-salvador.pdf`, módulo 5.2 («Clasificación fiscal de cada producto: gravado, exento o no sujeto, y su código de tributo»), sección 6.5 («La clasificación fiscal es por producto y por empresa. Ninguna regla asume que todo es gravado») y bloque V1.
Después viene V1d: datos personales.

## Alcance

Cada producto de cada empresa tiene su clasificación fiscal, y cada unidad de medida su código de Hacienda. Esos datos los necesita cada línea de un DTE.

Resultado verificable:
- un producto vendible muestra su tratamiento de IVA, su tipo de ítem, sus tributos adicionales y el código de Hacienda de su unidad de venta;
- si falta algo para facturarlo, la pantalla lo dice.

Queda fuera de V1c:
- el cálculo de impuestos (V2);
- las tasas de los tributos especiales, que se configuran con el motor de V2. Aquí solo se registra qué tributo lleva el producto.

## Hechos verificados (catálogos de Hacienda 1.1 y esquemas del DTE)

- **Línea del DTE (`cuerpoDocumento`).** Lleva:
  - `tipoItem` (CAT-011): 1 bienes, 2 servicios, 3 ambos, 4 otros tributos por ítem;
  - `uniMedida` (CAT-014);
  - montos separados en venta gravada, exenta y no sujeta;
  - `tributos`, con códigos de CAT-015.
- **IVA.** El IVA 13 % es el tributo 20 y el IVA de exportación es C3. Los dos los decide el tipo de venta y de documento, no el producto.
- **Tributos adicionales por producto** (CAT-015, sin 20 ni C3):
  - FOVIAL (D1) y COTRANS (C8) para combustibles;
  - impuestos especiales a bebidas, tabaco, armas y cemento;
  - otros.
- **Unidades (CAT-014).** Tiene metro, gramo, kilogramo, libra, galón, litro, mililitro, docena, unidad (59) y «Otra» (99). No tiene caja, paquete ni centímetro: esas van como 99.
- **Datos actuales.**
  - Grupo Lorena tiene 13 productos, todos bienes y vendibles.
  - Las unidades globales son: UNIT, BOX, PACK, METER, CENTIMETER, GRAM, KILOGRAM, POUND, GALLON, LITER y MILLILITER. Grupo Lorena tiene además una unidad propia, FT (pie).
  - `company_units` (llave `company_id`, `unit_id`) enlaza cada unidad con cada empresa.

## Decisiones

- **Columnas nuevas en `products`.**
  - `tax_treatment`: `taxed`, que es el valor por defecto, `exempt` o `not_subject`.
  - `dte_item_type`: opcional, `1`, `2` o `3`. Si va vacío, se deriva del tipo de producto: bien 1, servicio 2.
  - `additional_tax_codes`: lista de códigos de CAT-015 sin 20 ni C3; vacía por defecto.
- **Código de Hacienda de la unidad.** Va por empresa en `company_units.hacienda_unit_code`, porque cada empresa puede tener sus propias unidades y su propio criterio.
  - Si está vacío, se usa un valor sugerido según el código de la unidad: UNIT 59, KILOGRAM 34, GRAM 39, POUND 36, LITER 23, MILLILITER 26, GALLON 22, METER 1, y 99 para las demás.
  - La migración guarda la sugerencia en las filas que ya existen.
- **Requisitos para facturar un producto vendible.**
  - Su unidad de venta debe estar habilitada en la empresa y tener código de Hacienda.
  - Si es exento o no sujeto, no puede llevar tributos adicionales: los tributos especiales solo aplican a ventas gravadas.
  - El dominio devuelve los problemas en español.
- **API.**
  - `GET` y `PUT /products/{id}/fiscal`, con `products:read` y el permiso nuevo `products:fiscal`.
  - `GET /fiscal/units` y `PUT /fiscal/units/{unit_id}`, con `fiscal_settings:read` y `fiscal_settings:manage`.
  - Toda escritura queda en la bitácora.
- **Pantallas.**
  - Una tarjeta «Clasificación fiscal» en la ficha del producto, con edición en un modal.
  - Una pestaña «Unidades» en Configuración fiscal.
- **Interfaz.** No menciona a otras empresas.

## Pasos

- [x] **Paso 1: migración `0120_product_fiscal_classification` y modelos.**
  - Columnas en `products` y en `company_units`, su carga y el permiso `products:fiscal`.
  - Verificar con upgrade, downgrade y upgrade, y con `tests/integration/test_product_fiscal_migration.py`.
- [x] **Paso 2: dominio.**
  - `app/domain/entities/product_fiscal.py`: tratamiento, tipo de ítem efectivo, validación de tributos, unidad sugerida y requisitos.
  - Verificar con `tests/unit/test_product_fiscal_domain.py`.
- [ ] **Paso 3: repositorio, casos de uso y API.**
  - Archivos:
    - el puerto, el repositorio y los casos de uso;
    - los routers de productos y de configuración fiscal;
    - los esquemas;
    - el permiso en `rbac/catalogue.py`.
  - Verificar con las pruebas de integración y e2e: aislamiento entre empresas, permisos y auditoría.
- [ ] **Paso 4: frontend.**
  - La tarjeta y el modal en la ficha del producto, y la pestaña de unidades en Configuración fiscal.
  - Verificar con vitest.
- [ ] **Paso 5: semilla.** Clasificación de los productos de Grupo Lorena: gravados, salvo lo que el usuario indique. Debe poder reejecutarse.
- [ ] **Paso 6: documentación.** `docs/api.md`, `docs/database-schema.md` y el manual.
- [ ] **Paso 7: verificación y PR.**
  - Correr la batería completa y revisar en el navegador.
  - Reiniciar el contenedor `frontend` si una ruta nueva da «Not found».
  - Abrir el PR hacia `develop`.

## Estado actual

- **Paso en curso**: 3 (repositorio, casos de uso y API). Las unidades que una empresa habilite después quedan con `hacienda_unit_code` vacío y usan la sugerencia del dominio.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
- **Navegador**:
  - Iniciar sesión en `http://localhost:5173/login` con la cuenta local que dio el usuario.
  - Navegar con el menú, sin recargar la página.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.

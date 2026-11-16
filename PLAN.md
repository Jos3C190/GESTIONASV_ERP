# Plan: Ventas V1b — Clientes con datos fiscales

Rama: `feature/ventas-v1b-clientes-fiscales`, desde `develop` (ya incluye V1a, PR #38).
Fuente: `docs/plan-area-ventas-el-salvador.pdf`, módulo 5.1 (Clientes), secciones 4.3 y 6.2, y bloque V1.
Bloques anteriores: V1a, base fiscal del emisor, fusionado el 2026-11-15. Después vienen V1c (clasificación fiscal de productos) y V1d (datos personales).

## Alcance

El maestro de clientes se rehace con identidad fiscal y condiciones comerciales, y pasa del menú de Compras al de Ventas.

Resultado verificable:
- un cliente contribuyente con datos completos puede recibir comprobante de crédito fiscal;
- a uno incompleto la pantalla le dice qué le falta;
- cada sucursal tiene su cliente genérico «Consumidor final».

Queda fuera de V1b:
- las listas de precios (V2);
- la ruta de reparto (V5);
- el consentimiento y el aviso de privacidad (V1d).

## Hechos verificados

**Receptor del DTE en los esquemas oficiales:**
- **Factura (01).** Lleva tipo y número de documento (CAT-022), NRC opcional, nombre, actividad opcional, dirección opcional, teléfono y correo.
- **Comprobante de crédito fiscal (03).** Exige NIT de 14 o 9 dígitos, NRC, nombre, actividad (CAT-019), nombre comercial y dirección completa (departamento, municipio, distrito y complemento de hasta 200 caracteres), además de teléfono y correo.
- **Factura de exportación (11).** Lleva tipo y número de documento, país (CAT-020), complemento de dirección, tipo de persona (CAT-029) y descripción de la actividad.

**Otras reglas:**
- **Tipos de documento (CAT-022).** 36 NIT, 13 DUI, 02 carné de residente, 03 pasaporte y 37 otro. El DUI está homologado como NIT, así que 9 dígitos es un NIT válido.
- **Identificación del consumidor final.** No se exige en ventas menores de $25,000 (D.L. 94 de 2024). Lo controlará V3 al emitir.
- **Datos actuales.** `sales_customers` no tiene registros en ninguna empresa, así que se puede rediseñar sin migrar datos. Las cotizaciones y las ventas apuntan a esa tabla y se conservan.

## Decisiones

- **Tabla.** Se amplía `sales_customers` en lugar de crear otra, para conservar las llaves de cotizaciones y ventas.
- **Tipo de cliente.**
  - `customer_type`: `final_consumer`, `taxpayer` o `foreign`.
  - Para contribuyentes, `taxpayer_category`: `large`, `medium` u `other`.
  - `is_withholding_agent` marca al cliente que retiene el 1 % de IVA, incluido el gobierno; lo usará V2.
- **Identidad.**
  - `person_type` (CAT-029), nombre o razón social, nombre comercial, `document_type` (CAT-022) y número de documento normalizado.
  - NRC y actividad económica (CAT-019).
  - El NIT y el NRC se validan con `dte_nit` y `dte_nrc` del dominio fiscal y son únicos por empresa, sin contar el cliente genérico.
- **Dirección fiscal.**
  - Departamento, municipio y distrito del ERP, que ya tienen códigos de Hacienda, más el complemento.
  - Para clientes del extranjero: país (CAT-020) y complemento.
- **Contacto.** Teléfono y correo, que es a donde se enviarán los DTE.
- **Condiciones comerciales.** Plazo de crédito en días (0 es contado), límite de crédito en USD y vendedor asignado (empleado), todos opcionales.
- **Direcciones de entrega.**
  - Van en la tabla `sales_customer_delivery_addresses`, con nombre, dirección, geografía, coordenadas, contacto, teléfono y marca de principal (una por cliente).
  - Tienen coordenadas para el módulo de rastreo.
- **Cliente genérico «Consumidor final».**
  - Hay uno por sucursal, marcado `is_generic`. Se crea al pedirlo por primera vez con `GET /customers/generic?branch_id=` y siempre devuelve el mismo.
  - No se edita su identidad ni se desactiva.
- **Documentos que puede recibir.** Es un cálculo del dominio:
  - Factura (01): todos menos los del extranjero.
  - Crédito fiscal (03): contribuyente con NIT, NRC, actividad y dirección completa.
  - Exportación (11): clientes del extranjero.
  - La respuesta incluye lo que falta para el crédito fiscal, en español.
- **API.**
  - La API nueva es `/api/v1/customers`.
  - Se quitan las rutas `/sales/customers`. El servicio de ventas conserva su lectura interna de clientes.
  - El frontend de cotizaciones pasa a usar la API nueva.
- **Código del cliente.** Si no se envía, el servidor propone el siguiente `CLI-00001`.
- **Permisos.** Se mantienen `sales_customers:read` y `sales_customers:manage`.
- **Auditoría.** Toda escritura queda en `audit_logs`.
- **Interfaz.** Los textos no mencionan a otras empresas (regla del usuario).

## Pasos

- [x] **Paso 1: migración `0119_fiscal_customers` y modelos.**
  - La migración amplía `sales_customers` con sus columnas y checks, y crea `sales_customer_delivery_addresses`.
  - Verificar con upgrade, downgrade y upgrade, y con `tests/integration/test_customer_migration.py`.
- [x] **Paso 2: dominio.**
  - `app/domain/entities/customer.py`: validación por tipo, documentos que puede recibir, requisitos del crédito fiscal y normalización.
  - `app/domain/ports/customer_repository.py`: el puerto.
  - Verificar con `tests/unit/test_customer_domain.py`.
- [x] **Paso 3: repositorio y casos de uso.**
  - `app/infrastructure/repositories/customer_repository.py` y `app/application/customers/`.
  - Verificar con `tests/integration/test_customer_repository.py`: unicidades, cliente genérico, direcciones de entrega y aislamiento entre empresas.
- [x] **Paso 4: API.**
  - Archivos:
    - el router y los esquemas de `customers`;
    - quitar las rutas de clientes de `sales.py`;
    - las dependencias en `deps.py`.
  - Verificar con `tests/e2e/test_customers.py`, ajustar `test_sales_base.py` y reejecutar las pruebas de ventas.
- [x] **Paso 5: frontend, API y tipos.**
  - `lib/api/customers.ts`, `lib/types/customer.ts` y las etiquetas.
  - El editor de cotizaciones pasa a la API nueva.
  - Verificar con vitest.
- [x] **Paso 6: pantallas.** (la revisión en el navegador queda para el paso 9)
  - Lista de clientes con filtros, y ficha para crear y editar con estas secciones:
    - identidad fiscal;
    - dirección;
    - contacto;
    - condiciones;
    - direcciones de entrega;
    - documentos que puede recibir.
  - Mover «Clientes» al menú de Ventas.
  - Verificar con vitest y en el navegador.
- [x] **Paso 7: semilla.** Clientes de demostración de Grupo Lorena: un contribuyente completo, uno incompleto, un consumidor final identificado y uno del extranjero. Debe poder reejecutarse.
- [x] **Paso 8: documentación.** `docs/api.md`, `docs/database-schema.md` y `docs/ers-v1/manual-clientes.md`.
- [x] **Paso 9: verificación y PR.** Batería completa en verde (backend 1,800; frontend 1,128; lint, tipos y build). Revisión en el navegador: lista, ficha, falta de NRC y paso a crédito fiscal al completarlo. `./scripts/run-tests.sh all`, QA en el navegador y PR hacia `develop`.

## Estado actual

- **Paso en curso**: ninguno; V1b terminado, falta el PR. Después del reinicio del frontend, las rutas nuevas se ven sin recargar la caché: si una ruta recién creada da «Not found» en el navegador, reiniciar el contenedor `frontend`. Semilla: follow-up `seed.grupo_lorena.customers` con CLI-00001 a CLI-00004 y los genéricos `CF-<código de sucursal>`. Los pasos 5 y 6 se hicieron juntos porque `SalesCustomers.svelte` dependía de las rutas viejas; se eliminó. El selector de vendedor existe en la API pero aún no en la pantalla. Prettier solo se aplica a archivos nuevos o tocados: pasarlo por una carpeta entera reformatea código ajeno. La API vive en `/api/v1/customers`; ya no existe `/sales/customers`. Pendiente: correr `test_sales_deliveries.py` y `test_inventory_final_acceptance.py` en la batería completa, que ya apuntan a la ruta nueva. En los checks, `IN (...)` con NULL da NULL y PostgreSQL lo acepta: exigir `IS NOT NULL` explícito.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería: el hook de pre-commit usa la misma base de pruebas.
- **Navegador**:
  - Para revisar en el navegador, iniciar sesión en `http://localhost:5173/login` con la cuenta local que dio el usuario.
  - La sesión vive en memoria: navegar con el menú, sin recargar la página.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.
  - En documentos compartidos, el servicio de referencia se nombra «proyecto de referencia».

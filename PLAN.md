# Plan: Ventas V1a — Base fiscal del emisor

Rama: `feature/ventas-v1-base-fiscal`, creada sobre `chore/claude-workflow`, que a su vez sale de `develop`.
Fuente del diseño: `docs/plan-area-ventas-el-salvador.pdf`, secciones 6.1, 6.2, 6.5 y 7.1 (bloque V1).

## Alcance

El bloque V1 del plan se divide en cuatro entregas, cada una con su PR:

| Entrega | Contenido |
|---|---|
| **V1a (este plan)** | Catálogos de Hacienda, códigos de Hacienda en la geografía, perfil de emisor por empresa, actividades económicas, establecimientos por sucursal, puntos de venta y tipos de documento habilitados por empresa. |
| V1b | Clientes con datos fiscales (sustituye `sales_customers`). |
| V1c | Clasificación fiscal de productos (gravado, exento, no sujeto; tipo de ítem). |
| V1d | Datos personales: aviso de privacidad, consentimientos, solicitudes de titulares, incidentes. |

Queda fuera de V1a y pasa a V3: las credenciales de Hacienda y el certificado de firma, porque necesitan cifrado y viven junto al servicio DTE.

Resultado verificable: dos empresas configuradas como emisores distintos, sin datos compartidos.

## Hechos verificados (fuentes oficiales en `D:\josec\Downloads\Documentacion DTE\`)

- **Catálogos.** Están en `Catálogos - Facturación Electrónica (1 julio).xlsx`, versión 1.1 de 07/2026, que es la vigente. El PDF del 25 de mayo es el mismo documento. Tiene 33 catálogos (CAT-001 a CAT-033) en una sola hoja.
- **Dirección en el DTE.** Los esquemas v2 y v4 piden departamento (CAT-012), municipio (CAT-013) y distrito (CAT-008) en el emisor y en el receptor.
- **Códigos territoriales.**
  - Los códigos de municipio y de distrito son únicos solo dentro de su departamento.
  - El de distrito es correlativo por departamento: vuelve a 01 en cada uno.
  - El ERP ya tiene 14 departamentos, 44 municipios y 262 distritos (migración 0014). 261 distritos se enlazan por nombre; San José La Fuente (La Unión) corresponde al «SAN JOSE», código 15.
- **Número de control.** Sigue el patrón `DTE-TT-(M|B|S|P)NNNPNNN-15 dígitos`.
  - El código de establecimiento es la letra del tipo más 3 dígitos: M casa matriz, S sucursal, B bodega, P patio.
  - El punto de venta es `P` más 3 dígitos.
  - El emisor lleva `codEstable` (4 caracteres) y `codPuntoVenta` en el JSON.
- **Tipos de establecimiento** (CAT-009): 01 Sucursal, 02 Casa matriz, 04 Bodega, 07 Patio.
- **Tipos de documento** (CAT-002): 01, 03, 04, 05, 06, 07, 08, 09, 11, 14 y 15, más los eventos 17 y 18.

## Decisiones

- Los catálogos de Hacienda son globales, no por empresa. Viven en la tabla `hacienda_catalog_items`, con versión, y se cargan desde un módulo Python generado del Excel oficial.
- La geografía existente recibe una columna `hacienda_code`, sin crear tablas paralelas.
- **Perfil de emisor** (1:1 con la empresa). Guarda:
  - la categoría de contribuyente: gran contribuyente, mediano u otro;
  - el tipo de persona (CAT-029);
  - el modo de operación: `simulated`, `test` o `production`;
  - el correo y el teléfono para el DTE.
  El NIT, el NRC, la razón social y el nombre comercial siguen en `companies`.
- **Establecimiento**: uno por sucursal, como máximo. Su dirección es la de la sucursal. El código es único en la empresa y su letra debe coincidir con el tipo.
- **Punto de venta**: pertenece a un establecimiento; el código es único dentro de él. Las cajas de V6 se enlazarán aquí.
- **Documento habilitado**: va por empresa y tipo, con su estado de certificación (`pending`, `in_progress` o `approved`). En modo `production` solo se habilita un tipo que esté aprobado; en `simulated` y `test` se puede habilitar cualquiera.
- Para pasar a `production` hacen falta NIT, NRC, una actividad principal, un establecimiento activo con punto de venta y al menos un documento aprobado y habilitado.
- **Permisos**: `fiscal_settings:read` y `fiscal_settings:manage` (módulo `fiscal`). Los catálogos se leen con `reference_data:read`.
- Toda escritura queda en `audit_logs`.

## Pasos

- [x] **Paso 1: catálogos de Hacienda como datos.**
  - Archivos:
    - `backend/app/infrastructure/catalogs/hacienda_dte.py`: los 33 catálogos, la versión y la fecha.
    - `backend/app/infrastructure/catalogs/hacienda_geography.py`: el mapa de la geografía del ERP a los códigos de Hacienda.
    - `backend/scripts/generate_hacienda_catalogs.py`: el generador a partir del Excel oficial.
  - Verificar con `tests/unit/test_hacienda_catalogs.py`:
    - los conteos por catálogo;
    - 14, 44 y 262 códigos territoriales asignados;
    - códigos únicos por departamento;
    - una muestra de distritos.
- [ ] **Paso 2: migración `0118_fiscal_issuer_base` y modelos.**
  - La migración crea:
    - la tabla `hacienda_catalog_items`, con su carga;
    - la columna `hacienda_code` en `geographic_departments`, `municipalities` y `districts`, con su carga;
    - las tablas `company_fiscal_profiles`, `company_economic_activities`, `fiscal_establishments`, `fiscal_points_of_sale` y `company_dte_document_types`.
  - Modelos en `backend/app/infrastructure/models/fiscal.py`, más los cambios de geografía en `organization.py`.
  - Verificar que `alembic upgrade head`, `downgrade -1` y `upgrade` pasan sin errores. Agregar la prueba `tests/integration/test_fiscal_migration.py`.
- [ ] **Paso 3: dominio.**
  - `backend/app/domain/entities/fiscal.py` contiene las reglas puras: códigos de establecimiento y de punto de venta, tipos, habilitación según el modo y requisitos para pasar a producción.
  - `backend/app/domain/ports/fiscal_repository.py` define el puerto.
  - Verificar con `tests/unit/test_fiscal_domain.py`.
- [ ] **Paso 4: repositorio y casos de uso.**
  - `backend/app/infrastructure/repositories/fiscal_repository.py` y `backend/app/application/fiscal/use_cases.py`.
  - Verificar con `tests/integration/test_fiscal_repository.py`: CRUD, unicidades y aislamiento entre dos empresas.
- [ ] **Paso 5: API.**
  - Archivos:
    - `backend/app/api/v1/routers/fiscal.py`;
    - `backend/app/api/v1/schemas/fiscal.py`;
    - el registro en `router.py`;
    - los permisos en `rbac/catalogue.py`;
    - las dependencias en `deps.py`.
  - Verificar con `tests/e2e/test_fiscal_settings.py`: permisos, auditoría, aislamiento entre dos empresas y errores en español.
- [ ] **Paso 6: semilla.**
  - En `backend/seed/` (Grupo Lorena), en modo simulado:
    - el perfil fiscal;
    - las actividades económicas;
    - un establecimiento por sucursal;
    - un punto de venta por tienda;
    - los documentos 01, 03, 04, 05 y 06 habilitados.
  - La semilla debe poder reejecutarse sin duplicar nada.
  - Verificar con las pruebas unitarias de la semilla.
- [ ] **Paso 7: API y tipos del frontend.**
  - `frontend/src/lib/features/fiscal/api.ts` y `types.ts`, más sus etiquetas.
  - Verificar con vitest.
- [ ] **Paso 8: pantalla «Configuración fiscal».**
  - Ruta `/sales/fiscal-settings`, en el menú de Ventas, con pestañas: Emisor, Actividades, Establecimientos y puntos de venta, Documentos.
  - Debe tener estados de carga, vacío y error, verse bien en tema claro y oscuro, y funcionar a 375 px.
  - Verificar con vitest y en el navegador.
- [ ] **Paso 9: documentación.** `docs/api.md`, `docs/database-schema.md` y el manual en `docs/ers-v1/`.
- [ ] **Paso 10: verificación y PR.**
  - Correr `./scripts/run-tests.sh all` y hacer QA en el navegador con dos empresas.
  - Abrir el PR hacia `develop`, sin atribución.

## Estado actual

- **Paso en curso**: 2 (migración y modelos). Paso 1 listo; CAT-019 tiene 774 códigos (las 885 filas del Excel incluyen títulos de sector). El generador se ejecuta en el contenedor: `docker compose cp <xlsx> backend:/tmp/catalogos.xlsx` y `uv run python scripts/generate_hacienda_catalogs.py /tmp/catalogos.xlsx`, luego `ruff format`.
- **Herramientas**:
  - Los datos crudos de los catálogos, ya extraídos, están en el scratchpad de la sesión: `cats.json` y `geo_map.json`. Si se pierden, el paso 1 los regenera con el script a partir del Excel.
  - El Excel se lee con zipfile y XML, porque no hay openpyxl.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`.
  - Migraciones: `docker compose exec -T backend uv run alembic upgrade head`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - Ignorar el check de Vercel.
  - En documentos compartidos, el servicio de referencia se nombra «proyecto de referencia».

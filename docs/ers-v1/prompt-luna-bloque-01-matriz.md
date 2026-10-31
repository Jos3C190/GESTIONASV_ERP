# Encargo Luna — ERS-B01: sucursal matriz y bodega central

Implementa este bloque completo con pruebas y documentación. El usuario autorizó crear/reutilizar una sucursal matriz administrativa y asociarle la bodega central existente. Este encargo no crea una segunda bodega física ni copia inventario.

## Lectura y responsabilidad

Lee [guía común](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-01 y reglas transversales](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md) y [seguimiento](C:/Developer/GESTIONASV_ERP/docs/ers-v1/matriz-y-seguimiento.md). Aplica las instrucciones del repositorio y skills pertinentes. No estás solo en el repositorio: conserva y adapta los cambios existentes de otros trabajos.

Tu responsabilidad es organización, datos de matriz, reglas de centralidad, alcance de permisos y sus consumidores. Archivos iniciales:

- [Modelos organizacionales](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/organization.py).
- [DTO organizacional](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/schemas/organization.py) y [router](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/organization.py).
- [Acceso por empresa/sucursal](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/company_access.py) y [contexto operativo](C:/Developer/GESTIONASV_ERP/backend/app/application/organization/operational_context.py).
- [Semilla de Grupo Lorena](C:/Developer/GESTIONASV_ERP/backend/seed/seed_grupo_lorena.py).

Busca además los usos de is_central, branch_id nulo y bodega madre en compras, consolidaciones, traslados, frontend, repositorios y pruebas. Las migraciones 0072–0074 son antecedentes; no las edites.

## Implementación

1. Inventaría empresas, bodegas centrales y posibles matrices por identidad; prepara un mapeo verificable. Una variable de semilla llamada headquarters no demuestra por sí sola que una tienda sea la nueva sede administrativa.
2. Añade identificación explícita de matriz si falta un equivalente. Mantén como máximo una sede matriz activa por empresa; el nombre visible no será la condición de negocio.
3. Reutiliza la matriz inequívoca o crea «Casa matriz» con información mínima válida, descripción «Recepción y distribución» y procedencia de datos ficticios documentada. No exigir campos decorativos ni convertirla obligatoriamente en punto de venta. Conservar validación geográfica y requisitos reales del contrato.
4. Sustituye la restricción que exige branch_id nulo en la bodega central. La central debe pertenecer a la matriz de su empresa; mantener la unicidad vigente de bodega madre activa.
5. Adapta consultas, selección automática de bodega, políticas de acceso, contexto global/sucursal, semillas y frontend. Centralidad procede de su función y vínculo válido, nunca de branch_id nulo. Expón el vínculo en detalle/edición de forma comprensible.
6. Preserva compras/documentos históricos confirmados. Resuelve su origen por la bodega cuando corresponda sin reescribir el historial. Comprueba creación de una nueva recepción central y el acceso a las anteriores.
7. Crea migración nueva y adaptación idempotente de datos con simulación, mapa por empresa, validación previa y recuperación. Ensaya sobre copia/base aislada. Antes de actualizar la demo habitual, respalda y comprueba el destino; no ejecutes una siembra que reinicie datos.

## Aceptación obligatoria

- B01-A1: migrar una empresa con bodega central sin sucursal conserva IDs de bodega/ubicaciones/HUs, cantidades, valores, movimientos y documentos; solo añade/cambia las relaciones organizacionales previstas.
- B01-A2: repetir adaptación no duplica matriz ni bodega; una matriz existente válida se reutiliza. Mapeos ambiguos se diagnostican sin escritura parcial.
- B01-A3: dos empresas permanecen aisladas. Se rechaza matriz de otra empresa y dos centrales/matrices activas incompatibles.
- B01-A4: usuario de sucursal conserva acceso a sus bodegas; usuario matriz opera recepción central; usuario global consulta ambas. Asociar matriz no concede acceso global por accidente.
- B01-A5: compras y traslados siguen encontrando la bodega madre; las pantallas muestran su matriz. Una recepción previa y otra nueva conservan navegación/origen.
- B01-A6: fallo a mitad de adaptación no deja relaciones incoherentes; documentar recuperación y cabeza de Alembic en la demo utilizada.

Ejecuta pruebas pertinentes y un recorrido de sucursal/bodega/compras según la guía. No reconstruyas la base habitual para probar. Actualiza esquema/API/RBAC si corresponde, crea entrega-bloque-01.md en la carpeta de esta guía y actualiza E01/E13 en la matriz. No comiences B02 automáticamente.

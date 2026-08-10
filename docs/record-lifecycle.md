# Ciclo de vida empresarial de registros

## Objetivo

El sistema distingue tres conceptos que no son intercambiables:

1. **Activo/inactivo**: disponibilidad operativa reversible. El registro sigue visible en
   consultas administrativas e historial.
2. **Finalizado/revocado**: cierre de una relación histórica, como una asignación de empleado a
   sucursal. La relación se conserva con su fecha y estado.
3. **Eliminado lógicamente**: registro creado por error y enviado a papelera. Se oculta de toda
   operación normal, conserva trazabilidad y puede restaurarse si no existe un conflicto.

No se realizan borrados físicos de datos maestros desde la API del ERP.

## Contrato de soft-delete

Toda entidad administrable incluida en la política utiliza:

- `deleted_at TIMESTAMPTZ NULL`
- `deleted_by UUID NULL REFERENCES users(id) ON DELETE SET NULL`
- `deletion_reason TEXT NULL`

Las consultas ORM excluyen `deleted_at IS NOT NULL` de manera global. Solo el repositorio de ciclo
de vida puede omitir ese filtro mediante `include_deleted=True`.

Operaciones comunes:

- `GET /api/v1/lifecycle/trash`: papelera de la empresa actual.
- `DELETE /api/v1/lifecycle/{resource}/{id}`: eliminación lógica con motivo obligatorio.
- `POST /api/v1/lifecycle/{resource}/{id}/restore`: restauración con revalidación.

El cliente nunca usa `DELETE` para desactivar. Los endpoints `activate` y `deactivate` mantienen el
estado operativo existente en cada módulo.

## Matriz de política

| Recurso | Activar/desactivar | Soft-delete/restaurar | Regla principal |
| --- | --- | --- | --- |
| Empresas | Sí | Sí | Sin recursos operativos visibles dependientes |
| Sucursales | Sí | Sí | Sin almacenes ni asignaciones históricas |
| Categorías de almacén | Sí | Sí | Sin almacenes asociados |
| Almacenes | Sí | Sí | Sin ubicaciones asociadas |
| Ubicaciones | Sí | Sí | Sin referencias operativas futuras |
| Usuarios | Suspender/reactivar | Sí | No autoeliminación, no último superadmin; revoca sesiones |
| Empleados | Estado laboral | Sí | Solo registros erróneos sin cuenta, asignación ni responsabilidad |
| Departamentos | No aplica actualmente | Sí | Sin empleados, hijos ni asignaciones |
| Roles personalizados | No aplica actualmente | Sí | Sin usuarios asignados; roles internos protegidos |
| Permisos personalizados | No aplica actualmente | Sí | Sin roles que los usen; catálogo estándar protegido |
| Categorías/subcategorías de producto | Sí | Sí | Sin hijos o productos relacionados |
| Unidades personalizadas | Configuración por empresa | Sí | Unidades estándar y unidades usadas están protegidas |
| Productos | Sí | Sí | Conservación obligatoria cuando exista historia transaccional |
| Proveedores/contactos | Sí | Sí | Proveedor sin contactos para eliminar; contactos independientes |
| Asignaciones empleado/departamento–sucursal | Finalizar/reactivar | No | Se preserva el historial |
| Bitácora, geografía, tokens y tablas transaccionales | No | No | Inmutables, técnicos o históricos |

## Reglas transversales

- El motivo de eliminación es obligatorio y tiene entre 3 y 500 caracteres.
- El alcance de empresa y sucursal se valida antes de cada mutación.
- Los eliminados no aparecen en listados, detalles, buscadores, selectores, mapas, contadores ni
  dashboards normales.
- La papelera requiere `lifecycle:read`; eliminar y restaurar requieren permisos específicos por
  recurso.
- Roles, permisos y unidades estándar no pueden eliminarse aunque se invoque la API directamente.
- Una restauración vuelve a validar padres visibles, propiedad empresarial y unicidad.
- Si el identificador fue reutilizado, la restauración responde con conflicto empresarial `409`.
- Las restricciones únicas de negocio son índices parciales `WHERE deleted_at IS NULL`, por lo que
  un registro eliminado no bloquea la corrección de un dato creado por error.
- Cada eliminación y restauración registra actor, empresa, recurso, fecha y motivo en la bitácora.
- Repetir una operación nunca debe producir borrado físico ni modificar el historial previo.

## UX

El menú de acciones conserva una taxonomía uniforme:

- Registro activo: `Desactivar` y, si la política lo admite, `Eliminar`.
- Registro inactivo: `Reactivar` y, si la política lo admite, `Eliminar`.
- Papelera: `Restaurar`.

`Eliminar` abre el diálogo visual común, explica que el registro irá a la papelera y solicita el
motivo. Los conflictos de dependencias se presentan en lenguaje funcional; nunca se expone un
mensaje técnico como `Request failed with status 409`.

## Migración y despliegue

1. `0025` agrega metadatos de eliminación, filtros compatibles, permisos e índices únicos
   parciales.
2. `0026` corrige restricciones heredadas e incorpora índices compuestos para consultar la
   papelera por tenant.
3. El backend puede desplegarse antes del frontend: los endpoints existentes de activación se
   conservan y no se cambia su semántica.
4. La semilla automática corre solo en el primer setup y guarda un marcador en `app_meta`.
   Un reinicio normal no restaura registros eliminados; una reconciliación explícita con
   `FORCE_SEED=true` consulta eliminados y recupera únicamente el registro canónico.
5. Antes de producción se ejecutan `alembic upgrade head`, pruebas de aislamiento, restauración,
   dependencias, auditoría y regresión de autenticación.

## Criterios de aceptación

- Activo → inactivo → activo conserva el registro y su identidad.
- Visible → eliminado → restaurado conserva el mismo identificador.
- Un eliminado devuelve `404` desde endpoints ordinarios y solo aparece en la papelera autorizada.
- Ninguna consulta de otra empresa puede observar, eliminar o restaurar el registro.
- Las dependencias históricas producen un `409` con mensaje comprensible.
- Un usuario eliminado no puede iniciar sesión ni renovar tokens.
- Una clave de negocio puede reutilizarse tras eliminar; restaurar luego detecta la colisión.
- La segunda ejecución ordinaria de la semilla no muta datos; la reconciliación explícita no
  duplica ni borra físicamente registros maestros.

# Guía de desarrollo: ciclo de vida de registros

## Propósito

Este documento es el contrato de implementación para cualquier módulo nuevo o cambio que maneje
activación, desactivación, finalización, eliminación lógica, papelera o restauración. Su objetivo es
mantener una experiencia uniforme, conservar la trazabilidad y evitar borrados accidentales o fugas
entre empresas y sucursales.

La política funcional vigente y la matriz completa de recursos están en
[`record-lifecycle.md`](./record-lifecycle.md). Esta guía explica **cómo extender esa política en el
código**.

## 1. Decisión obligatoria antes de desarrollar

Antes de agregar una acción destructiva, clasifique el caso:

| Necesidad del negocio | Operación correcta | Resultado |
| --- | --- | --- |
| Suspender temporalmente el uso de un registro | Activar/desactivar | Sigue visible para administración e historial |
| Terminar una relación con valor histórico | Finalizar/revocar | Conserva fechas, actor y relación histórica |
| Retirar un registro maestro creado por error | Soft-delete | Se oculta de la operación normal y va a la papelera |
| Corregir datos del registro | Editar | No altera su ciclo de vida |
| Eliminar bitácora, transacción o catálogo técnico | No permitido | El registro permanece inmutable |

Reglas:

- `is_active` y `deleted_at` **no son equivalentes**.
- `DELETE` nunca significa desactivar.
- Una asignación histórica se finaliza; no se elimina genéricamente.
- No se implementa borrado físico de datos maestros desde la API del ERP.
- Si la clasificación no está clara, se debe definir primero la regla de negocio y actualizar
  `record-lifecycle.md` antes de programar.

## 2. Contrato de datos

### Entidades administrables

Las entidades creadas por usuarios que admitan papelera deben incorporar `SoftDeleteMixin`:

```python
class Example(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "examples"
```

Esto proporciona:

- `deleted_at`: fecha de eliminación lógica.
- `deleted_by`: usuario responsable, con `ON DELETE SET NULL`.
- `deletion_reason`: motivo funcional de 3 a 500 caracteres.

No duplique estas columnas en cada modelo. El mixin canónico se encuentra en
`backend/app/infrastructure/db/base.py`.

### Consultas

- Las consultas ordinarias deben conservar el filtro ORM global `deleted_at IS NULL`.
- Solo la infraestructura de ciclo de vida puede usar `include_deleted=True`.
- Listados, detalles, búsquedas, selects, mapas, dashboards, exportaciones y contadores deben excluir
  eliminados.
- Un acceso ordinario por ID a un eliminado debe responder `404`, no revelar que existe en la
  papelera.
- Los joins y subconsultas nuevas también deben respetar el filtro; se deben cubrir con una prueba de
  regresión.

### Unicidad y claves foráneas

- Las claves únicas reutilizables deben implementarse como índices únicos parciales con
  `WHERE deleted_at IS NULL`.
- El índice debe incluir el alcance correcto (`company_id` y, solo cuando el dominio lo requiera,
  `branch_id`).
- Las referencias históricas no deben usar `ON DELETE CASCADE` hacia datos maestros.
- Use `RESTRICT`/`NO ACTION` para relaciones de negocio y `SET NULL` únicamente para metadatos como
  `deleted_by`.
- Una restauración debe volver a validar unicidad, tenant, padres visibles y dependencias.
- Todo cambio de esquema se entrega mediante una migración Alembic incremental; no se modifica una
  base desplegada restaurando SQL manualmente.

## 3. Implementación backend por capas

Respete la arquitectura `domain -> application -> infrastructure -> api/v1`.

### Paso 1: registrar la política

Agregue el recurso al registro/política del repositorio de ciclo de vida y defina explícitamente:

- nombre estable del recurso usado por la API y el frontend;
- modelo y columna primaria;
- alcance global, por empresa o por sucursal;
- permiso para eliminar y permiso para restaurar;
- si el registro es de sistema/protegido;
- dependencias que bloquean la eliminación;
- dependencias y colisiones que bloquean la restauración;
- etiqueta legible que se mostrará en papelera y bitácora.

No escriba soft-delete ad hoc directamente en un router o repositorio de módulo.

### Paso 2: separar los endpoints

El contrato común de papelera es:

```text
GET    /api/v1/lifecycle/trash
DELETE /api/v1/lifecycle/{resource}/{record_id}
POST   /api/v1/lifecycle/{resource}/{record_id}/restore
```

El cuerpo del `DELETE` es:

```json
{ "reason": "Registro creado por duplicado" }
```

La activación y desactivación permanecen en el módulo:

```text
POST /api/v1/{resource}/{record_id}/activate
POST /api/v1/{resource}/{record_id}/deactivate
```

Evite contratos ambiguos como `DELETE /contact/{id}` que únicamente cambien `is_active`. Si existe
un contrato heredado, mantenga compatibilidad de manera explícita y márquelo como obsoleto mientras
el frontend migra al endpoint correcto.

### Paso 3: reglas de negocio

Las validaciones se ejecutan en backend aunque la interfaz oculte la acción:

- verificar empresa y sucursal antes de consultar o mutar;
- bloquear recursos estándar, protegidos o del sistema;
- bloquear autoeliminación de usuarios y eliminación del último superadministrador;
- revocar sesiones, refresh tokens y tokens de restablecimiento al eliminar un usuario;
- comprobar únicamente dependencias relevantes y activas según la política;
- devolver `409` con código estable y mensaje funcional cuando una dependencia o colisión impida la
  operación;
- hacer `DELETE` y `restore` idempotentes sin reescribir el historial innecesariamente.

Nunca confíe en que ser superadministrador implica saltarse silenciosamente el tenant. Los flujos
globales deben estar definidos y autorizados expresamente.

### Paso 4: RBAC

Toda capacidad nueva se registra en `backend/app/application/rbac/catalogue.py`.

Use permisos separados cuando correspondan:

```text
resource:read o resource.view
resource:activate
resource:deactivate
resource:delete
resource:restore
lifecycle:read
```

Respete la convención existente del módulo; no introduzca una tercera variante de nombres. La API
debe verificar el permiso específico y el frontend debe usarlo solo para decidir visibilidad y
habilitación. Ocultar un botón no reemplaza la autorización backend.

### Paso 5: auditoría

Las mutaciones de ciclo de vida son auditoría obligatoria (`required=True`):

- `ACTIVATE`
- `DEACTIVATE`
- `LOGICAL_DELETE`
- `RESTORE`
- `REVOKE` o `END_ASSIGNMENT`, cuando aplique

Registre actor, empresa, sucursal cuando corresponda, recurso, ID, etiqueta, motivo y estados
`before`/`after`. La operación debe fallar si no puede persistirse su auditoría obligatoria. Nunca
audite secretos, contraseñas ni tokens.

### Paso 6: errores públicos

- Use errores estructurados con un `code` estable y un mensaje en español comprensible.
- No exponga SQL, stack traces, nombres internos ni mensajes como `Request failed with status 409`.
- Reserve `404` para registros no visibles/no existentes, `403` para autorización y `409` para una
  regla de negocio o conflicto de restauración.

## 4. Implementación frontend

### Confirmación reutilizable

El diálogo global ya está montado en el layout raíz. Para toda acción sensible use
`confirmation.request` desde `frontend/src/lib/stores/confirmation.svelte.ts`.

Ejemplo de eliminación lógica:

```ts
confirmation.request({
  kind: 'delete',
  title: 'Eliminar producto',
  description: 'El producto se enviará a la papelera y dejará de estar disponible.',
  confirmLabel: 'Enviar a la papelera',
  resourceName: product.name,
  requireReason: true,
  reasonLabel: 'Motivo de eliminación',
  execute: async (reason) => {
    await api.lifecycle.delete('products', String(product.id_product), reason!);
    await reloadProducts();
  }
});
```

Ejemplo de desactivación:

```ts
confirmation.request({
  kind: 'deactivate',
  title: 'Desactivar producto',
  description: 'No podrá utilizarse en nuevas operaciones hasta que sea reactivado.',
  confirmLabel: 'Desactivar',
  resourceName: product.name,
  execute: async () => {
    await api.products.deactivate(String(product.id_product));
    await reloadProducts();
  }
});
```

Ejemplo de restauración:

```ts
confirmation.request({
  kind: 'restore',
  title: 'Restaurar registro',
  description: 'El registro volverá a estar disponible en su módulo.',
  confirmLabel: 'Restaurar',
  resourceName: record.label,
  execute: async () => {
    await api.lifecycle.restore(record.resource, record.record_id);
    await reloadTrash();
  }
});
```

Reglas obligatorias:

- No crear modales de confirmación específicos por módulo.
- No usar `window.confirm`, `window.alert` ni confirmaciones nativas del navegador.
- La eliminación lógica siempre solicita motivo; desactivar normalmente no lo requiere.
- Use `kind` para obtener la semántica visual común: peligro, advertencia o restauración.
- El texto debe explicar el efecto, la reversibilidad y, si aplica, la dependencia que bloquea.
- La acción debe mostrar estado de carga, impedir doble envío, conservar el foco y presentar el error
  dentro del diálogo.
- Mantenga accesibilidad: nombre accesible, navegación por teclado, `Escape`, focus trap y retorno del
  foco al disparador. Estas capacidades ya están resueltas por el componente compartido.

### Menús y visibilidad

En cards y tablas use el menú kebab/meatball común:

- activo: `Editar`, `Desactivar`, `Eliminar`;
- inactivo: `Editar`, `Reactivar`, `Eliminar`;
- papelera: `Restaurar`;
- protegido/estándar: no mostrar acciones prohibidas;
- usuario actual: no mostrar autoeliminación o autodesactivación si está bloqueada.

La acción se muestra solo con el permiso correspondiente, pero el servidor sigue siendo la autoridad.
No muestre simultáneamente `Desactivar` y `Reactivar`.

### Estado local y caché

Después de una mutación:

- invalide o recargue el listado, contador, detalle, selects y papelera afectados;
- ajuste la página si el último elemento de una página desaparece;
- limpie una sucursal/empresa seleccionada si dejó de ser visible;
- no inserte manualmente respuestas parciales en múltiples stores si existe una función canónica de
  recarga;
- preserve estados de loading, empty, error y success conforme al design system Geist y HIG.

## 5. Papelera

Toda entidad nueva con soft-delete debe integrarse con la papelera existente:

1. Incluir el recurso en la política backend.
2. Añadir su permiso de restauración al mapa del frontend.
3. Proporcionar etiqueta humana y datos mínimos seguros.
4. Respetar paginación y búsqueda en base de datos; no cargar el tenant completo para paginar en
   memoria.
5. Permitir ver solo recursos para los que el usuario tenga autorización.
6. Al restaurar, refrescar papelera y módulo de origen.

Las empresas tienen flujo de papelera accesible para superadministración aun cuando no exista una
empresa activa seleccionada. No generalice esta excepción a recursos con alcance de tenant.

## 6. Secuencia recomendada para un recurso nuevo

1. Clasificar el ciclo de vida y documentar sus reglas y dependencias.
2. Agregar modelo/mixin y migración con índices parciales y FKs seguras.
3. Registrar la política en el repositorio/servicio central de ciclo de vida.
4. Agregar permisos al catálogo RBAC y asignarlos únicamente a roles adecuados.
5. Implementar activación/desactivación en el módulo, sin reutilizar `DELETE`.
6. Integrar auditoría obligatoria y errores estructurados.
7. Verificar filtros de eliminados en todos los caminos de lectura.
8. Integrar menú de acciones, diálogo común y papelera en frontend.
9. Actualizar seed solo si el recurso forma parte del setup canónico; el seed ordinario nunca debe
   resucitar eliminados.
10. Ejecutar pruebas de modelo, repositorio, servicio, API, RBAC, tenant y UI.
11. Validar migración `upgrade`, ciclo de downgrade soportado y despliegue backend-before-frontend.
12. Actualizar `record-lifecycle.md` y esta guía si se introduce una nueva categoría de política.

## 7. Pruebas mínimas obligatorias

### Backend

- activo -> inactivo -> activo conserva ID y datos;
- visible -> eliminado -> restaurado conserva ID;
- eliminado no aparece en list/get/search/select/count/dashboard;
- consulta directa ordinaria devuelve `404`;
- motivo vacío, menor de 3 o mayor de 500 caracteres es rechazado;
- dependencia activa bloquea con `409` y mensaje funcional;
- restauración con clave reutilizada responde `409`;
- empresa/sucursal ajena no puede listar, eliminar ni restaurar;
- permisos insuficientes responden `403`;
- recursos protegidos se bloquean incluso invocando la API directamente;
- auditoría incluye `before`, `after`, actor, tenant y motivo;
- usuario eliminado pierde acceso y sesiones;
- repetir delete/restore no produce borrado físico ni auditoría corrupta;
- índice parcial permite reutilizar una clave tras soft-delete.

### Frontend

- cada acción se muestra solo para el estado y permiso correctos;
- eliminar exige motivo y no permite doble envío;
- cancelar y `Escape` no mutan datos y restauran el foco;
- los conflictos se muestran dentro del diálogo en lenguaje no técnico;
- restaurar actualiza papelera, contador y vista de origen;
- no existe `confirm()`/`alert()` en el flujo;
- estados loading, empty, error y success funcionan en claro y oscuro;
- la navegación por teclado y los nombres accesibles son válidos.

### Comandos de validación

Ejecute al menos los comandos aplicables dentro de los contenedores del proyecto:

```powershell
docker compose exec -T backend uv run alembic current
docker compose exec -T backend uv run pytest -q
docker compose exec -T backend uv run ruff check app tests
docker compose exec -T frontend pnpm lint
docker compose exec -T frontend pnpm check
docker compose exec -T frontend pnpm test:unit -- --run
docker compose exec -T frontend pnpm build
```

Las pruebas destructivas de migración o limpieza se ejecutan únicamente sobre una base aislada de
tests, nunca sobre desarrollo compartido, Supabase o producción.

## 8. Patrones prohibidos

- `session.delete(...)`, `DELETE FROM ...` o cascadas físicas para datos maestros desde flujos ERP.
- Cambiar `is_active = false` dentro de un endpoint llamado `DELETE`.
- Consultar eliminados con `include_deleted=True` fuera de infraestructura autorizada.
- Usar unicidad absoluta cuando la clave debe poder reutilizarse después de eliminar.
- Ocultar eliminados solo en frontend.
- Permitir restaurar sin revalidar tenant, padre, dependencias y unicidad.
- Conceder acceso a papelera por tener permiso genérico de edición.
- Crear un modal distinto o usar mensajes nativos para cada módulo.
- Mostrar errores HTTP o mensajes técnicos al usuario.
- Resucitar registros eliminados durante un seed o reinicio normal.
- Saltarse auditoría porque la operación ya se registró en logs técnicos.

## 9. Checklist de revisión y Definition of Done

Un cambio de ciclo de vida está terminado solo si todas las respuestas son afirmativas:

- [ ] La operación fue clasificada como activar, finalizar, eliminar o editar.
- [ ] La política y las dependencias están documentadas.
- [ ] No existe borrado físico de datos maestros.
- [ ] La migración usa campos comunes, índices parciales y FKs seguras.
- [ ] Todos los caminos de lectura excluyen eliminados.
- [ ] Tenant, sucursal, RBAC y recursos protegidos se validan en backend.
- [ ] Delete y restore tienen auditoría obligatoria y motivo cuando corresponde.
- [ ] Los errores tienen código estable y texto funcional en español.
- [ ] El frontend reutiliza `confirmation.request` y el menú de acciones común.
- [ ] La papelera respeta permisos, búsqueda y paginación.
- [ ] Cachés, stores, contadores y selección de contexto quedan consistentes.
- [ ] Existen pruebas positivas, negativas, de restauración y aislamiento.
- [ ] Alembic, Ruff, ESLint, Svelte Check, Vitest, pytest y build aplicables pasan.
- [ ] Se validó manualmente el flujo en modo claro/oscuro y con teclado.
- [ ] La documentación de política fue actualizada si cambió el comportamiento.

## 10. Archivos de referencia

- Política funcional: `docs/record-lifecycle.md`
- Mixin de soft-delete: `backend/app/infrastructure/db/base.py`
- Filtro ORM global: `backend/app/infrastructure/db/session.py`
- Servicio de ciclo de vida: `backend/app/application/lifecycle/service.py`
- Repositorio y políticas: `backend/app/infrastructure/repositories/lifecycle_repository.py`
- Router común: `backend/app/api/v1/routers/lifecycle.py`
- Catálogo RBAC: `backend/app/application/rbac/catalogue.py`
- Cliente frontend: `frontend/src/lib/api/client.ts`
- Store de confirmación: `frontend/src/lib/stores/confirmation.svelte.ts`
- Diálogo visual: `frontend/src/lib/components/ui/ConfirmActionDialog.svelte`
- Papelera: `frontend/src/routes/(app)/trash/+page.svelte`


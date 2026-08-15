# Autorización de recursos multiempresa

## Regla de seguridad

`X-Company-ID` selecciona el contexto operativo de la solicitud; no demuestra que
un recurso pertenezca a esa empresa. Un endpoint que recibe un UUID global debe
validar dos condiciones independientes:

1. `require_permission(...)` valida el permiso, la existencia de la empresa y la
   membresía actual; solo entonces guarda el UUID en
   `request.state.effective_company_id`.
2. Después de cargar el recurso, el router deriva su empresa desde relaciones
   persistidas y la compara con el contexto efectivo mediante
   `require_resource_company(...)`.

El segundo control también se aplica a superusuarios. Un superusuario puede elegir
otra empresa, pero no mezclar en una misma solicitud el contexto A con un recurso
de B.

## Patrón para ubicaciones

```python
from app.api.v1.company_access import require_resource_company

location = await session.get(Location, location_id)
if location is None:
    raise HTTPException(404, "Ubicación no encontrada.")

warehouse = await session.get(Warehouse, location.warehouse_id)
branch = await session.get(Branch, warehouse.branch_id) if warehouse else None
resource_company_id = branch.company_id if branch else None
require_resource_company(
    request,
    resource_company_id,
    not_found_detail="Ubicación no encontrada.",
)
```

La empresa nunca debe obtenerse del body, query string, cabecera duplicada ni de
un DTO producido por el cliente. Para operaciones que también deban comprobar
membresía o empresa activa puede usarse `require_resource_company_access(...)`.

## Respuesta ante cruce de empresas

El helper responde `404` tanto si el recurso no existe como si pertenece a otra
empresa. Esto evita convertir IDs globales en un oráculo de enumeración de datos
entre tenants. No incluir en logs accesibles al cliente el UUID ni el nombre de la
empresa propietaria.

## Endpoints que deben aplicarlo

- lectura, edición, bloqueo, retiro, restauración y etiquetas por ID;
- ejecución o consulta de un lote/plantilla por ID;
- descarga de errores o resultados de una importación;
- operaciones que acepten IDs de almacén, plantilla, ubicación padre o alias.

Para relaciones entre varios recursos se valida cada uno y luego se comprueba que
comparten empresa. Una FK válida no sustituye el control de autorización.

## Pruebas mínimas obligatorias

- contexto A + recurso A: permitido;
- contexto A + recurso B: `404`, incluso si el usuario pertenece a A y B;
- superusuario en contexto A + recurso B: `404`;
- solicitud sin contexto autorizado: `403`;
- dos dependencias que intentan fijar empresas distintas: `403`;
- recurso cuya cadena de pertenencia está rota: fallo cerrado, nunca `500`.

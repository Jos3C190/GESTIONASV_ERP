# Encargo para Luna: solicitudes ya incluidas en un consolidado

## Objetivo

Corrige el diagnóstico y la navegación de las solicitudes preseleccionadas al crear un consolidado. Si una solicitud ya pertenece a un consolidado activo, muestra cuál es y permite abrirlo. Conserva la protección contra duplicar pedidos. Implementa el arreglo; este documento no pide otro plan ni un rediseño.

Lee las instrucciones aplicables de AGENTS.md y `.agents/skills/feature-development/SKILL.md`. Respeta la arquitectura y las convenciones existentes. Hay cambios previos en el repositorio: no los reviertas, ni hagas commits.

## Diagnóstico confirmado

En la base local `erp_db`, la revisión de solo lectura encontró:

| Solicitud | ID | Estado | Consolidado existente |
| --- | --- | --- | --- |
| SCR-00036 | c51d7b8d-9c49-4649-ba88-1e4a57fd06b5 | approved | CD-00005, draft |
| SCR-00035 | 0fce4c21-8396-40ed-a63f-c66edfd5e985 | approved | CD-00005, draft |

La consulta de solicitudes elegibles respondió HTTP 200. El repositorio excluye las solicitudes vinculadas mediante sus detalles a consolidados cuyo estado no sea `cancelled`. Por ello estas dos solicitudes no aparecen en la respuesta. El frontend interpreta esa ausencia como detalle no disponible y muestra UUID abreviado, «No se pudo cargar el detalle» y «No está disponible para consolidar. Quítala para continuar».

El bloqueo contra duplicados es correcto. El mensaje mezcla una exclusión de negocio con un error de carga. SCR-00035 tiene varias líneas vinculadas: una consulta por joins puede repetir el mismo consolidado; deduplica las referencias.

Revalida los datos actuales antes de usar este caso como evidencia. No asumas que códigos, estados o vínculos permanecieron iguales. Otros errores históricos de permisos o sesión no demuestran la causa de este caso.

## Puntos de entrada

- `frontend/src/lib/features/purchase-requests/components/PurchaseConsolidationCreate.svelte`: `hydrateSelectedChunk`, `loadCandidates`, `selectedCandidatesById`, `selectedIdsWithoutDetails` y tarjetas de selección.
- `frontend/src/lib/api/purchase-consolidations.ts`: `eligibleRequests` envía `request_ids` como parámetros repetidos.
- `frontend/src/lib/types/purchase-consolidation.ts`.
- `backend/app/api/v1/routers/purchase_consolidations.py`: `list_eligible_requests` y comprobaciones de ámbito.
- `backend/app/infrastructure/repositories/purchase_consolidation_repository.py`: `list_approved_requests` y exclusión con `exists`.
- `backend/app/api/v1/schemas/purchase_consolidation.py` y casos de uso correspondientes.
- Pruebas existentes: `backend/tests/unit/test_purchase_consolidation_use_cases.py`, `frontend/tests/unit/PurchaseConsolidationDetail.test.ts`, `frontend/tests/unit/PurchaseConsolidationAdjudication.test.ts`. Localiza también cobertura pertinente antes de añadir pruebas.

## Comportamiento solicitado

1. Una solicitud accesible que ya esté consolidada debe mostrar su código real, por ejemplo:
   - **SCR-00035**.
   - **Ya incluida en CD-00005 · Borrador**.
   - **Abrir consolidado**, usando su ID real y la ruta existente.
   - **Quitar de esta selección**: solo elimina la selección local, nunca desvincula la solicitud del consolidado.
2. Resuelve explícitamente la razón de inelegibilidad desde el backend. Escoge el contrato aditivo más pequeño adecuado: metadatos compatibles o una consulta de resolución de seleccionadas. No deduzcas «ya consolidada» de una ausencia, no descargues todos los consolidados y no hardcodees los IDs del ejemplo.
3. Distingue solicitudes elegibles, ya consolidadas, de estado no elegible y no disponibles para el usuario. Los fallos transitorios deben ofrecer reintento y no convertirse en una exclusión de negocio.
4. Conserva el ámbito de empresa, sucursal y permisos. No reveles códigos, IDs ni estados de solicitudes o consolidados inaccesibles. Un HTTP 403 no significa «ya consolidada». El enlace debe respetar el permiso de consultar el destino.
5. Deduplica referencias por ID de consolidado. Si existen varios vínculos válidos, represéntalos correctamente en vez de elegir el primero arbitrariamente. Conserva las reglas actuales para consolidados cancelados.
6. Mantén deshabilitada la creación mientras queden seleccionadas solicitudes inelegibles o sin resolver. Al quitar esas selecciones, las solicitudes válidas deben poder continuar normalmente.
7. Conserva la selección entre filtros, la hidratación por lotes, el manejo de lotes con permisos mixtos, los controles contra respuestas tardías y el contexto de empresa. No pierdas información previamente cargada por un fallo transitorio.
8. Mantén la validación de duplicados al crear en el backend. Si otra operación consolida una solicitud entre selección y guardado, el conflicto debe ser comprensible; cuando el usuario tenga acceso, permite identificar y abrir el consolidado existente sin crear un duplicado.

No amplíes este encargo a retaceo, valoración, QR o adjudicación. No cambies estados ni cantidades para resolver el aviso.

## Pruebas y comprobación autorizadas

Añade o adapta pruebas focalizadas para:

- Solicitud aprobada sin consolidar: selección normal.
- Dos solicitudes en el mismo borrador: códigos legibles, referencia y enlace correctos; sin referencias repetidas por líneas.
- Selección mixta: quitar la inelegible permite continuar con la válida, sin desvincular registros.
- Error HTTP 500 o de red: reintento, sin diagnóstico falso de consolidación.
- Empresa o sucursal no autorizada: sin filtración de datos.
- Vínculo a consolidado cancelado: conserva la elegibilidad definida actualmente.
- Cambio de filtros/contexto o respuesta tardía: no sobrescribe el estado vigente.
- Conflicto concurrente al crear: no duplica el pedido.

Ejecuta las pruebas relevantes y las comprobaciones de tipos/lint aplicables a los archivos modificados. Antes de ejecutar fixtures destructivos, revisa su configuración y verifica que todas las conexiones de prueba apunten a una base aislada, nunca a `erp_db`.

Comprueba además la pantalla real usando la sesión disponible y el caso existente: las tarjetas deben explicar el motivo y el enlace debe abrir el consolidado correcto. Esta comprobación es de solo lectura: no crees, canceles, borres ni modifiques documentos comerciales para demostrar el arreglo. No reinicialices, migres ni siembres la base como solución al mensaje. Si la sesión o el entorno impiden comprobar el navegador, registra esa limitación y no declares esa aceptación como superada.

## Entrega

Deja una nota breve en `docs/solicitudes-ya-consolidadas-verificacion.md` con causa, solución, archivos, comandos y resultados reales de pruebas, comprobación de navegador y pendientes concretos. Distingue pruebas automáticas de validación en la aplicación. No declares completado lo que no verificaste.

El resultado esperado es que el usuario pueda entender por qué no puede volver a consolidar SCR-00035/SCR-00036 y continuar desde CD-00005, sin volver a pedir los productos.

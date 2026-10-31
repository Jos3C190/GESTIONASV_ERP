# Encargo Luna — ERS-B04: operación visible de traslados

Implementa las pantallas de vehículos, preparación, despacho, recepción e incidencias sobre el motor B03. El usuario debe poder elegir un producto en la bodega central, ver qué sucursales lo solicitan, preparar la cantidad correspondiente y seguir su traslado hasta la recepción y revisión en destino.

## Decisión vigente y punto de partida — 19/10/2026

El usuario autoriza construir B04 y **reserva la revisión completa de B01–B08 para el cierre de B08**. Realiza las comprobaciones técnicas focalizadas de este bloque; conserva los recorridos manuales pendientes para ese cierre. No hagas ahora una auditoría general ni declares aprobada la aceptación visual integrada. No inicies B05 automáticamente.

Según la entrega B03, la demo `erp_db` está en Alembic `0086`, con respaldo, ensayo aislado y API publicada. Ese informe registra 6 pruebas de integración, 3 E2E de traslados y 1 de migración aprobadas: son evidencia previa, no resultados ejecutados por B04. Comprueba el contrato efectivo que vas a consumir y corrige únicamente dependencias necesarias para que B04 funcione.

Lee antes de implementar:

- [Guía oficial](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-03/04/07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md) y [seguimiento](C:/Developer/GESTIONASV_ERP/docs/ers-v1/matriz-y-seguimiento.md).
- [Entrega B03](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-03.md) y [evidencia B03](C:/Developer/GESTIONASV_ERP/tmp/ers-v1/bloque-03/evidencia-2026-10-19.md).
- Sección 18 de [API](C:/Developer/GESTIONASV_ERP/docs/api.md), [RBAC](C:/Developer/GESTIONASV_ERP/docs/rbac-model.md), router y esquemas de `inventory_transfers` en el backend.

## Responsabilidad y archivos

Eres responsable del cliente tipado, componentes y rutas de traslados/vehículos, entrada desde Almacenes, comprobaciones focalizadas y documentación B04. No estás solo en el repositorio: conserva los cambios ajenos y adapta tu implementación a ellos. Reutiliza:

- [Ruta Traslados](<C:/Developer/GESTIONASV_ERP/frontend/src/routes/(app)/transfers/+page.svelte>).
- [Abastecimiento](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/components/TransferSupplyDashboard.svelte).
- [Unidades en Almacenes](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte).
- [Servicios](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/services.ts), [tipos](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/types.ts) y [navegación](C:/Developer/GESTIONASV_ERP/frontend/src/lib/navigation.ts).

Aplica las reglas y skills pertinentes del proyecto: Svelte 5 Runes, componentes existentes, tokens, temas claro/oscuro y español es-SV. La postergación de la revisión completa a B08 es una instrucción expresa del usuario. Evita rediseñar módulos ajenos.

## 1. Consumir el contrato B03

Todas las rutas nuevas parten de `/api/v1/inventory/transfers`:

| Acción | Método y ruta relativa |
| --- | --- |
| Demanda por producto/sucursal | `GET /demand` |
| Listar/crear vehículos | `GET /vehicles`, `POST /vehicles` |
| Activar/desactivar vehículo | `PATCH /vehicles/{vehicle_id}` |
| Listar/crear preparaciones | `GET` y `POST` sobre la raíz, sin barra final |
| Consultar/editar preparación | `GET /{transfer_id}`, **`PUT /{transfer_id}`** |
| Cancelar, despachar, recibir | `POST /{transfer_id}/cancel`, `/dispatch`, `/receive` |
| Abrir/resolver incidencia | `POST /{transfer_id}/incidents`, `/incidents/resolve` |

Nota de contrato comprobada al redactar este encargo: el router implementa **PUT** para editar preparación. La tabla de entrega B03 dice PATCH en esa fila; corrige esa referencia documental al integrar, sin inventar un endpoint alternativo. El PATCH de vehículo sí es correcto.

Usa los DTO y errores efectivos; respeta los campos requeridos por PUT, incluso los que admiten null. Las cantidades viajan como decimales con hasta seis posiciones; evita pérdidas de precisión y conversiones inferidas del nombre comercial. Producto, SKU, unidad/presentación, lote canónico y HU se obtienen del API.

## 2. Producto y sucursales solicitantes

Restituye la navegación por producto: existencias disponibles en central → sucursales solicitantes → solicitud/línea → preparar traslado. Debe estar accesible desde Traslados y desde la acción de Almacenes, conservando producto y HU seleccionados.

Muestra nombre del producto como identificación principal, SKU, presentación/unidad real, lote, HU, disponible y desglose por sucursal con SCR, fecha requerida, solicitado, asignado, despachado, en tránsito, recibido y pendiente. Usa las relaciones estructuradas de B03. Un registro histórico sin asociación verificable se identifica como legado.

`quantity_pending` de B03 significa solicitado menos asignado: incluye asignaciones a preparaciones activas y **no significa pendiente de recibir**. Etiqueta ese dato como «Pendiente de asignar». Muestra aparte el avance de recepción, sin sumar dos veces la misma solicitud ni confundir unidades de compra con unidades base. Los totales no pueden depender solo de la página visible.

Seleccionar una sucursal con demanda prellena el destino y los vínculos de solicitud. Mantén envío manual de productos sin demanda y excedente sobre lo solicitado, con existencia suficiente y motivo explícito. El excedente no debe atribuirse artificialmente a otra solicitud. Distingue carga, error, permiso insuficiente y demanda realmente vacía.

## 3. Preparación, vehículos y despacho

Permite guardar, recuperar, editar y cancelar documentos en preparación. Guardar una preparación no mueve ni reserva stock; el despacho valida la disponibilidad actual. Cerrar un panel o volver a la lista no equivale a cancelar un documento guardado.

Reutiliza el acceso existente de flota/navegación para ofrecer el catálogo mínimo de vehículos: código, nombre y estado activo/inactivo. La ubicación móvil la crea el servidor. Un receptor de sucursal no necesita consultar el catálogo reservado a matriz para visualizar o recibir su documento.

Antes de confirmar despacho muestra origen, destino, vehículo activo, productos, cantidades/unidades y asignaciones/excedentes. Despachar requiere una acción explícita. Cancelar solo está disponible antes del despacho; después se usan recepción e incidencias. Refresca existencia y demanda tras cada operación confirmada.

## 4. Recepciones e incidencias

Ofrece listado y detalle de documentos con filtros útiles y estados visibles: «En preparación», «En tránsito», «Recibido», «Con incidencia» y «Cancelado». El receptor ve sus entradas según su ámbito y selecciona una ubicación válida de recepción/cuarentena de la bodega destino.

Registra cada recepción parcial: 10 despachadas y 8 recibidas dejan 2 en tránsito; recibir luego 2 completa el documento. No rellenen ni confirmen cantidades automáticamente al abrir. Muestra historial de recepciones con cantidades, fecha y actor cuando el contrato los exponga.

Explica el siguiente paso: «Traslado recibido; mercancía en cuarentena, pendiente de revisión» cuando corresponda. Después de verificar medidas y etiqueta y liberar, la HU muestra «Revisión terminada · disponible para uso». Recibir un traslado no implica liberar stock automáticamente.

Las incidencias guardan motivo y referencia de evidencia según B03. Permite resolver únicamente las acciones admitidas por el servidor y conserva el historial. B03 no tiene comando de retorno; pérdidas/mermas requieren el ajuste autorizado de B05. No ofrecer cierre que borre remanentes, devolución ficticia ni controles que simulen una función aún pendiente.

## 5. Un solo recorrido desde Almacenes y fin del bucle

«Trasladar a sucursal» abre el mismo flujo documental con HU/producto/origen conservados y las sucursales solicitantes visibles. Todos los nuevos despachos y recepciones pasan por B03, incluyendo acceso directo al API. Revisa los consumidores anteriores y adapta el servidor donde sea necesario para que la compatibilidad legada quede acotada al histórico verificable; conserva las demás operaciones legítimas del motor genérico. Documenta ese mapa de consumidores, sin fabricar vehículos o despachos para registros antiguos.

«Dividir unidad» queda como operación opcional bajo otras acciones. Abrir, cerrar, cancelar, consultar QR, revisar o reimprimir etiquetas jamás debe ejecutar división, despacho o recepción como efecto de renderizado o navegación. Una HU disponible representa un proceso de revisión terminado, aunque aún se pueda consultar o dividir por una necesidad posterior.

Para despachos parciales, usa la cantidad prevista del contrato y comprueba la conducta del motor al mover parte de una HU. Toda separación necesaria se explica y se confirma una sola vez; si el motor exige preparación física previa, usa la división existente como paso deliberado, conservando el lote y sus requisitos de revisión. No fuerces mover toda la HU ni encadenes divisiones para terminar el flujo. Conserva remanentes exactos y no inventes un incremento mínimo por llamarse «Caja».

## 6. Reintentos, autorización y experiencia

- Conserva la misma clave idempotente para reintentar una acción cuyo resultado sea incierto; una acción nueva o cuerpo cambiado tiene otra clave. Bloquea doble envío mientras está en curso. No generes una nueva clave para cada reintento de red.
- B03 devuelve el snapshot original al repetir una clave. Después del éxito, consulta el estado actual del documento para evitar que un reintento muestre un estado anterior como vigente.
- Al cambiar empresa/sucursal, invalida respuestas atrasadas y estado operativo del contexto anterior; ninguna confirmación debe enviarse bajo una empresa diferente de aquella donde se preparó.
- Conserva los permisos `inventory:read`, `inventory:move` e `inventory:receive` y el alcance por empresa/origen/destino. No concedas acceso global ni expongas costo global para facilitar una recepción.
- Usa etiquetas y acciones comprensibles, navegación por teclado, foco y errores junto al campo. Mantén uso móvil y ambos temas. Un fallo no debe mostrarse como cero existencias ni cero solicitudes.

## Aceptación y comprobación focalizada

| Criterio | Resultado requerido |
| --- | --- |
| B04-A1 | Producto → sucursal solicitante → preparación → vehículo → despacho → recepción, conservando nombres, unidades y origen sin memorizar códigos. |
| B04-A2 | Cantidad pendiente, envío manual y excedente justificado; solo cambia el avance de las solicitudes realmente enlazadas. Cancelar preparación libera su asignación sin mover inventario. |
| B04-A3 | Recibir 8 de 10 conserva 2 en tránsito; recibir las 2 restantes completa el traslado y mantiene cuarentena/revisión en destino. Incidencia conserva cantidades hasta una resolución autorizada. |
| B04-A4 | Abrir/cerrar/cancelar paneles y consultar etiquetas no crea HUs ni movimientos. Reintentos, doble clic y respuestas atrasadas no duplican acciones ni mezclan empresas. |
| B04-A5 | Demanda cero, errores y permisos se distinguen. Filtros/paginación no alteran totales ni pierden la selección; nombre del producto y unidad se ven junto a la HU. |
| B04-A6 | Emisor, receptor y usuario global reciben únicamente las acciones/datos autorizados; cliente usa PUT correcto y un solo camino de despacho/recepción. Vehículo inactivo/con stock y ubicaciones no válidas se rechazan correctamente. |
| B04-A7 | Contrato de persistencia verificado con API de pruebas. Recorrido autenticado completo, recarga, móvil, teclado y temas quedan registrados como aceptación manual pendiente para B08. |

Ejecuta Vitest de los componentes/servicios afectados, comprobación de tipos Svelte, lint de archivos tocados y build. Añade pruebas significativas de demanda, preparación sin mutación, cantidades parciales, permisos, idempotencia y cambio de contexto; identifica las respuestas simuladas como tales. Si modificas backend, cubre el puente y sus restricciones con integración/E2E focalizadas, aprovechando pruebas existentes.

Antes de pruebas que reconstruyan esquema, inspecciona fixtures y DSN: solo `erp_db_test`, en serie. Preserva demo, IDs, saldos y etiquetas; no reabras el saldo inicial ni ejecutes semillas destructivas. B04 parte de 0086: si una corrección requiere migración, usa una sucesora desde la cabeza efectiva, respaldo y ensayo aislado antes de tocar la demo.

**La auditoría general, pruebas manuales completas y aceptación visual B01–B08 se realizan al finalizar B08.** En B04 no repitas todas las suites anteriores ni bloquees la entrega por el recorrido visual aplazado. Corrige los fallos técnicos de tu alcance y registra las limitaciones reales. No se exige lector ni impresión física para la demostración ficticia.

## Entrega documental

Crea `docs/ers-v1/entrega-bloque-04.md` y evidencia fechada en `tmp/ers-v1/bloque-04/`. Incluye archivos cambiados, contratos/correcciones de B03 necesarios, comandos con resultados reales, criterio A1–A7 y su estado, compatibilidad histórica y pendientes de B05/B08. No llames «probado» a un recorrido manual aplazado.

Actualiza E06/E07/E13 en la matriz, el estado de la guía y el manual de traslados existente; si falta, crea `docs/ers-v1/manual-traslados.md`. Documenta pasos de operador, diferencias entre guardar/despachar/recibir/liberar y escenarios manuales que se ejecutarán en B08. Actualiza API/RBAC solo si cambia su contrato. Termina con el resumen B04 y sus pendientes, sin iniciar B05.

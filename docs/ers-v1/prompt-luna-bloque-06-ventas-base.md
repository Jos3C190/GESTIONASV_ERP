# Encargo Luna — ERS-B06: documentos comerciales sin entrega

## Decisión vigente — preparación del encargo

Ejecuta únicamente B06 y las correcciones de dependencias imprescindibles para su funcionamiento. Completa sus comprobaciones técnicas y documentación. La revisión completa de B01–B08 y la aceptación visual autenticada se harán al finalizar B08, por decisión expresa del usuario. **No inicies B07 ni B08.**

B05 quedó implementado con comprobaciones focalizadas: 4 pruebas unitarias, 4 de integración y 9 frontend; migración documentada 0087 y respaldo/restauración en base aislada. Son antecedentes, no una auditoría nueva ni aceptación integral. B05 conserva pendientes de perfiles API, concurrencia y navegador consignados en su entrega; mantenlos visibles para B08. Si uno impide B06, corrige esa dependencia y demuestra el resultado, sin convertir este encargo en una revisión completa de bloques anteriores.

Antes de crear una migración comprueba la cabeza efectiva: 0087 es la última documentada, no una autorización para asumir que sigue siendo la actual. Lee `.agents/AGENTS.md` y aplica las skills pertinentes. Presenta un plan corto con contratos, estados y permisos antes de implementar; continúa con la construcción dentro de este alcance.

Implementa los prerrequisitos comerciales necesarios para la integración de inventario. Lee [guía](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-06/07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md) e informes de dependencias. No estás solo en el repositorio; preserva otros cambios. La entrega física corresponde a B07.

Lectura de continuidad: `docs/ers-v1/entrega-bloque-05.md`, `docs/ers-v1/matriz-y-seguimiento.md` y el contrato previsto de `docs/ers-v1/prompt-luna-bloque-07-entregas.md`. Leer B07 sirve para preparar identificadores y pendientes por línea; no autoriza implementarlo.

## Responsabilidad

Responsable de cliente básico, cotización de venta, conversión y venta confirmada, en dominio/aplicación/infraestructura/API/UI. Especifica contratos para B07/B08. Reutiliza catálogos de producto, unidades/conversiones, empresa/sucursal, auditoría, códigos documentales y componentes disponibles. [La navegación actual](C:/Developer/GESTIONASV_ERP/frontend/src/lib/navigation.ts) contiene entradas provisionales que debes sustituir solo cuando su ruta sea funcional.

Puntos concretos de inspección bajo `C:/Developer/GESTIONASV_ERP`:

- `backend/app/infrastructure/models/catalog.py` y sus servicios de producto/variantes/unidades: existen `can_sell`, `sale_unit`, nombres comerciales y unidad base. Respeta su identidad y conversiones reales.
- `backend/app/api/v1/company_access.py`, `deps.py`, `application/rbac/catalogue.py` y el catálogo/asignaciones de permisos.
- `backend/app/infrastructure/db/session.py`: la sesión puede confirmar al capturar `AppError`. Cada operación comercial compuesta debe tener rollback/savepoint explícito.
- Patrones de documentos de compras para reutilizar componentes y convenciones, conservando separados cotización de compra y cotización de venta.
- `frontend/src/lib/navigation.ts`, `stores/route-titles.ts`, componentes compartidos, API client y protección de rutas por permisos/contexto.

En la preparación del encargo, Clientes, Cotizaciones de venta y Ventas siguen apuntando a placeholders. Comprueba el estado real antes de crear entidades nuevas; reutiliza cualquier implementación equivalente que ya exista. No uses reset/clean ni reviertas trabajo ajeno.

## Alcance comercial mínimo

Cliente por empresa con código/nombre/estado y contacto opcional. Proporciona alta, consulta y selección reales para que el flujo sea ejecutable sin insertar datos manualmente en la base. Conserva datos históricos al desactivar. No inventar datos fiscales del cliente.

El código del cliente es único por empresa. Su catálogo es empresarial; los documentos comerciales pertenecen además a una sucursal autorizada. Una desactivación impide nuevas operaciones según la transición definida, pero conserva la lectura de documentos históricos y sus snapshots. Permite actualizar sus datos básicos con auditoría. No implementes eliminación física de clientes referenciados.

Cotización con cabecera, cliente, sucursal, moneda, vigencia, líneas de producto/unidad/cantidad, precio explícito y totales calculados en servidor. Permite borrador, confirmación, cancelación/vencimiento y conversión a venta. Convertir conserva origen y snapshots y es idempotente; esta etapa admite conversión completa de la cotización, sin conversiones parciales múltiples.

Contrato de conversión: una cotización confirmada y vigente crea una **venta en borrador** con enlace estable a la cotización y a sus líneas. Confirmar la venta es una acción explícita posterior. Mantén la condición de cotización convertida mediante estado o vínculo persistido y visible; no puede convertirse otra vez, incluso usando otra clave o después de cancelar la venta resultante. Un reintento válido devuelve la misma venta. No canceles automáticamente la venta al cancelar o vencer la cotización de origen: una cotización convertida conserva su historia y las acciones se realizan sobre la venta vinculada.

La vigencia se interpreta como fecha local de El Salvador, inclusiva hasta el fin del día indicado. Revalídala en servidor al convertir. Una cotización vencida/cancelada no se convierte. No hace falta un proceso periódico para materializar vencimiento si una proyección y la validación de comandos lo representan correctamente. Los cambios de contenido invalidan la confirmación anterior mediante revisión explícita; rechaza edición silenciosa de documentos confirmados/convertidos.

Venta con estados comerciales BORRADOR, CONFIRMADA y CANCELADA. La confirmación congela los términos; correcciones posteriores usan revisión/cancelación trazable según si existen entregas. Separar avance físico PENDIENTE/PARCIAL/COMPLETA, que será calculado desde entregas en B07. El frontend no puede decidir la cantidad entregada enviando un estado.

En B06 el recorrido obligatorio es venta desde cotización; no es necesario agregar una segunda vía de venta directa. La venta en borrador admite cambios comerciales autorizados y auditados, conservando sus vínculos de origen. Confirmar congela cliente, sucursal, moneda y líneas. Una venta confirmada sin entregas puede cancelarse con motivo e historial; su corrección se resuelve mediante un documento nuevo enlazado, sin sobreescribir la confirmada. Deja definido el punto de validación que B07 usará para impedir una cancelación incompatible con entregas existentes, sin inventar entregas o retornos en B06.

Precio comercial capturado expresamente y separado del costo promedio. Reutiliza convenciones de moneda y redondeo del proyecto. Si faltan reglas de impuestos/precios, mantén su alcance de demostración explícito sin implantar política fiscal ni derivar precio del costo. No se pide DTE, caja, cobros, crédito ni un módulo completo de asignación de precios.

Para la demostración usa USD; rechaza monedas no soportadas en lugar de convertirlas implícitamente. Usa Decimal en servidor y persiste importes/conversiones con precisión definida. Documenta la regla de redondeo y de suma de líneas. Las cantidades deben ser positivas, finitas y compatibles con la precisión del motor; precios no negativos y explícitos, incluido cero si el usuario lo captura. Si el módulo aún no tiene descuentos/impuestos definidos, no los añadas arbitrariamente ni presentes el documento como factura fiscal. Los totales enviados por cliente no son fuente de verdad.

Cada línea conserva IDs de producto/variante/artículo inventariable, unidad comercial y base, factor de conversión autorizado, cantidad comercial y cantidad base, código/nombre/unidad mostrados, precio y totales. Valida producto activo/vendible y unidad compatible. Congela la conversión usada; un cambio posterior del catálogo no debe cambiar la cantidad que entregará B07. No infieras equivalencias por el texto «Caja», «Galón» o por la unidad de compra. No exijas existencia disponible para cotizar/confirmar comercialmente; la disponibilidad se valida al entregar en B07.

Crear/confirmar cotización o venta sin entrega no llama a movimientos ni reduce disponibilidad física. No introducir reservas en esta etapa. Cancelar antes de entrega no genera movimiento. Guardar relaciones de empresa/sucursal y evitar seleccionar clientes o productos de otra empresa.

## Integridad, permisos y contratos para B07

Define permisos explícitos de lectura/gestión de clientes, lectura/gestión/confirmación/conversión de cotizaciones y lectura/gestión/confirmación/cancelación de ventas, reutilizando códigos equivalentes si existen. Documenta la matriz endpoint → permiso → alcance. Actualiza catálogo y asignaciones mediante migración; habilitar un enlace de navegación no concede permisos. El mismo operador puede completar el flujo si su rol lo permite. No reutilices permisos de compras o `inventory:move` como autorización comercial.

Valida alcance en lista, detalle, opciones, edición, confirmación, cancelación, conversión y replay. El cuerpo no elige empresa, actor, estado arbitrario ni progreso de entrega. Las FK/constraints deben proteger relaciones entre cabecera/líneas/cliente/producto y empresa. Sin permiso de costos, el DTO comercial no incluye promedio, costo de lotes, valor global ni márgenes derivados de esos costos.

Crear documentos y convertir debe resistir respuestas inciertas y doble clic. Las transiciones usan versión esperada o un mecanismo equivalente para evitar confirmar o convertir una revisión obsoleta. Serializa conversión y cancelación por documento; la unicidad en base impide dos ventas para una cotización aunque lleguen claves diferentes. Misma clave con cuerpo diferente da conflicto, y el replay vuelve a comprobar permisos/alcance. Conserva la clave en frontend mientras el resultado sea incierto.

Documento, líneas, relación de origen, transición y auditoría de éxito se confirman juntos. Prueba fallo de una segunda línea y fallo tardío de auditoría: ningún documento parcial o estado convertido debe quedar persistido. No cambies globalmente la política de sesión para resolver este caso.

Publica para B07 IDs estables de venta y líneas, empresa/sucursal de cumplimiento, estado comercial, revisión congelada, artículo/variante, unidades/factor y cantidad base por línea. B06 devuelve entregado = 0, pendiente = cantidad base vendida y progreso pendiente como valores de lectura; no acepta esos campos como escritura ni fabrica registros de entrega. B07 sustituirá esa proyección por entregas confirmadas, conservando separado lo devuelto en B08. Deja el contrato y ejemplos en la entrega B06.

## Interfaz y recorrido

Entrega alta/lista/edición básica de cliente y lista/formulario/detalle de cotización y venta. Usa filtros de sucursal, estado, cliente y fecha, con paginación acorde al proyecto. Muestra producto/SKU, unidad comercial, equivalencia base cuando aporte claridad, cantidad, precio y total; los UUID no deben ser el nombre visible.

Distingue acciones **Guardar borrador**, **Confirmar cotización**, **Crear venta**, **Confirmar venta** y **Cancelar con motivo**. La cotización convertida enlaza la venta; la venta enlaza su origen y muestra **Pendiente de entrega**. La acción de entrega no se presenta como disponible hasta B07. Incluye estados carga/vacío/error/sin permiso, recuperación de errores, teclado, etiquetas accesibles y diseño móvil/temas. Cambiar empresa/sucursal invalida formularios y respuestas del contexto anterior. Abrir, cerrar o navegar no crea documentos ni confirma operaciones.

Sustituye únicamente los tres placeholders de B06 al disponer de rutas reales. La aceptación visual autenticada se registra pendiente para B08; realiza ahora pruebas de comportamiento del cliente, tipos, lint y build.

## Aceptación

- B06-A1: crear cliente y cotización, confirmar y convertir produce venta con origen, líneas y totales correctos; doble conversión no duplica.
- B06-A2: cotización/vigencia/cancelación/venta confirmada sin entrega dejan HUs, movimientos, cantidades y valor exactamente iguales.
- B06-A3: cantidades, unidades, conversiones, precios y moneda se validan en servidor; los snapshots sobreviven a cambios posteriores del catálogo.
- B06-A4: confirmada no admite edición silenciosa de líneas; estado de entrega no se modifica desde el formulario comercial.
- B06-A5: aislamiento de empresa/sucursal, permisos de confirmación y lectura, auditoría e idempotencia; no filtrar costo global a usuarios comerciales sin permiso.
- B06-A6: pantallas y cliente implementan cliente → cotización → venta, recarga, cambio de contexto, errores y «pendiente de entrega». Pruebas focalizadas de comportamiento ahora; recorrido autenticado, móvil y temas pendientes de aceptación integrada B08.
- B06-A7: conversión simultánea, confirmación frente a edición/cancelación, replay con permisos revocados y falla tardía no duplican ventas ni dejan documentos, transiciones o auditoría de éxito parciales.
- B06-A8: migración desde cabeza real conserva datos anteriores; se ensaya con registros en base aislada y se documentan actualización de demo, respaldo y recuperación.

## Comprobaciones técnicas de este bloque

Ejecuta pruebas unitarias de reglas; integración PostgreSQL de conversión/atomicidad/concurrencia; API por perfiles de lectura, edición, confirmación, otra sucursal y otra empresa; Vitest del comportamiento afectado, Svelte-check, lint y build. El aplazamiento de la revisión integral no aplaza estas pruebas focalizadas de B06. Las verificaciones API de permisos deben comprobar respuestas reales y persistencia, no limitarse a buscar el texto del permiso en código.

Para A2 registra antes/después una huella de HUs, saldos por estado/ubicación, reservas existentes, movimientos, libro de valoración y promedios de los artículos de prueba; recorre todos los comandos comerciales y verifica igualdad. Incluye casos de cotización vencida/cancelada, cliente desactivado, producto/unidad inválidos, importes manipulados, catálogo modificado después de confirmar y venta cancelada que no permite reconvertir el mismo origen.

Antes de recolectar integración/E2E lee `backend/tests/conftest.py` y verifica ambos DSN de prueba sin imprimir secretos: solo `erp_db_test` para esas suites, ejecutadas en serie. El ensayo de migración/restauración utiliza una copia aislada identificada explícitamente. Respalda la demo antes de migrarla, compara huellas históricas antes/después y no ejecutes semillas destructivas ni reabras saldos iniciales. Usa runtimes y contenedores disponibles. Repite pruebas solo tras cambios, fallos o dudas justificadas; resultados anteriores no cuentan como ejecuciones de B06.

## Documentación y cierre

Crea `docs/ers-v1/entrega-bloque-06.md` con las siete secciones de la guía, `docs/ers-v1/manual-ventas-base.md` y evidencia fechada en `tmp/ers-v1/bloque-06/`. Documenta el contrato consumible por B07, estados, ejemplos, permisos, versiones/idempotencia, precios/unidades/redondeo, migración/recuperación y tabla A1–A8 → prueba → resultado → evidencia. Registra fallos encontrados y su corrección; distingue pruebas con mocks, PostgreSQL/API y aceptación de navegador.

Actualiza E09/E13, guía maestra, decisiones de arquitectura si se precisaron contratos, API, esquema y RBAC. Conserva los pendientes de B05 y los recorridos manuales diferidos a B08 sin darlos por aprobados. Finaliza explicando qué quedó implementado, qué comprobaciones pasaron y qué permanece pendiente. **No inicies B07 ni construyas entregas/devoluciones.**

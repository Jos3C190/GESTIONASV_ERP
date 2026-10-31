# Bloque 2: lotes, viñeteado y ubicación agrupada

Fecha: 14/10/2026.

## Estado

El bloque 2 tiene implementada la integración inicial, con migración `0083` para origen de recepción y confirmación de viñeteado. En la entrega anterior pasaron las regresiones unitarias backend y la suite frontend. **No está aceptado operativamente:** no se aplicó ninguna migración a PostgreSQL y no se ejecutó una prueba transaccional/concurrente real ni una prueba con impresora o escáner físico. La revisión posterior detectó defectos de fraccionamiento, autorización de reintentos y ubicación previa a la etiqueta; consultar la [revisión para el bloque 3](C:/Developer/GESTIONASV_ERP/docs/revision-inventario-bloque-2-y-alcance-bloque-3.md).

La entrega abordó H1, H2, H4 y H5, y unificó el orden de bloqueos de H3. H5 aún requiere cerrar la excepción de fraccionamiento descrita en la revisión posterior. La concurrencia real y los permisos efectivos con usuarios y sucursales siguen necesitando validación de integración sobre PostgreSQL. Consultar también el [informe de integración anterior](C:/Developer/GESTIONASV_ERP/docs/revision-inventario-bloques-1-2-2026-10-14.md).

### Actualización del estado en el código actual

El trabajo del bloque 3 cerró en código los hallazgos R1–R3 de la revisión posterior: fraccionar ya no reutiliza la etiqueta confirmada de la unidad original, los reintentos del grupo autorizan el alcance guardado y se puede ubicar en cuarentena mientras falte una condición de disponibilidad. Se añadieron regresiones unitarias de política, confirmación de etiqueta y flujo agrupado. La última validación disponible pasó 692 pruebas backend y 417 frontend; `svelte-check` reportó cero errores y advertencias, ESLint pasó y el build de producción finalizó. Esto actualiza el estado del código, **pero no convierte en aceptación los escenarios PostgreSQL**: concurrencia, rollback, migración `0083`, permisos efectivos por sucursal y operación física siguen pendientes. El detalle y la evidencia reciente están en el [cierre del bloque 3](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-3-kardex-conciliacion.md).

## Flujo operativo esperado

El recorrido siguiente describe el objetivo actual. La revisión inicial encontró excepciones R1/R3 en el fraccionamiento y la ubicación previa; las correcciones en código se describen en la actualización anterior. Su recorrido transaccional todavía requiere PostgreSQL.

1. **Verificar la recepción.** Las cantidades aceptadas crean un lote de recepción y unidades logísticas en cuarentena. Cada unidad conserva la línea de compra que le dio origen y la cantidad se expresa en unidad base.
2. **Aplicar el retaceo cuando corresponda.** La ubicación no cambia cantidades ni costos. Si está activa la valoración del bloque 1, la unidad no puede liberarse a disponible antes de aplicar el costo del retaceo requerido.
3. **Ubicar en grupo.** En Inventario, filtrar recepciones pendientes por bodega y agrupar por producto/lote. Asignar unidades o cantidades a ubicaciones de almacenamiento de esa misma bodega y confirmar el grupo. La operación valida las ubicaciones, las cantidades y los permisos, y guarda sus movimientos de forma idempotente.
4. **Resolver fracciones y medidas.** Si se asigna parte de una unidad, se crea una unidad logística hija para la cantidad movida; el sobrante conserva su cantidad y origen. La unidad hija necesita su propia etiqueta vigente y confirmación; no hereda la confirmación física de la unidad anterior. Unidades parciales, de medidas incompletas, de fracción estimada o vencidas quedan en cuarentena.
5. **Imprimir y colocar la etiqueta.** La vista previa muestra producto, código interno, lote, cantidad, presentación y equivalencia base (por ejemplo, una caja de 12 equivale a 12 unidades base). Registrar una impresión u abrir el diálogo del navegador no prueba colocación; el operador debe confirmar explícitamente la etiqueta vigente. Las reimpresiones no cambian existencias.
6. **Liberar.** Una recepción nueva solo pasa a disponible cuando cumple el costo/retaceo requerido, la etiqueta fue confirmada para esa unidad y tiene ubicación válida.
7. **Consultar trazabilidad.** El enlace QR abre `/inventory/trace` sin inicio de sesión y muestra datos acotados de la unidad, origen de compra y movimientos. Usuarios autorizados pueden invalidar todos los enlaces de esa unidad.

## Componentes y contratos

- `GET /api/v1/inventory/lots` lista lotes y cantidades pendientes, parciales o ubicadas. Puede filtrarse por compra o bodega; el filtro `pending_placement` incluye también lotes parcialmente ubicados que aún tienen trabajo pendiente.
- `POST /api/v1/inventory/putaway-groups/confirm` confirma asignaciones agrupadas con clave idempotente. Limita cada grupo a una bodega, valida permiso `inventory:move`, y registra movimiento y auditoría en transacción.
- `GET /api/v1/inventory/labels/preview` y `POST /api/v1/inventory/labels/prints` generan la vista previa y guardan un registro idempotente de impresión/reimpresión. El registro no cambia existencias.
- `POST /api/v1/inventory/labels/confirmations` registra de forma explícita, idempotente y auditada la colocación de la etiqueta vigente en una unidad. La confirmación vincula código/revisión, cantidad y registro de impresión actuales.
- `POST /api/v1/inventory/trace-capabilities` emite un enlace QR para una unidad elegible. `POST /api/v1/inventory/trace-capabilities/{handling_unit_id}/revoke` invalida todos sus enlaces activos.
- `POST /api/v1/inventory/public-traces/resolve` resuelve la ficha pública sin credenciales. Solo devuelve campos de producto, unidad, lote, origen comercial limitado, ubicación y movimientos; no incluye usuarios, nombres de operadores, permisos ni solicitudes de sucursal.

Consultar lotes y emitir una ficha QR requiere `inventory:read`; confirmar la ubicación agrupada requiere `inventory:read` y `inventory:move`, además de acceso a la bodega; imprimir, confirmar y registrar etiquetas requiere `inventory:receive`; revocar enlaces requiere `inventory:read` y `inventory:receive`. Las rutas de etiquetas y QR toman la sucursal de la bodega persistida de la unidad o de la compra, no del cuerpo de la solicitud. Resolver el QR es público por diseño y no envía cookies ni requiere sesión.

Los tokens públicos se generan aleatoriamente con 256 bits, se entregan una sola vez y en la base solo se conserva su SHA-256. El token está en el fragmento del enlace QR y el navegador lo envía en el cuerpo de la solicitud pública; la llamada omite cookies y credenciales. El acceso es tipo portador: cualquier persona que tenga una copia de la etiqueta puede abrir esa información limitada hasta que un usuario autorizado revoque el enlace.

## Uso con códigos QR y lectores USB

- **Abrir en una pestaña nueva desde GestionaSV:** usar el botón **Abrir ficha** en el visor del QR.
- **Usar la cámara de un teléfono:** la cámara puede seguir el enlace QR si el servidor tiene una dirección accesible desde ese teléfono.
- **Usar un lector USB 2D configurado como teclado:** el lector escribe los caracteres escaneados en el campo enfocado; no puede abrir por sí solo una pestaña del navegador. Para seguir el enlace hay que enfocar la barra de direcciones y confirmar la navegación, o usar una aplicación de escaneo que abra enlaces.
- **Usar `localhost`:** ese nombre apunta a la computadora que lo abre. Una etiqueta con `localhost` funciona en el navegador de esa computadora, pero no desde un teléfono u otra máquina. Para lectura desde otros dispositivos se debe emitir/imprimir el QR con un dominio o dirección de red accesible y HTTPS.

La configuración de distribución de teclado y sufijo Enter del lector depende del manual del HS-200 y del teclado configurado en Windows; no la puede cambiar el sistema web.

## Migraciones y activación

- `0080`: lotes y detalles de lote asociados a recepciones verificadas.
- `0081`: registro inmutable/idempotente de impresión de etiquetas.
- `0082`: capacidades públicas revocables de consulta de trazabilidad.
- `0083`: origen de compra por unidad, revisión de etiqueta, confirmación auditable y distinción entre lotes históricos y lotes que requieren confirmación.

La secuencia es `0079` → `0080` → `0081` → `0082` → `0083`. `0083` no marca históricos como etiquetados: los lotes existentes quedan sin requisito nuevo y los lotes creados después lo exigen. Alembic reportó `0083` como cabeza. No se pudo leer `current`, generar la secuencia offline ni aplicar migraciones porque WSL dejó de responder (`Wsl/Service/E_UNEXPECTED`) y no hay servidor PostgreSQL local ni daemon Docker disponible. Validar esos pasos cuando vuelva a estar disponible un entorno de base de prueba.

## Verificación de esta entrega

- Backend (Python 3.12.15): **85 pruebas aprobadas** en 11 módulos unitarios relacionados con inventario, lotes, etiquetas/QR, compras y retaceo.
- Frontend: **406 pruebas aprobadas en 94 archivos**, `svelte-check` con 0 errores/advertencias, build de producción, ESLint y Prettier completados.
- Ruff pasó y la sintaxis se validó en 16 archivos Python afectados; `compileall` de Alembic no se pudo completar cuando WSL dejó de responder.
- Alembic reportó `0083` como revisión cabeza. No se completó la generación SQL offline hasta `head`, la lectura de `current` ni la aplicación de migraciones: WSL dejó de responder y no había PostgreSQL local ni servicio Docker disponible. Esto no invalida la generación histórica `0078:0079 --sql` registrada en el bloque 1, pero tampoco la convierte en evidencia de `0083`.
- No se probó con usuarios reales por sucursal, concurrencia/rollback transaccional, impresora, etiqueta física ni escáner HS-200. Estos puntos no se consideran aprobados por tests unitarios ni frontend.

## Pasos pendientes para aceptación operativa

1. Levantar PostgreSQL desechable y confirmar que su único destino sea `erp_db_test`; aplicar migraciones hasta `0083`, comprobar `alembic current`, y ejecutar integración de concurrencia, rollback, idempotencia, dos bodegas/empresas y permisos por sucursal.
2. Recibir una compra ficticia de prueba, verificar cantidad aceptada, consultar su lote y asignar varias unidades a distintas ubicaciones del mismo almacén.
3. Repetir la confirmación con la misma clave para comprobar que no duplica movimientos; intentar exceder la cantidad o usar otra bodega y confirmar que el servidor lo rechaza.
4. Imprimir una etiqueta, comprobar en el papel que se leen el código 1D y el QR, abrir la ficha sin sesión y revocar el enlace.
5. Probar el HS-200 con un campo de texto y con la barra de direcciones enfocada. Confirmar distribución de teclado, puntuación de URL y sufijo Enter según la configuración del lector.
6. Para abrir desde teléfonos, configurar la URL pública o de red de la aplicación antes de imprimir etiquetas destinadas a ese uso.

### Estado posterior al bloque 4 — 14/10/2026

La continuación de fracciones con medidas estimadas ya ofrece verificación y exige una etiqueta vigente por fracción. Se agregó preparación transaccional para dividir una HU disponible y la excepción explícita de recepción parcial de traslado que mantiene la parte recibida en cuarentena. Las pruebas de interfaz pasan; el rollback, replay y aislamiento necesitan su ejecución PostgreSQL dedicada. No se verificó físicamente lector, impresora ni etiqueta. Véase el [cierre operativo del bloque 4](C:/Developer/GESTIONASV_ERP/docs/inventario-bloque-4-cierre-operativo.md).

# Encargo Luna — ERS-B07: entrega de ventas y salida de inventario

Implementa la entrega física de las ventas de B06 usando el inventario y la valoración existentes. Lee la [guía](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-04/06/07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md) y las entregas B02/B05/B06. No estás solo en el repositorio; conserva otros cambios y resuelve las dependencias necesarias sin ampliar el alcance comercial.

**Encargo preparado el 19/10/2026.** Este es el penúltimo bloque. Implementa B07, ejecuta sus comprobaciones técnicas y documenta resultados reales. La revisión completa y los recorridos autenticados de navegador acumulados se harán al terminar B08. No implementes devoluciones ni inicies B08 ahora. El archivo de aceptación denominado B09 es un checklist incorporado a B08, no un noveno bloque.

## Punto de partida y preparación

- Lee `.agents/AGENTS.md`, las instrucciones aplicables a los archivos que edites y los skills pertinentes. Revisa el estado del repositorio y formula un plan corto antes de modificarlo; no reviertas cambios ajenos.
- Usa `entrega-bloque-06.md`, `manual-ventas-base.md` y `tmp/ers-v1/bloque-06/evidencia-2026-10-19.md` como entrega previa, no como sustituto de las pruebas nuevas. No repitas la auditoría completa de B01–B06.
- B06 dejó clientes, cotizaciones y ventas, con líneas y conversiones a unidad base congeladas. La venta comercial confirmada todavía no mueve inventario. Sustituye las proyecciones actuales `quantity_delivered_base = 0`, `quantity_pending_base = quantity_base` y `delivery_progress = pending` por agregados de entregas confirmadas, también en listas y detalles.
- Localiza primero `backend/app/application/sales/service.py`, modelos y DTOs de ventas, el motor de salidas/valoración y `frontend/src/lib/features/sales/components/`. Reutiliza sus contratos y enlaces; no construyas una venta paralela.
- La última revisión documentada de demo es `0088`. Comprueba la cabeza real y el destino de la API antes de crear una migración; no supongas que la base de pruebas y la demo están sincronizadas. No publiques secretos al inspeccionar configuración.

## Responsabilidad

Responsable del documento de entrega, asignaciones físicas, aplicación transaccional, API, permisos y pantallas desde el detalle de venta. Reutiliza los casos de uso de salida, valoración, disponibilidad y trazabilidad. No crear un segundo libro de existencias ni descontar desde el frontend.

## Contrato funcional

1. Crear entrega vinculada a una venta CONFIRMADA, con líneas enlazadas a sus detalles. Registrar empresa, sucursal que entrega, ubicación, lote canónico, HU/asignaciones, cantidad y conversión a unidad base congelada, actor y fechas. Conservar los identificadores de movimiento físico y salida valorada: B08 los necesita para devolver al costo de origen.
2. Permitir entregas parciales o completas. Calcular el pendiente por línea como cantidad vendida menos cantidad ya entregada, bajo bloqueo dentro de la transacción. La cantidad devuelta posteriormente se mostrará por separado; no reabrirá automáticamente ese pendiente.
3. Consumir solo stock DISPONIBLE de ubicaciones de la sucursal autorizada para la venta. Existencias en otra sucursal, tránsito, cuarentena o HU cerrada no satisfacen la entrega. Validar empresa, producto/variante, unidad, lote, ubicación y relación con la línea comercial en servidor.
4. La salida usa el promedio vigente de empresa/artículo, independiente del precio de venta y del costo histórico del lote. El usuario que entrega no necesita leer el costo global; el servidor aplica la valoración y respeta los permisos al devolver información.
5. Guardar documento, asignaciones, salida física, HUs, saldo, costo y auditoría de éxito de forma atómica. Proteger errores de negocio tardíos con la unidad de trabajo descrita en ADR-07: la sesión actual hace commit ante AppError. Bloquear recursos en orden determinista y revalidar disponibilidad y pendiente después de adquirir los bloqueos.
6. Hacer idempotente la confirmación: reintento con el mismo cuerpo devuelve la entrega registrada; misma clave con otro cuerpo produce conflicto. Dos claves diferentes tampoco pueden consumir el mismo último stock ni exceder el pendiente de venta.
7. Una entrega confirmada es inmutable. Cancelar un borrador de entrega no mueve stock. Conforme al contrato B06, bloquear la cancelación comercial de una venta si ya tiene alguna entrega confirmada; explicar que la devolución seguirá B08. Nunca borrar la entrega original ni permitir despachos de una venta cancelada. Cancelación de venta y confirmación de entrega deben bloquear la misma venta y revalidar su estado para resolver la carrera entre ambas.

## Contrato técnico y preparación de devoluciones

- Define cabecera/líneas de entrega y asignaciones con estados explícitos de borrador, confirmada y cancelada, o sus equivalentes existentes. Protege ediciones con versión esperada. Antes de confirmar no descontar ni crear movimientos; una consulta o previsualización nunca confirma el documento.
- Cada asignación debe permitir recuperar la línea de venta, artículo/variante, lote canónico por producto de B02, bodega/ubicación, HU, cantidad base efectivamente consumida, movimiento físico y entrada de valoración de salida. Admite varias asignaciones para una línea. Conserva snapshots de unidades/factores; un cambio posterior de empaque no recalcula ventas confirmadas.
- Persiste el costo efectivo aplicado y su referencia de valoración con la precisión del motor, incluidos residuos de redondeo. Documenta cómo B08 recuperará el costo original y los ajustes de costo posteriores relacionados. El costo es global por empresa/artículo, compartido entre almacenes; la sucursal determina de dónde sale la mercancía, no otro promedio. No implementar devoluciones todavía.
- Si la valoración requerida no está activa o no existe el costo necesario, devuelve un error accionable sin salida parcial; no inventes costo cero ni uses el precio comercial. Reutiliza la política del motor para saldos valorados válidos en cero.
- Usa Decimal, límites y granularidad de las unidades existentes. Aplica restricciones de base de datos y validación de pertenencia: una línea de otra venta, empresa, artículo o variante no es asignable aunque llegue un ID válido.
- Serializa confirmaciones contra el pendiente de la venta y contra el stock/valoración compartidos. Contempla dos ventas diferentes compitiendo por el mismo inventario y varias líneas del mismo artículo. Revalida después de adquirir bloqueos y evita bloqueos en orden inverso.
- Confirma documento, movimientos, cantidades físicas, valoración, idempotencia y auditoría en una sola unidad atómica protegida ante AppError. Un comando fallido debe poder reintentarse sin residuos. No cambies globalmente el comportamiento de SessionDep para resolver este bloque.
- Define permisos explícitos de entrega (lectura, preparación, confirmación y cancelación según acciones existentes) y documéntalos. Valida empresa/sucursal también en opciones, detalles, movimientos enlazados y replays. Entregar no exige permiso de lectura de costos; no exponerlos en DTOs comerciales, errores ni respuestas idempotentes de operadores sin permiso.
- El pendiente comercial se deriva de entregas confirmadas; no aceptar del cliente cantidades entregadas, costos ni estados calculados. B08 conservará cantidad devuelta separada y no reabrirá el pendiente automáticamente.

La selección de cantidades no debe crear fracciones al abrir/cerrar el formulario. Aprovecha asignaciones y consumo parcial seguros del motor; si una operación requiere separación física y nueva validación de etiqueta/medidas, hazla explícita con el flujo existente. Entregar parcialmente una venta también puede hacerse seleccionando HUs completas. No crear un ciclo obligatorio de división.

## Pantallas

Desde la venta mostrar cantidades vendidas, entregadas y pendientes, y acción «Preparar entrega». Identificar producto, unidad/presentación, ubicación, lote y cantidad disponible. Permitir revisar el documento antes de confirmar y consultar el resultado y sus movimientos después. Distinguir pendiente comercial, falta de stock y error de consulta. Mantener estado correcto al recargar.

Reemplaza mensajes internos como «B07 incorpora…» por instrucciones para el usuario. Muestra «Pendiente», «Parcialmente entregada» o «Entregada» según cantidades reales. Abrir, cerrar, cancelar o reintentar una consulta no crea HUs ni divisiones. Ante respuesta de confirmación perdida, conserva la identidad del comando y recupera el resultado; no generes otra entrega por un reintento. Al cambiar empresa/sucursal limpia las selecciones anteriores y descarta respuestas tardías del contexto previo. Reutiliza componentes, estados de carga/vacío/error y temas del proyecto.

No ampliar este bloque a facturación electrónica, cobros, rutas de reparto a clientes o fijación automática de precios. Actualiza navegación solo para rutas reales.

## Aceptación

- B07-A1: una venta de 5 permite entregar 3 y luego 2; antes de confirmar cada entrega no cambia el inventario. La suma entregada nunca supera 5.
- B07-A2: stock de otra sucursal, cuarentena, tránsito, ubicación incompatible o saldo insuficiente se rechaza sin efectos parciales. Los artículos disponibles se descuentan de sus asignaciones correctas.
- B07-A3: con precio comercial distinto del costo promedio, la salida reduce cantidad y valor usando el promedio vigente. Cotización y confirmación comercial continúan sin efecto físico.
- B07-A4: doble clic, reintento, cuerpo conflictivo y dos entregas concurrentes contra el mismo pendiente/stock no duplican ni sobreconsumen. Una falla de segunda línea, tanto AppError como inesperada, revierte documento, stock, valoración y auditoría de éxito.
- B07-A5: conservar los vínculos venta → entrega → movimiento → valoración → lote/HU. Permisos de empresa/sucursal y consulta de costo se comprueban también al reintentar.
- B07-A6: probar técnicamente estados de preparación, confirmación, error/reintento y cambio de contexto en frontend. Cancelar preparación no altera datos físicos ni genera HUs. Dejar el recorrido autenticado parcial/total, recarga y consulta de Kardex/conciliación preparado y expresamente pendiente para B08.
- B07-A7: cancelar venta y confirmar entrega concurrentemente solo permite un resultado compatible; después de una entrega no se cancela la venta. Rechazar nuevas entregas de ventas canceladas y mutaciones de entregas confirmadas.
- B07-A8: probar conversión de empaque congelada, varias asignaciones y líneas del mismo artículo, dos ventas contra el último stock, y costo de salida recuperable desde cada asignación. Comprobar saldos físicos y valorados con Decimal, no solo códigos HTTP.
- B07-A9: migración ensayada sobre copia con datos anteriores, aplicada con respaldo y evidencias de conservación de IDs, documentos e inventario. La migración no genera entregas históricas ficticias.

## Comprobaciones técnicas y entorno

Ejecuta pruebas focalizadas de dominio, integración/API real PostgreSQL, permisos, concurrencia y rollback para B07-A1–A5/A7/A8. Incluye falla de segunda línea tanto AppError como inesperada y fallo tardío de auditoría. Agrega pruebas frontend de los comportamientos nuevos, tipos/Svelte-check, lint focalizado y build. Revisa regresiones focalizadas de B06 y de las salidas/valoración utilizadas. No presentes compilación como aceptación operativa completa.

Antes de ejecutar integración/E2E inspecciona fixtures y confirma que ambos DSN de prueba apuntan solo a `erp_db_test`: las fixtures reconstruyen el esquema. Ejecuta las suites en serie, sin afectar la demo ni otro proceso que utilice esa base. Para migraciones conserva un respaldo verificado, ensaya sobre una copia restaurada y compara datos antes/después antes de actualizar la base habitual. No uses reset, semillas destructivas ni un downgrade que borre documentos como recuperación ordinaria. Registra el procedimiento real de restauración y lo que no se ensayó.

La entrega B06 reportó 8 avisos CSS existentes y 3 imports sin uso en compras que hacen fallar el lint global. Comprueba su estado si ejecutas esos comandos y distingue resultados focalizados/globales; no ocultes fallos ni amplíes el bloque para una limpieza general. El recorrido visual autenticado integrado queda para B08 por decisión del usuario.

## Documentación obligatoria y traspaso a B08

1. Crea `docs/ers-v1/entrega-bloque-07.md`: alcance, decisiones, archivos/contratos, migración/respaldo, tabla B07-A1–A9 con prueba/resultado/evidencia, pasos de uso y pendientes. Distingue implementado, comprobado técnicamente y pendiente de aceptación integrada.
2. Crea `docs/ers-v1/manual-entregas.md` con acciones reales desde la venta confirmada, cantidades de ejemplo, entrega parcial/final, consulta de movimientos y errores habituales. Marca los recorridos no ejecutados como instrucciones por validar en B08.
3. Guarda comandos/resultados y evidencia fechada en `tmp/ers-v1/bloque-07/`, sin credenciales. Documenta las tablas/campos y un ejemplo verificable de venta → línea → entrega → asignación → salida física/valorada → lote/HU. Incluye el contrato de costo original que usará B08.
4. Actualiza `docs/api.md`, `docs/database-schema.md`, `docs/rbac-model.md`, guía y E10/E12/E13 de la matriz. Registra decisiones nuevas indispensables en `decisiones-arquitectura.md`. No marques devoluciones ni revisión integral como terminadas.
5. Completa [preparacion-revision-bloque-08.md](C:/Developer/GESTIONASV_ERP/docs/ers-v1/preparacion-revision-bloque-08.md) con enlaces exactos a evidencia, rutas, roles y casos de B07. Preserva los pendientes de B01–B06 y enlaza esta preparación desde tu entrega. El checklist integrado existente sigue siendo la referencia final; no crees un nuevo bloque.

**Cierre:** informa qué funciona, qué pruebas se ejecutaron realmente, qué falló o quedó impedido, estado de migración/demo y documentación. Detente al terminar B07. No inicies B08 ni declares aceptado todo el ERP.

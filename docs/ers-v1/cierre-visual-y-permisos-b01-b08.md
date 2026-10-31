# Cierre visual y permisos B01–B08

**Fecha de corte:** 21/10/2026, America/El_Salvador  
**Estado de aceptación integrada:** **PARCIAL**.  
**Alcance:** continuación del cierre B08 y del checklist histórico B09; no inicia un bloque funcional nuevo.

## Compra en moneda extranjera del recorrido — 21/10/2026

COM-00022 está intencionalmente en CRC frente a valoración USD. Se añadió una conversión documentada por recepción, persistida con la verificación y reutilizada en el retaceo. La migración 0091 está aplicada localmente; 62 pruebas de servidor y 17 de interfaz aprobaron. El ensayo SQL completo con tasa ficticia 500 pasó y se revirtió, conservando los saldos protegidos y la compra pendiente. Ver [alcance y evidencia](conversion-monedas-compras-2026-10-21.md). La validación visual y los criterios globales pendientes conservan su estado.

## Presentaciones de las harinas del recorrido — 21/10/2026

Se guardaron KG-HAR-003 y KG-HAR-001 con equivalencias de demostración por kilogramo, conservando las unidades base e historial. Las dos creaciones tienen auditoría persistida. La verificación completa de COM-00021 pasó en una transacción de simulación, revertida y comprobada mediante las huellas de 13 tablas de inventario/compras. La recepción definitiva sigue pendiente del usuario. Se mejoraron los avisos y el reintento del formulario; 7 pruebas de frontera y 7 de componentes aprobaron. Ver [supuestos, configuración y evidencia](presentaciones-harinas-demostracion-2026-10-21.md). No cierra los criterios visuales, permisos y recuperación todavía abiertos de la aceptación integrada.

## Hallazgo del recorrido manual del usuario — 21/10/2026

**Recepción y cierre del pendiente:** la consulta de OC-00019 encontró una recepción COM-00021 en borrador, sin movimiento de inventario. Se corrigió la navegación al guardar, se permite continuar el borrador existente y se anuncia la recepción completada sin ofrecer nuevas recepciones para órdenes totalmente recibidas. Pasaron 23 pruebas frontend, 14 backend, ESLint y Svelte-check (0 errores/8 advertencias). La confirmación del documento real queda en manos del usuario; ver [diagnóstico y evidencia](diagnostico-oc-00019-recepciones-y-cierre-2026-10-21.md). El cierre integrado continúa **PARCIAL**.

La orden desde adjudicaciones COT-00048 mostraba el destino central vacío: `PurchaseOrderEditor` aún exigía una bodega sin sucursal, contradiciendo la asociación a matriz de B01. Se corrigió el filtro conservando los controles de central activa, aptitud de almacenamiento y exclusión de tránsito. La regresión se reprodujo antes del parche; después aprobaron 10 pruebas focalizadas y ESLint. No se modificaron datos ni se creó una orden real. Falta confirmar desde la pantalla del usuario tras recargar; la aceptación integrada permanece **PARCIAL**. Ver [diagnóstico, cambio y evidencia](diagnostico-orden-consolidada-bodega-matriz-2026-10-21.md).

## Actualización de continuación — 21/10/2026

Se ejecutaron dos conciliaciones `READ ONLY` (antes/después), sin modificar datos ni código de producto. Los cuatro SKU protegidos y V04-01/02/03 siguen coherentes. La búsqueda SQL corregida de V03 localizó tres pares de alias de recepción y 24 HUs sin lote enlazado; no encontró movimientos que coincidieran con el predicado de literal divergente/FK nula. Esto no equivale a consultar etiquetas o Kardex desde UI. La herramienta rechazó adquirir `localhost:5174/inventory/trace` por su política de seguridad de URL; se detuvo el acceso y no se intentó un canal alterno. El crítico estático de UI no alcanzó el umbral 8.5/10 y no se cuenta como aceptación visual. Evidencia: [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md), [comandos y resultados](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/comandos-y-resultados.md), [alias](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/v03-alias-discovery.log) y [scorecard UI](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/critico-ui-estatico.md).

La aceptación permanece **PARCIAL**. V01 permisos/documentos, V02 PNG, V03-02/03/05 y V04-04 siguen abiertos; no se reprodujo un nuevo defecto funcional ni se cambiaron las pruebas aprobadas. La conciliación posterior está en [reconciliation-after.log](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/reconciliation-after.log).

En V01, el adaptador real de RustFS completó un round-trip ficticio con hash coincidente y borrado del objeto. El flujo de documentos por API no empezó porque el login de prueba devolvió 401; no se probaron más credenciales. V01 permanece abierto hasta completar descarga/vínculo y matriz de autorizaciones; evidencia en [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md).

## Actualización final de cuatro verificaciones — 21/10/2026

Se ejecutaron operaciones nuevas solo en la clon `erp_db_ers_final4p_20261020`. V04-01, V04-02 y V04-03 aprobaron con persistencia: corrección compensatoria de ajuste, traslado 8+2 y devolución mixta de una de dos entregas. V03 confirmó identidad de HU/lote, QR público sin costos y apertura/cancelación de división sin crear otra unidad. V01 sigue sin inventario de permisos exhaustivo; V02 sigue sin capturas PNG archivadas; V03 no cubre recepción repetida visual ni todos los alias/privacidad; V04-04 no pudo simular la pérdida postcommit desde el navegador. El dictamen global se mantiene **PARCIAL**.

El detalle de IDs, resultados y bloqueos está en [informe final V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md), [registro de casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md), [V03 UI](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/v03-ui-trace-qr-division-cancel-2026-10-21.md), [V04 UI](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/v04-ui-operations-2026-10-21.md), [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y [salida de conciliación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log). Los cuatro SKU protegidos concilian sin cambios en `erp_db` ni en la clon. Se restauró el CORS temporal del clon y se comprobó que admite solo `localhost:5173` y `127.0.0.1:5173`.

### E01–E15: estado vigente al 21/10/2026

| Criterio | Resultado vigente | Pendiente que impide aceptación completa |
| --- | --- | --- |
| E01 Matriz y bodega | Evidencia anterior conservada; las nuevas operaciones se ejecutaron en bodegas identificadas. | Matriz/bodega con perfiles, temas y PNG actuales. |
| E02 Recepción y lotes | HU y detalle/cabecera de `COM-00017` visibles por UI. | Recepción visual con mismo SKU repetido o equivalente parcial tras revisar contrato. |
| E03 Cantidad por ubicación/estado | Traslado persistido 8+2; HUs destino y valoración global conciliadas. | Recorrer y conciliar todos los estados y ubicaciones. |
| E04 Etiquetas/medidas | QR de HU, producto, unidad, revisión y estado visible. Cancelar división conserva cantidad. | Alias y PNG de etiqueta en móvil/temas; no se requiere impresora física. |
| E05 Código, QR y Kardex | QR público resolvió 9 movimientos sin mostrar costos/valoración. | Consulta de todos los alias aplicables y denegación privada ajena en UI. |
| E06 Traslados/incidencias | Traslado `TR-20261021-60344005` despachado 10 y recibido 8+2 desde UI. | Matriz de perfiles, incidencias y estados restantes. |
| E07 Parcialidad/neutralidad | Traslado 8+2 y retorno 2 de 3 mixto conciliados; costo de origen conservado. | Recuperación de respuesta perdida tras commit desde UI. |
| E08 Ajustes/documentos | Corrección `AJ-000005`→`AJ-000006` aplicada desde UI con soporte; original conservado. | Permisos/descarga real de bytes y cobertura documental de otros módulos (E13). |
| E09 Clientes/cotizaciones/ventas | Venta de prueba con 2 entregas distintas se usó para devolución; IDs y estados persistidos. | Variantes de permiso/perfil y evidencia visual exportada. |
| E10 Entregas | Dos entregas de 4 unidades/HU, recargadas y conservadas en el historial. | Permisos completos y pérdida de respuesta UI. |
| E11 Devoluciones | Devolución de 3: aceptadas 2 a cuarentena y rechazada 1 dañada; estado `mixed`, pendiente 0. | Perfiles/documentos y artefacto visual exportable. |
| E12 Promedio ponderado | Traslado no cambia promedio global; devolución aceptada usa valoración original. | Cobertura visual y de permisos en todos los contextos. |
| E13 Permisos/atomicidad | Casos seleccionados anteriores y ajuste documental se conservan; todas las operaciones nuevas de V04 persistieron. | Matriz por acción/ruta/empresa/sucursal y documentos sigue incompleta. |
| E14 Cuarentena/disponibilidad | Devolución aceptada quedó en cuarentena; división cancelada no mutó stock. | Estados visuales completos por perfil y tema. |
| E15 Migración/conciliación | No hubo migración; 4 SKU protegidos con físico=valorado en ambas bases. | Ninguno por migración en esta pasada; ver snapshot final. |

## Resumen

### Evidencia de interfaz y suite del corte anterior — 20/10/2026

Esta actualización reemplaza cualquier resultado anterior de la misma fecha que figure más abajo. La devolución se comprobó también en móvil: `/sales/returns` a 390×844, oscuro y claro, sin desbordamiento exterior; el filtro se abrió por teclado, Escape lo cerró y el foco permaneció en el control. La aceptación visual de esta pantalla es válida solo para el alcance ejercitado, no para todas sus acciones/perfiles.

Se corrigió además la presentación móvil de Traslados tras el rechazo del crítico: las pestañas se mantienen en una sola fila desplazable, acciones primarias con alto mínimo de 44 px, y despacho/tránsito/recepción se plegaron como detalle secundario. A 390×844 se confirmó el ancho exterior de 390 px y que sucursal solicitante/código SCR siguen visibles. La regresión de componente, el lint y el build pasan. El frontend se reinició para invalidar una transformación Vite obsoleta; solo se reinició ese servicio.

La suite backend completa **sí pasó** al ejecutarse con extras de prueba `dev+ocr`: 753 aprobadas. El problema previo de `pikepdf` era el entorno de la ejecución anterior, no un defecto del módulo; ya no es pendiente de aceptación. Se repitieron dos E2E de regresión en `erp_db_test` (una migración y una de ventas); no se cuentan como casos nuevos. El número anterior de 33 E2E únicas permanece igual.

### Continuación final P01–P04 — 20/10/2026

P01 prueba documentos de ajustes con roles y ámbitos distintos, redacción de costos, retiro del vínculo y revocación; se corrigió API/RBAC. P03 corrigió la ficha de una HU real para mostrar producto, lote de fabricante, detalle canónico y cabecera de recepción por separado. P04 probó corrección de ajuste, traslado parcial/final e idempotencia/rollback de devoluciones en API/PostgreSQL. Los casos y límites están en [evidencia P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

La aceptación sigue **PARCIAL**: falta una matriz E13 finita para todas las acciones aplicables; los PNG requeridos para P02 no se pudieron exportar desde la capacidad CUA disponible; P03 aún requiere recepción visual de líneas repetidas y consultas UI de los códigos con registro aplicable; P04 aún requiere devolución mixta/selección desde formularios y una respuesta perdida de navegador seguida de consulta/reintento. Ninguna evidencia API o de componente sustituye esos casos. La lista de códigos soportados y la evidencia disponible están en [alias-trazabilidad](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/alias-trazabilidad.md). El detalle está en [cierre de pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md) y [recorrido visual móvil](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/mobile-ui-run.md).

Se corrigieron dos defectos en Devoluciones:

1. **Unidad repetida:** se normaliza el símbolo tanto al crear nuevas etiquetas como al presentar snapshots comerciales antiguos. La corrección es de presentación y no reescribe movimientos ni documentos históricos.
2. **Estados y filtros sin señal:** Aceptada y Rechazada ahora usan colores semánticos distintos; el conteo del filtro es una región accesible con role=status y aria-live.

La bandeja se revisó autenticada con la API real, en escritorio 1280×720 y en móvil 390×844. La segunda revisión independiente de escritorio obtuvo **8.56/10 y aprobó**. La pasada adicional también comprobó móvil en claro/oscuro, sin desbordamiento, y apertura/cierre de filtro con teclado; no certifica los demás módulos, todos los estados ni todos los perfiles. La unidad aparece como «Unidad (u)» una sola vez.

En la pasada inicial pasaron 116 archivos / 513 pruebas frontend, 25 pruebas backend focalizadas y 10 E2E adicionales de permisos; se conservan además 23 E2E seleccionadas anteriores. En esta continuación pasaron 753 pruebas unitarias backend con extras `dev+ocr`, una regresión Vitest focalizada (2 pruebas), ESLint focalizado y el build de producción. svelte-check reportó cero errores y ocho avisos CSS conocidos. Dos E2E anteriores se repitieron con éxito y no se suman al total único. La causa de recolección por `pikepdf` quedó resuelta al usar el entorno de pruebas correcto.

La API usa erp_db con Alembic 0090 (head). Una consulta de solo lectura confirmó los cuatro saldos de demo. No se ejecutaron escrituras ni migraciones sobre erp_db. El árbol compartido ya estaba modificado; no se hizo reset, limpieza ni resembrado. Las E2E usan el guard de backend/tests/conftest.py: solo erp_db_test, esquema desechable por prueba y ejecución serial.

## Defectos corregidos

### Símbolo de unidad repetido

La causa era añadir el símbolo de unidad a un nombre de etiqueta que ya lo incluía. Se añadió normalización idempotente en el formateador backend y frontend. Para snapshots antiguos solo cambia el texto presentado; no se alteran datos de negocio. Archivos principales: backend/app/application/sales/service.py, frontend/src/lib/features/sales/unit-label.ts, sus componentes y src/routes/(app)/sales/returns. Las pruebas de dominio, formato, bandeja, panel, detalle de venta, entregas y cotizaciones pasan en la suite frontend/backend indicada.

### Estados y filtros de devoluciones

La revisión anterior identificó píldoras indistinguibles y falta de feedback inmediato al filtrar. Se diferenciaron los estados y se añadió un anuncio accesible del número de resultados. En navegador se verificaron los tres documentos ficticios, Aceptada verde, Rechazada roja, filtro sin coincidencias, foco visible y ambos temas. No se guardó una captura nueva en el directorio de evidencia; las capturas históricas de otros recorridos están en tmp/ers-v1/revision-2026-10-19/.

La primera evaluación rechazó la versión previa (8.25/10); después de corregir los dos puntos, una segunda evaluación fresca aprobó la pantalla actual con 8.56/10. Esa evaluación fue de escritorio y no comprobó móvil ni tema claro en vivo; el tema claro se comprobó por separado en esta pasada.

## E01–E15

| Criterio | Estado y evidencia actual | Pendiente exacto |
| --- | --- | --- |
| E01 Matriz y bodega | Catálogo por sucursal permite incluir Casa matriz explícitamente; se conserva evidencia previa de identidad. | Recorrido visual con perfiles y tamaños adicionales. |
| E02 Recepción y lotes | E2E de recepciones parciales con códigos distintos y migración que conserva movimientos/detalle legado. | Mostrar desde navegador una recepción con varias líneas del mismo producto. |
| E03 Cantidad por ubicación/estado | Flujos persistidos de recepción, ubicación, traslado y conciliación; almacén y Kardex sin desbordamiento exterior a 390×844. | Recorrer visualmente todos los estados y conciliarlos por ubicación. |
| E04 Etiquetas/medidas | HU de devolución revisada y liberada; unidad actual visible. Impresión digital simulada. | Alias históricos y presentación móvil/teclado de las pantallas de etiqueta. |
| E05 Código, QR y Kardex | Casos previos de consulta por etiqueta; E2E niega costos de empresa al perfil de sucursal. Kardex no desborda exteriormente a 390×844. | Verificar cada alias histórico y el alcance QR con datos de pantalla. |
| E06 Traslados/incidencias | E2E de recepción por sucursal y aislamiento de empresa; incidencia operada previamente. Pestañas, demanda por sucursal y acciones principales comprobadas a 390×844. | Perfiles, errores y todos los estados/acciones de traslado e incidencia. |
| E07 Parcialidad/neutralidad | Casos anteriores más una integración de traslado parcial/final y un E2E comercial focalizado de entrega/devolución con rollback e idempotencia; logs en [comandos y resultados](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/comandos-y-resultados.md). | Completar devolución mixta y recuperación de respuesta desde formularios; la evidencia API no sustituye UI. |
| E08 Ajustes/documentos | E2E nuevo de ajuste: detalle sin valoración redacta costos; descarga/carga/retirada denegadas según permiso; vínculo, empresa/sucursal, retiro y revocación comprobados. Se corrigió API/RBAC. | Matriz de acciones/archivos para los otros módulos; descarga de bytes y almacenamiento no cubiertos por el stub. |
| E09 Clientes/cotizaciones/ventas | Recorrido de pantalla y neutralidad de inventario; E2E de alcance/idempotencia. | Variantes restantes de permisos, recuperación y presentación. |
| E10 Entregas | E2E de parcialidad, costo, concurrencia y rollback; pantalla 2+2 documentada. | Permisos completos y recuperación desde interfaz para cada perfil. |
| E11 Devoluciones | E2E de parcialidad, límite, permiso ausente, sucursal ajena y replay; pantalla revisada en escritorio y móvil 390×844, temas claro/oscuro, filtro por teclado, Escape y foco visible. | Matriz completa de acciones/archivos, estados y perfiles; no generalizar esta revisión de bandeja a sus diálogos de operación. |
| E12 Promedio ponderado | Casos de retaceo tardío y devolución, más conciliación final de los SKU guardados. | No hay diferencia numérica en esos ejemplos; falta cobertura de presentación/alcance. |
| E13 Permisos/atomicidad | Se conservan las 33 E2E seleccionadas anteriores y se agregó un caso específico P01 para documentos de ajustes con permiso/alcance y redacción. | No existe aún matriz exhaustiva por acción, perfil, empresa/sucursal y documentos directos de los demás módulos. |
| E14 Cuarentena/disponibilidad | HU devuelta alcanzó «Revisión terminada · disponible para uso» sin doble contabilización. | Casos visuales restantes por perfil, tema y tamaño. No hace falta dividir/reimprimir otra vez. |
| E15 Migración/conciliación | 0090 head; los cuatro SKU conservan físico=valorado. El respaldo/ensayo previo está en evidencia histórica. | Esta pasada fue solo lectura; no se repitió migración/restauración. No reabrir el corte aprobado. |

## E13: permisos efectivamente comprobados

| Caso | Resultado observado | Evidencia |
| --- | --- | --- |
| Usuario restringido cruza sucursal o solicita alcance global | Denegado por servidor (403). | test_branch_isolation.py::test_restricted_user_cannot_cross_branch_boundary |
| Receptor autorizado recibe sin alcance global | Permitido dentro de su sucursal. | test_inventory_transfers.py::test_destination_branch_receiver_can_receive_without_global_access |
| Otra empresa consulta traslado por ID | No visible. | test_inventory_transfers.py::test_transfer_from_another_company_is_not_visible |
| Perfil Kardex de sucursal consulta valoración global | Denegado; JSON no contiene inventory_value ni average_unit_cost. | test_inventory_block4_closure.py::test_branch_kardex_profile_cannot_fetch_company_valuation_json |
| Permiso ausente o revocado intenta replay | Denegado; replay autorizado no expone costos. | test_inventory_block4_closure.py::test_concurrent_group_retry_applies_once_and_replays |
| Usuario sin permiso inicia carga documental | HTTP 403. | test_documents.py::test_document_upload_requires_explicit_permission |
| Lector sin permiso de valoración consulta ajuste | Detalle permitido en su sucursal; costos documentados `null`; descarga 403. | `test_inventory_adjustment_permissions.py::test_adjustment_evidence_download_requires_valuation_permission`; [comando/log](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log) |
| Responsable con valoración pero sin vínculo/alcance | ID no vinculado y otra empresa: 404; sucursal distinta: 403; vínculo retirado: nueva descarga 404; acceso revocado: nueva descarga 403. | Mismo E2E P01 y [comando/log](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log) |
| Usuario sin permiso accede a orden, recepción, retaceo o documentos de gasto | Casos seleccionados denegados. | Cinco pruebas de test_purchase_orders.py |
| Usuario sin permiso accede a cotización/solicitud de compra | Denegado. | test_purchase_quotations.py y test_purchase_requests.py |
| Asignación/listado de categoría de bodega de empresa ajena | Denegado por empresa. | Dos pruebas de test_warehouse_category_isolation.py |
| Ventas, entregas y devoluciones con sucursal/empresa ajena o replay sin alcance | Denegados en los casos directos probados. | test_sales_base.py y test_sales_deliveries.py |
| Sede con asignación explícita a Casa matriz lee recepción central | Permitido dentro de esa sede; sin alcance global. | test_purchase_orders.py::test_headquarters_user_can_read_new_central_receipt_without_global_scope |

Estos son casos concretos, no el producto cartesiano completo recursos × acciones × perfiles. P01 ahora incluye autorización documental de ajustes; quedan sin evidencia individual combinaciones de lectura, detalle, borrador, confirmación, aprobación/aplicación, cancelación/corrección y acceso a archivos en los demás perfiles/contextos, especialmente incidencias, etiquetas, ventas/entregas/devoluciones y Kardex. Superadmin no cuenta como evidencia de autorización.

## Pruebas y servicios

- Frontend Vitest inicial: 116 archivos, 513 pruebas aprobadas; regresión focalizada de Traslados: 2 aprobadas.
- svelte-check: 0 errores, 8 avisos CSS por @apply en TransferOperationsPage.svelte.
- ESLint focalizado de los componentes y prueba de Traslados: aprobado.
- Build de producción de continuación: aprobado en 1m 16s. Avisos no bloqueantes: importación jsbarcode sin uso en HandlingUnitLabelDialog.svelte y adapter-auto sin destino de despliegue configurado.
- Backend `tests/unit` con extras `dev+ocr`: 753 aprobadas en 35.18s. La ejecución no se omite ni requiere agregar OCR a dependencias globales.
- Regresiones E2E repetidas: migración, 1 aprobada en 26.18s; ventas base, 1 aprobada en 204.07s; ambas en `erp_db_test`, sin incrementar el conteo de casos únicos.
- Backend focalizado de ventas: 25 aprobadas.
- E2E anteriores: 11 aprobadas en ventas/entregas/documentos/aislamiento/Kardex y 12 aprobadas en lotes/ubicación/etiqueta/bodega madre.
- E2E E13 adicionales: 10 aprobadas en 96.23s. Salida: ../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/e13-permission-tests.log.
- Continuación P01–P04: P01 descarga documental 1 passed; P04 ajuste compensatorio + traslado parcial/final 2 passed; venta/entrega/devolución 1 passed. Son re-ejecuciones focalizadas, no suites completas; comandos y salidas en [comandos y resultados](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/comandos-y-resultados.md).
- El antiguo error de recolección por `pikepdf` queda resuelto al usar el entorno bloqueado con extras `dev+ocr`; no es un pendiente vigente.
- git diff --check: sin errores; solo avisos de conversión CRLF/LF de archivos compartidos.
- Servicios de frontend, API y base: healthy.

## Conciliación solo lectura de erp_db

| SKU | Físico | Valorado | Valor USD | Promedio USD |
| --- | ---: | ---: | ---: | ---: |
| ERS-INC-EE8FE228 | 4 | 4 | 40 | 10 |
| ERS-LATE-B1B55D6D | 5 | 5 | 60 | 12 |
| ERS-REVIEW-DD6BBF85 | 12 | 12 | 160 | 13.333333 |
| ERS-UI-F767BABC | 0 | 0 | 0 | 0 |

Los valores coinciden con el manual; cantidades físicas y valoradas iguales. En la pasada 21/10 no se ejecutaron escrituras, semillas ni cambios de corte en `erp_db`; se ejecutaron las operaciones ficticias V04 solo en la clon aislada. Ver la [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y el [log final de lectura](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log).

## Pendientes exactos de aceptación — corte final 21/10/2026

La ejecución se documenta en el [informe final V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md). No se sustituye por una nueva solicitud a otro agente.

1. **V01/E13 — ABIERTO:** el caso de documento de ajuste y otras pruebas puntuales 403/404/200 se conservan. Falta el mapa finito por acción/ruta/alcance de todos los recursos y bytes descargados desde almacenamiento real. Siguiente acción: completar `matriz-permisos.md` con las guardas dinámicas, el perfil, el recurso propio/ajeno y pruebas UI+API; revisar documentos de cada módulo.
2. **V02 — ABIERTO:** la interfaz de sesión no permitió archivar PNG. Siguiente acción exacta: usar navegador de prueba con exportación documentada; archivar las siete familias en escritorio y 390×844, claro/oscuro y completar el [manifiesto](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/manifiesto-capturas.md).
3. **V03 — ABIERTO:** QR público de HU y cancelar división se comprobaron; las dos HUs mantuvieron 2.25 cajas. El contrato de solicitud rechaza producto repetido, pero permite líneas de orden de cotización con referencias distintas; no se completó la recepción repetida visual. Siguiente acción: con compra/recepción ficticia permitida, registrar dos recepciones parciales del mismo producto, recargar y consultar aliases aplicables; probar además denegación privada ajena.
4. **V04 — parcial:** corrección de ajuste, traslado 8+2 y devolución mixta 2 aceptadas/1 rechazada desde UI aprobaron y conciliaron. **V04-04 abierto:** no se pudo simular en navegador la respuesta perdida postcommit; el intento de preparación fue bloqueado antes de reiniciar el Vite aislado. Siguiente acción: usar interceptación documentada o entorno autorizado para el Vite aislado, descartar la respuesta tras persistencia y consultar antes de replay.

La aceptación integrada sigue **PARCIAL** hasta cerrar V01, V02, V03 y V04-04. No se requiere B09 separado ni hardware físico. No se ha reproducido en esta pasada una falla nueva de permisos/stock que requiera otro cambio de código.

## Referencias

- [Revisión actual](revision-completa-2026-10-19.md)
- [Entrega B08](entrega-bloque-08.md)
- [Guía maestra](guia-maestra.md)
- [Manual de pruebas](manual-pruebas-y-demostracion.md)
- [Matriz de seguimiento](matriz-y-seguimiento.md)
- [Evidencia de 20/10](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/evidencia.md)
- [Cierre de la continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md)
- [Recorrido visual adicional](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/mobile-ui-run.md)
- [Alias de lote y trazabilidad](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/alias-trazabilidad.md)
- [Casos y evidencia P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md)
- [Matriz de permisos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/matriz-permisos.md)
- [Comandos y resultados](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/comandos-y-resultados.md)
- [Registro ESLint](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/eslint-focused.log)
- [Registro final V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md)

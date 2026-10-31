# Revisión B01–B08 y correcciones — 19/10/2026

Inicio: 19/10/2026. Continuidad y cierre de comprobaciones técnicas: 20/10/2026. La carpeta de evidencia conserva la fecha inicial.

## Estado vigente — verificación final de cuatro puntos, 21/10/2026

### Continuación más reciente — 21/10/2026

Se repitió la conciliación de solo lectura y se descubrieron datos aplicables para alias V03: tres pares de cabecera/detalle y 24 HUs históricas sin lote enlazado, sin movimiento que coincidiera con el criterio de literal divergente/FK de detalle nula. No hubo escrituras ni cambios funcionales. La herramienta de navegador rechazó la URL `localhost:5174/inventory/trace` por política de seguridad; por ello siguen sin verificarse los recorridos UI de V01, V02, V03-02/03/05 y V04-04. La crítica estática de código UI no sustituye aceptación visual y accesibilidad quedó bajo el umbral; ver [informe de continuación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/continuacion-pendientes/informe-continuacion.md).

El adaptador real de RustFS pasó un round-trip ficticio con igualdad de hash y objeto eliminado. El ciclo de documentos API no se inició: el login de prueba devolvió 401 antes de crear nada. V01 sigue abierto por la matriz de permisos/vínculos y la descarga autenticada; no se probaron credenciales adicionales.

El dictamen permanece **PARCIAL**. En clon aislada aprobaron V04-01 ajuste correctivo, V04-02 traslado 8+2 y V04-03 devolución mixta con persistencia. V01 permisos/documentos sigue abierto por matriz incompleta; V02 por no poder archivar PNG; V03 por recepción repetida/alias y consulta privada ajena aún no demostradas; V04-04 por no haberse ejecutado la pérdida de respuesta postcommit desde UI. Los SKU protegidos se conciliaron en lectura sin cambios. Evidencia vigente: [informe](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md), [casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md), [conciliación legible](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y [logs de lectura](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log).

## Estado de continuación — 20/10/2026, corte vigente

La pasada final está registrada en [cierre B01–B08](cierre-visual-y-permisos-b01-b08.md), [cierre de pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md) y [recorrido visual](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/mobile-ui-run.md). Corrige los resultados obsoletos de las secciones anteriores de esta misma fecha: Devoluciones sí se observó a 390×844 en claro/oscuro con filtro/teclado; la suite unitaria completa backend sí aprobó con extras dev+ocr; ya no se marca `pikepdf` como bloqueo.

Backend unitario: 753 aprobadas. Frontend: regresión de Traslados 2 aprobadas, chequeo 0 errores/8 avisos CSS ya conocidos, ESLint focalizado y build aprobados. Dos E2E anteriores (migración y ventas base) se repitieron, 1 cada una, en `erp_db_test`; no incrementan los 33 casos únicos que el corte anterior ya reportaba. La API en `erp_db` sigue en 0090; los cuatro SKU preservados se conciliaron solo en lectura.

La continuación corrigió la ficha de lote/HU y agregó casos persistidos para permisos de adjuntos de ajustes, corrección compensatoria, traslado 10 despachadas/8 recibidas/2 resueltas y devolución parcial multi-asignación con rollback/replay. Consulta de la HU y SKU preservados fue de solo lectura. Véase [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md) y el [registro final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md).

El cierre continúa **PARCIAL**: E13 sigue sin matriz finita de acciones/perfiles; CUA no pudo exportar PNG; P03 requiere recepción visual con líneas repetidas y consultas UI aplicables; P04 requiere devolución mixta en pantalla y recuperación de respuesta perdida desde navegador. No depende de lector ni impresora físicos.

## Resultado y alcance

Se revisaron los contratos y conexiones de B01–B08, sus decisiones de arquitectura, migraciones, pruebas y pantallas comerciales/operativas. Se corrigieron los defectos descritos abajo y se ejecutó un recorrido **persistido en `erp_db` mediante API HTTP autenticada**, desde solicitud y consolidado hasta devolución y ajuste. Se comprobó su lectura en navegador. Esto amplía la revisión acotada anterior; conserva como históricos los informes previos.

**El recorrido numérico y su conciliación están comprobados. La aceptación integral E01–E15 sigue parcial:** quedan controles visuales y combinaciones de perfiles/incidencias descritos al final. No corresponde afirmar que el manual completo se ejecutó mediante clics ni que todas las variantes posibles estén aprobadas.

Entorno: frontend `http://localhost:5173`, API `http://localhost:8000`, demo `erp_db`, Alembic `0090`. Las fixtures fueron inspeccionadas y los DSN se comprobaron por nombre de base: integración/E2E reconstruyen exclusivamente `erp_db_test`, en serie. La demo permaneció separada. No se migró ni se volvió a aprobar su corte inicial.

## Defectos corregidos

| Hallazgo | Corrección | Comprobación |
| --- | --- | --- |
| H01 Motivos vacíos tras quitar espacios | Contratos de devolución validan texto normalizado; creación/resolución también lo comprueban antes de escribir. | `test_sales_return_validation.py`: contratos y servicio sin llamadas a DB ante motivo vacío. |
| H02 Pruebas negativas buscaban «Preparar fracción» | Usan «Dividir unidad», abren el menú y comprueban que no se invoque la división. | 3 pruebas de integración de componentes de almacén. |
| H03 Documento bloqueado conservaba una instancia ORM anterior | Al bloquear cotización, venta, entrega, devolución y ajuste, se vuelve a cargar su estado persistido. | Seis casos fallaron antes de corregir; después pasan los seis más el ajuste: 7 casos de dos sesiones PostgreSQL. |
| H04 Consolidado rechazaba solicitudes nocturnas del día seleccionado | Comparación de período en `America/El_Salvador`, consistente con los filtros del repositorio. | Rechazo real de SCR-00037 antes del cambio; creación del consolidado después. Pruebas de frontera 05:00/06:00 UTC. |
| H05 Se exigía retaceo a toda recepción valorada | La liberación exige su aplicación cuando existe un retaceo activo para esa compra, conforme a la política de etiquetas. | COM-00018 bloqueó antes; luego se liberó conservando USD 200. Pruebas sin retaceo, con retaceo pendiente y aplicado. |
| H06 Navegación entre IDs podía conservar el documento anterior | Las rutas de venta y cotización, incluida edición, reinician el componente al cambiar el ID. | Revisión de ciclo de componentes y compilación. Falta caso de navegación SPA automatizado entre dos IDs. |
| H07 Recargar perdía la clave de una devolución con respuesta incierta | Comandos guardan su clave/cuerpo en `sessionStorage` por venta y acción; se limpia al confirmar éxito. Protección de doble envío. | Componente desmontado y abierto de nuevo conserva la clave tras error de red; replay real de aceptación no duplica. |
| H08 Venta entregada ofrecía preparar otra entrega | La acción se oculta cuando el progreso es completo. | Prueba de componente con venta completamente entregada. |
| H09 Guardar incidencia/resolución no enviaba el formulario | Ambos componentes Button declaran `type="submit"`. Se comprueba permiso operativo antes del envío. | `TransferIncidentForms.test.ts` monta la página, envía ambos formularios y comprueba la llamada y sus datos; también bloquea al perfil lector. No equivale a una operación persistida desde navegador. |
| H10 Ajuste por faltante bloqueaba motivo y referencia vacíos | Esos campos se pueden completar; el origen del traslado continúa fijo. | `AdjustmentIncidentEditor.test.ts` completa campos y guarda el origen, incidencia, HU y estado en tránsito correctos. |
| H11 Rechazo definitivo de una entrega dejaba selección bloqueada | Los errores definitivos 400/403/404/409/422 liberan el comando de creación para corregir la selección; un resultado incierto conserva la clave. | Prueba de rechazo 409 comprueba checkbox habilitado y eliminación del comando pendiente. |
| H12 Confirmar entrega reutilizaba una versión anterior tras editar | Se renueva la clave cuando el borrador recuperado tiene otra revisión; se conserva para repetir la misma revisión. | Prueba con comando versión 1 y documento versión 2 envía versión 2 y otra clave. |
| H13 Confirmar venta ignoraba edición visible sin guardar | Detección de cantidades, precios y notas pendientes; confirmación bloqueada hasta guardar. Botón de guardado explícitamente submit. | Prueba edita cantidad, bloquea confirmar y la habilita al guardar. |
| H14 Texto blanco sobre primario oscuro tenía contraste insuficiente | Botones comerciales usan `text-primary-foreground`, definido blanco en claro y negro en oscuro. | Token existente y compilación. No se afirma una auditoría AA completa de todas las pantallas. |
| H15 Anotaciones de fecha usaban un nombre no importado | Se importa `date` en el repositorio de valoración. | Ruff ya no informa F821. |
| H16 Expectativas antiguas en pruebas | Migración compara contra la cabeza real; carrera cancelar/convertir admite el conflicto de versión correcto o el rechazo por conversión, con código explícito. | Los dos casos se repitieron y pasaron. No se quitaron aserciones de integridad. |
| H17 Confirmar entrega ignoraba cambios visibles del borrador | La selección de HUs y las notas se comparan con el documento guardado. Se bloquea confirmar hasta guardar o descartar los cambios. | Prueba desmarca/restituye una HU y modifica notas; confirmar queda bloqueado y se habilita tras guardar. |
| H18 Resolver devolución enviaba cantidades inválidas | Validación exacta con enteros de seis decimales antes del comando; motivo normalizado con longitud mínima. | Cinco casos de componente: vacío, cero, negativo, superior al pendiente y precisión excesiva; ninguno invoca la API. |
| H19 Abrir otro traslado durante un guardado permitía que la respuesta anterior sustituyera su detalle | Navegación de documentos/filtro bloqueada durante el comando; guardia adicional en `openTransfer`. | `TransferDocumentNavigation.test.ts` comprueba bloqueo y posterior apertura. Los comandos son explícitos y la selección no cambia mientras se guardan. |
| H20 Texto semántico de avisos comerciales no alcanzaba contraste en claro | El cuerpo de avisos de error/advertencia y el estado de entrega usan `text-foreground`; conservan fondo y borde semánticos. | Revisión de tokens, comprobación de tipos/compilación y capturas comerciales en ambos temas. No se certifica AA global. |
| H21 Venta recién confirmada conservaba una consulta de disponibilidad rechazada en borrador | El panel no consulta stock de ventas borrador; recarga cuando cambia el ID/estado de la venta o su ámbito. | Prueba monta una venta borrador, la confirma sin remontar y prepara la entrega con stock actualizado y sin aviso anterior. |
| H22 Editor de ajustes usaba clases CSS de otro componente | Los controles y avisos definen clases Tailwind semánticas propias; no dependen de estilos scoped de Traslados. | Prueba de editor comprueba las clases de ancho/borde/superficie/texto y conserva el envío correcto; tipos/compilación. |
| H23 Acción de Kardex desbordaba su altura con productos de nombre largo | La etiqueta visible es «Ver Kardex»; el nombre del producto se conserva en texto accesible. | Prueba comprueba nombre accesible y texto oculto; la acción sigue abriendo el mismo artículo. |
| H24 Resumen de abastecimiento mostraba millonésimas como unidades | Se convierte el agregado entero de precisión interna a cantidad decimal antes de formatear. | Observado 2 → 2,000,000 en navegador; nueva prueba muestra 2.25 kg para 2,250,000 unidades internas. No se modifican saldos persistidos. |
| H25 Navegar a una corrección de ajuste podía mantener el detalle anterior | El detalle recarga por ID de documento y ámbito, sin depender solo de montaje inicial. | `AdjustmentDetailNavigation.test.ts` falló antes y pasa después; verifica cambio de encabezado y consulta del nuevo ID. |
| H26 Cierre con ajuste no mostraba numéricamente el faltante | El avance separa recibido, en tránsito, faltante documentado y devuelto, con unidad base. | Prueba del documento: despachado 3, recibido 2, tránsito 0, faltante 1, devuelto 0. |
| H27 Escrituras comerciales desde navegador fallaban antes de llegar al endpoint | CORS permite específicamente `Idempotency-Key`, exigida por cotizaciones/entregas/devoluciones. No se amplían orígenes ni permisos de negocio. | Preflight real del navegador daba 400. Prueba de aplicación: 3 casos fallaron antes; después pasan esos 3 y el rechazo de origen no autorizado (4 aprobados). |
| H28 Confirmaciones comerciales dependían de la ventana nativa del navegador | Cotización, venta y entrega usan el diálogo compartido del ERP, con cancelar/Escape, foco y errores recuperables. Capturan ID/revisión y cancelan la acción pendiente al abandonar la vista; la entrega describe la sucursal del documento. | Pruebas de cancelación, confirmación, fallo/reintento y desmontaje; prueba conjunta del detalle con el diálogo accesible. En navegador: Escape/confirmación de cotización, confirmación de venta y apertura/Escape del diálogo de entrega sin salida. Se cancelaron después su entrega y venta auxiliares, sin movimientos. |
| H29 Cargas comerciales podían terminar después de desmontar la pantalla | Se invalidan generaciones al salir de detalle, entregas y devoluciones; el detalle de cotización aplica la respuesta solo a la generación vigente. | Durante la prueba de desmontaje se observó aviso `derived_inert`; tras la guardia pasan 28 pruebas focalizadas sin ese aviso. |

Defensa adicional: el editor de ajustes vuelve a comprobar empresa/sucursal y generación después de cargar vehículos, unidades en tránsito y opciones. El layout ya remonta por ámbito; las guardias evitan además asignaciones tardías en el componente.

Archivos de pruebas y correcciones se conservan en el árbol de trabajo compartido, sin descartar los cambios de los bloques anteriores.

## Recorrido persistido

Artículo nuevo: **ERS-REVIEW-DD6BBF85**, unidad base `u`. Se utilizó exclusivamente para esta demostración, sin cambiar el café ni existencias históricas. La solicitud corresponde a El Tránsito y la recepción a la bodega madre. El artículo y los documentos se crearon por endpoints, sin insertar stock directamente en SQL.

| Paso | Cantidad empresa | Valor USD | Evidencia |
| --- | ---: | ---: | --- |
| Ajuste positivo documentado: 5 a 10 | 5 | 50 | Adjunto TXT real cargado, completado, aprobación y aplicación. |
| Solicitud → consolidado → RFQ → evaluación/adjudicación → orden → recepción de 10 a 15 | 15 | 200 | Documentos persistidos; compra COM-00018. Caso sin retaceo; el retaceo tardío se comprueba por separado en PostgreSQL. |
| Etiqueta y confirmación; liberación y preparación de traslado 10 | 15 | 200 | Nombre/SKU/lote de detalle y HU, sin incremento por etiquetar. |
| Despacho central → vehículo | 15 | 200 | Documento de traslado y existencia en tránsito. |
| Recepción parcial 8 | 15 | 200 | Documento continúa en tránsito; remanente 2. |
| Recepción final 2 | 15 | 200 | Documento recibido, destino 10. |
| División explícita de una HU de 8 en 3 + 5 | 15 | 200 | Una operación deliberada, revisión/etiqueta/liberación de ambas partes. |
| Cliente → cotización → venta confirmada a precio 25 | 15 | 200 | Precio comercial total 75; no crea salida. |
| Entrega confirmada de 3 | 12 | 160 | VTA-20261019-81DD0543, ENT-20261020-7D62A6E4. |
| Devolución documental recibida de 1 | 12 | 160 | No incrementa stock hasta aceptar. |
| Aceptación de 1 al costo original | 13 | 173.333333 | DEV-20261020-87D20EC3, entrada nueva en cuarentena. |
| Medidas, impresión, confirmación y liberación de la devolución | 13 | 173.333333 | No vuelve a reconocer cantidad ni costo. |
| Ajuste negativo documentado de 1 | 12 | 160 | Adjunto, aprobación y aplicación; historial anterior conservado. |
| Reimpresión/confirmación y replay de despacho, recepción parcial, entrega, devolución y ajuste | 12 | 160 | Sin duplicación. |

Conciliación final: **central 5 + sucursal 7 = físico 12 = valorado 12; diferencia 0; USD 160**. El Kardex filtrado con el código de lote mostrado en la etiqueta contiene movimientos. Se emitió un QR y su ficha pública resolvió sin credenciales, con producto y movimientos; el token no se guardó en los informes.

## Pruebas y evidencia

Carpeta: [evidencia de esta revisión](../../tmp/ers-v1/revision-2026-10-19/).

- `unit-backend.log`: 54 pruebas iniciales de reglas/contratos.
- `unit-final.log`: **37 pruebas aprobadas** de motivos, liberación, consolidado y CORS, con los nuevos casos.
- `integration.log`: 11 pruebas de valoración, retaceo tardío/devolución, traslados y ajustes.
- `locks-before.log`: seis fallos reproducidos; `locks-after.log`: seis aprobados; `recheck.log` incluye los siete casos actuales de bloqueo y dos E2E corregidas, **9 aprobados**.
- `e2e.log`: primera pasada **8 aprobados y 2 fallos** por expectativas antiguas. `recheck.log` acredita sus correcciones.
- `final-integration.log`: 12 pruebas aprobadas; la prueba ampliada de devoluciones falló al construir la empresa ficticia por un campo obligatorio de la fixture. Se corrigió esa fixture y se repitió en `returns-concurrency-scope.log`: **1 aprobado**.
- Esa última prueba comprueba dos aceptaciones concurrentes de la misma cantidad: una gana y otra se rechaza, con una sola entrada; lectura por sucursal propia, rechazo de consulta y aceptación desde otra sucursal, lista filtrada y 404 desde otra empresa. Respuestas de un operador sin valoración omiten importes de costo.
- `frontend.log`: suite inicial, **108 archivos/483 pruebas aprobadas**. `frontend-complete-final.log`: suite final, **115 archivos/509 pruebas aprobadas**. `commercial-confirmation-tests.log`: 28 pruebas focalizadas aprobadas sin el aviso de efecto desmontado; `confirmation-dialog-integration.log`: 3 pruebas del detalle/diálogo; `delivery-confirmation-tests.log`: 9 pruebas de entrega, incluido cancelar/desmontar confirmación sin salida. `ui-final-guards-recheck.log`: 22 pruebas focalizadas aprobadas. `incident-forms-final.log`: 3 pruebas de formularios/perfil lector/separación del faltante aprobadas. `ui-round3-recheck-final.log`: 22 pruebas de entregas, Kardex y ajustes aprobadas. `adjustment-navigation-before.log` conserva el fallo; `adjustment-navigation-after.log` acredita 3 casos aprobados. No se suman estas repeticiones.
- `cors-before.log`: 3 fallos de preflight y rechazo de origen no autorizado aprobado. `cors-after.log`: **4 aprobados**, sin base de datos. Ruff focalizado de `app/main.py` y `test_sales_cors.py` aprobado.
- `frontend-check-final.log`: **0 errores y 8 avisos CSS** `@apply` anteriores en TransferOperationsPage. `frontend-build-final.log`: **compilación de producción aprobada**, con avisos conocidos de importación no usada `jsbarcode` y selección de entorno `adapter-auto`. No se afirma que se desplegó a producción.
- `eslint-final.log`: **ESLint focalizado aprobado** para componentes comerciales, lista de documentos y nuevas pruebas de formularios/navegación. No equivale a lint global del ERP.
- `ruff-final.log`: quedan tres avisos de complejidad/constante en el caso de uso de consolidación; no se presenta lint global como aprobado.
- `demo-api.log`, `demo-state.json` y `demo_api.py`: resultado, IDs/respuestas sin credenciales y procedimiento de la demo. El script toma credenciales por entrada estándar; no contiene contraseñas. Sus checkpoints evitan volver a crear etapas ya registradas.

No se suman ejecuciones repetidas como si fueran casos distintos. Además de la prueba del motor PostgreSQL, se completó después el formulario de retaceo tardío descrito abajo.

### Lectura real en navegador

Se comprobó la venta entregada y la devolución aceptada con recarga, nombre/SKU, límite restante de devolución 2 e historial. La venta entregada ya no ofrece preparar otra entrega. El evento muestra «Aceptada · ingresó en cuarentena», sin afirmar que siga allí después de su liberación/ajuste. Se inspeccionó la zona de devolución en claro y oscuro.

Kardex → Conciliación mostró el artículo de demostración con físico **12**, valorado **12**, diferencia **0**, valor **USD 160.00**. Evidencias: `venta-devolucion-final-oscuro.png`, `venta-devolucion-final-claro.png` y `conciliacion-final.png`. Son capturas de lectura persistida, no prueba de todos los formularios por clics. Se reiniciaron servicios de desarrollo para servir sus correcciones, incluido backend por la configuración CORS; no se reconstruyó la base.

### Caso adicional de incidencia operado en pantalla

SKU nuevo **ERS-INC-EE8FE228**, separado del ejemplo principal. Se prepararon por API 5 unidades/USD 50, traslado de 3 y recepción parcial de 2. Desde el navegador se guardó una incidencia, se resolvió reanudando tránsito, se abrió una segunda por faltante definitivo y se creó su ajuste enlazado **AJ-20261020-000002**. El motivo/referencia se completaron en su formulario; se adjuntó el archivo ficticio `ACTA-INC-DEMO-02.txt` con validación, se aprobó y se aplicó con confirmación.

El diálogo se cerró con Escape devolviendo foco a «Aplicar ajuste…»; al reabrir, Tab alcanzó «Aplicar ajuste ahora» y Enter ejecutó la confirmación. El documento quedó aplicado y el traslado **TR-20261020-3BF90713** cerró como **Cerrado con ajuste**, conservando ambos eventos de incidencia. Lectura autenticada posterior: recibido 2, faltante autorizado 1, tránsito 0; conciliación del artículo **4/4, diferencia 0, USD 40**. El ejemplo principal conserva **12/12, USD 160**.

Evidencia: `incident-demo-setup.log`, `incident-demo-state.json`, `incident-demo-verified.log`, `traslado-cerrado-con-ajuste.png`, `ajuste-aplicado-movil.png` y `ajuste-aplicado-movil-cabecera.png`. El detalle aplicado se inspeccionó a **390×844**: ancho de documento y contenido 390 px, sin desbordamiento horizontal; se restauró el tamaño original. Esta comprobación no equivale a revisar todos los módulos en móvil.

### Devolución rechazada desde el navegador

Se creó **DEV-20261020-8A63F2BF** sobre la venta principal, con cantidad 1 y condición dañada. Creación, recepción y rechazo se operaron en pantalla. Antes de resolver se intentó cantidad cero: el formulario la bloqueó y conservó el pendiente. Al rechazar 1, quedó rechazada, sin movimiento ni entrada de valoración; la reserva volvió a cero y la cantidad susceptible de devolución volvió a 2. El saldo principal conserva **12/12, USD 160**. La lectura autenticada de `incident-demo-verified.log` comprueba esos efectos y el único evento de rechazo; captura `devolucion-rechazada-ui.png`.

### Retaceo tardío y devolución operados en pantalla

Caso independiente **ERS-LATE-B1B55D6D**, compra **COM-00019**: recepción de 10 a USD 10 y entrega de 6 mediante API, dejando **4/USD 40**. Desde la compra se creó **RET-00016**, se agregó flete de USD 20, se distribuyó a la línea recibida y se guardó. Calcular sin respaldo fue rechazado. Se adjuntó desde el formulario `ACTA-RETACEO-DEMO.txt` y se completó cálculo → verificación → aplicación → cierre.

Lecturas HTTP independientes después de cada etapa: calculado **4/40**, verificado **4/40**, aplicado y cerrado **4/48**. El único evento de ajuste tiene cantidad cero, costo fuente 20 y aumento del inventario 8; la diferencia **12** corresponde al costo de las salidas. No se modificó el precio comercial ni se sumaron unidades.

Después, desde la venta **VTA-20261020-EC35E6B7**, se creó y recibió **DEV-20261020-ACB68F5E**, todavía **4/48**, y se aceptó 1. Quedó **5/60**, con entrada de valor 12 vinculada a la salida original y nueva HU en cuarentena; no se reabrió pendiente de entrega. Esta prueba no usa el campo `source_value` de la devolución como costo reconocido: el motor lo deriva del origen y registra el efecto en `inventory_delta`.

Evidencia: `retaceo-demo-setup.log`, `retaceo-demo-state.json`, `retaceo-ui-calculated.log`, `retaceo-ui-verified.log`, `retaceo-ui-applied.log`, `retaceo-ui-closed.log`, `retaceo-ui-return-received.log`, `retaceo-ui-returned.log`, `retaceo-tardio-cerrado-ui.png` y `devolucion-tras-retaceo-ui.png`. El ejemplo principal conserva **12/USD 160**. No se reutilizaron existencias históricas ni se alteró el corte inicial.

Después se completó desde almacén la HU **HU-RET-222B0730708C466E**: medición manual de demostración 0.1 kg/0.001 m³, vista de etiqueta con nombre/SKU, código de barras, lote canónico, fecha y cantidad; confirmación de etiqueta y liberación a disponible. La impresión se **registró por API como simulación digital**, sin abrir el diálogo del sistema ni usar impresora; no acredita impresión o colocación físicas. La confirmación y liberación del sistema se operaron por pantalla para esta demostración ficticia, conforme a la exclusión de hardware del usuario. Resultado: «Revisión terminada · disponible para uso», cantidad 1 en su HU y total del artículo **5/USD 60**, sin otra entrada ni división. Evidencia `return-label-demo.log`, `return-released-ui.log` y `devolucion-liberada-almacen-ui.png`.

Comprobación adicional del último diálogo de entrega: se prepararon por API una venta y entrega auxiliares **VTA-20261020-C7A2F225 / ENT-20261020-BF14621F** sobre el mismo artículo; en navegador se abrió la confirmación integrada y Escape devolvió el foco sin ejecutar. Se cancelaron su borrador y venta desde pantalla. La lectura posterior acredita ambos cancelados, asignaciones sin movimiento y saldo **5/60** intacto (`delivery-dialog-cancelled-ui.log`). El historial permanece; no se borraron documentos.

### Cliente, cotización, venta y dos entregas desde pantalla

Caso separado **ERS-UI-F767BABC**: preparación por API de 4 unidades/USD 40 mediante ajuste documentado y dos HUs disponibles de 2. Desde navegador se registró el cliente **ERS-UI-F767BABC**, se creó **CV-20261020-2BFF8493**, se confirmó y convirtió en **VTA-20261020-C99E3B6F**, por 4 a precio comercial 20 (USD 80). Se modificaron notas: confirmar quedó deshabilitado hasta guardar. Escape en la confirmación de cotización conservó borrador y devolvió foco; reabrir y aceptar confirmó una vez. La venta confirmada cargó disponibilidad sin remonte manual.

Lectura HTTP independiente después de cliente/cotización, confirmación de cotización, confirmación de venta y borrador de entrega: **4/USD 40**. Se prepararon y confirmaron **ENT-20261020-60E9E1AB** y **ENT-20261020-0E0F9F4C**, 2 cada una: primera **2/USD 20**, segunda **0/USD 0**, estado de entrega completo, entregado 4, pendiente 0 y dos salidas. Después no se ofrece otra preparación. Hubo tiempos de espera del control de navegador; se consultó el estado guardado antes de repetir una escritura y no se duplicaron entregas. El intento inicial de confirmación de cotización se conserva como no acreditado en `commercial-ui-confirmation-attempt.log`; el verificador posterior exige también el estado confirmado.

Evidencia: `commercial-ui-setup.log`, `commercial-ui-state.json`, `commercial-ui-quote.log`, `commercial-ui-quote-confirmed.log`, `commercial-ui-sale-confirmed.log`, `commercial-ui-delivery-draft.log`, `commercial-ui-partial.log` y `commercial-ui-complete.log`; capturas `venta-entregas-parciales-completas.png` y `venta-entregada-movil-claro.png`. Lectura de venta entregada a 390×844, tema claro: contenido y viewport 390 px, sin desbordamiento horizontal exterior; tablas conservan su área desplazable. Se restauraron tema oscuro y tamaño de escritorio.

En Traslados se comprobó el agregado corregido del SKU de incidencia: **2 u**, sin mostrar 2,000,000. Para el SKU de retaceo se abrió la demanda **SCR-00038** de El Tránsito: producto/unidad visibles, pendiente 10 y destino El Tránsito preseleccionado. Descartar no creó traslado ni dividió unidades. El traslado cerrado de incidencia muestra ahora despachado 3, recibido 2, tránsito 0, **faltante documentado 1 u**, devuelto 0, y ambos eventos de incidencia. Capturas `demanda-destino-preseleccionado.png` y `traslado-faltante-numerico-final.png`.

Se inspeccionó también Sucursales: **Casa matriz**, código HQ-0A7303F6, activa, marcada matriz administrativa, sin ubicación física y con un almacén; su detalle distingue «No aplica» para actividad comercial. El inventario de la bodega central original mantiene la URL/ID **14e5a8bc-20e6-4184-99a1-4238000eca8a**. Captura `matriz-administrativa-final.png`. Conciliación actual de los cuatro casos: **incidencia 4/40, retaceo 5/60, principal 12/160, comercial 0/0**, todos con diferencia cero; captura `conciliacion-final-actual.png`.

## E01–E15: estado actual

| Criterio | Resultado demostrado | Lo que falta para la aceptación completa |
| --- | --- | --- |
| E01 Matriz/bodega original | Migración de conservación; inspección de Casa matriz administrativa activa, un almacén, sin actividad comercial ni ubicación física; bodega central conserva ID y URL. | Variantes de permisos y otros tamaños; no se acredita todo perfil. |
| E02 Lote por recepción/producto | Migración, recepciones parciales y lote canónico de COM-00018. | Repetir la consulta visual con varias líneas del mismo producto. |
| E03 Saldo por ubicación | Recepción, división, traslado y conciliación numérica persistida. | Recorrido visual de todos los estados/ubicaciones. |
| E04 Etiquetas | Impresión, confirmación, reimpresión y no duplicación por API. Vista de etiqueta y confirmación por pantalla de la devolución con nombre, SKU, código de barras, lote y cantidad. Registro de impresión digital simulado; hardware excluido. | Teclado y presentación móvil/claro/oscuro completa. |
| E05 Código/Kardex | Código de etiqueta filtra movimientos del Kardex; QR público resuelve. | Confirmación visual de todos los alias antiguos. |
| E06 Vehículo/estados/demanda | Solicitud enlazada, vehículo, despacho/recepción persistidos. Formularios de incidencia y resolución usados desde navegador, con historial y cierre por ajuste. | Revisión de presentación móvil/temas y perfiles restantes. |
| E07 Parcialidad/neutralidad | Recepción 8 + 2, estados y USD 200 invariantes, más E2E de concurrencia. | Ningún pendiente en ese caso numérico por API; queda uso desde pantallas. |
| E08 Ajustes/evidencia | Positivo/negativo con adjuntos, aprobación/aplicación; faltante creado, adjuntado, aprobado y aplicado desde navegador; diálogo probado con teclado y detalle móvil. | Matriz exhaustiva de permisos B05 y variantes de corrección desde interfaz. |
| E09 Documentos sin salida | Caso principal mantiene 15/USD 200. Caso UI: cliente/cotización/venta creados y confirmados desde pantalla mantienen 4/USD 40; guardar antes de confirmar y Escape comprobados. Lectura final móvil/claro sin desbordamiento exterior. | Perfiles y estados de error restantes; no se acredita toda combinación de pantallas/temas. |
| E10 Entrega | Salida 3/costo 40 del ejemplo principal. Dos entregas por pantalla de 2+2, saldo 4/40 → 2/20 → 0/0, entrega completa y sin nueva preparación. Último diálogo abierto/cancelado en pantalla sin salida; entrega/venta auxiliares canceladas. API cubre rollback, concurrencia, cuarentena y cancelaciones. | Recuperación de errores por clics con todos los perfiles; no se acredita cada variante. |
| E11 Devolución | Entrada de 1 al origen, cuarentena/liberación, concurrencia/alcance. Creación/recepción/rechazo y creación/recepción/aceptación tras retaceo realizados desde navegador; cero bloqueado y persistencia comprobada. | Completar la matriz visual de perfiles y variantes parciales; no se acredita toda combinación. |
| E12 Promedio global | Conciliación 12/USD 160, traslado neutro. Retaceo tardío creado, respaldado, calculado, verificado, aplicado y cerrado desde navegador: 4/40 → 4/48; devolución posterior 5/60. | Sin pendiente en estos casos numéricos; presentación y perfiles restantes se conservan en E13/E14. |
| E13 Permisos/atomicidad | Pruebas de sucursales/empresas, ocultación de costos, replay y rollback. | Matriz exhaustiva de perfiles sobre documentos y evidencias de todos los módulos. |
| E14 Cuarentena/disponibilidad | Recepción y devolución liberadas sin doble contabilización. La devolución posterior a RET-00016 completó medidas/confirmación de etiqueta/liberación desde pantalla, con impresión digital simulada, manteniendo 5/60. | Revisión móvil y perfiles restantes. Ningún pendiente numérico en este caso aplicable. |
| E15 Migración/conciliación | 0090, migraciones B01/B02 repetidas y conciliación tras el flujo completo por API y pantalla. | Conservación de demo antes/después documentada por respaldo y datos; restauración ya ensayada anteriormente, no repetida en esta pasada. |

## Respaldo y continuidad

Respaldo previo a los datos de esta demo: `tmp/ers-v1/revision-2026-10-19/erp_db_before_demo.dump`. SHA256: `38A7F89B5DF8F97FA0F1FFD4CB85351C39F86C84973384E91EEF90D0B8234C15`. Recuperar primero en una base aparte para inspeccionar; no sobrescribir la demo como parte de una prueba ordinaria. Los datos nuevos están identificados por el SKU de demostración.

Queda deuda de arquitectura: los servicios comerciales usan consultas ORM directamente en la capa application, aunque la guía pide puertos/repositorios. No se hizo una reestructuración global durante la auditoría funcional. La demostración comprobada no acredita conformidad literal del modelo físico con la ERS ni aprobación del docente.

Las revisiones independientes de UI detectaron H09–H14, H17–H20 y H21–H23. La segunda puntuó el estado anterior en **6.9/10 de categorías evaluables**, con rechazo; no era una puntuación visual completa. La tercera se completó al retomar el 20/10 y puntuó **7.5/10**, también con rechazo; detectó H21–H23, corregidos después. No se presenta esa puntuación como aprobación de la versión posterior.

Scorecard de la tercera revisión: distinción visual 7.5, tipografía/contenido 7.5, layout/responsive 7, interacciones 8, sistema de diseño 6.5, accesibilidad 8, código 8, estados 7.5. Evidencia limitada a código, pruebas leídas y capturas de escritorio. Se cumplieron tres rondas de revisión y corrección; la interfaz no se declara certificada con el estándar visual del skill. Los defectos funcionales encontrados se corrigieron y tienen las comprobaciones indicadas.

Pendiente de presentación observado: algunos snapshots comerciales repiten «Unidad (u) (u)». No se alteraron snapshots históricos ni se certificó la revisión móvil/teclado de todas las pantallas. El siguiente paso de aceptación es completar los controles concretos E01–E15 de la tabla, conservando esta evidencia. Impresora y lector físicos siguen excluidos; B09 es el checklist del cierre de B08.

### Punto concreto para continuar

El recorrido calculable, retaceo tardío, rechazos, pérdida autorizada, entregas parciales y final de revisión de almacén ya tienen evidencia persistida. No repetir sus escrituras para continuar la auditoría. Prioridades pendientes:

1. **E13 / variantes B05–B08:** completar la matriz pendiente de perfiles, permisos y acceso a adjuntos en todos los documentos, aprovechando las pruebas de aislamiento ya registradas. La cobertura focalizada actual no acredita esa matriz exhaustiva.
2. **E02/E04/E05:** consulta visual de varias líneas del mismo producto por recepción, alias históricos de lote/etiqueta y variantes de etiqueta en móvil/teclado. Las migraciones y los casos por API ya documentados se conservan.
3. **Presentación y recuperación:** completar temas/tamaños y recuperación de errores reales en las pantallas que la tabla todavía marca parciales. Corregir presentación duplicada de unidad sin reescribir snapshots históricos; distinguir esta mejora de la deuda ORM/puertos y complejidad de consolidación ya identificadas.

Estado de esta pasada: correcciones encontradas implementadas y comprobadas en las modalidades indicadas; aceptación total aún **parcial**, sin atribuir pendientes a la impresora o al lector excluidos por el usuario.
 
## Corte intermedio — 20/10/2026 (superado por la continuación final)

El texto de este apartado conserva el estado anterior a P01–P04. Para el estado vigente, usa la actualización que aparece al inicio y su [registro de casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md).

La revisión de cierre actual está en [cierre visual y permisos B01–B08](cierre-visual-y-permisos-b01-b08.md). En Devoluciones se corrigió «Unidad (u) (u)» solo en presentación y se añadieron estados semánticos y un anuncio accesible del filtro. La segunda revisión independiente aprobó esa pantalla con 8.56/10. Se comprobó en escritorio, tema claro y oscuro; el oscuro quedó restaurado.

Pasaron 116 archivos/513 pruebas frontend, 25 pruebas backend focalizadas y 33 E2E seleccionadas; svelte-check reportó cero errores y ocho avisos CSS conocidos; lint focalizado y build pasaron. La suite backend tests/unit completa no se recolecta por pikepdf ausente en la prueba OCR. No se escribió en erp_db. La conciliación de solo lectura confirma los cuatro SKU guardados.

La aceptación integrada continúa **PARCIAL**: E13 no tiene matriz exhaustiva por recurso/acción/perfil/contexto; Devoluciones móvil, recepción visual de varias líneas del mismo producto y alias históricos siguen sin evidencia en vivo. El detalle está en el nuevo informe y en su [evidencia fechada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/evidencia.md). Se preservan los cortes históricos anteriores.

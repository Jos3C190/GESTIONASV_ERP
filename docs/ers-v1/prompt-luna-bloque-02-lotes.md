# Encargo Luna — ERS-B02: lote por producto, etiqueta y Kardex

Implementa el bloque sobre B01 y conserva la trazabilidad histórica. Lee [guía](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-01/02/04/07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md), [entrega B01](C:/Developer/GESTIONASV_ERP/docs/ers-v1/entrega-bloque-01.md) y [revisión B01](C:/Developer/GESTIONASV_ERP/docs/ers-v1/revision-bloque-01.md). Aplica las instrucciones del repositorio y el protocolo feature-development. El usuario encarga ejecutar, probar y documentar; no te limites a entregar un plan.

## Fase 0 obligatoria — cerrar B01 antes de continuar

Revisión independiente del 18/10/2026: 28 pruebas repetidas y aprobadas, pero la demo `erp_db` sigue en 0083. Comprueba de nuevo el estado al comenzar; esta observación puede haber cambiado. No confundas pruebas aisladas con activación de la demo.

1. **R02, prevalidación:** alinea la vista previa `backend/scripts/preview_headquarters_migration.py` con las precondiciones de 0084, incluyendo almacenes no centrales sin sucursal y dirección vacía/NULL. Prueba que la vista previa informa los impedimentos reales sin escribir. Conserva el destino esperado obligatorio y el mapa por empresa. No flexibilices integridad para hacer pasar la migración. No reescribas migraciones ya aplicadas en otros entornos: comprueba su estado y usa una nueva migración si hace falta corregir esquema/datos desplegados.
2. **R03, evidencia:** amplía la prueba de migración con valoración activa y registros no vacíos de costo, entradas de valoración y aplicación de retaceo; compara IDs, cantidades, valores y filas antes/después. Añade prueba HTTP real de lectura/listado de recepción central histórica con sucursal nula por usuario matriz/global y rechazo de sucursal ajena, sin rellenar la sucursal histórica. Comprueba navegación a orden/retaceo cuando existan. Corrige el informe: el test actual crea el borrador como administrador y el usuario matriz recibe/verifica/consulta; no atribuyas creación al usuario limitado sin probarla. Corrige descripción del rol de prueba y método/ruta de actualización de almacenes en API docs.
3. Ejecuta en serie los E2E que reconstruyen `erp_db_test`; no ejecutes suites concurrentes sobre esa misma base. Repite las 28 pruebas de la revisión más las regresiones nuevas. No uses `erp_db` para fixtures destructivos.
4. **R01, activación:** confirma nombre real de base y revisión, realiza respaldo fuera del contenedor y comprueba que es restaurable en una base temporal distinta. Registra ubicación del respaldo, comando seguro y resultado, sin credenciales. Corre la vista previa; aplica 0084 a la demo solo con ensayo y respaldo satisfactorios. Está dentro del cierre solicitado: no vuelvas a pedir autorización rutinaria para ese procedimiento. Ante ambigüedad de mapeo, fallo de respaldo o diferencia de datos, detén esa escritura y documenta el impedimento; nunca borres/resembres para resolverlo. Si ya está aplicada, verifica en vez de duplicar Casa matriz.
5. Recorre autenticado sucursal matriz → bodega central → recepción antigua/nueva, verificando permisos y selección de la central. Conserva IDs, ubicaciones, HUs, lotes, saldos, valores e historial. Usa datos de prueba aislados para operaciones de compra; en demo prioriza consultas a documentos existentes. Actualiza entrega B01 y seguimiento con evidencia específica de R01–R03. Si queda un impedimento, no declares B01 cerrado ni B02 aceptado sobre la demo.

## Ejecución de B02

Una vez cerrado lo anterior, implementa el contrato siguiente. No cambies el alcance de B03–B09. Mantén separada la evidencia de correcciones B01 y funcionalidades B02.

## Responsabilidad y contexto

Eres responsable de identidad de lotes, migración/adaptación, proyección por ubicación, etiqueta, trazabilidad y filtro del Kardex. No estás solo en el repositorio; conserva cambios ajenos. Parte de:

- [Lotes](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory_lot.py) y [ingreso desde compra](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/purchase_inventory_gateway.py).
- [Etiquetas](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_label_repository.py).
- [Lectura Kardex](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_kardex_read_repository.py).
- [Modelos físicos](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/inventory.py) y [diálogo de etiqueta](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte).

## Contrato a implementar

Mantén la cabecera de recepción; identifica cada detalle real de producto recibido como lote canónico con código único por empresa. El código debe ser estable e independiente del orden de presentación. Recepciones parciales distintas y líneas distintas conservan su propio origen.

La estructura existente es `inventory_lots` (cabecera por recepción) y `inventory_lot_details` (producto/detalle recibido). Extiende el detalle existente; no crees un segundo motor de lotes. Propaga su identidad por relaciones explícitas de origen y claves por empresa. No deduzcas origen solo de producto, nombre, posición, lote del fabricante ni del texto libre de un movimiento. Aplica unicidad en PostgreSQL y prueba reintentos/concurrencia. La generación debe sobrevivir a reordenación de líneas y nuevas recepciones sin renumerar códigos previos.

Conecta etiqueta, búsqueda, trazabilidad, API y Kardex a esa identidad. La búsqueda del código antiguo de cabecera resuelve los lotes asociados; si son varios, los presenta sin atribuir todas las cantidades a un solo producto. Diferencia lote del fabricante. Conserva aliases, snapshots históricos y acceso a QR/etiquetas existentes; no los reescribas ni generes impresiones o confirmaciones por migrar.

Implementa una proyección de saldos por lote canónico, ubicación y estado equivalente a inventory_location_details. Su fuente son relaciones físicas existentes con origen fiable; no mantengas otro saldo editable. Reconcilia su suma con HUs, movimientos y totales. No asignes un origen inventado a stock histórico sin referencia: identifica esos registros y su tratamiento.

Haz visible el stock legado no atribuible como tal y concilia `atribuible + legado = total` para cada ámbito comparable. Incluir tránsito cuando corresponda al total de empresa; no sumar dos veces HUs y saldos que representan el mismo stock. El saldo inicial aprobado no constituye por sí mismo evidencia de una recepción específica. Una división explícita conserva lote y cantidad total, no dispara otra división al abrir/cerrar panel, revisar etiqueta, reimprimir o liberar. Conserva producto, SKU, presentación/unidad y HU visibles, así como el estado final «Disponible / revisión terminada» y la división opcional en otras acciones.

Conserva requisitos de medición, retaceo y etiqueta antes de disponible. Registra en documentación la secuencia provisional → retaceo aplicado → disponible, y su diferencia explícita respecto a la narrativa de la ERS. Esta tarea no cambia el método de costo ni el corte inicial aprobado.

## Aceptación

- B02-A1: recepción con dos productos produce dos códigos canónicos; otra recepción parcial del mismo producto produce otro origen distinguible. Dos líneas del mismo producto no se fusionan perdiendo su purchase_detail_id.
- B02-A2: buscar el código nuevo de la etiqueta devuelve sus movimientos correctos en Kardex; buscar la cabecera antigua sigue funcionando. Filtros de producto, fechas, empresa y lote se combinan correctamente.
- B02-A3: distribución del mismo lote entre ubicaciones, división y traslado conservan identidad y suma. Una HU cerrada o de cantidad cero no duplica el saldo.
- B02-A4: migración conserva cantidades, valores, movimientos, impresiones y confirmaciones históricas. El código anterior y QR resuelven su origen; no se exige reimprimir solo por esta adaptación.
- B02-A5: código de barras usa código interno y texto muestra producto, lote y fecha. No generar etiquetas con identidad ambigua de variante: resuelve el contrato o informa el caso pendiente explícito.
- B02-A6: otra empresa no consulta lotes ajenos; fallos y reintentos no crean duplicados. Kardex y proyección siguen conciliando con valoración activa.
- B02-A7: concurrencia y fallo tras una escritura intermedia no dejan lote/detalle/código, movimiento o auditoría de éxito parcialmente confirmados. Considera que la sesión actual confirma `AppError`: usa la unidad de trabajo/savepoint apropiado y prueba rollback.
- B02-A8: abrir/cerrar paneles, consultar QR, revisar etiqueta y liberar no crean HUs ni cambian cantidades. Dividir una vez crea solo la fracción prevista y conserva el origen; no se obliga a fraccionar nuevamente. Etiquetas históricas siguen resolviendo sin confirmar impresiones ficticias.

## Pruebas, migración y entrega

Prueba PostgreSQL y API, cambios de filtros/contexto de UI y recorrido autenticado etiqueta → Kardex con los códigos nuevo y antiguo. Verifica cambio de empresa y sucursal, estados de error/vacío/carga, acceso sin permiso de costos y enlace QR público sin ampliar la información sensible expuesta. El lector HS200 y la impresión física están excluidos; basta demostrar generación, vista y confirmación de etiqueta por software. No envíes trabajos a una impresora real.

Antes de migrar B02: inventario de referencias, previsualización del mapeo, ensayo en base aislada, comparación de cantidades/valores/historia y recuperación probada. Conserva revisiones previas y el orden Alembic; verifica la cabeza actual antes de asignar el siguiente número. Respalda antes de activar en demo y documenta la revisión final realmente aplicada. No uses un downgrade en demo después de operaciones nuevas como recuperación automática.

Documenta el mapeo entre tablas actuales y ERS; no declares identidad física de esquemas. Entrega `docs/ers-v1/entrega-bloque-02.md`, evidencia en `tmp/ers-v1/bloque-02/`, y actualiza API/esquema/RBAC cuando cambien, guía y matriz E02–E05, E12–E14. Mantén E01/E13 de B01 con su cierre específico. Incluye archivos modificados, casos por criterio, comandos/resultados, límites del legado y pasos manuales breves. Distingue probado, pendiente y no aplicable; no sustituyas evidencia por un conteo de pruebas. No avances a B03 automáticamente.

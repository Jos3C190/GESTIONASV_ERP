# Encargo Luna — ERS-B03: documento, vehículo y motor de traslados

Implementa el dominio, persistencia y API del nuevo traslado sobre B01/B02. Lee [guía](C:/Developer/GESTIONASV_ERP/docs/ers-v1/guia-maestra.md), [ADR-03/04/07](C:/Developer/GESTIONASV_ERP/docs/ers-v1/decisiones-arquitectura.md) e informes precedentes. La interfaz completa se conecta en B04; mantén utilizable el flujo anterior durante esta transición.

## Punto de partida y decisión del usuario (18/10/2026)

El usuario autoriza continuar B03 y hacer la revisión completa al terminar B08. B01/B02 están verificados técnicamente según sus informes; su aceptación visual pendiente se acumula para ese cierre y no bloquea este encargo. Mantén pruebas técnicas focalizadas por bloque; no vuelvas a auditar todo el proyecto ni marques la revisión manual como aprobada.

Lee entrega-bloque-02.md y tmp/ers-v1/bloque-02/evidencia-2026-10-18.md. La última base demo comprobada es erp_db en 0085; comprueba la cabeza efectiva antes de crear una migración sucesora. Preserva IDs de matriz/bodega central, saldos, etiquetas y documentos existentes. No ejecutes semillas destructivas ni reabras el saldo inicial aprobado.

B02 deja inventory_lot_details.code como identidad canónica por detalle recibido y inventory_movement_lines.inventory_lot_detail_id para nuevos movimientos. Los históricos son inmutables: su lectura solo puede resolver el detalle mediante una HU con relación exacta. El informe registró 18 líneas resolubles así y 53 sin atribución; son una referencia de ese corte, no cifras que debas forzar. No actualices esas líneas ni desactives su trigger para completar orígenes. Conserva alias de cabecera y QR previos. Transferir o dividir conserva el lote canónico; no genera otra recepción de compra.

## Archivos y límites

Responsable de nuevos módulos de vehículos y documentos de traslado en las cuatro capas, migraciones y puertos hacia inventario. Conserva cambios ajenos; no estás solo en el repositorio. Reutiliza [motor de movimientos](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/repositories/inventory_repository.py), [casos de uso](C:/Developer/GESTIONASV_ERP/backend/app/application/inventory/use_cases.py), [ubicaciones](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/location.py) y [API actual](C:/Developer/GESTIONASV_ERP/backend/app/api/v1/routers/inventory.py).

## Implementación

1. Vehículo mínimo por empresa con código/identificación, estado y ubicación móvil. Usa la ubicación vehicle dentro del almacén técnico de tránsito de ADR-03, asociado a la matriz. Mantén este almacén fuera de selectores de venta/recepción comercial y de capacidad de estantes, pero dentro de conciliación global. No duplicar mercancía.
2. Cabecera/detalles de traslado: código, empresa, bodegas origen/destino, vehículo/ubicación, fechas, estados, líneas de producto/lote/HU, cantidades previstas/despachadas/recibidas y actores. Enlaza solicitudes/detalles de demanda con cantidades asignadas mediante relaciones estructuradas; admite envío manual y excedente con motivo.
3. Acciones explícitas: crear/editar preparación, cancelar preparación, despachar, recibir parcial/total, abrir incidencia y resolverla con evidencia. Al inicio, la resolución de pérdidas depende del ajuste de B05: el estado de incidencia y su detalle funcionan, pero nunca descuentan una pérdida sin ajuste autorizado.
4. Preparación no mueve ni reserva stock físico. Despacho central → ubicación vehículo. Recepción vehículo → ubicación de recepción/cuarentena destino. Preservar lotes y política de liberación. No usar destino como ubicación física mientras viaja.
5. Conservación por línea: despachado = recibido + aún en tránsito + cantidades resueltas mediante retorno/pérdida documentada, sin solapar categorías. Una recepción parcial no marca el documento recibido completo.
6. Una transacción coordina documento, motor de inventario, valoración y auditoría. Protege errores de negocio frente al commit de AppError. Autorización de origen/destino/empresa y de acciones sobre vehículo; receptor autorizado de sucursal no requiere lectura global de empresa.
7. Especifica contratos consumibles por B04 y compatibilidad temporal con movimientos previos. Para histórico sin vehículo, conserva origen verificable y marca legado; nunca falsifiques un despacho. El endpoint de documento no acepta un movimiento genérico para saltarse estados.

8. Publica una tabla de transiciones PREPARACIÓN → EN TRÁNSITO → RECIBIDO, con INCIDENCIA y CANCELADO según ADR-03. Identifica cada evento de recepción parcial y cada asignación de HU/lote. Usa Decimal y unidades/conversiones explícitas; no redondees remanentes a cero ni supongas indivisibilidad por el nombre «Caja».
9. Centraliza comandos nuevos en el documento de traslado. Revisa los endpoints anteriores y documenta qué adaptador conserva cada consumidor: no mantener dos caminos que contabilicen el mismo despacho. No simular vehículo, despacho o recepción para el histórico. Preserva la consulta de demanda por producto/sucursal; B04 conectará su selección y las pantallas completas.
10. El API para B04 debe entregar producto, SKU, presentación/unidad, cantidades solicitadas/asignadas/en tránsito/recibidas y pendiente sin duplicar demanda entre documentos. Distingue cantidades sin solicitud y excedentes con motivo; valida vínculos de empresa/producto/destino. Incluye ejemplos de cuerpos, respuestas y errores, permisos, claves idempotentes y política de concurrencia. Abrir/consultar/cancelar un formulario nunca produce divisiones ni movimientos.

## Migración y comprobación técnica de este bloque

- Inspecciona las fixtures antes de ejecutar integración/E2E: los DSN deben apuntar exclusivamente a erp_db_test. Ejecuta suites que reconstruyen esquema en serie; nunca sobre erp_db. Reutiliza pruebas pertinentes y añade las necesarias para A1–A8, sin repetir suites sin cambios.
- Antes de migrar la demo, registra respaldo recuperable y realiza preflight/ensayo en copia aislada con datos previos. Compara cantidades por producto y ubicación/estado, valor global, identidades y contenido histórico. Actualiza la demo solo tras superar el ensayo; registra cabeza real y API que la utiliza. No borres datos para lograr una migración limpia.
- Revisa la dependencia de sesión que confirma AppError: documento, movimientos y auditoría de éxito deben revertirse conjuntamente ante fallos de negocio y excepciones inesperadas. No cambies globalmente esa dependencia sin analizar sus consumidores.
- Autoriza también los reintentos idempotentes; misma empresa/acción/clave y cuerpo devuelve el mismo resultado, cuerpo diferente produce conflicto. Bloquea saldos/HUs y documento en orden estable. Evita referencias cruzadas de empresa mediante restricciones y validaciones.
- La revisión completa de navegador se realiza al cerrar B08 con el checklist conservado en prompt-luna-bloque-09-aceptacion.md. Registra aquí los pasos manuales pendientes y cualquier bloqueo técnico real; la postergación visual no permite dejar fallos de stock o seguridad conocidos.

## Aceptación

- B03-A1: preparación/cancelación no altera existencias; despacho de 10 mueve 10 de central a vehículo una sola vez, sin cambio del promedio/valor de empresa.
- B03-A2: recibir 8 deja 2 en vehículo; recibir luego 2 cierra recibido. Repetir cualquiera de los comandos no duplica; sobre-recepción se rechaza.
- B03-A3: otro cuerpo con misma clave da conflicto; dos despachos distintos compitiendo por una HU no consumen de más; orden de bloqueos evita deadlocks no gestionados.
- B03-A4: fallo en segunda línea revierte documento, primera línea, saldos, valoración y auditoría de éxito. Verificar AppError y fallo inesperado con PostgreSQL.
- B03-A5: incidencia conserva cantidades hasta resolución documentada; cancelar después de despachar no devuelve stock automáticamente. No desactivar vehículo con stock en tránsito.
- B03-A6: acceso entre empresas denegado; sucursal receptora recibe su documento sin acceso a otros; costo global permanece protegido. Central, tránsito y sucursales suman el mismo total.
- B03-A7: nuevos movimientos conservan detalle canónico y consultas por etiqueta; histórico y QR anteriores siguen resolviendo cuando existe origen verificable. Migración preserva contenido inmutable y saldos. Almacén técnico no aparece como destino comercial ordinario, pero sí en conciliación.
- B03-A8: consumidores antiguos mantienen un camino documentado sin doble contabilización. Crear/consultar preparación no divide HUs; vínculos de demanda conservan origen y pendiente. Dos recepciones concurrentes no superan el saldo en tránsito y una repetición no duplica la entrada.

Publica contratos API y transiciones, migraciones y mapa de datos legados; crea entrega-bloque-03.md y actualiza E06/E07/E12/E13. B04 debe poder consumir el API sin volver a decidir el modelo de estados. No implementar las pantallas completas en este bloque.

Guarda evidencia fechada en tmp/ers-v1/bloque-03 y actualiza docs/api.md, docs/database-schema.md y documentación RBAC cuando corresponda. La entrega debe enumerar A1–A8 con comando/resultado real, cambios y límites, compatibilidad temporal y pendientes concretos para B04/B05/cierre B08. No inicies B04 automáticamente ni declares aprobada la aceptación integrada.

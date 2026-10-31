# Prompt para Luna — Inventario, bloque 3

## Encargo

Trabaja en `C:\Developer\GESTIONASV_ERP`. Implementa el **bloque 3 de la ampliación de Inventario: Kardex operativo y valorado, conciliación y cierre de integración**. El usuario autorizó la política de inventario/valoración; conserva sus decisiones. Entrega código y pruebas, no únicamente un plan. Este bloque no es el antiguo bloque 3 de Compras.

Primero lee:

- `C:\Developer\GESTIONASV_ERP\.agents\AGENTS.md` y las instrucciones aplicables por directorio.
- `C:\Developer\GESTIONASV_ERP\.agents\skills\feature-development\SKILL.md`.
- `C:\Developer\GESTIONASV_ERP\docs\inventario-valoracion-bloque-1.md`.
- `C:\Developer\GESTIONASV_ERP\docs\inventario-bloque-2-lotes-etiquetas-colocacion.md`.
- `C:\Developer\GESTIONASV_ERP\docs\revision-inventario-bloque-2-y-alcance-bloque-3.md`.
- `C:\Developer\GESTIONASV_ERP\docs\prompt-luna-cierre-inventario-bloque-2.md`, como contrato previo de aceptación.

Aplica el skill de calidad frontend cuando implementes la interfaz. Reutiliza componentes y patrones existentes. El repositorio tiene muchos cambios y archivos sin seguimiento: consérvalos; no hagas reset/clean, commits ni publicación sin encargo. No crees otro motor de costos ni reescribas módulos enteros. Para este bloque se requieren pruebas automatizadas y validación integrada.

## Estado de partida y orden

El bloque 1 contiene promedio por empresa/artículo, corte inicial documentado, entradas provisionales, aplicación idempotente del retaceo y reglas base de devolución. El bloque 2 agrega lotes, etiquetas/QR, confirmación física y ubicación agrupada. La cabeza documentada es `0083`: comprueba la cabeza real antes de cualquier migración. Las 85 pruebas backend y 406 frontend son evidencia anterior, no aceptación PostgreSQL.

Construye en tres pasos: **A. cerrar defectos → B. Kardex y conciliación → C. validar y documentar**. Revisa el código actual antes de corregir un hallazgo, por si cambió desde el informe. Si la infraestructura de base falla, continúa con el código y las comprobaciones independientes, dejando explícita la validación pendiente.

## A. Cerrar los hallazgos del bloque 2

### A1. Fraccionamiento y etiqueta vigente — R1

Revisa `inventory_repository.py`: el traslado genérico parcial admite destino disponible y valida la unidad original antes de crear la hija. No basta con que el panel agrupado mande cuarentena.

- Una hija con medidas estimadas y sin confirmación propia no puede quedar disponible. Rechaza explícitamente ese destino o exige un comando a cuarentena; no cambies silenciosamente el estado que confirma el usuario.
- La hija conserva lote y detalle de compra, tiene código propio y no hereda confirmación. El remanente cambia de revisión/cantidad y la impresión anterior ya no es válida para confirmarlo.
- El remanente de una unidad previamente disponible no puede seguir despachándose como si su etiqueta/medidas siguieran vigentes. Mantén coherencia entre estado de HU y saldos: cualquier paso a cuarentena debe ser un movimiento transaccional trazable, nunca solo cambiar un campo. Si se bloquea la operación hasta revalidar, ofrece un recorrido utilizable para completar esa revalidación.
- Aplica los requisitos de etiqueta a `label_confirmation_required`; no inventes confirmaciones ni conviertas el histórico en recepción nueva.
- Agrega regresión del endpoint genérico y del grupo: 10 unidades confirmadas → dividir 4 y 6; ninguna fracción usa la confirmación de 10. Luego mide, imprime/confirma y libera; cantidad y valor totales se conservan.

### A2. Autorización también en reintentos — R2

Revisa `inventory_putaway_groups.py`: el replay ocurre antes de validar sucursal.

- Autoriza empresa y alcance de las bodegas persistidas del movimiento antes de devolver el resultado guardado. La clave de idempotencia no es autorización.
- Separa esa autorización de la validación física de una operación nueva: no exijas que una unidad de un replay siga en la ubicación de recepción.
- Misma clave/cuerpo y usuario autorizado: mismo resultado, sin repetir movimientos ni auditorías de escritura. Misma clave/otro cuerpo: conflicto. Usuario de otra sucursal o acceso revocado: denegar sin revelar el grupo.
- Conserva orden consistente de bloqueos de empresa, ámbitos físicos y unidades. No resuelvas interbloqueos añadiendo reintentos sin corregir su causa.

### A3. Ubicación previa sin falsa disponibilidad — R3

- Una unidad completa que aún necesita etiqueta debe poder ubicarse permaneciendo en cuarentena, igual que una fracción. Usa una regla coherente de elegibilidad; no dupliques condiciones divergentes en UI, grupo y movimiento individual.
- La interfaz debe indicar si falta medir, confirmar etiqueta o aplicar el retaceo exigible y ofrecer acceso a la acción existente. Ubicar no aplica costos ni confirma etiquetas automáticamente.
- Capacidad insuficiente, permisos, exceso de cantidad o destino inválido siguen siendo errores y revierten el grupo completo.

### A4. Confirmación y migración

- Añade pruebas reales del repositorio `confirm_handling_unit_label`: impresión inexistente/ajena, revisión o cantidad obsoleta, misma clave y contenido, clave reutilizada con otro contenido, confirmación ya existente y fraccionamiento.
- Probar ausencia de confirmación, cancelar impresión, reimprimir y confirmar expresamente; `afterprint` nunca prueba colocación física.
- Valida `0083` y su convivencia con `0079`–`0082` sobre PostgreSQL. Si debes cambiar esquema, crea revisión nueva desde la cabeza real; no edites una migración previa suponiendo que nadie la aplicó.

## B. Kardex real sobre las fuentes existentes

### B1. Arquitectura y fuentes

El menú Kardex apunta a un placeholder. Implementa `/inventory/kardex` y conecta la navegación con permisos. Conserva `/inventory/valuation` para apertura y consulta actual; ofrece enlaces entre ambas pantallas sin duplicar configuración.

Reutiliza y extiende contratos existentes cuando sirvan:

- `inventory_movements`, `inventory_movement_lines`, balances y HU: hechos físicos.
- `inventory_valuation_entries`, `inventory_cost_averages` y ajustes aplicados: hechos de valor.
- `list_movements`, DTO `InventoryMovementHistoryOut`, `SqlAlchemyInventoryValuationRepository.ledger` y API de valoración.
- Componentes de detalle de movimientos y formateadores decimales ya disponibles.

La consulta nueva debe seguir las capas del proyecto, con DTO explícito, filtros en servidor, paginación limitada y orden determinista. No copies toda la valoración dentro del router, no hagas un motor de costo en TypeScript y no reconstruyas números usando textos de `source_reference` cuando existe una relación persistida. Agrega índices solo cuando la consulta lo justifique.

### B2. Dos vistas con alcance explícito

**Movimientos físicos:** requiere `inventory:read` y acceso a la bodega/sucursal. Filtros por producto/variante, bodega autorizada, período, tipo y lote cuando aplique. El servidor valida el alcance de filtros, detalle, conteos y respuesta; no basta ocultar opciones. Un usuario de sucursal no debe obtener datos privados de otras bodegas ni costos globales.

Mostrar fecha/hora, documento/tipo, producto y unidad base, lote/HU, origen/destino autorizados, entrada, salida y saldo de cantidad del ámbito consultado. En un traslado interno, cada bodega muestra su efecto; a nivel empresa la cantidad neta es cero. Un cambio de ubicación/estado dentro de una bodega no aumenta ni reduce la existencia total. Si se presenta a nivel ubicación/estado, identificar expresamente ese alcance. No sumar unidades de productos incompatibles en una tarjeta total.

**Valoración de empresa:** exige `inventory:valuation` y alcance de todas sus sucursales, como el contrato actual. Seleccionar empresa/producto y período; el promedio es compartido entre sus bodegas. No mostrar un promedio separado por bodega, lote ni sucursal. Los filtros de bodega/lote de la vista física no recortan silenciosamente el cálculo global.

Mostrar moneda configurada, fecha operativa y contable ya registradas, tipo/documento, entrada/salida de cantidad, variación de valor, saldo de cantidad/valor y costo promedio registrado. Los ajustes de costo tienen cantidad física cero. Un crédito de proveedor se presenta separado del costo de salida; no reduce stock otra vez. El retaceo tardío conserva el movimiento original y muestra su ajuste/desglose posterior; no reescribas filas antiguas ni atribuyas a ellas el promedio actual.

### B3. Fechas, paginación y origen

- Saldo anterior al período, entradas/salidas del período y saldo final deben tener el mismo producto y alcance. La página 2 continúa el saldo; no empieza en cero. Los totales representan todo el filtro, no solo la página visible.
- Vista física: período sobre fecha del movimiento, límites diarios en `America/El_Salvador`. Vista valorada: período sobre fecha contable, mostrando también fecha operativa. Usa límites coherentes y orden por secuencia persistida en valoración; para hechos físicos, fecha y desempate persistido.
- No inventes un saldo histórico cero si faltan movimientos/corte para reconstruirlo. Expón la limitación, mantén la consulta disponible y distingue saldo previo reconstruido de corte aprobado. No inventes costo para movimientos anteriores a la apertura.
- Unir eventos físicos y financieros no puede multiplicar cantidades por los ajustes de retaceo. Usa vistas separadas/enlaces cuando la relación sea uno a varios.
- Permite abrir movimiento, recepción, retaceo o ficha de HU mediante identificadores existentes y permisos del destino. No generes una URL ficticia ni muestres una acción hacia documentos ajenos. El Kardex autenticado no amplía los datos de la ficha QR pública.
- Tabla y filtros: español claro, tema claro/oscuro, carga/vacío/error, accesibilidad y respuesta adaptable. Los errores ofrecen reintento; consultas antiguas no sobrescriben filtros nuevos. Evita un componente monolítico.

### B4. Conciliación de lectura

Para el perfil con valoración global, mostrar por artículo la cantidad física de la empresa y la cantidad valorada, su diferencia, el valor y el promedio registrados. Usar una fotografía consistente; no comparar lecturas tomadas a ambos lados de una recepción concurrente.

Cuenta cada existencia una sola vez: disponible, cuarentena, bloqueada, dañada y tránsito perteneciente a la empresa según el modelo actual. No sumes balances y HU entre sí. El traslado conserva el total de empresa; el retaceo conserva cantidades. Si la valoración no está activada, indicar ese estado y permitir consulta física; no marcar diferencias falsas ni aprobar el corte automáticamente.

Una diferencia se informa con acceso al historial. No agregues un botón que arregle saldos ni generes movimientos automáticos para hacer coincidir los números.

## C. Pruebas de aceptación y cierre

### Casos mínimos

1. R1–R3 y confirmación de etiquetas, tanto API como UI donde corresponda.
2. Misma empresa: dos bodegas, recepción aceptada en cuarentena → retaceo requerido → ubicación → etiqueta confirmada → disponible → traslado. Sin duplicar entrada ni modificar el valor por traslado/ubicación.
3. Otra empresa y dos usuarios con distinto alcance de sucursal: autorización en consultas, detalles, replays y escritura. Usuario sin valoración no recibe importes ocultos en JSON.
4. Lote con dos líneas de compra del mismo artículo de 20 y 30: ubicar 50 conservando origen; rechazar 51. Fallo en la segunda asignación revierte todo, incluida auditoría de éxito.
5. Valoración: recibir 10 a $10 y 10 a $20, salida de 15, devolución al proveedor de 5 y crédito de $100 → cantidad 0, valor 0, salida valorada $75 y diferencia $25. Usar las API/motor existentes; no requiere construir pantallas completas de devolución.
6. Retaceo tardío: recibir 10 por $100, salida 6, costo adicional $20 → $8 al remanente y $12 a salidas. Aplicación repetida no duplica ajustes. Kardex muestra originales y ajuste con cantidad cero.
7. Filtros y paginación: registros anteriores al período, más de una página, empate de fecha, cambio de filtro, movimiento interno y stock previo al corte. Saldos/totales estables, sin sumar productos de distintas unidades ni inventar valores históricos.
8. PostgreSQL real: dos sesiones simultáneas sobre grupo/movimiento/medición y reintentos. Comprobar finalización sin deadlock, integridad de cantidades, idempotencia, rollback y ausencia de doble aplicación. Usar sincronización explícita y tiempos límite, no una carrera basada solo en `sleep`.
9. Históricos migrados no quedan falsamente confirmados; recepciones nuevas exigen la confirmación. Ficha QR limitada, sin sesión, revocable; lectura física se documenta por separado.

### Entorno y ejecución

- Backend requiere Python `>=3.12,<3.13`; usa entorno aislado y dependencias del proyecto. Frontend: ejecutar Vitest desde `frontend`, excluyendo `.pnpm-store/**`, y luego comprobaciones Svelte/build/lint sobre lo cambiado.
- Inspecciona el entorno disponible; la entrega anterior registró WSL `E_UNEXPECTED` y Docker sin daemon. No des por hecho que sigue igual ni reinicies/destruyas entornos del usuario para probar.
- **Usa un servidor PostgreSQL desechable y `erp_db_test` dedicado.** `backend/tests/conftest.py` reconstruye el esquema y siembra cuando recoge integración/E2E. Verifica host/puerto/nombre de destino antes de ejecutarlo; no basta cambiar una variable apuntando al servidor operativo. No imprimas credenciales ni uses la base del usuario.
- Comprobar `alembic heads`, migración real y `alembic current` en esa base, incluyendo paso de histórico `0082` a `0083` con datos ficticios. Si añades revisión, incluirla. No intentar un downgrade destructivo para validar historia financiera.
- Ejecuta primero regresiones de los defectos, luego integración y las suites relacionadas de valoración, recepción, retaceo, lotes/etiquetas/QR e interfaz. Guarda comandos, resultados, duración y límites reales. Una prueba omitida por infraestructura no cuenta como aprobada.
- En navegador, recorrer el caso con datos ficticios y perfiles autorizados, incluidos acceso directo/recarga, cambio de filtros y ambas vistas. No realizar recepciones, retaceos ni cortes sobre datos operativos. No afirmar lectura de impresora/HS-200 sin prueba física del usuario.

## Fuera de alcance

No construir libro mayor, períodos contables, retroactividad, conversión de moneda, deterioro, aprobación avanzada del inventario inicial, ventas completas, pantallas completas de devoluciones ni reversión financiera general. No cambiar la política de costos ni el diseño de permisos globales para conseguir que pase una prueba. No contactar proveedores ni publicar cambios.

## Entrega

1. Código funcional y regresiones para A–C.
2. `C:\Developer\GESTIONASV_ERP\docs\inventario-bloque-3-kardex-conciliacion.md`: recorrido, contratos/permisos, decisiones, migraciones, comandos y resultados, pendientes concretos.
3. Actualizar estados de bloques 1/2 y este informe sin borrar la evidencia histórica ni presentar pruebas anteriores como ejecutadas ahora.
4. Resumen al usuario con dónde usarlo, qué quedó corregido, qué se probó y qué sigue pendiente. Solo declarar aceptación completa cuando existan pruebas de PostgreSQL y recorrido funcional; distinguir trabajo construido de aceptación y de comprobación física del lector.

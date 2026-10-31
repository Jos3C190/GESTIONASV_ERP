# Presentaciones de las harinas y recuperación de la verificación

Fecha: 21/10/2026, America/El_Salvador.

## Solicitud y causa

El usuario solicitó preparar las presentaciones de los productos de su recorrido ficticio para evitar el bloqueo al demostrar la recepción. COM-00021, de OC-00019, contiene dos harinas compradas por kilogramo cuya identidad de inventario ya tenía **Caja** como unidad base. Ninguna tenía una equivalencia vigente para kilogramo. La presentación UNI-01 del producto DEMO-MANUAL-2110 no configura otros productos.

La orden y la compra estaban en `received`. La compra no tenía movimiento de inventario. El bloqueo correspondía a configuración de presentaciones, no a una nueva recepción ni a duplicación de existencias.

## Configuración aplicada a la empresa de demostración

Se conservó la unidad base histórica. Para esta demo, una Caja base representa un saco con el peso indicado en el nombre del producto. Es una convención ficticia documentada; no certifica cómo estaban empacados movimientos anteriores.

| Producto | Presentación nueva | Unidad de compra | Equivalencia por kg | Resultado para los 100 kg recibidos |
| --- | --- | --- | --- | --- |
| PRD-HAR-003 — Harina Integral de Trigo 25kg | KG-HAR-003 | Kilogramo | 0.040000 cajas base | 4.000000 cajas base |
| PRD-HAR-001 — Harina de Trigo Suave 50lb | KG-HAR-001 | Kilogramo | 0.044092 cajas base | 4.409200 cajas base |

50 lb corresponden a 22.6796185 kg; su inversa no cabe exactamente en los seis decimales del campo de equivalencia. Se almacenó **0.044092**, redondeado para esta demo. Las conversiones futuras usan ese factor persistido. No debe presentarse como una conversión exacta de precisión ilimitada.

Ambas presentaciones son de tipo **Otro / a granel**, correspondientes a **un kilogramo comprado**: peso bruto ficticio de **1 kg**, volumen ficticio de **0.002 m³**, sin dimensiones exteriores declaradas y no apilables. Estas medidas no representan el saco completo de 25 kg o 50 lb. PRD-EMP-010 mantiene BOLSA-12 y su conversión existente Caja→Caja = 1.

Se utilizó `PackagingCreate`, `InventoryUseCases.create_packaging` y el repositorio normal, con auditoría obligatoria en la misma transacción. Las entradas de auditoría tienen origen `user_authorized_demo_maintenance`, sin atribuir la ejecución a una sesión de usuario autenticada. El comando se limita a la empresa, la recepción y los dos SKU indicados; por defecto revierte la simulación y requiere `--apply` para persistir. Si encuentra una equivalencia diferente, se detiene sin sobrescribirla.

Comando reproducible: `docker exec gestionasv_erp-backend-1 python -m seed.configure_demo_flour_presentations`. Para futuras ediciones desde la aplicación usar **Nueva versión**, conservando el historial de la presentación anterior.

## Correcciones del flujo

- Los avisos del servidor identifican nombre y SKU dentro de la empresa de la compra. Conservan sus códigos de error y el rechazo de conversiones ausentes, ambiguas o no representables.
- La guía conduce a **Productos → Empaques y presentaciones de inventario**, en lugar de la entrada de menú Inventario que todavía es una pantalla pendiente.
- Ante estos errores, la verificación ofrece enlaces a los productos aceptados en otra pestaña y conserva cantidades y destinos.
- El botón permite **Volver a intentar la verificación** tras guardar la configuración. El formulario ya no queda bloqueado por conservar el mensaje del intento anterior.
- El detalle del producto tiene un destino `#presentaciones-inventario`, con desplazamiento tras cargar los datos.

## Evidencia

Archivos bajo `tmp/ers-v1/2026-10-21-presentaciones-harinas/`:

| Caso | Resultado | Evidencia |
| --- | --- | --- |
| Simular configuración y conversiones | Aprobado, cambios revertidos | `configuracion-simulacion-final.log/.exit` |
| Guardar presentaciones y auditoría | Aprobado, solo configuración | `configuracion-aplicada.log/.exit` |
| Ejecutar otra vez | Aprobado: dos resultados UNCHANGED, sin duplicar presentaciones | `configuracion-idempotente.log/.exit` |
| Comparar todas las filas de inventario y compras de la empresa antes/después | Iguales en 13 tablas, incluidos los productos protegidos | Huellas en `configuracion-aplicada.log` |
| Verificar COM-00021 con sus tres líneas y ubicaciones reales, mediante el caso de uso completo | Aprobado dentro de transacción: `verified`, con movimiento temporal; rollback comprobado | `verificar-recepcion-con-rollback.py`, `verificacion-con-rollback.log/.exit` |
| Comprobar persistencia después del rollback | COM-00021 sigue `received`, movimiento nulo, huellas iguales; dos auditorías de configuración persistidas | `verificacion-con-rollback.log` |
| Pruebas de frontera de compras/inventario | 7 aprobadas | `backend-final.log/.exit` |
| Formulario de verificación y detalle de compra | 7 aprobadas: división, configuración y reintento con el mismo contenido | `frontend-final.log/.exit` |
| Ruff y ESLint focalizados | Aprobados | `ruff-final.log/.exit`, `lint-final.log/.exit` |
| Comprobación de Svelte/TypeScript tras el último cambio | 0 errores, 8 advertencias en un archivo | `svelte-check-final.log/.exit` |
| Formato de los archivos de interfaz | Aprobado | `formato.log/.exit` |

Las ejecuciones iniciales fallidas también se conservan: una prueba nueva construía PhysicalMeasures sin sus tres dimensiones opcionales explícitas, el primer cálculo de huellas asumía una columna id que no existe en la tabla de promedios, el primer test de reintento intentaba activar el submit nativo del entorno de componentes, y Ruff pidió ordenar importaciones y dividir el auxiliar de mantenimiento. Se corrigieron los auxiliares de prueba/comprobación; no se consideran evidencia aprobada esos primeros logs.

## Continuación manual y alcance

En COM-00021, conservar **100 kg, 100 kg y 125 cajas** como cantidades aceptadas y sus destinos. Las equivalencias se aplican al registrar inventario: no introducir 4 o 4.4092 en los campos de cantidades aceptadas de la compra. Mantener el formulario abierto para reintentar; si se recarga, volver a asignar los destinos cuando sea necesario. Después pulsar **Verificar y registrar en inventario** y revisar el lote y las unidades en cuarentena.

La simulación no se guardó como operación del usuario. El ingreso definitivo desde su navegador, la revisión física, etiqueta y liberación siguen siendo pasos manuales del recorrido. No se obtuvo nueva evidencia visual en navegador en esta corrección; la evidencia de interfaz es de componentes. La aceptación global B01–B08 conserva sus pendientes documentados.

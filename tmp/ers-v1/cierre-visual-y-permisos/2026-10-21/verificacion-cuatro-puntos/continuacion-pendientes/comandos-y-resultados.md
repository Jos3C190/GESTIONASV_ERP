# Comandos y resultados — continuación 21/10/2026

No hubo cambios de backend/frontend ni escrituras de inventario en esta continuación. Las lecturas SQL validan el DSN de la clon y aplican `SET TRANSACTION READ ONLY`. Las copias temporales de scripts se retiraron del contenedor al terminar.

| Acción | Resultado | Evidencia |
| --- | --- | --- |
| Conciliación antes de continuar | Exit 0. Cuatro SKU coinciden en clon y demo: 4/40 USD, 5/60 USD, 12/160 USD, 0/0 USD. | `reconciliation-before.log` |
| Descubrimiento de alias, variante inicial | Exit 1 por pedir `inventory_movements.reference_type/reference_id`, columnas ausentes del modelo vigente. La consulta fue `READ ONLY`; no cambió datos. | El intento no se conserva como resultado exitoso; la causa queda descrita en `informe-continuacion.md`. |
| Descubrimiento de alias, consulta corregida | Exit 0. Tres pares cabecera/detalle con cantidad/HUs abiertas; cero registros que coincidieran con el predicado de literal divergente o FK detalle ausente; 24 HUs sin lote de recepción enlazado. | `v03-alias-discovery.log`, código en `readonly-v03-alias-discovery.py` |
| Conciliación después de la consulta corregida | Exit 0. Misma cantidad y valor protegido en ambas bases; ajuste correctivo, valoración y devolución mixta persistidos sin cambios. | `reconciliation-after.log` |
| Carga/descarga documental por API | El login de `superadmin` al API aislado devolvió HTTP 401; se detuvo antes de crear un documento y no se probaron más credenciales. | Fallo de autenticación previo a mutación; detalle en `informe-continuacion.md`. |
| Adaptador real de RustFS | Exit 0. Un objeto ficticio de 90 bytes se subió, consultó con HEAD y descargó con SHA-256 idéntico; después se pidió eliminar la misma clave. No se usó el endpoint de documentos ni se alteró la DB. | `real-storage-adapter-roundtrip.py`, `real-storage-adapter-roundtrip.log`, código de retorno en `.exit`. |
| Lectura de interfaz `localhost:5174/inventory/trace` | La herramienta de navegador rechazó `cua.getTab` por su política de seguridad de URL. Se detuvo la inspección de UI; no se intentó otro canal para acceder a esa misma sesión. | Impedimento registrado en `informe-continuacion.md`; `capturas/` permanece vacía. |
| Suite nueva | No ejecutada: no hubo cambio de código ni defecto de producto reproducido; los casos de UI pendientes no se pueden sustituir con una suite que ya está documentada. | Dictamen en `informe-continuacion.md`. |

No se registran credenciales, tokens QR ni URL firmadas. La conciliación permite afirmar que no se alteraron los cuatro SKU protegidos durante esta continuación.

# Encargo para Luna — completar verificaciones pendientes B01–B08

Preparado el 21/10/2026, America/El_Salvador.

## Objetivo

Continúa y termina los casos abiertos del encargo `docs/ers-v1/prompt-luna-verificacion-final-cuatro-puntos-b01-b08.md`: **V01, V02, V03 y V04-04**. Ejecuta las comprobaciones pendientes, corrige los defectos que reproduzcas y documenta la comprobación posterior. Entrega resultados ejecutados, no otro prompt ni solamente un resumen de lo que falta.

El alcance y los criterios son los del encargo original. Este documento concreta la continuación; no agrega módulos ni variantes ilimitadas. B09 sigue integrado en el cierre B08. No se requieren impresora, lector ni etiquetas físicas.

## Lectura mínima

Trabaja en `C:/Developer/GESTIONASV_ERP`. Lee:

1. `.agents/AGENTS.md` y los skills aplicables a la tarea real. Usa `feature-development` si corriges funcionalidad; aplica `frontend-quality-studio` si modificas o auditas una UI.
2. El encargo original citado arriba y `docs/ers-v1/revision-astra-verificacion-final-cuatro-puntos-2026-10-21.md`.
3. `docs/ers-v1/cierre-visual-y-permisos-b01-b08.md`, apartado vigente y pendientes exactos.
4. `tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/`: `informe-final.md`, `registro-casos.md`, `matriz-permisos.md`, `manifiesto-capturas.md`, `conciliacion-final.md`, `comandos-y-resultados-finales.md` y los logs del caso que continúes.
5. `tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/alias-trazabilidad.md` y las pruebas/contratos del caso pendiente.

## Conservación y entorno

V04-01, V04-02 y V04-03 ya tienen evidencia coherente: ajuste correctivo, traslado 8+2 y devolución mixta. Conserva sus documentos y logs. No repitas sus escrituras para obtener capturas; consulta los estados persistidos. Tampoco vuelvas a ejecutar suites completas sin un cambio o fallo que lo justifique.

Los SKU protegidos deben permanecer así en la demostración y en la copia usada para verificar:

| SKU | Físico = valorado | Valor USD |
| --- | ---: | ---: |
| ERS-REVIEW-DD6BBF85 | 12 | 160 |
| ERS-INC-EE8FE228 | 4 | 40 |
| ERS-LATE-B1B55D6D | 5 | 60 |
| ERS-UI-F767BABC | 0 | 0 |

Consulta y guarda antes/después en transacción de solo lectura. No alteres estos artículos, el corte inicial ni permisos de usuarios reales. Usa datos/actores ficticios identificados con `ERS-FINAL-4P`.

La referencia de prueba anterior fue frontend `5174`, API `8001`/contenedor `erp-final4p-api`, DB `erp_db_ers_final4p_20261020`, Alembic `0090`. La demostración habitual usó `5173/8000` y `erp_db`. Verifica ahora las conexiones efectivas antes de escribir; no asumas que siguen iguales. Reutiliza la copia aislada si está operativa. No cambies la conexión de la app habitual ni muevas/renombres directorios usados por un servidor activo.

Antes de usar pytest con base, inspecciona la guarda de `backend/tests/conftest.py`: integración/E2E reconstruyen `erp_db_test`, se ejecutan en serie y nunca sobre la demo ni sobre la copia estable usada por el navegador. No hagas reset/clean ni siembras destructivas. Los recursos de almacenamiento pueden estar compartidos aunque la DB esté clonada: usa archivos ficticios propios, conserva objetos ajenos y registra/restaura cualquier configuración temporal que afectes.

## 1. Completar V01 — permisos y documentos

Resuelve V01-01 a V01-04. El TSV de 304 declaraciones es un insumo estático; no demuestra autorización. Limita el inventario a capacidades B01–B08 y adjuntos enlazados. No conviertas endpoints ajenos en requisitos nuevos.

Completa una fila por acción/ruta aplicable con método, permiso efectivo, guarda de servicio si existe, regla empresa/sucursal/origen, control UI, perfil/contexto, esperado, observado y evidencia exacta. Puedes agrupar rutas únicamente si comparten la misma guarda y alcance, enumerando las representadas. Reutiliza los casos previos válidos; ejecuta los huecos.

Con actores ficticios cubre los contextos aplicables del encargo original: permiso ausente, lector sin costos, operador autorizado, responsable de empresa, recurso ajeno y nueva petición/replay después de perder alcance. Comprueba la UI y la petición directa al servidor; superadmin no acredita denegaciones.

Para cada familia documental implementada pendiente, identifica las operaciones reales y prueba el flujo permitido y las denegaciones aplicables: iniciar/subir/completar, listar/ver, emitir enlace/descargar, retirar y nueva autorización tras cambio de alcance. Comprueba archivo inocuo real descargado con igualdad de bytes o SHA256, vínculo al origen y aislamiento. Un stub de URL no acredita descarga. No guardes URLs firmadas, tokens ni credenciales. Mantén la política actual: retirar permisos impide nuevas emisiones; no se exige revocar anticipadamente una URL firmada ya emitida.

Si una operación no existe en el contrato, documenta `NO APLICA` con la referencia concreta. Si el almacenamiento impide descargar, registra servicio/configuración, petición y fallo concreto; no lo clasifiques automáticamente como defecto RBAC.

## 2. Completar V04-04 — respuesta perdida tras persistir

No repitas V04-01/02/03. Prepara comandos ficticios nuevos para la recuperación: ajuste y flujo comercial si sus mecanismos difieren.

Inspecciona las capacidades documentadas de la sesión actual. Usa un mecanismo autorizado que permita perder la respuesta **después** de que el servidor haya persistido. El proxy anterior no fue ejecutado y no constituye evidencia. Si una herramienta rechaza una acción por seguridad, respeta ese rechazo y no pruebes variaciones para eludirlo; registra el resultado y continúa los casos independientes.

Para cada mecanismo realmente distinto:

1. Ejecuta la acción por UI y descarta la respuesta posterior a la persistencia.
2. Confirma mediante consulta del documento/ledger que el servidor sí guardó antes de reintentar.
3. Recarga y reintenta con la misma clave idempotente y cuerpo conforme al contrato.
4. Comprueba un documento/efecto físico/valorado y auditoría coherente, sin duplicación.

Guarda cómo provocaste el fallo, IDs/tiempos, consultas de comprobación y resultados. Un fallo antes de enviar, un mock de componente o la mera existencia de una clave no sustituye el caso. No debilites controles del producto para facilitar la prueba.

## 3. Completar V03 — recepción, alias y acceso privado

Continúa V03-02, V03-03 y V03-05. Conserva las comprobaciones ya documentadas de ficha/QR y abrir/cancelar división.

- Verifica el contrato real de compra/recepción. La validación de SKU repetido en una solicitud no demuestra por sí sola una prohibición equivalente en la compra. Ejecuta desde UI el caso legítimo de varias líneas del mismo producto o, si ese contrato lo prohíbe, su equivalente permitido de recepciones parciales del mismo SKU. Cita la restricción sin eliminarla.
- Recibe, reabre y recarga; comprueba producto, presentación/unidad, cantidades, cabecera, detalle canónico y origen por recepción. No insertes stock directamente para sustituir el recorrido.
- Recorre la lista finita de `alias-trazabilidad.md`: cabecera, detalle canónico, literal histórico y resolución histórica sin FK donde existan y el contrato lo admita. Guarda por alias el valor consultado, ruta, identidad resuelta y evidencia. Para un tipo sin dato aplicable registra la consulta y el motivo; usa una fixture histórica aislada si es viable, sin fabricar historia en la demo ni exigir otra migración.
- Comprueba la consulta privada de recurso ajeno con perfil restringido y la denegación efectiva. Conserva la política pública QR ya verificada; no amplíes datos públicos para completar el caso.

Solo una división confirmada puede crear otra HU. Abrir/cerrar/cancelar, revisar etiqueta o consultar QR no debe dividir ni alterar stock. Conserva la disponibilidad final y la demanda/destino contextual existentes.

## 4. Completar V02 — archivos de evidencia visual

Obtén capturas durante los recorridos anteriores y mediante lectura de casos ya persistidos. Inspecciona primero las herramientas documentadas actuales; no supongas vigente ni resuelta la limitación de exportación anterior. Usa exclusivamente capacidades permitidas y no inventes APIs de captura.

Archiva la muestra original de siete familias: matriz/bodega; recepción/lotes/medidas/etiqueta; demanda/traslados/incidencias; ajustes/correcciones/adjuntos; clientes/cotización/venta; entregas/devoluciones; Kardex/conciliación. Por familia: escritorio y móvil 390×844, claro y oscuro, hasta 28 capturas base. Reutiliza imágenes válidas de la misma versión/ruta/estado cuando existan. No exijas cuatro capturas por rol/endpoint.

El manifiesto debe identificar caso, archivo real, ruta, tema, tamaño, perfil, estado y fecha. Una nota o árbol accesible no es PNG. Conserva la observación móvil previa de Devoluciones; su hueco señalado era el archivo. Comprueba los controles finitos de teclado/foco, desbordamiento y estados del encargo original, sin rediseñar pantallas aprobadas por preferencia estética.

## Evidencia, correcciones y cierre

Guarda esta continuación en `tmp/ers-v1/cierre-visual-y-permisos/AAAA-MM-DD/verificacion-cuatro-puntos/continuacion-pendientes/` (subdirectorio distinto si ya existe). Conserva las pasadas anteriores y los directorios del entorno de ejecución.

Entrega registro actualizado por ID original, matriz de permisos, manifiesto/capturas, comandos con salida y código de retorno, conciliación antes/después e informe. Para cada caso usa `APROBADO`, `NO APLICA` justificado o `ABIERTO`. Distingue operación UI, API, prueba automatizada, lectura SQL y revisión documental. No presentes esta última como nueva ejecución del producto.

Corrige únicamente defectos reproducidos dentro del alcance. Guarda causa, cambio, evidencia anterior/posterior y regresión apropiada. Si modificas frontend realiza tipos/lint/build y pruebas focalizadas necesarias; si modificas backend ejecuta los casos afectados. Conserva las suites aprobadas y no sumes reejecuciones como cobertura nueva.

Actualiza el cierre principal E01–E15, revisión, entrega B08, seguimiento, preparación, guía y manual con un único estado vigente al inicio y cortes anteriores históricos. Enlaza los resultados nuevos sin duplicar conclusiones contradictorias. Restaura la configuración temporal y deja operativa la demostración.

No uses «faltó revisar» o «faltó tiempo» como impedimento externo. Si un caso queda abierto, registra el intento exacto, resultado/error, recurso o capacidad faltante y siguiente acción concreta; completa mientras tanto todos los casos independientes que sí puedas ejecutar. No declares ausentes defectos en partes que no comprobaste.

Cuando V01–V04 y conciliación estén realmente aprobados, declara: **«Alcance B01–B08 cerrado para implementación y verificación; pendiente únicamente demostración del usuario y evaluación académica».** Si queda evidencia obligatoria abierta, conserva el cierre parcial y enumera exclusivamente los casos pendientes originales. Entrega la ejecución y su dictamen; no otro bloque ni otro prompt.

# Revisión documental del encargo final V01–V04

**Fecha:** 21/10/2026, America/El_Salvador. **Dictamen: cumplimiento parcial; encargo sin terminar.**

Se contrastó el [encargo](prompt-luna-verificacion-final-cuatro-puntos-b01-b08.md) con el informe, registro de casos, matriz de permisos, manifiesto de capturas y logs guardados. Esta revisión comprueba la coherencia de esa evidencia; no vuelve a ejecutar la aplicación, pruebas ni consultas a la base.

## Resultados respaldados

Los documentos de V04-01/02/03 concuerdan con el historial persistido:

- Ajuste: una salida de 1 L y una entrada compensatoria de 1 L; valoración 192/USD 2 → 191/USD 1.989583 → 192/USD 2. Los encabezados aplicados conservan el vínculo de corrección.
- Traslado: un despacho de 10 y dos recepciones de 8 y 2. Los movimientos son internos y no agregan un asiento de valoración global.
- Venta/devolución: dos salidas de 4; retorno aceptado de 2 vinculado al costo de la primera salida; rechazo de 1 sin movimiento ni valoración. Saldo final 2,208/USD 0.498646.
- Conservación: las ocho comparaciones numéricas de los logs (cuatro SKU por dos bases) coinciden con el baseline anterior. Es comprobación de archivos guardados, no lectura actual de las bases.

Referencias: [historial V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/transaction-history-v04.log), [conciliación](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y [log final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/reconciliation-final.log). El relato de UI acompaña estos registros; esta revisión documental no acredita por sí sola los clics ni las condiciones visuales.

## Requisitos originales sin completar

| Punto | Resultado de la revisión | Trabajo que conserva el encargo |
| --- | --- | --- |
| V01 Permisos/documentos | Incompleto. Hay 304 declaraciones estáticas de endpoint y pruebas previas puntuales; no una matriz resuelta de acciones, guardas y alcance. El informe reconoce que no agregó casos V01 en esta pasada. | Completar filas aplicables y ejecutar los huecos por perfil/empresa/sucursal, incluida denegación UI/API y descarga real de bytes documentales. No inferir cobertura por superadmin ni extender una prueba de ajustes a otros módulos. |
| V02 Evidencia visual | Incompleto. El directorio `capturas/` contiene **0 archivos**; las siete familias del manifiesto siguen abiertas. | Resolver el método permitido de exportación y guardar la muestra finita solicitada: escritorio/móvil y claro/oscuro, reutilizando evidencia vigente válida. El manifiesto relata una limitación de herramientas; esta revisión no la vuelve a reproducir. |
| V03 Recepción/trazabilidad | Incompleto. Hay ficha HU, QR público y cancelar división; falta el recorrido de recepción repetida, los alias aplicables y denegación privada ajena. | Ejecutar esos casos del registro. La prohibición de SKU repetido en una solicitud no demuestra que la compra/recepción prohíba todos los casos equivalentes; conservar el contrato y probar el recorrido legítimo. |
| V04 Recuperación | Tres subcasos respaldados; V04-04 sin ejecutar. El proxy preparado no acredita pérdida de respuesta después del commit. | Descartar controladamente una respuesta después de persistir, consultar antes del reintento y verificar efecto único/auditoría con la misma clave; ajuste y flujo comercial si sus mecanismos difieren. El rechazo del reinicio/reruteo está relatado en el registro. |

V01 y V03 describen trabajo no ejecutado; sus documentos no identifican un impedimento externo concreto que lo imposibilite. V02 y V04-04 registran limitaciones del procedimiento de herramientas utilizado. Ninguno de esos estados equivale a demostrar un fallo de producto.

## Decisión

La documentación reconoce correctamente el cierre parcial y distingue pruebas previas, operaciones realizadas y casos abiertos. Esa honestidad documental cumple la regla de no dar criterios por aprobados sin evidencia. **No cumple todavía el objetivo de terminar las cuatro verificaciones.**

Continuar el mismo encargo en V01, V02, V03 y V04-04, conservando V04-01/02/03 y los SKU protegidos. No se necesita otro bloque funcional ni ampliar requisitos. No corresponde afirmar que solo falta la demostración manual del usuario.

Estado de referencia: [informe final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md) y [registro de casos](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/registro-casos.md).

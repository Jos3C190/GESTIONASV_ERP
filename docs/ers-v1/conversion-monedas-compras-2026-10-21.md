# Conversión documentada de compras a la moneda de inventario

Fecha: 21/10/2026, America/El_Salvador.

## Solicitud y diagnóstico

El usuario confirmó que COT-00047 → OC-00022 → COM-00022 se creó intencionalmente en CRC para probar monedas. La valoración de Grupo Lorena está activa en USD. Se conservan los documentos, precios, descuentos, impuestos y gastos comerciales en CRC; su costo de inventario se convierte explícitamente a USD.

## Cambio implementado

1. La verificación consulta la moneda de valoración mediante `GET /purchases/{id}/valuation-context`. Requiere `purchases:verify` e `inventory:receive`, además del alcance de empresa y bodega de la recepción. Un fallo de consulta bloquea las cantidades aceptadas y ofrece reintento.
2. Cuando las monedas difieren y hay cantidad aceptada, pide **tipo de cambio, fecha y fuente/referencia**. No rellena una tasa automática. El significado de la tasa es **unidades de moneda de compra por una unidad de moneda de valoración**: para CRC→USD, **1 USD = tasa CRC**.
3. El servidor exige tasa positiva menor que 10¹², hasta doce decimales, fecha y referencia de 3 a 500 caracteres. Comprueba que la moneda destino coincide con la valoración activa. La moneda de compra se obtiene del documento, no de un campo editable enviado al verificar.
4. Se divide el costo provisional aceptado por esa tasa y se redondea con `Decimal`, seis decimales y `ROUND_HALF_UP`. Se convierte el total por detalle antes de distribuir entre sus unidades separadas, asignando el remanente a la última para conservar el costo. Las cantidades físicas siguen su conversión de presentación independiente.
5. La revisión guarda una copia de la conversión en `purchases.valuation_conversion`, junto con el movimiento, cantidades aceptadas y auditoría VERIFY, dentro de la transacción existente. La copia contiene moneda destino, tasa, fecha y referencia y aparece en el detalle de la compra. La cotización y orden no se reescriben.
6. El retaceo sigue documentado en la moneda de la compra y aplica su FOB y costo final convertidos mediante **la misma tasa guardada**. Su aplicación conserva moneda original, moneda de valoración y copia de la conversión en el resumen. No vuelve a consultar una tasa actual ni convierte dos veces la recepción.
7. Las compras en la misma moneda siguen el flujo previo sin conversión; una recepción totalmente rechazada no necesita tasa. Una compra sin valoración activa conserva el comportamiento anterior y no admite guardar una conversión de valoración todavía inexistente.

## Persistencia y despliegue

Migración **0091**, dependiente de 0090: añade una columna JSONB nullable a purchases y un CHECK de estructura básica, moneda, tasa positiva y referencia. El dominio y los DTO validan la precisión y el resto de campos. No rellena tasas retrospectivas ni cambia datos de documentos existentes. El modelo ORM declara la misma restricción.

Se aplicó `alembic upgrade 0091` en el backend local. [migracion.log](../../tmp/ers-v1/2026-10-21-moneda-recepcion/migracion.log), salida 0. En otro entorno debe aplicarse esa revisión antes de usar el backend actualizado.

## Evidencia de comprobación

Carpeta: `tmp/ers-v1/2026-10-21-moneda-recepcion/`.

| Caso | Resultado | Evidencia |
| --- | --- | --- |
| Diagnóstico original | COT-00047, OC-00022 y COM-00022 CRC; valoración USD; movimiento nulo | `diagnostico.log/.exit`, lectura sin cambios |
| Pruebas de servidor focalizadas | **62 aprobadas** | `backend-final.log/.exit` |
| Pruebas de verificación, detalle, acciones y cliente HTTP | **17 aprobadas** | `frontend.log/.exit` |
| Svelte/TypeScript | **0 errores, 8 advertencias en un archivo** | `svelte-check.log/.exit` |
| ESLint y Ruff de archivos afectados | Aprobados | `eslint.log/.exit`, `ruff.log/.exit` |
| Simulación de COM-00022 sin tasa | Rechazo antes de escribir inventario | `simulacion-crc.log` |
| Simulación completa de COM-00022 con tasa **ficticia** 500 CRC/USD | Estado verified, FOB aceptado **17,700 CRC → 35.400000 USD**; moneda y precios originales conservados; respuesta y copia de tasa correctas | `simular-crc-con-rollback.py`, `simulacion-crc.log/.exit` |
| Repetir la verificación de la compra ya verificada | Rechazado; huellas de filas iguales | `simulacion-crc.log` |
| Retaceo de la simulación con 500 CRC de gasto | Ajuste USD total **1.000000**; reutiliza la tasa; reintento conserva la aplicación | `simulacion-crc.log` |
| Rollback del ensayo | Las huellas de 13 tablas de inventario/compras de toda la empresa vuelven al valor previo; COM-00022 sigue received/CRC, sin tasa ni movimiento; sin aplicación de retaceo persistida | `simulacion-crc.log` |

La simulación usa los repositorios SQL y los casos de uso reales. Para la prueba monetaria del retaceo se utilizó el constructor heredado de costos; no acredita el flujo visual ni las validaciones de adjuntos/importación desde la orden. Las pruebas de permisos comprueban la protección declarada del endpoint; no sustituyen la matriz integral de roles pendiente.

El primer intento de pruebas de servidor dejó 59 aprobadas y una fallida por omitir un argumento obligatorio en un auxiliar de prueba nuevo. Se corrigió y la ejecución final dejó 62 aprobadas, incluyendo los casos añadidos. No se considera aprobado el primer registro.

## Continuación de la demostración

1. Recargar COM-00022 y abrir **Verificar recepción**. Volver a asignar las ubicaciones si el formulario se reinició. Mantener las cantidades originales de 400 y 900 kg.
2. En **Conversión para el costo de inventario**, introducir la tasa escogida para la demo. Por ejemplo, **500** significa **1 USD = 500 CRC**; es una tasa ficticia, no una cotización de mercado.
3. Elegir la fecha y escribir una referencia como **Prueba ficticia de demostración**. Revisar el equivalente estimado y verificar la recepción.
4. Confirmar que el detalle conserva CRC y muestra la tasa registrada; revisar el ingreso en cuarentena y el Kardex USD. Aplicar el retaceo de la compra cuando corresponda: conservar sus importes en CRC.

No hay descarga automática de tasas, tratamiento de diferencias cambiarias ni conversión independiente por cada gasto en una moneda adicional. Esta ampliación resuelve la recepción y retaceo en su moneda de compra frente a una valoración global. No se ejecutó el ingreso definitivo del usuario ni se declara cerrada la revisión visual o global B01–B08.

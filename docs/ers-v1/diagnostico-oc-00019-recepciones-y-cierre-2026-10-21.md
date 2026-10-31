# OC-00019: borrador de recepción, confirmación y cierre del pendiente

Fecha: 21/10/2026, America/El_Salvador.

## Hallazgo del usuario y datos comprobados

El usuario informó que, después de registrar la recepción, la orden seguía “Enviada”, la aplicación lo enviaba al listado de compras y podía comenzar otra recepción sin ver claramente si ya había terminado. Capturas aportadas: `C:/Users/rodri/AppData/Local/Temp/codex-clipboard-be24a038-215e-4399-a983-7582fc0ee556.png` y `C:/Users/rodri/AppData/Local/Temp/codex-clipboard-9dda2221-6dac-4577-8fc0-5f34d23fce1f.png`.

La consulta de diagnóstico a la base de demostración usó una transacción `READ ONLY`:

- Orden `OC-00019`, ID `2e94b2d9-13fb-4fff-8a3b-7b8ab4339752`, estado `sent`.
- Una sola recepción asociada: `COM-00021`, ID `b803ed0c-bfd7-400a-b291-918b3628f45c`, estado `draft`.
- Cantidades del borrador: 100, 100 y 125 en las unidades de sus líneas.
- `inventory_movement_id = null`; no hay una recepción confirmada para esa orden en la lectura realizada.

Evidencia: [consulta](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/diagnostico-solo-lectura.py), [resultado](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/diagnostico-solo-lectura.log), salida 0 y `transaction_read_only = on`.

Por tanto, no se comprobó una duplicación de entradas ni un cierre incumplido tras confirmación: se encontró un borrador pendiente. El problema reproducible del recorrido era que guardar dirigía a `/purchases` y la orden no mostraba cómo continuar ese borrador. No se debe cerrar la orden por guardar una propuesta de recepción.

## Cambios realizados

1. `PurchaseReceivingEditor`: después de guardar el borrador abre `/purchases/<id>` para continuar con **Confirmar recepción**. Incluye una explicación de que guardar y confirmar son pasos distintos.
2. Antes de preparar otro documento desde la URL de nueva recepción, consulta el borrador de la misma orden. Si existe, presenta **Continuar recepción COM-…** y no ofrece el formulario para duplicarlo. Un fallo de esa consulta presenta un error con reintento, sin tratar el fallo como una lista vacía.
3. `PurchaseOrderReceivingAction`: desde la orden se continúa el borrador existente. Si no hay borrador y la orden está enviada o parcialmente recibida, permite preparar la siguiente recepción. No ofrece crear mientras consulta ni si la consulta falla.
4. Una orden en `received` o `closed` presenta **Recepción completada**, con el texto de que ya fue recibida en su totalidad y no admite nuevas recepciones; no muestra el botón para registrar otra.

No se cambiaron los estados del dominio ni las reglas de recepción/aceptación. La consulta de borradores es una guía y prevención en la interfaz; no incorpora una restricción nueva de un solo borrador al endpoint de creación ni acredita un bloqueo de creaciones simultáneas. El servidor mantiene la defensa efectiva de cantidades y estado al confirmar.

## Secuencia de negocio conservada

- **Guardar borrador:** prepara el documento; no consume el pendiente ni ingresa mercancía.
- **Confirmar recepción:** cuenta las cantidades documentadas. La orden pasa automáticamente a `partially_received` o `received` según el saldo. Una vez completamente recibida no admite otra recepción mientras permanezca en ese estado.
- **Verificar recepción:** acepta/rechaza mercancía y registra las cantidades aceptadas en inventario mediante el flujo existente. Si se rechazan cantidades, el motor puede volver a dejar pendiente la reposición correspondiente; eso no es una entrada duplicada.
- El estado administrativo `closed` de la orden permanece separado del fin de la recepción. El estado `received` ya bloquea nuevas recepciones. La interfaz ahora anuncia ese resultado de forma explícita.

No se confirmó, canceló ni eliminó ningún documento real del usuario durante esta corrección. No se modificó inventario ni valoración; las pruebas de reglas de negocio usan repositorios en memoria.

## Comprobaciones

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Pantallas de recepción, acción de orden, detalles y acciones de compra | **23 aprobadas** | [frontend.log](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/frontend.log), salida 0 |
| Casos de uso de compras | **14 aprobadas** | [backend.log](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/backend.log), salida 0 |
| ESLint de componentes y pruebas modificados | Aprobado | [lint.log](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/lint.log), salida 0 |
| Svelte-check | **0 errores, 8 advertencias** | [svelte-check.log](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/svelte-check.log), salida 0 |

La cobertura focalizada incluye continuar el borrador desde la orden y desde la URL de nueva recepción, navegar al detalle al guardar, impedir crear desde la pantalla cuando falla la comprobación, recuperar la consulta mediante reintento y conservar recepciones parciales. En servidor se comprueba que, tras una recepción total, se rechaza reconfirmar la misma compra, confirmar otro borrador de esa orden o crear una nueva recepción; la cantidad contada permanece en la cantidad ordenada.

## Avance del recorrido manual y configuración pendiente en el diagnóstico inicial

El usuario continuó COM-00021 y aportó una captura de su verificación: `C:/Users/rodri/AppData/Local/Temp/codex-clipboard-20cb7764-6bd1-41c5-a999-92b7c17e27b7.png`. Una nueva consulta de solo lectura comprobó **OC-00019 = received** y **COM-00021 = received**, con `inventory_movement_id = null`. Se confirma la transición de la orden al registrar el recibo; la verificación de inventario todavía está pendiente.

La verificación mostró `purchase_receipt_unit_conversion_missing` para el producto 3. La [consulta de unidades](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/diagnostico-unidades-solo-lectura.py) y su [resultado](../../tmp/ers-v1/2026-10-21-cierre-recepcion-orden/diagnostico-unidades-solo-lectura.log), salida 0 y transacción de solo lectura, identificaron:

| Producto | Unidad recibida | Unidad base de inventario | Presentación vigente |
| --- | --- | --- | --- |
| PRD-HAR-003 — Harina Integral de Trigo 25kg | Kilogramo | Caja | Ninguna |
| PRD-HAR-001 — Harina de Trigo Suave 50lb | Kilogramo | Caja | Ninguna |
| PRD-EMP-010 — Bolsa Biodegradable Mediana | Caja | Caja | BOLSA-12, equivalencia 1 |

La presentación UNI-01 creada antes pertenece al producto nuevo de demostración; no define conversiones para estas harinas. En este diagnóstico aún no se habían configurado sus equivalencias. La intervención posterior autorizada por el usuario se documenta en [presentaciones de las harinas](presentaciones-harinas-demostracion-2026-10-21.md): se guardaron KG-HAR-003 y KG-HAR-001, con sus supuestos de demo, auditoría y comprobación completa mediante rollback.

Tras configurar esas equivalencias, reintentar la verificación de COM-00021 y comprobar el lote, las unidades logísticas y la valoración. La confirmación sobre el documento del usuario fue realizada por él, no por el agente. El cierre global B01–B08 permanece parcial por los casos de aceptación anteriores.

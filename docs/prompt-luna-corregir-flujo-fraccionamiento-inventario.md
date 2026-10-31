# Encargo para Luna: corregir el flujo de finalización y fraccionamiento de inventario

## Objetivo

Implementa y verifica una solución completa al flujo confuso de unidades logísticas en almacenes. El usuario termina de revisar medidas y etiqueta, libera la unidad a Disponible y cree que debe continuar dividiéndola. Cada división crea nuevas revisiones pendientes. Los cambios anteriores de texto no resolvieron el problema.

El proceso normal termina cuando la unidad está ubicada, revisada, con etiqueta vigente confirmada y Disponible. Dividir es una operación opcional que se inicia únicamente por una necesidad física explícita. Una unidad disponible permanece en el inventario; no debe desaparecer ni eliminarse para indicar que terminó su revisión.

Lee las instrucciones del repositorio y las skills aplicables. Conserva los cambios existentes de otros trabajos. Diagnostica, implementa, prueba y documenta el resultado; no te limites a producir otro plan o cambiar etiquetas de botones. Este encargo autoriza las pruebas indicadas abajo. No se requiere impresora física ni lector real: es una demostración del sistema.

## Evidencia y límites del diagnóstico

- Captura: `C:\Users\rodri\AppData\Local\Temp\codex-clipboard-d87b6da8-2a5e-4915-ab36-b2a4764431e3.png`.
- Pantalla: `/warehouses/d31dce4f-6078-47fb-a3e5-55e043abb6b0#inventario`, bodega de tienda Usulután.
- HU visible: `HU-8D63FE508BF14124`, Disponible, ubicación SEC-02, cantidad 2.25.
- El formulario permite introducir 2.249999 y muestra un remanente de 0.000001, con Confirmar división habilitado.
- Otros códigos visibles en capturas previas: `HU-EB8E841FE6534526` y `HU-8FEE57267CC84449`.
- El usuario interpreta que debe repetir dividir, verificar medidas, confirmar etiqueta y liberar indefinidamente.

La captura prueba que la interfaz permite preparar esa cantidad. No demuestra por sí sola una duplicación automática ni una pérdida de existencias. Separa errores de flujo, reglas de cantidades, solicitudes HTTP repetidas y posibles inconsistencias de datos.

Hallazgos de código que debes confirmar en el estado actual:

- El formulario de `HandlingUnitsPanel.svelte` usa precisión de seis decimales y valida principalmente que la cantidad sea positiva y menor al total. Cambiar el texto a Dividir unidad y dejar vacía la cantidad inicial fue insuficiente.
- `HandlingUnitSplitPrepareIn` admite Decimal con seis decimales. Esa precisión técnica no define la mínima cantidad física válida de cada producto.
- `UnitModel` y los esquemas de unidades en `catalog.py` no muestran un campo explícito de incremento mínimo. Revisa también producto, presentación y conversiones antes de diseñar la regla.
- El fraccionamiento conserva el código original para el remanente y crea otra HU. Ambas necesitan revalidación cuando cambian cantidades/etiquetas.
- Se reportaron anteriormente 31 pruebas de componente aprobadas. Eso no demuestra aceptación del flujo real ni integridad de las HUs de la captura.

## 1. Diagnóstico concreto antes de modificar

1. Identifica frontend, backend y base de datos realmente utilizados por localhost:5173. Evita validar otra instancia y declarar resuelto el problema del usuario.
2. Consulta sin modificar las HUs del caso: producto, unidad base, presentación, cantidades, origen, descendientes, estado, revisión de etiqueta, medidas y movimientos relacionados.
3. Comprueba si hay un bucle automático, múltiples envíos, respuestas obsoletas o simplemente operaciones opcionales presentadas como siguientes pasos obligatorios.
4. Reconcilia cantidades antes/después dentro del mismo conjunto de origen y verifica que fraccionar no agrega valor ni existencias. No sumes cantidades históricas como si todas fueran stock actual.
5. No declares duplicados dos movimientos solo por parecerse: despacho y recepción de un traslado pueden ser dos etapas legítimas. Comprueba IDs, referencias, origen/destino y efecto neto.

## 2. Flujo que debe quedar implementado

- Presenta de forma clara qué unidades requieren revisión y cuáles ya están disponibles. Muestra un cierre visible del proceso de revisión por unidad; cuando no haya pendientes, indícalo.
- Para una unidad Disponible, la acción principal no debe sugerir volver a dividir. Coloca Dividir unidad como operación secundaria explícita, por ejemplo dentro de Otras acciones.
- Dividir nunca se ejecuta ni abre automáticamente al cargar, actualizar, confirmar etiqueta o liberar. No preselecciones una cantidad de división.
- Abrir/cancelar el formulario no altera datos. Usa Cerrar formulario o Cancelar; evita Cerrar división para una acción que solo oculta el formulario.
- Muestra producto/SKU, unidad base real y equivalencia de presentación cuando corresponda. Evita que solo aparezca unidad base sin contexto para decidir cantidades.
- Antes de confirmar, muestra cantidad original, cantidad nueva y remanente con sus unidades, sin ruido de coma flotante. Explica brevemente que ambas partes tendrán que revisarse antes de quedar disponibles.
- Después de confirmar, cierra el formulario y presenta las dos unidades afectadas y sus requisitos reales. Al completar esos requisitos y liberarlas, muestra Disponible y revisión completada. Solo volverán a dividirse si el usuario inicia deliberadamente otra división válida.
- No ocultes pendientes reales de otras filas ni confundas sus avisos con los de una unidad ya liberada. No invalides una etiqueta vigente por consultar su QR o refrescar.
- Mantén una interfaz compacta y legible, sin párrafos repetidos por fila ni desbordamiento horizontal evitable.

## 3. Regla de cantidades en frontend y backend

Resuelve el caso 2.25 → 2.249999 + 0.000001 mediante una regla física explícita, no mediante un mínimo arbitrario global.

1. Identifica la granularidad permitida por unidad base/producto/presentación y conversiones existentes. Si falta esa política, añade la configuración mínima necesaria, compatible con el catálogo actual, y documenta cómo se obtiene y configura. No deduzcas toda la política únicamente del texto del símbolo.
2. Una división válida debe producir dos cantidades positivas y compatibles con esa granularidad. El servidor es la autoridad; el frontend debe anticipar los mismos errores y explicar el incremento permitido.
3. No impongas enteros a todos los productos: kg y L pueden admitir fracciones. Tampoco asumas que cualquier fracción de caja es válida sin su equivalencia configurada.
4. Si el caso actual usa una unidad indivisible y ya contiene 2.25, informa la inconsistencia de datos/configuración; no la arregles redondeando existencias. Si la granularidad permite legítimamente 0.000001, no lo prohíbas solo por verse pequeño: explica y prueba la política. Nunca inventes remanentes para mover una unidad completa.
5. Cantidad igual al total no es una división: recházala con explicación de que la unidad ya está completa y debe utilizarse la operación de unidad completa que exista, si corresponde.
6. Usa aritmética decimal exacta en backend. No redondees, deseches, absorbas ni ocultes remanentes silenciosamente. Evita discrepancias entre la previsualización y lo persistido.
7. Identifica otras rutas que puedan fraccionar HUs y aplica la misma regla compartida donde corresponda, sin romper movimientos completos ni operaciones legítimas.

## 4. Persistencia e integridad

- Conserva transacciones, aislamiento por empresa, permisos, auditoría, trazabilidad de origen y control de concurrencia.
- Doble clic, reintento de la misma operación o respuesta demorada no deben crear divisiones adicionales. Conserva idempotencia del servidor y deshabilita envíos concurrentes en la UI.
- Una solicitud inválida no debe crear movimientos, cambiar revisiones, mandar stock a cuarentena ni modificar saldos.
- Tras una división válida, la suma de ambas partes debe coincidir exactamente con la cantidad anterior y el valor total debe conservarse. Las medidas estimadas deben identificarse y verificarse por el mecanismo existente.
- Recargar la página debe conservar las confirmaciones y estados persistidos. No muestres éxito antes de que el servidor confirme.
- No borres HUs, movimientos o etiquetas históricas para hacer desaparecer filas. No fusiones unidades ni resetees inventario mediante SQL directo.
- Para datos existentes inconsistentes, entrega diagnóstico y una propuesta de corrección trazable por separado. No inventes confirmaciones físicas ni alteres los registros del usuario para aprobar una prueba.

## Archivos de referencia

- `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.svelte`
- `frontend/src/lib/features/inventory/components/HandlingUnitsPanel.test.ts`
- `frontend/src/lib/features/inventory/components/HandlingUnitLabelDialog.svelte`
- `frontend/src/lib/features/inventory/services.ts` y `types.ts`
- `backend/app/api/v1/routers/inventory.py`
- `backend/app/api/v1/schemas/inventory.py`
- `backend/app/infrastructure/repositories/inventory_repository.py`
- `backend/app/infrastructure/repositories/inventory_label_repository.py`
- `backend/app/domain/entities/inventory_release.py`
- `backend/app/infrastructure/models/inventory.py` y `catalog.py`
- `backend/app/api/v1/schemas/catalog.py`
- `backend/tests/integration/test_inventory_split_prepare_route.py`
- `backend/tests/integration/test_inventory_movement_idempotency.py`

Localiza los servicios adicionales que realmente intervengan. Evita refactorizaciones ajenas al problema.

## 5. Pruebas y aceptación obligatorias

Usa datos de prueba aislados para operaciones que mutan estado; conserva los del usuario.

### Backend

- División válida con granularidad conocida; suma exacta y valor conservado.
- Cero, negativo, igual al total, mayor al total y cantidades incompatibles con el incremento permitido.
- Validación tanto de la parte nueva como del remanente; reproducción del caso de la captura con la política documentada.
- Producto discreto y producto que admite fracciones legítimas.
- Reintento con la misma clave, doble envío y concurrencia: no hay duplicación ni saldo negativo.
- Empresa incorrecta y permisos insuficientes siguen bloqueados.
- Fallo de validación deja intactos cantidad, estado, movimientos y revisión de etiqueta.

### Frontend

- Disponible comunica finalización; dividir es opcional y no aparece como siguiente paso obligatorio.
- Cargar, refrescar, revisar etiqueta y liberar no envían solicitudes de división.
- Cancelar no muta datos; cantidad inicial vacía; errores claros; botón bloqueado durante envío.
- Vista previa y errores coherentes con la regla del servidor, incluyendo separadores numéricos admitidos por la UI.
- Actualización posterior muestra el estado correcto; respuestas antiguas no revierten una confirmación reciente.

### Recorrido real en navegador y API

Con un producto de prueba cuya unidad admita el caso, divide 10 en 4 y 6. Comprueba que hay exactamente las dos unidades esperadas, conserva total 10 y el valor original. Verifica medidas, revisa/confirma las etiquetas vigentes y libera ambas mediante el flujo soportado. Recarga y comprueba que siguen disponibles, sin nuevas HUs, sin nuevas divisiones y sin requisitos ya satisfechos reapareciendo. Prueba además una fracción legítima de una unidad continua y el intento de remanente incompatible con su política.

No necesitas imprimir físicamente ni escanear con hardware. Usa la previsualización y el flujo de demostración existente, documentando qué se simuló. No elimines las validaciones reales de etiqueta para pasar las pruebas.

Ejecuta las pruebas pertinentes, chequeo de tipos/Svelte, lint de archivos tocados y comprobación de diff según los comandos del repositorio. Reporta resultados reales. Si no puedes validar navegador o entorno, indícalo: no declares aceptación completa solo con tests simulados.

## Entregables

1. Corrección implementada con pruebas de regresión.
2. `docs/diagnostico-y-cierre-fraccionamiento-inventario.md`: causa confirmada, hechos frente a hipótesis, regla de cantidades elegida, archivos modificados, pruebas y resultados, diagnóstico de las HUs existentes y limitaciones pendientes.
3. Instrucciones manuales breves que respondan: dónde termina la revisión, cuándo dividir y cómo comprobar que las cantidades se conservaron.

El criterio de cierre es que el usuario pueda terminar la revisión y reconocer que terminó, y que una división explícita sea válida, trazable y no duplique existencias. Renombrar botones o esconder el inventario no satisface este encargo.

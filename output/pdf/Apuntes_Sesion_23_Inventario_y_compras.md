# Apuntes de la sesión 23
## Inventario, viñeteado, costos y kardex

**Documento de trabajo para los responsables de los cinco módulos de compras**

Sesión: 12 de octubre de 2026, según el nombre de la grabación. Elaboración de estos apuntes: 13 de octubre de 2026.

El ingeniero explica cómo continuar el proceso de compras hasta disponer de mercancía identificada, ubicada y valorada en inventario. La información debe permitir conocer de qué recepción provino un producto, dónde está, qué movimientos tuvo y con qué costo se valora.

> **Regla central de la clase:** recepción y retaceo finalizado → lote interno → impresión y colocación de viñetas → ubicación física confirmada → existencias disponibles y registro de movimientos.

### Cómo leer estos apuntes

- **CLASE:** explicación o requerimiento que se puede recuperar con claridad del TXT; se presenta en palabras corregidas, sin pretender una transcripción literal.
- **PROPUESTA:** solución de implementación o validación añadida al analizar el flujo. Necesita ajustarse al diseño del sistema.
- **POR DEFINIR:** aspecto que la transcripción no resuelve o cuya precisión requiere el material del ingeniero.

Se revisaron las 247 líneas del archivo. La introducción contiene ruido y varios ejemplos tienen cifras mal reconocidas. Los cálculos incluidos aquí se reconstruyeron a partir de cantidades claras. Las referencias a líneas permiten volver al TXT; el archivo no trae marcas de tiempo.

### Contenido

| Páginas | Tema |
|---|---|
| 2-4 | Impacto en los cinco módulos, flujo completo, recepción y retaceo |
| 5-6 | Lotes, viñetas y ubicación física |
| 7-8 | Costo promedio, PEPS y ejemplos corregidos |
| 9-10 | Kardex, traslados y ventas |
| 11-13 | Propuesta de datos y pantallas, tareas y criterios de aceptación |
| 14-15 | Decisiones pendientes, correcciones y avisos de la clase |

**Alcance:** análisis de la transcripción y traducción a tareas del sistema. La presencia o ausencia de cada función en el ERP debe contrastarse con su implementación; estos apuntes no certifican una auditoría del código.

Fuente: GMT20261012-222106_Recording (transcribed on 13-Oct-2026 15-33-37).txt.

<!-- page -->

# 1. Impacto en los cinco módulos de compras

Para organizar el trabajo, se toman como cinco módulos: **Solicitudes de compra, Cotizaciones, Órdenes de compra, Compras/Recepciones y Retaceo**, de acuerdo con el contexto previo del sistema. Esta distribución es editorial; el ingeniero concentra esta sesión en inventario.

| Módulo | Qué incorporar o comprobar | Alcance de esta sesión |
|---|---|---|
| 1. Solicitudes de compra | Conservar su relación con los documentos posteriores cuando exista, para poder consultar el origen de la necesidad. | No se describe una función nueva de solicitudes. Esta relación es una propuesta de continuidad con los apuntes anteriores. |
| 2. Cotizaciones | Mantener precios y condiciones ofrecidas como antecedentes de la compra; identificar la oferta de origen cuando corresponda. | No se redefine la comparación ni la adjudicación. El costo de inventario se toma del proceso de compra y retaceo, no directamente de una oferta. |
| 3. Órdenes de compra | Vincular orden, líneas y recepciones para contrastar lo pedido con lo recibido. Mantener accesible su relación con los gastos que llegan al retaceo. | Integración propuesta con el flujo existente; la clase menciona cantidades solicitadas y recibidas, pero no desarrolla otra vez la gestión de gastos de la orden. |
| 4. Compras / Recepciones | Registrar el conteo real, conservar el origen de cada recepción y habilitar el proceso de lote, viñetas y ubicación. | Es un punto central de la clase. Recibir mercancía no completa por sí solo su disponibilidad en inventario. |
| 5. Retaceo | Entregar el costo final de la mercancía recibida y mantener la relación con la compra y sus productos. | El retaceo finalizado precede al flujo de ingreso valorado. Después se aplica la valoración del inventario. |

### Funciones compartidas que deben conectarse

**CLASE.** Se necesitan lotes internos, viñeteado, ubicaciones codificadas, existencias, valoración y kardex. Al final se anuncia continuar con traslados y después con ventas.

**PROPUESTA.** Implementar estos procesos en Inventario y Almacenes y enlazarlos desde Compras/Recepciones y Retaceo. Una misma recepción puede quedar parcialmente ubicada; el usuario debe poder distinguir lo recibido, lo pendiente de ubicar y lo disponible.

**Continuidad con reuniones anteriores.** Los consolidados, PDFs por proveedor, adjudicaciones y documentos de gastos siguen siendo antecedentes del proyecto. Este TXT no introduce nuevas reglas detalladas para ellos.

Base del TXT: líneas 43-55, 69 y 245. El reparto por módulos es una propuesta de organización.

<!-- page -->

# 2. Flujo operativo explicado por el ingeniero

**CLASE.** Recepción y retaceo se trabajan de manera coordinada: una actividad verifica físicamente lo que llegó y la otra determina su costo. El flujo mostrado después exige que el retaceo esté finalizado antes de continuar hacia el ingreso valorado.

| Paso | Trabajo que realiza la persona | Resultado que debe registrar el sistema |
|---|---|---|
| 1. Descargar y recibir | Bajar la mercancía a una zona de recepción y contarla. | Cantidad solicitada y cantidad realmente recibida, asociadas a la compra. |
| 2. Finalizar el retaceo | Revisar y distribuir los costos de esa compra. | Costo final de cada producto recibido, disponible para la valoración. |
| 3. Crear el lote interno | Identificar el conjunto recibido. | Un lote de recepción que puede incluir varios productos. |
| 4. Generar e imprimir viñetas | Elegir producto, lote y cantidad de etiquetas. | Etiquetas con código interno, lote y fecha; control de impresión. |
| 5. Colocar las viñetas | Pegar físicamente las etiquetas en los productos. | Avance del trabajo de identificación, según el control que se diseñe. |
| 6. Ubicar la mercancía | Llevarla a una ubicación; escanear ubicación y producto e ingresar cantidad. | Relación entre producto, lote, ubicación y cantidad colocada. |
| 7. Confirmar el ingreso | Confirmar que la ubicación es válida y que la mercancía fue colocada. | Existencias por ubicación, disponibilidad y movimientos de inventario. |

### Qué significa para la interfaz

**PROPUESTA.** Presentar el avance por cantidades y etapas: recepción registrada, retaceo pendiente/finalizado, pendiente de viñeteado, pendiente de ubicación y ubicación parcial/completa. Estos nombres son una propuesta, no estados textuales aprobados por el ingeniero.

No basta un único estado de cabecera para describir una recepción con varios productos: pueden existir líneas terminadas y otras pendientes. Mostrar el detalle evita tratar toda la compra como disponible antes de tiempo.

La validación de ubicación es parte del flujo. Si el destino no es válido, se corrige la asignación y se vuelve a confirmar. La clase no entrega aún una regla técnica completa para capacidad, compatibilidad o restricciones del almacén.

Base del TXT: líneas 47-55 y 69.

<!-- page -->

# 3. Recepción y retaceo: qué debe quedar conectado

### Recepción de compra

**CLASE.** El personal cuenta lo descargado y compara lo recibido con lo solicitado. Mientras se organiza el ingreso, la mercancía permanece en el área física de descarga o recepción. El registro debe reflejar lo que ocurrió realmente.

**PROPUESTA.** Cada línea debe permitir consultar producto y unidad, cantidad pedida, cantidad recibida, diferencia, compra/orden de origen y fecha. Si existe una diferencia, registrar su explicación y el tratamiento aprobado. La sesión no establece cómo aceptar sobrantes, daños o faltantes; esa política debe definirse.

En recepciones parciales, cada recepción conserva su propia identidad. No se debe sumar otra vez una cantidad ya registrada al continuar el proceso de etiquetado o ubicación.

### Retaceo finalizado

**CLASE.** El retaceo determina el costo de esa compra. El costo promedio posterior combina ese costo de entrada con el valor de las existencias anteriores del mismo producto.

| Dato | Uso en el proceso |
|---|---|
| Recepción y línea de compra | Identificar qué mercancía y cantidades se están valorando. |
| Cantidad real aceptada para el ingreso | Base de unidades que se incorporarán al inventario; su definición ante incidencias debe acordarse. |
| Costo unitario y costo total del retaceo | Valor de entrada para el producto. |
| Estado de finalización | Evidencia de que el costo está listo para continuar. |
| Referencia al cálculo | Permitir consultar de dónde salió ese costo. |

Los identificadores, el control de cantidades aceptadas y la referencia a la versión del cálculo son **propuestas técnicas** para conservar la trazabilidad; no son nombres de campos dictados en esta clase.

### Dos costos que se deben conservar

**Costo de origen:** lo que costó la mercancía de una recepción determinada, después del retaceo. **Costo promedio vigente:** el resultado de combinar entradas con las existencias anteriores para valorar el producto.

**PROPUESTA.** Conservar ambos valores y su historial. Un promedio nuevo no debe borrar el costo original de una compra ni modificar retroactivamente los movimientos ya registrados.

El momento exacto de actualización de la valoración durante ubicaciones parciales requiere una regla única: registrar cada cantidad una sola vez, con el costo final correspondiente. La clase describe el ingreso después de ubicar; no especifica un asiento técnico para cada evento intermedio.

Base del TXT: líneas 45-47, 55, 69, 79-85 y 225.

<!-- page -->

# 4. Lotes internos y viñeteado

### Regla de identificación de la clase

**CLASE.** El código de barras representa el **código interno del producto** creado en el sistema. El lote interno se genera por recepción de compra. Distintos productos recibidos juntos pueden compartir ese lote, aunque cada producto tenga su propio código.

| Ejemplo de una recepción | Código de producto | Lote interno | Cantidad |
|---|---|---|---|
| Televisor, modelo A | PROD-A | LOTE-R001 | 20 |
| Televisor, modelo B | PROD-B | LOTE-R001 | 10 |
| Televisor, modelo C | PROD-C | LOTE-R001 | 20 |

Los códigos de esta tabla son ilustrativos. Las veinte unidades del modelo A comparten el código de producto, el lote y la fecha de recepción. La clase **no define un número de serie único por unidad**.

### Información de la viñeta

- Código de barras generado desde el código interno del producto.
- Lote interno y fecha de recepción visibles para identificar físicamente la procedencia y antigüedad.
- Nombre de la empresa y código escrito como elementos ajustables al tamaño de etiqueta; el ingeniero comenta que pueden simplificarse.
- Cantidad de etiquetas a imprimir por producto y lote. Debe existir un registro de las impresiones y sus fechas.

**CLASE.** Se imprime en material adhesivo y se pega físicamente. Las impresoras y medidas pueden variar. La organización de la impresión debe acompañar ese trabajo del personal.

### Controles propuestos

**PROPUESTA.** Distinguir etiquetas impresas, reimpresiones y unidades efectivamente etiquetadas. Reimprimir diez etiquetas no significa haber recibido o agregado diez productos más. Conservar usuario, fecha y motivo de reimpresión ayuda a explicar el historial.

El lote de recepción y el lote de fabricación son conceptos diferentes. El ingeniero utiliza el primero en este flujo; conservar un lote del fabricante, caducidad o seriales sería una decisión adicional del negocio. No se desprende de la clase que deban eliminarse datos ya existentes.

**Antecedente previo:** QR y Code 128 se habían mencionado en otros apuntes. Esta sesión exige un código de barras basado en el identificador interno, pero no fija explícitamente una simbología ni el contenido definitivo de un QR.

Base del TXT: líneas 47-51 y 61. Controles adicionales identificados como propuesta.

<!-- page -->

# 5. Ubicación física y confirmación de cantidades

**CLASE.** El ingeniero propone una pantalla sencilla con tres entradas: **ubicación, producto y cantidad**. El bodeguero escanea la ubicación, escanea uno de los productos y escribe cuántas unidades dejará allí. Al confirmar, se registra la colocación.

> **Precisión frente a apuntes anteriores:** en esta sesión se aclara que no es necesario escanear cada unidad. Se escanea un producto y se digita la cantidad del grupo que se coloca.

### Caso de ubicación parcial

Se llevan 20 unidades etiquetadas. En el primer lugar caben 12: se confirma ubicación A, producto y cantidad 12. Las otras 8 se colocan y confirman en la ubicación B. El sistema debe mostrar ambos destinos y un total de 20 unidades ubicadas.

Es preferible mantener los productos juntos cuando sea posible, pero el sistema debe admitir varios destinos. Una ubicación puede ser un rack, un anaquel o un espacio de piso identificado. El ingeniero también contempla introducir manualmente la nomenclatura cuando corresponda.

### Cómo mantener el lote al escanear

**POR DEFINIR.** Un código de barras que solo identifica el producto no permite distinguir dos lotes del mismo producto. El ingeniero no detalla cómo resolver esa selección en la pantalla de tres campos.

**PROPUESTA.** Abrir el trabajo desde una recepción/lote previamente seleccionado y mantener ese contexto durante el escaneo. Si existen varios lotes posibles, exigir selección explícita o una identificación adicional. No asignar un lote arbitrario por coincidencia del producto.

### Validaciones para incorporar

- Ubicación existente y válida para el almacén con el que se está trabajando.
- Producto y lote pertenecientes al trabajo de recepción seleccionado.
- Cantidad mayor que cero, con la unidad y precisión permitidas para ese producto.
- Cantidad colocada no superior al saldo pendiente de ubicar de esa línea/lote.
- Una confirmación repetida no debe duplicar el ingreso.
- Si se aplica control de capacidad o compatibilidad, impedir la confirmación hasta disponer de un destino permitido.

La existencia de una ubicación válida es **CLASE**. El detalle de estas validaciones es **PROPUESTA**. Capacidad y compatibilidad todavía requieren criterios y unidades definidos.

La sugerencia de colocar productos de mayor movimiento cerca de la salida es una recomendación operativa del ingeniero. No se solicita un algoritmo automático de asignación de espacios.

Base del TXT: líneas 51-55 y 69.

<!-- page -->

# 6. Valoración por costo promedio ponderado

**CLASE.** Para el proyecto se plantea utilizar costo promedio ponderado y configurarlo globalmente por empresa. Los lotes siguen siendo necesarios para conservar el origen y organizar físicamente las salidas.

### Fórmula reconstruida

> **Nuevo costo promedio = (valor anterior del inventario + valor de la entrada) / (cantidad anterior + cantidad de entrada).**

| Variable | Significado |
|---|---|
| Cantidad anterior | Unidades que quedan del producto antes de la nueva entrada. |
| Valor anterior | Valor que conservan esas existencias. En un promedio consistente: cantidad anterior por costo promedio anterior. |
| Cantidad de entrada | Unidades nuevas que se incorporan. |
| Valor de entrada | Cantidad incorporada por su costo unitario final, proveniente del retaceo. |

El promedio utiliza las **existencias remanentes**, no todas las unidades compradas históricamente. Se calcula por producto: no se mezclan costos de café con leche, ni de modelos diferentes de un televisor.

### Cuándo cambia

**CLASE.** Una nueva compra que entra con existencias anteriores obliga a combinar ambos valores. Si ya no queda ninguna unidad, la entrada toma su propio costo. Una venta reduce cantidad y valor al costo vigente; el ejemplo de la clase mantiene el promedio después de vender.

**PROPUESTA.** Definir una sola operación que confirme el ingreso, actualice el saldo valorado y registre el movimiento. Si una recepción se ubica por partes, usar únicamente la cantidad del ingreso que se está confirmando y evitar contabilizar toda la recepción en cada parte.

### Configuración por empresa

El alcance global por empresa aparece expresamente en la clase. **POR DEFINIR:** confirmar en el documento del ingeniero si, además de la política global, el saldo y el promedio de cada producto se agrupan entre todos los almacenes de la empresa. La interfaz puede mostrar existencias por ubicación sin que eso implique promedios independientes.

### Precisión y costo de venta

**PROPUESTA.** Calcular con precisión decimal suficiente y redondear según una política uniforme al presentar totales. No usar como base el promedio ya redondeado de la pantalla si eso altera el resultado.

El costo promedio valora la salida y las existencias. El precio que se cobra al cliente se define en el proceso comercial. La transcripción mezcla ocasionalmente estas expresiones; la clase distingue ambos conceptos al principio y durante los ejemplos.

Base del TXT: líneas 45, 67-85 y 197-225.

<!-- page -->

# 7. PEPS y promedio: ejemplos corregidos

**CLASE.** PEPS significa primeras entradas, primeras salidas. El ingeniero distingue sacar físicamente la mercancía más antigua de valorar sus costos mediante PEPS. Se puede mantener la rotación física por antigüedad y valorar por promedio.

### El ejemplo de 10 unidades y 8 unidades

Primera entrada: 10 unidades a $10 = $100. Segunda entrada: 8 unidades a $12 = $96. Antes de vender hay **18 unidades y $196 de valor total**. Se retiran 12 unidades.

| Concepto | Valoración PEPS | Promedio ponderado |
|---|---|---|
| Base de costo | Costos de los lotes más antiguos primero | $196 / 18 = $10.888888... por unidad |
| Costo de salida de 12 unidades | (10 × $10) + (2 × $12) = $124.00 | 12 × ($196 / 18) = $130.666666...; se muestra $130.67 |
| Unidades que quedan | 6 | 6 |
| Valor del inventario restante | 6 × $12 = $72.00 | 6 × ($196 / 18) = $65.333333...; se muestra $65.33 |
| Comprobación | $124 + $72 = $196 | $130.666666... + $65.333333... = $196 |

Los resultados se reconstruyeron matemáticamente; no son una copia de las cifras mal reconocidas por la transcripción. En particular, 10 + 8 no son 20, y el costo de salida por promedio no es $130.60.

### Qué quería mostrar el ejemplo de las vacas

Dos unidades comparables, una que costó $1,000 y otra $900, tienen un valor conjunto de $1,900 y un promedio de $950. Si la segunda hubiera costado $1,200, el total sería $2,200 y el promedio $1,100.

El promedio redistribuye el costo unitario entre las existencias. En estos ejemplos **no desaparece valor total por promediar**: baja el valor atribuido a una unidad cara y aumenta el atribuido a la barata. Esa es la aclaración útil que se recupera del ejemplo, más allá de sus frases confusas.

### Caso sin existencias anteriores

Si el saldo anterior es cero y entran 8 unidades a $12, el promedio queda en $12. Si queda una sola unidad de una compra anterior, su cantidad y valor deben incluirse en la fórmula.

**Alcance del proyecto:** el ingeniero elige promedio para esta fase y explica PEPS como comparación. Implementar un motor completo de valoración PEPS no queda establecido como entrega adicional obligatoria en este TXT.

Base del TXT: líneas 61-85, 147-195 y 215-225. Aritmética corregida para estos apuntes.

<!-- page -->

# 8. Kardex: historial de movimientos

**CLASE.** El kardex permite consultar cómo se ha movido un producto: fecha, tipo de movimiento, entradas, salidas, saldo y costo. El sistema lo alimenta desde las operaciones; el usuario consulta y filtra sus datos, sin editarlos directamente.

| Movimiento | Efecto físico explicado | Observación para el sistema |
|---|---|---|
| Compra incorporada al inventario | Entrada | Registrar al completar el ingreso definido en el flujo, evitando duplicar la recepción. |
| Venta | Salida | Aplicar el costo vigente conforme al método de valoración. |
| Devolución de cliente | Entrada | La clase describe su dirección; falta acordar qué costo se restituye. |
| Devolución a proveedor | Salida | Conservar el vínculo con la compra y el lote; política de costo pendiente. |
| Ajuste por sobrante | Entrada | Registrar una operación de ajuste con su motivo. |
| Ajuste por faltante | Salida | Registrar la disminución y su motivo. |
| Traslado entre almacenes | Salida del origen y entrada en destino | Relacionar ambos lados de la misma operación. |
| Cambio de ubicación | Salida de una ubicación y entrada en otra del mismo almacén | Cambia la distribución física; no aumenta el total del almacén. |

La dirección de los movimientos es **CLASE**. Los vínculos, controles de duplicidad y motivos de ajuste son **PROPUESTAS** de implementación.

### Qué mostrar y filtrar

**CLASE.** Consulta por producto, fecha y filtros relacionados con los movimientos. Mostrar entradas, salidas, saldo y costo promedio.

**PROPUESTA.** Añadir documento de origen, lote, almacén, ubicación, usuario responsable, costo unitario de la operación, valor del movimiento y valor del saldo. Filtros por empresa, almacén, lote y tipo de movimiento facilitan las investigaciones del personal.

### Historial que se pueda explicar

**PROPUESTA.** Una corrección debe dejar una operación vinculada y justificada, en vez de permitir sobrescribir una fila del kardex. El criterio técnico exacto de reversión y los permisos deben acordarse antes de implementarlo.

El saldo inicial también necesita una procedencia identificable. Los costos guardados en movimientos históricos deben representar el momento de la operación; consultar hoy un movimiento antiguo no debe sustituir su costo por el promedio actual.

Base del TXT: líneas 47, 227 y 229.

<!-- page -->

# 9. Traslados, ventas y separación de procesos

**CLASE.** El ingeniero anuncia completar primero traslados, después ventas y finalmente afinar el sistema. El objetivo es continuar desde las compras hasta registrar salidas de inventario dentro del mini ERP.

### Cambio de ubicación dentro del almacén

La persona mueve físicamente un producto de un sitio a otro. El sistema reduce la cantidad en la ubicación de origen y la aumenta en destino. Debe mantener el producto y su lote identificados.

**PROPUESTA.** Registrar ambos lados con un mismo identificador de operación. El total del almacén y de la empresa debe permanecer igual. Este movimiento no debe parecer una compra ni generar un nuevo lote de recepción.

### Traslado entre almacenes

El almacén que envía registra una salida y el que recibe registra una entrada. La clase no detalla el tiempo que transcurre entre despacho y recepción, ni el tratamiento de faltantes durante el transporte.

**POR DEFINIR.** Acordar si existirá estado «en tránsito», quién confirma la recepción, cómo se documentan diferencias y cómo se conserva el valor durante ese lapso. No asumir que una recepción en destino crea nuevas unidades para toda la empresa.

Si se confirma un único promedio por producto para toda la empresa, el traslado interno debe conservar el valor global. Si se elige otro alcance, será necesario definir expresamente la valoración entre almacenes. Es una decisión de diseño pendiente.

### Ventas

Una venta produce una salida. Bajo promedio se utiliza el costo vigente para valorarla, aunque el personal retire físicamente unidades de los lotes más antiguos. El precio de venta y los descuentos comerciales no sustituyen el costo de inventario.

**PROPUESTA.** Vincular cada salida con documento comercial, producto, cantidad, lote(s), ubicación(es) y costo registrado. Una salida puede necesitar cantidades de más de un lote o lugar.

### Bodega, exhibición y presentación del producto

El ingeniero comenta que la manipulación varía según el negocio: exhibición, vitrinas, producto en caja, unidades sueltas o paquetes. También menciona dificultades de adhesivos en productos refrigerados.

Esos ejemplos explican por qué el sistema debe acompañar la operación física. La sesión no define un módulo de exhibición, conversiones entre cajas y unidades, ni una integración obligatoria con códigos de fabricantes. Esas reglas deben acordarse según el negocio.

Base del TXT: líneas 49-53, 61, 83, 227-229 y 245.

<!-- page -->

# 10. Propuesta de datos, pantallas y responsabilidades

**PROPUESTA DE IMPLEMENTACIÓN.** La clase anuncia que las tablas definitivas se entregarían después. Lo siguiente organiza la información necesaria para cubrir el flujo; no reproduce un esquema de base de datos aprobado por el ingeniero.

| Registro o relación | Información mínima que debería conservar |
|---|---|
| Recepción y detalle | Empresa, compra/orden, producto, unidad, fecha, cantidades y diferencias. |
| Retaceo y detalle | Referencia a compra/recepción, costo final por línea, estado y referencia del cálculo. |
| Lote de recepción | Identificador interno, empresa, recepción de origen y fecha. |
| Producto dentro del lote | Producto, unidad, cantidad recibida e información del costo de origen. |
| Impresión de viñetas | Lote, producto, cantidad, fecha y responsable; distinguir reimpresión. |
| Trabajo de ubicación | Recepción/lote seleccionado, producto, destino, cantidad y confirmación. |
| Existencia física | Empresa, almacén, ubicación, producto, lote, unidad y cantidad. |
| Movimiento de inventario | Tipo, fecha/orden de registro, origen y destino, cantidades, costo y documento que lo originó. |
| Valoración | Producto, alcance acordado, cantidad, valor y costo promedio vigente. |

### Pantallas que hacen falta en el flujo funcional

1. **Seguimiento de la recepción:** cantidades recibidas, costo final y avance hacia viñeteado y ubicación.
2. **Viñeteado:** selección de recepción/lote y producto, impresión y consulta de impresiones anteriores.
3. **Ubicación por escaneo:** ubicación, producto y cantidad, conservando el lote de trabajo.
4. **Existencias:** consulta por producto, lote y ubicación, con disponibilidad y procedencia.
5. **Kardex:** historial filtrable con acceso al documento que originó cada movimiento.

No necesariamente son cinco menús nuevos: pueden integrarse como vistas o acciones en los módulos existentes.

### Responsabilidades por acordar

Recepción/bodega realiza conteo y colocación; el personal autorizado finaliza el retaceo; el responsable de inventario revisa ajustes; auditoría consulta trazabilidad y kardex. Esta distribución es una propuesta: el TXT describe actividades, pero no fija nombres de roles ni una matriz completa de permisos.

El sistema debe conservar el vínculo entre quien confirma una operación y su fecha. Registrar un evento no demuestra por sí solo que el trabajo físico ya se ejecutó: cada confirmación debe corresponder a una acción realizada.

Base conceptual: líneas 47-55, 69, 227 y 231-239. Estructura y pantallas propuestas.

<!-- page -->

# 11. Trabajo a repartir entre los responsables

Esta lista convierte los apuntes en entregables revisables. **Prioridad A** cubre el flujo principal de esta sesión. **Prioridad B** corresponde a la continuación anunciada o a decisiones complementarias.

| ID / prioridad | Responsable funcional | Entregable y condición de término |
|---|---|---|
| R01 / A | Solicitudes + Cotizaciones | Comprobar que se conserva el vínculo con los documentos posteriores cuando aplica. Es una integración propuesta; no se solicita rehacer estos módulos. |
| R02 / A | Órdenes + Recepciones | Consultar cantidades solicitadas y recibidas con su origen, fecha y diferencias. |
| R03 / A | Recepciones + Retaceo | Exponer el costo final y la condición de retaceo finalizado antes del ingreso valorado. |
| R04 / A | Recepciones + Inventario | Crear e identificar un lote interno por recepción, con varios productos asociados cuando corresponda. |
| R05 / A | Viñeteado | Imprimir código interno, lote y fecha; consultar cantidad y fecha de impresiones. |
| R06 / A | Almacenes | Confirmar ubicación, producto y cantidad; admitir distribución de un lote entre ubicaciones. |
| R07 / A | Inventario | Mostrar las cantidades ubicadas y pendientes, evitando registrar dos veces una misma incorporación. |
| R08 / A | Inventario / Costos | Calcular promedio con cantidad y valor remanentes más la entrada al costo final. Definir alcance por empresa y producto. |
| R09 / A | Kardex | Registrar entradas, salidas, saldos y costos; consultar y filtrar sin edición directa. |
| R10 / A | Equipo completo | Conservar referencias de compra, recepción, retaceo, lote, ubicación y movimiento para consultar la procedencia. |
| R11 / B | Traslados | Implementar salida de origen y entrada de destino relacionadas; resolver tránsito y diferencias. |
| R12 / B | Ventas | Registrar salidas y costo aplicado, conservando la identificación física del producto retirado. |

### Dependencias antes de cerrar cada entrega

**PROPUESTA.** R03 debe quedar resuelto antes de valorar las entradas; R04 antes de identificar las viñetas; R06 y R07 deben usar la misma regla de ingreso; R08 y R09 deben registrar cantidades y valores coherentes en una sola confirmación.

R01 y los detalles de permisos, reimpresión y prevención de duplicados son soluciones técnicas propuestas. El resto deriva del flujo descrito, con decisiones pendientes indicadas en sus capítulos.

Que una función aparezca en esta lista significa que **debe existir o comprobarse**. No significa que se haya verificado su ausencia en el sistema actual.

Base del TXT: líneas 43-85, 215-229 y 245.

<!-- page -->

# 12. Criterios para revisar la implementación

**PROPUESTA.** Estos casos son una guía para los equipos; no son resultados de pruebas ejecutadas contra el ERP. Permiten comprobar el comportamiento sin depender de frases ambiguas de la transcripción.

| Caso | Resultado esperado |
|---|---|
| Una recepción con tres productos | Un lote interno de recepción compartido y tres identificadores de producto diferentes. |
| El mismo producto en dos recepciones | Se distinguen los dos lotes y sus fechas, aunque el código de producto sea igual. |
| Imprimir o reimprimir etiquetas | Se registra la impresión; el stock permanece igual hasta la confirmación de ingreso correspondiente. |
| Escanear producto y ubicación para 20 unidades | Se digita 20; no se exigen veinte escaneos individuales. |
| Ubicar 12 y después 8 | Se muestran dos destinos, 20 unidades colocadas y cero pendientes de esa línea. |
| Intentar ubicar más del saldo pendiente | Se impide la confirmación y se muestra el saldo disponible para ubicar. |
| Dos lotes posibles al escanear un producto | Se conserva el lote de trabajo o se exige elegirlo antes de registrar. |
| Repetir la misma confirmación | No se duplica la existencia, el valor ni el movimiento. |
| 10 unidades a $10 y entrada de 8 a $12 | Saldo 18, valor $196 y promedio $10.888888... antes de la salida. |
| Salida posterior de 12 bajo promedio | Saldo 6; costo de salida $130.666666... y valor restante $65.333333... antes de redondear. |
| Entrada de 8 a $12 con saldo anterior cero | Saldo 8, valor $96 y promedio $12. |
| Cambiar mercancía de ubicación | La cantidad disminuye en origen y aumenta en destino; no cambia el total del almacén. |
| Consultar un movimiento antiguo | Se ve el costo histórico aplicado y su documento de origen. No se puede editar la fila directamente. |

### Comprobaciones complementarias

Para ubicaciones parciales, cada confirmación utiliza su cantidad exacta y el costo final correspondiente. Si se hacen ventas entre dos ingresos parciales, el promedio debe calcularse con el saldo que existe en cada momento, según la política de ingreso acordada.

Un cambio posterior al retaceo de una entrada ya registrada requiere una política de corrección. No debe recalcularse silenciosamente todo el historial. La sesión no desarrolla este caso; debe resolverse antes de permitir cambios sobre operaciones cerradas.

Los totales físicos por ubicación deben reconciliarse con el total del producto dentro del mismo alcance. La valoración y el kardex deben usar ese alcance de manera consistente.

<!-- page -->

# 13. Decisiones que siguen pendientes

La explicación define el flujo principal, pero no todos los detalles operativos. Estos puntos deben contrastarse con las tablas y el documento anunciados por el ingeniero.

| Tema | Decisión necesaria |
|---|---|
| Momento de ingreso | Confirmar cómo se registra una ubicación parcial y cuándo se reconoce su cantidad y valor, manteniendo la recepción sin duplicidades. |
| Promedio global | Precisar si todos los almacenes de una empresa comparten un promedio por producto, además de compartir el método configurado. |
| Identificación del lote | Resolver el caso de varios lotes del mismo producto cuando el código de barras contiene solo el código interno. |
| Unidades y presentaciones | Definir si el conteo y la viñeta corresponden a caja, paquete o unidad, y cómo se convierten cantidades si existen varias presentaciones. |
| Recepción con incidencias | Determinar aceptación de sobrantes, faltantes, daños y cantidades que no pueden incorporarse. |
| Ubicación válida | Definir qué significa capacidad y compatibilidad, sus unidades y quién autoriza un destino. |
| Devoluciones y ajustes | Acordar el costo que se aplica y los documentos o autorizaciones requeridos. |
| Traslado entre almacenes | Definir tránsito, confirmación de destino, diferencias y conservación del valor. |
| Cambios y redondeos | Fijar precisión, tratamiento de residuos, correcciones, fechas retroactivas y cambios a costos ya aplicados. |
| Lotes o seriales adicionales | Decidir necesidades de lote de fabricante, caducidad y número de serie según los productos del negocio. |

### Qué no debe darse por exigido en esta sesión

La clase no solicita explícitamente integración con una impresora o escáner de marca concreta, automatización de la mejor ubicación, un módulo completo de exhibición, QR con todos los documentos embebidos ni valoración PEPS obligatoria junto al promedio.

Tampoco entrega una nueva especificación completa de consolidación, cotizaciones, PDFs por proveedor o gastos. Esos temas proceden de reuniones anteriores y deben conservar su propia referencia.

### Orden de implementación propuesto

Cerrar primero el contrato de datos entre recepción, retaceo y lote; después viñeteado y ubicación; conectar la confirmación con existencias, valoración y kardex. Continuar con traslados y ventas, tal como anuncia el ingeniero.

Base del TXT: ambigüedades en líneas 47-69, 227-229 y 231-245. Lista de decisiones elaborada durante el análisis.

<!-- page -->

# 14. Correcciones de lectura y referencias

### Interpretaciones importantes de la transcripción

| Pasaje | Lectura utilizada en estos apuntes |
|---|---|
| Inicio con idiomas mezclados y frases sueltas | Ruido de transcripción; no contiene requerimientos fiables. La explicación comienza en la línea 31. |
| «Retaseo», «retesio», «vignetas», «resección» | Se normalizan como retaceo, viñetas/viñeteado y recepción según el contexto. |
| «Tenemos 20» junto a 10 y 8 unidades | El ejemplo se calcula con 18 unidades; se conservan las cantidades repetidas con claridad. |
| «Vender a ese costo promedio» | Se interpreta como costo de la salida. El expositor distingue costo y precio de venta en otras partes de la misma explicación. |
| Ejemplo de vacas con «95» o cifras fragmentadas | Se reconstruyen $950 y $1,100 a partir de pares explícitos: 1,000 + 900 y 1,000 + 1,200. No se usan los totales confusos de ganancias. |
| «La venta es una entrada» | Se corrige a salida: el propio ejemplo resta seis unidades y después el expositor identifica ventas como salidas. |
| Comentarios sobre Hacienda | Se conservan como contexto de la explicación sobre trazabilidad. No se convierten en una obligación legal verificada ni en una regla fiscal del sistema. |

### Mapa para consultar la fuente

| Líneas del TXT | Contenido |
|---|---|
| 31-45 | Inicio de la clase, finalidad del inventario y diferencia entre costo y precio |
| 47-55 | Recepción, retaceo, lote, viñetas y ubicación |
| 57-85 | PEPS físico, valoración, alcance por empresa y promedio ponderado |
| 97-195 | Ejemplos de percepción del costo y cifras de las vacas |
| 197-225 | Existencias anteriores y caso de saldo cero |
| 227-229 | Kardex y tipos de movimientos |
| 231-245 | Tablas pendientes, revisiones y continuación del proyecto |

### Avisos administrativos recuperables

El ingeniero anuncia que entregaría tablas y un documento complementario en la siguiente clase. Al cierre menciona revisiones para los grupos **2, 4 y 5**, lunes y miércoles de la semana siguiente, tras corregir una enumeración anterior. La agenda debe contrastarse con el aviso del curso; el TXT no aporta el calendario definitivo.

Se indica que aún había revisiones pendientes de retaceo. El orden de continuación anunciado es traslados y después ventas. La frase final sobre qué parte se «afina» está poco clara y no se transforma en una tarea específica.

**Fuente única de esta sesión:** archivo TXT indicado en la primera página, 247 líneas. No se revisó el audio ni el diagrama que el ingeniero mostraba en pantalla. Los estados, campos técnicos y casos de aceptación señalados como propuesta se añadieron para volver los apuntes utilizables por los equipos.

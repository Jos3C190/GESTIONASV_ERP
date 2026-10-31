# Análisis de la ERS y del ejemplo de retaceo

**Fecha:** 12 de octubre de 2026.  
**Proyecto:** GestionaSV.  
**Alcance:** análisis documental completo, comprobación aritmética del Excel y contraste puntual con el código de retaceo. No constituye una prueba de aceptación de todo el ERP.

## 1. Dictamen

Los documentos definen una base útil para solicitudes, cotizaciones, órdenes, recepción y retaceo. Sin embargo, contienen errores de ejemplo y decisiones operativas pendientes. Deben convertirse en reglas verificables antes de usarlos para declarar terminado el sistema.

Los hallazgos principales son:

1. **El Excel omite $1,250 de seguro en la hoja Retaceo**, aunque los incluye en el inventario de la hoja Datos. Los dos totales no concilian.
2. **La columna “Costo Unitario” del Excel calcula un total por línea.** No divide entre la cantidad. El defecto queda oculto porque ambos productos tienen cantidad 1.
3. **La ERS exige distribución proporcional al FOB.** El editor actual de gastos detallados del sistema solicita distribución manual. Existe un cálculo proporcional en el backend, pero el flujo revisado utiliza el manual cuando recibe gastos detallados.
4. **Los tres totales del ejemplo de comparación de proveedores del PDF difieren de la suma de cantidades por precios mostrados.**
5. **Las recepciones parciales están contempladas; la distribución de gastos de una orden entre esas recepciones no está suficientemente definida.** Es una decisión necesaria para evitar cobrar varias veces el mismo gasto al inventario.
6. **El PDF no especifica por completo las ampliaciones que hemos discutido:** consolidado como documento propio, adjudicación parcial con estados, recepción por grupos, cuarentena, reparto a sucursales y consulta pública por QR.

Estos puntos no significan que todo lo implementado esté mal. Por ejemplo, el código de retaceo revisado sí divide el costo entre la cantidad y sí separa el IVA de importación. El error del Excel no debe atribuirse automáticamente al sistema.

## 2. Fuentes y método

### Archivos analizados

- [MiniERP ERS v0.9 (2).pdf](<C:/Users/rodri/Downloads/MiniERP ERS v0.9 (2).pdf>): 103 páginas. Se extrajo y revisó el texto completo, con inspección visual de tablas y páginas clave. Las referencias siguientes utilizan la página del PDF.
- [Retaceo (4).xlsx](<C:/Users/rodri/Downloads/Retaceo (4).xlsx>): hojas **Retaceo** y **Datos**. Se revisaron todas las celdas con contenido, fórmulas, resultados guardados, rangos, validaciones y presentación.

Se recalcularon independientemente las **28 fórmulas** del libro: todas coinciden con sus resultados guardados, dentro de la tolerancia numérica empleada. Por tanto, no se encontró un caché de cálculo desactualizado; se encontraron omisiones y limitaciones del modelo de cálculo.

Los escenarios alternativos se calcularon fuera del archivo original. No se modificaron los dos documentos ni el código de la aplicación durante esta revisión.

Se distinguen tres clases de conclusión:

- **Hallazgo confirmado:** está directamente respaldado por una celda, fórmula, página o fragmento de código.
- **Ambigüedad documental:** faltan reglas suficientes para decidir una conducta única.
- **Propuesta:** mejora sugerida; no se presenta como una función ya implementada.

## 3. Qué contiene realmente la ERS

### 3.1 Organización y alcance

La portada dice **versión 0.6, borrador, julio de 2026**, pero su historial llega a **0.9, septiembre de 2026**, con retaceo, documentos, gastos y compras. Debe unificarse la versión de portada con la del contenido antes de usarla como referencia de entrega. **Fuente: p. 1.**

El alcance general enumera 20 módulos, pero el desarrollo detallado se concentra en ocho bloques:

| Bloque | Páginas | Contenido principal |
|---|---:|---|
| Seguridad y RBAC | 10–15 | Usuarios, roles, permisos y controles de acceso |
| Bitácora | 16–22 | Historial de operaciones, datos anteriores y nuevos, auditoría |
| Empresa | 23–26 | Datos de empresa, activación y separación de información |
| Sucursales | 27–30 | Relación con empresa y uso en documentos comerciales |
| Almacenes y ubicaciones | 31–35 | Almacenes por sucursal; pasillo, rack, nivel y posición |
| Proveedores y contactos | 36–43 | Datos, contactos, activación e historial |
| Productos | 44–59 | Identificación, categorías, imágenes y unidades |
| Gestión de compras y retaceo | 60–103 | Solicitud, cotización, orden, gastos, recepción y costo real |

El documento deja fuera contabilidad, nómina, activos fijos, producción, CRM, cuentas por cobrar/pagar, integración bancaria y facturación electrónica gubernamental. Por tanto, los dibujos de Banco, Pedidos en tránsito e IVA crédito fiscal del Excel no obligan, por sí solos, a construir un módulo contable completo. **Fuente: p. 5.**

Inventario y asignación de precios aparecen como integraciones preparadas o posteriores dentro del capítulo de compras. Tampoco deben confundirse 103 páginas de requisitos con una especificación completa de los 20 módulos anunciados. **Fuentes: pp. 63, 102–103.**

### 3.2 Reglas sólidas que conviene conservar

- Toda compra debe estar respaldada por una orden autorizada. **RN-006, p. 8.**
- Una orden puede recibirse parcialmente. La compra registra lo efectivamente recibido y conserva la referencia a cada línea de la orden. **pp. 75–78; CA-COM-017 a 019, p. 99.**
- Una cotización puede incluir demanda de distintas solicitudes, conservando las cantidades de origen. **pp. 68–70.**
- Una orden pertenece a un único proveedor. **pp. 72–73; CA-COM-012, p. 98.**
- El retaceo pertenece a una compra concreta. **pp. 79–80.**
- Los gastos se distribuyen proporcionalmente al FOB y el costo unitario se obtiene dividiendo el costo de la línea entre su cantidad. **p. 81; CA-COM-021 y 022, p. 99.**
- El IVA de importación se mantiene separado del costo del retaceo, también en reportes y procesos posteriores. **p. 82; CA-COM-024, p. 99.**
- Los comprobantes de gastos conservan su origen; no se deben duplicar archivos innecesariamente al avanzar en el proceso. **pp. 74–75, 97–98.**
- Los registros históricos se conservan y las operaciones críticas se auditan. La bitácora debe acompañar la transacción de negocio. **pp. 9, 22 y 99.**

## 4. Auditoría del Excel

### 4.1 Conciliación completa

| Concepto | Hoja Datos | Incluido en Retaceo |
|---|---:|---:|
| FOB | $55,780.00 — D4 | $55,780.00 — G10 |
| Seguro | **$1,250.00 — D5** | **No incluido** |
| Flete | $5,125.00 — D6 | $5,125.00 — G11 |
| DAI | $8,927.00 — D7 | $8,927.00 — I11 |
| Otros gastos | $1,500.00 — suma D9:D18 | $1,500.00 — I10 |
| Total sin IVA de importación | **$72,582.00** | **$71,332.00 — I19** |
| IVA de importación, separado | $8,367.00 — D8 | Excluido |

Los $1,500 de otros gastos se descomponen en: honorarios aduanales $250, fotocopias $5, gasolina $40, viáticos $90, almacenamiento $300, custodia $50, transporte $500, descarga $120, recarga $120 y otros $25. **No contienen el seguro.**

La diferencia exacta es:

**$72,582.00 − $71,332.00 = $1,250.00 de seguro.**

La hoja Datos calcula el CIF como FOB + seguro + flete: **$62,155.00**, en I2. También incluye el seguro en Pedidos en tránsito y en el inventario de L22. Es una inconsistencia entre hojas, no una diferencia de redondeo.

Si se mantiene el tratamiento que la propia hoja Datos da al seguro y se distribuye también por FOB, el resultado sería:

| Producto | Retaceo actual | Seguro proporcional adicional | Costo de línea con seguro |
|---|---:|---:|---:|
| Prensadora | $63,940.48 | $1,120.47 | **$65,060.95** |
| Camión | $7,391.52 | $129.53 | **$7,521.05** |
| Total | $71,332.00 | $1,250.00 | **$72,582.00** |

Esta es una conciliación matemática bajo el criterio del ejemplo, no una resolución fiscal sobre la capitalización de cualquier gasto.

**Relación con el PDF:** las pp. 81 y 101 repiten el ejemplo de $71,332 usando únicamente FOB, flete, gastos de $1,500 y DAI. Esa suma es correcta para esos conceptos. Lo que no concilia es el conjunto completo de costos que contiene la hoja Datos del Excel.

### 4.2 El costo unitario está mal definido en la fórmula

En Retaceo!I15 se utiliza:

```excel
=SUM(E15:H15)
```

La misma estructura se repite en I16:I18. La cantidad de D15:D18 nunca interviene. La fórmula obtiene el **costo total de la línea**, aunque el encabezado I14 dice “Costo Unitario”.

Ejemplo de sensibilidad, manteniendo el FOB de la línea en $50,000:

- Cantidad 1: total $63,940.48; unitario $63,940.48.
- Cantidad 2: total $63,940.48; unitario correcto **$31,970.24**.
- La fórmula actual seguiría mostrando **$63,940.48** como unitario.

La solución conceptual es conservar columnas separadas para **FOB total de línea**, **costo total de línea** y **costo unitario**. Este último se calcula como total de línea / cantidad positiva. No basta cambiar una etiqueta si después se suman costos unitarios como si fueran totales.

El PDF sí distingue costo unitario y total en su tabla de detalle, y define la división correspondiente. **Fuentes: pp. 81 y 91.**

### 4.3 Las hojas y los totales de entrada no están vinculados

Los valores de Retaceo!G10, G11, I10 e I11 están escritos como números. No provienen de fórmulas que consulten Datos. Los movimientos de Banco y Pedidos en tránsito también repiten importes manualmente.

Consecuencias:

- Cambiar el seguro, flete u otro gasto en Datos no actualiza automáticamente Retaceo.
- El FOB del encabezado, G10, puede diferir de la suma de líneas, E19.
- El denominador del reparto sigue siendo G10 aunque se cambien o agreguen productos.

Por ejemplo, si las líneas pasan de $55,780 a $60,780 de FOB y G10 permanece en $55,780, la fórmula asignaría **$16,946.05** de costos adicionales cuando solo existen **$15,552.00** para distribuir. Se crearían **$1,394.05** de costo por la inconsistencia del denominador.

Debe existir una única fuente para cada importe, y el FOB usado como base debe conciliar con las líneas elegibles.

### 4.4 Cero, rangos y controles

- Las fórmulas `IF(G10>0, importe/G10, 0)` asignan cero gasto si el FOB del encabezado no es positivo. Si existen costos por distribuir, ese resultado oculta una situación que requiere corrección o una regla alternativa explícita.
- Los totales abarcan las filas 15 a 18. Escribir productos fuera de ese rango no garantiza su inclusión. La hoja Retaceo no tiene una tabla estructurada que extienda automáticamente el modelo.
- No hay validaciones de datos que impidan cantidades negativas, cantidad cero o importes incoherentes.
- Las hojas no tienen protección activada para separar entradas de fórmulas.
- No hay área de impresión definida. Esto no demuestra por sí solo un fallo de impresión, pero deja el resultado dependiente de la configuración utilizada al imprimir.

Estas son limitaciones de una plantilla de ejemplo. Para un sistema transaccional deben convertirse en validaciones de servidor, además de ayudas visuales.

### 4.5 IVA y porcentajes

Datos!G2 contiene **15%** y D8 calcula `D4*G2`, es decir, 15% solo sobre FOB: **$8,367**. La ERS ordena excluir el IVA de importación del retaceo, pero no establece esa tasa ni esa base de cálculo. No hay fundamento documental suficiente para convertir el 15% y la base FOB en una regla fiscal permanente.

Además, G22, bajo IVA crédito fiscal, contiene $8,367 como número fijo. No se actualiza al cambiar D8.

Los porcentajes de los encabezados F14:H14 son razones entre un costo total y el FOB. El “DAI 16.00%” es la presentación redondeada de $8,927 / $55,780. **No demuestra una tasa arancelaria aplicable por producto.** El propio PDF pide calcular estos porcentajes dinámicamente. **p. 91.**

El esquema de Banco tampoco permite verificar un asiento contable completo: omite el desembolso correspondiente al IVA mostrado como crédito fiscal. Puede ser un esquema didáctico parcial; no debe presentarse como una conciliación bancaria o contable terminada.

## 5. Inconsistencias y decisiones pendientes en la ERS

### 5.1 Error aritmético en la comparación de proveedores

Las pp. 88–89 muestran 5 laptops, 10 mouse y 10 teclados. Usando exclusivamente los precios publicados:

| Proveedor | Operación | Total calculado | Total publicado | Diferencia publicada |
|---|---|---:|---:|---:|
| A | 5×800 + 10×15 + 10×20 | **$4,350** | $4,450 | +$100 |
| B | 5×780 + 10×13 + 10×19 | **$4,220** | $4,240 | +$20 |
| C | 5×825 + 10×14 + 10×18 | **$4,445** | $4,405 | −$40 |

La tabla no explica impuestos, gastos o descuentos que justifiquen esas diferencias. Si existieran ajustes, deben mostrarse. En caso contrario, deben corregirse los totales. El ejemplo no es una base numérica fiable para una prueba automatizada tal como está.

### 5.2 Momento de ingreso y disponibilidad de inventario

RN-009 afirma que una compra incrementa automáticamente el inventario. Después, las pp. 63 y 102 describen una integración preparada, en la que una compra registrada y verificada entrega información a Inventario, responsable de actualizar existencias.

Hace falta definir qué evento significa cada cosa:

1. Registrar una compra o recepción.
2. Confirmar lo contado físicamente.
3. Verificar lo aceptado y lo rechazado.
4. Registrar existencia física en recepción o cuarentena.
5. Ubicar y liberar existencia disponible.
6. Incorporar o ajustar su valoración con el retaceo.

**Recomendación para el flujo que hemos discutido:** mostrar por separado recibido, en cuarentena, disponible y en tránsito. Guardar o recalcular costos no debe crear otra entrada física. Un mismo ingreso debe quedar registrado una sola vez, aunque cambie posteriormente su valoración.

### 5.3 Recepciones parciales y gastos compartidos

La ERS permite varias compras/recepciones para una orden y asigna gastos a la orden. Cada retaceo pertenece a una compra. No define cuánto de un gasto compartido consume cada recepción.

Ejemplo: orden de 100 cajas con $100 de flete; llegan 60 y después 40. Si cada recepción carga los $100 completos, el inventario absorbe $200 aunque el gasto real sea $100.

Debe definirse si el gasto pertenece a toda la orden, a un envío o a una recepción concreta. Para gastos compartidos debe mantenerse un saldo asignable y una regla de distribución. Para gastos propios de un envío, la relación debe identificar ese envío. No conviene imponer 60/40 automáticamente cuando los productos tienen valores FOB distintos o el gasto corresponde a otra base aprobada.

También faltan reglas para cancelación de una recepción ya costeada, gastos tardíos y correcciones después de liberar inventario.

### 5.4 Unidades de compra, venta e inventario

El PDF distingue unidades de compra y de venta, y ejemplifica comprar cajas y vender unidades. Sin embargo, no define el factor de conversión por producto, su vigencia ni el redondeo. **pp. 44–59, 96–97.**

Es insuficiente saber que una solicitud dice “10 cajas” si el inventario maneja unidades base. Deben conocerse producto, presentación y equivalencia. Una caja no tiene la misma cantidad para todos los productos.

Debe conservarse la unidad de origen y su conversión en cada documento para evitar que una modificación posterior del catálogo altere el significado histórico de una compra o traslado. Esta carencia documental explica la importancia de los avisos de conversión que aparecieron durante el uso del sistema; no prueba por sí sola que una conversión concreta esté mal implementada.

### 5.5 Consolidación, adjudicación y estados

El documento contempla múltiples solicitudes por cotización y cantidades repartidas entre proveedores, pero no desarrolla un documento de consolidado con sus propias transiciones ni una entidad completa de adjudicación parcial. **pp. 68–70 y 86.**

Conviene precisar:

- Cantidad solicitada, incluida en consolidado, adjudicada, ordenada, recibida, aceptada y pendiente.
- Qué cantidad corresponde a una sucursal y qué cantidad es reserva adicional de la central.
- Qué significa una oferta parcialmente adjudicada.
- Cuándo termina la evaluación de una cotización y cuándo se cierra un consolidado.
- Cómo se evita ordenar dos veces una adjudicación y cómo se trata una orden cancelada.

Los estados `selected` y `under_review` de la cotización no bastan para describir todas esas situaciones. Una cotización con algunas líneas ganadoras y otras descartadas necesita cantidades y estados por línea, además de un resumen del documento.

El cierre tampoco debe utilizarse como sinónimo de cancelación. La regla de cierre debe comprobar la demanda relevante y sus movimientos vinculados, no solamente buscar una etiqueta general de “aprobada”.

### 5.6 Bodega central y acceso por QR

El modelo de almacenes exige que todo almacén pertenezca a una sucursal; las reglas comerciales también exigen asociación con sucursal. **RN-WHS-001, pp. 31–35; RN-BRA-007, pp. 27–30.** Una central independiente de sucursales, como la que se ha trabajado, debe documentarse como ampliación: propietario empresa, sucursal opcional y permisos compatibles con ambos casos.

RN-001 exige autenticación para acceder al sistema. Una ficha QR que pueda abrirse sin sesión es otra ampliación que necesita alcance explícito: datos públicos autorizados, datos reservados y operaciones que siguen requiriendo permisos. Abrir una pestaña nueva y permitir acceso público son comportamientos distintos. **p. 8.**

El PDF tampoco describe el flujo completo de traslado, conteo, cuarentena, ubicación final y liberación de una sucursal. Estas funciones pueden existir en el ERP, pero su aceptación requiere especificaciones adicionales.

### 5.7 Dinero, trazabilidad y seguridad documental

- **FOB cero:** RN-COM-025 permite FOB mayor o igual a cero, pero la distribución divide entre FOB total. Debe diferenciarse una línea de FOB cero de una compra cuyo FOB total es cero. **pp. 81 y 86.**
- **Redondeo:** no se fija precisión de importes, de cantidades o de costo unitario, ni cómo se distribuye un residuo. El total asignado debe coincidir exactamente con el gasto.
- **Descuentos e impuestos:** la p. 82 combina descuentos de línea y descuento global sin completar sus reglas de base imponible y distribución. Debe evitarse descontar dos veces o recalcular impuestos sobre una base incorrecta.
- **Monedas:** se registran monedas, pero no se define cómo combinar gastos en otra moneda ni qué tipo de cambio histórico conservar. No se pueden sumar dólares y otra moneda como si fueran equivalentes.
- **Trazabilidad por línea:** el modelo vincula la orden a una cotización y el retaceo a una compra, pero no especifica todas las claves de detalle necesarias para rastrear líneas repetidas, parciales y diferentes lotes. La regla textual es más completa que algunos diagramas/tablas.
- **Verificación:** se propone el estado `verified` para compras, pero el catálogo de permisos de compras de la p. 92 no enumera una operación de verificación. Debe aclararse qué permiso autoriza esa transición.
- **Bitácora y accesos fallidos:** se exige registrar accesos y bloquear tras cinco fallos, mientras la p. 22 exige usuario autenticado antes de registrar el evento. Debe diferenciarse auditoría de negocio de eventos de autenticación fallida.
- **Datos de auditoría:** registrar cambios de usuarios no debe implicar almacenar contraseñas, hashes o credenciales dentro de los JSON históricos. Hace falta una política de campos excluidos.
- **Requisitos no funcionales:** el documento menciona seguridad y escalabilidad, pero no aporta criterios suficientes de rendimiento, concurrencia, recuperación, tamaño de adjuntos o disponibilidad para una aceptación objetiva.

## 6. Contraste puntual con el código actual

Esta sección es una lectura de archivos concretos. No se ejecutaron operaciones de compra ni una prueba integral del ERP.

| Aspecto | Evidencia del código revisado | Conclusión |
|---|---|---|
| Distribución de gastos detallados | El editor indica distribución manual; el caso de uso selecciona el cálculo manual cuando recibe `costs` | Hay una diferencia con el reparto proporcional exigido por CA-COM-021. Puede ser una adaptación deliberada, pero debe conciliarse con la ERS |
| Costo unitario | El dominio divide total entre cantidad | No reproduce el defecto de la columna del Excel |
| Precisión y reparto proporcional | Existe una función proporcional con distribución de residuos y precisión decimal de seis posiciones | Hay una base reutilizable para ofrecer cálculo automático coherente |
| IVA de importación | El modelo distingue la clase de costo `import_vat` | Existe separación explícita; debe mantenerse en pantallas y reportes |
| Gastos de la orden al crear retaceo | `_source_costs` copia el importe completo de cada gasto de la orden | Riesgo a verificar con recepciones parciales; no se demuestra aquí su resultado operativo completo |
| Unicidad del gasto importado | El índice combina retaceo y gasto de origen | Evita repetirlo dentro del mismo retaceo; por sí solo no limita lo asignado entre varios retaceos |
| Metadatos de importación | No aparecen campos explícitos de país de origen o póliza de importación en la entidad y tipo frontend revisados | Verificar su disponibilidad en otras entidades/pantallas o documentar la desviación de pp. 79 y 90–91 |
| Guardar borrador | El componente contiene navegación al detalle del retaceo después del guardado | La redirección está expresada en el código; esta revisión no certifica su ejecución en un navegador |

Referencias del repositorio:

- [Editor de retaceo: descripción del reparto manual](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/retaceos/components/RetaceoDraftEditor.svelte:522).
- [Elección de algoritmo de distribución](C:/Developer/GESTIONASV_ERP/backend/app/application/retaceos/use_cases.py:296).
- [Cálculo del costo unitario](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/retaceo.py:258).
- [Reparto proporcional y tratamiento del residuo](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/retaceo.py:275).
- [Importación de gastos de la orden](C:/Developer/GESTIONASV_ERP/backend/app/application/retaceos/use_cases.py:374).
- [Índice de gastos importados](C:/Developer/GESTIONASV_ERP/backend/app/infrastructure/models/retaceo.py:254).
- [Entidad de retaceo](C:/Developer/GESTIONASV_ERP/backend/app/domain/entities/retaceo.py:417) y [tipo del frontend](C:/Developer/GESTIONASV_ERP/frontend/src/lib/types/retaceo.ts).
- [Navegación después de guardar](C:/Developer/GESTIONASV_ERP/frontend/src/lib/features/retaceos/components/RetaceoDraftEditor.svelte:355).

**Propuesta concreta:** ofrecer “Distribuir por FOB” como comportamiento automático previsto por la ERS. Si se conserva la distribución manual, tratarla como una opción de negocio explícita y trazable, con validación de sumas y motivo cuando corresponda. No hace falta eliminar el trabajo de gastos y comprobantes ya realizado para lograrlo.

## 7. Flujo que se desprende de los documentos y de tus comentarios

### 7.1 Después de adjudicar

Una precisión sobre la explicación anterior: **consolidar reúne demanda; adjudicar selecciona la oferta o proveedor y la cantidad que se le comprará.** La distribución de mercancía recibida a sucursales pertenece al abastecimiento posterior.

El siguiente paso después de confirmar adjudicaciones debe ser **preparar órdenes de compra de esas adjudicaciones**, conservando proveedor, cantidades, precios y origen.

Ejemplo: un consolidado termina con productos adjudicados al proveedor A y otros al proveedor B. El sistema prepara al menos una orden para A y otra para B, porque cada orden tiene un único proveedor. Si cambian moneda, destino, condiciones o reglas de agrupación, puede requerirse más de una orden para un mismo proveedor.

La navegación recomendada es:

**Comparar ofertas → Adjudicar → Revisar órdenes preparadas por proveedor → Aprobar → Registrar envío al proveedor.**

La ERS exige poder generar la orden desde la cotización seleccionada. La redirección automática a esa preparación es una mejora de experiencia; no está prescrita literalmente en el PDF. Automatizar la preparación no equivale a aprobar o enviar órdenes sin la acción y el permiso correspondientes.

Si solo se adjudicó parte del consolidado, deben verse las órdenes preparadas y la demanda pendiente. No se debe volver a pedir lo que ya quedó cubierto por órdenes válidas.

### 7.2 Recepción por grupos

Tu propuesta es compatible con el proceso, pero debe distinguir una selección en grupo de la identidad de cada recepción.

Flujo sugerido:

1. Filtrar órdenes autorizadas con cantidades pendientes y seleccionar varias.
2. Mostrar productos, proveedor, orden, destino, unidad y saldo pendiente.
3. Registrar lo contado y lo aceptado/rechazado por línea.
4. Crear las recepciones correspondientes preservando cada orden de origen.
5. Mostrar un resultado por orden y un resumen de la operación en grupo.

El modelo del PDF asocia cada compra a una sola orden. Por ello, seleccionar tres órdenes puede generar tres recepciones coordinadas, sin convertirlas en una compra que pierda su procedencia. Si se desea una sola recepción física que abarque varias órdenes, se necesita un encabezado de lote/envío y relaciones adicionales.

RN-LOG-008 ya pide que las operaciones masivas tengan un evento principal y detalle por registro. Eso aporta una base para la auditoría del grupo. **pp. 16–22.**

Queda por especificar qué ocurre si una de las órdenes falla: revertir todo el grupo o conservar las recepciones válidas con un resultado claro. También hay que impedir que dos usuarios consuman simultáneamente el mismo pendiente.

### 7.3 Guardar, calcular y cerrar retaceo

La ERS propone estados distintos: borrador, calculado, verificado, cerrado y cancelado. **p. 87.**

La navegación que pediste es coherente con ellos:

**Guardar borrador → abrir detalle/cálculo → calcular → revisar/verificar → cerrar.**

Guardar debe conservar datos y llevarte al siguiente paso. No debe afirmar “calculado” o “verificado” solo por haber guardado. Si faltan distribuciones o comprobantes exigidos por la implementación, la pantalla de cálculo debe explicar exactamente cuáles faltan.

### 7.4 Desde la central hasta la sucursal

Como ampliación funcional, el flujo operativo propuesto es:

**Recepción central → conteo y verificación → ubicación/liberación → existencias disponibles → distribución por sucursal → despacho → en tránsito → recepción contada en sucursal → verificación/ubicación → disponible.**

El retaceo determina costos de adquisición. Los traslados internos conservan su trazabilidad y no deben volver a tratar la mercancía como una compra nueva.

Para preparar despachos, la pantalla puede comenzar por productos realmente disponibles, tal como pediste. Al abrir un producto debe mostrar su demanda vinculada por sucursal, lo ya despachado, lo pendiente y la reserva central. Una solicitud aprobada no acredita por sí sola existencia física.

## 8. Matriz de los 27 criterios de aceptación de compras

Esta matriz resume lo que debe demostrarse. **No marca cumplimiento del ERP**, porque para ello faltaría ejecutar pruebas y revisar todos los módulos involucrados. Referencias originales: pp. 98–99.

| Criterios | Obligación | Evidencia necesaria para aceptación |
|---|---|---|
| CA-COM-001 a 004 | Solicitudes con productos, cantidades positivas, sucursal y almacén | Crear una solicitud válida y rechazar cantidades/destinos inválidos |
| CA-COM-005 y 006 | Varias cotizaciones por solicitud y una cotización con distintos orígenes | Mantener origen y cantidad por línea al agrupar demanda |
| CA-COM-007 y 008 | Precios, descuentos, impuestos, tiempos y disponibilidad por proveedor | Conservar ofertas distintas sin mezclar sus condiciones |
| CA-COM-009 y 010 | Comparar y seleccionar oferta/proveedor | Totales correctos y selección rastreable |
| CA-COM-011 a 013 | Orden desde cotización, un proveedor, referencia de origen | Ordenar cantidades adjudicadas y evitar duplicados |
| CA-COM-014 a 016 | Gastos de cotización/orden y documentos de respaldo | Importes conciliados y documentos accesibles desde su gasto |
| CA-COM-017 a 019 | Compra desde orden, parcialidad y relación de detalles | Recibir 60 y luego 40 de 100 sin duplicar cantidad ni perder origen |
| CA-COM-020 | Retaceo asociado a compra | Identificar exactamente la recepción costeada |
| CA-COM-021 | Reparto proporcional al FOB | Recalcular y conciliar cada gasto con sus asignaciones |
| CA-COM-022 | Costo unitario | Dividir entre cantidades distintas de 1 y conservar total de línea |
| CA-COM-023 | Porcentajes calculados | Recalcular al cambiar importes, sin usarlos como tasas fijas |
| CA-COM-024 | IVA de importación fuera del retaceo | Separación en cálculo, detalle, impresión y costo utilizado después |
| CA-COM-025 | Trazabilidad integral | Navegar solicitud → cotización → orden → compra → retaceo por documento y línea |
| CA-COM-026 | Auditoría de operaciones críticas | Actor, fecha, origen y cambios, incluyendo operaciones por grupo |
| CA-COM-027 | Conservación histórica | Impedir borrado físico de documentos utilizados |

## 9. Prioridades sugeridas

### Prioridad alta: integridad de cantidades y costos

1. Acordar y documentar el reparto proporcional al FOB como regla base; conciliarlo con el editor manual.
2. Resolver la omisión del seguro en el ejemplo y separar costo unitario de costo total.
3. Definir la distribución de gastos compartidos entre recepciones parciales y comprobar que no se dupliquen.
4. Formalizar conversiones por producto y cantidades pendientes por línea.
5. Definir el evento que registra existencia física, su disponibilidad y su valoración, evitando entradas duplicadas.

### Prioridad siguiente: continuidad del flujo

6. Llevar la adjudicación a preparación de órdenes con datos heredados y control contra duplicados.
7. Implementar la recepción por grupos conservando la recepción de cada orden y su resultado.
8. Mantener navegación clara de guardar a calcular retaceo, con mensajes accionables.
9. Formalizar cierres y estados parciales de consolidado/cotización sin confundirlos con cancelación.

### Documentación y presentación

10. Actualizar portada y corregir el ejemplo de comparación.
11. Acordar los campos de importación que son obligatorios, opcionales o provenientes de otro documento.
12. Documentar las ampliaciones de central independiente, cuarentena, traslados y consulta QR.
13. Definir tasas/bases fiscales desde sus soportes, precisión monetaria y criterios no funcionales medibles.

## 10. Casos que deberían integrar la próxima validación

Estos son casos propuestos, no resultados de pruebas del ERP realizadas en esta revisión:

| Caso | Resultado esperado |
|---|---|
| Ejemplo original sin seguro | Total de $71,332 con costos conciliados por línea |
| Mismo ejemplo incorporando seguro | Total de $72,582 bajo el mismo reparto por FOB |
| Dos unidades y FOB total de línea $50,000 | Unitario de $31,970.24 con los costos originales, no $63,940.48 |
| Cambio en FOB de una línea | Recalcular denominador, proporciones y totales desde la misma fuente |
| FOB total cero con gastos positivos | Bloqueo explicado o método alternativo expresamente autorizado |
| Reparto con residuo decimal | Asignaciones suman exactamente el gasto; política reproducible |
| Orden de 100, recepciones de 60 y 40 | Total recibido 100, gasto compartido asignado una sola vez |
| Dos usuarios reciben el mismo pendiente | Solo se consume la cantidad aún disponible de la orden |
| Adjudicación a dos proveedores | Órdenes separadas por proveedor, conservando fuentes |
| Repetir “generar orden” | No duplicar cantidades ya ordenadas |
| Compra en caja e inventario en unidad | Conversión correcta y registrada, sin asumir equivalencia 1:1 |
| IVA de importación informado | Visible por separado; no incrementa el costo del retaceo |
| Operación por grupo con una línea inválida | Resultado inequívoco según política de atomicidad definida |
| Guardar borrador de retaceo | Persistir y abrir detalle/cálculo; estado permanece borrador hasta calcular |
| Recalcular costo de mercancía recibida | Actualizar valoración según política sin duplicar existencia física |

## Conclusión

La ERS respalda el proceso principal y varias de las mejoras que han señalado tus compañeros. Sus puntos más claros son el origen documental, las recepciones parciales, el costo proporcional al FOB y la trazabilidad. Sus mayores vacíos están en los cruces entre procesos: adjudicación parcial, gastos compartidos, conversiones y el momento en que lo recibido queda disponible.

El Excel sirve para explicar el reparto, pero **no debe copiarse literalmente como cálculo definitivo**: omite el seguro y no calcula un costo unitario general. El siguiente trabajo debería partir de las reglas corregidas, reutilizando lo implementado que sí las cumple.

No es necesario rehacer todo el sistema. Sí hace falta cerrar estas reglas y comprobarlas con cantidades distintas de 1, varias recepciones y varios proveedores antes de afirmar cumplimiento completo.

---

**Evidencia técnica de esta revisión:** [resultados de la comprobación matemática](C:/Developer/GESTIONASV_ERP/tmp/document-review-20261012/math-audit.json) y [script de cálculo independiente](C:/Developer/GESTIONASV_ERP/tmp/document-review-20261012/audit_math.py).

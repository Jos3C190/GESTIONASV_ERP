# Manual: protección de datos personales

La Ley para la Protección de Datos Personales (D.L. 144/2024, reformada por el D.L.
659/2026) obliga a la empresa a informar a sus clientes cómo trata sus datos, a pedir su
consentimiento para los usos que no son necesarios, a responder sus solicitudes y a
reportar las vulneraciones de seguridad. El sistema lleva el registro de todo eso.

Pantalla: **Administración → Datos personales**, con tres pestañas: **Aviso de
privacidad**, **Solicitudes** y **Vulneraciones**.

| Permiso | Qué permite |
|---|---|
| `privacy:read` | Consultar el aviso, las solicitudes y las vulneraciones. |
| `privacy:manage` | Publicar el aviso, registrar y tramitar solicitudes, exportar los datos de un cliente y registrar vulneraciones. |
| `privacy:erase` | Anonimizar a un cliente que lo pidió. |

Los consentimientos se registran en la ficha del cliente con los permisos de clientes
(`sales_customers:read` para verlos y `sales_customers:manage` para registrarlos o
revocarlos).

## Aviso de privacidad

El aviso se informa al cliente antes de recolectar sus datos. Sin aviso publicado no se
pueden registrar consentimientos.

1. Pulsa **Redactar el aviso** o **Publicar nueva versión**.
2. El sistema propone un texto con el nombre, la dirección, el correo y el teléfono de la
   empresa. Revísalo y ajústalo a cómo la empresa trata los datos.
3. Marca los nueve elementos que exige el art. 24: identidad y domicilio del responsable,
   datos que se tratan, fundamento legal, finalidades, derechos y revocación, medios para
   ejercerlos, cómo se comunican los cambios, encargado del tratamiento y uso de cookies.
4. Pulsa **Publicar**. El botón se habilita solo cuando están marcados los nueve.

Cada publicación crea una versión nueva; las anteriores se conservan en **Ver versiones
anteriores**. Un aviso publicado no se edita.

## Consentimientos del cliente

Pantalla: **Clientes → (cliente)**, sección **Consentimientos**.

Los datos necesarios para venderle y facturarle no requieren consentimiento (art. 28). Sí
lo requieren estos usos:

- **Promociones y novedades.**
- **Análisis de preferencias de compra.**
- **Compartir datos con terceros.**

Para registrarlo pulsa **Registrar consentimiento**, elige el uso y cómo lo dio el cliente
(en persona, teléfono, correo, sitio web o por escrito). Se guarda la versión del aviso que
estaba vigente. Un uso ya autorizado no aparece de nuevo en la lista.

Si el cliente lo retira, pulsa **Revocar** e indica cómo lo pidió. El uso debe dejar de
aplicarse en un máximo de 5 días hábiles.

## Solicitudes de los titulares

Los titulares pueden pedir acceso, rectificación, cancelación, oposición, portabilidad,
olvido o limitación del tratamiento de sus datos (derechos ARCO-POL).

1. Pulsa **Registrar solicitud** e indica el derecho, la fecha en que se recibió, quién la
   presenta, el medio para responderle y qué pide. Si es cliente, búscalo en **Cliente
   relacionado**. Puedes asignar un responsable.
2. El sistema calcula el vencimiento: **20 días hábiles** desde el día siguiente a la
   recepción. No cuenta sábados, domingos ni los feriados del Código de Trabajo (1 de enero,
   Jueves, Viernes y Sábado Santo, 1 y 10 de mayo, 17 de junio, 6 de agosto, 15 de
   septiembre, 2 de noviembre y 25 de diciembre).
3. Abre la solicitud y elige la acción:
   - **Iniciar trámite.**
   - **Pedir corrección al titular**, si falta información. Le da 10 días hábiles; si no
     corrige, se puede **Archivar** al vencer ese plazo.
   - **Prorrogar 20 días hábiles**, una sola vez y con causa justificada.
   - **Responder y cerrar**, **Denegar** (con resolución motivada) o **Devolver**.

Las solicitudes vencidas se marcan **Vencida** en la bandeja.

### Acceso y portabilidad

Con un cliente relacionado, **Descargar datos del cliente** genera un archivo JSON con sus
datos, direcciones de entrega, consentimientos, cotizaciones y ventas. La descarga queda
en la bitácora.

### Cancelación y olvido

Con el permiso `privacy:erase`, **Anonimizar al cliente**:

- reemplaza el nombre por «Titular anonimizado CLI-…»;
- borra documento, contacto, dirección, vendedor y direcciones de entrega;
- revoca sus consentimientos y lo desactiva.

No se puede deshacer. Las cotizaciones, ventas y documentos fiscales ya emitidos se
conservan porque la ley tributaria obliga a guardarlos. Después, registra la respuesta con
**Responder y cerrar**. La ficha del cliente anonimizado muestra un aviso y ya no se edita.

## Vulneraciones de seguridad

Una vulneración es un acceso indebido, una pérdida o una filtración de datos personales.
Se notifica a la Agencia de Ciberseguridad del Estado, a la Fiscalía General de la
República y a los titulares afectados dentro de **72 horas** desde que se descubre (art.
25).

1. Pulsa **Registrar vulneración** e indica cuándo se descubrió, qué pasó, qué datos se
   comprometieron, cuántos titulares aproximadamente y las medidas tomadas.
2. Registra cada notificación con su fecha y referencia. Si no se notifica a los titulares,
   explica por qué.
3. Mientras falte alguna notificación, la vulneración muestra **Falta notificar a:** y, pasado
   el plazo, **Notificación vencida**.
4. Con todo registrado, pulsa **Cerrar**. Una vulneración cerrada ya no se edita.

## Datos de demostración

Grupo Lorena tiene publicado el aviso de privacidad versión 1, así que se pueden registrar
consentimientos desde el primer momento.

# Manual: configuración fiscal del emisor

Pantalla: **Ventas → Configuración fiscal** (`/sales/fiscal-settings`).
Permisos: `fiscal_settings:read` para consultar y `fiscal_settings:manage` para cambiar.

Aquí se configura con qué datos emite **la empresa activa** sus documentos tributarios
electrónicos (DTE). La pantalla solo muestra la configuración de esa empresa; la interfaz
no hace referencia a otras empresas.

Todavía no se emiten documentos desde esta pantalla. Esta configuración es la base que usarán
la facturación y el punto de venta en los bloques siguientes.

## 1. Emisor

- **Datos de la empresa.** La razón social, el nombre comercial, el NIT y el NRC se muestran
  aquí, pero se editan en la ficha de la empresa.
- **Modo de operación.**
  - *Simulado*: documentos sin validez fiscal, para capacitación y demostraciones.
  - *Pruebas de Hacienda*: documentos enviados al ambiente de pruebas para la certificación.
  - *Producción*: documentos con validez fiscal.
- **Categoría de contribuyente, tipo de persona, correo y teléfono** que aparecen en el DTE.
- **Requisitos de producción.** Mientras la empresa no esté en producción, un aviso enumera
  lo que falta para pasar a ese modo. Pasar a producción pide confirmación.

## 2. Actividades

Registra todas las actividades económicas de la empresa, buscándolas por código o por nombre
en el catálogo de Hacienda (CAT-019).

- La primera actividad que registres queda como **principal**.
- Puedes cambiar cuál es la principal en cualquier momento.
- Una actividad que usa un establecimiento no se puede quitar: primero cámbiala en el
  establecimiento.

## 3. Establecimientos

Cada sucursal que opera ante Hacienda es un **establecimiento**, y cada caja es un **punto de
venta**. Sus códigos forman el número de control del documento: `DTE-01-S001P001-…`.

| Tipo | Letra | Ejemplo |
|---|---|---|
| Casa matriz | M | M001 |
| Sucursal | S | S001 |
| Bodega | B | B001 |
| Patio | P | P001 |

- Cada sucursal puede ser solo un establecimiento. Al registrarlo, la pantalla sugiere el
  siguiente código libre del tipo elegido.
- El código es único dentro de la empresa.
- El DTE lleva la **dirección de la sucursal** donde se hizo la operación, con sus códigos de
  departamento, municipio y distrito de Hacienda. Si una sucursal no tiene esos códigos, la
  tarjeta lo avisa y la dirección se corrige en **Sucursales**.
- La **actividad del establecimiento** es la que llevarán sus operaciones; si no eliges una,
  se usa la principal de la empresa.
- Las cajas usan la letra P y tres dígitos (P001). El código es único dentro de su
  establecimiento.
- Un establecimiento o una caja inactivos dejan de emitir documentos.

## 4. Documentos

Lista los 13 tipos del catálogo de Hacienda (CAT-002), incluidos los eventos de operaciones
especiales y de retorno.

- **Habilitado**: las pantallas de venta solo ofrecerán los documentos habilitados.
- **Pruebas ante Hacienda**: el avance de la certificación de cada tipo. Puede estar sin
  iniciar, en pruebas o aprobado; al aprobarlo se guarda la fecha.
- En *simulado* y *pruebas* puedes habilitar cualquier documento para probarlo.
- En *producción* solo se habilita un documento cuyas pruebas estén aprobadas.

## 5. Correo

Los documentos tributarios se envían a los clientes desde el servidor de correo y el dominio de la
empresa.

1. Escribe el **servidor SMTP**, la **seguridad** y el **puerto** que te da tu proveedor de correo.
   Al elegir la seguridad se propone su puerto: STARTTLS 587, SSL 465.
2. Escribe el **usuario** y la **contraseña**. La contraseña se guarda cifrada y nunca se vuelve a
   mostrar; para cambiarla, escribe otra. Si la dejas vacía al editar, se conserva.
3. Escribe el **correo del remitente** y, si quieres, el **nombre del remitente** (por defecto, el
   nombre comercial).
4. **Guardar** y luego **Enviar correo de prueba** a tu propio correo. La pantalla guarda el
   resultado de la última prueba; cambiar la conexión la borra.

Con **Enviar los documentos con este correo** desmarcado, o con **Quitar**, los documentos salen
con el correo del servidor si existe; si no, no se envían por correo.

Proveedores comunes:

| Proveedor | Servidor | Seguridad y puerto | Usuario y contraseña |
|---|---|---|---|
| Google (Gmail o Workspace) | smtp.gmail.com | STARTTLS 587 | El correo y una contraseña de aplicación (requiere verificación en dos pasos). |
| Microsoft 365 | smtp.office365.com | STARTTLS 587 | El correo y su contraseña, con «SMTP autenticado» activado en el buzón. |
| Hosting del dominio | El que indique el proveedor | Normalmente STARTTLS 587 o SSL 465 | Los del buzón. |

**El dominio es responsabilidad de la empresa.** Para que Gmail y Outlook no manden los
documentos a spam, el dominio del remitente debe tener SPF, DKIM y DMARC configurados en su DNS.
Los proveedores de correo indican cómo hacerlo al dar de alta el dominio.

## Reglas que protegen a una empresa en producción

Una empresa en producción no puede quedar sin poder emitir. Por eso se rechaza, sin guardar
nada, cualquier cambio que la deje sin alguno de estos requisitos:

- NIT y NRC.
- Actividad principal.
- Un establecimiento activo con al menos una caja activa.
- Al menos un documento habilitado, con todos los habilitados aprobados.

Ejemplos de cambios que se rechazan: desactivar el único establecimiento o deshabilitar el
único documento.

## Datos de demostración

Grupo Lorena queda configurada en modo simulado:

- **Actividades**: 10712, fabricación de pan, como principal, y 47215, venta al por menor de
  panadería.
- **Establecimientos**: la casa matriz es M001 y cada pastelería es S001 a S007, cada uno con
  su caja P001.
- **Documentos habilitados**:
  - 01, factura;
  - 03, comprobante de crédito fiscal;
  - 04, nota de remisión;
  - 05, nota de crédito;
  - 06, nota de débito.

## Bitácora

Cada cambio queda en la bitácora con usuario, fecha, valores anteriores y nuevos. Los
recursos registrados son:
- `fiscal_profile`
- `fiscal_activity`
- `fiscal_establishment`
- `fiscal_point_of_sale`
- `fiscal_document_type`

# Manual: libros de IVA y anexos del F-07

En **Ventas → Libros de IVA** están, por empresa y mes, los tres libros de IVA (Código Tributario,
art. 141) y los anexos de la declaración mensual de IVA (F-07) listos para el portal de Hacienda.

## 1. De dónde salen

- **Ventas**: solo de los documentos fiscales sellados (o simulados), con los montos del JSON tal
  como se selló. Nunca de los pedidos.
- **Compras**: de las compras recibidas que tienen registrado el **documento del proveedor**
  (sección 4). Las que no lo tienen aparecen en la pestaña **Compras pendientes** y no entran.
- Un mes es de **producción** o de **simulado**, nunca mezcla los dos. Si la empresa factura en
  simulado, la pantalla lo avisa y los archivos llevan `_SIMULADO` en el nombre: el portal los
  rechaza, así que no hay riesgo de cargarlos por error.

## 2. La pantalla

1. Elige el **mes** (por omisión, el anterior, que es el que se declara) y **Consultar**.
2. Arriba, el **resumen**: débito fiscal, crédito fiscal, percepción del 1 % cobrada e impuesto
   del mes (débito − crédito + percepción). No incluye remanentes, retenciones que le hicieron a la
   empresa ni anticipos, que el ERP no registra.
3. Las pestañas:
   - **Contribuyentes**: créditos fiscales y notas de crédito y de débito vigentes. En el libro la
     nota de crédito resta.
   - **Consumidor final**: facturas agrupadas por día, con el primer y el último número de control.
     En rojo, las filas negativas (ver sección 3).
   - **Compras**: libro de compras.
   - **Anexos F-07**: cada archivo con su nombre y sus filas tal como se cargan.
   - **Compras pendientes**: compras recibidas del mes sin documento del proveedor; desde aquí se
     registra.
4. **Descargas**:
   - **Excel del mes**: resumen, los tres libros con el encabezado de la plantilla (nombre, mes,
     año, folio, NIT y NRC) y totales, y los anexos con las celdas en formato Texto.
   - **ZIP del F-07**: los CSV para el portal, el Excel y un LEEME con qué archivo va en qué
     pestaña.
   - **PDF** de cada libro: carta horizontal, numerado desde el **folio inicial** que se indique,
     con totales y línea para la firma del contador.

## 3. Reglas entre meses

| Caso | Qué hace |
|---|---|
| Crédito fiscal o nota invalidados | Salen del anexo 1 de su mes y van a anulados de ese mes. |
| Factura invalidada en su mismo mes | Sale del anexo 2 y va a anulados. |
| Factura de un mes anterior invalidada en este | El mes anterior la cuenta; este la resta con una fila negativa con su fecha original y la reporta en anulados (art. 111 CT). |
| Evento de retorno del mes | Fila negativa en el anexo 2 y en el libro, con la fecha de la factura. El retorno disminuye la venta y el débito sin invalidar la factura (Normativa 2.0, 13.3.2); el manual admite negativos en el anexo 2 para los ajustes del art. 111 CT, que incluye los que «disminuyan» una factura, y el art. 87 del reglamento los anota en el mes en que ocurren. Se confirma en la primera carga real. |
| Documento en contingencia sin sello | No aparece todavía; la pantalla avisa cuántos hay. |

Las notas de crédito van en el anexo 1 con su tipo (05) y en positivo: el portal las resta.

## 4. Documento del proveedor en una compra

En el detalle de una compra recibida, la sección **Documento del proveedor** (o **Registrar
documento** en Compras pendientes) pide:

- **Clase**: DTE, impreso por imprenta u otros (declaración de mercancías o mandamiento de
  ingreso). **Tipo**: crédito fiscal, nota de crédito o de débito (o 12 y 13 para importaciones).
- **Fecha** del documento: decide el mes del libro.
- En un **DTE**: código de generación, número de control y sello. En papel: el número impreso.
- **Proveedor** como figura en el documento, con su NIT, NRC o DUI sin guiones. Se propone el del
  catálogo de proveedores.
- **Clasificación de renta**: tipo de operación, clasificación (costo o gasto), sector y tipo de
  costo o gasto. Describen cómo usa la compra la empresa (su estructura de costos), no la
  actividad del proveedor. Se propone la **renta de compras por defecto**, que se cambia al pie
  de la pantalla de libros. Mientras no se guarde, sale de la actividad principal de la empresa:
  industria (como una panadería) 1 · 1 · 1 · 5, comercio 1 · 1 · 2 · 5, agropecuaria
  1 · 1 · 3 · 5 y servicios 1 · 2 · 4 · 2 (gasto de administración).

Los montos salen de la compra: gravado (líneas con IVA), exento (sin IVA) y crédito fiscal. Los
gastos de flota y los generales todavía no entran al libro de compras.

## 5. Lo que no cubre

- Anexos de casillas sin origen en el ERP: 66, 108, 161, 162, 163, 170, 171 y 172. La 162
  (retención que le hicieron a la empresa) se soporta con el comprobante que emite el cliente,
  que el ERP no registra.
- Cierre de período y declaración modificatoria.

## Permisos

| Permiso | Qué permite |
|---|---|
| `fiscal_books:read` | Ver los libros y anexos y descargar Excel, PDF y ZIP. |
| `fiscal_books:manage` | Registrar el documento del proveedor de una compra y la renta de compras por defecto. |

# Manual de Ventas y facturación electrónica

Guía de todo el ciclo de venta de GestionaSV: del cliente al libro de IVA. Cada sección resume qué pasa y enlaza
al manual de detalle. Todas las pantallas están en el menú **Ventas** y trabajan dentro de la empresa y la sucursal
elegidas arriba; cada usuario ve solo las sucursales de su alcance.

## El ciclo en una mirada

```
Cliente → (Cotización) → Pedido → Confirmar (sale de bodega) → Factura o CCF (DTE)
        → Cobro → Devolución (nota de crédito o retorno) → Saldo a favor o reintegro
        → Libros de IVA y F-07 → Cierre del mes → Análisis comercial
```

| Paso | Qué deja | Manual |
|---|---|---|
| Configurar el emisor | Datos fiscales, establecimientos, puntos de venta, documentos habilitados, credenciales de Hacienda | [configuración fiscal](manual-configuracion-fiscal.md) |
| Productos y precios | Tratamiento fiscal del producto, listas de precios con vigencia, márgenes, topes de descuento y promociones | [clasificación fiscal](manual-clasificacion-fiscal-productos.md), [listas de precios](manual-listas-precios.md), [margen y descuentos](manual-margen-y-descuentos.md) |
| Cliente | Contribuyente o consumidor final, crédito (días y límite), lista de precios, consentimiento de datos | [clientes](manual-clientes.md), [datos personales](manual-datos-personales.md) |
| Cotización (opcional) | Oferta con precios, impuestos, vigencia y PDF | [cotizaciones](manual-cotizaciones.md) |
| Pedido | Compromiso con fecha y lugar de entrega; al confirmar sale de bodega o se aparta | [pedidos](manual-pedidos.md), [entregas](manual-entregas.md) |
| Factura o crédito fiscal | DTE firmado y sellado (o simulado), PDF con QR, correo al cliente, contingencia, invalidación, notas | [facturación](manual-facturacion.md), [cálculo fiscal](manual-calculo-fiscal-ventas.md) |
| Cobro | Recibos, saldo a favor, crédito y gestión de cobro | [cobros](manual-cobros.md) |
| Devolución | Mercadería que vuelve, con su nota de crédito o evento de retorno automático; cambio de producto; reintegro | [cobros §8–9](manual-cobros.md) |
| Libros y F-07 | Libros de contribuyentes, consumidor final y compras; anexos en CSV; cierre del mes | [libros de IVA](manual-libros-iva.md) |
| Análisis | Venta sin IVA, margen, devoluciones y metas por sucursal | [análisis comercial](manual-analisis-comercial.md) |
| Punto de venta | Cajas, turnos, efectivo, cierre ciego con aprobación, depósitos y vitrina | [punto de venta](manual-pos.md) |

## 1. Antes de vender

1. **Configuración fiscal → Emisor**: NIT, NRC, actividad económica, establecimientos (uno por sucursal) y puntos de
   venta. Habilita los documentos que la empresa emite (01 factura, 03 crédito fiscal, 05/06 notas, 04 remisión) y
   el modo: **simulado** para practicar, pruebas de Hacienda o producción.
2. **Productos**: cada producto lleva su tratamiento (gravado, exento o no sujeto) y su tipo de ítem.
3. **Listas de precios**: un precio por producto y unidad, con fecha de inicio. El historial no se reescribe: un
   precio nuevo rige desde hoy o desde una fecha futura.
4. **Clientes**: un contribuyente (NIT y NRC) recibe crédito fiscal; un consumidor final, factura. Los días de
   crédito definen si el pedido es de contado o a crédito; el límite, cuánto puede deber.

## 2. Vender

- **Cotización** (opcional): precio de lista, descuentos dentro del tope del rol, impuestos y PDF. Cotizar no aparta
  existencias. Una cotización aceptada se convierte en pedido.
- **Pedido**: el servidor calcula precios, IVA, retención y percepción. **Nunca se vende bajo el costo del kardex**.
  Al **confirmar**, el pedido sale de bodega con unidades completas (si la empresa lo tiene encendido) o queda
  apartado para **Preparar entrega**.
- **Autorizaciones**: un descuento fuera de tope, un pedido a crédito que pasa el cupo, un cliente con mora o
  bloqueado quedan **Por autorizar** y los aprueba quien tiene el permiso.

## 3. Facturar

**Facturar** emite el documento del pedido: crédito fiscal para un contribuyente, factura para un consumidor final.
Se firma y transmite a Hacienda (o se simula) y queda el PDF con QR y el JSON. Si Hacienda no responde, el documento
pasa a **contingencia** y se transmite al volver el servicio. Un documento con error se **corrige** (invalidación
tipo 1 con reemplazo) o se **anula** (tipo 2) dentro del plazo. Las notas de crédito y de débito ajustan un crédito
fiscal sellado.

## 4. Cobrar

- **Contado**: se cobra al facturar.
- **Crédito**: el documento vence según los días del pedido. En **Cuentas por cobrar** se ve la cartera, la
  antigüedad y el estado de cuenta; **Registrar cobro** aplica un recibo a uno o varios documentos.
- **Saldo a favor**: lo cobrado de más (o lo que libera una nota de crédito) queda en el recibo; se **aplica** a otro
  documento desde la sección **Cobro** o se **reintegra** al cliente.
- **Comprobante de retención** del cliente agente de retención (1 %).

## 5. Devoluciones y cambios

1. Desde el pedido, **Registrar productos devueltos** (con evidencia opcional) y **Registrar recepción física**.
2. En la revisión, **aceptar** lo que está en buen estado: vuelve a bodega en cuarentena y el ERP emite solo la
   **nota de crédito** (si fue crédito fiscal) o el **evento de retorno** (si fue factura). Si no se puede (plazo,
   documento sin sello), queda el motivo visible.
3. Si el documento estaba pagado, el excedente vuelve como **saldo a favor**; se reintegra o se aplica.
4. **Cambiar por otro producto** abre un pedido nuevo vinculado a la devolución; su documento se cobra con el saldo a
   favor.

## 6. Cerrar el mes

En **Libros de IVA**: revisa los tres libros del mes, descarga el Excel, los PDF foliados y el ZIP con los anexos del
F-07, registra el documento del proveedor de las compras pendientes y, cuando ya declaraste, **Cerrar período**. Un mes
cerrado no admite cobros, reintegros, documentos de proveedor ni invalidaciones con su fecha; reabrirlo pide motivo.

## 7. Analizar

**Análisis comercial** muestra la venta sin IVA, documentos, tiquete promedio, devoluciones, margen bruto (con permiso
de costos) y el avance de las **metas** por sucursal, con cortes por día, hora, sucursal, categoría, cliente y
producto. El **Dashboard** resume la venta del mes para quien puede ver cifras.

## Quién puede hacer qué

| Permiso | Para qué |
|---|---|
| `sales_customers:read` / `:manage` | Consultar / crear, editar y desactivar clientes |
| `price_lists:read` / `:manage` | Consultar / gestionar listas de precios |
| `sales_costs:read` | Ver costo y margen (precios, pedidos y análisis) |
| `sales_discounts:manage` | Configurar los topes de descuento por rol |
| `sales_promotions:manage` | Crear y terminar promociones por sucursal |
| `sales_prices:override` | Cambiar el precio de lista en una cotización o pedido |
| `sales_discounts:authorize` | Autorizar descuentos fuera de tope (nunca bajo costo) |
| `sales_quotations:read` / `:manage` / `:confirm` / `:convert` | Cotizaciones |
| `sales:read` / `:manage` / `:confirm` / `:cancel` | Pedidos |
| `sales_deliveries:read` / `:manage` / `:confirm` / `:cancel` | Entregas |
| `sales_invoices:read` / `:issue` | Consultar / emitir documentos fiscales |
| `sales_invoices:notes` / `:returns` / `:invalidate` / `:contingency` | Notas, eventos de retorno, invalidación y contingencia |
| `sales_receivables:read` / `:collect` | Cartera / registrar recibos, reintegros y comprobantes |
| `sales_credit:authorize` | Autorizar crédito fuera de cupo o con mora; bloquear clientes |
| `sales_returns:read` / `:manage` / `:receive` / `:resolve` / `:cancel` | Devoluciones |
| `sales_analytics:read` | Ver cifras de venta, análisis, metas y el resumen del Dashboard |
| `sales_goals:manage` | Definir las metas mensuales por sucursal |
| `fiscal_settings:read` / `:manage` | Configuración fiscal del emisor |
| `fiscal_books:read` / `:manage` | Libros de IVA / datos fiscales de compras |
| `fiscal_periods:manage` | Cerrar y reabrir el mes |
| `pos:sell`, `pos:shift_open`, `pos:shift_close`, `pos:cash_movements`, `pos:reprint` | Trabajar en la caja con su propio turno (rol Cajero) |
| `pos:supervise`, `pos:reports`, `pos:deposits`, `pos:showcase` | Autorizar en caja, aprobar cierres, informes, depósitos y vitrina (rol Supervisor de tienda) |
| `pos:registers_manage` | Configurar las cajas |

## Recorrido de demostración

Con los datos de demostración (ver [datos de demostración](manual-datos-demostracion.md)) y el emisor en modo
simulado:

1. **Análisis comercial**, del 01/10 al 31/10: venta del mes, margen, devoluciones y avance de la meta de la Matriz.
2. **Libros de IVA**, octubre: créditos fiscales a Cafetería El Trigal y Distribuidora La Espiga, consumidor final
   agrupado por día y los anexos del F-07; probar **Cerrar período** y **Reabrir** con motivo.
3. **Cuentas por cobrar**: cartera con los documentos a 30 días de Distribuidora La Espiga y los recibos de octubre.
4. **Pedidos**: abrir una venta de octubre (referencia `GLVTA-…` en sus notas) con su entrega, su crédito fiscal y su
   cobro; una con devolución muestra la nota de crédito emitida y, en una, el **cambio de producto**.
5. **Kardex** de un producto vendido: las salidas de octubre a costo promedio y la devolución en cuarentena.
6. **Ciclo en vivo**: crear un pedido nuevo, confirmarlo, facturarlo, cobrarlo, devolver una unidad, ver la nota
   automática y reintegrar el saldo a favor.

La prueba automática `backend/tests/e2e/test_sales_full_cycle.py` recorre ese mismo ciclo y comprueba que cartera,
kardex, análisis y libro de IVA cuadran entre sí.

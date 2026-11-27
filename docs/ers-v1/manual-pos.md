# Manual del punto de venta: caja, turnos, depósitos y vitrina

El punto de venta trabaja por **turnos**: cada cajero abre el suyo en una caja, mueve efectivo durante el día,
lo cuenta al terminar y un supervisor aprueba el cierre. Después, el efectivo se deposita en el banco.

## Roles

| Rol | Qué hace |
|---|---|
| **Cajero** | Al entrar ve solo la caja, a pantalla completa. Abre y cuenta su turno, registra entradas, salidas y retiros, reimprime sus tiquetes. Nunca ve cuánto debería haber en la gaveta. |
| **Supervisor de tienda** | Todo lo del cajero, más: autoriza en caja con su PIN, revisa y aprueba los cierres de su sucursal, imprime los informes y registra los depósitos. Nunca aprueba su propio turno. |

Quien configura las cajas necesita el permiso **Configurar las cajas del punto de venta**.

## 1. Configurar las cajas

**Punto de venta → Cajas → Nueva caja.**

- Cada caja usa un **punto de venta** de la configuración fiscal de su sucursal (uno por caja). Si no hay
  ninguno, primero regístralo en **Ventas → Configuración fiscal**.
- **Fondo de la caja**: el efectivo con que empieza cada turno.
- **Salidas sin supervisor hasta**: una salida mayor pide la autorización de un supervisor.
- **Límite de efectivo en gaveta** (opcional): al llegar a él, la caja avisa que toca un retiro.

El código de una caja que ya tuvo turnos no cambia, porque aparece en sus tiquetes y cierres.

## 2. Definir el PIN del supervisor

En la caja, **Definir mi PIN**: escribe tu contraseña y un PIN de seis dígitos que no sean repetidos ni
seguidos. Cinco intentos fallidos bloquean el PIN durante 15 minutos.

## 3. Abrir el turno

En **Caja**, elige tu caja y cuenta el fondo **billete por billete** con los botones + y −. Si lo contado no
coincide con el fondo de la caja, explica la diferencia. Una caja no admite dos turnos abiertos, y un
cajero tampoco puede tener dos.

## 4. Mover efectivo

- **Entrada de efectivo**: cambio u otro efectivo que entra sin venta.
- **Salida de efectivo**: un pago menor con su comprobante. Si pasa el tope de la caja, el supervisor elige
  su nombre y escribe su PIN en la misma pantalla.
- **Retiro a caja fuerte**: efectivo que sale de la gaveta hacia la caja fuerte. Se deposita con el turno.

Ningún movimiento se edita ni se borra. Una salida o un retiro nunca pueden superar el efectivo en gaveta.

## 5. Contar y entregar el turno (cierre ciego)

**Contar y entregar turno**: cuenta todo el efectivo por denominación y escribe el total del cierre de lote del
datáfono y el de las transferencias recibidas. Al entregar, la caja deja de vender. La pantalla nunca muestra
cuánto debería haber: así el conteo es honesto.

## 6. Revisar y aprobar el cierre

En **Punto de venta → Turnos de caja**, pestaña **Por aprobar**, abre el turno. Vas a ver:

- lo **esperado** contra lo **contado**, con el sobrante o el faltante;
- el desglose por fuente (fondo, entradas, salidas, retiros, ventas y reintegros);
- los movimientos y cada conteo.

Puedes:

- **Pedir recuento**, explicando qué revisar. El cajero vuelve a contar y el conteo anterior queda en la
  historia.
- **Aprobar cierre**, indicando el **fondo que queda** para el siguiente turno. Si hay diferencia, explícala.
  Un cierre aprobado no se modifica.

**Imprimir corte X** (turno en curso) e **Imprimir cierre Z** (turno cerrado) generan el informe en rollo de
80 mm, con espacio para la firma del cajero y del supervisor.

## 7. Depositar

En **Punto de venta → Depósitos**, con la sucursal elegida, marca los turnos cerrados. Cada turno aporta lo
contado menos el fondo que quedó, más sus retiros a caja fuerte. Escribe el banco, la cuenta, el número de
boleta y el monto depositado. La fecha no puede ser futura ni anterior al cierre de los turnos. Si el monto no
cuadra, explica la diferencia. Una boleta no se registra dos veces.

## 8. Vitrina

La **vitrina** es la existencia suelta del mostrador. Cada sucursal tiene una, dentro de una de sus bodegas.

- **Crearla** (Punto de venta → Vitrina, quien configura cajas): elige la bodega. Se crea la ubicación
  `VITRINA`, que no se edita ni se retira desde el módulo de ubicaciones.
- **Pasar a vitrina** (supervisor de tienda): elige unidades completas de la bodega, primero las que vencen antes.
  Al pasar, la unidad se **abre**: desde entonces se vende por pieza y ya no se usa en pedidos, entregas ni
  traslados. Si solo va una parte de la caja, fracciónala antes en la bodega.
- **Existencias**: por producto, lo que se puede vender y lo vencido, con el próximo vencimiento. La caja vende
  primero lo que vence antes y nunca lo vencido.
- **Conteo de cierre**: al terminar el día cuenta lo que queda. Lo que falta contra el sistema es **merma**: sale
  del inventario al costo promedio, con su motivo, y queda en el historial con su costo. Lo vencido sale primero
  como merma. Si cuentas **más** de lo que registra el sistema, el conteo se rechaza: primero pasa a vitrina lo que
  falta registrar.

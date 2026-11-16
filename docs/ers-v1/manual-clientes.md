# Manual: clientes

Pantallas: **Ventas → Clientes** (`/customers`), ficha nueva (`/customers/new`) y ficha de
cada cliente (`/customers/{id}`).
Permisos: `sales_customers:read` para consultar y `sales_customers:manage` para registrar y
cambiar.

Los datos de cada cliente deciden qué documento se le puede emitir. La ficha lo muestra
siempre en **Puede recibir**.

## Tipos de cliente

| Tipo | Para quién | Documento que recibe |
|---|---|---|
| Consumidor final | Personas que compran para consumo propio. | Factura. |
| Contribuyente de IVA | Negocios inscritos en IVA que piden crédito fiscal. | Factura y, con los datos completos, comprobante de crédito fiscal. |
| Cliente del extranjero | Compradores fuera de El Salvador. | Factura de exportación. |

**Comprobante de crédito fiscal.** Un contribuyente solo lo recibe si tiene:
- NIT o DUI homologado;
- NRC;
- actividad económica;
- dirección completa: departamento, municipio, distrito y dirección.

Si algo falta, la ficha muestra **Para emitirle crédito fiscal falta:** con la lista.

**Consumidor final.** No necesita documento de identidad. Para ventas desde $25,000 la
identificación será obligatoria al emitir la factura.

## Registrar un cliente

1. Pulsa **Nuevo cliente** y elige el tipo.
2. **Código.** Si lo dejas vacío, el sistema asigna el siguiente: CLI-00001, CLI-00002…
3. **Identidad fiscal.**
   - Nombre o razón social, nombre comercial y tipo de persona.
   - Documento de identidad, NRC y actividad económica.
   - Para contribuyentes, también su categoría y si es agente de retención de IVA.
   - El NIT y el DUI se pueden escribir con o sin guiones: se guardan solo los dígitos.
   - La actividad se busca por código o por nombre en el catálogo de Hacienda.
4. **Dirección.**
   - Clientes de El Salvador: departamento, municipio y distrito, y la dirección.
   - Clientes del extranjero: país y dirección.
5. **Contacto y condiciones.**
   - Correo para recibir los documentos y teléfono.
   - Plazo de crédito en días (0 es contado) y límite de crédito.

El documento de identidad y el NRC no se pueden repetir entre clientes.

## Direcciones de entrega

Desde la ficha de un cliente ya registrado puedes agregar las direcciones donde se
entrega la mercadería:
- nombre, dirección y geografía;
- contacto y teléfono;
- coordenadas, que sirven para el seguimiento del reparto.

La primera dirección queda como **principal**. Solo una puede serlo a la vez.

## Cliente «Consumidor final» de cada sucursal

Cada sucursal tiene un cliente genérico llamado «Consumidor final», con código
`CF-<código de la sucursal>`. Sirve para las ventas de mostrador sin identificar.
- Se crea solo la primera vez que se necesita.
- No aparece en la lista de clientes.
- No se edita ni se desactiva.

## Desactivar un cliente

**Desactivar** impide cotizarle o venderle. Sus documentos anteriores se conservan y
puedes reactivarlo en cualquier momento.

## Datos de demostración

Grupo Lorena tiene cuatro clientes ficticios, con NIT, DUI y NRC que empiezan con 0000:

| Código | Cliente | Caso |
|---|---|---|
| CLI-00001 | Cafetería El Trigal | Contribuyente completo; puede recibir crédito fiscal. Tiene una dirección de entrega. |
| CLI-00002 | Distribuidora La Espiga | Contribuyente sin NRC; la ficha indica que le falta. |
| CLI-00003 | María Fernanda Rivas | Consumidor final identificado con DUI. |
| CLI-00004 | Panadería Centroamericana | Cliente del extranjero (Guatemala). |

Además, cada sucursal tiene su «Consumidor final».

## Bitácora

Cada registro, cambio, activación o dirección de entrega queda en la bitácora con
usuario, fecha y valores anteriores y nuevos. Los recursos son:
- `sales_customer`
- `sales_customer_delivery_address`

# Plan: Ventas V2a — Motor único de cálculo fiscal

Rama: `feature/ventas-v2a-motor-calculo`, desde `develop` (incluye V1a, V1b y V1c; V1d está en la PR #41).
Fuente: `docs/plan-area-ventas-el-salvador.pdf`, secciones 3.2 (IVA), 3.3 (retención y percepción), 4.5 (reglas de cálculo), módulo 5.2 y bloque V2.

## Decisiones del usuario (16/11/2026)

- V2 se divide en cinco sub-bloques, cada uno con su PR a `develop`:
  - **V2a**: motor único de cálculo (este plan);
  - **V2b**: listas de precios;
  - **V2c**: descuentos con topes por rol y venta bajo costo;
  - **V2d**: cotización rediseñada;
  - **V2e**: pedido de venta que sustituye a la venta actual.
- Las promociones (2×1, combos, precio por horario) van en V6, con la caja. V2 deja el motor listo para recibirlas.
- La cotización y la venta actuales (B06) se rehacen en su lugar, con migración. Si hubiera datos en algún entorno, la migración se niega a seguir en lugar de perderlos. Entregas y devoluciones se adaptan.

## Alcance de V2a

Un solo motor calcula los montos fiscales de cualquier documento de venta. Lo usarán la cotización, el pedido, el punto de venta y el DTE. Este sub-bloque no tiene migración ni pantallas: entrega el motor y un endpoint para previsualizar el cálculo.

Resultado verificable:
- el mismo producto da $1.13 con IVA incluido en la factura y $1.00 + $0.13 en el crédito fiscal (cuadro 1 del plan);
- el ejemplo oficial de crédito fiscal con descuento global y retención (Manual Funcional, cap. XVIII) da exactamente los mismos montos.

## Hechos verificados

- **Esquemas oficiales** (`svfe-json-schemas`; `fe-f-v2` y `fe-ccf-v4`):
  - los montos por línea admiten 8 decimales (`multipleOf 1e-08`) y los del resumen, 2;
  - la factura lleva `ivaItem` por línea y `totalIva` en el resumen;
  - el crédito fiscal lleva el IVA en `resumen.tributos` (código 20), más `ivaPerci` e `ivaRete`.
- **Redondeo y holgura** (Manual Funcional, cap. XXI): media hacia arriba, en el 8.º decimal en las líneas y en el 2.º en el resumen. Hacienda tolera $0.01 en cada campo del resumen.
- **Descuentos** (cap. XVIII):
  - el descuento por ítem se resta de precio × cantidad;
  - el descuento global va por naturaleza (gravada, exenta, no sujeta) en el resumen;
  - `totalDescu` suma ambos y es informativo.
- **Ejemplo oficial de crédito fiscal**: gravadas $775.00, descuento global gravado $77.50 → subtotal $697.50.
  - IVA: 697.50 × 0.13 = 90.675 → $90.68.
  - Retención: 1 % = $6.98.
  - Monto total de la operación: $697.50 + $90.68 − $6.98 = $781.20.
- **Lo que ya existe en el ERP**:
  - categoría del emisor (`large`, `medium`, `other`) en el perfil fiscal (V1a);
  - del cliente: categoría y si es agente de retención (V1b);
  - del producto: tratamiento de IVA, tipo de ítem y tributos adicionales (V1c);
  - documentos que puede recibir cada cliente (`receivable_documents`) y documentos habilitados por empresa (V1a).
- No existe ningún precio de producto en el ERP: «Asignación de precios» es un marcador del menú. Lo resuelve V2b.

## Reglas del motor

- **Documentos**: factura (01) y comprobante de crédito fiscal (03). Exportación y notas vienen con el DTE (V3 y V4).
- **Precio de cada línea**:
  - llega con la marca `price_includes_vat`;
  - el motor lo lleva a la forma del documento: con IVA en la factura y sin IVA en el crédito fiscal;
  - convierte con ÷ 1.13 o × 1.13, redondeando a 8 decimales;
  - el precio de una línea exenta o no sujeta nunca lleva IVA.
- **Venta por línea** = cantidad × precio − descuento por ítem, a 8 decimales. Va en `venta_gravada`, `venta_exenta` o `venta_no_sujeta` según el producto.
- **IVA**:
  - Factura: `iva_item` = venta gravada − venta gravada ÷ 1.13, por línea. En el resumen, `total_iva` se calcula sobre la gravada neta del descuento global.
  - Crédito fiscal: IVA = (gravada − descuento global gravado) × 0.13, redondeado a 2 decimales.
- **Retención 1 %** (CT art. 162):
  - aplica si el cliente es gran contribuyente o agente de retención, el emisor no es gran contribuyente y la gravada neta sin IVA llega a $100;
  - la base es la gravada neta sin IVA;
  - se resta del monto total.
- **Percepción 1 %** (CT art. 163):
  - solo en el crédito fiscal;
  - aplica si el emisor es gran contribuyente, el cliente es contribuyente sin esa categoría y la base llega a $100;
  - la base es la gravada neta de las líneas de bienes (tipo de ítem 1 o 3);
  - se suma al total.
- **Cuadre**: el descuento global de cada naturaleza no puede superar su total.
- **Tributos adicionales**: un producto con tributos adicionales (FOVIAL, COTRANS, etc.) se rechaza con un error claro, porque sus tasas y bases no son el 13 %. Quedan para cuando una empresa los necesite.
- **Total en letras**: en español y en mayúsculas, por ejemplo «CIENTO TRECE 50/100 DÓLARES».

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: dominio.**
  - Crear `backend/app/domain/entities/sales_tax.py` con el motor puro y `amount_in_words`.
  - Verificar con pruebas unitarias: cuadro 1, el ejemplo oficial, exentos y no sujetos, retención y percepción en su umbral y debajo de él, conversión de precio, redondeo con 5 en el 9.º decimal y errores.
- [x] **Paso 2: aplicación y API.**
  - Caso de uso que arma la entrada con el emisor, el cliente y la clasificación de cada producto, y valida que el documento lo pueda recibir el cliente y esté habilitado en la empresa.
  - Endpoint `POST /sales/tax-calculation`.
  - Verificar con pruebas e2e: permisos, empresa aislada, documento no habilitado o no permitido al cliente, producto con tributos adicionales.
- [x] **Paso 3: documentación.** `docs/api.md` y un manual del cálculo en `docs/ers-v1/`.
- [x] **Paso 4: verificación y PR.** Correr la batería completa y abrir el PR hacia `develop`.

## Estado actual

- **Paso en curso**: ninguno; V2a terminado y en PR hacia `develop`. Batería completa: backend 1,843 y frontend 1,134 pruebas en verde. Lo siguiente es V2b (listas de precios). Documentación en `docs/api.md` (Sales tax calculation) y `docs/ers-v1/manual-calculo-fiscal-ventas.md`. API en `routers/sales_tax.py` (`POST /sales/tax-calculation`, permiso `sales_quotations:read` o `sales:read`, sin auditoría porque no guarda); caso de uso en `application/sales_tax`; 5 pruebas e2e en `tests/e2e/test_sales_tax.py`. El motor está en `backend/app/domain/entities/sales_tax.py`, con 22 pruebas en `tests/unit/test_sales_tax.py`.
- **Comandos**:
  - Pruebas: `./scripts/run-tests.sh` con los objetivos `backend-unit`, `backend-integration`, `backend-e2e`, `frontend` y `lint`. La batería completa tarda unos 40 minutos.
  - No hacer commits mientras corre la batería.
  - Prettier solo se aplica a archivos nuevos o tocados.
  - Los esquemas oficiales están en `D:\josec\Downloads\Documentacion DTE\svfe-json-schemas.zip`.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop`.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.
  - En documentos compartidos, el servicio DTE de referencia se llama «proyecto de referencia».

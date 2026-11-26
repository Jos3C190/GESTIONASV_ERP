# Manual: un mes de ventas de demostración

La siembra `seed/seed_grupo_lorena_sales.py` genera el **mes anterior completo** de ventas de Grupo Lorena con
las reglas reales del ERP, para mostrar el análisis comercial, los libros de IVA, la cartera y el kardex con datos
de un mes. Solo existe para desarrollo y demostración: **nunca corre en producción** y solo funciona con el emisor
en modo **simulado** (sin validez fiscal).

## Qué genera

- **Cajas en la bodega central**: fracciona pallets de BOD-CENTRAL-01 en unidades de una caja (mide, etiqueta y
  libera, como se haría en bodega), para que cada venta salga entregada del kardex al confirmarse.
- **Ventas por día hábil** (lunes a sábado, unas seis por día) a clientes de mostrador y de mayoreo: pedido,
  confirmación con salida automática, autorización de crédito cuando pasa el cupo, factura o crédito fiscal
  simulado y cobro. Las de contado se cobran el mismo día; las de crédito, al vencer si el vencimiento cae dentro
  del mes (las de 30 días quedan en cartera).
- **Devoluciones** aceptadas con su nota de crédito o evento de retorno, un **cambio de producto** con el saldo a
  favor aplicado al documento nuevo y la **meta del mes** de la Matriz.

Cada documento lleva `Ref. GLVTA-…` en sus notas. Una nueva corrida encuentra lo ya creado y solo completa lo que
falte: no duplica ventas ni vuelve a fraccionar pallets.

## Cómo funcionan las fechas

El ERP emite siempre con la fecha de hoy, como pide Hacienda. Para un mes pasado la siembra mueve el reloj del
proceso a cada día (`time-machine`) y le pasa la misma fecha al servicio DTE en el encabezado `X-DTE-Demo-Clock`.
El servicio solo lo acepta con `DTE_DEMO_CLOCK_ENABLED=true` (activo en `compose.yaml` de desarrollo, apagado en
`compose.prod.yaml` y siempre ignorado con `DTE_MODE=production`) y con un emisor simulado; fuera de eso lo
rechaza. Así `fecEmi`, el número de control, el kardex, los cobros y los libros quedan con fechas del mes.

Las subidas al almacenamiento de objetos se hacen a la hora real: MinIO rechaza firmas con la hora movida.

Los precios sembrados rigen desde noviembre de 2026 y el ERP no admite precios con fecha pasada. Como dato maestro
de demostración, la siembra agrega el tramo anterior desde el primer día del mes con el precio vigente.

## Cómo correrla

Dentro del contenedor del backend:

```
uv run --no-sync python -m seed.seed_grupo_lorena_sales
```

- `SEED_DEMO_SALES_MONTH=2026-10` fija el mes (por omisión, el anterior a hoy).
- `SEED_DEMO_SALES_DAYS=2` limita la corrida a los primeros días hábiles (para probar).
- Como paso opcional de la siembra inicial: `SEED_DEMO_SALES=true` (después de `SEED_DEMO_OPERATIONS`, que deja las
  existencias de la bodega central).

Al terminar imprime lo creado (`orders`, `invoices`, `receipts`, `returns`, …) y los rechazos de la API, si los hubo.

## Notas

- Panadería Centroamericana (CLI-00004) no participa: es un cliente extranjero y solo recibe factura de exportación.
- Los documentos son simulados: sirven para revisar formatos, libros y anexos, no para cargarlos en Hacienda.

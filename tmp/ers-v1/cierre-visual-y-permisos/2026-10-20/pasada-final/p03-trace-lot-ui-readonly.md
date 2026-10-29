# P03 — Revisión visual de identidad lote/HU — 20/10/2026

## Causa

El servicio de inventario ya entregaba tres identificadores distintos, pero la ficha privada imprimía solamente `inventory_lots.lot_code`, destinado al lote del fabricante. Para una recepción cuyo proveedor no indicó lote de fabricante, eso dejaba el código visual vacío aunque la recepción sí tenía cabecera y detalle canónico. No era un lote perdido en datos; era una omisión de presentación.

## Corrección comprobada

La ficha de HU ahora etiqueta por separado el lote del fabricante, el detalle/lote canónico de recepción y el lote cabecera de la compra. El componente extrae ese formato en una pieza pequeña y probada para que no se mezclen los significados.

Caso real consultado en solo lectura: `HU-8D63FE508BF14124`, producto **Café Tostado y Molido 1kg** (`PRD-CAF-011`), recepción `COM-00017`, cabecera `LOT-COM-00017`, detalle `LOT-COM-00017-DA9DBC0769F114438A8C0CF242E8344D8`, 2.25 cajas (`cj`), ubicación `SEC-02`, disponible. El lote de fabricante aparece como no proporcionado cuando está vacío; no se crea un alias sintético.

## Evidencia y límites

- Unit y mapeo de servicios: [Vitest enfocado](p03-p04-focused-vitest.log).
- Lint del componente: [ESLint](p03-trace-lot-ui-eslint.log).
- Tipo Svelte/compilación: [Svelte-check](p03-p04-svelte-check-final.log) y [build](p03-p04-focused-build.log).
- Inspección autenticada de la ficha en `localhost:5173/inventory/handling-units/a6ccee14-a44b-4fea-9e0e-58a444ded43f`; estado observable incluye nombre, SKU, origen, cabecera, detalle, existencia y movimientos. No se generó movimiento durante la inspección.
- No hay PNG archivado. La sesión CUA disponible no brinda un mecanismo de escritura/exportación de su captura a la ruta local; la evidencia visual queda como inspección en sesión y no satisface el artefacto P02.
- Tampoco se repitió una compra/recepción del mismo SKU en varias líneas en el navegador. El siguiente paso requiere un caso nuevo en base aislada y una ruta de archivo de captura disponible.

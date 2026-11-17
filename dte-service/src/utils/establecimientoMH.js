const { TIPO_ESTABLECIMIENTO_LETRA } = require('../config/catalogs');

/**
 * Los schemas de eventos (Invalidación, Contingencia) piden codEstableMH y
 * codPuntoVentaMH como campos STRING de EXACTAMENTE 4 caracteres cada uno
 * — a diferencia de como los usa el Número de Control (que los concatena
 * directamente). Construidos así, coinciden exactamente con los primeros
 * 8 caracteres tras "DTE-{tt}-" en el Número de Control:
 *   codEstableMH   = {letra CAT-009}{3 dígitos}   ej. "M001"
 *   codPuntoVentaMH = "P"{3 dígitos}               ej. "P001"
 */
function construirCodEstableMH(tipoEstablecimiento, codEstablecimientoMH) {
  const letra = TIPO_ESTABLECIMIENTO_LETRA[tipoEstablecimiento];
  if (!letra) {
    throw new Error(
      `Tipo de establecimiento inválido: "${tipoEstablecimiento}". Debe ser uno de CAT-009: 01 (Sucursal), 02 (Casa Matriz), 04 (Bodega), 07 (Patio).`
    );
  }
  return `${letra}${String(codEstablecimientoMH).padStart(3, '0')}`;
}

function construirCodPuntoVentaMH(codPuntoVentaMH) {
  return `P${String(codPuntoVentaMH).padStart(3, '0')}`;
}

module.exports = { construirCodEstableMH, construirCodPuntoVentaMH };

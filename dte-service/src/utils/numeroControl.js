const correlativoStore = require('../services/correlativoStore');
const { construirCodEstableMH, construirCodPuntoVentaMH } = require('./establecimientoMH');
const { fechaHoraSV } = require('./fechaHoraSV');

/**
 * Número de Control: 31 caracteres. El patrón EXACTO viene confirmado por el
 * JSON Schema oficial de cada DTE (campo identificacion.numeroControl):
 *
 *   ^DTE-{tt}-(M|B|S|P)([0-9]{3})(P)([0-9]{3})-[0-9]{15}
 *
 * Que es exactamente la concatenación de codEstableMH + codPuntoVentaMH tal
 * como los exigen los schemas de eventos (Invalidación/Contingencia): dos
 * códigos de 4 caracteres cada uno (ver utils/establecimientoMH.js):
 *   DTE-{tt}-{codEstableMH}{codPuntoVentaMH}-{correlativo:15}
 *
 * OJO: esto es distinto del campo emisor.codEstable/codPuntoVenta del cuerpo
 * del DTE (esos son códigos INTERNOS del contribuyente, informativos). Los
 * códigos que van en el Número de Control son los oficiales de Hacienda.
 *
 * `anio` es el año de fecEmi en hora de El Salvador; los builders lo pasan
 * desde el mismo instante con el que arman fecEmi, para que el correlativo
 * no cambie de año antes que la fecha de emisión (31 de diciembre ≥ 18:00).
 */
function generarNumeroControl({
  tipoDte, tipoEstablecimiento, codEstablecimientoMH, codPuntoVentaMH, anio = fechaHoraSV().anio, nit = '', ambiente = '',
}) {
  const codEstableMH = construirCodEstableMH(tipoEstablecimiento, codEstablecimientoMH);
  const codPuntoVentaMHStr = construirCodPuntoVentaMH(codPuntoVentaMH);

  // El número no puede repetirse dentro del año calendario de la fecha de
  // emisión (hora de El Salvador): el correlativo se lleva por tipoDte +
  // año + establecimiento + punto de venta.
  // Multiemisor: cada emisor (NIT) y ambiente lleva su propia serie.
  const correlativo = correlativoStore.obtener(tipoDte, anio, codEstablecimientoMH, codPuntoVentaMH, nit, ambiente);
  const corr = String(correlativo).padStart(15, '0');

  return `DTE-${tipoDte}-${codEstableMH}${codPuntoVentaMHStr}-${corr}`;
}

const TIPO_ESTABLECIMIENTO_POR_LETRA = Object.freeze({ S: '01', M: '02', B: '04', P: '07' });
const NUMERO_CONTROL_REGEX = /^DTE-(\d{2})-([MBSP])(\d{3})P(\d{3})-(\d{15})$/;

/** Descompone un número de control en sus secciones (Manual Funcional XI). */
function parsearNumeroControl(numeroControl) {
  const partes = NUMERO_CONTROL_REGEX.exec(String(numeroControl || ''));
  if (!partes) throw new Error(`Número de control inválido: ${numeroControl}`);
  const [, tipoDte, letra, codEstablecimientoMH, codPuntoVentaMH, correlativo] = partes;
  return {
    tipoDte,
    tipoEstablecimiento: TIPO_ESTABLECIMIENTO_POR_LETRA[letra],
    codEstablecimientoMH,
    codPuntoVentaMH,
    codEstableMH: `${letra}${codEstablecimientoMH}`,
    codPuntoVentaMHCompleto: `P${codPuntoVentaMH}`,
    correlativo: Number(correlativo),
  };
}

module.exports = { generarNumeroControl, parsearNumeroControl };

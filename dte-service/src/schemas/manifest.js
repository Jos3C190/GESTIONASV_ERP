/**
 * Manifest de JSON Schemas oficiales de Hacienda, generado inspeccionando
 * los `const` de `identificacion.tipoDte` e `identificacion.version` de
 * cada archivo real entregado por el Ministerio (paquete "Json Schemas
 * (anexo al Manual Técnico para la Integración Tecnológica del Sistema de
 * Transmisión)", descargado de factura.gob.sv).
 *
 * NO EDITES ESTE ARCHIVO A MANO salvo que Hacienda publique nuevos schemas;
 * en ese caso, regenera este manifest inspeccionando los nuevos archivos de
 * la misma forma (leer identificacion.tipoDte.const e identificacion.version.const).
 */
module.exports = {
  // DTE (tienen tipoDte)
  porTipoDte: {
    '01': { archivo: 'v2/fe-f-v2.json', version: 2, nombre: 'Factura Electrónica' },
    '03': { archivo: 'v4/fe-ccf-v4.json', version: 4, nombre: 'Comprobante de Crédito Fiscal Electrónica' },
    '04': { archivo: 'v4/fe-nr-v4.json', version: 4, nombre: 'Nota de Remisión Electrónica' },
    '05': { archivo: 'v4/fe-nc-v4.json', version: 4, nombre: 'Nota de Crédito Electrónica' },
    '06': { archivo: 'v4/fe-nd-v4.json', version: 4, nombre: 'Nota de Débito Electrónica' },
    '07': { archivo: 'v2/fe-cr-v2.json', version: 2, nombre: 'Comprobante de Retención Electrónico' },
    '08': { archivo: 'v2/fe-cl-v2.json', version: 2, nombre: 'Comprobante de Liquidación Electrónica' },
    '09': { archivo: 'v2/fe-dcl-v2.json', version: 2, nombre: 'Documento Contable de Liquidación Electrónica' },
    '11': { archivo: 'v3/fe-fex-v3.json', version: 3, nombre: 'Factura de Exportación Electrónica' },
    '14': { archivo: 'v2/fe-fse-v2.json', version: 2, nombre: 'Factura de Sujeto Excluido Electrónica' },
    '15': { archivo: 'v2/fe-cd-v2.json', version: 2, nombre: 'Comprobante de Donación Electrónica' },
  },
  // Eventos (no tienen tipoDte propio; se identifican por nombre de archivo)
  eventos: {
    invalidacion: { archivo: 'v3/invalidacion-schema-v3.json', version: 3, nombre: 'Evento de Invalidación' },
    contingencia: { archivo: 'v4/contingencia-schema-v4.json', version: 4, nombre: 'Evento de Contingencia' },
    operacionesEspeciales: { archivo: 'v1/fe-eop-v1.json', version: 1, nombre: 'Evento de Operaciones Especiales' },
    retorno: { archivo: 'v1/fe-eret-v1.json', version: 1, nombre: 'Evento de Retorno' },
  },
};

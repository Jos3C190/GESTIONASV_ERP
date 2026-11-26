const path = require('path');
const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const manifest = require('../schemas/manifest');

/**
 * multipleOf exacto por decimales. Los schemas oficiales usan "multipleOf": 0.01
 * en los totales y 1e-8 en las líneas (precioUni, ventaGravada, etc.). Ajv lo
 * valida dividiendo en punto flotante, y eso falla con montos válidos: 131.70
 * con 0.01 (ajv-validator/ajv#2329) y 658.242 con 1e-8 (658.242 / 1e-8 da
 * 65824199999.99999, fuera de cualquier tolerancia de multipleOfPrecision).
 * Como el JSON que llega a Hacienda lleva la representación decimal más corta
 * del número (la de String y JSON.stringify), un monto es múltiplo de 10^-k
 * exactamente cuando esa representación tiene k decimales o menos.
 */
function decimalesDe(numero) {
  const [mantisa, exponente] = String(Math.abs(numero)).split('e');
  const decimales = (mantisa.split('.')[1] || '').length;
  return Math.max(0, decimales - Number(exponente || 0));
}

function esMultiploDe(numero, divisor) {
  const k = -Math.log10(divisor);
  if (Number.isInteger(k) && k >= 0) return decimalesDe(numero) <= k;
  const division = numero / divisor;
  return Math.abs(Math.round(division) - division) < 1e-6;
}

const ajv = new Ajv({ allErrors: true, strict: false });
ajv.removeKeyword('multipleOf');
ajv.addKeyword({
  keyword: 'multipleOf',
  type: 'number',
  schemaType: 'number',
  errors: true,
  validate: function multipleOf(divisor, numero) {
    if (esMultiploDe(numero, divisor)) return true;
    multipleOf.errors = [{ keyword: 'multipleOf', message: `must be multiple of ${divisor}`, params: { multipleOf: divisor } }];
    return false;
  },
});
addFormats(ajv);

const _validadoresPorTipoDte = {};
const _validadoresPorEvento = {};

function _compilar(rutaRelativa) {
  const schema = require(path.join('../schemas', rutaRelativa));
  return ajv.compile(schema);
}

/** Valida un DTE contra el JSON Schema OFICIAL correspondiente a su tipoDte. */
function validarDte(dte) {
  const tipoDte = dte?.identificacion?.tipoDte;
  const info = manifest.porTipoDte[tipoDte];
  if (!info) {
    return { valido: false, errores: [{ message: `No hay schema oficial registrado para tipoDte=${tipoDte}` }] };
  }
  if (!_validadoresPorTipoDte[tipoDte]) {
    _validadoresPorTipoDte[tipoDte] = _compilar(info.archivo);
  }
  const validar = _validadoresPorTipoDte[tipoDte];
  const valido = validar(dte);
  return { valido, errores: validar.errors || [], schema: info.nombre, version: info.version };
}

/** Valida un evento (invalidación, contingencia, operaciones especiales, retorno). */
function validarEvento(tipoEvento, documento) {
  const info = manifest.eventos[tipoEvento];
  if (!info) {
    return { valido: false, errores: [{ message: `Evento desconocido: ${tipoEvento}` }] };
  }
  if (!_validadoresPorEvento[tipoEvento]) {
    _validadoresPorEvento[tipoEvento] = _compilar(info.archivo);
  }
  const validar = _validadoresPorEvento[tipoEvento];
  const valido = validar(documento);
  return { valido, errores: validar.errors || [], schema: info.nombre, version: info.version };
}

module.exports = { validarDte, validarEvento, esMultiploDe };

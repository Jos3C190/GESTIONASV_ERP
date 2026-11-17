const path = require('path');
const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const manifest = require('../schemas/manifest');

/**
 * multipleOfPrecision es CRÍTICO para este proyecto: casi todos los campos
 * monetarios de los schemas oficiales usan "multipleOf": 0.01. Sin esta
 * opción, Ajv valida multipleOf con división de punto flotante directa
 * (data / 0.01), y números perfectamente válidos como 131.70 fallan porque
 * en binario se representan como 131.69999999999998863... — un bug conocido
 * y todavía abierto en Ajv (ver ajv-validator/ajv#2329). Sin este fix,
 * facturas matemáticamente correctas se rechazarían aquí mismo, antes
 * siquiera de llegar a Hacienda. El valor 6 sigue la fórmula documentada
 * por Ajv: Math.abs(Math.round(division) - division) < 1e-6.
 */
const ajv = new Ajv({ allErrors: true, strict: false, multipleOfPrecision: 6 });
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

module.exports = { validarDte, validarEvento };

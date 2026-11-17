const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { generarCodigoGeneracion } = require('../../src/utils/codigoGeneracion');

describe('codigoGeneracion.js', () => {
  test('genera un UUID v4 en formato válido (36 caracteres, mayúsculas)', () => {
    const codigo = generarCodigoGeneracion();
    assert.equal(codigo.length, 36);
    assert.equal(codigo, codigo.toUpperCase());
    assert.match(codigo, /^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$/);
  });

  test('genera códigos distintos en llamadas sucesivas', () => {
    const a = generarCodigoGeneracion();
    const b = generarCodigoGeneracion();
    assert.notEqual(a, b);
  });
});

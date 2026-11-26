/**
 * multipleOf de los schemas oficiales (0.01 en totales, 1e-8 en líneas) se
 * valida por decimales, no por división de punto flotante.
 */
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { construirCCF } = require('../../src/services/dteBuilder');
const { validarDte, esMultiploDe } = require('../../src/validators/dteSchema');

const RECEPTOR_CCF = {
  nit: '06141804941099',
  nrc: '7654321',
  nombre: 'Cliente Empresa S.A.',
  codActividad: '62010',
  descActividad: 'Programación informática',
  direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra dirección' },
  telefono: '22223333',
  correo: 'cliente@empresa.com',
};

describe('multipleOf por decimales', () => {
  test('acepta montos con hasta 8 decimales en 1e-8 aunque la división flotante falle', () => {
    assert.notEqual(Math.round(658.242 / 1e-8), 658.242 / 1e-8);
    assert.equal(esMultiploDe(658.242, 1e-8), true);
    assert.equal(esMultiploDe(20.358, 1e-8), true);
    assert.equal(esMultiploDe(0.12345678, 1e-8), true);
    assert.equal(esMultiploDe(99999999999.99, 1e-8), true);
  });

  test('acepta montos de 2 decimales en 0.01 (ajv#2329)', () => {
    assert.equal(esMultiploDe(131.7, 0.01), true);
    assert.equal(esMultiploDe(658.24, 0.01), true);
    assert.equal(esMultiploDe(0, 0.01), true);
    assert.equal(esMultiploDe(1e21, 0.01), true);
  });

  test('rechaza montos con más decimales de los permitidos', () => {
    assert.equal(esMultiploDe(658.242, 0.01), false);
    assert.equal(esMultiploDe(0.123456789, 1e-8), false);
    assert.equal(esMultiploDe(1e-9, 1e-8), false);
    assert.equal(esMultiploDe(0.1 + 0.2, 0.01), false);
  });

  test('CCF de 20 × $33.93 con 3 % de descuento valida contra el schema', () => {
    const { dte } = construirCCF({
      receptor: RECEPTOR_CCF,
      items: [{ descripcion: 'Harina', cantidad: 20, precioUni: 33.93, montoDescu: 20.358, ventaGravada: 658.242 }],
    });
    assert.equal(dte.cuerpoDocumento[0].ventaGravada, 658.242);
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, true, JSON.stringify(errores));
  });

  test('una línea con más de 8 decimales sigue rechazada', () => {
    const { dte } = construirCCF({
      receptor: RECEPTOR_CCF,
      items: [{ descripcion: 'Harina', cantidad: 1, precioUni: 10, ventaGravada: 10 }],
    });
    dte.cuerpoDocumento[0].precioUni = 10.123456789;
    const { valido, errores } = validarDte(dte);
    assert.equal(valido, false);
    assert.ok(errores.some((e) => e.keyword === 'multipleOf' && e.instancePath === '/cuerpoDocumento/0/precioUni'));
  });
});

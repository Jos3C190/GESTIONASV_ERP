const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { numeroALetras } = require('../../src/utils/numeroALetras');

describe('numeroALetras.js', () => {
  test('convierte un monto simple con centavos', () => {
    assert.equal(numeroALetras(1073.5), 'MIL SETENTA Y TRES 50/100 DÓLARES');
  });

  test('convierte cero', () => {
    assert.equal(numeroALetras(0), 'CERO 00/100 DÓLARES');
  });

  test('convierte exactamente cien', () => {
    assert.equal(numeroALetras(100), 'CIEN 00/100 DÓLARES');
  });

  test('convierte un valor con millones', () => {
    assert.equal(numeroALetras(1234567.89), 'UN MILLÓN DOSCIENTOS TREINTA Y CUATRO MIL QUINIENTOS SESENTA Y SIETE 89/100 DÓLARES');
  });

  test('siempre devuelve centavos con 2 dígitos (padding)', () => {
    assert.match(numeroALetras(19.05), /05\/100 DÓLARES$/);
    assert.match(numeroALetras(19.5), /50\/100 DÓLARES$/);
  });

  test('escribe correctamente las veintenas contractas', () => {
    assert.equal(numeroALetras(21), 'VEINTIUNO 00/100 DÓLARES');
    assert.equal(numeroALetras(22), 'VEINTIDÓS 00/100 DÓLARES');
    assert.equal(numeroALetras(23), 'VEINTITRÉS 00/100 DÓLARES');
    assert.equal(numeroALetras(26), 'VEINTISÉIS 00/100 DÓLARES');
  });

  test('apocopa UNO y VEINTIUNO delante de MIL y MILLONES', () => {
    assert.equal(numeroALetras(21000), 'VEINTIÚN MIL 00/100 DÓLARES');
    assert.equal(numeroALetras(31000), 'TREINTA Y UN MIL 00/100 DÓLARES');
    assert.equal(numeroALetras(101000), 'CIENTO UN MIL 00/100 DÓLARES');
    assert.equal(numeroALetras(21000000), 'VEINTIÚN MILLONES 00/100 DÓLARES');
    assert.equal(numeroALetras(1001001), 'UN MILLÓN MIL UNO 00/100 DÓLARES');
    assert.equal(numeroALetras(21021), 'VEINTIÚN MIL VEINTIUNO 00/100 DÓLARES');
  });

  test('lleva tilde en DIECISÉIS y calcula los centavos sin desbordar', () => {
    assert.equal(numeroALetras(16), 'DIECISÉIS 00/100 DÓLARES');
    assert.equal(numeroALetras(0.29), 'CERO 29/100 DÓLARES');
    assert.equal(numeroALetras(788.18), 'SETECIENTOS OCHENTA Y OCHO 18/100 DÓLARES');
    assert.throws(() => numeroALetras(1e9), /rango/);
  });

  test('nunca devuelve string vacío o con espacios dobles', () => {
    for (const monto of [0, 1, 10, 21, 100, 101, 999, 1000, 1001, 15000, 999999.99]) {
      const texto = numeroALetras(monto);
      assert.ok(texto.length > 0, `monto ${monto} produjo string vacío`);
      assert.doesNotMatch(texto, /\s{2,}/, `monto ${monto} produjo espacios dobles: "${texto}"`);
    }
  });
});

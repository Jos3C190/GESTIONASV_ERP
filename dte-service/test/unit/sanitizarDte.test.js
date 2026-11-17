const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { sanitizarProfundo } = require('../../src/utils/sanitizarDte');

describe('sanitizarDte.js', () => {
  test('quita un punto y coma suelto al final de un string', () => {
    assert.equal(sanitizarProfundo('Calle Principal #123;'), 'Calle Principal #123');
  });

  test('quita punto y coma seguido de espacios al final', () => {
    assert.equal(sanitizarProfundo('Calle Principal #123;   '), 'Calle Principal #123');
  });

  test('quita espacios en blanco sueltos al final aunque no haya punto y coma', () => {
    assert.equal(sanitizarProfundo('Cliente de Prueba   '), 'Cliente de Prueba');
  });

  test('NO toca punto y coma que no está al final (es contenido legítimo)', () => {
    assert.equal(sanitizarProfundo('Producto A; incluye envío'), 'Producto A; incluye envío');
  });

  test('quita caracteres de control no imprimibles', () => {
    const conControl = 'Texto\x00con\x1Fcontrol';
    assert.equal(sanitizarProfundo(conControl), 'Textoconcontrol');
  });

  test('normaliza a NFC (misma forma Unicode)', () => {
    // "é" como un solo code point (NFC) vs "e" + acento combinante (NFD)
    const nfd = 'cafe\u0301'; // e + ´ combinante
    const resultado = sanitizarProfundo(nfd);
    assert.equal(resultado, 'café'.normalize('NFC'));
  });

  test('recorre objetos anidados y arreglos, sanitizando cada string', () => {
    const dte = {
      identificacion: { codigoGeneracion: 'ABC-123' },
      receptor: { nombre: 'Cliente Final;  ', direccion: { complemento: 'Calle 1;' } },
      cuerpoDocumento: [{ descripcion: 'Item 1;' }, { descripcion: 'Item 2' }],
    };
    const limpio = sanitizarProfundo(dte);
    assert.equal(limpio.receptor.nombre, 'Cliente Final');
    assert.equal(limpio.receptor.direccion.complemento, 'Calle 1');
    assert.equal(limpio.cuerpoDocumento[0].descripcion, 'Item 1');
    assert.equal(limpio.cuerpoDocumento[1].descripcion, 'Item 2');
  });

  test('no toca valores no-string (números, booleanos, null)', () => {
    const dte = { cantidad: 5, activo: true, receptor: null, precio: 10.5 };
    const limpio = sanitizarProfundo(dte);
    assert.deepEqual(limpio, dte);
  });

  test('no muta el objeto original (devuelve uno nuevo)', () => {
    const original = { nombre: 'Test;' };
    const limpio = sanitizarProfundo(original);
    assert.equal(original.nombre, 'Test;'); // el original queda intacto
    assert.equal(limpio.nombre, 'Test');
  });
});

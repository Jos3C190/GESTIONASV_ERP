require('../setup-env');
const assert = require('node:assert/strict');
const { describe, test } = require('node:test');
const config = require('../../src/config');
const registry = require('../../src/services/issuerRegistry');

// En pruebas el despliegue opera en el modo de DTE_MODE (hacienda-test) y el NIT
// heredado del entorno es 06141804941035.
const MODO = config.dteMode;
const OTRO_MODO = MODO === 'simulated' ? 'hacienda-test' : 'simulated';

function codigo(fn) {
  try {
    fn();
  } catch (error) {
    assert.ok(error instanceof registry.IssuerError, error);
    return error.code;
  }
  return null;
}

describe('registro de emisores', () => {
  test('registra, normaliza el NIT y actualiza sin duplicar', () => {
    const creado = registry.registrar('0614-180494-103-9', {
      nombre: 'Panificadora Uno', modo: MODO, tiposHabilitados: ['03', '01', '01'],
    });
    assert.equal(creado.nit, '06141804941039');
    assert.deepEqual(creado.tiposHabilitados, ['01', '03']);
    assert.equal(creado.activo, true);
    const actualizado = registry.registrar('06141804941039', {
      nombre: 'Panificadora Uno', modo: MODO, tiposHabilitados: ['01'], activo: false,
    });
    assert.deepEqual(actualizado.tiposHabilitados, ['01']);
    assert.equal(actualizado.activo, false);
    assert.equal(registry.listar().filter((e) => e.nit === '06141804941039').length, 1);
  });

  test('rechaza datos inválidos', () => {
    assert.equal(codigo(() => registry.registrar('123', { nombre: 'X', modo: MODO })), 'INVALID_ISSUER');
    assert.equal(codigo(() => registry.registrar('061418049410', { nombre: ' ', modo: MODO })), 'INVALID_ISSUER');
    assert.equal(codigo(() => registry.registrar('061418049', { nombre: 'X', modo: 'otro' })), 'INVALID_ISSUER_MODE');
    assert.equal(
      codigo(() => registry.registrar('061418049', { nombre: 'X', modo: MODO, tiposHabilitados: ['1'] })),
      'INVALID_ISSUER'
    );
  });

  test('exige emisor registrado, activo, en el modo del despliegue y con el tipo habilitado', () => {
    assert.equal(codigo(() => registry.exigirEmision(null, '01')), 'ISSUER_REQUIRED');
    assert.equal(codigo(() => registry.exigirEmision('99999999999999', '01')), 'UNAUTHORIZED_ISSUER');
    // El emisor heredado del entorno sigue autorizado aunque no esté registrado.
    assert.equal(registry.exigirEmision('06141804941035', '01'), null);

    registry.registrar('11111111111111', { nombre: 'Activo', modo: MODO, tiposHabilitados: ['01'] });
    assert.equal(registry.exigirEmision('11111111111111', '01').nombre, 'Activo');
    assert.equal(codigo(() => registry.exigirEmision('11111111111111', '03')), 'DTE_DOCUMENT_TYPE_NOT_ALLOWED');

    registry.registrar('22222222222222', { nombre: 'Inactivo', modo: MODO, tiposHabilitados: ['01'], activo: false });
    assert.equal(codigo(() => registry.exigirEmision('22222222222222', '01')), 'ISSUER_INACTIVE');
    assert.equal(registry.autorizado('22222222222222'), false);

    registry.registrar('33333333333333', { nombre: 'Otro modo', modo: OTRO_MODO, tiposHabilitados: ['01'] });
    assert.equal(codigo(() => registry.exigirEmision('33333333333333', '01')), 'ISSUER_MODE_UNAVAILABLE');
  });
});

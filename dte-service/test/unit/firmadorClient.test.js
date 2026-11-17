const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { validarRespuestaFirmador, FirmadorError } = require('../../src/services/firmadorClient');

describe('firmadorClient.js', () => {
  test('acepta un JWS compacto con status OK', () => {
    assert.equal(validarRespuestaFirmador({ status: 'OK', body: 'header.payload.signature' }), 'header.payload.signature');
  });

  test('acepta la respuesta raw de un firmador compatible que devuelve directamente el JWS', () => {
    assert.equal(validarRespuestaFirmador('header.payload.signature'), 'header.payload.signature');
  });

  test('rechaza status ERROR aunque el HTTP haya sido exitoso', () => {
    assert.throws(
      () => validarRespuestaFirmador({ status: 'ERROR', body: 'header.payload.signature' }),
      (err) => err instanceof FirmadorError && /rechazó la solicitud \(sin código\)/.test(err.message) && err.configuracion === false,
    );
  });

  test('propaga código y mensaje del firmador oficial y marca los errores de configuración', () => {
    // FirmarDocumentoController responde HTTP 200 con { status: "ERROR", body: { codigo, mensaje } }.
    for (const codigo of ['803', '809', '812']) {
      assert.throws(
        () => validarRespuestaFirmador({ status: 'ERROR', body: { codigo, mensaje: ['Detalle del firmador'] } }),
        (err) => err instanceof FirmadorError
          && err.codigoFirmador === codigo
          && err.configuracion === true
          && err.message.includes(`(${codigo})`)
          && err.message.includes('Detalle del firmador'),
      );
    }
  });

  test('un error del firmador ajeno a la configuración no se marca como tal', () => {
    assert.throws(
      () => validarRespuestaFirmador({ status: 'ERROR', body: { codigo: 801, mensaje: 'Error interno' } }),
      (err) => err instanceof FirmadorError && err.codigoFirmador === '801' && err.configuracion === false,
    );
  });

  test('rechaza respuestas que no son JWS compacto', () => {
    assert.throws(() => validarRespuestaFirmador({ status: 'OK', body: 'texto-firmado' }), /JWS compacto válido/);
    assert.throws(() => validarRespuestaFirmador({ status: 'OK', body: 'header..signature' }), /JWS compacto válido/);
  });
});

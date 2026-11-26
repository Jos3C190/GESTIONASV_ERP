const { test, describe, afterEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const config = require('../../src/config');
const issuerContext = require('../../src/services/issuerContext');
const { relojDemostracion } = require('../../src/middleware/relojDemostracion');
const { fechaHoraSV, ahora } = require('../../src/utils/fechaHoraSV');

function respuesta() {
  return {
    codigo: null,
    cuerpo: null,
    status(codigo) {
      this.codigo = codigo;
      return this;
    },
    json(cuerpo) {
      this.cuerpo = cuerpo;
      return this;
    },
  };
}

describe('relojDemostracion', () => {
  const original = config.demoClockEnabled;
  const simulado = issuerContext.simulado;
  afterEach(() => {
    config.demoClockEnabled = original;
    issuerContext.simulado = simulado;
  });

  test('sin encabezado no cambia nada', () => {
    let llamado = false;
    relojDemostracion({ headers: {} }, respuesta(), () => {
      llamado = true;
    });
    assert.equal(llamado, true);
  });

  test('fija fecEmi y horEmi al instante pedido durante la solicitud', () => {
    config.demoClockEnabled = true;
    issuerContext.simulado = () => true;
    let dentro = null;
    relojDemostracion({ headers: { 'x-dte-demo-clock': '2026-10-15T15:30:00Z' } }, respuesta(), () => {
      dentro = fechaHoraSV();
    });
    assert.deepEqual(dentro, { fecha: '2026-10-15', hora: '09:30:00', anio: 2026 });
    assert.notEqual(ahora().toISOString(), '2026-10-15T15:30:00.000Z');
  });

  test('se rechaza si el entorno no lo habilita', () => {
    config.demoClockEnabled = false;
    const res = respuesta();
    relojDemostracion({ headers: { 'x-dte-demo-clock': '2026-10-15T15:30:00Z' } }, res, () => {
      assert.fail('no debe continuar');
    });
    assert.equal(res.codigo, 400);
    assert.equal(res.cuerpo.code, 'DEMO_CLOCK_NOT_ALLOWED');
  });

  test('se rechaza con un emisor que no es simulado', () => {
    config.demoClockEnabled = true;
    issuerContext.simulado = () => false;
    const res = respuesta();
    relojDemostracion({ headers: { 'x-dte-demo-clock': '2026-10-15T15:30:00Z' } }, res, () => {
      assert.fail('no debe continuar');
    });
    assert.equal(res.cuerpo.code, 'DEMO_CLOCK_NOT_ALLOWED');
  });

  test('rechaza instantes inválidos o futuros', () => {
    config.demoClockEnabled = true;
    issuerContext.simulado = () => true;
    for (const valor of ['no-es-fecha', '2999-01-01T00:00:00Z']) {
      const res = respuesta();
      relojDemostracion({ headers: { 'x-dte-demo-clock': valor } }, res, () => assert.fail('no debe continuar'));
      assert.equal(res.cuerpo.code, 'DEMO_CLOCK_INVALID');
    }
  });
});

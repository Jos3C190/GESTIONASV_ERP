const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { generarNumeroControl } = require('../../src/utils/numeroControl');
const correlativoStore = require('../../src/services/correlativoStore');
const { usarZonaDelProceso, fijarInstante } = require('../_relojSV');

describe('numeroControl.js', () => {
  beforeEach(() => {
    correlativoStore.reiniciarAMemoria();
  });

  test('respeta el patrón EXACTO del schema oficial: DTE-tt-(M|B|S|P)dddPddd-ddddddddddddddd', () => {
    const numeroControl = generarNumeroControl({
      tipoDte: '01',
      tipoEstablecimiento: '02', // Casa Matriz -> M
      codEstablecimientoMH: '1',
      codPuntoVentaMH: '1',
    });
    assert.match(numeroControl, /^DTE-01-(M|B|S|P)[0-9]{3}P[0-9]{3}-[0-9]{15}$/);
    assert.equal(numeroControl.length, 31);
  });

  test('usa la letra correcta según CAT-009 tipo de establecimiento', () => {
    const casos = [
      ['01', 'S'], // Sucursal
      ['02', 'M'], // Casa Matriz
      ['04', 'B'], // Bodega
      ['07', 'P'], // Patio
    ];
    for (const [tipoEstablecimiento, letraEsperada] of casos) {
      const nc = generarNumeroControl({ tipoDte: '01', tipoEstablecimiento, codEstablecimientoMH: '1', codPuntoVentaMH: '1' });
      const letraReal = nc.split('-')[2][0];
      assert.equal(letraReal, letraEsperada, `tipoEstablecimiento ${tipoEstablecimiento} debería usar letra ${letraEsperada}`);
    }
  });

  test('rellena con ceros los códigos de establecimiento/punto de venta a 3 dígitos', () => {
    const nc = generarNumeroControl({ tipoDte: '01', tipoEstablecimiento: '02', codEstablecimientoMH: '1', codPuntoVentaMH: '2' });
    // DTE-01-M001P002-...
    assert.ok(nc.startsWith('DTE-01-M001P002-'), `esperaba M001P002, obtuve: ${nc}`);
  });

  test('el correlativo incrementa secuencialmente para la misma combinación', () => {
    const params = { tipoDte: '01', tipoEstablecimiento: '02', codEstablecimientoMH: '1', codPuntoVentaMH: '1' };
    const nc1 = generarNumeroControl(params);
    const nc2 = generarNumeroControl(params);
    const nc3 = generarNumeroControl(params);
    assert.ok(nc1.endsWith('000000000000001'));
    assert.ok(nc2.endsWith('000000000000002'));
    assert.ok(nc3.endsWith('000000000000003'));
  });

  test('el correlativo es independiente por tipo de DTE', () => {
    const base = { tipoEstablecimiento: '02', codEstablecimientoMH: '1', codPuntoVentaMH: '1' };
    const factura1 = generarNumeroControl({ ...base, tipoDte: '01' });
    const ccf1 = generarNumeroControl({ ...base, tipoDte: '03' });
    assert.ok(factura1.endsWith('000000000000001'));
    assert.ok(ccf1.endsWith('000000000000001')); // cada tipo lleva su propio correlativo
  });

  test('por defecto lleva el correlativo por el año de El Salvador, no el del proceso', (t) => {
    usarZonaDelProceso(t, 'UTC');
    fijarInstante(t, '2027-01-01T02:00:00.000Z'); // 31 de diciembre de 2026, 20:00 SV
    const anios = [];
    correlativoStore.usar((tipoDte, anio) => {
      anios.push(anio);
      return 1;
    });
    generarNumeroControl({ tipoDte: '01', tipoEstablecimiento: '02', codEstablecimientoMH: '1', codPuntoVentaMH: '1' });
    generarNumeroControl({ tipoDte: '01', tipoEstablecimiento: '02', codEstablecimientoMH: '1', codPuntoVentaMH: '1', anio: 2030 });
    assert.deepEqual(anios, [2026, 2030]);
  });

  test('lanza error con un tipo de establecimiento inválido', () => {
    assert.throws(
      () => generarNumeroControl({ tipoDte: '01', tipoEstablecimiento: '99', codEstablecimientoMH: '1', codPuntoVentaMH: '1' }),
      /Tipo de establecimiento inválido/
    );
  });
});

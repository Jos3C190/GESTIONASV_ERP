const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { verificarVentanaLote } = require('../../src/utils/ventanaHoraria');
const { ZONAS_DEL_PROCESO, usarZonaDelProceso, fijarInstante } = require('../_relojSV');

/** Instante de la hora dada del 19 de julio de 2026 en El Salvador (UTC-6). */
function horaSV(hora, minuto = 0, segundo = 0) {
  return new Date(Date.UTC(2026, 6, 19, hora + 6, minuto, segundo));
}

// [ambiente, hora SV, dentro de la ventana]
const CASOS = [
  ['00', [10], true],
  ['00', [7], false],
  ['00', [7, 59, 59], false],
  ['00', [8], true],
  ['00', [16, 59, 59], true],
  ['00', [17], false], // límite exclusivo
  ['00', [20], false],
  ['01', [23], true],
  ['01', [2], true], // madrugada
  ['01', [10], false], // mediodía
  ['01', [21, 59, 59], false],
  ['01', [22], true],
  ['01', [4, 59, 59], true],
  ['01', [5], false], // límite exclusivo
];

describe('ventanaHoraria.js', () => {
  for (const zona of ZONAS_DEL_PROCESO) {
    describe(`evalúa la hora de El Salvador con el proceso en ${zona}`, () => {
      for (const [ambiente, hms, dentro] of CASOS) {
        const [h, m = 0, s = 0] = hms;
        const etiqueta = [h, m, s].map((n) => String(n).padStart(2, '0')).join(':');
        test(`ambiente ${ambiente}: ${etiqueta} SV está ${dentro ? 'dentro' : 'fuera'} de la ventana`, (t) => {
          usarZonaDelProceso(t, zona);
          assert.equal(verificarVentanaLote(ambiente, horaSV(...hms)).dentroDeVentana, dentro);
        });
      }

      test('sin instante explícito usa la hora actual de El Salvador', (t) => {
        usarZonaDelProceso(t, zona);
        fijarInstante(t, horaSV(23).toISOString());
        assert.equal(verificarVentanaLote('01').dentroDeVentana, true);
        assert.equal(verificarVentanaLote('00').dentroDeVentana, false);
      });
    });
  }

  test('un ambiente desconocido no opina (dentroDeVentana=true por defecto)', () => {
    const r = verificarVentanaLote('99', horaSV(3));
    assert.equal(r.dentroDeVentana, true);
    assert.equal(r.ventana, null);
  });

  test('devuelve el texto de la ventana para mensajes de log/advertencia', () => {
    assert.equal(verificarVentanaLote('00', horaSV(10)).ventana, '08:00–17:00');
    assert.equal(verificarVentanaLote('01', horaSV(23)).ventana, '22:00–05:00');
  });
});

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { fechaHoraSV, ZONA_HORARIA_SV } = require('../../src/utils/fechaHoraSV');
const { ZONAS_DEL_PROCESO, BORDES_DIA_SV, usarZonaDelProceso, fijarInstante } = require('../_relojSV');

describe('fechaHoraSV.js', () => {
  for (const zona of ZONAS_DEL_PROCESO) {
    describe(`con el proceso en ${zona}`, () => {
      for (const borde of BORDES_DIA_SV) {
        test(`${borde.utc} es ${borde.fecha} ${borde.hora} en El Salvador`, (t) => {
          usarZonaDelProceso(t, zona);
          assert.deepEqual(fechaHoraSV(new Date(borde.utc)), {
            fecha: borde.fecha,
            hora: borde.hora,
            anio: Number(borde.fecha.slice(0, 4)),
          });
        });
      }

      test('sin argumento usa el instante actual', (t) => {
        usarZonaDelProceso(t, zona);
        fijarInstante(t, '2026-10-10T02:55:45.000Z');
        assert.deepEqual(fechaHoraSV(), { fecha: '2026-10-09', hora: '20:55:45', anio: 2026 });
      });
    });
  }

  test('el año cambia a la medianoche de El Salvador, no a la medianoche UTC', () => {
    assert.deepEqual(fechaHoraSV(new Date('2027-01-01T05:59:59.999Z')), { fecha: '2026-12-31', hora: '23:59:59', anio: 2026 });
    assert.deepEqual(fechaHoraSV(new Date('2027-01-01T06:00:00.000Z')), { fecha: '2027-01-01', hora: '00:00:00', anio: 2027 });
  });

  test('respeta el 29 de febrero de un año bisiesto', () => {
    assert.deepEqual(fechaHoraSV(new Date('2028-03-01T03:00:00.000Z')), { fecha: '2028-02-29', hora: '21:00:00', anio: 2028 });
  });

  test('trunca los milisegundos (horEmi es HH:MM:SS)', () => {
    assert.equal(fechaHoraSV(new Date('2026-10-10T02:00:00.999Z')).hora, '20:00:00');
  });

  test(`coincide con la base de zonas horarias (${ZONA_HORARIA_SV}) a lo largo de 2026 y 2027`, () => {
    const formato = new Intl.DateTimeFormat('en-CA', {
      timeZone: ZONA_HORARIA_SV,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    });
    const paso = (7 * 60 + 13) * 60 * 1000 + 17 * 1000; // paso irregular para recorrer todas las horas del día
    for (let ms = Date.parse('2026-01-01T00:00:00Z'); ms < Date.parse('2028-01-01T00:00:00Z'); ms += paso) {
      const partes = Object.fromEntries(formato.formatToParts(new Date(ms)).map((p) => [p.type, p.value]));
      const esperado = { fecha: `${partes.year}-${partes.month}-${partes.day}`, hora: `${partes.hour}:${partes.minute}:${partes.second}` };
      const { fecha, hora } = fechaHoraSV(new Date(ms));
      assert.deepEqual({ fecha, hora }, esperado, new Date(ms).toISOString());
    }
  });

  test('rechaza valores que no son una fecha válida', () => {
    assert.throws(() => fechaHoraSV(new Date('no es fecha')), TypeError);
    assert.throws(() => fechaHoraSV('2026-10-10'), TypeError);
    assert.throws(() => fechaHoraSV(null), TypeError);
  });
});

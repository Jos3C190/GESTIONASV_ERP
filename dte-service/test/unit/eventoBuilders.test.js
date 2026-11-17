const { test, describe, afterEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { construirEventoContingencia } = require('../../src/services/eventoContingenciaBuilder');
const { validarEvento } = require('../../src/validators/dteSchema');
const { TIPO_CONTINGENCIA } = require('../../src/config/catalogs');
const { usarReloj } = require('../../src/utils/fechaHoraSV');
const { ZONAS_DEL_PROCESO, usarZonaDelProceso, fijarInstante } = require('../_relojSV');

describe('eventoContingenciaBuilder.js', () => {
  const documentos = [
    { tipoDte: '01', codigoGeneracion: 'ABCDEF12-3456-7890-ABCD-EF1234567890' },
    { tipoDte: '03', codigoGeneracion: 'ABCDEF12-3456-7890-ABCD-EF1234567891' },
  ];
  const emisor = {
    nit: '06141804941035',
    nombre: 'Emisor de Prueba S.A. de C.V.',
    telefono: '22221111',
    correo: 'facturacion@example.test',
    numeroControl: 'DTE-01-M001P002-000000000000007',
  };
  const periodo = { fInicio: '2026-07-13', fFin: '2026-07-13', hInicio: '08:00:00', hFin: '09:00:00' };
  const responsable = { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' };
  const base = { documentos, emisor, periodo, tipoContingencia: TIPO_CONTINGENCIA.NO_DISPONIBILIDAD_HACIENDA, responsable, ambiente: '00' };

  afterEach(() => usarReloj(null));

  test('genera un evento válido con el emisor de los documentos y la hora de El Salvador', () => {
    usarReloj(() => new Date('2026-07-13T16:05:00Z'));
    const { evento, codigoGeneracion } = construirEventoContingencia(base);
    const { valido, errores } = validarEvento('contingencia', evento);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(evento.identificacion.codigoGeneracion, codigoGeneracion);
    assert.equal(evento.identificacion.fTransmision, '2026-07-13');
    assert.equal(evento.identificacion.hTransmision, '10:05:00');
    assert.equal(evento.emisor.tipoEstablecimiento, '02');
    assert.equal(evento.emisor.codEstableMH, 'M001');
    assert.equal(evento.emisor.codPuntoVentaMH, 'P002');
    assert.equal(evento.emisor.nombreResponsable, 'Juan Pérez');
    assert.deepEqual(evento.detalleDTE.map((item) => [item.noItem, item.tipoDoc]), [[1, '01'], [2, '03']]);
    assert.equal(evento.motivo.motivoContingencia, null);
  });

  test('el tipo 5 exige motivo; tipos y periodos inválidos se rechazan', () => {
    assert.throws(() => construirEventoContingencia({ ...base, tipoContingencia: TIPO_CONTINGENCIA.OTRO }), /motivoContingencia/);
    const conMotivo = construirEventoContingencia({ ...base, tipoContingencia: TIPO_CONTINGENCIA.OTRO, motivoContingencia: 'Corte del proveedor de nube' });
    assert.equal(conMotivo.evento.motivo.motivoContingencia, 'Corte del proveedor de nube');
    assert.throws(() => construirEventoContingencia({ ...base, tipoContingencia: 99 }), /CAT-005/);
    assert.throws(() => construirEventoContingencia({ ...base, periodo: { ...periodo, hFin: '07:00:00' } }), /anterior/);
  });

  test('exige documentos (máximo 1000) y un responsable válido', () => {
    assert.throws(() => construirEventoContingencia({ ...base, documentos: [] }), /al menos un documento/);
    const mil = Array.from({ length: 1001 }, (_, indice) => ({ tipoDte: '01', codigoGeneracion: `ABCDEF12-3456-7890-ABCD-${String(indice).padStart(12, '0')}` }));
    assert.throws(() => construirEventoContingencia({ ...base, documentos: mil }), /1000/);
    assert.throws(() => construirEventoContingencia({ ...base, responsable: { ...responsable, numeroDocumento: '1234' } }), /DUI/);
    assert.throws(() => construirEventoContingencia({ ...base, responsable: { nombre: 'X' } }), /responsable/);
  });

  for (const zona of ZONAS_DEL_PROCESO) {
    test(`fTransmision y hTransmision en hora de El Salvador a las 20:00 SV con el proceso en ${zona}`, (t) => {
      usarZonaDelProceso(t, zona);
      fijarInstante(t, '2026-10-10T02:00:00.000Z');
      const { evento } = construirEventoContingencia(base);
      assert.equal(evento.identificacion.fTransmision, '2026-10-09');
      assert.equal(evento.identificacion.hTransmision, '20:00:00');
    });
  }
});

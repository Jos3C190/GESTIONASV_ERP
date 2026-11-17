const { test, describe, afterEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const correlativoStore = require('../../src/services/correlativoStore');
const { usarReloj } = require('../../src/utils/fechaHoraSV');
const { ZONAS_DEL_PROCESO, usarZonaDelProceso, fijarInstante } = require('../_relojSV');
const { construirFactura, construirCCF } = require('../../src/services/dteBuilder');
const { construirEventoInvalidacion, TIPO_ANULACION } = require('../../src/services/eventoInvalidacionBuilder');
const { validarEvento } = require('../../src/validators/dteSchema');
const {
  sumarMeses,
  domingoDePascua,
  plazoInvalidacion,
  fechaDelEventoInvalidacion,
  fechaDeProcesamiento,
} = require('../../src/utils/plazosFiscales');

const SELLO = '2026A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8';
const REEMPLAZO = 'FFFFFFFF-1111-2222-3333-444444444444';
const PERSONA = { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' };
const RESCINDIR = { tipoAnulacion: TIPO_ANULACION.RESCINDIR_OPERACION, responsable: PERSONA, solicitante: PERSONA };
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

function facturaEmitida(fechaUtc, receptor = null) {
  usarReloj(() => new Date(fechaUtc));
  const { dte } = construirFactura({ receptor, items: [{ descripcion: 'Servicio', cantidad: 1, precioUni: 113, ventaGravada: 113 }] });
  return dte;
}

function ccfEmitido(fechaUtc) {
  usarReloj(() => new Date(fechaUtc));
  const { dte } = construirCCF({
    receptor: RECEPTOR_CCF,
    items: [{ descripcion: 'Servicio', cantidad: 1, precioUni: 100, ventaGravada: 100, ivaItem: 13 }],
  });
  return dte;
}

afterEach(() => {
  usarReloj(null);
  correlativoStore.reiniciarAMemoria();
  delete process.env.DTE_DIAS_INHABILES;
});

describe('plazosFiscales.js', () => {
  test('suma meses de calendario con el último día del mes cuando no existe', () => {
    assert.equal(sumarMeses('2025-10-09', 3), '2026-01-09');
    assert.equal(sumarMeses('2025-11-30', 3), '2026-02-28');
    assert.equal(sumarMeses('2023-11-30', 3), '2024-02-29');
  });

  test('calcula el domingo de Pascua (base de jueves y viernes santos)', () => {
    assert.equal(domingoDePascua(2026).toISOString().slice(0, 10), '2026-04-05');
    assert.equal(domingoDePascua(2025).toISOString().slice(0, 10), '2025-04-20');
  });

  test('FE, FEX y FSE: tres meses desde el sello (ejemplo del Manual Funcional)', () => {
    assert.deepEqual(plazoInvalidacion('01', '2025-11-11'), { regla: 'TRES_MESES_DESDE_SELLO', limite: '2026-02-11', estimado: false });
    assert.equal(plazoInvalidacion('14', '2025-11-30').limite, '2026-02-28');
  });

  test('CCF y demás: décimo día hábil del mes siguiente al sello', () => {
    // Ejemplo 2 del Manual Funcional: sello el 25-abr-2026 → hasta el 15-may-2026 (1 de mayo es asueto).
    assert.equal(plazoInvalidacion('03', '2026-04-25').limite, '2026-05-15');
    // Ejemplo 1: sello el 19-mar-2026 → hasta el 20-abr-2026. Con solo los asuetos del Código de
    // Trabajo el cálculo da una fecha anterior (estimado conservador); con los días inhábiles
    // adicionales de Semana Santa coincide con el manual.
    const estimado = plazoInvalidacion('03', '2026-03-19');
    assert.equal(estimado.estimado, true);
    assert.equal(estimado.limite, '2026-04-16');
    process.env.DTE_DIAS_INHABILES = '2026-04-01,2026-04-06';
    assert.equal(plazoInvalidacion('03', '2026-03-19').limite, '2026-04-20');
  });

  test('fecha del evento: la de generación en CCF; hasta 3 meses después en FE', () => {
    assert.equal(fechaDelEventoInvalidacion('03', '2026-03-29', '2026-04-04'), '2026-03-29');
    assert.equal(fechaDelEventoInvalidacion('01', '2026-01-09', '2026-03-01'), '2026-03-01');
    assert.equal(fechaDelEventoInvalidacion('01', '2026-01-09', '2026-05-01'), '2026-04-09');
  });

  test('interpreta fhProcesamiento de Hacienda', () => {
    assert.equal(fechaDeProcesamiento('14/10/2026 10:00:00'), '2026-10-14');
    assert.equal(fechaDeProcesamiento(undefined), null);
  });
});

describe('eventoInvalidacionBuilder.js', () => {
  test('TIPO_ANULACION coincide con el catálogo oficial CAT-024', () => {
    const cat024 = require('../../src/config/catalogs').catalogosRaw['CAT-024'];
    for (const valor of Object.values(TIPO_ANULACION)) {
      assert.ok(cat024.entradas.some((entrada) => Number(entrada.codigo) === valor), `CAT-024 debería incluir ${valor}`);
    }
  });

  test('FE sin receptor: rescindir genera un evento válido con emisor y fechas del DTE', () => {
    const dte = facturaEmitida('2026-10-14T18:00:00Z');
    usarReloj(() => new Date('2026-11-02T16:30:00Z')); // 10:30 en El Salvador
    const { evento, codigoGeneracion, requiereReemplazo } = construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: RESCINDIR });

    const { valido, errores } = validarEvento('invalidacion', evento);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(requiereReemplazo, false);
    assert.notEqual(codigoGeneracion, dte.identificacion.codigoGeneracion);
    assert.equal(evento.identificacion.ambiente, dte.identificacion.ambiente);
    assert.equal(evento.identificacion.fecEmi, '2026-11-02');
    assert.equal(evento.identificacion.horEmi, '10:30:00');
    assert.equal(evento.emisor.nit, dte.emisor.nit);
    assert.equal(evento.emisor.codEstableMH, 'M001');
    assert.equal(evento.emisor.codPuntoVentaMH, 'P001');
    assert.deepEqual(
      [evento.documento.tipoDocumento, evento.documento.numDocumento, evento.documento.nombre],
      [null, null, null],
      'una factura sin receptor se invalida con receptor null',
    );
    assert.equal(evento.documento.fecEmi, '2026-10-14');
    assert.equal(evento.documento.codigoGeneracionR, null);
  });

  test('FE con receptor identificado copia sus datos al evento', () => {
    const dte = facturaEmitida('2026-10-14T18:00:00Z', { tipoDocumento: '13', numDocumento: '01234567-8', nombre: 'Cliente Prueba', correo: 'c@p.com' });
    const { evento } = construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: RESCINDIR });
    assert.equal(evento.documento.tipoDocumento, '13');
    assert.equal(evento.documento.numDocumento, '01234567-8');
    assert.equal(evento.documento.nombre, 'Cliente Prueba');
    assert.equal(evento.documento.correo, 'c@p.com');
  });

  test('FE invalidada después de 3 meses usa como fecha del evento el máximo permitido', () => {
    const dte = facturaEmitida('2026-01-09T18:00:00Z');
    usarReloj(() => new Date('2026-05-01T18:00:00Z'));
    const { evento } = construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: RESCINDIR });
    assert.equal(evento.identificacion.fecEmi, '2026-04-09');
  });

  test('CCF: receptor 36 + NIT y fecha del evento igual a la de generación', () => {
    const dte = ccfEmitido('2026-03-29T18:00:00Z');
    usarReloj(() => new Date('2026-04-04T18:00:00Z'));
    const { evento } = construirEventoInvalidacion({
      dte,
      selloRecibido: SELLO,
      motivo: { ...RESCINDIR, tipoAnulacion: TIPO_ANULACION.ERROR_INFORMACION },
      codigoGeneracionReemplazo: REEMPLAZO,
    });
    assert.equal(validarEvento('invalidacion', evento).valido, true);
    assert.equal(evento.identificacion.fecEmi, '2026-03-29');
    assert.equal(evento.documento.tipoDocumento, '36');
    assert.equal(evento.documento.numDocumento, RECEPTOR_CCF.nit);
    assert.equal(evento.documento.nombre, RECEPTOR_CCF.nombre);
    assert.equal(evento.documento.codigoGeneracionR, REEMPLAZO);
  });

  test('tipos 1 y 3 exigen reemplazo; el tipo 2 lo prohíbe', () => {
    const dte = facturaEmitida('2026-10-14T18:00:00Z');
    for (const tipoAnulacion of [TIPO_ANULACION.ERROR_INFORMACION, TIPO_ANULACION.OTRO]) {
      assert.throws(
        () => construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: { ...RESCINDIR, tipoAnulacion, motivoAnulacion: 'Cambio de producto' } }),
        /reemplaza/,
      );
    }
    assert.throws(
      () => construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: RESCINDIR, codigoGeneracionReemplazo: REEMPLAZO }),
      /tipo 2/,
    );
    assert.throws(
      () => construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: { ...RESCINDIR, tipoAnulacion: TIPO_ANULACION.OTRO }, codigoGeneracionReemplazo: REEMPLAZO }),
      /motivo/,
    );
  });

  test('una Nota de Crédito se invalida sin reemplazo aunque el tipo sea 1', () => {
    const dte = ccfEmitido('2026-10-14T18:00:00Z');
    dte.identificacion.tipoDte = '05';
    const { evento, requiereReemplazo } = construirEventoInvalidacion({
      dte, selloRecibido: SELLO, motivo: { ...RESCINDIR, tipoAnulacion: TIPO_ANULACION.ERROR_INFORMACION },
    });
    assert.equal(requiereReemplazo, false);
    assert.equal(evento.documento.codigoGeneracionR, null);
  });

  test('valida responsable, solicitante y sello', () => {
    const dte = facturaEmitida('2026-10-14T18:00:00Z');
    assert.throws(() => construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: { ...RESCINDIR, responsable: { ...PERSONA, numeroDocumento: '012345678' } } }), /DUI/);
    assert.throws(() => construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: { ...RESCINDIR, solicitante: { ...PERSONA, tipoDocumento: '99' } } }), /CAT-022/);
    assert.throws(() => construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: { ...RESCINDIR, solicitante: { nombre: 'X' } } }), /solicita/);
    assert.throws(() => construirEventoInvalidacion({ dte, selloRecibido: 'corto', motivo: RESCINDIR }), /sello/);
    assert.throws(() => construirEventoInvalidacion({ dte: null, selloRecibido: SELLO, motivo: RESCINDIR }), /JSON completo/);
  });

  for (const zona of ZONAS_DEL_PROCESO) {
    test(`fecEmi y horEmi del evento en hora de El Salvador a las 20:00 SV con el proceso en ${zona}`, (t) => {
      const dte = facturaEmitida('2026-10-08T16:00:00Z');
      usarReloj(null);
      usarZonaDelProceso(t, zona);
      fijarInstante(t, '2026-10-10T02:00:00.000Z');
      const { evento } = construirEventoInvalidacion({ dte, selloRecibido: SELLO, motivo: RESCINDIR });
      assert.equal(evento.identificacion.fecEmi, '2026-10-09');
      assert.equal(evento.identificacion.horEmi, '20:00:00');
      assert.equal(evento.documento.fecEmi, dte.identificacion.fecEmi); // la del DTE invalidado no se recalcula
    });
  }
});

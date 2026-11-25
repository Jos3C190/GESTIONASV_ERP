const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const { construirFactura } = require('../../src/services/dteBuilder');
const { construirEventoRetorno } = require('../../src/services/eventoRetornoBuilder');
const { construirEventoInvalidacion } = require('../../src/services/eventoInvalidacionBuilder');
const { validarEvento } = require('../../src/validators/dteSchema');
const correlativoStore = require('../../src/services/correlativoStore');

const RECEPTOR = {
  tipoDocumento: '13',
  numDocumento: '01234567-8',
  nombre: 'María Rivas',
  direccion: { departamento: '06', municipio: '23', distrito: '14', complemento: 'Col. Escalón' },
  telefono: '22223333',
  correo: 'maria@example.com',
};

function factura() {
  return construirFactura({
    receptor: RECEPTOR,
    items: [
      { descripcion: 'Harina 50 lb', codigo: 'PRD-HAR-001', cantidad: 4, precioUni: 22.6, ventaGravada: 90.4 },
      { descripcion: 'Azúcar 10 kg', codigo: 'PRD-AZU-004', cantidad: 2, precioUni: 11.3, ventaGravada: 22.6 },
    ],
  }).dte;
}

// Devolución de una bolsa de harina: 22.60 con IVA (2.60 de IVA).
const UNA_HARINA = { numItem: 1, cantidad: 1, montoDescu: 0, ventaNoSuj: 0, ventaExenta: 0, ventaGravada: 22.6, ivaItem: 2.6 };

describe('eventoRetornoBuilder.js', () => {
  beforeEach(() => correlativoStore.reiniciarAMemoria());

  test('arma un evento de retorno válido contra fe-eret-v1 desde la factura', () => {
    const fe = factura();
    const { evento, codigoGeneracion } = construirEventoRetorno({ dte: fe, items: [UNA_HARINA] });
    const { valido, errores } = validarEvento('retorno', evento);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(evento.identificacion.tipoEvento, '18');
    assert.equal(evento.identificacion.version, 1);
    assert.equal(evento.identificacion.codigoGeneracion, codigoGeneracion);
    assert.notEqual(codigoGeneracion, fe.identificacion.codigoGeneracion);
    assert.deepEqual(evento.documentoRelacionado, [
      { tipoDocumento: '01', codigoGeneracion: fe.identificacion.codigoGeneracion, fechaEmision: fe.identificacion.fecEmi },
    ]);
    assert.match(evento.emisor.codEstableMH, /^[MSBP]\d{3}$/);
    assert.match(evento.emisor.codPuntoVentaMH, /^P\d{3}$/);
    assert.equal(evento.documento.nombre, 'María Rivas');
    const [linea] = evento.cuerpoDocumento;
    assert.equal(linea.codigoGeneracion, fe.identificacion.codigoGeneracion);
    assert.equal(linea.descripcion, 'Harina 50 lb');
    assert.equal(linea.precioUni, 22.6);
    assert.equal(evento.resumen.totalGravada, 22.6);
    assert.equal(evento.resumen.totalIva, 2.6);
    assert.equal(evento.resumen.montoTotalOperacion, 22.6);
    assert.equal(evento.resumen.totalPagar, 22.6);
    assert.equal(evento.resumen.ivaRete, 0);
  });

  test('no deja pasar de lo vendido ni repetir una línea', () => {
    const fe = factura();
    assert.throws(() => construirEventoRetorno({ dte: fe, items: [{ ...UNA_HARINA, cantidad: 5, ventaGravada: 113, ivaItem: 13 }] }), /no pasar de lo vendido/);
    assert.throws(() => construirEventoRetorno({ dte: fe, items: [{ ...UNA_HARINA, numItem: 9 }] }), /no tiene la línea 9/);
    assert.throws(() => construirEventoRetorno({ dte: fe, items: [UNA_HARINA, UNA_HARINA] }), /se repite/);
    assert.throws(() => construirEventoRetorno({ dte: fe, items: [{ ...UNA_HARINA, ventaGravada: 30 }] }), /no coincide con la venta/);
    assert.throws(() => construirEventoRetorno({ dte: fe, items: [] }), /al menos una línea/);
  });

  test('solo se aplica a una factura', () => {
    const fe = factura();
    const ccf = { ...fe, identificacion: { ...fe.identificacion, tipoDte: '03' } };
    assert.throws(() => construirEventoRetorno({ dte: ccf, items: [UNA_HARINA] }), /Factura Electrónica/);
  });

  test('el retorno se anula con una invalidación tipo 2 sin número de control ni reemplazo', () => {
    const fe = factura();
    const { evento } = construirEventoRetorno({ dte: fe, items: [UNA_HARINA] });
    const persona = { nombre: 'Ana López', tipoDocumento: '13', numeroDocumento: '01234567-8' };
    const { evento: anulacion } = construirEventoInvalidacion({
      dte: evento,
      selloRecibido: 'A'.repeat(40),
      motivo: { tipoAnulacion: 2, responsable: persona, solicitante: persona },
      contactoEmisor: { telefono: fe.emisor.telefono, correo: fe.emisor.correo },
    });
    const { valido, errores } = validarEvento('invalidacion', anulacion);
    assert.equal(valido, true, JSON.stringify(errores));
    assert.equal(anulacion.documento.tipoDte, '18');
    assert.equal(anulacion.documento.numeroControl, null);
    assert.equal(anulacion.documento.codigoGeneracionR, null);
    assert.equal(anulacion.documento.codigoGeneracion, evento.identificacion.codigoGeneracion);
    assert.equal(anulacion.documento.nombre, 'María Rivas');
    assert.equal(anulacion.identificacion.fecEmi, evento.identificacion.fecEmi);
  });
});

const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const correlativoStore = require('../../src/services/correlativoStore');
const { usarReloj } = require('../../src/utils/fechaHoraSV');
const { construirFactura, construirCCF } = require('../../src/services/dteBuilder');
const { construirEventoInvalidacion, TIPO_ANULACION } = require('../../src/services/eventoInvalidacionBuilder');
const { generarPDFEventoInvalidacion } = require('../../src/services/representacionEventoInvalidacionBuilder');
const { contarPaginas, textoCompleto } = require('./_pdfTexto');

const SELLO_DTE = '2026A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8';
const SELLO_EVENTO = '2026F8E7D6C5B4A3F2E1D0C9B8A7F6E5D4C3B2A1';
const REEMPLAZO = 'FFFFFFFF-1111-2222-3333-444444444444';
const logo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAADUlEQVR4nGMQCVjwHwADhAIEWAExyQAAAABJRU5ErkJggg==', 'base64');

afterEach(() => {
  usarReloj(null);
  correlativoStore.reiniciarAMemoria();
});

/** Archivo del evento tal como lo entrega /eventos/:codigo/json: JSON + sello. */
function archivoCcfInvalidado({ selloRecibido = SELLO_EVENTO } = {}) {
  usarReloj(() => new Date('2026-10-14T18:00:00Z'));
  const { dte } = construirCCF({
    receptor: {
      nit: '06141804941099', nrc: '7654321', nombre: 'Cliente Empresa S.A. de C.V.', codActividad: '62010',
      descActividad: 'Programación informática',
      direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Colonia Escalón' },
      telefono: '22223333', correo: 'compras@empresa.com',
    },
    items: [{ descripcion: 'Servicio', cantidad: 1, precioUni: 100, ventaGravada: 100, ivaItem: 13 }],
  });
  const { evento } = construirEventoInvalidacion({
    dte,
    selloRecibido: SELLO_DTE,
    motivo: {
      tipoAnulacion: TIPO_ANULACION.ERROR_INFORMACION,
      motivoAnulacion: 'El NRC del receptor estaba equivocado',
      responsable: { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' },
      solicitante: { nombre: 'Ana López', tipoDocumento: '36', numeroDocumento: '06141804941035' },
    },
    codigoGeneracionReemplazo: REEMPLAZO,
  });
  return { dte, archivo: { ...evento, firmaElectronica: 'JWS.FIRMADO.FALSO', selloRecibido } };
}

test('el PDF del evento muestra identificación, partes, motivo, documento y reemplazo en una página', async () => {
  const { dte, archivo } = archivoCcfInvalidado();
  const antes = JSON.stringify(archivo);
  const pdf = await generarPDFEventoInvalidacion(archivo, { logoPngBuffer: logo });
  assert.equal(pdf.subarray(0, 4).toString('ascii'), '%PDF');
  assert.equal(contarPaginas(pdf), 1);
  assert.equal(JSON.stringify(archivo), antes, 'el PDF no modifica el evento');

  // Las celdas que envuelven parten el texto en líneas: se compara con espacios simples.
  const texto = textoCompleto(pdf).replace(/\s+/g, ' ');
  for (const esperado of [
    'EVENTO DE INVALIDACIÓN', 'Versión 3',
    archivo.identificacion.codigoGeneracion, archivo.identificacion.horEmi, SELLO_EVENTO,
    'Identificación del emisor', 'Identificación del receptor',
    'Cliente Empresa S.A. de C.V.', '0614-180494-109-9', 'compras@empresa.com',
    'Error en la Información del Documento Tributario Electrónico a invalidar.',
    'El NRC del receptor estaba equivocado',
    'Juan Pérez', '01234567-8', 'Ana López', '0614-180494-103-5',
    'Comprobante de crédito fiscal', dte.identificacion.codigoGeneracion, SELLO_DTE,
    dte.identificacion.numeroControl, '14 Oct 2026', REEMPLAZO,
  ]) {
    assert.ok(texto.includes(esperado), `falta «${esperado}» en el PDF`);
  }
  assert.doesNotMatch(texto, /SIN VALIDEZ FISCAL/);
});

test('sin documento de reemplazo y sin receptor el PDF lo indica sin dejar huecos', async () => {
  usarReloj(() => new Date('2026-10-14T18:00:00Z'));
  const { dte } = construirFactura({ receptor: null, items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 11.3, ventaGravada: 11.3 }] });
  const { evento } = construirEventoInvalidacion({
    dte,
    selloRecibido: SELLO_DTE,
    motivo: {
      tipoAnulacion: TIPO_ANULACION.RESCINDIR_OPERACION,
      responsable: { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' },
      solicitante: { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' },
    },
  });
  const texto = textoCompleto(await generarPDFEventoInvalidacion({ ...evento, selloRecibido: SELLO_EVENTO }));
  assert.match(texto, /Rescindir de la operación realizada/);
  assert.match(texto, /Factura/);
  assert.match(texto, /que reemplaza al invalidado:\s*No aplica/);
});

test('el evento simulado lleva la marca SIN VALIDEZ FISCAL y el identificador simulado', async () => {
  const marcador = 'SIMULATED-EVT-0123456789ABCDEF0123456789ABCDEF';
  const { archivo } = archivoCcfInvalidado({ selloRecibido: marcador });
  const pdf = await generarPDFEventoInvalidacion(archivo, { simulation: true, logoPngBuffer: logo });
  assert.equal(contarPaginas(pdf), 1);
  const texto = textoCompleto(pdf);
  assert.match(texto, /SIMULADO - SIN VALIDEZ FISCAL/);
  assert.match(texto, /Identificador simulado/);
  assert.ok(texto.includes(marcador));
  assert.doesNotMatch(texto, /Sello de Recepción/);
});

test('sin sello o sin documento no se genera el PDF del evento', async () => {
  const { archivo } = archivoCcfInvalidado();
  await assert.rejects(generarPDFEventoInvalidacion({ ...archivo, selloRecibido: '' }), /sin sello de recepción/);
  await assert.rejects(generarPDFEventoInvalidacion({ ...archivo, documento: undefined }), /identificación ni documento/);
});

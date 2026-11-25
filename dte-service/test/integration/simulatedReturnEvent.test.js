const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');

// Evento de Retorno (V4d2 del ERP) contra el proveedor simulado: nunca firma con
// el certificado ni llama a Hacienda.
process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.DTE_SIMULATION_RUN_ID = 'return-event-run';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '06141804941035';
process.env.MS_AUTH_DESHABILITADA = 'false';
process.env.MS_API_KEY_SCOPES = 'issue,read,simulate,invalidate';
require('../_setup');
const { db } = require('../../src/db');
const { textoCompleto } = require('../unit/_pdfTexto');

const API_KEY = 'clave-de-prueba-para-tests';
const persona = { nombre: 'Ana López', tipoDocumento: '13', numeroDocumento: '01234567-8' };
let server;
let baseUrl;

before(async () => {
  const firmadorClient = require('../../src/services/firmadorClient');
  const haciendaClient = require('../../src/services/haciendaClient');
  firmadorClient.firmarDocumento = async () => { throw new Error('El modo simulado intentó usar el firmador'); };
  haciendaClient.transmitirDte = async () => { throw new Error('El modo simulado intentó usar Hacienda'); };
  haciendaClient.anularDte = async () => { throw new Error('El modo simulado intentó invalidar ante Hacienda'); };
  const app = require('../../src/app');
  await new Promise((resolve) => {
    server = app.listen(0, () => {
      baseUrl = `http://127.0.0.1:${server.address().port}`;
      resolve();
    });
  });
});

after(() => server?.close());

function headers(extra = {}) {
  return { Authorization: `Bearer ${API_KEY}`, ...extra };
}

async function post(path, clave, cuerpo, extra = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': clave, ...extra }),
    body: JSON.stringify(cuerpo),
  });
  return { response, body: await response.json() };
}

async function factura(clave) {
  const { response, body } = await post('/api/dte/factura', clave, {
    receptor: {
      tipoDocumento: '13',
      numDocumento: '01234567-8',
      nombre: 'María Rivas',
      direccion: { departamento: '06', municipio: '23', distrito: '14', complemento: 'Col. Escalón' },
      telefono: '22223333',
      correo: 'maria@example.com',
    },
    items: [
      { descripcion: 'Harina 50 lb', cantidad: 4, precioUni: 22.6, ventaGravada: 90.4 },
      { descripcion: 'Azúcar 10 kg', cantidad: 2, precioUni: 11.3, ventaGravada: 22.6 },
    ],
    pago: { codigo: '01', montoPago: 113, referencia: null, numPagoElectronico: null },
  });
  assert.equal(response.status, 201, JSON.stringify(body));
  assert.equal(body.estado, 'SIMULADO');
  return body.codigoGeneracion;
}

const UNA_HARINA = { numItem: 1, cantidad: 1, montoDescu: 0, ventaNoSuj: 0, ventaExenta: 0, ventaGravada: 22.6, ivaItem: 2.6 };

test('aplica un retorno simulado, lo entrega en JSON y PDF y bloquea invalidar la factura', async () => {
  const codigoFactura = await factura('ret-fe-0001');
  const primero = await post(`/api/dte/${codigoFactura}/retorno`, 'ret-evt-0001', { items: [UNA_HARINA] });
  assert.equal(primero.response.status, 200, JSON.stringify(primero.body));
  assert.equal(primero.body.estado, 'SIMULADO');
  assert.equal(primero.body.tipoEvento, 'RETORNO');
  assert.equal(primero.body.codigoGeneracionDte, codigoFactura);
  assert.match(primero.body.simulationMarkerEvento, /^SIMULATED-EVT-[0-9A-F]{32}$/);
  const repetido = await post(`/api/dte/${codigoFactura}/retorno`, 'ret-evt-0001', { items: [UNA_HARINA] });
  assert.deepEqual(repetido.body, primero.body);

  const codigoRetorno = primero.body.codigoGeneracionEvento;
  const evento = db.prepare('SELECT * FROM eventos WHERE codigo_generacion = ?').get(codigoRetorno);
  assert.equal(evento.tipo, 'RETORNO');
  assert.equal(evento.modo_emision, 'SIMULATED');
  assert.equal(evento.sello_recepcion, null);

  const json = await fetch(`${baseUrl}/api/dte/eventos/${codigoRetorno}/json`, { headers: headers() });
  assert.equal(json.status, 200);
  const archivo = await json.json();
  assert.equal(archivo.identificacion.tipoEvento, '18');
  assert.equal(archivo.selloRecibido, primero.body.simulationMarkerEvento);
  assert.equal(archivo.resumen.totalPagar, 22.6);

  const pdf = await fetch(`${baseUrl}/api/dte/eventos/${codigoRetorno}/pdf/render`, {
    method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: '{}',
  });
  assert.equal(pdf.status, 200, await pdf.clone().text());
  const texto = textoCompleto(Buffer.from(await pdf.arrayBuffer()));
  assert.match(texto, /EVENTO DE RETORNO/);
  assert.match(texto, /Harina 50 lb/);
  assert.match(texto, /SIN VALIDEZ FISCAL/);

  // Una factura con retorno vigente no se invalida (Manual VII, nota 3).
  const anularFactura = await post(`/api/dte/${codigoFactura}/anular`, 'ret-inv-fe-01', { motivo: { tipoAnulacion: 2, responsable: persona, solicitante: persona } });
  assert.equal(anularFactura.response.status, 409, JSON.stringify(anularFactura.body));
  assert.equal(anularFactura.body.code, 'DTE_HAS_RETURN');

  // Se anula el retorno y después ya se puede invalidar la factura.
  const anulacion = await post(`/api/dte/eventos/${codigoRetorno}/anular`, 'ret-anul-0001', { motivo: { tipoAnulacion: 2, responsable: persona, solicitante: persona } });
  assert.equal(anulacion.response.status, 200, JSON.stringify(anulacion.body));
  assert.equal(anulacion.body.estado, 'RETORNO_INVALIDADO');
  const anulado = db.prepare('SELECT estado FROM eventos WHERE codigo_generacion = ?').get(codigoRetorno);
  assert.equal(anulado.estado, 'SIMULADO_INVALIDADO');
  const archivoAnulacion = await (await fetch(`${baseUrl}/api/dte/eventos/${anulacion.body.codigoGeneracionEvento}/json`, { headers: headers() })).json();
  assert.equal(archivoAnulacion.documento.tipoDte, '18');
  assert.equal(archivoAnulacion.documento.numeroControl, null);
  const otra = await post(`/api/dte/eventos/${codigoRetorno}/anular`, 'ret-anul-0002', { motivo: { tipoAnulacion: 2, responsable: persona, solicitante: persona } });
  assert.equal(otra.response.status, 409);
  assert.equal(otra.body.code, 'RETURN_ALREADY_INVALIDATED');

  const ahora = await post(`/api/dte/${codigoFactura}/anular`, 'ret-inv-fe-02', { motivo: { tipoAnulacion: 2, responsable: persona, solicitante: persona } });
  assert.equal(ahora.response.status, 200, JSON.stringify(ahora.body));
});

test('rechazos: escenario rejected y líneas inválidas', async () => {
  const codigoFactura = await factura('ret-fe-0002');
  const rechazado = await post(`/api/dte/${codigoFactura}/retorno`, 'ret-evt-0010', { items: [UNA_HARINA] }, { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.equal(rechazado.response.status, 422, JSON.stringify(rechazado.body));
  assert.equal(rechazado.body.code, 'RETURN_REJECTED');
  const invalido = await post(`/api/dte/${codigoFactura}/retorno`, 'ret-evt-0011', { items: [{ ...UNA_HARINA, cantidad: 9 }] });
  assert.equal(invalido.response.status, 400, JSON.stringify(invalido.body));
  assert.equal(invalido.body.code, 'INVALID_RETURN_REQUEST');
  const inexistente = await post('/api/dte/00000000-0000-4000-8000-000000000000/retorno', 'ret-evt-0012', { items: [UNA_HARINA] });
  assert.equal(inexistente.response.status, 404);
});

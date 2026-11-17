const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.DTE_SIMULATION_RUN_ID = 'fiscal-events-run';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '06141804941035';
process.env.MS_AUTH_DESHABILITADA = 'false';
process.env.MS_API_KEYS = 'clave-de-prueba-para-tests,clave-sin-scope-simulate';
process.env.MS_API_KEY_SCOPES = 'issue,read,simulate;issue,read';
require('../_setup');
const { db } = require('../../src/db');
const { textoCompleto } = require('../unit/_pdfTexto');

const API_KEY = 'clave-de-prueba-para-tests';
const responsable = { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' };
const solicitante = { nombre: 'Ana López', tipoDocumento: '36', numeroDocumento: '06141804941035' };
let server;
let baseUrl;

before(async () => {
  // Cualquier uso de los clientes reales en simulado es un error de diseño.
  const firmadorClient = require('../../src/services/firmadorClient');
  const haciendaClient = require('../../src/services/haciendaClient');
  firmadorClient.firmarDocumento = async () => { throw new Error('El modo simulado intentó usar el firmador'); };
  haciendaClient.anularDte = async () => { throw new Error('El modo simulado intentó invalidar ante Hacienda'); };
  haciendaClient.transmitirDte = async () => { throw new Error('El modo simulado intentó usar Hacienda'); };
  const app = require('../../src/app');
  await new Promise((resolve) => {
    server = app.listen(0, () => {
      baseUrl = `http://127.0.0.1:${server.address().port}`;
      resolve();
    });
  });
});

after(() => server?.close());

function headers(extra = {}, apiKey = API_KEY) {
  return { Authorization: `Bearer ${apiKey}`, ...extra };
}

async function emitirFactura(clave, extra = {}) {
  const response = await fetch(`${baseUrl}/api/dte/factura`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': clave, ...extra }),
    body: JSON.stringify({
      receptor: null,
      items: [{ descripcion: 'Producto simulado', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '05', montoPago: 113, referencia: clave, numPagoElectronico: null },
    }),
  });
  return { response, body: await response.json() };
}

async function anular(codigo, clave, cuerpo, extra = {}, apiKey = API_KEY) {
  const response = await fetch(`${baseUrl}/api/dte/simulacion/${codigo}/anular`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': clave, ...extra }, apiKey),
    body: JSON.stringify(cuerpo),
  });
  return { response, body: await response.json() };
}

function tipo2() {
  return { motivo: { tipoAnulacion: 2, responsable, solicitante } };
}

function fila(tabla, codigo) {
  return db.prepare(`SELECT * FROM ${tabla} WHERE codigo_generacion = ?`).get(codigo);
}

test('el bloqueo de egress está activo y nadie intentó salir al empezar', async () => {
  const health = await (await fetch(`${baseUrl}/api/health`)).json();
  assert.equal(health.dteMode, 'simulated');
  assert.equal(health.simulatedFiscalEventsEnabled, true);
  assert.equal(health.egressGuard, 'active');
  assert.equal(health.blockedExternalCalls, 0);
});

test('invalida tipo 2 una Factura simulada con marcador propio, sin sello ni respuesta de Hacienda', async () => {
  const { body: dte } = await emitirFactura('sim-inv-fe-001');
  assert.equal(dte.estado, 'SIMULADO');

  const preview = await fetch(`${baseUrl}/api/dte/simulacion/${dte.codigoGeneracion}/invalidacion`, { headers: headers() });
  const previa = await preview.json();
  assert.equal(preview.status, 200, JSON.stringify(previa));
  assert.equal(previa.issuanceMode, 'SIMULATED');
  assert.deepEqual(previa.reemplazoRequeridoEnTipos, [1, 3]);
  assert.equal(previa.plazo.vencido, false);

  const primero = await anular(dte.codigoGeneracion, 'sim-inv-evt-001', tipo2());
  assert.equal(primero.response.status, 200, JSON.stringify(primero.body));
  assert.equal(primero.body.estado, 'SIMULADO_INVALIDADO');
  assert.equal(primero.body.estadoEvento, 'SIMULADO');
  assert.equal(primero.body.issuanceMode, 'SIMULATED');
  assert.equal(primero.body.codigoGeneracionDte, dte.codigoGeneracion);
  assert.match(primero.body.simulationMarkerEvento, /^SIMULATED-EVT-[0-9A-F]{32}$/);
  assert.equal(primero.body.selloRecepcionEvento, undefined);
  assert.equal(primero.body.respuestaHacienda, undefined);

  const repetido = await anular(dte.codigoGeneracion, 'sim-inv-evt-001', tipo2());
  assert.equal(repetido.response.status, 200);
  assert.deepEqual(repetido.body, primero.body);

  assert.equal(fila('dtes', dte.codigoGeneracion).estado, 'SIMULADO_INVALIDADO');
  const evento = fila('eventos', primero.body.codigoGeneracionEvento);
  assert.equal(evento.estado, 'SIMULADO');
  assert.equal(evento.modo_emision, 'SIMULATED');
  assert.equal(evento.sello_recepcion, null);
  assert.equal(evento.simulation_marker, primero.body.simulationMarkerEvento);

  const json = await fetch(`${baseUrl}/api/dte/simulacion/eventos/${primero.body.codigoGeneracionEvento}/json`, { headers: headers() });
  assert.equal(json.status, 200);
  assert.equal(json.headers.get('x-dte-issuance-mode'), 'simulated');
  const archivo = await json.json();
  assert.equal(archivo.selloRecibido, primero.body.simulationMarkerEvento);
  assert.equal(archivo.documento.codigoGeneracion, dte.codigoGeneracion);
  assert.equal(archivo.documento.codigoGeneracionR, null);
  assert.equal(archivo.documento.selloRecibido.length, 40);
  assert.ok(archivo.documento.selloRecibido.startsWith('SIMULATED-'));
  assert.equal(archivo.motivo.tipoAnulacion, 2);
  const [cabecera] = archivo.firmaElectronica.split('.');
  assert.equal(JSON.parse(Buffer.from(cabecera, 'base64url').toString()).alg, 'SIM');

  // PDF del evento simulado: con la marca de simulación y sin tocar el evento.
  const pdf = await fetch(`${baseUrl}/api/dte/simulacion/eventos/${primero.body.codigoGeneracionEvento}/pdf/render`, {
    method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' }, body: '{}',
  });
  assert.equal(pdf.status, 200);
  assert.equal(pdf.headers.get('content-type'), 'application/pdf');
  assert.equal(pdf.headers.get('x-dte-issuance-mode'), 'simulated');
  const bytesPdf = Buffer.from(await pdf.arrayBuffer());
  assert.equal(bytesPdf.subarray(0, 4).toString('ascii'), '%PDF');
  assert.match(textoCompleto(bytesPdf), /SIN VALIDEZ FISCAL/);
  assert.equal(fila('eventos', primero.body.codigoGeneracionEvento).payload_json, evento.payload_json);
  const ajeno = await fetch(`${baseUrl}/api/dte/simulacion/eventos/${dte.codigoGeneracion}/pdf/render`, {
    method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' }, body: '{}',
  });
  assert.equal(ajeno.status, 404);

  const otra = await anular(dte.codigoGeneracion, 'sim-inv-evt-002', tipo2());
  assert.equal(otra.response.status, 409);
  assert.equal(otra.body.code, 'DTE_ALREADY_INVALIDATED');
  assert.equal(otra.body.codigoGeneracionEvento, primero.body.codigoGeneracionEvento);

  const previewTardia = await fetch(`${baseUrl}/api/dte/simulacion/${dte.codigoGeneracion}/invalidacion`, { headers: headers() });
  assert.equal(previewTardia.status, 409);
});

test('tipo 1 exige un reemplazo SIMULADO de la misma base y lo enlaza en el evento', async () => {
  const { body: original } = await emitirFactura('sim-inv-original-001');
  const { body: reemplazo } = await emitirFactura('sim-inv-reemplazo-001');
  const motivo = { tipoAnulacion: 1, motivoAnulacion: 'Error en el receptor', responsable, solicitante };

  const sinReemplazo = await anular(original.codigoGeneracion, 'sim-inv-t1-a', { motivo });
  assert.equal(sinReemplazo.response.status, 400);
  assert.equal(sinReemplazo.body.code, 'INVALID_INVALIDATION_REQUEST');

  const inexistente = await anular(original.codigoGeneracion, 'sim-inv-t1-b', { motivo, codigoGeneracionReemplazo: crypto.randomUUID().toUpperCase() });
  assert.equal(inexistente.response.status, 409);
  assert.equal(inexistente.body.code, 'INVALIDATION_REPLACEMENT_NOT_READY');

  // Un documento real nunca sirve de reemplazo de uno simulado, aunque esté en la misma base.
  const real = crypto.randomUUID().toUpperCase();
  db.prepare(
    `INSERT INTO dtes (codigo_generacion, numero_control, tipo_dte, estado, payload_json, sello_recepcion, modo_emision)
     VALUES (?, 'DTE-01-M001P001-000000000099999', '01', 'TRANSMITIDO', '{}', ?, 'HACIENDA_TEST')`
  ).run(real, 'R'.repeat(40));
  const mezclado = await anular(original.codigoGeneracion, 'sim-inv-t1-c', { motivo, codigoGeneracionReemplazo: real });
  assert.equal(mezclado.response.status, 409);
  assert.equal(mezclado.body.code, 'INVALIDATION_REPLACEMENT_NOT_READY');

  const correcto = await anular(original.codigoGeneracion, 'sim-inv-t1-d', { motivo, codigoGeneracionReemplazo: reemplazo.codigoGeneracion });
  assert.equal(correcto.response.status, 200, JSON.stringify(correcto.body));
  const archivo = await (await fetch(`${baseUrl}/api/dte/simulacion/eventos/${correcto.body.codigoGeneracionEvento}/json`, { headers: headers() })).json();
  assert.equal(archivo.documento.codigoGeneracionR, reemplazo.codigoGeneracion);
  assert.equal(fila('dtes', reemplazo.codigoGeneracion).estado, 'SIMULADO');
});

test('el escenario invalidation-rejected rechaza el evento y deja el documento vigente', async () => {
  const { body: dte } = await emitirFactura('sim-inv-rechazo-001');
  const rechazo = await anular(dte.codigoGeneracion, 'sim-inv-rechazo-evt-001', tipo2(), { 'X-DTE-Simulation-Scenario': 'invalidation-rejected' });
  assert.equal(rechazo.response.status, 422, JSON.stringify(rechazo.body));
  assert.equal(rechazo.body.code, 'INVALIDATION_REJECTED');
  assert.equal(rechazo.body.simulacion.codigoMsg, 'SIM-RECHAZO-INVALIDACION');
  assert.equal(rechazo.body.respuestaHacienda, undefined);
  assert.equal(fila('dtes', dte.codigoGeneracion).estado, 'SIMULADO');
  assert.equal(fila('eventos', rechazo.body.codigoGeneracionEvento).estado, 'RECHAZADO');

  const nuevo = await anular(dte.codigoGeneracion, 'sim-inv-rechazo-evt-002', tipo2());
  assert.equal(nuevo.response.status, 200, JSON.stringify(nuevo.body));
  assert.notEqual(nuevo.body.codigoGeneracionEvento, rechazo.body.codigoGeneracionEvento);
});

test('el escenario rejected deja la Factura RECHAZADA con identidad simulada y sin respuesta de Hacienda', async () => {
  const clave = 'sim-emision-rechazo-001';
  const { response, body } = await emitirFactura(clave, { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.equal(response.status, 200, JSON.stringify(body));
  assert.equal(body.estado, 'RECHAZADO');
  assert.equal(body.issuanceMode, 'SIMULATED');
  assert.equal(body.selloRecepcion, null);
  assert.equal(body.respuestaHacienda, undefined);
  assert.equal(body.simulacion.escenario, 'rejected');
  assert.match(body.codigoGeneracion, /^[0-9A-F-]{36}$/);

  const persistida = fila('dtes', body.codigoGeneracion);
  assert.deepEqual({ estado: persistida.estado, modo: persistida.modo_emision, firma: persistida.documento_firmado, marcador: persistida.simulation_marker },
    { estado: 'RECHAZADO', modo: 'SIMULATED', firma: null, marcador: null });

  const repetida = await emitirFactura(clave, { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.deepEqual(repetida.body, body);

  // Recuperación tras caída: la respuesta se reconstruye desde SQLite, también sin respuestaHacienda.
  db.prepare(
    `UPDATE idempotency_keys SET estado = 'PROCESANDO', status_code = NULL, respuesta_json = NULL,
     actualizado_en = datetime('now', '-1 hour') WHERE clave = ?`
  ).run(clave);
  const recuperada = await emitirFactura(clave, { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.equal(recuperada.response.status, 200);
  assert.equal(recuperada.body.codigoGeneracion, body.codigoGeneracion);
  assert.equal(recuperada.body.issuanceMode, 'SIMULATED');
  assert.equal(recuperada.body.respuestaHacienda, undefined);
  assert.equal(recuperada.body.simulacion.codigoMsg, 'SIM-RECHAZO');

  const estado = await (await fetch(`${baseUrl}/api/dte/${body.codigoGeneracion}`, { headers: headers() })).json();
  assert.equal(estado.estado, 'RECHAZADO');
  assert.equal(estado.modo_emision, 'SIMULATED');

  const invalidar = await anular(body.codigoGeneracion, 'sim-emision-rechazo-evt', tipo2());
  assert.equal(invalidar.response.status, 409);
  assert.equal(invalidar.body.code, 'DTE_NOT_INVALIDATABLE');
});

test('el escenario validation-failed responde 400 sin reservar identidad ni correlativo', async () => {
  const contar = () => ({
    dtes: db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n,
    correlativo: db.prepare('SELECT COALESCE(SUM(ultimo), 0) AS n FROM correlativos').get().n,
  });
  const antes = contar();
  const { response, body } = await emitirFactura('sim-emision-validacion-001', { 'X-DTE-Simulation-Scenario': 'validation-failed' });
  assert.equal(response.status, 400);
  assert.equal(body.code, 'INVALID_DTE_REQUEST');
  assert.equal(body.simulacion.escenario, 'validation-failed');
  assert.deepEqual(contar(), antes);
});

test('rechaza escenarios desconocidos y el header en rutas que no lo usan', async () => {
  const desconocido = await emitirFactura('sim-escenario-x-001', { 'X-DTE-Simulation-Scenario': 'mh-timeout' });
  assert.equal(desconocido.response.status, 400);
  assert.equal(desconocido.body.code, 'SIMULATION_SCENARIO_INVALID');

  const { body: dte } = await emitirFactura('sim-escenario-x-002');
  const deEmisionEnInvalidacion = await anular(dte.codigoGeneracion, 'sim-escenario-x-evt', tipo2(), { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.equal(deEmisionEnInvalidacion.response.status, 400);
  assert.equal(deEmisionEnInvalidacion.body.code, 'SIMULATION_SCENARIO_INVALID');

  const enConsulta = await fetch(`${baseUrl}/api/dte/${dte.codigoGeneracion}`, { headers: headers({ 'X-DTE-Simulation-Scenario': 'success' }) });
  assert.equal(enConsulta.status, 400);
  assert.equal((await enConsulta.json()).code, 'SIMULATION_SCENARIO_NOT_ALLOWED');
});

test('una key sin scope simulate no puede usar las rutas de simulación', async () => {
  const { body: dte } = await emitirFactura('sim-scope-001');
  const preview = await fetch(`${baseUrl}/api/dte/simulacion/${dte.codigoGeneracion}/invalidacion`, { headers: headers({}, 'clave-sin-scope-simulate') });
  assert.equal(preview.status, 403);
  const intento = await anular(dte.codigoGeneracion, 'sim-scope-evt', tipo2(), {}, 'clave-sin-scope-simulate');
  assert.equal(intento.response.status, 403);
  assert.equal(fila('dtes', dte.codigoGeneracion).estado, 'SIMULADO');
});

test('aplica el mismo plazo que el flujo real', async () => {
  const { body: dte } = await emitirFactura('sim-plazo-001');
  const row = fila('dtes', dte.codigoGeneracion);
  const payload = JSON.parse(row.payload_json);
  payload.identificacion.fecEmi = '2025-01-02';
  db.prepare('UPDATE dtes SET payload_json = ? WHERE codigo_generacion = ?').run(JSON.stringify(payload), dte.codigoGeneracion);
  const vencido = await anular(dte.codigoGeneracion, 'sim-plazo-evt', tipo2());
  assert.equal(vencido.response.status, 422);
  assert.equal(vencido.body.code, 'INVALIDATION_DEADLINE_EXCEEDED');
});

// El 409 de /:codigo/anular con scope invalidate lo cubre simulatedEmission.test.js; aquí la
// key del perfil simulado ni siquiera tiene ese scope.
test('la key simulada no alcanza la invalidación ante Hacienda', async () => {
  const { body: dte } = await emitirFactura('sim-anular-real-001');
  const response = await fetch(`${baseUrl}/api/dte/${dte.codigoGeneracion}/anular`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'sim-anular-real-evt' }),
    body: JSON.stringify(tipo2()),
  });
  assert.equal(response.status, 403);
  assert.equal(fila('dtes', dte.codigoGeneracion).estado, 'SIMULADO');
});

test('ninguna prueba anterior intentó salir de la máquina y la salida a Hacienda queda bloqueada', async () => {
  const antes = await (await fetch(`${baseUrl}/api/health`)).json();
  assert.equal(antes.blockedExternalCalls, 0);

  await assert.rejects(fetch('https://apitest.dtes.mh.gob.sv/fesv/anulardte'), (error) => error.cause?.code === 'SIMULATION_EGRESS_BLOCKED');
  await assert.rejects(require('axios').get('https://api.dtes.mh.gob.sv/fesv/recepciondte'), (error) => error.code === 'SIMULATION_EGRESS_BLOCKED');
  await assert.rejects(require('node:dns').promises.lookup('apitest.dtes.mh.gob.sv'), (error) => error.code === 'SIMULATION_EGRESS_BLOCKED');

  const despues = await (await fetch(`${baseUrl}/api/health`)).json();
  assert.equal(despues.blockedExternalCalls, 3);
});

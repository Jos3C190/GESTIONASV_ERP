const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.DTE_SIMULATION_RUN_ID = 'local-integration-run';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '06141804941035';
process.env.MS_AUTH_DESHABILITADA = 'false';
require('../_setup');
const { db } = require('../../src/db');

const API_KEY = 'clave-de-prueba-para-tests';
let server;
let baseUrl;

before(async () => {
  const firmadorClient = require('../../src/services/firmadorClient');
  const haciendaClient = require('../../src/services/haciendaClient');
  firmadorClient.firmarDocumento = async () => { throw new Error('El modo simulado intentó usar el firmador'); };
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

function headers(extra = {}) {
  return { Authorization: `Bearer ${API_KEY}`, ...extra };
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  return value;
}

function issuerV2() {
  const canonical = { legalName: 'Emisor V2 de Integración S.A. de C.V.', tradeName: 'Emisor V2', nit: '06141804941035', nrc: '1234567', economicActivityCode: '62010', economicActivityDescription: 'Programación informática', activityCatalogVersion: 'CAT-019', address: { departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro', districtCode: '14', districtName: 'San Salvador', complement: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-TEST-1' }, phone: '22221111', email: 'fiscal-v2@example.test', establishmentType: '02', mhEstablishmentCode: '001', mhPointOfSaleCode: '001', internalEstablishmentCode: 'CASA', internalPointOfSaleCode: null };
  return { revisionId: 'revision-v2-integration', snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'), nit: canonical.nit, nrc: canonical.nrc, nombre: canonical.legalName, nombreComercial: canonical.tradeName, codActividad: canonical.economicActivityCode, descActividad: canonical.economicActivityDescription, activityCatalogVersion: canonical.activityCatalogVersion, direccion: { departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro', distrito: '14', districtName: 'San Salvador', complemento: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-TEST-1' }, telefono: canonical.phone, correo: canonical.email, tipoEstablecimiento: '02', codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: 'CASA', codPuntoVenta: null };
}

async function issueV2(path, key, receptor) {
  return fetch(`${baseUrl}/api/dte/v2/${path}`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': key }), body: JSON.stringify({ emisor: issuerV2(), receptor, items: [path === 'factura' ? { descripcion: 'Producto v2', cantidad: 1, precioUni: 113, ventaGravada: 113 } : { descripcion: 'Producto v2', cantidad: 1, precioUni: 100, ventaGravada: 100 }], pago: { codigo: '05', montoPago: 113, referencia: key, numPagoElectronico: null } }) });
}

test('v2 emite Factura 01 y conserva el snapshot del emisor en JSON/PDF', async () => {
  const response = await issueV2('factura', 'simulation-v2-fe-001', null);
  const issued = await response.json();
  assert.equal(response.status, 201, JSON.stringify(issued));
  const jsonResponse = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/json`, { headers: headers() });
  const artifact = await jsonResponse.json();
  assert.equal(artifact.identificacion.tipoDte, '01');
  assert.equal(artifact.emisor.nombre, issuerV2().nombre);
  assert.equal(artifact.emisor.nit, issuerV2().nit);
  const pdf = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/pdf`, { headers: headers() });
  assert.equal(pdf.status, 200);
  assert.equal(Buffer.from(await pdf.arrayBuffer()).subarray(0, 4).toString('ascii'), '%PDF');
});

test('v2 emite CCF 03 y rechaza un snapshot alterado antes de persistir', async () => {
  const receptor = { nit: '06141804941099', nrc: '7654321', nombre: 'Cliente Empresa S.A.', codActividad: '62010', descActividad: 'Programación informática', nombreComercial: null, direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra dirección' }, telefono: '22223333', correo: 'qa-fiscal@example.test' };
  const response = await issueV2('ccf', 'simulation-v2-ccf-001', receptor);
  const issued = await response.json();
  assert.equal(response.status, 201, JSON.stringify(issued));
  const artifact = await (await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/json`, { headers: headers() })).json();
  assert.equal(artifact.identificacion.tipoDte, '03');
  assert.equal(artifact.emisor.correo, issuerV2().correo);

  const altered = issuerV2(); altered.nombre = 'Emisor alterado';
  const rejected = await fetch(`${baseUrl}/api/dte/v2/factura`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'simulation-v2-invalid-001' }), body: JSON.stringify({ emisor: altered, receptor: null, items: [{ descripcion: 'X', cantidad: 1, precioUni: 10, ventaGravada: 10 }] }) });
  assert.equal(rejected.status, 400);
  assert.equal((await rejected.json()).code, 'ISSUER_HASH_MISMATCH');
});

test('v2 emite CCF simulado con IVA incluido de 24.99, envio 4.50 y pago de 29.49', async () => {
  const receptor = { nit: '06141804941099', nrc: '7654321', nombre: 'Cliente Empresa S.A.', codActividad: '62010', descActividad: 'Programacion informatica', nombreComercial: null, direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra direccion' }, telefono: '22223333', correo: 'qa-fiscal@example.test' };
  const response = await fetch(`${baseUrl}/api/dte/v2/ccf`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'simulation-v2-ccf-2949' }),
    body: JSON.stringify({
      emisor: issuerV2(), receptor,
      items: [
        { descripcion: 'Producto', cantidad: 1, precioUni: 22.12, ventaGravada: 22.12, ivaItem: 2.87 },
        { descripcion: 'Servicio de entrega', cantidad: 1, precioUni: 4.5, ventaGravada: 0, ventaNoSuj: 4.5, ivaItem: 0 },
      ],
      pago: { codigo: null, montoPago: 29.49, referencia: 'SIMULATED-WOMPI-2949' },
    }),
  });
  const issued = await response.json();
  assert.equal(response.status, 201, JSON.stringify(issued));
  assert.equal(issued.estado, 'SIMULADO');
  const artifact = await (await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/json`, { headers: headers() })).json();
  assert.equal(artifact.resumen.tributos[0].valor, 2.87);
  assert.equal(artifact.resumen.totalPagar, 29.49);
  assert.equal(artifact.resumen.pagos[0].montoPago, 29.49);
  const pdf = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/pdf`, { headers: headers() });
  assert.equal(pdf.status, 200);
  assert.equal(Buffer.from(await pdf.arrayBuffer()).subarray(0, 4).toString('ascii'), '%PDF');
});

test('emite Factura simulada, conserva idempotencia y entrega JSON/PDF marcados sin red fiscal', async () => {
  const request = {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'simulation-order-001' }),
    body: JSON.stringify({
      receptor: null,
      items: [{ descripcion: 'Producto de prueba', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '05', montoPago: 113, referencia: 'QA-TRANSFER', numPagoElectronico: null },
    }),
  };
  const first = await fetch(`${baseUrl}/api/dte/factura`, request);
  assert.equal(first.status, 201);
  const issued = await first.json();
  assert.equal(issued.estado, 'SIMULADO');
  assert.equal(issued.issuanceMode, 'SIMULATED');
  assert.match(issued.simulationMarker, /^SIMULATED-/);
  assert.equal(
    db.prepare('SELECT simulation_run_id FROM dtes WHERE codigo_generacion = ?').get(issued.codigoGeneracion).simulation_run_id,
    'local-integration-run',
  );

  const duplicate = await fetch(`${baseUrl}/api/dte/factura`, request);
  assert.equal(duplicate.status, 201);
  assert.deepEqual(await duplicate.json(), issued);

  const status = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}`, { headers: headers() });
  const statusBody = await status.json();
  assert.equal(statusBody.estado, 'SIMULADO');
  assert.equal(statusBody.modo_emision, 'SIMULATED');

  const json = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/json`, { headers: headers() });
  assert.equal(json.status, 200);
  assert.equal(json.headers.get('x-dte-issuance-mode'), 'simulated');
  const artifact = await json.json();
  assert.equal(artifact.selloRecibido, issued.simulationMarker);
  assert.match(artifact.firmaElectronica, /^[^.]+\.[^.]+\.[^.]+$/);

  const pdf = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/pdf`, { headers: headers() });
  assert.equal(pdf.status, 200);
  assert.equal(pdf.headers.get('x-dte-issuance-mode'), 'simulated');
  assert.match(pdf.headers.get('content-disposition'), /SIMULADO-/);
  assert.equal(Buffer.from(await pdf.arrayBuffer()).subarray(0, 4).toString('ascii'), '%PDF');

  const health = await fetch(`${baseUrl}/api/health`);
  const healthBody = await health.json();
  assert.equal(healthBody.dteMode, 'simulated');
  assert.equal(healthBody.haciendaCallsEnabled, false);
  assert.equal(healthBody.firmadorEnabled, false);
});

test('recupera una respuesta simulada persistida tras caída sin volver a emitir otro DTE', async () => {
  const key = 'simulation-recovery-after-persist-001'
  const request = {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': key }),
    body: JSON.stringify({
      receptor: null,
      items: [{ descripcion: 'Producto recuperación', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '05', montoPago: 113, referencia: 'QA-RECOVERY', numPagoElectronico: null },
    }),
  }
  const first = await fetch(`${baseUrl}/api/dte/factura`, request)
  assert.equal(first.status, 201)
  const issued = await first.json()

  db.prepare(
    `UPDATE idempotency_keys SET estado = 'PROCESANDO', status_code = NULL, respuesta_json = NULL,
     actualizado_en = datetime('now', '-1 hour') WHERE clave = ?`
  ).run(key)

  const recovered = await fetch(`${baseUrl}/api/dte/factura`, request)
  const recoveredBody = await recovered.json()
  assert.equal(recovered.status, 201)
  assert.equal(recoveredBody.codigoGeneracion, issued.codigoGeneracion)
  assert.equal(recoveredBody.numeroControl, issued.numeroControl)
  assert.equal(recoveredBody.simulationMarker, issued.simulationMarker)
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM dtes WHERE codigo_generacion = ?').get(issued.codigoGeneracion).n, 1)
  const stored = db.prepare('SELECT estado, status_code FROM idempotency_keys WHERE clave = ?').get(key)
  assert.deepEqual(stored, { estado: 'COMPLETADO', status_code: 201 })
})

test('emite CCF simulado con receptor fiscal y mantiene los artefactos fuera de Hacienda', async () => {
  const response = await fetch(`${baseUrl}/api/dte/ccf`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'simulation-ccf-001' }),
    body: JSON.stringify({
      receptor: {
        nit: '06141804941099',
        nrc: '7654321',
        nombre: 'Cliente Empresa S.A.',
        codActividad: '62010',
        descActividad: 'Programación informática',
        nombreComercial: null,
        direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra dirección' },
        telefono: '22223333',
        correo: 'qa-fiscal@example.test',
      },
      items: [{ descripcion: 'Producto gravado de prueba', cantidad: 1, precioUni: 100, ventaGravada: 100 }],
      pago: { codigo: '05', montoPago: 113, referencia: 'QA-CCF', numPagoElectronico: null },
    }),
  });

  assert.equal(response.status, 201);
  const issued = await response.json();
  assert.equal(issued.estado, 'SIMULADO');
  assert.match(issued.simulationMarker, /^SIMULATED-/);

  const json = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/json`, { headers: headers() });
  const artifact = await json.json();
  assert.equal(artifact.identificacion.tipoDte, '03');
  assert.equal(artifact.selloRecibido, issued.simulationMarker);

  const pdf = await fetch(`${baseUrl}/api/dte/${issued.codigoGeneracion}/pdf`, { headers: headers() });
  assert.equal(pdf.status, 200);
  assert.match(pdf.headers.get('content-disposition'), /SIMULADO-/);
});

test('no consulta a Hacienda el estado de un DTE ni de un lote en modo simulado', async () => {
  const haciendaClient = require('../../src/services/haciendaClient');
  haciendaClient.consultarDte = async () => { throw new Error('El modo simulado intentó consultar un DTE en Hacienda'); };
  haciendaClient.consultarLoteDte = async () => { throw new Error('El modo simulado intentó consultar un lote en Hacienda'); };
  const issued = await (await fetch(`${baseUrl}/api/dte/factura`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'simulation-hacienda-query-001' }),
    body: JSON.stringify({
      receptor: null,
      items: [{ descripcion: 'Producto consulta', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '05', montoPago: 113, referencia: 'QA-QUERY', numPagoElectronico: null },
    }),
  })).json();
  assert.equal(issued.estado, 'SIMULADO');

  for (const path of [`/api/dte/${issued.codigoGeneracion}/hacienda`, '/api/dte/lote/LOTE-SIMULADO-001']) {
    const response = await fetch(`${baseUrl}${path}`, { headers: headers() });
    assert.equal(response.status, 409, path);
    const body = await response.json();
    assert.equal(body.code, 'HACIENDA_QUERY_SIMULATED');
    assert.match(body.error, /simulad/i);
  }
});

test('bloquea la contingencia global mientras el modo es simulado', async () => {
  // La invalidación de un emisor simulado ya no se bloquea: usa el proveedor simulado (V4b del ERP).
  const anular = await fetch(`${baseUrl}/api/dte/00000000-0000-4000-8000-000000000000/anular`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': 'simulation-event-anular' }),
    body: JSON.stringify({}),
  });
  assert.equal(anular.status, 404);
  const paths = [
    '/api/dte/contingencia/forzar',
    '/api/dte/contingencia/1/cerrar',
  ];
  for (const [index, path] of paths.entries()) {
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': `simulation-event-${index}` }),
      body: JSON.stringify({}),
    });
    assert.equal(response.status, 409);
    assert.match((await response.json()).error, /simulad/i);
  }
});

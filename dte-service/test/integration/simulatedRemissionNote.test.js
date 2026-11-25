const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

// Nota de Remisión (04) habilitada solo en este proceso: la allowlist por
// defecto (01,03) sigue respondiendo 403 (ver app.test.js).
process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.DTE_SIMULATION_RUN_ID = 'remission-note-run';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '06141804941035';
process.env.DTE_ALLOWED_DOCUMENT_TYPES = '01,03,04';
process.env.MS_AUTH_DESHABILITADA = 'false';
process.env.MS_API_KEY_SCOPES = 'issue,read,simulate';
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

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  return value;
}

/** Emisor v2: establecimiento de la bodega de origen, con su punto de venta. */
function issuerV2() {
  const canonical = { legalName: 'Emisor V2 de Integración S.A. de C.V.', tradeName: 'Emisor V2', nit: '06141804941035', nrc: '1234567', economicActivityCode: '62010', economicActivityDescription: 'Programación informática', activityCatalogVersion: 'CAT-019', address: { departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro', districtCode: '14', districtName: 'San Salvador', complement: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-TEST-1' }, phone: '22221111', email: 'fiscal-v2@example.test', establishmentType: '02', mhEstablishmentCode: '001', mhPointOfSaleCode: '001', internalEstablishmentCode: 'M001', internalPointOfSaleCode: 'P001' };
  return { revisionId: 'revision-v2-remision', snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'), nit: canonical.nit, nrc: canonical.nrc, nombre: canonical.legalName, nombreComercial: canonical.tradeName, codActividad: canonical.economicActivityCode, descActividad: canonical.economicActivityDescription, activityCatalogVersion: canonical.activityCatalogVersion, direccion: { departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro', distrito: '14', districtName: 'San Salvador', complemento: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-TEST-1' }, telefono: canonical.phone, correo: canonical.email, tipoEstablecimiento: '02', codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: 'M001', codPuntoVenta: 'P001' };
}

// Traslado: el receptor es la misma empresa, con la dirección del establecimiento destino.
const RECEPTOR = {
  tipoDocumento: '36',
  numDocumento: '06141804941035',
  nrc: '1234567',
  nombre: 'Emisor V2 de Integración S.A. de C.V.',
  codActividad: '62010',
  descActividad: 'Programación informática',
  direccion: { departamento: '11', municipio: '24', distrito: '01', complemento: 'Sucursal Usulután' },
  telefono: '22221111',
  correo: 'fiscal-v2@example.test',
};

function cuerpo(cambios = {}) {
  return {
    emisor: issuerV2(),
    receptor: RECEPTOR,
    bienTitulo: '04',
    items: [
      { descripcion: 'Harina 50 lb', codigo: 'PRD-HAR-001', cantidad: 10, uniMedida: 59, precioUni: 18.5, ventaGravada: 185 },
    ],
    observaciones: 'Traslado TR-0001. Vehículo P123-456, conductor Ana Pérez.',
    ...cambios,
  };
}

async function post(path, clave, body, extra = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${API_KEY}`, 'Content-Type': 'application/json', 'Idempotency-Key': clave, ...extra },
    body: JSON.stringify(body),
  });
  return { response, body: await response.json() };
}

test('v2 emite una Nota de Remisión simulada con el emisor de la solicitud', async () => {
  const { response, body } = await post('/api/dte/v2/nota-remision', 'nr-emision-001', cuerpo(), { 'X-DTE-Simulation-Scenario': 'success' });
  assert.equal(response.status, 201, JSON.stringify(body));
  assert.equal(body.estado, 'SIMULADO');
  assert.match(body.numeroControl, /^DTE-04-M001P001-\d{15}$/);
  const fila = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(body.codigoGeneracion);
  assert.equal(fila.tipo_dte, '04');
  const dte = await (await fetch(`${baseUrl}/api/dte/${body.codigoGeneracion}/json`, { headers: { Authorization: `Bearer ${API_KEY}` } })).json();
  assert.equal(dte.receptor.bienTitulo, '04');
  assert.equal(dte.emisor.codEstable, 'M001');
  assert.equal(dte.resumen.montoTotalOperacion, 209.05);
  assert.match(dte.resumen.observaciones, /P123-456/);
});

test('el escenario rejected deja la Nota de Remisión RECHAZADA sin respuesta de Hacienda', async () => {
  const { response, body } = await post('/api/dte/v2/nota-remision', 'nr-emision-002', cuerpo(), { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.equal(response.status, 200, JSON.stringify(body));
  assert.equal(body.estado, 'RECHAZADO');
  assert.equal(body.selloRecepcion, null);
});

test('una solicitud sin bienTitulo es un error de solicitud', async () => {
  const { response, body } = await post('/api/dte/v2/nota-remision', 'nr-emision-003', cuerpo({ bienTitulo: null }));
  assert.equal(response.status, 400, JSON.stringify(body));
  assert.match(JSON.stringify(body), /bienTitulo/);
});

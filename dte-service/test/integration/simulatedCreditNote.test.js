const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

// Nota de Crédito (05) habilitada solo en este proceso: la allowlist por
// defecto (01,03) sigue respondiendo 403 (ver app.test.js).
process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.DTE_SIMULATION_RUN_ID = 'credit-note-run';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '06141804941035';
process.env.DTE_ALLOWED_DOCUMENT_TYPES = '01,03,05';
process.env.MS_AUTH_DESHABILITADA = 'false';
process.env.MS_API_KEY_SCOPES = 'issue,read,simulate';
require('../_setup');
const { db } = require('../../src/db');

const API_KEY = 'clave-de-prueba-para-tests';
const responsable = { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' };
const solicitante = { nombre: 'Ana López', tipoDocumento: '36', numeroDocumento: '06141804941035' };
const RECEPTOR_CCF = { nit: '06141804941099', nrc: '7654321', nombre: 'Cliente Empresa S.A.', codActividad: '62010', descActividad: 'Programación informática', nombreComercial: null, direccion: { departamento: '06', municipio: '20', distrito: '01', complemento: 'Otra dirección' }, telefono: '22223333', correo: 'qa-fiscal@example.test' };
// El receptor de la nota es el del CCF, identificado con NIT (tipo 36).
const { nit, ...restoReceptor } = RECEPTOR_CCF;
const RECEPTOR_NC = { tipoDocumento: '36', numDocumento: nit, ...restoReceptor };
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

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  return value;
}

function issuerV2() {
  const canonical = { legalName: 'Emisor V2 de Integración S.A. de C.V.', tradeName: 'Emisor V2', nit: '06141804941035', nrc: '1234567', economicActivityCode: '62010', economicActivityDescription: 'Programación informática', activityCatalogVersion: 'CAT-019', address: { departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro', districtCode: '14', districtName: 'San Salvador', complement: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-TEST-1' }, phone: '22221111', email: 'fiscal-v2@example.test', establishmentType: '02', mhEstablishmentCode: '001', mhPointOfSaleCode: '001', internalEstablishmentCode: 'CASA', internalPointOfSaleCode: null };
  return { revisionId: 'revision-v2-integration', snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'), nit: canonical.nit, nrc: canonical.nrc, nombre: canonical.legalName, nombreComercial: canonical.tradeName, codActividad: canonical.economicActivityCode, descActividad: canonical.economicActivityDescription, activityCatalogVersion: canonical.activityCatalogVersion, direccion: { departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro', distrito: '14', districtName: 'San Salvador', complemento: 'Dirección fiscal v2', geoCatalogVersion: 'GEO-TEST-1' }, telefono: canonical.phone, correo: canonical.email, tipoEstablecimiento: '02', codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: 'CASA', codPuntoVenta: null };
}

async function post(path, clave, cuerpo, extra = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json', 'Idempotency-Key': clave, ...extra }),
    body: JSON.stringify(cuerpo),
  });
  return { response, body: await response.json() };
}

async function artefacto(codigo) {
  return (await fetch(`${baseUrl}/api/dte/${codigo}/json`, { headers: headers() })).json();
}

/** CCF v2 simulado de $100 + IVA, el documento que las notas ajustan. */
async function emitirCCF(clave) {
  const { response, body } = await post('/api/dte/v2/ccf', clave, {
    emisor: issuerV2(),
    receptor: RECEPTOR_CCF,
    items: [
      { descripcion: 'Camiseta', cantidad: 2, precioUni: 40, ventaGravada: 80, ivaItem: 10.4 },
      { descripcion: 'Taza', cantidad: 1, precioUni: 20, ventaGravada: 20, ivaItem: 2.6 },
    ],
    pago: { codigo: '05', montoPago: 113, referencia: clave, numPagoElectronico: null },
  });
  assert.equal(response.status, 201, JSON.stringify(body));
  const ccf = await artefacto(body.codigoGeneracion);
  return { codigoGeneracion: body.codigoGeneracion, fecEmi: ccf.identificacion.fecEmi };
}

function cuerpoNota(ccf, cambios = {}) {
  return {
    emisor: issuerV2(),
    receptor: RECEPTOR_NC,
    documentosRelacionados: [{ tipoDocumento: '03', tipoGeneracion: 2, numeroDocumento: ccf.codigoGeneracion, fechaEmision: ccf.fecEmi }],
    // Devolución de una camiseta: el IVA acreditado es el que cobró el CCF.
    items: [{ descripcion: 'Camiseta devuelta', cantidad: 1, precioUni: 40, ventaGravada: 40, ivaItem: 5.2, numeroDocumento: ccf.codigoGeneracion }],
    observaciones: 'Devolución de una camiseta',
    ...cambios,
  };
}

function contar() {
  return {
    dtes: db.prepare('SELECT COUNT(*) AS n FROM dtes').get().n,
    correlativo: db.prepare('SELECT COALESCE(SUM(ultimo), 0) AS n FROM correlativos').get().n,
  };
}

function fila(codigo) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigo);
}

test('v2 emite una Nota de Crédito simulada que relaciona el CCF y conserva el emisor del snapshot', async () => {
  const ccf = await emitirCCF('nc-ccf-001');
  const peticion = cuerpoNota(ccf);
  const { response, body } = await post('/api/dte/v2/nota-credito', 'nc-emision-001', peticion, { 'X-DTE-Simulation-Scenario': 'success' });
  assert.equal(response.status, 201, JSON.stringify(body));
  assert.equal(body.estado, 'SIMULADO');
  assert.equal(body.issuanceMode, 'SIMULATED');
  assert.match(body.numeroControl, /^DTE-05-M001P001-\d{15}$/);
  assert.equal(fila(body.codigoGeneracion).tipo_dte, '05');

  const nota = await artefacto(body.codigoGeneracion);
  assert.equal(nota.identificacion.tipoDte, '05');
  assert.equal(nota.identificacion.fusion, null);
  assert.deepEqual(nota.documentoRelacionado, [{ tipoDocumento: '03', tipoGeneracion: 2, numeroDocumento: ccf.codigoGeneracion, fechaEmision: ccf.fecEmi }]);
  assert.equal(nota.cuerpoDocumento[0].numeroDocumento, ccf.codigoGeneracion);
  assert.equal(nota.cuerpoDocumento[0].totalIva, 5.2);
  assert.equal(nota.resumen.totalPagar, 45.2);
  assert.equal(nota.resumen.observaciones, 'Devolución de una camiseta');
  assert.equal(nota.emisor.nombre, issuerV2().nombre);
  assert.equal('codEstable' in nota.emisor, false);
  assert.equal(nota.receptor.numDocumento, RECEPTOR_CCF.nit);
  assert.equal(nota.selloRecibido, body.simulationMarker);

  const repetida = await post('/api/dte/v2/nota-credito', 'nc-emision-001', peticion, { 'X-DTE-Simulation-Scenario': 'success' });
  assert.equal(repetida.response.status, 201);
  assert.deepEqual(repetida.body, body);

  const pdf = await fetch(`${baseUrl}/api/dte/${body.codigoGeneracion}/pdf`, { headers: headers() });
  assert.equal(pdf.status, 200);
  assert.match(pdf.headers.get('content-disposition'), /SIMULADO-/);
  assert.equal(Buffer.from(await pdf.arrayBuffer()).subarray(0, 4).toString('ascii'), '%PDF');
});

test('la ruta sin contrato v2 emite con el emisor del .env y acepta el escenario', async () => {
  const ccf = await emitirCCF('nc-ccf-legacy');
  const { emisor, ...sinEmisor } = cuerpoNota(ccf);
  // Aunque llegue un emisor, la ruta vieja lo ignora (como /ccf).
  const { response, body } = await post('/api/dte/nota-credito', 'nc-legacy-001', { ...sinEmisor, emisor }, { 'X-DTE-Simulation-Scenario': 'success' });
  assert.equal(response.status, 201, JSON.stringify(body));
  const nota = await artefacto(body.codigoGeneracion);
  assert.equal(nota.emisor.nombre, 'Mi Empresa de Pruebas S.A. de C.V.');
});

test('emite la nota de un CCF cuyo receptor no tiene teléfono', async () => {
  const ccf = await emitirCCF('nc-ccf-sin-telefono');
  const { response, body } = await post('/api/dte/v2/nota-credito', 'nc-sin-telefono-001', cuerpoNota(ccf, { receptor: { ...RECEPTOR_NC, telefono: null } }));
  assert.equal(response.status, 201, JSON.stringify(body));
  const nota = await artefacto(body.codigoGeneracion);
  assert.equal(nota.receptor.telefono, null);
  assert.equal(nota.receptor.correo, RECEPTOR_NC.correo);
});

test('el escenario rejected deja la Nota de Crédito RECHAZADA sin respuesta de Hacienda', async () => {
  const ccf = await emitirCCF('nc-ccf-rechazo');
  const { response, body } = await post('/api/dte/v2/nota-credito', 'nc-rechazo-001', cuerpoNota(ccf), { 'X-DTE-Simulation-Scenario': 'rejected' });
  assert.equal(response.status, 200, JSON.stringify(body));
  assert.equal(body.estado, 'RECHAZADO');
  assert.equal(body.issuanceMode, 'SIMULATED');
  assert.equal(body.selloRecepcion, null);
  assert.equal(body.respuestaHacienda, undefined);
  assert.equal(body.simulacion.escenario, 'rejected');
  assert.equal(fila(body.codigoGeneracion).estado, 'RECHAZADO');
});

test('validation-failed y una solicitud inválida responden 400 sin reservar identidad ni correlativo', async () => {
  const ccf = await emitirCCF('nc-ccf-validacion');
  const antes = contar();

  const escenario = await post('/api/dte/v2/nota-credito', 'nc-validacion-001', cuerpoNota(ccf), { 'X-DTE-Simulation-Scenario': 'validation-failed' });
  assert.equal(escenario.response.status, 400);
  assert.equal(escenario.body.code, 'INVALID_DTE_REQUEST');
  assert.equal(escenario.body.simulacion.escenario, 'validation-failed');

  const invalida = await post('/api/dte/v2/nota-credito', 'nc-invalida-001', cuerpoNota(ccf, {
    documentosRelacionados: [{ tipoDocumento: '01', tipoGeneracion: 2, numeroDocumento: ccf.codigoGeneracion, fechaEmision: ccf.fecEmi }],
  }));
  assert.equal(invalida.response.status, 400);
  assert.equal(invalida.body.code, 'INVALID_DTE_REQUEST');
  assert.match(invalida.body.error, /Comprobantes de Crédito Fiscal/);

  const sinDocumento = await post('/api/dte/v2/nota-credito', 'nc-invalida-002', cuerpoNota(ccf, {
    items: [{ descripcion: 'Sin documento', cantidad: 1, precioUni: 10, ventaGravada: 10 }],
  }));
  assert.equal(sinDocumento.response.status, 400);
  assert.match(sinDocumento.body.error, /numeroDocumento/);

  assert.deepEqual(contar(), antes);
});

test('invalida una Nota de Crédito simulada sin documento de reemplazo', async () => {
  const ccf = await emitirCCF('nc-ccf-invalidacion');
  const { body: nota } = await post('/api/dte/v2/nota-credito', 'nc-invalidacion-001', cuerpoNota(ccf));
  assert.equal(nota.estado, 'SIMULADO');

  const preview = await fetch(`${baseUrl}/api/dte/simulacion/${nota.codigoGeneracion}/invalidacion`, { headers: headers() });
  const previa = await preview.json();
  assert.equal(preview.status, 200, JSON.stringify(previa));
  assert.equal(previa.tipoDte, '05');
  assert.deepEqual(previa.reemplazoRequeridoEnTipos, []);
  assert.equal(previa.plazo.vencido, false);

  // El manual exime a la NC del reemplazo también en los tipos 1 y 3.
  const motivo = { tipoAnulacion: 1, motivoAnulacion: 'Monto acreditado por error', responsable, solicitante };
  const evento = await post(`/api/dte/simulacion/${nota.codigoGeneracion}/anular`, 'nc-invalidacion-evt-001', { motivo });
  assert.equal(evento.response.status, 200, JSON.stringify(evento.body));
  assert.equal(evento.body.estado, 'SIMULADO_INVALIDADO');
  assert.equal(evento.body.issuanceMode, 'SIMULATED');
  assert.equal(fila(nota.codigoGeneracion).estado, 'SIMULADO_INVALIDADO');
  // El CCF relacionado no cambia: su bloqueo mientras tenga notas lo aplica el backend.
  assert.equal(fila(ccf.codigoGeneracion).estado, 'SIMULADO');

  const archivo = await (await fetch(`${baseUrl}/api/dte/simulacion/eventos/${evento.body.codigoGeneracionEvento}/json`, { headers: headers() })).json();
  assert.equal(archivo.documento.tipoDte, '05');
  assert.equal(archivo.documento.codigoGeneracion, nota.codigoGeneracion);
  assert.equal(archivo.documento.codigoGeneracionR, null);
  assert.equal(archivo.documento.tipoDocumento, '36');
  assert.equal(archivo.documento.numDocumento, RECEPTOR_CCF.nit);

  const otra = await post(`/api/dte/simulacion/${nota.codigoGeneracion}/anular`, 'nc-invalidacion-evt-002', { motivo: { tipoAnulacion: 2, responsable, solicitante } });
  assert.equal(otra.response.status, 409);
  assert.equal(otra.body.code, 'DTE_ALREADY_INVALIDATED');
});

test('ninguna prueba intentó salir de la máquina', async () => {
  const health = await (await fetch(`${baseUrl}/api/health`)).json();
  assert.equal(health.dteMode, 'simulated');
  assert.equal(health.blockedExternalCalls, 0);
});

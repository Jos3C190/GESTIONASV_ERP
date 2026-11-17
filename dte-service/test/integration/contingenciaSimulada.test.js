/**
 * Contingencia de un emisor simulado (bloque V4a del ERP): el operador la activa,
 * los documentos nacen en diferido con firma simulada y el evento se construye y
 * se valida contra el esquema, con un sello simulado. Nada sale del servicio.
 */
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const EMPRESA = { nit: '06142010004016', nombre: 'Demostración S.A. de C.V.' };
const RESPONSABLE = { nombre: 'Encargado de demostración', tipoDocumento: '13', numeroDocumento: '04567890-1' };

let servidorApi;
let baseUrl;
let db;

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, canonicalize(v)]));
  }
  return value;
}

function snapshot({ nit, nombre }) {
  const canonical = {
    legalName: nombre, tradeName: null, nit, nrc: '1234567', economicActivityCode: '10711',
    economicActivityDescription: 'Elaboración de productos de panadería', activityCatalogVersion: 'CAT-019',
    address: {
      departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro',
      districtCode: '14', districtName: 'San Salvador', complement: 'Calle Principal 1', geoCatalogVersion: 'GEO-1',
    },
    phone: '22221111', email: 'fiscal@example.test', establishmentType: '02', mhEstablishmentCode: '001',
    mhPointOfSaleCode: '001', internalEstablishmentCode: 'M001', internalPointOfSaleCode: 'P001',
  };
  return {
    revisionId: `rev-${nit}`,
    snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'),
    nit, nrc: '1234567', nombre, nombreComercial: null, codActividad: '10711',
    descActividad: canonical.economicActivityDescription, activityCatalogVersion: 'CAT-019',
    direccion: {
      departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro',
      distrito: '14', districtName: 'San Salvador', complemento: 'Calle Principal 1', geoCatalogVersion: 'GEO-1',
    },
    telefono: '22221111', correo: 'fiscal@example.test', tipoEstablecimiento: '02',
    codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: 'M001', codPuntoVenta: 'P001',
  };
}

function headers(nit, extra = {}) {
  return {
    Authorization: 'Bearer clave-de-prueba-para-tests',
    'Content-Type': 'application/json',
    ...(nit ? { 'X-DTE-Issuer-NIT': nit } : {}),
    ...extra,
  };
}

let secuencia = 0;
async function factura() {
  const res = await fetch(`${baseUrl}/api/dte/v2/factura`, {
    method: 'POST',
    headers: headers(EMPRESA.nit, { 'Idempotency-Key': `cont-sim-${++secuencia}` }),
    body: JSON.stringify({
      emisor: snapshot(EMPRESA),
      receptor: null,
      items: [{ descripcion: 'Pan dulce', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '01', montoPago: 113, referencia: null, numPagoElectronico: null },
    }),
  });
  return { status: res.status, body: await res.json() };
}

before(async () => {
  Object.assign(process.env, {
    DTE_MODE: 'simulated',
    DTE_SIMULATION_ACKNOWLEDGED: 'true',
    DTE_SIMULATION_RUN_ID: 'contingencia-simulada',
    DTE_SIMULATION_SQLITE_PATH: ':memory:',
    MH_NIT: '',
    DTE_AUTHORIZED_ISSUER_NITS: '',
    MS_API_KEY_SCOPES: 'issue,read,invalidate,contingency,issuers',
    // Un firmador inalcanzable: la contingencia simulada no debe llamarlo.
    FIRMADOR_URL: 'http://127.0.0.1:9/firmardocumento/',
  });
  require('../_setup');
  const baseDatos = require('../../src/db');
  db = baseDatos.db;
  require('../../src/services/correlativoStore').usar(baseDatos.obtenerSiguienteCorrelativo);
  const app = require('../../src/app');
  await new Promise((resolve) => {
    servidorApi = app.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${servidorApi.address().port}`;
      resolve();
    });
  });
  const registro = await fetch(`${baseUrl}/api/emisores/${EMPRESA.nit}`, {
    method: 'PUT',
    headers: headers(null),
    body: JSON.stringify({ nombre: EMPRESA.nombre, modo: 'simulated', tiposHabilitados: ['01'], responsable: RESPONSABLE }),
  });
  assert.equal(registro.status, 200, await registro.text());
});

after(() => servidorApi?.close());

test('activar, emitir en diferido, cerrar y quedar simulado sin salir del servicio', async () => {
  const ruta = (sufijo = '') => `${baseUrl}/api/emisores/${EMPRESA.nit}/contingencias${sufijo}`;
  const activada = await fetch(ruta(), {
    method: 'POST',
    headers: headers(null),
    body: JSON.stringify({ establecimiento: 'M001', tipoContingencia: 4, motivoContingencia: 'Corte de energía' }),
  });
  const ventana = await activada.json();
  assert.equal(activada.status, 201, JSON.stringify(ventana));

  const emitida = await factura();
  assert.equal(emitida.status, 202, JSON.stringify(emitida.body));
  assert.equal(emitida.body.estado, 'CONTINGENCIA');
  assert.equal(emitida.body.issuanceMode, 'SIMULATED');
  const fila = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(emitida.body.codigoGeneracion);
  assert.equal(fila.estado, 'CONTINGENCIA');
  assert.ok(fila.documento_firmado, 'lleva firma simulada');
  const payload = JSON.parse(fila.payload_json);
  assert.equal(payload.identificacion.tipoModelo, 2);
  assert.equal(payload.identificacion.tipoContingencia, 4);

  const consulta = await fetch(`${baseUrl}/api/dte/${emitida.body.codigoGeneracion}`, { headers: headers(EMPRESA.nit) });
  assert.equal(consulta.status, 200);
  assert.equal((await consulta.json()).estado, 'CONTINGENCIA');

  const cerrada = await fetch(ruta(`/${ventana.id}/cerrar`), { method: 'POST', headers: headers(null), body: '{}' });
  assert.equal(cerrada.status, 200);
  const resumen = await cerrada.json();
  assert.equal(resumen.estado, 'COMPLETADA', JSON.stringify(resumen));
  assert.equal(resumen.evento.estado, 'ACEPTADO');
  assert.equal(resumen.evento.selloRecepcion.length, 40);
  assert.equal(db.prepare('SELECT estado FROM dtes WHERE codigo_generacion = ?').get(emitida.body.codigoGeneracion).estado, 'SIMULADO');
  const evento = db.prepare('SELECT * FROM eventos WHERE codigo_generacion = ?').get(resumen.evento.codigoGeneracion);
  assert.equal(JSON.parse(evento.payload_json).emisor.nombreResponsable, RESPONSABLE.nombre);
  assert.ok(evento.simulation_marker);

  // Después de la ventana se emite normal.
  const normal = await factura();
  assert.equal(normal.status, 201);
  assert.equal(normal.body.estado, 'SIMULADO');
});

/**
 * Multiemisor (bloque V3a del ERP): un despliegue en modo simulado sin emisor
 * en el entorno, con dos empresas registradas desde el ERP.
 */
const { test, before, after } = require('node:test');
const { certificadoPrueba } = require('../helpers/certificadoPrueba');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

process.env.DTE_MODE = 'simulated';
process.env.DTE_SIMULATION_ACKNOWLEDGED = 'true';
process.env.DTE_SIMULATION_SQLITE_PATH = ':memory:';
process.env.MH_NIT = '';
process.env.DTE_AUTHORIZED_ISSUER_NITS = '';
process.env.MS_API_KEY_SCOPES = 'issue,read,invalidate,contingency,simulate,issuers';
process.env.MS_AUTH_DESHABILITADA = 'false';
require('../_setup');

const API_KEY = 'clave-de-prueba-para-tests';
const EMPRESA_A = { nit: '06142010001018', nombre: 'Panificadora del Norte S.A. de C.V.' };
const EMPRESA_B = { nit: '06142010001026', nombre: 'Distribuidora del Sur S.A. de C.V.' };
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
  for (const empresa of [EMPRESA_A, EMPRESA_B]) {
    const respuesta = await registrar(empresa.nit, { nombre: empresa.nombre, modo: 'simulated', tiposHabilitados: ['01', '03'] });
    assert.equal(respuesta.status, 200, await respuesta.text());
  }
});

after(() => server?.close());

function headers(nit, extra = {}) {
  return {
    Authorization: `Bearer ${API_KEY}`,
    'Content-Type': 'application/json',
    ...(nit ? { 'X-DTE-Issuer-NIT': nit } : {}),
    ...extra,
  };
}

function registrar(nit, datos) {
  return fetch(`${baseUrl}/api/emisores/${nit}`, { method: 'PUT', headers: headers(null), body: JSON.stringify(datos) });
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  }
  return value;
}

/** Snapshot v2 del emisor; ambas empresas usan el mismo establecimiento 001 y punto 001. */
function snapshot({ nit, nombre }) {
  const canonical = {
    legalName: nombre, tradeName: null, nit, nrc: '1234567', economicActivityCode: '10711',
    economicActivityDescription: 'Elaboración de productos de panadería', activityCatalogVersion: 'CAT-019',
    address: {
      departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro',
      districtCode: '14', districtName: 'San Salvador', complement: 'Calle Principal 1', geoCatalogVersion: 'GEO-1',
    },
    phone: '22221111', email: 'fiscal@example.test', establishmentType: '02', mhEstablishmentCode: '001',
    mhPointOfSaleCode: '001', internalEstablishmentCode: null, internalPointOfSaleCode: null,
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
    codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: null, codPuntoVenta: null,
  };
}

function factura(empresa, clave, { nitEncabezado = empresa.nit, tipo = 'factura' } = {}) {
  const cuerpo = {
    emisor: snapshot(empresa),
    receptor: null,
    items: [{ descripcion: 'Pan dulce', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
    pago: { codigo: '01', montoPago: 113, referencia: null, numPagoElectronico: null },
  };
  return fetch(`${baseUrl}/api/dte/v2/${tipo}`, {
    method: 'POST',
    headers: headers(nitEncabezado, { 'Idempotency-Key': clave }),
    body: JSON.stringify(cuerpo),
  });
}

test('sin emisor declarado la solicitud se rechaza', async () => {
  const respuesta = await factura(EMPRESA_A, 'multi-sin-emisor-01', { nitEncabezado: null });
  assert.equal(respuesta.status, 400);
  assert.equal((await respuesta.json()).code, 'ISSUER_REQUIRED');
});

test('cada empresa lleva su numeración aunque compartan establecimiento y punto de venta', async () => {
  const a = await (await factura(EMPRESA_A, 'multi-serie-a-01')).json();
  const b = await (await factura(EMPRESA_B, 'multi-serie-b-01')).json();
  const a2 = await (await factura(EMPRESA_A, 'multi-serie-a-02')).json();
  assert.equal(a.estado, 'SIMULADO', JSON.stringify(a));
  assert.equal(b.estado, 'SIMULADO', JSON.stringify(b));
  const correlativo = (numero) => Number(numero.slice(-15));
  assert.equal(correlativo(b.numeroControl), 1);
  assert.equal(correlativo(a2.numeroControl), correlativo(a.numeroControl) + 1);
});

test('una empresa no ve los documentos de otra', async () => {
  const emitido = await (await factura(EMPRESA_A, 'multi-propiedad-a-01')).json();
  const propio = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/json`, { headers: headers(EMPRESA_A.nit) });
  assert.equal(propio.status, 200);
  assert.equal((await propio.json()).emisor.nit, EMPRESA_A.nit);
  const ajeno = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/json`, { headers: headers(EMPRESA_B.nit) });
  assert.equal(ajeno.status, 404);
  const pdfAjeno = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/pdf`, { headers: headers(EMPRESA_B.nit) });
  assert.equal(pdfAjeno.status, 404);
});

test('la misma clave de idempotencia en dos empresas crea dos documentos', async () => {
  const a = await (await factura(EMPRESA_A, 'multi-clave-compartida')).json();
  const b = await (await factura(EMPRESA_B, 'multi-clave-compartida')).json();
  assert.notEqual(a.codigoGeneracion, b.codigoGeneracion);
  const repetido = await (await factura(EMPRESA_A, 'multi-clave-compartida')).json();
  assert.equal(repetido.codigoGeneracion, a.codigoGeneracion);
});

test('el emisor del documento debe coincidir con el de la solicitud', async () => {
  const respuesta = await factura(EMPRESA_B, 'multi-mezcla-01', { nitEncabezado: EMPRESA_A.nit });
  assert.equal(respuesta.status, 400);
  assert.equal((await respuesta.json()).code, 'ISSUER_MISMATCH');
});

test('emisor no registrado, desactivado o con el tipo no habilitado se rechaza', async () => {
  const intruso = { nit: '06142010001034', nombre: 'Empresa sin registro' };
  const sinRegistro = await factura(intruso, 'multi-intruso-01');
  assert.equal(sinRegistro.status, 403);
  assert.equal((await sinRegistro.json()).code, 'UNAUTHORIZED_ISSUER');

  const solo01 = { nit: '06142010001042', nombre: 'Empresa solo factura' };
  assert.equal((await registrar(solo01.nit, { nombre: solo01.nombre, modo: 'simulated', tiposHabilitados: ['01'] })).status, 200);
  const ccf = await factura(solo01, 'multi-tipo-01', { tipo: 'ccf' });
  assert.equal(ccf.status, 403);
  assert.equal((await ccf.json()).code, 'DTE_DOCUMENT_TYPE_NOT_ALLOWED');

  assert.equal((await registrar(solo01.nit, { nombre: solo01.nombre, modo: 'simulated', tiposHabilitados: ['01'], activo: false })).status, 200);
  const inactivo = await factura(solo01, 'multi-inactivo-01');
  assert.equal(inactivo.status, 403);

  const otroModo = { nit: '06142010001050', nombre: 'Empresa en pruebas' };
  const sinClaves = await registrar(otroModo.nit, { nombre: otroModo.nombre, modo: 'hacienda-test', tiposHabilitados: ['01'] });
  assert.equal(sinClaves.status, 400);
  assert.equal((await sinClaves.json()).code, 'ISSUER_CREDENTIALS_REQUIRED');
  const conClaves = await registrar(otroModo.nit, {
    nombre: otroModo.nombre,
    modo: 'hacienda-test',
    tiposHabilitados: ['01'],
    credenciales: { passwordApi: 'api', passwordPri: 'pri', certificado: certificadoPrueba(otroModo.nit, 'pri').toString('base64') },
  });
  assert.equal(conClaves.status, 200);
  const registrado = await conClaves.json();
  assert.equal(registrado.credenciales.configuradas, true);
  assert.equal(JSON.stringify(registrado).includes('pri"'), false);
  const modo = await factura(otroModo, 'multi-modo-01');
  assert.equal(modo.status, 409);
  assert.equal((await modo.json()).code, 'ISSUER_MODE_UNAVAILABLE');
});

test('el registro de emisores exige el alcance issuers', async () => {
  const sinClave = await fetch(`${baseUrl}/api/emisores`);
  assert.equal(sinClave.status, 401);
  const lista = await (await fetch(`${baseUrl}/api/emisores`, { headers: headers(null) })).json();
  assert.ok(lista.emisores.some((e) => e.nit === EMPRESA_A.nit));
});

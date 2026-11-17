/**
 * Modo por emisor (bloque V3d del ERP): un despliegue que admite hasta
 * hacienda-test, sin emisor en el entorno, con dos empresas a la vez:
 *
 * - una en pruebas, que se autentica con su NIT y su contraseña de la API y
 *   firma con su NIT y su contraseña privada contra un Hacienda y un firmador
 *   simulados por HTTP;
 * - otra en simulado, que emite sin tocar Hacienda ni el firmador.
 */
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const http = require('node:http');

const EN_PRUEBAS = { nit: '06142010002011', nombre: 'Panificadora en pruebas S.A. de C.V.', api: 'api-pruebas', pri: 'pri-pruebas' };
const OTRA_EN_PRUEBAS = { nit: '06142010002029', nombre: 'Otra en pruebas S.A. de C.V.', api: 'api-otra', pri: 'pri-otra' };
const SIMULADA = { nit: '06142010002037', nombre: 'Demostración S.A. de C.V.' };
const SELLO = '2026B1C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A8';

const llamadas = [];
const servidorHacienda = http.createServer((req, res) => {
  let datos = '';
  req.on('data', (parte) => { datos += parte; });
  req.on('end', () => {
    const json = (status, cuerpo) => {
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(cuerpo));
    };
    if (req.url === '/seguridad/auth') {
      const { user, pwd } = Object.fromEntries(new URLSearchParams(datos));
      llamadas.push({ ruta: 'auth', user });
      const empresa = [EN_PRUEBAS, OTRA_EN_PRUEBAS].find((e) => e.nit === user && e.api === pwd);
      if (!empresa) return json(401, { status: 'ERROR', body: { descripcionMsg: 'Usuario o contraseña incorrectos' } });
      return json(200, { status: 'OK', body: { token: `Bearer token-${user}` } });
    }
    const cuerpo = datos ? JSON.parse(datos) : null;
    if (req.url === '/firmardocumento/') {
      llamadas.push({ ruta: 'firmar', nit: cuerpo.nit, passwordPri: cuerpo.passwordPri, ambiente: cuerpo.dteJson.identificacion.ambiente });
      return json(200, { status: 'OK', body: `eyJhbGciOiJSUzUxMiJ9.${Buffer.from(cuerpo.nit).toString('base64url')}.firma` });
    }
    if (req.url === '/fesv/recepciondte') {
      llamadas.push({ ruta: 'recepcion', token: req.headers.authorization, ambiente: cuerpo.ambiente });
      return json(200, {
        version: 2, ambiente: '00', versionApp: 2, estado: 'PROCESADO', codigoGeneracion: cuerpo.codigoGeneracion,
        selloRecibido: SELLO, fhProcesamiento: '17/11/2026 10:00:00', clasificaMsg: '10', codigoMsg: '001',
        descripcionMsg: 'RECIBIDO', observaciones: [],
      });
    }
    res.writeHead(404);
    return res.end();
  });
});

let servidorApi;
let baseUrl;

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

function headers(nit, extra = {}) {
  return {
    Authorization: 'Bearer clave-de-prueba-para-tests',
    'Content-Type': 'application/json',
    ...(nit ? { 'X-DTE-Issuer-NIT': nit } : {}),
    ...extra,
  };
}

function registrar(empresa, datos) {
  return fetch(`${baseUrl}/api/emisores/${empresa.nit}`, {
    method: 'PUT',
    headers: headers(null),
    body: JSON.stringify({ nombre: empresa.nombre, tiposHabilitados: ['01'], ...datos }),
  });
}

async function factura(empresa, clave) {
  const res = await fetch(`${baseUrl}/api/dte/v2/factura`, {
    method: 'POST',
    headers: headers(empresa.nit, { 'Idempotency-Key': clave }),
    body: JSON.stringify({
      emisor: snapshot(empresa),
      receptor: null,
      items: [{ descripcion: 'Pan dulce', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '01', montoPago: 113, referencia: null, numPagoElectronico: null },
    }),
  });
  return { status: res.status, body: await res.json() };
}

before(async () => {
  await new Promise((resolve) => servidorHacienda.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${servidorHacienda.address().port}`;
  Object.assign(process.env, {
    DTE_MODE: 'hacienda-test',
    MH_NIT: '',
    DTE_AUTHORIZED_ISSUER_NITS: '',
    MS_API_KEY_SCOPES: 'issue,read,invalidate,contingency,issuers',
    DTE_ALLOW_NON_OFFICIAL_MH_HOSTS: 'true',
    MH_AUTH_URL: `${base}/seguridad/auth`,
    MH_RECEPCION_URL: `${base}/fesv/recepciondte`,
    MH_RECEPCION_LOTE_URL: `${base}/fesv/recepcionlote`,
    MH_ANULACION_URL: `${base}/fesv/anulardte`,
    MH_CONTINGENCIA_URL: `${base}/fesv/contingencia`,
    MH_CONSULTA_URL: `${base}/fesv/recepcion/consultadte`,
    MH_CONSULTA_LOTE_URL: `${base}/fesv/recepcion/consultadtelote`,
    FIRMADOR_URL: `${base}/firmardocumento/`,
  });
  require('../_setup');
  const { obtenerSiguienteCorrelativo } = require('../../src/db');
  require('../../src/services/correlativoStore').usar(obtenerSiguienteCorrelativo);
  const { certificadoPrueba } = require('../helpers/certificadoPrueba');
  const app = require('../../src/app');
  await new Promise((resolve) => {
    servidorApi = app.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${servidorApi.address().port}`;
      resolve();
    });
  });
  for (const empresa of [EN_PRUEBAS, OTRA_EN_PRUEBAS]) {
    const registro = await registrar(empresa, {
      modo: 'hacienda-test',
      credenciales: {
        passwordApi: empresa.api,
        passwordPri: empresa.pri,
        certificado: certificadoPrueba(empresa.nit, empresa.pri).toString('base64'),
      },
    });
    assert.equal(registro.status, 200, await registro.text());
  }
  assert.equal((await registrar(SIMULADA, { modo: 'simulated' })).status, 200);
});

after(() => {
  servidorApi?.close();
  servidorHacienda.closeAllConnections();
  servidorHacienda.close();
});

test('cada empresa en pruebas se autentica y firma con lo suyo, y la simulada no sale', async () => {
  const pruebas = await factura(EN_PRUEBAS, 'modo-pruebas-01');
  assert.equal(pruebas.status, 201, JSON.stringify(pruebas.body));
  assert.equal(pruebas.body.estado, 'TRANSMITIDO');
  assert.equal(pruebas.body.selloRecepcion, SELLO);

  const otra = await factura(OTRA_EN_PRUEBAS, 'modo-otra-01');
  assert.equal(otra.status, 201, JSON.stringify(otra.body));

  const simulada = await factura(SIMULADA, 'modo-simulada-01');
  assert.equal(simulada.status, 201, JSON.stringify(simulada.body));
  assert.equal(simulada.body.estado, 'SIMULADO');

  // Un token por empresa y cada firma con su NIT, su contraseña privada y el ambiente 00.
  assert.deepEqual(llamadas.filter((l) => l.ruta === 'auth').map((l) => l.user).sort(), [EN_PRUEBAS.nit, OTRA_EN_PRUEBAS.nit].sort());
  const firmas = llamadas.filter((l) => l.ruta === 'firmar');
  assert.deepEqual(firmas.map((f) => [f.nit, f.passwordPri, f.ambiente]), [
    [EN_PRUEBAS.nit, EN_PRUEBAS.pri, '00'],
    [OTRA_EN_PRUEBAS.nit, OTRA_EN_PRUEBAS.pri, '00'],
  ]);
  assert.deepEqual(llamadas.filter((l) => l.ruta === 'recepcion').map((l) => l.token), [
    `Bearer token-${EN_PRUEBAS.nit}`,
    `Bearer token-${OTRA_EN_PRUEBAS.nit}`,
  ]);

  // El token se reutiliza: una segunda emisión no vuelve a autenticar.
  assert.equal((await factura(EN_PRUEBAS, 'modo-pruebas-02')).status, 201);
  assert.equal(llamadas.filter((l) => l.ruta === 'auth' && l.user === EN_PRUEBAS.nit).length, 1);
});

test('las credenciales de la API equivocadas fallan como error de configuración', async () => {
  const mal = { ...EN_PRUEBAS, nit: '06142010002045', api: 'no-es-esta', pri: 'pri-mal', nombre: 'Clave equivocada S.A.' };
  const { certificadoPrueba } = require('../helpers/certificadoPrueba');
  const registro = await registrar(mal, {
    modo: 'hacienda-test',
    credenciales: { passwordApi: mal.api, passwordPri: mal.pri, certificado: certificadoPrueba(mal.nit, mal.pri).toString('base64') },
  });
  assert.equal(registro.status, 200);
  const respuesta = await factura(mal, 'modo-mal-01');
  assert.notEqual(respuesta.status, 201);
  assert.equal(llamadas.some((l) => l.ruta === 'firmar' && l.nit === mal.nit), true);
  assert.equal(llamadas.some((l) => l.ruta === 'recepcion' && l.token === `Bearer token-${mal.nit}`), false);
});

test('un emisor de producción no emite en un despliegue que admite hasta pruebas', async () => {
  const prod = { nit: '06142010002053', nombre: 'Producción S.A.', pri: 'p' };
  const { certificadoPrueba } = require('../helpers/certificadoPrueba');
  await registrar(prod, {
    modo: 'production',
    credenciales: { passwordApi: 'a', passwordPri: prod.pri, certificado: certificadoPrueba(prod.nit, prod.pri).toString('base64') },
  });
  const respuesta = await factura(prod, 'modo-prod-01');
  assert.equal(respuesta.status, 409);
  assert.equal(respuesta.body.code, 'ISSUER_MODE_UNAVAILABLE');
});

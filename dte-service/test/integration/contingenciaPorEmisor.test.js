/**
 * Contingencia por emisor y establecimiento (bloque V4a del ERP).
 *
 * Despliegue hasta hacienda-test, sin emisor en el entorno, con dos empresas en
 * pruebas contra un Hacienda y un firmador simulados por HTTP:
 *
 * - una ventana de la empresa A en su establecimiento M001 no afecta a su
 *   establecimiento M002 ni a la empresa B;
 * - el evento de esa ventana se firma, se autentica y se transmite con lo de A
 *   y lleva el responsable registrado con A;
 * - una caída que solo afecta a B abre la ventana de B, no la de A.
 */
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const http = require('node:http');

const EMPRESA_A = { nit: '06142010003010', nombre: 'Panificadora A S.A. de C.V.', api: 'api-a', pri: 'pri-a' };
const EMPRESA_B = { nit: '06142010003028', nombre: 'Panificadora B S.A. de C.V.', api: 'api-b', pri: 'pri-b' };
const RESPONSABLE_A = { nombre: 'Encargada de tienda A', tipoDocumento: '13', numeroDocumento: '01234567-8' };
const SELLO_DTE = '2026A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8';
const SELLO_EVENTO = '2026EVENTO0000000000000000000000000000001';

const llamadas = [];
/** NIT cuya recepción se corta (sin respuesta de Hacienda) para simular la caída. */
const caidos = new Set();

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
      const empresa = [EMPRESA_A, EMPRESA_B].find((e) => e.nit === user && e.api === pwd);
      if (!empresa) return json(401, { status: 'ERROR', body: { descripcionMsg: 'Usuario o contraseña incorrectos' } });
      return json(200, { status: 'OK', body: { token: `Bearer token-${user}` } });
    }
    const cuerpo = datos ? JSON.parse(datos) : null;
    if (req.url === '/firmardocumento/') {
      const tipo = cuerpo.dteJson.detalleDTE ? 'evento' : 'dte';
      llamadas.push({ ruta: 'firmar', tipo, nit: cuerpo.nit, passwordPri: cuerpo.passwordPri, documento: cuerpo.dteJson });
      return json(200, { status: 'OK', body: `eyJhbGciOiJSUzUxMiJ9.${Buffer.from(cuerpo.nit).toString('base64url')}.firma` });
    }
    const nitDelToken = String(req.headers.authorization || '').replace('Bearer token-', '');
    if (req.url === '/fesv/recepciondte') {
      if (caidos.has(nitDelToken)) return req.socket.destroy();
      llamadas.push({ ruta: 'recepcion', nit: nitDelToken });
      return json(200, {
        version: 2, ambiente: '00', versionApp: 2, estado: 'PROCESADO', codigoGeneracion: cuerpo.codigoGeneracion,
        selloRecibido: SELLO_DTE, fhProcesamiento: '17/11/2026 10:00:00', clasificaMsg: '10', codigoMsg: '001',
        descripcionMsg: 'RECIBIDO', observaciones: [],
      });
    }
    if (req.url === '/fesv/contingencia') {
      llamadas.push({ ruta: 'contingencia', nit: cuerpo.nit, token: nitDelToken });
      return json(200, { estado: 'RECIBIDO', selloRecibido: SELLO_EVENTO, mensaje: 'EVENTO RECIBIDO' });
    }
    if (req.url === '/fesv/recepcion/consultadte') {
      if (caidos.has(nitDelToken)) return req.socket.destroy();
      return json(404, {});
    }
    res.writeHead(404);
    return res.end();
  });
});

let servidorApi;
let baseUrl;
let contingenciaService;
let retryQueue;
let db;

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, canonicalize(v)]));
  }
  return value;
}

function snapshot({ nit, nombre }, establecimiento) {
  const codigoMH = establecimiento === 'M001' ? '001' : '002';
  const canonical = {
    legalName: nombre, tradeName: null, nit, nrc: '1234567', economicActivityCode: '10711',
    economicActivityDescription: 'Elaboración de productos de panadería', activityCatalogVersion: 'CAT-019',
    address: {
      departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro',
      districtCode: '14', districtName: 'San Salvador', complement: 'Calle Principal 1', geoCatalogVersion: 'GEO-1',
    },
    phone: '22221111', email: 'fiscal@example.test', establishmentType: '02', mhEstablishmentCode: codigoMH,
    mhPointOfSaleCode: '001', internalEstablishmentCode: establecimiento, internalPointOfSaleCode: 'P001',
  };
  return {
    revisionId: `rev-${nit}-${establecimiento}`,
    snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'),
    nit, nrc: '1234567', nombre, nombreComercial: null, codActividad: '10711',
    descActividad: canonical.economicActivityDescription, activityCatalogVersion: 'CAT-019',
    direccion: {
      departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro',
      distrito: '14', districtName: 'San Salvador', complemento: 'Calle Principal 1', geoCatalogVersion: 'GEO-1',
    },
    telefono: '22221111', correo: 'fiscal@example.test', tipoEstablecimiento: '02',
    codEstablecimientoMH: codigoMH, codPuntoVentaMH: '001', codEstable: establecimiento, codPuntoVenta: 'P001',
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
    body: JSON.stringify({ nombre: empresa.nombre, modo: 'hacienda-test', tiposHabilitados: ['01'], ...datos }),
  });
}

let secuencia = 0;
async function factura(empresa, establecimiento) {
  const res = await fetch(`${baseUrl}/api/dte/v2/factura`, {
    method: 'POST',
    headers: headers(empresa.nit, { 'Idempotency-Key': `cont-emisor-${++secuencia}` }),
    body: JSON.stringify({
      emisor: snapshot(empresa, establecimiento),
      receptor: null,
      items: [{ descripcion: 'Pan dulce', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
      pago: { codigo: '01', montoPago: 113, referencia: null, numPagoElectronico: null },
    }),
  });
  return { status: res.status, body: await res.json() };
}

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

before(async () => {
  await new Promise((resolve) => servidorHacienda.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${servidorHacienda.address().port}`;
  Object.assign(process.env, {
    DTE_MODE: 'hacienda-test',
    MH_NIT: '',
    DTE_AUTHORIZED_ISSUER_NITS: '',
    DTE_ALLOW_FORCED_CONTINGENCY: 'true',
    MH_RESPONSABLE_NOMBRE: '',
    MH_RESPONSABLE_TIPO_DOC: '',
    MH_RESPONSABLE_NUM_DOC: '',
    RETRY_MAX_ATTEMPTS: '2',
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
  const baseDatos = require('../../src/db');
  db = baseDatos.db;
  require('../../src/services/correlativoStore').usar(baseDatos.obtenerSiguienteCorrelativo);
  contingenciaService = require('../../src/services/contingenciaService');
  retryQueue = require('../../src/services/retryQueue');
  const { certificadoPrueba } = require('../helpers/certificadoPrueba');
  const app = require('../../src/app');
  await new Promise((resolve) => {
    servidorApi = app.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${servidorApi.address().port}`;
      resolve();
    });
  });
  for (const empresa of [EMPRESA_A, EMPRESA_B]) {
    const registro = await registrar(empresa, {
      credenciales: {
        passwordApi: empresa.api,
        passwordPri: empresa.pri,
        certificado: certificadoPrueba(empresa.nit, empresa.pri).toString('base64'),
      },
      ...(empresa === EMPRESA_A ? { responsable: RESPONSABLE_A } : {}),
    });
    assert.equal(registro.status, 200, await registro.text());
  }
});

after(() => {
  servidorApi?.close();
  servidorHacienda.closeAllConnections();
  servidorHacienda.close();
});

test('el responsable se registra con el emisor, se valida y se conserva si no se envía', async () => {
  const invalido = await registrar(EMPRESA_B, { responsable: { nombre: 'Sin documento', tipoDocumento: '99', numeroDocumento: '1' } });
  assert.equal(invalido.status, 400);
  assert.equal((await invalido.json()).code, 'INVALID_ISSUER');

  const sinCampo = await registrar(EMPRESA_A, {});
  assert.equal(sinCampo.status, 200);
  assert.deepEqual((await sinCampo.json()).responsable, RESPONSABLE_A);
});

test('una ventana de un establecimiento no afecta al otro establecimiento ni a otra empresa', async () => {
  const ventana = contingenciaService.forzar({
    clave: { nit: EMPRESA_A.nit, establecimiento: 'M001' },
    tipoContingencia: 5,
    motivoContingencia: 'Corte de energía en la tienda M001',
  });
  assert.equal(ventana.nit, EMPRESA_A.nit);
  assert.equal(ventana.establecimiento, 'M001');

  const enContingencia = await factura(EMPRESA_A, 'M001');
  assert.equal(enContingencia.status, 202, JSON.stringify(enContingencia.body));
  assert.equal(enContingencia.body.estado, 'CONTINGENCIA');
  const diferido = JSON.parse(leerDte(enContingencia.body.codigoGeneracion).payload_json);
  assert.equal(diferido.identificacion.tipoModelo, 2);
  assert.equal(diferido.identificacion.motivoContin, 'Corte de energía en la tienda M001');

  const otraTienda = await factura(EMPRESA_A, 'M002');
  assert.equal(otraTienda.status, 201, JSON.stringify(otraTienda.body));
  assert.equal(otraTienda.body.estado, 'TRANSMITIDO');
  const otraEmpresa = await factura(EMPRESA_B, 'M001');
  assert.equal(otraEmpresa.status, 201, JSON.stringify(otraEmpresa.body));
  assert.equal(otraEmpresa.body.estado, 'TRANSMITIDO');

  assert.equal(contingenciaService.estadoGeneral({ nit: EMPRESA_B.nit }).ventanas.length, 0);
  const deA = contingenciaService.estadoGeneral({ nit: EMPRESA_A.nit });
  assert.equal(deA.activa, true);
  assert.equal(deA.responsableConfigurado, true);
  assert.deepEqual(deA.ventanas.map((v) => [v.establecimiento, v.documentos.total]), [['M001', 1]]);

  // El evento se firma y se transmite con lo de A y lleva su responsable.
  llamadas.length = 0;
  contingenciaService.cerrar(ventana.id);
  const informada = await contingenciaService.enviarEvento(ventana.id);
  assert.equal(informada.estado, 'REPORTADA', JSON.stringify(informada));
  const [firmaEvento] = llamadas.filter((l) => l.ruta === 'firmar' && l.tipo === 'evento');
  assert.equal(firmaEvento.nit, EMPRESA_A.nit);
  assert.equal(firmaEvento.passwordPri, EMPRESA_A.pri);
  assert.equal(firmaEvento.documento.emisor.nombreResponsable, RESPONSABLE_A.nombre);
  assert.deepEqual(firmaEvento.documento.detalleDTE.map((d) => d.codigoGeneracion), [enContingencia.body.codigoGeneracion]);
  assert.deepEqual(llamadas.filter((l) => l.ruta === 'contingencia').map((l) => [l.nit, l.token]), [[EMPRESA_A.nit, EMPRESA_A.nit]]);

  // Momento 3: el documento se transmite con el token de A.
  await retryQueue.procesarCola();
  assert.equal(leerDte(enContingencia.body.codigoGeneracion).estado, 'TRANSMITIDO');
  assert.ok(llamadas.some((l) => l.ruta === 'recepcion' && l.nit === EMPRESA_A.nit));
});

test('una caída que solo afecta a una empresa abre la ventana de esa empresa y ese establecimiento', async () => {
  caidos.add(EMPRESA_B.nit);
  try {
    const caida = await factura(EMPRESA_B, 'M002');
    // Sin respuesta tras la política de reintentos: el documento queda en espera o en contingencia.
    assert.ok([201, 202].includes(caida.status), JSON.stringify(caida.body));
    for (let intento = 0; intento < 5 && leerDte(caida.body.codigoGeneracion).estado !== 'CONTINGENCIA'; intento += 1) {
      db.prepare(`UPDATE cola_reintentos SET proximo_intento = datetime('now')`).run();
      await retryQueue.procesarCola();
    }
    assert.equal(leerDte(caida.body.codigoGeneracion).estado, 'CONTINGENCIA');
    const deB = contingenciaService.estadoGeneral({ nit: EMPRESA_B.nit });
    assert.deepEqual(deB.ventanas.map((v) => [v.establecimiento, v.estado]), [['M002', 'ACTIVA']]);
    assert.equal(deB.responsableConfigurado, false);
    assert.equal(contingenciaService.ventanaActiva({ nit: EMPRESA_A.nit, establecimiento: 'M002' }), null);

    // La otra empresa sigue emitiendo normal en el mismo establecimiento.
    const normal = await factura(EMPRESA_A, 'M002');
    assert.equal(normal.status, 201, JSON.stringify(normal.body));
  } finally {
    caidos.delete(EMPRESA_B.nit);
  }

  // Al volver Hacienda, el sondeo cierra la ventana de B; sin responsable, el evento espera.
  const cerradas = await contingenciaService.sondearRecuperacion({ forzar: true });
  assert.deepEqual(cerradas.map((v) => [v.nit_emisor, v.cod_establecimiento, v.estado]), [[EMPRESA_B.nit, 'M002', 'CERRADA']]);
  await contingenciaService.procesar();
  const deB = contingenciaService.estadoGeneral({ nit: EMPRESA_B.nit });
  assert.equal(deB.ventanas[0].estado, 'CERRADA');
  assert.equal(llamadas.filter((l) => l.ruta === 'contingencia' && l.nit === EMPRESA_B.nit).length, 0);
});

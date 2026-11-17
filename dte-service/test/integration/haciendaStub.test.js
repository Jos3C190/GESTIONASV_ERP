/**
 * Integración contra un servidor HTTP que imita al firmador y a los
 * servicios de Hacienda (Manual Técnico v2.0, sección 4). A diferencia de
 * dteEmission.test.js no se reemplazan funciones: corren authService,
 * haciendaClient, firmadorClient, la cola de reintentos y las rutas reales,
 * de modo que se prueban los códigos HTTP, encabezados y cuerpos tal como
 * viajan por la red (p. ej. el RECHAZADO llega con HTTP 400).
 */
const { test, describe, before, beforeEach, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

const NIT = '06141804941035';
const TOKEN = 'Bearer eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJzdHViIn0.dG9rZW4';
const JWS = 'eyJhbGciOiJSUzUxMiJ9.eyJzdHViIjp0cnVlfQ.ZmlybWEtZGUtcHJ1ZWJh';
const SELLO = '2026A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8';
const SELLO_EVENTO = '2026EVENTO0000000000000000000000000000001';

const FACTURA = {
  receptor: null,
  items: [{ descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
  pago: { codigo: '05', montoPago: 113, referencia: 'TRANSFER-STUB', numPagoElectronico: null },
};

const RUTAS = {
  '/seguridad/auth': 'auth',
  '/firmardocumento/': 'firmar',
  '/fesv/recepciondte': 'recepcion',
  '/fesv/recepcion/consultadte': 'consulta',
  '/fesv/anulardte': 'anulacion',
};

function json(status, cuerpo) {
  return (_llamada, res) => {
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(cuerpo === undefined ? '' : JSON.stringify(cuerpo));
  };
}

const respuestasPendientes = [];
/** No responde: el cliente agota MH_TIMEOUT_MS como si Hacienda no contestara. */
function colgar() {
  return (_llamada, res) => respuestasPendientes.push(res);
}

const PREDETERMINADOS = {
  auth: json(200, { status: 'OK', body: { user: NIT, token: TOKEN, tokenType: 'Bearer', roles: [] } }),
  firmar: json(200, { status: 'OK', body: JWS }),
  recepcion: (llamada, res) => json(200, {
    version: 2,
    ambiente: '00',
    versionApp: 2,
    estado: 'PROCESADO',
    codigoGeneracion: llamada.cuerpo.codigoGeneracion,
    selloRecibido: SELLO,
    fhProcesamiento: '14/10/2026 10:00:00',
    clasificaMsg: '10',
    codigoMsg: '001',
    descripcionMsg: 'RECIBIDO',
    observaciones: [],
  })(llamada, res),
  consulta: json(404, {}),
  anulacion: json(200, { estado: 'PROCESADO', selloRecibido: SELLO_EVENTO, codigoMsg: '001', descripcionMsg: 'INVALIDACION PROCESADA' }),
};

let manejadores;
let llamadas;

function programar(ruta, ...respuestas) {
  manejadores[ruta].push(...respuestas);
}

function llamadasA(ruta) {
  return llamadas.filter((llamada) => llamada.ruta === ruta);
}

function parsearCuerpo(datos, contentType = '') {
  if (!datos) return null;
  if (contentType.includes('application/x-www-form-urlencoded')) return Object.fromEntries(new URLSearchParams(datos));
  return JSON.parse(datos);
}

const servidorHacienda = http.createServer((req, res) => {
  let datos = '';
  req.on('data', (fragmento) => { datos += fragmento; });
  req.on('end', () => {
    const ruta = RUTAS[req.url];
    if (!ruta) {
      res.writeHead(404);
      res.end();
      return;
    }
    const llamada = { ruta, headers: req.headers, cuerpo: parsearCuerpo(datos, req.headers['content-type']) };
    llamadas.push(llamada);
    (manejadores[ruta].shift() || PREDETERMINADOS[ruta])(llamada, res);
  });
});

let servidorApi;
let baseUrl;
let db;
let retryQueue;
let authService;
let secuenciaClaves = 0;

async function emitir(cuerpo = FACTURA, clave = `stub-emision-${++secuenciaClaves}`) {
  const res = await fetch(`${baseUrl}/api/dte/factura`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer clave-de-prueba-para-tests', 'Idempotency-Key': clave },
    body: JSON.stringify(cuerpo),
  });
  return { status: res.status, body: await res.json() };
}

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function adelantarCola() {
  db.prepare(`UPDATE cola_reintentos SET proximo_intento = datetime('now', '-1 second')`).run();
}

describe('Emisión contra un Hacienda simulado por HTTP', () => {
  before(async () => {
    await new Promise((resolve) => servidorHacienda.listen(0, '127.0.0.1', resolve));
    const base = `http://127.0.0.1:${servidorHacienda.address().port}`;
    Object.assign(process.env, {
      DTE_ALLOW_NON_OFFICIAL_MH_HOSTS: 'true',
      MH_AUTH_URL: `${base}/seguridad/auth`,
      MH_RECEPCION_URL: `${base}/fesv/recepciondte`,
      MH_RECEPCION_LOTE_URL: `${base}/fesv/recepcionlote`,
      MH_ANULACION_URL: `${base}/fesv/anulardte`,
      MH_CONTINGENCIA_URL: `${base}/fesv/contingencia`,
      MH_CONSULTA_URL: `${base}/fesv/recepcion/consultadte`,
      MH_CONSULTA_LOTE_URL: `${base}/fesv/recepcion/consultadtelote`,
      FIRMADOR_URL: `${base}/firmardocumento/`,
      MH_TIMEOUT_MS: '250',
      RETRY_MAX_ATTEMPTS: '3',
      RETRY_BASE_DELAY_MS: '30',
    });
    require('../_setup');

    ({ db } = require('../../src/db'));
    const { obtenerSiguienteCorrelativo } = require('../../src/db');
    require('../../src/services/correlativoStore').usar(obtenerSiguienteCorrelativo);
    retryQueue = require('../../src/services/retryQueue');
    authService = require('../../src/services/authService');

    const app = require('../../src/app');
    await new Promise((resolve) => {
      servidorApi = app.listen(0, '127.0.0.1', () => {
        baseUrl = `http://127.0.0.1:${servidorApi.address().port}`;
        resolve();
      });
    });
  });

  after(() => {
    for (const res of respuestasPendientes) res.destroy();
    servidorApi?.close();
    servidorHacienda.closeAllConnections();
    servidorHacienda.close();
  });

  beforeEach(() => {
    db.exec('DELETE FROM cola_reintentos; DELETE FROM contingencia_documentos; DELETE FROM contingencias; DELETE FROM eventos; DELETE FROM dtes; DELETE FROM correlativos; DELETE FROM idempotency_keys;');
    manejadores = { auth: [], firmar: [], recepcion: [], consulta: [], anulacion: [] };
    llamadas = [];
    authService.invalidar();
  });

  test('camino feliz: autentica, firma y transmite con el contrato del Manual Técnico', async () => {
    const { status, body } = await emitir();
    assert.equal(status, 201, JSON.stringify(body));
    assert.equal(body.estado, 'TRANSMITIDO');
    assert.equal(body.selloRecepcion, SELLO);

    const [auth] = llamadasA('auth');
    assert.match(auth.headers['content-type'], /application\/x-www-form-urlencoded/);
    assert.ok(auth.headers['user-agent']);
    assert.equal(auth.cuerpo.user, NIT);
    assert.equal(auth.cuerpo.pwd, process.env.MH_PASSWORD_API);

    const [firma] = llamadasA('firmar');
    assert.equal(firma.cuerpo.nit, NIT);
    assert.equal(firma.cuerpo.activo, true);
    assert.equal(firma.cuerpo.dteJson.identificacion.codigoGeneracion, body.codigoGeneracion);

    const [recepcion] = llamadasA('recepcion');
    assert.equal(recepcion.headers.authorization, TOKEN, 'el token ya trae el prefijo Bearer y no se duplica');
    assert.ok(recepcion.headers['user-agent']);
    assert.equal(recepcion.cuerpo.ambiente, '00');
    assert.ok(Number.isInteger(recepcion.cuerpo.idEnvio) && recepcion.cuerpo.idEnvio <= 2147483647);
    assert.equal(recepcion.cuerpo.version, firma.cuerpo.dteJson.identificacion.version);
    assert.equal(recepcion.cuerpo.tipoDte, '01');
    assert.equal(recepcion.cuerpo.documento, JWS);
    assert.equal(recepcion.cuerpo.codigoGeneracion, body.codigoGeneracion);
  });

  test('un RECHAZADO con HTTP 400 es definitivo: no se reintenta ni pasa a contingencia', async () => {
    programar('recepcion', json(400, {
      version: 2,
      ambiente: '00',
      estado: 'RECHAZADO',
      codigoMsg: '020',
      descripcionMsg: 'CAMPO resumen.totalPagar NO CUADRA',
      observaciones: ['Revise los totales'],
    }));

    const { status, body } = await emitir();
    assert.equal(status, 200);
    assert.equal(body.estado, 'RECHAZADO');
    assert.equal(body.respuestaHacienda.descripcionMsg, 'CAMPO resumen.totalPagar NO CUADRA');

    await retryQueue.procesarCola();
    assert.equal(llamadasA('recepcion').length, 1);
    assert.equal(llamadasA('consulta').length, 0);
    assert.equal(leerDte(body.codigoGeneracion).estado, 'RECHAZADO');
  });

  test('"ya existe" (004) consulta el mismo código y recupera el sello sin reenviar', async () => {
    programar('recepcion', json(400, {
      estado: 'RECHAZADO',
      codigoMsg: '004',
      descripcionMsg: '[identificacion.codigoGeneracion] YA EXISTE UN REGISTRO CON ESE VALOR',
    }));
    programar('consulta', (llamada, res) => json(200, {
      estado: 'PROCESADO',
      codigoGeneracion: llamada.cuerpo.codigoGeneracion,
      selloRecibido: SELLO,
    })(llamada, res));

    const { status, body } = await emitir();
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');

    await retryQueue.procesarCola();
    const [consulta] = llamadasA('consulta');
    assert.deepEqual(consulta.cuerpo, { nitEmisor: NIT, tdte: '01', codigoGeneracion: body.codigoGeneracion });
    const dte = leerDte(body.codigoGeneracion);
    assert.equal(dte.estado, 'TRANSMITIDO');
    assert.equal(dte.sello_recepcion, SELLO);
    assert.equal(llamadasA('recepcion').length, 1);
  });

  test('sin respuesta: consulta → "no existe" → 2 reenvíos → contingencia (Manual Técnico 3.3)', async () => {
    programar('recepcion', colgar(), colgar(), colgar());
    programar('consulta', json(404, {}), json(200, { codigoMsg: '014', descripcionMsg: 'NO EXISTE EL DOCUMENTO' }), json(404));

    const { status, body } = await emitir();
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');

    // consulta → reenvío → consulta → reenvío → consulta (agotado) → contingencia
    for (let paso = 0; paso < 5; paso++) await retryQueue.procesarCola();

    const envios = llamadasA('recepcion');
    assert.equal(envios.length, 3, 'envío original + 2 reenvíos');
    assert.ok(envios.every((envio) => envio.cuerpo.codigoGeneracion === body.codigoGeneracion), 'siempre el mismo documento');
    assert.equal(new Set(envios.map((envio) => envio.cuerpo.idEnvio)).size, 3, 'cada envío lleva un idEnvio distinto');
    assert.equal(llamadasA('consulta').length, 3);
    assert.equal(leerDte(body.codigoGeneracion).estado, 'CONTINGENCIA');
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cola_reintentos').get().n, 0);
  });

  test('errores 5xx también en la consulta: agota los intentos y pasa a contingencia', async () => {
    programar('recepcion', json(503, { message: 'Service Unavailable' }));
    programar('consulta', json(503, {}), json(502, {}), json(504, {}));

    const { status, body } = await emitir();
    assert.equal(status, 202);
    assert.equal(body.estado, 'PENDIENTE_RECONCILIACION');

    for (let intento = 0; intento < 3; intento++) {
      adelantarCola();
      await retryQueue.procesarCola();
    }
    assert.equal(llamadasA('consulta').length, 3);
    assert.equal(llamadasA('recepcion').length, 1, 'sin confirmar que no llegó, no se reenvía');
    assert.equal(leerDte(body.codigoGeneracion).estado, 'CONTINGENCIA');
  });

  test('un 401 en la recepción renueva el token y reintenta una sola vez', async () => {
    programar('recepcion', json(401, {}));
    const { status, body } = await emitir();
    assert.equal(status, 201, JSON.stringify(body));
    assert.equal(llamadasA('auth').length, 2);
    assert.equal(llamadasA('recepcion').length, 2);
  });

  test('credenciales rechazadas (HTTP 200 con status ERROR): 502 de configuración y reanudación sin volver a firmar', async () => {
    programar('auth', json(200, { status: 'ERROR', message: 'Usuario o clave incorrectos' }));

    const clave = 'stub-credenciales';
    const r1 = await emitir(FACTURA, clave);
    assert.equal(r1.status, 502);
    assert.equal(r1.body.code, 'HACIENDA_AUTH_CONFIGURATION_ERROR');
    assert.equal(llamadasA('recepcion').length, 0);
    assert.equal(leerDte(r1.body.codigoGeneracion).estado, 'FIRMADO');

    const r2 = await emitir(FACTURA, clave);
    assert.equal(r2.status, 201, JSON.stringify(r2.body));
    assert.equal(r2.body.codigoGeneracion, r1.body.codigoGeneracion);
    assert.equal(llamadasA('firmar').length, 1);
  });

  test('invalidación por HTTP: un RECHAZADO (400) no invalida; PROCESADO con sello sí', async () => {
    const { body: emitido } = await emitir();
    const anular = async (clave) => {
      const res = await fetch(`${baseUrl}/api/dte/${emitido.codigoGeneracion}/anular`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer clave-de-prueba-para-tests', 'Idempotency-Key': clave },
        body: JSON.stringify({
          motivo: {
            tipoAnulacion: 2,
            responsable: { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' },
            solicitante: { nombre: 'Juan Pérez', tipoDocumento: '13', numeroDocumento: '01234567-8' },
          },
        }),
      });
      return { status: res.status, body: await res.json() };
    };

    programar('anulacion', json(400, { estado: 'RECHAZADO', codigoMsg: '020', descripcionMsg: 'FECHA DEL EVENTO FUERA DE PLAZO' }));
    const rechazo = await anular('stub-anular-rechazo');
    assert.equal(rechazo.status, 422);
    assert.equal(rechazo.body.code, 'INVALIDATION_REJECTED');
    assert.equal(leerDte(emitido.codigoGeneracion).estado, 'TRANSMITIDO');

    const aceptado = await anular('stub-anular-ok');
    assert.equal(aceptado.status, 200, JSON.stringify(aceptado.body));
    assert.equal(aceptado.body.selloRecepcionEvento, SELLO_EVENTO);
    assert.equal(leerDte(emitido.codigoGeneracion).estado, 'INVALIDADO');

    const envios = llamadasA('anulacion');
    assert.equal(envios.length, 2);
    assert.equal(envios[1].cuerpo.ambiente, '00');
    assert.equal(envios[1].cuerpo.version, 3);
    assert.equal(envios[1].cuerpo.documento, JWS);
    assert.ok(Number.isInteger(envios[1].cuerpo.idEnvio));
    assert.notEqual(envios[0].cuerpo.idEnvio, envios[1].cuerpo.idEnvio);
    const evento = llamadasA('firmar').at(-1).cuerpo.dteJson;
    assert.equal(evento.documento.codigoGeneracion, emitido.codigoGeneracion);
    assert.equal(evento.documento.codigoGeneracionR, null);
  });

  test('un error de configuración del firmador (809) se informa con su código', async () => {
    programar('firmar', json(200, { status: 'ERROR', body: { codigo: '809', mensaje: ['El NIT es requerido'] } }));
    const { status, body } = await emitir();
    assert.equal(status, 502);
    assert.equal(body.code, 'FIRMADOR_CONFIGURATION_ERROR');
    assert.match(body.detalle, /809/);
    assert.equal(llamadasA('recepcion').length, 0);
  });
});

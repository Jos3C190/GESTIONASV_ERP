/**
 * Tests de integración de retryQueue.js contra una base SQLite real
 * (en memoria). Requiere las dependencias reales instaladas (`npm install`).
 *
 * Política del Manual Técnico v2.0 (3.3): sin respuesta se CONSULTA el mismo
 * código antes de reenviar; si Hacienda confirma que no lo recibió se
 * reenvía (máximo 2 veces) y, agotado eso, el documento pasa a contingencia.
 */
const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');

// Reintentos rápidos para que el test no tarde: 2 intentos máximo, 30ms base.
process.env.RETRY_MAX_ATTEMPTS = '2';
process.env.RETRY_BASE_DELAY_MS = '30';
require('../_setup');

const { db } = require('../../src/db');
const retryQueue = require('../../src/services/retryQueue');
const haciendaClient = require('../../src/services/haciendaClient');
const firmadorClient = require('../../src/services/firmadorClient');
const { construirFactura } = require('../../src/services/dteBuilder');
const { AuthError } = require('../../src/services/authService');

const SELLO = 'SELLO-FALSO-123'.padEnd(40, 'X');
const NO_EXISTE = { httpStatus: 404, data: null };

/** Factura real (schema oficial) para que la conversión a contingencia pueda validarse. */
function insertarDte(codigoGeneracion, estado = 'PENDIENTE_REINTENTO') {
  const { dte, numeroControl } = construirFactura({
    receptor: null,
    items: [{ descripcion: 'Servicio', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
  });
  dte.identificacion.codigoGeneracion = codigoGeneracion;
  db.prepare(
    `INSERT INTO dtes (codigo_generacion, numero_control, tipo_dte, estado, payload_json, documento_firmado)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).run(codigoGeneracion, numeroControl, '01', estado, JSON.stringify(dte), 'JWS_FIRMADO_FALSO');
}

function ventanasActivas() {
  return db.prepare(`SELECT * FROM contingencias WHERE estado = 'ACTIVA'`).all();
}

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function leerCola(codigoGeneracion) {
  return db.prepare('SELECT * FROM cola_reintentos WHERE codigo_generacion = ?').all(codigoGeneracion);
}

/** Vence el backoff programado sin esperar en tiempo real. */
function adelantarCola() {
  db.prepare(`UPDATE cola_reintentos SET proximo_intento = datetime('now', '-1 second')`).run();
}

function timeout() {
  return new haciendaClient.HaciendaError('Hacienda no respondió (ECONNABORTED)', { tipo: 'RED' });
}

describe('retryQueue.js (integración con SQLite real)', () => {
  beforeEach(() => {
    db.exec(`DELETE FROM cola_reintentos; DELETE FROM contingencia_documentos; DELETE FROM contingencias;
      DELETE FROM eventos; DELETE FROM dtes; DELETE FROM correlativos;`);
    firmadorClient.firmarDocumento = async () => 'JWS.CONTINGENCIA';
  });

  test('procesarCola reenvía un documento confirmado como no recibido y limpia la cola', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000001';
    insertarDte(codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    let envio;
    haciendaClient.transmitirDte = async (datos) => {
      envio = datos;
      return { estado: 'PROCESADO', selloRecibido: SELLO };
    };

    await retryQueue.procesarCola();

    const dte = leerDte(codigoGeneracion);
    assert.equal(dte.estado, 'TRANSMITIDO');
    assert.equal(dte.sello_recepcion, SELLO);
    assert.equal(leerCola(codigoGeneracion).length, 0, 'la cola debe quedar vacía tras un envío exitoso');
    // idEnvio es un entero secuencial que cabe en un Integer de 32 bits.
    assert.ok(Number.isInteger(envio.idEnvio) && envio.idEnvio > 0 && envio.idEnvio <= 2147483647);
    assert.equal(envio.version, 2, 'versión del schema de la Factura (fe-f-v2)');
    assert.equal(envio.codigoGeneracion, codigoGeneracion);
  });

  test('procesarCola reconcilia un DTE ambiguo consultando el mismo código', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000005';
    insertarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION');
    retryQueue.encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');

    let consultas = 0;
    haciendaClient.transmitirDte = async () => assert.fail('no debe reenviar un documento sin consultar antes');
    haciendaClient.consultarDte = async ({ codigoGeneracion: consultado }) => {
      consultas++;
      assert.equal(consultado, codigoGeneracion);
      return { httpStatus: 200, data: { estado: 'PROCESADO', selloRecibido: 'SELLO-RECONCILIADO-005'.padEnd(40, 'X') } };
    };

    await retryQueue.procesarCola();

    const dte = leerDte(codigoGeneracion);
    assert.equal(consultas, 1);
    assert.equal(dte.estado, 'TRANSMITIDO');
    assert.equal(dte.sello_recepcion, 'SELLO-RECONCILIADO-005'.padEnd(40, 'X'));
    assert.equal(leerCola(codigoGeneracion).length, 0);
  });

  test('una reconciliación que sigue sin conclusión termina en RECONCILIACION, no en CONTINGENCIA', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000006';
    insertarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION');
    retryQueue.encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');

    haciendaClient.consultarDte = async () => ({ httpStatus: 200, data: { estado: 'PROCESADO' } });

    await retryQueue.procesarCola();
    adelantarCola();
    await retryQueue.procesarCola();

    assert.equal(leerDte(codigoGeneracion).estado, 'RECONCILIACION');
    assert.equal(leerCola(codigoGeneracion).length, 0);
  });

  test('si el reenvío no obtiene respuesta, consulta antes de volver a enviar', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000002';
    insertarDte(codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    haciendaClient.transmitirDte = async () => {
      throw timeout();
    };

    await retryQueue.procesarCola();

    assert.equal(leerDte(codigoGeneracion).estado, 'PENDIENTE_RECONCILIACION', 'el documento pudo haber llegado: no se reenvía a ciegas');
    const [item] = leerCola(codigoGeneracion);
    assert.equal(item.accion, 'CONSULTAR');
    assert.equal(item.motivo, 'SIN_RESPUESTA');
    assert.equal(item.intentos, 0);
  });

  test('ciclo completo: sin respuesta → consulta "no existe" → 2 reenvíos → contingencia', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000003';
    insertarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION');
    retryQueue.encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');

    const idsEnvio = [];
    haciendaClient.transmitirDte = async ({ idEnvio }) => {
      idsEnvio.push(idEnvio);
      throw timeout();
    };
    haciendaClient.consultarDte = async () => NO_EXISTE;

    // consulta → reenvío 1 → consulta → reenvío 2 → consulta → contingencia
    for (let paso = 0; paso < 4; paso++) await retryQueue.procesarCola();
    assert.equal(leerDte(codigoGeneracion).estado, 'PENDIENTE_RECONCILIACION');
    await retryQueue.procesarCola();

    const dte = leerDte(codigoGeneracion);
    assert.equal(idsEnvio.length, 2, 'máximo 2 reenvíos (Manual Técnico 3.3)');
    assert.notEqual(idsEnvio[0], idsEnvio[1], 'cada envío usa un idEnvio nuevo');
    assert.equal(dte.estado, 'CONTINGENCIA');
    assert.equal(leerCola(codigoGeneracion).length, 0, 'el ítem debe salir de la cola al pasar a contingencia');

    // Manual Funcional VIII: el documento pasa a modelo diferido con el tipo de la ventana y se vuelve a firmar.
    const payload = JSON.parse(dte.payload_json);
    assert.equal(payload.identificacion.tipoModelo, 2);
    assert.equal(payload.identificacion.tipoOperacion, 2);
    assert.equal(payload.identificacion.tipoContingencia, 1, 'Hacienda respondió la consulta pero no recibió el documento');
    assert.equal(payload.identificacion.codigoGeneracion, codigoGeneracion);
    assert.equal(dte.documento_firmado, 'JWS.CONTINGENCIA');
    assert.equal(JSON.parse(dte.payload_original_json).identificacion.tipoModelo, 1, 'se conserva la versión original');
    const [ventana] = ventanasActivas();
    assert.equal(ventana.tipo_contingencia, 1);
    assert.equal(db.prepare('SELECT contingencia_id FROM contingencia_documentos WHERE codigo_generacion = ?').get(codigoGeneracion).contingencia_id, ventana.id);
  });

  test('si Hacienda tampoco responde a la consulta, agota los intentos y pasa a CONTINGENCIA', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000007';
    insertarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION');
    retryQueue.encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');

    haciendaClient.consultarDte = async () => {
      throw new haciendaClient.HaciendaError('Error del servidor de Hacienda (503)', { tipo: 'SERVIDOR', httpStatus: 503 });
    };

    // RETRY_MAX_ATTEMPTS=2: la primera consulta reprograma con backoff, la segunda agota.
    await retryQueue.procesarCola();
    const [item] = leerCola(codigoGeneracion);
    assert.equal(item.intentos, 1);
    assert.match(item.ultimo_error, /503/);
    assert.equal(leerDte(codigoGeneracion).estado, 'PENDIENTE_RECONCILIACION', 'no debe pasar a contingencia en el primer fallo');

    adelantarCola();
    await retryQueue.procesarCola();
    assert.equal(leerDte(codigoGeneracion).estado, 'CONTINGENCIA');
    assert.equal(leerCola(codigoGeneracion).length, 0);
    assert.equal(ventanasActivas().length, 1, 'se abre una sola ventana de contingencia');
  });

  test('un documento ya informado en un evento con sello no abre otra contingencia', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-00000000000D';
    insertarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION');
    const { lastInsertRowid } = db.prepare(
      `INSERT INTO contingencias (estado, tipo_contingencia, inicio, fin, evento_sello, evento_sello_en)
       VALUES ('REPORTADA', 1, '2026-10-10T10:00:00.000Z', '2026-10-10T11:00:00.000Z', 'SELLO', '2026-10-10T12:00:00.000Z')`
    ).run();
    db.prepare('INSERT INTO contingencia_documentos (contingencia_id, codigo_generacion) VALUES (?, ?)').run(lastInsertRowid, codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');
    haciendaClient.consultarDte = async () => {
      throw timeout();
    };

    await retryQueue.procesarCola();
    adelantarCola();
    await retryQueue.procesarCola();

    assert.equal(leerDte(codigoGeneracion).estado, 'CONTINGENCIA_REPORTADA');
    assert.equal(ventanasActivas().length, 0);
    const [item] = leerCola(codigoGeneracion);
    assert.equal(item.accion, 'TRANSMITIR', 'se sigue intentando dentro del plazo de 72 h');
  });

  test('un RECHAZADO (HTTP 400) en el reenvío es definitivo y limpia la cola', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000008';
    insertarDte(codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    // haciendaClient devuelve el cuerpo del 400 en vez de lanzar.
    haciendaClient.transmitirDte = async () => ({ estado: 'RECHAZADO', codigoMsg: '020', descripcionMsg: 'Total no cuadra', observaciones: ['Campo resumen.totalPagar'] });

    await retryQueue.procesarCola();

    const dte = leerDte(codigoGeneracion);
    assert.equal(dte.estado, 'RECHAZADO');
    assert.match(dte.observaciones, /Total no cuadra/);
    assert.equal(leerCola(codigoGeneracion).length, 0);
  });

  test('"ya existe" (004) se resuelve consultando el mismo código y recupera el sello', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000009';
    insertarDte(codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    haciendaClient.transmitirDte = async () => ({
      estado: 'RECHAZADO',
      codigoMsg: '004',
      descripcionMsg: '[identificacion.codigoGeneracion] YA EXISTE UN REGISTRO CON ESE VALOR',
    });
    haciendaClient.consultarDte = async () => ({ httpStatus: 200, data: { estado: 'PROCESADO', selloRecibido: SELLO } });

    await retryQueue.procesarCola();
    assert.equal(leerDte(codigoGeneracion).estado, 'PENDIENTE_RECONCILIACION');
    assert.equal(leerCola(codigoGeneracion)[0].motivo, 'DUPLICADO');

    await retryQueue.procesarCola();
    const dte = leerDte(codigoGeneracion);
    assert.equal(dte.estado, 'TRANSMITIDO');
    assert.equal(dte.sello_recepcion, SELLO);
  });

  test('"ya existe" sobre un código que Hacienda no tiene es un rechazo, no un reenvío', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-00000000000A';
    insertarDte(codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    let envios = 0;
    haciendaClient.transmitirDte = async () => {
      envios++;
      return { estado: 'RECHAZADO', codigoMsg: '004', descripcionMsg: '[identificacion.numeroControl] YA EXISTE UN REGISTRO CON ESE VALOR' };
    };
    haciendaClient.consultarDte = async () => NO_EXISTE;

    await retryQueue.procesarCola();
    await retryQueue.procesarCola();

    const dte = leerDte(codigoGeneracion);
    assert.equal(envios, 1);
    assert.equal(dte.estado, 'RECHAZADO');
    assert.match(dte.observaciones, /numeroControl/);
    assert.equal(leerCola(codigoGeneracion).length, 0);
  });

  test('credenciales del API rechazadas: conserva la acción con backoff y no abre contingencia', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-00000000000B';
    insertarDte(codigoGeneracion);
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    haciendaClient.transmitirDte = async () => {
      throw new AuthError('Hacienda rechazó la autenticación: usuario o clave incorrectos', { credenciales: true });
    };

    await retryQueue.procesarCola();
    const [item] = leerCola(codigoGeneracion);
    assert.equal(item.accion, 'TRANSMITIR');
    assert.equal(item.intentos, 1);
    assert.equal(leerDte(codigoGeneracion).estado, 'PENDIENTE_REINTENTO');

    adelantarCola();
    await retryQueue.procesarCola();
    const dte = leerDte(codigoGeneracion);
    assert.equal(dte.estado, 'RECONCILIACION');
    assert.match(dte.observaciones, /CONFIGURACION/);
    assert.equal(leerCola(codigoGeneracion).length, 0);
  });

  test('encolar() rechaza un codigo_generacion que no existe en dtes (integridad referencial real)', async () => {
    assert.throws(() => retryQueue.encolar('CODIGO-QUE-NO-EXISTE-EN-DTES', 'TRANSMITIR'), /FOREIGN KEY/);
  });

  test('procesarCola no toca ítems cuyo proximo_intento todavía no vence', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-000000000004';
    insertarDte(codigoGeneracion);
    db.prepare(
      `INSERT INTO cola_reintentos (codigo_generacion, accion, proximo_intento) VALUES (?, 'TRANSMITIR', datetime('now', '+1 hour'))`
    ).run(codigoGeneracion);

    let llamadas = 0;
    haciendaClient.transmitirDte = async () => {
      llamadas++;
      return { estado: 'PROCESADO', selloRecibido: 'NO-DEBERIA-LLEGAR' };
    };

    await retryQueue.procesarCola();
    assert.equal(llamadas, 0, 'no debe procesar un ítem programado para el futuro');
  });

  test('descarta acciones sobre documentos que ya no están pendientes', async () => {
    const codigoGeneracion = 'AAAAAAAA-0000-0000-0000-00000000000C';
    insertarDte(codigoGeneracion, 'TRANSMITIDO');
    retryQueue.encolar(codigoGeneracion, 'TRANSMITIR');

    haciendaClient.transmitirDte = async () => assert.fail('no debe reenviar un documento ya transmitido');

    await retryQueue.procesarCola();
    assert.equal(leerCola(codigoGeneracion).length, 0);
    assert.equal(leerDte(codigoGeneracion).estado, 'TRANSMITIDO');
  });
});

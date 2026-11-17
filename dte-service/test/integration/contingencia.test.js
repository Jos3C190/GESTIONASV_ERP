/**
 * Ciclo de contingencia (Manual Funcional VIII) contra la API real con SQLite
 * en memoria; solo se reemplazan las llamadas de red al firmador y a Hacienda.
 *
 * Momento 1: los documentos se generan en modelo diferido.
 * Momento 2: el Evento de Contingencia exige RECIBIDO con sello.
 * Momento 3: los documentos informados se transmiten sin cambiar sus campos.
 */
const { test, describe, before, beforeEach, after } = require('node:test');
const assert = require('node:assert/strict');

process.env.DTE_ALLOW_FORCED_CONTINGENCY = 'true';
process.env.MH_RESPONSABLE_NOMBRE = 'Responsable Establecimiento';
process.env.MH_RESPONSABLE_TIPO_DOC = '13';
process.env.MH_RESPONSABLE_NUM_DOC = '01234567-8';
process.env.RETRY_MAX_ATTEMPTS = '2';
require('../_setup');

const { db, obtenerSiguienteCorrelativo } = require('../../src/db');
require('../../src/services/correlativoStore').usar(obtenerSiguienteCorrelativo);
const firmadorClient = require('../../src/services/firmadorClient');
const haciendaClient = require('../../src/services/haciendaClient');
const retryQueue = require('../../src/services/retryQueue');
const contingenciaService = require('../../src/services/contingenciaService');
const { usarReloj } = require('../../src/utils/fechaHoraSV');

const API_KEY = 'clave-de-prueba-para-tests';
const SELLO_DTE = 'SELLO-DTE'.padEnd(40, 'D');
const SELLO_EVENTO = 'SELLO-EVENTO-CONTINGENCIA'.padEnd(40, 'C');
const FACTURA = {
  receptor: null,
  items: [{ descripcion: 'Servicio de prueba', cantidad: 1, precioUni: 113, ventaGravada: 113 }],
  pago: { codigo: '05', montoPago: 113, referencia: 'TRANSFER-CONT', numPagoElectronico: null },
};

let server;
let baseUrl;
let secuencia = 0;

async function llamar(metodo, ruta, body) {
  const headers = { Authorization: `Bearer ${API_KEY}` };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (metodo === 'POST' && ruta.startsWith('/api/dte/') && !ruta.startsWith('/api/dte/contingencia')) {
    headers['Idempotency-Key'] = `contingencia-test-${++secuencia}`;
  }
  const res = await fetch(`${baseUrl}${ruta}`, { method: metodo, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, body: await res.json() };
}

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

describe('Contingencia de punta a punta', () => {
  before(async () => {
    const app = require('../../src/app');
    await new Promise((resolve) => {
      server = app.listen(0, () => {
        baseUrl = `http://127.0.0.1:${server.address().port}`;
        resolve();
      });
    });
  });

  after(() => {
    usarReloj(null);
    server?.close();
  });

  beforeEach(() => {
    db.exec(`DELETE FROM cola_reintentos; DELETE FROM contingencia_documentos; DELETE FROM contingencias;
      DELETE FROM eventos; DELETE FROM dtes; DELETE FROM correlativos; DELETE FROM idempotency_keys;`);
    contingenciaService._reiniciarSondeo();
    usarReloj(null);
    firmadorClient.firmarDocumento = async () => 'JWS.FIRMADO.CONTINGENCIA';
    haciendaClient.transmitirDte = async () => ({ estado: 'PROCESADO', selloRecibido: SELLO_DTE, fhProcesamiento: '10/10/2026 12:00:00' });
    haciendaClient.consultarDte = async () => ({ httpStatus: 404, data: null });
    haciendaClient.transmitirContingencia = async () => ({ estado: 'RECIBIDO', selloRecibido: SELLO_EVENTO, mensaje: 'EVENTO RECIBIDO' });
  });

  test('contingencia forzada: diferido → evento con sello → transmisión con los mismos campos', async () => {
    const forzada = await llamar('POST', '/api/dte/contingencia/forzar', { tipoContingencia: 5, motivoContingencia: 'Prueba de certificación de contingencia' });
    assert.equal(forzada.status, 201, JSON.stringify(forzada.body));
    assert.equal(forzada.body.estado, 'ACTIVA');
    assert.equal(forzada.body.forzada, true);

    let transmisiones = 0;
    haciendaClient.transmitirDte = async () => {
      transmisiones += 1;
      return { estado: 'PROCESADO', selloRecibido: SELLO_DTE };
    };
    const primera = await llamar('POST', '/api/dte/factura', FACTURA);
    const segunda = await llamar('POST', '/api/dte/factura', FACTURA);
    assert.equal(primera.status, 202);
    assert.equal(primera.body.estado, 'CONTINGENCIA');
    assert.equal(transmisiones, 0, 'en contingencia no se intenta transmitir');
    const payload = JSON.parse(leerDte(primera.body.codigoGeneracion).payload_json);
    assert.equal(payload.identificacion.tipoModelo, 2);
    assert.equal(payload.identificacion.tipoOperacion, 2);
    assert.equal(payload.identificacion.tipoContingencia, 5);
    assert.equal(payload.identificacion.motivoContin, 'Prueba de certificación de contingencia');

    let eventoEnviado;
    firmadorClient.firmarDocumento = async (documento) => {
      if (documento.detalleDTE) eventoEnviado = documento;
      return 'JWS.FIRMADO.CONTINGENCIA';
    };
    const cierre = await llamar('POST', `/api/dte/contingencia/${forzada.body.id}/cerrar`, {});
    assert.equal(cierre.status, 200, JSON.stringify(cierre.body));
    assert.equal(cierre.body.estado, 'REPORTADA');
    assert.equal(cierre.body.evento.selloRecepcion, SELLO_EVENTO);
    assert.ok(cierre.body.plazos.transmisionLimite, 'plazo de 72 h desde el sello del evento');
    assert.deepEqual(eventoEnviado.detalleDTE.map((item) => item.codigoGeneracion).sort(), [primera.body.codigoGeneracion, segunda.body.codigoGeneracion].sort());
    assert.equal(eventoEnviado.motivo.tipoContingencia, 5);
    assert.equal(eventoEnviado.motivo.motivoContingencia, 'Prueba de certificación de contingencia');
    assert.equal(eventoEnviado.emisor.nombreResponsable, 'Responsable Establecimiento');
    assert.equal(leerDte(primera.body.codigoGeneracion).estado, 'CONTINGENCIA_REPORTADA');

    // Momento 3: la cola transmite cada documento uno a uno.
    await retryQueue.procesarCola();
    assert.equal(transmisiones, 2);
    for (const { body } of [primera, segunda]) {
      const dte = leerDte(body.codigoGeneracion);
      assert.equal(dte.estado, 'TRANSMITIDO');
      assert.equal(dte.sello_recepcion, SELLO_DTE);
      assert.equal(JSON.parse(dte.payload_json).identificacion.tipoModelo, 2, 'los campos de contingencia no cambian al transmitir');
    }
    contingenciaService.completarVentanas();
    const estado = await llamar('GET', '/api/dte/contingencia');
    assert.equal(estado.body.ventanas.find((ventana) => ventana.id === forzada.body.id).estado, 'COMPLETADA');

    // Las emisiones posteriores vuelven al modelo previo.
    const normal = await llamar('POST', '/api/dte/factura', FACTURA);
    assert.equal(normal.status, 201);
    assert.equal(JSON.parse(leerDte(normal.body.codigoGeneracion).payload_json).identificacion.tipoModelo, 1);
  });

  test('un evento rechazado deja la ventana cerrada con el error y el reenvío crea otro evento', async () => {
    const { body: ventana } = await llamar('POST', '/api/dte/contingencia/forzar', { tipoContingencia: 1 });
    await llamar('POST', '/api/dte/factura', FACTURA);
    haciendaClient.transmitirContingencia = async () => ({ estado: 'RECHAZADO', descripcionMsg: 'PERIODO DE CONTINGENCIA INVÁLIDO' });

    const cierre = await llamar('POST', `/api/dte/contingencia/${ventana.id}/cerrar`, {});
    assert.equal(cierre.body.estado, 'CERRADA');
    assert.match(cierre.body.ultimoError, /PERIODO/);
    const primerEvento = cierre.body.evento.codigoGeneracion;
    assert.equal(cierre.body.evento.estado, 'RECHAZADO');

    haciendaClient.transmitirContingencia = async () => ({ estado: 'RECIBIDO', selloRecibido: SELLO_EVENTO });
    const reenvio = await llamar('POST', `/api/dte/contingencia/${ventana.id}/evento`, {});
    assert.equal(reenvio.body.estado, 'REPORTADA');
    assert.notEqual(reenvio.body.evento.codigoGeneracion, primerEvento);
  });

  test('sin responsable configurado ni enviado, el evento espera la acción del operador', async () => {
    const { body: ventana } = await llamar('POST', '/api/dte/contingencia/forzar', { tipoContingencia: 1 });
    await llamar('POST', '/api/dte/factura', FACTURA);
    contingenciaService.cerrar(ventana.id);
    await assert.rejects(contingenciaService.enviarEvento(ventana.id, { responsable: null }), /responsable/);
    const conResponsable = await llamar('POST', `/api/dte/contingencia/${ventana.id}/evento`, {
      responsable: { nombre: 'Otra Persona', tipoDocumento: '36', numeroDocumento: '06141804941035' },
    });
    assert.equal(conResponsable.body.estado, 'REPORTADA');
  });

  test('contingencia automática: el sondeo detecta la recuperación y restaura un DTE que Hacienda sí tenía', async () => {
    haciendaClient.transmitirDte = async () => {
      throw new haciendaClient.HaciendaError('Hacienda no respondió (ECONNABORTED)', { tipo: 'RED' });
    };
    haciendaClient.consultarDte = async () => {
      throw new haciendaClient.HaciendaError('Hacienda no respondió (ECONNABORTED)', { tipo: 'RED' });
    };
    const recibido = await llamar('POST', '/api/dte/factura', FACTURA);
    const perdido = await llamar('POST', '/api/dte/factura', FACTURA);
    assert.equal(recibido.body.estado, 'PENDIENTE_RECONCILIACION');

    // Agota la política de reintentos (RETRY_MAX_ATTEMPTS=2) sin respuesta de Hacienda.
    for (let intento = 0; intento < 2; intento++) {
      db.prepare(`UPDATE cola_reintentos SET proximo_intento = datetime('now', '-1 second')`).run();
      await retryQueue.procesarCola();
    }
    assert.equal(leerDte(recibido.body.codigoGeneracion).estado, 'CONTINGENCIA');
    const [activa] = (await llamar('GET', '/api/dte/contingencia')).body.ventanas;
    assert.equal(activa.estado, 'ACTIVA');
    assert.equal(activa.forzada, false);
    assert.equal(activa.documentos.total, 2);

    // Con la ventana activa, las nuevas emisiones nacen en diferido.
    const durante = await llamar('POST', '/api/dte/factura', FACTURA);
    assert.equal(durante.body.estado, 'CONTINGENCIA');

    // Hacienda vuelve: el sondeo cierra la ventana; en la conciliación previa al
    // evento Hacienda ya tenía uno de los documentos convertidos.
    haciendaClient.consultarDte = async ({ codigoGeneracion }) => (codigoGeneracion === recibido.body.codigoGeneracion
      ? { httpStatus: 200, data: { estado: 'PROCESADO', selloRecibido: SELLO_DTE, fhProcesamiento: '10/10/2026 10:01:00' } }
      : { httpStatus: 404, data: null });
    let detalleEvento;
    firmadorClient.firmarDocumento = async (documento) => {
      if (documento.detalleDTE) detalleEvento = documento.detalleDTE;
      return 'JWS.FIRMADO.CONTINGENCIA';
    };
    await contingenciaService.procesar();

    const restaurado = leerDte(recibido.body.codigoGeneracion);
    assert.equal(restaurado.estado, 'TRANSMITIDO');
    assert.equal(JSON.parse(restaurado.payload_json).identificacion.tipoModelo, 1, 'se restaura la versión que Hacienda recibió');
    assert.deepEqual(detalleEvento.map((item) => item.codigoGeneracion).sort(), [perdido.body.codigoGeneracion, durante.body.codigoGeneracion].sort());
    const [reportada] = (await llamar('GET', '/api/dte/contingencia')).body.ventanas;
    assert.equal(reportada.estado, 'REPORTADA');
    assert.equal(reportada.tipoContingencia, 1);
    assert.equal(reportada.plazos.eventoVencido, false);
  });

  test('la contingencia forzada está deshabilitada si no hay permiso explícito', async () => {
    const config = require('../../src/config');
    config.contingencia.forzadaPermitida = false;
    try {
      const { status, body } = await llamar('POST', '/api/dte/contingencia/forzar', { tipoContingencia: 1 });
      assert.equal(status, 403);
      assert.equal(body.code, 'CONTINGENCY_FORCE_DISABLED');
    } finally {
      config.contingencia.forzadaPermitida = true;
    }
  });
});

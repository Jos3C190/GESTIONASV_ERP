const { db, siguienteIdEnvio } = require('../db');
const config = require('../config');
const logger = require('../utils/logger');
const haciendaClient = require('./haciendaClient');
const { clasificarRespuestaDte, clasificarConsultaDte } = require('./haciendaResponse');
const contingenciaService = require('./contingenciaService');
const { AuthError } = require('./authService');
const issuerContext = require('./issuerContext');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { fechaDeProcesamiento } = require('../utils/plazosFiscales');

/**
 * Transmisión y reconciliación de DTE según la política de reintentos del
 * Manual Técnico v2.0 (sección 3.3):
 *   1. Si Hacienda no responde, se CONSULTA el estado antes de reenviar.
 *   2. Si no fue recibido, se reenvía, máximo 2 veces.
 *   3. Si aun así no se logra la recepción, se opera en contingencia.
 * Un RECHAZADO (HTTP 400) es definitivo; un "ya existe" (004) obliga a
 * consultar para recuperar el sello del documento ya recibido.
 *
 * Estados: FIRMADO → TRANSMITIDO | RECHAZADO | PENDIENTE_RECONCILIACION
 * (consulta pendiente) | PENDIENTE_REINTENTO (reenvío pendiente) |
 * RECONCILIACION (respuesta no concluyente, revisión manual) | CONTINGENCIA.
 */
const MAX_REENVIOS = 2;

function leerDte(codigoGeneracion) {
  return db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function actualizarDte(codigoGeneracion, estado, observaciones, selloRecepcion = null) {
  db.prepare(
    `UPDATE dtes SET estado = ?, observaciones = ?, sello_recepcion = COALESCE(?, sello_recepcion),
     actualizado_en = datetime('now') WHERE codigo_generacion = ?`
  ).run(estado, observaciones, selloRecepcion, codigoGeneracion);
}

/** Registra la fecha del sello (fhProcesamiento de Hacienda o, en su defecto, hoy en El Salvador). */
function registrarFechaSello(codigoGeneracion, respuesta) {
  const fecha = fechaDeProcesamiento(respuesta?.fhProcesamiento) || fechaHoraSV().fecha;
  db.prepare('UPDATE dtes SET fecha_sello = ? WHERE codigo_generacion = ?').run(fecha, codigoGeneracion);
}

function quitarDeCola(codigoGeneracion) {
  db.prepare('DELETE FROM cola_reintentos WHERE codigo_generacion = ?').run(codigoGeneracion);
}

/** Deja una única acción pendiente por documento (opcionalmente diferida). */
function encolar(codigoGeneracion, accion, motivo = null, retrasoSegundos = 0) {
  quitarDeCola(codigoGeneracion);
  db.prepare(
    `INSERT INTO cola_reintentos (codigo_generacion, accion, motivo, proximo_intento)
     VALUES (?, ?, ?, datetime('now', '+' || ? || ' seconds'))`
  ).run(codigoGeneracion, accion, motivo, Math.max(0, Math.round(retrasoSegundos)));
}

function aplicarRespuestaTransmision(codigoGeneracion, respuesta) {
  const clasificacion = clasificarRespuestaDte(respuesta);
  const observaciones = JSON.stringify(respuesta);

  if (clasificacion.resultado === 'ACEPTADO') {
    quitarDeCola(codigoGeneracion);
    actualizarDte(codigoGeneracion, 'TRANSMITIDO', observaciones, clasificacion.selloRecepcion);
    registrarFechaSello(codigoGeneracion, respuesta);
    return { estado: 'TRANSMITIDO', selloRecepcion: clasificacion.selloRecepcion, respuesta };
  }
  if (clasificacion.resultado === 'RECHAZADO') {
    quitarDeCola(codigoGeneracion);
    actualizarDte(codigoGeneracion, 'RECHAZADO', observaciones);
    logger.warn({ codigoGeneracion, codigoMsg: clasificacion.codigoMsg }, 'Hacienda rechazó el DTE');
    return { estado: 'RECHAZADO', respuesta };
  }
  if (clasificacion.resultado === 'DUPLICADO') {
    encolar(codigoGeneracion, 'CONSULTAR', 'DUPLICADO');
    actualizarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION', observaciones);
    return {
      estado: 'PENDIENTE_RECONCILIACION',
      respuesta,
      mensaje: 'Hacienda indicó que el documento ya existe; se consultará el mismo código para recuperar su sello.',
    };
  }
  encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');
  actualizarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION', JSON.stringify({ respuesta, motivo: clasificacion.motivo }));
  return {
    estado: 'PENDIENTE_RECONCILIACION',
    respuesta,
    mensaje: 'La respuesta de Hacienda no permite confirmar la aceptación; se consultará el mismo código antes de reenviar.',
  };
}

function aplicarFallaTransmision(codigoGeneracion, error, { desdeCola }) {
  if (error instanceof AuthError && error.credenciales) {
    // Credenciales del API rechazadas: el documento no salió. Desde la cola se
    // conserva la acción para reintentarla con backoff; en la emisión directa
    // queda FIRMADO y la misma Idempotency-Key lo reanuda al corregir la clave.
    if (desdeCola) return { reintentar: true, tipo: 'CONFIGURACION', error: error.message };
    quitarDeCola(codigoGeneracion);
    actualizarDte(codigoGeneracion, 'FIRMADO', JSON.stringify({ error: error.message }));
    return { estado: 'ERROR_CONFIGURACION', codigo: 'HACIENDA_AUTH_CONFIGURATION_ERROR', mensaje: error.message };
  }
  if (error instanceof haciendaClient.HaciendaError && !error.transitorio) {
    // 4xx sin respuesta semántica: reenviar la misma solicitud no cambia el resultado.
    quitarDeCola(codigoGeneracion);
    actualizarDte(codigoGeneracion, 'RECHAZADO', JSON.stringify({ httpStatus: error.httpStatus, respuesta: error.haciendaResponse, mensaje: error.message }));
    return { estado: 'RECHAZADO', respuesta: error.haciendaResponse ?? null };
  }
  // Sin respuesta: el documento pudo haber llegado; se consulta antes de reenviar.
  encolar(codigoGeneracion, 'CONSULTAR', 'SIN_RESPUESTA');
  actualizarDte(codigoGeneracion, 'PENDIENTE_RECONCILIACION', JSON.stringify({ error: error.message }));
  return {
    estado: 'PENDIENTE_RECONCILIACION',
    mensaje: 'Hacienda no respondió; se consultará el estado del documento antes de reenviarlo.',
  };
}

/**
 * Transmite un DTE ya firmado y aplica el resultado. `desdeCola` indica que
 * la llamada viene del worker de reintentos.
 */
async function transmitir(codigoGeneracion, { desdeCola = false } = {}) {
  const dte = leerDte(codigoGeneracion);
  if (!dte?.documento_firmado) throw new Error('El DTE no tiene documento firmado para transmitir');
  const payload = JSON.parse(dte.payload_json);
  try {
    const respuesta = await haciendaClient.transmitirDte({
      ambiente: issuerContext.actual().ambiente,
      idEnvio: siguienteIdEnvio(),
      version: payload.identificacion.version,
      tipoDte: dte.tipo_dte,
      documentoFirmado: dte.documento_firmado,
      codigoGeneracion,
    });
    return aplicarRespuestaTransmision(codigoGeneracion, respuesta);
  } catch (error) {
    return aplicarFallaTransmision(codigoGeneracion, error, { desdeCola });
  }
}

function normalizarConsulta(resultado) {
  if (resultado && typeof resultado === 'object' && 'httpStatus' in resultado && 'data' in resultado) return resultado;
  return { httpStatus: 200, data: resultado };
}

/**
 * Consulta el estado de un documento cuya recepción no está confirmada.
 * Devuelve el nuevo estado, o `{ reintentar, tipo }` cuando la consulta no
 * fue concluyente (la cola aplica el backoff y decide al agotar intentos).
 */
async function reconciliar(codigoGeneracion, motivo) {
  const dte = leerDte(codigoGeneracion);
  let consulta;
  try {
    consulta = clasificarConsultaDte(normalizarConsulta(await haciendaClient.consultarDte({
      nitEmisor: issuerContext.actual().nit,
      tdte: dte.tipo_dte,
      codigoGeneracion,
    })));
  } catch (error) {
    if (error instanceof AuthError && error.credenciales) {
      return { reintentar: true, tipo: 'CONFIGURACION', error: error.message };
    }
    const sinRespuesta = !(error instanceof haciendaClient.HaciendaError) || error.transitorio;
    return { reintentar: true, tipo: sinRespuesta ? 'SIN_RESPUESTA' : 'DESCONOCIDO', error: error.message };
  }

  if (consulta.resultado === 'ACEPTADO') {
    quitarDeCola(codigoGeneracion);
    actualizarDte(codigoGeneracion, 'TRANSMITIDO', JSON.stringify(consulta), consulta.selloRecepcion);
    registrarFechaSello(codigoGeneracion, consulta);
    logger.info({ codigoGeneracion }, 'DTE confirmado por consulta a Hacienda');
    return { estado: 'TRANSMITIDO', selloRecepcion: consulta.selloRecepcion };
  }
  if (consulta.resultado === 'RECHAZADO') {
    quitarDeCola(codigoGeneracion);
    actualizarDte(codigoGeneracion, 'RECHAZADO', JSON.stringify(consulta));
    return { estado: 'RECHAZADO' };
  }
  if (consulta.resultado === 'NO_ENCONTRADO') {
    if (motivo === 'DUPLICADO') {
      // Hacienda dijo "ya existe" pero no tiene este código: el valor repetido
      // es otro campo (p. ej. el número de control). Reenviar no lo corrige.
      quitarDeCola(codigoGeneracion);
      actualizarDte(codigoGeneracion, 'RECHAZADO', dte.observaciones);
      return { estado: 'RECHAZADO' };
    }
    if ((dte.reenvios ?? 0) < MAX_REENVIOS) {
      db.prepare(
        `UPDATE dtes SET reenvios = reenvios + 1, estado = 'PENDIENTE_REINTENTO', actualizado_en = datetime('now')
         WHERE codigo_generacion = ?`
      ).run(codigoGeneracion);
      encolar(codigoGeneracion, 'TRANSMITIR');
      return { estado: 'PENDIENTE_REINTENTO' };
    }
    quitarDeCola(codigoGeneracion);
    // Hacienda responde a la consulta pero no recibe el documento: falla del servicio de recepción (CAT-005 tipo 1).
    return contingenciaService.registrarFallaDeConectividad(codigoGeneracion, { reenvios: dte.reenvios, tipoContingencia: 1 });
  }
  return { reintentar: true, tipo: 'DESCONOCIDO', error: consulta.descripcionMsg || 'Consulta no concluyente' };
}

module.exports = { MAX_REENVIOS, encolar, quitarDeCola, transmitir, reconciliar, aplicarRespuestaTransmision };

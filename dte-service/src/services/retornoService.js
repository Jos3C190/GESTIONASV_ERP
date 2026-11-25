const crypto = require('node:crypto');
const { db, siguienteIdEnvio } = require('../db');
const logger = require('../utils/logger');
const manifest = require('../schemas/manifest');
const { validarEvento } = require('../validators/dteSchema');
const { sanitizarProfundo } = require('../utils/sanitizarDte');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { plazoInvalidacion } = require('../utils/plazosFiscales');
const { construirEventoRetorno, TIPO_EVENTO_RETORNO } = require('./eventoRetornoBuilder');
const { construirEventoInvalidacion } = require('./eventoInvalidacionBuilder');
const { asociarIdentidad } = require('./idempotency');
const issuerContext = require('./issuerContext');

/**
 * Evento de Retorno (V4d2 del ERP; Normativa 2.0, regla 13.3; Manual Funcional
 * v2.0, sección X) y su anulación.
 *
 * - El retorno se guarda en `eventos` (tipo RETORNO, dte_codigo_generacion = la
 *   factura) antes de firmarlo: un reintento con la misma Idempotency-Key reenvía
 *   el mismo evento.
 * - Transmisión: el Manual Técnico solo trae servicios propios para contingencia
 *   e invalidación; el retorno tiene código de generación y es el tipo 18 de
 *   CAT-002, así que va por recepción uno a uno con tipoDte "18". Por confirmar
 *   en la certificación (la URL es la de recepción, configurable).
 * - Emisor simulado: el mismo evento validado, con firma y marcador sintéticos,
 *   sin firmador ni Hacienda.
 * - Anulación: evento de invalidación tipo 2 que referencia el retorno, sin
 *   número de control ni reemplazo. Cuelga de la misma factura y apunta al retorno
 *   en evento_relacionado; al aceptarse, el retorno queda INVALIDADO.
 *
 * Estados del retorno: PENDIENTE | ERROR_FIRMA | FIRMADO | SIN_CONFIRMAR |
 * ACEPTADO | RECHAZADO | INVALIDADO (y SIMULADO | SIMULADO_INVALIDADO).
 */
const TIPO = 'RETORNO';
const VIGENTES = ['ACEPTADO', 'SIMULADO'];
const EN_CURSO = ['PENDIENTE', 'ERROR_FIRMA', 'FIRMADO', 'SIN_CONFIRMAR'];
const PREFIJO = 'SIMULATED-';
const PREFIJO_EVENTO = 'SIMULATED-EVT-';

function leerEvento(codigoGeneracion) {
  return db.prepare('SELECT * FROM eventos WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function actualizarEvento(codigoGeneracion, cambios) {
  const columnas = Object.keys(cambios);
  db.prepare(
    `UPDATE eventos SET ${columnas.map((columna) => `${columna} = ?`).join(', ')}, actualizado_en = datetime('now')
     WHERE codigo_generacion = ?`
  ).run(...columnas.map((columna) => cambios[columna]), codigoGeneracion);
}

function conflicto(status, error, code, extra = {}) {
  return { respuesta: { status, body: { error, code, ...extra } } };
}

function simulado() {
  return issuerContext.simulado();
}

function esFacturaSimulada(row) {
  return row?.modo_emision === 'SIMULATED' && typeof row.simulation_marker === 'string' && row.simulation_marker.startsWith(PREFIJO);
}

function base64url(valor) {
  return Buffer.from(valor).toString('base64url');
}

/** Firma sintética y marcador deterministas, como la invalidación simulada. */
function firmarSimulado(payload) {
  const digest = crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex').toUpperCase();
  const header = base64url(JSON.stringify({ alg: 'SIM', typ: 'JWT', simulation: true }));
  const cuerpo = base64url(JSON.stringify({ codGen: payload.identificacion.codigoGeneracion, digest }));
  return {
    documentoFirmado: `${header}.${cuerpo}.${base64url(`${PREFIJO}${digest}`)}`,
    simulationMarker: `${PREFIJO_EVENTO}${digest.slice(0, 32)}`,
  };
}

function respuestaEvento(evento, status, extra = {}) {
  const payload = JSON.parse(evento.payload_json);
  return {
    status,
    body: {
      codigoGeneracion: evento.codigo_generacion,
      codigoGeneracionEvento: evento.codigo_generacion,
      codigoGeneracionDte: evento.dte_codigo_generacion,
      tipoEvento: evento.tipo,
      estadoEvento: evento.estado,
      fechaEvento: payload.identificacion.fecEmi,
      ...(evento.modo_emision === 'SIMULATED' ? { issuanceMode: 'SIMULATED' } : {}),
      ...extra,
    },
  };
}

function respuestaHacienda(evento) {
  return evento.respuesta_json ? JSON.parse(evento.respuesta_json) : undefined;
}

/** Resultado final ya guardado de un retorno o de su anulación (null si sigue en curso). */
function resultadoPersistido(evento) {
  const anulacion = evento.tipo === 'INVALIDACION';
  const nombre = anulacion ? 'la anulación del evento de retorno' : 'el evento de retorno';
  if (evento.estado === 'ACEPTADO' || evento.estado === 'INVALIDADO') {
    return respuestaEvento(evento, 200, {
      estado: anulacion ? 'RETORNO_INVALIDADO' : 'ACEPTADO',
      selloRecepcionEvento: evento.sello_recepcion,
      respuestaHacienda: respuestaHacienda(evento),
    });
  }
  if (evento.estado === 'SIMULADO' || evento.estado === 'SIMULADO_INVALIDADO') {
    return respuestaEvento(evento, 200, {
      estado: anulacion ? 'RETORNO_INVALIDADO' : 'SIMULADO',
      simulationMarkerEvento: evento.simulation_marker,
    });
  }
  if (evento.estado === 'RECHAZADO') {
    return respuestaEvento(evento, 422, {
      error: `Hacienda rechazó ${nombre}`,
      code: anulacion ? 'RETURN_INVALIDATION_REJECTED' : 'RETURN_REJECTED',
      respuestaHacienda: respuestaHacienda(evento),
    });
  }
  return null;
}

// --- retorno -----------------------------------------------------------------------------------

/** Valida la solicitud contra la factura guardada y persiste el evento. */
function preparar({ row, items, contingencia = null, claveIdempotencia }) {
  const enSimulado = simulado();
  if (enSimulado ? !(row.estado === 'SIMULADO' && esFacturaSimulada(row)) : !(row.estado === 'TRANSMITIDO' && row.sello_recepcion)) {
    return conflicto(409, `Solo se aplica un retorno a una factura con sello (estado actual: ${row.estado})`, 'DTE_NOT_RETURNABLE');
  }
  const enCurso = db.prepare(
    `SELECT codigo_generacion FROM eventos
     WHERE dte_codigo_generacion = ? AND tipo = ? AND estado IN (${EN_CURSO.map(() => '?').join(', ')})`
  ).get(row.codigo_generacion, TIPO, ...EN_CURSO);
  if (enCurso) {
    return conflicto(409, 'Hay un evento de retorno sin confirmar para esta factura; reintenta con su misma Idempotency-Key',
      'RETURN_IN_PROGRESS', { codigoGeneracionEvento: enCurso.codigo_generacion });
  }

  let construido;
  try {
    construido = construirEventoRetorno({ dte: JSON.parse(row.payload_json), items, contingencia });
  } catch (error) {
    return conflicto(400, error.message, error.code || 'INVALID_RETURN_REQUEST');
  }
  const evento = sanitizarProfundo(construido.evento);
  const { valido, errores } = validarEvento('retorno', evento);
  if (!valido) {
    return conflicto(422, 'Evento de retorno inválido según el schema oficial', 'EVENT_SCHEMA_INVALID', { detalles: errores });
  }
  db.transaction(() => {
    db.prepare(
      `INSERT INTO eventos (codigo_generacion, tipo, dte_codigo_generacion, estado, payload_json, modo_emision)
       VALUES (?, ?, ?, 'PENDIENTE', ?, ?)`
    ).run(construido.codigoGeneracion, TIPO, row.codigo_generacion, JSON.stringify(evento), enSimulado ? 'SIMULATED' : row.modo_emision);
    asociarIdentidad(claveIdempotencia, construido.codigoGeneracion);
  })();
  return { evento: leerEvento(construido.codigoGeneracion) };
}

/** Emisor simulado: firma y marcador sintéticos. Repetirlo devuelve el resultado guardado. */
function aplicarSimulado(codigoGeneracion, { escenario = 'success' } = {}) {
  const evento = leerEvento(codigoGeneracion);
  const persistido = resultadoPersistido(evento);
  if (persistido) return persistido;
  if (escenario === 'rejected') {
    actualizarEvento(codigoGeneracion, {
      estado: 'RECHAZADO',
      respuesta_json: JSON.stringify({ escenario, codigoMsg: 'SIM-RECHAZO-RETORNO', descripcionMsg: 'Rechazo simulado del evento de retorno' }),
    });
    return resultadoPersistido(leerEvento(codigoGeneracion));
  }
  const { documentoFirmado, simulationMarker } = firmarSimulado(JSON.parse(evento.payload_json));
  actualizarEvento(codigoGeneracion, { estado: 'SIMULADO', documento_firmado: documentoFirmado, simulation_marker: simulationMarker });
  return resultadoPersistido(leerEvento(codigoGeneracion));
}

/** Firma, transmite y aplica la respuesta de Hacienda (recepción uno a uno, tipoDte 18). */
async function transmitir(codigoGeneracion, { anulacion = false } = {}) {
  // Carga perezosa: el modo simulado nunca toca el firmador ni Hacienda.
  const config = require('../config');
  const firmadorClient = require('./firmadorClient');
  const haciendaClient = require('./haciendaClient');
  const { clasificarRespuestaDte, clasificarRespuestaEvento, esDuplicado } = require('./haciendaResponse');
  const { AuthError } = require('./authService');

  let evento = leerEvento(codigoGeneracion);
  const persistido = resultadoPersistido(evento);
  if (persistido) return persistido;
  const nombre = anulacion ? 'la anulación del evento de retorno' : 'el evento de retorno';

  if (!evento.documento_firmado) {
    try {
      const documentoFirmado = await firmadorClient.firmarDocumento(JSON.parse(evento.payload_json));
      actualizarEvento(codigoGeneracion, { documento_firmado: documentoFirmado, estado: 'FIRMADO' });
    } catch (error) {
      actualizarEvento(codigoGeneracion, { estado: 'ERROR_FIRMA', respuesta_json: JSON.stringify({ error: error.message }) });
      return respuestaEvento(leerEvento(codigoGeneracion), 502, {
        error: `No se pudo firmar ${nombre}`,
        detalle: error.message,
        code: error.configuracion ? 'FIRMADOR_CONFIGURATION_ERROR' : 'RETURN_SIGNING_FAILED',
      });
    }
    evento = leerEvento(codigoGeneracion);
  }

  let respuesta;
  try {
    respuesta = anulacion
      ? await haciendaClient.anularDte({
        ambiente: config.ambiente,
        idEnvio: siguienteIdEnvio(),
        version: manifest.eventos.invalidacion.version,
        documentoFirmado: evento.documento_firmado,
      })
      : await haciendaClient.transmitirDte({
        ambiente: config.ambiente,
        idEnvio: siguienteIdEnvio(),
        version: manifest.eventos.retorno.version,
        tipoDte: TIPO_EVENTO_RETORNO,
        documentoFirmado: evento.documento_firmado,
        codigoGeneracion,
      });
  } catch (error) {
    if (error instanceof AuthError && error.credenciales) {
      return respuestaEvento(evento, 502, { error: error.message, code: 'HACIENDA_AUTH_CONFIGURATION_ERROR' });
    }
    if (error instanceof haciendaClient.HaciendaError && !error.transitorio) {
      actualizarEvento(codigoGeneracion, {
        estado: 'RECHAZADO',
        respuesta_json: JSON.stringify({ httpStatus: error.httpStatus, respuesta: error.haciendaResponse, mensaje: error.message }),
      });
      return resultadoPersistido(leerEvento(codigoGeneracion));
    }
    actualizarEvento(codigoGeneracion, { respuesta_json: JSON.stringify({ error: error.message }) });
    return respuestaEvento(leerEvento(codigoGeneracion), 502, {
      error: `Hacienda no respondió ${nombre}; reintenta con la misma Idempotency-Key`,
      code: 'RETURN_NO_RESPONSE',
    });
  }

  const clasificacion = anulacion
    ? clasificarRespuestaEvento(respuesta, { estadoAceptado: 'PROCESADO' })
    : clasificarRespuestaDte(respuesta);
  if (clasificacion.resultado === 'ACEPTADO') {
    db.transaction(() => {
      actualizarEvento(codigoGeneracion, { estado: 'ACEPTADO', sello_recepcion: clasificacion.selloRecepcion, respuesta_json: JSON.stringify(respuesta) });
      if (anulacion) actualizarEvento(evento.evento_relacionado, { estado: 'INVALIDADO' });
    })();
    logger.info({ evento: codigoGeneracion, anulacion }, 'Evento de retorno aceptado por Hacienda');
    return resultadoPersistido(leerEvento(codigoGeneracion));
  }
  if (clasificacion.resultado === 'DUPLICADO' || (clasificacion.resultado === 'RECHAZADO' && esDuplicado(respuesta))) {
    actualizarEvento(codigoGeneracion, { estado: 'CONCILIACION', respuesta_json: JSON.stringify(respuesta) });
    return respuestaEvento(leerEvento(codigoGeneracion), 409, {
      error: 'Hacienda indica que el evento ya existe; verifica su estado antes de actuar',
      code: 'RETURN_REQUIRES_RECONCILIATION',
      respuestaHacienda: respuesta,
    });
  }
  if (clasificacion.resultado === 'RECHAZADO') {
    actualizarEvento(codigoGeneracion, { estado: 'RECHAZADO', respuesta_json: JSON.stringify(respuesta) });
    return resultadoPersistido(leerEvento(codigoGeneracion));
  }
  actualizarEvento(codigoGeneracion, { estado: 'SIN_CONFIRMAR', respuesta_json: JSON.stringify(respuesta) });
  return respuestaEvento(leerEvento(codigoGeneracion), 502, {
    error: `Hacienda no confirmó ${nombre} (sin sello); reintenta con la misma Idempotency-Key`,
    code: 'RETURN_UNCONFIRMED',
    respuestaHacienda: respuesta,
  });
}

/** Aplica la solicitud ya preparada según el emisor (simulado o ante Hacienda). */
function procesar(codigoGeneracion, { escenario, anulacion = false } = {}) {
  if (simulado()) return anulacion ? aplicarAnulacionSimulada(codigoGeneracion) : aplicarSimulado(codigoGeneracion, { escenario });
  return transmitir(codigoGeneracion, { anulacion });
}

/** Archivo del evento (JSON firmado + sello o marcador) para entregar o archivar. */
function archivoEvento(evento) {
  if (!evento.documento_firmado) return null;
  if (['ACEPTADO', 'INVALIDADO'].includes(evento.estado) && evento.sello_recepcion) {
    return { ...JSON.parse(evento.payload_json), firmaElectronica: evento.documento_firmado, selloRecibido: evento.sello_recepcion };
  }
  if (['SIMULADO', 'SIMULADO_INVALIDADO'].includes(evento.estado) && evento.simulation_marker) {
    return { ...JSON.parse(evento.payload_json), firmaElectronica: evento.documento_firmado, selloRecibido: evento.simulation_marker };
  }
  return null;
}

// --- anulación del retorno ----------------------------------------------------------------------

function prepararAnulacion({ retorno, motivo, claveIdempotencia }) {
  const enSimulado = simulado();
  if (retorno.estado === 'INVALIDADO' || retorno.estado === 'SIMULADO_INVALIDADO') {
    return conflicto(409, 'El evento de retorno ya fue anulado', 'RETURN_ALREADY_INVALIDATED');
  }
  if (!VIGENTES.includes(retorno.estado) || (enSimulado !== (retorno.estado === 'SIMULADO'))) {
    return conflicto(409, `Solo se anula un evento de retorno vigente (estado actual: ${retorno.estado})`, 'RETURN_NOT_INVALIDATABLE');
  }
  const enCurso = db.prepare(
    `SELECT codigo_generacion FROM eventos WHERE evento_relacionado = ? AND tipo = 'INVALIDACION'
     AND estado IN (${EN_CURSO.map(() => '?').join(', ')})`
  ).get(retorno.codigo_generacion, ...EN_CURSO);
  if (enCurso) {
    return conflicto(409, 'Hay una anulación sin confirmar de este retorno; reintenta con su misma Idempotency-Key',
      'RETURN_INVALIDATION_IN_PROGRESS', { codigoGeneracionEvento: enCurso.codigo_generacion });
  }
  const payload = JSON.parse(retorno.payload_json);
  const { fecha: hoy } = fechaHoraSV();
  const plazo = plazoInvalidacion(TIPO_EVENTO_RETORNO, payload.identificacion.fecEmi);
  if (hoy > plazo.limite) {
    logger.warn({ retorno: retorno.codigo_generacion, limite: plazo.limite }, 'Anulación de retorno posiblemente fuera de plazo; Hacienda decide');
  }
  const factura = db.prepare('SELECT payload_json FROM dtes WHERE codigo_generacion = ?').get(retorno.dte_codigo_generacion);
  const emisorFactura = factura ? JSON.parse(factura.payload_json).emisor : {};
  const sello = enSimulado ? retorno.simulation_marker.slice(0, 40).padEnd(40, '0') : retorno.sello_recepcion;
  let construido;
  try {
    construido = construirEventoInvalidacion({
      dte: payload,
      selloRecibido: sello,
      motivo: { ...motivo, tipoAnulacion: 2 },
      codigoGeneracionReemplazo: null,
      contactoEmisor: { telefono: emisorFactura.telefono, correo: emisorFactura.correo },
    });
  } catch (error) {
    return conflicto(400, error.message, error.code || 'INVALID_INVALIDATION_REQUEST');
  }
  const evento = sanitizarProfundo(construido.evento);
  const { valido, errores } = validarEvento('invalidacion', evento);
  if (!valido) {
    return conflicto(422, 'Evento de invalidación inválido según el schema oficial', 'EVENT_SCHEMA_INVALID', { detalles: errores });
  }
  db.transaction(() => {
    db.prepare(
      `INSERT INTO eventos (codigo_generacion, tipo, dte_codigo_generacion, estado, payload_json, modo_emision, evento_relacionado)
       VALUES (?, 'INVALIDACION', ?, 'PENDIENTE', ?, ?, ?)`
    ).run(construido.codigoGeneracion, retorno.dte_codigo_generacion, JSON.stringify(evento), retorno.modo_emision, retorno.codigo_generacion);
    asociarIdentidad(claveIdempotencia, construido.codigoGeneracion);
  })();
  return { evento: leerEvento(construido.codigoGeneracion) };
}

function aplicarAnulacionSimulada(codigoGeneracion) {
  const evento = leerEvento(codigoGeneracion);
  const persistido = resultadoPersistido(evento);
  if (persistido) return persistido;
  const { documentoFirmado, simulationMarker } = firmarSimulado(JSON.parse(evento.payload_json));
  db.transaction(() => {
    actualizarEvento(codigoGeneracion, { estado: 'SIMULADO_INVALIDADO', documento_firmado: documentoFirmado, simulation_marker: simulationMarker });
    actualizarEvento(evento.evento_relacionado, { estado: 'SIMULADO_INVALIDADO' });
  })();
  return resultadoPersistido(leerEvento(codigoGeneracion));
}

module.exports = {
  TIPO,
  leerEvento,
  preparar,
  procesar,
  prepararAnulacion,
  archivoEvento,
  resultadoPersistido,
};

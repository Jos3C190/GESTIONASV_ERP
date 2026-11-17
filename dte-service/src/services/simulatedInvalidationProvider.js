const crypto = require('node:crypto');
const { db } = require('../db');
const { validarEvento } = require('../validators/dteSchema');
const { sanitizarProfundo } = require('../utils/sanitizarDte');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { plazoInvalidacion, fechaDelEventoInvalidacion, TIPOS_PLAZO_TRES_MESES } = require('../utils/plazosFiscales');
const { construirEventoInvalidacion, TIPOS_SIN_REEMPLAZO } = require('./eventoInvalidacionBuilder');
const { asociarIdentidad } = require('./idempotency');

/**
 * Invalidación SIMULADA (DEC-010, DTE_SIMULATION_FISCAL_EVENTS_PLAN.md §4).
 *
 * Construye y valida el mismo Evento de Invalidación que el flujo real, pero
 * nunca lo firma con el certificado ni lo transmite: este módulo no importa
 * firmadorClient, haciendaClient ni authService (lo verifica una prueba).
 * Solo opera sobre documentos SIMULADO de la base simulada y nunca escribe
 * sello_recepcion, el estado ACEPTADO ni INVALIDADO.
 *
 * Estados propios en SQLite: eventos.estado SIMULADO | RECHAZADO (escenario
 * invalidation-rejected) y dtes.estado SIMULADO_INVALIDADO.
 */

const PREFIJO = 'SIMULATED-';
const PREFIJO_EVENTO = 'SIMULATED-EVT-';

function base64url(valor) {
  return Buffer.from(valor).toString('base64url');
}

function leerEvento(codigoGeneracion) {
  return db.prepare('SELECT * FROM eventos WHERE codigo_generacion = ?').get(codigoGeneracion);
}

function esDocumentoSimulado(row) {
  return row?.modo_emision === 'SIMULATED'
    && typeof row.simulation_marker === 'string'
    && row.simulation_marker.startsWith(PREFIJO);
}

/**
 * El schema del evento exige que documento.selloRecibido tenga exactamente
 * 40 caracteres: se usan los primeros 40 del marcador del DTE, que conservan
 * el prefijo reservado y lo hacen inconfundible con un sello de Hacienda.
 */
function selloParaEvento(row) {
  return row.simulation_marker.slice(0, 40);
}

/** Fecha del evento y plazo informativo; los simulados no tienen fecha de sello. */
function vistaPrevia(row) {
  const dte = JSON.parse(row.payload_json);
  const tipoDte = dte.identificacion.tipoDte;
  const { fecha: hoy } = fechaHoraSV();
  const fechaReferencia = row.fecha_sello || dte.identificacion.fecEmi;
  const plazo = plazoInvalidacion(tipoDte, fechaReferencia);
  return {
    codigoGeneracion: row.codigo_generacion,
    tipoDte,
    fecEmi: dte.identificacion.fecEmi,
    fechaSello: fechaReferencia,
    fechaEvento: fechaDelEventoInvalidacion(tipoDte, dte.identificacion.fecEmi, hoy),
    plazo: { ...plazo, vencido: hoy > plazo.limite },
    reemplazoRequeridoEnTipos: TIPOS_SIN_REEMPLAZO.has(tipoDte) ? [] : [1, 3],
    issuanceMode: 'SIMULATED',
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
      estadoEvento: evento.estado,
      fechaEvento: payload.identificacion.fecEmi,
      issuanceMode: 'SIMULATED',
      ...extra,
    },
  };
}

function resultadoPersistido(evento) {
  if (evento.estado === 'SIMULADO') {
    return respuestaEvento(evento, 200, { estado: 'SIMULADO_INVALIDADO', simulationMarkerEvento: evento.simulation_marker });
  }
  if (evento.estado === 'RECHAZADO') {
    return respuestaEvento(evento, 422, {
      error: 'Rechazo simulado del evento de invalidación (escenario invalidation-rejected)',
      code: 'INVALIDATION_REJECTED',
      simulacion: evento.respuesta_json ? JSON.parse(evento.respuesta_json) : undefined,
    });
  }
  return null;
}

function conflicto(status, error, code, extra = {}) {
  return { respuesta: { status, body: { error, code, ...extra } } };
}

/**
 * Valida la solicitud y persiste el evento. Devuelve { evento } o
 * { respuesta } cuando no procede. Mismas reglas que el flujo real (tipos,
 * reemplazo, plazo y schema oficial), con documentos simulados.
 */
function preparar({ row, motivo, codigoGeneracionReemplazo, claveIdempotencia }) {
  if (row.estado === 'SIMULADO_INVALIDADO') {
    const previo = db.prepare(
      `SELECT codigo_generacion, simulation_marker FROM eventos
       WHERE dte_codigo_generacion = ? AND tipo = 'INVALIDACION' AND estado = 'SIMULADO'`
    ).get(row.codigo_generacion);
    return conflicto(409, 'El DTE simulado ya fue invalidado', 'DTE_ALREADY_INVALIDATED', {
      codigoGeneracionEvento: previo?.codigo_generacion ?? null,
      simulationMarkerEvento: previo?.simulation_marker ?? null,
    });
  }
  if (row.estado !== 'SIMULADO' || !esDocumentoSimulado(row)) {
    return conflicto(409, `Solo se invalida en simulación un DTE SIMULADO (estado actual: ${row.estado})`, 'DTE_NOT_INVALIDATABLE');
  }
  const enCurso = db.prepare(
    `SELECT codigo_generacion FROM eventos
     WHERE dte_codigo_generacion = ? AND tipo = 'INVALIDACION' AND estado = 'PENDIENTE'`
  ).get(row.codigo_generacion);
  if (enCurso) {
    return conflicto(409, 'Ya existe un evento de invalidación simulado sin terminar; reintenta con su misma Idempotency-Key',
      'INVALIDATION_IN_PROGRESS', { codigoGeneracionEvento: enCurso.codigo_generacion });
  }

  if (codigoGeneracionReemplazo) {
    const reemplazo = db.prepare('SELECT * FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracionReemplazo);
    if (!reemplazo || reemplazo.estado !== 'SIMULADO' || !esDocumentoSimulado(reemplazo)) {
      return conflicto(409, 'El documento de reemplazo debe ser un DTE SIMULADO de esta misma base', 'INVALIDATION_REPLACEMENT_NOT_READY');
    }
  }

  const dte = JSON.parse(row.payload_json);
  const previa = vistaPrevia(row);
  if (TIPOS_PLAZO_TRES_MESES.has(previa.tipoDte) && previa.plazo.vencido) {
    return conflicto(422, `El plazo para invalidar este documento venció el ${previa.plazo.limite}`, 'INVALIDATION_DEADLINE_EXCEEDED', { plazo: previa.plazo });
  }

  let construido;
  try {
    construido = construirEventoInvalidacion({ dte, selloRecibido: selloParaEvento(row), motivo, codigoGeneracionReemplazo });
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
      `INSERT INTO eventos (codigo_generacion, tipo, dte_codigo_generacion, estado, payload_json, modo_emision)
       VALUES (?, 'INVALIDACION', ?, 'PENDIENTE', ?, 'SIMULATED')`
    ).run(construido.codigoGeneracion, row.codigo_generacion, JSON.stringify(evento));
    asociarIdentidad(claveIdempotencia, construido.codigoGeneracion);
  })();
  return { evento: leerEvento(construido.codigoGeneracion) };
}

/** Firma sintética y marcador deterministas del evento, como emitirSimulado. */
function firmarSimulado(payload) {
  const digest = crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex').toUpperCase();
  const header = base64url(JSON.stringify({ alg: 'SIM', typ: 'JWT', simulation: true }));
  const cuerpo = base64url(JSON.stringify({ codGen: payload.identificacion.codigoGeneracion, digest }));
  return {
    documentoFirmado: `${header}.${cuerpo}.${base64url(`${PREFIJO}${digest}`)}`,
    simulationMarker: `${PREFIJO_EVENTO}${digest.slice(0, 32)}`,
  };
}

/** Aplica el escenario al evento preparado. Repetirlo devuelve el resultado guardado. */
function aplicar(codigoGeneracion, { escenario = 'success' } = {}) {
  const evento = leerEvento(codigoGeneracion);
  const persistido = resultadoPersistido(evento);
  if (persistido) return persistido;

  if (escenario === 'invalidation-rejected') {
    const simulacion = {
      escenario,
      codigoMsg: 'SIM-RECHAZO-INVALIDACION',
      descripcionMsg: 'Rechazo simulado: Hacienda no participó y el documento sigue vigente en la simulación',
    };
    db.prepare(
      `UPDATE eventos SET estado = 'RECHAZADO', respuesta_json = ?, actualizado_en = datetime('now') WHERE codigo_generacion = ?`
    ).run(JSON.stringify(simulacion), codigoGeneracion);
    return resultadoPersistido(leerEvento(codigoGeneracion));
  }

  const payload = JSON.parse(evento.payload_json);
  const { documentoFirmado, simulationMarker } = firmarSimulado(payload);
  db.transaction(() => {
    db.prepare(
      `UPDATE eventos SET estado = 'SIMULADO', documento_firmado = ?, simulation_marker = ?, actualizado_en = datetime('now')
       WHERE codigo_generacion = ?`
    ).run(documentoFirmado, simulationMarker, codigoGeneracion);
    db.prepare(
      `UPDATE dtes SET estado = 'SIMULADO_INVALIDADO', actualizado_en = datetime('now')
       WHERE codigo_generacion = ? AND estado = 'SIMULADO' AND modo_emision = 'SIMULATED'`
    ).run(evento.dte_codigo_generacion);
  })();
  return resultadoPersistido(leerEvento(codigoGeneracion));
}

/** Archivo del evento simulado: JSON con firma sintética y el marcador como selloRecibido. */
function archivoEvento(evento) {
  if (evento.estado !== 'SIMULADO' || !evento.documento_firmado || !evento.simulation_marker) return null;
  return { ...JSON.parse(evento.payload_json), firmaElectronica: evento.documento_firmado, selloRecibido: evento.simulation_marker };
}

module.exports = { leerEvento, esDocumentoSimulado, vistaPrevia, preparar, aplicar, archivoEvento, resultadoPersistido };

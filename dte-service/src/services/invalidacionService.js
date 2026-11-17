const { db, siguienteIdEnvio } = require('../db');
const config = require('../config');
const logger = require('../utils/logger');
const manifest = require('../schemas/manifest');
const { validarEvento } = require('../validators/dteSchema');
const { sanitizarProfundo } = require('../utils/sanitizarDte');
const { fechaHoraSV } = require('../utils/fechaHoraSV');
const { plazoInvalidacion, fechaDelEventoInvalidacion, TIPOS_PLAZO_TRES_MESES } = require('../utils/plazosFiscales');
const { construirEventoInvalidacion, TIPOS_SIN_REEMPLAZO } = require('./eventoInvalidacionBuilder');
const { asociarIdentidad } = require('./idempotency');
const firmadorClient = require('./firmadorClient');
const haciendaClient = require('./haciendaClient');
const { clasificarRespuestaEvento, esDuplicado } = require('./haciendaResponse');
const { AuthError } = require('./authService');

/**
 * Invalidación de un DTE recibido (Manual Funcional v2.0, VII). El evento se
 * persiste antes de firmarlo: si Hacienda no responde, la misma
 * Idempotency-Key reenvía el mismo evento (mismo código de generación) y el
 * DTE solo pasa a INVALIDADO cuando el evento obtiene PROCESADO con sello.
 */

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

/** Fecha del sello del DTE; en registros antiguos se aproxima con la fecha de emisión. */
function fechaSelloDe(row, dte) {
  return row.fecha_sello || dte.identificacion.fecEmi;
}

/** Fecha del evento, plazo de transmisión y reglas de reemplazo para un DTE. */
function vistaPrevia(row) {
  const dte = JSON.parse(row.payload_json);
  const tipoDte = dte.identificacion.tipoDte;
  const { fecha: hoy } = fechaHoraSV();
  const fechaSello = fechaSelloDe(row, dte);
  const plazo = plazoInvalidacion(tipoDte, fechaSello);
  return {
    codigoGeneracion: row.codigo_generacion,
    tipoDte,
    fecEmi: dte.identificacion.fecEmi,
    fechaSello,
    fechaEvento: fechaDelEventoInvalidacion(tipoDte, dte.identificacion.fecEmi, hoy),
    plazo: { ...plazo, vencido: hoy > plazo.limite },
    reemplazoRequeridoEnTipos: TIPOS_SIN_REEMPLAZO.has(tipoDte) ? [] : [1, 3],
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
      ...extra,
    },
  };
}

function resultadoPersistido(evento) {
  const respuestaHacienda = evento.respuesta_json ? JSON.parse(evento.respuesta_json) : undefined;
  if (evento.estado === 'ACEPTADO') {
    return respuestaEvento(evento, 200, { estado: 'INVALIDADO', selloRecepcionEvento: evento.sello_recepcion, respuestaHacienda });
  }
  if (evento.estado === 'RECHAZADO') {
    return respuestaEvento(evento, 422, { error: 'Hacienda rechazó el evento de invalidación', code: 'INVALIDATION_REJECTED', respuestaHacienda });
  }
  return null;
}

/**
 * Valida la solicitud contra el estado local y persiste el evento firmable.
 * Devuelve { evento } o { respuesta } cuando la solicitud no procede.
 */
function preparar({ row, motivo, codigoGeneracionReemplazo, claveIdempotencia }) {
  if (row.estado === 'INVALIDADO') {
    const aceptado = db.prepare(
      `SELECT * FROM eventos WHERE dte_codigo_generacion = ? AND tipo = 'INVALIDACION' AND estado = 'ACEPTADO'`
    ).get(row.codigo_generacion);
    return {
      respuesta: {
        status: 409,
        body: {
          error: 'El DTE ya fue invalidado',
          code: 'DTE_ALREADY_INVALIDATED',
          codigoGeneracionEvento: aceptado?.codigo_generacion ?? null,
          selloRecepcionEvento: aceptado?.sello_recepcion ?? null,
        },
      },
    };
  }
  if (row.estado !== 'TRANSMITIDO' || !row.sello_recepcion) {
    return {
      respuesta: {
        status: 409,
        body: { error: `Solo se puede invalidar un DTE TRANSMITIDO con sello (estado actual: ${row.estado})`, code: 'DTE_NOT_INVALIDATABLE' },
      },
    };
  }
  const enCurso = db.prepare(
    `SELECT codigo_generacion FROM eventos
     WHERE dte_codigo_generacion = ? AND tipo = 'INVALIDACION' AND estado IN ('PENDIENTE', 'ERROR_FIRMA', 'FIRMADO', 'SIN_CONFIRMAR')`
  ).get(row.codigo_generacion);
  if (enCurso) {
    return {
      respuesta: {
        status: 409,
        body: {
          error: 'Ya existe un evento de invalidación sin confirmar para este DTE; reintenta con su misma Idempotency-Key',
          code: 'INVALIDATION_IN_PROGRESS',
          codigoGeneracionEvento: enCurso.codigo_generacion,
        },
      },
    };
  }

  if (codigoGeneracionReemplazo) {
    const reemplazo = db.prepare('SELECT estado, sello_recepcion FROM dtes WHERE codigo_generacion = ?').get(codigoGeneracionReemplazo);
    if (!reemplazo || reemplazo.estado !== 'TRANSMITIDO' || !reemplazo.sello_recepcion) {
      return {
        respuesta: {
          status: 409,
          body: {
            error: 'El documento de reemplazo debe estar transmitido y con sello de recepción antes de invalidar',
            code: 'INVALIDATION_REPLACEMENT_NOT_READY',
          },
        },
      };
    }
  }

  const dte = JSON.parse(row.payload_json);
  const previa = vistaPrevia(row);
  if (TIPOS_PLAZO_TRES_MESES.has(previa.tipoDte) && previa.plazo.vencido) {
    // Plazo de calendario exacto: Hacienda no otorgaría sello al evento.
    return {
      respuesta: {
        status: 422,
        body: {
          error: `El plazo para invalidar este documento venció el ${previa.plazo.limite}`,
          code: 'INVALIDATION_DEADLINE_EXCEEDED',
          plazo: previa.plazo,
        },
      },
    };
  }

  let construido;
  try {
    construido = construirEventoInvalidacion({ dte, selloRecibido: row.sello_recepcion, motivo, codigoGeneracionReemplazo });
  } catch (error) {
    return { respuesta: { status: 400, body: { error: error.message, code: error.code || 'INVALID_INVALIDATION_REQUEST' } } };
  }
  const evento = sanitizarProfundo(construido.evento);
  const { valido, errores } = validarEvento('invalidacion', evento);
  if (!valido) {
    return {
      respuesta: {
        status: 422,
        body: { error: 'Evento de invalidación inválido según el schema oficial', code: 'EVENT_SCHEMA_INVALID', detalles: errores },
      },
    };
  }

  db.transaction(() => {
    db.prepare(
      `INSERT INTO eventos (codigo_generacion, tipo, dte_codigo_generacion, estado, payload_json)
       VALUES (?, 'INVALIDACION', ?, 'PENDIENTE', ?)`
    ).run(construido.codigoGeneracion, row.codigo_generacion, JSON.stringify(evento));
    asociarIdentidad(claveIdempotencia, construido.codigoGeneracion);
  })();
  if (previa.plazo.vencido) {
    logger.warn({ codigoGeneracion: row.codigo_generacion, limite: previa.plazo.limite }, 'Invalidación posiblemente fuera de plazo; Hacienda decide');
  }
  return { evento: leerEvento(construido.codigoGeneracion), plazo: previa.plazo };
}

/** Firma (si hace falta), transmite el evento y aplica la respuesta. */
async function transmitir(codigoGeneracion, { plazo } = {}) {
  let evento = leerEvento(codigoGeneracion);
  const persistido = resultadoPersistido(evento);
  if (persistido) return persistido;

  if (!evento.documento_firmado) {
    try {
      const documentoFirmado = await firmadorClient.firmarDocumento(JSON.parse(evento.payload_json));
      actualizarEvento(codigoGeneracion, { documento_firmado: documentoFirmado, estado: 'FIRMADO' });
    } catch (error) {
      actualizarEvento(codigoGeneracion, { estado: 'ERROR_FIRMA', respuesta_json: JSON.stringify({ error: error.message }) });
      return respuestaEvento(leerEvento(codigoGeneracion), 502, {
        error: 'No se pudo firmar el evento de invalidación',
        detalle: error.message,
        code: error.configuracion ? 'FIRMADOR_CONFIGURATION_ERROR' : 'INVALIDATION_SIGNING_FAILED',
      });
    }
    evento = leerEvento(codigoGeneracion);
  }

  let respuesta;
  try {
    respuesta = await haciendaClient.anularDte({
      ambiente: config.emisor.ambiente,
      idEnvio: siguienteIdEnvio(),
      version: manifest.eventos.invalidacion.version,
      documentoFirmado: evento.documento_firmado,
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
    // Sin respuesta: el evento pudo llegar. Se reintenta con el mismo código.
    actualizarEvento(codigoGeneracion, { respuesta_json: JSON.stringify({ error: error.message }) });
    return respuestaEvento(leerEvento(codigoGeneracion), 502, {
      error: 'Hacienda no respondió al evento de invalidación; reintenta con la misma Idempotency-Key',
      code: 'INVALIDATION_NO_RESPONSE',
    });
  }

  const clasificacion = clasificarRespuestaEvento(respuesta, { estadoAceptado: 'PROCESADO' });
  if (clasificacion.resultado === 'ACEPTADO') {
    db.transaction(() => {
      actualizarEvento(codigoGeneracion, { estado: 'ACEPTADO', sello_recepcion: clasificacion.selloRecepcion, respuesta_json: JSON.stringify(respuesta) });
      db.prepare(`UPDATE dtes SET estado = 'INVALIDADO', actualizado_en = datetime('now') WHERE codigo_generacion = ?`)
        .run(evento.dte_codigo_generacion);
    })();
    logger.info({ codigoGeneracion: evento.dte_codigo_generacion, evento: codigoGeneracion }, 'DTE invalidado ante Hacienda');
    return resultadoPersistido(leerEvento(codigoGeneracion));
  }
  if (clasificacion.resultado === 'RECHAZADO' && esDuplicado(respuesta)) {
    // El mismo evento ya había llegado (se perdió la respuesta anterior) y no
    // existe un servicio para consultar su sello: se concilia manualmente.
    actualizarEvento(codigoGeneracion, { estado: 'CONCILIACION', respuesta_json: JSON.stringify(respuesta) });
    return respuestaEvento(leerEvento(codigoGeneracion), 409, {
      error: 'Hacienda indica que el evento ya existe; verifica el estado del DTE en la consulta pública antes de actuar',
      code: 'INVALIDATION_REQUIRES_RECONCILIATION',
      respuestaHacienda: respuesta,
    });
  }
  if (clasificacion.resultado === 'RECHAZADO') {
    actualizarEvento(codigoGeneracion, { estado: 'RECHAZADO', respuesta_json: JSON.stringify(respuesta) });
    logger.warn({ codigoGeneracion: evento.dte_codigo_generacion, codigoMsg: clasificacion.codigoMsg }, 'Hacienda rechazó la invalidación');
    return resultadoPersistido(leerEvento(codigoGeneracion));
  }
  actualizarEvento(codigoGeneracion, { estado: 'SIN_CONFIRMAR', respuesta_json: JSON.stringify(respuesta) });
  return respuestaEvento(leerEvento(codigoGeneracion), 502, {
    error: 'Hacienda no confirmó el evento de invalidación (sin sello); reintenta con la misma Idempotency-Key',
    code: 'INVALIDATION_UNCONFIRMED',
    respuestaHacienda: respuesta,
    ...(plazo ? { plazo } : {}),
  });
}

/** Archivo del evento aceptado: JSON firmado más el sello (como el archivo DTE). */
function archivoEvento(evento) {
  if (evento.estado !== 'ACEPTADO' || !evento.documento_firmado || !evento.sello_recepcion) return null;
  return { ...JSON.parse(evento.payload_json), firmaElectronica: evento.documento_firmado, selloRecibido: evento.sello_recepcion };
}

module.exports = { leerEvento, vistaPrevia, preparar, transmitir, archivoEvento, resultadoPersistido };

const { db } = require('../db');
const config = require('../config');
const logger = require('../utils/logger');
const transmisionService = require('./transmisionService');
const issuerContext = require('./issuerContext');
const contingenciaService = require('./contingenciaService');

/**
 * Cola persistida en SQLite que ejecuta la política de reintentos del Manual
 * Técnico v2.0 (3.3) sobre documentos cuya recepción no está confirmada:
 *   CONSULTAR  consulta el estado del mismo codigoGeneracion.
 *   TRANSMITIR reenvía un documento que Hacienda confirmó no haber recibido.
 * La lógica de cada transición vive en transmisionService; aquí solo se
 * programa el siguiente intento.
 */

/** Compatibilidad: encola una acción para un documento (una por documento). */
function encolar(codigoGeneracion, accion, motivo = null) {
  transmisionService.encolar(codigoGeneracion, accion, motivo);
}

function _actualizarEstadoDte(codigoGeneracion, estado, observaciones = null, selloRecepcion = null) {
  db.prepare(
    `UPDATE dtes SET estado = ?, observaciones = ?, sello_recepcion = COALESCE(?, sello_recepcion),
     actualizado_en = datetime('now') WHERE codigo_generacion = ?`
  ).run(estado, observaciones, selloRecepcion, codigoGeneracion);
}

function _quitar(item) {
  db.prepare('DELETE FROM cola_reintentos WHERE id = ?').run(item.id);
}

async function _reprogramar(item, resultado) {
  const intentos = item.intentos + 1;
  if (intentos >= config.retry.maxAttempts) {
    _quitar(item);
    if (resultado.tipo === 'SIN_RESPUESTA') {
      // Hacienda no responde ni a la consulta: se opera en contingencia.
      await contingenciaService.registrarFallaDeConectividad(item.codigo_generacion, { ultimoError: resultado.error });
    } else if (resultado.tipo === 'CONFIGURACION') {
      // Credenciales del API rechazadas: no es una caída de Hacienda ni justifica contingencia.
      _actualizarEstadoDte(item.codigo_generacion, 'RECONCILIACION', JSON.stringify({ ultimoError: resultado.error, tipo: 'CONFIGURACION' }));
      logger.error({ codigoGeneracion: item.codigo_generacion }, 'Hacienda rechaza las credenciales del API (MH_NIT/MH_PASSWORD_API); requiere corregir la configuración');
    } else {
      // Hacienda responde, pero sin confirmar ni negar la recepción.
      _actualizarEstadoDte(item.codigo_generacion, 'RECONCILIACION', JSON.stringify({ ultimoError: resultado.error }));
      logger.error({ codigoGeneracion: item.codigo_generacion }, 'Consulta a Hacienda no concluyente; requiere revisión fiscal');
    }
    return;
  }

  // Se calcula con datetime() de SQLite para comparar en el mismo formato
  // ("YYYY-MM-DD HH:MM:SS") que usa la consulta de pendientes.
  const delaySegundos = Math.max(1, Math.round((config.retry.baseDelayMs * Math.pow(2, intentos - 1)) / 1000));
  db.prepare(
    `UPDATE cola_reintentos SET intentos = ?, proximo_intento = datetime('now', '+' || ? || ' seconds'), ultimo_error = ?
     WHERE id = ?`
  ).run(intentos, delaySegundos, resultado.error ?? null, item.id);
  logger.warn({ codigoGeneracion: item.codigo_generacion, intentos, delaySegundos }, 'Consulta a Hacienda reprogramada');
}

async function _procesarItem(item) {
  const dteRow = db.prepare('SELECT estado, documento_firmado FROM dtes WHERE codigo_generacion = ?').get(item.codigo_generacion);
  if (!dteRow) {
    logger.warn({ item }, 'DTE de la cola no encontrado, se descarta');
    _quitar(item);
    return;
  }

  if (item.accion === 'TRANSMITIR') {
    const transmisibles = ['PENDIENTE_REINTENTO', 'FIRMADO', 'PENDIENTE_RECONCILIACION', 'CONTINGENCIA_REPORTADA'];
    if (!transmisibles.includes(dteRow.estado) || !dteRow.documento_firmado) {
      _quitar(item);
      return;
    }
    // transmitir() deja la siguiente acción en la cola o la limpia si el resultado es final.
    const resultado = await transmisionService.transmitir(item.codigo_generacion, { desdeCola: true });
    if (resultado.reintentar) await _reprogramar(item, resultado);
    return;
  }

  if (item.accion === 'CONSULTAR') {
    if (!['PENDIENTE_RECONCILIACION', 'PENDIENTE_REINTENTO'].includes(dteRow.estado)) {
      _quitar(item);
      return;
    }
    const resultado = await transmisionService.reconciliar(item.codigo_generacion, item.motivo);
    if (resultado.reintentar) await _reprogramar(item, resultado);
    return;
  }

  logger.warn({ item }, 'Acción de cola desconocida, se descarta');
  _quitar(item);
}

/** Worker periódico (ver server.js). */
async function procesarCola() {
  const pendientes = db
    .prepare(`SELECT * FROM cola_reintentos WHERE proximo_intento <= datetime('now') ORDER BY id ASC LIMIT 20`)
    .all();

  for (const item of pendientes) {
    try {
      const { nit } = db.prepare('SELECT nit FROM dtes WHERE codigo_generacion = ?').get(item.codigo_generacion) ?? {};
      await issuerContext.conEmisor(nit, () => _procesarItem(item));
    } catch (err) {
      logger.error({ err: err.message, codigoGeneracion: item.codigo_generacion }, 'Error procesando acción de la cola');
      // Solo si la acción sigue pendiente: una transición ya aplicada no se revierte.
      if (db.prepare('SELECT id FROM cola_reintentos WHERE id = ?').get(item.id)) {
        await _reprogramar(item, { tipo: 'DESCONOCIDO', error: err.message });
      }
    }
  }
}

module.exports = { encolar, procesarCola, _actualizarEstadoDte };

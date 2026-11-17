const axios = require('axios');
const config = require('../config');
const authService = require('./authService');
const logger = require('../utils/logger');
const { verificarVentanaLote } = require('../utils/ventanaHoraria');
const { registrarAccesoExitoso, servicioDeUrl } = require('./accesoHacienda');

/**
 * Error de comunicación con Hacienda, clasificado para la política de
 * reintentos del Manual Técnico v2.0 (sección 3.3):
 *   RED           sin respuesta (timeout, DNS, conexión): consultar estado.
 *   SERVIDOR      5xx: igual que RED, el documento pudo o no ser recibido.
 *   AUTENTICACION token rechazado aun después de renovarlo.
 *   SOLICITUD     4xx sin respuesta semántica (estructura o parámetros).
 */
class HaciendaError extends Error {
  constructor(mensaje, { tipo, httpStatus = null, data = null } = {}) {
    super(mensaje);
    this.name = 'HaciendaError';
    this.tipo = tipo;
    this.httpStatus = httpStatus;
    this.haciendaResponse = data;
  }

  get transitorio() {
    return this.tipo === 'RED' || this.tipo === 'SERVIDOR' || this.tipo === 'AUTENTICACION';
  }
}

/**
 * Un rechazo de Hacienda llega como HTTP 400 con `estado: "RECHAZADO"` en el
 * cuerpo (Manual Técnico 4.2.1). Esa respuesta es un resultado válido que
 * debe clasificarse, no una falla de red que se reintenta.
 */
function esRespuestaSemantica(data) {
  return Boolean(data) && typeof data === 'object' && typeof data.estado === 'string' && data.estado.trim() !== '';
}

function encabezados(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: token.startsWith('Bearer ') ? token : `Bearer ${token}`,
    'User-Agent': config.hacienda.userAgent,
  };
}

async function llamar(metodo, url, body, { timeoutMs = config.hacienda.timeoutMs, renovarToken = true, aceptarNoEncontrado = false } = {}) {
  const token = await authService.obtenerToken();
  let response;
  try {
    response = await axios.request({
      method: metodo,
      url,
      data: body,
      headers: encabezados(token),
      timeout: timeoutMs,
      validateStatus: () => true,
    });
  } catch (err) {
    logger.warn({ url, codigo: err.code }, 'Hacienda no respondió');
    throw new HaciendaError(`Hacienda no respondió (${err.code || err.message})`, { tipo: 'RED' });
  }

  if (response.status === 401) {
    authService.invalidar();
    if (renovarToken) return llamar(metodo, url, body, { timeoutMs, renovarToken: false, aceptarNoEncontrado });
    throw new HaciendaError('Hacienda rechazó el token de autenticación', { tipo: 'AUTENTICACION', httpStatus: 401, data: response.data });
  }
  if (response.status >= 500) {
    logger.warn({ url, httpStatus: response.status }, 'Error del servidor de Hacienda');
    throw new HaciendaError(`Error del servidor de Hacienda (${response.status})`, { tipo: 'SERVIDOR', httpStatus: response.status, data: response.data });
  }
  if (response.status >= 400 && !esRespuestaSemantica(response.data) && !(aceptarNoEncontrado && response.status === 404)) {
    logger.error({ url, httpStatus: response.status, detalle: response.data }, 'Hacienda rechazó la solicitud');
    throw new HaciendaError(`Hacienda rechazó la solicitud (${response.status})`, { tipo: 'SOLICITUD', httpStatus: response.status, data: response.data });
  }
  registrarAccesoExitoso(servicioDeUrl(url));
  return { httpStatus: response.status, data: response.data };
}

/**
 * Transmite UN DTE firmado (modelo uno a uno). POST /fesv/recepciondte
 * Body (Manual Técnico 4.2.1): { ambiente, idEnvio (Integer), version (la
 * de identificacion), tipoDte, documento (JWS), codigoGeneracion }.
 * Devuelve el cuerpo de la respuesta, incluido un RECHAZADO (HTTP 400).
 */
async function transmitirDte({ ambiente, idEnvio, version, tipoDte, documentoFirmado, codigoGeneracion }) {
  const { data } = await llamar('post', config.hacienda.recepcionUrl, {
    ambiente,
    idEnvio,
    version,
    tipoDte,
    documento: documentoFirmado,
    codigoGeneracion,
  });
  return data;
}

/**
 * Transmite un LOTE de DTE firmados (máx. 100). POST /fesv/recepcionlote
 * Body (4.2.2): { ambiente, idEnvio (UUID v4 MAYÚSCULAS), version (del
 * schema de lotes), nitEmisor, documentos[] }. La respuesta solo confirma la
 * recepción del lote; el resultado se obtiene con consultarLoteDte().
 */
async function transmitirLote({ ambiente, idEnvio, version, nitEmisor, documentos }) {
  // Solo advierte: la restricción horaria aplica a facturación cíclica.
  const { dentroDeVentana, ventana } = verificarVentanaLote(ambiente);
  if (!dentroDeVentana) {
    logger.warn({ ambiente, ventana }, 'Envío de lote fuera de la ventana horaria documentada por Hacienda');
  }
  const { data } = await llamar('post', config.hacienda.recepcionLoteUrl, { ambiente, idEnvio, version, nitEmisor, documentos });
  return data;
}

/**
 * Evento de Contingencia. POST /fesv/contingencia, body { nit, documento }.
 * Respuesta (4.4): { estado RECIBIDO|RECHAZADO, fechaHora, mensaje,
 * selloRecibido, observaciones }.
 */
async function transmitirContingencia({ nit, documentoFirmado }) {
  const { data } = await llamar('post', config.hacienda.contingenciaUrl, { nit, documento: documentoFirmado });
  return data;
}

/**
 * Evento de Invalidación. POST /fesv/anulardte,
 * body { ambiente, idEnvio (Integer), version, documento }.
 */
async function anularDte({ ambiente, idEnvio, version, documentoFirmado }) {
  const { data } = await llamar('post', config.hacienda.anulacionUrl, { ambiente, idEnvio, version, documento: documentoFirmado });
  return data;
}

/**
 * Consulta el estado de un DTE (POST, Manual Técnico 4.3.1):
 * body { nitEmisor, tdte, codigoGeneracion }. Devuelve { httpStatus, data }
 * para distinguir un documento inexistente de un error.
 */
async function consultarDte({ nitEmisor, tdte, codigoGeneracion }) {
  return llamar('post', config.hacienda.consultaUrl, { nitEmisor, tdte, codigoGeneracion }, { aceptarNoEncontrado: true });
}

/** GET /fesv/recepcion/consultadtelote/{codigoLote} → { procesados[], rechazados[] }. */
async function consultarLoteDte(codigoLote) {
  const { data } = await llamar('get', `${config.hacienda.consultaLoteUrl}/${encodeURIComponent(codigoLote)}`, undefined);
  return data;
}

module.exports = {
  HaciendaError,
  esRespuestaSemantica,
  transmitirDte,
  transmitirLote,
  transmitirContingencia,
  anularDte,
  consultarLoteDte,
  consultarDte,
};

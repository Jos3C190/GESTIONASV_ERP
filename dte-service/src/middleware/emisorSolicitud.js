/**
 * Multiemisor: identifica al emisor de cada solicitud y aísla sus documentos.
 *
 * - El ERP declara la empresa en `X-DTE-Issuer-NIT`. En un despliegue
 *   multiemisor (sin emisor en el entorno) el encabezado es obligatorio; en uno
 *   heredado de un solo emisor es opcional.
 * - Si la solicitud trae el snapshot del emisor (contrato v2), su NIT debe
 *   coincidir con el encabezado.
 * - `propietarioDocumento` responde 404 cuando un código de generación (de un
 *   DTE o de un evento) pertenece a otro emisor.
 */
const config = require('../config');
const { db } = require('../db');
const issuerRegistry = require('../services/issuerRegistry');

function emisorSolicitud(req, res, next) {
  const encabezado = issuerRegistry.normalizarNit(req.headers['x-dte-issuer-nit'] || '');
  if (!encabezado) {
    if (!config.emisor) {
      return res.status(400).json({ error: 'Indica el emisor en el encabezado X-DTE-Issuer-NIT', code: 'ISSUER_REQUIRED' });
    }
    req.dteIssuerNit = null;
    return next();
  }
  if (!issuerRegistry.autorizado(encabezado)) {
    return res.status(403).json({ error: 'El emisor no está registrado o está desactivado', code: 'UNAUTHORIZED_ISSUER' });
  }
  const nitCuerpo = req.body?.emisor?.nit;
  if (nitCuerpo && issuerRegistry.normalizarNit(nitCuerpo) !== encabezado) {
    return res.status(400).json({ error: 'El emisor del documento no coincide con el de la solicitud', code: 'ISSUER_MISMATCH' });
  }
  req.dteIssuerNit = encabezado;
  return next();
}

const nitDeDte = db.prepare('SELECT nit FROM dtes WHERE codigo_generacion = ?');
const nitDeEvento = db.prepare(
  `SELECT d.nit FROM eventos e JOIN dtes d ON d.codigo_generacion = e.dte_codigo_generacion
   WHERE e.codigo_generacion = ?`
);

function propietarioDocumento(req, res, next, codigoGeneracion) {
  if (!req.dteIssuerNit) return next();
  const fila = nitDeDte.get(codigoGeneracion) || nitDeEvento.get(codigoGeneracion);
  if (fila && fila.nit !== req.dteIssuerNit) {
    return res.status(404).json({ error: 'DTE no encontrado', code: 'DTE_NOT_FOUND' });
  }
  return next();
}

/**
 * Corre el resto de la solicitud con el contexto del emisor (V3d): su modo,
 * su ambiente, sus URLs de Hacienda y sus credenciales. Va después de
 * `emisorSolicitud`; sin encabezado usa el emisor del entorno.
 */
function contextoEmisor(req, res, next) {
  const issuerContext = require('../services/issuerContext');
  issuerContext.conEmisor(req.dteIssuerNit, () => next());
}

module.exports = { contextoEmisor, emisorSolicitud, propietarioDocumento };

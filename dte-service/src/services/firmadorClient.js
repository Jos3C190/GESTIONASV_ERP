const axios = require('axios');
const config = require('../config');
const logger = require('../utils/logger');

const MAX_SIGNED_DOCUMENT_BYTES = 16 * 1024 * 1024;

/**
 * Errores del firmador oficial (Errores.java de svfe-api-firmador) que
 * dependen de la configuración del emisor y no se resuelven reintentando:
 *   803 no existe llave pública / contraseña de la llave privada incorrecta
 *   809 datos requeridos (p. ej. formato de NIT)
 *   812 no se encontró el archivo del certificado
 */
const ERRORES_CONFIGURACION = new Set(['803', '809', '812']);

class FirmadorError extends Error {
  constructor(mensaje, { codigo = null, configuracion = false } = {}) {
    super(mensaje);
    this.name = 'FirmadorError';
    this.codigoFirmador = codigo;
    this.configuracion = configuracion;
  }
}

function mensajeDelFirmador(body) {
  const mensaje = body?.mensaje;
  if (Array.isArray(mensaje)) return mensaje.join('; ');
  return typeof mensaje === 'string' ? mensaje : 'sin detalle';
}

/**
 * El firmador siempre responde HTTP 200 con { status: "OK", body: "<JWS>" }
 * o { status: "ERROR", body: { codigo, mensaje } } (FirmarDocumentoController).
 */
function validarRespuestaFirmador(data) {
  if (data && typeof data === 'object' && !Array.isArray(data) && data.status !== undefined && data.status !== 'OK') {
    const codigo = data.body?.codigo == null ? null : String(data.body.codigo);
    throw new FirmadorError(`El firmador rechazó la solicitud (${codigo ?? 'sin código'}): ${mensajeDelFirmador(data.body)}`, {
      codigo,
      configuracion: ERRORES_CONFIGURACION.has(codigo),
    });
  }

  const documentoFirmado = typeof data === 'string' ? data : data?.body;
  if (typeof documentoFirmado !== 'string' || !documentoFirmado.trim()) {
    throw new FirmadorError('El firmador no devolvió un documento firmado');
  }

  const jws = documentoFirmado.trim();
  if (Buffer.byteLength(jws, 'utf8') > MAX_SIGNED_DOCUMENT_BYTES) {
    throw new FirmadorError('El documento firmado excede el tamaño permitido');
  }
  if (jws.split('.').length !== 3 || jws.split('.').some((segmento) => !segmento)) {
    throw new FirmadorError('El firmador no devolvió un JWS compacto válido');
  }
  return jws;
}

/**
 * Cliente del servicio de firma local (svfe-api-firmador). Nunca se expone a
 * internet. POST /firmardocumento/ con { nit, activo, passwordPri, dteJson };
 * firma con RS512 usando el certificado {nit}.crt del contenedor.
 */
async function firmarDocumento(dteJson) {
  let response;
  try {
    response = await axios.post(
      config.firmador.url,
      {
        nit: config.emisor.nit,
        activo: true,
        passwordPri: config.emisor.passwordPri,
        dteJson,
      },
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 20000,
      }
    );
  } catch (err) {
    logger.error({ err: err.message }, 'El firmador no respondió');
    throw new FirmadorError(`No se pudo firmar el documento: ${err.message}`);
  }

  try {
    return validarRespuestaFirmador(response.data);
  } catch (err) {
    logger.error({ err: err.message, codigoFirmador: err.codigoFirmador }, 'Fallo al firmar el DTE');
    throw err;
  }
}

module.exports = { firmarDocumento, validarRespuestaFirmador, FirmadorError };

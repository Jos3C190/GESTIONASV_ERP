const axios = require('axios');
const config = require('../config');
const logger = require('../utils/logger');
const { registrarAccesoExitoso } = require('./accesoHacienda');

/**
 * Autenticación contra el API de Seguridad de Hacienda (Manual Técnico v2.0,
 * secciones 1.1 y 4.1): POST /seguridad/auth con `user` (NIT) y `pwd` (clave
 * del API, distinta de la clave de la llave privada) en form-urlencoded y
 * header User-Agent. Respuesta exitosa: { status: "OK", body: { token } };
 * los errores controlados llegan con HTTP 200 y status "ERROR".
 *
 * El token dura 24 h en producción y 48 h en pruebas; se renueva cada 12 h
 * con un margen de 10 minutos para no autenticar en cada envío.
 */
class AuthError extends Error {
  constructor(mensaje, { credenciales = false } = {}) {
    super(mensaje);
    this.name = 'AuthError';
    // Credenciales rechazadas: error de configuración, no una caída de Hacienda.
    this.credenciales = credenciales;
  }
}

class AuthService {
  constructor() {
    this._token = null;
    this._expiraEn = 0; // epoch ms
    this._margenMs = 10 * 60 * 1000;
    this._enCurso = null;
  }

  async obtenerToken() {
    if (this._token && Date.now() < this._expiraEn - this._margenMs) {
      return this._token;
    }
    // Una sola autenticación aunque lleguen varias emisiones a la vez.
    if (!this._enCurso) {
      this._enCurso = this._autenticar().finally(() => {
        this._enCurso = null;
      });
    }
    return this._enCurso;
  }

  async _autenticar() {
    let response;
    try {
      response = await axios.post(
        config.hacienda.authUrl,
        new URLSearchParams({
          user: config.emisor.nit,
          pwd: config.emisor.passwordApi,
        }),
        {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': config.hacienda.userAgent },
          timeout: 15000,
          validateStatus: () => true,
        }
      );
    } catch (err) {
      logger.error({ err: err.message }, 'El servicio de autenticación de Hacienda no respondió');
      throw new AuthError(`No se pudo autenticar contra Hacienda: ${err.message}`);
    }

    const data = response.data;
    const token = data?.body?.token;
    if (response.status === 200 && data?.status === 'OK' && typeof token === 'string' && token.trim()) {
      this._token = token.trim();
      this._expiraEn = Date.now() + 12 * 60 * 60 * 1000;
      registrarAccesoExitoso('autenticacion');
      logger.info({ ambiente: config.emisor.ambiente }, 'Token de Hacienda renovado');
      return this._token;
    }

    const credenciales = response.status === 401 || (response.status === 200 && data?.status === 'ERROR');
    const detalle = data?.message || data?.body?.descripcionMsg || data?.error || `HTTP ${response.status}`;
    logger.error({ httpStatus: response.status, credenciales }, 'Hacienda rechazó la autenticación');
    throw new AuthError(`Hacienda rechazó la autenticación: ${detalle}`, { credenciales });
  }

  /**
   * Prueba de conexión del panel: autentica de nuevo aunque haya token
   * vigente (si la autenticación responde, el nuevo token reemplaza al
   * anterior). No emite nada.
   */
  async probarAutenticacion() {
    return this._autenticar();
  }

  /** Fuerza la renovación del token (p. ej. si Hacienda responde 401). */
  invalidar() {
    this._token = null;
    this._expiraEn = 0;
  }
}

module.exports = new AuthService();
module.exports.AuthError = AuthError;

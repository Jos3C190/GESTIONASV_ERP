const axios = require('axios');
const config = require('../config');
const issuerContext = require('./issuerContext');
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

/**
 * Un token por emisor (V3d): cada empresa se autentica con su NIT y su
 * contraseña de la API, en el host de su modo. El emisor sale del contexto.
 */
class AuthService {
  constructor() {
    this._sesiones = new Map();
    this._margenMs = 10 * 60 * 1000;
  }

  _sesion() {
    const contexto = issuerContext.actual();
    const clave = `${contexto.nit ?? ''}:${contexto.modo}`;
    if (!this._sesiones.has(clave)) this._sesiones.set(clave, { token: null, expiraEn: 0, enCurso: null });
    return { sesion: this._sesiones.get(clave), contexto };
  }

  async obtenerToken() {
    const { sesion, contexto } = this._sesion();
    if (sesion.token && Date.now() < sesion.expiraEn - this._margenMs) {
      return sesion.token;
    }
    // Una sola autenticación por emisor aunque lleguen varias emisiones a la vez.
    if (!sesion.enCurso) {
      sesion.enCurso = this._autenticar(sesion, contexto).finally(() => {
        sesion.enCurso = null;
      });
    }
    return sesion.enCurso;
  }

  async _autenticar(sesion, contexto) {
    const credenciales = contexto.credenciales();
    const urls = contexto.hacienda ?? config.hacienda;
    if (!contexto.nit || !credenciales?.passwordApi || !urls?.authUrl) {
      throw new AuthError('El emisor no tiene credenciales de Hacienda configuradas', { credenciales: true });
    }
    let response;
    try {
      response = await axios.post(
        urls.authUrl,
        new URLSearchParams({
          user: contexto.nit,
          pwd: credenciales.passwordApi,
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
      sesion.token = token.trim();
      sesion.expiraEn = Date.now() + 12 * 60 * 60 * 1000;
      registrarAccesoExitoso('autenticacion');
      logger.info({ ambiente: contexto.ambiente, nit: contexto.nit }, 'Token de Hacienda renovado');
      return sesion.token;
    }

    const rechazadas = response.status === 401 || (response.status === 200 && data?.status === 'ERROR');
    const detalle = data?.message || data?.body?.descripcionMsg || data?.error || `HTTP ${response.status}`;
    logger.error({ httpStatus: response.status, credenciales: rechazadas }, 'Hacienda rechazó la autenticación');
    throw new AuthError(`Hacienda rechazó la autenticación: ${detalle}`, { credenciales: rechazadas });
  }

  /**
   * Prueba de conexión del panel: autentica de nuevo aunque haya token
   * vigente (si la autenticación responde, el nuevo token reemplaza al
   * anterior). No emite nada.
   */
  async probarAutenticacion() {
    const { sesion, contexto } = this._sesion();
    return this._autenticar(sesion, contexto);
  }

  /** Fuerza la renovación del token del emisor en curso (p. ej. si Hacienda responde 401). */
  invalidar() {
    const { sesion } = this._sesion();
    sesion.token = null;
    sesion.expiraEn = 0;
  }
}

module.exports = new AuthService();
module.exports.AuthError = AuthError;

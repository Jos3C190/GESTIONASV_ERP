/**
 * Contexto del emisor en curso (bloque V3d del ERP): modo, ambiente, URLs de
 * Hacienda y credenciales de la empresa que emite.
 *
 * Se fija con `conEmisor(nit, fn)` al empezar una emisión (o un reintento de la
 * cola) y lo leen la autenticación, la firma, la identificación y la
 * transmisión con `actual()`. Así cada empresa usa su propio modo y sus propias
 * credenciales sin pasar el emisor por cada función.
 *
 * Sin contexto (despliegue heredado de un solo emisor) todo sale de la
 * configuración del entorno, como antes.
 */
const { AsyncLocalStorage } = require('node:async_hooks');
const config = require('../config');

const almacen = new AsyncLocalStorage();

/** De menor a mayor: un despliegue admite emisores hasta su DTE_MODE. */
const RANGO_MODO = Object.freeze({ simulated: 0, 'hacienda-test': 1, production: 2 });
const AMBIENTE_POR_MODO = Object.freeze({ 'hacienda-test': '00', production: '01' });

function modoPermitido(modo) {
  return RANGO_MODO[modo] !== undefined && RANGO_MODO[modo] <= RANGO_MODO[config.dteMode];
}

function ambienteDe(modo) {
  return modo === 'simulated' ? config.ambiente : AMBIENTE_POR_MODO[modo];
}

function contextoDelEntorno() {
  return {
    nit: config.emisor?.nit ?? null,
    modo: config.dteMode,
    ambiente: config.ambiente,
    hacienda: config.haciendaPorModo(config.dteMode),
    credenciales: () =>
      config.emisor ? { passwordApi: config.emisor.passwordApi, passwordPri: config.emisor.passwordPri } : null,
    heredado: true,
  };
}

/**
 * Corre `fn` con el contexto del emisor registrado `nit`. Un NIT sin registro
 * (el heredado del entorno) usa la configuración del entorno.
 */
function conEmisor(nit, fn) {
  // Se requieren aquí para evitar el ciclo config -> db -> registro al cargar.
  const issuerRegistry = require('./issuerRegistry');
  const issuerCredentials = require('./issuerCredentials');
  const registro = nit ? issuerRegistry.obtener(nit) : null;
  if (!registro) return almacen.run(contextoDelEntorno(), fn);
  let cache;
  const contexto = {
    nit: registro.nit,
    modo: registro.modo,
    ambiente: ambienteDe(registro.modo),
    hacienda: registro.modo === 'simulated' ? null : config.haciendaPorModo(registro.modo),
    // Las contraseñas se descifran solo si se usan, y quedan en memoria del contexto.
    credenciales: () => {
      if (cache === undefined) cache = issuerCredentials.obtener(registro.nit);
      return cache;
    },
    heredado: false,
  };
  return almacen.run(contexto, fn);
}

function actual() {
  return almacen.getStore() ?? contextoDelEntorno();
}

function simulado() {
  return actual().modo === 'simulated';
}

module.exports = { conEmisor, actual, simulado, modoPermitido, ambienteDe, RANGO_MODO };

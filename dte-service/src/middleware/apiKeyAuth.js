const crypto = require('crypto');
const config = require('../config');

/**
 * Autenticación por API Key para el propio microservicio (distinta de la
 * autenticación con Hacienda, que va en authService.js). Protege que
 * cualquiera que llegue a la red donde corre este servicio pueda emitir o
 * anular DTE sin credenciales.
 *
 * Acepta la key en cualquiera de estas dos formas:
 *   Authorization: Bearer <api-key>
 *   X-API-Key: <api-key>
 *
 * La comparación usa crypto.timingSafeEqual para no filtrar información
 * por timing (comparar con === es vulnerable a ataques de temporización
 * cuando se comparan secretos carácter por carácter).
 */
function _extraerApiKey(req) {
  const authHeader = req.headers['authorization'];
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.slice('Bearer '.length).trim();
  }
  const headerKey = req.headers['x-api-key'];
  if (headerKey) return String(headerKey).trim();
  return null;
}

function _buscarRegistro(candidata) {
  if (!candidata) return null;
  const candidataBuf = Buffer.from(candidata);
  return config.security.apiKeyRecords.find((registro) => {
    const validaBuf = Buffer.from(registro.key);
    // timingSafeEqual exige buffers del mismo tamaño; si difieren, ya
    // sabemos que no coincide (comparar longitudes no filtra el secreto).
    if (candidataBuf.length !== validaBuf.length) return false;
    return crypto.timingSafeEqual(candidataBuf, validaBuf);
  }) || null;
}

function apiKeyAuth(req, res, next) {
  if (config.security.authDeshabilitada) {
    req.dteAuth = { scopes: config.security.allScopes };
    return next(); // Solo para desarrollo local explícito, ver .env.example
  }

  const candidata = _extraerApiKey(req);
  const registro = _buscarRegistro(candidata);
  if (!registro) {
    return res.status(401).json({ error: 'API key inválida o ausente. Envíala como "Authorization: Bearer <key>" o "X-API-Key: <key>".' });
  }

  req.dteAuth = { scopes: registro.scopes };
  next();
}

function requireDteScope(scope) {
  return (req, res, next) => {
    if (!req.dteAuth?.scopes?.includes(scope)) {
      return res.status(403).json({ error: `La API key no tiene el scope requerido: ${scope}` });
    }
    next();
  };
}

module.exports = apiKeyAuth;
module.exports.requireDteScope = requireDteScope;

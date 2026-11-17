/**
 * Rate limiting simple, en memoria, por API key (ventana fija). No agrega
 * una dependencia nueva al proyecto — es intencionalmente sencillo, pensado
 * para un microservicio interno con una sola instancia corriendo (como el
 * `docker-compose.yml` de este proyecto).
 *
 * LIMITACIÓN CONOCIDA: el contador vive en memoria del proceso. Si corres
 * más de una instancia detrás de un balanceador (escalado horizontal), cada
 * instancia lleva su propio contador — el límite efectivo termina siendo
 * `limite * cantidad_de_instancias`, no uno global compartido. Para eso
 * necesitarías un store compartido (Redis, etc.) — no incluido aquí a
 * propósito, para no forzar una dependencia de infraestructura que la
 * mayoría de despliegues de un solo contenedor no necesita.
 */
const config = require('../config');
const crypto = require('crypto');

const _contadores = new Map(); // clave -> { count, resetAt }

function _identidadDeLaPeticion(req) {
  // Se limita por API key (ya autenticada por apiKeyAuth, que corre antes);
  // si por algún motivo no hay key (no debería pasar en rutas protegidas),
  // se usa la IP como respaldo.
  const authHeader = req.headers['authorization'];
  let apiKey = null;
  if (authHeader && authHeader.startsWith('Bearer ')) apiKey = authHeader.slice(7).trim();
  else if (req.headers['x-api-key']) apiKey = String(req.headers['x-api-key']).trim();
  if (apiKey) {
    // El contador debe distinguir consumidores sin conservar la credencial
    // completa en memoria ni en dumps de heap.
    return `key:${crypto.createHash('sha256').update(apiKey, 'utf8').digest('hex')}`;
  }
  return req.socket?.remoteAddress || 'desconocido';
}

function rateLimiter(req, res, next) {
  const { maxPeticiones, ventanaMs } = config.security.rateLimit;
  if (!maxPeticiones) return next(); // rate limiting deshabilitado (maxPeticiones=0)

  const clave = _identidadDeLaPeticion(req);
  const ahora = Date.now();

  let entrada = _contadores.get(clave);
  if (!entrada || ahora >= entrada.resetAt) {
    entrada = { count: 0, resetAt: ahora + ventanaMs };
    _contadores.set(clave, entrada);
  }

  entrada.count += 1;

  if (entrada.count > maxPeticiones) {
    const segundosRestantes = Math.ceil((entrada.resetAt - ahora) / 1000);
    res.setHeader('Retry-After', String(segundosRestantes));
    return res.status(429).json({
      error: `Límite de peticiones excedido (máximo ${maxPeticiones} cada ${ventanaMs / 1000}s). Reintenta en ${segundosRestantes}s.`,
    });
  }

  next();
}

/** Solo para tests: vacía los contadores entre casos. */
function reiniciar() {
  _contadores.clear();
}

module.exports = rateLimiter;
module.exports.reiniciar = reiniciar;

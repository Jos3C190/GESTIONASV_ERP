const { reclamar, guardarResultado, hashSolicitud } = require('../services/idempotency');

/**
 * Envuelve emitir() (o cualquier handler que devuelva {status, body}) con
 * soporte de idempotencia vía el header `Idempotency-Key`. Es OPCIONAL:
 * sin ese header, el comportamiento es idéntico a antes (crea un DTE nuevo
 * en cada llamada). Con el header, una repetición exacta de la misma key
 * devuelve el resultado ya guardado en vez de volver a construir/firmar/
 * transmitir — así un reintento de red de tu ERP no duplica el DTE ante
 * Hacienda.
 */
function conIdempotencia(handlerAsync, { revalidarErrorPreIdentidad = false } = {}) {
  return async (req, res) => {
    const rawClave = req.headers['idempotency-key'];
    const clave = typeof rawClave === 'string' ? rawClave.trim() : '';
    if (clave.length < 8 || clave.length > 200) {
      return res.status(400).json({
        error: 'Idempotency-Key es obligatoria en operaciones DTE y debe tener entre 8 y 200 caracteres.',
      });
    }
    const requestHash = clave ? hashSolicitud(req.method, `${req.baseUrl}${req.path}`, req.body) : null;
    const { debeSeguir, existente, enCurso, conflictoSolicitud, reconciliacionRequerida } = reclamar(
      clave,
      requestHash,
      { revalidarErrorPreIdentidad },
    );

    if (!debeSeguir) {
      if (conflictoSolicitud) {
        return res.status(409).json({
          error: 'La Idempotency-Key ya fue usada con una solicitud diferente.',
          code: 'IDEMPOTENCY_KEY_REUSED',
        });
      }
      if (reconciliacionRequerida) {
        return res.status(409).json({
          error: 'La clave tiene un intento vencido sin identidad verificable; requiere conciliación antes de reemitir.',
          code: 'IDEMPOTENCY_RECONCILIATION_REQUIRED',
        });
      }
      if (enCurso) {
        return res.status(409).json({
          error: 'Ya hay una petición en curso con esta misma Idempotency-Key. Espera a que termine antes de reintentar.',
          code: 'IDEMPOTENCY_IN_PROGRESS',
        });
      }
      // Ya se completó antes: se devuelve EXACTAMENTE lo mismo que la primera vez.
      return res.status(existente.status_code).json(JSON.parse(existente.respuesta_json));
    }

    req.dteIdempotency = { clave, codigoGeneracion: existente?.codigo_generacion || null };
    const { status, body } = await handlerAsync(req);
    guardarResultado(clave, status, body, { revalidarErrorPreIdentidad });
    res.status(status).json(body);
  };
}

module.exports = conIdempotencia;

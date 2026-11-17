const { db } = require('../db');
const crypto = require('crypto');

/**
 * Si una clave queda en estado PROCESANDO por más de esto (ej. el proceso
 * se cayó a media transmisión, o el request original nunca terminó), se
 * considera abandonada y se permite reclamarla de nuevo — de lo contrario,
 * una petición fallida a medias bloquearía esa clave para siempre.
 * Debe superar el peor caso de una emisión: firma (20 s) + autenticación
 * (15 s) + transmisión con renovación de token (2 × MH_TIMEOUT_MS).
 */
const VENTANA_PROCESANDO_MS = 120000;
const ESTADO_VALIDACION_REINTENTABLE = 'VALIDACION_REINTENTABLE';

function _antiguedadMs(fechaSqlite) {
  // SQLite guarda "YYYY-MM-DD HH:MM:SS" (espacio, sin zona horaria, en UTC);
  // Date necesita "T" y sufijo "Z" para parsearlo correctamente como UTC.
  const fecha = new Date(fechaSqlite.replace(' ', 'T') + 'Z');
  return Date.now() - fecha.getTime();
}

function _canonico(value) {
  if (Array.isArray(value)) return value.map(_canonico);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, _canonico(value[key])]));
  }
  return value;
}

function hashSolicitud(method, path, body) {
  const canonicalBody = JSON.stringify(_canonico(body ?? null));
  return crypto.createHash('sha256').update(`${method}\n${path}\n${canonicalBody}`, 'utf8').digest('hex');
}

/**
 * Intenta "reclamar" una Idempotency-Key para procesarla. Devuelve:
 *   { debeSeguir: true }  — nadie más la está usando, procesa normal y
 *                           luego llama a guardarResultado().
 *   { debeSeguir: false, existente }         — ya se completó antes; usa
 *                                              existente.status_code y
 *                                              existente.respuesta_json
 *                                              tal cual, sin reprocesar.
 *   { debeSeguir: false, enCurso: true }      — otra petición con la misma
 *                                              key está en curso AHORA;
 *                                              responde 409.
 *
 * Sin `clave` (el caller no mandó el header), siempre debeSeguir=true — la
 * idempotencia es opcional, no obligatoria.
 */
function parsearRespuesta(respuestaJson) {
  try {
    return JSON.parse(respuestaJson || '{}');
  } catch {
    return null;
  }
}

function esErrorPreIdentidadRevalidable(existente, requestHash, habilitado) {
  if (!habilitado || !requestHash || !existente.request_hash || existente.request_hash !== requestHash) return false;
  if (existente.codigo_generacion || existente.status_code !== 400) return false;
  if (!['COMPLETADO', ESTADO_VALIDACION_REINTENTABLE].includes(existente.estado)) return false;
  return parsearRespuesta(existente.respuesta_json)?.code === 'INVALID_DTE_REQUEST';
}

function reclamar(clave, requestHash = null, { revalidarErrorPreIdentidad = false } = {}) {
  if (!clave) return { debeSeguir: true };

  const existente = db.prepare('SELECT * FROM idempotency_keys WHERE clave = ?').get(clave);

  if (existente) {
    if (requestHash && existente.request_hash && requestHash !== existente.request_hash) {
      return { debeSeguir: false, conflictoSolicitud: true };
    }
    if (esErrorPreIdentidadRevalidable(existente, requestHash, revalidarErrorPreIdentidad)) {
      const claim = db.prepare(
        `UPDATE idempotency_keys
         SET estado = 'PROCESANDO', reintentos_validacion = reintentos_validacion + 1,
             actualizado_en = datetime('now')
         WHERE clave = ? AND estado = ? AND status_code = 400
           AND codigo_generacion IS NULL AND request_hash = ? AND respuesta_json = ?`
      ).run(clave, existente.estado, requestHash, existente.respuesta_json);
      if (claim.changes === 1) {
        return {
          debeSeguir: true,
          existente: { ...existente, estado: 'PROCESANDO', reintentos_validacion: existente.reintentos_validacion + 1 },
        };
      }
      return { debeSeguir: false, enCurso: true };
    }
    if (existente.estado === 'COMPLETADO' || existente.estado === 'PENDIENTE'
      || existente.estado === ESTADO_VALIDACION_REINTENTABLE) {
      return { debeSeguir: false, existente };
    }
    if (existente.estado === 'REINTENTABLE') {
      if (!existente.codigo_generacion) {
        return { debeSeguir: false, reconciliacionRequerida: true };
      }
      const claim = db.prepare(
        `UPDATE idempotency_keys SET estado = 'PROCESANDO', actualizado_en = datetime('now')
         WHERE clave = ? AND estado = 'REINTENTABLE' AND actualizado_en = ? AND codigo_generacion = ?`
      ).run(clave, existente.actualizado_en, existente.codigo_generacion);
      if (claim.changes === 1) return { debeSeguir: true, existente: { ...existente, estado: 'PROCESANDO' } };
      return { debeSeguir: false, enCurso: true };
    }
    // PROCESANDO: ¿sigue realmente en curso, o quedó abandonada?
    if (_antiguedadMs(existente.actualizado_en || existente.creado_en) < VENTANA_PROCESANDO_MS) {
      return { debeSeguir: false, enCurso: true };
    }
    // Sin identidad, una fila antigua podría corresponder a un DTE insertado
    // antes de que el proceso cayera. No se crea otra identidad a ciegas.
    if (!existente.codigo_generacion) {
      return { debeSeguir: false, reconciliacionRequerida: true };
    }
    const fechaObservada = existente.actualizado_en || existente.creado_en;
    const claim = db.prepare(
      `UPDATE idempotency_keys SET estado = 'PROCESANDO', actualizado_en = datetime('now')
       WHERE clave = ? AND estado = 'PROCESANDO' AND actualizado_en = ? AND codigo_generacion = ?`
    ).run(clave, fechaObservada, existente.codigo_generacion);
    if (claim.changes === 1) return { debeSeguir: true, existente: { ...existente, estado: 'PROCESANDO' } };
    return { debeSeguir: false, enCurso: true };
  }

  try {
    db.prepare(
      `INSERT INTO idempotency_keys (clave, estado, request_hash) VALUES (?, 'PROCESANDO', ?)`
    ).run(clave, requestHash);
    return { debeSeguir: true };
  } catch (err) {
    // Carrera: dos peticiones con la misma key casi al mismo tiempo. La que
    // pierde la carrera de INSERT trata la otra como "ya en curso".
    const carrera = db.prepare('SELECT clave FROM idempotency_keys WHERE clave = ?').get(clave);
    if (carrera) return { debeSeguir: false, enCurso: true };
    throw err;
  }
}

function asociarIdentidad(clave, codigoGeneracion) {
  if (!clave || !codigoGeneracion) return;
  const result = db.prepare(
    `UPDATE idempotency_keys SET codigo_generacion = ?, actualizado_en = datetime('now')
     WHERE clave = ? AND estado = 'PROCESANDO'
       AND (codigo_generacion IS NULL OR codigo_generacion = ?)`
  ).run(codigoGeneracion, clave, codigoGeneracion);
  if (result.changes !== 1) throw new Error('No se pudo asociar de forma segura la identidad DTE a su clave idempotente');
}

/**
 * Rechazos del emisor (bloque V3b): ocurren antes de reservar identidad y dependen
 * de la configuración del emisor, no de la solicitud. Se libera la clave para que
 * el mismo documento se pueda reintentar con ella cuando la configuración cambie;
 * sin identidad reservada, reintentar no puede duplicar un DTE.
 */
const RECHAZOS_DEL_EMISOR = Object.freeze([
  'ISSUER_REQUIRED',
  'UNAUTHORIZED_ISSUER',
  'ISSUER_INACTIVE',
  'ISSUER_MODE_UNAVAILABLE',
  'DTE_DOCUMENT_TYPE_NOT_ALLOWED',
]);

/** Guarda el resultado y clasifica si es terminal, pendiente o reintentable. */
function guardarResultado(clave, statusCode, body, { revalidarErrorPreIdentidad = false } = {}) {
  if (!clave) return;
  if (RECHAZOS_DEL_EMISOR.includes(body?.code) && !body?.codigoGeneracion) {
    const liberada = db.prepare('DELETE FROM idempotency_keys WHERE clave = ? AND codigo_generacion IS NULL').run(clave);
    if (liberada.changes === 1) return;
  }
  // Solo una operación enlazada a un codigoGeneracion (DTE o evento de
  // invalidación persistido) puede reanudarse sin crear otra identidad.
  const errorPreIdentidad = revalidarErrorPreIdentidad
    && statusCode === 400
    && body?.code === 'INVALID_DTE_REQUEST'
    && !body?.codigoGeneracion;
  const estado = errorPreIdentidad
    ? ESTADO_VALIDACION_REINTENTABLE
    : statusCode >= 500 && body?.codigoGeneracion
    ? 'REINTENTABLE'
    : statusCode === 202
      ? 'PENDIENTE'
      : 'COMPLETADO';
  db.prepare(
    `UPDATE idempotency_keys SET estado = ?, status_code = ?, respuesta_json = ?,
     codigo_generacion = COALESCE(codigo_generacion, ?), actualizado_en = datetime('now')
     WHERE clave = ?`
  ).run(estado, statusCode, JSON.stringify(body), body?.codigoGeneracion || null, clave);
}

module.exports = { reclamar, asociarIdentidad, guardarResultado, hashSolicitud };

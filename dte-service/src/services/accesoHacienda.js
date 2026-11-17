const { db } = require('../db');
const logger = require('../utils/logger');

/**
 * Último acceso exitoso a Hacienda: la última autenticación aceptada o la
 * última respuesta válida de un servicio (transmisión, consulta, evento).
 * Lo muestra la tarjeta «Conexión con Hacienda» del panel. Nunca guarda
 * credenciales ni contenido de la respuesta: solo la fecha y el tipo.
 */
db.exec(`
  CREATE TABLE IF NOT EXISTS estado_hacienda (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
  )
`);

const CLAVE = 'ultimo_acceso_exitoso';

/** `tipo`: 'autenticacion' o el servicio llamado (p. ej. 'recepciondte'). Nunca falla. */
function registrarAccesoExitoso(tipo, ahora = new Date()) {
  try {
    db.prepare(
      `INSERT INTO estado_hacienda (clave, valor, actualizado_en) VALUES (?, ?, datetime('now'))
       ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, actualizado_en = excluded.actualizado_en`
    ).run(CLAVE, JSON.stringify({ en: ahora.toISOString(), tipo: String(tipo).slice(0, 40) }));
  } catch (err) {
    logger.warn({ err: err.message }, 'No se pudo registrar el último acceso a Hacienda');
  }
}

/** { en, tipo } o null si nunca hubo un acceso exitoso. */
function ultimoAccesoExitoso() {
  const fila = db.prepare('SELECT valor FROM estado_hacienda WHERE clave = ?').get(CLAVE);
  if (!fila) return null;
  try {
    const valor = JSON.parse(fila.valor);
    return typeof valor?.en === 'string' ? { en: valor.en, tipo: valor.tipo ?? null } : null;
  } catch {
    return null;
  }
}

/** Nombre corto del servicio a partir de su URL (el último tramo de la ruta). */
function servicioDeUrl(url) {
  try {
    return new URL(url).pathname.split('/').filter(Boolean).pop() || 'hacienda';
  } catch {
    return 'hacienda';
  }
}

module.exports = { registrarAccesoExitoso, ultimoAccesoExitoso, servicioDeUrl };

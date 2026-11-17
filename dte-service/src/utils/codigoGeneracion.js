const { v4: uuidv4 } = require('uuid');

/**
 * Código de Generación: UUID de 36 caracteres (formato 8-4-4-4-12), en MAYÚSCULAS.
 * Es el identificador único de trazabilidad de cada DTE en todo el ecosistema
 * de facturación electrónica (emisor, receptor, Hacienda).
 */
function generarCodigoGeneracion() {
  return uuidv4().toUpperCase();
}

module.exports = { generarCodigoGeneracion };

/**
 * Ruta del archivo SQLite según DTE_MODE: la simulación usa su propio archivo
 * para no mezclar documentos sin validez con correlativos fiscales.
 *
 * Sin dependencias ni validaciones a propósito: la usan el arranque
 * (config/index.js) y scripts/backup-sqlite.js, y el respaldo tiene que leer
 * exactamente la base que abre el servicio aunque falten variables del emisor.
 */
function rutaSqlite(env = process.env) {
  const modo = (env.DTE_MODE || 'hacienda-test').trim().toLowerCase();
  return modo === 'simulated'
    ? (env.DTE_SIMULATION_SQLITE_PATH || './data/dte-simulation.db')
    : (env.SQLITE_PATH || './data/dte.db');
}

module.exports = { rutaSqlite };

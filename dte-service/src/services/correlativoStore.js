/**
 * Indirección para obtener el siguiente correlativo de Número de Control.
 *
 * Por defecto usa un contador EN MEMORIA (Map) — perfecto para tests
 * unitarios, pero NO PERSISTE entre reinicios, así que NUNCA debe usarse
 * en el servidor real. `server.js` llama a `usar()` al arrancar para
 * reemplazar este proveedor por el respaldado en SQLite
 * (`src/db/index.js`), que sí persiste correctamente.
 *
 * Esto existe para que `dteBuilder*.js` (y sus tests) no dependan de que
 * better-sqlite3 esté instalado/compilado sólo para calcular un número.
 */

const _memoria = new Map();

function _proveedorEnMemoria(tipoDte, anio, codEstablecimiento, codPuntoVenta) {
  const clave = `${tipoDte}|${anio}|${codEstablecimiento}|${codPuntoVenta}`;
  const siguiente = (_memoria.get(clave) || 0) + 1;
  _memoria.set(clave, siguiente);
  return siguiente;
}

let _proveedorActivo = _proveedorEnMemoria;

/** Reemplaza el proveedor activo (usado por server.js con el de SQLite real). */
function usar(fn) {
  _proveedorActivo = fn;
}

/** Vuelve al proveedor en memoria (útil entre tests para resetear estado). */
function reiniciarAMemoria() {
  _memoria.clear();
  _proveedorActivo = _proveedorEnMemoria;
}

function obtener(tipoDte, anio, codEstablecimiento, codPuntoVenta) {
  return _proveedorActivo(tipoDte, anio, codEstablecimiento, codPuntoVenta);
}

module.exports = { obtener, usar, reiniciarAMemoria };

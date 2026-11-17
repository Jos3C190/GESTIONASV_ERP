/**
 * Registro de emisores (multiemisor, bloque V3a del ERP).
 *
 * Cada empresa del ERP es un emisor aislado: el ERP la registra aquí con su
 * NIT, su modo y los tipos de DTE que emite. Un emisor registrado solo emite
 * si está activo, si su modo es el del despliegue y si el tipo está habilitado
 * tanto para él como para el despliegue.
 *
 * Compatibilidad: un NIT no registrado que figure en DTE_AUTHORIZED_ISSUER_NITS
 * (configuración heredada de un solo emisor) sigue autorizado.
 */
const { db } = require('../db');
const config = require('../config');
const credenciales = require('./issuerCredentials');

const MODOS = Object.freeze(['simulated', 'hacienda-test', 'production']);
const NIT_REGEX = /^(\d{9}|\d{14})$/;
const TIPO_REGEX = /^\d{2}$/;

db.exec(`
  CREATE TABLE IF NOT EXISTS emisores (
    nit TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    modo TEXT NOT NULL,
    tipos_habilitados TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

class IssuerError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function normalizarNit(nit) {
  return typeof nit === 'string' ? nit.replace(/[\s-]/g, '') : '';
}

function aRegistro(row) {
  if (!row) return null;
  return {
    nit: row.nit,
    nombre: row.nombre,
    modo: row.modo,
    tiposHabilitados: row.tipos_habilitados ? row.tipos_habilitados.split(',') : [],
    activo: row.activo === 1,
    // Nunca las contraseñas: solo si hay credenciales y la huella del certificado.
    credenciales: credenciales.estado(row.nit),
    creadoEn: row.creado_en,
    actualizadoEn: row.actualizado_en,
  };
}

function obtener(nit) {
  return aRegistro(db.prepare('SELECT * FROM emisores WHERE nit = ?').get(normalizarNit(nit)));
}

function listar() {
  return db.prepare('SELECT * FROM emisores ORDER BY nombre').all().map(aRegistro);
}

/** Alta o actualización de un emisor; la hace el ERP al guardar la configuración fiscal. */
function registrar(nit, datos) {
  const limpio = normalizarNit(nit);
  if (!NIT_REGEX.test(limpio)) throw new IssuerError(400, 'INVALID_ISSUER', 'El NIT del emisor debe tener 9 o 14 dígitos');
  const nombre = typeof datos?.nombre === 'string' ? datos.nombre.trim() : '';
  if (!nombre) throw new IssuerError(400, 'INVALID_ISSUER', 'Indica el nombre del emisor');
  if (!MODOS.includes(datos?.modo)) {
    throw new IssuerError(400, 'INVALID_ISSUER_MODE', `El modo debe ser uno de: ${MODOS.join(', ')}`);
  }
  const tipos = Array.isArray(datos?.tiposHabilitados) ? [...new Set(datos.tiposHabilitados)] : [];
  if (tipos.some((tipo) => !TIPO_REGEX.test(tipo))) {
    throw new IssuerError(400, 'INVALID_ISSUER', 'Los tipos de DTE son códigos de dos dígitos');
  }
  const activo = datos?.activo === false ? 0 : 1;
  // Fuera de simulado el emisor firma y se autentica con Hacienda con lo suyo (V3d).
  if (datos?.credenciales) {
    credenciales.guardar(limpio, datos.credenciales);
  } else if (datos.modo !== 'simulated' && !credenciales.estado(limpio).configuradas) {
    throw new IssuerError(
      400,
      'ISSUER_CREDENTIALS_REQUIRED',
      'Un emisor en pruebas o producción necesita sus credenciales de Hacienda y su certificado',
    );
  }
  db.prepare(
    `INSERT INTO emisores (nit, nombre, modo, tipos_habilitados, activo)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(nit) DO UPDATE SET nombre = excluded.nombre, modo = excluded.modo,
       tipos_habilitados = excluded.tipos_habilitados, activo = excluded.activo,
       actualizado_en = datetime('now')`
  ).run(limpio, nombre, datos.modo, tipos.sort().join(','), activo);
  return obtener(limpio);
}

/** Un NIT puede emitir si está registrado y activo, o si es un emisor heredado del entorno. */
function autorizado(nit) {
  const registro = obtener(nit);
  if (registro) return registro.activo;
  return config.security.authorizedIssuerNits.includes(normalizarNit(nit));
}

/**
 * Valida que el emisor pueda emitir este tipo de DTE en este despliegue.
 * Lanza IssuerError con el código que la API devuelve.
 */
function exigirEmision(nit, tipoDte) {
  const limpio = normalizarNit(nit);
  if (!limpio) throw new IssuerError(400, 'ISSUER_REQUIRED', 'La solicitud no indica el emisor');
  const registro = obtener(limpio);
  if (!registro) {
    if (config.security.authorizedIssuerNits.includes(limpio)) return null;
    throw new IssuerError(403, 'UNAUTHORIZED_ISSUER', 'El emisor no está registrado en el servicio DTE');
  }
  if (!registro.activo) throw new IssuerError(403, 'ISSUER_INACTIVE', 'El emisor está desactivado');
  // Varios modos a la vez exigen una sesión con Hacienda por emisor (V3d).
  if (registro.modo !== config.dteMode) {
    throw new IssuerError(
      409,
      'ISSUER_MODE_UNAVAILABLE',
      `El emisor está en modo ${registro.modo} y este despliegue opera en ${config.dteMode}`
    );
  }
  if (!registro.tiposHabilitados.includes(tipoDte)) {
    throw new IssuerError(403, 'DTE_DOCUMENT_TYPE_NOT_ALLOWED', `El tipo de DTE ${tipoDte} no está habilitado para este emisor`);
  }
  return registro;
}

module.exports = { MODOS, IssuerError, obtener, listar, registrar, autorizado, exigirEmision, normalizarNit };

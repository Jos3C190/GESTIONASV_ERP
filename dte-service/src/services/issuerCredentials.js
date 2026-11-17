/**
 * Credenciales de Hacienda por emisor (bloque V3d del ERP).
 *
 * Cada empresa trae su contraseña de la API de Hacienda, la contraseña de la
 * llave privada y su certificado `{nit}.crt` (el XML que entrega Hacienda).
 *
 * - Las contraseñas se guardan cifradas con AES-256-GCM y la clave del
 *   servicio (`DTE_CREDENTIALS_KEY`); solo se descifran en memoria al usarlas.
 * - El certificado se valida (mismo NIT y contraseña privada correcta: el
 *   firmador compara el SHA-512 de la contraseña con `privateKey.clave`) y se
 *   escribe en la carpeta que comparte con el firmador oficial.
 * - Nada secreto sale de este módulo hacia la API: `estado()` solo dice qué hay.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { db } = require('../db');
const config = require('../config');

const VERSION = 'v1';
const MAX_CERTIFICADO_BYTES = 256 * 1024;

db.exec(`
  CREATE TABLE IF NOT EXISTS emisor_credenciales (
    nit TEXT PRIMARY KEY,
    password_api TEXT NOT NULL,
    password_pri TEXT NOT NULL,
    certificado_sha256 TEXT NOT NULL,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

class CredentialsError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function clave() {
  const raw = (config.credenciales.clave || '').trim();
  if (!raw) {
    throw new CredentialsError(
      503,
      'ISSUER_CREDENTIALS_UNAVAILABLE',
      'El servicio DTE no tiene configurada DTE_CREDENTIALS_KEY para guardar credenciales de Hacienda',
    );
  }
  const key = Buffer.from(raw.replace(/-/g, '+').replace(/_/g, '/'), 'base64');
  if (key.length !== 32) {
    throw new CredentialsError(503, 'ISSUER_CREDENTIALS_UNAVAILABLE', 'DTE_CREDENTIALS_KEY debe tener 32 bytes en base64');
  }
  return key;
}

function cifrar(texto) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', clave(), iv);
  const datos = Buffer.concat([cipher.update(texto, 'utf8'), cipher.final()]);
  return `${VERSION}:${Buffer.concat([iv, cipher.getAuthTag(), datos]).toString('base64')}`;
}

function descifrar(valor) {
  const [version, cuerpo] = String(valor).split(':');
  if (version !== VERSION || !cuerpo) throw new Error('Credencial cifrada con un formato desconocido');
  const buffer = Buffer.from(cuerpo, 'base64');
  const decipher = crypto.createDecipheriv('aes-256-gcm', clave(), buffer.subarray(0, 12));
  decipher.setAuthTag(buffer.subarray(12, 28));
  return Buffer.concat([decipher.update(buffer.subarray(28)), decipher.final()]).toString('utf8');
}

/** Primer valor de una etiqueta XML dentro de un fragmento (el certificado es XML de Jackson). */
function etiqueta(xml, nombre) {
  const match = new RegExp(`<${nombre}>([^<]*)</${nombre}>`).exec(xml);
  return match ? match[1].trim() : null;
}

/**
 * Valida el certificado de Hacienda: XML con el NIT del emisor y la llave
 * privada protegida con `passwordPri` (SHA-512 en hexadecimal, como el firmador).
 */
function validarCertificado(nit, certificado, passwordPri) {
  if (certificado.length > MAX_CERTIFICADO_BYTES) {
    throw new CredentialsError(400, 'INVALID_CERTIFICATE', 'El certificado excede 256 KB');
  }
  const xml = certificado.toString('utf8');
  const privada = /<privateKey>([\s\S]*?)<\/privateKey>/.exec(xml);
  const nitCertificado = etiqueta(xml.replace(/<(publicKey|privateKey|certificado)>[\s\S]*?<\/\1>/g, ''), 'nit');
  if (!privada || !nitCertificado || !/<publicKey>/.test(xml)) {
    throw new CredentialsError(400, 'INVALID_CERTIFICATE', 'El archivo no es un certificado de Hacienda (.crt)');
  }
  if (nitCertificado.replace(/[\s-]/g, '') !== nit) {
    throw new CredentialsError(400, 'CERTIFICATE_NIT_MISMATCH', `El certificado es del NIT ${nitCertificado}, no del emisor ${nit}`);
  }
  const esperado = etiqueta(privada[1], 'clave');
  const calculado = crypto.createHash('sha512').update(passwordPri, 'utf8').digest('hex');
  if (!esperado || esperado.toLowerCase() !== calculado) {
    throw new CredentialsError(400, 'INVALID_PRIVATE_KEY_PASSWORD', 'La contraseña de la llave privada no corresponde al certificado');
  }
}

function rutaCertificado(nit) {
  return path.join(config.credenciales.directorioCertificados, `${nit}.crt`);
}

/** Escribe el certificado de forma atómica para que el firmador nunca lea uno a medias. */
function escribirCertificado(nit, certificado) {
  const destino = rutaCertificado(nit);
  fs.mkdirSync(path.dirname(destino), { recursive: true });
  const temporal = `${destino}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(temporal, certificado, { mode: 0o644 });
  fs.renameSync(temporal, destino);
}

/**
 * Guarda las credenciales de un emisor. `datos.certificado` va en base64.
 * Si se omite el certificado se conserva el guardado, pero la contraseña
 * privada nueva debe corresponder a él.
 */
function guardar(nit, datos) {
  const passwordApi = typeof datos?.passwordApi === 'string' ? datos.passwordApi : '';
  const passwordPri = typeof datos?.passwordPri === 'string' ? datos.passwordPri : '';
  if (!passwordApi || !passwordPri) {
    throw new CredentialsError(400, 'INVALID_ISSUER_CREDENTIALS', 'Indica la contraseña de la API y la de la llave privada');
  }
  let certificado;
  if (typeof datos.certificado === 'string' && datos.certificado.trim()) {
    certificado = Buffer.from(datos.certificado, 'base64');
  } else if (fs.existsSync(rutaCertificado(nit))) {
    certificado = fs.readFileSync(rutaCertificado(nit));
  } else {
    throw new CredentialsError(400, 'INVALID_ISSUER_CREDENTIALS', 'Sube el certificado (.crt) del emisor');
  }
  validarCertificado(nit, certificado, passwordPri);
  const cifradas = [cifrar(passwordApi), cifrar(passwordPri)];
  escribirCertificado(nit, certificado);
  db.prepare(
    `INSERT INTO emisor_credenciales (nit, password_api, password_pri, certificado_sha256)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(nit) DO UPDATE SET password_api = excluded.password_api,
       password_pri = excluded.password_pri, certificado_sha256 = excluded.certificado_sha256,
       actualizado_en = datetime('now')`
  ).run(nit, ...cifradas, crypto.createHash('sha256').update(certificado).digest('hex'));
  return estado(nit);
}

/** Lo que se puede mostrar: si hay credenciales y la huella del certificado. */
function estado(nit) {
  const row = db.prepare('SELECT certificado_sha256, actualizado_en FROM emisor_credenciales WHERE nit = ?').get(nit);
  return {
    configuradas: Boolean(row),
    certificadoPresente: fs.existsSync(rutaCertificado(nit)),
    certificadoSha256: row?.certificado_sha256 ?? null,
    actualizadoEn: row?.actualizado_en ?? null,
  };
}

/** Las contraseñas en claro, solo para usarlas en memoria (autenticación y firma). */
function obtener(nit) {
  const row = db.prepare('SELECT password_api, password_pri FROM emisor_credenciales WHERE nit = ?').get(nit);
  if (!row) return null;
  return { passwordApi: descifrar(row.password_api), passwordPri: descifrar(row.password_pri) };
}

function eliminar(nit) {
  db.prepare('DELETE FROM emisor_credenciales WHERE nit = ?').run(nit);
  fs.rmSync(rutaCertificado(nit), { force: true });
}

module.exports = { CredentialsError, guardar, estado, obtener, eliminar, validarCertificado, rutaCertificado };

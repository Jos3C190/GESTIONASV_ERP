const { createHash } = require('crypto');

const FIRMA_PNG = Buffer.from('89504e470d0a1a0a', 'hex');

/**
 * Logo opcional de un render privado ({ logoPngBase64, logoSha256 }): PNG de
 * hasta 1 MB cuyo hash coincide. Devuelve { logoPngBuffer } (null sin logo)
 * o { error } con el mensaje para responder 422.
 */
function leerLogoPdf(body) {
  if (body?.logoPngBase64 === undefined && body?.logoSha256 === undefined) return { logoPngBuffer: null };
  const encoded = body.logoPngBase64;
  const hash = body.logoSha256;
  if (typeof encoded !== 'string' || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)
    || encoded.length > 1500000 || typeof hash !== 'string' || !/^[a-f0-9]{64}$/.test(hash)) {
    return { error: 'Logo PDF inválido' };
  }
  const logoPngBuffer = Buffer.from(encoded, 'base64');
  if (logoPngBuffer.length > 1024 * 1024 || !logoPngBuffer.subarray(0, 8).equals(FIRMA_PNG)
    || createHash('sha256').update(logoPngBuffer).digest('hex') !== hash) {
    return { error: 'Logo PDF corrupto o demasiado grande' };
  }
  return { logoPngBuffer };
}

module.exports = { leerLogoPdf };

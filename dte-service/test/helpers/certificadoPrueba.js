/**
 * Certificado de prueba con el formato del `{nit}.crt` de Hacienda (XML de
 * Jackson, modelo CertificadoMH del firmador oficial): llaves RSA reales en
 * base64 y `privateKey.clave` = SHA-512 en hexadecimal de la contraseña
 * privada. Sirve para probar el registro y, con el firmador, una firma real.
 */
const crypto = require('node:crypto');

function certificadoPrueba(nit, passwordPri) {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
  const publica = publicKey.export({ type: 'spki', format: 'der' }).toString('base64');
  const privada = privateKey.export({ type: 'pkcs8', format: 'der' }).toString('base64');
  const clave = crypto.createHash('sha512').update(passwordPri, 'utf8').digest('hex');
  const xml =
    '<CertificadoMH>' +
    `<_id>${nit}</_id>` +
    `<nit>${nit}</nit>` +
    '<publicKey><keyType>PUBLIC</keyType><algorithm>RSA</algorithm>' +
    `<encodied>${publica}</encodied><format>X.509</format><clave>${clave}</clave></publicKey>` +
    '<privateKey><keyType>PRIVATE</keyType><algorithm>RSA</algorithm>' +
    `<encodied>${privada}</encodied><format>PKCS#8</format><clave>${clave}</clave></privateKey>` +
    '<activo>true</activo>' +
    '</CertificadoMH>';
  return Buffer.from(xml, 'utf8');
}

module.exports = { certificadoPrueba };

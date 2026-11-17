/**
 * Prueba de conexión de un emisor (bloque V3d del ERP).
 *
 * Con el contexto del emisor: autentica contra Hacienda con su NIT y su
 * contraseña de la API, y firma un documento de prueba con el firmador
 * oficial (su certificado y su contraseña privada). No emite nada ni consume
 * números de control. Cada parte informa su resultado por separado.
 */
const issuerContext = require('./issuerContext');
const issuerRegistry = require('./issuerRegistry');
const issuerCredentials = require('./issuerCredentials');
const authService = require('./authService');
const firmadorClient = require('./firmadorClient');

function resultado(ok, mensaje) {
  return { ok, mensaje };
}

async function probar(nit) {
  const registro = issuerRegistry.obtener(nit);
  if (!registro) {
    throw new issuerRegistry.IssuerError(404, 'ISSUER_NOT_FOUND', 'Emisor no registrado');
  }
  if (registro.modo === 'simulated') {
    return {
      nit: registro.nit,
      modo: registro.modo,
      ok: true,
      autenticacion: resultado(true, 'En modo simulado no se usa Hacienda'),
      firma: resultado(true, 'En modo simulado no se usa el firmador'),
    };
  }
  const estado = issuerCredentials.estado(registro.nit);
  return issuerContext.conEmisor(registro.nit, async () => {
    let autenticacion;
    try {
      await authService.probarAutenticacion();
      autenticacion = resultado(true, 'Hacienda aceptó las credenciales de la API');
    } catch (error) {
      autenticacion = resultado(false, error.message);
    }
    let firma;
    if (!estado.certificadoPresente) {
      firma = resultado(false, 'El certificado del emisor no está en el firmador');
    } else {
      try {
        await firmadorClient.firmarDocumento({ prueba: 'conexion', nit: registro.nit, fecha: new Date().toISOString() });
        firma = resultado(true, 'El firmador firmó con el certificado del emisor');
      } catch (error) {
        firma = resultado(false, error.message);
      }
    }
    return {
      nit: registro.nit,
      modo: registro.modo,
      ok: autenticacion.ok && firma.ok,
      autenticacion,
      firma,
    };
  });
}

module.exports = { probar };

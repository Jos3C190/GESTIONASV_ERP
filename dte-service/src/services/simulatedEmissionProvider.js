const crypto = require('crypto');

function base64url(value) {
  return Buffer.from(value).toString('base64url');
}

function emitirSimulado(dte) {
  const canonical = JSON.stringify(dte);
  const digest = crypto.createHash('sha256').update(canonical).digest('hex').toUpperCase();
  const header = base64url(JSON.stringify({ alg: 'SIM', typ: 'JWT', simulation: true }));
  const payload = base64url(JSON.stringify({ codGen: dte.identificacion.codigoGeneracion, digest }));
  const signature = base64url(`SIMULATED-${digest}`);
  return {
    documentoFirmado: `${header}.${payload}.${signature}`,
    simulationMarker: `SIMULATED-${digest.slice(0, 32)}`,
  };
}

/**
 * Escenario `rejected` (DEC-010): el documento conserva su identidad simulada
 * y queda RECHAZADO sin firma. El detalle va en `simulacion`, nunca como
 * respuesta de Hacienda.
 */
function rechazoSimulado() {
  return {
    escenario: 'rejected',
    codigoMsg: 'SIM-RECHAZO',
    descripcionMsg: 'Rechazo simulado: Hacienda no participó y el documento no tiene validez fiscal',
  };
}

module.exports = { emitirSimulado, rechazoSimulado };

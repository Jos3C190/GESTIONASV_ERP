const config = require('../config');
const issuerContext = require('../services/issuerContext');
const { conInstante } = require('../utils/fechaHoraSV');

/**
 * Reloj de demostración (bloque V9b del ERP): la siembra de datos de
 * demostración genera un mes ya pasado y necesita que fecEmi, horEmi y el año
 * del número de control sean los de ese día.
 *
 * Falla cerrado: el encabezado X-DTE-Demo-Clock solo se acepta con
 * DTE_DEMO_CLOCK_ENABLED=true (nunca en DTE_MODE=production) y con un emisor
 * simulado. Fuera de eso se rechaza antes de tocar correlativos o identidad.
 */
const HEADER = 'x-dte-demo-clock';
const UN_DIA_MS = 24 * 60 * 60 * 1000;

function rechazo(res, mensaje, code) {
  return res.status(400).json({ error: mensaje, code });
}

function relojDemostracion(req, res, next) {
  const crudo = req.headers[HEADER];
  if (crudo === undefined) return next();
  if (!config.demoClockEnabled) {
    return rechazo(res, 'El reloj de demostración no está habilitado en este servicio', 'DEMO_CLOCK_NOT_ALLOWED');
  }
  if (!issuerContext.simulado()) {
    return rechazo(res, 'El reloj de demostración solo se acepta con un emisor simulado', 'DEMO_CLOCK_NOT_ALLOWED');
  }
  const instante = new Date(String(crudo).trim());
  if (!Number.isFinite(instante.getTime()) || instante.getTime() > Date.now() + UN_DIA_MS) {
    return rechazo(res, 'X-DTE-Demo-Clock debe ser un instante ISO 8601 que no esté en el futuro', 'DEMO_CLOCK_INVALID');
  }
  return conInstante(instante, () => next());
}

module.exports = { relojDemostracion, HEADER };

const config = require('../config');

/**
 * Escenario de prueba por documento (DEC-010): el backend lo envía en
 * X-DTE-Simulation-Scenario solo para invoices SIMULATED. Nunca lo elige el
 * navegador ni llega por parámetros públicos.
 */
const HEADER = 'x-dte-simulation-scenario';

/** Rutas que aceptan el header, y solo en modo simulated. */
const RUTAS_CON_ESCENARIO = [
  /^\/api\/dte\/(v2\/)?(factura|ccf|nota-credito|nota-debito)$/,
  /^\/api\/dte\/simulacion\/[^/]+\/anular$/,
];

/**
 * Falla cerrado: fuera de simulated, o en una ruta que no lo usa, el header
 * se rechaza antes de tocar idempotencia, correlativos o identidad.
 */
function rechazarEscenarioNoAdmitido(req, res, next) {
  if (req.headers[HEADER] === undefined) return next();
  const ruta = `${req.baseUrl}${req.path}`.replace(/\/+$/, '');
  const admitida = config.dteMode === 'simulated'
    && req.method === 'POST'
    && RUTAS_CON_ESCENARIO.some((patron) => patron.test(ruta));
  if (admitida) return next();
  return res.status(400).json({
    error: config.dteMode === 'simulated'
      ? 'Esta ruta no admite el header X-DTE-Simulation-Scenario'
      : 'El header X-DTE-Simulation-Scenario solo se acepta en modo simulated',
    code: 'SIMULATION_SCENARIO_NOT_ALLOWED',
  });
}

/** Valida el escenario de la operación y lo deja en req.dteSimulationScenario. */
function escenarioSimulacion(operacion) {
  const permitidos = config.simulation.orderScenarios[operacion];
  return (req, res, next) => {
    if (config.dteMode !== 'simulated') {
      req.dteSimulationScenario = null;
      return next();
    }
    const crudo = req.headers[HEADER];
    const escenario = crudo === undefined ? config.simulation.scenario : String(crudo).trim();
    if (!permitidos.includes(escenario)) {
      return res.status(400).json({
        error: `Escenario de simulación desconocido para ${operacion}: ${escenario.slice(0, 40)}`,
        code: 'SIMULATION_SCENARIO_INVALID',
        permitidos,
      });
    }
    req.dteSimulationScenario = escenario;
    next();
  };
}

module.exports = { rechazarEscenarioNoAdmitido, escenarioSimulacion };
